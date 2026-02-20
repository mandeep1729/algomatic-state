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
	"pullback_to": true,
	"bullish_divergence": true, "bearish_divergence": true,
	"candle_bullish": true, "candle_bearish": true,
	"breaks_above_level": true, "breaks_below_level": true,
	"squeeze": true, "range_exceeds_atr": true, "bb_width_increasing": true,
	"gap_up": true, "gap_down": true,
	"held_above": true, "held_below": true,
	"was_below_then_crosses_above": true, "was_above_then_crosses_below": true,
	"adx_in_range": true,
	"deviation_below": true, "deviation_above": true,
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
	}

	return errs
}
