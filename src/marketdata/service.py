"""Centralized market data service for fetching, aggregating, and storing OHLCV data."""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from src.data.database.connection import DatabaseManager, get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.loaders.database_loader import (
    AGGREGATABLE_TIMEFRAMES,
    aggregate_ohlcv,
)
from src.marketdata.base import MarketDataProvider

logger = logging.getLogger(__name__)


class MarketDataService:
    """Fetch missing OHLCV data from a provider and persist it to the database.

    This service owns the "ensure data exists" responsibility.  It does
    *not* return DataFrames to the caller — it only updates the DB so
    that downstream readers (``ContextPackBuilder``, API endpoints, etc.)
    can query fresh rows.

    The gap-detection and aggregation logic mirrors
    ``DatabaseLoader._sync_missing_data()`` but is extracted here so
    that the pub/sub orchestrator can call it without instantiating a
    ``DatabaseLoader``.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        self.provider = provider
        self.db_manager = db_manager or get_db_manager()

    def ensure_data(
        self,
        symbol: str,
        timeframes: list[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> dict[str, int]:
        """Make sure the requested OHLCV data is present in the database.

        For each timeframe the method:
        1. Checks what already exists in the DB.
        2. Fetches missing ranges from the provider.
        3. Aggregates intraday timeframes from 1Min when appropriate.
        4. Fetches 1Day data directly from the provider.

        Args:
            symbol: Ticker symbol (e.g. ``"AAPL"``).
            timeframes: Timeframes to ensure (e.g. ``["1Min", "5Min", "1Day"]``).
            start: Start of the desired range.  ``None`` lets the provider
                decide (usually the earliest available).
            end: End of the desired range.  Defaults to *now* (UTC).

        Returns:
            Mapping of ``timeframe -> new_bars_inserted``.
        """
        symbol = symbol.upper()
        end = end or datetime.now(timezone.utc).replace(tzinfo=None)
        result: dict[str, int] = {}

        logger.info(
            "MarketDataService.ensure_data: symbol=%s, timeframes=%s, start=%s, end=%s",
            symbol, timeframes, start, end,
        )

        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            ticker = repo.get_or_create_ticker(symbol)

            # Always ensure 1Min first (other intraday TFs aggregate from it)
            if "1Min" in timeframes or any(tf in AGGREGATABLE_TIMEFRAMES for tf in timeframes):
                bars = self._ensure_1min(repo, ticker, symbol, start, end)
                result["1Min"] = bars

            # Aggregate intraday timeframes from 1Min
            for tf in timeframes:
                if tf in AGGREGATABLE_TIMEFRAMES:
                    bars = self._aggregate_timeframe(repo, ticker, symbol, tf, start, end)
                    result[tf] = bars

            # Ensure 1Day (fetched directly, not aggregated)
            if "1Day" in timeframes:
                bars = self._ensure_daily(repo, ticker, symbol, start, end)
                result["1Day"] = bars

        logger.info(
            "MarketDataService.ensure_data complete: symbol=%s, result=%s",
            symbol, result,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_1min(
        self,
        repo: OHLCVRepository,
        ticker,
        symbol: str,
        start: Optional[datetime],
        end: datetime,
    ) -> int:
        """Fetch missing 1-minute bars from the provider."""
        db_latest = repo.get_latest_timestamp(symbol, "1Min")

        if db_latest is None:
            # Brand-new symbol — fetch everything
            fetch_start = start
            fetch_end = end
        else:
            if db_latest.tzinfo is not None:
                db_latest = db_latest.replace(tzinfo=None)
            buffer = timedelta(minutes=1)
            if end <= db_latest + buffer:
                logger.debug("1Min data is up-to-date for %s", symbol)
                return 0
            fetch_start = db_latest + buffer
            fetch_end = end

        return self._fetch_and_insert(
            repo, ticker, symbol, "1Min", fetch_start, fetch_end,
        )

    def _ensure_daily(
        self,
        repo: OHLCVRepository,
        ticker,
        symbol: str,
        start: Optional[datetime],
        end: datetime,
    ) -> int:
        """Fetch missing daily bars from the provider."""
        db_latest = repo.get_latest_timestamp(symbol, "1Day")

        if db_latest is None:
            fetch_start = start
            fetch_end = end
        else:
            if db_latest.tzinfo is not None:
                db_latest = db_latest.replace(tzinfo=None)
            buffer = timedelta(days=1)
            if end <= db_latest + buffer:
                logger.debug("1Day data is up-to-date for %s", symbol)
                return 0
            fetch_start = db_latest + buffer
            fetch_end = end

        return self._fetch_and_insert(
            repo, ticker, symbol, "1Day", fetch_start, fetch_end,
        )

    def _fetch_and_insert(
        self,
        repo: OHLCVRepository,
        ticker,
        symbol: str,
        timeframe: str,
        start: Optional[datetime],
        end: datetime,
    ) -> int:
        """Fetch bars from the provider and bulk-insert into the database."""
        try:
            logger.info(
                "Fetching %s bars for %s from %s to %s",
                timeframe, symbol, start, end,
            )
            if timeframe == "1Day":
                df = self.provider.fetch_daily_bars(symbol, start, end)
            else:
                df = self.provider.fetch_1min_bars(symbol, start, end)

            if df.empty:
                logger.warning("Provider returned 0 %s bars for %s", timeframe, symbol)
                return 0

            # Ensure timezone-naive timestamps
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            rows = repo.bulk_insert_bars(
                df=df,
                ticker_id=ticker.id,
                timeframe=timeframe,
                source=self.provider.source_name,
            )

            repo.update_sync_log(
                ticker_id=ticker.id,
                timeframe=timeframe,
                last_synced_timestamp=df.index.max(),
                first_synced_timestamp=df.index.min(),
                bars_fetched=rows,
                status="success",
            )

            logger.info("Inserted %d %s bars for %s", rows, timeframe, symbol)
            return rows

        except Exception as e:
            logger.error("Failed to fetch %s bars for %s: %s", timeframe, symbol, e)
            repo.update_sync_log(
                ticker_id=ticker.id,
                timeframe=timeframe,
                bars_fetched=0,
                status="failed",
                error_message=str(e),
            )
            return 0

    def _aggregate_timeframe(
        self,
        repo: OHLCVRepository,
        ticker,
        symbol: str,
        target_tf: str,
        start: Optional[datetime],
        end: datetime,
    ) -> int:
        """Aggregate 1Min data to a higher intraday timeframe and insert."""
        try:
            df_1min = repo.get_bars(symbol, "1Min", start, end)
            if df_1min.empty:
                logger.warning("No 1Min data to aggregate for %s/%s", symbol, target_tf)
                return 0

            df_agg = aggregate_ohlcv(df_1min, target_tf)
            if df_agg.empty:
                return 0

            rows = repo.bulk_insert_bars(
                df=df_agg,
                ticker_id=ticker.id,
                timeframe=target_tf,
                source="aggregated",
            )

            repo.update_sync_log(
                ticker_id=ticker.id,
                timeframe=target_tf,
                last_synced_timestamp=df_agg.index.max(),
                first_synced_timestamp=df_agg.index.min(),
                bars_fetched=rows,
                status="success",
            )

            logger.info("Aggregated %d %s bars for %s", rows, target_tf, symbol)
            return rows

        except Exception as e:
            logger.error("Failed to aggregate %s for %s: %s", target_tf, symbol, e)
            return 0


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service: MarketDataService | None = None
_service_lock = threading.Lock()


def get_market_data_service(provider: MarketDataProvider) -> MarketDataService:
    """Return a process-wide ``MarketDataService`` singleton.

    The singleton is created lazily on first call.  Subsequent calls
    return the same instance regardless of the *provider* argument (the
    provider is fixed at creation time).
    """
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = MarketDataService(provider)
                logger.info(
                    "Created MarketDataService singleton (provider=%s)",
                    provider.source_name,
                )
    return _service
