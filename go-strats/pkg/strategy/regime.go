package strategy

// Regime-Switch / Multi-Filter Hybrid strategies (IDs 91-100).

import (
	c "github.com/algomatic/strats100/go-strats/pkg/conditions"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func regimeStrategies() []*types.StrategyDef {
	// Strategy 91 sub-conditions
	trendLong := c.AllOf(c.Above("adx_14", c.NumRef(25)), c.CrossesAbove("ema_20", c.ColRef("ema_50")))
	trendShort := c.AllOf(c.Above("adx_14", c.NumRef(25)), c.CrossesBelow("ema_20", c.ColRef("ema_50")))
	rangeLong := c.AllOf(c.Below("adx_14", c.NumRef(18)), c.CrossesAbove("close", c.ColRef("bb_lower")))
	rangeShort := c.AllOf(c.Below("adx_14", c.NumRef(18)), c.CrossesBelow("close", c.ColRef("bb_upper")))

	// Strategy 92 sub-conditions
	expandLong := c.AllOf(c.Above("atr_14", c.ColRef("atr_sma_50")), c.BreaksAboveLevel("donchian_high_20"))
	expandShort := c.AllOf(c.Above("atr_14", c.ColRef("atr_sma_50")), c.BreaksBelowLevel("donchian_low_20"))
	contractLong := c.AllOf(c.ATRBelowContractedSMA(0.85), c.MeanRevLong("typical_price_sma_20", 1.5))
	contractShort := c.AllOf(c.ATRBelowContractedSMA(0.85), c.MeanRevShort("typical_price_sma_20", 1.5))

	return []*types.StrategyDef{
		// 91: ADX Trend vs Range Switch
		{
			ID: 91, Name: "adx_trend_range_switch",
			DisplayName: "ADX Trend vs Range Switch",
			Philosophy:  "Adapting strategy to the current regime (trending vs ranging) avoids whipsaws.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"regime", "multi_filter", "long_short", "threshold", "mixed", "ADX", "EMA", "RSI", "BBANDS", "ATR", "swing"},
			EntryLong:  []types.ConditionFn{c.AnyOf(trendLong, rangeLong)},
			EntryShort: []types.ConditionFn{c.AnyOf(trendShort, rangeShort)},
			ExitLong:   []types.ConditionFn{c.AnyOf(c.CrossesBelow("ema_20", c.ColRef("ema_50")), c.Above("close", c.ColRef("bb_middle")))},
			ExitShort:  []types.ConditionFn{c.AnyOf(c.CrossesAbove("ema_20", c.ColRef("ema_50")), c.Below("close", c.ColRef("bb_middle")))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"adx_14", "ema_20", "ema_50", "bb_upper", "bb_lower", "bb_middle", "atr_14"},
		},
		// 92: Volatility Regime Switch
		{
			ID: 92, Name: "volatility_regime_switch",
			DisplayName: "Volatility Regime Switch",
			Philosophy:  "Switching between breakout and mean reversion based on volatility regime aligns strategy with market conditions.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"regime", "volatility", "long_short", "threshold", "mixed", "ATR", "BBANDS", "MAX", "MIN", "swing"},
			EntryLong:  []types.ConditionFn{c.AnyOf(expandLong, contractLong)},
			EntryShort: []types.ConditionFn{c.AnyOf(expandShort, contractShort)},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"atr_14", "atr_sma_50", "donchian_high_20", "donchian_low_20", "typical_price_sma_20"},
		},
		// 93: Trend Quality Filter
		{
			ID: 93, Name: "trend_quality_filter",
			DisplayName: "Trend Quality Filter",
			Philosophy:  "Combining trend strength (ADX), expanding volatility (BB width), and pullback timing produces higher quality trend entries.",
			Category: "regime", Direction: types.LongOnly,
			Tags:      []string{"regime", "trend", "long_only", "pullback", "trailing", "ADX", "BBANDS", "EMA", "ATR", "trend_favor", "swing"},
			EntryLong: []types.ConditionFn{c.Above("adx_14", c.NumRef(20)), c.Rising("bb_width", 3), c.PullbackTo("ema_20", 0.5)},
			ExitLong:  []types.ConditionFn{c.Below("close", c.ColRef("ema_20"))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"adx_14", "bb_width", "ema_20", "atr_14"},
		},
		// 94: No-Trade Filter Strategy
		{
			ID: 94, Name: "no_trade_filter",
			DisplayName: "No-Trade Filter Strategy",
			Philosophy:  "Filtering out unfavorable conditions before entering improves overall strategy quality.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"regime", "long_short", "threshold", "time", "ATR", "ADX", "risk:tight", "scalp"},
			EntryLong:  []types.ConditionFn{c.ADXInRange(18, 35), c.ATRNotBottomPct(20, 200), c.CrossesAbove("roc_10", c.NumRef(0)), c.Above("close", c.ColRef("sma_200"))},
			EntryShort: []types.ConditionFn{c.ADXInRange(18, 35), c.ATRNotBottomPct(20, 200), c.CrossesBelow("roc_10", c.NumRef(0)), c.Below("close", c.ColRef("sma_200"))},
			ATRStopMult: 2.0, TimeStopBars: 15,
			RequiredIndicators: []string{"adx_14", "atr_14", "roc_10", "sma_200"},
		},
		// 95: Dual-Timeframe Filter
		{
			ID: 95, Name: "dual_timeframe_filter",
			DisplayName: "Dual-Timeframe Filter",
			Philosophy:  "Using a slow MA as a higher-timeframe proxy ensures entries align with the broader trend.",
			Category: "regime", Direction: types.LongOnly,
			Tags:      []string{"multi_filter", "trend", "long_only", "pullback", "trailing", "EMA", "RSI", "ATR", "trend_favor", "swing"},
			EntryLong: []types.ConditionFn{c.Above("close", c.ColRef("sma_200")), c.WasBelowThenCrossesAbove("rsi_14", 50, 10), c.Above("close", c.ColRef("ema_20"))},
			ExitLong:  []types.ConditionFn{c.Below("close", c.ColRef("ema_20"))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"sma_200", "rsi_14", "ema_20", "atr_14"},
		},
		// 96: Mean Reversion Only When Trend Flat
		{
			ID: 96, Name: "trend_flat_mean_reversion",
			DisplayName: "Trend Flat Mean Reversion",
			Philosophy:  "Mean reversion strategies work best when there is no underlying trend; filtering by slope near zero avoids fighting momentum.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"multi_filter", "mean_reversion", "regime", "long_short", "threshold", "time", "SMA", "LINEARREG_SLOPE", "RSI", "ATR", "range_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.FlatSlope("linearreg_slope_20", 0.001), c.CrossesAbove("rsi_14", c.NumRef(30))},
			EntryShort: []types.ConditionFn{c.FlatSlope("linearreg_slope_20", 0.001), c.CrossesBelow("rsi_14", c.NumRef(70))},
			ExitLong:   []types.ConditionFn{c.Above("rsi_14", c.NumRef(50))},
			ExitShort:  []types.ConditionFn{c.Below("rsi_14", c.NumRef(50))},
			ATRStopMult: 2.0, TimeStopBars: 25,
			RequiredIndicators: []string{"linearreg_slope_20", "rsi_14", "atr_14"},
		},
		// 97: Breakout Only When Volume/Flow Confirms
		{
			ID: 97, Name: "volume_confirmed_breakout",
			DisplayName: "Breakout Only When Volume/Flow Confirms",
			Philosophy:  "Requiring multiple volume/flow confirmations filters out false breakouts.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"multi_filter", "breakout", "volume_flow", "long_short", "breakout", "atr_stop", "MAX", "MIN", "OBV", "ADOSC", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.BreaksAboveLevel("donchian_high_20"), c.BreaksAboveLevel("obv_high_20"), c.Above("adosc", c.NumRef(0))},
			EntryShort: []types.ConditionFn{c.BreaksBelowLevel("donchian_low_20"), c.BreaksBelowLevel("obv_low_20"), c.Below("adosc", c.NumRef(0))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"donchian_high_20", "donchian_low_20", "obv", "obv_high_20", "obv_low_20", "adosc", "atr_14"},
		},
		// 98: Trend + Mean Reversion Add-on (simplified)
		{
			ID: 98, Name: "trend_mr_addon",
			DisplayName: "Trend + Mean Reversion Add-on",
			Philosophy:  "Entering on a trend signal combined with mean reversion timing improves entry quality.",
			Category: "regime", Direction: types.LongOnly,
			Tags:      []string{"trend", "mean_reversion", "multi_filter", "long_only", "pullback", "trailing", "EMA", "RSI", "ATR", "trend_favor", "position"},
			EntryLong: []types.ConditionFn{c.CrossesAbove("ema_20", c.ColRef("ema_50")), c.Above("close", c.ColRef("ema_50"))},
			ExitLong:  []types.ConditionFn{c.Below("close", c.ColRef("ema_50"))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"ema_20", "ema_50", "atr_14"},
		},
		// 99: Volatility Breakout with Failure Exit
		{
			ID: 99, Name: "vol_breakout_failure_exit",
			DisplayName: "Volatility Breakout with Failure Exit",
			Philosophy:  "Adding a failure exit to the classic squeeze breakout cuts losses quickly when the breakout does not follow through.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"breakout", "volatility", "long_short", "breakout", "signal", "atr_stop", "BBANDS", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.Squeeze("bb_width", 60), c.Above("close", c.ColRef("bb_upper"))},
			EntryShort: []types.ConditionFn{c.Squeeze("bb_width", 60), c.Below("close", c.ColRef("bb_lower"))},
			ExitLong:   []types.ConditionFn{c.Below("close", c.ColRef("bb_upper"))},
			ExitShort:  []types.ConditionFn{c.Above("close", c.ColRef("bb_lower"))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"bb_upper", "bb_lower", "bb_width", "atr_14"},
		},
		// 100: Ensemble Vote (3-Strategy Majority)
		{
			ID: 100, Name: "ensemble_vote",
			DisplayName: "Ensemble Vote (3-Strategy Majority)",
			Philosophy:  "Combining multiple independent signals via majority vote reduces false signals and increases conviction.",
			Category: "regime", Direction: types.LongShort,
			Tags:       []string{"regime", "ensemble", "multi_filter", "long_short", "mixed", "EMA", "RSI", "MACD", "ATR", "swing"},
			EntryLong:  []types.ConditionFn{c.MajorityBull()},
			EntryShort: []types.ConditionFn{c.MajorityBear()},
			ExitLong:   []types.ConditionFn{c.MajorityBear()},
			ExitShort:  []types.ConditionFn{c.MajorityBull()},
			ATRStopMult: 2.0, ATRTargetMult: 3.0,
			RequiredIndicators: []string{"ema_20", "ema_50", "rsi_14", "macd_hist", "atr_14"},
		},
	}
}
