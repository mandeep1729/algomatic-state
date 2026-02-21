"""FastAPI router for position campaigns.

Provides endpoints for:
- Listing campaigns (summaries with computed aggregates)
- Fetching campaign details with fills mapped to "legs" for UI
- Fetching P&L summary aggregated by ticker
- Fetching P&L timeseries for charting
- Saving/updating decision contexts on fills
- Rebuilding campaigns
- Stub endpoints for removed features (uncategorized-count, orphaned-legs)
"""

import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_broker_repo, get_db
from src.data.database.broker_repository import BrokerRepository
from src.data.database.trading_repository import TradingBuddyRepository
from src.data.database.broker_models import TradeFill
from src.data.database.trade_lifecycle_models import DecisionContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


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
# Response Models - Campaign List (matches frontend CampaignSummary)
# -----------------------------------------------------------------------------

class CampaignSummaryResponse(BaseModel):
    """Summary of a campaign for the list view.

    Field names match the frontend CampaignSummary TypeScript type.
    Each fill in the campaign is treated as a "leg" for UI purposes.
    """
    campaignId: str
    symbol: str
    direction: str
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    legsCount: int
    maxQty: float
    legQuantities: List[float] = []
    overallLabel: str = "mixed"
    keyFlags: List[str] = []
    strategies: List[str] = []
    orderIds: List[str] = []
    pnlRealized: Optional[float] = None


# -----------------------------------------------------------------------------
# Response Models - Campaign Detail (matches frontend CampaignDetail)
# -----------------------------------------------------------------------------

class LegResponse(BaseModel):
    """A fill mapped to the frontend CampaignLeg type."""
    legId: str
    campaignId: Optional[str] = None
    legType: str
    side: str
    quantity: float
    avgPrice: float
    startedAt: str
    endedAt: str
    symbol: Optional[str] = None
    direction: Optional[str] = None
    orderIds: Optional[List[str]] = None
    strategyName: Optional[str] = None


class CampaignMetadataResponse(BaseModel):
    """Campaign metadata matching the frontend Campaign type."""
    campaignId: str
    symbol: str
    direction: str
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    legsCount: int
    maxQty: float
    pnlRealized: Optional[float] = None
    costBasisMethod: str = "fifo"
    source: str = "broker_synced"


class CheckResponse(BaseModel):
    """Campaign check matching the frontend CampaignCheck type."""
    checkId: str
    legId: str
    checkType: str
    code: str
    severity: str
    passed: bool
    nudgeText: Optional[str] = None
    details: Optional[dict] = None
    checkPhase: str
    checkedAt: Optional[str] = None
    acknowledged: Optional[bool] = None
    traderAction: Optional[str] = None


class ContextResponse(BaseModel):
    """Decision context matching the frontend DecisionContext type."""
    contextId: str
    scope: str = "leg"
    campaignId: Optional[str] = None
    legId: Optional[str] = None
    contextType: str
    strategyTags: List[str] = []
    hypothesis: Optional[str] = None
    exitIntent: Optional[str] = None
    feelingsThen: Optional[dict] = None
    feelingsNow: Optional[dict] = None
    notes: Optional[str] = None
    updatedAt: str


class CampaignDetailResponse(BaseModel):
    """Full campaign detail matching the frontend CampaignDetail type.

    Returns nested structure: campaign metadata + legs (fills as legs) +
    contexts/checks grouped by legId (fillId).
    """
    campaign: CampaignMetadataResponse
    legs: List[LegResponse]
    contextsByLeg: dict = {}
    checksByLeg: dict = {}


# -----------------------------------------------------------------------------
# Response Models - Fill Context
# -----------------------------------------------------------------------------

class SaveFillContextRequest(BaseModel):
    """Request body for saving a decision context on a fill."""
    contextType: str
    strategyName: Optional[str] = None
    hypothesis: Optional[str] = None
    exitIntent: Optional[str] = None
    feelingsThen: Optional[dict] = None
    feelingsNow: Optional[dict] = None
    notes: Optional[str] = None


