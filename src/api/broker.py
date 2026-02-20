"""FastAPI router for Broker integration via SnapTrade.

Provides endpoints for:
- Connecting brokerage accounts
- Syncing data
- Fetching trade history
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from src.api.auth_middleware import get_current_user
from src.data.database.dependencies import get_broker_repo
from src.data.database.broker_repository import BrokerRepository
from src.data.database.broker_models import TradeFill
from src.execution.snaptrade_client import SnapTradeClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/broker", tags=["broker"])

# -----------------------------------------------------------------------------
# Dependency
# -----------------------------------------------------------------------------

def get_snaptrade_client():
    """Get SnapTrade client instance."""
    return SnapTradeClient()


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    redirect_url: Optional[str] = None
    broker: Optional[str] = None
    force: bool = False

class ConnectResponse(BaseModel):
    redirect_url: str

class ContextSummary(BaseModel):
    """Summary of decision context for a trade fill."""
    strategy: Optional[str] = None
    emotions: Optional[str] = None
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
    tags: List[str] = []

class TradeListAPIResponse(BaseModel):
    trades: List[TradeResponse]
    total: int
    page: int
    limit: int

class SyncResponse(BaseModel):
    status: str
    trades_synced: int
    campaigns_created: int = 0
    fills_backfilled: int = 0

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/connect", response_model=ConnectResponse)
async def connect_broker(
    request: ConnectRequest,
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Initiate broker connection."""
    logger.debug("connect_broker: user_id=%d, broker=%s, force=%s", user_id, request.broker, request.force)
    if not client.client:
        logger.error("SnapTrade client not available for user %s", user_id)
        raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    snap_user = broker_repo.get_snaptrade_user(user_id)
    needs_registration = not snap_user or snap_user.snaptrade_user_id.startswith("alpaca_direct_")

    if needs_registration:
        snap_user_id = f"algomatic_user_{user_id}"
        logger.debug("Registering SnapTrade user: %s (had_dummy_creds=%s)", snap_user_id, snap_user is not None)

        registration = client.register_user(snap_user_id)
        if not registration:
            logger.error("Failed to register SnapTrade user for user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="Failed to register user with SnapTrade")

        if snap_user:
            snap_user = broker_repo.update_snaptrade_credentials(
                snap_user,
                snaptrade_id=registration["user_id"],
                snaptrade_secret=registration["user_secret"],
            )
        else:
            snap_user = broker_repo.get_or_create_snaptrade_user(
                user_id=user_id,
                snaptrade_id=registration["user_id"],
                snaptrade_secret=registration["user_secret"],
            )

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
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Sync trades and accounts from connected brokers."""
    logger.debug("sync_data: user_id=%d", user_id)
    if not client.client:
        logger.error("SnapTrade client not available for user %s", user_id)
        raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    snap_user = broker_repo.get_snaptrade_user(user_id)
    if not snap_user:
        raise HTTPException(status_code=404, detail="User not registered with SnapTrade")

    # 1. Update Broker Connections
    accounts = client.get_accounts(snap_user.snaptrade_user_id, snap_user.snaptrade_user_secret)
    logger.debug("Found %d connected accounts for user_id=%d", len(accounts) if accounts else 0, user_id)
    if accounts:
        for acc in accounts:
            auth_id = acc.get("brokerage_authorization")
            if not auth_id or not isinstance(auth_id, str):
                continue

            broker_name = acc.get("institution_name") or acc.get("name") or "Unknown Broker"
            broker_slug = broker_name.lower().replace(" ", "_")

            conn = broker_repo.get_connection_by_auth_id(auth_id)

            if not conn:
                broker_repo.create_connection(
                    snaptrade_user_id=snap_user.id,
                    brokerage_name=broker_name,
                    brokerage_slug=broker_slug,
                    authorization_id=auth_id,
                    meta=acc,
                )
            else:
                conn.meta = acc
            broker_repo.session.flush()

    # Pre-load all user connections for matching
    user_conns = broker_repo.get_connections_for_user(snap_user.id)

    # Fetch all activities
    activities = client.get_activities(snap_user.snaptrade_user_id, snap_user.snaptrade_user_secret)
    synced_count = 0

    if activities:
        for activity in activities:
            activity_type = activity.get("type", "").upper()
            if activity_type not in ["BUY", "SELL"]:
                continue

            account_data = activity.get("account")
            if isinstance(account_data, dict):
                account_id = account_data.get("id")
            else:
                account_id = None

            conn = None
            for c in user_conns:
                if c.meta and c.meta.get("id") == account_id:
                    conn = c
                    break

            if not conn and user_conns:
                conn = user_conns[0]

            if not conn:
                logger.warning("Could not find connection for account %s", account_id)
                continue

            trade_id = str(activity.get("id"))
            if broker_repo.exists_by_external_id(trade_id):
                continue

            symbol_data = activity.get("symbol")
            if isinstance(symbol_data, dict):
                symbol = symbol_data.get("symbol", "UNKNOWN")
            elif isinstance(symbol_data, str):
                symbol = symbol_data
            else:
                symbol = "UNKNOWN"

            trade_date_str = activity.get("trade_date") or activity.get("settlement_date")
            if trade_date_str:
                executed_at = datetime.fromisoformat(trade_date_str.replace("Z", "+00:00"))
            else:
                logger.warning("No trade date for activity %s, using current time", activity.get("id", "unknown"))
                executed_at = datetime.now(timezone.utc)

            # Extract tags from activity if available
            tags = None
            if "tags" in activity:
                tags = activity.get("tags")
            if "strategy_id" in activity:
                if tags is None:
                    tags = {}
                tags["strategy_id"] = activity.get("strategy_id")

            broker_repo.create_fill(
                broker_connection_id=conn.id,
                account_id=user_id,
                symbol=symbol,
                side=activity_type.lower(),
                quantity=float(activity.get("units", 0)),
                price=float(activity.get("price", 0)),
                fees=float(activity.get("fee", 0)),
                executed_at=executed_at,
                external_trade_id=trade_id,
                raw_data=activity,
                tags=tags,
            )
            synced_count += 1

    # Backfill account_id on any existing fills that are NULL
    user_conn_ids = [c.id for c in user_conns]
    backfilled = broker_repo.backfill_account_id(user_conn_ids, user_id)

    # Rebuild campaigns from fills
    from src.data.database.trading_repository import TradingBuddyRepository
    repo = TradingBuddyRepository(broker_repo.session)
    rebuild_stats = repo.rebuild_all_campaigns(account_id=user_id)

    logger.info(
        "Sync complete for user_id=%d: %d trades synced, %d backfilled, "
        "%d campaigns created",
        user_id, synced_count, backfilled,
        rebuild_stats.get("campaigns_created", 0),
    )

    # Trigger baseline stats computation after sync
    try:
        from src.reviewer.publisher import publish_baseline_requested
        publish_baseline_requested(account_id=user_id)
    except Exception:
        logger.debug("Failed to publish baseline requested after sync", exc_info=True)

    return SyncResponse(
        status="success",
        trades_synced=synced_count,
        campaigns_created=rebuild_stats.get("campaigns_created", 0),
        fills_backfilled=backfilled,
    )


@router.get("/trades", response_model=TradeListAPIResponse)
async def get_trades(
    user_id: int = Depends(get_current_user),
    symbol: Optional[str] = None,
    uncategorized: bool = False,
    sort: str = "-executed_at",
    page: int = 1,
    limit: int = 50,
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get trade history, optionally filtered by symbol, with pagination."""
    logger.debug(
        "get_trades: user_id=%d, symbol=%s, uncategorized=%s, page=%d, limit=%d",
        user_id, symbol, uncategorized, page, limit
    )

    snap_user = broker_repo.get_snaptrade_user(user_id)
    if not snap_user:
        return TradeListAPIResponse(trades=[], total=0, page=page, limit=limit)

    desc_sort = sort.startswith("-")
    sort_field = sort.lstrip("-")

    trades, total = broker_repo.get_fills_paginated(
        account_id=user_id,
        symbol=symbol,
        sort_field=sort_field,
        sort_desc=desc_sort,
        uncategorized=uncategorized,
        page=page,
        limit=limit,
        snaptrade_user_id=snap_user.id,
    )

    # Fetch context summaries for all trade fills
    trade_ids = [t.id for t in trades]
    context_map: Dict[int, ContextSummary] = {}

    if trade_ids:
        raw_contexts = broker_repo.get_context_summaries_for_fills(trade_ids)
        for fill_id, data in raw_contexts.items():
            emotions: Optional[str] = None
            feelings_then = data.get("feelings_then")
            if feelings_then and isinstance(feelings_then, dict):
                chips = feelings_then.get("chips", [])
                if chips:
                    emotions = ", ".join(chips[:3])

            hypothesis_snippet: Optional[str] = None
            hypothesis = data.get("hypothesis")
            if hypothesis:
                snippet = hypothesis[:50]
                if len(hypothesis) > 50:
                    snippet += "..."
                hypothesis_snippet = snippet

            context_map[fill_id] = ContextSummary(
                strategy=data.get("strategy_name"),
                emotions=emotions,
                hypothesis_snippet=hypothesis_snippet,
            )

    def _extract_tags(raw_tags: Optional[dict]) -> List[str]:
        """Extract display tags from the JSONB tags field.

        The TradeFill.tags column is a JSONB dict with broker metadata.
        Convert dict keys to a list of display-friendly strings, filtering
        out internal keys like strategy_id.
        """
        if not raw_tags:
            return []
        if isinstance(raw_tags, list):
            return [str(t) for t in raw_tags]
        # Dict: use keys as tags, excluding internal metadata keys
        internal_keys = {"strategy_id"}
        return [k for k in raw_tags if k not in internal_keys]

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
                tags=_extract_tags(t.tags),
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


# --- Brokerage catalog & connection detail models ---

class BrokerageInfo(BaseModel):
    id: str
    name: str
    display_name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    square_logo_url: Optional[str] = None
    brokerage_type: Optional[str] = None
    enabled: bool = True
    allows_trading: bool = False
    maintenance_mode: bool = False
    url: Optional[str] = None


class BrokerageListResponse(BaseModel):
    brokerages: List[BrokerageInfo]


class ConnectionDetail(BaseModel):
    authorization_id: str
    brokerage_name: str
    brokerage_slug: str
    brokerage_logo_url: Optional[str] = None
    created_date: Optional[str] = None
    disabled: bool = False


class ConnectionStatusDetailResponse(BaseModel):
    connected: bool
    connections: List[ConnectionDetail]


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Check if user has any connected brokerages."""
    logger.debug("get_connection_status: user_id=%d", user_id)
    snap_user = broker_repo.get_snaptrade_user(user_id)

    if not snap_user:
        return ConnectionStatusResponse(connected=False, brokerages=[])

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
                        name = acc.get("institution_name") or acc.get("name") or "Unknown"
                        brokerages.append(name)
                except Exception as e:
                    logger.warning("Error parsing account data: %s", e, exc_info=True)
                    continue
            return ConnectionStatusResponse(connected=len(brokerages) > 0, brokerages=list(set(brokerages)))

    return ConnectionStatusResponse(connected=False, brokerages=[])


@router.get("/callback")
async def broker_callback(
    status: str = "success",
):
    """Handle callback from SnapTrade after broker connection."""
    return {
        "status": status,
        "message": "Connection process completed. Check /api/broker/status for connection state."
    }


# -----------------------------------------------------------------------------
# Brokerage Catalog & Connection Detail Endpoints
# -----------------------------------------------------------------------------

# Simple in-memory cache for brokerage list (1 hour TTL)
_brokerage_cache: Tuple[float, List[BrokerageInfo]] = (0.0, [])
_BROKERAGE_CACHE_TTL = 3600  # 1 hour


@router.get("/brokerages", response_model=BrokerageListResponse)
async def list_brokerages(
    user_id: int = Depends(get_current_user),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """List all SnapTrade-supported brokerages (enabled only, cached 1h)."""
    global _brokerage_cache
    logger.debug("list_brokerages: user_id=%d", user_id)

    if not client.client:
        raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    cached_at, cached_list = _brokerage_cache
    if cached_list and (time.time() - cached_at) < _BROKERAGE_CACHE_TTL:
        logger.debug("Returning cached brokerage list (%d items)", len(cached_list))
        return BrokerageListResponse(brokerages=cached_list)

    raw = client.list_brokerages()
    if raw is None:
        raise HTTPException(status_code=502, detail="Failed to fetch brokerages from SnapTrade")

    brokerages = []
    for b in raw:
        # Only include enabled brokerages
        if not b.get("enabled", False):
            continue
        brokerages.append(BrokerageInfo(
            id=str(b.get("id", "")),
            name=b.get("name", ""),
            display_name=b.get("display_name") or b.get("name", ""),
            slug=b.get("slug", ""),
            description=b.get("description"),
            logo_url=b.get("aws_s3_logo_url"),
            square_logo_url=b.get("aws_s3_square_logo_url"),
            brokerage_type=b.get("brokerage_type", {}).get("name") if isinstance(b.get("brokerage_type"), dict) else str(b.get("brokerage_type", "")),
            enabled=b.get("enabled", True),
            allows_trading=b.get("allows_trading", False),
            maintenance_mode=b.get("maintenance_mode", False),
            url=b.get("url"),
        ))

    brokerages.sort(key=lambda x: x.display_name.lower())
    _brokerage_cache = (time.time(), brokerages)
    logger.info("Fetched and cached %d brokerages from SnapTrade", len(brokerages))

    return BrokerageListResponse(brokerages=brokerages)


@router.get("/connections", response_model=ConnectionStatusDetailResponse)
async def list_connections(
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """List user's connected brokerages with per-connection details."""
    logger.debug("list_connections: user_id=%d", user_id)

    snap_user = broker_repo.get_snaptrade_user(user_id)
    if not snap_user:
        return ConnectionStatusDetailResponse(connected=False, connections=[])

    if not client.client:
        # Fall back to local DB connections
        local_conns = broker_repo.get_connections_for_user(snap_user.id)
        connections = [
            ConnectionDetail(
                authorization_id=c.authorization_id,
                brokerage_name=c.brokerage_name,
                brokerage_slug=c.brokerage_slug,
                created_date=c.created_at.isoformat() if c.created_at else None,
                disabled=not c.is_active,
            )
            for c in local_conns if c.is_active
        ]
        return ConnectionStatusDetailResponse(
            connected=len(connections) > 0,
            connections=connections,
        )

    raw = client.list_connections(
        snap_user.snaptrade_user_id,
        snap_user.snaptrade_user_secret,
    )

    if raw is None:
        logger.warning("Failed to fetch connections from SnapTrade for user_id=%d", user_id)
        return ConnectionStatusDetailResponse(connected=False, connections=[])

    connections = []
    for auth in raw:
        brokerage = auth.get("brokerage") or {}
        connections.append(ConnectionDetail(
            authorization_id=str(auth.get("id", "")),
            brokerage_name=brokerage.get("name") or auth.get("brokerage_name", "Unknown"),
            brokerage_slug=brokerage.get("slug") or auth.get("brokerage_slug", ""),
            brokerage_logo_url=brokerage.get("aws_s3_square_logo_url") or brokerage.get("aws_s3_logo_url"),
            created_date=auth.get("created_date"),
            disabled=auth.get("disabled", False),
        ))

    return ConnectionStatusDetailResponse(
        connected=len(connections) > 0,
        connections=connections,
    )


@router.delete("/connections/{authorization_id}")
async def remove_connection(
    authorization_id: str,
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
    client: SnapTradeClient = Depends(get_snaptrade_client),
):
    """Disconnect a broker by removing the SnapTrade authorization."""
    logger.debug("remove_connection: user_id=%d, auth_id=%s", user_id, authorization_id)

    if not client.client:
        raise HTTPException(status_code=503, detail="SnapTrade service unavailable")

    snap_user = broker_repo.get_snaptrade_user(user_id)
    if not snap_user:
        raise HTTPException(status_code=404, detail="User not registered with SnapTrade")

    # Verify ownership: check the connection belongs to this user
    conn = broker_repo.get_connection_by_auth_id(authorization_id)
    if conn and conn.snaptrade_user_id != snap_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to remove this connection")

    removed = client.remove_connection(
        authorization_id=authorization_id,
        user_id=snap_user.snaptrade_user_id,
        user_secret=snap_user.snaptrade_user_secret,
    )

    if not removed:
        raise HTTPException(status_code=500, detail="Failed to remove connection from SnapTrade")

    # Mark local connection as inactive
    if conn:
        conn.is_active = False
        conn.updated_at = datetime.now(timezone.utc)
        broker_repo.session.flush()
        logger.info("Marked connection %s as inactive for user_id=%d", authorization_id, user_id)

    return {"status": "disconnected", "authorization_id": authorization_id}


# -----------------------------------------------------------------------------
# Fill Context Endpoints
# -----------------------------------------------------------------------------

class FillContextDetail(BaseModel):
    """Full decision context for a trade fill."""
    fill_id: int
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
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Get the full decision context for a specific trade fill."""
    logger.debug("get_fill_context: fill_id=%d, user_id=%d", fill_id, user_id)

    fill = broker_repo.get_fill(fill_id, account_id=user_id)
    if not fill:
        raise HTTPException(status_code=404, detail=f"Fill {fill_id} not found")

    context = broker_repo.get_decision_context(fill_id)
    if not context:
        return FillContextDetail(fill_id=fill_id)

    # Get strategy name
    strategy_name: Optional[str] = None
    if context.strategy_id:
        strategy = broker_repo.get_strategy_by_id(context.strategy_id)
        if strategy:
            strategy_name = strategy.name

    exit_intent_str: Optional[str] = None
    if context.exit_intent:
        if isinstance(context.exit_intent, dict):
            exit_intent_str = context.exit_intent.get("type")
        elif isinstance(context.exit_intent, str):
            exit_intent_str = context.exit_intent

    return FillContextDetail(
        fill_id=fill_id,
        context_id=context.id,
        context_type=context.context_type,
        strategy_id=context.strategy_id,
        strategy_name=strategy_name,
        hypothesis=context.hypothesis,
        exit_intent=exit_intent_str,
        feelings_then=context.feelings_then,
        feelings_now=context.feelings_now,
        notes=context.notes,
        updated_at=context.updated_at,
    )


@router.put("/fills/{fill_id}/context", response_model=FillContextDetail)
async def save_fill_context(
    fill_id: int,
    request: SaveFillContextRequest,
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Save or update the decision context for a trade fill."""
    logger.debug("save_fill_context: fill_id=%d, user_id=%d", fill_id, user_id)

    fill = broker_repo.get_fill(fill_id, account_id=user_id)
    if not fill:
        raise HTTPException(status_code=404, detail=f"Fill {fill_id} not found")

    from src.data.database.trading_repository import TradingBuddyRepository
    repo = TradingBuddyRepository(broker_repo.session)

    # Determine context type from fill side
    context_type = "entry" if fill.side.lower() == "buy" else "exit"

    # Get or create decision context
    context = repo.get_or_create_decision_context(
        fill_id=fill_id,
        account_id=user_id,
        context_type=context_type,
    )

    # Track old strategy for campaign rebuild
    old_strategy_id = context.strategy_id

    # Update context fields
    if request.strategy_id is not None:
        context.strategy_id = request.strategy_id
    context.hypothesis = request.hypothesis
    context.exit_intent = request.exit_intent
    context.feelings_then = request.feelings_then
    context.feelings_now = request.feelings_now
    context.notes = request.notes
    context.updated_at = datetime.now(timezone.utc)
    flag_modified(context, "exit_intent")
    flag_modified(context, "feelings_then")
    flag_modified(context, "feelings_now")
    broker_repo.session.flush()

    # If strategy changed, rebuild affected campaigns
    new_strategy_id = context.strategy_id
    if old_strategy_id != new_strategy_id:
        repo.on_strategy_updated(
            account_id=user_id,
            fill_id=fill_id,
            old_strategy_id=old_strategy_id,
            new_strategy_id=new_strategy_id,
        )

    logger.info("Saved fill context: fill_id=%d, context_id=%d", fill_id, context.id)

    # Get strategy name for response
    strategy_name: Optional[str] = None
    if context.strategy_id:
        strategy = broker_repo.get_strategy_by_id(context.strategy_id)
        if strategy:
            strategy_name = strategy.name

    return FillContextDetail(
        fill_id=fill_id,
        context_id=context.id,
        context_type=context.context_type,
        strategy_id=context.strategy_id,
        strategy_name=strategy_name,
        hypothesis=context.hypothesis,
        exit_intent=request.exit_intent,
        feelings_then=context.feelings_then,
        feelings_now=context.feelings_now,
        notes=context.notes,
        updated_at=context.updated_at,
    )


# -----------------------------------------------------------------------------
# Bulk Strategy Update Endpoint
# -----------------------------------------------------------------------------

class BulkUpdateStrategyRequest(BaseModel):
    """Request body for bulk-updating strategy on multiple fills."""
    fill_ids: List[int]
    strategy_id: Optional[int] = None


class BulkUpdateStrategyResponse(BaseModel):
    """Response for bulk strategy update."""
    updated_count: int
    skipped_count: int


@router.post("/fills/bulk-update-strategy", response_model=BulkUpdateStrategyResponse)
async def bulk_update_strategy(
    request: BulkUpdateStrategyRequest,
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Bulk-update the strategy assignment for multiple trade fills."""
    logger.debug(
        "bulk_update_strategy: user_id=%d, fill_ids=%s, strategy_id=%s",
        user_id, request.fill_ids, request.strategy_id
    )

    if not request.fill_ids:
        return BulkUpdateStrategyResponse(updated_count=0, skipped_count=0)

    # Validate strategy exists if provided
    if request.strategy_id is not None:
        strategy = broker_repo.get_strategy_by_id(request.strategy_id, account_id=user_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

    # Verify fills belong to the user
    user_fills = []
    for fid in request.fill_ids:
        f = broker_repo.get_fill(fid, account_id=user_id)
        if f:
            user_fills.append(f)
    valid_fill_ids = {f.id for f in user_fills}

    from src.data.database.trading_repository import TradingBuddyRepository
    repo = TradingBuddyRepository(broker_repo.session)

    updated_count = 0
    skipped_count = 0
    affected_symbols: set[str] = set()
    old_strategy_ids: set[Optional[int]] = set()

    for fill_id in request.fill_ids:
        if fill_id not in valid_fill_ids:
            skipped_count += 1
            continue

        fill = next(f for f in user_fills if f.id == fill_id)
        context_type = "entry" if fill.side.lower() == "buy" else "exit"

        context = repo.get_or_create_decision_context(
            fill_id=fill_id,
            account_id=user_id,
            context_type=context_type,
        )

        old_strategy_ids.add(context.strategy_id)
        context.strategy_id = request.strategy_id
        context.updated_at = datetime.now(timezone.utc)
        affected_symbols.add(fill.symbol)
        updated_count += 1

    broker_repo.session.flush()

    # Rebuild campaigns for affected (symbol, strategy) groups
    for symbol in affected_symbols:
        for old_sid in old_strategy_ids:
            if old_sid != request.strategy_id:
                repo.rebuild_campaigns(user_id, symbol, old_sid)
        repo.rebuild_campaigns(user_id, symbol, request.strategy_id)

    logger.info(
        "bulk_update_strategy: user_id=%d, updated=%d, skipped=%d",
        user_id, updated_count, skipped_count,
    )

    return BulkUpdateStrategyResponse(
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


# -----------------------------------------------------------------------------
# Rebuild Campaigns Endpoint
# -----------------------------------------------------------------------------

class RebuildCampaignsResponse(BaseModel):
    """Response for rebuild-campaigns endpoint."""
    status: str
    campaigns_created: int
    fills_grouped: int
    groups_rebuilt: int
    message: str


@router.post("/rebuild-campaigns", response_model=RebuildCampaignsResponse)
async def rebuild_campaigns(
    symbol: Optional[str] = None,
    user_id: int = Depends(get_current_user),
    broker_repo: BrokerRepository = Depends(get_broker_repo),
):
    """Rebuild campaigns from trade fills."""
    from src.data.database.trading_repository import TradingBuddyRepository

    try:
        repo = TradingBuddyRepository(broker_repo.session)

        if symbol:
            stats = {"campaigns_created": 0, "fills_grouped": 0, "groups_rebuilt": 0}
            strategy_ids = broker_repo.get_distinct_strategy_ids(user_id, symbol)
            for sid in strategy_ids:
                group_stats = repo.rebuild_campaigns(user_id, symbol.upper(), sid)
                stats["campaigns_created"] += group_stats["campaigns_created"]
                stats["fills_grouped"] += group_stats["fills_grouped"]
                stats["groups_rebuilt"] += 1
        else:
            stats = repo.rebuild_all_campaigns(account_id=user_id)

        message = f"Rebuilt {stats['campaigns_created']} campaigns from {stats['fills_grouped']} fills"

        return RebuildCampaignsResponse(
            status="success",
            campaigns_created=stats["campaigns_created"],
            fills_grouped=stats["fills_grouped"],
            groups_rebuilt=stats.get("groups_rebuilt", 0),
            message=message,
        )

    except Exception as e:
        logger.exception("Failed to rebuild campaigns: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
