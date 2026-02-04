"""Multi-asset data loading with timestamp alignment and parallel execution."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from src.data.loaders.base import BaseDataLoader

logger = logging.getLogger(__name__)


def align_timestamps(
    data: dict[str, pd.DataFrame],
    method: str = "inner",
    fill_method: str | None = "ffill",
) -> dict[str, pd.DataFrame]:
    """Align timestamps across multiple asset DataFrames.

    Args:
        data: Dictionary mapping symbols to DataFrames
        method: How to align timestamps:
            - "inner": Keep only timestamps present in ALL assets
            - "outer": Keep all timestamps, fill missing with NaN
        fill_method: How to fill missing values after alignment:
            - "ffill": Forward fill
            - "bfill": Backward fill
            - None: Leave as NaN

    Returns:
        Dictionary of aligned DataFrames with matching timestamps
    """
    if not data:
        return {}

    # Filter out empty DataFrames
    non_empty = {k: v for k, v in data.items() if not v.empty}
    if not non_empty:
        return data

    if len(non_empty) == 1:
        return data

    # Get all unique timestamps
    all_indices = [df.index for df in non_empty.values()]

    if method == "inner":
        # Find common timestamps (intersection)
        common_index = all_indices[0]
        for idx in all_indices[1:]:
            common_index = common_index.intersection(idx)
        common_index = common_index.sort_values()
    else:
        # Union of all timestamps
        common_index = all_indices[0]
        for idx in all_indices[1:]:
            common_index = common_index.union(idx)
        common_index = common_index.sort_values()

    # Reindex all DataFrames to common timestamps
    aligned = {}
    for symbol, df in data.items():
        if df.empty:
            aligned[symbol] = df
            continue

        # Reindex to common timestamps
        reindexed = df.reindex(common_index)

        # Fill missing values if requested
        if fill_method == "ffill":
            reindexed = reindexed.ffill()
        elif fill_method == "bfill":
            reindexed = reindexed.bfill()

        aligned[symbol] = reindexed

    return aligned


class MultiAssetLoader:
    """Load data for multiple assets with parallel execution and timestamp alignment.

    Provides a unified interface for loading multiple assets from any BaseDataLoader
    with optional parallel execution and timestamp alignment.
    """

    def __init__(
        self,
        loader: BaseDataLoader,
        max_workers: int = 4,
        align: bool = True,
        align_method: str = "inner",
        fill_method: str | None = "ffill",
    ):
        """Initialize the multi-asset loader.

        Args:
            loader: The underlying data loader to use
            max_workers: Maximum parallel loading threads
            align: Whether to align timestamps across assets
            align_method: Alignment method ("inner" or "outer")
            fill_method: Fill method for missing values after alignment
        """
        self.loader = loader
        self.max_workers = max_workers
        self.align = align
        self.align_method = align_method
        self.fill_method = fill_method

    def load(
        self,
        sources: list[str | Path],
        start: datetime | None = None,
        end: datetime | None = None,
        parallel: bool = True,
        on_error: str = "warn",
    ) -> dict[str, pd.DataFrame]:
        """Load data for multiple assets.

        Args:
            sources: List of data sources (symbols, file paths, etc.)
            start: Optional start datetime filter
            end: Optional end datetime filter
            parallel: Whether to load assets in parallel
            on_error: How to handle errors:
                - "warn": Log warning and return empty DataFrame for failed asset
                - "raise": Raise exception immediately
                - "skip": Silently skip failed assets

        Returns:
            Dictionary mapping source names to DataFrames
        """
        if parallel and len(sources) > 1:
            result = self._load_parallel(sources, start, end, on_error)
        else:
            result = self._load_sequential(sources, start, end, on_error)

        if self.align:
            result = align_timestamps(result, self.align_method, self.fill_method)

        return result

    def _load_sequential(
        self,
        sources: list[str | Path],
        start: datetime | None,
        end: datetime | None,
        on_error: str,
    ) -> dict[str, pd.DataFrame]:
        """Load assets sequentially."""
        result = {}
        for source in sources:
            name = self._get_source_name(source)
            try:
                result[name] = self.loader.load(source, start, end)
            except Exception as e:
                result[name] = self._handle_error(name, e, on_error)
        return result

    def _load_parallel(
        self,
        sources: list[str | Path],
        start: datetime | None,
        end: datetime | None,
        on_error: str,
    ) -> dict[str, pd.DataFrame]:
        """Load assets in parallel using thread pool."""
        result = {}

        def load_one(source: str | Path) -> tuple[str, pd.DataFrame | Exception]:
            name = self._get_source_name(source)
            try:
                return name, self.loader.load(source, start, end)
            except Exception as e:
                return name, e

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(load_one, src): src for src in sources}

            for future in as_completed(futures):
                name, data = future.result()
                if isinstance(data, Exception):
                    result[name] = self._handle_error(name, data, on_error)
                else:
                    result[name] = data

        return result

    def _get_source_name(self, source: str | Path) -> str:
        """Extract a name from the source."""
        if isinstance(source, Path):
            return source.stem
        # For symbols/strings, return uppercased
        return str(source).upper()

    def _handle_error(
        self, name: str, error: Exception, on_error: str
    ) -> pd.DataFrame:
        """Handle loading error based on on_error strategy."""
        if on_error == "raise":
            raise RuntimeError(f"Failed to load {name}: {error}") from error
        elif on_error == "warn":
            logger.warning("Failed to load %s: %s", name, error)
        # Return empty DataFrame for "warn" and "skip"
        return pd.DataFrame()


def load_and_combine(
    data: dict[str, pd.DataFrame],
    combine_method: str = "panel",
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """Combine multiple asset DataFrames into a single structure.

    Args:
        data: Dictionary mapping symbols to DataFrames
        combine_method:
            - "panel": Return as dict (for multi-asset analysis)
            - "columns": Combine into single DataFrame with multi-level columns

    Returns:
        Combined data structure
    """
    if combine_method == "panel":
        return data

    if combine_method == "columns":
        # Create multi-level column index
        combined = pd.concat(data, axis=1)
        # Flatten column names if needed
        if isinstance(combined.columns, pd.MultiIndex):
            combined.columns = [f"{sym}_{col}" for sym, col in combined.columns]
        return combined

    raise ValueError(f"Unknown combine_method: {combine_method}")
