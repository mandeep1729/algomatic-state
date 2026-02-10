package conditions

import (
	"math"
	"testing"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// makeBars creates a slice of BarData from close prices.
func makeBars(closes []float64) []types.BarData {
	bars := make([]types.BarData, len(closes))
	for i, c := range closes {
		bars[i] = types.BarData{
			Bar: types.Bar{
				Open:   c - 0.5,
				High:   c + 1.0,
				Low:    c - 1.0,
				Close:  c,
				Volume: 1000,
			},
			Indicators: make(types.IndicatorRow),
		}
	}
	return bars
}

// makeBarsWithIndicators creates bars from close prices and adds named indicator arrays.
func makeBarsWithIndicators(closes []float64, indicators map[string][]float64) []types.BarData {
	bars := make([]types.BarData, len(closes))
	for i, c := range closes {
		bars[i] = types.BarData{
			Bar: types.Bar{
				Open:   c - 0.5,
				High:   c + 1.0,
				Low:    c - 1.0,
				Close:  c,
				Volume: 1000,
			},
			Indicators: make(types.IndicatorRow),
		}
		for name, values := range indicators {
			if i < len(values) {
				bars[i].Indicators[name] = values[i]
			}
		}
	}
	return bars
}

func TestCrossesAbove(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104},
		map[string][]float64{
			"ema_20": {50, 49, 48, 51, 52},
			"ema_50": {50, 50, 50, 50, 50},
		},
	)

	fn := CrossesAbove("ema_20", ColRef("ema_50"))

	// idx 0: no prior bar
	if fn(bars, 0) {
		t.Error("expected false at idx 0 (no prior bar)")
	}
	// idx 1: 50->49 vs 50->50, no cross
	if fn(bars, 1) {
		t.Error("expected false at idx 1 (no cross)")
	}
	// idx 3: 48->51 crosses above 50->50
	if !fn(bars, 3) {
		t.Error("expected true at idx 3 (crosses above)")
	}
	// idx 4: 51->52 both above, no cross
	if fn(bars, 4) {
		t.Error("expected false at idx 4 (already above)")
	}
}

func TestCrossesBelow(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104},
		map[string][]float64{
			"ema_20": {52, 51, 50, 49, 48},
			"ema_50": {50, 50, 50, 50, 50},
		},
	)

	fn := CrossesBelow("ema_20", ColRef("ema_50"))

	// idx 2: 51->50 crosses at boundary (50 >= 50 and 50 < 50 is false)
	// Actually 51>=50 is true and 50<50 is false, so no cross
	if fn(bars, 2) {
		t.Error("expected false at idx 2 (at boundary)")
	}
	// idx 3: 50->49 crosses below 50->50
	if !fn(bars, 3) {
		t.Error("expected true at idx 3 (crosses below)")
	}
}

func TestAboveBelow(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104},
		map[string][]float64{
			"rsi_14": {30, 40, 50, 60, 70},
		},
	)

	above := Above("rsi_14", NumRef(55))
	below := Below("rsi_14", NumRef(55))

	if above(bars, 2) {
		t.Error("rsi=50 should not be above 55")
	}
	if !above(bars, 3) {
		t.Error("rsi=60 should be above 55")
	}
	if !below(bars, 2) {
		t.Error("rsi=50 should be below 55")
	}
	if below(bars, 3) {
		t.Error("rsi=60 should not be below 55")
	}
}

func TestRisingFalling(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104},
		map[string][]float64{
			"adx_14": {10, 12, 14, 16, 18},
		},
	)

	rising := Rising("adx_14", 3)
	falling := Falling("adx_14", 3)

	if !rising(bars, 3) {
		t.Error("adx should be rising at idx 3")
	}
	if falling(bars, 3) {
		t.Error("adx should not be falling at idx 3")
	}
	if rising(bars, 1) {
		t.Error("not enough bars for rising check at idx 1 with n=3")
	}
}

