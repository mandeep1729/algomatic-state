"""FastAPI router for user profile and risk preference endpoints.

Provides:
- GET  /api/user/profile — get current user's trading profile
- PUT  /api/user/profile — update trading profile
- GET  /api/user/risk — get risk preferences
- PUT  /api/user/risk — update risk preferences
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user-profile"])


# ---- Request / Response models ----

class ProfileResponse(BaseModel):
    """User trading profile."""
    account_balance: float
    max_position_size_pct: float
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    min_risk_reward_ratio: float
    default_timeframes: list[str]
    experience_level: Optional[str] = None
    trading_style: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Fields that can be updated on the profile."""
    account_balance: Optional[float] = Field(None, ge=0)
    max_position_size_pct: Optional[float] = Field(None, gt=0, le=100)
    max_risk_per_trade_pct: Optional[float] = Field(None, gt=0, le=100)
    max_daily_loss_pct: Optional[float] = Field(None, gt=0, le=100)
    min_risk_reward_ratio: Optional[float] = Field(None, gt=0)
    default_timeframes: Optional[list[str]] = None
    experience_level: Optional[str] = None
    trading_style: Optional[str] = None


class RiskResponse(BaseModel):
    """Risk preferences subset."""
    max_position_size_pct: float
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    min_risk_reward_ratio: float


class RiskUpdate(BaseModel):
    """Risk preference update."""
    max_position_size_pct: Optional[float] = Field(None, gt=0, le=100)
    max_risk_per_trade_pct: Optional[float] = Field(None, gt=0, le=100)
    max_daily_loss_pct: Optional[float] = Field(None, gt=0, le=100)
    min_risk_reward_ratio: Optional[float] = Field(None, gt=0)


# ---- Endpoints ----

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user_id: int = Depends(get_current_user)):
    """Get the authenticated user's trading profile."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        profile = repo.get_or_create_profile(user_id)

        return ProfileResponse(
            account_balance=profile.account_balance,
            max_position_size_pct=profile.max_position_size_pct,
            max_risk_per_trade_pct=profile.max_risk_per_trade_pct,
            max_daily_loss_pct=profile.max_daily_loss_pct,
            min_risk_reward_ratio=profile.min_risk_reward_ratio,
            default_timeframes=profile.default_timeframes or [],
            experience_level=profile.experience_level,
            trading_style=profile.trading_style,
        )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdate,
    user_id: int = Depends(get_current_user),
):
    """Update the authenticated user's trading profile."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        profile = repo.update_profile(user_id, **updates)
        if profile is None:
            # Profile doesn't exist yet — create with provided values
            profile = repo.create_profile(user_id, **updates)

        return ProfileResponse(
            account_balance=profile.account_balance,
            max_position_size_pct=profile.max_position_size_pct,
            max_risk_per_trade_pct=profile.max_risk_per_trade_pct,
            max_daily_loss_pct=profile.max_daily_loss_pct,
            min_risk_reward_ratio=profile.min_risk_reward_ratio,
            default_timeframes=profile.default_timeframes or [],
            experience_level=profile.experience_level,
            trading_style=profile.trading_style,
        )


@router.get("/risk", response_model=RiskResponse)
async def get_risk(user_id: int = Depends(get_current_user)):
    """Get the authenticated user's risk preferences."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        profile = repo.get_or_create_profile(user_id)

        return RiskResponse(
            max_position_size_pct=profile.max_position_size_pct,
            max_risk_per_trade_pct=profile.max_risk_per_trade_pct,
            max_daily_loss_pct=profile.max_daily_loss_pct,
            min_risk_reward_ratio=profile.min_risk_reward_ratio,
        )


@router.put("/risk", response_model=RiskResponse)
async def update_risk(
    data: RiskUpdate,
    user_id: int = Depends(get_current_user),
):
    """Update the authenticated user's risk preferences."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        profile = repo.update_profile(user_id, **updates)
        if profile is None:
            profile = repo.create_profile(user_id, **updates)

        return RiskResponse(
            max_position_size_pct=profile.max_position_size_pct,
            max_risk_per_trade_pct=profile.max_risk_per_trade_pct,
            max_daily_loss_pct=profile.max_daily_loss_pct,
            min_risk_reward_ratio=profile.min_risk_reward_ratio,
        )
