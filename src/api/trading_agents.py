"""FastAPI router for automated trading agents.

Provides:
- Strategy endpoints: list, get, create, clone, update
- Agent CRUD: list, get, create, update, delete
- Lifecycle: start, pause, stop
- Activity: orders, activity log
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_agent_repo
from src.trading_agents.repository import TradingAgentRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["trading-agents"])


# -----------------------------------------------------------------------------
# Request / Response Models
# -----------------------------------------------------------------------------


class StrategyResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    direction: str
    entry_long: Optional[str] = None
    entry_short: Optional[str] = None
    exit_long: Optional[str] = None
    required_features: Optional[list] = None
    tags: Optional[list] = None
    timeframes: Optional[list] = None
    max_risk_pct: Optional[float] = None
    min_risk_reward: Optional[float] = None
    atr_stop_mult: Optional[float] = None
    atr_target_mult: Optional[float] = None
    trailing_atr_mult: Optional[float] = None
    time_stop_bars: Optional[int] = None
    is_predefined: bool
    source_strategy_id: Optional[int] = None
    is_active: bool


class StrategyCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    category: str = "custom"
    direction: str = "long_short"
    entry_long: Optional[dict] = None
    entry_short: Optional[dict] = None
    exit_long: Optional[dict] = None
    exit_short: Optional[dict] = None
    required_features: Optional[list] = None
    tags: Optional[list] = None
    timeframes: Optional[list] = None
    max_risk_pct: Optional[float] = None
    min_risk_reward: Optional[float] = None
    atr_stop_mult: Optional[float] = None
    atr_target_mult: Optional[float] = None
    trailing_atr_mult: Optional[float] = None
    time_stop_bars: Optional[int] = None


class StrategyUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    direction: Optional[str] = None
    entry_long: Optional[dict] = None
    entry_short: Optional[dict] = None
    exit_long: Optional[dict] = None
    exit_short: Optional[dict] = None
    required_features: Optional[list] = None
    tags: Optional[list] = None
    timeframes: Optional[list] = None
    max_risk_pct: Optional[float] = None
    min_risk_reward: Optional[float] = None
    atr_stop_mult: Optional[float] = None
    atr_target_mult: Optional[float] = None
    trailing_atr_mult: Optional[float] = None
    time_stop_bars: Optional[int] = None


class CloneRequest(BaseModel):
    new_name: str


class AgentResponse(BaseModel):
    id: int
    name: str
    symbol: str
    strategy_id: int
    strategy_name: Optional[str] = None
    status: str
    timeframe: str
    interval_minutes: int
    lookback_days: int
    position_size_dollars: float
    risk_config: Optional[dict] = None
    exit_config: Optional[dict] = None
    paper: bool
    last_run_at: Optional[str] = None
    last_signal: Optional[str] = None
    error_message: Optional[str] = None
    consecutive_errors: int = 0
    current_position: Optional[dict] = None
    created_at: str
    updated_at: str


class AgentCreate(BaseModel):
    name: str
    symbol: str
    strategy_id: int
    timeframe: str = "5Min"
    interval_minutes: int = 5
    lookback_days: int = 30
    position_size_dollars: float = Field(default=1000.0, gt=0)
    risk_config: Optional[dict] = None
    exit_config: Optional[dict] = None
    paper: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    strategy_id: Optional[int] = None
    timeframe: Optional[str] = None
    interval_minutes: Optional[int] = None
    lookback_days: Optional[int] = None
    position_size_dollars: Optional[float] = None
    risk_config: Optional[dict] = None
    exit_config: Optional[dict] = None
    paper: Optional[bool] = None


class OrderResponse(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    order_type: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: str
    broker_order_id: Optional[str] = None
    status: str
    filled_quantity: Optional[float] = None
    filled_avg_price: Optional[float] = None
    signal_direction: Optional[str] = None
    signal_metadata: Optional[dict] = None
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    created_at: str


class ActivityResponse(BaseModel):
    id: int
    activity_type: str
    message: str
    details: Optional[dict] = None
    severity: str
    created_at: str


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _parse_jsonb_text(value) -> str | None:
    """Extract plain text from JSONB-stored entry/exit fields."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _strategy_to_response(s) -> StrategyResponse:
    return StrategyResponse(
        id=s.id,
        name=s.name,
        display_name=s.display_name,
        description=s.description,
        category=s.category,
        direction=s.direction,
        entry_long=_parse_jsonb_text(s.entry_long),
        entry_short=_parse_jsonb_text(s.entry_short),
        exit_long=_parse_jsonb_text(s.exit_long),
        required_features=s.required_features,
        tags=s.tags,
        timeframes=s.timeframes,
        max_risk_pct=s.max_risk_pct,
        min_risk_reward=s.min_risk_reward,
        atr_stop_mult=s.atr_stop_mult,
        atr_target_mult=s.atr_target_mult,
        trailing_atr_mult=s.trailing_atr_mult,
        time_stop_bars=s.time_stop_bars,
        is_predefined=s.is_predefined,
        source_strategy_id=s.source_strategy_id,
        is_active=s.is_active,
    )


