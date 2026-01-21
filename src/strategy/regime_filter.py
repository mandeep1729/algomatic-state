"""Regime-based trade filtering."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import numpy as np

from src.state.clustering import RegimeClusterer
from src.strategy.signals import Signal, SignalDirection, SignalMetadata


@dataclass
class RegimeFilterConfig:
    """Configuration for regime-based filtering.

    Attributes:
        min_sharpe: Minimum regime Sharpe ratio to allow trading
        blocked_regimes: List of regime labels to always block
        allowed_regimes: List of regime labels to always allow (overrides min_sharpe)
        filter_mode: 'block' to block unfavorable, 'reduce' to reduce strength
        strength_reduction: Factor to reduce strength in marginal regimes
        log_decisions: Whether to log filter decisions
    """

    min_sharpe: float = 0.0
    blocked_regimes: list[int] = field(default_factory=list)
    allowed_regimes: list[int] = field(default_factory=list)
    filter_mode: Literal["block", "reduce"] = "block"
    strength_reduction: float = 0.5
    log_decisions: bool = False


class RegimeFilter:
    """Filter trades based on detected market regime.

    Uses a fitted RegimeClusterer to determine the current regime
    and filter out trades in unfavorable market conditions.

    Example:
        >>> clusterer = RegimeClusterer(n_clusters=5)
        >>> clusterer.fit(train_states, train_returns)
        >>> filter = RegimeFilter(clusterer, config)
        >>> filtered_signal = filter.apply(signal, current_state)
    """

    def __init__(
        self,
        clusterer: RegimeClusterer,
        config: RegimeFilterConfig | None = None,
    ):
        """Initialize regime filter.

        Args:
            clusterer: Fitted RegimeClusterer instance
            config: Filter configuration
        """
        if not clusterer.is_fitted:
            raise ValueError("RegimeClusterer must be fitted before use")

        self._clusterer = clusterer
        self._config = config or RegimeFilterConfig()
        self._decisions: list[dict[str, Any]] = []

    @property
    def config(self) -> RegimeFilterConfig:
        """Return filter configuration."""
        return self._config

    @property
    def clusterer(self) -> RegimeClusterer:
        """Return the underlying clusterer."""
        return self._clusterer

    @property
    def decisions(self) -> list[dict[str, Any]]:
        """Return logged filter decisions."""
        return self._decisions

    def apply(
        self,
        signal: Signal,
        state: np.ndarray,
    ) -> Signal:
        """Apply regime filter to a signal.

        Args:
            signal: Input signal to filter
            state: Current state vector (latent_dim,) or (1, latent_dim)

        Returns:
            Filtered signal (may be blocked or strength-reduced)
        """
        # Flat signals pass through unchanged
        if signal.direction == SignalDirection.FLAT:
            return signal

        # Predict current regime
        if state.ndim == 1:
            state = state.reshape(1, -1)

        regime_label = int(self._clusterer.predict(state)[0])
        regime_info = self._clusterer.regime_info.get(regime_label)

        regime_sharpe = regime_info.sharpe if regime_info else 0.0

        # Check if regime is explicitly blocked
        is_blocked = regime_label in self._config.blocked_regimes
        is_allowed = regime_label in self._config.allowed_regimes

        # Determine filter action
        should_filter = False
        filter_reason = ""

        if is_blocked:
            should_filter = True
            filter_reason = f"regime {regime_label} is blocked"
        elif not is_allowed and regime_sharpe < self._config.min_sharpe:
            should_filter = True
            filter_reason = f"regime {regime_label} Sharpe {regime_sharpe:.3f} < {self._config.min_sharpe}"

        # Log decision if enabled
        if self._config.log_decisions:
            self._decisions.append({
                "timestamp": signal.timestamp.isoformat(),
                "symbol": signal.symbol,
                "direction": str(signal.direction),
                "regime_label": regime_label,
                "regime_sharpe": regime_sharpe,
                "should_filter": should_filter,
                "filter_reason": filter_reason,
            })

        # Apply filter
        if should_filter:
            if self._config.filter_mode == "block":
                # Block the trade entirely
                return Signal(
                    timestamp=signal.timestamp,
                    symbol=signal.symbol,
                    direction=SignalDirection.FLAT,
                    strength=0.0,
                    size=0.0,
                    metadata=SignalMetadata(
                        regime_label=regime_label,
                        regime_sharpe=regime_sharpe,
                        momentum_value=signal.metadata.momentum_value,
                        volatility=signal.metadata.volatility,
                        custom={"filtered": True, "filter_reason": filter_reason},
                    ),
                )
            else:
                # Reduce signal strength
                new_strength = signal.strength * self._config.strength_reduction
                return Signal(
                    timestamp=signal.timestamp,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    strength=new_strength,
                    size=signal.size,
                    metadata=SignalMetadata(
                        regime_label=regime_label,
                        regime_sharpe=regime_sharpe,
                        momentum_value=signal.metadata.momentum_value,
                        volatility=signal.metadata.volatility,
                        custom={
                            "strength_reduced": True,
                            "original_strength": signal.strength,
                        },
                    ),
                )

        # Signal passes through with regime info added
        return Signal(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            direction=signal.direction,
            strength=signal.strength,
            size=signal.size,
            metadata=SignalMetadata(
                regime_label=regime_label,
                regime_sharpe=regime_sharpe,
                momentum_value=signal.metadata.momentum_value,
                volatility=signal.metadata.volatility,
                pattern_match_count=signal.metadata.pattern_match_count,
                pattern_expected_return=signal.metadata.pattern_expected_return,
                pattern_confidence=signal.metadata.pattern_confidence,
                custom=signal.metadata.custom,
            ),
        )

    def apply_batch(
        self,
        signals: list[Signal],
        states: np.ndarray,
    ) -> list[Signal]:
        """Apply regime filter to multiple signals.

        Args:
            signals: List of signals to filter
            states: State vectors (n_signals, latent_dim)

        Returns:
            List of filtered signals
        """
        if len(signals) != len(states):
            raise ValueError(
                f"Number of signals ({len(signals)}) must match number of states ({len(states)})"
            )

        return [
            self.apply(signal, state)
            for signal, state in zip(signals, states)
        ]

    def is_favorable(self, state: np.ndarray) -> bool:
        """Check if current state is in a favorable regime.

        Args:
            state: Current state vector

        Returns:
            True if regime is favorable for trading
        """
        if state.ndim == 1:
            state = state.reshape(1, -1)

        regime_label = int(self._clusterer.predict(state)[0])

        # Check explicit lists first
        if regime_label in self._config.blocked_regimes:
            return False
        if regime_label in self._config.allowed_regimes:
            return True

        # Check Sharpe threshold
        regime_info = self._clusterer.regime_info.get(regime_label)
        if regime_info is None:
            return False

        return regime_info.sharpe >= self._config.min_sharpe

    def get_regime_status(self, state: np.ndarray) -> dict[str, Any]:
        """Get detailed regime status for current state.

        Args:
            state: Current state vector

        Returns:
            Dictionary with regime information
        """
        if state.ndim == 1:
            state = state.reshape(1, -1)

        regime_label = int(self._clusterer.predict(state)[0])
        regime_info = self._clusterer.regime_info.get(regime_label)

        return {
            "regime_label": regime_label,
            "regime_sharpe": regime_info.sharpe if regime_info else 0.0,
            "regime_size": regime_info.size if regime_info else 0,
            "regime_mean_return": regime_info.mean_return if regime_info else 0.0,
            "is_favorable": self.is_favorable(state),
            "is_blocked": regime_label in self._config.blocked_regimes,
            "is_allowed": regime_label in self._config.allowed_regimes,
        }

    def clear_decisions(self) -> None:
        """Clear logged filter decisions."""
        self._decisions = []

    def get_filter_stats(self) -> dict[str, Any]:
        """Get statistics about filter decisions.

        Returns:
            Dictionary with filter statistics
        """
        if not self._decisions:
            return {
                "total_signals": 0,
                "filtered_count": 0,
                "filter_rate": 0.0,
                "by_regime": {},
            }

        total = len(self._decisions)
        filtered = sum(1 for d in self._decisions if d["should_filter"])

        # Group by regime
        by_regime: dict[int, dict[str, int]] = {}
        for d in self._decisions:
            regime = d["regime_label"]
            if regime not in by_regime:
                by_regime[regime] = {"total": 0, "filtered": 0}
            by_regime[regime]["total"] += 1
            if d["should_filter"]:
                by_regime[regime]["filtered"] += 1

        return {
            "total_signals": total,
            "filtered_count": filtered,
            "filter_rate": filtered / total if total > 0 else 0.0,
            "by_regime": by_regime,
        }
