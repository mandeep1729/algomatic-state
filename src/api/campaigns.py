"""FastAPI router for Position Campaign endpoints.

Provides endpoints for:
- Listing campaigns (summaries)
- Getting campaign detail (with legs, evaluations, contexts)
- Saving/updating decision contexts
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.trading_repository import TradingBuddyRepository

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
    overallLabel: str
    keyFlags: List[str]


class CampaignLegResponse(BaseModel):
    """A single leg within a campaign."""
    legId: str
    campaignId: str
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
# Helpers
# -----------------------------------------------------------------------------

def _format_dt(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime to ISO 8601 string with Z suffix."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _campaign_to_summary(campaign) -> CampaignSummaryResponse:
    """Convert a PositionCampaign ORM model to a summary response."""
    legs_count = len(campaign.legs) if campaign.legs else 0
    # Extract key flags from campaign tags
    tags_dict = campaign.tags or {}
    key_flags = tags_dict.get("key_flags", [])

    # Determine overall label from tags (default to 'mixed' if not set)
    overall_label = tags_dict.get("overall_label", "mixed")

    return CampaignSummaryResponse(
        campaignId=str(campaign.id),
        symbol=campaign.symbol,
        direction=campaign.direction,
        status=campaign.status,
        openedAt=_format_dt(campaign.opened_at),
        closedAt=_format_dt(campaign.closed_at),
        legsCount=legs_count,
        maxQty=campaign.max_qty or campaign.qty_opened or 0,
        overallLabel=overall_label,
        keyFlags=key_flags,
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

    return DecisionContextResponse(
        contextId=str(ctx.id),
        scope="leg" if ctx.leg_id else "campaign",
        campaignId=str(ctx.campaign_id) if ctx.campaign_id else None,
        legId=str(ctx.leg_id) if ctx.leg_id else None,
        contextType=ctx.context_type,
        strategyTags=ctx.strategy_tags or [],
        hypothesis=ctx.hypothesis,
        exitIntent=exit_intent if isinstance(exit_intent, str) else None,
        feelingsThen=ctx.feelings_then,
        feelingsNow=ctx.feelings_now,
        notes=ctx.notes,
        updatedAt=_format_dt(ctx.updated_at),
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

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
        existing.strategy_tags = request.strategyTags
        existing.hypothesis = request.hypothesis
        existing.exit_intent = exit_intent_value
        existing.feelings_then = request.feelingsThen
        existing.feelings_now = request.feelingsNow
        existing.notes = request.notes
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info("Updated decision context id=%s for campaign %s", existing.id, campaign_id)
        return _context_to_response(existing)
    else:
        # Create new context
        ctx = repo.create_decision_context(
            account_id=user_id,
            campaign_id=campaign_id,
            leg_id=leg_id,
            context_type=request.contextType,
            strategy_tags=request.strategyTags,
            hypothesis=request.hypothesis,
            exit_intent=exit_intent_value,
            feelings_then=request.feelingsThen,
            feelings_now=request.feelingsNow,
            notes=request.notes,
        )
        logger.info("Created decision context id=%s for campaign %s", ctx.id, campaign_id)
        return _context_to_response(ctx)
