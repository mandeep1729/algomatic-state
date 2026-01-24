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
    ComputedFeature,
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

        # Get total bar count - need to look up ticker symbol
        total_bars = 0
        if ticker_id:
            ticker = self.session.query(Ticker).filter(Ticker.id == ticker_id).first()
            if ticker:
                total_bars = self.get_bar_count(ticker.symbol, timeframe)
        sync_log.total_bars = total_bars

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
    # Feature Operations
    # -------------------------------------------------------------------------

    def store_features(
        self,
        features_df: pd.DataFrame,
        ticker_id: int,
        timeframe: str,
        version: Optional[str] = None,
    ) -> int:
        """Store computed features for a ticker/timeframe.

        Args:
            features_df: DataFrame with datetime index and feature columns
            ticker_id: Ticker ID
            timeframe: Bar timeframe
            version: Optional feature version string

        Returns:
            Number of features stored
        """
        if features_df.empty:
            return 0

        # 1. Get existing bars to map timestamp -> bar_id
        start_date = features_df.index.min()
        end_date = features_df.index.max()

        bars = self.session.query(OHLCVBar.timestamp, OHLCVBar.id).filter(
            OHLCVBar.ticker_id == ticker_id,
            OHLCVBar.timeframe == timeframe,
            OHLCVBar.timestamp >= start_date,
            OHLCVBar.timestamp <= end_date,
        ).all()

        timestamp_map = {b.timestamp: b.id for b in bars}

        # 2. Prepare records
        records = []
        for timestamp, row in features_df.iterrows():
            if timestamp not in timestamp_map:
                continue  # Skip features for missing bars

            # Convert row to dict, handling NaN/Inf if necessary (JSON compliant)
            feature_data = row.where(pd.notnull(row), None).to_dict()
            # Remove None values to save space/cleanliness (optional)
            feature_data = {k: v for k, v in feature_data.items() if v is not None}

            records.append({
                "bar_id": timestamp_map[timestamp],
                "ticker_id": ticker_id,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "features": feature_data,
                "feature_version": version,
            })

        if not records:
            return 0

        # 3. Bulk Upsert (Update existing features for this bar)
        stmt = pg_insert(ComputedFeature).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["bar_id"],  # Unique constraint on bar_id
            set_={
                "features": stmt.excluded.features,
                "feature_version": stmt.excluded.feature_version,
                "timestamp": stmt.excluded.timestamp, # Update timestamp index just in case
            }
        )

        result = self.session.execute(stmt)
        return result.rowcount

    def get_features(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retrieve features as a pandas DataFrame.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            start: Optional start datetime
            end: Optional end datetime

        Returns:
            DataFrame with datetime index and feature columns (expanded from JSON)
        """
        query = self.session.query(
            ComputedFeature.timestamp,
            ComputedFeature.features,
        ).join(Ticker).filter(
            Ticker.symbol == symbol.upper(),
            ComputedFeature.timeframe == timeframe,
        )

        if start:
            query = query.filter(ComputedFeature.timestamp >= start)
        if end:
            query = query.filter(ComputedFeature.timestamp <= end)

        query = query.order_by(ComputedFeature.timestamp)
        results = query.all()

        if not results:
            return pd.DataFrame()

        # Convert list of (timestamp, feature_dict) to DataFrame
        data = []
        for ts, feats in results:
            row = feats.copy()
            row["timestamp"] = ts
            data.append(row)

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        
        return df

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
            
            # Check for features
            feature_count = self.session.query(func.count(ComputedFeature.id)).filter(
                ComputedFeature.ticker_id == ticker.id,
                ComputedFeature.timeframe == timeframe
            ).scalar() or 0

            if count > 0:
                summary[timeframe] = {
                    "earliest": earliest,
                    "latest": latest,
                    "bar_count": count,
                    "feature_count": feature_count,
                }

        return summary
