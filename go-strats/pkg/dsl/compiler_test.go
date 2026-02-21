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

func TestConsecutiveHigherCloses(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "consecutive_higher_closes", N: 3},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{100, 101, 102, 103, 104})
	if !fns[0](bars, 4) {
		t.Error("expected consecutive_higher_closes to be true on ascending bars")
	}
}

func TestConsecutiveLowerCloses(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "consecutive_lower_closes", N: 2},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := makeBars([]float64{104, 103, 102, 101})
	if !fns[0](bars, 3) {
		t.Error("expected consecutive_lower_closes to be true on descending bars")
	}
}

func TestInTopPctOfRange(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "in_top_pct_of_range", Pct: 0.30},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	// makeBars: High = close+1, Low = close-1, so range=2. Close is at 50% of range.
	// With pct=0.30 we need close in top 30%, i.e. close >= High - 0.30*range = High - 0.6
	// That means close >= 101.4 but close=102, High=103, Low=101 => close at 50% => NOT in top 30%
	// Need a bar where close is near high.
	bars := []types.BarData{
		{
			Bar:        types.Bar{Open: 100, High: 105, Low: 100, Close: 104.5, Volume: 1000},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
	}
	// range=5, top 30% starts at 105 - 0.30*5 = 103.5. Close=104.5 => in top 30%
	if !fns[0](bars, 0) {
		t.Error("expected in_top_pct_of_range(0.30) to be true when close is near high")
	}
}

func TestInBottomPctOfRange(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "in_bottom_pct_of_range", Pct: 0.30},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Open: 100, High: 105, Low: 100, Close: 100.5, Volume: 1000},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
	}
	// range=5, bottom 30% ends at 100 + 0.30*5 = 101.5. Close=100.5 => in bottom 30%
	if !fns[0](bars, 0) {
		t.Error("expected in_bottom_pct_of_range(0.30) to be true when close is near low")
	}
}

func TestCloseAboveUpperChannel(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "close_above_upper_channel", Col: "ema_20", Multiplier: 1.0},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 110},
			Indicators: types.IndicatorRow{"ema_20": 100.0, "atr_14": 5.0},
		},
	}
	// close(110) > ema_20(100) + 1.0*atr_14(5) = 105 => true
	if !fns[0](bars, 0) {
		t.Error("expected close_above_upper_channel to be true")
	}
}

func TestCloseBelowLowerChannel(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "close_below_lower_channel", Col: "ema_20", Multiplier: 1.0},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 90},
			Indicators: types.IndicatorRow{"ema_20": 100.0, "atr_14": 5.0},
		},
	}
	// close(90) < ema_20(100) - 1.0*atr_14(5) = 95 => true
	if !fns[0](bars, 0) {
		t.Error("expected close_below_lower_channel to be true")
	}
}

func TestTRIXCrossesAboveSMA(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "trix_crosses_above_sma"},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
	// TRIX uses an internal SMA calculation so just verify it compiles
}

func TestTRIXCrossesBelowSMA(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "trix_crosses_below_sma"},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestBreaksAboveSMAEnvelope(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "breaks_above_sma_envelope", Col: "sma_20", Multiplier: 1.0},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestBreaksBelowSMAEnvelope(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "breaks_below_sma_envelope", Col: "sma_20", Multiplier: 1.0},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestFlatSlope(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "flat_slope", Col: "linearreg_slope_20", Epsilon: 0.001},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 100},
			Indicators: types.IndicatorRow{"linearreg_slope_20": 0.0005},
		},
	}
	// abs(0.0005) < 0.001 => true
	if !fns[0](bars, 0) {
		t.Error("expected flat_slope to be true when slope is near zero")
	}
}

func TestATRBelowContractedSMA(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "atr_below_contracted_sma", Factor: 0.80},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 100},
			Indicators: types.IndicatorRow{"atr_14": 1.5, "atr_sma_50": 2.5},
		},
	}
	// atr_14(1.5) < 0.80 * atr_sma_50(2.5) = 2.0 => true
	if !fns[0](bars, 0) {
		t.Error("expected atr_below_contracted_sma to be true")
	}
}

func TestMeanRevLong(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "mean_rev_long", RefCol: "ema_20", Multiplier: 1.5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 90},
			Indicators: types.IndicatorRow{"ema_20": 100.0, "atr_14": 5.0},
		},
	}
	// (ema_20(100) - close(90)) = 10 > 1.5*atr_14(5) = 7.5 => true
	if !fns[0](bars, 0) {
		t.Error("expected mean_rev_long to be true when close is far below ref")
	}
}

