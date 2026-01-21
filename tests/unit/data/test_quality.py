"""Unit tests for data quality validation."""

import pandas as pd
import pytest

from src.data.quality import (
    DataQualityReport,
    DataQualityValidator,
    GapInfo,
    OutlierInfo,
    detect_gaps,
    detect_outliers,
    generate_quality_report,
)


@pytest.fixture
def valid_ohlcv_df():
    """Create a valid OHLCV DataFrame with no issues."""
    dates = pd.date_range("2024-01-01 09:30", periods=5, freq="1min")
    return pd.DataFrame(
        {
            "open": [100.0, 100.5, 101.0, 100.5, 101.5],
            "high": [101.0, 102.0, 101.5, 101.0, 102.0],
            "low": [99.5, 100.0, 100.5, 100.0, 101.0],
            "close": [100.5, 101.5, 101.0, 100.5, 101.5],
            "volume": [1000, 1500, 1200, 800, 2000],
        },
        index=dates,
    )


@pytest.fixture
def df_with_gaps():
    """Create a DataFrame with timestamp gaps."""
    # Missing bars at 09:32, 09:33, 09:34 (3 bars gap)
    dates = pd.DatetimeIndex([
        "2024-01-01 09:30",
        "2024-01-01 09:31",
        "2024-01-01 09:35",  # Gap: missing 09:32, 09:33, 09:34
        "2024-01-01 09:36",
    ])
    return pd.DataFrame(
        {
            "open": [100.0, 100.5, 102.0, 102.5],
            "high": [101.0, 102.0, 103.0, 103.5],
            "low": [99.5, 100.0, 101.5, 102.0],
            "close": [100.5, 101.5, 102.5, 103.0],
            "volume": [1000, 1500, 1800, 2000],
        },
        index=dates,
    )


@pytest.fixture
def df_with_outliers():
    """Create a DataFrame with price outliers."""
    dates = pd.date_range("2024-01-01 09:30", periods=5, freq="1min")
    return pd.DataFrame(
        {
            "open": [100.0, 100.5, 115.0, 100.5, 101.5],  # 115.0 is 15% spike
            "high": [101.0, 102.0, 116.0, 101.0, 102.0],
            "low": [99.5, 100.0, 114.0, 100.0, 101.0],
            "close": [100.5, 101.5, 115.5, 100.5, 101.5],  # 115.5 is outlier
            "volume": [1000, 1500, 1200, 800, 2000],
        },
        index=dates,
    )


@pytest.fixture
def df_with_missing_values():
    """Create a DataFrame with missing values."""
    dates = pd.date_range("2024-01-01 09:30", periods=3, freq="1min")
    return pd.DataFrame(
        {
            "open": [100.0, None, 101.0],
            "high": [101.0, 102.0, 101.5],
            "low": [99.5, 100.0, 100.5],
            "close": [100.5, 101.5, 101.0],
            "volume": [1000, None, 1200],
        },
        index=dates,
    )


class TestDataQualityValidator:
    """Test suite for DataQualityValidator."""

    def test_valid_data_passes(self, valid_ohlcv_df):
        """Test that valid data produces a passing report."""
        validator = DataQualityValidator()
        report = validator.validate(valid_ohlcv_df, symbol="AAPL")

        assert report.is_valid
        assert report.has_required_columns
        assert report.dtype_valid
        assert report.high_low_valid
        assert report.total_missing == 0
        assert len(report.gaps) == 0
        assert len(report.outliers) == 0

    def test_empty_dataframe(self):
        """Test validation of empty DataFrame."""
        validator = DataQualityValidator()
        report = validator.validate(pd.DataFrame(), symbol="EMPTY")

        assert not report.is_valid
        assert "empty" in report.issues[0].lower()

    def test_missing_columns_detected(self):
        """Test detection of missing columns."""
        df = pd.DataFrame(
            {"open": [100.0], "high": [101.0], "low": [99.0]},
            index=pd.date_range("2024-01-01", periods=1),
        )
        validator = DataQualityValidator()
        report = validator.validate(df)

        assert not report.has_required_columns
        assert "close" in report.missing_columns
        assert "volume" in report.missing_columns

    def test_invalid_dtypes_detected(self, valid_ohlcv_df):
        """Test detection of invalid data types."""
        df = valid_ohlcv_df.copy()
        df["open"] = df["open"].astype(str)  # Invalid dtype

        validator = DataQualityValidator()
        report = validator.validate(df)

        assert not report.dtype_valid
        assert "open" in str(report.dtype_issues)

    def test_high_low_inconsistency_detected(self):
        """Test detection of high/low consistency violations."""
        dates = pd.date_range("2024-01-01 09:30", periods=2, freq="1min")
        df = pd.DataFrame(
            {
                "open": [100.0, 100.5],
                "high": [99.0, 102.0],  # First high is below open!
                "low": [99.5, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000, 1500],
            },
            index=dates,
        )

        validator = DataQualityValidator()
        report = validator.validate(df)

        assert not report.high_low_valid
        assert report.high_low_violations == 1

    def test_missing_values_detected(self, df_with_missing_values):
        """Test detection of missing values."""
        validator = DataQualityValidator()
        report = validator.validate(df_with_missing_values)

        assert report.total_missing == 2
        assert report.missing_values.get("open") == 1
        assert report.missing_values.get("volume") == 1

    def test_gaps_detected(self, df_with_gaps):
        """Test detection of timestamp gaps."""
        validator = DataQualityValidator(expected_frequency="1min")
        report = validator.validate(df_with_gaps)

        assert len(report.gaps) == 1
        gap = report.gaps[0]
        assert gap.start == pd.Timestamp("2024-01-01 09:31")
        assert gap.end == pd.Timestamp("2024-01-01 09:35")
        assert gap.missing_bars == 3  # 09:32, 09:33, 09:34

    def test_outliers_detected(self, df_with_outliers):
        """Test detection of price outliers."""
        validator = DataQualityValidator(outlier_threshold=0.10)
        report = validator.validate(df_with_outliers)

        assert len(report.outliers) > 0
        # The spike from 101.5 to 115.0 is ~13% change
        outlier_timestamps = [o.timestamp for o in report.outliers]
        assert pd.Timestamp("2024-01-01 09:32") in outlier_timestamps

    def test_outlier_threshold_configurable(self, df_with_outliers):
        """Test that outlier threshold is configurable."""
        # With 20% threshold, the 15% spike should not be detected
        validator = DataQualityValidator(outlier_threshold=0.20)
        report = validator.validate(df_with_outliers)

        # Filter to only the specific spike at 09:32
        spikes_at_32 = [
            o for o in report.outliers
            if o.timestamp == pd.Timestamp("2024-01-01 09:32")
            and o.change_pct < 0.20
        ]
        assert len(spikes_at_32) == 0


