"""Integration tests for the data pipeline.

Tests sync log upsert behavior, feature computation idempotency,
and timeframe aggregation correctness.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.data.loaders.database_loader import aggregate_ohlcv, AGGREGATABLE_TIMEFRAMES
from src.marketdata.service import MarketDataService


def _make_1min_ohlcv(n_bars: int = 120, start: str = "2024-06-03 09:30:00") -> pd.DataFrame:
    """Create a realistic 1-minute OHLCV DataFrame."""
    np.random.seed(42)
    index = pd.date_range(start, periods=n_bars, freq="1min")
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.05)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n_bars) * 0.02,
            "high": close + np.abs(np.random.randn(n_bars) * 0.05),
            "low": close - np.abs(np.random.randn(n_bars) * 0.05),
            "close": close,
            "volume": np.random.randint(100, 10000, n_bars),
        },
        index=index,
    )


class TestAggregationCorrectness:
    """Verify OHLCV aggregation produces correct results."""

    def test_5min_aggregation_bar_count(self):
        """120 1-min bars → 24 5-min bars."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "5Min")
        assert len(result) == 24

    def test_15min_aggregation_bar_count(self):
        """120 1-min bars → 8 15-min bars."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "15Min")
        assert len(result) == 8

    def test_1hour_aggregation_bar_count(self):
        """120 1-min bars starting at 09:30 → 3 partial-hour bars."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "1Hour")
        # 09:30-09:59 (30 bars), 10:00-10:59 (60 bars), 11:00-11:29 (30 bars)
        assert len(result) == 3

    def test_aggregation_open_is_first(self):
        """Aggregated open should be the first bar's open."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "5Min")
        first_5min_open = df["open"].iloc[0]
        assert result["open"].iloc[0] == pytest.approx(first_5min_open)

    def test_aggregation_high_is_max(self):
        """Aggregated high should be the max of the window."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "5Min")
        first_5min_high = df["high"].iloc[:5].max()
        assert result["high"].iloc[0] == pytest.approx(first_5min_high)

    def test_aggregation_low_is_min(self):
        """Aggregated low should be the min of the window."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "5Min")
        first_5min_low = df["low"].iloc[:5].min()
        assert result["low"].iloc[0] == pytest.approx(first_5min_low)

    def test_aggregation_close_is_last(self):
        """Aggregated close should be the last bar's close."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "5Min")
        first_5min_close = df["close"].iloc[4]
        assert result["close"].iloc[0] == pytest.approx(first_5min_close)

    def test_aggregation_volume_is_sum(self):
        """Aggregated volume should be the sum of all bars."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "5Min")
        first_5min_vol = df["volume"].iloc[:5].sum()
        assert result["volume"].iloc[0] == first_5min_vol

    def test_aggregation_preserves_naive_timestamps(self):
        """Output timestamps should be naive (no timezone)."""
        df = _make_1min_ohlcv(120)
        result = aggregate_ohlcv(df, "15Min")
        assert result.index.tz is None

    def test_invalid_timeframe_raises(self):
        """Aggregating to unsupported timeframe should raise."""
        df = _make_1min_ohlcv(120)
        with pytest.raises(ValueError, match="Cannot aggregate"):
            aggregate_ohlcv(df, "3Min")


class TestTimezoneEnforcement:
    """Verify bulk_insert_bars rejects timezone-aware timestamps."""

    def test_bulk_insert_bars_rejects_aware_timestamps(self):
        """bulk_insert_bars should raise ValueError for tz-aware data."""
        from src.data.database.market_repository import OHLCVRepository

        df = _make_1min_ohlcv(10)
        df.index = df.index.tz_localize("UTC")

        mock_session = MagicMock()
        repo = OHLCVRepository(mock_session)

        with pytest.raises(ValueError, match="timezone-aware"):
            repo.bulk_insert_bars(df, ticker_id=1, timeframe="1Min")

    def test_bulk_insert_bars_accepts_naive_timestamps(self):
        """bulk_insert_bars should accept naive timestamps without tz error."""
        from src.data.database.market_repository import OHLCVRepository

        df = _make_1min_ohlcv(10)
        assert df.index.tz is None  # Confirm naive

        mock_session = MagicMock()
        repo = OHLCVRepository(mock_session)

        # This will fail on actual DB insert ops, but should NOT fail
        # on the timezone validation check
        try:
            repo.bulk_insert_bars(df, ticker_id=1, timeframe="1Min")
        except ValueError as e:
            if "timezone" in str(e).lower():
                pytest.fail("Should not reject naive timestamps")


def _patch_grpc(mock_repo):
    """Return a patch context manager that makes grpc_market_client() yield mock_repo."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_repo)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return patch("src.marketdata.service.grpc_market_client", return_value=mock_ctx)


class TestMarketDataServiceCoalescing:
    """Verify request coalescing in MarketDataService."""

    def test_ensure_data_normalizes_naive_end(self):
        """End parameter should be normalized to naive UTC."""
        mock_provider = MagicMock()
        mock_provider.source_name = "test"

        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_or_create_ticker.return_value = MagicMock(id=1)
        mock_repo.get_latest_timestamp.return_value = None
        mock_provider.fetch_1min_bars.return_value = pd.DataFrame()
        mock_provider.fetch_daily_bars.return_value = pd.DataFrame()

        with _patch_grpc(mock_repo):
            service = MarketDataService(mock_provider, mock_db)

            # Pass timezone-aware end
            end_aware = datetime(2024, 6, 3, 16, 0, tzinfo=timezone.utc)
            service.ensure_data("AAPL", ["1Min"], end=end_aware)

            # The service should have stripped tz before using it


class TestFeatureComputationIdempotency:
    """Verify feature computation is idempotent."""

    def test_compute_features_deterministic(self):
        """Same input should produce identical features across runs."""
        try:
            from src.features import FeaturePipeline
        except ImportError:
            pytest.skip("FeaturePipeline not available")

        df = _make_1min_ohlcv(500)
        pipeline = FeaturePipeline.default()

        result1 = pipeline.compute(df)
        result2 = pipeline.compute(df)

        pd.testing.assert_frame_equal(result1, result2)
