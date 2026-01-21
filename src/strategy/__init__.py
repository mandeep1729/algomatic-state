"""Trading strategy module.

This module provides the trading strategy layer for the algomatic-state system:
- Signal types and data structures
- Base strategy interface
- Baseline momentum strategy
- Regime-based trade filtering
- Historical pattern matching
- Dynamic position sizing
- Integrated state-enhanced strategy
"""

from src.strategy.signals import Signal, SignalDirection, SignalMetadata
from src.strategy.base import BaseStrategy, StrategyConfig
from src.strategy.momentum import MomentumStrategy, MomentumConfig
from src.strategy.regime_filter import RegimeFilter, RegimeFilterConfig
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig, PatternMatch
from src.strategy.position_sizer import PositionSizer, PositionSizerConfig
from src.strategy.state_enhanced import StateEnhancedStrategy, StateEnhancedConfig

__all__ = [
    # Signals
    "Signal",
    "SignalDirection",
    "SignalMetadata",
    # Base
    "BaseStrategy",
    "StrategyConfig",
    # Momentum
    "MomentumStrategy",
    "MomentumConfig",
    # Regime filter
    "RegimeFilter",
    "RegimeFilterConfig",
    # Pattern matcher
    "PatternMatcher",
    "PatternMatchConfig",
    "PatternMatch",
    # Position sizer
    "PositionSizer",
    "PositionSizerConfig",
    # State enhanced
    "StateEnhancedStrategy",
    "StateEnhancedConfig",
]