func TestAllOfAnyOf(t *testing.T) {
	trueFunc := func(bars []types.BarData, idx int) bool { return true }
	falseFunc := func(bars []types.BarData, idx int) bool { return false }

	bars := makeBarsWithIndicators([]float64{100}, nil)

	if !AllOf(trueFunc, trueFunc)(bars, 0) {
		t.Error("AllOf with all true should return true")
	}
	if AllOf(trueFunc, falseFunc)(bars, 0) {
		t.Error("AllOf with one false should return false")
	}
	if !AnyOf(trueFunc, falseFunc)(bars, 0) {
		t.Error("AnyOf with one true should return true")
	}
	if AnyOf(falseFunc, falseFunc)(bars, 0) {
		t.Error("AnyOf with all false should return false")
	}
}

func TestConsecutiveHigherCloses(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 102},
		nil,
	)

	fn := ConsecutiveHigherCloses(3)
	if !fn(bars, 3) {
		t.Error("3 consecutive higher closes at idx 3")
	}
	if fn(bars, 4) {
		t.Error("close dropped at idx 4")
	}
}

func TestConsecutiveLowerCloses(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{104, 103, 102, 101, 102},
		nil,
	)

	fn := ConsecutiveLowerCloses(3)
	if !fn(bars, 3) {
		t.Error("3 consecutive lower closes at idx 3")
	}
	if fn(bars, 4) {
		t.Error("close rose at idx 4")
	}
}

func TestSqueeze(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104},
		map[string][]float64{
			"bb_width": {5.0, 4.5, 4.0, 3.5, 3.0},
		},
	)

	fn := Squeeze("bb_width", 4)
	// At idx 4, bb_width=3.0 is the lowest of last 4 bars (idx 1-4: 4.5, 4.0, 3.5, 3.0)
	if !fn(bars, 4) {
		t.Error("expected squeeze at idx 4 (lowest width)")
	}
}

func TestRangeExceedsATR(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{High: 110, Low: 100, Close: 105},
			Indicators: types.IndicatorRow{"atr_14": 4.0},
		},
	}

	fn := RangeExceedsATR(2.0)
	// Range = 10, 2.0 * 4.0 = 8.0, so 10 > 8 is true
	if !fn(bars, 0) {
		t.Error("range 10 should exceed 2.0 * ATR 4.0 = 8.0")
	}

	fn2 := RangeExceedsATR(3.0)
	// 3.0 * 4.0 = 12.0, 10 < 12 is false
	if fn2(bars, 0) {
		t.Error("range 10 should not exceed 3.0 * ATR 4.0 = 12.0")
	}
}

func TestBreaksAboveLevel(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{98, 99, 101, 102},
		map[string][]float64{
			"donchian_high_20": {100, 100, 100, 100},
		},
	)

	fn := BreaksAboveLevel("donchian_high_20")
	// idx 2: close went from 99 (<=100) to 101 (>100)
	if !fn(bars, 2) {
		t.Error("expected break above at idx 2")
	}
	// idx 3: 101 was already above, no break
	if fn(bars, 3) {
		t.Error("expected no break at idx 3 (already above)")
	}
}

func TestBreaksBelowLevel(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{102, 101, 99, 98},
		map[string][]float64{
			"donchian_low_20": {100, 100, 100, 100},
		},
	)

	fn := BreaksBelowLevel("donchian_low_20")
	// idx 2: close went from 101 (>=100) to 99 (<100)
	if !fn(bars, 2) {
		t.Error("expected break below at idx 2")
	}
}

func TestPullbackTo(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{High: 105, Low: 99.5, Close: 101},
			Indicators: types.IndicatorRow{"ema_20": 100, "atr_14": 2.0},
		},
	}

	fn := PullbackTo("ema_20", 0.5)
	// Low=99.5 <= 100 + 0.5*2.0 = 101, and Close=101 > 100: true
	if !fn(bars, 0) {
		t.Error("expected pullback at idx 0")
	}
}

