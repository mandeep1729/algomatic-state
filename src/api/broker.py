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
    user_id: int = 1  # Default to internal user ID 1
    redirect_url: Optional[str] = None  # URL to redirect after connection
    broker: Optional[str] = None  # Pre-select broker (e.g., 'ALPACA')

class ConnectResponse(BaseModel):
    redirect_url: str

class TradeResponse(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float
    executed_at: datetime
    brokerage: str

class SyncResponse(BaseModel):
    status: str
    trades_synced: int

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/connect", response_model=ConnectResponse)
async def connect_broker(
    request: ConnectRequest,
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client)
):
    """Initiate broker connection.

    Registers user with SnapTrade if needed and returns a connection link.
    """
    if not client.client:
         raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    # 1. Check if user exists
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == request.user_id
    ).first()

    # 2. Register if not exists
    if not snap_user:
        # Generate a unique ID for SnapTrade (e.g., "algomatic_user_{id}")
        snap_user_id = f"algomatic_user_{request.user_id}"
        
        registration = client.register_user(snap_user_id)
        if not registration:
             raise HTTPException(status_code=500, detail="Failed to register user with SnapTrade")
        
        snap_user = SnapTradeUser(
            user_account_id=request.user_id,
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
    user_id: int = 1,
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client)
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
            # Check/Update connection
            # Note: SnapTrade account structure is hierarchical (Broker -> Account)
            # We treat each "Account" as a connection for simplicity or map them
            # For now, let's just log or store simple connection info.
            
            # Find existing
            broker_slug = acc.get("brokerage_authorization", {}).get("brokerage", {}).get("slug", "unknown")
            broker_name = acc.get("brokerage_authorization", {}).get("brokerage", {}).get("name", "Unknown Broker")
            auth_id = acc.get("brokerage_authorization", {}).get("id")
            
            if not auth_id:
                continue

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
            
    # Fetch all activities
    activities = client.get_activities(snap_user.snaptrade_user_id, snap_user.snaptrade_user_secret)
    synced_count = 0
    
    if activities:
        for activity in activities:
            # Filter for trades
            if activity.get("type") not in ["BUY", "SELL"]:
                continue
                
            # Find corresponding connection (we need account_id from activity)
            # This part requires mapping account_id back to BrokerConnection
            # For simplicity, we just pick the first connection or try to match
            # activity['account']['id']
            
            account_id = activity.get("account", {}).get("id")
            # We stored auth_id in BrokerConnection, but account_id is different (one auth can have multiple accounts)
            # Ideally BrokerConnection should rely on authorization_id, and we might need an Account table.
            # For this MVP, let's just link to the SnapTradeUser via a generic BrokerConnection lookup 
            # OR just assume we attach to the first valid connection for that user, 
            # OR better: fetch connection by matching account_id inside the meta JSONB we stored.
            
            # Simple fallback: find connection where meta->id == account_id
            # This is slow in SQL but ok for MVP.
            
            conn = None
            # Iterate loaded connections in session or query properly
            # Optimization: Pre-load all user connections
            user_conns = db.query(BrokerConnection).filter(BrokerConnection.snaptrade_user_id == snap_user.id).all()
            for c in user_conns:
                # meta is the account object from SnapTrade
                if c.meta.get("id") == account_id:
                    conn = c
                    break
            
            if not conn:
                # If we can't find the connection, we skip or create a dummy one.
                # Let's skip with warning
                logger.warning(f"Could not find connection for account {account_id}")
                continue

            # Check if trade exists
            trade_id = str(activity.get("id"))
            exists = db.query(TradeHistory).filter(TradeHistory.external_trade_id == trade_id).first()
            if exists:
                continue
                
            # Create Trade
            trade = TradeHistory(
                broker_connection_id=conn.id,
                symbol=activity.get("symbol", {}).get("symbol", "UNKNOWN"),
                side=activity.get("type", "UNKNOWN").lower(),
                quantity=float(activity.get("units", 0)),
                price=float(activity.get("price", 0)),
                fees=float(activity.get("fees", 0)),
                executed_at=datetime.fromisoformat(activity.get("trade_date").replace("Z", "+00:00")),
                external_trade_id=trade_id,
                raw_data=activity
            )
            db.add(trade)
            synced_count += 1

    return SyncResponse(status="success", trades_synced=synced_count)


@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    user_id: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get trade history."""
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        return []

    # Join tables
    trades = db.query(TradeHistory).join(BrokerConnection).filter(
        BrokerConnection.snaptrade_user_id == snap_user.id
    ).order_by(TradeHistory.executed_at.desc()).limit(limit).all()

    return [
        TradeResponse(
            symbol=t.symbol,
            side=t.side,
            quantity=t.quantity,
            price=t.price,
            executed_at=t.executed_at,
            brokerage=t.connection.brokerage_name
        )
        for t in trades
    ]


class ConnectionStatusResponse(BaseModel):
    connected: bool
    brokerages: List[str] = []


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    user_id: int = 1,
    db: Session = Depends(get_db),
    client: SnapTradeClient = Depends(get_snaptrade_client)
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

