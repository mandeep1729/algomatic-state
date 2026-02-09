"""Volume flow strategies (IDs 71-80)."""

from src.strats_prob.strategies.volume_flow.obv_breakout_confirmation import strategy as s71
from src.strats_prob.strategies.volume_flow.obv_trend_pullback import strategy as s72
from src.strats_prob.strategies.volume_flow.adosc_momentum import strategy as s73
from src.strats_prob.strategies.volume_flow.mfi_bb_breakout import strategy as s74
from src.strats_prob.strategies.volume_flow.volume_spike_trend import strategy as s75
from src.strats_prob.strategies.volume_flow.obv_divergence_reversal import strategy as s76
from src.strats_prob.strategies.volume_flow.chaikin_ad_trend import strategy as s77
from src.strats_prob.strategies.volume_flow.mfi_reversion_adx_low import strategy as s78
from src.strats_prob.strategies.volume_flow.obv_break_retest import strategy as s79
from src.strats_prob.strategies.volume_flow.price_breakout_accumulation import strategy as s80

VOLUME_FLOW_STRATEGIES = [s71, s72, s73, s74, s75, s76, s77, s78, s79, s80]
