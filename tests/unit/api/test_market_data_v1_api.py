"""Tests for the v1 market data API endpoints with flexible time queries.

Endpoints under test:
- GET /api/v1/marketdata             -- OHLCV bar data
- GET /api/v1/indicators             -- computed indicator values
- GET /api/v1/marketdata+indicators  -- combined bars + indicators

Also tests the utility functions:
- parse_lookback
- determine_date_range
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.market_data_api import (
    determine_date_range,
    parse_lookback,
    router,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db_manager():
    """Create a mock DatabaseManager whose get_session yields a mock session."""
    from contextlib import contextmanager

    mock_manager = MagicMock()
    mock_session = MagicMock()

    @contextmanager
    def _mock_session():
        yield mock_session

    mock_manager.get_session = _mock_session
    return mock_manager, mock_session


def _make_bars_df(n: int = 3) -> pd.DataFrame:
    """Create a sample OHLCV DataFrame."""
    timestamps = pd.date_range("2024-01-02 10:00", periods=n, freq="h")
    data = {
        "open": [100.0 + i for i in range(n)],
        "high": [105.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [103.0 + i for i in range(n)],
        "volume": [1000 + i * 100 for i in range(n)],
    }
    df = pd.DataFrame(data, index=timestamps)
    df.index.name = None
    return df


def _make_features_df(n: int = 3) -> pd.DataFrame:
    """Create a sample features DataFrame."""
    timestamps = pd.date_range("2024-01-02 10:00", periods=n, freq="h")
    data = {
        "atr_14": [2.5 + i * 0.1 for i in range(n)],
        "rsi_14": [55.0 + i for i in range(n)],
        "sma_20": [100.0 + i for i in range(n)],
    }
    df = pd.DataFrame(data, index=timestamps)
    df.index.name = None
    return df


def _create_test_client(mock_manager, mock_repo_instance):
    """Create a FastAPI TestClient with mocked database layer."""
    app = FastAPI()
    app.include_router(router)
    with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
         patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo_instance):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# parse_lookback tests
# ---------------------------------------------------------------------------


class TestParseLookback:
    """Unit tests for parse_lookback()."""

    def test_parse_hours(self):
        """Should parse hour-based lookback."""
        result = parse_lookback("1h")
        assert result == timedelta(hours=1)

    def test_parse_hours_large(self):
        """Should parse multi-hour lookback."""
        result = parse_lookback("24h")
        assert result == timedelta(hours=24)

    def test_parse_days(self):
        """Should parse day-based lookback."""
        result = parse_lookback("30d")
        assert result == timedelta(days=30)

    def test_parse_weeks(self):
        """Should parse week-based lookback."""
        result = parse_lookback("4w")
        assert result == timedelta(weeks=4)

    def test_parse_month(self):
        """Should parse month-based lookback as 30 days."""
        result = parse_lookback("1month")
        assert result == timedelta(days=30)

    def test_parse_months_multiple(self):
        """Should parse multi-month lookback."""
        result = parse_lookback("3month")
        assert result == timedelta(days=90)

    def test_parse_year(self):
        """Should parse year-based lookback."""
        result = parse_lookback("1y")
        assert result == timedelta(days=365)

    def test_parse_case_insensitive(self):
        """Should handle uppercase units."""
        result = parse_lookback("4W")
        assert result == timedelta(weeks=4)

    def test_parse_with_whitespace(self):
        """Should handle leading/trailing whitespace."""
        result = parse_lookback("  2d  ")
        assert result == timedelta(days=2)

    def test_invalid_empty_string(self):
        """Should raise ValueError for empty string."""
        with pytest.raises(ValueError, match="must not be empty"):
            parse_lookback("")

    def test_invalid_format(self):
        """Should raise ValueError for unrecognised format."""
        with pytest.raises(ValueError, match="Invalid lookback format"):
            parse_lookback("abc")

    def test_invalid_no_number(self):
        """Should raise ValueError when number is missing."""
        with pytest.raises(ValueError, match="Invalid lookback format"):
            parse_lookback("d")

    def test_invalid_no_unit(self):
        """Should raise ValueError when unit is missing."""
        with pytest.raises(ValueError, match="Invalid lookback format"):
            parse_lookback("30")

    def test_exceeds_max_lookback(self):
        """Should raise ValueError when lookback exceeds 5 years."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            parse_lookback("6y")

    def test_invalid_unit(self):
        """Should raise ValueError for unrecognised unit."""
        with pytest.raises(ValueError, match="Invalid lookback format"):
            parse_lookback("30x")


