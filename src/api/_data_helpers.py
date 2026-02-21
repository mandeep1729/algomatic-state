"""Shared utilities for API routers: cache, database loader, internal helpers.

This module provides common functionality used across multiple API routers:
- Thread-safe TTL cache for request-level caching
- Database loader factory with optional Alpaca integration
- Internal helpers for OHLCV loading and feature computation
"""

import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from cachetools import TTLCache
from fastapi import HTTPException
from pydantic import BaseModel

from config.settings import get_settings
from src.data.database.dependencies import grpc_market_client
from src.data.database.models import VALID_TIMEFRAMES
from src.data.loaders.database_loader import DatabaseLoader
from src.features.pipeline import FeaturePipeline

logger = logging.getLogger(__name__)

# Determine project root directory for consistent path resolution
PROJECT_ROOT = Path(__file__).parent.parent.parent

# ---------------------------------------------------------------------------
# Thread-safe cache with TTL and size limits
# ---------------------------------------------------------------------------

_cache: TTLCache = TTLCache(maxsize=500, ttl=300)
_cache_lock = threading.RLock()


def get_cached_data(key: str):
    """Get data from cache (thread-safe)."""
    with _cache_lock:
        return _cache.get(key)


def set_cached_data(key: str, data):
    """Set data in cache (thread-safe)."""
    with _cache_lock:
        _cache[key] = data


def invalidate_cache_for_symbol(symbol: str):
    """Remove all cached entries for a symbol (thread-safe)."""
    upper = symbol.upper()
    with _cache_lock:
        keys_to_remove = [k for k in _cache if upper in k.upper()]
        for k in keys_to_remove:
            del _cache[k]


def clear_all_cache():
    """Clear entire cache (thread-safe)."""
    with _cache_lock:
        _cache.clear()


def get_cache_keys() -> list[str]:
    """Get all cache keys (thread-safe snapshot)."""
    with _cache_lock:
        return list(_cache.keys())


# ---------------------------------------------------------------------------
# Database loader factory
# ---------------------------------------------------------------------------


def get_database_loader() -> DatabaseLoader:
    """Get database loader with optional Alpaca integration."""
    alpaca_loader = None
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        try:
            from src.data.loaders.alpaca_loader import AlpacaLoader
            alpaca_loader = AlpacaLoader(use_cache=False, validate=True)
        except Exception as e:
            logger.warning("Failed to initialize Alpaca loader: %s", e)
    return DatabaseLoader(alpaca_loader=alpaca_loader, validate=True, auto_fetch=True)


# ---------------------------------------------------------------------------
# Shared response models
# ---------------------------------------------------------------------------


class ComputeFeaturesResponse(BaseModel):
    """Response for compute features endpoint."""
    symbol: str
    timeframes_processed: int
    timeframes_skipped: int
    features_stored: int
    message: str


# ---------------------------------------------------------------------------
# Internal helpers shared across routers
# ---------------------------------------------------------------------------


async def load_ohlcv_internal(
    symbol: str,
    timeframe: str = "1Min",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Load OHLCV data from database (auto-fetching from Alpaca if needed).

    Shared helper used by OHLCV, features, regimes, and analysis routers.
    """
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of {list(VALID_TIMEFRAMES)}"
        )

    loader = get_database_loader()
    logger.info(
        "Loading OHLCV for %s, timeframe=%s, alpaca_loader=%s",
        symbol, timeframe, loader.alpaca_loader is not None,
    )

    settings = get_settings()
    history_days = settings.data.history_months * 30
    end = datetime.fromisoformat(end_date) if end_date else datetime.now()
    start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=history_days)
    if end <= start:
        end = start + timedelta(days=1)
    logger.info("Date range: %s to %s", start, end)

    df = loader.load(symbol.upper(), start=start, end=end, timeframe=timeframe)
    logger.info("Loaded %d rows for %s", len(df), symbol)

    if df.empty:
        logger.warning("No data found for %s in range %s to %s", symbol, start, end)
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {symbol}. Ensure Alpaca API is configured or import data manually."
        )

    response = {
        "timestamps": df.index.strftime("%Y-%m-%dT%H:%M:%SZ").tolist(),
        "open": df["open"].tolist(),
        "high": df["high"].tolist(),
        "low": df["low"].tolist(),
        "close": df["close"].tolist(),
        "volume": df["volume"].tolist(),
    }

    set_cached_data(f"df_{symbol}", df)
    return response


async def get_features_internal(
    symbol: str,
    timeframe: str = "1Min",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Compute and return features for a symbol.

    Shared helper used by features and regimes routers.
    """
    await load_ohlcv_internal(symbol, timeframe, start_date, end_date)

    cache_key = f"features_{symbol}_{timeframe}_{start_date}_{end_date}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    df = get_cached_data(f"df_{symbol.upper()}")
    if df is None:
        raise HTTPException(status_code=400, detail="OHLCV data not loaded")

    pipeline = FeaturePipeline.default()
    features_df = pipeline.compute(df)

    set_cached_data(f"features_df_{symbol.upper()}", features_df)

    response = {
        "timestamps": features_df.index.strftime("%Y-%m-%dT%H:%M:%SZ").tolist(),
        "features": {
            col: features_df[col].replace([np.inf, -np.inf], np.nan).fillna(0).tolist()
            for col in features_df.columns
        },
        "feature_names": features_df.columns.tolist(),
    }

    set_cached_data(cache_key, response)
    return response


async def compute_features_internal(
    symbol: str, force: bool = False,
) -> ComputeFeaturesResponse:
    """Compute features for all timeframes of a ticker.

    Shared helper used by features and analysis routers.
    Uses gRPC to communicate with the data-service.

    Args:
        symbol: Ticker symbol.
        force: If True, recompute features for all bars.
    """
    pipeline = FeaturePipeline.default()

    stats = {
        "timeframes_processed": 0,
        "timeframes_skipped": 0,
        "features_stored": 0,
    }

    with grpc_market_client() as repo:
        ticker = repo.get_or_create_ticker(symbol.upper())

        for timeframe in VALID_TIMEFRAMES:
            df = repo.get_bars(symbol.upper(), timeframe)
            if df.empty:
                continue

            if force:
                missing_timestamps = set(
                    ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
                    for ts in df.index
                )
                logger.info("  %s: Force recomputing features for %d bars", timeframe, len(df))
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
                    logger.info("  %s: All %d bars already have features", timeframe, len(df))
                    continue

                logger.info(
                    "  %s: Computing features for %d bars (out of %d total)",
                    timeframe, len(missing_timestamps), len(df),
                )

            features_df = pipeline.compute_incremental(df, new_bars=len(missing_timestamps))
            if features_df.empty:
                continue

            features_df_filtered = features_df[
                features_df.index.map(
                    lambda ts: (ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts)
                    in missing_timestamps
                )
            ]

            if features_df_filtered.empty:
                continue

            rows_stored = repo.store_features(
                features_df=features_df_filtered,
                ticker_id=ticker.id,
                timeframe=timeframe,
                version="v1.0",
            )

            stats["timeframes_processed"] += 1
            stats["features_stored"] += rows_stored
            logger.info("  %s: Stored %d feature rows", timeframe, rows_stored)

    return ComputeFeaturesResponse(
        symbol=symbol.upper(),
        timeframes_processed=stats["timeframes_processed"],
        timeframes_skipped=stats["timeframes_skipped"],
        features_stored=stats["features_stored"],
        message=f"Computed features for {symbol.upper()}: {stats['features_stored']} rows stored",
    )
