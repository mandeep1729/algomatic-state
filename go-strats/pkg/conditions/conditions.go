// Package conditions provides reusable condition factory functions for strategy definitions.
//
// Each factory returns a ConditionFn: func(bars []BarData, idx int) bool
// that receives the full bar data slice and the current bar index.
// These mirror the Python conditions in src/strats_prob/conditions.py.
package conditions

import (
	"math"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// val resolves a reference to a numeric value at bar idx.
// If ref is a column name (string), it looks up the indicator.
// Otherwise it returns the literal float64 value.
type Ref struct {
	Col string  // indicator column name (used if non-empty)
	Val float64 // literal value (used if Col is empty)
}

// ColRef creates a Ref from a column name.
func ColRef(col string) Ref {
	return Ref{Col: col}
}

// NumRef creates a Ref from a numeric value.
func NumRef(val float64) Ref {
	return Ref{Val: val}
}

// resolve returns the numeric value for a Ref at the given bar.
func resolve(bars []types.BarData, idx int, ref Ref) (float64, bool) {
	if ref.Col != "" {
		return getIndicator(bars, idx, ref.Col)
	}
	return ref.Val, true
}

// getIndicator safely retrieves an indicator value at bar idx.
func getIndicator(bars []types.BarData, idx int, col string) (float64, bool) {
	if idx < 0 || idx >= len(bars) {
		return math.NaN(), false
	}
	// Check OHLCV first
	switch col {
	case "open":
		return bars[idx].Bar.Open, true
	case "high":
		return bars[idx].Bar.High, true
	case "low":
		return bars[idx].Bar.Low, true
	case "close":
		return bars[idx].Bar.Close, true
	case "volume":
		return bars[idx].Bar.Volume, true
	}
	return bars[idx].Indicators.Get(col)
}

// safe returns true if the value is finite (not NaN or Inf).
func safe(v float64) bool {
	return !math.IsNaN(v) && !math.IsInf(v, 0)
}

// ---------------------------------------------------------------------------
// Cross conditions
// ---------------------------------------------------------------------------

// CrossesAbove returns true when colA crosses above colB (or a fixed value) at bar idx.
func CrossesAbove(colA string, refB Ref) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		currA, ok := getIndicator(bars, idx, colA)
		if !ok {
			return false
		}
		prevA, ok := getIndicator(bars, idx-1, colA)
		if !ok {
			return false
		}
		currB, ok := resolve(bars, idx, refB)
		if !ok {
			return false
		}
		prevB, ok := resolve(bars, idx-1, refB)
		if !ok {
			return false
		}
		return prevA <= prevB && currA > currB
	}
}

// CrossesBelow returns true when colA crosses below colB (or a fixed value) at bar idx.
func CrossesBelow(colA string, refB Ref) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		currA, ok := getIndicator(bars, idx, colA)
		if !ok {
			return false
		}
		prevA, ok := getIndicator(bars, idx-1, colA)
		if !ok {
			return false
		}
		currB, ok := resolve(bars, idx, refB)
		if !ok {
			return false
		}
		prevB, ok := resolve(bars, idx-1, refB)
		if !ok {
			return false
		}
		return prevA >= prevB && currA < currB
	}
}

// ---------------------------------------------------------------------------
// Threshold / comparison conditions
// ---------------------------------------------------------------------------

// Above returns true when col is above ref at the current bar.
func Above(col string, ref Ref) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		v, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		r, ok := resolve(bars, idx, ref)
		if !ok {
			return false
		}
		return v > r
	}
}

// Below returns true when col is below ref at the current bar.
func Below(col string, ref Ref) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		v, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		r, ok := resolve(bars, idx, ref)
		if !ok {
			return false
		}
		return v < r
	}
}

// ---------------------------------------------------------------------------
// Directional / trend conditions
// ---------------------------------------------------------------------------

// Rising returns true when col has been rising for the last n bars.
func Rising(col string, n int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < n {
			return false
		}
		for i := idx - n + 1; i <= idx; i++ {
			curr, ok := getIndicator(bars, i, col)
			if !ok {
				return false
			}
			prev, ok := getIndicator(bars, i-1, col)
			if !ok {
				return false
			}
			if curr <= prev {
				return false
			}
		}
		return true
	}
}

// Falling returns true when col has been falling for the last n bars.
func Falling(col string, n int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < n {
			return false
		}
		for i := idx - n + 1; i <= idx; i++ {
			curr, ok := getIndicator(bars, i, col)
			if !ok {
				return false
			}
			prev, ok := getIndicator(bars, i-1, col)
			if !ok {
				return false
			}
			if curr >= prev {
				return false
			}
		}
		return true
	}
}

