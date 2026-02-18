"""Tests for authentication middleware (get_current_user)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.api.auth_middleware import get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with an endpoint that uses get_current_user."""
    app = FastAPI()

    @app.get("/test-user")
    def get_test_user(user_id: int = Depends(get_current_user)):
        return {"user_id": user_id}

    return app


def _make_token(user_id: int, secret: str = "test-secret", hours: int = 24) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _mock_settings(dev_mode: bool = False, secret: str = "test-secret", dev_user_id: int = 1):
    """Return a mock settings object."""
    settings = MagicMock()
    settings.auth.dev_mode = dev_mode
    settings.auth.dev_user_id = dev_user_id
    settings.auth.jwt_secret_key = secret
    settings.auth.jwt_algorithm = "HS256"
    settings.auth.jwt_expiry_hours = 24
    settings.environment = "development"
    return settings


# ---------------------------------------------------------------------------
# Dev mode tests
# ---------------------------------------------------------------------------


class TestDevMode:
    """Tests for AUTH_DEV_MODE behavior."""

    def test_dev_mode_returns_configured_user_id(self):
        """Dev mode without token should return AUTH_DEV_USER_ID."""
        settings = _mock_settings(dev_mode=True, dev_user_id=8)

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get("/test-user")

        assert resp.status_code == 200
        assert resp.json()["user_id"] == 8

    def test_dev_mode_defaults_to_user_id_1(self):
        """Dev mode without AUTH_DEV_USER_ID should default to 1."""
        settings = _mock_settings(dev_mode=True)

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get("/test-user")

        assert resp.status_code == 200
        assert resp.json()["user_id"] == 1

    def test_dev_mode_with_valid_jwt_uses_token_user_id(self):
        """Dev mode with a valid JWT should use the token's user_id."""
        secret = "test-secret"
        settings = _mock_settings(dev_mode=True, secret=secret)
        token = _make_token(user_id=42, secret=secret)

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert resp.json()["user_id"] == 42

    def test_dev_mode_with_invalid_jwt_falls_back_to_configured_id(self):
        """Dev mode with a bad JWT should fall back to configured dev_user_id."""
        settings = _mock_settings(dev_mode=True, secret="test-secret", dev_user_id=8)

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": "Bearer invalid-token-garbage"},
            )

        assert resp.status_code == 200
        assert resp.json()["user_id"] == 8


# ---------------------------------------------------------------------------
# Production mode tests
# ---------------------------------------------------------------------------


class TestProductionMode:
    """Tests for normal (non-dev) JWT authentication."""

    def test_no_token_returns_401(self):
        """Missing Authorization header should return 401."""
        settings = _mock_settings(dev_mode=False)

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get("/test-user")

        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        """Invalid JWT should return 401."""
        settings = _mock_settings(dev_mode=False, secret="test-secret")

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )

        assert resp.status_code == 401

    def test_expired_token_returns_401(self):
        """Expired JWT should return 401."""
        secret = "test-secret"
        settings = _mock_settings(dev_mode=False, secret=secret)
        token = _make_token(user_id=1, secret=secret, hours=-1)

        app = _make_app()
        with patch("src.api.auth_middleware.get_settings", return_value=settings):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401

    def test_valid_token_with_active_user_returns_200(self):
        """Valid JWT for an active user should return 200 with the user_id."""
        secret = "test-secret"
        settings = _mock_settings(dev_mode=False, secret=secret)
        token = _make_token(user_id=5, secret=secret)

        mock_account = MagicMock()
        mock_account.is_active = True

        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_account.return_value = mock_account

        app = _make_app()
        with (
            patch("src.api.auth_middleware.get_settings", return_value=settings),
            patch("src.api.auth_middleware.session_scope", return_value=mock_ctx),
            patch("src.api.auth_middleware.TradingBuddyRepository", return_value=mock_repo),
        ):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert resp.json()["user_id"] == 5

    def test_valid_token_with_inactive_user_returns_401(self):
        """Valid JWT for an inactive user should return 401."""
        secret = "test-secret"
        settings = _mock_settings(dev_mode=False, secret=secret)
        token = _make_token(user_id=5, secret=secret)

        mock_account = MagicMock()
        mock_account.is_active = False

        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_account.return_value = mock_account

        app = _make_app()
        with (
            patch("src.api.auth_middleware.get_settings", return_value=settings),
            patch("src.api.auth_middleware.session_scope", return_value=mock_ctx),
            patch("src.api.auth_middleware.TradingBuddyRepository", return_value=mock_repo),
        ):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401

    def test_valid_token_with_nonexistent_user_returns_401(self):
        """Valid JWT for a user that doesn't exist should return 401."""
        secret = "test-secret"
        settings = _mock_settings(dev_mode=False, secret=secret)
        token = _make_token(user_id=999, secret=secret)

        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_account.return_value = None

        app = _make_app()
        with (
            patch("src.api.auth_middleware.get_settings", return_value=settings),
            patch("src.api.auth_middleware.session_scope", return_value=mock_ctx),
            patch("src.api.auth_middleware.TradingBuddyRepository", return_value=mock_repo),
        ):
            client = TestClient(app)
            resp = client.get(
                "/test-user",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