def _agent_to_response(a) -> AgentResponse:
    strategy_name = a.strategy.display_name if a.strategy else None
    return AgentResponse(
        id=a.id,
        name=a.name,
        symbol=a.symbol,
        strategy_id=a.strategy_id,
        strategy_name=strategy_name,
        status=a.status,
        timeframe=a.timeframe,
        interval_minutes=a.interval_minutes,
        lookback_days=a.lookback_days,
        position_size_dollars=a.position_size_dollars,
        risk_config=a.risk_config,
        exit_config=a.exit_config,
        paper=a.paper,
        last_run_at=a.last_run_at.isoformat() if a.last_run_at else None,
        last_signal=a.last_signal,
        error_message=a.error_message,
        consecutive_errors=a.consecutive_errors,
        current_position=a.current_position,
        created_at=a.created_at.isoformat(),
        updated_at=a.updated_at.isoformat(),
    )


def _order_to_response(o) -> OrderResponse:
    return OrderResponse(
        id=o.id,
        symbol=o.symbol,
        side=o.side,
        quantity=o.quantity,
        order_type=o.order_type,
        limit_price=o.limit_price,
        stop_price=o.stop_price,
        client_order_id=o.client_order_id,
        broker_order_id=o.broker_order_id,
        status=o.status,
        filled_quantity=o.filled_quantity,
        filled_avg_price=o.filled_avg_price,
        signal_direction=o.signal_direction,
        signal_metadata=o.signal_metadata,
        submitted_at=o.submitted_at.isoformat() if o.submitted_at else None,
        filled_at=o.filled_at.isoformat() if o.filled_at else None,
        created_at=o.created_at.isoformat(),
    )


def _activity_to_response(a) -> ActivityResponse:
    return ActivityResponse(
        id=a.id,
        activity_type=a.activity_type,
        message=a.message,
        details=a.details,
        severity=a.severity,
        created_at=a.created_at.isoformat(),
    )


def _check_agent_ownership(agent, user_id: int) -> None:
    """Raise 403 if the agent does not belong to the user."""
    if agent.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")


# -----------------------------------------------------------------------------
# Strategy Endpoints
# -----------------------------------------------------------------------------


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """List predefined + user's custom strategies."""
    strategies = repo.list_strategies(user_id)
    logger.debug("Listed %d strategies for user_id=%d", len(strategies), user_id)
    return [_strategy_to_response(s) for s in strategies]


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Get strategy detail."""
    strategy = repo.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    # Allow access to predefined strategies or user's own
    if strategy.account_id is not None and strategy.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return _strategy_to_response(strategy)


@router.post("/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    data: StrategyCreate,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Create a custom strategy."""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Strategy name is required")

    strategy = repo.create_strategy(
        account_id=user_id,
        **data.model_dump(),
    )
    logger.info("Created custom strategy id=%s for user_id=%d", strategy.id, user_id)
    return _strategy_to_response(strategy)