// ---------------------------------------------------------------------------
// Combinators
// ---------------------------------------------------------------------------

// AllOf returns true when all sub-conditions are true.
func AllOf(conditions ...types.ConditionFn) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		for _, c := range conditions {
			if !c(bars, idx) {
				return false
			}
		}
		return true
	}
}

// AnyOf returns true when at least one sub-condition is true.
func AnyOf(conditions ...types.ConditionFn) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		for _, c := range conditions {
			if c(bars, idx) {
				return true
			}
		}
		return false
	}
}

// ---------------------------------------------------------------------------
// Pullback conditions
// ---------------------------------------------------------------------------

// PullbackTo returns true when price dips to level (within tolerance * ATR) and closes back above.
func PullbackTo(levelCol string, toleranceATRMult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		lowVal := bars[idx].Bar.Low
		closeVal := bars[idx].Bar.Close
		level, ok := getIndicator(bars, idx, levelCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		tolerance := toleranceATRMult * atr
		return lowVal <= level+tolerance && closeVal > level
	}
}

// PullbackBelow returns true when price spikes to level (within tolerance * ATR) and closes back below.
func PullbackBelow(levelCol string, toleranceATRMult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		highVal := bars[idx].Bar.High
		closeVal := bars[idx].Bar.Close
		level, ok := getIndicator(bars, idx, levelCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		tolerance := toleranceATRMult * atr
		return highVal >= level-tolerance && closeVal < level
	}
}

// ---------------------------------------------------------------------------
// Divergence conditions
// ---------------------------------------------------------------------------

// BullishDivergence returns true when price makes lower low but indicator makes higher low.
func BullishDivergence(indicatorCol string, lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		priceNow := bars[idx].Bar.Low
		pricePrev := bars[idx-lookback].Bar.Low
		indNow, ok := getIndicator(bars, idx, indicatorCol)
		if !ok {
			return false
		}
		indPrev, ok := getIndicator(bars, idx-lookback, indicatorCol)
		if !ok {
			return false
		}
		return priceNow < pricePrev && indNow > indPrev
	}
}

// BearishDivergence returns true when price makes higher high but indicator makes lower high.
func BearishDivergence(indicatorCol string, lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		priceNow := bars[idx].Bar.High
		pricePrev := bars[idx-lookback].Bar.High
		indNow, ok := getIndicator(bars, idx, indicatorCol)
		if !ok {
			return false
		}
		indPrev, ok := getIndicator(bars, idx-lookback, indicatorCol)
		if !ok {
			return false
		}
		return priceNow > pricePrev && indNow < indPrev
	}
}

// ---------------------------------------------------------------------------
// Candlestick pattern conditions
// ---------------------------------------------------------------------------

// CandleBullish returns true when the candle pattern column signals bullish (> 0).
func CandleBullish(patternCol string) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		v, ok := getIndicator(bars, idx, patternCol)
		if !ok {
			return false
		}
		return v > 0
	}
}

// CandleBearish returns true when the candle pattern column signals bearish (< 0).
func CandleBearish(patternCol string) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		v, ok := getIndicator(bars, idx, patternCol)
		if !ok {
			return false
		}
		return v < 0
	}
}

// ---------------------------------------------------------------------------
// Consecutive close conditions
// ---------------------------------------------------------------------------

// ConsecutiveHigherCloses returns true when the last count closes are each higher than the previous.
func ConsecutiveHigherCloses(count int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < count {
			return false
		}
		for i := idx - count + 1; i <= idx; i++ {
			if bars[i].Bar.Close <= bars[i-1].Bar.Close {
				return false
			}
		}
		return true
	}
}

// ConsecutiveLowerCloses returns true when the last count closes are each lower than the previous.
func ConsecutiveLowerCloses(count int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < count {
			return false
		}
		for i := idx - count + 1; i <= idx; i++ {
			if bars[i].Bar.Close >= bars[i-1].Bar.Close {
				return false
			}
		}
		return true
	}
}

// ---------------------------------------------------------------------------
// Volatility / range conditions
// ---------------------------------------------------------------------------

