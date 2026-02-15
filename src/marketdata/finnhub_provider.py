"""Finnhub market data provider."""

import logging
import os
from datetime import datetime

import finnhub
import pandas as pd

from src.marketdata.base import MarketDataProvider
from src.marketdata.utils import (
    RateLimiter,
    fetch_with_retry,
    generate_date_chunks,
    normalize_ohlcv,
)

logger = logging.getLogger(__name__)

# Finnhub resolution codes
RESOLUTION_MAP = {
    "1Min": "1",
    "1Day": "D",
}

MAX_DAYS_PER_CHUNK = 30


class FinnhubProvider(MarketDataProvider):
    """Fetch OHLCV bars from the Finnhub API.

    Uses the ``finnhub-python`` SDK.  The free tier allows 60 API
    calls/minute, so the default rate limit is conservative.
    """

    source_name = "finnhub"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit: int = 60,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Finnhub API key required. Set FINNHUB_API_KEY environment "
                "variable or pass directly."
            )

        self.client = finnhub.Client(api_key=self.api_key)
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
        fh_resolution = RESOLUTION_MAP.get(resolution)
        if fh_resolution is None:
            raise ValueError(
                f"Unsupported resolution '{resolution}'. "
                f"Supported: {list(RESOLUTION_MAP)}"
            )

        chunks = generate_date_chunks(start, end, MAX_DAYS_PER_CHUNK)
        all_data: list[pd.DataFrame] = []

        for chunk_start, chunk_end in chunks:
            chunk_df = self._fetch_chunk(symbol, chunk_start, chunk_end, fh_resolution)
            if not chunk_df.empty:
                all_data.append(chunk_df)

        if not all_data:
            logger.warning("Finnhub returned no data for %s (%s to %s)", symbol, start, end)
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
        resolution: str,
    ) -> pd.DataFrame:
        """Fetch a single chunk with retry."""
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        def _call() -> pd.DataFrame:
            data = self.client.stock_candles(symbol, resolution, start_ts, end_ts)

            if data.get("s") == "no_data" or "t" not in data:
                logger.debug("Finnhub returned no_data for %s chunk", symbol)
                return pd.DataFrame()

            df = pd.DataFrame({
                "open": data["o"],
                "high": data["h"],
                "low": data["l"],
                "close": data["c"],
                "volume": data["v"],
            })
            df.index = pd.to_datetime(data["t"], unit="s")
            df.index.name = "timestamp"
            return df

        return fetch_with_retry(_call, self.max_retries, self.rate_limiter)
