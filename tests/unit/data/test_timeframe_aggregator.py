"""Unit tests for TimeframeAggregator."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from src.data.timeframe_aggregator import (
    DEFAULT_TARGET_TIMEFRAMES,
    INTRADAY_AGGREGATABLE,
    TimeframeAggregator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_manager():
    """Create a mock DatabaseManager with session context manager."""
    manager = MagicMock()
    session = MagicMock()
    manager.get_session.return_value.__enter__ = MagicMock(return_value=session)
    manager.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_provider():
    """Create a mock MarketDataProvider."""
    provider = MagicMock()
    provider.source_name = "alpaca"
    provider.fetch_daily_bars.return_value = pd.DataFrame()
    return provider


@pytest.fixture
def sample_1min_df():
    """60 minutes of synthetic 1Min OHLCV data."""
    dates = pd.date_range("2024-01-02 09:30", periods=60, freq="1min")
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
def sample_daily_df():
    """5 days of synthetic daily OHLCV data."""
    dates = pd.date_range("2024-01-02", periods=5, freq="B")
    return pd.DataFrame(
        {
            "open": [150.0 + i for i in range(5)],
            "high": [155.0 + i for i in range(5)],
            "low": [148.0 + i for i in range(5)],
            "close": [153.0 + i for i in range(5)],
            "volume": [5_000_000 + i * 100_000 for i in range(5)],
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_default_target_timeframes(self):
        """Default targets include 15Min, 1Hour, and 1Day."""
        assert "15Min" in DEFAULT_TARGET_TIMEFRAMES
        assert "1Hour" in DEFAULT_TARGET_TIMEFRAMES
        assert "1Day" in DEFAULT_TARGET_TIMEFRAMES

    def test_intraday_aggregatable(self):
        """Intraday list contains only 15Min and 1Hour."""
        assert "15Min" in INTRADAY_AGGREGATABLE
        assert "1Hour" in INTRADAY_AGGREGATABLE
        assert "1Day" not in INTRADAY_AGGREGATABLE
        assert "1Min" not in INTRADAY_AGGREGATABLE


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestTimeframeAggregatorInit:
    """Tests for TimeframeAggregator initialisation."""

    def test_init_with_defaults(self, mock_db_manager):
        """Aggregator stores the db_manager and provider."""
        with patch(
            "src.data.timeframe_aggregator.get_db_manager",
            return_value=mock_db_manager,
        ):
            agg = TimeframeAggregator()
            assert agg.db_manager is mock_db_manager
            assert agg.provider is None

    def test_init_with_provider(self, mock_db_manager, mock_provider):
        """Provider is stored when passed explicitly."""
        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )
        assert agg.provider is mock_provider


# ---------------------------------------------------------------------------
# Intraday aggregation
# ---------------------------------------------------------------------------


class TestAggregateIntraday:
    """Tests for _aggregate_intraday (15Min / 1Hour from 1Min)."""

    def test_inserts_aggregated_bars(self, mock_db_manager, sample_1min_df):
        """Aggregated bars are inserted via bulk_insert_bars."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 4  # 60min / 15 = 4
        mock_ticker = MagicMock()
        mock_ticker.id = 1
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        count = agg._aggregate_intraday(mock_repo, "AAPL", "15Min")

        assert count == 4
        mock_repo.bulk_insert_bars.assert_called_once()
        call_kwargs = mock_repo.bulk_insert_bars.call_args
        assert call_kwargs.kwargs["timeframe"] == "15Min"
        assert call_kwargs.kwargs["source"] == "aggregated"

    def test_skips_when_no_1min_data(self, mock_db_manager):
        """Returns 0 when there are no 1Min bars to aggregate."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_bars.return_value = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

        count = agg._aggregate_intraday(mock_repo, "AAPL", "15Min")

        assert count == 0
        mock_repo.bulk_insert_bars.assert_not_called()

    def test_uses_latest_target_timestamp_as_start(
        self, mock_db_manager, sample_1min_df
    ):
        """When target bars already exist, only 1Min bars after the latest
        target timestamp are fetched."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        existing_ts = datetime(2024, 1, 2, 9, 45)
        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = existing_ts
        mock_repo.get_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 2
        mock_ticker = MagicMock()
        mock_ticker.id = 1
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        agg._aggregate_intraday(mock_repo, "AAPL", "15Min")

        # get_bars should be called with start=existing_ts (stripped tz)
        mock_repo.get_bars.assert_called_once_with("AAPL", "1Min", start=existing_ts)

    def test_handles_timezone_aware_latest_ts(self, mock_db_manager, sample_1min_df):
        """Timezone-aware timestamps from the DB are normalised to naive."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        tz_aware_ts = datetime(2024, 1, 2, 9, 45, tzinfo=timezone.utc)
        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = tz_aware_ts
        mock_repo.get_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 2
        mock_ticker = MagicMock()
        mock_ticker.id = 1
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        agg._aggregate_intraday(mock_repo, "AAPL", "1Hour")

        expected_naive = datetime(2024, 1, 2, 9, 45)
        mock_repo.get_bars.assert_called_once_with("AAPL", "1Min", start=expected_naive)

    def test_updates_sync_log_on_insert(self, mock_db_manager, sample_1min_df):
        """Sync log is updated when bars are inserted."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 4
        mock_ticker = MagicMock()
        mock_ticker.id = 42
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        agg._aggregate_intraday(mock_repo, "AAPL", "15Min")

        mock_repo.update_sync_log.assert_called_once()
        log_kwargs = mock_repo.update_sync_log.call_args.kwargs
        assert log_kwargs["ticker_id"] == 42
        assert log_kwargs["timeframe"] == "15Min"
        assert log_kwargs["bars_fetched"] == 4
        assert log_kwargs["status"] == "success"

    def test_does_not_update_sync_log_on_zero_inserts(self, mock_db_manager):
        """Sync log is NOT updated when no bars are inserted."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_bars.return_value = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

        agg._aggregate_intraday(mock_repo, "AAPL", "15Min")

        mock_repo.update_sync_log.assert_not_called()


# ---------------------------------------------------------------------------
# Daily bar fetching
# ---------------------------------------------------------------------------


class TestAggregatDaily:
    """Tests for _aggregate_daily (fetch 1Day bars from provider)."""

    def test_fetches_and_inserts_daily_bars(
        self, mock_db_manager, mock_provider, sample_daily_df
    ):
        """Daily bars from the provider are persisted in the DB."""
        mock_provider.fetch_daily_bars.return_value = sample_daily_df

        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_earliest_timestamp.return_value = datetime(2024, 1, 2)
        mock_repo.bulk_insert_bars.return_value = 5
        mock_ticker = MagicMock()
        mock_ticker.id = 1
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        count = agg._aggregate_daily(mock_repo, "AAPL")

        assert count == 5
        mock_provider.fetch_daily_bars.assert_called_once()
        mock_repo.bulk_insert_bars.assert_called_once()

    def test_returns_zero_when_no_provider(self, mock_db_manager):
        """Returns 0 when no provider is configured."""
        agg = TimeframeAggregator(db_manager=mock_db_manager, provider=None)
        mock_repo = MagicMock()

        count = agg._aggregate_daily(mock_repo, "AAPL")

        assert count == 0
        mock_repo.bulk_insert_bars.assert_not_called()

    def test_returns_zero_when_provider_returns_empty(
        self, mock_db_manager, mock_provider
    ):
        """Returns 0 when the provider returns no daily bars."""
        mock_provider.fetch_daily_bars.return_value = pd.DataFrame()

        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_earliest_timestamp.return_value = datetime(2024, 1, 2)

        count = agg._aggregate_daily(mock_repo, "AAPL")

        assert count == 0

    def test_returns_zero_when_no_reference_data(
        self, mock_db_manager, mock_provider
    ):
        """Returns 0 when there is no 1Min or 1Day data to anchor the range."""
        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_earliest_timestamp.return_value = None

        count = agg._aggregate_daily(mock_repo, "AAPL")

        assert count == 0
        mock_provider.fetch_daily_bars.assert_not_called()

    def test_handles_provider_exception(self, mock_db_manager, mock_provider):
        """Exceptions from the provider are caught and logged."""
        mock_provider.fetch_daily_bars.side_effect = RuntimeError("API down")

        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_earliest_timestamp.return_value = datetime(2024, 1, 2)

        count = agg._aggregate_daily(mock_repo, "AAPL")

        assert count == 0

    def test_uses_latest_daily_timestamp_as_start(
        self, mock_db_manager, mock_provider, sample_daily_df
    ):
        """When daily bars exist, fetch starts from the latest timestamp."""
        mock_provider.fetch_daily_bars.return_value = sample_daily_df

        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        existing_daily_ts = datetime(2024, 1, 3)
        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = existing_daily_ts
        mock_repo.bulk_insert_bars.return_value = 3
        mock_ticker = MagicMock()
        mock_ticker.id = 1
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        agg._aggregate_daily(mock_repo, "AAPL")

        fetch_call = mock_provider.fetch_daily_bars.call_args
        # Start should be the existing daily ts (normalised to naive)
        assert fetch_call.args[1] == existing_daily_ts

    def test_strips_timezone_from_daily_df(
        self, mock_db_manager, mock_provider
    ):
        """Timezone-aware daily bars are stored as timezone-naive."""
        dates = pd.date_range("2024-01-02", periods=3, freq="B", tz="UTC")
        df_tz = pd.DataFrame(
            {
                "open": [150.0, 151.0, 152.0],
                "high": [155.0, 156.0, 157.0],
                "low": [148.0, 149.0, 150.0],
                "close": [153.0, 154.0, 155.0],
                "volume": [5_000_000, 5_100_000, 5_200_000],
            },
            index=dates,
        )
        mock_provider.fetch_daily_bars.return_value = df_tz

        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        mock_repo = MagicMock()
        mock_repo.get_latest_timestamp.return_value = None
        mock_repo.get_earliest_timestamp.return_value = datetime(2024, 1, 2)
        mock_repo.bulk_insert_bars.return_value = 3
        mock_ticker = MagicMock()
        mock_ticker.id = 1
        mock_repo.get_or_create_ticker.return_value = mock_ticker

        agg._aggregate_daily(mock_repo, "AAPL")

        # The df passed to bulk_insert_bars should have tz-naive index
        inserted_df = mock_repo.bulk_insert_bars.call_args.kwargs["df"]
        assert inserted_df.index.tz is None


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


class TestAggregateMissingTimeframes:
    """Tests for the public aggregate_missing_timeframes method."""

    def test_calls_intraday_and_daily(self, mock_db_manager, mock_provider):
        """All three default timeframes are processed."""
        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        with (
            patch.object(agg, "_aggregate_intraday", return_value=4) as mock_intra,
            patch.object(agg, "_aggregate_daily", return_value=5) as mock_daily,
        ):
            result = agg.aggregate_missing_timeframes("aapl")

        assert result == {"15Min": 4, "1Hour": 4, "1Day": 5}
        assert mock_intra.call_count == 2
        mock_daily.assert_called_once()

    def test_normalises_ticker_to_uppercase(self, mock_db_manager):
        """The ticker symbol is normalised to uppercase."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        with patch.object(agg, "_aggregate_intraday", return_value=0) as mock_intra:
            agg.aggregate_missing_timeframes("aapl", target_timeframes=["15Min"])

        mock_intra.assert_called_once()
        # Second arg (symbol) should be uppercase
        assert mock_intra.call_args.args[1] == "AAPL"

    def test_custom_target_timeframes(self, mock_db_manager):
        """Only the requested timeframes are processed."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        with patch.object(agg, "_aggregate_intraday", return_value=10) as mock_intra:
            result = agg.aggregate_missing_timeframes(
                "SPY", target_timeframes=["1Hour"]
            )

        assert result == {"1Hour": 10}
        mock_intra.assert_called_once()

    def test_skips_unknown_timeframes(self, mock_db_manager):
        """Unknown timeframes produce 0 and a warning."""
        agg = TimeframeAggregator(db_manager=mock_db_manager)

        result = agg.aggregate_missing_timeframes(
            "SPY", target_timeframes=["2Hour"]
        )

        assert result == {"2Hour": 0}

    def test_returns_summary_dict(self, mock_db_manager, mock_provider):
        """Return value maps each timeframe to its insert count."""
        agg = TimeframeAggregator(
            db_manager=mock_db_manager, provider=mock_provider
        )

        with (
            patch.object(agg, "_aggregate_intraday", return_value=0),
            patch.object(agg, "_aggregate_daily", return_value=0),
        ):
            result = agg.aggregate_missing_timeframes("AAPL")

        assert isinstance(result, dict)
        assert set(result.keys()) == {"15Min", "1Hour", "1Day"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestNormalizeTs:
    """Tests for the _normalize_ts static method."""

    def test_none_returns_none(self):
        """None input returns None."""
        assert TimeframeAggregator._normalize_ts(None) is None

    def test_naive_datetime_unchanged(self):
        """A naive datetime is returned as-is."""
        ts = datetime(2024, 1, 2, 9, 30)
        assert TimeframeAggregator._normalize_ts(ts) == ts
        assert TimeframeAggregator._normalize_ts(ts).tzinfo is None

    def test_aware_datetime_stripped(self):
        """Timezone info is removed from aware datetimes."""
        ts = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)
        result = TimeframeAggregator._normalize_ts(ts)
        assert result == datetime(2024, 1, 2, 9, 30)
        assert result.tzinfo is None
