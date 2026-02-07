"""FastAPI router for user profile, risk preference, and evaluation control endpoints.

Provides:
- GET  /api/user/profile — get current user's trading profile
- PUT  /api/user/profile — update trading profile
- GET  /api/user/risk-preferences — get risk preferences (frontend format)
- PUT  /api/user/risk-preferences — update risk preferences (frontend format)
- GET  /api/user/evaluation-controls — get evaluation controls
- PUT  /api/user/evaluation-controls — update evaluation controls
- GET  /api/user/risk — get risk preferences (legacy format)
- PUT  /api/user/risk — update risk preferences (legacy format)
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


# -----------------------------------------------------------------------------
# Trading Profile — matches frontend TradingProfile type
# -----------------------------------------------------------------------------

class TradingProfileResponse(BaseModel):
    """User trading profile matching frontend TradingProfile interface."""
    experience_level: str
    trading_style: str
    primary_markets: list[str]
    typical_timeframes: list[str]
    account_size_range: str


class TradingProfileUpdate(BaseModel):
    """Fields that can be updated on the trading profile."""
    experience_level: Optional[str] = None
    trading_style: Optional[str] = None
    primary_markets: Optional[list[str]] = None
    typical_timeframes: Optional[list[str]] = None
    account_size_range: Optional[str] = None


@router.get("/profile", response_model=TradingProfileResponse)
async def get_profile(user_id: int = Depends(get_current_user)):
    """Get the authenticated user's trading profile."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        profile = repo.get_or_create_profile(user_id)

        return TradingProfileResponse(
            experience_level=profile.experience_level or "beginner",
            trading_style=profile.trading_style or "day_trading",
            primary_markets=profile.primary_markets or ["US_EQUITIES"],
            typical_timeframes=profile.default_timeframes or ["1Min", "15Min", "1Hour"],
            account_size_range=profile.account_size_range or "$10k-$50k",
        )


@router.put("/profile", response_model=TradingProfileResponse)
async def update_profile(
    data: TradingProfileUpdate,
    user_id: int = Depends(get_current_user),
):
    """Update the authenticated user's trading profile."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)

        # Map frontend field names to DB column names
        updates = {}
        raw = data.model_dump(exclude_none=True)
        field_map = {
            "experience_level": "experience_level",
            "trading_style": "trading_style",
            "primary_markets": "primary_markets",
            "typical_timeframes": "default_timeframes",
            "account_size_range": "account_size_range",
        }
        for frontend_key, db_key in field_map.items():
            if frontend_key in raw:
                updates[db_key] = raw[frontend_key]

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        profile = repo.update_profile(user_id, **updates)
        if profile is None:
            profile = repo.create_profile(user_id, **updates)

        logger.info("Updated trading profile for user_id=%d fields=%s", user_id, list(updates.keys()))

        return TradingProfileResponse(
            experience_level=profile.experience_level or "beginner",
            trading_style=profile.trading_style or "day_trading",
            primary_markets=profile.primary_markets or ["US_EQUITIES"],
            typical_timeframes=profile.default_timeframes or ["1Min", "15Min", "1Hour"],
            account_size_range=profile.account_size_range or "$10k-$50k",
        )


# -----------------------------------------------------------------------------
# Risk Preferences — matches frontend RiskPreferences type
# -----------------------------------------------------------------------------

class RiskPreferencesResponse(BaseModel):
    """Risk preferences matching frontend RiskPreferences interface."""
    max_loss_per_trade_pct: float
    max_daily_loss_pct: float
    max_open_positions: int
    risk_reward_minimum: float
    stop_loss_required: bool


class RiskPreferencesUpdate(BaseModel):
    """Risk preference update."""
    max_loss_per_trade_pct: Optional[float] = Field(None, gt=0, le=100)
    max_daily_loss_pct: Optional[float] = Field(None, gt=0, le=100)
    max_open_positions: Optional[int] = Field(None, ge=1, le=50)
    risk_reward_minimum: Optional[float] = Field(None, gt=0)
    stop_loss_required: Optional[bool] = None


@router.get("/risk-preferences", response_model=RiskPreferencesResponse)
async def get_risk_preferences(user_id: int = Depends(get_current_user)):
    """Get the authenticated user's risk preferences (frontend format)."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        profile = repo.get_or_create_profile(user_id)

        return RiskPreferencesResponse(
            max_loss_per_trade_pct=profile.max_risk_per_trade_pct,
            max_daily_loss_pct=profile.max_daily_loss_pct,
            max_open_positions=profile.max_open_positions,
            risk_reward_minimum=profile.min_risk_reward_ratio,
            stop_loss_required=profile.stop_loss_required,
        )