// Squeeze returns true when widthCol is at its lowest in the last lookback bars.
func Squeeze(widthCol string, lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		currWidth, ok := getIndicator(bars, idx, widthCol)
		if !ok {
			return false
		}
		for i := idx - lookback + 1; i < idx; i++ {
			w, ok := getIndicator(bars, i, widthCol)
			if !ok {
				return false
			}
			if w < currWidth {
				return false
			}
		}
		return true
	}
}

// RangeExceedsATR returns true when current bar range exceeds multiplier * ATR.
func RangeExceedsATR(multiplier float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		barRange := bars[idx].Bar.High - bars[idx].Bar.Low
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return barRange > multiplier*atr
	}
}

// NarrowestRange returns true when current bar range is the smallest of last lookback bars.
func NarrowestRange(lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback-1 {
			return false
		}
		currRange := bars[idx].Bar.High - bars[idx].Bar.Low
		for i := idx - lookback + 1; i < idx; i++ {
			r := bars[i].Bar.High - bars[i].Bar.Low
			if r < currRange {
				return false
			}
		}
		return true
	}
}

// ---------------------------------------------------------------------------
// Breakout conditions
// ---------------------------------------------------------------------------

// BreaksAboveLevel returns true when close breaks above levelCol at current bar.
func BreaksAboveLevel(levelCol string) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		closeNow := bars[idx].Bar.Close
		closePrev := bars[idx-1].Bar.Close
		levelNow, ok := getIndicator(bars, idx, levelCol)
		if !ok {
			return false
		}
		levelPrev, ok := getIndicator(bars, idx-1, levelCol)
		if !ok {
			return false
		}
		return closePrev <= levelPrev && closeNow > levelNow
	}
}

// BreaksBelowLevel returns true when close breaks below levelCol at current bar.
func BreaksBelowLevel(levelCol string) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		closeNow := bars[idx].Bar.Close
		closePrev := bars[idx-1].Bar.Close
		levelNow, ok := getIndicator(bars, idx, levelCol)
		if !ok {
			return false
		}
		levelPrev, ok := getIndicator(bars, idx-1, levelCol)
		if !ok {
			return false
		}
		return closePrev >= levelPrev && closeNow < levelNow
	}
}

// ---------------------------------------------------------------------------
// Range position conditions
// ---------------------------------------------------------------------------

// InTopPctOfRange returns true when close is in the top pct of bar range.
func InTopPctOfRange(pct float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		h := bars[idx].Bar.High
		l := bars[idx].Bar.Low
		c := bars[idx].Bar.Close
		if h == l {
			return false
		}
		return (c-l)/(h-l) >= (1.0 - pct)
	}
}

// InBottomPctOfRange returns true when close is in the bottom pct of bar range.
func InBottomPctOfRange(pct float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		h := bars[idx].Bar.High
		l := bars[idx].Bar.Low
		c := bars[idx].Bar.Close
		if h == l {
			return false
		}
		return (c-l)/(h-l) <= pct
	}
}

// ---------------------------------------------------------------------------
// Gap conditions
// ---------------------------------------------------------------------------

// GapUp returns true when open gaps up more than atrMult * ATR above prior close.
func GapUp(atrMult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		openNow := bars[idx].Bar.Open
		closePrev := bars[idx-1].Bar.Close
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return openNow > closePrev+atrMult*atr
	}
}

// GapDown returns true when open gaps down more than atrMult * ATR below prior close.
func GapDown(atrMult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		openNow := bars[idx].Bar.Open
		closePrev := bars[idx-1].Bar.Close
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return openNow < closePrev-atrMult*atr
	}
}

// ---------------------------------------------------------------------------
// Deviation condition
// ---------------------------------------------------------------------------

// DeviationBelow returns true when (refCol - col) > atrMult * ATR.
func DeviationBelow(col string, refCol string, atrMult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		v, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		r, ok := getIndicator(bars, idx, refCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return (r - v) > atrMult*atr
	}
}

// DeviationAbove returns true when (col - refCol) > atrMult * ATR.
func DeviationAbove(col string, refCol string, atrMult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		v, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		r, ok := getIndicator(bars, idx, refCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return (v - r) > atrMult*atr
	}
}

// ---------------------------------------------------------------------------
// Holding / state conditions
// ---------------------------------------------------------------------------

// WasBelowThenCrossesAbove returns true when col was below threshold
// within last lookback bars and now crosses above.
func WasBelowThenCrossesAbove(col string, threshold float64, lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		curr, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		prev, ok := getIndicator(bars, idx-1, col)
		if !ok {
			return false
		}
		// Must cross above now
		if !(prev <= threshold && curr > threshold) {
			return false
		}
		// Must have been below threshold within lookback
		for i := idx - lookback; i < idx; i++ {
			v, ok := getIndicator(bars, i, col)
			if ok && v < threshold {
				return true
			}
		}
		return false
	}
}

