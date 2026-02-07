"""CSV data loader for OHLCV market data."""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.loaders.base import BaseDataLoader
from src.data.schemas import validate_ohlcv

logger = logging.getLogger(__name__)


# Common timestamp column names to detect
TIMESTAMP_COLUMN_NAMES = [
    "timestamp",
    "date",
    "datetime",
    "time",
    "date_time",
    "ts",
]

# Common date formats to try when parsing (ordered by priority)
DATE_FORMATS = [
    "%d/%m/%Y %H:%M",  # DD/MM/YYYY HH:MM (oil_all.csv format)
    "%d/%m/%Y %H:%M:%S",  # DD/MM/YYYY with seconds
    "%Y-%m-%d %H:%M:%S",  # ISO 8601 with time
    "%Y-%m-%dT%H:%M:%S",  # ISO 8601 with T separator
    "%Y-%m-%d %H:%M",  # ISO 8601 without seconds
    "%Y-%m-%d",  # ISO 8601 date only
    "%m/%d/%Y %H:%M",  # MM/DD/YYYY HH:MM (US format)
    "%m/%d/%Y %H:%M:%S",  # MM/DD/YYYY with seconds
]

# Standard OHLCV column name mappings
COLUMN_MAPPINGS = {
    "open": ["open", "o", "open_price"],
    "high": ["high", "h", "high_price"],
    "low": ["low", "l", "low_price"],
    "close": ["close", "c", "close_price", "adj_close", "adj close"],
    "volume": ["volume", "vol", "v"],
}


class CSVLoader(BaseDataLoader):
    """Load OHLCV data from local CSV files.

    Features:
    - Automatic timestamp column detection
    - Multiple date format support
    - Column name normalization
    - Missing value handling
    - Schema validation via pandera
    """

    def __init__(self, validate: bool = True, fill_missing: bool = True):
        """Initialize the CSV loader.

        Args:
            validate: Whether to validate data against OHLCV schema
            fill_missing: Whether to fill missing values
        """
        self.validate = validate
        self.fill_missing = fill_missing

    def load(
        self,
        source: str | Path,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Load OHLCV data from a CSV file.

        Args:
            source: Path to CSV file
            start: Optional start datetime filter
            end: Optional end datetime filter

        Returns:
            DataFrame with datetime index and columns: open, high, low, close, volume

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required columns are missing or data is invalid
        """
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        logger.debug("Loading CSV from %s", path)

        # Load raw CSV
        df = pd.read_csv(path)

        # Normalize column names to lowercase
        df.columns = df.columns.str.lower().str.strip()

        # Detect and parse timestamp column
        df = self._parse_timestamp(df)

        # Drop rows with invalid timestamps (NaT)
        df = df.dropna(subset=["timestamp"])

        # Normalize OHLCV column names
        df = self._normalize_columns(df)
        logger.debug("Columns normalized, rows=%d", len(df))

        # Handle missing values
        if self.fill_missing:
            df = self._handle_missing(df)
            logger.debug("Missing values handled")

        # Set timestamp as index and sort
        df = df.set_index("timestamp").sort_index()

        # Filter by date range
        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]

        # Select only OHLCV columns
        ohlcv_cols = ["open", "high", "low", "close", "volume"]
        df = df[ohlcv_cols]

        # Validate schema
        if self.validate:
            df = validate_ohlcv(df)

        logger.info("Loaded %d rows from %s", len(df), path)

        return df

    def load_multiple(
        self,
        sources: list[str | Path],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Load OHLCV data from multiple CSV files.

        Args:
            sources: List of paths to CSV files
            start: Optional start datetime filter
            end: Optional end datetime filter

        Returns:
            Dictionary mapping file stems to DataFrames
        """
        result = {}
        for source in sources:
            path = Path(source)
            name = path.stem
            result[name] = self.load(source, start, end)
        return result

    def _parse_timestamp(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect and parse the timestamp column.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with 'timestamp' column as datetime

        Raises:
            ValueError: If no timestamp column found or parsing fails
        """
        # Find timestamp column
        ts_col = self._find_timestamp_column(df)
        if ts_col is None:
            raise ValueError(
                f"Could not find timestamp column. Expected one of: {TIMESTAMP_COLUMN_NAMES}"
            )

        # Try parsing with different formats
        ts_series = df[ts_col]
        parsed = self._try_parse_dates(ts_series)

        if parsed is None:
            raise ValueError(
                f"Could not parse timestamps in column '{ts_col}'. "
                f"Tried formats: {DATE_FORMATS}"
            )

        # Rename to standard 'timestamp'
        df = df.copy()
        df["timestamp"] = parsed
        if ts_col != "timestamp":
            df = df.drop(columns=[ts_col])

        return df

    def _find_timestamp_column(self, df: pd.DataFrame) -> str | None:
        """Find the timestamp column in the DataFrame."""
        for col in df.columns:
            if col.lower() in TIMESTAMP_COLUMN_NAMES:
                logger.debug("Found timestamp column: %s", col)
                return col
        logger.debug("No timestamp column found in: %s", list(df.columns))
        return None

    def _try_parse_dates(self, series: pd.Series) -> pd.Series | None:
        """Try parsing dates with multiple formats.

        Args:
            series: Series containing date strings

        Returns:
            Parsed datetime series, or None if all formats fail
        """
        # Try specific formats first (more reliable than auto-detection)
        for fmt in DATE_FORMATS:
            try:
                # Use errors='coerce' to handle occasional bad rows
                parsed = pd.to_datetime(series, format=fmt, errors="coerce")
                # Accept if >95% of values parsed successfully
                valid_ratio = parsed.notna().mean()
                if valid_ratio > 0.95:
                    logger.debug("Date format matched: %s (valid_ratio=%.2f)", fmt, valid_ratio)
                    return parsed
            except (ValueError, TypeError):
                continue

        # Fall back to pandas auto-detection with dayfirst=True (common for financial data)
        try:
            parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
            if parsed.notna().mean() > 0.95:
                return parsed
        except (ValueError, TypeError):
            pass

        # Last resort: pandas auto-detection with default settings
        try:
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() > 0.95:
                return parsed
        except (ValueError, TypeError):
            pass

        return None

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to standard OHLCV names.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with standardized column names

        Raises:
            ValueError: If required columns cannot be found
        """
        df = df.copy()
        rename_map = {}

        for standard_name, alternatives in COLUMN_MAPPINGS.items():
            found = False
            for alt in alternatives:
                if alt in df.columns:
                    if alt != standard_name:
                        rename_map[alt] = standard_name
                    found = True
                    break

            if not found:
                raise ValueError(
                    f"Could not find '{standard_name}' column. "
                    f"Expected one of: {alternatives}"
                )

        if rename_map:
            df = df.rename(columns=rename_map)

        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in OHLCV data.

        Strategy:
        - Forward-fill prices (use last known value)
        - Fill remaining NaN prices with backward-fill
        - Fill volume NaN with 0

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with missing values handled
        """
        df = df.copy()
        price_cols = ["open", "high", "low", "close"]

        # Forward-fill then backward-fill prices
        for col in price_cols:
            if col in df.columns:
                df[col] = df[col].ffill().bfill()

        # Fill volume with 0
        if "volume" in df.columns:
            df["volume"] = df["volume"].fillna(0)

        return df
