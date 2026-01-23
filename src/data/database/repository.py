"""Data access layer for OHLCV market data."""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.data.database.models import (
    DataSyncLog,
    OHLCVBar,
    Ticker,
    VALID_SOURCES,
    VALID_TIMEFRAMES,
)


class OHLCVRepository:
    """Repository for OHLCV bar data operations.

    Provides methods for storing and retrieving market data
    from the PostgreSQL database.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self.session = session

    # -------------------------------------------------------------------------
    # Ticker Operations
    # -------------------------------------------------------------------------

    def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker by symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Ticker object or None if not found
        """
        return self.session.query(Ticker).filter(
            Ticker.symbol == symbol.upper()
        ).first()

    def get_or_create_ticker(
        self,
        symbol: str,
        name: Optional[str] = None,
        exchange: Optional[str] = None,
        asset_type: str = "stock",
    ) -> Ticker:
        """Get existing ticker or create a new one.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            name: Company name (optional)
            exchange: Exchange (e.g., 'NYSE', 'NASDAQ')
            asset_type: Asset type ('stock', 'etf', etc.)

        Returns:
            Ticker object (existing or newly created)
        """
        ticker = self.get_ticker(symbol)
        if ticker is None:
            ticker = Ticker(
                symbol=symbol.upper(),
                name=name,
                exchange=exchange,
                asset_type=asset_type,
            )
            self.session.add(ticker)
            self.session.flush()  # Get the ID without committing
        return ticker

    def list_tickers(self, active_only: bool = True) -> list[Ticker]:
        """List all tickers in the database.

        Args:
            active_only: If True, only return active tickers

        Returns:
            List of Ticker objects
        """
        query = self.session.query(Ticker)
        if active_only:
            query = query.filter(Ticker.is_active == True)
        return query.order_by(Ticker.symbol).all()

    # -------------------------------------------------------------------------
    # OHLCV Bar Operations
    # -------------------------------------------------------------------------

    def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[datetime]:
        """Get the most recent bar timestamp for a symbol/timeframe.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (e.g., '1Min', '1Hour')

        Returns:
            Latest timestamp or None if no data exists
        """
        result = self.session.query(
            func.max(OHLCVBar.timestamp)
        ).join(Ticker).filter(
            Ticker.symbol == symbol.upper(),
            OHLCVBar.timeframe == timeframe,
        ).scalar()
        return result

    def get_earliest_timestamp(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[datetime]:
        """Get the earliest bar timestamp for a symbol/timeframe.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            Earliest timestamp or None if no data exists
        """
        result = self.session.query(
            func.min(OHLCVBar.timestamp)
        ).join(Ticker).filter(
            Ticker.symbol == symbol.upper(),
            OHLCVBar.timeframe == timeframe,
        ).scalar()
        return result

    def get_bar_count(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Get count of bars for a symbol/timeframe.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start: Optional start datetime filter
            end: Optional end datetime filter

        Returns:
            Number of bars matching criteria
        """
        query = self.session.query(
            func.count(OHLCVBar.id)
        ).join(Ticker).filter(
            Ticker.symbol == symbol.upper(),
            OHLCVBar.timeframe == timeframe,
        )
        if start:
            query = query.filter(OHLCVBar.timestamp >= start)
        if end:
            query = query.filter(OHLCVBar.timestamp <= end)
        return query.scalar() or 0

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """Retrieve bars as a pandas DataFrame.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start: Optional start datetime filter
            end: Optional end datetime filter
            limit: Optional maximum number of bars to return

        Returns:
            DataFrame with datetime index and OHLCV columns
        """
        query = self.session.query(
            OHLCVBar.timestamp,
            OHLCVBar.open,
            OHLCVBar.high,
            OHLCVBar.low,
            OHLCVBar.close,
            OHLCVBar.volume,
        ).join(Ticker).filter(
            Ticker.symbol == symbol.upper(),
            OHLCVBar.timeframe == timeframe,
        )

        if start:
            query = query.filter(OHLCVBar.timestamp >= start)
        if end:
            query = query.filter(OHLCVBar.timestamp <= end)

        query = query.order_by(OHLCVBar.timestamp)

        if limit:
            query = query.limit(limit)

        # Execute and convert to DataFrame
        results = query.all()

        if not results:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.DataFrame(
            results,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df.set_index("timestamp", inplace=True)
        df.index.name = None  # Match expected format

        return df

    def bulk_insert_bars(
        self,
        df: pd.DataFrame,
        ticker_id: int,
        timeframe: str,
        source: str = "alpaca",
    ) -> int:
        """Efficiently insert multiple bars using bulk operations.

        Uses PostgreSQL ON CONFLICT DO NOTHING for upsert behavior,
        which safely handles duplicate timestamps.

        Args:
            df: DataFrame with datetime index and OHLCV columns
            ticker_id: ID of the ticker
            timeframe: Bar timeframe
            source: Data source identifier

        Returns:
            Number of rows inserted

        Raises:
            ValueError: If timeframe or source is invalid
        """
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {VALID_TIMEFRAMES}")
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {source}. Must be one of {VALID_SOURCES}")

        if df.empty:
            return 0

        # Prepare data for insertion
        records = []
        for timestamp, row in df.iterrows():
            records.append({
                "ticker_id": ticker_id,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "source": source,
            })

        # Use PostgreSQL INSERT ... ON CONFLICT DO NOTHING
        stmt = pg_insert(OHLCVBar).values(records)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["ticker_id", "timeframe", "timestamp"]
        )

        result = self.session.execute(stmt)
        return result.rowcount

    def delete_bars(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Delete bars for a symbol/timeframe within a date range.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start: Optional start datetime (inclusive)
            end: Optional end datetime (inclusive)

        Returns:
            Number of rows deleted
        """
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return 0

        query = self.session.query(OHLCVBar).filter(
            OHLCVBar.ticker_id == ticker.id,
            OHLCVBar.timeframe == timeframe,
        )
        if start:
            query = query.filter(OHLCVBar.timestamp >= start)
        if end:
            query = query.filter(OHLCVBar.timestamp <= end)

        count = query.delete(synchronize_session=False)
        return count

    # -------------------------------------------------------------------------
    # Sync Log Operations
    # -------------------------------------------------------------------------

    def get_sync_log(
        self,
        ticker_id: int,
        timeframe: str,
    ) -> Optional[DataSyncLog]:
        """Get sync log for a ticker/timeframe.

        Args:
            ticker_id: Ticker ID
            timeframe: Bar timeframe

        Returns:
            DataSyncLog object or None
        """
        return self.session.query(DataSyncLog).filter(
            DataSyncLog.ticker_id == ticker_id,
            DataSyncLog.timeframe == timeframe,
        ).first()

    def update_sync_log(
        self,
        ticker_id: int,
        timeframe: str,
        last_synced_timestamp: Optional[datetime] = None,
        first_synced_timestamp: Optional[datetime] = None,
        bars_fetched: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> DataSyncLog:
        """Update or create sync log entry.

        Args:
            ticker_id: Ticker ID
            timeframe: Bar timeframe
            last_synced_timestamp: Most recent timestamp synced
            first_synced_timestamp: Earliest timestamp synced
            bars_fetched: Number of bars fetched in this sync
            status: Sync status ('success', 'partial', 'failed')
            error_message: Error message if status is 'failed'

        Returns:
            Updated or created DataSyncLog
        """
        sync_log = self.get_sync_log(ticker_id, timeframe)

        if sync_log is None:
            sync_log = DataSyncLog(
                ticker_id=ticker_id,
                timeframe=timeframe,
            )
            self.session.add(sync_log)

        # Update fields
        if last_synced_timestamp:
            sync_log.last_synced_timestamp = last_synced_timestamp
        if first_synced_timestamp:
            if sync_log.first_synced_timestamp is None:
                sync_log.first_synced_timestamp = first_synced_timestamp
            else:
                sync_log.first_synced_timestamp = min(
                    sync_log.first_synced_timestamp,
                    first_synced_timestamp,
                )

        sync_log.last_sync_at = datetime.utcnow()
        sync_log.bars_fetched = bars_fetched
        sync_log.total_bars = self.get_bar_count(
            symbol=sync_log.ticker.symbol if hasattr(sync_log, 'ticker') else None,
            timeframe=timeframe,
        ) if sync_log.ticker_id else 0
        sync_log.status = status
        sync_log.error_message = error_message

        self.session.flush()
        return sync_log

    def get_all_sync_logs(
        self,
        symbol: Optional[str] = None,
    ) -> list[DataSyncLog]:
        """Get all sync logs, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of DataSyncLog objects
        """
        query = self.session.query(DataSyncLog).join(Ticker)
        if symbol:
            query = query.filter(Ticker.symbol == symbol.upper())
        return query.order_by(Ticker.symbol, DataSyncLog.timeframe).all()

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_data_summary(self, symbol: str) -> dict:
        """Get summary of available data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with data summary per timeframe
        """
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return {}

        summary = {}
        for timeframe in VALID_TIMEFRAMES:
            earliest = self.get_earliest_timestamp(symbol, timeframe)
            latest = self.get_latest_timestamp(symbol, timeframe)
            count = self.get_bar_count(symbol, timeframe)

            if count > 0:
                summary[timeframe] = {
                    "earliest": earliest,
                    "latest": latest,
                    "bar_count": count,
                }

        return summary