// WasAboveThenCrossesBelow returns true when col was above threshold
// within last lookback bars and now crosses below.
func WasAboveThenCrossesBelow(col string, threshold float64, lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		curr, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		prev, ok := getIndicator(bars, idx-1, col)
		if !ok {
			return false
		}
		if !(prev >= threshold && curr < threshold) {
			return false
		}
		for i := idx - lookback; i < idx; i++ {
			v, ok := getIndicator(bars, i, col)
			if ok && v > threshold {
				return true
			}
		}
		return false
	}
}

// HeldForNBars returns true when a lambda condition on col values has been true for last nBars.
func HeldForNBars(col string, check func(float64) bool, nBars int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < nBars-1 {
			return false
		}
		for i := idx - nBars + 1; i <= idx; i++ {
			v, ok := getIndicator(bars, i, col)
			if !ok || !check(v) {
				return false
			}
		}
		return true
	}
}

// ---------------------------------------------------------------------------
// Custom inline conditions for specific strategies
// ---------------------------------------------------------------------------

// CloseAboveUpperChannel returns true when close > ema_20 + mult*atr_14.
func CloseAboveUpperChannel(emaCcol string, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		closeVal := bars[idx].Bar.Close
		ema, ok := getIndicator(bars, idx, emaCcol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return closeVal > ema+mult*atr
	}
}

// CloseBelowLowerChannel returns true when close < ema_20 - mult*atr_14.
func CloseBelowLowerChannel(emaCol string, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		closeVal := bars[idx].Bar.Close
		ema, ok := getIndicator(bars, idx, emaCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return closeVal < ema-mult*atr
	}
}

// BBWidthIncreasing returns true when BB width at current bar exceeds BB width n bars ago.
func BBWidthIncreasing(n int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < n {
			return false
		}
		curr, ok := getIndicator(bars, idx, "bb_width")
		if !ok {
			return false
		}
		prev, ok := getIndicator(bars, idx-n, "bb_width")
		if !ok {
			return false
		}
		return curr > prev
	}
}

// RibbonCompressed returns true when |EMA20-EMA50| < mult*ATR for last lookback bars.
func RibbonCompressed(lookback int, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback-1 {
			return false
		}
		for i := idx - lookback + 1; i <= idx; i++ {
			ema20, ok := getIndicator(bars, i, "ema_20")
			if !ok {
				return false
			}
			ema50, ok := getIndicator(bars, i, "ema_50")
			if !ok {
				return false
			}
			atr, ok := getIndicator(bars, i, "atr_14")
			if !ok {
				return false
			}
			if math.Abs(ema20-ema50) >= mult*atr {
				return false
			}
		}
		return true
	}
}

// RibbonBreakLong returns true when ribbon is compressed AND close > max(EMA20,EMA50) + mult*ATR.
func RibbonBreakLong(lookback int, mult float64) types.ConditionFn {
	compressed := RibbonCompressed(lookback, mult)
	return func(bars []types.BarData, idx int) bool {
		if !compressed(bars, idx) {
			return false
		}
		closeVal := bars[idx].Bar.Close
		ema20, ok := getIndicator(bars, idx, "ema_20")
		if !ok {
			return false
		}
		ema50, ok := getIndicator(bars, idx, "ema_50")
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		upper := math.Max(ema20, ema50) + mult*atr
		return closeVal > upper
	}
}

// RibbonBreakShort returns true when ribbon is compressed AND close < min(EMA20,EMA50) - mult*ATR.
func RibbonBreakShort(lookback int, mult float64) types.ConditionFn {
	compressed := RibbonCompressed(lookback, mult)
	return func(bars []types.BarData, idx int) bool {
		if !compressed(bars, idx) {
			return false
		}
		closeVal := bars[idx].Bar.Close
		ema20, ok := getIndicator(bars, idx, "ema_20")
		if !ok {
			return false
		}
		ema50, ok := getIndicator(bars, idx, "ema_50")
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		lower := math.Min(ema20, ema50) - mult*atr
		return closeVal < lower
	}
}

