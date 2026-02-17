"""Database-backed data loader with smart incremental fetching."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import pandas as pd

from src.data.database.connection import DatabaseManager, get_db_manager
from src.data.database.dependencies import grpc_market_client
from src.data.database.models import VALID_TIMEFRAMES
from src.data.loaders.base import BaseDataLoader
from src.data.schemas import validate_ohlcv

if TYPE_CHECKING:
    from src.marketdata.base import MarketDataProvider

logger = logging.getLogger(__name__)

# Timeframes that can be aggregated from 1Min data
AGGREGATABLE_TIMEFRAMES = ["5Min", "15Min", "1Hour"]

# Mapping of timeframe to pandas resample rule
TIMEFRAME_RESAMPLE_MAP = {
    "5Min": "5min",
    "15Min": "15min",
    "1Hour": "1h",
}


def aggregate_ohlcv(df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """Aggregate 1-minute OHLCV data to a higher timeframe.

    Args:
        df: DataFrame with 1-minute OHLCV data (datetime index)
        target_timeframe: Target timeframe ('5Min', '15Min', '1Hour')

    Returns:
        Aggregated DataFrame with OHLCV columns
    """
    if target_timeframe not in TIMEFRAME_RESAMPLE_MAP:
        raise ValueError(f"Cannot aggregate to {target_timeframe}")

    resample_rule = TIMEFRAME_RESAMPLE_MAP[target_timeframe]

    # Resample using standard OHLCV aggregation rules
    agg_df = df.resample(resample_rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })

    # Drop rows with NaN (incomplete periods)
    agg_df = agg_df.dropna()

    return agg_df


class DatabaseLoader(BaseDataLoader):
    """Load OHLCV data from PostgreSQL database with smart fetching.

    This loader provides:
    - Storage and retrieval of OHLCV data from PostgreSQL
    - Smart incremental fetching from Alpaca (only fetch new data)
    - Support for multiple timeframes
    - CSV/Parquet file import capability

    The smart fetch logic:
    1. Check what data exists in the database for the requested range
    2. If auto_fetch enabled and alpaca_loader provided:
       - Determine gaps in data
       - Fetch only missing data from Alpaca
       - Store new data in database
    3. Return data from database for the requested range
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        alpaca_loader: Optional["AlpacaLoader"] = None,
        provider: Optional["MarketDataProvider"] = None,
        validate: bool = True,
        auto_fetch: bool = True,
    ):
        """Initialize DatabaseLoader.

        Args:
            db_manager: Database manager instance (uses singleton if not provided)
            alpaca_loader: Deprecated — use *provider* instead.  Kept for
                backward compatibility; when set, an ``AlpacaProvider``-compatible
                adapter wraps it automatically.
            provider: A :class:`MarketDataProvider` used to fetch missing data.
            validate: Whether to validate data against OHLCV schema
            auto_fetch: Automatically fetch missing data from the provider
        """
        self.db_manager = db_manager or get_db_manager()
        self.validate = validate
        self.auto_fetch = auto_fetch

        # Backward compat: if caller passed the legacy alpaca_loader but no
        # provider, wrap it so the rest of the class only talks to provider.
        if provider is not None:
            self.provider: MarketDataProvider | None = provider
        elif alpaca_loader is not None:
            self.provider = _AlpacaLoaderAdapter(alpaca_loader)
        else:
            self.provider = None

        # Keep the legacy attribute so existing call-sites that read it
        # directly keep working (e.g. ``if self.alpaca_loader:``).
        self.alpaca_loader = alpaca_loader

    def load(
        self,
        source: str | Path,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: str = "1Min",
    ) -> pd.DataFrame:
        """Load OHLCV data from database, fetching from Alpaca if needed.

        Args:
            source: Stock symbol (e.g., 'AAPL')
            start: Optional start datetime filter
            end: Optional end datetime filter (defaults to now)
            timeframe: Bar timeframe ('1Min', '5Min', '15Min', '1Hour', '1Day')

        Returns:
            DataFrame with datetime index and OHLCV columns

        Raises:
            ValueError: If timeframe is invalid
        """
        symbol = str(source).upper()

        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {VALID_TIMEFRAMES}")

        # Default end to now
        if end is None:
            end = datetime.now(timezone.utc).replace(tzinfo=None)

        with grpc_market_client() as repo:
            # Smart fetch: check what we have vs what we need
            if self.auto_fetch and self.provider:
                self._sync_missing_data(repo, symbol, timeframe, start, end)

            # Load from data-service
            df = repo.get_bars(symbol, timeframe, start, end)

        if self.validate and not df.empty:
            df = validate_ohlcv(df)

        return df

    def load_multiple(
        self,
        sources: list[str | Path],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: str = "1Min",
    ) -> dict[str, pd.DataFrame]:
        """Load OHLCV data for multiple symbols.

        Args:
            sources: List of stock symbols
            start: Optional start datetime filter
            end: Optional end datetime filter
            timeframe: Bar timeframe

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        result = {}
        for source in sources:
            symbol = str(source).upper()
            try:
                result[symbol] = self.load(source, start, end, timeframe)
            except Exception as e:
                logger.error(f"Failed to load {symbol}: {e}")
                result[symbol] = pd.DataFrame()
        return result

    def _sync_missing_data(
        self,
        repo,
        symbol: str,
        timeframe: str,
        start: Optional[datetime],
        end: datetime,
    ) -> None:
        """Synchronize missing data from the market data provider.

        Delegates fetch/insert/aggregation to :class:`MarketDataService`
        (the canonical implementation), then computes technical indicators
        for any timeframes that were updated.

        Args:
            repo: OHLCV repository instance
            symbol: Stock symbol
            timeframe: Bar timeframe
            start: Requested start datetime
            end: Requested end datetime
        """
        if self.provider is None:
            logger.info("No market data provider configured, skipping sync for %s", symbol)
            return

        logger.info("Checking missing data for %s/%s from %s to %s", symbol, timeframe, start, end)

        from src.marketdata.service import MarketDataService

        service = MarketDataService(self.provider, self.db_manager)

        # Determine which timeframes to ensure
        db_1min_latest = repo.get_latest_timestamp(symbol, "1Min")
        if db_1min_latest is None:
            # New symbol — ensure all timeframes
            timeframes = list(VALID_TIMEFRAMES)
        else:
            timeframes = [timeframe]

        result = service.ensure_data(symbol, timeframes, start, end)

        # Compute technical indicators for timeframes that received new bars
        updated_timeframes = [tf for tf, count in result.items() if count > 0]
        if updated_timeframes:
            ticker = repo.get_or_create_ticker(symbol)
            self._compute_indicators_for_timeframes(repo, ticker, symbol, updated_timeframes)

    def import_csv(
        self,
        file_path: Path | str,
        symbol: str,
        timeframe: str = "1Min",
    ) -> int:
        """Import data from CSV file into database.

        Args:
            file_path: Path to CSV file
            symbol: Stock symbol to associate with data
            timeframe: Bar timeframe

        Returns:
            Number of rows imported

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        from src.data.loaders.csv_loader import CSVLoader

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Load from CSV
        csv_loader = CSVLoader(validate=True)
        df = csv_loader.load(file_path)

        if df.empty:
            logger.warning(f"No data loaded from {file_path}")
            return 0

        # Ensure timezone-naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        with grpc_market_client() as repo:
            # Get or create ticker
            ticker = repo.get_or_create_ticker(symbol.upper())

            # Insert via data-service
            rows_inserted = repo.bulk_insert_bars(
                df=df,
                ticker_id=ticker.id,
                timeframe=timeframe,
                source="csv_import",
            )

            # Update sync log
            if rows_inserted > 0:
                repo.update_sync_log(
                    ticker_id=ticker.id,
                    timeframe=timeframe,
                    last_synced_timestamp=df.index.max(),
                    first_synced_timestamp=df.index.min(),
                    bars_fetched=rows_inserted,
                    status="success",
                )

            logger.info(f"Imported {rows_inserted} bars from {file_path} for {symbol}/{timeframe}")
            return rows_inserted

    def import_parquet(
        self,
        file_path: Path | str,
        symbol: str,
        timeframe: str = "1Min",
    ) -> int:
        """Import data from Parquet file into database.

        Args:
            file_path: Path to Parquet file
            symbol: Stock symbol to associate with data
            timeframe: Bar timeframe

        Returns:
            Number of rows imported
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Load from Parquet
        df = pd.read_parquet(file_path)

        # Normalize column names
        df.columns = df.columns.str.lower()

        # Set timestamp as index if it's a column
        if "timestamp" in df.columns:
            df.set_index("timestamp", inplace=True)

        # Ensure timezone-naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        if self.validate:
            df = validate_ohlcv(df)

        with grpc_market_client() as repo:
            # Get or create ticker
            ticker = repo.get_or_create_ticker(symbol.upper())

            # Insert via data-service
            rows_inserted = repo.bulk_insert_bars(
                df=df,
                ticker_id=ticker.id,
                timeframe=timeframe,
                source="parquet_import",
            )

            # Update sync log
            if rows_inserted > 0:
                repo.update_sync_log(
                    ticker_id=ticker.id,
                    timeframe=timeframe,
                    last_synced_timestamp=df.index.max(),
                    first_synced_timestamp=df.index.min(),
                    bars_fetched=rows_inserted,
                    status="success",
                )

            logger.info(f"Imported {rows_inserted} bars from {file_path} for {symbol}/{timeframe}")
            return rows_inserted

    def get_available_tickers(self) -> list[str]:
        """Get list of tickers available in database.

        Returns:
            List of symbol strings
        """
        with grpc_market_client() as repo:
            tickers = repo.list_tickers(active_only=True)
            return [t.symbol for t in tickers]

    def get_data_summary(self, symbol: str) -> dict:
        """Get summary of available data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with data summary per timeframe
        """
        with grpc_market_client() as repo:
            return repo.get_data_summary(symbol)

    def get_sync_status(self, symbol: str) -> list[dict]:
        """Get synchronization status for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of sync log entries as dictionaries
        """
        with grpc_market_client() as repo:
            logs = repo.get_all_sync_logs(symbol)
            return [
                {
                    "symbol": symbol.upper(),
                    "timeframe": log.timeframe,
                    "last_synced_timestamp": log.last_synced_timestamp.isoformat() if log.last_synced_timestamp else None,
                    "first_synced_timestamp": log.first_synced_timestamp.isoformat() if log.first_synced_timestamp else None,
                    "last_sync_at": log.last_sync_at.isoformat() if log.last_sync_at else None,
                    "bars_fetched": log.bars_fetched,
                    "total_bars": log.total_bars,
                    "status": log.status,
                    "error_message": log.error_message,
                }
                for log in logs
            ]

    def _get_feature_pipeline(self):
        """Get the feature pipeline for computing all features.

        Returns the full FeaturePipeline which includes:
        - Returns features (r1, r5, r15, r60)
        - Volatility features (rv_60, range_z_60, etc.)
        - Volume features (relvol_60, vol_z_60)
        - Intrabar features (clv, body_ratio)
        - Anchor features (dist_vwap_60, breakout_20)
        - Time-of-day features (tod_sin, tod_cos)
        - TA-Lib indicators (RSI, MACD, Bollinger Bands, etc.)

        Returns:
            FeaturePipeline instance or None if not available
        """
        try:
            from src.features import FeaturePipeline
            return FeaturePipeline.default()
        except ImportError as e:
            logger.warning(f"Failed to create FeaturePipeline: {e}")
            return None

    def _try_redis_indicators(self, symbol: str, timeframes: list[str]) -> bool:
        """Attempt to compute indicators via Redis-based C++ engine.

        Returns ``True`` if all timeframes were successfully handled via Redis,
        ``False`` if the caller should fall back to in-process computation.
        """
        try:
            from config.settings import get_settings
            if get_settings().messaging.backend != "redis":
                return False
        except Exception:
            logger.debug("Could not load settings for Redis indicator check", exc_info=True)
            return False

        try:
            from src.messaging.bus import get_message_bus
            from src.messaging.events import Event, EventType

            bus = get_message_bus()
            for tf in timeframes:
                response = bus.publish_and_wait(
                    Event(
                        event_type=EventType.INDICATOR_COMPUTE_REQUEST,
                        payload={"symbol": symbol, "timeframe": tf},
                        source="DatabaseLoader",
                    ),
                    EventType.INDICATOR_COMPUTE_COMPLETE,
                    timeout=60.0,
                )
                if response is None:
                    logger.warning(
                        "Indicator engine did not respond for %s/%s, "
                        "falling back to in-process computation",
                        symbol, tf,
                    )
                    return False

                logger.info(
                    "Indicator engine computed %s/%s: %d bars computed, %d skipped",
                    symbol, tf,
                    response.payload.get("bars_computed", 0),
                    response.payload.get("bars_skipped", 0),
                )

            return True

        except Exception:
            logger.warning(
                "Redis indicator request failed for %s, "
                "falling back to in-process computation",
                symbol,
                exc_info=True,
            )
            return False

    def _compute_indicators_for_timeframes(
        self,
        repo,
        ticker,
        symbol: str,
        timeframes: list[str],
        version: str = "v1.0",
    ) -> None:
        """Compute and store all features for specific timeframes.

        When messaging backend is ``"redis"``, publishes
        ``INDICATOR_COMPUTE_REQUEST`` events to the C++ indicator engine
        via Redis and waits for completion.  Falls back to the in-process
        ``FeaturePipeline`` when the backend is ``"memory"`` or on failure.

        Args:
            repo: OHLCV repository instance
            ticker: Ticker database object
            symbol: Stock symbol
            timeframes: List of timeframes to compute features for
            version: Feature version string for tracking
        """
        # Try Redis-based indicator engine first
        if self._try_redis_indicators(symbol, timeframes):
            return

        pipeline = self._get_feature_pipeline()
        if pipeline is None:
            logger.warning(
                "FeaturePipeline not available, skipping feature computation"
            )
            return

        logger.info(f"Computing features for {symbol} ({timeframes})")

        for timeframe in timeframes:
            try:
                # Get OHLCV data for this timeframe
                df = repo.get_bars(symbol, timeframe)

                if df.empty:
                    logger.debug(f"No {timeframe} data for {symbol}, skipping features")
                    continue

                # Get existing feature timestamps to avoid recomputation
                existing_timestamps = repo.get_existing_feature_timestamps(
                    ticker_id=ticker.id,
                    timeframe=timeframe,
                )

                # Normalize df index for comparison (ensure timezone-naive)
                df_timestamps = set(
                    ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
                    for ts in df.index
                )

                # Find bars that need features computed
                missing_timestamps = df_timestamps - existing_timestamps

                if not missing_timestamps:
                    logger.debug(
                        f"All {len(df)} bars for {symbol}/{timeframe} already have features"
                    )
                    continue

                logger.info(
                    f"{symbol}/{timeframe}: {len(missing_timestamps)} bars need features "
                    f"(out of {len(df)} total, {len(existing_timestamps)} existing)"
                )

                # Compute all features on full dataframe (needed for lookback periods)
                features_df = pipeline.compute(df)

                if features_df.empty:
                    logger.warning(f"No features computed for {symbol}/{timeframe}")
                    continue

                # Filter to only store features for bars that don't have them yet
                features_df_filtered = features_df[
                    features_df.index.map(
                        lambda ts: (ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts)
                        in missing_timestamps
                    )
                ]

                if features_df_filtered.empty:
                    logger.debug(f"No new features to store for {symbol}/{timeframe}")
                    continue

                # Store only the new features
                rows_stored = repo.store_features(
                    features_df=features_df_filtered,
                    ticker_id=ticker.id,
                    timeframe=timeframe,
                    version=version,
                )

                logger.info(
                    f"Stored {rows_stored} feature rows for {symbol}/{timeframe} "
                    f"({len(features_df.columns)} features)"
                )

            except Exception as e:
                logger.error(f"Failed to compute features for {symbol}/{timeframe}: {e}")


class _AlpacaLoaderAdapter:
    """Thin adapter that wraps a legacy ``AlpacaLoader`` as a ``MarketDataProvider``.

    This is *not* a full ``MarketDataProvider`` subclass — it only provides
    the three attributes / methods that ``DatabaseLoader`` actually calls:
    ``source_name``, ``fetch_1min_bars``, and ``fetch_daily_bars``.
    """

    source_name = "alpaca"

    def __init__(self, loader):
        self._loader = loader

    def fetch_1min_bars(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        return self._loader.load(symbol, start=start, end=end)

    def fetch_daily_bars(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        # The legacy AlpacaLoader only fetches 1Min bars.  Daily bars
        # require a separate provider call, so we return empty here and
        # rely on the caller to handle it (matching old behaviour where
        # _fetch_daily_data created its own client).
        try:
            from src.marketdata.alpaca_provider import AlpacaProvider
            provider = AlpacaProvider(
                api_key=self._loader.api_key,
                secret_key=self._loader.secret_key,
            )
            return provider.fetch_daily_bars(symbol, start, end)
        except Exception:
            logger.warning("Could not fetch daily bars via AlpacaProvider adapter")
            return pd.DataFrame()
