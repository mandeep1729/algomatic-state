"""FastAPI router for Broker integration via SnapTrade.

Provides endpoints for:
- Connecting brokerage accounts
- Syncing data
- Fetching trade history
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.broker_models import SnapTradeUser, BrokerConnection, TradeFill
from src.data.database.trade_lifecycle_models import LegFillMap, CampaignLeg, DecisionContext
from src.data.database.strategy_models import Strategy
from src.execution.snaptrade_client import SnapTradeClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/broker", tags=["broker"])

# -----------------------------------------------------------------------------
# Dependency
# -----------------------------------------------------------------------------

def get_db():
    """Get database session."""
    with get_db_manager().get_session() as session:
        yield session

def get_snaptrade_client():
    """Get SnapTrade client instance."""
    return SnapTradeClient()


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    redirect_url: Optional[str] = None  # URL to redirect after connection
    broker: Optional[str] = None  # Pre-select broker (e.g., 'ALPACA')
    force: bool = False  # Force reconnect even if already connected

class ConnectResponse(BaseModel):
    redirect_url: str

class ContextSummary(BaseModel):
    """Summary of decision context for a trade fill."""

    strategy: Optional[str] = None
    emotions: Optional[str] = None  # Comma-separated chips
    hypothesis_snippet: Optional[str] = None


class TradeResponse(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    price: float
    fees: float
    executed_at: datetime
    brokerage: str
    context_summary: Optional[ContextSummary] = None

class TradeListAPIResponse(BaseModel):
    trades: List[TradeResponse]
    total: int
    page: int
    limit: int

class SyncResponse(BaseModel):
    status: str
    trades_synced: int

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/connect", response_model=ConnectResponse)
async def connect_broker(
    request: ConnectRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Initiate broker connection.

    Registers user with SnapTrade if needed and returns a connection link.
    Use force=true to reconnect even if already connected.
    """
    logger.debug("connect_broker: user_id=%d, broker=%s, force=%s", user_id, request.broker, request.force)
    if not client.client:
         raise HTTPException(status_code=503, detail="SnapTrade service unavailable")


    # 1. Check if user exists
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    # 2. Register if not exists
    if not snap_user:
        # Generate a unique ID for SnapTrade (e.g., "algomatic_user_{id}")
        snap_user_id = f"algomatic_user_{user_id}"
        logger.debug("Registering new SnapTrade user: %s", snap_user_id)

        registration = client.register_user(snap_user_id)
        if not registration:
             raise HTTPException(status_code=500, detail="Failed to register user with SnapTrade")
        
        snap_user = SnapTradeUser(
            user_account_id=user_id,
            snaptrade_user_id=registration["user_id"],
            snaptrade_user_secret=registration["user_secret"]
        )
        db.add(snap_user)
        db.flush() # Commit handled by context manager on exit, but flush for ID if needed (though we use objects)

    # 3. Generate link
    redirect_url = client.generate_connection_link(
        snap_user.snaptrade_user_id,
        snap_user.snaptrade_user_secret,
        custom_redirect=request.redirect_url,
        broker=request.broker,
    )

    if not redirect_url:
        raise HTTPException(status_code=500, detail="Failed to generate connection link")

    logger.debug("Generated connection link for user_id=%d", user_id)
    return ConnectResponse(redirect_url=redirect_url)


