"""FastAPI router for direct Alpaca integration.

Provides endpoints for:
- Syncing trade fills from Alpaca paper/live trading
- Fetching account info and positions
- Manual and automatic sync controls
- On-login background sync
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth_middleware import get_current_user
from src.data.database.connection import get_db_manager
from src.data.database.broker_models import BrokerConnection, TradeFill, SnapTradeUser
from src.execution.client import AlpacaClient, TradeFillInfo

logger = logging.getLogger(__name__)

# Minimum interval between automatic syncs (5 minutes)
AUTO_SYNC_INTERVAL = timedelta(minutes=5)

router = APIRouter(prefix="/api/alpaca", tags=["alpaca"])


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

def get_db():
    """Get database session."""
    with get_db_manager().get_session() as session:
        yield session


def get_alpaca_client():
    """Get Alpaca client instance (paper trading by default)."""
    try:
        return AlpacaClient(paper=True)
    except ValueError as e:
        logger.warning(f"Alpaca client not available: {e}")
        return None


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class AlpacaAccountResponse(BaseModel):
    """Alpaca account info response."""
    account_id: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    pattern_day_trader: bool
    trading_blocked: bool


class AlpacaPositionResponse(BaseModel):
    """Alpaca position response."""
    symbol: str
    quantity: float
    market_value: float
    avg_entry_price: float
    unrealized_pl: float
    unrealized_pl_pct: float
    current_price: float
    side: str


class SyncResponse(BaseModel):
    """Sync operation response."""
    status: str
    fills_synced: int
    fills_skipped: int
    message: str
    # Campaign population summary (populated if fills were synced)
    campaigns_created: Optional[int] = None
    lots_created: Optional[int] = None
    legs_created: Optional[int] = None
    pnl_summary: Optional[float] = None


class TradeResponse(BaseModel):
    """Trade fill response."""
    id: int
    symbol: str
    side: str
    quantity: float
    price: float
    fees: float
    executed_at: datetime
    broker: str
    external_trade_id: Optional[str] = None


class TradeListResponse(BaseModel):
    """Paginated trade list response."""
    trades: List[TradeResponse]
    total: int
    page: int
    limit: int


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def get_or_create_alpaca_connection(
    db: Session,
    user_id: int,
    paper: bool = True
) -> BrokerConnection:
    """Get or create a broker connection for Alpaca.

    Since we're using direct Alpaca API (not SnapTrade), we create a
    'virtual' connection to store fills.
    """
    broker_name = "Alpaca Paper" if paper else "Alpaca Live"
    broker_slug = "alpaca_paper" if paper else "alpaca_live"

    # Check for existing snaptrade user or create one
    snap_user = db.query(SnapTradeUser).filter(
        SnapTradeUser.user_account_id == user_id
    ).first()

    if not snap_user:
        # Create a placeholder SnapTrade user for direct Alpaca
        snap_user = SnapTradeUser(
            user_account_id=user_id,
            snaptrade_user_id=f"alpaca_direct_{user_id}",
            snaptrade_user_secret="direct_connection"  # Not used for direct API
        )
        db.add(snap_user)
        db.flush()

    # Check for existing Alpaca connection
    conn = db.query(BrokerConnection).filter(
        BrokerConnection.snaptrade_user_id == snap_user.id,
        BrokerConnection.brokerage_slug == broker_slug
    ).first()

    if not conn:
        conn = BrokerConnection(
            snaptrade_user_id=snap_user.id,
            brokerage_name=broker_name,
            brokerage_slug=broker_slug,
            authorization_id=f"alpaca_direct_{user_id}_{broker_slug}",
            meta={"connection_type": "direct_api", "paper": paper}
        )
        db.add(conn)
        db.flush()
        logger.info(f"Created Alpaca connection for user {user_id}")

    return conn


def sync_fills_to_db(
    db: Session,
    connection: BrokerConnection,
    user_id: int,
    fills: list[TradeFillInfo],
) -> tuple[int, int]:
    """Sync trade fills to database.

    Returns:
        Tuple of (synced_count, skipped_count)
    """
    synced = 0
    skipped = 0

    for fill in fills:
        # Check if already exists by external_trade_id
        exists = db.query(TradeFill).filter(
            TradeFill.external_trade_id == fill.id
        ).first()

        if exists:
            skipped += 1
            continue

        # Create new trade fill
        trade = TradeFill(
            broker_connection_id=connection.id,
            account_id=user_id,
            symbol=fill.symbol,
            side=fill.side.lower(),
            quantity=fill.quantity,
            price=fill.price,
            fees=0.0,  # Alpaca is commission-free for most trades
            executed_at=fill.transaction_time,
            broker="Alpaca",
            asset_type="equity",
            currency="USD",
            order_id=fill.order_id,
            external_trade_id=fill.id,
            source="broker_synced",  # Valid source value per check constraint
            raw_data=fill.raw_data
        )
        db.add(trade)
        synced += 1

    if synced > 0:
        db.flush()
        logger.info(f"Synced {synced} fills to database (skipped {skipped} duplicates)")

    return synced, skipped


# -----------------------------------------------------------------------------
# Background Sync (called on login)
# -----------------------------------------------------------------------------

def sync_alpaca_fills_background(user_id: int) -> None:
    """Background task to sync Alpaca trade fills and populate trading journal.

    Called automatically on user login/session validation.
    Only syncs if last sync was more than AUTO_SYNC_INTERVAL ago.

    After syncing fills, automatically populates position_campaigns,
    position_lots, and campaign_legs to build the trading journal.
    """
    from src.data.database.trading_repository import TradingBuddyRepository

    try:
        # Check if Alpaca client is available
        client = AlpacaClient(paper=True)
    except ValueError as e:
        logger.debug(f"Alpaca client not configured, skipping auto-sync: {e}")
        return

    try:
        with get_db_manager().get_session() as db:
            # Check last sync time
            latest_trade = db.query(TradeFill).filter(
                TradeFill.account_id == user_id,
                TradeFill.broker == "Alpaca"
            ).order_by(TradeFill.created_at.desc()).first()

            if latest_trade:
                last_sync = latest_trade.created_at
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                if now - last_sync < AUTO_SYNC_INTERVAL:
                    logger.debug(
                        f"Skipping auto-sync for user {user_id}, last sync was {now - last_sync} ago"
                    )
                    return

            # Perform sync
            logger.info(f"Auto-syncing Alpaca fills for user {user_id}")
            connection = get_or_create_alpaca_connection(db, user_id, paper=client.paper)
            fills = client.get_trade_fills()

            synced = 0
            if fills:
                synced, skipped = sync_fills_to_db(db, connection, user_id, fills)
                logger.info(f"Auto-sync complete: {synced} new fills, {skipped} skipped")
            else:
                logger.debug("No fills to sync from Alpaca")

            # Populate campaigns and legs if we synced any new fills
            if synced > 0:
                try:
                    repo = TradingBuddyRepository(db)
                    pop_stats = repo.populate_campaigns_and_legs(account_id=user_id)
                    if pop_stats.get("campaigns_created", 0) > 0:
                        logger.info(
                            "Auto-sync created %d campaigns with %d legs, total P&L: %.2f",
                            pop_stats.get("campaigns_created", 0),
                            pop_stats.get("legs_created", 0),
                            pop_stats.get("total_pnl", 0.0),
                        )
                except Exception as pop_err:
                    # Log but don't fail the sync for population errors
                    logger.error(f"Background campaign population failed: {pop_err}")

    except Exception as e:
        logger.error(f"Background Alpaca sync failed for user {user_id}: {e}")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/account", response_model=AlpacaAccountResponse)
async def get_account(
    user_id: int = Depends(get_current_user),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Get Alpaca account information."""
    if not client:
        raise HTTPException(status_code=503, detail="Alpaca client not configured")

    try:
        account = client.get_account()
        return AlpacaAccountResponse(
            account_id=account.account_id,
            buying_power=account.buying_power,
            cash=account.cash,
            portfolio_value=account.portfolio_value,
            equity=account.equity,
            pattern_day_trader=account.pattern_day_trader,
            trading_blocked=account.trading_blocked,
        )
    except Exception as e:
        logger.error(f"Failed to get Alpaca account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=List[AlpacaPositionResponse])
async def get_positions(
    user_id: int = Depends(get_current_user),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Get all current positions from Alpaca."""
    if not client:
        raise HTTPException(status_code=503, detail="Alpaca client not configured")

    try:
        positions = client.get_positions()
        return [
            AlpacaPositionResponse(
                symbol=p.symbol,
                quantity=p.quantity,
                market_value=p.market_value,
                avg_entry_price=p.avg_entry_price,
                unrealized_pl=p.unrealized_pl,
                unrealized_pl_pct=p.unrealized_pl_pct,
                current_price=p.current_price,
                side=p.side,
            )
            for p in positions
        ]
    except Exception as e:
        logger.error(f"Failed to get Alpaca positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=SyncResponse)
async def sync_trades(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Sync trade fills from Alpaca to database and populate trading journal.

    Fetches all trade activities (FILL events) from Alpaca and stores
    them in the trade_fills table. Duplicates are skipped based on
    external_trade_id.

    After syncing fills, automatically populates position_campaigns,
    position_lots, and campaign_legs to build the trading journal.
    """
    from src.data.database.trading_repository import TradingBuddyRepository

    if not client:
        raise HTTPException(status_code=503, detail="Alpaca client not configured")

    try:
        # Get or create connection
        connection = get_or_create_alpaca_connection(db, user_id, paper=client.paper)

        # Fetch fills from Alpaca (using closed orders)
        logger.info(f"Fetching trade fills from Alpaca for user {user_id}")
        fills = client.get_trade_fills()

        if not fills:
            return SyncResponse(
                status="success",
                fills_synced=0,
                fills_skipped=0,
                message="No trade fills found in Alpaca account"
            )

        # Sync to database
        synced, skipped = sync_fills_to_db(db, connection, user_id, fills)

        # Populate campaigns and legs if we synced any new fills
        campaigns_created = 0
        lots_created = 0
        legs_created = 0
        pnl_summary = None

        if synced > 0:
            try:
                repo = TradingBuddyRepository(db)
                pop_stats = repo.populate_campaigns_and_legs(account_id=user_id)
                campaigns_created = pop_stats.get("campaigns_created", 0)
                lots_created = pop_stats.get("lots_created", 0)
                legs_created = pop_stats.get("legs_created", 0)
                pnl_summary = pop_stats.get("total_pnl", 0.0)

                if campaigns_created > 0:
                    logger.info(
                        "Created %d campaigns with %d legs, total P&L: %.2f",
                        campaigns_created,
                        legs_created,
                        pnl_summary or 0.0,
                    )
            except Exception as pop_err:
                # Log but don't fail the sync for population errors
                logger.error(f"Failed to populate campaigns: {pop_err}")

        # Build response message
        msg_parts = [f"Synced {synced} new fills, skipped {skipped} existing"]
        if campaigns_created > 0:
            msg_parts.append(f"created {campaigns_created} campaigns with {legs_created} legs")
        message = "; ".join(msg_parts)

        return SyncResponse(
            status="success",
            fills_synced=synced,
            fills_skipped=skipped,
            message=message,
            campaigns_created=campaigns_created if synced > 0 else None,
            lots_created=lots_created if synced > 0 else None,
            legs_created=legs_created if synced > 0 else None,
            pnl_summary=pnl_summary,
        )

    except Exception as e:
        logger.error(f"Failed to sync Alpaca trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades", response_model=TradeListResponse)
async def get_trades(
    user_id: int = Depends(get_current_user),
    symbol: Optional[str] = None,
    sort: str = "-executed_at",
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get synced trade fills from database.

    Note: Call /sync first to fetch latest trades from Alpaca.
    """
    # Build query for Alpaca trades
    query = db.query(TradeFill).filter(
        TradeFill.account_id == user_id,
        TradeFill.broker == "Alpaca"
    )

    if symbol:
        query = query.filter(TradeFill.symbol == symbol.upper())

    total = query.count()

    # Sorting
    desc_sort = sort.startswith("-")
    sort_field = sort.lstrip("-")
    column = getattr(TradeFill, sort_field, TradeFill.executed_at)
    query = query.order_by(column.desc() if desc_sort else column.asc())

    # Pagination
    offset = (max(page, 1) - 1) * limit
    trades = query.offset(offset).limit(limit).all()

    return TradeListResponse(
        trades=[
            TradeResponse(
                id=t.id,
                symbol=t.symbol,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                fees=t.fees,
                executed_at=t.executed_at,
                broker=t.broker or "Alpaca",
                external_trade_id=t.external_trade_id,
            )
            for t in trades
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/status")
async def get_status(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Get Alpaca connection and sync status."""
    result = {
        "client_configured": client is not None,
        "paper_trading": client.paper if client else None,
        "market_open": None,
        "last_sync": None,
        "total_fills": 0,
    }

    if client:
        try:
            result["market_open"] = client.is_market_open()
        except Exception:
            pass

    # Get latest sync info
    latest_trade = db.query(TradeFill).filter(
        TradeFill.account_id == user_id,
        TradeFill.broker == "Alpaca"
    ).order_by(TradeFill.created_at.desc()).first()

    if latest_trade:
        result["last_sync"] = latest_trade.created_at.isoformat()

    # Count total fills
    result["total_fills"] = db.query(TradeFill).filter(
        TradeFill.account_id == user_id,
        TradeFill.broker == "Alpaca"
    ).count()

    return result
