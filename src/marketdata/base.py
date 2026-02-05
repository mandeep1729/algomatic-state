"""Abstract base class for market data providers."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class MarketDataProvider(ABC):
    """Provider-agnostic interface for fetching OHLCV bars.

    Implementations wrap a specific data vendor SDK (Alpaca, Finnhub, etc.)
    and return normalised DataFrames with columns:
        open, high, low, close, volume
    and a timezone-naive datetime index named ``timestamp``.
    """

    source_name: str  # e.g. "alpaca", "finnhub"

    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        resolution: str = "1Min",
    ) -> pd.DataFrame:
        """Fetch OHLCV bars for *symbol* between *start* and *end*.

        Args:
            symbol: Ticker symbol (e.g. ``"AAPL"``).
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).
            resolution: Bar resolution — ``"1Min"`` or ``"1Day"``.

        Returns:
            DataFrame with standard OHLCV columns and a timezone-naive
            datetime index.  Returns an empty DataFrame when no data is
            available for the requested range.
        """

    def fetch_1min_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Convenience wrapper: fetch 1-minute bars."""
        logger.debug("Fetching 1-minute bars: symbol=%s, start=%s, end=%s", symbol, start, end)
        return self.fetch_bars(symbol, start, end, resolution="1Min")

    def fetch_daily_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Convenience wrapper: fetch daily bars."""
        logger.debug("Fetching daily bars: symbol=%s, start=%s, end=%s", symbol, start, end)
        return self.fetch_bars(symbol, start, end, resolution="1Day")