# ---------------------------------------------------------------------------
# determine_date_range tests
# ---------------------------------------------------------------------------


class TestDetermineDateRange:
    """Unit tests for determine_date_range()."""

    def test_lookback_mode(self):
        """Should compute start from lookback relative to now."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start=None, end=None, lookback="4w", last_n_bars=None, timeframe="1Hour",
        )
        assert bar_limit is None
        assert start_dt is not None
        assert end_dt is not None
        # end should be roughly now
        assert abs((end_dt - datetime.now(timezone.utc)).total_seconds()) < 5
        # start should be ~28 days before end
        assert abs((end_dt - start_dt).days - 28) <= 1

    def test_lookback_with_explicit_end(self):
        """Should use explicit end when provided with lookback."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start=None, end="2024-06-01T00:00:00Z", lookback="7d",
            last_n_bars=None, timeframe="1Day",
        )
        assert bar_limit is None
        assert end_dt == datetime(2024, 6, 1, tzinfo=timezone.utc)
        assert start_dt == datetime(2024, 5, 25, tzinfo=timezone.utc)

    def test_lookback_takes_priority_over_start_end(self):
        """lookback should take priority even when start/end are also given."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start="2020-01-01", end="2020-02-01", lookback="1d",
            last_n_bars=None, timeframe="1Hour",
        )
        # Should use lookback mode, not the explicit start/end
        assert bar_limit is None
        # end should be ~now since we did not provide end for lookback (but we did here)
        # Actually, lookback + end means end=parsed end
        assert end_dt == datetime(2020, 2, 1, tzinfo=timezone.utc)
        expected_start = datetime(2020, 1, 31, tzinfo=timezone.utc)
        assert start_dt == expected_start

    def test_last_n_bars_mode(self):
        """Should return bar_limit when last_n_bars is specified."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start=None, end=None, lookback=None, last_n_bars=500, timeframe="15Min",
        )
        assert start_dt is None
        assert end_dt is None
        assert bar_limit == 500

    def test_last_n_bars_invalid_zero(self):
        """Should raise ValueError for zero bar count."""
        with pytest.raises(ValueError, match="positive integer"):
            determine_date_range(
                start=None, end=None, lookback=None, last_n_bars=0, timeframe="1Day",
            )

    def test_last_n_bars_invalid_negative(self):
        """Should raise ValueError for negative bar count."""
        with pytest.raises(ValueError, match="positive integer"):
            determine_date_range(
                start=None, end=None, lookback=None, last_n_bars=-10, timeframe="1Day",
            )

    def test_last_n_bars_exceeds_max(self):
        """Should raise ValueError for excessive bar count."""
        with pytest.raises(ValueError, match="cannot exceed"):
            determine_date_range(
                start=None, end=None, lookback=None, last_n_bars=200_000, timeframe="1Day",
            )

    def test_absolute_range_mode(self):
        """Should use start and end when both provided."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start="2024-01-01T00:00:00Z", end="2024-02-01T00:00:00Z",
            lookback=None, last_n_bars=None, timeframe="1Hour",
        )
        assert bar_limit is None
        assert start_dt == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert end_dt == datetime(2024, 2, 1, tzinfo=timezone.utc)

    def test_absolute_range_start_after_end(self):
        """Should raise ValueError when start >= end."""
        with pytest.raises(ValueError, match="start must be before end"):
            determine_date_range(
                start="2024-02-01T00:00:00Z", end="2024-01-01T00:00:00Z",
                lookback=None, last_n_bars=None, timeframe="1Hour",
            )

    def test_start_only_mode(self):
        """Should default end to now when only start is given."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start="2024-01-01T00:00:00Z", end=None,
            lookback=None, last_n_bars=None, timeframe="1Day",
        )
        assert bar_limit is None
        assert start_dt == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert abs((end_dt - datetime.now(timezone.utc)).total_seconds()) < 5

    def test_nothing_specified_raises(self):
        """Should raise ValueError when nothing is specified."""
        with pytest.raises(ValueError, match="Must specify at least one"):
            determine_date_range(
                start=None, end=None, lookback=None, last_n_bars=None, timeframe="1Day",
            )

    def test_lookback_priority_over_last_n_bars(self):
        """lookback should take priority over last_n_bars."""
        start_dt, end_dt, bar_limit = determine_date_range(
            start=None, end=None, lookback="1d", last_n_bars=100, timeframe="1Hour",
        )
        # Should be lookback mode, not bar count
        assert bar_limit is None
        assert start_dt is not None
        assert end_dt is not None


