"""Data quality validation and reporting for OHLCV market data."""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class GapInfo:
    """Information about a gap in timestamp data."""

    start: pd.Timestamp
    end: pd.Timestamp
    expected_bars: int
    actual_bars: int
    missing_bars: int

    @property
    def gap_duration(self) -> timedelta:
        """Duration of the gap."""
        return self.end - self.start


@dataclass
class OutlierInfo:
    """Information about a detected outlier."""

    timestamp: pd.Timestamp
    column: str
    value: float
    previous_value: float
    change_pct: float


@dataclass
class DataQualityReport:
    """Comprehensive data quality report."""

    symbol: str
    total_rows: int
    date_range_start: pd.Timestamp | None
    date_range_end: pd.Timestamp | None

    # Column checks
    has_required_columns: bool
    missing_columns: list[str] = field(default_factory=list)

    # Data type checks
    dtype_valid: bool = True
    dtype_issues: list[str] = field(default_factory=list)

    # OHLCV consistency
    high_low_valid: bool = True
    high_low_violations: int = 0

    # Missing values
    missing_values: dict[str, int] = field(default_factory=dict)
    total_missing: int = 0

    # Gaps
    gaps: list[GapInfo] = field(default_factory=list)
    total_gap_bars: int = 0

    # Outliers
    outliers: list[OutlierInfo] = field(default_factory=list)

    # Summary
    is_valid: bool = True
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "symbol": self.symbol,
            "total_rows": self.total_rows,
            "date_range": {
                "start": str(self.date_range_start) if self.date_range_start else None,
                "end": str(self.date_range_end) if self.date_range_end else None,
            },
            "columns": {
                "has_required": self.has_required_columns,
                "missing": self.missing_columns,
            },
            "dtypes": {
                "valid": self.dtype_valid,
                "issues": self.dtype_issues,
            },
            "high_low": {
                "valid": self.high_low_valid,
                "violations": self.high_low_violations,
            },
            "missing_values": {
                "by_column": self.missing_values,
                "total": self.total_missing,
            },
            "gaps": {
                "count": len(self.gaps),
                "total_missing_bars": self.total_gap_bars,
                "details": [
                    {
                        "start": str(g.start),
                        "end": str(g.end),
                        "missing_bars": g.missing_bars,
                    }
                    for g in self.gaps
                ],
            },
            "outliers": {
                "count": len(self.outliers),
                "details": [
                    {
                        "timestamp": str(o.timestamp),
                        "column": o.column,
                        "value": o.value,
                        "previous": o.previous_value,
                        "change_pct": o.change_pct,
                    }
                    for o in self.outliers
                ],
            },
            "is_valid": self.is_valid,
            "issues": self.issues,
        }

    def __str__(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Data Quality Report: {self.symbol}",
            "=" * 50,
            f"Total rows: {self.total_rows}",
            f"Date range: {self.date_range_start} to {self.date_range_end}",
            "",
            f"Valid: {'Yes' if self.is_valid else 'No'}",
        ]

        if self.issues:
            lines.append("")
            lines.append("Issues:")
            for issue in self.issues:
                lines.append(f"  - {issue}")

        if self.gaps:
            lines.append("")
            lines.append(f"Gaps detected: {len(self.gaps)} ({self.total_gap_bars} missing bars)")

        if self.outliers:
            lines.append("")
            lines.append(f"Outliers detected: {len(self.outliers)}")

        return "\n".join(lines)