class DecisionContextApiResponse(BaseModel):
    """Decision context response for fill-level context endpoints."""
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
    """P&L summary for a single ticker symbol.

    Field names match the frontend TickerPnlSummary type.
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
    fill_count: int


class PnlTimeseriesResponse(BaseModel):
    """P&L timeseries response for charting."""
    symbol: Optional[str] = None
    points: List[PnlTimeseriesPoint]
    total_pnl: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _compute_campaign_aggregates(fills: list[TradeFill]) -> dict:
    """Compute aggregates from a list of fills for a campaign.

    Returns dict with: direction, status, opened_at, closed_at,
    net_quantity, max_qty, leg_quantities, realized_pnl, order_ids,
    strategies.
    """
    if not fills:
        return {
            "direction": "flat",
            "status": "closed",
            "opened_at": None,
            "closed_at": None,
            "net_quantity": 0.0,
            "max_qty": 0.0,
            "leg_quantities": [],
            "realized_pnl": 0.0,
            "order_ids": [],
            "strategies": [],
        }

    net_qty = 0.0
    max_qty = 0.0
    total_bought_qty = 0.0
    total_sold_qty = 0.0
    total_bought_cost = 0.0
    total_sold_proceeds = 0.0
    order_ids: list[str] = []
    seen_order_ids: set = set()
    leg_quantities: list[float] = []

    for fill in fills:
        if fill.side.lower() == "buy":
            total_bought_qty += fill.quantity
            total_bought_cost += fill.quantity * fill.price
            net_qty += fill.quantity
            leg_quantities.append(fill.quantity)
        else:
            total_sold_qty += fill.quantity
            total_sold_proceeds += fill.quantity * fill.price
            net_qty -= fill.quantity
            leg_quantities.append(-fill.quantity)

        max_qty = max(max_qty, abs(net_qty))

        if fill.order_id and fill.order_id not in seen_order_ids:
            seen_order_ids.add(fill.order_id)
            order_ids.append(fill.order_id)

    # Direction based on first fill
    direction = "long" if fills[0].side.lower() == "buy" else "short"

    # Status based on net quantity
    status = "closed" if abs(net_qty) < 1e-9 else "open"

    # Realized P&L: matched quantity x (sell_avg - buy_avg)
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
        "max_qty": max_qty,
        "leg_quantities": leg_quantities,
        "realized_pnl": realized_pnl,
        "order_ids": order_ids,
    }


def _derive_leg_type(
    fill: TradeFill,
    fill_index: int,
    net_qty_after: float,
    net_qty_before: float,
) -> str:
    """Derive legType from position state (always correct for campaign display).

    Uses net position before/after the fill to determine:
    - open: first fill in the campaign
    - add: position size increases (abs grows)
    - reduce: position size decreases (abs shrinks)
    - close: position goes to zero
    """
    if fill_index == 0:
        return "open"

    if abs(net_qty_after) < 1e-9:
        return "close"

    if abs(net_qty_after) > abs(net_qty_before):
        return "add"

    return "reduce"


def _batch_load_fill_data(
    fills: list[TradeFill],
    repo: TradingBuddyRepository,
) -> tuple[dict, dict]:
    """Batch-load decision contexts and strategies for a list of fills.

    Returns:
        Tuple of (contexts_by_fill_id, strategies_by_id)
    """
    fill_ids = [f.id for f in fills]
    contexts_map = repo.get_decision_contexts_for_fills(fill_ids)

    strategy_ids = list({
        dc.strategy_id for dc in contexts_map.values()
        if dc.strategy_id is not None
    })
    strategies_map = repo.get_strategies_by_ids(strategy_ids)

    return contexts_map, strategies_map


def _get_campaign_strategies(
    fills: list[TradeFill],
    contexts_map: dict,
    strategies_map: dict,
) -> list[str]:
    """Get unique strategy names from pre-loaded data (no DB queries)."""
    strategies: list[str] = []
    seen: set = set()
    for fill in fills:
        ctx = contexts_map.get(fill.id)
        if ctx and ctx.strategy_id:
            strategy = strategies_map.get(ctx.strategy_id)
            if strategy and strategy.name not in seen:
                seen.add(strategy.name)
                strategies.append(strategy.name)
    return strategies


def _fill_to_leg_response(
    fill: TradeFill,
    group_id: int,
    direction: str,
    leg_type: str,
    contexts_map: dict,
    strategies_map: dict,
) -> LegResponse:
    """Convert a TradeFill to LegResponse using pre-loaded data."""
    strategy_name = None
    ctx = contexts_map.get(fill.id)
    if ctx and ctx.strategy_id:
        strategy = strategies_map.get(ctx.strategy_id)
        if strategy:
            strategy_name = strategy.name

    order_ids = [fill.order_id] if fill.order_id else []

    return LegResponse(
        legId=str(fill.id),
        campaignId=str(group_id),
        legType=leg_type,
        side=fill.side,
        quantity=fill.quantity,
        avgPrice=fill.price,
        startedAt=_format_dt(fill.executed_at),
        endedAt=_format_dt(fill.executed_at),
        symbol=fill.symbol,
        direction=direction,
        orderIds=order_ids,
        strategyName=strategy_name,
    )


def _build_contexts_by_leg(
    fills: list[TradeFill],
    group_id: int,
    contexts_map: dict,
    strategies_map: dict,
) -> dict:
    """Build contextsByLeg dict using pre-loaded data (no DB queries)."""
    result = {}
    for fill in fills:
        ctx = contexts_map.get(fill.id)
        if not ctx:
            continue

        strategy_name = None
        if ctx.strategy_id:
            strategy = strategies_map.get(ctx.strategy_id)
            if strategy:
                strategy_name = strategy.name

        exit_intent = ctx.exit_intent
        if isinstance(exit_intent, dict):
            exit_intent = exit_intent.get("type", "unknown")

        result[str(fill.id)] = ContextResponse(
            contextId=str(ctx.id),
            scope="leg",
            campaignId=str(group_id),
            legId=str(fill.id),
            contextType=ctx.context_type,
            strategyTags=[strategy_name] if strategy_name else [],
            hypothesis=ctx.hypothesis,
            exitIntent=exit_intent if isinstance(exit_intent, str) else None,
            feelingsThen=ctx.feelings_then,
            feelingsNow=ctx.feelings_now,
            notes=ctx.notes,
            updatedAt=_format_dt(ctx.updated_at),
        ).model_dump()

    # Derive a synthetic "campaign" key from the most recently updated leg.
    # Campaign-level saves write identical values to all legs, so the latest
    # leg context is representative of the campaign-level state.
    if result:
        latest_key = max(result, key=lambda k: result[k].get("updatedAt", ""))
        latest = result[latest_key]
        result["campaign"] = {
            **latest,
            "scope": "campaign",
            "legId": None,
            "contextType": "post_trade_reflection",
        }

    return result


def _build_checks_by_leg(
    fills: list[TradeFill],
    contexts_map: dict,
    repo: TradingBuddyRepository,
) -> dict:
    """Build checksByLeg dict using batch-loaded checks."""
    context_ids = [
        contexts_map[f.id].id
        for f in fills
        if f.id in contexts_map
    ]
    checks_map = repo.get_checks_for_contexts(context_ids)

    result = {}
    for fill in fills:
        ctx = contexts_map.get(fill.id)
        if not ctx:
            continue

        checks = checks_map.get(ctx.id, [])
        if checks:
            result[str(fill.id)] = [
                CheckResponse(
                    checkId=str(check.id),
                    legId=str(fill.id),
                    checkType=check.check_type,
                    code=check.check_name,
                    severity=check.severity,
                    passed=check.passed,
                    nudgeText=check.nudge_text,
                    details=check.details,
                    checkPhase=check.check_phase,
                    checkedAt=_format_dt(check.checked_at),
                    acknowledged=check.acknowledged,
                    traderAction=check.trader_action,
                ).model_dump()
                for check in checks
            ]
    return result


def _context_to_api_response(ctx: DecisionContext, broker_repo: BrokerRepository) -> DecisionContextApiResponse:
    """Convert a DecisionContext to API response."""
    strategy_name = None
    if ctx.strategy_id:
        strategy = broker_repo.get_strategy_by_id(ctx.strategy_id)
        if strategy:
            strategy_name = strategy.name

    exit_intent = ctx.exit_intent
    if isinstance(exit_intent, dict):
        exit_intent = exit_intent.get("type", "unknown")

    return DecisionContextApiResponse(
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
# Stub Endpoints (features removed during restructuring)
# These return empty results so the frontend doesn't crash on 404.
# -----------------------------------------------------------------------------

@router.get("/uncategorized-count")
async def get_uncategorized_count(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Return count of fills not yet assigned to a campaign group.

    After a rebuild, all fills should be grouped, so this typically returns 0.
    """
    repo = TradingBuddyRepository(db)
    total_fills = broker_repo.count_fills(user_id)
    grouped_fills = repo.count_grouped_fills(user_id)
    count = max(0, total_fills - grouped_fills)

    logger.debug("Uncategorized fills for user_id=%d: %d", user_id, count)
    return {"count": count}


