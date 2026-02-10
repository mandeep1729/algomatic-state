"""Regime strategies (IDs 91-100)."""

from src.strats_prob.strategies.regime.adx_trend_range_switch import strategy as s91
from src.strats_prob.strategies.regime.volatility_regime_switch import strategy as s92
from src.strats_prob.strategies.regime.trend_quality_filter import strategy as s93
from src.strats_prob.strategies.regime.no_trade_filter import strategy as s94
from src.strats_prob.strategies.regime.dual_timeframe_filter import strategy as s95
from src.strats_prob.strategies.regime.trend_flat_mean_reversion import strategy as s96
from src.strats_prob.strategies.regime.volume_confirmed_breakout import strategy as s97
from src.strats_prob.strategies.regime.trend_mr_addon import strategy as s98
from src.strats_prob.strategies.regime.vol_breakout_failure_exit import strategy as s99
from src.strats_prob.strategies.regime.ensemble_vote import strategy as s100

REGIME_STRATEGIES = [s91, s92, s93, s94, s95, s96, s97, s98, s99, s100]
