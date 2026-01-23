"""Database-backed data loader with smart incremental fetching."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from src.data.database.connection import DatabaseManager, get_db_manager
from src.data.database.models import VALID_TIMEFRAMES
from src.data.database.repository import OHLCVRepository
from src.data.loaders.base import BaseDataLoader
from src.data.schemas import validate_ohlcv

logger = logging.getLogger(__name__)


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
        validate: bool = True,
        auto_fetch: bool = True,
    ):
        """Initialize DatabaseLoader.

        Args:
            db_manager: Database manager instance (uses singleton if not provided)
            alpaca_loader: Optional Alpaca loader for fetching new data
            validate: Whether to validate data against OHLCV schema
            auto_fetch: Automatically fetch missing data from Alpaca
        """
        self.db_manager = db_manager or get_db_manager()
        self.alpaca_loader = alpaca_loader
        self.validate = validate
        self.auto_fetch = auto_fetch

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
            end = datetime.utcnow()

        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            # Smart fetch: check what we have vs what we need
            if self.auto_fetch and self.alpaca_loader:
                self._sync_missing_data(repo, symbol, timeframe, start, end)

            # Load from database
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
        repo: OHLCVRepository,
        symbol: str,
        timeframe: str,
        start: Optional[datetime],
        end: datetime,
    ) -> None:
        """Synchronize missing data from Alpaca.

        Args:
            repo: OHLCV repository instance
            symbol: Stock symbol
            timeframe: Bar timeframe
            start: Requested start datetime
            end: Requested end datetime
        """
        if self.alpaca_loader is None:
            return

        # Get or create ticker
        ticker = repo.get_or_create_ticker(symbol)

        # Get current data range in database
        db_latest = repo.get_latest_timestamp(symbol, timeframe)
        db_earliest = repo.get_earliest_timestamp(symbol, timeframe)

        # Determine what data to fetch
        fetch_start = None
        fetch_end = None

        if db_latest is None:
            # No data exists - fetch entire requested range
            fetch_start = start
            fetch_end = end
            logger.info(f"No existing data for {symbol}/{timeframe}, fetching full range")
        else:
            # Data exists - check if we need to fetch more recent data
            # Add a small buffer (1 minute) to avoid gaps
            buffer = timedelta(minutes=1)

            if end > db_latest + buffer:
                fetch_start = db_latest + buffer
                fetch_end = end
                logger.info(
                    f"Fetching new data for {symbol}/{timeframe} from "
                    f"{fetch_start} to {fetch_end}"
                )

            # Optionally fetch older data if start is before our earliest data
            if start and db_earliest and start < db_earliest - buffer:
                # For now, we only fetch forward. Backfilling historical data
                # would be a separate operation to avoid excessive API calls.
                logger.debug(
                    f"Requested start {start} is before earliest data {db_earliest}. "
                    "Use backfill method to fetch historical data."
                )

        # Fetch from Alpaca if needed
        if fetch_start is not None and fetch_end is not None:
            try:
                # Map timeframe to Alpaca format
                alpaca_timeframe = self._map_timeframe(timeframe)

                df = self.alpaca_loader.load(
                    symbol,
                    start=fetch_start,
                    end=fetch_end,
                    timeframe=alpaca_timeframe,
                )

                if not df.empty:
                    # Ensure timezone-naive timestamps for consistent storage
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)

                    # Insert into database
                    rows_inserted = repo.bulk_insert_bars(
                        df=df,
                        ticker_id=ticker.id,
                        timeframe=timeframe,
                        source="alpaca",
                    )

                    # Update sync log
                    repo.update_sync_log(
                        ticker_id=ticker.id,
                        timeframe=timeframe,
                        last_synced_timestamp=df.index.max(),
                        first_synced_timestamp=df.index.min(),
                        bars_fetched=rows_inserted,
                        status="success",
                    )

                    logger.info(f"Inserted {rows_inserted} bars for {symbol}/{timeframe}")
                else:
                    logger.info(f"No new data available from Alpaca for {symbol}/{timeframe}")

            except Exception as e:
                logger.error(f"Failed to fetch data from Alpaca for {symbol}: {e}")
                # Update sync log with error
                repo.update_sync_log(
                    ticker_id=ticker.id,
                    timeframe=timeframe,
                    bars_fetched=0,
                    status="failed",
                    error_message=str(e),
                )

    def _map_timeframe(self, timeframe: str) -> str:
        """Map internal timeframe to Alpaca timeframe format.

        Args:
            timeframe: Internal timeframe string

        Returns:
            Alpaca-compatible timeframe string
        """
        # Alpaca uses same format, but this allows for future mapping changes
        mapping = {
            "1Min": "1Min",
            "5Min": "5Min",
            "15Min": "15Min",
            "1Hour": "1Hour",
            "1Day": "1Day",
        }
        return mapping.get(timeframe, timeframe)

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

        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            # Get or create ticker
            ticker = repo.get_or_create_ticker(symbol.upper())

            # Insert into database
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

        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            # Get or create ticker
            ticker = repo.get_or_create_ticker(symbol.upper())

            # Insert into database
            rows_inserted = repo.bulk_insert_bars(
                df=df,
                ticker_id=ticker.id,
                timeframe=timeframe,
                source="csv_import",  # Same source for parquet imports
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
        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            tickers = repo.list_tickers(active_only=True)
            return [t.symbol for t in tickers]

    def get_data_summary(self, symbol: str) -> dict:
        """Get summary of available data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with data summary per timeframe
        """
        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            return repo.get_data_summary(symbol)

    def get_sync_status(self, symbol: str) -> list[dict]:
        """Get synchronization status for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of sync log entries as dictionaries
        """
        with self.db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            logs = repo.get_all_sync_logs(symbol)
            return [
                {
                    "symbol": log.ticker.symbol,
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
