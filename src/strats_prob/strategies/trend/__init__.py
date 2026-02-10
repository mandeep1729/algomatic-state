"""Trend strategies (IDs 1-25)."""

from src.strats_prob.strategies.trend.ema20_ema50_trend_cross import strategy as s1
from src.strats_prob.strategies.trend.ema50_ema200_golden_death_cross import strategy as s2
from src.strats_prob.strategies.trend.price_above_below_kama import strategy as s3
from src.strats_prob.strategies.trend.macd_signal_cross_trend_filter import strategy as s4
from src.strats_prob.strategies.trend.macd_hist_zero_line import strategy as s5
from src.strats_prob.strategies.trend.adx_rising_di_continuation import strategy as s6
from src.strats_prob.strategies.trend.sar_trend_ride import strategy as s7
from src.strats_prob.strategies.trend.trix_signal_cross import strategy as s8
from src.strats_prob.strategies.trend.apo_momentum_cross import strategy as s9
from src.strats_prob.strategies.trend.roc_break_sma200 import strategy as s10
from src.strats_prob.strategies.trend.momentum_pullback_ema20 import strategy as s11
from src.strats_prob.strategies.trend.momentum_pullback_bb_middle import strategy as s12
from src.strats_prob.strategies.trend.super_trend_atr_channel import strategy as s13
from src.strats_prob.strategies.trend.linear_reg_slope_filter import strategy as s14
from src.strats_prob.strategies.trend.aroon_trend_start import strategy as s15
from src.strats_prob.strategies.trend.ichimoku_lite import strategy as s16
from src.strats_prob.strategies.trend.trend_vol_expansion import strategy as s17
from src.strats_prob.strategies.trend.ppo_signal_cross import strategy as s18
from src.strats_prob.strategies.trend.ema_ribbon_compression_break import strategy as s19
from src.strats_prob.strategies.trend.trend_day_vwap_proxy import strategy as s20
from src.strats_prob.strategies.trend.di_pullback_entry import strategy as s21
from src.strats_prob.strategies.trend.trend_continuation_rsi_reset import strategy as s22
from src.strats_prob.strategies.trend.ma_envelope_break import strategy as s23
from src.strats_prob.strategies.trend.ht_trendline_cross import strategy as s24
from src.strats_prob.strategies.trend.three_bar_trend_ema import strategy as s25

TREND_STRATEGIES = [
    s1, s2, s3, s4, s5, s6, s7, s8, s9, s10,
    s11, s12, s13, s14, s15, s16, s17, s18, s19, s20,
    s21, s22, s23, s24, s25,
]
