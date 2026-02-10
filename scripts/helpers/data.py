"""Data loading helpers."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_parquet_file(path: Path) -> pd.DataFrame:
    """Load a parquet file."""
    logger.debug(f"Loading parquet file: {path}")
    df = pd.read_parquet(path)
    logger.debug(f"Loaded {len(df)} rows from {path.name}")
    return df


def load_csv_file(path: Path) -> pd.DataFrame:
    """Load a CSV file with datetime index."""
    logger.debug(f"Loading CSV file: {path}")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    logger.debug(f"Loaded {len(df)} rows from {path.name}")
    return df


def _load_single_file(path: Path) -> pd.DataFrame:
    """Load a single data file based on extension."""
    logger.debug(f"Loading single file: {path} (format: {path.suffix})")
    if path.suffix == ".parquet":
        return load_parquet_file(path)
    elif path.suffix == ".csv":
        return load_csv_file(path)
    logger.error(f"Unsupported file format: {path.suffix}")
    raise ValueError(f"Unsupported format: {path.suffix}")


def _load_directory_parquets(path: Path) -> pd.DataFrame:
    """Load and combine all parquet files in directory."""
    files = list(path.glob("*.parquet"))
    logger.debug(f"Found {len(files)} parquet files in {path}")
    if not files:
        logger.error(f"No parquet files found in {path}")
        raise ValueError(f"No parquet files found in {path}")
    dfs = [pd.read_parquet(f) for f in files]
    result = pd.concat(dfs).sort_index()
    logger.debug(f"Combined {len(files)} files into {len(result)} total rows")
    return result


def load_data_from_path(path: str) -> pd.DataFrame:
    """Load data from file or directory."""
    path = Path(path)
    logger.info(f"Loading data from path: {path}")
    if path.is_file():
        return _load_single_file(path)
    elif path.is_dir():
        return _load_directory_parquets(path)
    logger.error(f"Path does not exist: {path}")
    raise ValueError(f"Path does not exist: {path}")


def _extract_symbol(path: Path) -> str:
    """Extract symbol from filename (e.g., AAPL_1Min.parquet -> AAPL)."""
    return path.stem.split("_")[0]


def load_multi_symbol_data(path: str) -> dict[str, pd.DataFrame]:
    """Load data from file or directory as dict by symbol."""
    path = Path(path)
    logger.info(f"Loading multi-symbol data from: {path}")
    if path.is_file():
        symbol = _extract_symbol(path)
        logger.debug(f"Single file mode: extracted symbol={symbol}")
        return {symbol: _load_single_file(path)}
    elif path.is_dir():
        files = list(path.glob("*.parquet"))
        logger.debug(f"Directory mode: found {len(files)} parquet files")
        result = {_extract_symbol(f): pd.read_parquet(f) for f in files}
        logger.info(f"Loaded {len(result)} symbols: {list(result.keys())}")
        return result
    logger.warning(f"Path does not exist, returning empty dict: {path}")
    return {}