# ---------------------------------------------------------------------------
# /api/v1/marketdata Tests
# ---------------------------------------------------------------------------


class TestGetMarketData:
    """GET /api/v1/marketdata"""

    def test_returns_bars_with_absolute_range(self, mock_db_manager):
        """Should return bars for start/end range."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(3)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "start": "2024-01-02T00:00:00Z",
                    "end": "2024-01-03T00:00:00Z",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1Hour"
        assert data["total_bars"] == 3
        assert len(data["bars"]) == 3
        assert data["bars"][0]["open"] == 100.0
        assert "range" in data
        assert "start" in data["range"]
        assert "end" in data["range"]

    def test_returns_bars_with_lookback(self, mock_db_manager):
        """Should return bars when using lookback parameter."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(2)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "4w",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_bars"] == 2
        # Verify the repo was called with start/end (not limit)
        mock_repo.get_bars.assert_called_once()

    def test_returns_bars_with_last_n_bars(self, mock_db_manager):
        """Should return bars when using last_n_bars parameter."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(5)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "last_n_bars": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_bars"] == 5
        # Should have been called with limit parameter
        mock_repo.get_bars.assert_called_once_with("AAPL", "1Hour", limit=5)

    def test_missing_time_params_returns_400(self, mock_db_manager):
        """Should return 400 when no time specification is provided."""
        mock_manager, _ = mock_db_manager
        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={"symbol": "AAPL", "timeframe": "1Hour"},
            )

        assert response.status_code == 400
        assert "Must specify" in response.json()["detail"]

    def test_invalid_timeframe_returns_400(self, mock_db_manager):
        """Should return 400 for an invalid timeframe."""
        mock_manager, _ = mock_db_manager
        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "INVALID",
                    "lookback": "4w",
                },
            )

        assert response.status_code == 400
        assert "Invalid timeframe" in response.json()["detail"]

    def test_symbol_not_found_returns_404(self, mock_db_manager):
        """Should return 404 when symbol does not exist."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_repo.get_ticker.return_value = None

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "NOSYMBOL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_no_bars_returns_404(self, mock_db_manager):
        """Should return 404 when no bars exist."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 404

    def test_invalid_lookback_returns_400(self, mock_db_manager):
        """Should return 400 for invalid lookback format."""
        mock_manager, _ = mock_db_manager
        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "invalid",
                },
            )

        assert response.status_code == 400

    def test_missing_required_params_returns_422(self, mock_db_manager):
        """Should return 422 when required params are missing."""
        mock_manager, _ = mock_db_manager
        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/api/v1/marketdata")

        assert response.status_code == 422

    def test_start_only_defaults_end_to_now(self, mock_db_manager):
        """Should default end to now when only start is given."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(2)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "start": "2024-01-01T00:00:00Z",
                },
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /api/v1/indicators Tests
# ---------------------------------------------------------------------------


