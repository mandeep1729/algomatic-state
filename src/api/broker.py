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

    # Filter for uncategorized fills (not processed into lots/campaigns)
    if uncategorized:
        from src.data.database.trade_lifecycle_models import PositionLot, LotClosure

        # Get fills used as opening fills in lots
        open_fill_subq = db.query(PositionLot.open_fill_id).filter(
            PositionLot.account_id == user_id
        ).subquery()

        # Get fills used as closing fills in closures
        close_fill_subq = db.query(LotClosure.close_fill_id).join(
            PositionLot, PositionLot.id == LotClosure.lot_id
        ).filter(
            PositionLot.account_id == user_id
        ).subquery()

        # Exclude processed fills
        query = query.filter(
            TradeFill.id.notin_(open_fill_subq),
            TradeFill.id.notin_(close_fill_subq),
        )

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

