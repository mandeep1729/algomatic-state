"""FastAPI router for position campaigns.

Provides endpoints for:
- Fetching campaign details with legs and fill information
- Fetching P&L summary aggregated by ticker symbol
- This replaces the mock fetchTradeDetail and fetchTickerPnl functions in the frontend
"""

import logging
from datetime import datetime
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trade_lifecycle_models import (
    PositionCampaign,
    CampaignLeg,
    DecisionContext,
)

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
# Response Models
# -----------------------------------------------------------------------------


class FillSummary(BaseModel):
    """Summary of a fill in a leg."""

    fill_id: int
    allocated_qty: Optional[float] = None


class CampaignLegResponse(BaseModel):
    """Campaign leg response with fill summaries."""

    id: int
    leg_type: str
    side: str
    quantity: float
    avg_price: Optional[float] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    fill_count: int
    notes: Optional[str] = None
    fills: List[FillSummary] = []


class CampaignDetailResponse(BaseModel):
    """Full campaign detail response."""

    id: int
    symbol: str
    direction: str
    status: str
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    holding_period_sec: Optional[int] = None
    qty_opened: Optional[float] = None
    qty_closed: Optional[float] = None
    avg_open_price: Optional[float] = None
    avg_close_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    return_pct: Optional[float] = None
    r_multiple: Optional[float] = None
    legs: List[CampaignLegResponse] = []
    tags: dict = {}
    notes: Optional[str] = None


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


# -----------------------------------------------------------------------------
# Endpoints
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


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    campaign_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full details for a position campaign.

    Returns the campaign with all its legs and fill information.
    Returns 404 if the campaign doesn't exist or isn't owned by the user.
    """
    # Query campaign with eager loading of legs and fill maps
    campaign = (
        db.query(PositionCampaign)
        .options(
            joinedload(PositionCampaign.legs).joinedload(CampaignLeg.fill_maps)
        )
        .filter(
            PositionCampaign.id == campaign_id,
            PositionCampaign.account_id == user_id,
        )
        .first()
    )

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign {campaign_id} not found",
        )

    # Get notes from decision context if available
    notes = None
    context = (
        db.query(DecisionContext)
        .filter(DecisionContext.campaign_id == campaign_id)
        .first()
    )
    if context:
        notes = context.notes

    # Build legs response
    legs_response = []
    for leg in campaign.legs:
        fills = [
            FillSummary(
                fill_id=fm.fill_id,
                allocated_qty=fm.allocated_qty,
            )
            for fm in leg.fill_maps
        ]
        legs_response.append(
            CampaignLegResponse(
                id=leg.id,
                leg_type=leg.leg_type,
                side=leg.side,
                quantity=leg.quantity,
                avg_price=leg.avg_price,
                started_at=leg.started_at,
                ended_at=leg.ended_at,
                fill_count=leg.fill_count,
                notes=leg.notes,
                fills=fills,
            )
        )

    return CampaignDetailResponse(
        id=campaign.id,
        symbol=campaign.symbol,
        direction=campaign.direction,
        status=campaign.status,
        opened_at=campaign.opened_at,
        closed_at=campaign.closed_at,
        holding_period_sec=campaign.holding_period_sec,
        qty_opened=campaign.qty_opened,
        qty_closed=campaign.qty_closed,
        avg_open_price=campaign.avg_open_price,
        avg_close_price=campaign.avg_close_price,
        realized_pnl=campaign.realized_pnl,
        return_pct=campaign.return_pct,
        r_multiple=campaign.r_multiple,
        legs=legs_response,
        tags=campaign.tags,
        notes=notes,
    )
