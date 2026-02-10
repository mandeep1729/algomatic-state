// Package types defines core data structures for the strategy probe engine.
//
// These types map closely to the Python equivalents in src/strats_prob/:
//   - Bar = OHLCV row from ohlcv_bars table
//   - IndicatorRow = computed indicator values keyed by name
//   - Trade = result of a single simulated trade
//   - RiskProfile = scaling factors for exit parameters
package types

import (
	"fmt"
	"math"
	"time"
)

// Bar represents a single OHLCV bar.
type Bar struct {
	Timestamp time.Time
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
}

// IndicatorRow holds all computed indicator values for one bar, keyed by name.
// Missing indicators are represented by NaN values (math.NaN()).
type IndicatorRow map[string]float64

// Get returns the value for a given indicator key.
// Returns (value, true) if present and finite; (NaN, false) if missing or NaN.
func (r IndicatorRow) Get(key string) (float64, bool) {
	v, ok := r[key]
	if !ok || math.IsNaN(v) || math.IsInf(v, 0) {
		return math.NaN(), false
	}
	return v, true
}

// BarData combines a Bar with its corresponding indicator values.
// This is the primary input for condition functions.
type BarData struct {
	Bar        Bar
	Indicators IndicatorRow
}

// Direction represents trade direction.
type Direction string

const (
	Long  Direction = "long"
	Short Direction = "short"
)

// StrategyDirection controls which directions a strategy supports.
type StrategyDirection string

const (
	LongShort StrategyDirection = "long_short"
	LongOnly  StrategyDirection = "long_only"
	ShortOnly StrategyDirection = "short_only"
)

// Trade represents a completed simulated trade.
type Trade struct {
	EntryTime          time.Time
	ExitTime           time.Time
	EntryPrice         float64
	ExitPrice          float64
	Direction          Direction
	PnLPct             float64
	BarsHeld           int
	MaxDrawdownPct     float64
	MaxProfitPct       float64
	PnLStd             float64
	ExitReason         string
	Quantity           int
	EntryJustification string
	ExitJustification  string
}

// String returns a human-readable representation of the trade.
func (t Trade) String() string {
	return fmt.Sprintf(
		"%s %s entry=%.4f exit=%.4f pnl=%.4f%% bars=%d reason=%s",
		t.Direction, t.EntryTime.Format("2006-01-02 15:04"),
		t.EntryPrice, t.ExitPrice, t.PnLPct*100, t.BarsHeld, t.ExitReason,
	)
}

// RiskProfile controls how exit parameters are scaled.
// Matches Python RiskProfile: low/medium/high with different multipliers.
type RiskProfile struct {
	Name       string
	StopScale  float64
	TargetScale float64
	TrailScale float64
	TimeScale  float64
}

// Predefined risk profiles matching the Python implementation.
var (
	RiskLow = RiskProfile{
		Name:       "low",
		StopScale:  1.0,
		TargetScale: 1.0,
		TrailScale: 1.0,
		TimeScale:  0.6,
	}
	RiskMedium = RiskProfile{
		Name:       "medium",
		StopScale:  1.5,
		TargetScale: 1.5,
		TrailScale: 1.5,
		TimeScale:  1.0,
	}
	RiskHigh = RiskProfile{
		Name:       "high",
		StopScale:  2.0,
		TargetScale: 2.0,
		TrailScale: 2.0,
		TimeScale:  1.5,
	}
)

// RiskProfileByName returns the risk profile for a given name.
// Returns RiskMedium if the name is not recognized.
func RiskProfileByName(name string) RiskProfile {
	switch name {
	case "low":
		return RiskLow
	case "medium":
		return RiskMedium
	case "high":
		return RiskHigh
	default:
		return RiskMedium
	}
}

// ConditionFn is the signature for entry/exit condition checks.
// It receives the full slice of bar data and the current bar index,
// returning true if the condition is met.
type ConditionFn func(bars []BarData, idx int) bool

// StrategyDef defines a single probe strategy declaratively.
// This mirrors the Python StrategyDef dataclass.
type StrategyDef struct {
	ID          int
	Name        string
	DisplayName string
	Philosophy  string
	Category    string // trend, mean_reversion, breakout, volume_flow, pattern, regime
	Tags        []string
	Direction   StrategyDirection

	// Entry conditions: all must be true to trigger entry.
	EntryLong  []ConditionFn
	EntryShort []ConditionFn

	// Exit conditions (signal-based): any being true triggers exit.
	ExitLong  []ConditionFn
	ExitShort []ConditionFn

	// ATR-based exit multipliers. Zero means not used.
	ATRStopMult    float64
	ATRTargetMult  float64
	TrailingATRMult float64
	TimeStopBars   int // 0 means not used

	// Required indicator column names.
	RequiredIndicators []string
}

// HasATRStop returns true if the strategy uses an ATR-based stop loss.
func (s *StrategyDef) HasATRStop() bool {
	return s.ATRStopMult > 0
}

// HasATRTarget returns true if the strategy uses an ATR-based profit target.
func (s *StrategyDef) HasATRTarget() bool {
	return s.ATRTargetMult > 0
}

// HasTrailingStop returns true if the strategy uses a trailing stop.
func (s *StrategyDef) HasTrailingStop() bool {
	return s.TrailingATRMult > 0
}

// HasTimeStop returns true if the strategy uses a time-based stop.
func (s *StrategyDef) HasTimeStop() bool {
	return s.TimeStopBars > 0
}
