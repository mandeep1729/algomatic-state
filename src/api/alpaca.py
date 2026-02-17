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
from src.data.database.dependencies import get_broker_repo, get_db, session_scope
from src.data.database.broker_repository import BrokerRepository
from src.data.database.broker_models import BrokerConnection, TradeFill
from src.execution.client import AlpacaClient, TradeFillInfo

logger = logging.getLogger(__name__)

# Minimum interval between automatic syncs (5 minutes)
AUTO_SYNC_INTERVAL = timedelta(minutes=5)

router = APIRouter(prefix="/api/alpaca", tags=["alpaca"])


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

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
    campaigns_created: Optional[int] = None
    fills_grouped: Optional[int] = None


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
    repo: BrokerRepository,
    user_id: int,
    paper: bool = True,
) -> BrokerConnection:
    """Get or create a broker connection for Alpaca.

    Since we're using direct Alpaca API (not SnapTrade), we create a
    'virtual' connection to store fills.
    """
    broker_name = "Alpaca Paper" if paper else "Alpaca Live"
    broker_slug = "alpaca_paper" if paper else "alpaca_live"

    snap_user = repo.get_or_create_snaptrade_user(
        user_id=user_id,
        snaptrade_id=f"alpaca_direct_{user_id}",
        snaptrade_secret="direct_connection",
    )

    conn = repo.get_connection(snap_user.id, broker_slug)
    if not conn:
        conn = repo.create_connection(
            snaptrade_user_id=snap_user.id,
            brokerage_name=broker_name,
            brokerage_slug=broker_slug,
            authorization_id=f"alpaca_direct_{user_id}_{broker_slug}",
            meta={"connection_type": "direct_api", "paper": paper},
        )

    return conn


