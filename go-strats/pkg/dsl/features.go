package dsl

// ExtractRequiredFeatures walks the condition tree and collects all
// indicator column names referenced by condition nodes.
// These are the columns the data pipeline must compute for this strategy.
func ExtractRequiredFeatures(nodes []ConditionNode) []string {
	seen := make(map[string]bool)
	for _, node := range nodes {
		extractFromNode(node, seen)
	}

	features := make([]string, 0, len(seen))
	for col := range seen {
		features = append(features, col)
	}
	return features
}

func extractFromNode(node ConditionNode, seen map[string]bool) {
	// Direct column references
	if node.Col != "" {
		seen[node.Col] = true
	}
	if node.Ref != nil && node.Ref.Col != "" {
		seen[node.Ref.Col] = true
	}

	// Named column fields
	if node.LevelCol != "" {
		seen[node.LevelCol] = true
	}
	if node.IndicatorCol != "" {
		seen[node.IndicatorCol] = true
	}
	if node.PatternCol != "" {
		seen[node.PatternCol] = true
	}
	if node.WidthCol != "" {
		seen[node.WidthCol] = true
	}
	if node.RefCol != "" {
		seen[node.RefCol] = true
	}

	// Operators that implicitly require ATR
	switch node.Op {
	case "pullback_to", "range_exceeds_atr", "gap_up", "gap_down",
		"deviation_below", "deviation_above":
		seen["atr_14"] = true
	}

	// ADX operators implicitly require adx_14
	if node.Op == "adx_in_range" {
		seen["adx_14"] = true
	}

	// BB width increasing implicitly requires bb_width
	if node.Op == "bb_width_increasing" {
		seen["bb_width"] = true
	}

	// Recurse into composite children
	for _, child := range node.Conditions {
		extractFromNode(child, seen)
	}
}