func TestMeanRevShort(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "mean_rev_short", RefCol: "ema_20", Multiplier: 1.5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 110},
			Indicators: types.IndicatorRow{"ema_20": 100.0, "atr_14": 5.0},
		},
	}
	// (close(110) - ema_20(100)) = 10 > 1.5*atr_14(5) = 7.5 => true
	if !fns[0](bars, 0) {
		t.Error("expected mean_rev_short to be true when close is far above ref")
	}
}

func TestMajorityBull(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "majority_bull"},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar: types.Bar{Close: 100},
			Indicators: types.IndicatorRow{
				"ema_20":    100.0, // ema_20 > ema_50 => bull
				"ema_50":    95.0,
				"rsi_14":    60.0, // rsi > 55 => bull (was > 50 based on conditions.go at line 1105)
				"macd_hist": 0.5,  // macd_hist > 0 => bull
			},
		},
	}
	if !fns[0](bars, 0) {
		t.Error("expected majority_bull to be true with all 3 bullish signals")
	}
}

func TestMajorityBear(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "majority_bear"},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{
			Bar: types.Bar{Close: 100},
			Indicators: types.IndicatorRow{
				"ema_20":    90.0,  // ema_20 < ema_50 => bear
				"ema_50":    95.0,
				"rsi_14":    40.0,  // rsi < 45 => bear
				"macd_hist": -0.5,  // macd_hist < 0 => bear
			},
		},
	}
	if !fns[0](bars, 0) {
		t.Error("expected majority_bear to be true with all 3 bearish signals")
	}
}

func TestNarrowestRange(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "narrowest_range", Lookback: 3},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	bars := []types.BarData{
		{Bar: types.Bar{High: 105, Low: 100, Close: 102}, Indicators: types.IndicatorRow{"atr_14": 2.0}},
		{Bar: types.Bar{High: 104, Low: 100, Close: 102}, Indicators: types.IndicatorRow{"atr_14": 2.0}},
		{Bar: types.Bar{High: 103, Low: 100, Close: 102}, Indicators: types.IndicatorRow{"atr_14": 2.0}},
		{Bar: types.Bar{High: 101, Low: 100, Close: 100.5}, Indicators: types.IndicatorRow{"atr_14": 2.0}}, // range=1, smallest
	}
	if !fns[0](bars, 3) {
		t.Error("expected narrowest_range to be true when current bar has smallest range")
	}
}

func TestRibbonBreakLong(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "ribbon_break_long", Lookback: 3, Multiplier: 0.5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestRibbonExitLong(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "ribbon_exit_long", Multiplier: 0.5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestDoubleTapBelowBB(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "double_tap_below_bb", Lookback: 5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestATRNotBottomPct(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "atr_not_bottom_pct", Pct: 20, Lookback: 5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

func TestPullbackBelow(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "pullback_below", LevelCol: "bb_middle", ToleranceATRMult: 0.5},
	}
	fns, err := Compile(nodes)
	if err != nil {
		t.Fatalf("compile: %v", err)
	}
	if len(fns) != 1 {
		t.Fatalf("expected 1 fn, got %d", len(fns))
	}
}

// --- Error cases for new operators ---

func TestConsecutiveHigherClosesError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "consecutive_higher_closes"},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for consecutive_higher_closes without n")
	}
}

func TestNarrowestRangeError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "narrowest_range"},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for narrowest_range without lookback")
	}
}

func TestInTopPctOfRangeError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "in_top_pct_of_range"},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for in_top_pct_of_range without pct")
	}
}

func TestCloseAboveUpperChannelError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "close_above_upper_channel", Multiplier: 2.0},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for close_above_upper_channel without col")
	}
}

func TestFlatSlopeError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "flat_slope", Epsilon: 0.001},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for flat_slope without col")
	}
}

func TestMeanRevLongError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "mean_rev_long", Multiplier: 1.5},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for mean_rev_long without ref_col")
	}
}

func TestATRBelowContractedSMAError(t *testing.T) {
	nodes := []ConditionNode{
		{Op: "atr_below_contracted_sma"},
	}
	_, err := Compile(nodes)
	if err == nil {
		t.Error("expected error for atr_below_contracted_sma without factor")
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
