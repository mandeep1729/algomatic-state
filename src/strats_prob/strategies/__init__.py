"""All 100 strategy definitions for the probe system."""

from src.strats_prob.strategies.trend import TREND_STRATEGIES
from src.strats_prob.strategies.mean_reversion import MEAN_REVERSION_STRATEGIES
from src.strats_prob.strategies.breakout import BREAKOUT_STRATEGIES
from src.strats_prob.strategies.volume_flow import VOLUME_FLOW_STRATEGIES
from src.strats_prob.strategies.pattern import PATTERN_STRATEGIES
from src.strats_prob.strategies.regime import REGIME_STRATEGIES

ALL_STRATEGIES = (
    TREND_STRATEGIES
    + MEAN_REVERSION_STRATEGIES
    + BREAKOUT_STRATEGIES
    + VOLUME_FLOW_STRATEGIES
    + PATTERN_STRATEGIES
    + REGIME_STRATEGIES
)
