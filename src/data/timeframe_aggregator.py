"""Timeframe aggregation for building higher-timeframe bars from 1Min data.

Provides a standalone TimeframeAggregator that queries the database for
1-minute ticks, resamples them into 15Min and 1Hour bars, and persists the
results.  Daily bars are fetched directly from the configured market data
provider rather than aggregated from intraday data.

Usage (programmatic)::

    from src.data.timeframe_aggregator import TimeframeAggregator

    aggregator = TimeframeAggregator(db_manager=db_manager, provider=provider)
    summary = aggregator.aggregate_missing_timeframes("AAPL")

Usage (CLI)::

    python scripts/aggregate_timeframes.py --symbols AAPL,SPY --timeframes 15Min,1Hour,1Day
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import pandas as pd

from src.data.database.connection import DatabaseManager, get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.loaders.database_loader import aggregate_ohlcv, AGGREGATABLE_TIMEFRAMES

if TYPE_CHECKING:
    from src.marketdata.base import MarketDataProvider

logger = logging.getLogger(__name__)

# Intraday timeframes that can be built from 1Min ticks
INTRADAY_AGGREGATABLE = ["15Min", "1Hour"]

# Default list of target timeframes to fill
DEFAULT_TARGET_TIMEFRAMES = ["15Min", "1Hour", "1Day"]


class TimeframeAggregator:
    """Build higher-timeframe OHLCV bars from existing 1Min data.

    For intraday targets (15Min, 1Hour) the aggregator resamples 1-minute
    bars already stored in the database.  For 1Day bars it delegates to
    an external :class:`MarketDataProvider`.

    All writes use ``ON CONFLICT DO NOTHING`` via
    :meth:`OHLCVRepository.bulk_insert_bars` so the operation is idempotent
    and safe to run repeatedly.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        provider: Optional["MarketDataProvider"] = None,
    ):
        """Initialize the aggregator.

        Args:
            db_manager: Database manager instance.  Falls back to the
                global singleton when *None*.
            provider: Market data provider used to fetch daily bars.
                When *None*, daily-bar aggregation is skipped.
        """
        self.db_manager = db_manager or get_db_manager()
        self.provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def aggregate_missing_timeframes(
        self,
        ticker: str,
        target_timeframes: Optional[list[str]] = None,
    ) -> dict[str, int]:
        """Fill missing higher-timeframe bars for *ticker*.

        For each target timeframe the method determines which 1Min bars
        have not yet been aggregated, resamples them, and writes the
        result to the database.

        Args:
            ticker: Stock symbol (e.g. ``"AAPL"``).
            target_timeframes: Timeframes to fill.  Defaults to
                ``["15Min", "1Hour", "1Day"]``.

        Returns:
            Mapping of ``{timeframe: bars_inserted}`` for every target
            that was processed.
        """
        if target_timeframes is None:
            target_timeframes = list(DEFAULT_TARGET_TIMEFRAMES)

        symbol = ticker.upper()
        logger.info("Aggregating missing timeframes for %s: %s", symbol, target_timeframes)

        results: dict[str, int] = {}

        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            for timeframe in target_timeframes:
                if timeframe == "1Day":
                    count = self._aggregate_daily(repo, symbol)
                elif timeframe in AGGREGATABLE_TIMEFRAMES:
                    count = self._aggregate_intraday(repo, symbol, timeframe)
                else:
                    logger.warning(
                        "Timeframe %s is not aggregatable, skipping", timeframe
                    )
                    count = 0

                results[timeframe] = count

        logger.info("Aggregation summary for %s: %s", symbol, results)
        return results

    # ------------------------------------------------------------------
    # Intraday aggregation (15Min / 1Hour from 1Min)
    # ------------------------------------------------------------------

    def _aggregate_intraday(
        self,
        repo: OHLCVRepository,
        symbol: str,
        target_timeframe: str,
    ) -> int:
        """Aggregate 1Min bars into *target_timeframe* bars.

        Only processes 1Min bars that are newer than the latest existing
        bar of the target timeframe so that repeated runs are cheap.

        Args:
            repo: Repository bound to the current session.
            symbol: Normalized stock symbol.
            target_timeframe: ``"5Min"``, ``"15Min"``, or ``"1Hour"``.

        Returns:
            Number of new bars inserted.
        """
        logger.debug(
            "Aggregating 1Min -> %s for %s", target_timeframe, symbol
        )

        # Determine the starting point: only aggregate 1Min bars that
        # are newer than the latest bar we already have for the target.
        max_target_ts = repo.get_latest_timestamp(symbol, target_timeframe)
        start_ts = self._normalize_ts(max_target_ts)

        if start_ts is not None:
            logger.debug(
                "Latest %s bar for %s is at %s, fetching 1Min ticks after that",
                target_timeframe, symbol, start_ts,
            )

        # Fetch 1Min bars from *start_ts* onward
        df_1min = repo.get_bars(symbol, "1Min", start=start_ts)

        if df_1min.empty:
            logger.info(
                "No new 1Min bars available for %s after %s, skipping %s aggregation",
                symbol, start_ts, target_timeframe,
            )
            return 0

        # Resample
        df_agg = aggregate_ohlcv(df_1min, target_timeframe)

        if df_agg.empty:
            logger.info(
                "Aggregation produced no %s bars for %s", target_timeframe, symbol
            )
            return 0

        # Persist (upsert / ON CONFLICT DO NOTHING)
        ticker_obj = repo.get_or_create_ticker(symbol)
        rows_inserted = repo.bulk_insert_bars(
            df=df_agg,
            ticker_id=ticker_obj.id,
            timeframe=target_timeframe,
            source="aggregated",
        )

        if rows_inserted > 0:
            repo.update_sync_log(
                ticker_id=ticker_obj.id,
                timeframe=target_timeframe,
                last_synced_timestamp=df_agg.index.max(),
                first_synced_timestamp=df_agg.index.min(),
                bars_fetched=rows_inserted,
                status="success",
            )

        logger.info(
            "Aggregated %d new %s bars for %s", rows_inserted, target_timeframe, symbol
        )
        return rows_inserted

    # ------------------------------------------------------------------
    # Daily bar fetching
    # ------------------------------------------------------------------

    def _aggregate_daily(
        self,
        repo: OHLCVRepository,
        symbol: str,
    ) -> int:
        """Fetch daily bars from the configured provider.

        Only fetches bars newer than the latest 1Day bar already stored.

        Args:
            repo: Repository bound to the current session.
            symbol: Normalized stock symbol.

        Returns:
            Number of new daily bars inserted.
        """
        if self.provider is None:
            logger.warning(
                "No market data provider configured, skipping 1Day fetch for %s",
                symbol,
            )
            return 0

        max_daily_ts = repo.get_latest_timestamp(symbol, "1Day")
        start_ts = self._normalize_ts(max_daily_ts)

        # Determine sensible boundaries
        if start_ts is None:
            # Fall back to the earliest 1Min bar we have
            earliest_1min = repo.get_earliest_timestamp(symbol, "1Min")
            start_ts = self._normalize_ts(earliest_1min)

        if start_ts is None:
            logger.info(
                "No reference data to determine start date for %s daily bars",
                symbol,
            )
            return 0

        end_ts = datetime.now(timezone.utc).replace(tzinfo=None)

        logger.debug(
            "Fetching 1Day bars for %s from %s to %s", symbol, start_ts, end_ts
        )

        try:
            df_daily = self.provider.fetch_daily_bars(symbol, start_ts, end_ts)
        except Exception:
            logger.exception("Failed to fetch 1Day bars for %s", symbol)
            return 0

        if df_daily.empty:
            logger.info("Provider returned no 1Day bars for %s", symbol)
            return 0

        ticker_obj = repo.get_or_create_ticker(symbol)
        rows_inserted = repo.bulk_insert_bars(
            df=df_daily,
            ticker_id=ticker_obj.id,
            timeframe="1Day",
            source=self.provider.source_name,
        )

        if rows_inserted > 0:
            repo.update_sync_log(
                ticker_id=ticker_obj.id,
                timeframe="1Day",
                last_synced_timestamp=df_daily.index.max(),
                first_synced_timestamp=df_daily.index.min(),
                bars_fetched=rows_inserted,
                status="success",
            )

        logger.info("Fetched %d 1Day bars for %s from provider", rows_inserted, symbol)
        return rows_inserted

    # ------------------------------------------------------------------
    # Shared aggregation helpers (used by DatabaseLoader / MarketDataService)
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate_intraday_range(
        repo: OHLCVRepository,
        ticker,
        symbol: str,
        target_timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Aggregate 1Min bars in a date range into a higher timeframe.

        This is the canonical path for callers that already hold a repo
        and ticker object and want to aggregate over a specific range.

        Args:
            repo: Repository bound to the current session.
            ticker: Ticker database object (must have ``.id``).
            symbol: Normalized stock symbol.
            target_timeframe: ``"5Min"``, ``"15Min"``, or ``"1Hour"``.
            start: Start of the 1Min range to read (inclusive).
            end: End of the 1Min range to read (inclusive).

        Returns:
            Number of new bars inserted.
        """
        logger.info("Aggregating 1Min -> %s for %s (range %s..%s)",
                     target_timeframe, symbol, start, end)

        df_1min = repo.get_bars(symbol, "1Min", start, end)
        if df_1min.empty:
            logger.warning("No 1Min data to aggregate for %s/%s", symbol, target_timeframe)
            return 0

        return TimeframeAggregator.aggregate_intraday_from_df(
            repo, ticker, df_1min, target_timeframe,
        )

    @staticmethod
    def aggregate_intraday_from_df(
        repo: OHLCVRepository,
        ticker,
        df_1min: pd.DataFrame,
        target_timeframe: str,
    ) -> int:
        """Aggregate an in-memory 1Min DataFrame into a higher timeframe.

        Useful when the caller already has the 1Min data loaded (e.g.
        after fetching from a provider) and wants to avoid a redundant
        database read.

        Args:
            repo: Repository bound to the current session.
            ticker: Ticker database object (must have ``.id``).
            df_1min: DataFrame with 1-minute OHLCV data and a datetime index.
            target_timeframe: ``"5Min"``, ``"15Min"``, or ``"1Hour"``.

        Returns:
            Number of new bars inserted.
        """
        logger.info("Aggregating in-memory 1Min -> %s (%d source bars)",
                     target_timeframe, len(df_1min))

        df_agg = aggregate_ohlcv(df_1min, target_timeframe)

        if df_agg.empty:
            logger.warning("Aggregation produced no %s bars", target_timeframe)
            return 0

        rows_inserted = repo.bulk_insert_bars(
            df=df_agg,
            ticker_id=ticker.id,
            timeframe=target_timeframe,
            source="aggregated",
        )

        if rows_inserted > 0:
            repo.update_sync_log(
                ticker_id=ticker.id,
                timeframe=target_timeframe,
                last_synced_timestamp=df_agg.index.max(),
                first_synced_timestamp=df_agg.index.min(),
                bars_fetched=rows_inserted,
                status="success",
            )

        logger.info("Aggregated %d %s bars", rows_inserted, target_timeframe)
        return rows_inserted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_ts(ts: Optional[datetime]) -> Optional[datetime]:
        """Strip timezone info from a timestamp for comparison.

        Args:
            ts: Potentially timezone-aware datetime.

        Returns:
            Timezone-naive datetime or *None*.
        """
        if ts is None:
            return None
        if ts.tzinfo is not None:
            return ts.replace(tzinfo=None)
        return ts
