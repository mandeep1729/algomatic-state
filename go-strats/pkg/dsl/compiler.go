package dsl

import (
	"fmt"

	"github.com/algomatic/strats100/go-strats/pkg/conditions"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// compileNode dispatches on the Op field to build a ConditionFn.
func compileNode(node ConditionNode) (types.ConditionFn, error) {
	switch node.Op {

	// --- Comparison operators (col + ref) ---

	case "crosses_above":
		ref, err := resolveRef(node)
		if err != nil {
			return nil, err
		}
		if node.Col == "" {
			return nil, fmt.Errorf("crosses_above: missing col")
		}
		return conditions.CrossesAbove(node.Col, ref), nil

	case "crosses_below":
		ref, err := resolveRef(node)
		if err != nil {
			return nil, err
		}
		if node.Col == "" {
			return nil, fmt.Errorf("crosses_below: missing col")
		}
		return conditions.CrossesBelow(node.Col, ref), nil

	case "above":
		ref, err := resolveRef(node)
		if err != nil {
			return nil, err
		}
		if node.Col == "" {
			return nil, fmt.Errorf("above: missing col")
		}
		return conditions.Above(node.Col, ref), nil

	case "below":
		ref, err := resolveRef(node)
		if err != nil {
			return nil, err
		}
		if node.Col == "" {
			return nil, fmt.Errorf("below: missing col")
		}
		return conditions.Below(node.Col, ref), nil

	// --- Directional operators ---

	case "rising":
		if node.Col == "" {
			return nil, fmt.Errorf("rising: missing col")
		}
		if node.N <= 0 {
			return nil, fmt.Errorf("rising: n must be > 0")
		}
		return conditions.Rising(node.Col, node.N), nil

	case "falling":
		if node.Col == "" {
			return nil, fmt.Errorf("falling: missing col")
		}
		if node.N <= 0 {
			return nil, fmt.Errorf("falling: n must be > 0")
		}
		return conditions.Falling(node.Col, node.N), nil

	// --- Composite operators ---

	case "all_of":
		if len(node.Conditions) == 0 {
			return nil, fmt.Errorf("all_of: conditions array is empty")
		}
		subs, err := compileChildren(node.Conditions)
		if err != nil {
			return nil, fmt.Errorf("all_of: %w", err)
		}
		return conditions.AllOf(subs...), nil

	case "any_of":
		if len(node.Conditions) == 0 {
			return nil, fmt.Errorf("any_of: conditions array is empty")
		}
		subs, err := compileChildren(node.Conditions)
		if err != nil {
			return nil, fmt.Errorf("any_of: %w", err)
		}
		return conditions.AnyOf(subs...), nil

	// --- Pullback operators ---

	case "pullback_to":
		if node.LevelCol == "" {
			return nil, fmt.Errorf("pullback_to: missing level_col")
		}
		return conditions.PullbackTo(node.LevelCol, node.ToleranceATRMult), nil

	// --- Divergence operators ---

	case "bullish_divergence":
		if node.IndicatorCol == "" {
			return nil, fmt.Errorf("bullish_divergence: missing indicator_col")
		}
		lookback := node.Lookback
		if lookback <= 0 {
			lookback = 14
		}
		return conditions.BullishDivergence(node.IndicatorCol, lookback), nil

	case "bearish_divergence":
		if node.IndicatorCol == "" {
			return nil, fmt.Errorf("bearish_divergence: missing indicator_col")
		}
		lookback := node.Lookback
		if lookback <= 0 {
			lookback = 14
		}
		return conditions.BearishDivergence(node.IndicatorCol, lookback), nil

	// --- Candle pattern operators ---

	case "candle_bullish":
		if node.PatternCol == "" {
			return nil, fmt.Errorf("candle_bullish: missing pattern_col")
		}
		return conditions.CandleBullish(node.PatternCol), nil

	case "candle_bearish":
		if node.PatternCol == "" {
			return nil, fmt.Errorf("candle_bearish: missing pattern_col")
		}
		return conditions.CandleBearish(node.PatternCol), nil

	// --- Breakout operators ---

	case "breaks_above_level":
		if node.LevelCol == "" {
			return nil, fmt.Errorf("breaks_above_level: missing level_col")
		}
		return conditions.BreaksAboveLevel(node.LevelCol), nil

	case "breaks_below_level":
		if node.LevelCol == "" {
			return nil, fmt.Errorf("breaks_below_level: missing level_col")
		}
		return conditions.BreaksBelowLevel(node.LevelCol), nil

	// --- Volatility / squeeze operators ---

	case "squeeze":
		if node.WidthCol == "" {
			return nil, fmt.Errorf("squeeze: missing width_col")
		}
		lookback := node.Lookback
		if lookback <= 0 {
			lookback = 60
		}
		return conditions.Squeeze(node.WidthCol, lookback), nil

	case "range_exceeds_atr":
		return conditions.RangeExceedsATR(node.Multiplier), nil

	case "bb_width_increasing":
		if node.N <= 0 {
			return nil, fmt.Errorf("bb_width_increasing: n must be > 0")
		}
		return conditions.BBWidthIncreasing(node.N), nil

	// --- Gap operators ---

	case "gap_up":
		return conditions.GapUp(node.ATRMult), nil

	case "gap_down":
		return conditions.GapDown(node.ATRMult), nil

	// --- Held operators ---

	case "held_above":
		if node.Col == "" {
			return nil, fmt.Errorf("held_above: missing col")
		}
		if node.N <= 0 {
			return nil, fmt.Errorf("held_above: n must be > 0")
		}
		threshold := node.Threshold
		return conditions.HeldForNBars(node.Col, func(v float64) bool { return v > threshold }, node.N), nil

	case "held_below":
		if node.Col == "" {
			return nil, fmt.Errorf("held_below: missing col")
		}
		if node.N <= 0 {
			return nil, fmt.Errorf("held_below: n must be > 0")
		}
		threshold := node.Threshold
		return conditions.HeldForNBars(node.Col, func(v float64) bool { return v < threshold }, node.N), nil

	// --- Was-then-crosses operators ---

	case "was_below_then_crosses_above":
		if node.Col == "" {
			return nil, fmt.Errorf("was_below_then_crosses_above: missing col")
		}
		lookback := node.Lookback
		if lookback <= 0 {
			lookback = 14
		}
		return conditions.WasBelowThenCrossesAbove(node.Col, node.Threshold, lookback), nil

	case "was_above_then_crosses_below":
		if node.Col == "" {
			return nil, fmt.Errorf("was_above_then_crosses_below: missing col")
		}
		lookback := node.Lookback
		if lookback <= 0 {
			lookback = 14
		}
		return conditions.WasAboveThenCrossesBelow(node.Col, node.Threshold, lookback), nil

	// --- ADX range ---

	case "adx_in_range":
		return conditions.ADXInRange(node.Low, node.High), nil

	// --- Deviation operators ---

	case "deviation_below":
		if node.Col == "" {
			return nil, fmt.Errorf("deviation_below: missing col")
		}
		if node.RefCol == "" {
			return nil, fmt.Errorf("deviation_below: missing ref_col")
		}
		return conditions.DeviationBelow(node.Col, node.RefCol, node.ATRMult), nil

	case "deviation_above":
		if node.Col == "" {
			return nil, fmt.Errorf("deviation_above: missing col")
		}
		if node.RefCol == "" {
			return nil, fmt.Errorf("deviation_above: missing ref_col")
		}
		return conditions.DeviationAbove(node.Col, node.RefCol, node.ATRMult), nil

	// --- Pullback below ---

	case "pullback_below":
		if node.LevelCol == "" {
			return nil, fmt.Errorf("pullback_below: missing level_col")
		}
		return conditions.PullbackBelow(node.LevelCol, node.ToleranceATRMult), nil

	// --- Consecutive close operators ---

	case "consecutive_higher_closes":
		if node.N <= 0 {
			return nil, fmt.Errorf("consecutive_higher_closes: n must be > 0")
		}
		return conditions.ConsecutiveHigherCloses(node.N), nil

	case "consecutive_lower_closes":
		if node.N <= 0 {
			return nil, fmt.Errorf("consecutive_lower_closes: n must be > 0")
		}
		return conditions.ConsecutiveLowerCloses(node.N), nil

	// --- Range operators ---

	case "narrowest_range":
		if node.Lookback <= 0 {
			return nil, fmt.Errorf("narrowest_range: lookback must be > 0")
		}
		return conditions.NarrowestRange(node.Lookback), nil

	case "in_top_pct_of_range":
		if node.Pct <= 0 {
			return nil, fmt.Errorf("in_top_pct_of_range: pct must be > 0")
		}
		return conditions.InTopPctOfRange(node.Pct), nil

	case "in_bottom_pct_of_range":
		if node.Pct <= 0 {
			return nil, fmt.Errorf("in_bottom_pct_of_range: pct must be > 0")
		}
		return conditions.InBottomPctOfRange(node.Pct), nil

	// --- Channel operators ---

	case "close_above_upper_channel":
		if node.Col == "" {
			return nil, fmt.Errorf("close_above_upper_channel: missing col")
		}
		return conditions.CloseAboveUpperChannel(node.Col, node.Multiplier), nil

	case "close_below_lower_channel":
		if node.Col == "" {
			return nil, fmt.Errorf("close_below_lower_channel: missing col")
		}
		return conditions.CloseBelowLowerChannel(node.Col, node.Multiplier), nil

	// --- EMA ribbon operators ---

	case "ribbon_break_long":
		if node.Lookback <= 0 {
			return nil, fmt.Errorf("ribbon_break_long: lookback must be > 0")
		}
		return conditions.RibbonBreakLong(node.Lookback, node.Multiplier), nil

	case "ribbon_break_short":
		if node.Lookback <= 0 {
			return nil, fmt.Errorf("ribbon_break_short: lookback must be > 0")
		}
		return conditions.RibbonBreakShort(node.Lookback, node.Multiplier), nil

	case "ribbon_exit_long":
		return conditions.RibbonExitLong(node.Multiplier), nil

	case "ribbon_exit_short":
		return conditions.RibbonExitShort(node.Multiplier), nil

	// --- TRIX operators ---

	case "trix_crosses_above_sma":
		return conditions.TRIXCrossesAboveSMA(), nil

	case "trix_crosses_below_sma":
		return conditions.TRIXCrossesBelowSMA(), nil

	// --- SMA envelope operators ---

	case "breaks_above_sma_envelope":
		if node.Col == "" {
			return nil, fmt.Errorf("breaks_above_sma_envelope: missing col")
		}
		return conditions.BreaksAboveSMAEnvelope(node.Col, node.Multiplier), nil

	case "breaks_below_sma_envelope":
		if node.Col == "" {
			return nil, fmt.Errorf("breaks_below_sma_envelope: missing col")
		}
		return conditions.BreaksBelowSMAEnvelope(node.Col, node.Multiplier), nil

	// --- Double tap operators ---

	case "double_tap_below_bb":
		if node.Lookback <= 0 {
			return nil, fmt.Errorf("double_tap_below_bb: lookback must be > 0")
		}
		return conditions.DoubleTapBelowBB(node.Lookback), nil

	case "double_tap_above_bb":
		if node.Lookback <= 0 {
			return nil, fmt.Errorf("double_tap_above_bb: lookback must be > 0")
		}
		return conditions.DoubleTapAboveBB(node.Lookback), nil

	// --- ATR / volatility operators ---

	case "atr_not_bottom_pct":
		if node.Pct <= 0 {
			return nil, fmt.Errorf("atr_not_bottom_pct: pct must be > 0")
		}
		if node.Lookback <= 0 {
			return nil, fmt.Errorf("atr_not_bottom_pct: lookback must be > 0")
		}
		return conditions.ATRNotBottomPct(node.Pct, node.Lookback), nil

	case "atr_below_contracted_sma":
		if node.Factor <= 0 {
			return nil, fmt.Errorf("atr_below_contracted_sma: factor must be > 0")
		}
		return conditions.ATRBelowContractedSMA(node.Factor), nil

	// --- Slope operators ---

	case "flat_slope":
		if node.Col == "" {
			return nil, fmt.Errorf("flat_slope: missing col")
		}
		return conditions.FlatSlope(node.Col, node.Epsilon), nil

	// --- Mean reversion operators ---

	case "mean_rev_long":
		if node.RefCol == "" {
			return nil, fmt.Errorf("mean_rev_long: missing ref_col")
		}
		return conditions.MeanRevLong(node.RefCol, node.Multiplier), nil

	case "mean_rev_short":
		if node.RefCol == "" {
			return nil, fmt.Errorf("mean_rev_short: missing ref_col")
		}
		return conditions.MeanRevShort(node.RefCol, node.Multiplier), nil

	// --- Ensemble / majority operators ---

	case "majority_bull":
		return conditions.MajorityBull(), nil

	case "majority_bear":
		return conditions.MajorityBear(), nil

	default:
		return nil, fmt.Errorf("unknown operator: %q", node.Op)
	}
}

// resolveRef converts the DSL Ref to a conditions.Ref.
func resolveRef(node ConditionNode) (conditions.Ref, error) {
	if node.Ref == nil {
		return conditions.Ref{}, fmt.Errorf("%s: missing ref", node.Op)
	}
	if node.Ref.Col != "" {
		return conditions.ColRef(node.Ref.Col), nil
	}
	if node.Ref.Value != nil {
		return conditions.NumRef(*node.Ref.Value), nil
	}
	return conditions.Ref{}, fmt.Errorf("%s: ref must have col or value", node.Op)
}

// compileChildren compiles a slice of child condition nodes.
func compileChildren(nodes []ConditionNode) ([]types.ConditionFn, error) {
	fns := make([]types.ConditionFn, 0, len(nodes))
	for i, child := range nodes {
		fn, err := compileNode(child)
		if err != nil {
			return nil, fmt.Errorf("condition[%d]: %w", i, err)
		}
		fns = append(fns, fn)
	}
	return fns, nil
}
