package dsl

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// makeBars creates a simple slice of BarData for testing.
func makeBars(closes []float64) []types.BarData {
	bars := make([]types.BarData, len(closes))
	for i, c := range closes {
		bars[i] = types.BarData{
			Bar: types.Bar{
				Timestamp: time.Date(2026, 1, 1, 0, i, 0, 0, time.UTC),
				Open:      c - 0.5,
				High:      c + 1.0,
				Low:       c - 1.0,
				Close:     c,
				Volume:    1000,
			},
			Indicators: types.IndicatorRow{
				"ema_20":    c * 0.98,
				"ema_50":    c * 0.95,
				"rsi_14":    55.0,
				"adx_14":    25.0,
				"atr_14":    2.0,
				"bb_width":  float64(10 - i%5),
				"bb_upper":  c + 3.0,
				"bb_lower":  c - 3.0,
				"macd_hist": float64(i) * 0.1,
			},
		}
	}
	return bars
}

func floatPtr(v float64) *float64 { return &v }

func TestCrossesAbove(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "crosses_above", Col: "close", Ref: &Ref{Col: "ema_20"}},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}

	// Create bars where close crosses above ema_20
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 10.0},
			Indicators: types.IndicatorRow{"ema_20": 11.0},
		},
		{
			Bar:        types.Bar{Close: 12.0},
			Indicators: types.IndicatorRow{"ema_20": 11.0},
		},
	}
	if !fns[0](bars, 1) {
		t.Error("expected crosses_above to be true")
	}
}

func TestAboveWithNumericRef(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "above", Col: "rsi_14", Ref: &Ref{Value: floatPtr(30.0)}},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100, 101, 102})
	// rsi_14 is 55.0 in makeBars — should be above 30
	if !fns[0](bars, 2) {
		t.Error("expected above(rsi_14, 30) to be true")
	}
}

func TestBelowWithNumericRef(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "below", Col: "rsi_14", Ref: &Ref{Value: floatPtr(70.0)}},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100, 101, 102})
	if !fns[0](bars, 2) {
		t.Error("expected below(rsi_14, 70) to be true")
	}
}

func TestRising(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "rising", Col: "close", N: 3},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100, 101, 102, 103, 104})
	if !fns[0](bars, 4) {
		t.Error("expected rising(close, 3) to be true on ascending bars")
	}
}

func TestFalling(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "falling", Col: "close", N: 2},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{104, 103, 102, 101})
	if !fns[0](bars, 3) {
		t.Error("expected falling(close, 2) to be true on descending bars")
	}
}

func TestAllOf(t *testing.T) {
	nodes := []ConditionNode{
		{
			Op: "all_of",
			Conditions: []ConditionNode{
				{Op: "above", Col: "rsi_14", Ref: &Ref{Value: floatPtr(30.0)}},
				{Op: "below", Col: "rsi_14", Ref: &Ref{Value: floatPtr(70.0)}},
			},
		},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100})
	if !fns[0](bars, 0) {
		t.Error("expected all_of(above 30, below 70) to be true for rsi=55")
	}
}

func TestAnyOf(t *testing.T) {
	nodes := []ConditionNode{
		{
			Op: "any_of",
			Conditions: []ConditionNode{
				{Op: "above", Col: "rsi_14", Ref: &Ref{Value: floatPtr(80.0)}},
				{Op: "below", Col: "rsi_14", Ref: &Ref{Value: floatPtr(60.0)}},
			},
		},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100})
	// rsi=55, so above(80) is false but below(60) is true
	if !fns[0](bars, 0) {
		t.Error("expected any_of to be true when one child matches")
	}
}

func TestADXInRange(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "adx_in_range", Low: 20.0, High: 30.0},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100})
	// adx_14 = 25.0 in makeBars
	if !fns[0](bars, 0) {
		t.Error("expected adx_in_range(20, 30) to be true for adx=25")
	}
}

func TestGapUp(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "gap_up", ATRMult: 0.5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 100.0},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
		{
			Bar:        types.Bar{Open: 102.0, Close: 102.0},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
	}
	// gap = 102 - 100 = 2.0 > 0.5 * 2.0 = 1.0
	if !fns[0](bars, 1) {
		t.Error("expected gap_up to be true")
	}
}

func TestUnknownOpError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "foobar"},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for unknown operator")
	}
}

func TestMissingColError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "rising", N: 3},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for missing col")
	}
}

func TestParseAndCompile(t *testing.T) {
	raw := json.RawMessage(`[{"op":"above","col":"rsi_14","ref":{"value":30}}]`)
	fns, err := ParseAndCompile(raw)
	if err != nil {
		t.Fatalf("ParseAndCompile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
	bars := makeBars([]float64{100})
	if !fns[0](bars, 0) {
		t.Error("expected above(rsi, 30) to be true")
	}
}

func TestParseAndCompileNull(t *testing.T) {
	fns, err := ParseAndCompile(nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if fns != nil {
		t.Error("expected nil for null input")
	}
}

func TestValidateJSON(t *testing.T) {
	raw := json.RawMessage(`[{"op":"foobar"}]`)
	errs := ValidateJSON(raw)
	if len(errs) == 0 {
		t.Error("expected validation errors for unknown op")
	}
}

func TestValidateConditions(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "rising"},
	}
	errs := ValidateConditions(nodes)
	if len(errs) == 0 {
		t.Error("expected validation errors for rising without col/n")
	}
}

func TestExtractFeatures(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "crosses_above", Col: "close", Ref: &Ref{Col: "ema_20"}},
		{Op: "above", Col: "rsi_14", Ref: &Ref{Value: floatPtr(30.0)}},
		{Op: "gap_up", ATRMult: 0.5},
	}
	features := ExtractRequiredFeatures(nodes)
	featureSet := make(map[string]bool)
	for _, f := range features {
		featureSet[f] = true
	}
	for _, expected := range []string{"close", "ema_20", "rsi_14", "atr_14"} {
		if !featureSet[expected] {
			t.Errorf("expected feature %q in extracted features", expected)
		}
	}
}

func TestHeldAbove(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "held_above", Col: "rsi_14", Threshold: 50.0, N: 3},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100, 101, 102, 103})
	// rsi_14 = 55.0 in all bars, threshold = 50 → should be true
	if !fns[0](bars, 3) {
		t.Error("expected held_above to be true")
	}
}

func TestSqueeze(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "squeeze", WidthCol: "bb_width", Lookback: 3},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}

	// Create bars where bb_width is decreasing (squeeze)
	bars := []types.BarData{
		{Bar: types.Bar{Close: 100}, Indicators: types.IndicatorRow{"bb_width": 10.0}},
		{Bar: types.Bar{Close: 101}, Indicators: types.IndicatorRow{"bb_width": 8.0}},
		{Bar: types.Bar{Close: 102}, Indicators: types.IndicatorRow{"bb_width": 6.0}},
		{Bar: types.Bar{Close: 103}, Indicators: types.IndicatorRow{"bb_width": 4.0}},
	}
	// At idx=3, bb_width=4.0 is the lowest in lookback=3 window
	if !fns[0](bars, 3) {
		t.Error("expected squeeze to be true when current width is lowest")
	}
}
