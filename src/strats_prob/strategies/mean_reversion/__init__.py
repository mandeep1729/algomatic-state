"""Mean reversion strategies (IDs 26-50)."""

from src.strats_prob.strategies.mean_reversion.rsi_oversold_bounce import strategy as s26
from src.strats_prob.strategies.mean_reversion.rsi_overbought_fade import strategy as s27
from src.strats_prob.strategies.mean_reversion.bb_reversion_middle import strategy as s28
from src.strats_prob.strategies.mean_reversion.bb_double_tap_fade import strategy as s29
from src.strats_prob.strategies.mean_reversion.stoch_oversold_overbought import strategy as s30
from src.strats_prob.strategies.mean_reversion.willr_snapback import strategy as s31
from src.strats_prob.strategies.mean_reversion.cci_reversion import strategy as s32
from src.strats_prob.strategies.mean_reversion.mfi_extreme_fade import strategy as s33
from src.strats_prob.strategies.mean_reversion.rsi2_quick_mean_reversion import strategy as s34
from src.strats_prob.strategies.mean_reversion.price_ema_deviation import strategy as s35
from src.strats_prob.strategies.mean_reversion.zscore_sma20 import strategy as s36
from src.strats_prob.strategies.mean_reversion.bb_squeeze_fade import strategy as s37
from src.strats_prob.strategies.mean_reversion.donchian_middle_reversion import strategy as s38
from src.strats_prob.strategies.mean_reversion.rsi_divergence import strategy as s39
from src.strats_prob.strategies.mean_reversion.macd_divergence import strategy as s40
from src.strats_prob.strategies.mean_reversion.stoch_hook_extremes import strategy as s41
from src.strats_prob.strategies.mean_reversion.mean_reversion_vwap_proxy import strategy as s42
from src.strats_prob.strategies.mean_reversion.range_fade_adx_low import strategy as s43
from src.strats_prob.strategies.mean_reversion.bb_percentb_reversion import strategy as s44
from src.strats_prob.strategies.mean_reversion.cci_atr_exhaustion import strategy as s45
from src.strats_prob.strategies.mean_reversion.rsi_midline_range import strategy as s46
from src.strats_prob.strategies.mean_reversion.lower_bb_bullish_candle import strategy as s47
from src.strats_prob.strategies.mean_reversion.upper_bb_bearish_candle import strategy as s48
from src.strats_prob.strategies.mean_reversion.slow_ma_reversion import strategy as s49
from src.strats_prob.strategies.mean_reversion.pinch_reversion import strategy as s50

MEAN_REVERSION_STRATEGIES = [
    s26, s27, s28, s29, s30,
    s31, s32, s33, s34, s35,
    s36, s37, s38, s39, s40,
    s41, s42, s43, s44, s45,
    s46, s47, s48, s49, s50,
]
