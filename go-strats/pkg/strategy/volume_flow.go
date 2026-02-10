package strategy

// Volume flow strategies (IDs 71-80).

import (
	c "github.com/algomatic/strats100/go-strats/pkg/conditions"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

func volumeFlowStrategies() []*types.StrategyDef {
	return []*types.StrategyDef{
		// 71: OBV Breakout Confirmation
		{
			ID: 71, Name: "obv_breakout_confirmation",
			DisplayName: "OBV Breakout Confirmation",
			Philosophy:  "Price breakouts confirmed by volume flow (OBV) breakouts have higher conviction.",
			Category: "volume_flow", Direction: types.LongShort,
			Tags:       []string{"volume_flow", "breakout", "long_short", "breakout", "atr_stop", "OBV", "MAX", "MIN", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.BreaksAboveLevel("donchian_high_20"), c.BreaksAboveLevel("obv_high_20")},
			EntryShort: []types.ConditionFn{c.BreaksBelowLevel("donchian_low_20"), c.BreaksBelowLevel("obv_low_20")},
			ExitLong:   []types.ConditionFn{c.BreaksBelowLevel("donchian_low_20")},
			ExitShort:  []types.ConditionFn{c.BreaksAboveLevel("donchian_high_20")},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"donchian_high_20", "donchian_low_20", "obv", "obv_high_20", "obv_low_20", "atr_14"},
		},
		// 72: OBV Trend + Pullback
		{
			ID: 72, Name: "obv_trend_pullback",
			DisplayName: "OBV Trend + Pullback",
			Philosophy:  "OBV above its SMA confirms accumulation; pullback to EMA20 is a high-quality entry.",
			Category: "volume_flow", Direction: types.LongOnly,
			Tags:       []string{"volume_flow", "trend", "long_only", "pullback", "trailing", "OBV", "EMA", "ATR", "trend_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.Above("obv", c.ColRef("obv_sma_20")), c.Above("close", c.ColRef("ema_50")), c.PullbackTo("ema_20", 0.5)},
			ExitLong:   []types.ConditionFn{c.Below("close", c.ColRef("ema_20"))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"obv", "obv_sma_20", "ema_20", "ema_50", "atr_14"},
		},
		// 73: ADOSC Momentum
		{
			ID: 73, Name: "adosc_momentum",
			DisplayName: "ADOSC Momentum",
			Philosophy:  "Accumulation/Distribution oscillator zero-line cross confirms volume-backed momentum.",
			Category: "volume_flow", Direction: types.LongShort,
			Tags:       []string{"volume_flow", "long_short", "threshold", "time", "ADOSC", "ATR", "trend_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.CrossesAbove("adosc", c.NumRef(0)), c.Above("close", c.ColRef("ema_50"))},
			EntryShort: []types.ConditionFn{c.CrossesBelow("adosc", c.NumRef(0)), c.Below("close", c.ColRef("ema_50"))},
			ExitLong:   []types.ConditionFn{c.CrossesBelow("adosc", c.NumRef(0))},
			ExitShort:  []types.ConditionFn{c.CrossesAbove("adosc", c.NumRef(0))},
			ATRStopMult: 2.0,
			RequiredIndicators: []string{"adosc", "ema_50", "atr_14"},
		},
		// 74: MFI + BB Breakout
		{
			ID: 74, Name: "mfi_bb_breakout",
			DisplayName: "MFI + BB Breakout",
			Philosophy:  "Bollinger breakout confirmed by strong MFI validates volume participation.",
			Category: "volume_flow", Direction: types.LongShort,
			Tags:       []string{"volume_flow", "breakout", "long_short", "breakout", "atr_stop", "atr_target", "MFI", "BBANDS", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.Above("close", c.ColRef("bb_upper")), c.Above("mfi_14", c.NumRef(60))},
			EntryShort: []types.ConditionFn{c.Below("close", c.ColRef("bb_lower")), c.Below("mfi_14", c.NumRef(40))},
			ExitLong:   []types.ConditionFn{c.Below("close", c.ColRef("bb_middle"))},
			ExitShort:  []types.ConditionFn{c.Above("close", c.ColRef("bb_middle"))},
			ATRStopMult: 2.0, ATRTargetMult: 3.0,
			RequiredIndicators: []string{"close", "bb_upper", "bb_lower", "bb_middle", "mfi_14", "atr_14"},
		},
		// 75: Volume Spike Trend Continuation
		{
			ID: 75, Name: "volume_spike_trend",
			DisplayName: "Volume Spike Trend Continuation",
			Philosophy:  "Volume spike with trend alignment signals institutional participation.",
			Category: "volume_flow", Direction: types.LongOnly,
			Tags:       []string{"volume_flow", "trend", "long_only", "threshold", "time", "SMA", "ATR", "trend_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.Above("close", c.ColRef("sma_50")), c.Above("volume", c.ColRef("volume_sma_20_2x")), c.InTopPctOfRange(0.25)},
			ExitLong:   nil,
			TrailingATRMult: 2.0, ATRStopMult: 2.0, TimeStopBars: 20,
			RequiredIndicators: []string{"close", "sma_50", "volume", "volume_sma_20_2x", "atr_14"},
		},
		// 76: OBV Divergence Reversal
		{
			ID: 76, Name: "obv_divergence_reversal",
			DisplayName: "OBV Divergence Reversal",
			Philosophy:  "OBV-price divergence reveals hidden accumulation/distribution before reversals.",
			Category: "volume_flow", Direction: types.LongShort,
			Tags:       []string{"volume_flow", "mean_reversion", "long_short", "divergence", "time", "OBV", "ATR", "range_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.BullishDivergence("obv", 10)},
			EntryShort: []types.ConditionFn{c.BearishDivergence("obv", 10)},
			ATRStopMult: 2.5, ATRTargetMult: 3.0, TimeStopBars: 25,
			RequiredIndicators: []string{"close", "high", "low", "obv", "atr_14"},
		},
		// 77: Chaikin A/D Line Trend
		{
			ID: 77, Name: "chaikin_ad_trend",
			DisplayName: "Chaikin A/D Line Trend",
			Philosophy:  "Persistent ADOSC direction confirms institutional flow aligned with price trend.",
			Category: "volume_flow", Direction: types.LongShort,
			Tags:       []string{"volume_flow", "trend", "long_short", "threshold", "trailing", "ADOSC", "EMA", "ATR", "trend_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.HeldForNBars("adosc", func(v float64) bool { return v > 0 }, 5), c.Above("close", c.ColRef("ema_50"))},
			EntryShort: []types.ConditionFn{c.HeldForNBars("adosc", func(v float64) bool { return v < 0 }, 5), c.Below("close", c.ColRef("ema_50"))},
			ExitLong:   []types.ConditionFn{c.CrossesBelow("adosc", c.NumRef(0))},
			ExitShort:  []types.ConditionFn{c.CrossesAbove("adosc", c.NumRef(0))},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"adosc", "ema_50", "atr_14"},
		},
		// 78: MFI Reversion with ADX Low
		{
			ID: 78, Name: "mfi_reversion_adx_low",
			DisplayName: "MFI Reversion with ADX Low",
			Philosophy:  "MFI extremes in low-ADX environments signal high-probability reversion.",
			Category: "volume_flow", Direction: types.LongShort,
			Tags:       []string{"volume_flow", "mean_reversion", "regime", "long_short", "threshold", "time", "MFI", "ADX", "ATR", "range_favor", "swing"},
			EntryLong:  []types.ConditionFn{c.Below("adx_14", c.NumRef(15)), c.CrossesAbove("mfi_14", c.NumRef(20))},
			EntryShort: []types.ConditionFn{c.Below("adx_14", c.NumRef(15)), c.CrossesBelow("mfi_14", c.NumRef(80))},
			ExitLong:   []types.ConditionFn{c.Above("mfi_14", c.NumRef(50))},
			ExitShort:  []types.ConditionFn{c.Below("mfi_14", c.NumRef(50))},
			ATRStopMult: 2.0, TimeStopBars: 20,
			RequiredIndicators: []string{"adx_14", "mfi_14", "atr_14"},
		},
		// 79: OBV Break then Retest
		{
			ID: 79, Name: "obv_break_retest",
			DisplayName: "OBV Break then Retest",
			Philosophy:  "OBV breakout followed by price pullback and recovery is high-conviction continuation.",
			Category: "volume_flow", Direction: types.LongOnly,
			Tags:       []string{"volume_flow", "breakout", "long_only", "pullback", "atr_stop", "OBV", "MAX", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.Above("obv", c.ColRef("obv_high_20")), c.PullbackTo("ema_20", 1.0)},
			TrailingATRMult: 2.0, ATRStopMult: 2.0, TimeStopBars: 40,
			RequiredIndicators: []string{"obv", "obv_high_20", "ema_20", "atr_14"},
		},
		// 80: Price Breakout + Positive Accumulation
		{
			ID: 80, Name: "price_breakout_accumulation",
			DisplayName: "Price Breakout + Positive Accumulation",
			Philosophy:  "Price breakout backed by rising ADOSC confirms institutional accumulation.",
			Category: "volume_flow", Direction: types.LongOnly,
			Tags:       []string{"volume_flow", "breakout", "long_only", "breakout", "atr_stop", "ADOSC", "MAX", "ATR", "vol_expand", "swing"},
			EntryLong:  []types.ConditionFn{c.BreaksAboveLevel("donchian_high_20"), c.Rising("adosc", 3)},
			TrailingATRMult: 2.0, ATRStopMult: 2.0,
			RequiredIndicators: []string{"donchian_high_20", "adosc", "atr_14"},
		},
	}
}
