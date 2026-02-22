"""gRPC client for the data-service — drop-in replacement for OHLCVRepository.

This client communicates with the Go data-service over gRPC for all market data
table operations (tickers, ohlcv_bars, computed_features, data_sync_log).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import grpc
import numpy as np
import pandas as pd
from google.protobuf.timestamp_pb2 import Timestamp

from proto.gen.python.market.v1 import (
    bar_pb2,
    feature_pb2,
    service_pb2_grpc,
    sync_log_pb2,
    ticker_pb2,
)

logger = logging.getLogger(__name__)


def _dt_to_pb(dt: Optional[datetime]) -> Optional[Timestamp]:
    """Convert a Python datetime to a protobuf Timestamp."""
    if dt is None:
        return None
    ts = Timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts


def _pb_to_dt(ts: Optional[Timestamp]) -> Optional[datetime]:
    """Convert a protobuf Timestamp to a naive-UTC Python datetime."""
    if ts is None or (ts.seconds == 0 and ts.nanos == 0):
        return None
    return ts.ToDatetime().replace(tzinfo=None)


class MarketDataGrpcClient:
    """gRPC client matching OHLCVRepository interface for market data operations."""

    def __init__(self, channel: grpc.Channel):
        self.stub = service_pb2_grpc.MarketDataServiceStub(channel)

    # -------------------------------------------------------------------------
    # Ticker Operations
    # -------------------------------------------------------------------------

    def get_ticker(self, symbol: str) -> Optional[object]:
        """Get ticker by symbol. Returns a ticker-like object or None."""
        try:
            resp = self.stub.GetTicker(ticker_pb2.GetTickerRequest(symbol=symbol.upper()))
            return _TickerProxy(resp.ticker)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    def get_or_create_ticker(
        self,
        symbol: str,
        name: Optional[str] = None,
        exchange: Optional[str] = None,
        asset_type: str = "stock",
    ) -> object:
        """Get existing ticker or create a new one."""
        resp = self.stub.GetOrCreateTicker(ticker_pb2.GetOrCreateTickerRequest(
            symbol=symbol.upper(),
            name=name or "",
            exchange=exchange or "",
            asset_type=asset_type,
        ))
        return _TickerProxy(resp.ticker)

    def list_tickers(self, active_only: bool = True) -> list:
        """List all tickers."""
        resp = self.stub.ListTickers(ticker_pb2.ListTickersRequest(active_only=active_only))
        return [_TickerProxy(t) for t in resp.tickers]

    def bulk_upsert_tickers(self, tickers: list[dict]) -> int:
        """Bulk upsert tickers."""
        if not tickers:
            return 0
        pb_tickers = []
        for t in tickers:
            pb_tickers.append(ticker_pb2.Ticker(
                symbol=t.get("symbol", "").upper(),
                name=t.get("name", ""),
                exchange=t.get("exchange", ""),
                asset_type=t.get("asset_type", "stock"),
                is_active=t.get("is_active", True),
            ))
        resp = self.stub.BulkUpsertTickers(ticker_pb2.BulkUpsertTickersRequest(tickers=pb_tickers))
        return resp.upserted_count

    # -------------------------------------------------------------------------
    # OHLCV Bar Operations
    # -------------------------------------------------------------------------

    def get_latest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get the most recent bar timestamp for a symbol/timeframe."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return None
        resp = self.stub.GetLatestTimestamp(bar_pb2.GetLatestTimestampRequest(
            ticker_id=ticker.id, timeframe=timeframe,
        ))
        return _pb_to_dt(resp.timestamp)

    def get_earliest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get the earliest bar timestamp for a symbol/timeframe."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return None
        resp = self.stub.GetEarliestTimestamp(bar_pb2.GetEarliestTimestampRequest(
            ticker_id=ticker.id, timeframe=timeframe,
        ))
        return _pb_to_dt(resp.timestamp)

    def get_bar_count(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Get count of bars for a symbol/timeframe."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return 0
        req = bar_pb2.GetBarCountRequest(ticker_id=ticker.id, timeframe=timeframe)
        if start:
            req.start.CopyFrom(_dt_to_pb(start))
        if end:
            req.end.CopyFrom(_dt_to_pb(end))
        resp = self.stub.GetBarCount(req)
        return resp.count

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """Retrieve bars as a pandas DataFrame with datetime index and OHLCV columns."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            logger.debug("No ticker found for %s", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        all_bars = []
        page_token = ""
        page_size = min(limit, 2000) if limit else 2000
        remaining = limit

        while True:
            req = bar_pb2.GetBarsRequest(
                ticker_id=ticker.id,
                timeframe=timeframe,
                page_size=page_size,
                page_token=page_token,
            )
            if start:
                req.start.CopyFrom(_dt_to_pb(start))
            if end:
                req.end.CopyFrom(_dt_to_pb(end))

            resp = self.stub.GetBars(req)
            all_bars.extend(resp.bars)

            if remaining is not None:
                remaining -= len(resp.bars)
                if remaining <= 0:
                    break

            if not resp.next_page_token:
                break
            page_token = resp.next_page_token

        if not all_bars:
            logger.debug("No bars found for %s/%s", symbol, timeframe)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        data = []
        for b in all_bars:
            data.append({
                "timestamp": _pb_to_dt(b.timestamp),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            })

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        df.index.name = None

        if limit and len(df) > limit:
            df = df.iloc[:limit]

        logger.debug("Retrieved %d bars for %s/%s", len(df), symbol, timeframe)
        return df

    @staticmethod
    def _validate_bars(df: pd.DataFrame) -> pd.DataFrame:
        """Validate OHLCV bar data before insertion.

        Checks for:
        - Negative prices
        - OHLC consistency (high >= open/close/low, low <= open/close/high)
        - Negative volume

        Args:
            df: DataFrame with OHLCV columns.

        Returns:
            DataFrame with invalid rows removed.
        """
        initial_count = len(df)
        if initial_count == 0:
            return df

        # Reject negative prices
        price_cols = ["open", "high", "low", "close"]
        negative_mask = (df[price_cols] < 0).any(axis=1)
        if negative_mask.any():
            n_neg = negative_mask.sum()
            logger.warning(
                "Rejecting %d bars with negative prices", n_neg,
            )
            df = df[~negative_mask]

        if df.empty:
            return df

        # OHLC consistency: high must be >= open, close, low; low must be <= open, close, high
        inconsistent_high = (
            (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["high"] < df["low"])
        )
        inconsistent_low = (
            (df["low"] > df["open"])
            | (df["low"] > df["close"])
            | (df["low"] > df["high"])
        )
        inconsistent = inconsistent_high | inconsistent_low
        if inconsistent.any():
            n_bad = inconsistent.sum()
            logger.warning(
                "Rejecting %d bars with OHLC inconsistency (high < low or similar)", n_bad,
            )
            df = df[~inconsistent]

        if df.empty:
            return df

        # Reject negative volume
        if "volume" in df.columns:
            neg_vol = df["volume"] < 0
            if neg_vol.any():
                n_neg_vol = neg_vol.sum()
                logger.warning("Rejecting %d bars with negative volume", n_neg_vol)
                df = df[~neg_vol]

        removed = initial_count - len(df)
        if removed > 0:
            logger.info(
                "Bar validation: %d/%d bars passed (%d rejected)",
                len(df), initial_count, removed,
            )
        else:
            logger.debug("Bar validation: all %d bars passed", initial_count)

        return df

    def bulk_insert_bars(
        self,
        df: pd.DataFrame,
        ticker_id: int,
        timeframe: str,
        source: str = "alpaca",
    ) -> int:
        """Insert multiple bars. Returns number of rows inserted."""
        if df.empty:
            return 0

        # Validate bars before insertion
        df = self._validate_bars(df)
        if df.empty:
            logger.warning("All bars rejected by validation, nothing to insert")
            return 0

        # Convert DataFrame rows to protobuf bars.
        pb_bars = []
        for timestamp, row in df.iterrows():
            bar = bar_pb2.OHLCVBar(
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
            )
            bar.timestamp.CopyFrom(_dt_to_pb(timestamp))
            pb_bars.append(bar)

        # Chunk into 1000-bar RPCs.
        total_inserted = 0
        for i in range(0, len(pb_bars), 1000):
            chunk = pb_bars[i:i + 1000]
            resp = self.stub.BulkInsertBars(bar_pb2.BulkInsertBarsRequest(
                ticker_id=ticker_id,
                timeframe=timeframe,
                source=source,
                bars=chunk,
            ))
            total_inserted += resp.rows_inserted

        return total_inserted

    def delete_bars(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Delete bars for a symbol/timeframe."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return 0
        req = bar_pb2.DeleteBarsRequest(ticker_id=ticker.id, timeframe=timeframe)
        if start:
            req.start.CopyFrom(_dt_to_pb(start))
        if end:
            req.end.CopyFrom(_dt_to_pb(end))
        resp = self.stub.DeleteBars(req)
        return resp.rows_deleted

    # -------------------------------------------------------------------------
    # Sync Log Operations
    # -------------------------------------------------------------------------

    def get_sync_log(self, ticker_id: int, timeframe: str) -> Optional[object]:
        """Get sync log for a ticker/timeframe."""
        resp = self.stub.GetSyncLog(sync_log_pb2.GetSyncLogRequest(
            ticker_id=ticker_id, timeframe=timeframe,
        ))
        if resp.sync_log and resp.sync_log.id > 0:
            return _SyncLogProxy(resp.sync_log)
        return None

    def update_sync_log(
        self,
        ticker_id: int,
        timeframe: str,
        last_synced_timestamp: Optional[datetime] = None,
        first_synced_timestamp: Optional[datetime] = None,
        bars_fetched: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> object:
        """Update or create sync log entry."""
        req = sync_log_pb2.UpdateSyncLogRequest(
            ticker_id=ticker_id,
            timeframe=timeframe,
            bars_fetched=bars_fetched,
            status=status,
        )
        if last_synced_timestamp:
            req.last_synced_timestamp.CopyFrom(_dt_to_pb(last_synced_timestamp))
        if first_synced_timestamp:
            req.first_synced_timestamp.CopyFrom(_dt_to_pb(first_synced_timestamp))
        if error_message is not None:
            req.error_message = error_message
        resp = self.stub.UpdateSyncLog(req)
        return _SyncLogProxy(resp.sync_log)

    def get_all_sync_logs(self, symbol: Optional[str] = None) -> list:
        """Get all sync logs, optionally filtered by symbol."""
        req = sync_log_pb2.ListSyncLogsRequest()
        if symbol:
            req.symbol = symbol.upper()
        resp = self.stub.ListSyncLogs(req)
        return [_SyncLogProxy(sl) for sl in resp.sync_logs]

    # -------------------------------------------------------------------------
    # Feature Operations
    # -------------------------------------------------------------------------

    # Aggregate timeframes backed by continuous aggregates (no real bar rows).
    _AGGREGATE_TIMEFRAMES = {"5Min", "15Min", "1Hour"}

    def store_features(
        self,
        features_df: pd.DataFrame,
        ticker_id: int,
        timeframe: str,
        version: Optional[str] = None,
    ) -> int:
        """Store computed features for a ticker/timeframe."""
        if features_df.empty:
            return 0

        is_aggregate = timeframe in self._AGGREGATE_TIMEFRAMES

        # Only look up bar_ids for non-aggregate timeframes.
        bar_id_map: dict = {}
        if not is_aggregate:
            timestamps = list(features_df.index)
            bar_id_map = self.get_bar_ids_for_timestamps(ticker_id, timeframe, timestamps)

        # Build feature records.
        pb_features = []
        skipped = 0
        for timestamp, row in features_df.iterrows():
            if not is_aggregate and timestamp not in bar_id_map:
                skipped += 1
                continue

            feature_data = {}
            for k, v in row.items():
                if pd.isna(v) or (isinstance(v, float) and (np.isinf(v) or np.isnan(v))):
                    continue
                feature_data[k] = float(v) if isinstance(v, (np.floating, np.integer)) else v

            f = feature_pb2.ComputedFeature(
                ticker_id=ticker_id,
                timeframe=timeframe,
                feature_version=version or "",
                features=feature_data,
            )
            if not is_aggregate and timestamp in bar_id_map:
                f.bar_id = bar_id_map[timestamp]
            f.timestamp.CopyFrom(_dt_to_pb(timestamp))
            pb_features.append(f)

        if skipped:
            logger.warning(
                "Skipped %d features for missing bars (ticker_id=%s/%s)",
                skipped, ticker_id, timeframe,
            )

        if not pb_features:
            return 0

        # Chunk into 5000 per RPC.
        total_upserted = 0
        for i in range(0, len(pb_features), 5000):
            chunk = pb_features[i:i + 5000]
            resp = self.stub.BulkUpsertFeatures(
                feature_pb2.BulkUpsertFeaturesRequest(features=chunk)
            )
            total_upserted += resp.rows_upserted

        logger.info("Stored %d feature records for ticker_id=%s/%s", total_upserted, ticker_id, timeframe)
        return total_upserted

    def get_existing_feature_timestamps(
        self,
        ticker_id: int,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> set[datetime]:
        """Get timestamps that already have computed features."""
        req = feature_pb2.GetExistingFeatureTimestampsRequest(
            ticker_id=ticker_id, timeframe=timeframe,
        )
        if start:
            req.start.CopyFrom(_dt_to_pb(start))
        if end:
            req.end.CopyFrom(_dt_to_pb(end))
        resp = self.stub.GetExistingFeatureTimestamps(req)
        return {_pb_to_dt(ts) for ts in resp.timestamps}

    def get_features(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retrieve features as a pandas DataFrame."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return pd.DataFrame()

        all_features = []
        page_token = ""

        while True:
            req = feature_pb2.GetFeaturesRequest(
                ticker_id=ticker.id, timeframe=timeframe,
                page_size=2000, page_token=page_token,
            )
            if start:
                req.start.CopyFrom(_dt_to_pb(start))
            if end:
                req.end.CopyFrom(_dt_to_pb(end))
            resp = self.stub.GetFeatures(req)
            all_features.extend(resp.features)

            if not resp.next_page_token:
                break
            page_token = resp.next_page_token

        if not all_features:
            logger.debug("No features found for %s/%s", symbol, timeframe)
            return pd.DataFrame()

        data = []
        for f in all_features:
            row = dict(f.features)
            row["timestamp"] = _pb_to_dt(f.timestamp)
            data.append(row)

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        logger.debug("Retrieved %d feature rows for %s/%s", len(df), symbol, timeframe)
        return df

    # -------------------------------------------------------------------------
    # State Operations
    # -------------------------------------------------------------------------

    def store_states(self, states: list[dict], model_id: str) -> int:
        """Store HMM state assignments.

        Each state dict must contain: ticker_id, timeframe, timestamp, state_id, state_prob.
        Optional: log_likelihood, bar_id.
        """
        if not states:
            return 0
        pb_states = []
        for s in states:
            f = feature_pb2.ComputedFeature(
                ticker_id=int(s["ticker_id"]),
                timeframe=s["timeframe"],
                state_id=int(s["state_id"]),
                state_prob=float(s["state_prob"]),
            )
            f.timestamp.CopyFrom(_dt_to_pb(s["timestamp"]))
            if s.get("log_likelihood") is not None:
                f.log_likelihood = float(s["log_likelihood"])
            pb_states.append(f)

        resp = self.stub.StoreStates(feature_pb2.StoreStatesRequest(
            states=pb_states, model_id=model_id,
        ))
        return resp.rows_stored

    def get_states(
        self,
        symbol: str,
        timeframe: str,
        model_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retrieve state assignments as a DataFrame."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood"])

        req = feature_pb2.GetStatesRequest(
            ticker_id=ticker.id, timeframe=timeframe, model_id=model_id,
        )
        if start:
            req.start.CopyFrom(_dt_to_pb(start))
        if end:
            req.end.CopyFrom(_dt_to_pb(end))
        resp = self.stub.GetStates(req)

        if not resp.states:
            return pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood"])

        data = []
        for s in resp.states:
            data.append({
                "timestamp": _pb_to_dt(s.timestamp),
                "state_id": s.state_id if s.HasField("state_id") else None,
                "state_prob": s.state_prob if s.HasField("state_prob") else None,
                "log_likelihood": s.log_likelihood if s.HasField("log_likelihood") else None,
            })

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    def get_latest_states(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Retrieve the most recent state assignments."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood", "model_id"])

        resp = self.stub.GetLatestStates(feature_pb2.GetLatestStatesRequest(
            ticker_id=ticker.id, timeframe=timeframe,
        ))

        if not resp.states:
            return pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood", "model_id"])

        data = []
        for s in resp.states:
            data.append({
                "timestamp": _pb_to_dt(s.timestamp),
                "state_id": s.state_id if s.HasField("state_id") else None,
                "state_prob": s.state_prob if s.HasField("state_prob") else None,
                "log_likelihood": s.log_likelihood if s.HasField("log_likelihood") else None,
                "model_id": s.model_id if s.HasField("model_id") else None,
            })

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_bar_ids_for_timestamps(
        self,
        ticker_id: int,
        timeframe: str,
        timestamps: list[datetime],
    ) -> dict[datetime, int]:
        """Get bar IDs for a list of timestamps."""
        if not timestamps:
            return {}

        pb_timestamps = [_dt_to_pb(ts) for ts in timestamps]
        resp = self.stub.GetBarIdsForTimestamps(bar_pb2.GetBarIdsForTimestampsRequest(
            ticker_id=ticker_id, timeframe=timeframe, timestamps=pb_timestamps,
        ))

        result = {}
        for ts_str, bar_id in resp.timestamp_to_id.items():
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            result[dt] = bar_id
        return result

    def get_data_summary(self, symbol: str) -> dict:
        """Get summary of available data for a symbol."""
        ticker = self.get_ticker(symbol)
        if ticker is None:
            return {}

        summary = {}
        for timeframe in ["1Min", "15Min", "1Hour", "1Day"]:
            earliest = self.get_earliest_timestamp(symbol, timeframe)
            latest = self.get_latest_timestamp(symbol, timeframe)
            count = self.get_bar_count(symbol, timeframe)
            if count > 0:
                summary[timeframe] = {
                    "earliest": earliest,
                    "latest": latest,
                    "bar_count": count,
                    "feature_count": 0,  # TODO: add feature count RPC
                }

        return summary


class _TickerProxy:
    """Proxy object that mimics SQLAlchemy Ticker model attributes."""

    def __init__(self, pb_ticker):
        self.id = pb_ticker.id
        self.symbol = pb_ticker.symbol
        self.name = pb_ticker.name
        self.exchange = pb_ticker.exchange
        self.asset_type = pb_ticker.asset_type
        self.is_active = pb_ticker.is_active
        self.created_at = _pb_to_dt(pb_ticker.created_at)
        self.updated_at = _pb_to_dt(pb_ticker.updated_at)


class _SyncLogProxy:
    """Proxy object that mimics SQLAlchemy DataSyncLog model attributes."""

    def __init__(self, pb_sync_log):
        self.id = pb_sync_log.id
        self.ticker_id = pb_sync_log.ticker_id
        self.timeframe = pb_sync_log.timeframe
        self.last_synced_timestamp = _pb_to_dt(pb_sync_log.last_synced_timestamp)
        self.first_synced_timestamp = _pb_to_dt(pb_sync_log.first_synced_timestamp)
        self.last_sync_at = _pb_to_dt(pb_sync_log.last_sync_at)
        self.bars_fetched = pb_sync_log.bars_fetched
        self.total_bars = pb_sync_log.total_bars
        self.status = pb_sync_log.status
        self.error_message = pb_sync_log.error_message if pb_sync_log.error_message else None
