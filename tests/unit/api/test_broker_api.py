"""Tests for the broker API endpoints.

Endpoints under test:
- GET  /api/broker/trades        (list trades with pagination)
- GET  /api/broker/status        (connection status)
- GET  /api/broker/callback      (broker callback)
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from tests.unit.api.conftest import TEST_USER_ID, OTHER_USER_ID


def _create_snaptrade_user(db_session: Session, account_id: int):
    """Helper to create a SnapTradeUser row."""
    from src.data.database.broker_models import SnapTradeUser

    snap_user = SnapTradeUser(
        user_account_id=account_id,
        snaptrade_user_id=f"snap_{account_id}",
        snaptrade_user_secret=f"secret_{account_id}",
    )
    db_session.add(snap_user)
    db_session.flush()
    return snap_user


def _create_broker_connection(db_session: Session, snaptrade_user_id: int, **kwargs):
    """Helper to create a BrokerConnection row."""
    from src.data.database.broker_models import BrokerConnection

    conn = BrokerConnection(
        snaptrade_user_id=snaptrade_user_id,
        brokerage_name=kwargs.get("brokerage_name", "Alpaca"),
        brokerage_slug=kwargs.get("brokerage_slug", "alpaca"),
        authorization_id=kwargs.get("authorization_id", "auth_001"),
        meta=kwargs.get("meta", {}),
    )
    db_session.add(conn)
    db_session.flush()
    return conn


_fill_id_counter = 0


def _next_fill_id():
    """Generate a unique fill ID for SQLite BigInteger PK compatibility."""
    global _fill_id_counter
    _fill_id_counter += 1
    return _fill_id_counter


def _create_trade_fill(db_session: Session, broker_connection_id: int, account_id: int, **kwargs):
    """Helper to create a TradeFill row."""
    from src.data.database.broker_models import TradeFill

    fill = TradeFill(
        id=_next_fill_id(),
        broker_connection_id=broker_connection_id,
        account_id=account_id,
        symbol=kwargs.get("symbol", "AAPL"),
        side=kwargs.get("side", "buy"),
        quantity=kwargs.get("quantity", 10.0),
        price=kwargs.get("price", 150.0),
        fees=kwargs.get("fees", 0.0),
        executed_at=kwargs.get(
            "executed_at", datetime(2025, 1, 15, 14, 30, tzinfo=timezone.utc)
        ),
        external_trade_id=kwargs.get("external_trade_id"),
        raw_data=kwargs.get("raw_data", {}),
    )
    db_session.add(fill)
    db_session.flush()
    return fill


# ---------------------------------------------------------------------------
# List Trades
# ---------------------------------------------------------------------------


class TestGetTrades:
    """GET /api/broker/trades"""

    def test_empty_trades_for_user_without_snaptrade(self, client, test_account):
        """User with no SnapTrade registration should get empty trades list."""
        response = client.get("/api/broker/trades")
        assert response.status_code == 200

        data = response.json()
        assert data["trades"] == []
        assert data["total"] == 0

    def test_returns_trades_for_user(self, client, test_account, db_session: Session):
        """Should return trades belonging to the authenticated user."""
        snap_user = _create_snaptrade_user(db_session, TEST_USER_ID)
        conn = _create_broker_connection(db_session, snap_user.id)
        _create_trade_fill(
            db_session, conn.id, TEST_USER_ID,
            symbol="AAPL", side="buy", quantity=50, price=150.0,
            external_trade_id="ext_001",
        )
        _create_trade_fill(
            db_session, conn.id, TEST_USER_ID,
            symbol="MSFT", side="sell", quantity=25, price=400.0,
            external_trade_id="ext_002",
        )

        response = client.get("/api/broker/trades")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["trades"]) == 2

    def test_filter_trades_by_symbol(self, client, test_account, db_session: Session):
        """Should filter trades by symbol query parameter."""
        snap_user = _create_snaptrade_user(db_session, TEST_USER_ID)
        conn = _create_broker_connection(db_session, snap_user.id)
        _create_trade_fill(
            db_session, conn.id, TEST_USER_ID,
            symbol="AAPL", external_trade_id="ext_a1",
        )
        _create_trade_fill(
            db_session, conn.id, TEST_USER_ID,
            symbol="MSFT", external_trade_id="ext_m1",
        )

        response = client.get("/api/broker/trades", params={"symbol": "AAPL"})
        data = response.json()
        assert data["total"] == 1
        assert data["trades"][0]["symbol"] == "AAPL"

    def test_trades_pagination(self, client, test_account, db_session: Session):
        """Should support page and limit parameters."""
        snap_user = _create_snaptrade_user(db_session, TEST_USER_ID)
        conn = _create_broker_connection(db_session, snap_user.id)

        for i in range(5):
            _create_trade_fill(
                db_session, conn.id, TEST_USER_ID,
                symbol="SPY",
                quantity=10.0 + i,
                external_trade_id=f"ext_page_{i}",
            )

        response = client.get("/api/broker/trades", params={"page": 1, "limit": 2})
        data = response.json()
        assert data["total"] == 5
        assert len(data["trades"]) == 2
        assert data["page"] == 1
        assert data["limit"] == 2

    def test_trade_response_structure(self, client, test_account, db_session: Session):
        """Each trade should have the expected fields."""
        snap_user = _create_snaptrade_user(db_session, TEST_USER_ID)
        conn = _create_broker_connection(db_session, snap_user.id, brokerage_name="Robinhood")
        _create_trade_fill(
            db_session, conn.id, TEST_USER_ID,
            symbol="GOOGL", side="buy", quantity=5, price=175.0, fees=0.50,
            external_trade_id="ext_struct_1",
        )

        response = client.get("/api/broker/trades")
        data = response.json()
        trade = data["trades"][0]

        assert "id" in trade
        assert trade["symbol"] == "GOOGL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 5.0
        assert trade["price"] == 175.0
        assert trade["fees"] == 0.50
        assert trade["brokerage"] == "Robinhood"
        assert "executed_at" in trade

    def test_does_not_return_other_users_trades(
        self, client, test_account, other_account, db_session: Session
    ):
        """Multi-tenant isolation: should not see other user's trades."""
        # Set up test user's trades
        snap_user = _create_snaptrade_user(db_session, TEST_USER_ID)
        conn = _create_broker_connection(db_session, snap_user.id, authorization_id="auth_a")
        _create_trade_fill(
            db_session, conn.id, TEST_USER_ID,
            symbol="AAPL", external_trade_id="ext_own_1",
        )

        # Set up other user's trades
        snap_user2 = _create_snaptrade_user(db_session, OTHER_USER_ID)
        conn2 = _create_broker_connection(
            db_session, snap_user2.id, authorization_id="auth_b"
        )
        _create_trade_fill(
            db_session, conn2.id, OTHER_USER_ID,
            symbol="TSLA", external_trade_id="ext_other_1",
        )

        response = client.get("/api/broker/trades")
        data = response.json()
        assert data["total"] == 1
        assert data["trades"][0]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Broker Callback
# ---------------------------------------------------------------------------


class TestBrokerCallback:
    """GET /api/broker/callback"""

    def test_callback_returns_success(self, client, test_account):
        """Callback endpoint should return a status message."""
        response = client.get("/api/broker/callback")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "message" in data