// RibbonExitLong returns true when close < min(EMA20,EMA50) - mult*ATR.
func RibbonExitLong(mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		closeVal := bars[idx].Bar.Close
		ema20, ok := getIndicator(bars, idx, "ema_20")
		if !ok {
			return false
		}
		ema50, ok := getIndicator(bars, idx, "ema_50")
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		lower := math.Min(ema20, ema50) - mult*atr
		return closeVal < lower
	}
}

// RibbonExitShort returns true when close > max(EMA20,EMA50) + mult*ATR.
func RibbonExitShort(mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		closeVal := bars[idx].Bar.Close
		ema20, ok := getIndicator(bars, idx, "ema_20")
		if !ok {
			return false
		}
		ema50, ok := getIndicator(bars, idx, "ema_50")
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		upper := math.Max(ema20, ema50) + mult*atr
		return closeVal > upper
	}
}

// TRIXCrossesAboveSMA returns true when trix_15 crosses above its 9-period SMA.
func TRIXCrossesAboveSMA() types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 10 {
			return false
		}
		currTrix, ok := getIndicator(bars, idx, "trix_15")
		if !ok {
			return false
		}
		prevTrix, ok := getIndicator(bars, idx-1, "trix_15")
		if !ok {
			return false
		}
		currSMA := trixSMA(bars, idx, 9)
		prevSMA := trixSMA(bars, idx-1, 9)
		if math.IsNaN(currSMA) || math.IsNaN(prevSMA) {
			return false
		}
		return prevTrix <= prevSMA && currTrix > currSMA
	}
}

// TRIXCrossesBelowSMA returns true when trix_15 crosses below its 9-period SMA.
func TRIXCrossesBelowSMA() types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 10 {
			return false
		}
		currTrix, ok := getIndicator(bars, idx, "trix_15")
		if !ok {
			return false
		}
		prevTrix, ok := getIndicator(bars, idx-1, "trix_15")
		if !ok {
			return false
		}
		currSMA := trixSMA(bars, idx, 9)
		prevSMA := trixSMA(bars, idx-1, 9)
		if math.IsNaN(currSMA) || math.IsNaN(prevSMA) {
			return false
		}
		return prevTrix >= prevSMA && currTrix < currSMA
	}
}

// trixSMA computes the simple moving average of trix_15 at bar idx over period bars.
func trixSMA(bars []types.BarData, idx int, period int) float64 {
	if idx < period-1 {
		return math.NaN()
	}
	sum := 0.0
	for i := idx - period + 1; i <= idx; i++ {
		v, ok := getIndicator(bars, i, "trix_15")
		if !ok {
			return math.NaN()
		}
		sum += v
	}
	return sum / float64(period)
}

// BreaksAboveSMAEnvelope returns true when close breaks above SMA20 + mult*ATR.
func BreaksAboveSMAEnvelope(smaCol string, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		closeNow := bars[idx].Bar.Close
		closePrev := bars[idx-1].Bar.Close
		smaNow, ok := getIndicator(bars, idx, smaCol)
		if !ok {
			return false
		}
		smaPrev, ok := getIndicator(bars, idx-1, smaCol)
		if !ok {
			return false
		}
		atrNow, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		atrPrev, ok := getIndicator(bars, idx-1, "atr_14")
		if !ok {
			return false
		}
		upperNow := smaNow + mult*atrNow
		upperPrev := smaPrev + mult*atrPrev
		return closePrev <= upperPrev && closeNow > upperNow
	}
}

// BreaksBelowSMAEnvelope returns true when close breaks below SMA20 - mult*ATR.
func BreaksBelowSMAEnvelope(smaCol string, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < 1 {
			return false
		}
		closeNow := bars[idx].Bar.Close
		closePrev := bars[idx-1].Bar.Close
		smaNow, ok := getIndicator(bars, idx, smaCol)
		if !ok {
			return false
		}
		smaPrev, ok := getIndicator(bars, idx-1, smaCol)
		if !ok {
			return false
		}
		atrNow, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		atrPrev, ok := getIndicator(bars, idx-1, "atr_14")
		if !ok {
			return false
		}
		lowerNow := smaNow - mult*atrNow
		lowerPrev := smaPrev - mult*atrPrev
		return closePrev >= lowerPrev && closeNow < lowerNow
	}
}

// DoubleTapBelowBB returns true when at least 2 closes in last lookback bars were below BB lower.
func DoubleTapBelowBB(lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		count := 0
		for i := idx - lookback; i < idx; i++ {
			closeVal := bars[i].Bar.Close
			bbLow, ok := getIndicator(bars, i, "bb_lower")
			if !ok {
				continue
			}
			if closeVal < bbLow {
				count++
			}
		}
		return count >= 2
	}
}

