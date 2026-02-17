"""FastAPI router for authentication endpoints.

Provides:
- POST /api/auth/google — verify Google ID token, find/create user, issue JWT
- GET  /api/auth/me — return current user info (triggers background broker sync)
- POST /api/auth/logout — placeholder (JWT is stateless, client discards token)
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import jwt
from pydantic import BaseModel

from config.settings import get_settings
from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_trading_repo
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---- Request / Response models ----

class GoogleLoginRequest(BaseModel):
    """Request body for Google OAuth login."""
    credential: str  # Google ID token from frontend


class AuthResponse(BaseModel):
    """Response after successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """Current user info."""
    id: int
    name: str
    email: str
    profile_picture_url: str | None = None
    google_id: str | None = None
    auth_provider: str
    is_active: bool
    created_at: str


# ---- Helpers ----

def _create_access_token(user_id: int) -> str:
    """Create a JWT access token for a user.

    Args:
        user_id: User account ID

    Returns:
        Encoded JWT string
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.auth.jwt_expiry_hours)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload,
        settings.auth.jwt_secret_key,
        algorithm=settings.auth.jwt_algorithm,
    )


# ---- Endpoints ----

@router.post("/google", response_model=AuthResponse)
async def google_login(
    request: GoogleLoginRequest,
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """Authenticate with Google ID token.

    Verifies the Google ID token, finds or creates the user account,
    creates a default profile if needed, and returns a JWT.
    """
    settings = get_settings()

    if not settings.auth.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured",
        )

    # Verify Google ID token
    try:
        idinfo = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            settings.auth.google_client_id,
        )
    except ValueError as e:
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        )

    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name", email.split("@")[0])
    picture = idinfo.get("picture")

    logger.info(f"Google login for email={email}, google_id={google_id}")

    # Find existing user by google_id or email
    account = repo.get_account_by_google_id(google_id)
    if account is None:
        account = repo.get_account_by_email(email)

    if account is None:
        # New user — check waitlist approval (skip in dev mode)
        if not settings.auth.dev_mode:
            if not repo.is_email_approved(email):
                # Auto-add to waitlist so they don't have to fill the form
                repo.get_or_create_waitlist_entry(name=name, email=email)
                logger.info("Blocked unapproved login: email=%s", email)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account is pending approval. We'll notify you when access is granted.",
                )

        # Approved — create new account
        account = repo.create_account(
            external_user_id=f"google_{google_id}",
            name=name,
            email=email,
            google_id=google_id,
            auth_provider="google",
            profile_picture_url=picture,
        )
        # Create default profile
        repo.create_profile(account.id)
        logger.info(f"Created new account id={account.id} for {email}")
    else:
        # Update existing account with latest Google info
        if not account.google_id:
            account.google_id = google_id
        account.name = name
        account.profile_picture_url = picture
        repo.session.flush()

        # Ensure profile exists
        repo.get_or_create_profile(account.id)

    # Generate JWT
    access_token = _create_access_token(account.id)

    user_data = {
        "id": account.id,
        "name": account.name,
        "email": account.email,
        "profile_picture_url": account.profile_picture_url,
        "auth_provider": account.auth_provider,
    }

    return AuthResponse(access_token=access_token, user=user_data)


@router.get("/me", response_model=UserResponse)
async def get_me(
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """Return the current authenticated user's info.

    Also triggers background sync of broker trade fills (Alpaca).
    """
    logger.debug("GET /api/auth/me for user_id=%d", user_id)

    # Import here to avoid circular dependency
    from src.api.alpaca import sync_alpaca_fills_background

    account = repo.get_account(user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="User not found")

    user_response = UserResponse(
        id=account.id,
        name=account.name,
        email=account.email,
        profile_picture_url=account.profile_picture_url,
        google_id=account.google_id,
        auth_provider=account.auth_provider,
        is_active=account.is_active,
        created_at=account.created_at.isoformat(),
    )

    # Trigger background sync of Alpaca trade fills
    background_tasks.add_task(sync_alpaca_fills_background, user_id)

    return user_response


@router.post("/logout")
async def logout():
    """Logout endpoint (stateless JWT — client discards token)."""
    logger.debug("POST /api/auth/logout")
    return {"message": "Logged out successfully"}
