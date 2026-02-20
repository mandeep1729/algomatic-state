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
