"""Abstract base class for data loaders."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import pandas as pd


class BaseDataLoader(ABC):
    """Abstract base class for loading OHLCV market data."""

    @abstractmethod
    def load(
        self,
        source: str | Path,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Load OHLCV data from a source.

        Args:
            source: Data source identifier (file path, symbol, etc.)
            start: Optional start datetime filter
            end: Optional end datetime filter

        Returns:
            DataFrame with datetime index and columns: open, high, low, close, volume
        """
        pass

    @abstractmethod
    def load_multiple(
        self,
        sources: list[str | Path],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Load OHLCV data from multiple sources.

        Args:
            sources: List of data source identifiers
            start: Optional start datetime filter
            end: Optional end datetime filter

        Returns:
            Dictionary mapping source names to DataFrames
        """
        pass
