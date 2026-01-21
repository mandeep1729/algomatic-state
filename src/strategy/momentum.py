"""Baseline momentum trading strategy."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.strategy.base import BaseStrategy, StrategyConfig
from src.strategy.signals import Signal, SignalDirection, SignalMetadata


@dataclass
class MomentumConfig(StrategyConfig):
    """Configuration for momentum strategy.

    Attributes:
        momentum_window: Window for momentum calculation (in bars)
        momentum_feature: Feature column to use for momentum signal
        long_threshold: Momentum threshold for long signals
        short_threshold: Momentum threshold for short signals (negative)
        signal_mode: 'both' for long/short, 'long_only', or 'short_only'
        strength_scaling: How to scale signal strength ('linear', 'sigmoid', 'binary')
        min_strength: Minimum strength to generate a signal
    """

    name: str = "momentum"
    momentum_window: int = 20
    momentum_feature: str = "r5"  # 5-minute log return
    long_threshold: float = 0.001  # 0.1% threshold
    short_threshold: float = -0.001
    signal_mode: Literal["both", "long_only", "short_only"] = "both"
    strength_scaling: Literal["linear", "sigmoid", "binary"] = "linear"
    min_strength: float = 0.1


class MomentumStrategy(BaseStrategy):
    """Baseline momentum strategy.

    Generates long signals when momentum exceeds a threshold,
    short signals when momentum falls below negative threshold,
    and flat signals otherwise.

    This strategy serves as a baseline to compare state-enhanced
    strategies against.

    Example:
        >>> config = MomentumConfig(
        ...     momentum_feature='r5',
        ...     long_threshold=0.002,
        ...     short_threshold=-0.002,
        ... )
        >>> strategy = MomentumStrategy(config)
        >>> signals = strategy.generate_signals(features, timestamp)
    """

    def __init__(self, config: MomentumConfig | None = None):
        """Initialize momentum strategy.

        Args:
            config: Momentum strategy configuration
        """
        super().__init__(config or MomentumConfig())
        self._momentum_history: dict[str, list[float]] = {}

    @property
    def config(self) -> MomentumConfig:
        """Return momentum-specific configuration."""
        return self._config

    @property
    def required_features(self) -> list[str]:
        """Return required feature columns."""
        return [self.config.momentum_feature]

    def generate_signals(
        self,
        features: pd.DataFrame,
        timestamp: datetime,
        **kwargs: Any,
    ) -> list[Signal]:
        """Generate momentum-based trading signals.

        Args:
            features: DataFrame with feature columns. Can be:
                - Single row (latest features only)
                - Multiple rows (lookback history)
            timestamp: Current timestamp
            **kwargs: Additional data (ignored in baseline)

        Returns:
            List of Signal objects (one per symbol)
        """
        signals = []

        # Get symbols from config or infer from features
        symbols = self.config.symbols
        if not symbols:
            # If single asset, use default symbol
            symbols = ["default"]

        for symbol in symbols:
            signal = self._generate_signal_for_symbol(
                features, timestamp, symbol, **kwargs
            )
            if signal is not None:
                self._record_signal(signal)
                signals.append(signal)

        return signals

    def _generate_signal_for_symbol(
        self,
        features: pd.DataFrame,
        timestamp: datetime,
        symbol: str,
        **kwargs: Any,
    ) -> Signal | None:
        """Generate signal for a single symbol.

        Args:
            features: Feature DataFrame
            timestamp: Current timestamp
            symbol: Asset symbol
            **kwargs: Additional data

        Returns:
            Signal or None
        """
        # Get momentum value
        momentum_col = self.config.momentum_feature
        if momentum_col not in features.columns:
            raise ValueError(f"Required feature '{momentum_col}' not in DataFrame")

        # Get latest momentum value
        if len(features) == 0:
            return None

        momentum = features[momentum_col].iloc[-1]

        if pd.isna(momentum):
            return self._create_flat_signal(symbol, timestamp)

        # Get volatility if available (for metadata)
        volatility = 0.0
        if "rv_15" in features.columns:
            vol_val = features["rv_15"].iloc[-1]
            if not pd.isna(vol_val):
                volatility = float(vol_val)

        # Determine direction and strength
        direction = SignalDirection.FLAT
        strength = 0.0

        if momentum > self.config.long_threshold:
            if self.config.signal_mode in ("both", "long_only"):
                direction = SignalDirection.LONG
                strength = self._calculate_strength(
                    momentum, self.config.long_threshold, is_long=True
                )
        elif momentum < self.config.short_threshold:
            if self.config.signal_mode in ("both", "short_only"):
                direction = SignalDirection.SHORT
                strength = self._calculate_strength(
                    momentum, self.config.short_threshold, is_long=False
                )

        # Check minimum strength
        if direction != SignalDirection.FLAT and strength < self.config.min_strength:
            direction = SignalDirection.FLAT
            strength = 0.0

        # Create signal with metadata
        metadata = SignalMetadata(
            momentum_value=float(momentum),
            volatility=volatility,
        )

        return Signal(
            timestamp=timestamp,
            symbol=symbol,
            direction=direction,
            strength=strength,
            metadata=metadata,
        )

    def _calculate_strength(
        self, momentum: float, threshold: float, is_long: bool
    ) -> float:
        """Calculate signal strength based on momentum magnitude.

        Args:
            momentum: Current momentum value
            threshold: Signal threshold
            is_long: Whether this is a long signal

        Returns:
            Signal strength (0-1)
        """
        if self.config.strength_scaling == "binary":
            return 1.0

        # Calculate how far beyond threshold
        if is_long:
            excess = (momentum - threshold) / abs(threshold) if threshold != 0 else momentum
        else:
            excess = (threshold - momentum) / abs(threshold) if threshold != 0 else abs(momentum)

        if self.config.strength_scaling == "linear":
            # Linear scaling: excess/threshold ratio, capped at 1
            strength = min(1.0, max(0.0, excess))
        elif self.config.strength_scaling == "sigmoid":
            # Sigmoid scaling: smoother transition
            strength = 1.0 / (1.0 + np.exp(-2 * excess))
        else:
            strength = 1.0

        return float(strength)

    def update(self, features: pd.DataFrame, **kwargs: Any) -> None:
        """Update strategy state with new features.

        Args:
            features: New feature data
            **kwargs: Additional data
        """
        super().update(features, **kwargs)

        # Track momentum history for potential analysis
        momentum_col = self.config.momentum_feature
        if momentum_col in features.columns:
            for symbol in self.config.symbols or ["default"]:
                if symbol not in self._momentum_history:
                    self._momentum_history[symbol] = []

                # Append latest momentum
                momentum = features[momentum_col].iloc[-1]
                if not pd.isna(momentum):
                    self._momentum_history[symbol].append(float(momentum))

                    # Keep only recent history
                    max_history = self.config.momentum_window * 2
                    if len(self._momentum_history[symbol]) > max_history:
                        self._momentum_history[symbol] = self._momentum_history[symbol][-max_history:]

    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self._momentum_history = {}

    def get_momentum_stats(self, symbol: str = "default") -> dict[str, float]:
        """Get momentum statistics for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Dictionary with mean, std, min, max momentum
        """
        history = self._momentum_history.get(symbol, [])
        if not history:
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

        arr = np.array(history)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }
