"""FastAPI backend for regime state visualization UI."""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging to show application logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.loaders.csv_loader import CSVLoader
from src.data.loaders.database_loader import DatabaseLoader
from src.data.database.connection import get_db_manager
from src.data.database.models import VALID_TIMEFRAMES
from src.features.pipeline import FeaturePipeline, get_minimal_features

logger = logging.getLogger(__name__)

app = FastAPI(title="Regime State Visualization API", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"


class DataSourceInfo(BaseModel):
    """Information about available data sources."""
    name: str
    type: str  # "local" or "alpaca"
    path: Optional[str] = None


class OHLCVResponse(BaseModel):
    """OHLCV data response."""
    timestamps: list[str]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]


class FeatureResponse(BaseModel):
    """Feature data response."""
    timestamps: list[str]
    features: dict[str, list[float]]
    feature_names: list[str]


class RegimeResponse(BaseModel):
    """Regime state response."""
    timestamps: list[str]
    regime_labels: list[int]
    regime_info: list[dict]
    transition_matrix: list[list[float]]


class StatisticsResponse(BaseModel):
    """Statistics summary response."""
    ohlcv_stats: dict
    feature_stats: dict
    regime_stats: dict


class TickerInfo(BaseModel):
    """Information about a ticker in the database."""
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    is_active: bool = True
    timeframes: list[str] = []


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


class DataSummaryResponse(BaseModel):
    """Data summary for a symbol."""
    symbol: str
    timeframes: dict


# Helper functions
def get_database_loader() -> DatabaseLoader:
    """Get database loader with optional Alpaca integration."""
    alpaca_loader = None
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        try:
            from src.data.loaders.alpaca_loader import AlpacaLoader
            alpaca_loader = AlpacaLoader(use_cache=False, validate=True)
        except Exception as e:
            logger.warning(f"Failed to initialize Alpaca loader: {e}")
    return DatabaseLoader(alpaca_loader=alpaca_loader, validate=True, auto_fetch=True)


# Cache for loaded data and computed states
_cache = {}


def get_cached_data(key: str):
    """Get data from cache."""
    return _cache.get(key)


def set_cached_data(key: str, data):
    """Set data in cache."""
    _cache[key] = data


@app.get("/api/sources", response_model=list[DataSourceInfo])
async def get_data_sources():
    """Get list of available data sources."""
    sources = []

    # List tickers from database
    try:
        db_loader = get_database_loader()
        db_tickers = db_loader.get_available_tickers()
        for ticker in db_tickers:
            sources.append(DataSourceInfo(
                name=ticker,
                type="database",
                path=None
            ))
    except Exception as e:
        logger.warning(f"Failed to list database tickers: {e}")

    # List local CSV files
    if DATA_DIR.exists():
        for csv_file in DATA_DIR.glob("*.csv"):
            sources.append(DataSourceInfo(
                name=csv_file.stem,
                type="local",
                path=str(csv_file)
            ))

    # Check if Alpaca credentials are available (for direct Alpaca queries)
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        # Add common tickers for Alpaca (these can be synced to database)
        for ticker in ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "QQQ", "IWM"]:
            # Only add if not already in database
            if ticker not in [s.name for s in sources]:
                sources.append(DataSourceInfo(
                    name=ticker,
                    type="alpaca",
                    path=None
                ))

    return sources


