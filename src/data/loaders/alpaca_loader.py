"""Alpaca API data loader for historical market data.

This module is a backward-compatible wrapper around
:class:`~src.marketdata.alpaca_provider.AlpacaProvider`.  It adds caching
and schema validation on top of the provider's fetch logic.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.cache import DataCache
from src.data.loaders.base import BaseDataLoader
from src.data.schemas import validate_ohlcv
from src.marketdata.alpaca_provider import AlpacaProvider
from src.marketdata.utils import RateLimiter  # noqa: F401 — re-export for backward compat

logger = logging.getLogger(__name__)


class AlpacaLoader(BaseDataLoader):
    """Load historical OHLCV data from Alpaca Markets API.

    Features:
    - API authentication via environment variables or direct credentials
    - Automatic pagination for large date ranges
    - Rate limiting to avoid API throttling
    - Retry logic with exponential backoff
    - Caching to parquet files
    """

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        cache_dir: str | Path = "data/cache",
        use_cache: bool = True,
        validate: bool = True,
        rate_limit: int = 200,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass directly."
            )

        self._provider = AlpacaProvider(
            api_key=self.api_key,
            secret_key=self.secret_key,
            rate_limit=rate_limit,
            max_retries=max_retries,
        )
        # Pass configured max_cache_age_hours so stale data is auto-expired
        try:
            from config.settings import get_settings
            max_age = get_settings().data.max_cache_age_hours
        except Exception:
            max_age = 24
        self.cache = DataCache(cache_dir, max_cache_age_hours=max_age) if use_cache else None
        self.use_cache = use_cache
        self.validate = validate

    def load(
        self,
        source: str | Path,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Load historical OHLCV data for a symbol.

        Args:
            source: Stock symbol (e.g., "AAPL", "SPY")
            start: Start datetime (required)
            end: End datetime (defaults to now)

        Returns:
            DataFrame with datetime index and columns: open, high, low, close, volume

        Raises:
            ValueError: If start date not provided or invalid symbol
        """
        symbol = str(source).upper()

        if start is None:
            raise ValueError("Start date is required for Alpaca API requests")

        if end is None:
            end = datetime.now()

        # Check cache first
        if self.use_cache and self.cache:
            cached = self.cache.get(symbol, start, end)
            if cached is not None:
                return cached

        # Delegate to provider
        df = self._provider.fetch_1min_bars(symbol, start, end)

        if df.empty:
            return df

        # Validate schema
        if self.validate:
            df = validate_ohlcv(df)

        # Cache the result
        if self.use_cache and self.cache:
            self.cache.put(symbol, start, end, df)

        return df

    def load_multiple(
        self,
        sources: list[str | Path],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Load historical data for multiple symbols.

        Args:
            sources: List of stock symbols
            start: Start datetime (required)
            end: End datetime (defaults to now)

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        result = {}
        for source in sources:
            symbol = str(source).upper()
            try:
                result[symbol] = self.load(symbol, start, end)
            except Exception as e:
                logger.warning("Failed to load %s: %s", symbol, e)
                result[symbol] = pd.DataFrame()
        return result
