"""Unit tests for DatabaseLoader and aggregation functions."""

from datetime import datetime, timedelta

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.data.loaders.database_loader import (
    DatabaseLoader,
    aggregate_ohlcv,
    AGGREGATABLE_TIMEFRAMES,
    TIMEFRAME_RESAMPLE_MAP,
)


@pytest.fixture
def sample_1min_df():
    """Create sample 1-minute OHLCV data for testing aggregation."""
    # Create 60 minutes of data (1 hour)
    dates = pd.date_range("2024-01-01 09:00", periods=60, freq="1min")
    return pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(60)],
            "high": [101.0 + i * 0.1 for i in range(60)],
            "low": [99.0 + i * 0.1 for i in range(60)],
            "close": [100.5 + i * 0.1 for i in range(60)],
            "volume": [1000 + i * 10 for i in range(60)],
        },
        index=dates,
    )


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    manager = MagicMock()
    manager.get_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    manager.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_alpaca_loader():
    """Create a mock Alpaca loader."""
    return MagicMock()


class TestAggregateOhlcv:
    """Tests for the aggregate_ohlcv function."""

    def test_aggregate_to_5min(self, sample_1min_df):
        """Test aggregation from 1Min to 5Min."""
        result = aggregate_ohlcv(sample_1min_df, "5Min")

        # 60 minutes -> 12 5-minute bars
        assert len(result) == 12
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_aggregate_to_15min(self, sample_1min_df):
        """Test aggregation from 1Min to 15Min."""
        result = aggregate_ohlcv(sample_1min_df, "15Min")

        # 60 minutes -> 4 15-minute bars
        assert len(result) == 4

    def test_aggregate_to_1hour(self, sample_1min_df):
        """Test aggregation from 1Min to 1Hour."""
        result = aggregate_ohlcv(sample_1min_df, "1Hour")

        # 60 minutes -> 1 hourly bar
        assert len(result) == 1

    def test_aggregate_open_is_first(self, sample_1min_df):
        """Test that aggregated open is first value in period."""
        result = aggregate_ohlcv(sample_1min_df, "5Min")

        # First 5-minute bar should have open from first 1-minute bar
        assert result.iloc[0]["open"] == sample_1min_df.iloc[0]["open"]

    def test_aggregate_close_is_last(self, sample_1min_df):
        """Test that aggregated close is last value in period."""
        result = aggregate_ohlcv(sample_1min_df, "5Min")

        # First 5-minute bar should have close from 5th 1-minute bar
        assert result.iloc[0]["close"] == sample_1min_df.iloc[4]["close"]

    def test_aggregate_high_is_max(self, sample_1min_df):
        """Test that aggregated high is max value in period."""
        result = aggregate_ohlcv(sample_1min_df, "5Min")

        # First 5-minute bar should have max high from first 5 bars
        expected_high = sample_1min_df.iloc[:5]["high"].max()
        assert result.iloc[0]["high"] == expected_high

    def test_aggregate_low_is_min(self, sample_1min_df):
        """Test that aggregated low is min value in period."""
        result = aggregate_ohlcv(sample_1min_df, "5Min")

        # First 5-minute bar should have min low from first 5 bars
        expected_low = sample_1min_df.iloc[:5]["low"].min()
        assert result.iloc[0]["low"] == expected_low

    def test_aggregate_volume_is_sum(self, sample_1min_df):
        """Test that aggregated volume is sum of volumes in period."""
        result = aggregate_ohlcv(sample_1min_df, "5Min")

        # First 5-minute bar should have sum of volumes from first 5 bars
        expected_volume = sample_1min_df.iloc[:5]["volume"].sum()
        assert result.iloc[0]["volume"] == expected_volume

    def test_aggregate_invalid_timeframe_raises(self, sample_1min_df):
        """Test that invalid timeframe raises ValueError."""
        with pytest.raises(ValueError, match="Cannot aggregate"):
            aggregate_ohlcv(sample_1min_df, "invalid")

    def test_aggregate_1min_raises(self, sample_1min_df):
        """Test that aggregating to 1Min raises (not in mapping)."""
        with pytest.raises(ValueError):
            aggregate_ohlcv(sample_1min_df, "1Min")

    def test_aggregate_1day_raises(self, sample_1min_df):
        """Test that aggregating to 1Day raises (fetched directly from Alpaca)."""
        with pytest.raises(ValueError):
            aggregate_ohlcv(sample_1min_df, "1Day")

    def test_aggregate_empty_df(self):
        """Test aggregation of empty DataFrame."""
        empty_df = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.DatetimeIndex([], freq="1min"),
        )
        result = aggregate_ohlcv(empty_df, "5Min")
        assert result.empty

    def test_aggregate_handles_partial_periods(self):
        """Test that partial periods are included in aggregation."""
        # Create 7 minutes of data (1 complete + 1 partial 5-min bar)
        dates = pd.date_range("2024-01-01 09:00", periods=7, freq="1min")
        df = pd.DataFrame(
            {
                "open": [100.0] * 7,
                "high": [101.0] * 7,
                "low": [99.0] * 7,
                "close": [100.5] * 7,
                "volume": [1000] * 7,
            },
            index=dates,
        )

        result = aggregate_ohlcv(df, "5Min")

        # Pandas resample includes partial periods
        # First bar: 5 minutes (09:00-09:04), Second bar: 2 minutes (09:05-09:06)
        assert len(result) == 2
        # First bar should have volume of 5000 (5 x 1000)
        assert result.iloc[0]["volume"] == 5000
        # Second bar should have volume of 2000 (2 x 1000)
        assert result.iloc[1]["volume"] == 2000


