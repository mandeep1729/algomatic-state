"""Dynamic position sizing based on state confidence and volatility."""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from src.strategy.signals import Signal, SignalDirection


@dataclass
class PositionSizerConfig:
    """Configuration for position sizing.

    Attributes:
        base_size: Base position size in dollars
        max_size: Maximum position size in dollars
        min_size: Minimum position size in dollars
        sizing_method: Method for calculating size
        vol_target: Target volatility (annualized, for vol targeting)
        vol_lookback: Lookback for volatility calculation
        regime_scale: Scale factor for regime confidence
        pattern_scale: Scale factor for pattern match confidence
        strength_scale: Scale factor for signal strength
    """

    base_size: float = 10000.0
    max_size: float = 50000.0
    min_size: float = 1000.0
    sizing_method: Literal["fixed", "signal_scaled", "vol_targeted", "kelly"] = "signal_scaled"
    vol_target: float = 0.15  # 15% annualized volatility target
    vol_lookback: int = 60
    regime_scale: float = 1.0
    pattern_scale: float = 1.0
    strength_scale: float = 1.0


class PositionSizer:
    """Calculate dynamic position sizes based on multiple factors.

    Factors considered:
    - Signal strength
    - Regime confidence (via Sharpe ratio)
    - Pattern match quality
    - Current volatility

    Example:
        >>> sizer = PositionSizer(PositionSizerConfig(base_size=10000))
        >>> sized_signal = sizer.size(signal)
        >>> print(f"Position size: ${sized_signal.size:.2f}")
    """

    def __init__(self, config: PositionSizerConfig | None = None):
        """Initialize position sizer.

        Args:
            config: Position sizing configuration
        """
        self._config = config or PositionSizerConfig()

    @property
    def config(self) -> PositionSizerConfig:
        """Return configuration."""
        return self._config

    def size(
        self,
        signal: Signal,
        current_volatility: float | None = None,
    ) -> Signal:
        """Calculate position size for a signal.

        Args:
            signal: Input signal with metadata
            current_volatility: Current realized volatility (optional override)

        Returns:
            Signal with size field populated
        """
        # Flat signals have zero size
        if signal.direction == SignalDirection.FLAT:
            return signal.with_size(0.0)

        # Get volatility from signal metadata or parameter
        vol = current_volatility
        if vol is None:
            vol = signal.metadata.volatility
        if vol is None or vol <= 0:
            vol = 0.01  # Default to 1% if not available

        # Calculate size based on method
        if self._config.sizing_method == "fixed":
            size = self._fixed_size()
        elif self._config.sizing_method == "signal_scaled":
            size = self._signal_scaled_size(signal)
        elif self._config.sizing_method == "vol_targeted":
            size = self._vol_targeted_size(signal, vol)
        elif self._config.sizing_method == "kelly":
            size = self._kelly_size(signal)
        else:
            size = self._config.base_size

        # Apply confidence scaling (not for fixed method)
        if self._config.sizing_method != "fixed":
            size = self._apply_confidence_scaling(size, signal)

            # Apply volatility scaling (inverse)
            if vol > 0 and self._config.sizing_method != "vol_targeted":
                # Scale inversely by volatility (higher vol = smaller position)
                vol_scale = min(2.0, 0.01 / vol)  # Cap at 2x for very low vol
                size = size * vol_scale

        # Clamp to min/max
        size = max(self._config.min_size, min(self._config.max_size, size))

        return signal.with_size(size)

    def _fixed_size(self) -> float:
        """Return fixed base size."""
        return self._config.base_size

    def _signal_scaled_size(self, signal: Signal) -> float:
        """Scale size by signal strength.

        Args:
            signal: Trading signal

        Returns:
            Scaled position size
        """
        strength_factor = signal.strength ** self._config.strength_scale
        return self._config.base_size * strength_factor

    def _vol_targeted_size(self, signal: Signal, volatility: float) -> float:
        """Calculate size to target specific volatility.

        Uses: size = (vol_target / current_vol) * base_size

        Args:
            signal: Trading signal
            volatility: Current realized volatility (annualized)

        Returns:
            Volatility-targeted position size
        """
        if volatility <= 0:
            return self._config.base_size

        # Annualize volatility if it's per-minute
        # Assuming 390 minutes per day, 252 days per year
        annual_vol = volatility * np.sqrt(390 * 252)

        vol_ratio = self._config.vol_target / max(annual_vol, 0.01)
        size = self._config.base_size * vol_ratio

        # Also scale by signal strength
        size = size * signal.strength

        return size

    def _kelly_size(self, signal: Signal) -> float:
        """Calculate Kelly criterion-based size.

        Uses pattern match statistics for win rate and expected payoff.

        Args:
            signal: Trading signal with pattern match metadata

        Returns:
            Kelly-optimal position size (fractional Kelly)
        """
        win_rate = 0.5  # Default
        expected_return = 0.0

        # Get from pattern matching metadata if available
        if signal.metadata.pattern_match_count > 0:
            expected_return = signal.metadata.pattern_expected_return
            # Estimate win rate from expected return direction
            if expected_return > 0:
                win_rate = 0.5 + signal.metadata.pattern_confidence * 0.2
            else:
                win_rate = 0.5 - signal.metadata.pattern_confidence * 0.2

        # Kelly formula: f* = (bp - q) / b
        # where b = odds ratio, p = win prob, q = lose prob
        # For simplicity, assume symmetric payoffs (b = 1)
        kelly_fraction = 2 * win_rate - 1  # Simplified Kelly

        # Apply half-Kelly for safety
        kelly_fraction = kelly_fraction * 0.5

        # Clamp to reasonable range
        kelly_fraction = max(0.0, min(1.0, kelly_fraction))

        return self._config.base_size * kelly_fraction * signal.strength

    def _apply_confidence_scaling(self, size: float, signal: Signal) -> float:
        """Apply confidence-based scaling factors.

        Args:
            size: Base position size
            signal: Signal with metadata

        Returns:
            Confidence-scaled size
        """
        scale = 1.0

        # Scale by regime confidence
        if signal.metadata.regime_sharpe is not None:
            # Higher Sharpe = more confidence
            regime_confidence = min(1.0, max(0.0, signal.metadata.regime_sharpe / 2.0))
            regime_factor = 0.5 + 0.5 * regime_confidence  # Range: 0.5 to 1.0
            scale *= regime_factor ** self._config.regime_scale

        # Scale by pattern match confidence
        if signal.metadata.pattern_confidence > 0:
            pattern_factor = 0.5 + 0.5 * signal.metadata.pattern_confidence
            scale *= pattern_factor ** self._config.pattern_scale

        return size * scale

    def size_batch(
        self,
        signals: list[Signal],
        volatilities: list[float] | None = None,
    ) -> list[Signal]:
        """Calculate sizes for multiple signals.

        Args:
            signals: List of signals
            volatilities: Optional list of volatilities for each signal

        Returns:
            List of sized signals
        """
        if volatilities is None:
            volatilities = [None] * len(signals)

        if len(signals) != len(volatilities):
            raise ValueError(
                f"Signals ({len(signals)}) and volatilities ({len(volatilities)}) must match"
            )

        return [
            self.size(signal, vol)
            for signal, vol in zip(signals, volatilities)
        ]

    def calculate_portfolio_allocation(
        self,
        signals: list[Signal],
        total_capital: float,
        max_position_pct: float = 0.1,
    ) -> list[Signal]:
        """Allocate capital across multiple signals.

        Ensures total allocation doesn't exceed capital and no single
        position exceeds max_position_pct of capital.

        Args:
            signals: List of signals to size
            total_capital: Total available capital
            max_position_pct: Maximum position as fraction of capital

        Returns:
            List of signals with allocated sizes
        """
        # First, calculate raw sizes
        raw_sized = self.size_batch(signals)

        # Calculate total raw allocation
        total_raw = sum(s.size for s in raw_sized if s.direction != SignalDirection.FLAT)

        if total_raw == 0:
            return raw_sized

        # Scale to fit within capital
        scale_factor = min(1.0, total_capital / total_raw)

        # Apply scaling and max position constraint
        max_size = total_capital * max_position_pct

        sized_signals = []
        for signal in raw_sized:
            if signal.direction == SignalDirection.FLAT:
                sized_signals.append(signal)
            else:
                scaled_size = signal.size * scale_factor
                capped_size = min(scaled_size, max_size)
                sized_signals.append(signal.with_size(capped_size))

        return sized_signals
