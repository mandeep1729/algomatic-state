"""Unit tests for OHLCV repository."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.data.database.models import (
    Ticker,
    OHLCVBar,
    DataSyncLog,
    ComputedFeature,
    VALID_TIMEFRAMES,
    VALID_SOURCES,
)
from src.data.database.repository import OHLCVRepository


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def repository(mock_session):
    """Create repository with mock session."""
    return OHLCVRepository(mock_session)


@pytest.fixture
def sample_ticker():
    """Create a sample ticker object."""
    ticker = Ticker(
        id=1,
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    return ticker


@pytest.fixture
def sample_ohlcv_df():
    """Create a sample OHLCV DataFrame."""
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


class TestTickerOperations:
    """Tests for ticker-related operations."""

    def test_get_ticker_normalizes_symbol(self, repository, mock_session):
        """Test that get_ticker normalizes symbol to uppercase."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        repository.get_ticker("aapl")

        # Verify the filter was called with uppercase symbol
        mock_session.query.assert_called_once()

    def test_get_ticker_returns_none_when_not_found(self, repository, mock_session):
        """Test that get_ticker returns None for non-existent ticker."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.get_ticker("UNKNOWN")

        assert result is None

    def test_get_ticker_returns_ticker_when_found(self, repository, mock_session, sample_ticker):
        """Test that get_ticker returns ticker when found."""
        mock_session.query.return_value.filter.return_value.first.return_value = sample_ticker

        result = repository.get_ticker("AAPL")

        assert result == sample_ticker
        assert result.symbol == "AAPL"

    def test_get_or_create_ticker_returns_existing(self, repository, mock_session, sample_ticker):
        """Test that get_or_create_ticker returns existing ticker."""
        mock_session.query.return_value.filter.return_value.first.return_value = sample_ticker

        result = repository.get_or_create_ticker("AAPL")

        assert result == sample_ticker
        mock_session.add.assert_not_called()

    def test_get_or_create_ticker_creates_new(self, repository, mock_session):
        """Test that get_or_create_ticker creates new ticker when not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.get_or_create_ticker(
            "AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_list_tickers_filters_active_only(self, repository, mock_session):
        """Test that list_tickers can filter active only."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        repository.list_tickers(active_only=True)

        mock_session.query.return_value.filter.assert_called_once()

    def test_list_tickers_returns_all(self, repository, mock_session):
        """Test that list_tickers returns all when active_only=False."""
        mock_session.query.return_value.order_by.return_value.all.return_value = []

        repository.list_tickers(active_only=False)

        mock_session.query.return_value.filter.assert_not_called()


class TestOHLCVBarOperations:
    """Tests for OHLCV bar operations."""

    def test_get_latest_timestamp(self, repository, mock_session):
        """Test getting latest timestamp."""
        expected_ts = datetime(2024, 1, 15, 16, 0)
        mock_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = expected_ts

        result = repository.get_latest_timestamp("AAPL", "1Min")

        assert result == expected_ts

    def test_get_latest_timestamp_returns_none_when_no_data(self, repository, mock_session):
        """Test that get_latest_timestamp returns None when no data."""
        mock_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = None

        result = repository.get_latest_timestamp("AAPL", "1Min")

        assert result is None

    def test_get_earliest_timestamp(self, repository, mock_session):
        """Test getting earliest timestamp."""
        expected_ts = datetime(2024, 1, 1, 9, 30)
        mock_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = expected_ts

        result = repository.get_earliest_timestamp("AAPL", "1Min")

        assert result == expected_ts

    def test_get_bar_count(self, repository, mock_session):
        """Test getting bar count."""
        mock_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = 100

        result = repository.get_bar_count("AAPL", "1Min")

        assert result == 100

    def test_get_bar_count_with_date_range(self, repository, mock_session):
        """Test getting bar count with date range filter."""
        mock_session.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value.scalar.return_value = 50

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 15)

        result = repository.get_bar_count("AAPL", "1Min", start=start, end=end)

        assert result == 50

    def test_get_bar_count_returns_zero_when_none(self, repository, mock_session):
        """Test that get_bar_count returns 0 when no data."""
        mock_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = None

        result = repository.get_bar_count("AAPL", "1Min")

        assert result == 0

    def test_get_bars_returns_empty_dataframe_when_no_data(self, repository, mock_session):
        """Test that get_bars returns empty DataFrame when no data."""
        mock_session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = repository.get_bars("AAPL", "1Min")

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_get_bars_returns_dataframe(self, repository, mock_session):
        """Test that get_bars returns properly formatted DataFrame."""
        mock_data = [
            (datetime(2024, 1, 1, 9, 30), 100.0, 101.0, 99.5, 100.5, 1000),
            (datetime(2024, 1, 1, 9, 31), 100.5, 102.0, 100.0, 101.5, 1500),
        ]
        mock_session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = mock_data

        result = repository.get_bars("AAPL", "1Min")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert result.iloc[0]["open"] == 100.0

    def test_bulk_insert_bars_validates_timeframe(self, repository, sample_ohlcv_df):
        """Test that bulk_insert_bars validates timeframe."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            repository.bulk_insert_bars(sample_ohlcv_df, 1, "invalid", "alpaca")

    def test_bulk_insert_bars_validates_source(self, repository, sample_ohlcv_df):
        """Test that bulk_insert_bars validates source."""
        with pytest.raises(ValueError, match="Invalid source"):
            repository.bulk_insert_bars(sample_ohlcv_df, 1, "1Min", "invalid")

    def test_bulk_insert_bars_returns_zero_for_empty_df(self, repository):
        """Test that bulk_insert_bars returns 0 for empty DataFrame."""
        empty_df = pd.DataFrame()

        result = repository.bulk_insert_bars(empty_df, 1, "1Min", "alpaca")

        assert result == 0

    def test_bulk_insert_bars_executes_insert(self, repository, mock_session, sample_ohlcv_df):
        """Test that bulk_insert_bars executes insert statement."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        result = repository.bulk_insert_bars(sample_ohlcv_df, 1, "1Min", "alpaca")

        assert result == 5
        mock_session.execute.assert_called_once()

    def test_delete_bars_returns_zero_when_ticker_not_found(self, repository, mock_session):
        """Test that delete_bars returns 0 when ticker not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.delete_bars("UNKNOWN", "1Min")

        assert result == 0


class TestSyncLogOperations:
    """Tests for sync log operations."""

    def test_get_sync_log(self, repository, mock_session):
        """Test getting sync log."""
        mock_log = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_log

        result = repository.get_sync_log(1, "1Min")

        assert result == mock_log

    def test_update_sync_log_creates_new(self, repository, mock_session):
        """Test that update_sync_log creates new log when not found."""
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            None,  # First call for get_sync_log
            MagicMock(symbol="AAPL"),  # Second call for ticker lookup
        ]

        repository.update_sync_log(
            ticker_id=1,
            timeframe="1Min",
            bars_fetched=100,
            status="success",
        )

        mock_session.add.assert_called_once()

    def test_update_sync_log_updates_existing(self, repository, mock_session):
        """Test that update_sync_log updates existing log."""
        existing_log = MagicMock()
        existing_log.first_synced_timestamp = datetime(2024, 1, 1)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            existing_log,
            MagicMock(symbol="AAPL"),
        ]

        result = repository.update_sync_log(
            ticker_id=1,
            timeframe="1Min",
            last_synced_timestamp=datetime(2024, 1, 15),
            bars_fetched=100,
            status="success",
        )

        # Result should be UTC-normalized
        assert result.last_synced_timestamp == datetime(2024, 1, 15, tzinfo=timezone.utc)
        mock_session.add.assert_not_called()

    def test_update_sync_log_handles_timezone_mismatch(self, repository, mock_session):
        """Test that update_sync_log handles TZ-aware existing vs TZ-naive incoming timestamps.

        This reproduces a bug where PostgreSQL returns TZ-aware timestamps (DateTime(timezone=True))
        but the code passes in TZ-naive timestamps from pandas DataFrames, causing:
        'can't compare offset-naive and offset-aware datetimes'
        """
        existing_log = MagicMock()
        # Existing log has TZ-aware timestamp (as returned by PostgreSQL)
        existing_log.first_synced_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            existing_log,
            MagicMock(symbol="AAPL"),
        ]

        # New fetch has TZ-naive timestamp (as from pandas df.index.min())
        # This used to raise: "can't compare offset-naive and offset-aware datetimes"
        result = repository.update_sync_log(
            ticker_id=1,
            timeframe="1Min",
            first_synced_timestamp=datetime(2023, 12, 15),  # TZ-naive, earlier than existing
            last_synced_timestamp=datetime(2024, 1, 20),  # TZ-naive
            bars_fetched=100,
            status="success",
        )

        # Should pick the earlier timestamp (Dec 15) after normalizing both to UTC
        assert result.first_synced_timestamp == datetime(2023, 12, 15, tzinfo=timezone.utc)
        assert result.last_synced_timestamp == datetime(2024, 1, 20, tzinfo=timezone.utc)


