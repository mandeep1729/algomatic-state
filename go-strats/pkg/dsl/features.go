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
	case "pullback_to", "pullback_below", "range_exceeds_atr", "gap_up", "gap_down",
		"deviation_below", "deviation_above",
		"close_above_upper_channel", "close_below_lower_channel",
		"ribbon_break_long", "ribbon_break_short", "ribbon_exit_long", "ribbon_exit_short",
		"breaks_above_sma_envelope", "breaks_below_sma_envelope",
		"atr_not_bottom_pct", "atr_below_contracted_sma",
		"mean_rev_long", "mean_rev_short",
		"in_top_pct_of_range", "in_bottom_pct_of_range", "narrowest_range":
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

	// TRIX operators implicitly require trix_15
	if node.Op == "trix_crosses_above_sma" || node.Op == "trix_crosses_below_sma" {
		seen["trix_15"] = true
	}

	// Double tap BB operators implicitly require bb_lower/bb_upper
	if node.Op == "double_tap_below_bb" {
		seen["bb_lower"] = true
	}
	if node.Op == "double_tap_above_bb" {
		seen["bb_upper"] = true
	}

	// ATR below contracted SMA implicitly requires atr_sma_50
	if node.Op == "atr_below_contracted_sma" {
		seen["atr_sma_50"] = true
	}

	// Ribbon operators implicitly require ema_20 and ema_50
	switch node.Op {
	case "ribbon_break_long", "ribbon_break_short", "ribbon_exit_long", "ribbon_exit_short":
		seen["ema_20"] = true
		seen["ema_50"] = true
	}

	// Majority operators implicitly require ema_20, ema_50, rsi_14, macd_hist
	if node.Op == "majority_bull" || node.Op == "majority_bear" {
		seen["ema_20"] = true
		seen["ema_50"] = true
		seen["rsi_14"] = true
		seen["macd_hist"] = true
	}

	// Recurse into composite children
	for _, child := range node.Conditions {
		extractFromNode(child, seen)
	}
}
