// Package dsl provides a JSON-based DSL interpreter for strategy conditions.
//
// The DSL maps structured JSON condition nodes to compiled Go ConditionFn closures,
// bridging the gap between the frontend condition builder UI and the go-strats
// condition evaluation engine.
//
// Each condition node has an "op" field that determines which condition factory
// to call from the conditions package. The compiler produces the same ConditionFn
// closures that predefined strategies use, so evaluation is identical.
package dsl

import (
	"encoding/json"
	"fmt"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// ConditionNode represents a single condition in the JSON DSL.
// It uses a flat struct with optional fields — the compiler selects
// which fields to read based on the Op value.
type ConditionNode struct {
	Op string `json:"op"`

	// Comparison operators: col + ref
	Col string `json:"col,omitempty"`
	Ref *Ref   `json:"ref,omitempty"`

	// Parameterized operators
	N         int     `json:"n,omitempty"`
	Threshold float64 `json:"threshold,omitempty"`
	Lookback  int     `json:"lookback,omitempty"`
	Multiplier float64 `json:"multiplier,omitempty"`

	// Pullback
	LevelCol          string  `json:"level_col,omitempty"`
	ToleranceATRMult  float64 `json:"tolerance_atr_mult,omitempty"`

	// Divergence / candle
	IndicatorCol string `json:"indicator_col,omitempty"`
	PatternCol   string `json:"pattern_col,omitempty"`

	// Squeeze / BB
	WidthCol string `json:"width_col,omitempty"`

	// Gap
	ATRMult float64 `json:"atr_mult,omitempty"`

	// Deviation
	RefCol string `json:"ref_col,omitempty"`

	// ADX range
	Low  float64 `json:"low,omitempty"`
	High float64 `json:"high,omitempty"`

	// Composite operators
	Conditions []ConditionNode `json:"conditions,omitempty"`
}

// Ref represents either a column reference or a literal numeric value.
type Ref struct {
	Col   string   `json:"col,omitempty"`
	Value *float64 `json:"value,omitempty"`
}

// Compile takes a slice of JSON-parsed condition nodes and returns
// compiled Go ConditionFn closures. Returns an error if any node
// contains an unknown operator or is missing required fields.
func Compile(nodes []ConditionNode) ([]types.ConditionFn, error) {
	fns := make([]types.ConditionFn, 0, len(nodes))
	for i, node := range nodes {
		fn, err := compileNode(node)
		if err != nil {
			return nil, fmt.Errorf("condition[%d]: %w", i, err)
		}
		fns = append(fns, fn)
	}
	return fns, nil
}

// ParseAndCompile parses raw JSON bytes into condition nodes and compiles them.
func ParseAndCompile(raw json.RawMessage) ([]types.ConditionFn, error) {
	if len(raw) == 0 || string(raw) == "null" {
		return nil, nil
	}

	var nodes []ConditionNode
	if err := json.Unmarshal(raw, &nodes); err != nil {
		return nil, fmt.Errorf("parsing condition JSON: %w", err)
	}

	return Compile(nodes)
}
