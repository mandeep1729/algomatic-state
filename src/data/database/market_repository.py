"""Data access layer for OHLCV market data."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
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

logger = logging.getLogger(__name__)


def _normalize_timestamp_to_utc(ts: Optional[datetime]) -> Optional[datetime]:
    """Normalize a timestamp to UTC timezone-aware format.

    Args:
        ts: Timestamp that may be naive or aware

    Returns:
        UTC timezone-aware timestamp, or None if input is None
    """
    if ts is None:
        return None
    if ts.tzinfo is None:
        # Assume naive timestamps are UTC
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


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
    # Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize symbol to uppercase.

        Args:
            symbol: Stock symbol (e.g., 'aapl', 'AAPL')

        Returns:
            Uppercase symbol string
        """
        return symbol.upper()

    def _get_bars_base_query(self, symbol: str, timeframe: str):
        """Get base query for OHLCV bars filtered by symbol and timeframe.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            SQLAlchemy query object with symbol/timeframe filters applied
        """
        return self.session.query(OHLCVBar).join(Ticker).filter(
            Ticker.symbol == self._normalize_symbol(symbol),
            OHLCVBar.timeframe == timeframe,
        )

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
            Ticker.symbol == self._normalize_symbol(symbol)
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
        normalized_symbol = self._normalize_symbol(symbol)
        ticker = self.get_ticker(normalized_symbol)
        if ticker is None:
            ticker = Ticker(
                symbol=normalized_symbol,
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

    def bulk_upsert_tickers(self, tickers: list[dict]) -> int:
        """Bulk upsert tickers using PostgreSQL ON CONFLICT.

        Inserts new tickers or updates existing ones (by symbol).
        Sets is_active=True on conflict so re-seeding reactivates symbols.

        Args:
            tickers: List of dicts with keys: symbol, name, exchange, asset_type

        Returns:
            Number of rows affected
        """
        if not tickers:
            return 0

        stmt = pg_insert(Ticker).values(tickers)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "exchange": stmt.excluded.exchange,
                "asset_type": stmt.excluded.asset_type,
                "is_active": True,
            },
        )
        result = self.session.execute(stmt)
        return result.rowcount

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
        return self.session.query(
            func.max(OHLCVBar.timestamp)
        ).join(Ticker).filter(
            Ticker.symbol == self._normalize_symbol(symbol),
            OHLCVBar.timeframe == timeframe,
        ).scalar()

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
        return self.session.query(
            func.min(OHLCVBar.timestamp)
        ).join(Ticker).filter(
            Ticker.symbol == self._normalize_symbol(symbol),
            OHLCVBar.timeframe == timeframe,
        ).scalar()

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
            Ticker.symbol == self._normalize_symbol(symbol),
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
            Ticker.symbol == self._normalize_symbol(symbol),
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
            logger.debug(f"No bars found for {symbol}/{timeframe}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.DataFrame(
            results,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df.set_index("timestamp", inplace=True)
        df.index.name = None  # Match expected format

        logger.debug(f"Retrieved {len(df)} bars for {symbol}/{timeframe} from {df.index.min()} to {df.index.max()}")
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

        # All timestamps must be timezone-naive (UTC assumed) by this point.
        # Providers strip tz at the boundary; callers must not pass tz-aware data.
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            raise ValueError(
                "bulk_insert_bars received timezone-aware timestamps. "
                "Normalize to naive UTC before calling."
            )

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
        """Update or create sync log entry using PostgreSQL upsert.

        Uses ON CONFLICT DO UPDATE to avoid TOCTOU race conditions when
        concurrent syncs target the same ticker/timeframe.

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
        now = datetime.now(timezone.utc)
        normalized_last = _normalize_timestamp_to_utc(last_synced_timestamp) if last_synced_timestamp else None
        normalized_first = _normalize_timestamp_to_utc(first_synced_timestamp) if first_synced_timestamp else None

        # Get total bar count
        total_bars = 0
        if ticker_id:
            ticker = self.session.query(Ticker).filter(Ticker.id == ticker_id).first()
            if ticker:
                total_bars = self.get_bar_count(ticker.symbol, timeframe)

        # Build insert values
        insert_values = {
            "ticker_id": ticker_id,
            "timeframe": timeframe,
            "last_synced_timestamp": normalized_last,
            "first_synced_timestamp": normalized_first,
            "last_sync_at": now,
            "bars_fetched": bars_fetched,
            "total_bars": total_bars,
            "status": status,
            "error_message": error_message,
        }

        # Build update set for conflict — use SQL expressions for conditional updates
        update_set = {
            "last_sync_at": now,
            "bars_fetched": bars_fetched,
            "total_bars": total_bars,
            "status": status,
            "error_message": error_message,
        }
        if normalized_last is not None:
            update_set["last_synced_timestamp"] = normalized_last
        if normalized_first is not None:
            # Keep the earliest first_synced_timestamp via LEAST()
            update_set["first_synced_timestamp"] = func.least(
                DataSyncLog.first_synced_timestamp, normalized_first
            )

        stmt = pg_insert(DataSyncLog).values(**insert_values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sync_ticker_timeframe",
            set_=update_set,
        ).returning(DataSyncLog.id)

        result = self.session.execute(stmt)
        sync_log_id = result.scalar_one()
        self.session.flush()

        # Return the full ORM object
        return self.session.query(DataSyncLog).get(sync_log_id)

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
            query = query.filter(Ticker.symbol == self._normalize_symbol(symbol))
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
        skipped = 0
        for timestamp, row in features_df.iterrows():
            if timestamp not in timestamp_map:
                skipped += 1
                continue  # Skip features for missing bars

            # Convert row to dict, handling NaN/Inf (JSON doesn't support these)
            feature_data = {}
            for k, v in row.items():
                if pd.isna(v) or (isinstance(v, float) and (np.isinf(v) or np.isnan(v))):
                    continue  # Skip NaN/Inf values
                feature_data[k] = float(v) if isinstance(v, (np.floating, np.integer)) else v

            records.append({
                "bar_id": timestamp_map[timestamp],
                "ticker_id": ticker_id,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "features": feature_data,
                "feature_version": version,
            })

        if skipped:
            logger.warning(
                "Skipped %d features for missing bars (ticker_id=%s/%s)",
                skipped, ticker_id, timeframe,
            )

        if not records:
            logger.debug(f"No features to store for ticker_id={ticker_id}/{timeframe}")
            return 0

        # 3. Bulk Upsert (Update existing features for this bar)
        logger.info(f"Storing {len(records)} feature records for ticker_id={ticker_id}/{timeframe}")
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
        logger.debug(f"Upserted {result.rowcount} feature records")
        return result.rowcount

    def get_existing_feature_timestamps(
        self,
        ticker_id: int,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> set[datetime]:
        """Get timestamps that already have computed features.

        Args:
            ticker_id: Ticker ID
            timeframe: Bar timeframe
            start: Optional start datetime filter
            end: Optional end datetime filter

        Returns:
            Set of timestamps that have features computed
        """
        query = self.session.query(ComputedFeature.timestamp).filter(
            ComputedFeature.ticker_id == ticker_id,
            ComputedFeature.timeframe == timeframe,
        )

        if start:
            query = query.filter(ComputedFeature.timestamp >= start)
        if end:
            query = query.filter(ComputedFeature.timestamp <= end)

        results = query.all()
        return {r.timestamp.replace(tzinfo=None) if r.timestamp.tzinfo else r.timestamp for r in results}

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
            Ticker.symbol == self._normalize_symbol(symbol),
            ComputedFeature.timeframe == timeframe,
        )

        if start:
            query = query.filter(ComputedFeature.timestamp >= start)
        if end:
            query = query.filter(ComputedFeature.timestamp <= end)

        query = query.order_by(ComputedFeature.timestamp)
        results = query.all()

        if not results:
            logger.debug(f"No features found for {symbol}/{timeframe}")
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

        logger.debug(f"Retrieved {len(df)} feature rows for {symbol}/{timeframe} with {len(df.columns)} features")
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
            logger.debug("No ticker found for %s, returning empty summary", symbol)
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

    # -------------------------------------------------------------------------
    # State Operations
    # -------------------------------------------------------------------------

    def store_states(
        self,
        states: list[dict],
        model_id: str,
    ) -> int:
        """Store HMM state assignments in computed_features table.

        Args:
            states: List of dicts with keys: bar_id, state_id, state_prob, is_ood, log_likelihood
            model_id: Model identifier (e.g., "state_v001")

        Returns:
            Number of states stored/updated
        """
        if not states:
            logger.debug(f"No states to store for model {model_id}")
            return 0

        logger.info(f"Storing {len(states)} state assignments for model {model_id}")

        # Update computed_features rows with state information
        updated_count = 0
        for state in states:
            bar_id = int(state["bar_id"])
            state_id = int(state["state_id"])  # -1 indicates OOD
            state_prob = float(state["state_prob"])
            log_likelihood = float(state["log_likelihood"]) if state.get("log_likelihood") is not None else None

            # Update the ComputedFeature row for this bar
            result = self.session.query(ComputedFeature).filter(
                ComputedFeature.bar_id == bar_id
            ).update({
                "model_id": model_id,
                "state_id": state_id,
                "state_prob": state_prob,
                "log_likelihood": log_likelihood,
            }, synchronize_session=False)

            updated_count += result

        logger.info(f"Updated {updated_count} feature records with state info for model {model_id}")
        return updated_count

    def get_states(
        self,
        symbol: str,
        timeframe: str,
        model_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retrieve state assignments from computed_features as a DataFrame.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            model_id: Model identifier
            start: Optional start datetime
            end: Optional end datetime

        Returns:
            DataFrame with timestamp index and state columns
        """
        query = self.session.query(
            ComputedFeature.timestamp,
            ComputedFeature.state_id,
            ComputedFeature.state_prob,
            ComputedFeature.log_likelihood,
        ).join(
            Ticker, ComputedFeature.ticker_id == Ticker.id
        ).filter(
            Ticker.symbol == self._normalize_symbol(symbol),
            ComputedFeature.timeframe == timeframe,
            ComputedFeature.model_id == model_id,
            ComputedFeature.state_id.isnot(None),  # Only rows with state assigned
        )

        if start:
            query = query.filter(ComputedFeature.timestamp >= start)
        if end:
            query = query.filter(ComputedFeature.timestamp <= end)

        query = query.order_by(ComputedFeature.timestamp)
        results = query.all()

        if not results:
            logger.debug(f"No states found for {symbol}/{timeframe} model={model_id}")
            return pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood"])

        df = pd.DataFrame(
            results,
            columns=["timestamp", "state_id", "state_prob", "log_likelihood"],
        )
        df.set_index("timestamp", inplace=True)
        logger.debug(f"Retrieved {len(df)} states for {symbol}/{timeframe} model={model_id}")
        return df

    def get_latest_states(
        self,
        symbol: str,
        timeframe: str,
    ) -> pd.DataFrame:
        """Retrieve the most recent state row for a symbol/timeframe.

        Unlike get_states(), this does not filter by model_id, returning
        whichever model produced the latest state assignment.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe

        Returns:
            DataFrame with columns: state_id, state_prob, log_likelihood, model_id
            (single row or empty)
        """
        query = self.session.query(
            ComputedFeature.timestamp,
            ComputedFeature.state_id,
            ComputedFeature.state_prob,
            ComputedFeature.log_likelihood,
            ComputedFeature.model_id,
        ).join(
            Ticker, ComputedFeature.ticker_id == Ticker.id
        ).filter(
            Ticker.symbol == self._normalize_symbol(symbol),
            ComputedFeature.timeframe == timeframe,
            ComputedFeature.state_id.isnot(None),
        ).order_by(
            ComputedFeature.timestamp.desc()
        ).limit(1)

        results = query.all()

        if not results:
            logger.debug(f"No states found for {symbol}/{timeframe}")
            return pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood", "model_id"])

        df = pd.DataFrame(
            results,
            columns=["timestamp", "state_id", "state_prob", "log_likelihood", "model_id"],
        )
        df.set_index("timestamp", inplace=True)
        logger.debug(f"Retrieved latest state for {symbol}/{timeframe}: state_id={df.iloc[0]['state_id']}, model={df.iloc[0]['model_id']}")
        return df

    def get_state_counts(
        self,
        symbol: str,
        timeframe: str,
        model_id: str,
    ) -> dict[int, int]:
        """Get count of bars per state from computed_features.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            model_id: Model identifier

        Returns:
            Dictionary mapping state_id -> count
        """
        query = self.session.query(
            ComputedFeature.state_id,
            func.count(ComputedFeature.id),
        ).join(
            Ticker, ComputedFeature.ticker_id == Ticker.id
        ).filter(
            Ticker.symbol == self._normalize_symbol(symbol),
            ComputedFeature.timeframe == timeframe,
            ComputedFeature.model_id == model_id,
            ComputedFeature.state_id.isnot(None),
        ).group_by(ComputedFeature.state_id)

        results = query.all()
        return {state_id: count for state_id, count in results}

    def get_bar_ids_for_timestamps(
        self,
        ticker_id: int,
        timeframe: str,
        timestamps: list[datetime],
    ) -> dict[datetime, int]:
        """Get bar IDs for a list of timestamps.

        Args:
            ticker_id: Ticker ID
            timeframe: Bar timeframe
            timestamps: List of timestamps to look up

        Returns:
            Dictionary mapping timestamp -> bar_id
        """
        if not timestamps:
            return {}

        min_ts = min(timestamps)
        max_ts = max(timestamps)

        bars = self.session.query(OHLCVBar.timestamp, OHLCVBar.id).filter(
            OHLCVBar.ticker_id == ticker_id,
            OHLCVBar.timeframe == timeframe,
            OHLCVBar.timestamp >= min_ts,
            OHLCVBar.timestamp <= max_ts,
        ).all()

        return {b.timestamp: b.id for b in bars}

    def delete_states(
        self,
        symbol: str,
        timeframe: str,
        model_id: str,
    ) -> int:
        """Clear state assignments for a symbol/timeframe/model in computed_features.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            model_id: Model identifier

        Returns:
            Number of rows updated (state cleared)
        """
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return 0

        # Clear state columns for this ticker/timeframe/model
        count = self.session.query(ComputedFeature).filter(
            ComputedFeature.ticker_id == ticker.id,
            ComputedFeature.timeframe == timeframe,
            ComputedFeature.model_id == model_id,
        ).update({
            "model_id": None,
            "state_id": None,
            "state_prob": None,
            "log_likelihood": None,
        }, synchronize_session=False)

        logger.info(f"Cleared {count} state assignments for {symbol}/{timeframe} model={model_id}")
        return count
