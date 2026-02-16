"""FastAPI router for position campaigns.

Provides endpoints for:
- Listing campaigns (summaries with computed aggregates)
- Fetching campaign details with fills and decision contexts
- Fetching P&L summary aggregated by ticker
- Fetching P&L timeseries for charting
- Saving/updating decision contexts on fills
- Rebuilding campaigns
"""

import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trading_repository import TradingBuddyRepository
from src.data.database.broker_models import TradeFill
from src.data.database.trade_lifecycle_models import (
    CampaignCheck,
    DecisionContext,
)
from src.data.database.strategy_models import Strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

def get_db():
    """Get database session."""
    with get_db_manager().get_session() as session:
        yield session


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _format_dt(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime to ISO 8601 string with Z suffix."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# -----------------------------------------------------------------------------
# Response Models - Campaign List/Detail
# -----------------------------------------------------------------------------

class FillResponse(BaseModel):
    """A single trade fill within a campaign."""
    fillId: str
    symbol: str
    side: str
    quantity: float
    price: float
    fees: float
    executedAt: str
    broker: Optional[str] = None
    orderId: Optional[str] = None
    contextType: Optional[str] = None
    strategyName: Optional[str] = None
    hypothesis: Optional[str] = None
    notes: Optional[str] = None


class CampaignSummaryResponse(BaseModel):
    """Summary of a campaign for the list view."""
    campaignId: str
    symbol: str
    direction: str
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    fillCount: int
    netQuantity: float
    totalBought: float
    totalSold: float
    realizedPnl: Optional[float] = None
    strategyName: Optional[str] = None
    orderIds: List[str] = []


class CampaignDetailResponse(BaseModel):
    """Full campaign detail response."""
    campaignId: str
    symbol: str
    direction: str
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    fillCount: int
    netQuantity: float
    totalBought: float
    totalSold: float
    realizedPnl: Optional[float] = None
    strategyName: Optional[str] = None
    fills: List[FillResponse]
    checks: List[dict] = []


class SaveFillContextRequest(BaseModel):
    """Request body for saving a decision context on a fill."""
    contextType: str
    strategyName: Optional[str] = None
    hypothesis: Optional[str] = None
    exitIntent: Optional[str] = None
    feelingsThen: Optional[dict] = None
    feelingsNow: Optional[dict] = None
    notes: Optional[str] = None


class DecisionContextResponse(BaseModel):
    """Decision context response."""
    contextId: str
    fillId: str
    contextType: str
    strategyName: Optional[str] = None
    hypothesis: Optional[str] = None
    exitIntent: Optional[str] = None
    feelingsThen: Optional[dict] = None
    feelingsNow: Optional[dict] = None
    notes: Optional[str] = None
    updatedAt: str


# -----------------------------------------------------------------------------
# Response Models - P&L
# -----------------------------------------------------------------------------

class TickerPnlResponse(BaseModel):
    """P&L summary for a single ticker symbol."""
    symbol: str
    total_pnl: float
    total_pnl_pct: float
    campaign_count: int
    fill_count: int
    first_entry_time: Optional[datetime] = None


class TickerPnlListResponse(BaseModel):
    """List of ticker P&L summaries."""
    tickers: List[TickerPnlResponse]


class PnlTimeseriesPoint(BaseModel):
    """A single point in the P&L timeseries."""
    timestamp: datetime
    realized_pnl: float
    cumulative_pnl: float
    fill_count: int


class PnlTimeseriesResponse(BaseModel):
    """P&L timeseries response for charting."""
    symbol: Optional[str] = None
    points: List[PnlTimeseriesPoint]
    total_pnl: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Helper Functions — Campaign Aggregates
# -----------------------------------------------------------------------------

def _compute_campaign_aggregates(fills: list[TradeFill]) -> dict:
    """Compute aggregates from a list of fills for a campaign.

    Returns dict with: direction, status, opened_at, closed_at,
    net_quantity, total_bought, total_sold, realized_pnl, order_ids.
    """
    if not fills:
        return {
            "direction": "flat",
            "status": "closed",
            "opened_at": None,
            "closed_at": None,
            "net_quantity": 0.0,
            "total_bought": 0.0,
            "total_sold": 0.0,
            "realized_pnl": 0.0,
            "order_ids": [],
        }

    net_qty = 0.0
    total_bought_qty = 0.0
    total_sold_qty = 0.0
    total_bought_cost = 0.0
    total_sold_proceeds = 0.0
    order_ids: list[str] = []
    seen_order_ids: set = set()

    for fill in fills:
        if fill.side.lower() == "buy":
            total_bought_qty += fill.quantity
            total_bought_cost += fill.quantity * fill.price
            net_qty += fill.quantity
        else:
            total_sold_qty += fill.quantity
            total_sold_proceeds += fill.quantity * fill.price
            net_qty -= fill.quantity

        if fill.order_id and fill.order_id not in seen_order_ids:
            seen_order_ids.add(fill.order_id)
            order_ids.append(fill.order_id)

    # Direction based on first fill
    direction = "long" if fills[0].side.lower() == "buy" else "short"

    # Status based on net quantity
    status = "closed" if abs(net_qty) < 1e-9 else "open"

    # Realized P&L: matched quantity × (sell_avg - buy_avg)
    matched_qty = min(total_bought_qty, total_sold_qty)
    if matched_qty > 0:
        buy_avg = total_bought_cost / total_bought_qty if total_bought_qty > 0 else 0
        sell_avg = total_sold_proceeds / total_sold_qty if total_sold_qty > 0 else 0
        realized_pnl = round(matched_qty * (sell_avg - buy_avg), 2)
        # Invert for short direction
        if direction == "short":
            realized_pnl = -realized_pnl
    else:
        realized_pnl = 0.0

    # Fees reduce P&L
    total_fees = sum(f.fees for f in fills)
    realized_pnl -= total_fees

    return {
        "direction": direction,
        "status": status,
        "opened_at": fills[0].executed_at,
        "closed_at": fills[-1].executed_at if status == "closed" else None,
        "net_quantity": round(net_qty, 6),
        "total_bought": total_bought_qty,
        "total_sold": total_sold_qty,
        "realized_pnl": realized_pnl,
        "order_ids": order_ids,
    }


def _fill_to_response(fill: TradeFill, db: Session) -> FillResponse:
    """Convert a TradeFill to FillResponse, including context info."""
    ctx = db.query(DecisionContext).filter(
        DecisionContext.fill_id == fill.id
    ).first()

    strategy_name = None
    if ctx and ctx.strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == ctx.strategy_id).first()
        if strategy:
            strategy_name = strategy.name

    return FillResponse(
        fillId=str(fill.id),
        symbol=fill.symbol,
        side=fill.side,
        quantity=fill.quantity,
        price=fill.price,
        fees=fill.fees,
        executedAt=_format_dt(fill.executed_at),
        broker=fill.broker,
        orderId=fill.order_id,
        contextType=ctx.context_type if ctx else None,
        strategyName=strategy_name,
        hypothesis=ctx.hypothesis if ctx else None,
        notes=ctx.notes if ctx else None,
    )