// DoubleTapAboveBB returns true when at least 2 closes in last lookback bars were above BB upper.
func DoubleTapAboveBB(lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		count := 0
		for i := idx - lookback; i < idx; i++ {
			closeVal := bars[i].Bar.Close
			bbUp, ok := getIndicator(bars, i, "bb_upper")
			if !ok {
				continue
			}
			if closeVal > bbUp {
				count++
			}
		}
		return count >= 2
	}
}

// ADXInRange returns true when ADX is between low and high.
func ADXInRange(low, high float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		adx, ok := getIndicator(bars, idx, "adx_14")
		if !ok {
			return false
		}
		return adx >= low && adx <= high
	}
}

// ATRNotBottomPct returns true when ATR is not in the bottom pct percentile over lookback bars.
func ATRNotBottomPct(pct float64, lookback int) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		if idx < lookback {
			return false
		}
		atrNow, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		// Collect ATR values for percentile computation
		values := make([]float64, 0, lookback)
		for i := idx - lookback + 1; i <= idx; i++ {
			v, ok := getIndicator(bars, i, "atr_14")
			if ok {
				values = append(values, v)
			}
		}
		if len(values) < 20 {
			return false
		}
		// Simple percentile: count how many are below atrNow
		belowCount := 0
		for _, v := range values {
			if v < atrNow {
				belowCount++
			}
		}
		percentile := float64(belowCount) / float64(len(values)) * 100.0
		return percentile >= pct
	}
}

// FlatSlope returns true when abs(linearreg_slope_20) < epsilon.
func FlatSlope(col string, epsilon float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		slope, ok := getIndicator(bars, idx, col)
		if !ok {
			return false
		}
		return math.Abs(slope) < epsilon
	}
}

// ATRBelowContractedSMA returns true when ATR < factor * atr_sma_50.
func ATRBelowContractedSMA(factor float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		atrSMA, ok := getIndicator(bars, idx, "atr_sma_50")
		if !ok {
			return false
		}
		return atr < factor*atrSMA
	}
}

// MeanRevLong returns true when (refCol - close) > mult * ATR.
func MeanRevLong(refCol string, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		closeVal := bars[idx].Bar.Close
		ref, ok := getIndicator(bars, idx, refCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return (ref - closeVal) > mult*atr
	}
}

// MeanRevShort returns true when (close - refCol) > mult * ATR.
func MeanRevShort(refCol string, mult float64) types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		closeVal := bars[idx].Bar.Close
		ref, ok := getIndicator(bars, idx, refCol)
		if !ok {
			return false
		}
		atr, ok := getIndicator(bars, idx, "atr_14")
		if !ok {
			return false
		}
		return (closeVal - ref) > mult*atr
	}
}

// MajorityBull returns true when at least 2 of 3 signals are bullish:
// EMA20 > EMA50, RSI > 55, MACD hist > 0.
func MajorityBull() types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		ema20, ok := getIndicator(bars, idx, "ema_20")
		if !ok {
			return false
		}
		ema50, ok := getIndicator(bars, idx, "ema_50")
		if !ok {
			return false
		}
		rsi, ok := getIndicator(bars, idx, "rsi_14")
		if !ok {
			return false
		}
		hist, ok := getIndicator(bars, idx, "macd_hist")
		if !ok {
			return false
		}
		votes := 0
		if ema20 > ema50 {
			votes++
		}
		if rsi > 55 {
			votes++
		}
		if hist > 0 {
			votes++
		}
		return votes >= 2
	}
}

// MajorityBear returns true when at least 2 of 3 signals are bearish:
// EMA20 < EMA50, RSI < 45, MACD hist < 0.
func MajorityBear() types.ConditionFn {
	return func(bars []types.BarData, idx int) bool {
		ema20, ok := getIndicator(bars, idx, "ema_20")
		if !ok {
			return false
		}
		ema50, ok := getIndicator(bars, idx, "ema_50")
		if !ok {
			return false
		}
		rsi, ok := getIndicator(bars, idx, "rsi_14")
		if !ok {
			return false
		}
		hist, ok := getIndicator(bars, idx, "macd_hist")
		if !ok {
			return false
		}
		votes := 0
		if ema20 < ema50 {
			votes++
		}
		if rsi < 45 {
			votes++
		}
		if hist < 0 {
			votes++
		}
		return votes >= 2
	}
}