func TestBullishDivergence(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{105, 104, 103, 102, 101, 100},
		map[string][]float64{
			"rsi_14": {30, 32, 34, 36, 38, 35},
		},
	)
	// Price lower low: bars[5].Low < bars[0].Low (99 < 104) - yes
	// RSI higher low: 35 > 30 - yes

	fn := BullishDivergence("rsi_14", 5)
	if !fn(bars, 5) {
		t.Error("expected bullish divergence at idx 5")
	}
}

func TestMissingIndicatorReturnsFalse(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101},
		nil, // no indicators
	)

	fn := Above("rsi_14", NumRef(50))
	if fn(bars, 0) {
		t.Error("missing indicator should return false")
	}
}

func TestNaNIndicatorReturnsFalse(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100},
		map[string][]float64{
			"rsi_14": {math.NaN()},
		},
	)

	fn := Above("rsi_14", NumRef(50))
	if fn(bars, 0) {
		t.Error("NaN indicator should return false")
	}
}

func TestInTopPctOfRange(t *testing.T) {
	bars := []types.BarData{
		{Bar: types.Bar{High: 110, Low: 100, Close: 108}},
	}

	fn := InTopPctOfRange(0.25)
	// (108-100)/(110-100) = 0.8 >= 0.75
	if !fn(bars, 0) {
		t.Error("close at 80% of range should be in top 25%")
	}

	fn2 := InTopPctOfRange(0.10)
	// 0.8 >= 0.90? no
	if fn2(bars, 0) {
		t.Error("close at 80% of range should not be in top 10%")
	}
}

func TestInBottomPctOfRange(t *testing.T) {
	bars := []types.BarData{
		{Bar: types.Bar{High: 110, Low: 100, Close: 102}},
	}

	fn := InBottomPctOfRange(0.25)
	// (102-100)/(110-100) = 0.2 <= 0.25
	if !fn(bars, 0) {
		t.Error("close at 20% of range should be in bottom 25%")
	}
}

func TestGapUp(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Open: 100, High: 105, Low: 99, Close: 103},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
		{
			Bar:        types.Bar{Open: 106, High: 108, Low: 105, Close: 107},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
	}

	fn := GapUp(1.0)
	// Gap = 106 - 103 = 3, threshold = 1.0 * 2.0 = 2.0, 3 > 2 is true
	if !fn(bars, 1) {
		t.Error("expected gap up at idx 1")
	}
}

func TestGapDown(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Open: 100, High: 105, Low: 99, Close: 103},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
		{
			Bar:        types.Bar{Open: 100, High: 101, Low: 99, Close: 100},
			Indicators: types.IndicatorRow{"atr_14": 2.0},
		},
	}

	fn := GapDown(1.0)
	// Gap = 100 - 103 = -3, threshold = -1.0 * 2.0 = -2.0
	// open < closePrev - atrMult*atr => 100 < 103 - 2 = 101, yes
	if !fn(bars, 1) {
		t.Error("expected gap down at idx 1")
	}
}

func TestDeviationBelow(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 90},
			Indicators: types.IndicatorRow{"ema_20": 100, "atr_14": 3.0},
		},
	}

	fn := DeviationBelow("close", "ema_20", 2.0)
	// (100 - 90) = 10 > 2.0*3.0 = 6.0, yes
	if !fn(bars, 0) {
		t.Error("expected deviation below")
	}
}

func TestDeviationAbove(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 110},
			Indicators: types.IndicatorRow{"ema_20": 100, "atr_14": 3.0},
		},
	}

	fn := DeviationAbove("close", "ema_20", 2.0)
	// (110 - 100) = 10 > 2.0*3.0 = 6.0, yes
	if !fn(bars, 0) {
		t.Error("expected deviation above")
	}
}