def _context_to_response(ctx: DecisionContext, db: Session) -> DecisionContextResponse:
    """Convert a DecisionContext to response."""
    strategy_name = None
    if ctx.strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == ctx.strategy_id).first()
        if strategy:
            strategy_name = strategy.name

    exit_intent = ctx.exit_intent
    if isinstance(exit_intent, dict):
        exit_intent = exit_intent.get("type", "unknown")

    return DecisionContextResponse(
        contextId=str(ctx.id),
        fillId=str(ctx.fill_id),
        contextType=ctx.context_type,
        strategyName=strategy_name,
        hypothesis=ctx.hypothesis,
        exitIntent=exit_intent if isinstance(exit_intent, str) else None,
        feelingsThen=ctx.feelings_then,
        feelingsNow=ctx.feelings_now,
        notes=ctx.notes,
        updatedAt=_format_dt(ctx.updated_at),
    )


# -----------------------------------------------------------------------------
# P&L Endpoints (computed from fills)
# -----------------------------------------------------------------------------

@router.get("/pnl/by-ticker", response_model=TickerPnlListResponse)
async def get_pnl_by_ticker(
    limit: int = Query(50, ge=1, le=200, description="Maximum tickers to return"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get P&L summary aggregated by ticker symbol.

    Computes P&L from trade_fills grouped by symbol. Includes counts
    of campaigns and fills per symbol.
    """
    logger.debug("Fetching P&L by ticker for user_id=%d, limit=%d", user_id, limit)

    # Get all symbols for this user
    symbols = (
        db.query(distinct(TradeFill.symbol))
        .filter(TradeFill.account_id == user_id)
        .all()
    )

    tickers = []
    for (symbol,) in symbols:
        fills = (
            db.query(TradeFill)
            .filter(TradeFill.account_id == user_id, TradeFill.symbol == symbol)
            .order_by(TradeFill.executed_at.asc())
            .all()
        )

        if not fills:
            continue

        # Compute P&L from fills
        total_bought_cost = 0.0
        total_bought_qty = 0.0
        total_sold_proceeds = 0.0
        total_sold_qty = 0.0
        total_fees = 0.0

        for fill in fills:
            if fill.side.lower() == "buy":
                total_bought_qty += fill.quantity
                total_bought_cost += fill.quantity * fill.price
            else:
                total_sold_qty += fill.quantity
                total_sold_proceeds += fill.quantity * fill.price
            total_fees += fill.fees

        matched_qty = min(total_bought_qty, total_sold_qty)
        if matched_qty > 0 and total_bought_qty > 0 and total_sold_qty > 0:
            buy_avg = total_bought_cost / total_bought_qty
            sell_avg = total_sold_proceeds / total_sold_qty
            total_pnl = round(matched_qty * (sell_avg - buy_avg) - total_fees, 2)
        else:
            total_pnl = round(-total_fees, 2)

        total_cost = total_bought_cost if total_bought_cost > 0 else 1.0
        total_pnl_pct = round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0.0

        # Count campaigns for this symbol
        repo = TradingBuddyRepository(db)
        campaign_count = repo.count_campaign_groups(user_id, symbol=symbol)

        tickers.append(TickerPnlResponse(
            symbol=symbol,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            campaign_count=campaign_count,
            fill_count=len(fills),
            first_entry_time=fills[0].executed_at,
        ))

    # Sort by total_pnl descending and limit
    tickers.sort(key=lambda t: t.total_pnl, reverse=True)
    tickers = tickers[:limit]

    logger.debug("Found %d tickers with P&L data", len(tickers))
    return TickerPnlListResponse(tickers=tickers)


@router.get("/pnl/timeseries", response_model=PnlTimeseriesResponse)
async def get_pnl_timeseries(
    symbol: Optional[str] = Query(None, description="Filter by ticker symbol"),
    start_date: Optional[date] = Query(None, description="Start date (inclusive)"),
    end_date: Optional[date] = Query(None, description="End date (inclusive)"),
    granularity: Literal["day", "week", "month"] = Query(
        "day", description="Time granularity for grouping"
    ),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get P&L timeseries for charting.

    Computes cumulative P&L over time from fills. Groups by date
    granularity for rendering charts.
    """
    logger.debug(
        "Fetching P&L timeseries: user_id=%d, symbol=%s, start=%s, end=%s, granularity=%s",
        user_id, symbol, start_date, end_date, granularity,
    )

    # Date truncation for grouping
    if granularity == "week":
        date_trunc = func.date_trunc("week", TradeFill.executed_at)
    elif granularity == "month":
        date_trunc = func.date_trunc("month", TradeFill.executed_at)
    else:
        date_trunc = func.date(TradeFill.executed_at)

    # Build query: sells represent realized proceeds, buys represent cost
    # We approximate daily P&L as (sell_proceeds - buy_cost) for that period
    query = db.query(
        date_trunc.label("period"),
        func.coalesce(
            func.sum(
                func.case(
                    (TradeFill.side == "sell", TradeFill.quantity * TradeFill.price),
                    else_=0.0,
                )
            ),
            0.0,
        ).label("sell_proceeds"),
        func.coalesce(
            func.sum(
                func.case(
                    (TradeFill.side == "buy", TradeFill.quantity * TradeFill.price),
                    else_=0.0,
                )
            ),
            0.0,
        ).label("buy_cost"),
        func.coalesce(func.sum(TradeFill.fees), 0.0).label("fees"),
        func.count(TradeFill.id).label("fill_count"),
    ).filter(TradeFill.account_id == user_id)

    if symbol:
        query = query.filter(TradeFill.symbol == symbol.upper())
    if start_date:
        query = query.filter(func.date(TradeFill.executed_at) >= start_date)
    if end_date:
        query = query.filter(func.date(TradeFill.executed_at) <= end_date)

    results = (
        query.group_by(date_trunc)
        .order_by(date_trunc.asc())
        .all()
    )

    logger.debug("Found %d periods with fill data", len(results))

    points = []
    cumulative = 0.0
    for row in results:
        # Period P&L approximation: sells - buys - fees
        period_pnl = round(row.sell_proceeds - row.buy_cost - row.fees, 2)
        cumulative += period_pnl

        period_ts = row.period
        if isinstance(period_ts, date) and not isinstance(period_ts, datetime):
            period_ts = datetime.combine(period_ts, datetime.min.time())

        points.append(PnlTimeseriesPoint(
            timestamp=period_ts,
            realized_pnl=period_pnl,
            cumulative_pnl=round(cumulative, 2),
            fill_count=row.fill_count,
        ))

    period_start = points[0].timestamp if points else None
    period_end = points[-1].timestamp if points else None

    return PnlTimeseriesResponse(
        symbol=symbol.upper() if symbol else None,
        points=points,
        total_pnl=round(cumulative, 2),
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/pnl/{symbol}", response_model=TickerPnlResponse)
async def get_ticker_pnl(
    symbol: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get P&L summary for a single ticker symbol."""
    logger.debug("Fetching P&L for symbol=%s, user_id=%d", symbol, user_id)

    fills = (
        db.query(TradeFill)
        .filter(TradeFill.account_id == user_id, TradeFill.symbol == symbol.upper())
        .order_by(TradeFill.executed_at.asc())
        .all()
    )

    if not fills:
        return TickerPnlResponse(
            symbol=symbol.upper(),
            total_pnl=0.0,
            total_pnl_pct=0.0,
            campaign_count=0,
            fill_count=0,
            first_entry_time=None,
        )

    total_bought_cost = 0.0
    total_bought_qty = 0.0
    total_sold_proceeds = 0.0
    total_sold_qty = 0.0
    total_fees = 0.0

    for fill in fills:
        if fill.side.lower() == "buy":
            total_bought_qty += fill.quantity
            total_bought_cost += fill.quantity * fill.price
        else:
            total_sold_qty += fill.quantity
            total_sold_proceeds += fill.quantity * fill.price
        total_fees += fill.fees

    matched_qty = min(total_bought_qty, total_sold_qty)
    if matched_qty > 0 and total_bought_qty > 0 and total_sold_qty > 0:
        buy_avg = total_bought_cost / total_bought_qty
        sell_avg = total_sold_proceeds / total_sold_qty
        total_pnl = round(matched_qty * (sell_avg - buy_avg) - total_fees, 2)
    else:
        total_pnl = round(-total_fees, 2)

    total_cost = total_bought_cost if total_bought_cost > 0 else 1.0
    total_pnl_pct = round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0.0

    repo = TradingBuddyRepository(db)
    campaign_count = repo.count_campaign_groups(user_id, symbol=symbol.upper())

    return TickerPnlResponse(
        symbol=symbol.upper(),
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        campaign_count=campaign_count,
        fill_count=len(fills),
        first_entry_time=fills[0].executed_at,
    )


# -----------------------------------------------------------------------------
# Campaign List/Detail Endpoints
# -----------------------------------------------------------------------------

@router.get("", response_model=List[CampaignSummaryResponse])
async def list_campaigns(
    symbol: Optional[str] = None,
    strategy_id: Optional[int] = None,
    limit: int = Query(200, ge=1, le=500),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List campaigns for the authenticated user.

    Optional filters:
    - symbol: Filter by ticker symbol
    - strategy_id: Filter by strategy
    """
    logger.debug(
        "list_campaigns: user_id=%d symbol=%s strategy_id=%s",
        user_id, symbol, strategy_id,
    )

    repo = TradingBuddyRepository(db)
    campaigns = repo.get_campaigns(
        account_id=user_id,
        symbol=symbol.upper() if symbol else None,
        strategy_id=strategy_id,
        limit=limit,
    )

    result = []
    for campaign in campaigns:
        group_id = campaign["group_id"]
        fills = repo.get_campaign_fills(group_id)
        agg = _compute_campaign_aggregates(fills)

        # Derive strategy from first fill's decision context
        strategy_name = None
        if fills:
            ctx = db.query(DecisionContext).filter(
                DecisionContext.fill_id == fills[0].id
            ).first()
            if ctx and ctx.strategy_id:
                strategy = db.query(Strategy).filter(Strategy.id == ctx.strategy_id).first()
                if strategy:
                    strategy_name = strategy.name

        result.append(CampaignSummaryResponse(
            campaignId=str(group_id),
            symbol=fills[0].symbol if fills else "",
            direction=agg["direction"],
            status=agg["status"],
            openedAt=_format_dt(agg["opened_at"]),
            closedAt=_format_dt(agg["closed_at"]),
            fillCount=len(fills),
            netQuantity=agg["net_quantity"],
            totalBought=agg["total_bought"],
            totalSold=agg["total_sold"],
            realizedPnl=agg["realized_pnl"],
            strategyName=strategy_name,
            orderIds=agg["order_ids"],
        ))

    logger.debug("Returning %d campaigns for user_id=%d", len(result), user_id)
    return result


@router.get("/{group_id}", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    group_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full campaign detail including fills and decision contexts."""
    repo = TradingBuddyRepository(db)

    if not repo.campaign_group_exists(group_id, user_id):
        raise HTTPException(status_code=404, detail=f"Campaign {group_id} not found")

    fills = repo.get_campaign_fills(group_id)
    agg = _compute_campaign_aggregates(fills)

    # Derive strategy from first fill's decision context
    strategy_name = None
    if fills:
        ctx = db.query(DecisionContext).filter(
            DecisionContext.fill_id == fills[0].id
        ).first()
        if ctx and ctx.strategy_id:
            strategy = db.query(Strategy).filter(Strategy.id == ctx.strategy_id).first()
            if strategy:
                strategy_name = strategy.name

    # Build fill responses with context
    fill_responses = [_fill_to_response(f, db) for f in fills]

    # Gather checks for all fills' decision contexts
    checks_list = []
    for fill in fills:
        ctx = db.query(DecisionContext).filter(DecisionContext.fill_id == fill.id).first()
        if ctx:
            checks = (
                db.query(CampaignCheck)
                .filter(CampaignCheck.decision_context_id == ctx.id)
                .order_by(CampaignCheck.checked_at.asc())
                .all()
            )
            for check in checks:
                checks_list.append({
                    "checkId": str(check.id),
                    "fillId": str(fill.id),
                    "checkType": check.check_type,
                    "code": (check.details or {}).get("code", check.check_type),
                    "severity": check.severity,
                    "passed": check.passed,
                    "nudgeText": check.nudge_text,
                    "details": check.details,
                    "checkPhase": check.check_phase,
                    "checkedAt": _format_dt(check.checked_at),
                    "acknowledged": check.acknowledged,
                    "traderAction": check.trader_action,
                })

    return CampaignDetailResponse(
        campaignId=str(group_id),
        symbol=fills[0].symbol if fills else "",
        direction=agg["direction"],
        status=agg["status"],
        openedAt=_format_dt(agg["opened_at"]),
        closedAt=_format_dt(agg["closed_at"]),
        fillCount=len(fills),
        netQuantity=agg["net_quantity"],
        totalBought=agg["total_bought"],
        totalSold=agg["total_sold"],
        realizedPnl=agg["realized_pnl"],
        strategyName=strategy_name,
        fills=fill_responses,
        checks=checks_list,
    )


# -----------------------------------------------------------------------------
# Fill Context Endpoints (atomic unit: fill)
# -----------------------------------------------------------------------------

@router.get("/fills/{fill_id}/context", response_model=DecisionContextResponse)
async def get_fill_context(
    fill_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the decision context for a specific fill."""
    fill = db.query(TradeFill).filter(
        TradeFill.id == fill_id,
        TradeFill.account_id == user_id,
    ).first()

    if not fill:
        raise HTTPException(status_code=404, detail="Fill not found")

    ctx = db.query(DecisionContext).filter(DecisionContext.fill_id == fill_id).first()
    if not ctx:
        raise HTTPException(status_code=404, detail="No context for this fill")

    return _context_to_response(ctx, db)


@router.put("/fills/{fill_id}/context", response_model=DecisionContextResponse)
async def save_fill_context(
    fill_id: int,
    request: SaveFillContextRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update a decision context for a fill.

    If a context already exists for this fill, it is updated.
    Otherwise, a new context is created.

    If strategy changes, triggers campaign rebuild for affected groups.
    """
    fill = db.query(TradeFill).filter(
        TradeFill.id == fill_id,
        TradeFill.account_id == user_id,
    ).first()

    if not fill:
        raise HTTPException(status_code=404, detail="Fill not found")

    repo = TradingBuddyRepository(db)

    # Resolve strategy name to ID
    strategy_id = None
    if request.strategyName:
        strategy = db.query(Strategy).filter(
            Strategy.name == request.strategyName,
            Strategy.account_id == user_id,
        ).first()
        if strategy:
            strategy_id = strategy.id

    # Build exit_intent value
    exit_intent_value = request.exitIntent

    # Get or create context
    ctx = db.query(DecisionContext).filter(DecisionContext.fill_id == fill_id).first()
    old_strategy_id = ctx.strategy_id if ctx else None

    if ctx:
        ctx.context_type = request.contextType
        ctx.strategy_id = strategy_id
        ctx.hypothesis = request.hypothesis
        ctx.exit_intent = exit_intent_value
        ctx.feelings_then = request.feelingsThen
        ctx.feelings_now = request.feelingsNow
        ctx.notes = request.notes
        ctx.updated_at = datetime.now(timezone.utc)
        flag_modified(ctx, "exit_intent")
        flag_modified(ctx, "feelings_then")
        flag_modified(ctx, "feelings_now")
        db.flush()
        logger.info("Updated decision context id=%s for fill %s", ctx.id, fill_id)
    else:
        ctx = repo.create_decision_context(
            fill_id=fill_id,
            account_id=user_id,
            context_type=request.contextType,
            strategy_id=strategy_id,
            hypothesis=request.hypothesis,
            exit_intent=exit_intent_value,
            feelings_then=request.feelingsThen,
            feelings_now=request.feelingsNow,
            notes=request.notes,
        )
        logger.info("Created decision context id=%s for fill %s", ctx.id, fill_id)

    # Rebuild campaigns if strategy changed
    if old_strategy_id != strategy_id:
        repo.on_strategy_updated(
            account_id=user_id,
            fill_id=fill_id,
            old_strategy_id=old_strategy_id,
            new_strategy_id=strategy_id,
        )

    db.commit()
    return _context_to_response(ctx, db)


# -----------------------------------------------------------------------------
# Rebuild Campaigns
# -----------------------------------------------------------------------------

class RebuildCampaignsResponse(BaseModel):
    """Response for campaign rebuild."""
    campaigns_created: int
    fills_grouped: int
    groups_rebuilt: int


@router.post("/rebuild", response_model=RebuildCampaignsResponse)
async def rebuild_campaigns(
    symbol: Optional[str] = Query(None, description="Optional symbol filter"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rebuild campaigns from fills.

    Deletes existing campaigns and recomputes from trade_fills +
    decision_contexts using zero-crossing algorithm.
    """
    logger.info("rebuild_campaigns: user_id=%d, symbol=%s", user_id, symbol)

    repo = TradingBuddyRepository(db)

    if symbol:
        # Rebuild for all strategy groups under this symbol
        strategy_ids = (
            db.query(distinct(DecisionContext.strategy_id))
            .join(TradeFill, TradeFill.id == DecisionContext.fill_id)
            .filter(
                TradeFill.account_id == user_id,
                TradeFill.symbol == symbol.upper(),
            )
            .all()
        )

        total_stats = {"campaigns_created": 0, "fills_grouped": 0, "groups_rebuilt": 0}
        for (sid,) in strategy_ids:
            group_stats = repo.rebuild_campaigns(user_id, symbol.upper(), sid)
            total_stats["campaigns_created"] += group_stats["campaigns_created"]
            total_stats["fills_grouped"] += group_stats["fills_grouped"]
            total_stats["groups_rebuilt"] += 1
    else:
        total_stats = repo.rebuild_all_campaigns(user_id)

    db.commit()

    logger.info("Rebuild complete for user_id=%d: %s", user_id, total_stats)
    return RebuildCampaignsResponse(**total_stats)
