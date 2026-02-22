"""Internal API endpoints for service-to-service communication.

These endpoints are called by the reviewer service (and potentially other
internal services) to read trade/market data and write computed results.
They are NOT authenticated via JWT — they use the /api/internal/ prefix
and are intended for same-network calls only.

Endpoints:
- GET  /api/internal/accounts/{account_id}/fills          -- fills + decision contexts
- GET  /api/internal/accounts/{account_id}/profile        -- user profile data
- PUT  /api/internal/accounts/{account_id}/baseline-stats -- save baseline stats
- PUT  /api/internal/fills/{fill_id}/inferred-context     -- merge inferred context
- GET  /api/internal/accounts                             -- list active accounts
- GET  /api/internal/position-symbols                     -- symbols with open positions
- GET  /api/internal/agent-symbols                        -- symbols from active trading agents
- GET  /api/internal/favorite-symbols                     -- symbols from user favorites
- GET  /api/internal/recent-trade-symbols                 -- symbols traded in last N days
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case as sa_case, func as sa_func, literal
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.data.database.broker_models import TradeFill
from src.data.database.dependencies import get_broker_repo, get_db
from src.data.database.broker_repository import BrokerRepository
from src.data.database.trading_buddy_models import UserProfile
from src.trading_agents.models import TradingAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------

class FillWithContext(BaseModel):
    """A trade fill with its associated decision context data."""
    fill_id: int
    account_id: int
    symbol: str
    side: str
    quantity: float
    price: float
    fees: float
    executed_at: str
    context_type: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_name: Optional[str] = None
    hypothesis: Optional[str] = None
    exit_intent: Optional[dict] = None
    timeframe: Optional[str] = None


class FillsResponse(BaseModel):
    fills: list[FillWithContext]
    total: int


class ProfileResponse(BaseModel):
    account_id: int
    account_balance: float
    risk_profile: dict
    profile: dict
    stats: Optional[dict] = None


class BaselineStatsRequest(BaseModel):
    stats: dict


class InferredContextRequest(BaseModel):
    inferred_context: dict


class ActiveAccountsResponse(BaseModel):
    account_ids: list[int]


class PositionSymbolsResponse(BaseModel):
    symbols: list[str]


class AgentSymbolsResponse(BaseModel):
    symbols: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/accounts/{account_id}/fills", response_model=FillsResponse)
async def get_fills_with_context(
    account_id: int,
    lookback_days: int = Query(default=90, ge=1, le=365),
    symbol: Optional[str] = Query(default=None),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get fills with decision contexts for an account within a lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    try:
        rows = broker_repo.get_fills_with_context(
            account_id=account_id,
            cutoff=cutoff,
            symbol=symbol,
        )

        fills = []
        for fill, dc, strategy_name in rows:
            timeframe = None
            exit_intent = None
            if dc and isinstance(dc.exit_intent, dict):
                exit_intent = dc.exit_intent
                timeframe = exit_intent.get("timeframe")

            fills.append(FillWithContext(
                fill_id=fill.id,
                account_id=fill.account_id or account_id,
                symbol=fill.symbol,
                side=fill.side,
                quantity=fill.quantity,
                price=fill.price,
                fees=fill.fees,
                executed_at=fill.executed_at.isoformat(),
                context_type=dc.context_type if dc else None,
                strategy_id=dc.strategy_id if dc else None,
                strategy_name=strategy_name,
                hypothesis=dc.hypothesis if dc else None,
                exit_intent=exit_intent,
                timeframe=timeframe,
            ))

        logger.info(
            "Returned %d fills for account_id=%s (lookback=%d days)",
            len(fills), account_id, lookback_days,
        )
        return FillsResponse(fills=fills, total=len(fills))

    except Exception:
        logger.exception("Failed to fetch fills for account_id=%s", account_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts/{account_id}/profile", response_model=ProfileResponse)
async def get_account_profile(
    account_id: int,
    db: Session = Depends(get_db),
):
    """Get user profile including account_balance, risk settings, and stats."""
    try:
        profile = db.query(UserProfile).filter(
            UserProfile.user_account_id == account_id,
        ).first()

        if profile is None:
            raise HTTPException(
                status_code=404,
                detail=f"No profile found for account_id={account_id}",
            )

        return ProfileResponse(
            account_id=account_id,
            account_balance=profile.account_balance,
            risk_profile=profile.risk_profile or {},
            profile=profile.profile or {},
            stats=profile.stats,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch profile for account_id=%s", account_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/accounts/{account_id}/baseline-stats")
async def save_baseline_stats(
    account_id: int,
    request: BaselineStatsRequest,
    db: Session = Depends(get_db),
):
    """Save computed baseline stats to user_profiles.stats JSONB column."""
    try:
        profile = db.query(UserProfile).filter(
            UserProfile.user_account_id == account_id,
        ).first()

        if profile is None:
            raise HTTPException(
                status_code=404,
                detail=f"No profile found for account_id={account_id}",
            )

        profile.stats = request.stats
        flag_modified(profile, "stats")
        db.flush()

        logger.info(
            "Saved baseline stats for account_id=%s (%d keys)",
            account_id, len(request.stats),
        )
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save baseline stats for account_id=%s", account_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/fills/{fill_id}/inferred-context")
async def save_inferred_context(
    fill_id: int,
    request: InferredContextRequest,
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Merge entry quality results into decision_contexts.inferred_context JSONB."""
    try:
        dc = broker_repo.get_decision_context(fill_id)

        if dc is None:
            raise HTTPException(
                status_code=404,
                detail=f"No DecisionContext for fill_id={fill_id}",
            )

        existing = dc.inferred_context or {}
        merged = {**existing, **request.inferred_context}
        dc.inferred_context = merged

        flag_modified(dc, "inferred_context")
        broker_repo.session.flush()

        logger.info(
            "Saved inferred context for fill_id=%s (%d keys merged)",
            fill_id, len(request.inferred_context),
        )
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save inferred context for fill_id=%s", fill_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts", response_model=ActiveAccountsResponse)
async def get_active_accounts(
    active_since_days: int = Query(default=30, ge=1, le=365),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """List account IDs with recent trading activity."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=active_since_days)

    try:
        account_ids = broker_repo.get_active_account_ids(cutoff)

        logger.info(
            "Found %d active accounts (since %d days ago)",
            len(account_ids), active_since_days,
        )
        return ActiveAccountsResponse(account_ids=account_ids)

    except Exception:
        logger.exception("Failed to fetch active accounts")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/position-symbols", response_model=PositionSymbolsResponse)
async def get_position_symbols(
    db: Session = Depends(get_db),
):
    """Return symbols with non-zero net positions across all accounts.

    Computes net quantity per symbol from trade_fills
    (buy = +qty, sell = -qty) and returns symbols where net != 0.
    Used by marketdata-service to scope periodic scans.
    """
    try:
        net_qty = sa_func.sum(
            sa_case(
                (TradeFill.side == "buy", TradeFill.quantity),
                else_=-TradeFill.quantity,
            )
        ).label("net_qty")

        rows = (
            db.query(TradeFill.symbol)
            .group_by(TradeFill.symbol)
            .having(net_qty != literal(0))
            .all()
        )

        symbols = sorted(row[0] for row in rows)
        logger.info("Position symbols: %d symbols with open positions", len(symbols))
        return PositionSymbolsResponse(symbols=symbols)

    except Exception:
        logger.exception("Failed to compute position symbols")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/agent-symbols", response_model=AgentSymbolsResponse)
async def get_agent_symbols(
    db: Session = Depends(get_db),
):
    """Return distinct symbols from active trading agents.

    Includes agents with status 'created' or 'active'.
    Used by marketdata-service to include agent tickers in periodic scans.
    """
    try:
        rows = (
            db.query(TradingAgent.symbol)
            .filter(TradingAgent.status.in_(["created", "active"]))
            .distinct()
            .all()
        )

        symbols = sorted(row[0] for row in rows)
        logger.info("Agent symbols: %d symbols from active agents", len(symbols))
        return AgentSymbolsResponse(symbols=symbols)

    except Exception:
        logger.exception("Failed to fetch agent symbols")
        raise HTTPException(status_code=500, detail="Internal server error")


class FavoriteSymbolsResponse(BaseModel):
    symbols: list[str]


@router.get("/favorite-symbols", response_model=FavoriteSymbolsResponse)
async def get_favorite_symbols(
    db: Session = Depends(get_db),
):
    """Return symbols from all users' favorite tickers lists.

    Reads the favorite_tickers array from user_profiles.profile JSONB,
    flattens across all users, and returns deduplicated symbols.
    Used by marketdata-service to scope periodic scans.
    """
    try:
        rows = db.query(UserProfile.profile).all()

        seen: set[str] = set()
        for (profile,) in rows:
            if profile and isinstance(profile, dict):
                favs = profile.get("favorite_tickers", [])
                if isinstance(favs, list):
                    for s in favs:
                        if isinstance(s, str) and s.strip():
                            seen.add(s.strip().upper())

        symbols = sorted(seen)
        logger.info("Favorite symbols: %d symbols across all users", len(symbols))
        return FavoriteSymbolsResponse(symbols=symbols)

    except Exception:
        logger.exception("Failed to fetch favorite symbols")
        raise HTTPException(status_code=500, detail="Internal server error")


class RecentTradeSymbolsResponse(BaseModel):
    symbols: list[str]


@router.get("/recent-trade-symbols", response_model=RecentTradeSymbolsResponse)
async def get_recent_trade_symbols(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Return symbols that had trades in the last N days.

    Queries trade_fills for distinct symbols with executed_at >= cutoff.
    Used by marketdata-service to keep recently-traded symbols updated.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        rows = (
            db.query(TradeFill.symbol)
            .filter(TradeFill.executed_at >= cutoff)
            .distinct()
            .all()
        )

        symbols = sorted(row[0] for row in rows)
        logger.info(
            "Recent trade symbols: %d symbols traded in last %d days",
            len(symbols),
            days,
        )
        return RecentTradeSymbolsResponse(symbols=symbols)

    except Exception:
        logger.exception("Failed to fetch recent trade symbols")
        raise HTTPException(status_code=500, detail="Internal server error")
