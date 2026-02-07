"""Tests for user profile, risk preferences, and evaluation controls API endpoints.

Endpoints under test:
- GET  /api/user/profile
- PUT  /api/user/profile
- GET  /api/user/risk-preferences
- PUT  /api/user/risk-preferences
- GET  /api/user/evaluation-controls
- PUT  /api/user/evaluation-controls
- GET  /api/user/risk  (legacy)
- PUT  /api/user/risk  (legacy)
"""

import pytest
from sqlalchemy.orm import Session

from tests.unit.api.conftest import TEST_USER_ID


# ---------------------------------------------------------------------------
# Trading Profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    """GET /api/user/profile"""

    def test_returns_default_profile_for_new_user(self, client, test_account):
        """New user with no profile row should get sensible defaults."""
        response = client.get("/api/user/profile")
        assert response.status_code == 200

        data = response.json()
        assert data["experience_level"] == "beginner"
        assert data["trading_style"] == "day_trading"
        assert isinstance(data["primary_markets"], list)
        assert isinstance(data["typical_timeframes"], list)

    def test_returns_existing_profile_fields(self, client, test_account, db_session: Session):
        """When a profile row already exists, its fields are returned."""
        from src.data.database.trading_buddy_models import UserProfile

        profile = UserProfile(
            user_account_id=TEST_USER_ID,
            experience_level="advanced",
            trading_style="swing_trading",
            primary_markets=["CRYPTO"],
            default_timeframes=["1Day"],
            account_size_range="$50k-$100k",
        )
        db_session.add(profile)
        db_session.flush()

        response = client.get("/api/user/profile")
        assert response.status_code == 200

        data = response.json()
        assert data["experience_level"] == "advanced"
        assert data["trading_style"] == "swing_trading"
        assert data["primary_markets"] == ["CRYPTO"]
        assert data["typical_timeframes"] == ["1Day"]
        assert data["account_size_range"] == "$50k-$100k"


