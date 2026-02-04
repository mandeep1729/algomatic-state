"""Alpaca market data provider."""

import logging
import os
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.marketdata.base import MarketDataProvider
from src.marketdata.utils import (
    RateLimiter,
    ensure_timezone_naive,
    fetch_with_retry,
    generate_date_chunks,
    normalize_ohlcv,
)

logger = logging.getLogger(__name__)

RESOLUTION_MAP = {
    "1Min": TimeFrame.Minute,
    "1Day": TimeFrame.Day,
}

MAX_DAYS_PER_CHUNK = 25


class AlpacaProvider(MarketDataProvider):
    """Fetch OHLCV bars from the Alpaca Markets API.

    Uses the ``alpaca-py`` SDK with shared rate-limiting, retry, and
    pagination utilities.
    """

    source_name = "alpaca"

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
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

        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.rate_limiter = RateLimiter(rate_limit)
        self.max_retries = max_retries

    def fetch_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        resolution: str = "1Min",
    ) -> pd.DataFrame:
        symbol = symbol.upper()
        timeframe = RESOLUTION_MAP.get(resolution)
        if timeframe is None:
            raise ValueError(
                f"Unsupported resolution '{resolution}'. "
                f"Supported: {list(RESOLUTION_MAP)}"
            )

        chunks = generate_date_chunks(start, end, MAX_DAYS_PER_CHUNK)
        all_data: list[pd.DataFrame] = []

        for chunk_start, chunk_end in chunks:
            chunk_df = self._fetch_chunk(symbol, chunk_start, chunk_end, timeframe)
            if not chunk_df.empty:
                all_data.append(chunk_df)
                # Advance past last received bar for 1Min to avoid duplication
                if resolution == "1Min":
                    last_ts = chunk_df.index.max()
                    next_start = last_ts + timedelta(minutes=1)
                    if next_start > chunk_end:
                        continue

        if not all_data:
            return pd.DataFrame()

        df = pd.concat(all_data)
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        return normalize_ohlcv(df)

    def _fetch_chunk(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: TimeFrame,
    ) -> pd.DataFrame:
        """Fetch a single chunk with retry."""

        def _call() -> pd.DataFrame:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                feed=DataFeed.IEX,
            )
            bars = self.client.get_stock_bars(request)

            if symbol not in bars.data or not bars.data[symbol]:
                return pd.DataFrame()

            df = bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level="symbol")
            return ensure_timezone_naive(df)

        return fetch_with_retry(_call, self.max_retries, self.rate_limiter)
