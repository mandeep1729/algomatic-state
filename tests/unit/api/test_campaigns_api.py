"""Tests for the campaigns API endpoints (new schema).

Endpoints under test:
- GET  /api/campaigns                        (list campaigns)
- GET  /api/campaigns/{id}                   (campaign detail with fills & checks)
- GET  /api/campaigns/fills/{fill_id}/context (get fill context)
- PUT  /api/campaigns/fills/{fill_id}/context (save decision context on a fill)
- POST /api/campaigns/rebuild                (rebuild campaigns)
- GET  /api/campaigns/pnl/by-ticker          (P&L by ticker)
- GET  /api/campaigns/pnl/timeseries         (P&L timeseries)
- GET  /api/campaigns/pnl/{symbol}           (ticker P&L)
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from tests.unit.api.conftest import TEST_USER_ID, OTHER_USER_ID

# ---------------------------------------------------------------------------
# SQLite BigInteger PK counters — SQLite cannot auto-increment BigInteger
# columns, so we assign IDs manually.
# ---------------------------------------------------------------------------

_fill_id_counter = 0
_campaign_id_counter = 0
_context_id_counter = 0
_check_id_counter = 0


def _next_fill_id():
    global _fill_id_counter
    _fill_id_counter += 1
    return _fill_id_counter


def _next_campaign_id():
    global _campaign_id_counter
    _campaign_id_counter += 1
    return _campaign_id_counter


def _next_context_id():
    global _context_id_counter
    _context_id_counter += 1
    return _context_id_counter


def _next_check_id():
    global _check_id_counter
    _check_id_counter += 1
    return _check_id_counter


# ---------------------------------------------------------------------------
# Helper: broker prerequisite records
# ---------------------------------------------------------------------------

_snaptrade_user_counter = 0
_broker_conn_counter = 0


def _next_snaptrade_user_id():
    global _snaptrade_user_counter
    _snaptrade_user_counter += 1
    return _snaptrade_user_counter


def _next_broker_conn_id():
    global _broker_conn_counter
    _broker_conn_counter += 1
    return _broker_conn_counter


def _ensure_broker_connection(db_session: Session, account_id: int) -> int:
    """Create SnapTradeUser + BrokerConnection for the given account if missing.

    Returns the broker_connection.id.
    """
    from src.data.database.broker_models import BrokerConnection, SnapTradeUser

    existing_st = (
        db_session.query(SnapTradeUser)
        .filter(SnapTradeUser.user_account_id == account_id)
        .first()
    )
    if existing_st:
        conn = (
            db_session.query(BrokerConnection)
            .filter(BrokerConnection.snaptrade_user_id == existing_st.id)
            .first()
        )
        if conn:
            return conn.id

    st_id = _next_snaptrade_user_id()
    st = SnapTradeUser(
        id=st_id,
        user_account_id=account_id,
        snaptrade_user_id=f"st_user_{account_id}_{st_id}",
        snaptrade_user_secret="secret",
    )
    db_session.add(st)
    db_session.flush()

    conn_id = _next_broker_conn_id()
    conn = BrokerConnection(
        id=conn_id,
        snaptrade_user_id=st.id,
        brokerage_name="TestBroker",
        brokerage_slug="testbroker",
        authorization_id=f"auth_{account_id}_{conn_id}",
        meta={},
        is_active=True,
    )
    db_session.add(conn)
    db_session.flush()
    return conn.id


# ---------------------------------------------------------------------------
# Helpers: create test data using the new schema models
# ---------------------------------------------------------------------------

_ext_trade_counter = 0


def _next_external_trade_id():
    global _ext_trade_counter
    _ext_trade_counter += 1
    return f"ext_trade_{_ext_trade_counter}"


def _create_fill(db_session: Session, account_id: int, **kwargs):
    """Create a TradeFill record (requires broker connection)."""
    from src.data.database.broker_models import TradeFill

    broker_conn_id = _ensure_broker_connection(db_session, account_id)

    fill = TradeFill(
        id=_next_fill_id(),
        broker_connection_id=kwargs.get("broker_connection_id", broker_conn_id),
        account_id=account_id,
        symbol=kwargs.get("symbol", "AAPL"),
        side=kwargs.get("side", "buy"),
        quantity=kwargs.get("quantity", 10.0),
        price=kwargs.get("price", 150.0),
        fees=kwargs.get("fees", 0.0),
        executed_at=kwargs.get(
            "executed_at", datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc)
        ),
        broker=kwargs.get("broker", "TestBroker"),
        order_id=kwargs.get("order_id"),
        external_trade_id=kwargs.get("external_trade_id", _next_external_trade_id()),
        source=kwargs.get("source", "broker_synced"),
        raw_data=kwargs.get("raw_data", {}),
    )
    db_session.add(fill)
    db_session.flush()
    return fill


def _create_campaign(db_session: Session, account_id: int, **kwargs):
    """Create a Campaign record."""
    from src.data.database.trade_lifecycle_models import Campaign

    campaign = Campaign(
        id=_next_campaign_id(),
        account_id=account_id,
        symbol=kwargs.get("symbol", "AAPL"),
        strategy_id=kwargs.get("strategy_id"),
        created_at=kwargs.get(
            "created_at", datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc)
        ),
    )
    db_session.add(campaign)
    db_session.flush()
    return campaign


def _link_fill_to_campaign(db_session: Session, campaign_id: int, fill_id: int):
    """Create a CampaignFill junction row."""
    from src.data.database.trade_lifecycle_models import CampaignFill

    cf = CampaignFill(campaign_id=campaign_id, fill_id=fill_id)
    db_session.add(cf)
    db_session.flush()
    return cf


def _create_decision_context(db_session: Session, account_id: int, fill_id: int, **kwargs):
    """Create a DecisionContext record."""
    from src.data.database.trade_lifecycle_models import DecisionContext

    ctx = DecisionContext(
        id=_next_context_id(),
        account_id=account_id,
        fill_id=fill_id,
        context_type=kwargs.get("context_type", "entry"),
        strategy_id=kwargs.get("strategy_id"),
        hypothesis=kwargs.get("hypothesis", "Price will bounce off support"),
        exit_intent=kwargs.get("exit_intent"),
        feelings_then=kwargs.get("feelings_then"),
        feelings_now=kwargs.get("feelings_now"),
        notes=kwargs.get("notes", "Strong volume at support"),
    )
    db_session.add(ctx)
    db_session.flush()
    return ctx


def _create_campaign_check(db_session: Session, decision_context_id: int, account_id: int, **kwargs):
    """Create a CampaignCheck record."""
    from src.data.database.trade_lifecycle_models import CampaignCheck

    check = CampaignCheck(
        id=_next_check_id(),
        decision_context_id=decision_context_id,
        account_id=account_id,
        check_type=kwargs.get("check_type", "risk_sanity"),
        check_name=kwargs.get("check_name", "RS001"),
        severity=kwargs.get("severity", "warn"),
        passed=kwargs.get("passed", True),
        details=kwargs.get("details", {"code": "RS001"}),
        nudge_text=kwargs.get("nudge_text", "Consider your position size"),
        acknowledged=kwargs.get("acknowledged"),
        trader_action=kwargs.get("trader_action"),
        checked_at=kwargs.get(
            "checked_at", datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc)
        ),
        check_phase=kwargs.get("check_phase", "pre_trade"),
    )
    db_session.add(check)
    db_session.flush()
    return check


def _create_strategy(db_session: Session, account_id: int, **kwargs):
    """Create a Strategy record."""
    from src.data.database.strategy_models import Strategy

    strategy = Strategy(
        account_id=account_id,
        name=kwargs.get("name", "momentum"),
        description=kwargs.get("description"),
        is_active=True,
    )
    db_session.add(strategy)
    db_session.flush()
    return strategy


def _build_campaign_with_fills(
    db_session: Session,
    account_id: int,
    symbol: str = "AAPL",
    strategy_id=None,
    fills_spec=None,
):
    """Helper that creates a campaign, fills, and links them together.

    fills_spec is a list of dicts with keys: side, quantity, price, fees,
    executed_at, order_id. Defaults to a simple buy-then-sell round trip.

    Returns (campaign, list_of_fills).
    """
    if fills_spec is None:
        fills_spec = [
            {"side": "buy", "quantity": 10, "price": 150.0, "fees": 0.0,
             "executed_at": datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
             "order_id": "ord_buy_1"},
            {"side": "sell", "quantity": 10, "price": 155.0, "fees": 0.0,
             "executed_at": datetime(2025, 1, 12, 14, 0, tzinfo=timezone.utc),
             "order_id": "ord_sell_1"},
        ]

    campaign = _create_campaign(
        db_session, account_id, symbol=symbol, strategy_id=strategy_id,
    )

    fills = []
    for spec in fills_spec:
        fill = _create_fill(db_session, account_id, symbol=symbol, **spec)
        _link_fill_to_campaign(db_session, campaign.id, fill.id)
        fills.append(fill)

    return campaign, fills


# ---------------------------------------------------------------------------
# List Campaigns
# ---------------------------------------------------------------------------


class TestListCampaigns:
    """GET /api/campaigns"""

    def test_empty_list_for_new_user(self, client, test_account):
        """User with no campaigns should get an empty list."""
        response = client.get("/api/campaigns")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_user_campaigns(self, client, test_account, db_session: Session):
        """Should return campaigns for the authenticated user."""
        _build_campaign_with_fills(db_session, TEST_USER_ID, symbol="AAPL")
        _build_campaign_with_fills(db_session, TEST_USER_ID, symbol="MSFT")

        response = client.get("/api/campaigns")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        symbols = {c["symbol"] for c in data}
        assert symbols == {"AAPL", "MSFT"}

    def test_filter_by_symbol(self, client, test_account, db_session: Session):
        """Should filter campaigns by symbol query param (case-insensitive)."""
        _build_campaign_with_fills(db_session, TEST_USER_ID, symbol="AAPL")
        _build_campaign_with_fills(db_session, TEST_USER_ID, symbol="MSFT")

        response = client.get("/api/campaigns", params={"symbol": "aapl"})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    def test_filter_by_strategy(self, client, test_account, db_session: Session):
        """Should filter campaigns by strategy_id."""
        strategy = _create_strategy(db_session, TEST_USER_ID, name="breakout")
        _build_campaign_with_fills(
            db_session, TEST_USER_ID, symbol="AAPL", strategy_id=strategy.id,
        )
        _build_campaign_with_fills(db_session, TEST_USER_ID, symbol="MSFT")

        response = client.get(
            "/api/campaigns", params={"strategy_id": strategy.id},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"
        assert data[0]["strategyName"] == "breakout"

    def test_campaign_summary_has_computed_fields(
        self, client, test_account, db_session: Session,
    ):
        """Summary should include direction, status, net qty, P&L computed from fills."""
        _build_campaign_with_fills(
            db_session, TEST_USER_ID, symbol="AAPL",
            fills_spec=[
                {"side": "buy", "quantity": 10, "price": 150.0, "fees": 1.0,
                 "executed_at": datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
                 "order_id": "ord_b1"},
                {"side": "sell", "quantity": 10, "price": 160.0, "fees": 1.0,
                 "executed_at": datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
                 "order_id": "ord_s1"},
            ],
        )

        response = client.get("/api/campaigns")
        data = response.json()
        assert len(data) == 1

        summary = data[0]
        assert summary["direction"] == "long"
        assert summary["status"] == "closed"
        assert summary["fillCount"] == 2
        assert summary["netQuantity"] == 0.0
        assert summary["totalBought"] == 10.0
        assert summary["totalSold"] == 10.0
        # Realized P&L = 10 * (160 - 150) - 2 fees = 98.0
        assert summary["realizedPnl"] == 98.0
        assert set(summary["orderIds"]) == {"ord_b1", "ord_s1"}

    def test_does_not_return_other_users_campaigns(
        self, client, test_account, other_account, db_session: Session,
    ):
        """Multi-tenant isolation for campaigns."""
        _build_campaign_with_fills(db_session, TEST_USER_ID, symbol="AAPL")
        _build_campaign_with_fills(db_session, OTHER_USER_ID, symbol="TSLA")

        response = client.get("/api/campaigns")
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Campaign Detail
# ---------------------------------------------------------------------------


class TestCampaignDetail:
    """GET /api/campaigns/{campaign_id}"""

    def test_returns_detail_with_fills(
        self, client, test_account, db_session: Session,
    ):
        """Should return campaign detail with fills."""
        campaign, fills = _build_campaign_with_fills(
            db_session, TEST_USER_ID, symbol="AAPL",
        )

        response = client.get(f"/api/campaigns/{campaign.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["campaignId"] == str(campaign.id)
        assert data["symbol"] == "AAPL"
        assert data["direction"] == "long"
        assert data["status"] == "closed"
        assert data["fillCount"] == 2
        assert len(data["fills"]) == 2
        assert data["fills"][0]["side"] == "buy"
        assert data["fills"][1]["side"] == "sell"

    def test_detail_includes_checks(
        self, client, test_account, db_session: Session,
    ):
        """Campaign detail should include checks from decision contexts."""
        campaign, fills = _build_campaign_with_fills(
            db_session, TEST_USER_ID, symbol="AAPL",
        )
        ctx = _create_decision_context(
            db_session, TEST_USER_ID, fills[0].id,
        )
        _create_campaign_check(
            db_session, ctx.id, TEST_USER_ID,
            check_type="overtrading",
            severity="warn",
            passed=False,
            nudge_text="You traded 5 times today",
        )

        response = client.get(f"/api/campaigns/{campaign.id}")
        data = response.json()
        assert len(data["checks"]) == 1
        check = data["checks"][0]
        assert check["checkType"] == "overtrading"
        assert check["passed"] is False
        assert check["nudgeText"] == "You traded 5 times today"
        assert check["fillId"] == str(fills[0].id)

    def test_detail_fills_include_context_info(
        self, client, test_account, db_session: Session,
    ):
        """Fills in the detail should include context type and hypothesis."""
        campaign, fills = _build_campaign_with_fills(
            db_session, TEST_USER_ID, symbol="AAPL",
        )
        _create_decision_context(
            db_session, TEST_USER_ID, fills[0].id,
            context_type="entry",
            hypothesis="Breaking out of consolidation",
        )

        response = client.get(f"/api/campaigns/{campaign.id}")
        data = response.json()
        entry_fill = data["fills"][0]
        assert entry_fill["contextType"] == "entry"
        assert entry_fill["hypothesis"] == "Breaking out of consolidation"

    def test_nonexistent_returns_404(self, client, test_account):
        """Fetching a non-existent campaign should return 404."""
        response = client.get("/api/campaigns/99999")
        assert response.status_code == 404

    def test_other_users_campaign_returns_403(
        self, client, test_account, other_account, db_session: Session,
    ):
        """Viewing another user's campaign should return 403."""
        other_campaign, _ = _build_campaign_with_fills(
            db_session, OTHER_USER_ID, symbol="TSLA",
        )
        response = client.get(f"/api/campaigns/{other_campaign.id}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Fill Context — GET
# ---------------------------------------------------------------------------


class TestGetFillContext:
    """GET /api/campaigns/fills/{fill_id}/context"""

    def test_returns_context_for_fill(
        self, client, test_account, db_session: Session,
    ):
        """Should return the decision context for a fill."""
        fill = _create_fill(db_session, TEST_USER_ID, symbol="AAPL")
        ctx = _create_decision_context(
            db_session, TEST_USER_ID, fill.id,
            hypothesis="Breakout above resistance",
        )

        response = client.get(f"/api/campaigns/fills/{fill.id}/context")
        assert response.status_code == 200

        data = response.json()
        assert data["contextId"] == str(ctx.id)
        assert data["fillId"] == str(fill.id)
        assert data["contextType"] == "entry"
        assert data["hypothesis"] == "Breakout above resistance"

    def test_returns_404_when_no_context(
        self, client, test_account, db_session: Session,
    ):
        """Should return 404 if no context exists for the fill."""
        fill = _create_fill(db_session, TEST_USER_ID, symbol="AAPL")

        response = client.get(f"/api/campaigns/fills/{fill.id}/context")
        assert response.status_code == 404

    def test_returns_404_for_nonexistent_fill(self, client, test_account):
        """Should return 404 for unknown fill id."""
        response = client.get("/api/campaigns/fills/99999/context")
        assert response.status_code == 404

    def test_cannot_access_other_users_fill_context(
        self, client, test_account, other_account, db_session: Session,
    ):
        """Multi-tenant isolation: cannot see another user's fill context."""
        fill = _create_fill(db_session, OTHER_USER_ID, symbol="AAPL")
        _create_decision_context(db_session, OTHER_USER_ID, fill.id)

        response = client.get(f"/api/campaigns/fills/{fill.id}/context")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Fill Context — PUT (save/update)
# ---------------------------------------------------------------------------


class TestSaveFillContext:
    """PUT /api/campaigns/fills/{fill_id}/context"""

    def test_create_new_context(self, client, test_account, db_session: Session):
        """Should create a new decision context for a fill."""
        fill = _create_fill(db_session, TEST_USER_ID, symbol="AAPL")

        payload = {
            "contextType": "entry",
            "hypothesis": "Breakout above resistance",
            "exitIntent": "trailing_stop",
            "notes": "Volume confirming",
        }
        response = client.put(
            f"/api/campaigns/fills/{fill.id}/context", json=payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["hypothesis"] == "Breakout above resistance"
        assert data["contextType"] == "entry"
        assert data["notes"] == "Volume confirming"
        assert data["fillId"] == str(fill.id)

        # Verify in DB
        from src.data.database.trade_lifecycle_models import DecisionContext

        ctx = db_session.query(DecisionContext).filter(
            DecisionContext.fill_id == fill.id,
        ).first()
        assert ctx is not None
        assert ctx.hypothesis == "Breakout above resistance"

    def test_update_existing_context(
        self, client, test_account, db_session: Session,
    ):
        """Should update an existing context on repeated PUT."""
        fill = _create_fill(db_session, TEST_USER_ID, symbol="AAPL")
        _create_decision_context(
            db_session, TEST_USER_ID, fill.id, hypothesis="Original",
        )

        payload = {
            "contextType": "entry",
            "hypothesis": "Updated hypothesis",
        }
        response = client.put(
            f"/api/campaigns/fills/{fill.id}/context", json=payload,
        )
        assert response.status_code == 200
        assert response.json()["hypothesis"] == "Updated hypothesis"

    @pytest.mark.xfail(
        reason=(
            "In-memory SQLite + SingletonThreadPool: save_fill_context calls "
            "db.commit() then queries Strategy via _context_to_response(). "
            "TestClient runs async endpoints on a worker thread, which gets "
            "a different in-memory database. Needs StaticPool to fix."
        ),
        strict=False,
    )
    def test_save_context_with_strategy_name(
        self, client, test_account, db_session: Session,
    ):
        """Should resolve strategyName to strategy_id when saving context."""
        fill = _create_fill(db_session, TEST_USER_ID, symbol="AAPL")
        strategy = _create_strategy(db_session, TEST_USER_ID, name="breakout")

        payload = {
            "contextType": "entry",
            "strategyName": "breakout",
            "hypothesis": "Breaking out",
        }
        response = client.put(
            f"/api/campaigns/fills/{fill.id}/context", json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["strategyName"] == "breakout"

        # Verify strategy_id set in DB
        from src.data.database.trade_lifecycle_models import DecisionContext

        ctx = db_session.query(DecisionContext).filter(
            DecisionContext.fill_id == fill.id,
        ).first()
        assert ctx.strategy_id == strategy.id

    def test_save_context_with_feelings(
        self, client, test_account, db_session: Session,
    ):
        """Should save feelings_then and feelings_now as JSONB."""
        fill = _create_fill(db_session, TEST_USER_ID, symbol="AAPL")

        payload = {
            "contextType": "entry",
            "hypothesis": "Testing feelings",
            "feelingsThen": {"confidence": "high", "mood": "excited"},
            "feelingsNow": {"confidence": "low", "mood": "regretful"},
        }
        response = client.put(
            f"/api/campaigns/fills/{fill.id}/context", json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feelingsThen"]["confidence"] == "high"
        assert data["feelingsNow"]["mood"] == "regretful"

    def test_context_on_nonexistent_fill_returns_404(
        self, client, test_account,
    ):
        """Saving context on a non-existent fill should return 404."""
        payload = {
            "contextType": "entry",
            "hypothesis": "Test",
        }
        response = client.put(
            "/api/campaigns/fills/99999/context", json=payload,
        )
        assert response.status_code == 404

    def test_context_on_other_users_fill_returns_404(
        self, client, test_account, other_account, db_session: Session,
    ):
        """Cannot save context on another user's fill (returns 404)."""
        fill = _create_fill(db_session, OTHER_USER_ID, symbol="AAPL")

        payload = {
            "contextType": "entry",
            "hypothesis": "Hacked",
        }
        response = client.put(
            f"/api/campaigns/fills/{fill.id}/context", json=payload,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# P&L by Ticker
# ---------------------------------------------------------------------------


class TestPnlByTicker:
    """GET /api/campaigns/pnl/by-ticker"""

    def test_empty_when_no_fills(self, client, test_account):
        """User with no fills should get empty tickers list."""
        response = client.get("/api/campaigns/pnl/by-ticker")
        assert response.status_code == 200
        assert response.json()["tickers"] == []

    def test_aggregates_pnl_by_symbol(
        self, client, test_account, db_session: Session,
    ):
        """Should aggregate P&L from fills across campaigns for each symbol."""
        # Buy 10 AAPL @ 150, Sell 10 AAPL @ 160 => P&L = 100
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=150.0, fees=0.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="sell",
            quantity=10, price=160.0, fees=0.0,
            executed_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        )

        # Also create a campaign for the count
        campaign = _create_campaign(db_session, TEST_USER_ID, symbol="AAPL")

        response = client.get("/api/campaigns/pnl/by-ticker")
        assert response.status_code == 200

        data = response.json()
        assert len(data["tickers"]) == 1
        ticker = data["tickers"][0]
        assert ticker["symbol"] == "AAPL"
        assert ticker["total_pnl"] == 100.0
        assert ticker["fill_count"] == 2
        assert ticker["campaign_count"] == 1

    def test_does_not_include_other_users_fills(
        self, client, test_account, other_account, db_session: Session,
    ):
        """Multi-tenant isolation: P&L only includes own fills."""
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=150.0,
        )
        _create_fill(
            db_session, OTHER_USER_ID, symbol="TSLA", side="buy",
            quantity=5, price=200.0,
        )

        response = client.get("/api/campaigns/pnl/by-ticker")
        data = response.json()
        symbols = [t["symbol"] for t in data["tickers"]]
        assert "AAPL" in symbols
        assert "TSLA" not in symbols


# ---------------------------------------------------------------------------
# Ticker P&L
# ---------------------------------------------------------------------------


class TestTickerPnl:
    """GET /api/campaigns/pnl/{symbol}"""

    def test_returns_zero_for_unknown_symbol(self, client, test_account):
        """Unknown symbol should return zero P&L, not 404."""
        response = client.get("/api/campaigns/pnl/ZZZZ")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "ZZZZ"
        assert data["total_pnl"] == 0.0
        assert data["fill_count"] == 0

    def test_returns_correct_pnl_for_symbol(
        self, client, test_account, db_session: Session,
    ):
        """Should return correct aggregate P&L for a known symbol."""
        # Buy 10 TSLA @ 250, Sell 10 TSLA @ 270 => P&L = 200
        _create_fill(
            db_session, TEST_USER_ID, symbol="TSLA", side="buy",
            quantity=10, price=250.0, fees=0.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        _create_fill(
            db_session, TEST_USER_ID, symbol="TSLA", side="sell",
            quantity=10, price=270.0, fees=0.0,
            executed_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        )

        # Create a campaign for the campaign_count
        _create_campaign(db_session, TEST_USER_ID, symbol="TSLA")

        response = client.get("/api/campaigns/pnl/TSLA")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "TSLA"
        assert data["total_pnl"] == 200.0
        assert data["fill_count"] == 2
        assert data["campaign_count"] == 1

    def test_pnl_deducts_fees(
        self, client, test_account, db_session: Session,
    ):
        """Fees should be subtracted from realized P&L."""
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=100.0, fees=5.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="sell",
            quantity=10, price=110.0, fees=5.0,
            executed_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        )

        response = client.get("/api/campaigns/pnl/AAPL")
        data = response.json()
        # P&L = 10 * (110 - 100) - 10 fees = 90
        assert data["total_pnl"] == 90.0

    def test_case_insensitive_symbol_lookup(
        self, client, test_account, db_session: Session,
    ):
        """Symbol lookup should be case-insensitive (uppercased)."""
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=100.0,
        )

        response = client.get("/api/campaigns/pnl/aapl")
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["fill_count"] == 1


# ---------------------------------------------------------------------------
# P&L Timeseries
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "Endpoint uses func.case() with else_ keyword which is incompatible "
        "with SQLite. This is PostgreSQL-specific SQL generation in "
        "get_pnl_timeseries and will work correctly against Postgres."
    ),
    strict=False,
)
class TestPnlTimeseries:
    """GET /api/campaigns/pnl/timeseries"""

    def test_empty_timeseries(self, client, test_account):
        """No fills should return empty timeseries."""
        response = client.get("/api/campaigns/pnl/timeseries")
        assert response.status_code == 200
        data = response.json()
        assert data["points"] == []
        assert data["total_pnl"] == 0.0

    def test_timeseries_with_fills(
        self, client, test_account, db_session: Session,
    ):
        """Should return timeseries points grouped by day."""
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=150.0, fees=0.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="sell",
            quantity=10, price=160.0, fees=0.0,
            executed_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        )

        response = client.get("/api/campaigns/pnl/timeseries")
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) >= 1
        assert data["total_pnl"] != 0.0

    def test_timeseries_filter_by_symbol(
        self, client, test_account, db_session: Session,
    ):
        """Should filter timeseries by symbol."""
        _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=150.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        _create_fill(
            db_session, TEST_USER_ID, symbol="TSLA", side="buy",
            quantity=5, price=200.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )

        response = client.get(
            "/api/campaigns/pnl/timeseries", params={"symbol": "AAPL"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Rebuild Campaigns
# ---------------------------------------------------------------------------


class TestRebuildCampaigns:
    """POST /api/campaigns/rebuild"""

    def test_rebuild_returns_stats(
        self, client, test_account, db_session: Session,
    ):
        """Rebuild should return stats on campaigns created."""
        # Create fills with decision contexts (rebuild needs them)
        fill1 = _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=150.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        fill2 = _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="sell",
            quantity=10, price=160.0,
            executed_at=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        )

        response = client.post("/api/campaigns/rebuild")
        assert response.status_code == 200

        data = response.json()
        assert "campaigns_created" in data
        assert "fills_grouped" in data
        assert "groups_rebuilt" in data

    def test_rebuild_with_symbol_filter(
        self, client, test_account, db_session: Session,
    ):
        """Rebuild with symbol filter should only rebuild that symbol."""
        fill1 = _create_fill(
            db_session, TEST_USER_ID, symbol="AAPL", side="buy",
            quantity=10, price=150.0,
            executed_at=datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc),
        )
        # Assign a decision context so there is a strategy group to rebuild
        _create_decision_context(db_session, TEST_USER_ID, fill1.id)

        response = client.post(
            "/api/campaigns/rebuild", params={"symbol": "AAPL"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "campaigns_created" in data
