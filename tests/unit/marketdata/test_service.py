"""Tests for MarketDataService."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from src.marketdata.service import MarketDataService


@pytest.fixture
def sample_1min_df():
    """60 minutes of 1Min OHLCV bars."""
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
    """20 daily bars."""
    dates = pd.date_range("2024-01-02", periods=20, freq="B")
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(20)],
            "high": [102.0 + i for i in range(20)],
            "low": [98.0 + i for i in range(20)],
            "close": [101.0 + i for i in range(20)],
            "volume": [1_000_000 + i * 10_000 for i in range(20)],
        },
        index=dates,
    )


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.source_name = "test_provider"
    provider.fetch_1min_bars.return_value = pd.DataFrame()
    provider.fetch_daily_bars.return_value = pd.DataFrame()
    return provider


@pytest.fixture
def mock_db_manager():
    manager = MagicMock()
    session = MagicMock()
    manager.get_session.return_value.__enter__ = MagicMock(return_value=session)
    manager.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_or_create_ticker.return_value = MagicMock(id=1)
    repo.get_latest_timestamp.return_value = None
    repo.bulk_insert_bars.return_value = 0
    return repo


def _make_service(provider, db_manager):
    return MarketDataService(provider=provider, db_manager=db_manager)


# -----------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------


class TestInit:
    def test_stores_provider(self, mock_provider, mock_db_manager):
        svc = _make_service(mock_provider, mock_db_manager)
        assert svc.provider is mock_provider

    def test_stores_db_manager(self, mock_provider, mock_db_manager):
        svc = _make_service(mock_provider, mock_db_manager)
        assert svc.db_manager is mock_db_manager

    def test_uses_default_db_manager(self, mock_provider):
        with patch("src.marketdata.service.get_db_manager") as mock_get:
            mock_get.return_value = MagicMock()
            svc = MarketDataService(provider=mock_provider)
            assert svc.db_manager is mock_get.return_value


# -----------------------------------------------------------------------
# ensure_data — 1Min
# -----------------------------------------------------------------------


class TestEnsureData1Min:
    def test_fetches_1min_for_new_symbol(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df,
    ):
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = len(sample_1min_df)

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], start=datetime(2024, 1, 2))

        assert result["1Min"] == 60
        mock_provider.fetch_1min_bars.assert_called_once()

    def test_skips_fetch_when_up_to_date(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        mock_repo.get_latest_timestamp.return_value = now

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], end=now)

        assert result["1Min"] == 0
        mock_provider.fetch_1min_bars.assert_not_called()

    def test_incremental_fetch_from_latest(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df,
    ):
        old_latest = datetime(2024, 1, 2, 9, 30)
        mock_repo.get_latest_timestamp.return_value = old_latest
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 10

        end = datetime(2024, 1, 2, 11, 0)
        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], end=end)

        assert result["1Min"] == 10
        # Fetch should start after db_latest + 1 min buffer
        call_args = mock_provider.fetch_1min_bars.call_args
        fetch_start = call_args[0][1]
        assert fetch_start > old_latest

    def test_empty_provider_response_returns_zero(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        mock_provider.fetch_1min_bars.return_value = pd.DataFrame()

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], start=datetime(2024, 1, 2))

        assert result["1Min"] == 0

    def test_provider_error_returns_zero(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        mock_provider.fetch_1min_bars.side_effect = ConnectionError("timeout")

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], start=datetime(2024, 1, 2))

        assert result["1Min"] == 0
        mock_repo.update_sync_log.assert_called()


# -----------------------------------------------------------------------
# ensure_data — 1Day
# -----------------------------------------------------------------------


class TestEnsureDataDaily:
    def test_fetches_daily_for_new_symbol(
        self, mock_provider, mock_db_manager, mock_repo, sample_daily_df,
    ):
        mock_provider.fetch_daily_bars.return_value = sample_daily_df
        mock_repo.bulk_insert_bars.return_value = 20
        # Return None for both 1Min and 1Day latest
        mock_repo.get_latest_timestamp.return_value = None

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Day"], start=datetime(2024, 1, 2))

        assert result["1Day"] == 20
        mock_provider.fetch_daily_bars.assert_called_once()

    def test_skips_daily_when_up_to_date(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        mock_repo.get_latest_timestamp.return_value = now

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Day"], end=now)

        assert result["1Day"] == 0
        mock_provider.fetch_daily_bars.assert_not_called()


# -----------------------------------------------------------------------
# ensure_data — aggregation
# -----------------------------------------------------------------------


class TestEnsureDataAggregation:
    def test_aggregates_5min_from_1min(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df,
    ):
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_repo.get_bars.return_value = sample_1min_df
        # First call for 1Min bulk_insert, second for 5Min bulk_insert
        mock_repo.bulk_insert_bars.side_effect = [60, 12]

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["5Min"], start=datetime(2024, 1, 2))

        # 1Min should have been ensured first
        assert "1Min" in result
        assert "5Min" in result
        assert result["5Min"] == 12

    def test_requesting_1min_and_5min_together(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df,
    ):
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_repo.get_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.side_effect = [60, 12]

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data(
                "AAPL", ["1Min", "5Min"], start=datetime(2024, 1, 2),
            )

        assert "1Min" in result
        assert "5Min" in result

    def test_aggregation_with_empty_1min_returns_zero(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        mock_provider.fetch_1min_bars.return_value = pd.DataFrame()
        mock_repo.get_bars.return_value = pd.DataFrame()

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["15Min"], start=datetime(2024, 1, 2))

        assert result["15Min"] == 0


# -----------------------------------------------------------------------
# ensure_data — mixed timeframes
# -----------------------------------------------------------------------


class TestEnsureDataMixed:
    def test_all_timeframes(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df, sample_daily_df,
    ):
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_provider.fetch_daily_bars.return_value = sample_daily_df
        mock_repo.get_bars.return_value = sample_1min_df
        # 1Min, 5Min, 1Hour, 1Day
        mock_repo.bulk_insert_bars.side_effect = [60, 12, 1, 20]

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data(
                "aapl",  # should be uppercased
                ["1Min", "5Min", "1Hour", "1Day"],
                start=datetime(2024, 1, 2),
            )

        assert "1Min" in result
        assert "5Min" in result
        assert "1Hour" in result
        assert "1Day" in result


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------


class TestEdgeCases:
    def test_symbol_uppercased(self, mock_provider, mock_db_manager, mock_repo):
        mock_provider.fetch_1min_bars.return_value = pd.DataFrame()

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            svc.ensure_data("aapl", ["1Min"], start=datetime(2024, 1, 2))

        mock_repo.get_or_create_ticker.assert_called_with("AAPL")

    def test_end_defaults_to_now(self, mock_provider, mock_db_manager, mock_repo):
        mock_provider.fetch_1min_bars.return_value = pd.DataFrame()

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            before = datetime.now(timezone.utc).replace(tzinfo=None)
            svc.ensure_data("AAPL", ["1Min"])
            # Should not raise — end is computed internally

    def test_timezone_aware_db_latest_normalised(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df,
    ):
        """get_latest_timestamp may return a tz-aware datetime; the service must handle it."""
        aware_ts = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
        mock_repo.get_latest_timestamp.return_value = aware_ts
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 60

        end = datetime(2024, 1, 2, 11, 0)
        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], end=end)

        # Should not raise and should have fetched data
        assert result["1Min"] == 60

    def test_timezone_aware_dataframe_index_stripped(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        """Provider may return tz-aware index; it should be localised to naive."""
        dates = pd.date_range("2024-01-02 09:30", periods=5, freq="1min", tz="UTC")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1000] * 5,
            },
            index=dates,
        )
        mock_provider.fetch_1min_bars.return_value = df
        mock_repo.bulk_insert_bars.return_value = 5

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            result = svc.ensure_data("AAPL", ["1Min"], start=datetime(2024, 1, 2))

        assert result["1Min"] == 5
        # The df passed to bulk_insert_bars should have tz-naive index
        inserted_df = mock_repo.bulk_insert_bars.call_args[1]["df"]
        assert inserted_df.index.tz is None

    def test_sync_log_updated_on_success(
        self, mock_provider, mock_db_manager, mock_repo, sample_1min_df,
    ):
        mock_provider.fetch_1min_bars.return_value = sample_1min_df
        mock_repo.bulk_insert_bars.return_value = 60

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            svc.ensure_data("AAPL", ["1Min"], start=datetime(2024, 1, 2))

        mock_repo.update_sync_log.assert_called()
        sync_call = mock_repo.update_sync_log.call_args
        assert sync_call[1]["status"] == "success"
        assert sync_call[1]["bars_fetched"] == 60

    def test_sync_log_updated_on_failure(
        self, mock_provider, mock_db_manager, mock_repo,
    ):
        mock_provider.fetch_1min_bars.side_effect = RuntimeError("API down")

        with patch("src.marketdata.service.OHLCVRepository", return_value=mock_repo):
            svc = _make_service(mock_provider, mock_db_manager)
            svc.ensure_data("AAPL", ["1Min"], start=datetime(2024, 1, 2))

        mock_repo.update_sync_log.assert_called()
        sync_call = mock_repo.update_sync_log.call_args
        assert sync_call[1]["status"] == "failed"
        assert "API down" in sync_call[1]["error_message"]