class TestAggregatableTimeframes:
    """Tests for aggregatable timeframe constants."""

    def test_5min_is_aggregatable(self):
        """Test that 5Min is in aggregatable timeframes."""
        assert "5Min" in AGGREGATABLE_TIMEFRAMES

    def test_15min_is_aggregatable(self):
        """Test that 15Min is in aggregatable timeframes."""
        assert "15Min" in AGGREGATABLE_TIMEFRAMES

    def test_1hour_is_aggregatable(self):
        """Test that 1Hour is in aggregatable timeframes."""
        assert "1Hour" in AGGREGATABLE_TIMEFRAMES

    def test_1min_not_aggregatable(self):
        """Test that 1Min is not in aggregatable timeframes."""
        assert "1Min" not in AGGREGATABLE_TIMEFRAMES

    def test_1day_not_aggregatable(self):
        """Test that 1Day is not in aggregatable timeframes."""
        assert "1Day" not in AGGREGATABLE_TIMEFRAMES


class TestTimeframeResampleMap:
    """Tests for timeframe to resample rule mapping."""

    def test_5min_maps_to_5min(self):
        """Test 5Min maps to pandas '5min' resample rule."""
        assert TIMEFRAME_RESAMPLE_MAP["5Min"] == "5min"

    def test_15min_maps_to_15min(self):
        """Test 15Min maps to pandas '15min' resample rule."""
        assert TIMEFRAME_RESAMPLE_MAP["15Min"] == "15min"

    def test_1hour_maps_to_1h(self):
        """Test 1Hour maps to pandas '1h' resample rule."""
        assert TIMEFRAME_RESAMPLE_MAP["1Hour"] == "1h"


class TestDatabaseLoaderInit:
    """Tests for DatabaseLoader initialization."""

    def test_init_with_defaults(self, mock_db_manager):
        """Test initialization with default parameters."""
        with patch("src.data.loaders.database_loader.get_db_manager", return_value=mock_db_manager):
            loader = DatabaseLoader()

            assert loader.db_manager == mock_db_manager
            assert loader.alpaca_loader is None
            assert loader.validate is True
            assert loader.auto_fetch is True

    def test_init_with_custom_params(self, mock_db_manager, mock_alpaca_loader):
        """Test initialization with custom parameters."""
        loader = DatabaseLoader(
            db_manager=mock_db_manager,
            alpaca_loader=mock_alpaca_loader,
            validate=False,
            auto_fetch=False,
        )

        assert loader.db_manager == mock_db_manager
        assert loader.alpaca_loader == mock_alpaca_loader
        assert loader.validate is False
        assert loader.auto_fetch is False


class TestDatabaseLoaderLoad:
    """Tests for DatabaseLoader.load method."""

    def test_load_invalid_timeframe_raises(self, mock_db_manager):
        """Test that load raises ValueError for invalid timeframe."""
        loader = DatabaseLoader(db_manager=mock_db_manager)

        with pytest.raises(ValueError, match="Invalid timeframe"):
            loader.load("AAPL", timeframe="invalid")

    def test_load_calls_sync_when_auto_fetch(self, mock_db_manager, mock_alpaca_loader):
        """Test that load calls _sync_missing_data when auto_fetch is True."""
        loader = DatabaseLoader(
            db_manager=mock_db_manager,
            alpaca_loader=mock_alpaca_loader,
            auto_fetch=True,
        )

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_bars.return_value = pd.DataFrame()

        with patch.object(loader, "_sync_missing_data") as mock_sync:
            mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

            with patch("src.data.loaders.database_loader.OHLCVRepository", return_value=mock_repo):
                loader.load("AAPL", timeframe="1Min")

            mock_sync.assert_called_once()

    def test_load_skips_sync_when_no_auto_fetch(self, mock_db_manager):
        """Test that load skips sync when auto_fetch is False."""
        loader = DatabaseLoader(
            db_manager=mock_db_manager,
            auto_fetch=False,
        )

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_bars.return_value = pd.DataFrame()

        with patch.object(loader, "_sync_missing_data") as mock_sync:
            mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

            with patch("src.data.loaders.database_loader.OHLCVRepository", return_value=mock_repo):
                loader.load("AAPL", timeframe="1Min")

            mock_sync.assert_not_called()



# TestDatabaseLoaderMapTimeframe was removed — the _map_timeframe method was
# dead code (unused identity mapping) and was removed during Phase 4.2
# consolidation of DatabaseLoader.
