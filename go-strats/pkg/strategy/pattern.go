package strategy

// Candlestick / Pattern strategies (IDs 81-90).

import (
	c "github.com/algomatic/strats100/go-strats/pkg/conditions"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func patternStrategies() []*types.StrategyDef {
	return []*types.StrategyDef{
		// 81: Bullish Engulfing + Trend Filter
		{
			ID: 81, Name: "bullish_engulfing_trend",
			DisplayName: "Bullish Engulfing + Trend Filter",
			Philosophy:  "A bullish engulfing pattern in an uptrend signals strong demand overwhelming recent supply.",
			Category: "pattern", Direction: types.LongOnly,
			Tags:      []string{"pattern", "trend", "long_only", "pattern", "atr_stop", "atr_target", "CDLENGULFING", "EMA", "ATR", "trend_favor", "swing"},
			EntryLong: []types.ConditionFn{c.CandleBullish("cdl_engulfing"), c.Above("close", c.ColRef("ema_50"))},
			ExitLong:  []types.ConditionFn{c.Below("close", c.ColRef("ema_20"))},
			ATRStopMult: 2.0, ATRTargetMult: 3.0,
			RequiredIndicators: []string{"cdl_engulfing", "ema_20", "ema_50", "atr_14"},
		},
		// 82: Bearish Engulfing + Trend Filter
		{
			ID: 82, Name: "bearish_engulfing_trend",
			DisplayName: "Bearish Engulfing + Trend Filter",
			Philosophy:  "A bearish engulfing pattern in a downtrend signals strong supply overwhelming recent demand.",
			Category: "pattern", Direction: types.ShortOnly,
			Tags:       []string{"pattern", "trend", "short_only", "pattern", "atr_stop", "atr_target", "CDLENGULFING", "EMA", "ATR", "trend_favor", "swing"},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_engulfing"), c.Below("close", c.ColRef("ema_50"))},
			ExitShort:  []types.ConditionFn{c.Above("close", c.ColRef("ema_20"))},
			ATRStopMult: 2.0, ATRTargetMult: 3.0,
			RequiredIndicators: []string{"cdl_engulfing", "ema_20", "ema_50", "atr_14"},
		},
		// 83: Hammer at Lower BB
		{
			ID: 83, Name: "hammer_lower_bb",
			DisplayName: "Hammer at Lower BB",
			Philosophy:  "Hammer candle at lower Bollinger Band signals rejection of lower prices.",
			Category: "pattern", Direction: types.LongOnly,
			Tags:      []string{"pattern", "mean_reversion", "long_only", "pattern", "time", "CDLHAMMER", "BBANDS", "ATR", "range_favor", "swing"},
			EntryLong: []types.ConditionFn{c.CandleBullish("cdl_hammer"), c.Below("low", c.ColRef("bb_lower"))},
			ExitLong:  []types.ConditionFn{c.Above("close", c.ColRef("bb_middle"))},
			ATRStopMult: 2.0, TimeStopBars: 20,
			RequiredIndicators: []string{"cdl_hammer", "low", "bb_lower", "bb_middle", "atr_14"},
		},
		// 84: Shooting Star at Upper BB
		{
			ID: 84, Name: "shooting_star_upper_bb",
			DisplayName: "Shooting Star at Upper BB",
			Philosophy:  "Shooting star candle at upper Bollinger Band signals rejection of higher prices.",
			Category: "pattern", Direction: types.ShortOnly,
			Tags:       []string{"pattern", "mean_reversion", "short_only", "pattern", "time", "CDLSHOOTINGSTAR", "BBANDS", "ATR", "range_favor", "swing"},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_shooting_star"), c.Above("high", c.ColRef("bb_upper"))},
			ExitShort:  []types.ConditionFn{c.Below("close", c.ColRef("bb_middle"))},
			ATRStopMult: 2.0, TimeStopBars: 20,
			RequiredIndicators: []string{"cdl_shooting_star", "high", "bb_upper", "bb_middle", "atr_14"},
		},
		// 85: Morning Star (reversal)
		{
			ID: 85, Name: "morning_star_reversal",
			DisplayName: "Morning Star Reversal",
			Philosophy:  "Three-candle morning star pattern signals bullish reversal at support.",
			Category: "pattern", Direction: types.LongOnly,
			Tags:      []string{"pattern", "mean_reversion", "long_only", "pattern", "atr_stop", "CDLMORNINGSTAR", "ATR", "range_favor", "swing"},
			EntryLong: []types.ConditionFn{c.CandleBullish("cdl_morning_star")},
			ATRStopMult: 2.5, ATRTargetMult: 3.0, TimeStopBars: 30,
			RequiredIndicators: []string{"cdl_morning_star", "atr_14"},
		},
		// 86: Evening Star (reversal)
		{
			ID: 86, Name: "evening_star_reversal",
			DisplayName: "Evening Star Reversal",
			Philosophy:  "Three-candle evening star pattern signals bearish reversal at resistance.",
			Category: "pattern", Direction: types.ShortOnly,
			Tags:       []string{"pattern", "mean_reversion", "short_only", "pattern", "atr_stop", "CDLEVENINGSTAR", "ATR", "range_favor", "swing"},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_evening_star")},
			ATRStopMult: 2.5, ATRTargetMult: 3.0, TimeStopBars: 30,
			RequiredIndicators: []string{"cdl_evening_star", "atr_14"},
		},
		// 87: Doji + Trend Exhaustion
		{
			ID: 87, Name: "doji_trend_exhaustion",
			DisplayName: "Doji + Trend Exhaustion",
			Philosophy:  "Doji with wide range and RSI non-extreme signals indecision after strong move.",
			Category: "pattern", Direction: types.LongShort,
			Tags:       []string{"pattern", "mean_reversion", "volatility", "long_short", "pattern", "time", "CDLDOJI", "ATR", "RSI", "range_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.CandleBullish("cdl_doji"), c.RangeExceedsATR(1.8), c.Below("rsi_14", c.NumRef(45)), c.ConsecutiveHigherCloses(1)},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_doji"), c.RangeExceedsATR(1.8), c.Above("rsi_14", c.NumRef(55)), c.ConsecutiveLowerCloses(1)},
			ATRStopMult: 2.0, ATRTargetMult: 2.5, TimeStopBars: 20,
			RequiredIndicators: []string{"cdl_doji", "rsi_14", "atr_14"},
		},
		// 88: Three White Soldiers / Three Black Crows
		{
			ID: 88, Name: "three_soldiers_crows",
			DisplayName: "Three White Soldiers / Three Black Crows",
			Philosophy:  "Three consecutive strong directional candles signal sustained momentum.",
			Category: "pattern", Direction: types.LongShort,
			Tags:       []string{"pattern", "trend", "long_short", "pattern", "trailing", "CDL3WHITESOLDIERS", "CDL3BLACKCROWS", "ATR", "trend_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.CandleBullish("cdl_3white_soldiers")},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_3black_crows")},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"cdl_3white_soldiers", "cdl_3black_crows", "atr_14"},
		},
		// 89: Harami + RSI Confirm
		{
			ID: 89, Name: "harami_rsi_confirm",
			DisplayName: "Harami + RSI Confirm",
			Philosophy:  "Harami pattern with RSI confirmation signals high-quality reversal setup.",
			Category: "pattern", Direction: types.LongShort,
			Tags:       []string{"pattern", "mean_reversion", "long_short", "pattern", "time", "CDLHARAMI", "RSI", "ATR", "range_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.CandleBullish("cdl_harami"), c.Below("rsi_14", c.NumRef(45)), c.Rising("rsi_14", 2)},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_harami"), c.Above("rsi_14", c.NumRef(55)), c.Falling("rsi_14", 2)},
			ExitLong:   []types.ConditionFn{c.Above("rsi_14", c.NumRef(50))},
			ExitShort:  []types.ConditionFn{c.Below("rsi_14", c.NumRef(50))},
			ATRStopMult: 2.0, TimeStopBars: 25,
			RequiredIndicators: []string{"cdl_harami", "rsi_14", "atr_14"},
		},
		// 90: Marubozu Breakout Continuation
		{
			ID: 90, Name: "marubozu_breakout",
			DisplayName: "Marubozu Breakout Continuation",
			Philosophy:  "Marubozu (strong body, no wicks) with price breakout signals conviction momentum.",
			Category: "pattern", Direction: types.LongShort,
			Tags:       []string{"pattern", "breakout", "long_short", "pattern", "breakout", "time", "CDLMARUBOZU", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.CandleBullish("cdl_marubozu"), c.BreaksAboveLevel("donchian_high_10")},
			EntryShort: []types.ConditionFn{c.CandleBearish("cdl_marubozu"), c.BreaksBelowLevel("donchian_low_10")},
			TrailingATRMult: 2.0, ATRStopMult: 2.0, TimeStopBars: 20,
			RequiredIndicators: []string{"cdl_marubozu", "donchian_high_10", "donchian_low_10", "atr_14"},
		},
	}
}