@app.get("/api/ohlcv/{symbol}")
async def get_ohlcv_data(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Load OHLCV data for a ticker symbol.

    Data is loaded from the PostgreSQL database. If data is not available for the
    requested range, it will be automatically fetched from Alpaca API (if configured)
    and stored in the database before returning.

    All chart data always comes from the ohlcv_bars table.
    """
    cache_key = f"ohlcv_{symbol}_{timeframe}_{start_date}_{end_date}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        if timeframe not in VALID_TIMEFRAMES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
            )

        # Always use database loader with auto-fetch from Alpaca
        loader = get_database_loader()
        logger.info(f"Loading OHLCV for {symbol}, timeframe={timeframe}, alpaca_loader={loader.alpaca_loader is not None}")

        # Default to last 30 days if no dates specified
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()
        start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=30)
        logger.info(f"Date range: {start} to {end}")

        # This will:
        # 1. Check if data exists in database for the requested range
        # 2. If not, fetch from Alpaca (if configured) and store in ohlcv_bars
        # 3. Return data from database
        df = loader.load(symbol.upper(), start=start, end=end, timeframe=timeframe)
        logger.info(f"Loaded {len(df)} rows for {symbol}")

        if df.empty:
            logger.warning(f"No data found for {symbol} in range {start} to {end}")
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol}. Ensure Alpaca API is configured or import data manually."
            )

        response = {
            "timestamps": df.index.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            "open": df["open"].tolist(),
            "high": df["high"].tolist(),
            "low": df["low"].tolist(),
            "close": df["close"].tolist(),
            "volume": df["volume"].tolist(),
        }

        # Store raw dataframe in cache for feature computation
        set_cached_data(f"df_{symbol}", df)
        set_cached_data(cache_key, response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error loading OHLCV data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/features/{symbol}")
async def get_features(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Compute and return features for the data."""
    # First ensure OHLCV data is loaded
    await get_ohlcv_data(symbol, timeframe, start_date, end_date)

    cache_key = f"features_{symbol}_{timeframe}_{start_date}_{end_date}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    try:
        df = get_cached_data(f"df_{symbol.upper()}")
        if df is None:
            raise HTTPException(status_code=400, detail="OHLCV data not loaded")

        # Compute features
        pipeline = FeaturePipeline.default()
        features_df = pipeline.compute(df)

        # Store for regime computation
        set_cached_data(f"features_df_{symbol.upper()}", features_df)

        # Convert to response format
        response = {
            "timestamps": features_df.index.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            "features": {col: features_df[col].replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
                        for col in features_df.columns},
            "feature_names": features_df.columns.tolist(),
        }

        set_cached_data(cache_key, response)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/regimes/{symbol}")
async def get_regimes(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    n_clusters: int = Query(5, ge=2, le=10),
    window_size: int = Query(60, ge=10, le=200),
    n_components: int = Query(8, ge=2, le=20),
):
    """Compute and return regime states.

    NOTE: This endpoint is temporarily disabled while the state vector
    and HMM regime tracking system is being reimplemented.
    """
    raise HTTPException(
        status_code=501,
        detail="Regime computation is being reimplemented. See docs/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md"
    )


@app.get("/api/statistics/{symbol}")
async def get_statistics(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get comprehensive statistics summary."""
    # Load data first
    await get_ohlcv_data(symbol, timeframe, start_date, end_date)

    try:
        df = get_cached_data(f"df_{symbol.upper()}")
        features_df = get_cached_data(f"features_df_{symbol.upper()}")

        # OHLCV statistics
        ohlcv_stats = {
            "total_bars": len(df),
            "date_range": {
                "start": df.index.min().strftime("%Y-%m-%d %H:%M:%S"),
                "end": df.index.max().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "price": {
                "min": float(df["low"].min()),
                "max": float(df["high"].max()),
                "mean": float(df["close"].mean()),
                "std": float(df["close"].std()),
                "current": float(df["close"].iloc[-1]),
            },
            "volume": {
                "min": float(df["volume"].min()),
                "max": float(df["volume"].max()),
                "mean": float(df["volume"].mean()),
                "total": float(df["volume"].sum()),
            },
            "returns": {
                "total_return": float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100),
                "daily_volatility": float(df["close"].pct_change().std() * 100),
            }
        }

        # Feature statistics
        feature_stats = {}
        if features_df is not None:
            for col in features_df.columns:
                series = features_df[col].replace([np.inf, -np.inf], np.nan).dropna()
                if len(series) > 0:
                    feature_stats[col] = {
                        "min": float(series.min()),
                        "max": float(series.max()),
                        "mean": float(series.mean()),
                        "std": float(series.std()),
                        "median": float(series.median()),
                    }

        # Regime statistics (if computed)
        regime_stats = {}
        regime_cache_key = None
        for key in _cache.keys():
            if key.startswith(f"regimes_{symbol.upper()}"):
                regime_cache_key = key
                break

        if regime_cache_key:
            regime_data = get_cached_data(regime_cache_key)
            if regime_data:
                regime_stats = {
                    "n_regimes": len(regime_data.get("regime_info", [])),
                    "regimes": regime_data.get("regime_info", []),
                    "explained_variance": regime_data.get("explained_variance"),
                }

        return {
            "ohlcv_stats": ohlcv_stats,
            "feature_stats": feature_stats,
            "regime_stats": regime_stats,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache")
async def clear_cache():
    """Clear the data cache."""
    global _cache
    _cache = {}
    return {"message": "Cache cleared"}


# =============================================================================
# Database-specific endpoints
# =============================================================================


@app.get("/api/tickers", response_model=list[TickerInfo])
async def list_tickers():
    """List all tickers stored in the database."""
    try:
        db_loader = get_database_loader()
        tickers = db_loader.get_available_tickers()

        result = []
        for symbol in tickers:
            summary = db_loader.get_data_summary(symbol)
            result.append(TickerInfo(
                symbol=symbol,
                timeframes=list(summary.keys()),
            ))
        return result
    except Exception as e:
        logger.exception(f"Error listing tickers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickers/{symbol}/summary", response_model=DataSummaryResponse)
async def get_ticker_summary(symbol: str):
    """Get data summary for a specific ticker."""
    try:
        db_loader = get_database_loader()
        summary = db_loader.get_data_summary(symbol.upper())

        # Convert datetime objects to strings
        formatted_summary = {}
        for timeframe, data in summary.items():
            formatted_summary[timeframe] = {
                "earliest": data["earliest"].isoformat() if data.get("earliest") else None,
                "latest": data["latest"].isoformat() if data.get("latest") else None,
                "bar_count": data.get("bar_count", 0),
            }

        return DataSummaryResponse(
            symbol=symbol.upper(),
            timeframes=formatted_summary,
        )
    except Exception as e:
        logger.exception(f"Error getting ticker summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync-status/{symbol}", response_model=list[SyncStatusResponse])
async def get_sync_status(symbol: str):
    """Get synchronization status for a symbol."""
    try:
        db_loader = get_database_loader()
        statuses = db_loader.get_sync_status(symbol.upper())

        if not statuses:
            # Return empty list if no sync logs exist
            return []

        return [SyncStatusResponse(**status) for status in statuses]
    except Exception as e:
        logger.exception(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/{symbol}")
async def trigger_sync(
    symbol: str,
    timeframe: str = Query("1Min", description="Timeframe to sync"),
    start_date: Optional[str] = Query(None, description="Start date for historical sync"),
    end_date: Optional[str] = Query(None, description="End date (defaults to now)"),
):
    """Trigger data synchronization for a symbol.

    This will fetch data from Alpaca and store it in the database.
    """
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
        )

    try:
        db_loader = get_database_loader()

        if db_loader.alpaca_loader is None:
            raise HTTPException(
                status_code=400,
                detail="Alpaca credentials not configured. Cannot sync data."
            )

        # Parse dates
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()
        start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=30)

        # Trigger sync by loading data (auto_fetch is enabled)
        df = db_loader.load(symbol.upper(), start=start, end=end, timeframe=timeframe)

        return {
            "message": f"Sync completed for {symbol.upper()}/{timeframe}",
            "bars_loaded": len(df),
            "date_range": {
                "start": df.index.min().isoformat() if not df.empty else None,
                "end": df.index.max().isoformat() if not df.empty else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error syncing data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ComputeFeaturesResponse(BaseModel):
    """Response for compute features endpoint."""
    symbol: str
    timeframes_processed: int
    timeframes_skipped: int
    features_stored: int
    message: str


@app.post("/api/compute-features/{symbol}")
async def compute_features(symbol: str, force: bool = False):
    """Compute technical indicators for all timeframes of a ticker.

    This computes indicators like RSI, MACD, Bollinger Bands, etc.
    and stores them in the computed_features table.

    Args:
        symbol: Ticker symbol
        force: If True, recompute features for all bars (overwrites existing)
    """
    try:
        from src.data.database.repository import OHLCVRepository
        from src.features import PandasTAIndicatorCalculator, PANDAS_TA_AVAILABLE
        from src.features import TALibIndicatorCalculator, TALIB_AVAILABLE

        # Get calculator (prefer TA-Lib, fall back to pandas-ta)
        calculator = None
        if TALIB_AVAILABLE:
            calculator = TALibIndicatorCalculator()
        elif PANDAS_TA_AVAILABLE:
            calculator = PandasTAIndicatorCalculator()
        else:
            raise HTTPException(
                status_code=500,
                detail="No indicator calculator available. Install TA-Lib or pandas-ta."
            )

        db_manager = get_db_manager()
        stats = {
            "timeframes_processed": 0,
            "timeframes_skipped": 0,
            "features_stored": 0,
        }

        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            # Get ticker
            ticker = repo.get_or_create_ticker(symbol.upper())

            for timeframe in VALID_TIMEFRAMES:
                # Get OHLCV data
                df = repo.get_bars(symbol.upper(), timeframe)
                if df.empty:
                    continue

                # Check existing features (skip if force=True)
                if force:
                    missing_timestamps = set(
                        ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
                        for ts in df.index
                    )
                    logger.info(f"  {timeframe}: Force recomputing features for {len(df)} bars")
                else:
                    existing_timestamps = repo.get_existing_feature_timestamps(
                        ticker_id=ticker.id,
                        timeframe=timeframe,
                    )

                    df_timestamps = set(
                        ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
                        for ts in df.index
                    )
                    missing_timestamps = df_timestamps - existing_timestamps

                    if not missing_timestamps:
                        stats["timeframes_skipped"] += 1
                        logger.info(f"  {timeframe}: All {len(df)} bars already have features")
                        continue

                    logger.info(
                        f"  {timeframe}: Computing features for {len(missing_timestamps)} bars "
                        f"(out of {len(df)} total)"
                    )

                # Compute indicators
                features_df = calculator.compute(df)
                if features_df.empty:
                    continue

                # Filter to only store new features
                features_df_filtered = features_df[
                    features_df.index.map(
                        lambda ts: (ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts)
                        in missing_timestamps
                    )
                ]

                if features_df_filtered.empty:
                    continue

                # Store features
                rows_stored = repo.store_features(
                    features_df=features_df_filtered,
                    ticker_id=ticker.id,
                    timeframe=timeframe,
                    version="v1.0",
                )

                stats["timeframes_processed"] += 1
                stats["features_stored"] += rows_stored
                logger.info(f"  {timeframe}: Stored {rows_stored} feature rows")

            session.commit()

        return ComputeFeaturesResponse(
            symbol=symbol.upper(),
            timeframes_processed=stats["timeframes_processed"],
            timeframes_skipped=stats["timeframes_skipped"],
            features_stored=stats["features_stored"],
            message=f"Computed features for {symbol.upper()}: {stats['features_stored']} rows stored"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error computing features: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/import")
async def import_data(
    symbol: str = Query(..., description="Symbol to import as"),
    file_path: str = Query(..., description="Path to CSV or Parquet file"),
    timeframe: str = Query("1Min", description="Timeframe of the data"),
):
    """Import data from a local file into the database."""
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
    except Exception as e:
        logger.exception(f"Error importing data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint including database connectivity."""
    health = {
        "status": "healthy",
        "api": True,
        "database": False,
        "alpaca": False,
    }

    # Check database
    try:
        db_manager = get_db_manager()
        health["database"] = db_manager.health_check()
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    # Check Alpaca
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        health["alpaca"] = True

    if not health["database"]:
        health["status"] = "degraded"

    return health


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