class TestUpdateProfile:
    """PUT /api/user/profile"""

    def test_update_all_fields(self, client, test_account, db_session: Session):
        """Full update persists all fields to the database."""
        # Ensure profile exists first (mirrors normal user flow: GET then PUT)
        client.get("/api/user/profile")

        payload = {
            "experience_level": "intermediate",
            "trading_style": "scalping",
            "primary_markets": ["FOREX"],
            "typical_timeframes": ["5Min"],
            "account_size_range": "$100k+",
        }
        response = client.put("/api/user/profile", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["experience_level"] == "intermediate"
        assert data["trading_style"] == "scalping"
        assert data["primary_markets"] == ["FOREX"]
        assert data["typical_timeframes"] == ["5Min"]
        assert data["account_size_range"] == "$100k+"

        # Verify persistence directly in DB
        from src.data.database.trading_buddy_models import UserProfile

        profile = db_session.query(UserProfile).filter(
            UserProfile.user_account_id == TEST_USER_ID
        ).first()
        assert profile is not None
        assert profile.experience_level == "intermediate"
        assert profile.trading_style == "scalping"

    def test_partial_update_preserves_other_fields(self, client, test_account, db_session: Session):
        """Updating only one field should not reset others."""
        # Create initial profile
        from src.data.database.trading_buddy_models import UserProfile

        profile = UserProfile(
            user_account_id=TEST_USER_ID,
            experience_level="advanced",
            trading_style="swing_trading",
        )
        db_session.add(profile)
        db_session.flush()

        # Update only experience_level
        response = client.put("/api/user/profile", json={"experience_level": "beginner"})
        assert response.status_code == 200

        # Reload from DB
        db_session.refresh(profile)
        assert profile.experience_level == "beginner"
        assert profile.trading_style == "swing_trading"  # unchanged

    def test_empty_update_returns_400(self, client, test_account):
        """Sending no fields to update should return 400."""
        response = client.put("/api/user/profile", json={})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Risk Preferences (frontend format)
# ---------------------------------------------------------------------------


class TestGetRiskPreferences:
    """GET /api/user/risk-preferences"""

    def test_returns_defaults_for_new_user(self, client, test_account):
        """New user should get default risk preferences."""
        response = client.get("/api/user/risk-preferences")
        assert response.status_code == 200

        data = response.json()
        assert "max_loss_per_trade_pct" in data
        assert "max_daily_loss_pct" in data
        assert "max_open_positions" in data
        assert "risk_reward_minimum" in data
        assert isinstance(data["stop_loss_required"], bool)

    def test_returns_persisted_values(self, client, test_account, db_session: Session):
        """When risk settings have been saved, they are returned correctly."""
        from src.data.database.trading_buddy_models import UserProfile

        profile = UserProfile(
            user_account_id=TEST_USER_ID,
            max_risk_per_trade_pct=2.5,
            max_daily_loss_pct=5.0,
            max_open_positions=10,
            min_risk_reward_ratio=3.0,
            stop_loss_required=False,
        )
        db_session.add(profile)
        db_session.flush()

        response = client.get("/api/user/risk-preferences")
        assert response.status_code == 200

        data = response.json()
        assert data["max_loss_per_trade_pct"] == 2.5
        assert data["max_daily_loss_pct"] == 5.0
        assert data["max_open_positions"] == 10
        assert data["risk_reward_minimum"] == 3.0
        assert data["stop_loss_required"] is False


class TestUpdateRiskPreferences:
    """PUT /api/user/risk-preferences"""

    def test_update_saves_all_fields(self, client, test_account, db_session: Session):
        """PUT should save all risk fields and return them."""
        # Ensure profile exists first (mirrors normal user flow)
        client.get("/api/user/risk-preferences")

        payload = {
            "max_loss_per_trade_pct": 1.5,
            "max_daily_loss_pct": 4.0,
            "max_open_positions": 8,
            "risk_reward_minimum": 2.5,
            "stop_loss_required": True,
        }
        response = client.put("/api/user/risk-preferences", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["max_loss_per_trade_pct"] == 1.5
        assert data["max_daily_loss_pct"] == 4.0
        assert data["max_open_positions"] == 8
        assert data["risk_reward_minimum"] == 2.5
        assert data["stop_loss_required"] is True

        # Verify in DB
        from src.data.database.trading_buddy_models import UserProfile

        profile = db_session.query(UserProfile).filter(
            UserProfile.user_account_id == TEST_USER_ID
        ).first()
        assert profile.max_risk_per_trade_pct == 1.5
        assert profile.max_open_positions == 8

    def test_empty_update_returns_400(self, client, test_account):
        """Empty body should be rejected."""
        response = client.put("/api/user/risk-preferences", json={})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Evaluation Controls
# ---------------------------------------------------------------------------


class TestGetEvaluationControls:
    """GET /api/user/evaluation-controls"""

    def test_returns_defaults_for_new_user(self, client, test_account):
        """A new user should get the default evaluation controls."""
        response = client.get("/api/user/evaluation-controls")
        assert response.status_code == 200

        data = response.json()
        assert "evaluators_enabled" in data
        assert isinstance(data["evaluators_enabled"], dict)
        assert "severity_threshold" in data

    def test_returns_saved_controls(self, client, test_account, db_session: Session):
        """When custom controls are saved, they are returned."""
        from src.data.database.trading_buddy_models import UserProfile

        custom_controls = {
            "evaluators_enabled": {"regime_fit": False, "behavioral": True},
            "auto_evaluate_synced": True,
            "notification_on_blocker": False,
            "severity_threshold": "critical",
        }
        profile = UserProfile(
            user_account_id=TEST_USER_ID,
            evaluation_controls=custom_controls,
        )
        db_session.add(profile)
        db_session.flush()

        response = client.get("/api/user/evaluation-controls")
        assert response.status_code == 200

        data = response.json()
        assert data["auto_evaluate_synced"] is True
        assert data["notification_on_blocker"] is False
        assert data["severity_threshold"] == "critical"


class TestUpdateEvaluationControls:
    """PUT /api/user/evaluation-controls"""

    def test_update_merges_with_existing(self, client, test_account, db_session: Session):
        """Updating evaluation controls should merge with existing values."""
        payload = {"severity_threshold": "blocker", "auto_evaluate_synced": True}
        response = client.put("/api/user/evaluation-controls", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["severity_threshold"] == "blocker"
        assert data["auto_evaluate_synced"] is True
        # Default values should still be present
        assert "evaluators_enabled" in data

    def test_update_persists_to_db(self, client, test_account, db_session: Session):
        """Verify controls are actually saved to the profile record."""
        payload = {"notification_on_blocker": False}
        response = client.put("/api/user/evaluation-controls", json=payload)
        assert response.status_code == 200

        from src.data.database.trading_buddy_models import UserProfile

        profile = db_session.query(UserProfile).filter(
            UserProfile.user_account_id == TEST_USER_ID
        ).first()
        assert profile is not None
        assert profile.evaluation_controls is not None
        assert profile.evaluation_controls["notification_on_blocker"] is False


# ---------------------------------------------------------------------------
# Legacy Risk Endpoints
# ---------------------------------------------------------------------------


class TestLegacyRisk:
    """GET/PUT /api/user/risk (legacy format)"""

    def test_get_legacy_risk_defaults(self, client, test_account):
        """GET should return default risk values for a new user."""
        response = client.get("/api/user/risk")
        assert response.status_code == 200

        data = response.json()
        assert "max_position_size_pct" in data
        assert "max_risk_per_trade_pct" in data
        assert "max_daily_loss_pct" in data
        assert "min_risk_reward_ratio" in data

    def test_put_legacy_risk_saves_fields(self, client, test_account, db_session: Session):
        """PUT should save legacy risk fields."""
        payload = {
            "max_position_size_pct": 10.0,
            "max_risk_per_trade_pct": 2.0,
        }
        response = client.put("/api/user/risk", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["max_position_size_pct"] == 10.0
        assert data["max_risk_per_trade_pct"] == 2.0

    def test_put_legacy_risk_empty_returns_400(self, client, test_account):
        """Empty update should be rejected."""
        response = client.put("/api/user/risk", json={})
        assert response.status_code == 400
