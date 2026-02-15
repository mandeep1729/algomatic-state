"""Caching layer for market data."""

import hashlib
import logging
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """File-based cache for market data using pickle format.

    Caches data by symbol and date range to avoid redundant API calls.
    """

    def __init__(self, cache_dir: str | Path = "data/cache"):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cached files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
    ) -> str:
        """Generate a unique cache key for the request.

        Args:
            symbol: Stock symbol
            start: Start datetime
            end: End datetime
            timeframe: Bar timeframe

        Returns:
            Cache key string
        """
        # Uppercase symbol for case-insensitive matching
        key_str = f"{symbol.upper()}_{start.isoformat()}_{end.isoformat()}_{timeframe}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def _get_cache_path(self, symbol: str, cache_key: str) -> Path:
        """Get the cache file path.

        Args:
            symbol: Stock symbol
            cache_key: Unique cache key

        Returns:
            Path to cache file
        """
        symbol_dir = self.cache_dir / symbol.upper()
        symbol_dir.mkdir(exist_ok=True)
        return symbol_dir / f"{cache_key}.pkl"

    def get(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
    ) -> pd.DataFrame | None:
        """Retrieve cached data if available.

        Args:
            symbol: Stock symbol
            start: Start datetime
            end: End datetime
            timeframe: Bar timeframe

        Returns:
            Cached DataFrame or None if not found
        """
        cache_key = self._get_cache_key(symbol, start, end, timeframe)
        cache_path = self._get_cache_path(symbol, cache_key)

        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    data = pickle.load(f)
                logger.debug("Cache hit for %s", symbol)
                return data
            except Exception:
                logger.warning(
                    "Corrupted cache file for %s, removing %s",
                    symbol, cache_path, exc_info=True,
                )
                cache_path.unlink(missing_ok=True)
                return None
        return None

    def put(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        data: pd.DataFrame,
        timeframe: str = "1Min",
    ) -> Path:
        """Store data in cache.

        Args:
            symbol: Stock symbol
            start: Start datetime
            end: End datetime
            data: DataFrame to cache
            timeframe: Bar timeframe

        Returns:
            Path to cached file
        """
        cache_key = self._get_cache_key(symbol, start, end, timeframe)
        cache_path = self._get_cache_path(symbol, cache_key)

        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
        logger.debug("Cached %s (%d rows) to %s", symbol, len(data), cache_path)
        return cache_path

    def clear(self, symbol: str | None = None) -> int:
        """Clear cached data.

        Args:
            symbol: Optional symbol to clear. If None, clears all cache.

        Returns:
            Number of files removed
        """
        count = 0
        if symbol:
            symbol_dir = self.cache_dir / symbol.upper()
            if symbol_dir.exists():
                for f in symbol_dir.glob("*.pkl"):
                    f.unlink()
                    count += 1
        else:
            for f in self.cache_dir.rglob("*.pkl"):
                f.unlink()
                count += 1
        logger.info("Cleared %d cache files%s", count, f" for {symbol}" if symbol else "")
        return count

    def list_cached(self, symbol: str | None = None) -> list[dict]:
        """List cached entries.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of cache entry metadata
        """
        entries = []
        search_path = self.cache_dir / symbol.upper() if symbol else self.cache_dir

        for f in search_path.rglob("*.pkl"):
            try:
                with open(f, "rb") as fh:
                    df = pickle.load(fh)
                entries.append({
                    "symbol": f.parent.name,
                    "file": f.name,
                    "rows": len(df),
                    "start": df.index.min() if len(df) > 0 else None,
                    "end": df.index.max() if len(df) > 0 else None,
                    "size_kb": f.stat().st_size / 1024,
                })
            except Exception:
                logger.debug("Failed to read cache file %s, skipping", f, exc_info=True)
                continue

        return entries
