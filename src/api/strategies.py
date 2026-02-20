"""FastAPI router for user strategy CRUD endpoints.

Provides:
- GET  /api/user/strategies — list strategies for the authenticated user
- POST /api/user/strategies — create a new strategy
- PUT  /api/user/strategies/{id} — update an existing strategy

Uses the unified agent_strategies table via TradingBuddyRepository.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_trading_repo
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["strategies"])


# -----------------------------------------------------------------------------
# Request / Response Models
# -----------------------------------------------------------------------------

class StrategyResponse(BaseModel):
    """Strategy response matching frontend StrategyDefinition interface."""
    id: int
    name: str
    display_name: str
    description: str
    category: str
    direction: str
    entry_long: str | None
    entry_short: str | None
    exit_long: str | None
    required_features: list[str] | None
    tags: list[str] | None
    timeframes: list[str]
    max_risk_pct: float
    min_risk_reward: float
    atr_stop_mult: float | None
    atr_target_mult: float | None
    trailing_atr_mult: float | None
    time_stop_bars: int | None
    is_predefined: bool
    source_strategy_id: int | None
    is_active: bool


class StrategyCreate(BaseModel):
    """Create a new strategy."""
    name: str
    display_name: str = ""
    description: str = ""
    category: str = "custom"
    direction: str = "long_short"
    entry_long: str | None = None
    entry_short: str | None = None
    exit_long: str | None = None
    required_features: list[str] | None = None
    tags: list[str] | None = None
    timeframes: list[str] = []
    max_risk_pct: float = 2.0
    min_risk_reward: float = 1.5
    atr_stop_mult: float | None = None
    atr_target_mult: float | None = None
    trailing_atr_mult: float | None = None
    time_stop_bars: int | None = None
    is_active: bool = True


class StrategyUpdate(BaseModel):
    """Update an existing strategy."""
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    direction: Optional[str] = None
    entry_long: Optional[str] = None
    entry_short: Optional[str] = None
    exit_long: Optional[str] = None
    required_features: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    timeframes: Optional[list[str]] = None
    max_risk_pct: Optional[float] = None
    min_risk_reward: Optional[float] = None
    atr_stop_mult: Optional[float] = None
    atr_target_mult: Optional[float] = None
    trailing_atr_mult: Optional[float] = None
    time_stop_bars: Optional[int] = None
    is_active: Optional[bool] = None


# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def _parse_jsonb_text(value) -> str | None:
    """Extract plain text from JSONB-stored entry/exit fields.

    The migration stores old criteria as JSON strings (e.g. '"some text"').
    New entries may be plain strings or JSON arrays. Return human-readable text.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _strategy_to_response(strategy) -> StrategyResponse:
    """Convert an AgentStrategy ORM model to a response."""
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        display_name=strategy.display_name or strategy.name,
        description=strategy.description or "",
        category=strategy.category or "custom",
        direction=strategy.direction or "long_short",
        entry_long=_parse_jsonb_text(strategy.entry_long),
        entry_short=_parse_jsonb_text(strategy.entry_short),
        exit_long=_parse_jsonb_text(strategy.exit_long),
        required_features=strategy.required_features,
        tags=strategy.tags,
        timeframes=strategy.timeframes or [],
        max_risk_pct=strategy.max_risk_pct or 2.0,
        min_risk_reward=strategy.min_risk_reward or 1.5,
        atr_stop_mult=strategy.atr_stop_mult,
        atr_target_mult=strategy.atr_target_mult,
        trailing_atr_mult=strategy.trailing_atr_mult,
        time_stop_bars=strategy.time_stop_bars,
        is_predefined=strategy.is_predefined,
        source_strategy_id=strategy.source_strategy_id,
        is_active=strategy.is_active,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    user_id: int = Depends(get_current_user),
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """List all user-defined strategies for the authenticated user."""
    strategies = repo.get_strategies_for_account(user_id, active_only=False)
    logger.debug("Listed %d strategies for user_id=%d", len(strategies), user_id)
    return [_strategy_to_response(s) for s in strategies]


@router.post("/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    data: StrategyCreate,
    user_id: int = Depends(get_current_user),
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """Create a new strategy for the authenticated user."""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Strategy name is required")

    # Check for duplicate name
    existing = repo.get_strategy_by_name(user_id, data.name.strip())
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Strategy with name '{data.name}' already exists",
        )

    strategy = repo.create_strategy(
        account_id=user_id,
        name=data.name.strip(),
        display_name=data.display_name.strip() or data.name.strip(),
        description=data.description,
        category=data.category,
        direction=data.direction,
        entry_long=data.entry_long,
        entry_short=data.entry_short,
        exit_long=data.exit_long,
        required_features=data.required_features,
        tags=data.tags,
        timeframes=data.timeframes,
        max_risk_pct=data.max_risk_pct,
        min_risk_reward=data.min_risk_reward,
    )

    # Update extra ATR fields if provided
    atr_fields = {}
    if data.atr_stop_mult is not None:
        atr_fields["atr_stop_mult"] = data.atr_stop_mult
    if data.atr_target_mult is not None:
        atr_fields["atr_target_mult"] = data.atr_target_mult
    if data.trailing_atr_mult is not None:
        atr_fields["trailing_atr_mult"] = data.trailing_atr_mult
    if data.time_stop_bars is not None:
        atr_fields["time_stop_bars"] = data.time_stop_bars
    if atr_fields:
        repo.update_strategy(strategy.id, **atr_fields)

    logger.info("Created strategy id=%s name='%s' for user_id=%d", strategy.id, data.name, user_id)
    return _strategy_to_response(strategy)


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    data: StrategyUpdate,
    user_id: int = Depends(get_current_user),
    repo: TradingBuddyRepository = Depends(get_trading_repo),
):
    """Update an existing strategy."""
    strategy = repo.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    if strategy.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this strategy")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = repo.update_strategy(strategy_id, **updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    logger.info("Updated strategy id=%s fields=%s for user_id=%d", strategy_id, list(updates.keys()), user_id)
    return _strategy_to_response(updated)
