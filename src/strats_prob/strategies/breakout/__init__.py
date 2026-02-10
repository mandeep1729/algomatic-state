"""Breakout strategies (IDs 51-70)."""

from src.strats_prob.strategies.breakout.donchian_20_breakout import strategy as s51
from src.strats_prob.strategies.breakout.donchian_atr_filter import strategy as s52
from src.strats_prob.strategies.breakout.bb_breakout import strategy as s53
from src.strats_prob.strategies.breakout.bb_squeeze_breakout import strategy as s54
from src.strats_prob.strategies.breakout.atr_channel_breakout import strategy as s55
from src.strats_prob.strategies.breakout.range_expansion_breakout import strategy as s56
from src.strats_prob.strategies.breakout.opening_range_breakout import strategy as s57
from src.strats_prob.strategies.breakout.vol_stepup_break import strategy as s58
from src.strats_prob.strategies.breakout.keltner_breakout import strategy as s59
from src.strats_prob.strategies.breakout.adx_breakout import strategy as s60
from src.strats_prob.strategies.breakout.rsi_breakout import strategy as s61
from src.strats_prob.strategies.breakout.macd_breakout_confirmation import strategy as s62
from src.strats_prob.strategies.breakout.bb_walk_the_band import strategy as s63
from src.strats_prob.strategies.breakout.pivot_breakout import strategy as s64
from src.strats_prob.strategies.breakout.vcp_proxy import strategy as s65
from src.strats_prob.strategies.breakout.gap_and_go import strategy as s66
from src.strats_prob.strategies.breakout.inside_bar_breakout import strategy as s67
from src.strats_prob.strategies.breakout.one_two_three_breakout import strategy as s68
from src.strats_prob.strategies.breakout.atr_trailing_breakout import strategy as s69
from src.strats_prob.strategies.breakout.cmo_breakout import strategy as s70

BREAKOUT_STRATEGIES = [
    s51, s52, s53, s54, s55, s56, s57, s58, s59, s60,
    s61, s62, s63, s64, s65, s66, s67, s68, s69, s70,
]