@router.post("/sync", response_model=SyncResponse)
async def sync_data(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Sync trades and accounts from connected brokers."""
    logger.debug("sync_data: user_id=%d", user_id)
    if not client.client:
         raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        raise HTTPException(status_code=404, detail="User not registered with SnapTrade")

    # 1. Update Broker Connections (optional but good for metadata)
    accounts = client.get_accounts(snap_user.snaptrade_user_id, snap_user.snaptrade_user_secret)
    logger.debug("Found %d connected accounts for user_id=%d", len(accounts) if accounts else 0, user_id)
    if accounts:
        for acc in accounts:
            # Extract broker info from account - brokerage_authorization is just an ID string
            auth_id = acc.get("brokerage_authorization")
            if not auth_id or not isinstance(auth_id, str):
                continue

            broker_name = acc.get("institution_name") or acc.get("name") or "Unknown Broker"
            broker_slug = broker_name.lower().replace(" ", "_")

            conn = db.query(BrokerConnection).filter(
                BrokerConnection.authorization_id == auth_id
            ).first()

            if not conn:
                conn = BrokerConnection(
                    snaptrade_user_id=snap_user.id,
                    brokerage_name=broker_name,
                    brokerage_slug=broker_slug,
                    authorization_id=auth_id,
                    meta=acc
                )
                db.add(conn)
            else:
                conn.meta = acc
            db.flush()

            # 2. Sync Trades for this account
            # Use 'get_activities' or similar. 
            # Note: client.get_activities we implemented might list ALL activities.
            pass # We'll do it outside the loop if it fetches all
            
    # Pre-load all user connections for matching
    user_conns = db.query(BrokerConnection).filter(BrokerConnection.snaptrade_user_id == snap_user.id).all()

    # Fetch all activities
    activities = client.get_activities(snap_user.snaptrade_user_id, snap_user.snaptrade_user_secret)
    synced_count = 0

    if activities:
        for activity in activities:
            # Filter for actual trades (BUY, SELL) - skip journals, dividends, etc.
            activity_type = activity.get("type", "").upper()
            if activity_type not in ["BUY", "SELL"]:
                continue

            # Get account ID from activity
            account_data = activity.get("account")
            if isinstance(account_data, dict):
                account_id = account_data.get("id")
            else:
                account_id = None

            # Find connection by matching account_id in meta
            conn = None
            for c in user_conns:
                if c.meta and c.meta.get("id") == account_id:
                    conn = c
                    break

            if not conn and user_conns:
                # Fallback to first connection if can't match
                conn = user_conns[0]

            if not conn:
                logger.warning(f"Could not find connection for account {account_id}")
                continue

            # Check if trade already exists
            trade_id = str(activity.get("id"))
            exists = db.query(TradeFill).filter(TradeFill.external_trade_id == trade_id).first()
            if exists:
                continue

            # Extract symbol - can be None for some activity types
            symbol_data = activity.get("symbol")
            if isinstance(symbol_data, dict):
                symbol = symbol_data.get("symbol", "UNKNOWN")
            elif isinstance(symbol_data, str):
                symbol = symbol_data
            else:
                symbol = "UNKNOWN"

            # Parse trade date
            trade_date_str = activity.get("trade_date") or activity.get("settlement_date")
            if trade_date_str:
                executed_at = datetime.fromisoformat(trade_date_str.replace("Z", "+00:00"))
            else:
                executed_at = datetime.utcnow()

            # Create Trade
            trade = TradeFill(
                broker_connection_id=conn.id,
                symbol=symbol,
                side=activity_type.lower(),
                quantity=float(activity.get("units", 0)),
                price=float(activity.get("price", 0)),
                fees=float(activity.get("fee", 0)),
                executed_at=executed_at,
                external_trade_id=trade_id,
                raw_data=activity
            )
            db.add(trade)
            synced_count += 1

    logger.debug("Sync complete for user_id=%d: %d trades synced", user_id, synced_count)
    return SyncResponse(status="success", trades_synced=synced_count)


@router.get("/trades", response_model=TradeListAPIResponse)
async def get_trades(
    user_id: int = Depends(get_current_user),
    symbol: Optional[str] = None,
    uncategorized: bool = False,
    sort: str = "-executed_at",
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get trade history, optionally filtered by symbol, with pagination.

    Args:
        symbol: Filter by ticker symbol
        uncategorized: If True, only return fills not yet processed into campaigns
        sort: Sort field (prefix with - for descending)
        page: Page number (1-indexed)
        limit: Items per page
    """
    logger.debug(
        "get_trades: user_id=%d, symbol=%s, uncategorized=%s, page=%d, limit=%d",
        user_id, symbol, uncategorized, page, limit
    )
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        return TradeListAPIResponse(trades=[], total=0, page=page, limit=limit)

    # Join tables
    query = db.query(TradeFill).join(BrokerConnection).filter(
        BrokerConnection.snaptrade_user_id == snap_user.id
    )

    if symbol:
        query = query.filter(TradeFill.symbol == symbol)

    # Filter for uncategorized fills (fills without a strategy assigned)
    # A fill is "uncategorized" if it lacks a strategy assignment in its DecisionContext
    if uncategorized:
        from sqlalchemy import select

        # Subquery: fills that have a strategy assigned via LegFillMap -> CampaignLeg -> DecisionContext
        categorized_fill_subq = (
            select(LegFillMap.fill_id)
            .select_from(LegFillMap)
            .join(CampaignLeg, CampaignLeg.id == LegFillMap.leg_id)
            .join(DecisionContext, DecisionContext.leg_id == CampaignLeg.id)
            .where(DecisionContext.strategy_id.isnot(None))
            .scalar_subquery()
        )

        # Only include fills that are NOT categorized (no strategy assigned)
        query = query.filter(TradeFill.id.notin_(categorized_fill_subq))

    total = query.count()

    # Sorting
    desc_sort = sort.startswith("-")
    sort_field = sort.lstrip("-")
    column = getattr(TradeFill, sort_field, TradeFill.executed_at)
    query = query.order_by(column.desc() if desc_sort else column.asc())

    # Pagination
    offset = (max(page, 1) - 1) * limit
    trades = query.offset(offset).limit(limit).all()

    # Fetch context summaries for all trade fills in a single query
    # Path: TradeFill -> LegFillMap -> CampaignLeg -> DecisionContext
    trade_ids = [t.id for t in trades]
    context_map: Dict[int, ContextSummary] = {}

    if trade_ids:
        # Query to get context info for each fill
        # A fill can be linked to multiple legs, take the first match
        context_results = (
            db.query(
                LegFillMap.fill_id,
                DecisionContext.hypothesis,
                DecisionContext.feelings_then,
                Strategy.name.label("strategy_name"),
            )
            .select_from(LegFillMap)
            .join(CampaignLeg, CampaignLeg.id == LegFillMap.leg_id)
            .join(DecisionContext, DecisionContext.leg_id == CampaignLeg.id)
            .outerjoin(Strategy, Strategy.id == DecisionContext.strategy_id)
            .filter(LegFillMap.fill_id.in_(trade_ids))
            .all()
        )

        for fill_id, hypothesis, feelings_then, strategy_name in context_results:
            if fill_id in context_map:
                continue  # Already processed, take the first match

            # Build context summary
            emotions: Optional[str] = None
            if feelings_then and isinstance(feelings_then, dict):
                chips = feelings_then.get("chips", [])
                if chips:
                    emotions = ", ".join(chips[:3])  # Limit to 3 chips

            hypothesis_snippet: Optional[str] = None
            if hypothesis:
                snippet = hypothesis[:50]
                if len(hypothesis) > 50:
                    snippet += "..."
                hypothesis_snippet = snippet

            context_map[fill_id] = ContextSummary(
                strategy=strategy_name,
                emotions=emotions,
                hypothesis_snippet=hypothesis_snippet,
            )

    return TradeListAPIResponse(
        trades=[
            TradeResponse(
                id=t.id,
                symbol=t.symbol,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                fees=t.fees,
                executed_at=t.executed_at,
                brokerage=t.connection.brokerage_name,
                context_summary=context_map.get(t.id),
            )
            for t in trades
        ],
        total=total,
        page=page,
        limit=limit,
    )


class ConnectionStatusResponse(BaseModel):
    connected: bool
    brokerages: List[str] = []


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Check if user has any connected brokerages."""
    logger.debug("get_connection_status: user_id=%d", user_id)
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        return ConnectionStatusResponse(connected=False, brokerages=[])

    # Check with SnapTrade for connected accounts
    if client.client:
        accounts = client.get_accounts(
            snap_user.snaptrade_user_id,
            snap_user.snaptrade_user_secret
        )
        if accounts:
            brokerages = []
            for acc in accounts:
                try:
                    if isinstance(acc, dict):
                        # Use institution_name or name field
                        name = acc.get("institution_name") or acc.get("name") or "Unknown"
                        brokerages.append(name)
                except Exception as e:
                    logger.warning(f"Error parsing account: {e}")
                    continue
            return ConnectionStatusResponse(connected=len(brokerages) > 0, brokerages=list(set(brokerages)))

    return ConnectionStatusResponse(connected=False, brokerages=[])


@router.get("/callback")
async def broker_callback(
    status: str = "success",
    db: Session = Depends(get_db),
):
    """Handle callback from SnapTrade after broker connection.

    This endpoint is called when the user completes (or cancels) the broker connection.
    The frontend should poll /status to check connection state.
    """
    return {
        "status": status,
        "message": "Connection process completed. Check /api/broker/status for connection state."
    }


# -----------------------------------------------------------------------------
# Fill Context Endpoints
# -----------------------------------------------------------------------------

class FillContextDetail(BaseModel):
    """Full decision context for a trade fill."""

    fill_id: int
    campaign_id: Optional[int] = None
    leg_id: Optional[int] = None
    context_id: Optional[int] = None
    context_type: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_name: Optional[str] = None
    hypothesis: Optional[str] = None
    exit_intent: Optional[str] = None
    feelings_then: Optional[Dict[str, Any]] = None
    feelings_now: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None


class SaveFillContextRequest(BaseModel):
    """Request body for saving a decision context for a fill."""

    strategy_id: Optional[int] = None
    hypothesis: Optional[str] = None
    exit_intent: Optional[str] = None
    feelings_then: Optional[Dict[str, Any]] = None
    feelings_now: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


@router.get("/fills/{fill_id}/context", response_model=FillContextDetail)
async def get_fill_context(
    fill_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the full decision context for a specific trade fill.

    Returns context details including campaign/leg IDs needed for editing.
    If the fill is not linked to a campaign, returns null values for context fields.
    """
    logger.debug("get_fill_context: fill_id=%d, user_id=%d", fill_id, user_id)

    # Verify fill belongs to user
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        raise HTTPException(status_code=404, detail="User not found")

    fill = db.query(TradeFill).join(BrokerConnection).filter(
        TradeFill.id == fill_id,
        BrokerConnection.snaptrade_user_id == snap_user.id
    ).first()

    if not fill:
        raise HTTPException(status_code=404, detail=f"Fill {fill_id} not found")

    # Get the leg mapping and context
    # Path: TradeFill -> LegFillMap -> CampaignLeg -> DecisionContext
    result = (
        db.query(
            LegFillMap.fill_id,
            CampaignLeg.id.label("leg_id"),
            CampaignLeg.campaign_id,
            CampaignLeg.leg_type,
            DecisionContext.id.label("context_id"),
            DecisionContext.context_type,
            DecisionContext.strategy_id,
            Strategy.name.label("strategy_name"),
            DecisionContext.hypothesis,
            DecisionContext.exit_intent,
            DecisionContext.feelings_then,
            DecisionContext.feelings_now,
            DecisionContext.notes,
            DecisionContext.updated_at,
        )
        .select_from(LegFillMap)
        .join(CampaignLeg, CampaignLeg.id == LegFillMap.leg_id)
        .outerjoin(DecisionContext, DecisionContext.leg_id == CampaignLeg.id)
        .outerjoin(Strategy, Strategy.id == DecisionContext.strategy_id)
        .filter(LegFillMap.fill_id == fill_id)
        .first()
    )

    if not result:
        # Fill is not linked to a campaign/leg
        return FillContextDetail(fill_id=fill_id)

    # Extract exit_intent string from JSONB if present
    exit_intent_str: Optional[str] = None
    if result.exit_intent:
        if isinstance(result.exit_intent, dict):
            exit_intent_str = result.exit_intent.get("type")
        elif isinstance(result.exit_intent, str):
            exit_intent_str = result.exit_intent

    return FillContextDetail(
        fill_id=fill_id,
        campaign_id=result.campaign_id,
        leg_id=result.leg_id,
        context_id=result.context_id,
        context_type=result.context_type or result.leg_type,
        strategy_id=result.strategy_id,
        strategy_name=result.strategy_name,
        hypothesis=result.hypothesis,
        exit_intent=exit_intent_str,
        feelings_then=result.feelings_then,
        feelings_now=result.feelings_now,
        notes=result.notes,
        updated_at=result.updated_at,
    )


@router.put("/fills/{fill_id}/context", response_model=FillContextDetail)
async def save_fill_context(
    fill_id: int,
    request: SaveFillContextRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update the decision context for a trade fill.

    The fill must be linked to a campaign/leg. If no context exists for
    the leg, a new one is created. Otherwise, the existing context is updated.
    """
    logger.debug("save_fill_context: fill_id=%d, user_id=%d", fill_id, user_id)

    # Verify fill belongs to user
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        raise HTTPException(status_code=404, detail="User not found")

    fill = db.query(TradeFill).join(BrokerConnection).filter(
        TradeFill.id == fill_id,
        BrokerConnection.snaptrade_user_id == snap_user.id
    ).first()

    if not fill:
        raise HTTPException(status_code=404, detail=f"Fill {fill_id} not found")

    # Get the leg mapping
    leg_map = (
        db.query(LegFillMap, CampaignLeg)
        .join(CampaignLeg, CampaignLeg.id == LegFillMap.leg_id)
        .filter(LegFillMap.fill_id == fill_id)
        .first()
    )

    if not leg_map:
        raise HTTPException(
            status_code=400,
            detail="Fill is not linked to a campaign. Cannot save context."
        )

    _, leg = leg_map
    campaign_id = leg.campaign_id

    # Check if a context already exists for this leg
    existing_context = db.query(DecisionContext).filter(
        DecisionContext.leg_id == leg.id
    ).first()

    # Build exit_intent value
    exit_intent_value: Optional[str] = request.exit_intent

    if existing_context:
        # Update existing context
        if request.strategy_id is not None:
            existing_context.strategy_id = request.strategy_id
        existing_context.hypothesis = request.hypothesis
        existing_context.exit_intent = exit_intent_value
        existing_context.feelings_then = request.feelings_then
        existing_context.feelings_now = request.feelings_now
        existing_context.notes = request.notes
        existing_context.updated_at = datetime.utcnow()
        db.flush()

        context = existing_context
        logger.info(
            "Updated fill context: fill_id=%d, context_id=%d",
            fill_id, context.id
        )
    else:
        # Create new context
        # Determine context_type from leg type
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
            campaign_id=campaign_id,
            leg_id=leg.id,
            context_type=context_type,
            strategy_id=request.strategy_id,
            hypothesis=request.hypothesis,
            exit_intent=exit_intent_value,
            feelings_then=request.feelings_then,
            feelings_now=request.feelings_now,
            notes=request.notes,
        )
        db.add(context)
        db.flush()

        logger.info(
            "Created fill context: fill_id=%d, context_id=%d",
            fill_id, context.id
        )

    # Get strategy name for response
    strategy_name: Optional[str] = None
    if context.strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == context.strategy_id).first()
        if strategy:
            strategy_name = strategy.name

    return FillContextDetail(
        fill_id=fill_id,
        campaign_id=campaign_id,
        leg_id=leg.id,
        context_id=context.id,
        context_type=context.context_type,
        strategy_id=context.strategy_id,
        strategy_name=strategy_name,
        hypothesis=context.hypothesis,
        exit_intent=exit_intent_value,
        feelings_then=context.feelings_then,
        feelings_now=context.feelings_now,
        notes=context.notes,
        updated_at=context.updated_at,
    )

