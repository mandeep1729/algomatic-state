"""FastAPI router for position campaigns.

Provides endpoints for:
- Fetching campaign details with legs and fill information
- This replaces the mock fetchTradeDetail function in the frontend
"""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
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


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


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
