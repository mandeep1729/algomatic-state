"""Alpaca API data loader for historical market data."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.data.cache import DataCache
from src.data.loaders.base import BaseDataLoader
from src.data.schemas import validate_ohlcv


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 200):
        """Initialize rate limiter.

        Args:
            calls_per_minute: Maximum API calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0.0

    def wait(self) -> None:
        """Wait if necessary to respect rate limits."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()


class AlpacaLoader(BaseDataLoader):
    """Load historical OHLCV data from Alpaca Markets API.

    Features:
    - API authentication via environment variables or direct credentials
    - Automatic pagination for large date ranges
    - Rate limiting to avoid API throttling
    - Retry logic with exponential backoff
    - Caching to parquet files
    """

    # Alpaca limits bars per request
    MAX_BARS_PER_REQUEST = 10000
    # Max days to request in one call (1 min bars = 390 bars/day)
    MAX_DAYS_PER_REQUEST = 25

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
        """Initialize the Alpaca loader.

        Args:
            api_key: Alpaca API key (defaults to ALPACA_API_KEY env var)
            secret_key: Alpaca secret key (defaults to ALPACA_SECRET_KEY env var)
            cache_dir: Directory for cached data
            use_cache: Whether to use caching
            validate: Whether to validate data against OHLCV schema
            rate_limit: API calls per minute limit
            max_retries: Maximum retry attempts on failure
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass directly."
            )

        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.cache = DataCache(cache_dir) if use_cache else None
        self.use_cache = use_cache
        self.validate = validate
        self.rate_limiter = RateLimiter(rate_limit)
        self.max_retries = max_retries

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

        # Fetch from API with pagination
        df = self._fetch_with_pagination(symbol, start, end)

        if df.empty:
            return df

        # Normalize column names
        df = self._normalize_columns(df)

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
                # Log error but continue with other symbols
                print(f"Warning: Failed to load {symbol}: {e}")
                result[symbol] = pd.DataFrame()
        return result

    def _fetch_with_pagination(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Fetch data with pagination for large date ranges.

        Args:
            symbol: Stock symbol
            start: Start datetime
            end: End datetime

        Returns:
            Combined DataFrame from all pages
        """
        all_data = []
        current_start = start

        while current_start < end:
            # Calculate chunk end date
            chunk_end = min(
                current_start + timedelta(days=self.MAX_DAYS_PER_REQUEST),
                end,
            )

            # Fetch chunk with retries
            chunk_df = self._fetch_with_retry(symbol, current_start, chunk_end)

            if not chunk_df.empty:
                all_data.append(chunk_df)
                # Move start to after the last bar received
                current_start = chunk_df.index.max() + timedelta(minutes=1)
            else:
                # No data for this period, move forward
                current_start = chunk_end

        if not all_data:
            return pd.DataFrame()

        # Combine all chunks
        df = pd.concat(all_data)
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()

        return df

    def _fetch_with_retry(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Fetch data with exponential backoff retry.

        Args:
            symbol: Stock symbol
            start: Start datetime
            end: End datetime

        Returns:
            DataFrame from API call
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self.rate_limiter.wait()

                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Minute,
                    start=start,
                    end=end,
                )

                bars = self.client.get_stock_bars(request)

                if symbol not in bars.data or not bars.data[symbol]:
                    return pd.DataFrame()

                # Convert to DataFrame
                df = bars.df

                # Handle multi-index if present
                if isinstance(df.index, pd.MultiIndex):
                    df = df.xs(symbol, level="symbol")

                # Remove timezone for consistent comparison with naive datetimes
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)

                return df

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    sleep_time = 2**attempt
                    time.sleep(sleep_time)

        raise RuntimeError(
            f"Failed to fetch {symbol} after {self.max_retries} attempts: {last_error}"
        )

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize Alpaca column names to standard OHLCV format.

        Args:
            df: Raw DataFrame from Alpaca

        Returns:
            DataFrame with standardized columns
        """
        # Alpaca returns: open, high, low, close, volume, trade_count, vwap
        # We explicitly drop 'vwap' and 'trade_count' here by not including them in ohlcv_cols
        df = df.copy()

        # Ensure index is named 'timestamp'
        df.index.name = "timestamp"

        # Select only OHLCV columns (strict schema)
        ohlcv_cols = ["open", "high", "low", "close", "volume"]
        available_cols = [c for c in ohlcv_cols if c in df.columns]

        if len(available_cols) != 5:
            raise ValueError(
                f"Missing required columns. Found: {df.columns.tolist()}"
            )

        return df[ohlcv_cols]
