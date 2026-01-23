"""Strategy creation helpers."""

from src.strategy.momentum import MomentumStrategy, MomentumConfig
from src.strategy.state_enhanced import StateEnhancedStrategy, StateEnhancedConfig
from src.strategy.regime_filter import RegimeFilterConfig
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig
from src.strategy.position_sizer import PositionSizerConfig
from src.state.clustering import RegimeClusterer


def create_momentum_config(
    symbols: list[str],
    long_threshold: float,
    short_threshold: float,
) -> MomentumConfig:
    """Create momentum strategy configuration."""
    return MomentumConfig(
        symbols=symbols,
        long_threshold=long_threshold,
        short_threshold=short_threshold,
    )


def create_momentum_strategy(
    symbols: list[str],
    long_threshold: float,
    short_threshold: float,
) -> MomentumStrategy:
    """Create baseline momentum strategy."""
    config = create_momentum_config(symbols, long_threshold, short_threshold)
    return MomentumStrategy(config)


def _create_position_sizer_config(base_size: float, max_size: float | None) -> PositionSizerConfig:
    """Create position sizer configuration."""
    if max_size is not None:
        return PositionSizerConfig(base_size=base_size, max_size=max_size)
    return PositionSizerConfig(base_size=base_size)


def create_state_enhanced_config(
    symbols: list[str], long_threshold: float, short_threshold: float,
    base_size: float, max_size: float | None = None, min_sharpe: float = 0.0,
    enable_regime_filter: bool = True, enable_pattern_matching: bool = False,
    enable_dynamic_sizing: bool = True,
) -> StateEnhancedConfig:
    """Create state-enhanced strategy configuration."""
    return StateEnhancedConfig(
        momentum_config=create_momentum_config(symbols, long_threshold, short_threshold),
        regime_filter_config=RegimeFilterConfig(min_sharpe=min_sharpe),
        pattern_match_config=PatternMatchConfig(k_neighbors=10, backend="sklearn"),
        position_sizer_config=_create_position_sizer_config(base_size, max_size),
        enable_regime_filter=enable_regime_filter,
        enable_pattern_matching=enable_pattern_matching,
        enable_dynamic_sizing=enable_dynamic_sizing,
    )


def create_pattern_matcher() -> PatternMatcher:
    """Create pattern matcher with default config."""
    return PatternMatcher(PatternMatchConfig(k_neighbors=10, backend="sklearn"))


def create_state_enhanced_strategy(
    config: StateEnhancedConfig,
    clusterer: RegimeClusterer,
    pattern_matcher: PatternMatcher | None = None,
) -> StateEnhancedStrategy:
    """Create state-enhanced strategy."""
    if pattern_matcher is None:
        pattern_matcher = create_pattern_matcher()
    return StateEnhancedStrategy(config, clusterer=clusterer, pattern_matcher=pattern_matcher)