@router.post("/strategies/{strategy_id}/clone", response_model=StrategyResponse, status_code=201)
async def clone_strategy(
    strategy_id: int,
    data: CloneRequest,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Clone a predefined strategy into a custom one."""
    if not data.new_name.strip():
        raise HTTPException(status_code=400, detail="New name is required")

    clone = repo.clone_strategy(strategy_id, user_id, data.new_name.strip())
    if clone is None:
        raise HTTPException(status_code=404, detail="Source strategy not found")

    logger.info("Cloned strategy %d -> %d for user_id=%d", strategy_id, clone.id, user_id)
    return _strategy_to_response(clone)


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    data: StrategyUpdate,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Update a custom strategy (cannot update predefined)."""
    strategy = repo.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.is_predefined:
        raise HTTPException(status_code=403, detail="Cannot modify predefined strategies")
    if strategy.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = repo.update_strategy(strategy_id, **updates)
    return _strategy_to_response(updated)


# -----------------------------------------------------------------------------
# Agent CRUD Endpoints
# -----------------------------------------------------------------------------


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """List all agents for the authenticated user."""
    agents = repo.list_agents(user_id)
    logger.debug("Listed %d agents for user_id=%d", len(agents), user_id)
    return [_agent_to_response(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Get agent detail."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)
    return _agent_to_response(agent)


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Create a new trading agent."""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Agent name is required")
    if not data.symbol.strip():
        raise HTTPException(status_code=400, detail="Symbol is required")

    # Verify strategy exists and is accessible
    strategy = repo.get_strategy(data.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.account_id is not None and strategy.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to use this strategy")

    agent = repo.create_agent(
        account_id=user_id,
        **data.model_dump(),
    )

    repo.log_activity(
        agent_id=agent.id,
        account_id=user_id,
        activity_type="created",
        message=f"Agent '{agent.name}' created for {agent.symbol}",
    )

    logger.info("Created agent id=%s name='%s' for user_id=%d", agent.id, agent.name, user_id)
    return _agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    data: AgentUpdate,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Update an agent (only when created or stopped)."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    if agent.status not in ("created", "stopped"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot update agent in '{agent.status}' status. Stop it first.",
        )

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "symbol" in updates:
        updates["symbol"] = updates["symbol"].upper()

    updated = repo.update_agent(agent_id, **updates)
    logger.info("Updated agent id=%s fields=%s for user_id=%d", agent_id, list(updates.keys()), user_id)
    return _agent_to_response(updated)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Delete an agent (must be stopped or created)."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    if agent.status not in ("created", "stopped", "error"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete agent in '{agent.status}' status. Stop it first.",
        )

    repo.delete_agent(agent_id)
    logger.info("Deleted agent id=%s for user_id=%d", agent_id, user_id)


# -----------------------------------------------------------------------------
# Lifecycle Endpoints
# -----------------------------------------------------------------------------


@router.post("/{agent_id}/start", response_model=AgentResponse)
async def start_agent(
    agent_id: int,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Start an agent (set status=active for Go service to pick up)."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    if agent.status not in ("created", "stopped", "paused", "error"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start agent in '{agent.status}' status",
        )

    updated = repo.set_agent_status(agent_id, "active")

    repo.log_activity(
        agent_id=agent_id,
        account_id=user_id,
        activity_type="started",
        message=f"Agent '{agent.name}' started",
    )

    logger.info("Started agent id=%s for user_id=%d", agent_id, user_id)
    return _agent_to_response(updated)


@router.post("/{agent_id}/pause", response_model=AgentResponse)
async def pause_agent(
    agent_id: int,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Pause an agent (Go service skips it)."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    if agent.status != "active":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot pause agent in '{agent.status}' status",
        )

    updated = repo.set_agent_status(agent_id, "paused")

    repo.log_activity(
        agent_id=agent_id,
        account_id=user_id,
        activity_type="paused",
        message=f"Agent '{agent.name}' paused",
    )

    logger.info("Paused agent id=%s for user_id=%d", agent_id, user_id)
    return _agent_to_response(updated)


@router.post("/{agent_id}/stop", response_model=AgentResponse)
async def stop_agent(
    agent_id: int,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """Stop an agent (Go service removes it)."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    if agent.status not in ("active", "paused", "error"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot stop agent in '{agent.status}' status",
        )

    updated = repo.set_agent_status(agent_id, "stopped")

    repo.log_activity(
        agent_id=agent_id,
        account_id=user_id,
        activity_type="stopped",
        message=f"Agent '{agent.name}' stopped",
    )

    logger.info("Stopped agent id=%s for user_id=%d", agent_id, user_id)
    return _agent_to_response(updated)


# -----------------------------------------------------------------------------
# Activity Endpoints
# -----------------------------------------------------------------------------


@router.get("/{agent_id}/orders", response_model=list[OrderResponse])
async def list_orders(
    agent_id: int,
    limit: int = 100,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """List orders for an agent."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    orders = repo.list_orders(agent_id, limit=limit)
    return [_order_to_response(o) for o in orders]


@router.get("/{agent_id}/activity", response_model=list[ActivityResponse])
async def list_activity(
    agent_id: int,
    limit: int = 100,
    user_id: int = Depends(get_current_user),
    repo: TradingAgentRepository = Depends(get_agent_repo),
):
    """List activity log for an agent."""
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    _check_agent_ownership(agent, user_id)

    activities = repo.list_activity(agent_id, limit=limit)
    return [_activity_to_response(a) for a in activities]
