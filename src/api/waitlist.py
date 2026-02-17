"""FastAPI router for waitlist endpoints.

Provides:
- POST /api/waitlist — public (no auth), submit name + email to join waitlist
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.data.database.dependencies import get_trading_repo
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistRequest(BaseModel):
    """Request body for waitlist signup."""
    name: str
    email: str
    referral_source: str | None = None


class WaitlistResponse(BaseModel):
    """Response after waitlist signup."""
    message: str
    already_registered: bool = False


@router.post("", response_model=WaitlistResponse)
async def join_waitlist(
    request: WaitlistRequest,
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """Submit a waitlist signup request.

    Public endpoint — no authentication required.
    Idempotent: re-submitting the same email returns already_registered=True.
    """
    name = request.name.strip()
    email = request.email.strip().lower()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name is required",
        )

    if not _EMAIL_RE.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address",
        )

    entry, created = repo.get_or_create_waitlist_entry(
        name=name,
        email=email,
        referral_source=request.referral_source,
    )

    if not created:
        logger.info("Waitlist re-submission for email=%s", email)
        return WaitlistResponse(
            message="You're already on our waitlist! We'll be in touch soon.",
            already_registered=True,
        )

    logger.info("New waitlist signup: email=%s name=%s", email, name)
    return WaitlistResponse(
        message="Thanks for signing up! We'll notify you when your account is ready.",
        already_registered=False,
    )
