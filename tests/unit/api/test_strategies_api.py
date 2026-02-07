"""Tests for the strategies CRUD API endpoints.

Endpoints under test:
- GET  /api/user/strategies
- POST /api/user/strategies
- PUT  /api/user/strategies/{id}
"""

import pytest
from sqlalchemy.orm import Session

from tests.unit.api.conftest import TEST_USER_ID, OTHER_USER_ID


def _create_strategy(db_session: Session, account_id: int, name: str, **kwargs):
    """Helper to insert a strategy directly into the database."""
    from src.data.database.strategy_models import Strategy

    strategy = Strategy(
        account_id=account_id,
        name=name,
        description=kwargs.get("description", ""),
        direction=kwargs.get("direction", "both"),
        timeframes=kwargs.get("timeframes", []),
        entry_criteria=kwargs.get("entry_criteria", ""),
        exit_criteria=kwargs.get("exit_criteria", ""),
        max_risk_pct=kwargs.get("max_risk_pct", 2.0),
        min_risk_reward=kwargs.get("min_risk_reward", 1.5),
        is_active=kwargs.get("is_active", True),
    )
    db_session.add(strategy)
    db_session.flush()
    return strategy


# ---------------------------------------------------------------------------
# List Strategies
# ---------------------------------------------------------------------------


class TestListStrategies:
    """GET /api/user/strategies"""

    def test_empty_list_for_new_user(self, client, test_account):
        """User with no strategies should get an empty list."""
        response = client.get("/api/user/strategies")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_all_strategies_for_user(self, client, test_account, db_session: Session):
        """Should return all strategies belonging to the authenticated user."""
        _create_strategy(db_session, TEST_USER_ID, "Breakout Long")
        _create_strategy(db_session, TEST_USER_ID, "Mean Reversion")

        response = client.get("/api/user/strategies")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        names = {s["name"] for s in data}
        assert names == {"Breakout Long", "Mean Reversion"}

    def test_does_not_return_other_users_strategies(
        self, client, test_account, other_account, db_session: Session
    ):
        """Multi-tenant isolation: user A should not see user B's strategies."""
        _create_strategy(db_session, TEST_USER_ID, "My Strategy")
        _create_strategy(db_session, OTHER_USER_ID, "Other Strategy")

        response = client.get("/api/user/strategies")
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "My Strategy"


# ---------------------------------------------------------------------------
# Create Strategy
# ---------------------------------------------------------------------------


class TestCreateStrategy:
    """POST /api/user/strategies"""

    def test_create_with_valid_data(self, client, test_account, db_session: Session):
        """Creating a strategy with valid data should return 201."""
        payload = {
            "name": "VWAP Scalp",
            "description": "Scalp around VWAP",
            "direction": "long",
            "timeframes": ["1Min", "5Min"],
            "entry_criteria": "Price crosses VWAP from below",
            "exit_criteria": "Price reaches 2R",
            "max_risk_pct": 1.0,
            "min_risk_reward": 2.0,
        }
        response = client.post("/api/user/strategies", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "VWAP Scalp"
        assert data["direction"] == "long"
        assert data["is_active"] is True
        assert "id" in data

        # Verify persisted to DB
        from src.data.database.strategy_models import Strategy

        db_strategy = db_session.query(Strategy).filter(Strategy.name == "VWAP Scalp").first()
        assert db_strategy is not None
        assert db_strategy.account_id == TEST_USER_ID
        assert db_strategy.description == "Scalp around VWAP"

    def test_create_with_defaults(self, client, test_account):
        """Creating with only name should apply defaults for other fields."""
        response = client.post("/api/user/strategies", json={"name": "Simple"})
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Simple"
        assert data["direction"] == "both"
        assert data["max_risk_pct"] == 2.0

    def test_create_empty_name_returns_400(self, client, test_account):
        """Blank strategy name should be rejected."""
        response = client.post("/api/user/strategies", json={"name": "   "})
        assert response.status_code == 400

    def test_create_duplicate_name_returns_409(self, client, test_account, db_session: Session):
        """Duplicate strategy name for the same user should return 409."""
        _create_strategy(db_session, TEST_USER_ID, "Alpha")
        response = client.post("/api/user/strategies", json={"name": "Alpha"})
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Update Strategy
# ---------------------------------------------------------------------------


class TestUpdateStrategy:
    """PUT /api/user/strategies/{id}"""

    def test_update_existing_strategy(self, client, test_account, db_session: Session):
        """Should update specified fields and return the updated strategy."""
        strategy = _create_strategy(db_session, TEST_USER_ID, "Original Name")

        payload = {"name": "Renamed", "direction": "short", "is_active": False}
        response = client.put(f"/api/user/strategies/{strategy.id}", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Renamed"
        assert data["direction"] == "short"
        assert data["is_active"] is False

        # Verify persistence
        db_session.refresh(strategy)
        assert strategy.name == "Renamed"
        assert strategy.direction == "short"
        assert strategy.is_active is False

    def test_update_nonexistent_returns_404(self, client, test_account):
        """Updating a strategy that does not exist should return 404."""
        response = client.put("/api/user/strategies/99999", json={"name": "X"})
        assert response.status_code == 404

    def test_update_other_users_strategy_returns_403(
        self, client, test_account, other_account, db_session: Session
    ):
        """User should not be able to update another user's strategy."""
        other_strategy = _create_strategy(db_session, OTHER_USER_ID, "Their Strategy")

        response = client.put(
            f"/api/user/strategies/{other_strategy.id}",
            json={"name": "Hacked"},
        )
        assert response.status_code == 403

    def test_update_empty_body_returns_400(self, client, test_account, db_session: Session):
        """Sending no fields to update should return 400."""
        strategy = _create_strategy(db_session, TEST_USER_ID, "S1")
        response = client.put(f"/api/user/strategies/{strategy.id}", json={})
        assert response.status_code == 400