class TestDetectGaps:
    """Test suite for detect_gaps function."""

    def test_no_gaps(self, valid_ohlcv_df):
        """Test that continuous data has no gaps."""
        gaps = detect_gaps(valid_ohlcv_df)
        assert len(gaps) == 0

    def test_detects_gaps(self, df_with_gaps):
        """Test gap detection."""
        gaps = detect_gaps(df_with_gaps, expected_frequency="1min")
        assert len(gaps) == 1
        assert gaps[0].missing_bars == 3

    def test_multiple_gaps(self):
        """Test detection of multiple gaps."""
        dates = pd.DatetimeIndex([
            "2024-01-01 09:30",
            "2024-01-01 09:33",  # Gap 1: missing 09:31, 09:32
            "2024-01-01 09:36",  # Gap 2: missing 09:34, 09:35
        ])
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000, 1200, 1400],
            },
            index=dates,
        )

        gaps = detect_gaps(df, expected_frequency="1min")
        assert len(gaps) == 2


class TestDetectOutliers:
    """Test suite for detect_outliers function."""

    def test_no_outliers(self, valid_ohlcv_df):
        """Test that normal data has no outliers."""
        outliers = detect_outliers(valid_ohlcv_df, threshold=0.10)
        assert len(outliers) == 0

    def test_detects_outliers(self, df_with_outliers):
        """Test outlier detection."""
        outliers = detect_outliers(df_with_outliers, threshold=0.10)
        assert len(outliers) > 0

    def test_outlier_info_populated(self, df_with_outliers):
        """Test that OutlierInfo fields are correctly populated."""
        outliers = detect_outliers(df_with_outliers, threshold=0.10)

        # Find the first outlier
        outlier = outliers[0]
        assert isinstance(outlier.timestamp, pd.Timestamp)
        assert outlier.column in ["open", "high", "low", "close"]
        assert outlier.change_pct > 0.10


class TestGenerateQualityReport:
    """Test suite for generate_quality_report function."""

    def test_generates_report(self, valid_ohlcv_df):
        """Test that function generates a report."""
        report = generate_quality_report(valid_ohlcv_df, symbol="TEST")

        assert isinstance(report, DataQualityReport)
        assert report.symbol == "TEST"
        assert report.total_rows == 5

    def test_report_to_dict(self, valid_ohlcv_df):
        """Test report conversion to dictionary."""
        report = generate_quality_report(valid_ohlcv_df, symbol="TEST")
        result = report.to_dict()

        assert result["symbol"] == "TEST"
        assert result["total_rows"] == 5
        assert "date_range" in result
        assert "columns" in result
        assert "gaps" in result
        assert "outliers" in result

    def test_report_str_representation(self, valid_ohlcv_df):
        """Test report string representation."""
        report = generate_quality_report(valid_ohlcv_df, symbol="TEST")
        str_repr = str(report)

        assert "TEST" in str_repr
        assert "Total rows: 5" in str_repr
        assert "Valid: Yes" in str_repr


class TestGapInfo:
    """Test suite for GapInfo dataclass."""

    def test_gap_duration(self):
        """Test gap_duration property."""
        gap = GapInfo(
            start=pd.Timestamp("2024-01-01 09:30"),
            end=pd.Timestamp("2024-01-01 09:35"),
            expected_bars=5,
            actual_bars=0,
            missing_bars=5,
        )

        assert gap.gap_duration == pd.Timedelta("5min")


class TestDataQualityReportIssues:
    """Test issue reporting in DataQualityReport."""

    def test_multiple_issues_reported(self, df_with_gaps, df_with_outliers):
        """Test that multiple issues are properly reported."""
        # Create a DF with multiple issues
        dates = pd.DatetimeIndex([
            "2024-01-01 09:30",
            "2024-01-01 09:31",
            "2024-01-01 09:35",  # Gap
        ])
        df = pd.DataFrame(
            {
                "open": [100.0, 115.0, 102.0],  # Outlier at second row
                "high": [101.0, 116.0, 103.0],
                "low": [99.0, 114.0, 101.0],
                "close": [100.5, 115.5, 102.5],
                "volume": [1000, 1500, 1800],
            },
            index=dates,
        )

        validator = DataQualityValidator(
            expected_frequency="1min",
            outlier_threshold=0.10,
        )
        report = validator.validate(df)

        # Should have both gap and outlier issues
        issues_str = " ".join(report.issues).lower()
        assert "gap" in issues_str
        assert "outlier" in issues_str
        assert not report.is_valid
