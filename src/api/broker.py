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
from src.data.database.broker_models import SnapTradeUser, BrokerConnection, TradeHistory
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

class TradeResponse(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    price: float
    fees: float
    executed_at: datetime
    brokerage: str

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

    return ConnectResponse(redirect_url=redirect_url)


@router.post("/sync", response_model=SyncResponse)
async def sync_data(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Sync trades and accounts from connected brokers."""
    if not client.client:
         raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        raise HTTPException(status_code=404, detail="User not registered with SnapTrade")

    # 1. Update Broker Connections (optional but good for metadata)
    accounts = client.get_accounts(snap_user.snaptrade_user_id, snap_user.snaptrade_user_secret)
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
            exists = db.query(TradeHistory).filter(TradeHistory.external_trade_id == trade_id).first()
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
            trade = TradeHistory(
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

    return SyncResponse(status="success", trades_synced=synced_count)


@router.get("/trades", response_model=TradeListAPIResponse)
async def get_trades(
    user_id: int = Depends(get_current_user),
    symbol: Optional[str] = None,
    sort: str = "-executed_at",
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get trade history, optionally filtered by symbol, with pagination."""
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        return TradeListAPIResponse(trades=[], total=0, page=page, limit=limit)

    # Join tables
    query = db.query(TradeHistory).join(BrokerConnection).filter(
        BrokerConnection.snaptrade_user_id == snap_user.id
    )

    if symbol:
        query = query.filter(TradeHistory.symbol == symbol)

    total = query.count()

    # Sorting
    desc_sort = sort.startswith("-")
    sort_field = sort.lstrip("-")
    column = getattr(TradeHistory, sort_field, TradeHistory.executed_at)
    query = query.order_by(column.desc() if desc_sort else column.asc())

    # Pagination
    offset = (max(page, 1) - 1) * limit
    trades = query.offset(offset).limit(limit).all()

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
                brokerage=t.connection.brokerage_name
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

