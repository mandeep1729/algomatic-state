"""FastAPI router for position campaigns.

Provides endpoints for:
- Listing campaigns (summaries)
- Fetching campaign details with legs and fill information
- Fetching P&L summary aggregated by ticker symbol
- Fetching P&L timeseries for charting
- Saving/updating decision contexts
"""

import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trading_repository import TradingBuddyRepository
from src.data.database.trade_lifecycle_models import (
    PositionCampaign,
    CampaignLeg,
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

class CampaignSummaryResponse(BaseModel):
    """Summary of a campaign for the list view."""
    campaignId: str
    symbol: str
    direction: str
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    legsCount: int
    maxQty: float
    legQuantities: List[float]
    overallLabel: str
    keyFlags: List[str]
    orderIds: List[str] = []


class CampaignLegResponse(BaseModel):
    """A single leg within a campaign."""
    legId: str
    campaignId: Optional[str] = None
    legType: str
    side: str
    quantity: float
    avgPrice: float
    startedAt: str
    endedAt: Optional[str] = None


class CampaignMetaResponse(BaseModel):
    """Full campaign metadata (used in detail view)."""
    campaignId: str
    symbol: str
    direction: str
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    legsCount: int
    maxQty: float
    pnlRealized: Optional[float] = None
    costBasisMethod: str
    source: str


class DecisionContextResponse(BaseModel):
    """Decision context attached to a campaign or leg."""
    contextId: str
    scope: str
    campaignId: Optional[str] = None
    legId: Optional[str] = None
    contextType: str
    strategyTags: List[str]
    hypothesis: Optional[str] = None
    exitIntent: Optional[str] = None
    feelingsThen: Optional[dict] = None
    feelingsNow: Optional[dict] = None
    notes: Optional[str] = None
    updatedAt: str


class CampaignDetailResponse(BaseModel):
    """Full campaign detail response."""
    campaign: CampaignMetaResponse
    legs: List[CampaignLegResponse]
    contextsByLeg: dict


class SaveContextRequest(BaseModel):
    """Request body for saving a decision context."""
    scope: str
    campaignId: Optional[str] = None
    legId: Optional[str] = None
    contextType: str
    strategyTags: List[str] = []
    hypothesis: Optional[str] = None
    exitIntent: Optional[str] = None
    feelingsThen: Optional[dict] = None
    feelingsNow: Optional[dict] = None
    notes: Optional[str] = None


# -----------------------------------------------------------------------------
# Response Models - P&L
# -----------------------------------------------------------------------------

class TickerPnlResponse(BaseModel):
    """P&L summary for a single ticker symbol.

    Aggregates P&L and trade statistics from position_campaigns.
    """

    symbol: str
    total_pnl: float
    total_pnl_pct: float
    trade_count: int
    closed_count: int
    first_entry_time: Optional[datetime] = None


class TickerPnlListResponse(BaseModel):
    """List of ticker P&L summaries."""

    tickers: List[TickerPnlResponse]


class PnlTimeseriesPoint(BaseModel):
    """A single point in the P&L timeseries."""

    timestamp: datetime
    realized_pnl: float
    cumulative_pnl: float
    trade_count: int


class PnlTimeseriesResponse(BaseModel):
    """P&L timeseries response for charting.

    Returns time series of cumulative P&L grouped by date.
    """

    symbol: Optional[str] = None
    points: List[PnlTimeseriesPoint]
    total_pnl: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _campaign_to_summary(campaign) -> CampaignSummaryResponse:
    """Convert a PositionCampaign ORM model to a summary response."""
    legs_count = len(campaign.legs) if campaign.legs else 0
    # Extract key flags from campaign tags
    tags_dict = campaign.tags or {}
    key_flags = tags_dict.get("key_flags", [])

    # Determine overall label from tags (default to 'mixed' if not set)
    overall_label = tags_dict.get("overall_label", "mixed")

    # Build leg quantities with sign: buy is positive, sell is negative
    leg_quantities: List[float] = []
    if campaign.legs:
        for leg in campaign.legs:
            qty = leg.quantity or 0
            # Sell legs are negative, buy legs are positive
            if leg.side == "sell":
                qty = -qty
            leg_quantities.append(qty)

    # Collect unique broker order IDs from fills
    order_ids: List[str] = []
    seen_order_ids: set = set()
    if campaign.legs:
        for leg in campaign.legs:
            for fm in (leg.fill_maps or []):
                fill = fm.fill
                if fill and fill.order_id and fill.order_id not in seen_order_ids:
                    seen_order_ids.add(fill.order_id)
                    order_ids.append(fill.order_id)

    return CampaignSummaryResponse(
        campaignId=str(campaign.id),
        symbol=campaign.symbol,
        direction=campaign.direction,
        status=campaign.status,
        openedAt=_format_dt(campaign.opened_at),
        closedAt=_format_dt(campaign.closed_at),
        legsCount=legs_count,
        maxQty=campaign.max_qty or campaign.qty_opened or 0,
        legQuantities=leg_quantities,
        overallLabel=overall_label,
        keyFlags=key_flags,
        orderIds=order_ids,
    )


def _leg_to_response(leg, campaign_id: str) -> CampaignLegResponse:
    """Convert a CampaignLeg ORM model to a response."""
    return CampaignLegResponse(
        legId=str(leg.id),
        campaignId=campaign_id,
        legType=leg.leg_type,
        side=leg.side,
        quantity=leg.quantity,
        avgPrice=leg.avg_price or 0,
        startedAt=_format_dt(leg.started_at),
        endedAt=_format_dt(leg.ended_at),
    )


def _context_to_response(ctx) -> DecisionContextResponse:
    """Convert a DecisionContext ORM model to a response."""
    # exit_intent stored as JSONB in DB, but frontend expects a string
    exit_intent = ctx.exit_intent
    if isinstance(exit_intent, dict):
        exit_intent = exit_intent.get("type", "unknown")

    # The DB model uses strategy_id (FK) not strategy_tags (array).
    # Return the strategy name as a single-element list if set.
    strategy_tags: List[str] = []
    if hasattr(ctx, 'strategy') and ctx.strategy:
        strategy_tags = [ctx.strategy.name]

    return DecisionContextResponse(
        contextId=str(ctx.id),
        scope="leg" if ctx.leg_id else "campaign",
        campaignId=str(ctx.campaign_id) if ctx.campaign_id else None,
        legId=str(ctx.leg_id) if ctx.leg_id else None,
        contextType=ctx.context_type,
        strategyTags=strategy_tags,
        hypothesis=ctx.hypothesis,
        exitIntent=exit_intent if isinstance(exit_intent, str) else None,
        feelingsThen=ctx.feelings_then,
        feelingsNow=ctx.feelings_now,
        notes=ctx.notes,
        updatedAt=_format_dt(ctx.updated_at),
    )


# -----------------------------------------------------------------------------
# P&L Endpoints
# -----------------------------------------------------------------------------

@router.get("/pnl/by-ticker", response_model=TickerPnlListResponse)
async def get_pnl_by_ticker(
    status: Literal["open", "closed", "all"] = Query(
        "all", description="Filter by campaign status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of tickers to return"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get P&L summary aggregated by ticker symbol.

    Aggregates realized P&L and trade counts from position_campaigns
    grouped by symbol. Ordered by total P&L descending.

    Args:
        status: Filter by campaign status ('open', 'closed', or 'all')
        limit: Maximum number of tickers to return (default 50, max 200)

    Returns:
        List of ticker P&L summaries.
    """
    logger.debug(
        "Fetching P&L by ticker for user_id=%d, status=%s, limit=%d",
        user_id,
        status,
        limit,
    )

    # Build base query with aggregations
    base_query = db.query(
        PositionCampaign.symbol,
        func.coalesce(func.sum(PositionCampaign.realized_pnl), 0.0).label("total_pnl"),
        func.count(PositionCampaign.id).label("trade_count"),
        func.count(PositionCampaign.id).filter(
            PositionCampaign.status == "closed"
        ).label("closed_count"),
        func.min(PositionCampaign.opened_at).label("first_entry_time"),
    ).filter(PositionCampaign.account_id == user_id)

    # Apply status filter
    if status == "open":
        base_query = base_query.filter(PositionCampaign.status == "open")
    elif status == "closed":
        base_query = base_query.filter(PositionCampaign.status == "closed")
    # 'all' means no additional filter

    # Group by symbol and order by total P&L descending
    results = (
        base_query.group_by(PositionCampaign.symbol)
        .order_by(func.coalesce(func.sum(PositionCampaign.realized_pnl), 0.0).desc())
        .limit(limit)
        .all()
    )

    logger.debug("Found %d tickers with P&L data", len(results))

    # Build response - need to compute total_pnl_pct from aggregated data
    tickers = []
    for row in results:
        # For P&L percentage, we need to calculate cost basis
        # Query total cost basis for this symbol (closed trades only have realized P&L)
        cost_basis_query = db.query(
            func.sum(PositionCampaign.avg_open_price * PositionCampaign.qty_opened)
        ).filter(
            PositionCampaign.account_id == user_id,
            PositionCampaign.symbol == row.symbol,
            PositionCampaign.status == "closed",
        ).scalar()

        total_cost = cost_basis_query or 0.0
        total_pnl_pct = (row.total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        tickers.append(
            TickerPnlResponse(
                symbol=row.symbol,
                total_pnl=round(row.total_pnl, 2),
                total_pnl_pct=round(total_pnl_pct, 2),
                trade_count=row.trade_count,
                closed_count=row.closed_count,
                first_entry_time=row.first_entry_time,
            )
        )

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

    Returns cumulative P&L over time based on closed position campaigns.
    Useful for rendering P&L charts aligned with price data.

    Args:
        symbol: Optional filter by ticker symbol (case-insensitive)
        start_date: Start date for the time range (inclusive)
        end_date: End date for the time range (inclusive)
        granularity: Time grouping - 'day', 'week', or 'month'

    Returns:
        Timeseries of daily/weekly/monthly P&L with running cumulative totals.
    """
    logger.debug(
        "Fetching P&L timeseries for user_id=%d, symbol=%s, start=%s, end=%s, granularity=%s",
        user_id,
        symbol,
        start_date,
        end_date,
        granularity,
    )

    # Build date truncation expression based on granularity
    if granularity == "week":
        # Truncate to start of week (Monday)
        date_trunc = func.date_trunc("week", PositionCampaign.closed_at)
    elif granularity == "month":
        date_trunc = func.date_trunc("month", PositionCampaign.closed_at)
    else:  # day
        date_trunc = func.date(PositionCampaign.closed_at)

    # Build base query: aggregate P&L by time period
    base_query = db.query(
        date_trunc.label("period"),
        func.coalesce(func.sum(PositionCampaign.realized_pnl), 0.0).label("realized_pnl"),
        func.count(PositionCampaign.id).label("trade_count"),
    ).filter(
        PositionCampaign.account_id == user_id,
        PositionCampaign.status == "closed",
        PositionCampaign.closed_at.isnot(None),
    )

    # Apply optional filters
    if symbol:
        base_query = base_query.filter(PositionCampaign.symbol == symbol.upper())

    if start_date:
        base_query = base_query.filter(
            func.date(PositionCampaign.closed_at) >= start_date
        )

    if end_date:
        base_query = base_query.filter(
            func.date(PositionCampaign.closed_at) <= end_date
        )

    # Group by period and order chronologically
    results = (
        base_query.group_by(date_trunc)
        .order_by(date_trunc.asc())
        .all()
    )

    logger.debug("Found %d periods with P&L data", len(results))

    # Build response with running cumulative total
    points = []
    cumulative = 0.0
    for row in results:
        cumulative += row.realized_pnl
        # Convert period to datetime for response
        period_ts = row.period
        if isinstance(period_ts, date) and not isinstance(period_ts, datetime):
            period_ts = datetime.combine(period_ts, datetime.min.time())
        points.append(
            PnlTimeseriesPoint(
                timestamp=period_ts,
                realized_pnl=round(row.realized_pnl, 2),
                cumulative_pnl=round(cumulative, 2),
                trade_count=row.trade_count,
            )
        )

    # Calculate period bounds from data
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
    """Get P&L summary for a single ticker symbol.

    Args:
        symbol: The ticker symbol to get P&L for.

    Returns:
        P&L summary for the specified ticker.
    """
    logger.debug("Fetching P&L for symbol=%s, user_id=%d", symbol, user_id)

    # Query aggregated data for this symbol
    result = db.query(
        func.coalesce(func.sum(PositionCampaign.realized_pnl), 0.0).label("total_pnl"),
        func.count(PositionCampaign.id).label("trade_count"),
        func.count(PositionCampaign.id).filter(
            PositionCampaign.status == "closed"
        ).label("closed_count"),
        func.min(PositionCampaign.opened_at).label("first_entry_time"),
    ).filter(
        PositionCampaign.account_id == user_id,
        PositionCampaign.symbol == symbol.upper(),
    ).first()

    if result is None or result.trade_count == 0:
        # Return zero values for unknown ticker
        return TickerPnlResponse(
            symbol=symbol.upper(),
            total_pnl=0.0,
            total_pnl_pct=0.0,
            trade_count=0,
            closed_count=0,
            first_entry_time=None,
        )

    # Calculate cost basis for P&L percentage
    cost_basis_query = db.query(
        func.sum(PositionCampaign.avg_open_price * PositionCampaign.qty_opened)
    ).filter(
        PositionCampaign.account_id == user_id,
        PositionCampaign.symbol == symbol.upper(),
        PositionCampaign.status == "closed",
    ).scalar()

    total_cost = cost_basis_query or 0.0
    total_pnl_pct = (result.total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    return TickerPnlResponse(
        symbol=symbol.upper(),
        total_pnl=round(result.total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        trade_count=result.trade_count,
        closed_count=result.closed_count,
        first_entry_time=result.first_entry_time,
    )


# -----------------------------------------------------------------------------
# Campaign Consolidation
# -----------------------------------------------------------------------------

class ConsolidateResponse(BaseModel):
    """Response for campaign consolidation."""
    groups_merged: int
    campaigns_removed: int
    lots_reassigned: int
    legs_reassigned: int


@router.post("/consolidate", response_model=ConsolidateResponse)
async def consolidate_campaigns(
    symbol: Optional[str] = Query(None, description="Optional symbol filter"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consolidate duplicate open campaigns for the same (symbol, direction).

    When incremental sync creates parallel open campaigns, this endpoint
    merges them by keeping the oldest campaign and reassigning all related
    objects (lots, legs, contexts, evaluations) from the duplicates.

    Args:
        symbol: Optional ticker symbol to consolidate (all symbols if omitted)

    Returns:
        Stats on groups merged, campaigns removed, and objects reassigned.
    """
    logger.info(
        "consolidate_campaigns: user_id=%d, symbol=%s", user_id, symbol,
    )

    repo = TradingBuddyRepository(db)
    stats = repo.consolidate_campaigns(account_id=user_id, symbol=symbol)
    db.commit()

    logger.info(
        "Consolidation complete for user_id=%d: %s", user_id, stats,
    )

    return ConsolidateResponse(**stats)


# -----------------------------------------------------------------------------
# Campaign List/Detail Endpoints
# -----------------------------------------------------------------------------

class UncategorizedCountResponse(BaseModel):
    """Response for uncategorized trade fills count."""
    count: int


@router.get("/uncategorized-count", response_model=UncategorizedCountResponse)
async def get_uncategorized_count(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get count of trade fills not yet categorized into campaigns.

    These are fills that have been synced from the broker but not yet
    processed into position campaigns. The user should categorize these
    for better trading insights.

    Returns:
        Count of uncategorized trade fills.
    """
    logger.debug("Fetching uncategorized fills count for user_id=%d", user_id)

    repo = TradingBuddyRepository(db)
    unprocessed_fills = repo.get_unprocessed_fills(account_id=user_id)
    count = len(unprocessed_fills)

    logger.debug("Found %d uncategorized fills for user_id=%d", count, user_id)

    return UncategorizedCountResponse(count=count)


# -----------------------------------------------------------------------------
# Bulk Leg Strategy Update
# -----------------------------------------------------------------------------

class BulkUpdateLegStrategyRequest(BaseModel):
    """Request body for bulk-updating strategy on multiple campaign legs."""
    leg_ids: List[int]
    strategy_id: Optional[int] = None


class BulkUpdateLegStrategyResponse(BaseModel):
    """Response for bulk leg strategy update."""
    updated_count: int
    skipped_count: int


@router.post("/legs/bulk-update-strategy", response_model=BulkUpdateLegStrategyResponse)
async def bulk_update_leg_strategy(
    request: BulkUpdateLegStrategyRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-update the strategy assignment for multiple campaign legs.

    For each leg, finds or creates a DecisionContext and sets the strategy_id.
    Legs not owned by the current user are skipped.
    """
    logger.debug(
        "bulk_update_leg_strategy: user_id=%d, leg_ids=%s, strategy_id=%s",
        user_id, request.leg_ids, request.strategy_id,
    )

    if not request.leg_ids:
        return BulkUpdateLegStrategyResponse(updated_count=0, skipped_count=0)

    # Validate strategy ownership if provided
    if request.strategy_id is not None:
        strategy = db.query(Strategy).filter(
            Strategy.id == request.strategy_id,
            Strategy.account_id == user_id,
        ).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

    # Load legs by account_id (supports both campaign-bound and orphaned legs)
    legs = (
        db.query(CampaignLeg)
        .filter(
            CampaignLeg.id.in_(request.leg_ids),
            CampaignLeg.account_id == user_id,
        )
        .all()
    )
    valid_leg_ids = {leg.id for leg in legs}

    updated_count = 0
    skipped_count = 0
    affected_legs: list[tuple[int, int]] = []  # (leg_id, campaign_id)

    for leg_id in request.leg_ids:
        if leg_id not in valid_leg_ids:
            skipped_count += 1
            logger.warning(
                "bulk_update_leg_strategy: leg_id=%d not owned by user_id=%d",
                leg_id, user_id,
            )
            continue

        leg = next(l for l in legs if l.id == leg_id)

        # Find or create DecisionContext for this leg
        context = db.query(DecisionContext).filter(
            DecisionContext.leg_id == leg.id,
        ).first()

        if context:
            context.strategy_id = request.strategy_id
            context.updated_at = datetime.now(timezone.utc)
        else:
            context_type_map = {
                "open": "entry",
                "add": "add",
                "reduce": "reduce",
                "close": "exit",
                "flip_close": "exit",
                "flip_open": "entry",
            }
            context_type = context_type_map.get(leg.leg_type, "entry")

            context = DecisionContext(
                account_id=user_id,
                campaign_id=leg.campaign_id,
                leg_id=leg.id,
                context_type=context_type,
                strategy_id=request.strategy_id,
            )
            db.add(context)

        updated_count += 1
        affected_legs.append((leg.id, leg.campaign_id))

    db.flush()

    # Trigger unwind + regroup for each unique (symbol, strategy) combo
    if request.strategy_id is not None and affected_legs:
        repo = TradingBuddyRepository(db)

        # Collect unique (symbol, strategy_id) pairs and earliest timestamp
        scope_map: dict[tuple[str, int], datetime] = {}
        for leg_id, _campaign_id in affected_legs:
            leg = next(l for l in legs if l.id == leg_id)
            key = (leg.symbol, request.strategy_id)
            if key not in scope_map or leg.started_at < scope_map[key]:
                scope_map[key] = leg.started_at

        for (sym, strat_id), earliest_ts in scope_map.items():
            logger.info(
                "Unwind+regroup for symbol=%s strategy=%d after %s",
                sym, strat_id, earliest_ts,
            )
            # Unwind: unlink later legs from existing campaigns for this strategy
            repo.unwind_legs_after(user_id, sym, strat_id, earliest_ts)
            # Also orphan the updated legs from their old campaigns
            for leg_id, _cid in affected_legs:
                leg = next(l for l in legs if l.id == leg_id)
                if leg.symbol == sym and leg.campaign_id is not None:
                    leg.campaign_id = None
            db.flush()
            # Regroup all orphaned legs for this (symbol, strategy)
            repo.regroup_legs_for_strategy(user_id, sym, strat_id)

    db.commit()

    # Trigger reviewer checks for affected legs
    if affected_legs:
        from src.reviewer.publisher import publish_context_updated
        for leg_id, campaign_id in affected_legs:
            publish_context_updated(
                leg_id=leg_id, campaign_id=campaign_id, account_id=user_id,
            )

    logger.info(
        "bulk_update_leg_strategy: user_id=%d, updated=%d, skipped=%d",
        user_id, updated_count, skipped_count,
    )

    return BulkUpdateLegStrategyResponse(
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


# -----------------------------------------------------------------------------
# Delete Campaign (orphans legs)
# -----------------------------------------------------------------------------

class DeleteCampaignResponse(BaseModel):
    """Response for campaign deletion."""
    deleted: bool
    legs_orphaned: int
    contexts_updated: int


@router.delete("/{campaign_id}", response_model=DeleteCampaignResponse)
async def delete_campaign(
    campaign_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a campaign, orphaning its legs instead of destroying them.

    Legs become orphaned (campaign_id=NULL) and their strategy_id is cleared
    on decision contexts, but hypothesis/notes/feelings are preserved.
    """
    logger.info("delete_campaign: campaign_id=%d, user_id=%d", campaign_id, user_id)

    repo = TradingBuddyRepository(db)
    try:
        result = repo.delete_campaign(campaign_id, account_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db.commit()

    logger.info(
        "Deleted campaign %d: orphaned %d legs, updated %d contexts",
        campaign_id, result["legs_orphaned"], result["contexts_updated"],
    )

    return DeleteCampaignResponse(
        deleted=True,
        legs_orphaned=result["legs_orphaned"],
        contexts_updated=result["contexts_updated"],
    )


# -----------------------------------------------------------------------------
# Orphaned Legs
# -----------------------------------------------------------------------------

class OrphanedLegResponse(BaseModel):
    """A single orphaned leg."""
    legId: str
    legType: str
    side: str
    quantity: float
    avgPrice: float
    startedAt: str
    endedAt: Optional[str] = None
    symbol: str
    direction: str
    strategyName: Optional[str] = None


class OrphanedLegGroup(BaseModel):
    """Group of orphaned legs by symbol + direction."""
    symbol: str
    direction: str
    legs: List[OrphanedLegResponse]


@router.get("/orphaned-legs", response_model=List[OrphanedLegGroup])
async def get_orphaned_legs(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get orphaned legs (campaign_id IS NULL) grouped by symbol + direction.

    Includes decision context strategy info per leg.
    """
    logger.debug("get_orphaned_legs: user_id=%d", user_id)

    repo = TradingBuddyRepository(db)
    legs = repo.get_orphaned_legs(account_id=user_id)

    # Build response grouped by (symbol, direction)
    groups: dict[tuple[str, str], list[OrphanedLegResponse]] = {}
    for leg in legs:
        # Get strategy name from decision context
        ctx = db.query(DecisionContext).filter(
            DecisionContext.leg_id == leg.id,
        ).first()
        strategy_name = None
        if ctx and ctx.strategy_id:
            strategy = db.query(Strategy).filter(Strategy.id == ctx.strategy_id).first()
            if strategy:
                strategy_name = strategy.name

        leg_resp = OrphanedLegResponse(
            legId=str(leg.id),
            legType=leg.leg_type,
            side=leg.side,
            quantity=leg.quantity,
            avgPrice=leg.avg_price or 0,
            startedAt=_format_dt(leg.started_at),
            endedAt=_format_dt(leg.ended_at),
            symbol=leg.symbol,
            direction=leg.direction,
            strategyName=strategy_name,
        )

        key = (leg.symbol, leg.direction)
        if key not in groups:
            groups[key] = []
        groups[key].append(leg_resp)

    result = [
        OrphanedLegGroup(symbol=sym, direction=direction, legs=group_legs)
        for (sym, direction), group_legs in sorted(groups.items())
    ]

    logger.debug("Found %d orphaned leg groups for user_id=%d", len(result), user_id)
    return result


@router.get("", response_model=List[CampaignSummaryResponse])
async def list_campaigns(
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List campaigns for the authenticated user.

    Optional filters:
    - symbol: Filter by ticker symbol
    - status: Filter by status ('open' or 'closed')
    """
    repo = TradingBuddyRepository(db)
    campaigns = repo.get_campaigns(
        account_id=user_id,
        symbol=symbol.upper() if symbol else None,
        status=status,
        limit=200,
    )

    return [_campaign_to_summary(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    campaign_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full campaign detail including legs and decision contexts."""
    repo = TradingBuddyRepository(db)
    campaign = repo.get_campaign(campaign_id)

    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    if campaign.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this campaign")

    campaign_id_str = str(campaign.id)
    legs = repo.get_legs_for_campaign(campaign.id)
    contexts = repo.get_contexts_for_campaign(campaign.id)

    # Build legs response
    legs_response = [_leg_to_response(leg, campaign_id_str) for leg in legs]
    legs_count = len(legs_response)

    # Build contexts keyed by leg_id (or 'campaign' for campaign-level)
    contexts_by_leg: dict = {}
    for ctx in contexts:
        key = str(ctx.leg_id) if ctx.leg_id else "campaign"
        contexts_by_leg[key] = _context_to_response(ctx)

    campaign_meta = CampaignMetaResponse(
        campaignId=campaign_id_str,
        symbol=campaign.symbol,
        direction=campaign.direction,
        status=campaign.status,
        openedAt=_format_dt(campaign.opened_at),
        closedAt=_format_dt(campaign.closed_at),
        legsCount=legs_count,
        maxQty=campaign.max_qty or campaign.qty_opened or 0,
        pnlRealized=campaign.realized_pnl,
        costBasisMethod=campaign.cost_basis_method,
        source=campaign.source,
    )

    return CampaignDetailResponse(
        campaign=campaign_meta,
        legs=legs_response,
        contextsByLeg=contexts_by_leg,
    )


@router.put("/{campaign_id}/context", response_model=DecisionContextResponse)
async def save_context(
    campaign_id: int,
    request: SaveContextRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update a decision context for a campaign or leg.

    If a context already exists for the given campaign+leg combination,
    it is updated. Otherwise, a new context is created.
    """
    repo = TradingBuddyRepository(db)

    # Verify campaign ownership
    campaign = repo.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    if campaign.account_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    leg_id = int(request.legId) if request.legId else None

    # Build exit_intent as the frontend expects
    exit_intent_value = request.exitIntent

    # Lookup strategy_id from strategyTags (names)
    strategy_id = None
    if request.strategyTags:
        strategy = db.query(Strategy).filter(
            Strategy.name == request.strategyTags[0],
            Strategy.account_id == user_id,
        ).first()
        if strategy:
            strategy_id = strategy.id

    # Check if a context already exists for this campaign + leg
    existing_contexts = repo.get_contexts_for_campaign(campaign_id)
    existing = None
    for ctx in existing_contexts:
        if ctx.leg_id == leg_id:
            existing = ctx
            break
        if leg_id is None and ctx.leg_id is None:
            existing = ctx
            break

    if existing:
        # Update existing context
        existing.context_type = request.contextType
        existing.strategy_id = strategy_id
        existing.hypothesis = request.hypothesis
        existing.exit_intent = exit_intent_value
        existing.feelings_then = request.feelingsThen
        existing.feelings_now = request.feelingsNow
        existing.notes = request.notes
        existing.updated_at = datetime.now(timezone.utc)
        # SQLAlchemy doesn't auto-detect JSONB mutations; flag them explicitly
        flag_modified(existing, "exit_intent")
        flag_modified(existing, "feelings_then")
        flag_modified(existing, "feelings_now")
        db.flush()
        logger.info("Updated decision context id=%s for campaign %s", existing.id, campaign_id)

        # Trigger reviewer checks for this leg
        if leg_id is not None:
            from src.reviewer.publisher import publish_context_updated
            publish_context_updated(leg_id=leg_id, campaign_id=campaign_id, account_id=user_id)

        return _context_to_response(existing)
    else:
        # Create new context
        ctx = repo.create_decision_context(
            account_id=user_id,
            campaign_id=campaign_id,
            leg_id=leg_id,
            context_type=request.contextType,
            strategy_id=strategy_id,
            hypothesis=request.hypothesis,
            exit_intent=exit_intent_value,
            feelings_then=request.feelingsThen,
            feelings_now=request.feelingsNow,
            notes=request.notes,
        )
        logger.info("Created decision context id=%s for campaign %s", ctx.id, campaign_id)

        # Trigger reviewer checks for this leg
        if leg_id is not None:
            from src.reviewer.publisher import publish_context_updated
            publish_context_updated(leg_id=leg_id, campaign_id=campaign_id, account_id=user_id)

        return _context_to_response(ctx)