@router.get("/orphaned-legs")
async def get_orphaned_legs(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return orphaned legs (fills without a campaign group).

    In the current schema, orphaned legs are not tracked separately.
    Returns empty list.
    """
    return []


# -----------------------------------------------------------------------------
# P&L Endpoints (computed from fills)
# -----------------------------------------------------------------------------

@router.get("/pnl/by-ticker", response_model=TickerPnlListResponse)
async def get_pnl_by_ticker(
    limit: int = Query(50, ge=1, le=200, description="Maximum tickers to return"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get P&L summary aggregated by ticker symbol."""
    logger.debug("Fetching P&L by ticker for user_id=%d, limit=%d", user_id, limit)

    symbols = broker_repo.get_distinct_symbols(user_id)

    tickers = []
    repo = TradingBuddyRepository(db)

    for symbol in symbols:
        fills = broker_repo.get_fills(user_id, symbol=symbol, order_desc=False)

        if not fills:
            continue

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

        campaign_count = repo.count_campaign_groups(user_id, symbol=symbol)
        closed_count = repo.count_closed_campaign_groups(user_id, symbol=symbol)

        tickers.append(TickerPnlResponse(
            symbol=symbol,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            trade_count=campaign_count,
            closed_count=closed_count,
            first_entry_time=fills[0].executed_at,
        ))

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
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get P&L timeseries for charting."""
    logger.debug(
        "Fetching P&L timeseries: user_id=%d, symbol=%s, start=%s, end=%s, granularity=%s",
        user_id, symbol, start_date, end_date, granularity,
    )

    results = broker_repo.get_pnl_timeseries(
        account_id=user_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )

    logger.debug("Found %d periods with fill data", len(results))

    points = []
    cumulative = 0.0
    for row in results:
        period_pnl = round(row["sell_proceeds"] - row["buy_cost"] - row["fees"], 2)
        cumulative += period_pnl

        period_ts = row["period"]
        if isinstance(period_ts, date) and not isinstance(period_ts, datetime):
            period_ts = datetime.combine(period_ts, datetime.min.time())

        points.append(PnlTimeseriesPoint(
            timestamp=period_ts,
            realized_pnl=period_pnl,
            cumulative_pnl=round(cumulative, 2),
            fill_count=row["fill_count"],
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
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get P&L summary for a single ticker symbol."""
    logger.debug("Fetching P&L for symbol=%s, user_id=%d", symbol, user_id)

    fills = broker_repo.get_fills(user_id, symbol=symbol.upper(), order_desc=False)

    if not fills:
        return TickerPnlResponse(
            symbol=symbol.upper(),
            total_pnl=0.0,
            total_pnl_pct=0.0,
            trade_count=0,
            closed_count=0,
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
    closed_count = repo.count_closed_campaign_groups(user_id, symbol=symbol.upper())

    return TickerPnlResponse(
        symbol=symbol.upper(),
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        trade_count=campaign_count,
        closed_count=closed_count,
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
    """List campaigns for the authenticated user."""
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
        contexts_map, strategies_map = _batch_load_fill_data(fills, repo)
        strategies = _get_campaign_strategies(fills, contexts_map, strategies_map)

        result.append(CampaignSummaryResponse(
            campaignId=str(group_id),
            symbol=fills[0].symbol if fills else "",
            direction=agg["direction"],
            status=agg["status"],
            openedAt=_format_dt(agg["opened_at"]),
            closedAt=_format_dt(agg["closed_at"]),
            legsCount=len(fills),
            maxQty=agg["max_qty"],
            legQuantities=agg["leg_quantities"],
            overallLabel="mixed",
            keyFlags=[],
            strategies=strategies,
            orderIds=agg["order_ids"],
            pnlRealized=agg["realized_pnl"],
        ))

    logger.debug("Returning %d campaigns for user_id=%d", len(result), user_id)
    return result


@router.get("/{group_id}", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    group_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full campaign detail with fills mapped to legs."""
    logger.debug("get_campaign_detail: group_id=%d, user_id=%d", group_id, user_id)

    repo = TradingBuddyRepository(db)

    if not repo.campaign_group_exists(group_id, user_id):
        raise HTTPException(status_code=404, detail=f"Campaign {group_id} not found")

    fills = repo.get_campaign_fills(group_id)
    agg = _compute_campaign_aggregates(fills)
    contexts_map, strategies_map = _batch_load_fill_data(fills, repo)

    # Build legs from fills
    legs = []
    net_qty = 0.0
    for idx, fill in enumerate(fills):
        net_qty_before = net_qty
        if fill.side.lower() == "buy":
            net_qty += fill.quantity
        else:
            net_qty -= fill.quantity

        leg_type = _derive_leg_type(fill, idx, net_qty, net_qty_before)
        leg = _fill_to_leg_response(
            fill, group_id, agg["direction"], leg_type,
            contexts_map, strategies_map,
        )
        legs.append(leg)

    # Build campaign metadata
    campaign_meta = CampaignMetadataResponse(
        campaignId=str(group_id),
        symbol=fills[0].symbol if fills else "",
        direction=agg["direction"],
        status=agg["status"],
        openedAt=_format_dt(agg["opened_at"]),
        closedAt=_format_dt(agg["closed_at"]),
        legsCount=len(fills),
        maxQty=agg["max_qty"],
        pnlRealized=agg["realized_pnl"],
        costBasisMethod="fifo",
        source="broker_synced",
    )

    # Build contexts and checks grouped by legId (fillId)
    contexts_by_leg = _build_contexts_by_leg(fills, group_id, contexts_map, strategies_map)
    checks_by_leg = _build_checks_by_leg(fills, contexts_map, repo)

    return CampaignDetailResponse(
        campaign=campaign_meta,
        legs=legs,
        contextsByLeg=contexts_by_leg,
        checksByLeg=checks_by_leg,
    )


# -----------------------------------------------------------------------------
# Fill Context Endpoints (atomic unit: fill)
# -----------------------------------------------------------------------------

@router.get("/fills/{fill_id}/context", response_model=DecisionContextApiResponse)
async def get_fill_context(
    fill_id: int,
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get the decision context for a specific fill."""
    fill = broker_repo.get_fill(fill_id, account_id=user_id)
    if not fill:
        raise HTTPException(status_code=404, detail="Fill not found")

    ctx = broker_repo.get_decision_context(fill_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="No context for this fill")

    return _context_to_api_response(ctx, broker_repo)


@router.put("/fills/{fill_id}/context", response_model=DecisionContextApiResponse)
async def save_fill_context(
    fill_id: int,
    request: SaveFillContextRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Save or update a decision context for a fill.

    If strategy changes, triggers campaign rebuild for affected groups.
    """
    fill = broker_repo.get_fill(fill_id, account_id=user_id)
    if not fill:
        raise HTTPException(status_code=404, detail="Fill not found")

    repo = TradingBuddyRepository(db)

    # Resolve strategy name to ID
    strategy_id = None
    if request.strategyName:
        strategy = broker_repo.get_strategy_by_name(request.strategyName, user_id)
        if strategy:
            strategy_id = strategy.id

    exit_intent_value = request.exitIntent

    # Get or create context
    ctx = broker_repo.get_decision_context(fill_id)
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
    return _context_to_api_response(ctx, broker_repo)


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
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Rebuild campaigns from fills using zero-crossing algorithm."""
    logger.info("rebuild_campaigns: user_id=%d, symbol=%s", user_id, symbol)

    repo = TradingBuddyRepository(db)

    if symbol:
        strategy_ids = broker_repo.get_distinct_strategy_ids(user_id, symbol)

        total_stats = {"campaigns_created": 0, "fills_grouped": 0, "groups_rebuilt": 0}
        for sid in strategy_ids:
            group_stats = repo.rebuild_campaigns(user_id, symbol.upper(), sid)
            total_stats["campaigns_created"] += group_stats["campaigns_created"]
            total_stats["fills_grouped"] += group_stats["fills_grouped"]
            total_stats["groups_rebuilt"] += 1
    else:
        total_stats = repo.rebuild_all_campaigns(user_id)

    db.commit()

    logger.info("Rebuild complete for user_id=%d: %s", user_id, total_stats)
    return RebuildCampaignsResponse(**total_stats)