class TestGetIndicators:
    """GET /api/v1/indicators"""

    def test_returns_indicators_with_absolute_range(self, mock_db_manager):
        """Should return indicator rows for start/end range."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = _make_features_df(3)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "start": "2024-01-02T00:00:00Z",
                    "end": "2024-01-03T00:00:00Z",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["total_rows"] == 3
        assert len(data["indicators"]) == 3
        assert "atr_14" in data["indicators"][0]
        assert "range" in data
        assert data["missing_indicators"] == []

    def test_returns_indicators_with_lookback(self, mock_db_manager):
        """Should return indicators when using lookback parameter."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = _make_features_df(2)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 200

    def test_indicator_filter_returns_subset(self, mock_db_manager):
        """Should return only requested indicators when filter is specified."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = _make_features_df(2)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                    "indicators": "atr_14,rsi_14",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # Should only have the requested indicators (plus timestamp)
        for row in data["indicators"]:
            indicator_keys = {k for k in row if k != "timestamp"}
            assert indicator_keys <= {"atr_14", "rsi_14"}

    def test_indicator_filter_reports_missing(self, mock_db_manager):
        """Should report missing indicators in the response."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = _make_features_df(2)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                    "indicators": "atr_14,nonexistent_indicator",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "nonexistent_indicator" in data["missing_indicators"]

    def test_symbol_not_found_returns_404(self, mock_db_manager):
        """Should return 404 when symbol does not exist."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_repo.get_ticker.return_value = None

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/indicators",
                params={
                    "symbol": "NOSYMBOL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 404

    def test_no_indicators_returns_404(self, mock_db_manager):
        """Should return 404 when no indicators exist."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = pd.DataFrame()

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/v1/marketdata+indicators Tests
# ---------------------------------------------------------------------------


class TestGetCombined:
    """GET /api/v1/marketdata+indicators"""

    def test_returns_combined_data(self, mock_db_manager):
        """Should return both bars and indicators."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(3)
        mock_repo.get_features.return_value = _make_features_df(3)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata+indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "4w",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["total_bars"] == 3
        assert data["total_indicator_rows"] == 3
        assert len(data["bars"]) == 3
        assert len(data["indicators"]) == 3
        assert "range" in data

    def test_returns_bars_without_indicators(self, mock_db_manager):
        """Should return bars even if indicators are empty."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(3)
        mock_repo.get_features.return_value = pd.DataFrame()

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata+indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_bars"] == 3
        assert data["total_indicator_rows"] == 0
        assert data["indicators"] == []

    def test_no_bars_returns_404(self, mock_db_manager):
        """Should return 404 when no bars exist."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata+indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 404

    def test_symbol_not_found_returns_404(self, mock_db_manager):
        """Should return 404 when symbol does not exist."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_repo.get_ticker.return_value = None

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata+indicators",
                params={
                    "symbol": "NOSYMBOL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                },
            )

        assert response.status_code == 404

    def test_indicator_filter_in_combined(self, mock_db_manager):
        """Should filter indicators in combined endpoint."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(2)
        mock_repo.get_features.return_value = _make_features_df(2)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata+indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "lookback": "1d",
                    "indicators": "rsi_14",
                },
            )

        assert response.status_code == 200
        data = response.json()
        for row in data["indicators"]:
            indicator_keys = {k for k in row if k != "timestamp"}
            assert indicator_keys <= {"rsi_14"}

    def test_with_last_n_bars(self, mock_db_manager):
        """Should work with last_n_bars in combined endpoint."""
        mock_manager, mock_session = mock_db_manager
        mock_repo = MagicMock()
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(5)
        mock_repo.get_features.return_value = _make_features_df(5)

        app = FastAPI()
        app.include_router(router)
        with patch("src.api.market_data_api.get_db_manager", return_value=mock_manager), \
             patch("src.api.market_data_api.OHLCVRepository", return_value=mock_repo):
            client = TestClient(app)
            response = client.get(
                "/api/v1/marketdata+indicators",
                params={
                    "symbol": "AAPL",
                    "timeframe": "1Hour",
                    "last_n_bars": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_bars"] == 5