@router.put("/risk-preferences", response_model=RiskPreferencesResponse)
async def update_risk_preferences(
    data: RiskPreferencesUpdate,
    user_id: int = Depends(get_current_user),
):
    """Update the authenticated user's risk preferences (frontend format)."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)

        # Map frontend field names to DB column names
        updates = {}
        raw = data.model_dump(exclude_none=True)
        field_map = {
            "max_loss_per_trade_pct": "max_risk_per_trade_pct",
            "max_daily_loss_pct": "max_daily_loss_pct",
            "max_open_positions": "max_open_positions",
            "risk_reward_minimum": "min_risk_reward_ratio",
            "stop_loss_required": "stop_loss_required",
        }
        for frontend_key, db_key in field_map.items():
            if frontend_key in raw:
                updates[db_key] = raw[frontend_key]

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        profile = repo.update_profile(user_id, **updates)
        if profile is None:
            profile = repo.create_profile(user_id, **updates)

        logger.info("Updated risk preferences for user_id=%d fields=%s", user_id, list(updates.keys()))

        return RiskPreferencesResponse(
            max_loss_per_trade_pct=profile.max_risk_per_trade_pct,
            max_daily_loss_pct=profile.max_daily_loss_pct,
            max_open_positions=profile.max_open_positions,
            risk_reward_minimum=profile.min_risk_reward_ratio,
            stop_loss_required=profile.stop_loss_required,
        )


# -----------------------------------------------------------------------------
# Evaluation Controls — matches frontend EvaluationControls type
# -----------------------------------------------------------------------------

DEFAULT_EVALUATION_CONTROLS = {
    "evaluators_enabled": {
        "regime_fit": True,
        "entry_timing": True,
        "exit_logic": True,
        "risk_positioning": True,
        "behavioral": True,
        "strategy_consistency": True,
    },
    "auto_evaluate_synced": False,
    "notification_on_blocker": True,
    "severity_threshold": "warning",
}


class EvaluationControlsResponse(BaseModel):
    """Evaluation controls matching frontend EvaluationControls interface."""
    evaluators_enabled: dict[str, bool]
    auto_evaluate_synced: bool
    notification_on_blocker: bool
    severity_threshold: str


class EvaluationControlsUpdate(BaseModel):
    """Evaluation controls update."""
    evaluators_enabled: Optional[dict[str, bool]] = None
    auto_evaluate_synced: Optional[bool] = None
    notification_on_blocker: Optional[bool] = None
    severity_threshold: Optional[str] = None


@router.get("/evaluation-controls", response_model=EvaluationControlsResponse)
async def get_evaluation_controls(user_id: int = Depends(get_current_user)):
    """Get the authenticated user's evaluation controls."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        profile = repo.get_or_create_profile(user_id)

        controls = profile.evaluation_controls or DEFAULT_EVALUATION_CONTROLS
        return EvaluationControlsResponse(**controls)


@router.put("/evaluation-controls", response_model=EvaluationControlsResponse)
async def update_evaluation_controls(
    data: EvaluationControlsUpdate,
    user_id: int = Depends(get_current_user),
):
    """Update the authenticated user's evaluation controls."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        profile = repo.get_or_create_profile(user_id)

        # Merge with existing controls
        current = profile.evaluation_controls or DEFAULT_EVALUATION_CONTROLS.copy()
        updates = data.model_dump(exclude_none=True)
        current.update(updates)

        repo.update_profile(user_id, evaluation_controls=current)

        logger.info("Updated evaluation controls for user_id=%d", user_id)

        return EvaluationControlsResponse(**current)


# -----------------------------------------------------------------------------
# Legacy Risk Endpoints (kept for backward compatibility)
# -----------------------------------------------------------------------------

class RiskResponse(BaseModel):
    """Risk preferences subset (legacy format)."""
    max_position_size_pct: float
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    min_risk_reward_ratio: float


class RiskUpdate(BaseModel):
    """Risk preference update (legacy format)."""
    max_position_size_pct: Optional[float] = Field(None, gt=0, le=100)
    max_risk_per_trade_pct: Optional[float] = Field(None, gt=0, le=100)
    max_daily_loss_pct: Optional[float] = Field(None, gt=0, le=100)
    min_risk_reward_ratio: Optional[float] = Field(None, gt=0)


@router.get("/risk", response_model=RiskResponse)
async def get_risk(user_id: int = Depends(get_current_user)):
    """Get the authenticated user's risk preferences (legacy format)."""
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
    """Update the authenticated user's risk preferences (legacy format)."""
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
