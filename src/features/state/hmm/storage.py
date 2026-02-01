"""Storage for state time-series data.

Implements:
- Parquet writer for state outputs
- Parquet reader for backtesting
- Schema validation
- Partitioned storage layout
"""

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.features.state.hmm.artifacts import StatesPaths, get_states_path
from src.features.state.hmm.contracts import HMMOutput, VALID_TIMEFRAMES


STATE_SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("timeframe", pa.string()),
    ("model_id", pa.string()),
    ("state_id", pa.int32()),
    ("state_prob", pa.float64()),
    ("log_likelihood", pa.float64()),
    ("is_ood", pa.bool_()),
    ("entropy", pa.float64()),
])


def get_state_schema(latent_dim: int) -> pa.Schema:
    """Get Parquet schema including latent vector columns.

    Args:
        latent_dim: Dimensionality of latent vectors

    Returns:
        PyArrow schema
    """
    fields = list(STATE_SCHEMA)

    for i in range(latent_dim):
        fields.append((f"z_{i}", pa.float64()))

    return pa.schema(fields)


@dataclass
class StateRecord:
    """A single state inference record for storage."""

    symbol: str
    timestamp: datetime
    timeframe: str
    model_id: str
    state_id: int
    state_prob: float
    log_likelihood: float
    is_ood: bool
    entropy: float
    z: np.ndarray

    @classmethod
    def from_hmm_output(cls, output: HMMOutput) -> "StateRecord":
        """Create from HMMOutput."""
        return cls(
            symbol=output.symbol,
            timestamp=output.timestamp,
            timeframe=output.timeframe,
            model_id=output.model_id,
            state_id=output.state_id,
            state_prob=output.state_prob,
            log_likelihood=output.log_likelihood,
            is_ood=output.is_ood,
            entropy=output.entropy,
            z=output.z if output.z is not None else np.array([]),
        )


class StateWriter:
    """Write state inference results to Parquet files."""

    def __init__(
        self,
        states_root: Path = Path("states"),
        compression: str = "snappy",
    ):
        """Initialize state writer.

        Args:
            states_root: Root directory for state storage
            compression: Parquet compression codec
        """
        self.states_root = states_root
        self.compression = compression
        self._buffer: list[StateRecord] = []

    def write(self, output: HMMOutput) -> None:
        """Buffer a single state output for writing.

        Args:
            output: HMM inference output
        """
        record = StateRecord.from_hmm_output(output)
        self._buffer.append(record)

    def write_batch(self, outputs: list[HMMOutput]) -> None:
        """Buffer multiple outputs for writing.

        Args:
            outputs: List of HMM outputs
        """
        for output in outputs:
            self.write(output)

    def flush(
        self,
        timeframe: str,
        model_id: str,
        symbol: str,
        target_date: date,
    ) -> Path:
        """Flush buffered records to Parquet file.

        Args:
            timeframe: Model timeframe
            model_id: Model ID
            symbol: Symbol
            target_date: Date for partitioning

        Returns:
            Path to written Parquet file
        """
        if not self._buffer:
            raise ValueError("No records to flush")

        paths = get_states_path(timeframe, model_id, self.states_root)
        paths.ensure_dirs(symbol, datetime.combine(target_date, datetime.min.time()))

        output_path = paths.get_parquet_path(
            symbol,
            datetime.combine(target_date, datetime.min.time()),
        )

        df = self._records_to_dataframe(self._buffer)
        latent_dim = len(self._buffer[0].z) if self._buffer[0].z.size > 0 else 0
        schema = get_state_schema(latent_dim)

        table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
        pq.write_table(
            table,
            output_path,
            compression=self.compression,
        )

        self._buffer.clear()

        return output_path

    def flush_by_date(
        self,
        timeframe: str,
        model_id: str,
    ) -> list[Path]:
        """Flush buffered records, partitioned by symbol and date.

        Args:
            timeframe: Model timeframe
            model_id: Model ID

        Returns:
            List of written Parquet file paths
        """
        if not self._buffer:
            return []

        grouped: dict[tuple[str, date], list[StateRecord]] = {}
        for record in self._buffer:
            key = (record.symbol, record.timestamp.date())
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(record)

        written_paths = []
        for (symbol, target_date), records in grouped.items():
            self._buffer = records
            path = self.flush(timeframe, model_id, symbol, target_date)
            written_paths.append(path)

        self._buffer.clear()
        return written_paths

    def _records_to_dataframe(self, records: list[StateRecord]) -> pd.DataFrame:
        """Convert records to DataFrame."""
        data = {
            "symbol": [r.symbol for r in records],
            "timestamp": [r.timestamp for r in records],
            "timeframe": [r.timeframe for r in records],
            "model_id": [r.model_id for r in records],
            "state_id": [r.state_id for r in records],
            "state_prob": [r.state_prob for r in records],
            "log_likelihood": [r.log_likelihood for r in records],
            "is_ood": [r.is_ood for r in records],
            "entropy": [r.entropy for r in records],
        }

        if records and records[0].z.size > 0:
            latent_dim = len(records[0].z)
            for i in range(latent_dim):
                data[f"z_{i}"] = [r.z[i] if r.z.size > i else np.nan for r in records]

        return pd.DataFrame(data)