class TestValidSources:
    """Tests for valid source constants."""

    def test_valid_sources_include_aggregated(self):
        """Test that VALID_SOURCES includes 'aggregated'."""
        assert "aggregated" in VALID_SOURCES

    def test_valid_sources_include_alpaca(self):
        """Test that VALID_SOURCES includes 'alpaca'."""
        assert "alpaca" in VALID_SOURCES

    def test_valid_sources_include_csv_import(self):
        """Test that VALID_SOURCES includes 'csv_import'."""
        assert "csv_import" in VALID_SOURCES


class TestValidTimeframes:
    """Tests for valid timeframe constants."""

    def test_valid_timeframes_include_1min(self):
        """Test that VALID_TIMEFRAMES includes '1Min'."""
        assert "1Min" in VALID_TIMEFRAMES

    def test_valid_timeframes_include_5min(self):
        """Test that VALID_TIMEFRAMES includes '5Min'."""
        assert "5Min" in VALID_TIMEFRAMES

    def test_valid_timeframes_include_15min(self):
        """Test that VALID_TIMEFRAMES includes '15Min'."""
        assert "15Min" in VALID_TIMEFRAMES

    def test_valid_timeframes_include_1hour(self):
        """Test that VALID_TIMEFRAMES includes '1Hour'."""
        assert "1Hour" in VALID_TIMEFRAMES

    def test_valid_timeframes_include_1day(self):
        """Test that VALID_TIMEFRAMES includes '1Day'."""
        assert "1Day" in VALID_TIMEFRAMES
