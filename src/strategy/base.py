"""Base strategy interface and configuration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.strategy.signals import Signal, SignalDirection


@dataclass
class StrategyConfig:
    """Base configuration for all strategies.

    Attributes:
        name: Strategy name identifier
        symbols: List of symbols to trade
        enabled: Whether strategy is enabled
        params: Additional strategy-specific parameters
    """

    name: str = "base"
    symbols: list[str] = field(default_factory=list)
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """Abstract base class for trading strategies.

    All strategies must implement:
    - generate_signals(): Generate signals from market data
    - update(): Update strategy state with new data

    Subclasses should also implement:
    - config property
    - required_features property
    """

    def __init__(self, config: StrategyConfig | None = None):
        """Initialize strategy.

        Args:
            config: Strategy configuration
        """
        self._config = config or StrategyConfig()
        self._last_signals: dict[str, Signal] = {}
        self._is_initialized = False

    @property
    def config(self) -> StrategyConfig:
        """Return strategy configuration."""
        return self._config

    @property
    def name(self) -> str:
        """Return strategy name."""
        return self._config.name

    @property
    def is_initialized(self) -> bool:
        """Check if strategy has been initialized."""
        return self._is_initialized

    @property
    @abstractmethod
    def required_features(self) -> list[str]:
        """Return list of required feature column names."""
        pass

    @abstractmethod
    def generate_signals(
        self,
        features: pd.DataFrame,
        timestamp: datetime,
        **kwargs: Any,
    ) -> list[Signal]:
        """Generate trading signals from current market features.

        Args:
            features: DataFrame with feature columns (single row or multiple rows)
            timestamp: Current timestamp
            **kwargs: Additional data (e.g., state vectors)

        Returns:
            List of Signal objects
        """
        pass

    def update(self, features: pd.DataFrame, **kwargs: Any) -> None:
        """Update strategy state with new data.

        Override this method to maintain strategy state across time steps.

        Args:
            features: New feature data
            **kwargs: Additional data
        """
        self._is_initialized = True

    def reset(self) -> None:
        """Reset strategy state.

        Override this method to reset any internal state.
        """
        self._last_signals = {}
        self._is_initialized = False

    def get_last_signal(self, symbol: str) -> Signal | None:
        """Get the last signal generated for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Last signal or None if no signal was generated
        """
        return self._last_signals.get(symbol)

    def _record_signal(self, signal: Signal) -> None:
        """Record a signal for tracking.

        Args:
            signal: Signal to record
        """
        self._last_signals[signal.symbol] = signal

    def _create_flat_signal(self, symbol: str, timestamp: datetime) -> Signal:
        """Create a flat (exit) signal.

        Args:
            symbol: Asset symbol
            timestamp: Signal timestamp

        Returns:
            Flat signal
        """
        return Signal(
            timestamp=timestamp,
            symbol=symbol,
            direction=SignalDirection.FLAT,
            strength=0.0,
            size=0.0,
        )

    def _create_long_signal(
        self,
        symbol: str,
        timestamp: datetime,
        strength: float = 1.0,
        **metadata_kwargs: Any,
    ) -> Signal:
        """Create a long signal.

        Args:
            symbol: Asset symbol
            timestamp: Signal timestamp
            strength: Signal strength (0-1)
            **metadata_kwargs: Additional metadata

        Returns:
            Long signal
        """
        from src.strategy.signals import SignalMetadata

        return Signal(
            timestamp=timestamp,
            symbol=symbol,
            direction=SignalDirection.LONG,
            strength=strength,
            metadata=SignalMetadata(**metadata_kwargs),
        )

    def _create_short_signal(
        self,
        symbol: str,
        timestamp: datetime,
        strength: float = 1.0,
        **metadata_kwargs: Any,
    ) -> Signal:
        """Create a short signal.

        Args:
            symbol: Asset symbol
            timestamp: Signal timestamp
            strength: Signal strength (0-1)
            **metadata_kwargs: Additional metadata

        Returns:
            Short signal
        """
        from src.strategy.signals import SignalMetadata

        return Signal(
            timestamp=timestamp,
            symbol=symbol,
            direction=SignalDirection.SHORT,
            strength=strength,
            metadata=SignalMetadata(**metadata_kwargs),
        )
