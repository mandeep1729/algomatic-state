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
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.data.database.connection import get_db_manager
from src.data.database.broker_models import TradeFill
from src.data.database.trade_lifecycle_models import DecisionContext
from src.data.database.trading_buddy_models import UserProfile
from src.data.database.strategy_models import Strategy

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/accounts/{account_id}/fills", response_model=FillsResponse)
async def get_fills_with_context(
    account_id: int,
    lookback_days: int = Query(default=90, ge=1, le=365),
    symbol: Optional[str] = Query(default=None),
):
    """Get fills with decision contexts for an account within a lookback window.

    Returns fills joined with their decision context data including
    strategy info and exit intent.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    try:
        with get_db_manager().get_session() as session:
            query = (
                session.query(TradeFill, DecisionContext, Strategy.name.label("strategy_name"))
                .outerjoin(DecisionContext, DecisionContext.fill_id == TradeFill.id)
                .outerjoin(Strategy, Strategy.id == DecisionContext.strategy_id)
                .filter(
                    TradeFill.account_id == account_id,
                    TradeFill.executed_at >= cutoff,
                )
            )

            if symbol:
                query = query.filter(TradeFill.symbol == symbol.upper())

            query = query.order_by(TradeFill.executed_at.asc())
            rows = query.all()

            fills = []
            for fill, dc, strategy_name in rows:
                # Extract timeframe from exit_intent if available
                timeframe = None
                if dc and dc.exit_intent and isinstance(dc.exit_intent, dict):
                    timeframe = dc.exit_intent.get("timeframe")

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
                    exit_intent=dc.exit_intent if dc else None,
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
async def get_account_profile(account_id: int):
    """Get user profile including account_balance, risk settings, and stats."""
    try:
        with get_db_manager().get_session() as session:
            profile = session.query(UserProfile).filter(
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
async def save_baseline_stats(account_id: int, request: BaselineStatsRequest):
    """Save computed baseline stats to user_profiles.stats JSONB column."""
    try:
        with get_db_manager().get_session() as session:
            profile = session.query(UserProfile).filter(
                UserProfile.user_account_id == account_id,
            ).first()

            if profile is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No profile found for account_id={account_id}",
                )

            profile.stats = request.stats

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(profile, "stats")
            session.flush()

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
async def save_inferred_context(fill_id: int, request: InferredContextRequest):
    """Merge entry quality results into decision_contexts.inferred_context JSONB.

    Performs a shallow merge: existing keys in inferred_context are preserved,
    new keys from the request are added/overwritten.
    """
    try:
        with get_db_manager().get_session() as session:
            dc = session.query(DecisionContext).filter(
                DecisionContext.fill_id == fill_id,
            ).first()

            if dc is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No DecisionContext for fill_id={fill_id}",
                )

            existing = dc.inferred_context or {}
            merged = {**existing, **request.inferred_context}
            dc.inferred_context = merged

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(dc, "inferred_context")
            session.flush()

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
):
    """List account IDs with recent trading activity.

    Returns accounts that have at least one fill within the lookback window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=active_since_days)

    try:
        with get_db_manager().get_session() as session:
            from sqlalchemy import distinct

            rows = (
                session.query(distinct(TradeFill.account_id))
                .filter(
                    TradeFill.account_id.isnot(None),
                    TradeFill.executed_at >= cutoff,
                )
                .all()
            )

            account_ids = [row[0] for row in rows]

        logger.info(
            "Found %d active accounts (since %d days ago)",
            len(account_ids), active_since_days,
        )
        return ActiveAccountsResponse(account_ids=account_ids)

    except Exception:
        logger.exception("Failed to fetch active accounts")
        raise HTTPException(status_code=500, detail="Internal server error")
