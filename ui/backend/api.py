"""FastAPI backend for regime state visualization UI.

This is the application shell — it creates the FastAPI app, configures CORS,
manages orchestrator lifecycles, includes all routers, and provides the
health check and Go-strats compatibility endpoints.

Business logic is delegated to focused routers in src/api/:
- ohlcv.py — OHLCV data, tickers, statistics
- features_api.py — Feature computation
- regimes.py — HMM + PCA regime states
- data_sync.py — Sync, import, sync-status
- analysis.py — Symbol analysis (HMM + PCA)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Determine project root directory for consistent path resolution
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

# Add parent directory to path for imports (needed before importing src modules)
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth_middleware import get_current_user
from src.api._data_helpers import clear_all_cache

from config.settings import get_settings
from src.utils.logging import setup_logging

# Configure logging
settings = get_settings()
LOGS_DIR = PROJECT_ROOT / "logs"
setup_logging(
    level=settings.logging.level,
    format="text",
    file=LOGS_DIR / "backend.log",
    rotate_size_mb=settings.logging.rotate_size_mb,
    retain_count=settings.logging.retain_count,
)

from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository

# Import all routers
from src.api.auth import router as auth_router
from src.api.user_profile import router as user_profile_router
from src.api.trading_buddy import router as trading_buddy_router
from src.api.broker import router as broker_router
from src.api.alpaca import router as alpaca_router
from src.api.campaigns import router as campaigns_router
from src.api.strategies import router as strategies_router
from src.api.journal import router as journal_router
from src.api.strategy_probe import router as strategy_probe_router
from src.api.ohlcv import router as ohlcv_router
from src.api.features_api import router as features_router
from src.api.regimes import router as regimes_router
from src.api.data_sync import router as data_sync_router
from src.api.analysis import router as analysis_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Regime State Visualization API", version="1.0.0")

# MarketDataOrchestrator instance (set during startup)
_market_data_orchestrator = None
# ReviewerOrchestrator instance (set during startup)
_reviewer_orchestrator = None


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _startup_market_data_orchestrator():
    """Start the MarketDataOrchestrator so messaging-based data requests work."""
    global _market_data_orchestrator
    try:
        from src.marketdata.orchestrator import MarketDataOrchestrator

        provider = None
        if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
            try:
                from src.marketdata.alpaca_provider import AlpacaProvider
                provider = AlpacaProvider()
            except Exception as e:
                logger.warning("Failed to create AlpacaProvider for orchestrator: %s", e)

        if provider is None:
            logger.info("No market data provider available; MarketDataOrchestrator not started")
            return

        _market_data_orchestrator = MarketDataOrchestrator(provider)
        _market_data_orchestrator.start()
        logger.info("MarketDataOrchestrator started on app startup")
    except Exception as e:
        logger.warning("Failed to start MarketDataOrchestrator: %s", e)


@app.on_event("startup")
def _startup_reviewer_orchestrator():
    """Start the ReviewerOrchestrator so behavioral checks run via events."""
    global _reviewer_orchestrator
    try:
        from src.reviewer.orchestrator import ReviewerOrchestrator

        _reviewer_orchestrator = ReviewerOrchestrator()
        _reviewer_orchestrator.start()
        logger.info("ReviewerOrchestrator started on app startup")
    except Exception as e:
        logger.warning("Failed to start ReviewerOrchestrator: %s", e)


@app.on_event("shutdown")
def _shutdown_orchestrators():
    """Stop orchestrators and message bus cleanly."""
    global _market_data_orchestrator, _reviewer_orchestrator

    if _market_data_orchestrator is not None:
        _market_data_orchestrator.stop()
        _market_data_orchestrator = None
        logger.info("MarketDataOrchestrator stopped on app shutdown")

    if _reviewer_orchestrator is not None:
        _reviewer_orchestrator.stop()
        _reviewer_orchestrator = None
        logger.info("ReviewerOrchestrator stopped on app shutdown")

    try:
        from src.messaging.bus import get_message_bus
        bus = get_message_bus()
        bus.shutdown()
        logger.info("MessageBus shut down on app shutdown")
    except Exception as e:
        logger.warning("Failed to shut down MessageBus: %s", e)


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(user_profile_router)
app.include_router(trading_buddy_router)
app.include_router(broker_router)
app.include_router(alpaca_router)
app.include_router(campaigns_router)
app.include_router(strategies_router)
app.include_router(journal_router)
app.include_router(strategy_probe_router)
app.include_router(ohlcv_router)
app.include_router(features_router)
app.include_router(regimes_router)
app.include_router(data_sync_router)
app.include_router(analysis_router)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Go-strats compatible endpoints (/api/bars, /api/indicators)
# NOTE: These remain unauthenticated — the Go client is an internal service
# that does not send JWT tokens. Consider adding API-key auth for
# machine-to-machine calls if these are exposed externally.
# ---------------------------------------------------------------------------


@app.get("/api/bars")
async def get_bars_for_go(
    symbol: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_timestamp: Optional[str] = Query(None, description="Start timestamp (ISO 8601)"),
    end_timestamp: Optional[str] = Query(None, description="End timestamp (ISO 8601)"),
):
    """Return OHLCV bars in the format expected by go-strats backend client."""
    symbol = symbol.upper()
    logger.info(
        "GET /api/bars: symbol=%s, timeframe=%s, start=%s, end=%s",
        symbol, timeframe, start_timestamp, end_timestamp,
    )

    try:
        with get_db_manager().get_session() as session:
            repo = OHLCVRepository(session)

            start = datetime.fromisoformat(start_timestamp) if start_timestamp else None
            end = datetime.fromisoformat(end_timestamp) if end_timestamp else None
            if start and start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            if end and end.tzinfo is not None:
                end = end.replace(tzinfo=None)

            df = repo.get_bars(symbol, timeframe, start=start, end=end)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No bars for {symbol}/{timeframe}")

        bars = []
        for ts, row in df.iterrows():
            bars.append({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(bars),
            "bars": bars,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /api/bars: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/indicators")
async def get_indicators_for_go(
    symbol: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_timestamp: Optional[str] = Query(None, description="Start timestamp (ISO 8601)"),
    end_timestamp: Optional[str] = Query(None, description="End timestamp (ISO 8601)"),
):
    """Return computed indicators in the format expected by go-strats backend client."""
    symbol = symbol.upper()
    logger.info(
        "GET /api/indicators: symbol=%s, timeframe=%s, start=%s, end=%s",
        symbol, timeframe, start_timestamp, end_timestamp,
    )

    try:
        with get_db_manager().get_session() as session:
            repo = OHLCVRepository(session)

            start = datetime.fromisoformat(start_timestamp) if start_timestamp else None
            end = datetime.fromisoformat(end_timestamp) if end_timestamp else None
            if start and start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            if end and end.tzinfo is not None:
                end = end.replace(tzinfo=None)

            features_df = repo.get_features(symbol, timeframe, start=start, end=end)

        if features_df.empty:
            logger.info("No stored features for %s/%s, computing from OHLCV", symbol, timeframe)
            with get_db_manager().get_session() as session:
                repo = OHLCVRepository(session)
                ohlcv_df = repo.get_bars(symbol, timeframe, start=start, end=end)

            if ohlcv_df.empty:
                raise HTTPException(status_code=404, detail=f"No data for {symbol}/{timeframe}")

            from src.features.talib_indicators import TALibIndicatorCalculator
            calculator = TALibIndicatorCalculator()
            features_df = calculator.compute(ohlcv_df)

        indicator_names = sorted(features_df.columns.tolist())
        rows = []
        for ts, row in features_df.iterrows():
            indicators = {}
            for col in indicator_names:
                val = row[col]
                if pd.notna(val) and not (isinstance(val, float) and (np.isinf(val) or np.isnan(val))):
                    indicators[col] = float(val)
            rows.append({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "indicators": indicators,
            })

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(rows),
            "indicator_names": indicator_names,
            "rows": rows,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /api/indicators: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Cache and health endpoints
# ---------------------------------------------------------------------------


@app.delete("/api/cache")
async def clear_cache(_user_id: int = Depends(get_current_user)):
    """Clear the data cache."""
    clear_all_cache()
    return {"message": "Cache cleared"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint including database connectivity."""
    health = {
        "status": "healthy",
        "api": True,
        "database": False,
        "redis": False,
        "alpaca": False,
    }

    try:
        db_manager = get_db_manager()
        health["database"] = db_manager.health_check()
    except Exception as e:
        logger.error("Database health check failed: %s", e)

    try:
        from src.messaging.bus import get_message_bus
        bus = get_message_bus()
        health["redis"] = bus.health_check()
    except Exception as e:
        logger.error("Redis health check failed: %s", e)

    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        health["alpaca"] = True

    if not health["database"]:
        health["status"] = "degraded"

    return health


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