class DataQualityValidator:
    """Validate data quality and generate reports for OHLCV data."""

    REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

    def __init__(
        self,
        expected_frequency: str = "1min",
        outlier_threshold: float = 0.10,
        max_gap_bars: int = 5,
    ):
        """Initialize the validator.

        Args:
            expected_frequency: Expected bar frequency (pandas offset alias)
            outlier_threshold: Price change threshold for outlier detection (0.10 = 10%)
            max_gap_bars: Maximum allowed gap before flagging as issue
        """
        self.expected_frequency = expected_frequency
        self.outlier_threshold = outlier_threshold
        self.max_gap_bars = max_gap_bars

    def validate(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
    ) -> DataQualityReport:
        """Validate a DataFrame and generate a quality report.

        Args:
            df: OHLCV DataFrame with datetime index
            symbol: Symbol name for the report

        Returns:
            DataQualityReport with validation results
        """
        logger.debug("Validating data quality: symbol=%s, rows=%d", symbol, len(df))
        report = DataQualityReport(
            symbol=symbol,
            total_rows=len(df),
            date_range_start=df.index.min() if len(df) > 0 else None,
            date_range_end=df.index.max() if len(df) > 0 else None,
            has_required_columns=True,
        )

        if df.empty:
            report.is_valid = False
            report.issues.append("DataFrame is empty")
            return report

        # Check required columns
        self._check_columns(df, report)

        # Check data types
        self._check_dtypes(df, report)

        # Check OHLCV consistency (only if dtypes are valid)
        if report.dtype_valid:
            self._check_high_low_consistency(df, report)

        # Check missing values
        self._check_missing_values(df, report)

        # Detect gaps
        self._detect_gaps(df, report)

        # Detect outliers (only if dtypes are valid)
        if report.dtype_valid:
            self._detect_outliers(df, report)

        # Set overall validity
        report.is_valid = (
            report.has_required_columns
            and report.dtype_valid
            and report.high_low_valid
            and report.total_missing == 0
            and len(report.gaps) == 0
            and len(report.outliers) == 0
        )

        if report.issues:
            logger.warning(
                "Data quality issues for %s: %s",
                symbol, "; ".join(report.issues),
            )
        else:
            logger.debug("Data quality validation passed for %s", symbol)

        return report

    def _check_columns(self, df: pd.DataFrame, report: DataQualityReport) -> None:
        """Check for required columns."""
        logger.debug("Checking required columns: %s", self.REQUIRED_COLUMNS)
        missing = []
        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                missing.append(col)

        if missing:
            report.has_required_columns = False
            report.missing_columns = missing
            report.issues.append(f"Missing required columns: {missing}")

    def _check_dtypes(self, df: pd.DataFrame, report: DataQualityReport) -> None:
        """Check data types."""
        # Check index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            report.dtype_valid = False
            report.dtype_issues.append("Index is not DatetimeIndex")
            report.issues.append("Index is not a datetime type")

        # Check numeric columns
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                report.dtype_valid = False
                report.dtype_issues.append(f"{col} is not numeric")
                report.issues.append(f"Column '{col}' is not numeric")

    def _check_high_low_consistency(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> None:
        """Check that high >= max(open, close) and low <= min(open, close)."""
        if not all(c in df.columns for c in ["open", "high", "low", "close"]):
            return

        high_invalid = df["high"] < df[["open", "close"]].max(axis=1)
        low_invalid = df["low"] > df[["open", "close"]].min(axis=1)

        violations = (high_invalid | low_invalid).sum()

        if violations > 0:
            report.high_low_valid = False
            report.high_low_violations = int(violations)
            report.issues.append(f"High/Low consistency violations: {violations} rows")

    def _check_missing_values(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> None:
        """Check for missing values."""
        for col in self.REQUIRED_COLUMNS:
            if col in df.columns:
                missing = df[col].isna().sum()
                if missing > 0:
                    report.missing_values[col] = int(missing)
                    report.total_missing += int(missing)

        if report.total_missing > 0:
            report.issues.append(f"Missing values: {report.total_missing} total")

    def _detect_gaps(self, df: pd.DataFrame, report: DataQualityReport) -> None:
        """Detect gaps in timestamps."""
        if len(df) < 2:
            logger.debug("Gap detection skipped: fewer than 2 rows")
            return

        logger.debug("Detecting gaps with expected frequency: %s", self.expected_frequency)
        # Calculate expected interval
        expected_delta = pd.Timedelta(self.expected_frequency)

        # Get time differences
        time_diffs = df.index.to_series().diff()

        # Find gaps larger than expected
        gap_mask = time_diffs > expected_delta * 1.5
        gap_indices = df.index[gap_mask]

        for i, gap_end in enumerate(gap_indices):
            # Get the index position
            pos = df.index.get_loc(gap_end)
            if pos == 0:
                continue

            gap_start = df.index[pos - 1]
            actual_gap = gap_end - gap_start

            # Calculate expected vs actual bars
            expected_bars = int(actual_gap / expected_delta)
            actual_bars = 1  # We only have start and end
            missing_bars = expected_bars - actual_bars

            if missing_bars > 0:
                gap = GapInfo(
                    start=gap_start,
                    end=gap_end,
                    expected_bars=expected_bars,
                    actual_bars=actual_bars,
                    missing_bars=missing_bars,
                )
                report.gaps.append(gap)
                report.total_gap_bars += missing_bars

        if report.gaps:
            report.issues.append(
                f"Timestamp gaps: {len(report.gaps)} gaps, "
                f"{report.total_gap_bars} missing bars"
            )

    def _detect_outliers(self, df: pd.DataFrame, report: DataQualityReport) -> None:
        """Detect price outliers (spikes > threshold)."""
        price_cols = ["open", "high", "low", "close"]
        available_cols = [c for c in price_cols if c in df.columns]

        if not available_cols or len(df) < 2:
            logger.debug("Outlier detection skipped: insufficient data")
            return

        logger.debug("Detecting outliers with threshold: %.2f%%", self.outlier_threshold * 100)

        for col in available_cols:
            # Calculate percentage changes
            pct_change = df[col].pct_change(fill_method=None).abs()

            # Find values exceeding threshold
            outlier_mask = pct_change > self.outlier_threshold
            outlier_indices = df.index[outlier_mask]

            for ts in outlier_indices:
                pos = df.index.get_loc(ts)
                if pos == 0:
                    continue

                current_val = df.loc[ts, col]
                prev_val = df.iloc[pos - 1][col]
                change = pct_change.loc[ts]

                outlier = OutlierInfo(
                    timestamp=ts,
                    column=col,
                    value=float(current_val),
                    previous_value=float(prev_val),
                    change_pct=float(change),
                )
                report.outliers.append(outlier)

        if report.outliers:
            report.issues.append(
                f"Price outliers: {len(report.outliers)} "
                f"(threshold: {self.outlier_threshold:.0%})"
            )


def detect_gaps(
    df: pd.DataFrame,
    expected_frequency: str = "1min",
) -> list[GapInfo]:
    """Detect gaps in timestamps.

    Args:
        df: DataFrame with datetime index
        expected_frequency: Expected bar frequency

    Returns:
        List of detected gaps
    """
    validator = DataQualityValidator(expected_frequency=expected_frequency)
    report = validator.validate(df)
    return report.gaps


def detect_outliers(
    df: pd.DataFrame,
    threshold: float = 0.10,
) -> list[OutlierInfo]:
    """Detect price outliers.

    Args:
        df: OHLCV DataFrame
        threshold: Price change threshold (0.10 = 10%)

    Returns:
        List of detected outliers
    """
    validator = DataQualityValidator(outlier_threshold=threshold)
    report = validator.validate(df)
    return report.outliers


def generate_quality_report(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    expected_frequency: str = "1min",
    outlier_threshold: float = 0.10,
) -> DataQualityReport:
    """Generate a comprehensive data quality report.

    Args:
        df: OHLCV DataFrame with datetime index
        symbol: Symbol name for the report
        expected_frequency: Expected bar frequency
        outlier_threshold: Price change threshold for outlier detection

    Returns:
        DataQualityReport with all validation results
    """
    validator = DataQualityValidator(
        expected_frequency=expected_frequency,
        outlier_threshold=outlier_threshold,
    )
    return validator.validate(df, symbol)