func TestWasBelowThenCrossesAbove(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104, 105},
		map[string][]float64{
			"rsi_14": {45, 40, 35, 42, 49, 52},
		},
	)

	fn := WasBelowThenCrossesAbove("rsi_14", 50, 5)
	// At idx 5: prev=49 <= 50, curr=52 > 50 (cross)
	// Was below 50 in lookback: yes, many bars below 50
	if !fn(bars, 5) {
		t.Error("expected was_below_then_crosses_above at idx 5")
	}
}

func TestHeldForNBars(t *testing.T) {
	bars := makeBarsWithIndicators(
		[]float64{100, 101, 102, 103, 104},
		map[string][]float64{
			"adosc": {1, 2, 3, 4, 5},
		},
	)

	fn := HeldForNBars("adosc", func(v float64) bool { return v > 0 }, 3)
	if !fn(bars, 4) {
		t.Error("adosc positive for last 3 bars at idx 4")
	}
	if fn(bars, 1) {
		t.Error("not enough bars at idx 1 for n=3")
	}
}

func TestMajorityBull(t *testing.T) {
	bars := []types.BarData{
		{
			Bar: types.Bar{Close: 105},
			Indicators: types.IndicatorRow{
				"ema_20":    52,
				"ema_50":    50,
				"rsi_14":    60,
				"macd_hist": 0.5,
			},
		},
	}

	fn := MajorityBull()
	if !fn(bars, 0) {
		t.Error("all 3 bull signals, should be majority")
	}

	// Test with only 1 bull signal (not majority)
	bars[0].Indicators["ema_20"] = 48 // bear
	bars[0].Indicators["rsi_14"] = 40 // bear
	if fn(bars, 0) {
		t.Error("only 1 bull signal, should not be majority")
	}
}

func TestMajorityBear(t *testing.T) {
	bars := []types.BarData{
		{
			Bar: types.Bar{Close: 95},
			Indicators: types.IndicatorRow{
				"ema_20":    48,
				"ema_50":    50,
				"rsi_14":    40,
				"macd_hist": -0.5,
			},
		},
	}

	fn := MajorityBear()
	if !fn(bars, 0) {
		t.Error("all 3 bear signals, should be majority")
	}
}

func TestFlatSlope(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 100},
			Indicators: types.IndicatorRow{"linearreg_slope_20": 0.0005},
		},
	}

	fn := FlatSlope("linearreg_slope_20", 0.001)
	if !fn(bars, 0) {
		t.Error("slope 0.0005 should be flat (< 0.001)")
	}

	bars[0].Indicators["linearreg_slope_20"] = 0.002
	if fn(bars, 0) {
		t.Error("slope 0.002 should not be flat (>= 0.001)")
	}
}

func TestATRBelowContractedSMA(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 100},
			Indicators: types.IndicatorRow{"atr_14": 1.5, "atr_sma_50": 2.0},
		},
	}

	fn := ATRBelowContractedSMA(0.85)
	// 1.5 < 0.85 * 2.0 = 1.7, yes
	if !fn(bars, 0) {
		t.Error("ATR 1.5 should be below 0.85 * 2.0 = 1.7")
	}
}

func TestCloseAboveUpperChannel(t *testing.T) {
	bars := []types.BarData{
		{
			Bar:        types.Bar{Close: 110},
			Indicators: types.IndicatorRow{"ema_20": 100, "atr_14": 4.0},
		},
	}

	fn := CloseAboveUpperChannel("ema_20", 2.0)
	// 110 > 100 + 2*4 = 108, yes
	if !fn(bars, 0) {
		t.Error("close 110 should be above upper channel 108")
	}
}

func TestOHLCVColumnsAccessible(t *testing.T) {
	bars := []types.BarData{
		{
			Bar: types.Bar{Open: 100, High: 105, Low: 95, Close: 103, Volume: 5000},
		},
	}

	// Conditions should be able to reference OHLCV columns
	fn := Above("close", ColRef("open"))
	if !fn(bars, 0) {
		t.Error("close 103 should be above open 100")
	}

	fn2 := Below("low", ColRef("high"))
	if !fn2(bars, 0) {
		t.Error("low 95 should be below high 105")
	}
}
