"""State-enhanced momentum strategy combining all enhancements."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.state.clustering import RegimeClusterer
from src.strategy.base import BaseStrategy, StrategyConfig
from src.strategy.momentum import MomentumStrategy, MomentumConfig
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig
from src.strategy.position_sizer import PositionSizer, PositionSizerConfig
from src.strategy.regime_filter import RegimeFilter, RegimeFilterConfig
from src.strategy.signals import Signal, SignalDirection, SignalMetadata


@dataclass
class StateEnhancedConfig(StrategyConfig):
    """Configuration for state-enhanced strategy.

    Attributes:
        momentum_config: Configuration for baseline momentum
        regime_filter_config: Configuration for regime filtering
        pattern_match_config: Configuration for pattern matching
        position_sizer_config: Configuration for position sizing
        enable_regime_filter: Whether to enable regime filtering
        enable_pattern_matching: Whether to enable pattern matching
        enable_dynamic_sizing: Whether to enable dynamic position sizing
        log_decisions: Whether to log strategy decisions
    """

    name: str = "state_enhanced"
    momentum_config: MomentumConfig = field(default_factory=MomentumConfig)
    regime_filter_config: RegimeFilterConfig = field(default_factory=RegimeFilterConfig)
    pattern_match_config: PatternMatchConfig = field(default_factory=PatternMatchConfig)
    position_sizer_config: PositionSizerConfig = field(default_factory=PositionSizerConfig)
    enable_regime_filter: bool = True
    enable_pattern_matching: bool = True
    enable_dynamic_sizing: bool = True
    log_decisions: bool = False


class StateEnhancedStrategy(BaseStrategy):
    """State-enhanced momentum trading strategy.

    Combines:
    1. Baseline momentum strategy for signal generation
    2. Regime filtering to block trades in unfavorable conditions
    3. Pattern matching for confidence estimation
    4. Dynamic position sizing based on all factors

    Example:
        >>> # Fit state components
        >>> clusterer = RegimeClusterer(n_clusters=5)
        >>> clusterer.fit(train_states, train_returns)
        >>> matcher = PatternMatcher()
        >>> matcher.fit(train_states, train_returns)
        >>>
        >>> # Create strategy
        >>> config = StateEnhancedConfig(enable_pattern_matching=True)
        >>> strategy = StateEnhancedStrategy(config, clusterer, matcher)
        >>>
        >>> # Generate signals
        >>> signals = strategy.generate_signals(features, timestamp, state=current_state)
    """

    def __init__(
        self,
        config: StateEnhancedConfig | None = None,
        clusterer: RegimeClusterer | None = None,
        pattern_matcher: PatternMatcher | None = None,
    ):
        """Initialize state-enhanced strategy.

        Args:
            config: Strategy configuration
            clusterer: Fitted regime clusterer (optional if regime filter disabled)
            pattern_matcher: Fitted pattern matcher (optional if matching disabled)
        """
        config = config or StateEnhancedConfig()
        super().__init__(config)

        # Initialize sub-components
        self._momentum = MomentumStrategy(config.momentum_config)

        # Regime filter (requires clusterer)
        self._regime_filter: RegimeFilter | None = None
        if config.enable_regime_filter:
            if clusterer is None:
                raise ValueError(
                    "RegimeClusterer required when enable_regime_filter=True"
                )
            self._regime_filter = RegimeFilter(clusterer, config.regime_filter_config)

        # Pattern matcher
        self._pattern_matcher = pattern_matcher
        if config.enable_pattern_matching and pattern_matcher is None:
            raise ValueError(
                "PatternMatcher required when enable_pattern_matching=True"
            )

        # Position sizer
        self._position_sizer: PositionSizer | None = None
        if config.enable_dynamic_sizing:
            self._position_sizer = PositionSizer(config.position_sizer_config)

        # Decision logging
        self._decisions: list[dict[str, Any]] = []

    @property
    def config(self) -> StateEnhancedConfig:
        """Return strategy configuration."""
        return self._config

    @property
    def required_features(self) -> list[str]:
        """Return required feature columns."""
        return self._momentum.required_features

    @property
    def regime_filter(self) -> RegimeFilter | None:
        """Return regime filter component."""
        return self._regime_filter

    @property
    def pattern_matcher(self) -> PatternMatcher | None:
        """Return pattern matcher component."""
        return self._pattern_matcher

    @property
    def position_sizer(self) -> PositionSizer | None:
        """Return position sizer component."""
        return self._position_sizer

    @property
    def decisions(self) -> list[dict[str, Any]]:
        """Return logged decisions."""
        return self._decisions

    def generate_signals(
        self,
        features: pd.DataFrame,
        timestamp: datetime,
        **kwargs: Any,
    ) -> list[Signal]:
        """Generate state-enhanced trading signals.

        Args:
            features: DataFrame with feature columns
            timestamp: Current timestamp
            **kwargs: Additional data including:
                - state: Current state vector (required if using state features)
                - states: Batch of state vectors for batch processing

        Returns:
            List of Signal objects
        """
        # Get state vector(s) from kwargs
        state = kwargs.get("state")
        states = kwargs.get("states")

        # 1. Generate baseline momentum signals
        base_signals = self._momentum.generate_signals(features, timestamp)

        if not base_signals:
            return []

        # Handle single state or batch
        if states is not None:
            return self._process_batch(base_signals, states, timestamp)

        # Single signal processing
        enhanced_signals = []
        for signal in base_signals:
            enhanced = self._enhance_signal(signal, state)
            self._record_signal(enhanced)
            enhanced_signals.append(enhanced)

        return enhanced_signals

    def _enhance_signal(
        self,
        signal: Signal,
        state: np.ndarray | None,
    ) -> Signal:
        """Apply all enhancements to a signal.

        Args:
            signal: Base momentum signal
            state: Current state vector

        Returns:
            Enhanced signal
        """
        # Start with base signal
        enhanced = signal

        # Track decision details
        decision = {
            "timestamp": signal.timestamp.isoformat(),
            "symbol": signal.symbol,
            "base_direction": str(signal.direction),
            "base_strength": signal.strength,
        }

        # 2. Apply regime filter
        if self._regime_filter is not None and state is not None:
            enhanced = self._regime_filter.apply(enhanced, state)
            decision["regime_label"] = enhanced.metadata.regime_label
            decision["regime_sharpe"] = enhanced.metadata.regime_sharpe
            decision["filtered"] = enhanced.direction == SignalDirection.FLAT and signal.direction != SignalDirection.FLAT

        # 3. Apply pattern matching
        if (
            self.config.enable_pattern_matching
            and self._pattern_matcher is not None
            and state is not None
            and enhanced.direction != SignalDirection.FLAT
        ):
            match = self._pattern_matcher.query(state)

            # Update metadata with pattern match info
            enhanced = Signal(
                timestamp=enhanced.timestamp,
                symbol=enhanced.symbol,
                direction=enhanced.direction,
                strength=enhanced.strength,
                size=enhanced.size,
                metadata=SignalMetadata(
                    regime_label=enhanced.metadata.regime_label,
                    regime_sharpe=enhanced.metadata.regime_sharpe,
                    pattern_match_count=len(match.indices),
                    pattern_expected_return=match.expected_return,
                    pattern_confidence=match.confidence,
                    momentum_value=enhanced.metadata.momentum_value,
                    volatility=enhanced.metadata.volatility,
                    custom=enhanced.metadata.custom,
                ),
            )

            # Adjust strength based on pattern confidence
            if match.confidence >= self.config.pattern_match_config.min_confidence:
                # Boost or reduce strength based on expected return direction
                if enhanced.is_long and match.expected_return > 0:
                    new_strength = min(1.0, enhanced.strength * (1 + match.confidence * 0.5))
                    enhanced = enhanced.with_strength(new_strength)
                elif enhanced.is_short and match.expected_return < 0:
                    new_strength = min(1.0, enhanced.strength * (1 + match.confidence * 0.5))
                    enhanced = enhanced.with_strength(new_strength)
                elif (enhanced.is_long and match.expected_return < -0.001) or \
                     (enhanced.is_short and match.expected_return > 0.001):
                    # Conflicting signal - reduce strength
                    new_strength = enhanced.strength * (1 - match.confidence * 0.3)
                    if new_strength < 0.2:
                        # Too weak - block the trade
                        enhanced = Signal(
                            timestamp=enhanced.timestamp,
                            symbol=enhanced.symbol,
                            direction=SignalDirection.FLAT,
                            strength=0.0,
                            metadata=enhanced.metadata,
                        )
                    else:
                        enhanced = enhanced.with_strength(new_strength)

            decision["pattern_match_count"] = len(match.indices)
            decision["pattern_expected_return"] = match.expected_return
            decision["pattern_confidence"] = match.confidence

        # 4. Apply position sizing
        if self._position_sizer is not None:
            enhanced = self._position_sizer.size(enhanced)
            decision["position_size"] = enhanced.size

        decision["final_direction"] = str(enhanced.direction)
        decision["final_strength"] = enhanced.strength

        # Log decision
        if self.config.log_decisions:
            self._decisions.append(decision)

        return enhanced

    def _process_batch(
        self,
        signals: list[Signal],
        states: np.ndarray,
        timestamp: datetime,
    ) -> list[Signal]:
        """Process a batch of signals with states.

        Args:
            signals: List of base signals
            states: State vectors (n_signals, latent_dim)
            timestamp: Current timestamp

        Returns:
            List of enhanced signals
        """
        if len(signals) != len(states):
            raise ValueError(
                f"Signals ({len(signals)}) and states ({len(states)}) must match"
            )

        enhanced = []
        for signal, state in zip(signals, states):
            result = self._enhance_signal(signal, state)
            self._record_signal(result)
            enhanced.append(result)

        return enhanced

    def update(self, features: pd.DataFrame, **kwargs: Any) -> None:
        """Update strategy state.

        Args:
            features: New feature data
            **kwargs: Additional data
        """
        super().update(features, **kwargs)
        self._momentum.update(features, **kwargs)

    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self._momentum.reset()
        self._decisions = []
        if self._regime_filter is not None:
            self._regime_filter.clear_decisions()

    def get_enhancement_stats(self) -> dict[str, Any]:
        """Get statistics about strategy enhancements.

        Returns:
            Dictionary with enhancement statistics
        """
        if not self._decisions:
            return {
                "total_signals": 0,
                "regime_filter_rate": 0.0,
                "pattern_boost_rate": 0.0,
                "avg_position_size": 0.0,
            }

        total = len(self._decisions)
        filtered = sum(1 for d in self._decisions if d.get("filtered", False))
        boosted = sum(
            1 for d in self._decisions
            if d.get("pattern_confidence", 0) >= self.config.pattern_match_config.min_confidence
        )
        sizes = [d.get("position_size", 0) for d in self._decisions]

        return {
            "total_signals": total,
            "regime_filter_rate": filtered / total if total > 0 else 0.0,
            "pattern_boost_rate": boosted / total if total > 0 else 0.0,
            "avg_position_size": sum(sizes) / len(sizes) if sizes else 0.0,
        }

    def set_regime_filter(self, clusterer: RegimeClusterer) -> None:
        """Set or update the regime filter.

        Args:
            clusterer: Fitted regime clusterer
        """
        self._regime_filter = RegimeFilter(clusterer, self.config.regime_filter_config)

    def set_pattern_matcher(self, matcher: PatternMatcher) -> None:
        """Set or update the pattern matcher.

        Args:
            matcher: Fitted pattern matcher
        """
        self._pattern_matcher = matcher
