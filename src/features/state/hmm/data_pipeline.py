"""Data pipeline for loading and preparing features for state vector training.

Handles:
- Loading pre-computed features from database
- Bar alignment and gap handling
- Feature selection and validation
- Train/validation/test splitting with leakage prevention
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.database.models import ComputedFeature, OHLCVBar, Ticker
from src.features.state.hmm.contracts import FeatureVector, VALID_TIMEFRAMES


@dataclass
class DataSplit:
    """Time-based data split for training.

    Attributes:
        train: Training data DataFrame
        val: Validation data DataFrame
        test: Test data DataFrame
        train_start: Training period start
        train_end: Training period end
        val_start: Validation period start
        val_end: Validation period end
        test_start: Test period start (if test data exists)
        test_end: Test period end (if test data exists)
    """

    train: pd.DataFrame
    val: pd.DataFrame
    test: Optional[pd.DataFrame]
    train_start: datetime
    train_end: datetime
    val_start: datetime
    val_end: datetime
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None

    def __post_init__(self):
        if self.train_end >= self.val_start:
            raise ValueError("Training end must be before validation start")
        if self.test is not None and self.val_end >= self.test_start:
            raise ValueError("Validation end must be before test start")


class FeatureLoader:
    """Load pre-computed features from database."""

    def __init__(self, session: Session):
        """Initialize feature loader.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def load_features(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        feature_names: list[str],
    ) -> pd.DataFrame:
        """Load features from computed_features table.

        Args:
            symbol: Ticker symbol
            timeframe: Bar timeframe
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)
            feature_names: List of feature names to load

        Returns:
            DataFrame with timestamp index and feature columns

        Raises:
            ValueError: If symbol not found or invalid timeframe
        """
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )

        ticker = self.session.execute(
            select(Ticker).where(Ticker.symbol == symbol)
        ).scalar_one_or_none()

        if ticker is None:
            raise ValueError(f"Symbol not found: {symbol}")

        stmt = (
            select(ComputedFeature)
            .where(
                ComputedFeature.ticker_id == ticker.id,
                ComputedFeature.timeframe == timeframe,
                ComputedFeature.timestamp >= start,
                ComputedFeature.timestamp <= end,
            )
            .order_by(ComputedFeature.timestamp)
        )

        features = self.session.execute(stmt).scalars().all()

        if not features:
            return pd.DataFrame(columns=["timestamp"] + feature_names)

        records = []
        for f in features:
            record = {"timestamp": f.timestamp}
            for name in feature_names:
                record[name] = f.features.get(name, np.nan)
            records.append(record)

        df = pd.DataFrame(records)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        return df

    def load_features_multi_symbol(
        self,
        symbols: list[str],
        timeframe: str,
        start: datetime,
        end: datetime,
        feature_names: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Load features for multiple symbols.

        Args:
            symbols: List of ticker symbols
            timeframe: Bar timeframe
            start: Start timestamp
            end: End timestamp
            feature_names: List of feature names

        Returns:
            Dictionary mapping symbol -> DataFrame
        """
        result = {}
        for symbol in symbols:
            try:
                df = self.load_features(symbol, timeframe, start, end, feature_names)
                if not df.empty:
                    result[symbol] = df
            except ValueError:
                continue

        return result


class GapHandler:
    """Handle data gaps in feature time series."""

    def __init__(
        self,
        timeframe: str,
        max_gap_bars: int = 5,
        forward_fill_non_price: bool = True,
    ):
        """Initialize gap handler.

        Args:
            timeframe: Expected bar timeframe
            max_gap_bars: Maximum gap size to forward-fill
            forward_fill_non_price: Whether to forward-fill non-price features
        """
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe '{timeframe}'")

        self.timeframe = timeframe
        self.max_gap_bars = max_gap_bars
        self.forward_fill_non_price = forward_fill_non_price

        self.bar_duration = self._get_bar_duration(timeframe)

    @staticmethod
    def _get_bar_duration(timeframe: str) -> timedelta:
        """Get expected duration between bars."""
        durations = {
            "1Min": timedelta(minutes=1),
            "5Min": timedelta(minutes=5),
            "15Min": timedelta(minutes=15),
            "1Hour": timedelta(hours=1),
            "1Day": timedelta(days=1),
        }
        return durations[timeframe]

    def detect_gaps(self, df: pd.DataFrame) -> pd.Series:
        """Detect gaps in time series.

        Args:
            df: DataFrame with DatetimeIndex

        Returns:
            Boolean series where True indicates a gap before that bar
        """
        if df.empty or len(df) < 2:
            return pd.Series(False, index=df.index)

        time_diffs = df.index.to_series().diff()
        expected = self.bar_duration

        if self.timeframe == "1Day":
            max_expected = timedelta(days=4)
        else:
            tolerance = expected * 0.5
            max_expected = expected + tolerance

        has_gap = time_diffs > max_expected
        has_gap.iloc[0] = False

        return has_gap

    def mark_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add gap marker column to DataFrame.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with 'has_gap' column added
        """
        df = df.copy()
        df["has_gap"] = self.detect_gaps(df)
        return df

    def handle_gaps(
        self,
        df: pd.DataFrame,
        price_features: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Handle gaps by forward-filling or marking.

        Args:
            df: Input DataFrame with features
            price_features: Features that should NOT be forward-filled

        Returns:
            DataFrame with gaps handled
        """
        price_features = price_features or []
        df = self.mark_gaps(df)

        gaps = self.detect_gaps(df)
        gap_sizes = self._compute_gap_sizes(df.index)

        for col in df.columns:
            if col == "has_gap":
                continue

            if col in price_features:
                continue

            if self.forward_fill_non_price:
                fillable = gap_sizes <= self.max_gap_bars
                mask = gaps & fillable
                df.loc[mask, col] = df[col].ffill().loc[mask]

        return df

    def _compute_gap_sizes(self, index: pd.DatetimeIndex) -> pd.Series:
        """Compute gap sizes in bars."""
        if len(index) < 2:
            return pd.Series(0, index=index)

        time_diffs = index.to_series().diff()
        gap_bars = (time_diffs / self.bar_duration).fillna(1).astype(int)
        gap_bars = gap_bars.clip(lower=1)

        return gap_bars


class TimeSplitter:
    """Time-based train/validation/test splitting with leakage prevention."""

    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        gap_bars: int = 0,
    ):
        """Initialize time splitter.

        Args:
            train_ratio: Fraction of data for training
            val_ratio: Fraction of data for validation
            test_ratio: Fraction of data for testing
            gap_bars: Number of bars to skip between splits (prevents leakage)
        """
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
            raise ValueError("Ratios must sum to 1.0")

        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.gap_bars = gap_bars

    def split(self, df: pd.DataFrame) -> DataSplit:
        """Split DataFrame into train/val/test sets.

        Args:
            df: DataFrame with DatetimeIndex, sorted by time

        Returns:
            DataSplit with train, val, and test DataFrames

        Raises:
            ValueError: If DataFrame is too small to split
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")

        n = len(df)
        min_samples = 3 + 2 * self.gap_bars
        if n < min_samples:
            raise ValueError(
                f"DataFrame too small to split. Need at least {min_samples} rows."
            )

        train_end_idx = int(n * self.train_ratio)
        val_end_idx = int(n * (self.train_ratio + self.val_ratio))

        val_start_idx = train_end_idx + self.gap_bars
        test_start_idx = val_end_idx + self.gap_bars

        train = df.iloc[:train_end_idx]
        val = df.iloc[val_start_idx:val_end_idx]

        if self.test_ratio > 0 and test_start_idx < n:
            test = df.iloc[test_start_idx:]
            test_start = df.index[test_start_idx]
            test_end = df.index[-1]
        else:
            test = None
            test_start = None
            test_end = None

        return DataSplit(
            train=train,
            val=val,
            test=test,
            train_start=df.index[0],
            train_end=df.index[train_end_idx - 1],
            val_start=df.index[val_start_idx],
            val_end=df.index[val_end_idx - 1],
            test_start=test_start,
            test_end=test_end,
        )

    def walk_forward_splits(
        self,
        df: pd.DataFrame,
        train_window: int,
        val_window: int,
        step: int,
    ) -> list[DataSplit]:
        """Generate walk-forward validation splits.

        Args:
            df: DataFrame with DatetimeIndex
            train_window: Number of bars in training window
            val_window: Number of bars in validation window
            step: Number of bars to step forward between splits

        Returns:
            List of DataSplit objects

        Raises:
            ValueError: If window sizes are invalid
        """
        n = len(df)
        min_size = train_window + val_window + self.gap_bars

        if n < min_size:
            raise ValueError(
                f"DataFrame too small for walk-forward. "
                f"Need at least {min_size} rows."
            )

        splits = []
        start_idx = 0

        while start_idx + min_size <= n:
            train_end_idx = start_idx + train_window
            val_start_idx = train_end_idx + self.gap_bars
            val_end_idx = val_start_idx + val_window

            if val_end_idx > n:
                break

            train = df.iloc[start_idx:train_end_idx]
            val = df.iloc[val_start_idx:val_end_idx]

            split = DataSplit(
                train=train,
                val=val,
                test=None,
                train_start=df.index[start_idx],
                train_end=df.index[train_end_idx - 1],
                val_start=df.index[val_start_idx],
                val_end=df.index[val_end_idx - 1],
            )
            splits.append(split)

            start_idx += step

        return splits


def validate_no_leakage(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: Optional[pd.DataFrame] = None,
) -> bool:
    """Validate that there is no temporal leakage between splits.

    Args:
        train_df: Training DataFrame
        val_df: Validation DataFrame
        test_df: Optional test DataFrame

    Returns:
        True if no leakage detected

    Raises:
        ValueError: If leakage is detected
    """
    if train_df.index.max() >= val_df.index.min():
        raise ValueError(
            f"Leakage detected: train_end ({train_df.index.max()}) >= "
            f"val_start ({val_df.index.min()})"
        )

    if test_df is not None and not test_df.empty:
        if val_df.index.max() >= test_df.index.min():
            raise ValueError(
                f"Leakage detected: val_end ({val_df.index.max()}) >= "
                f"test_start ({test_df.index.min()})"
            )

    return True


def create_feature_vectors(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    feature_names: list[str],
) -> list[FeatureVector]:
    """Convert DataFrame rows to FeatureVector objects.

    Args:
        df: DataFrame with features
        symbol: Ticker symbol
        timeframe: Bar timeframe
        feature_names: Ordered list of feature names

    Returns:
        List of FeatureVector objects
    """
    has_gap_col = "has_gap" in df.columns

    vectors = []
    for ts, row in df.iterrows():
        features = {name: row[name] for name in feature_names if name in row}
        has_gap = row["has_gap"] if has_gap_col else False

        vectors.append(
            FeatureVector(
                symbol=symbol,
                timestamp=ts,
                timeframe=timeframe,
                features=features,
                has_gap=has_gap,
            )
        )

    return vectors