def sync_fills_to_db(
    repo: BrokerRepository,
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
        if repo.exists_by_external_id(fill.id):
            skipped += 1
            continue

        repo.create_fill(
            broker_connection_id=connection.id,
            account_id=user_id,
            symbol=fill.symbol,
            side=fill.side.lower(),
            quantity=fill.quantity,
            price=fill.price,
            fees=0.0,
            executed_at=fill.transaction_time,
            broker="Alpaca",
            asset_type="equity",
            currency="USD",
            order_id=fill.order_id,
            external_trade_id=fill.id,
            source="broker_synced",
            raw_data=fill.raw_data,
        )
        synced += 1

    if synced > 0:
        logger.info("Synced %d fills to database (skipped %d duplicates)", synced, skipped)

    return synced, skipped


# -----------------------------------------------------------------------------
# Background Sync (called on login)
# -----------------------------------------------------------------------------

def sync_alpaca_fills_background(user_id: int) -> None:
    """Background task to sync Alpaca trade fills and rebuild campaigns.

    Called automatically on user login/session validation.
    Only syncs if last sync was more than AUTO_SYNC_INTERVAL ago.

    After syncing fills, automatically rebuilds campaigns from fills.
    """
    from src.data.database.trading_repository import TradingBuddyRepository

    try:
        client = AlpacaClient(paper=True)
    except ValueError as e:
        logger.debug("Alpaca client not configured, skipping auto-sync: %s", e)
        return

    try:
        with session_scope() as db:
            repo = BrokerRepository(db)

            latest_trade = repo.get_latest_fill(user_id, broker="Alpaca")

            if latest_trade:
                last_sync = latest_trade.created_at
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                if now - last_sync < AUTO_SYNC_INTERVAL:
                    logger.debug(
                        "Skipping auto-sync for user %d, last sync was %s ago",
                        user_id, now - last_sync,
                    )
                    return

            # Perform sync
            logger.info("Auto-syncing Alpaca fills for user %d", user_id)
            connection = get_or_create_alpaca_connection(repo, user_id, paper=client.paper)
            fills = client.get_trade_fills()

            synced = 0
            if fills:
                synced, skipped = sync_fills_to_db(repo, connection, user_id, fills)
                logger.info("Auto-sync complete: %d new fills, %d skipped", synced, skipped)
            else:
                logger.debug("No fills to sync from Alpaca")

            # Rebuild campaigns if we synced any new fills
            if synced > 0:
                try:
                    trading_repo = TradingBuddyRepository(db)
                    rebuild_stats = trading_repo.rebuild_all_campaigns(account_id=user_id)
                    if rebuild_stats.get("campaigns_created", 0) > 0:
                        logger.info(
                            "Auto-sync rebuilt %d campaigns across %d groups",
                            rebuild_stats.get("campaigns_created", 0),
                            rebuild_stats.get("groups_rebuilt", 0),
                        )
                except Exception as rebuild_err:
                    logger.error(
                        "Background campaign rebuild failed for user %s: %s",
                        user_id, rebuild_err,
                    )

    except Exception as e:
        logger.error("Background Alpaca sync failed for user %d: %s", user_id, e)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/account", response_model=AlpacaAccountResponse)
async def get_account(
    user_id: int = Depends(get_current_user),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Get Alpaca account information."""
    logger.debug("GET /api/alpaca/account for user_id=%d", user_id)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get Alpaca account: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/positions", response_model=List[AlpacaPositionResponse])
async def get_positions(
    user_id: int = Depends(get_current_user),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Get all current positions from Alpaca."""
    logger.debug("GET /api/alpaca/positions for user_id=%d", user_id)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get Alpaca positions: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync", response_model=SyncResponse)
async def sync_trades(
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Sync trade fills from Alpaca to database and rebuild campaigns."""
    from src.data.database.trading_repository import TradingBuddyRepository

    if not client:
        raise HTTPException(status_code=503, detail="Alpaca client not configured")

    try:
        connection = get_or_create_alpaca_connection(broker_repo, user_id, paper=client.paper)

        logger.info("Fetching trade fills from Alpaca for user %d", user_id)
        fills = client.get_trade_fills()

        if not fills:
            return SyncResponse(
                status="success",
                fills_synced=0,
                fills_skipped=0,
                message="No trade fills found in Alpaca account"
            )

        synced, skipped = sync_fills_to_db(broker_repo, connection, user_id, fills)

        campaigns_created = 0
        fills_grouped = 0

        if synced > 0:
            try:
                trading_repo = TradingBuddyRepository(broker_repo.session)
                rebuild_stats = trading_repo.rebuild_all_campaigns(account_id=user_id)
                campaigns_created = rebuild_stats.get("campaigns_created", 0)
                fills_grouped = rebuild_stats.get("fills_grouped", 0)

                if campaigns_created > 0:
                    logger.info(
                        "Rebuilt %d campaigns grouping %d fills",
                        campaigns_created, fills_grouped,
                    )
            except Exception as rebuild_err:
                logger.error("Failed to rebuild campaigns: %s", rebuild_err)

        msg_parts = [f"Synced {synced} new fills, skipped {skipped} existing"]
        if campaigns_created > 0:
            msg_parts.append(f"rebuilt {campaigns_created} campaigns")
        message = "; ".join(msg_parts)

        return SyncResponse(
            status="success",
            fills_synced=synced,
            fills_skipped=skipped,
            message=message,
            campaigns_created=campaigns_created if synced > 0 else None,
            fills_grouped=fills_grouped if synced > 0 else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to sync Alpaca trades: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trades", response_model=TradeListResponse)
async def get_trades(
    user_id: int = Depends(get_current_user),
    symbol: Optional[str] = None,
    sort: str = "-executed_at",
    page: int = 1,
    limit: int = 50,
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get synced trade fills from database."""
    logger.debug(
        "GET /api/alpaca/trades for user_id=%d: symbol=%s, sort=%s, page=%d, limit=%d",
        user_id, symbol, sort, page, limit,
    )

    desc_sort = sort.startswith("-")
    sort_field = sort.lstrip("-")

    trades, total = broker_repo.get_fills_paginated(
        account_id=user_id,
        symbol=symbol.upper() if symbol else None,
        broker="Alpaca",
        sort_field=sort_field,
        sort_desc=desc_sort,
        page=page,
        limit=limit,
    )

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
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: AlpacaClient = Depends(get_alpaca_client),
):
    """Get Alpaca connection and sync status."""
    logger.debug("GET /api/alpaca/status for user_id=%d", user_id)
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

    latest_trade = broker_repo.get_latest_fill(user_id, broker="Alpaca")
    if latest_trade:
        result["last_sync"] = latest_trade.created_at.isoformat()

    result["total_fills"] = broker_repo.count_fills(user_id, broker="Alpaca")

    return result
