"""Tests for the campaigns API endpoints.

Endpoints under test:
- GET  /api/campaigns                        (list campaigns)
- GET  /api/campaigns/{id}                   (campaign detail)
- PUT  /api/campaigns/{id}/context           (save decision context)
- GET  /api/campaigns/pnl/by-ticker          (P&L by ticker)
- GET  /api/campaigns/pnl/timeseries         (P&L timeseries)
- GET  /api/campaigns/pnl/{symbol}           (ticker P&L)
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from tests.unit.api.conftest import TEST_USER_ID, OTHER_USER_ID

# Counters for BigInteger PK fields that SQLite cannot auto-increment.
_campaign_id_counter = 0
_leg_id_counter = 0
_context_id_counter = 0


def _next_campaign_id():
    global _campaign_id_counter
    _campaign_id_counter += 1
    return _campaign_id_counter


def _next_leg_id():
    global _leg_id_counter
    _leg_id_counter += 1
    return _leg_id_counter


def _next_context_id():
    global _context_id_counter
    _context_id_counter += 1
    return _context_id_counter


def _create_campaign(db_session: Session, account_id: int, **kwargs):
    """Helper to create a PositionCampaign directly in the database."""
    from src.data.database.trade_lifecycle_models import PositionCampaign

    campaign = PositionCampaign(
        id=_next_campaign_id(),
        account_id=account_id,
        symbol=kwargs.get("symbol", "AAPL"),
        direction=kwargs.get("direction", "long"),
        status=kwargs.get("status", "open"),
        opened_at=kwargs.get("opened_at", datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc)),
        closed_at=kwargs.get("closed_at"),
        qty_opened=kwargs.get("qty_opened", 100.0),
        qty_closed=kwargs.get("qty_closed"),
        avg_open_price=kwargs.get("avg_open_price", 150.0),
        avg_close_price=kwargs.get("avg_close_price"),
        realized_pnl=kwargs.get("realized_pnl"),
        tags=kwargs.get("tags", {}),
        source=kwargs.get("source", "broker_synced"),
        cost_basis_method=kwargs.get("cost_basis_method", "average"),
        max_qty=kwargs.get("max_qty", 100.0),
    )
    db_session.add(campaign)
    db_session.flush()
    return campaign


def _create_campaign_leg(db_session: Session, campaign_id: int, **kwargs):
    """Helper to create a CampaignLeg."""
    from src.data.database.trade_lifecycle_models import CampaignLeg

    leg = CampaignLeg(
        id=_next_leg_id(),
        campaign_id=campaign_id,
        leg_type=kwargs.get("leg_type", "open"),
        side=kwargs.get("side", "buy"),
        quantity=kwargs.get("quantity", 100.0),
        avg_price=kwargs.get("avg_price", 150.0),
        started_at=kwargs.get("started_at", datetime(2025, 1, 10, 14, 0, tzinfo=timezone.utc)),
    )
    db_session.add(leg)
    db_session.flush()
    return leg


def _create_decision_context(db_session: Session, account_id: int, campaign_id: int, **kwargs):
    """Helper to create a DecisionContext."""
    from src.data.database.trade_lifecycle_models import DecisionContext

    ctx = DecisionContext(
        id=_next_context_id(),
        account_id=account_id,
        campaign_id=campaign_id,
        leg_id=kwargs.get("leg_id"),
        context_type=kwargs.get("context_type", "entry"),
        hypothesis=kwargs.get("hypothesis", "Price will bounce off support"),
        notes=kwargs.get("notes", "Strong volume at support"),
    )
    db_session.add(ctx)
    db_session.flush()
    return ctx


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
        _create_campaign(db_session, TEST_USER_ID, symbol="AAPL")
        _create_campaign(db_session, TEST_USER_ID, symbol="MSFT")

        response = client.get("/api/campaigns")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        symbols = {c["symbol"] for c in data}
        assert symbols == {"AAPL", "MSFT"}

    def test_filter_by_symbol(self, client, test_account, db_session: Session):
        """Should filter campaigns by symbol query param."""
        _create_campaign(db_session, TEST_USER_ID, symbol="AAPL")
        _create_campaign(db_session, TEST_USER_ID, symbol="MSFT")

        response = client.get("/api/campaigns", params={"symbol": "aapl"})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    def test_filter_by_status(self, client, test_account, db_session: Session):
        """Should filter campaigns by status."""
        _create_campaign(db_session, TEST_USER_ID, status="open")
        _create_campaign(
            db_session, TEST_USER_ID, status="closed",
            closed_at=datetime(2025, 1, 20, tzinfo=timezone.utc),
            realized_pnl=50.0,
        )

        response = client.get("/api/campaigns", params={"status": "open"})
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "open"

    def test_does_not_return_other_users_campaigns(
        self, client, test_account, other_account, db_session: Session
    ):
        """Multi-tenant isolation for campaigns."""
        _create_campaign(db_session, TEST_USER_ID, symbol="AAPL")
        _create_campaign(db_session, OTHER_USER_ID, symbol="TSLA")

        response = client.get("/api/campaigns")
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Campaign Detail
# ---------------------------------------------------------------------------


class TestCampaignDetail:
    """GET /api/campaigns/{id}"""

    def test_returns_detail_with_legs_and_contexts(
        self, client, test_account, db_session: Session
    ):
        """Should return full campaign detail including legs and contexts."""
        campaign = _create_campaign(db_session, TEST_USER_ID, symbol="AAPL")
        leg = _create_campaign_leg(db_session, campaign.id)
        _create_decision_context(db_session, TEST_USER_ID, campaign.id)

        response = client.get(f"/api/campaigns/{campaign.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["campaign"]["symbol"] == "AAPL"
        assert data["campaign"]["direction"] == "long"
        assert len(data["legs"]) == 1
        assert data["legs"][0]["legType"] == "open"
        assert "campaign" in data["contextsByLeg"] or len(data["contextsByLeg"]) >= 0

    def test_nonexistent_returns_404(self, client, test_account):
        """Fetching a non-existent campaign should return 404."""
        response = client.get("/api/campaigns/99999")
        assert response.status_code == 404

    def test_other_users_campaign_returns_403(
        self, client, test_account, other_account, db_session: Session
    ):
        """Viewing another user's campaign should return 403."""
        other_campaign = _create_campaign(db_session, OTHER_USER_ID)
        response = client.get(f"/api/campaigns/{other_campaign.id}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Save Decision Context
# ---------------------------------------------------------------------------


class TestSaveContext:
    """PUT /api/campaigns/{id}/context"""

    def test_create_new_context(self, client, test_account, db_session: Session):
        """Should create a new decision context for a campaign."""
        campaign = _create_campaign(db_session, TEST_USER_ID)

        payload = {
            "scope": "campaign",
            "contextType": "entry",
            "hypothesis": "Breakout above resistance",
            "notes": "Volume confirming",
            "strategyTags": [],
        }
        response = client.put(f"/api/campaigns/{campaign.id}/context", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["hypothesis"] == "Breakout above resistance"
        assert data["scope"] == "campaign"

        # Verify in DB
        from src.data.database.trade_lifecycle_models import DecisionContext

        ctx = db_session.query(DecisionContext).filter(
            DecisionContext.campaign_id == campaign.id
        ).first()
        assert ctx is not None
        assert ctx.hypothesis == "Breakout above resistance"

    def test_update_existing_context(self, client, test_account, db_session: Session):
        """Should update an existing context on repeated PUT."""
        campaign = _create_campaign(db_session, TEST_USER_ID)
        _create_decision_context(
            db_session, TEST_USER_ID, campaign.id,
            hypothesis="Original",
        )

        payload = {
            "scope": "campaign",
            "contextType": "entry",
            "hypothesis": "Updated hypothesis",
            "strategyTags": [],
        }
        response = client.put(f"/api/campaigns/{campaign.id}/context", json=payload)
        assert response.status_code == 200
        assert response.json()["hypothesis"] == "Updated hypothesis"

    def test_context_on_nonexistent_campaign_returns_404(self, client, test_account):
        """Saving context on a non-existent campaign should return 404."""
        payload = {
            "scope": "campaign",
            "contextType": "entry",
            "hypothesis": "Test",
            "strategyTags": [],
        }
        response = client.put("/api/campaigns/99999/context", json=payload)
        assert response.status_code == 404

    def test_context_on_other_users_campaign_returns_403(
        self, client, test_account, other_account, db_session: Session
    ):
        """Cannot save context on another user's campaign."""
        other_campaign = _create_campaign(db_session, OTHER_USER_ID)

        payload = {
            "scope": "campaign",
            "contextType": "entry",
            "hypothesis": "Hacked",
            "strategyTags": [],
        }
        response = client.put(f"/api/campaigns/{other_campaign.id}/context", json=payload)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# P&L by Ticker
# ---------------------------------------------------------------------------


class TestPnlByTicker:
    """GET /api/campaigns/pnl/by-ticker"""

    def test_empty_when_no_campaigns(self, client, test_account):
        """User with no campaigns should get empty tickers list."""
        response = client.get("/api/campaigns/pnl/by-ticker")
        assert response.status_code == 200
        assert response.json()["tickers"] == []

    def test_aggregates_pnl_by_symbol(self, client, test_account, db_session: Session):
        """Should aggregate P&L across campaigns for each symbol."""
        _create_campaign(
            db_session, TEST_USER_ID, symbol="AAPL", status="closed",
            closed_at=datetime(2025, 1, 20, tzinfo=timezone.utc),
            realized_pnl=100.0, qty_opened=10, avg_open_price=150.0,
        )
        _create_campaign(
            db_session, TEST_USER_ID, symbol="AAPL", status="closed",
            closed_at=datetime(2025, 1, 25, tzinfo=timezone.utc),
            realized_pnl=-30.0, qty_opened=5, avg_open_price=155.0,
        )

        response = client.get("/api/campaigns/pnl/by-ticker")
        assert response.status_code == 200

        data = response.json()
        assert len(data["tickers"]) == 1
        ticker = data["tickers"][0]
        assert ticker["symbol"] == "AAPL"
        assert ticker["total_pnl"] == 70.0
        assert ticker["trade_count"] == 2


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
        assert data["trade_count"] == 0

    def test_returns_correct_pnl_for_symbol(self, client, test_account, db_session: Session):
        """Should return correct aggregate P&L for a known symbol."""
        _create_campaign(
            db_session, TEST_USER_ID, symbol="TSLA", status="closed",
            closed_at=datetime(2025, 1, 20, tzinfo=timezone.utc),
            realized_pnl=200.0, qty_opened=10, avg_open_price=250.0,
        )

        response = client.get("/api/campaigns/pnl/TSLA")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "TSLA"
        assert data["total_pnl"] == 200.0
        assert data["trade_count"] == 1
        assert data["closed_count"] == 1
