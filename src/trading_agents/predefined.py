"""Predefined strategy seed data mapping all 100 go-strats strategies.

For predefined strategies:
- is_predefined=True, account_id=None (global)
- source_strategy_id = go-strats ID (1-100)
- Entry/exit conditions are executable DSL JSON arrays matching Go condition functions.
  Each condition is a dict with an "op" field and operator-specific parameters.
  The Go DSL compiler (go-strats/pkg/dsl/) compiles these into the same ConditionFn
  closures that the predefined go-strats registry uses.
"""


def get_predefined_strategies() -> list[dict]:
    """Return seed data for all 100 predefined strategies.

    Each dict matches the AgentStrategy model columns.
    """
    return [
        # =====================================================================
        # TREND STRATEGIES (1-25)
        # =====================================================================
        {
            "source_strategy_id": 1,
            "name": "ema20_ema50_trend_cross",
            "display_name": "EMA20/EMA50 Trend Cross",
            "description": "Classic dual-EMA crossover captures medium-term trend shifts.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "ema_20", "ref": {"col": "ema_50"}},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "ema_20", "ref": {"col": "ema_50"}},
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "ema_20", "ref": {"col": "ema_50"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "ema_20", "ref": {"col": "ema_50"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["ema_20", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 2,
            "name": "ema50_ema200_golden_death_cross",
            "display_name": "EMA50/EMA200 Golden/Death Cross",
            "description": "Slow crossover captures major trend reversals with wide stops.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "ema_50", "ref": {"col": "ema_200"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "ema_50", "ref": {"col": "ema_200"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "ema_50", "ref": {"col": "ema_200"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "ema_50", "ref": {"col": "ema_200"}},
            ],
            "atr_stop_mult": 2.5,
            "time_stop_bars": 120,
            "required_features": ["ema_50", "ema_200", "atr_14"],
        },
        {
            "source_strategy_id": 3,
            "name": "price_above_below_kama",
            "display_name": "Price Above/Below KAMA Trend",
            "description": "Adaptive moving average filters noise; price crossing KAMA signals trend change.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "kama_30"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "kama_30"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "kama_30"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "kama_30"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["kama_30", "atr_14"],
        },
        {
            "source_strategy_id": 4,
            "name": "macd_signal_cross_trend_filter",
            "display_name": "MACD Line/Signal Cross with Trend Filter",
            "description": "MACD crossover filtered by ADX ensures entries only in trending markets.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "macd", "ref": {"col": "macd_signal"}},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "macd", "ref": {"col": "macd_signal"}},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "macd", "ref": {"col": "macd_signal"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "macd", "ref": {"col": "macd_signal"}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["macd", "macd_signal", "adx_14", "atr_14"],
        },
        {
            "source_strategy_id": 5,
            "name": "macd_hist_zero_line",
            "display_name": "MACD Histogram Zero-Line",
            "description": "Histogram zero-line cross captures momentum shifts earlier than MACD line cross.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["macd_hist", "atr_14"],
        },
        {
            "source_strategy_id": 6,
            "name": "adx_rising_di_continuation",
            "display_name": "ADX Rising Trend Continuation (DI+/-)",
            "description": "Rising ADX with DI alignment confirms strengthening trend.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "plus_di_14", "ref": {"col": "minus_di_14"}},
                {"op": "rising", "col": "adx_14", "n": 3},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
            ],
            "entry_short": [
                {"op": "above", "col": "minus_di_14", "ref": {"col": "plus_di_14"}},
                {"op": "rising", "col": "adx_14", "n": 3},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "minus_di_14", "ref": {"col": "plus_di_14"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "plus_di_14", "ref": {"col": "minus_di_14"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["adx_14", "plus_di_14", "minus_di_14", "psar", "atr_14"],
        },
        {
            "source_strategy_id": 7,
            "name": "sar_trend_ride",
            "display_name": "SAR Trend Ride",
            "description": "Parabolic SAR provides built-in trailing stop that accelerates with trend.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "psar"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "psar"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "psar"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "psar"}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["psar", "atr_14"],
        },
        {
            "source_strategy_id": 8,
            "name": "trix_signal_cross",
            "display_name": "TRIX Signal Cross",
            "description": "Triple-smoothed EMA rate of change filters noise; signal cross confirms trend.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "trix_crosses_above_sma"},
            ],
            "entry_short": [
                {"op": "trix_crosses_below_sma"},
            ],
            "exit_long": [
                {"op": "trix_crosses_below_sma"},
            ],
            "exit_short": [
                {"op": "trix_crosses_above_sma"},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["trix_15", "atr_14"],
        },
        {
            "source_strategy_id": 9,
            "name": "apo_momentum_cross",
            "display_name": "APO Momentum Cross",
            "description": "Absolute Price Oscillator zero-line cross with EMA trend filter.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "apo", "ref": {"value": 0}},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "apo", "ref": {"value": 0}},
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "apo", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "apo", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["apo", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 10,
            "name": "roc_break_sma200",
            "display_name": "ROC Break in Direction of SMA200",
            "description": "Rate of Change zero-line break confirmed by long-term trend direction.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "crosses_above", "col": "roc_10", "ref": {"value": 0}},
            ],
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "crosses_below", "col": "roc_10", "ref": {"value": 0}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "roc_10", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "roc_10", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 30,
            "required_features": ["roc_10", "sma_200", "atr_14"],
        },
        {
            "source_strategy_id": 11,
            "name": "momentum_pullback_ema20",
            "display_name": "Momentum + Pullback to EMA20",
            "description": "Enter trending pullbacks at the fast EMA for high-probability continuation.",
            "category": "trend",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "pullback_to", "level_col": "ema_20", "tolerance_atr_mult": 0.5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["ema_20", "ema_50", "adx_14", "atr_14"],
        },
        {
            "source_strategy_id": 12,
            "name": "momentum_pullback_bb_middle",
            "display_name": "Momentum + Pullback to BB Middle",
            "description": "Bollinger middle band acts as dynamic support/resistance in trending markets.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
                {"op": "pullback_to", "level_col": "bb_middle", "tolerance_atr_mult": 0.5},
            ],
            "entry_short": [
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
                {"op": "pullback_below", "level_col": "bb_middle", "tolerance_atr_mult": 0.5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["bb_middle", "adx_14", "atr_14"],
        },
        {
            "source_strategy_id": 13,
            "name": "super_trend_atr_channel",
            "display_name": "Super Trend-like ATR Channel",
            "description": "ATR channel around EMA captures strong breakouts beyond normal volatility.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "close_above_upper_channel", "col": "ema_20", "multiplier": 2.0},
            ],
            "entry_short": [
                {"op": "close_below_lower_channel", "col": "ema_20", "multiplier": 2.0},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["ema_20", "atr_14"],
        },
        {
            "source_strategy_id": 14,
            "name": "linear_reg_slope_filter",
            "display_name": "Linear Regression Slope + Price Filter",
            "description": "Linear regression slope quantifies trend direction; combined with SMA filter.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "linearreg_slope_20", "ref": {"value": 0}},
                {"op": "above", "col": "close", "ref": {"col": "sma_50"}},
            ],
            "entry_short": [
                {"op": "below", "col": "linearreg_slope_20", "ref": {"value": 0}},
                {"op": "below", "col": "close", "ref": {"col": "sma_50"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "linearreg_slope_20", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "linearreg_slope_20", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 40,
            "required_features": ["linearreg_slope_20", "sma_50", "atr_14"],
        },
        {
            "source_strategy_id": 15,
            "name": "aroon_trend_start",
            "display_name": "Aroon Trend Start",
            "description": "Aroon oscillator detects new trend initiation when one direction dominates.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "aroon_up_25", "ref": {"value": 70}},
                {"op": "below", "col": "aroon_down_25", "ref": {"value": 30}},
            ],
            "entry_short": [
                {"op": "crosses_above", "col": "aroon_down_25", "ref": {"value": 70}},
                {"op": "below", "col": "aroon_up_25", "ref": {"value": 30}},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "aroon_down_25", "ref": {"value": 70}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "aroon_up_25", "ref": {"value": 70}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["aroon_up_25", "aroon_down_25", "atr_14"],
        },
        {
            "source_strategy_id": 16,
            "name": "ichimoku_lite",
            "display_name": "Ichimoku-lite (EMA proxy)",
            "description": "EMA stack alignment (20>50>200) proxies Ichimoku cloud bullish conditions.",
            "category": "trend",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "ema_20", "ref": {"col": "ema_50"}},
                {"op": "above", "col": "ema_50", "ref": {"col": "ema_200"}},
                {"op": "above", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "exit_long": [
                {"op": "any_of", "conditions": [
                    {"op": "below", "col": "ema_20", "ref": {"col": "ema_50"}},
                    {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
                ]},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["ema_20", "ema_50", "ema_200", "atr_14"],
        },
        {
            "source_strategy_id": 17,
            "name": "trend_vol_expansion",
            "display_name": "Trend + Volatility Expansion Confirmation",
            "description": "Breakout beyond BB bands with expanding width confirms genuine volatility expansion.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "breaks_above_level", "level_col": "bb_upper"},
                {"op": "bb_width_increasing", "n": 5},
            ],
            "entry_short": [
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "breaks_below_level", "level_col": "bb_lower"},
                {"op": "bb_width_increasing", "n": 5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["adx_14", "bb_upper", "bb_lower", "bb_middle", "bb_width", "atr_14"],
        },
        {
            "source_strategy_id": 18,
            "name": "ppo_signal_cross",
            "display_name": "PPO Signal Cross with Long-Term Filter",
            "description": "Percentage Price Oscillator normalises MACD; SMA200 filter ensures trend alignment.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "crosses_above", "col": "ppo", "ref": {"col": "ppo_signal"}},
            ],
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "crosses_below", "col": "ppo", "ref": {"col": "ppo_signal"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "ppo", "ref": {"col": "ppo_signal"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "ppo", "ref": {"col": "ppo_signal"}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["ppo", "ppo_signal", "sma_200", "atr_14"],
        },
        {
            "source_strategy_id": 19,
            "name": "ema_ribbon_compression_break",
            "display_name": "EMA Ribbon Compression Break",
            "description": "Tight EMA compression signals coiling energy; breakout indicates directional resolve.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "ribbon_break_long", "lookback": 10, "multiplier": 0.5},
            ],
            "entry_short": [
                {"op": "ribbon_break_short", "lookback": 10, "multiplier": 0.5},
            ],
            "exit_long": [
                {"op": "ribbon_exit_long", "multiplier": 0.5},
            ],
            "exit_short": [
                {"op": "ribbon_exit_short", "multiplier": 0.5},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["ema_20", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 20,
            "name": "trend_day_vwap_proxy",
            "display_name": "Trend Day Filter with VWAP Proxy",
            "description": "VWAP proxy with ADX and RSI filters identifies intraday trending conditions.",
            "category": "trend",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "typical_price_sma_20"}},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "above", "col": "rsi_14", "ref": {"value": 55}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "typical_price_sma_20"}},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 10,
            "required_features": ["typical_price_sma_20", "adx_14", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 21,
            "name": "di_pullback_entry",
            "display_name": "DI Pullback Entry",
            "description": "Enter trend pullbacks when RSI resets and DI direction is confirmed.",
            "category": "trend",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "plus_di_14", "ref": {"col": "minus_di_14"}},
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "was_below_then_crosses_above", "col": "rsi_14", "threshold": 50, "lookback": 5},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "minus_di_14", "ref": {"col": "plus_di_14"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["plus_di_14", "minus_di_14", "adx_14", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 22,
            "name": "trend_continuation_rsi_reset",
            "display_name": "Trend Continuation After RSI Reset",
            "description": "RSI dip-and-recover in an uptrend signals exhausted sellers and fresh momentum.",
            "category": "trend",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
                {"op": "was_below_then_crosses_above", "col": "rsi_14", "threshold": 50, "lookback": 10},
            ],
            "exit_long": [
                {"op": "any_of", "conditions": [
                    {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 45}},
                    {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
                ]},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["ema_50", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 23,
            "name": "ma_envelope_break",
            "display_name": "Moving Average Envelope Break",
            "description": "ATR-based envelope around SMA captures momentum breakouts normalized for volatility.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_sma_envelope", "col": "sma_20", "multiplier": 1.5},
            ],
            "entry_short": [
                {"op": "breaks_below_sma_envelope", "col": "sma_20", "multiplier": 1.5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "sma_20"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "sma_20"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["sma_20", "atr_14"],
        },
        {
            "source_strategy_id": 24,
            "name": "ht_trendline_cross",
            "display_name": "HT Trendline Cross (Hilbert)",
            "description": "Hilbert Transform trendline adapts to dominant cycle; cross signals trend change.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "ht_trendline"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "ht_trendline"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "ht_trendline"}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "ht_trendline"}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["ht_trendline", "atr_14"],
        },
        {
            "source_strategy_id": 25,
            "name": "three_bar_trend_ema",
            "display_name": "Three-Bar Trend with EMA Filter",
            "description": "Short-term momentum (3 consecutive directional closes) with EMA trend confirmation.",
            "category": "trend",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
                {"op": "consecutive_higher_closes", "n": 3},
            ],
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
                {"op": "consecutive_lower_closes", "n": 3},
            ],
            "exit_long": [
                {"op": "consecutive_lower_closes", "n": 2},
            ],
            "exit_short": [
                {"op": "consecutive_higher_closes", "n": 2},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 8,
            "required_features": ["ema_50", "atr_14"],
        },
        # =====================================================================
        # MEAN REVERSION STRATEGIES (26-50)
        # =====================================================================
        {
            "source_strategy_id": 26,
            "name": "rsi_oversold_bounce",
            "display_name": "RSI Oversold Bounce",
            "description": "Buy oversold dips in uptrending markets for mean reversion to the norm.",
            "category": "mean_reversion",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 30}},
            ],
            "exit_long": [
                {"op": "above", "col": "rsi_14", "ref": {"value": 55}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 2.5,
            "time_stop_bars": 20,
            "required_features": ["close", "sma_200", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 27,
            "name": "rsi_overbought_fade",
            "display_name": "RSI Overbought Fade",
            "description": "Fade overbought rallies in downtrending markets for mean reversion.",
            "category": "mean_reversion",
            "direction": "short_only",
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 70}},
            ],
            "exit_short": [
                {"op": "below", "col": "rsi_14", "ref": {"value": 45}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 2.5,
            "required_features": ["close", "sma_200", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 28,
            "name": "bb_reversion_middle",
            "display_name": "Bollinger Band Reversion to Middle",
            "description": "Price bouncing off Bollinger extremes tends to revert toward the middle band.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["close", "bb_upper", "bb_middle", "bb_lower", "atr_14"],
        },
        {
            "source_strategy_id": 29,
            "name": "bb_double_tap_fade",
            "display_name": "Bollinger Double Tap Fade",
            "description": "Multiple touches of Bollinger extremes with RSI confirmation increase reversion probability.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "double_tap_below_bb", "lookback": 5},
                {"op": "below", "col": "rsi_14", "ref": {"value": 35}},
                {"op": "crosses_above", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "entry_short": [
                {"op": "double_tap_above_bb", "lookback": 5},
                {"op": "above", "col": "rsi_14", "ref": {"value": 65}},
                {"op": "crosses_below", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["close", "bb_upper", "bb_middle", "bb_lower", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 30,
            "name": "stoch_oversold_overbought",
            "display_name": "Stoch Oversold/Overbought Cross",
            "description": "Stochastic crossovers at extreme zones signal short-term exhaustion and reversion.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "stoch_k", "ref": {"col": "stoch_d"}},
                {"op": "below", "col": "stoch_k", "ref": {"value": 20}},
                {"op": "below", "col": "stoch_d", "ref": {"value": 20}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "stoch_k", "ref": {"col": "stoch_d"}},
                {"op": "above", "col": "stoch_k", "ref": {"value": 80}},
                {"op": "above", "col": "stoch_d", "ref": {"value": 80}},
            ],
            "exit_long": [
                {"op": "above", "col": "stoch_k", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "stoch_k", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 10,
            "required_features": ["stoch_k", "stoch_d", "atr_14"],
        },
        {
            "source_strategy_id": 31,
            "name": "willr_snapback",
            "display_name": "Williams %R Snapback",
            "description": "Williams %R extreme reversals capture quick snapback momentum.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "willr_14", "ref": {"value": -80}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "willr_14", "ref": {"value": -20}},
            ],
            "exit_long": [
                {"op": "above", "col": "willr_14", "ref": {"value": -50}},
            ],
            "exit_short": [
                {"op": "below", "col": "willr_14", "ref": {"value": -50}},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 8,
            "required_features": ["willr_14", "atr_14"],
        },
        {
            "source_strategy_id": 32,
            "name": "cci_reversion",
            "display_name": "CCI +/-100 Reversion",
            "description": "CCI crossing back through extremes signals momentum exhaustion and reversion.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "cci_20", "ref": {"value": -100}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "cci_20", "ref": {"value": 100}},
            ],
            "exit_long": [
                {"op": "above", "col": "cci_20", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "below", "col": "cci_20", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 12,
            "required_features": ["cci_20", "atr_14"],
        },
        {
            "source_strategy_id": 33,
            "name": "mfi_extreme_fade",
            "display_name": "MFI Extreme Fade",
            "description": "Money Flow Index extremes combine price and volume for higher-quality reversion signals.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "mfi_14", "ref": {"value": 20}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "mfi_14", "ref": {"value": 80}},
            ],
            "exit_long": [
                {"op": "above", "col": "mfi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "mfi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["mfi_14", "atr_14"],
        },
        {
            "source_strategy_id": 34,
            "name": "rsi2_quick_mean_reversion",
            "display_name": "RSI(2) Quick Mean Reversion",
            "description": "Ultra-short RSI(2) extremes capture quick snapback moves with tight risk.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "rsi_2", "ref": {"value": 5}},
                {"op": "above", "col": "close", "ref": {"col": "sma_50"}},
            ],
            "entry_short": [
                {"op": "above", "col": "rsi_2", "ref": {"value": 95}},
                {"op": "below", "col": "close", "ref": {"col": "sma_50"}},
            ],
            "exit_long": [
                {"op": "above", "col": "rsi_2", "ref": {"value": 60}},
            ],
            "exit_short": [
                {"op": "below", "col": "rsi_2", "ref": {"value": 40}},
            ],
            "atr_stop_mult": 1.0,
            "time_stop_bars": 5,
            "required_features": ["rsi_2", "close", "sma_50", "atr_14"],
        },
        {
            "source_strategy_id": 35,
            "name": "price_ema_deviation",
            "display_name": "Price vs EMA Deviation Reversion",
            "description": "Extreme price deviation from EMA signals rubber-band snap-back potential.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "deviation_below", "col": "close", "ref_col": "ema_20", "atr_mult": 2.0},
            ],
            "entry_short": [
                {"op": "deviation_above", "col": "close", "ref_col": "ema_20", "atr_mult": 2.0},
            ],
            "exit_long": [
                {"op": "above", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "exit_short": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 2.0,
            "required_features": ["close", "ema_20", "atr_14"],
        },
        {
            "source_strategy_id": 36,
            "name": "zscore_sma20",
            "display_name": "Z-Score of Close vs SMA20",
            "description": "Statistical extremes (z-score beyond 2) with RSI confirmation signal reversion.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "zscore_20", "ref": {"value": -2}},
                {"op": "rising", "col": "rsi_14", "n": 2},
            ],
            "entry_short": [
                {"op": "above", "col": "zscore_20", "ref": {"value": 2}},
                {"op": "falling", "col": "rsi_14", "n": 2},
            ],
            "exit_long": [
                {"op": "above", "col": "zscore_20", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "below", "col": "zscore_20", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["zscore_20", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 37,
            "name": "bb_squeeze_fade",
            "display_name": "BB Squeeze Fade First Expansion",
            "description": "After extreme compression, the first breakout often fails; fading it captures the snap back.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "squeeze", "width_col": "bb_width", "lookback": 50},
                {"op": "below", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "entry_short": [
                {"op": "squeeze", "width_col": "bb_width", "lookback": 50},
                {"op": "above", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 10,
            "required_features": ["close", "bb_upper", "bb_middle", "bb_lower", "bb_width", "atr_14"],
        },
        {
            "source_strategy_id": 38,
            "name": "donchian_middle_reversion",
            "display_name": "Donchian Middle Reversion",
            "description": "Range-bound price reverting from Donchian extremes toward the midpoint.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "close", "ref": {"col": "donchian_low_20"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "close", "ref": {"col": "donchian_high_20"}},
            ],
            "exit_long": [
                {"op": "above", "col": "close", "ref": {"col": "donchian_mid_20"}},
            ],
            "exit_short": [
                {"op": "below", "col": "close", "ref": {"col": "donchian_mid_20"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["donchian_high_20", "donchian_low_20", "donchian_mid_20", "atr_14"],
        },
        {
            "source_strategy_id": 39,
            "name": "rsi_divergence",
            "display_name": "RSI Divergence",
            "description": "Price-RSI divergence reveals waning momentum; reversion follows as trend exhausts.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "bullish_divergence", "indicator_col": "rsi_14", "lookback": 5},
                {"op": "below", "col": "rsi_14", "ref": {"value": 40}},
            ],
            "entry_short": [
                {"op": "bearish_divergence", "indicator_col": "rsi_14", "lookback": 5},
                {"op": "above", "col": "rsi_14", "ref": {"value": 60}},
            ],
            "exit_long": [
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 25,
            "required_features": ["close", "high", "low", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 40,
            "name": "macd_divergence",
            "display_name": "MACD Divergence",
            "description": "MACD histogram divergence from price signals momentum exhaustion.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "bullish_divergence", "indicator_col": "macd_hist", "lookback": 10},
                {"op": "crosses_above", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "entry_short": [
                {"op": "bearish_divergence", "indicator_col": "macd_hist", "lookback": 10},
                {"op": "crosses_below", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "macd_hist", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.5,
            "time_stop_bars": 30,
            "required_features": ["close", "high", "low", "macd_hist", "atr_14"],
        },
        {
            "source_strategy_id": 41,
            "name": "stoch_hook_extremes",
            "display_name": "Stoch Hook at Extremes",
            "description": "Stochastic turning at extremes captures momentum reversal with tight timing.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "stoch_k", "ref": {"value": 20}},
                {"op": "rising", "col": "stoch_k", "n": 2},
            ],
            "entry_short": [
                {"op": "above", "col": "stoch_k", "ref": {"value": 80}},
                {"op": "falling", "col": "stoch_k", "n": 2},
            ],
            "exit_long": [
                {"op": "above", "col": "stoch_k", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "stoch_k", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 10,
            "required_features": ["stoch_k", "atr_14"],
        },
        {
            "source_strategy_id": 42,
            "name": "mean_reversion_vwap_proxy",
            "display_name": "Mean Reversion to VWAP Proxy",
            "description": "Deviation from typical price SMA with RSI filter captures intraday reversion.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "mean_rev_long", "ref_col": "typical_price_sma_20", "multiplier": 1.5},
                {"op": "below", "col": "rsi_14", "ref": {"value": 40}},
            ],
            "entry_short": [
                {"op": "mean_rev_short", "ref_col": "typical_price_sma_20", "multiplier": 1.5},
                {"op": "above", "col": "rsi_14", "ref": {"value": 60}},
            ],
            "exit_long": [
                {"op": "above", "col": "close", "ref": {"col": "typical_price_sma_20"}},
            ],
            "exit_short": [
                {"op": "below", "col": "close", "ref": {"col": "typical_price_sma_20"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 12,
            "required_features": ["typical_price_sma_20", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 43,
            "name": "range_fade_adx_low",
            "display_name": "Range Fade with ADX Low",
            "description": "Low ADX confirms ranging market; RSI extremes signal reversion opportunities.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "adx_14", "ref": {"value": 15}},
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 30}},
            ],
            "entry_short": [
                {"op": "below", "col": "adx_14", "ref": {"value": 15}},
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 70}},
            ],
            "exit_long": [
                {"op": "above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["adx_14", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 44,
            "name": "bb_percentb_reversion",
            "display_name": "BB PercentB Reversion",
            "description": "Bollinger %B crossing back from extremes signals mean reversion momentum.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "bb_percentb", "ref": {"value": 0.1}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "bb_percentb", "ref": {"value": 0.9}},
            ],
            "exit_long": [
                {"op": "above", "col": "bb_percentb", "ref": {"value": 0.5}},
            ],
            "exit_short": [
                {"op": "below", "col": "bb_percentb", "ref": {"value": 0.5}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["bb_percentb", "atr_14"],
        },
        {
            "source_strategy_id": 45,
            "name": "cci_atr_exhaustion",
            "display_name": "CCI + ATR Exhaustion Fade",
            "description": "Extreme CCI with wide range bar signals exhaustion; next close confirms reversal.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "cci_20", "ref": {"value": -200}},
                {"op": "range_exceeds_atr", "multiplier": 2.0},
                {"op": "consecutive_higher_closes", "n": 1},
            ],
            "entry_short": [
                {"op": "above", "col": "cci_20", "ref": {"value": 200}},
                {"op": "range_exceeds_atr", "multiplier": 2.0},
                {"op": "consecutive_lower_closes", "n": 1},
            ],
            "exit_long": [
                {"op": "above", "col": "cci_20", "ref": {"value": -100}},
            ],
            "exit_short": [
                {"op": "below", "col": "cci_20", "ref": {"value": 100}},
            ],
            "atr_stop_mult": 2.5,
            "atr_target_mult": 3.0,
            "required_features": ["cci_20", "atr_14"],
        },
        {
            "source_strategy_id": 46,
            "name": "rsi_midline_range",
            "display_name": "RSI Midline Range Strategy",
            "description": "RSI crossing 50 in low-ADX environments captures range momentum.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "adx_14", "ref": {"value": 20}},
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "entry_short": [
                {"op": "below", "col": "adx_14", "ref": {"value": 20}},
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 25,
            "required_features": ["adx_14", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 47,
            "name": "lower_bb_bullish_candle",
            "display_name": "Price Touches Lower BB + Bullish Candle",
            "description": "Bullish candle at lower Bollinger Band confirms demand overcoming supply.",
            "category": "mean_reversion",
            "direction": "long_only",
            "entry_long": [
                {"op": "below", "col": "low", "ref": {"col": "bb_lower"}},
                {"op": "any_of", "conditions": [
                    {"op": "candle_bullish", "pattern_col": "cdl_engulfing"},
                    {"op": "candle_bullish", "pattern_col": "cdl_harami"},
                ]},
            ],
            "exit_long": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["low", "bb_lower", "bb_middle", "cdl_engulfing", "cdl_harami", "atr_14"],
        },
        {
            "source_strategy_id": 48,
            "name": "upper_bb_bearish_candle",
            "display_name": "Upper BB + Bearish Candle",
            "description": "Bearish candle at upper Bollinger Band confirms supply overcoming demand.",
            "category": "mean_reversion",
            "direction": "short_only",
            "entry_short": [
                {"op": "above", "col": "high", "ref": {"col": "bb_upper"}},
                {"op": "any_of", "conditions": [
                    {"op": "candle_bearish", "pattern_col": "cdl_engulfing"},
                    {"op": "candle_bearish", "pattern_col": "cdl_shooting_star"},
                ]},
            ],
            "exit_short": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["high", "bb_upper", "bb_middle", "cdl_engulfing", "cdl_shooting_star", "atr_14"],
        },
        {
            "source_strategy_id": 49,
            "name": "slow_ma_reversion",
            "display_name": "Slow MA Mean Reversion (to SMA50)",
            "description": "Extreme deviation from slow MA with RSI filter captures position-scale reversions.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "deviation_below", "col": "close", "ref_col": "sma_50", "atr_mult": 2.0},
                {"op": "below", "col": "rsi_14", "ref": {"value": 40}},
            ],
            "entry_short": [
                {"op": "deviation_above", "col": "close", "ref_col": "sma_50", "atr_mult": 2.0},
                {"op": "above", "col": "rsi_14", "ref": {"value": 60}},
            ],
            "exit_long": [
                {"op": "above", "col": "close", "ref": {"col": "sma_50"}},
            ],
            "exit_short": [
                {"op": "below", "col": "close", "ref": {"col": "sma_50"}},
            ],
            "atr_stop_mult": 2.5,
            "time_stop_bars": 30,
            "required_features": ["close", "sma_50", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 50,
            "name": "pinch_reversion",
            "display_name": "Pinch Reversion",
            "description": "ATR contraction with low ADX signals coiling; RSI 50 cross triggers the snap.",
            "category": "mean_reversion",
            "direction": "long_short",
            "entry_long": [
                {"op": "atr_below_contracted_sma", "factor": 0.80},
                {"op": "below", "col": "adx_14", "ref": {"value": 20}},
                {"op": "was_below_then_crosses_above", "col": "rsi_14", "threshold": 50, "lookback": 10},
            ],
            "entry_short": [
                {"op": "atr_below_contracted_sma", "factor": 0.80},
                {"op": "below", "col": "adx_14", "ref": {"value": 20}},
                {"op": "was_above_then_crosses_below", "col": "rsi_14", "threshold": 50, "lookback": 10},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 25,
            "required_features": ["atr_14", "atr_sma_50", "adx_14", "rsi_14"],
        },
        # =====================================================================
        # BREAKOUT STRATEGIES (51-70)
        # =====================================================================
        {
            "source_strategy_id": 51,
            "name": "donchian_20_breakout",
            "display_name": "Donchian 20 High/Low Breakout",
            "description": "Classic channel breakout captures new highs/lows as trend initiators.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
            ],
            "entry_short": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
            ],
            "exit_long": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
            ],
            "exit_short": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 4.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["donchian_high_20", "donchian_low_20", "atr_14"],
        },
        {
            "source_strategy_id": 52,
            "name": "donchian_atr_filter",
            "display_name": "Donchian + ATR Filter",
            "description": "Donchian breakout filtered by expanded range confirms genuine momentum.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
                {"op": "range_exceeds_atr", "multiplier": 1.2},
            ],
            "entry_short": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
                {"op": "range_exceeds_atr", "multiplier": 1.2},
            ],
            "exit_long": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
            ],
            "exit_short": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["donchian_high_20", "donchian_low_20", "atr_14"],
        },
        {
            "source_strategy_id": 53,
            "name": "bb_breakout",
            "display_name": "BB Upper/Lower Breakout",
            "description": "Bollinger Band breakout with rising width confirms volatility expansion.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "bb_upper"}},
                {"op": "rising", "col": "bb_width", "n": 3},
            ],
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "bb_lower"}},
                {"op": "rising", "col": "bb_width", "n": 3},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["close", "bb_upper", "bb_lower", "bb_middle", "bb_width", "atr_14"],
        },
        {
            "source_strategy_id": 54,
            "name": "bb_squeeze_breakout",
            "display_name": "BB Squeeze Breakout",
            "description": "Bollinger squeeze identifies low-volatility consolidation; breakout signals expansion.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "squeeze", "width_col": "bb_width", "lookback": 60},
                {"op": "above", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "entry_short": [
                {"op": "squeeze", "width_col": "bb_width", "lookback": 60},
                {"op": "below", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["close", "bb_upper", "bb_lower", "bb_middle", "bb_width", "atr_14"],
        },
        {
            "source_strategy_id": 55,
            "name": "atr_channel_breakout",
            "display_name": "ATR Channel Breakout",
            "description": "Price breaking beyond ATR-scaled SMA channel signals strong directional momentum.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_sma_envelope", "col": "sma_20", "multiplier": 2.0},
            ],
            "entry_short": [
                {"op": "breaks_below_sma_envelope", "col": "sma_20", "multiplier": 2.0},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "sma_20"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "sma_20"}},
            ],
            "atr_stop_mult": 2.5,
            "atr_target_mult": 4.0,
            "required_features": ["sma_20", "atr_14"],
        },
        {
            "source_strategy_id": 56,
            "name": "range_expansion_breakout",
            "display_name": "Range Expansion Day Breakout",
            "description": "Extreme range expansion with directional close signals institutional activity.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "range_exceeds_atr", "multiplier": 1.8},
                {"op": "in_top_pct_of_range", "pct": 0.20},
            ],
            "entry_short": [
                {"op": "range_exceeds_atr", "multiplier": 1.8},
                {"op": "in_bottom_pct_of_range", "pct": 0.20},
            ],
            "atr_stop_mult": 1.5,
            "trailing_atr_mult": 1.5,
            "time_stop_bars": 10,
            "required_features": ["atr_14"],
        },
        {
            "source_strategy_id": 57,
            "name": "opening_range_breakout",
            "display_name": "Opening Range Breakout Proxy",
            "description": "Proxy of opening range using Donchian channels captures early-session momentum.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_5"},
            ],
            "entry_short": [
                {"op": "breaks_below_level", "level_col": "donchian_low_5"},
            ],
            "atr_stop_mult": 1.5,
            "trailing_atr_mult": 1.5,
            "time_stop_bars": 15,
            "required_features": ["donchian_high_5", "donchian_low_5", "atr_14"],
        },
        {
            "source_strategy_id": 58,
            "name": "vol_stepup_break",
            "display_name": "Volatility Step-Up + Break",
            "description": "Rising ATR with expanding bands confirms genuine volatility step-up for breakout.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "rising", "col": "atr_14", "n": 5},
                {"op": "rising", "col": "bb_width", "n": 5},
                {"op": "breaks_above_level", "level_col": "donchian_high_10"},
            ],
            "entry_short": [
                {"op": "rising", "col": "atr_14", "n": 5},
                {"op": "rising", "col": "bb_width", "n": 5},
                {"op": "breaks_below_level", "level_col": "donchian_low_10"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["atr_14", "bb_width", "donchian_high_10", "donchian_low_10"],
        },
        {
            "source_strategy_id": 59,
            "name": "keltner_breakout",
            "display_name": "Keltner-style Breakout",
            "description": "Keltner channel (EMA + ATR) breakout normalizes for volatility, reducing false signals.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "close_above_upper_channel", "col": "ema_20", "multiplier": 1.5},
            ],
            "entry_short": [
                {"op": "close_below_lower_channel", "col": "ema_20", "multiplier": 1.5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["ema_20", "atr_14"],
        },
        {
            "source_strategy_id": 60,
            "name": "adx_breakout",
            "display_name": "ADX Breakout (trend ignition)",
            "description": "ADX rising from low levels signals new trend ignition; breakout confirms direction.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
            ],
            "entry_short": [
                {"op": "crosses_above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["adx_14", "donchian_high_20", "donchian_low_20", "atr_14"],
        },
        {
            "source_strategy_id": 61,
            "name": "rsi_breakout",
            "display_name": "RSI Breakout (momentum ignition)",
            "description": "RSI crossing key levels with price breakout confirms momentum ignition.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 60}},
                {"op": "breaks_above_level", "level_col": "donchian_high_10"},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 40}},
                {"op": "breaks_below_level", "level_col": "donchian_low_10"},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 25,
            "required_features": ["rsi_14", "donchian_high_10", "donchian_low_10", "atr_14"],
        },
        {
            "source_strategy_id": 62,
            "name": "macd_breakout_confirmation",
            "display_name": "MACD Breakout Confirmation",
            "description": "Price breakout confirmed by MACD alignment reduces false breakout risk.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
                {"op": "above", "col": "macd", "ref": {"value": 0}},
            ],
            "entry_short": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
                {"op": "below", "col": "macd", "ref": {"value": 0}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "macd", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "macd", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["donchian_high_20", "donchian_low_20", "macd", "atr_14"],
        },
        {
            "source_strategy_id": 63,
            "name": "bb_walk_the_band",
            "display_name": "Bollinger Walk the Band",
            "description": "Consecutive closes beyond Bollinger Band signal persistent trend momentum.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "bb_upper"}},
                {"op": "consecutive_higher_closes", "n": 3},
            ],
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "bb_lower"}},
                {"op": "consecutive_lower_closes", "n": 3},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["close", "bb_upper", "bb_lower", "atr_14"],
        },
        {
            "source_strategy_id": 64,
            "name": "pivot_breakout",
            "display_name": "Pivot Breakout",
            "description": "Pivot level breakout captures intraday directional momentum.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "close_above_upper_channel", "col": "typical_price_sma_1", "multiplier": 1.0},
            ],
            "entry_short": [
                {"op": "close_below_lower_channel", "col": "typical_price_sma_1", "multiplier": 1.0},
            ],
            "atr_stop_mult": 1.5,
            "time_stop_bars": 15,
            "required_features": ["typical_price_sma_1", "atr_14"],
        },
        {
            "source_strategy_id": 65,
            "name": "vcp_proxy",
            "display_name": "Volatility Contraction Pattern Proxy",
            "description": "Decreasing ATR with higher lows signals coiling energy; breakout captures expansion.",
            "category": "breakout",
            "direction": "long_only",
            "entry_long": [
                {"op": "falling", "col": "atr_14", "n": 10},
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["atr_14", "donchian_high_20"],
        },
        {
            "source_strategy_id": 66,
            "name": "gap_and_go",
            "display_name": "Gap + Go",
            "description": "Gaps backed by directional close signal continuation momentum.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "gap_up", "atr_mult": 1.0},
                {"op": "above", "col": "close", "ref": {"col": "open"}},
            ],
            "entry_short": [
                {"op": "gap_down", "atr_mult": 1.0},
                {"op": "below", "col": "close", "ref": {"col": "open"}},
            ],
            "atr_stop_mult": 1.5,
            "trailing_atr_mult": 1.5,
            "time_stop_bars": 10,
            "required_features": ["open", "close", "atr_14"],
        },
        {
            "source_strategy_id": 67,
            "name": "inside_bar_breakout",
            "display_name": "Inside Bar Breakout",
            "description": "Narrowest range bar signals compression; breakout captures directional expansion.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "narrowest_range", "lookback": 7},
                {"op": "above", "col": "close", "ref": {"col": "high"}},
            ],
            "entry_short": [
                {"op": "narrowest_range", "lookback": 7},
                {"op": "below", "col": "close", "ref": {"col": "low"}},
            ],
            "atr_stop_mult": 1.5,
            "atr_target_mult": 2.5,
            "time_stop_bars": 10,
            "required_features": ["atr_14"],
        },
        {
            "source_strategy_id": 68,
            "name": "one_two_three_breakout",
            "display_name": "1-2-3 Breakout",
            "description": "Swing low formation then break above pullback high signals trend continuation.",
            "category": "breakout",
            "direction": "long_only",
            "entry_long": [
                {"op": "rising", "col": "close", "n": 2},
                {"op": "breaks_above_level", "level_col": "donchian_high_10"},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["donchian_high_10", "atr_14"],
        },
        {
            "source_strategy_id": 69,
            "name": "atr_trailing_breakout",
            "display_name": "ATR Trailing Breakout",
            "description": "Close exceeding prior close by full ATR signals strong momentum thrust.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "close_above_upper_channel", "col": "close", "multiplier": 1.0},
            ],
            "entry_short": [
                {"op": "close_below_lower_channel", "col": "close", "multiplier": 1.0},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["atr_14"],
        },
        {
            "source_strategy_id": 70,
            "name": "cmo_breakout",
            "display_name": "Chande Momentum Oscillator Breakout",
            "description": "Strong CMO reading with price breakout confirms momentum-driven move.",
            "category": "breakout",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "cmo_14", "ref": {"value": 40}},
                {"op": "breaks_above_level", "level_col": "donchian_high_10"},
            ],
            "entry_short": [
                {"op": "below", "col": "cmo_14", "ref": {"value": -40}},
                {"op": "breaks_below_level", "level_col": "donchian_low_10"},
            ],
            "exit_long": [
                {"op": "below", "col": "cmo_14", "ref": {"value": 10}},
            ],
            "exit_short": [
                {"op": "above", "col": "cmo_14", "ref": {"value": -10}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["cmo_14", "donchian_high_10", "donchian_low_10", "atr_14"],
        },
        # =====================================================================
        # VOLUME FLOW STRATEGIES (71-80)
        # =====================================================================
        {
            "source_strategy_id": 71,
            "name": "obv_breakout_confirmation",
            "display_name": "OBV Breakout Confirmation",
            "description": "Price breakouts confirmed by volume flow (OBV) breakouts have higher conviction.",
            "category": "volume_flow",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
                {"op": "breaks_above_level", "level_col": "obv_high_20"},
            ],
            "entry_short": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
                {"op": "breaks_below_level", "level_col": "obv_low_20"},
            ],
            "exit_long": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
            ],
            "exit_short": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["donchian_high_20", "donchian_low_20", "obv", "obv_high_20", "obv_low_20", "atr_14"],
        },
        {
            "source_strategy_id": 72,
            "name": "obv_trend_pullback",
            "display_name": "OBV Trend + Pullback",
            "description": "OBV above its SMA confirms accumulation; pullback to EMA20 is a high-quality entry.",
            "category": "volume_flow",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "obv", "ref": {"col": "obv_sma_20"}},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
                {"op": "pullback_to", "level_col": "ema_20", "tolerance_atr_mult": 0.5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["obv", "obv_sma_20", "ema_20", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 73,
            "name": "adosc_momentum",
            "display_name": "ADOSC Momentum",
            "description": "Accumulation/Distribution oscillator zero-line cross confirms volume-backed momentum.",
            "category": "volume_flow",
            "direction": "long_short",
            "entry_long": [
                {"op": "crosses_above", "col": "adosc", "ref": {"value": 0}},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "entry_short": [
                {"op": "crosses_below", "col": "adosc", "ref": {"value": 0}},
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "adosc", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "adosc", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "required_features": ["adosc", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 74,
            "name": "mfi_bb_breakout",
            "display_name": "MFI + BB Breakout",
            "description": "Bollinger breakout confirmed by strong MFI validates volume participation.",
            "category": "volume_flow",
            "direction": "long_short",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "bb_upper"}},
                {"op": "above", "col": "mfi_14", "ref": {"value": 60}},
            ],
            "entry_short": [
                {"op": "below", "col": "close", "ref": {"col": "bb_lower"}},
                {"op": "below", "col": "mfi_14", "ref": {"value": 40}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["close", "bb_upper", "bb_lower", "bb_middle", "mfi_14", "atr_14"],
        },
        {
            "source_strategy_id": 75,
            "name": "volume_spike_trend",
            "display_name": "Volume Spike Trend Continuation",
            "description": "Volume spike with trend alignment signals institutional participation.",
            "category": "volume_flow",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "sma_50"}},
                {"op": "above", "col": "volume", "ref": {"col": "volume_sma_20_2x"}},
                {"op": "in_top_pct_of_range", "pct": 0.25},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["close", "sma_50", "volume", "volume_sma_20_2x", "atr_14"],
        },
        {
            "source_strategy_id": 76,
            "name": "obv_divergence_reversal",
            "display_name": "OBV Divergence Reversal",
            "description": "OBV-price divergence reveals hidden accumulation/distribution before reversals.",
            "category": "volume_flow",
            "direction": "long_short",
            "entry_long": [
                {"op": "bullish_divergence", "indicator_col": "obv", "lookback": 10},
            ],
            "entry_short": [
                {"op": "bearish_divergence", "indicator_col": "obv", "lookback": 10},
            ],
            "atr_stop_mult": 2.5,
            "atr_target_mult": 3.0,
            "time_stop_bars": 25,
            "required_features": ["close", "high", "low", "obv", "atr_14"],
        },
        {
            "source_strategy_id": 77,
            "name": "chaikin_ad_trend",
            "display_name": "Chaikin A/D Line Trend",
            "description": "Persistent ADOSC direction confirms institutional flow aligned with price trend.",
            "category": "volume_flow",
            "direction": "long_short",
            "entry_long": [
                {"op": "held_above", "col": "adosc", "threshold": 0, "n": 5},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "entry_short": [
                {"op": "held_below", "col": "adosc", "threshold": 0, "n": 5},
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_long": [
                {"op": "crosses_below", "col": "adosc", "ref": {"value": 0}},
            ],
            "exit_short": [
                {"op": "crosses_above", "col": "adosc", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["adosc", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 78,
            "name": "mfi_reversion_adx_low",
            "display_name": "MFI Reversion with ADX Low",
            "description": "MFI extremes in low-ADX environments signal high-probability reversion.",
            "category": "volume_flow",
            "direction": "long_short",
            "entry_long": [
                {"op": "below", "col": "adx_14", "ref": {"value": 15}},
                {"op": "crosses_above", "col": "mfi_14", "ref": {"value": 20}},
            ],
            "entry_short": [
                {"op": "below", "col": "adx_14", "ref": {"value": 15}},
                {"op": "crosses_below", "col": "mfi_14", "ref": {"value": 80}},
            ],
            "exit_long": [
                {"op": "above", "col": "mfi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "mfi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["adx_14", "mfi_14", "atr_14"],
        },
        {
            "source_strategy_id": 79,
            "name": "obv_break_retest",
            "display_name": "OBV Break then Retest",
            "description": "OBV breakout followed by price pullback and recovery is high-conviction continuation.",
            "category": "volume_flow",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "obv", "ref": {"col": "obv_high_20"}},
                {"op": "pullback_to", "level_col": "ema_20", "tolerance_atr_mult": 1.0},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "time_stop_bars": 40,
            "required_features": ["obv", "obv_high_20", "ema_20", "atr_14"],
        },
        {
            "source_strategy_id": 80,
            "name": "price_breakout_accumulation",
            "display_name": "Price Breakout + Positive Accumulation",
            "description": "Price breakout backed by rising ADOSC confirms institutional accumulation.",
            "category": "volume_flow",
            "direction": "long_only",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
                {"op": "rising", "col": "adosc", "n": 3},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["donchian_high_20", "adosc", "atr_14"],
        },
        # =====================================================================
        # PATTERN STRATEGIES (81-90)
        # =====================================================================
        {
            "source_strategy_id": 81,
            "name": "bullish_engulfing_trend",
            "display_name": "Bullish Engulfing + Trend Filter",
            "description": "A bullish engulfing pattern in an uptrend signals strong demand overwhelming recent supply.",
            "category": "pattern",
            "direction": "long_only",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_engulfing"},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["cdl_engulfing", "ema_20", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 82,
            "name": "bearish_engulfing_trend",
            "display_name": "Bearish Engulfing + Trend Filter",
            "description": "A bearish engulfing pattern in a downtrend signals strong supply overwhelming recent demand.",
            "category": "pattern",
            "direction": "short_only",
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_engulfing"},
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["cdl_engulfing", "ema_20", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 83,
            "name": "hammer_lower_bb",
            "display_name": "Hammer at Lower BB",
            "description": "Hammer candle at lower Bollinger Band signals rejection of lower prices.",
            "category": "pattern",
            "direction": "long_only",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_hammer"},
                {"op": "below", "col": "low", "ref": {"col": "bb_lower"}},
            ],
            "exit_long": [
                {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["cdl_hammer", "low", "bb_lower", "bb_middle", "atr_14"],
        },
        {
            "source_strategy_id": 84,
            "name": "shooting_star_upper_bb",
            "display_name": "Shooting Star at Upper BB",
            "description": "Shooting star candle at upper Bollinger Band signals rejection of higher prices.",
            "category": "pattern",
            "direction": "short_only",
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_shooting_star"},
                {"op": "above", "col": "high", "ref": {"col": "bb_upper"}},
            ],
            "exit_short": [
                {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["cdl_shooting_star", "high", "bb_upper", "bb_middle", "atr_14"],
        },
        {
            "source_strategy_id": 85,
            "name": "morning_star_reversal",
            "display_name": "Morning Star Reversal",
            "description": "Three-candle morning star pattern signals bullish reversal at support.",
            "category": "pattern",
            "direction": "long_only",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_morning_star"},
            ],
            "atr_stop_mult": 2.5,
            "atr_target_mult": 3.0,
            "time_stop_bars": 30,
            "required_features": ["cdl_morning_star", "atr_14"],
        },
        {
            "source_strategy_id": 86,
            "name": "evening_star_reversal",
            "display_name": "Evening Star Reversal",
            "description": "Three-candle evening star pattern signals bearish reversal at resistance.",
            "category": "pattern",
            "direction": "short_only",
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_evening_star"},
            ],
            "atr_stop_mult": 2.5,
            "atr_target_mult": 3.0,
            "time_stop_bars": 30,
            "required_features": ["cdl_evening_star", "atr_14"],
        },
        {
            "source_strategy_id": 87,
            "name": "doji_trend_exhaustion",
            "display_name": "Doji + Trend Exhaustion",
            "description": "Doji with wide range and RSI non-extreme signals indecision after strong move.",
            "category": "pattern",
            "direction": "long_short",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_doji"},
                {"op": "range_exceeds_atr", "multiplier": 1.8},
                {"op": "below", "col": "rsi_14", "ref": {"value": 45}},
                {"op": "consecutive_higher_closes", "n": 1},
            ],
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_doji"},
                {"op": "range_exceeds_atr", "multiplier": 1.8},
                {"op": "above", "col": "rsi_14", "ref": {"value": 55}},
                {"op": "consecutive_lower_closes", "n": 1},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 2.5,
            "time_stop_bars": 20,
            "required_features": ["cdl_doji", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 88,
            "name": "three_soldiers_crows",
            "display_name": "Three White Soldiers / Three Black Crows",
            "description": "Three consecutive strong directional candles signal sustained momentum.",
            "category": "pattern",
            "direction": "long_short",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_3white_soldiers"},
            ],
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_3black_crows"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["cdl_3white_soldiers", "cdl_3black_crows", "atr_14"],
        },
        {
            "source_strategy_id": 89,
            "name": "harami_rsi_confirm",
            "display_name": "Harami + RSI Confirm",
            "description": "Harami pattern with RSI confirmation signals high-quality reversal setup.",
            "category": "pattern",
            "direction": "long_short",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_harami"},
                {"op": "below", "col": "rsi_14", "ref": {"value": 45}},
                {"op": "rising", "col": "rsi_14", "n": 2},
            ],
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_harami"},
                {"op": "above", "col": "rsi_14", "ref": {"value": 55}},
                {"op": "falling", "col": "rsi_14", "n": 2},
            ],
            "exit_long": [
                {"op": "above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 25,
            "required_features": ["cdl_harami", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 90,
            "name": "marubozu_breakout",
            "display_name": "Marubozu Breakout Continuation",
            "description": "Marubozu (strong body, no wicks) with price breakout signals conviction momentum.",
            "category": "pattern",
            "direction": "long_short",
            "entry_long": [
                {"op": "candle_bullish", "pattern_col": "cdl_marubozu"},
                {"op": "breaks_above_level", "level_col": "donchian_high_10"},
            ],
            "entry_short": [
                {"op": "candle_bearish", "pattern_col": "cdl_marubozu"},
                {"op": "breaks_below_level", "level_col": "donchian_low_10"},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "time_stop_bars": 20,
            "required_features": ["cdl_marubozu", "donchian_high_10", "donchian_low_10", "atr_14"],
        },
        # =====================================================================
        # REGIME / MULTI-FILTER STRATEGIES (91-100)
        # =====================================================================
        {
            "source_strategy_id": 91,
            "name": "adx_trend_range_switch",
            "display_name": "ADX Trend vs Range Switch",
            "description": "Adapting strategy to the current regime (trending vs ranging) avoids whipsaws.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "any_of", "conditions": [
                    {"op": "all_of", "conditions": [
                        {"op": "above", "col": "adx_14", "ref": {"value": 25}},
                        {"op": "crosses_above", "col": "ema_20", "ref": {"col": "ema_50"}},
                    ]},
                    {"op": "all_of", "conditions": [
                        {"op": "below", "col": "adx_14", "ref": {"value": 18}},
                        {"op": "crosses_above", "col": "close", "ref": {"col": "bb_lower"}},
                    ]},
                ]},
            ],
            "entry_short": [
                {"op": "any_of", "conditions": [
                    {"op": "all_of", "conditions": [
                        {"op": "above", "col": "adx_14", "ref": {"value": 25}},
                        {"op": "crosses_below", "col": "ema_20", "ref": {"col": "ema_50"}},
                    ]},
                    {"op": "all_of", "conditions": [
                        {"op": "below", "col": "adx_14", "ref": {"value": 18}},
                        {"op": "crosses_below", "col": "close", "ref": {"col": "bb_upper"}},
                    ]},
                ]},
            ],
            "exit_long": [
                {"op": "any_of", "conditions": [
                    {"op": "crosses_below", "col": "ema_20", "ref": {"col": "ema_50"}},
                    {"op": "above", "col": "close", "ref": {"col": "bb_middle"}},
                ]},
            ],
            "exit_short": [
                {"op": "any_of", "conditions": [
                    {"op": "crosses_above", "col": "ema_20", "ref": {"col": "ema_50"}},
                    {"op": "below", "col": "close", "ref": {"col": "bb_middle"}},
                ]},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["adx_14", "ema_20", "ema_50", "bb_upper", "bb_lower", "bb_middle", "atr_14"],
        },
        {
            "source_strategy_id": 92,
            "name": "volatility_regime_switch",
            "display_name": "Volatility Regime Switch",
            "description": "Switching between breakout and mean reversion based on volatility regime aligns strategy with market conditions.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "any_of", "conditions": [
                    {"op": "all_of", "conditions": [
                        {"op": "above", "col": "atr_14", "ref": {"col": "atr_sma_50"}},
                        {"op": "breaks_above_level", "level_col": "donchian_high_20"},
                    ]},
                    {"op": "all_of", "conditions": [
                        {"op": "atr_below_contracted_sma", "factor": 0.85},
                        {"op": "mean_rev_long", "ref_col": "typical_price_sma_20", "multiplier": 1.5},
                    ]},
                ]},
            ],
            "entry_short": [
                {"op": "any_of", "conditions": [
                    {"op": "all_of", "conditions": [
                        {"op": "above", "col": "atr_14", "ref": {"col": "atr_sma_50"}},
                        {"op": "breaks_below_level", "level_col": "donchian_low_20"},
                    ]},
                    {"op": "all_of", "conditions": [
                        {"op": "atr_below_contracted_sma", "factor": 0.85},
                        {"op": "mean_rev_short", "ref_col": "typical_price_sma_20", "multiplier": 1.5},
                    ]},
                ]},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["atr_14", "atr_sma_50", "donchian_high_20", "donchian_low_20", "typical_price_sma_20"],
        },
        {
            "source_strategy_id": 93,
            "name": "trend_quality_filter",
            "display_name": "Trend Quality Filter",
            "description": "Combining trend strength (ADX), expanding volatility (BB width), and pullback timing produces higher quality trend entries.",
            "category": "regime",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "adx_14", "ref": {"value": 20}},
                {"op": "rising", "col": "bb_width", "n": 3},
                {"op": "pullback_to", "level_col": "ema_20", "tolerance_atr_mult": 0.5},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["adx_14", "bb_width", "ema_20", "atr_14"],
        },
        {
            "source_strategy_id": 94,
            "name": "no_trade_filter",
            "display_name": "No-Trade Filter Strategy",
            "description": "Filtering out unfavorable conditions before entering improves overall strategy quality.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "adx_in_range", "low": 18, "high": 35},
                {"op": "atr_not_bottom_pct", "pct": 20, "lookback": 200},
                {"op": "crosses_above", "col": "roc_10", "ref": {"value": 0}},
                {"op": "above", "col": "close", "ref": {"col": "sma_200"}},
            ],
            "entry_short": [
                {"op": "adx_in_range", "low": 18, "high": 35},
                {"op": "atr_not_bottom_pct", "pct": 20, "lookback": 200},
                {"op": "crosses_below", "col": "roc_10", "ref": {"value": 0}},
                {"op": "below", "col": "close", "ref": {"col": "sma_200"}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 15,
            "required_features": ["adx_14", "atr_14", "roc_10", "sma_200"],
        },
        {
            "source_strategy_id": 95,
            "name": "dual_timeframe_filter",
            "display_name": "Dual-Timeframe Filter",
            "description": "Using a slow MA as a higher-timeframe proxy ensures entries align with the broader trend.",
            "category": "regime",
            "direction": "long_only",
            "entry_long": [
                {"op": "above", "col": "close", "ref": {"col": "sma_200"}},
                {"op": "was_below_then_crosses_above", "col": "rsi_14", "threshold": 50, "lookback": 10},
                {"op": "above", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_20"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["sma_200", "rsi_14", "ema_20", "atr_14"],
        },
        {
            "source_strategy_id": 96,
            "name": "trend_flat_mean_reversion",
            "display_name": "Trend Flat Mean Reversion",
            "description": "Mean reversion strategies work best when there is no underlying trend; filtering by slope near zero avoids fighting momentum.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "flat_slope", "col": "linearreg_slope_20", "epsilon": 0.001},
                {"op": "crosses_above", "col": "rsi_14", "ref": {"value": 30}},
            ],
            "entry_short": [
                {"op": "flat_slope", "col": "linearreg_slope_20", "epsilon": 0.001},
                {"op": "crosses_below", "col": "rsi_14", "ref": {"value": 70}},
            ],
            "exit_long": [
                {"op": "above", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "exit_short": [
                {"op": "below", "col": "rsi_14", "ref": {"value": 50}},
            ],
            "atr_stop_mult": 2.0,
            "time_stop_bars": 25,
            "required_features": ["linearreg_slope_20", "rsi_14", "atr_14"],
        },
        {
            "source_strategy_id": 97,
            "name": "volume_confirmed_breakout",
            "display_name": "Breakout Only When Volume/Flow Confirms",
            "description": "Requiring multiple volume/flow confirmations filters out false breakouts.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "breaks_above_level", "level_col": "donchian_high_20"},
                {"op": "breaks_above_level", "level_col": "obv_high_20"},
                {"op": "above", "col": "adosc", "ref": {"value": 0}},
            ],
            "entry_short": [
                {"op": "breaks_below_level", "level_col": "donchian_low_20"},
                {"op": "breaks_below_level", "level_col": "obv_low_20"},
                {"op": "below", "col": "adosc", "ref": {"value": 0}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["donchian_high_20", "donchian_low_20", "obv", "obv_high_20", "obv_low_20", "adosc", "atr_14"],
        },
        {
            "source_strategy_id": 98,
            "name": "trend_mr_addon",
            "display_name": "Trend + Mean Reversion Add-on",
            "description": "Entering on a trend signal combined with mean reversion timing improves entry quality.",
            "category": "regime",
            "direction": "long_only",
            "entry_long": [
                {"op": "crosses_above", "col": "ema_20", "ref": {"col": "ema_50"}},
                {"op": "above", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "ema_50"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["ema_20", "ema_50", "atr_14"],
        },
        {
            "source_strategy_id": 99,
            "name": "vol_breakout_failure_exit",
            "display_name": "Volatility Breakout with Failure Exit",
            "description": "Adding a failure exit to the classic squeeze breakout cuts losses quickly when the breakout does not follow through.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "squeeze", "width_col": "bb_width", "lookback": 60},
                {"op": "above", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "entry_short": [
                {"op": "squeeze", "width_col": "bb_width", "lookback": 60},
                {"op": "below", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "exit_long": [
                {"op": "below", "col": "close", "ref": {"col": "bb_upper"}},
            ],
            "exit_short": [
                {"op": "above", "col": "close", "ref": {"col": "bb_lower"}},
            ],
            "atr_stop_mult": 2.0,
            "trailing_atr_mult": 2.0,
            "required_features": ["bb_upper", "bb_lower", "bb_width", "atr_14"],
        },
        {
            "source_strategy_id": 100,
            "name": "ensemble_vote",
            "display_name": "Ensemble Vote (3-Strategy Majority)",
            "description": "Combining multiple independent signals via majority vote reduces false signals and increases conviction.",
            "category": "regime",
            "direction": "long_short",
            "entry_long": [
                {"op": "majority_bull"},
            ],
            "entry_short": [
                {"op": "majority_bear"},
            ],
            "exit_long": [
                {"op": "majority_bear"},
            ],
            "exit_short": [
                {"op": "majority_bull"},
            ],
            "atr_stop_mult": 2.0,
            "atr_target_mult": 3.0,
            "required_features": ["ema_20", "ema_50", "rsi_14", "macd_hist", "atr_14"],
        },
    ]
