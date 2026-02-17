"""Tests for the market data API endpoints.

Endpoints under test:
- GET /api/bars       -- OHLCV bar data
- GET /api/indicators -- computed indicator values
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.market_data import router
from src.data.database.dependencies import get_market_grpc_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repo():
    """Create a mock OHLCVRepository."""
    return MagicMock()


@pytest.fixture()
def client(mock_repo):
    """Create a FastAPI TestClient with mocked market repo dependency."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_market_grpc_client] = lambda: mock_repo
    yield TestClient(app)


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


# ---------------------------------------------------------------------------
# /api/bars Tests
# ---------------------------------------------------------------------------


class TestGetBars:
    """GET /api/bars"""

    def test_returns_bars_successfully(self, client, mock_repo):
        """Should return OHLCV bars as JSON."""
        mock_ticker = MagicMock()
        mock_ticker.symbol = "AAPL"
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = _make_bars_df(2)

        response = client.get(
            "/api/bars",
            params={
                "symbol": "AAPL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1Hour"
        assert data["count"] == 2
        assert len(data["bars"]) == 2
        assert data["bars"][0]["open"] == 100.0

    def test_missing_required_params(self, client):
        """Should return 422 when required query params are missing."""
        response = client.get("/api/bars")
        assert response.status_code == 422

    def test_invalid_timeframe(self, client):
        """Should return 400 for an invalid timeframe."""
        response = client.get(
            "/api/bars",
            params={
                "symbol": "AAPL",
                "timeframe": "INVALID",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 400
        assert "Invalid timeframe" in response.json()["detail"]

    def test_start_after_end(self, client):
        """Should return 400 when start >= end."""
        response = client.get(
            "/api/bars",
            params={
                "symbol": "AAPL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-03T00:00:00",
                "end_timestamp": "2024-01-02T00:00:00",
            },
        )

        assert response.status_code == 400
        assert "start_timestamp must be before end_timestamp" in response.json()["detail"]

    def test_symbol_not_found(self, client, mock_repo):
        """Should return 404 when symbol does not exist."""
        mock_repo.get_ticker.return_value = None

        response = client.get(
            "/api/bars",
            params={
                "symbol": "NOSYMBOL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_no_bars_in_range(self, client, mock_repo):
        """Should return 404 when no bars exist in the date range."""
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_bars.return_value = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

        response = client.get(
            "/api/bars",
            params={
                "symbol": "AAPL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/indicators Tests
# ---------------------------------------------------------------------------


class TestGetIndicators:
    """GET /api/indicators"""

    def test_returns_indicators_successfully(self, client, mock_repo):
        """Should return indicator rows with names."""
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = _make_features_df(2)

        response = client.get(
            "/api/indicators",
            params={
                "symbol": "AAPL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["count"] == 2
        assert "atr_14" in data["indicator_names"]
        assert "rsi_14" in data["indicator_names"]
        assert len(data["rows"]) == 2
        assert "atr_14" in data["rows"][0]["indicators"]

    def test_invalid_timeframe(self, client):
        """Should return 400 for an invalid timeframe."""
        response = client.get(
            "/api/indicators",
            params={
                "symbol": "AAPL",
                "timeframe": "INVALID",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 400

    def test_symbol_not_found(self, client, mock_repo):
        """Should return 404 when symbol does not exist."""
        mock_repo.get_ticker.return_value = None

        response = client.get(
            "/api/indicators",
            params={
                "symbol": "NOSYMBOL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 404

    def test_no_indicators_in_range(self, client, mock_repo):
        """Should return 404 when no indicators exist in the date range."""
        mock_ticker = MagicMock()
        mock_repo.get_ticker.return_value = mock_ticker
        mock_repo.get_features.return_value = pd.DataFrame()

        response = client.get(
            "/api/indicators",
            params={
                "symbol": "AAPL",
                "timeframe": "1Hour",
                "start_timestamp": "2024-01-02T00:00:00",
                "end_timestamp": "2024-01-03T00:00:00",
            },
        )

        assert response.status_code == 404
