"""FastAPI authentication middleware.

Provides the get_current_user dependency that validates JWT tokens
and returns the authenticated user's account ID.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config.settings import get_settings
from src.data.database.dependencies import session_scope
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> int:
    """Validate JWT token and return the user's account ID.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User account ID (int)

    Raises:
        HTTPException: 401 if token is missing/invalid/expired
    """
    settings = get_settings()

    # Dev mode: bypass OAuth and return default user
    if settings.auth.dev_mode:
        # Use token's user_id if provided, otherwise find first active user
        if credentials is not None:
            try:
                payload = jwt.decode(
                    credentials.credentials,
                    settings.auth.jwt_secret_key,
                    algorithms=[settings.auth.jwt_algorithm],
                )
                uid = payload.get("sub")
                if uid is not None:
                    logger.debug("Auth dev_mode: using user_id=%s from JWT", uid)
                    return int(uid)
            except JWTError:
                pass  # Fall through to default lookup

        dev_user_id = settings.auth.dev_user_id
        logger.debug("Auth dev_mode enabled, using default user_id=%d", dev_user_id)
        return dev_user_id

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret_key,
            algorithms=[settings.auth.jwt_algorithm],
        )
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    with session_scope() as session:
        repo = TradingBuddyRepository(session)
        account = repo.get_account(int(user_id))
        if account is None or not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

    logger.debug("JWT validated successfully for user_id=%s", user_id)
    return int(user_id)
