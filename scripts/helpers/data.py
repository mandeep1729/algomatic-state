"""Data loading helpers."""

from pathlib import Path

import pandas as pd


def load_parquet_file(path: Path) -> pd.DataFrame:
    """Load a parquet file."""
    return pd.read_parquet(path)


def load_csv_file(path: Path) -> pd.DataFrame:
    """Load a CSV file with datetime index."""
    return pd.read_csv(path, index_col=0, parse_dates=True)


def _load_single_file(path: Path) -> pd.DataFrame:
    """Load a single data file based on extension."""
    if path.suffix == ".parquet":
        return load_parquet_file(path)
    elif path.suffix == ".csv":
        return load_csv_file(path)
    raise ValueError(f"Unsupported format: {path.suffix}")


def _load_directory_parquets(path: Path) -> pd.DataFrame:
    """Load and combine all parquet files in directory."""
    dfs = [pd.read_parquet(f) for f in path.glob("*.parquet")]
    if not dfs:
        raise ValueError(f"No parquet files found in {path}")
    return pd.concat(dfs).sort_index()


def load_data_from_path(path: str) -> pd.DataFrame:
    """Load data from file or directory."""
    path = Path(path)
    if path.is_file():
        return _load_single_file(path)
    elif path.is_dir():
        return _load_directory_parquets(path)
    raise ValueError(f"Path does not exist: {path}")


def _extract_symbol(path: Path) -> str:
    """Extract symbol from filename (e.g., AAPL_1Min.parquet -> AAPL)."""
    return path.stem.split("_")[0]


def load_multi_symbol_data(path: str) -> dict[str, pd.DataFrame]:
    """Load data from file or directory as dict by symbol."""
    path = Path(path)
    if path.is_file():
        return {_extract_symbol(path): _load_single_file(path)}
    elif path.is_dir():
        return {_extract_symbol(f): pd.read_parquet(f) for f in path.glob("*.parquet")}
    return {}

