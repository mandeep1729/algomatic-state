"""FastAPI router for data synchronization and import endpoints."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config.settings import get_settings
from src.api.auth_middleware import get_current_user
from src.api._data_helpers import (
    get_database_loader,
    invalidate_cache_for_symbol,
    PROJECT_ROOT,
)
from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.database.models import VALID_TIMEFRAMES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data-sync"])


class SyncStatusResponse(BaseModel):
    """Sync status for a symbol."""
    symbol: str
    timeframe: str
    last_synced_timestamp: Optional[str] = None
    first_synced_timestamp: Optional[str] = None
    last_sync_at: Optional[str] = None
    bars_fetched: int = 0
    total_bars: int = 0
    status: str = "unknown"
    error_message: Optional[str] = None


@router.get("/api/sync-status/{symbol}", response_model=list[SyncStatusResponse])
async def get_sync_status(symbol: str, _user_id: int = Depends(get_current_user)):
    """Get synchronization status for a symbol."""
    try:
        db_loader = get_database_loader()
        statuses = db_loader.get_sync_status(symbol.upper())

        if not statuses:
            logger.debug("No sync statuses found for symbol %s", symbol.upper())
            return []

        return [SyncStatusResponse(**status) for status in statuses]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting sync status: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/sync/{symbol}")
async def trigger_sync(
    symbol: str,
    timeframe: str = Query("1Min", description="Timeframe to sync"),
    start_date: Optional[str] = Query(None, description="Start date for historical sync"),
    end_date: Optional[str] = Query(None, description="End date (defaults to now)"),
    _user_id: int = Depends(get_current_user),
):
    """Trigger data synchronization for a symbol.

    Publishes a MARKET_DATA_REQUEST via the messaging bus. The
    MarketDataOrchestrator handles fetching from the provider and
    inserting into the database.
    """
    logger.debug(
        "POST /api/sync/%s: timeframe=%s, start_date=%s, end_date=%s",
        symbol, timeframe, start_date, end_date,
    )
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
        )

    try:
        from src.messaging.events import Event, EventType
        from src.messaging.bus import get_message_bus

        settings = get_settings()
        history_days = settings.data.history_months * 30
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()
        start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=history_days)

        bus = get_message_bus()
        bus.publish(Event(
            event_type=EventType.MARKET_DATA_REQUEST,
            payload={
                "symbol": symbol.upper(),
                "timeframes": [timeframe],
                "start": start,
                "end": end,
            },
            source="ui.backend.api",
        ))

        invalidate_cache_for_symbol(symbol)

        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            df = repo.get_bars(symbol.upper(), timeframe, start, end)

        return {
            "message": f"Sync completed for {symbol.upper()}/{timeframe}",
            "bars_loaded": len(df),
            "date_range": {
                "start": df.index.min().isoformat() if not df.empty else None,
                "end": df.index.max().isoformat() if not df.empty else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error syncing data: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/import")
async def import_data(
    symbol: str = Query(..., description="Symbol to import as"),
    file_path: str = Query(..., description="Path to CSV or Parquet file"),
    timeframe: str = Query("1Min", description="Timeframe of the data"),
    _user_id: int = Depends(get_current_user),
):
    """Import data from a local file into the database."""
    logger.info(
        "POST /api/import: symbol=%s, file_path=%s, timeframe=%s",
        symbol, file_path, timeframe,
    )
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
        )

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    try:
        db_loader = get_database_loader()

        if path.suffix.lower() == ".parquet":
            rows = db_loader.import_parquet(path, symbol.upper(), timeframe)
        else:
            rows = db_loader.import_csv(path, symbol.upper(), timeframe)

        return {
            "message": f"Import completed for {symbol.upper()}/{timeframe}",
            "rows_imported": rows,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error importing data: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
