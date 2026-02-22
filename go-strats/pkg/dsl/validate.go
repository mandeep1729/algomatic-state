package dsl

import (
	"encoding/json"
	"fmt"
)

// knownOps is the set of operators the compiler recognises.
var knownOps = map[string]bool{
	"crosses_above": true, "crosses_below": true,
	"above": true, "below": true,
	"rising": true, "falling": true,
	"all_of": true, "any_of": true,
	"pullback_to": true, "pullback_below": true,
	"bullish_divergence": true, "bearish_divergence": true,
	"candle_bullish": true, "candle_bearish": true,
	"breaks_above_level": true, "breaks_below_level": true,
	"squeeze": true, "range_exceeds_atr": true, "bb_width_increasing": true,
	"gap_up": true, "gap_down": true,
	"held_above": true, "held_below": true,
	"was_below_then_crosses_above": true, "was_above_then_crosses_below": true,
	"adx_in_range": true,
	"deviation_below": true, "deviation_above": true,
	"consecutive_higher_closes": true, "consecutive_lower_closes": true,
	"narrowest_range": true,
	"in_top_pct_of_range": true, "in_bottom_pct_of_range": true,
	"close_above_upper_channel": true, "close_below_lower_channel": true,
	"ribbon_break_long": true, "ribbon_break_short": true,
	"ribbon_exit_long": true, "ribbon_exit_short": true,
	"trix_crosses_above_sma": true, "trix_crosses_below_sma": true,
	"breaks_above_sma_envelope": true, "breaks_below_sma_envelope": true,
	"double_tap_below_bb": true, "double_tap_above_bb": true,
	"atr_not_bottom_pct": true, "atr_below_contracted_sma": true,
	"flat_slope": true,
	"mean_rev_long": true, "mean_rev_short": true,
	"majority_bull": true, "majority_bear": true,
}

// ValidateJSON parses raw JSON into condition nodes and validates them
// without compiling. Returns human-readable errors for unknown operators
// or structurally invalid nodes.
func ValidateJSON(raw json.RawMessage) []string {
	if len(raw) == 0 || string(raw) == "null" {
		return nil
	}

	var nodes []ConditionNode
	if err := json.Unmarshal(raw, &nodes); err != nil {
		return []string{fmt.Sprintf("invalid JSON: %v", err)}
	}

	return ValidateConditions(nodes)
}

// ValidateConditions checks a slice of condition nodes for structural issues.
func ValidateConditions(nodes []ConditionNode) []string {
	var errs []string
	for i, node := range nodes {
		errs = append(errs, validateNode(node, fmt.Sprintf("[%d]", i))...)
	}
	return errs
}

func validateNode(node ConditionNode, path string) []string {
	var errs []string

	if node.Op == "" {
		errs = append(errs, fmt.Sprintf("%s: missing op", path))
		return errs
	}

	if !knownOps[node.Op] {
		errs = append(errs, fmt.Sprintf("%s: unknown operator %q", path, node.Op))
		return errs
	}

	// Validate composite children recursively
	if node.Op == "all_of" || node.Op == "any_of" {
		if len(node.Conditions) == 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires non-empty conditions array", path, node.Op))
		}
		for i, child := range node.Conditions {
			childPath := fmt.Sprintf("%s.conditions[%d]", path, i)
			errs = append(errs, validateNode(child, childPath)...)
		}
	}

	// Validate required fields per operator
	switch node.Op {
	case "crosses_above", "crosses_below", "above", "below":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
		if node.Ref == nil {
			errs = append(errs, fmt.Sprintf("%s: %s requires ref", path, node.Op))
		} else if node.Ref.Col == "" && node.Ref.Value == nil {
			errs = append(errs, fmt.Sprintf("%s: %s ref must have col or value", path, node.Op))
		}
	case "rising", "falling":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
		if node.N <= 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires n > 0", path, node.Op))
		}
	case "pullback_to":
		if node.LevelCol == "" {
			errs = append(errs, fmt.Sprintf("%s: pullback_to requires level_col", path))
		}
	case "bullish_divergence", "bearish_divergence":
		if node.IndicatorCol == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires indicator_col", path, node.Op))
		}
	case "candle_bullish", "candle_bearish":
		if node.PatternCol == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires pattern_col", path, node.Op))
		}
	case "breaks_above_level", "breaks_below_level":
		if node.LevelCol == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires level_col", path, node.Op))
		}
	case "squeeze":
		if node.WidthCol == "" {
			errs = append(errs, fmt.Sprintf("%s: squeeze requires width_col", path))
		}
	case "bb_width_increasing":
		if node.N <= 0 {
			errs = append(errs, fmt.Sprintf("%s: bb_width_increasing requires n > 0", path))
		}
	case "held_above", "held_below":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
		if node.N <= 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires n > 0", path, node.Op))
		}
	case "was_below_then_crosses_above", "was_above_then_crosses_below":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
	case "deviation_below", "deviation_above":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
		if node.RefCol == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires ref_col", path, node.Op))
		}
	case "pullback_below":
		if node.LevelCol == "" {
			errs = append(errs, fmt.Sprintf("%s: pullback_below requires level_col", path))
		}
	case "consecutive_higher_closes", "consecutive_lower_closes":
		if node.N <= 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires n > 0", path, node.Op))
		}
	case "narrowest_range":
		if node.Lookback <= 0 {
			errs = append(errs, fmt.Sprintf("%s: narrowest_range requires lookback > 0", path))
		}
	case "in_top_pct_of_range", "in_bottom_pct_of_range":
		if node.Pct <= 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires pct > 0", path, node.Op))
		}
	case "close_above_upper_channel", "close_below_lower_channel":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
	case "ribbon_break_long", "ribbon_break_short":
		if node.Lookback <= 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires lookback > 0", path, node.Op))
		}
	case "breaks_above_sma_envelope", "breaks_below_sma_envelope":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires col", path, node.Op))
		}
	case "double_tap_below_bb", "double_tap_above_bb":
		if node.Lookback <= 0 {
			errs = append(errs, fmt.Sprintf("%s: %s requires lookback > 0", path, node.Op))
		}
	case "atr_not_bottom_pct":
		if node.Pct <= 0 {
			errs = append(errs, fmt.Sprintf("%s: atr_not_bottom_pct requires pct > 0", path))
		}
		if node.Lookback <= 0 {
			errs = append(errs, fmt.Sprintf("%s: atr_not_bottom_pct requires lookback > 0", path))
		}
	case "atr_below_contracted_sma":
		if node.Factor <= 0 {
			errs = append(errs, fmt.Sprintf("%s: atr_below_contracted_sma requires factor > 0", path))
		}
	case "flat_slope":
		if node.Col == "" {
			errs = append(errs, fmt.Sprintf("%s: flat_slope requires col", path))
		}
	case "mean_rev_long", "mean_rev_short":
		if node.RefCol == "" {
			errs = append(errs, fmt.Sprintf("%s: %s requires ref_col", path, node.Op))
		}
	}

	return errs
}