class StateReader:
    """Read state data from Parquet files."""

    def __init__(self, states_root: Path = Path("states")):
        """Initialize state reader.

        Args:
            states_root: Root directory for state storage
        """
        self.states_root = states_root

    def read(
        self,
        timeframe: str,
        model_id: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Read state data for a symbol and date range.

        Args:
            timeframe: Model timeframe
            model_id: Model ID
            symbol: Symbol to read
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with state data
        """
        paths = get_states_path(timeframe, model_id, self.states_root)

        dfs = []
        current = start_date
        while current <= end_date:
            parquet_path = paths.get_parquet_path(
                symbol,
                datetime.combine(current, datetime.min.time()),
            )
            if parquet_path.exists():
                df = pq.read_table(parquet_path).to_pandas()
                dfs.append(df)

            current = date(
                current.year,
                current.month,
                current.day + 1 if current.day < 28 else 1,
            )
            if current.day == 1:
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

            from datetime import timedelta
            current = (datetime.combine(start_date, datetime.min.time()) +
                      timedelta(days=(current - start_date).days + 1)).date()
            if current > end_date:
                break

        if not dfs:
            return pd.DataFrame()

        result = pd.concat(dfs, ignore_index=True)
        result = result.sort_values("timestamp").reset_index(drop=True)

        return result

    def read_date_range(
        self,
        timeframe: str,
        model_id: str,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Read state data for a datetime range.

        Args:
            timeframe: Model timeframe
            model_id: Model ID
            symbol: Symbol
            start: Start datetime
            end: End datetime

        Returns:
            DataFrame filtered to datetime range
        """
        df = self.read(timeframe, model_id, symbol, start.date(), end.date())

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)

        return df[mask].reset_index(drop=True)

    def read_latest(
        self,
        timeframe: str,
        model_id: str,
        symbol: str,
        n_records: int = 100,
    ) -> pd.DataFrame:
        """Read most recent state records.

        Args:
            timeframe: Model timeframe
            model_id: Model ID
            symbol: Symbol
            n_records: Number of recent records to return

        Returns:
            DataFrame with most recent records
        """
        paths = get_states_path(timeframe, model_id, self.states_root)
        dates = paths.list_dates(symbol)

        if not dates:
            return pd.DataFrame()

        dfs = []
        total_records = 0

        for d in reversed(dates):
            parquet_path = paths.get_parquet_path(symbol, d)
            if parquet_path.exists():
                df = pq.read_table(parquet_path).to_pandas()
                dfs.append(df)
                total_records += len(df)

                if total_records >= n_records:
                    break

        if not dfs:
            return pd.DataFrame()

        result = pd.concat(dfs, ignore_index=True)
        result = result.sort_values("timestamp", ascending=False)
        result = result.head(n_records)

        return result.sort_values("timestamp").reset_index(drop=True)

    def list_symbols(self, timeframe: str, model_id: str) -> list[str]:
        """List available symbols.

        Args:
            timeframe: Model timeframe
            model_id: Model ID

        Returns:
            List of symbols
        """
        paths = get_states_path(timeframe, model_id, self.states_root)
        return paths.list_symbols()

    def get_latent_vectors(
        self,
        df: pd.DataFrame,
    ) -> np.ndarray:
        """Extract latent vectors from state DataFrame.

        Args:
            df: State DataFrame with z_* columns

        Returns:
            2D array of latent vectors (n_samples, latent_dim)
        """
        z_cols = [c for c in df.columns if c.startswith("z_")]
        z_cols = sorted(z_cols, key=lambda x: int(x.split("_")[1]))

        if not z_cols:
            return np.array([])

        return df[z_cols].values


def validate_state_dataframe(df: pd.DataFrame) -> bool:
    """Validate that DataFrame conforms to state schema.

    Args:
        df: DataFrame to validate

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    required_columns = [
        "symbol",
        "timestamp",
        "timeframe",
        "model_id",
        "state_id",
        "state_prob",
        "log_likelihood",
        "is_ood",
    ]

    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if df["timeframe"].iloc[0] not in VALID_TIMEFRAMES:
        raise ValueError(f"Invalid timeframe: {df['timeframe'].iloc[0]}")

    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        raise ValueError("timestamp must be datetime type")

    if df["state_prob"].min() < 0 or df["state_prob"].max() > 1:
        raise ValueError("state_prob must be in [0, 1]")

    return True
