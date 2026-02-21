"""FastAPI router for OHLCV data endpoints.

Provides endpoints for loading OHLCV bar data, listing tickers,
and viewing data summaries.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth_middleware import get_current_user
from src.api._data_helpers import (
    get_cached_data,
    get_cache_keys,
    get_database_loader,
    load_ohlcv_internal,
    set_cached_data,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ohlcv"])

DATA_DIR = PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class DataSourceInfo(BaseModel):
    """Information about available data sources."""
    name: str
    type: str
    path: Optional[str] = None


class OHLCVResponse(BaseModel):
    """OHLCV data response."""
    timestamps: list[str]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    oldest_available: Optional[str] = None
    newest_available: Optional[str] = None


class TickerInfo(BaseModel):
    """Information about a ticker in the database."""
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    is_active: bool = True
    timeframes: list[str] = []


class DataSummaryResponse(BaseModel):
    """Data summary for a symbol."""
    symbol: str
    timeframes: dict


class StatisticsResponse(BaseModel):
    """Statistics summary response."""
    ohlcv_stats: dict
    feature_stats: dict
    regime_stats: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/sources", response_model=list[DataSourceInfo])
async def get_data_sources(_user_id: int = Depends(get_current_user)):
    """Get list of available data sources."""
    sources = []

    try:
        db_loader = get_database_loader()
        db_tickers = db_loader.get_available_tickers()
        for ticker in db_tickers:
            sources.append(DataSourceInfo(name=ticker, type="database", path=None))
    except Exception as e:
        logger.warning("Failed to list database tickers: %s", e)

    if DATA_DIR.exists():
        for csv_file in DATA_DIR.glob("*.csv"):
            sources.append(DataSourceInfo(name=csv_file.stem, type="local", path=str(csv_file)))

    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        for ticker in ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "QQQ", "IWM"]:
            if ticker not in [s.name for s in sources]:
                sources.append(DataSourceInfo(name=ticker, type="alpaca", path=None))

    return sources


@router.get("/api/ohlcv/{symbol}")
async def get_ohlcv_data(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe (1Min, 15Min, 1Hour, 1Day)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: Optional[int] = Query(None, description="Max bars to return (newest N)"),
    _user_id: int = Depends(get_current_user),
):
    """Load OHLCV data for a ticker symbol.

    Data is loaded from the PostgreSQL database. If data is not available for the
    requested range, it will be automatically fetched from Alpaca API (if configured)
    and stored in the database before returning.

    Use ``limit`` to cap the number of bars returned (keeps the newest N).
    """
    logger.info(
        "OHLCV request received: symbol=%s, timeframe=%s, start=%s, end=%s, limit=%s",
        symbol, timeframe, start_date, end_date, limit,
    )

    cache_key = f"ohlcv_{symbol}_{timeframe}_{start_date}_{end_date}_{limit}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        logger.info("OHLCV cache hit for %s/%s", symbol, timeframe)
        return cached

    try:
        response = await load_ohlcv_internal(symbol, timeframe, start_date, end_date, limit=limit)
        set_cached_data(cache_key, response)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error loading OHLCV data: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/tickers", response_model=list[TickerInfo])
async def list_tickers(_user_id: int = Depends(get_current_user)):
    """List all tickers stored in the database."""
    try:
        db_loader = get_database_loader()
        tickers = db_loader.get_available_tickers()

        result = []
        for symbol in tickers:
            summary = db_loader.get_data_summary(symbol)
            result.append(TickerInfo(symbol=symbol, timeframes=list(summary.keys())))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing tickers: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/tickers/{symbol}/summary", response_model=DataSummaryResponse)
async def get_ticker_summary(symbol: str, _user_id: int = Depends(get_current_user)):
    """Get data summary for a specific ticker."""
    try:
        db_loader = get_database_loader()
        summary = db_loader.get_data_summary(symbol.upper())

        formatted_summary = {}
        for timeframe, data in summary.items():
            formatted_summary[timeframe] = {
                "earliest": data["earliest"].isoformat() if data.get("earliest") else None,
                "latest": data["latest"].isoformat() if data.get("latest") else None,
                "bar_count": data.get("bar_count", 0),
            }

        return DataSummaryResponse(symbol=symbol.upper(), timeframes=formatted_summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting ticker summary: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/statistics/{symbol}")
async def get_statistics(
    symbol: str,
    timeframe: str = Query("1Min", description="Bar timeframe"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _user_id: int = Depends(get_current_user),
):
    """Get comprehensive statistics summary."""
    await load_ohlcv_internal(symbol, timeframe, start_date, end_date)

    try:
        from src.api._data_helpers import _cache_lock

        df = get_cached_data(f"df_{symbol.upper()}")
        features_df = get_cached_data(f"features_df_{symbol.upper()}")

        ohlcv_stats = {
            "total_bars": len(df),
            "date_range": {
                "start": df.index.min().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": df.index.max().strftime("%Y-%m-%dT%H:%M:%SZ"),
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
            },
        }

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

        regime_stats = {}
        regime_cache_key = None
        for key in get_cache_keys():
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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error computing statistics: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
