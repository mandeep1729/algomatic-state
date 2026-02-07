"""FastAPI router for user strategy CRUD endpoints.

Provides:
- GET  /api/user/strategies — list strategies for the authenticated user
- POST /api/user/strategies — create a new strategy
- PUT  /api/user/strategies/{id} — update an existing strategy
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["strategies"])


# -----------------------------------------------------------------------------
# Request / Response Models
# -----------------------------------------------------------------------------

class StrategyResponse(BaseModel):
    """Strategy response matching frontend StrategyDefinition interface."""
    id: str
    name: str
    description: str
    direction: str
    timeframes: list[str]
    entry_criteria: str
    exit_criteria: str
    max_risk_pct: float
    min_risk_reward: float
    is_active: bool


class StrategyCreate(BaseModel):
    """Create a new strategy."""
    name: str
    description: str = ""
    direction: str = "both"
    timeframes: list[str] = []
    entry_criteria: str = ""
    exit_criteria: str = ""
    max_risk_pct: float = 2.0
    min_risk_reward: float = 1.5
    is_active: bool = True


class StrategyUpdate(BaseModel):
    """Update an existing strategy."""
    name: Optional[str] = None
    description: Optional[str] = None
    direction: Optional[str] = None
    timeframes: Optional[list[str]] = None
    entry_criteria: Optional[str] = None
    exit_criteria: Optional[str] = None
    max_risk_pct: Optional[float] = None
    min_risk_reward: Optional[float] = None
    is_active: Optional[bool] = None


# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def _strategy_to_response(strategy) -> StrategyResponse:
    """Convert a Strategy ORM model to a response."""
    return StrategyResponse(
        id=str(strategy.id),
        name=strategy.name,
        description=strategy.description or "",
        direction=strategy.direction or "both",
        timeframes=strategy.timeframes or [],
        entry_criteria=strategy.entry_criteria or "",
        exit_criteria=strategy.exit_criteria or "",
        max_risk_pct=strategy.max_risk_pct or 2.0,
        min_risk_reward=strategy.min_risk_reward or 1.5,
        is_active=strategy.is_active,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(user_id: int = Depends(get_current_user)):
    """List all strategies for the authenticated user."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)
        strategies = repo.get_strategies_for_account(user_id, active_only=False)
        logger.debug("Listed %d strategies for user_id=%d", len(strategies), user_id)
        return [_strategy_to_response(s) for s in strategies]


@router.post("/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    data: StrategyCreate,
    user_id: int = Depends(get_current_user),
):
    """Create a new strategy for the authenticated user."""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Strategy name is required")

    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)

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
            description=data.description,
        )

        # Update extra fields
        extra_fields = {
            "direction": data.direction,
            "timeframes": data.timeframes,
            "entry_criteria": data.entry_criteria,
            "exit_criteria": data.exit_criteria,
            "max_risk_pct": data.max_risk_pct,
            "min_risk_reward": data.min_risk_reward,
            "is_active": data.is_active,
        }
        repo.update_strategy(strategy.id, **extra_fields)

        logger.info("Created strategy id=%s name='%s' for user_id=%d", strategy.id, data.name, user_id)
        return _strategy_to_response(strategy)


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    data: StrategyUpdate,
    user_id: int = Depends(get_current_user),
):
    """Update an existing strategy."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = TradingBuddyRepository(session)

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
