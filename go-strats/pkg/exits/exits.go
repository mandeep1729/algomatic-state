// Package exits implements exit management for the probe engine.
//
// Handles ATR-based stops, targets, trailing stops, and time stops
// with risk-profile scaling. Mirrors Python src/strats_prob/exits.py.
package exits

import (
	"math"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// ExitManager manages exit logic for a single trade.
// Initialized at entry with risk-profile-scaled parameters.
// Call Check() each bar to determine if the trade should be closed.
type ExitManager struct {
	EntryPrice  float64
	Direction   types.Direction
	ATR         float64 // ATR at entry
	RiskProfile types.RiskProfile

	// Scaled distances (0 means not used)
	StopDist   float64
	TargetDist float64
	TrailDist  float64
	TimeLimit  int // 0 means not used

	// Tracking
	BarsHeld     int
	BestPrice    float64
	WorstPrice   float64
	trailingStop float64
	hasTrail     bool
	barPnLs      []float64
}

// NewExitManager creates a new ExitManager for a trade entry.
func NewExitManager(
	entryPrice float64,
	direction types.Direction,
	atrAtEntry float64,
	strategy *types.StrategyDef,
	riskProfile types.RiskProfile,
) *ExitManager {
	em := &ExitManager{
		EntryPrice:  entryPrice,
		Direction:   direction,
		ATR:         atrAtEntry,
		RiskProfile: riskProfile,
		BestPrice:   entryPrice,
		WorstPrice:  entryPrice,
		barPnLs:     make([]float64, 0, 64),
	}

	// Scale multipliers by risk profile
	if strategy.ATRStopMult > 0 {
		em.StopDist = strategy.ATRStopMult * riskProfile.StopScale * atrAtEntry
	}
	if strategy.ATRTargetMult > 0 {
		em.TargetDist = strategy.ATRTargetMult * riskProfile.TargetScale * atrAtEntry
	}
	if strategy.TrailingATRMult > 0 {
		em.TrailDist = strategy.TrailingATRMult * riskProfile.TrailScale * atrAtEntry
		em.hasTrail = true
		if direction == types.Long {
			em.trailingStop = entryPrice - em.TrailDist
		} else {
			em.trailingStop = entryPrice + em.TrailDist
		}
	}
	if strategy.TimeStopBars > 0 {
		em.TimeLimit = int(float64(strategy.TimeStopBars) * riskProfile.TimeScale)
	}

	return em
}

// Check evaluates whether any exit condition is met for the current bar.
// Returns the exit reason string, or empty string if no exit triggered.
func (em *ExitManager) Check(high, low, closePrice float64) string {
	em.BarsHeld++

	// Update MFE/MAE tracking
	if em.Direction == types.Long {
		em.BestPrice = math.Max(em.BestPrice, high)
		em.WorstPrice = math.Min(em.WorstPrice, low)
	} else {
		em.BestPrice = math.Min(em.BestPrice, low)
		em.WorstPrice = math.Max(em.WorstPrice, high)
	}

	// Track bar-by-bar P&L % for pnl_std computation
	var barPnL float64
	if em.Direction == types.Long {
		barPnL = (closePrice - em.EntryPrice) / em.EntryPrice
	} else {
		barPnL = (em.EntryPrice - closePrice) / em.EntryPrice
	}
	em.barPnLs = append(em.barPnLs, barPnL)

	// 1. Fixed stop loss
	if em.StopDist > 0 {
		if em.Direction == types.Long {
			stopLevel := em.EntryPrice - em.StopDist
			if low <= stopLevel {
				return "stop_loss"
			}
		} else {
			stopLevel := em.EntryPrice + em.StopDist
			if high >= stopLevel {
				return "stop_loss"
			}
		}
	}

	// 2. Fixed target
	if em.TargetDist > 0 {
		if em.Direction == types.Long {
			targetLevel := em.EntryPrice + em.TargetDist
			if high >= targetLevel {
				return "target"
			}
		} else {
			targetLevel := em.EntryPrice - em.TargetDist
			if low <= targetLevel {
				return "target"
			}
		}
	}

	// 3. Trailing stop
	if em.hasTrail {
		if em.Direction == types.Long {
			newTrail := high - em.TrailDist
			if newTrail > em.trailingStop {
				em.trailingStop = newTrail
			}
			if low <= em.trailingStop {
				return "trailing_stop"
			}
		} else {
			newTrail := low + em.TrailDist
			if newTrail < em.trailingStop {
				em.trailingStop = newTrail
			}
			if high >= em.trailingStop {
				return "trailing_stop"
			}
		}
	}

	// 4. Time stop
	if em.TimeLimit > 0 && em.BarsHeld >= em.TimeLimit {
		return "time_stop"
	}

	return ""
}

// MaxDrawdownPct returns the maximum adverse excursion as a percentage of entry price.
func (em *ExitManager) MaxDrawdownPct() float64 {
	if em.Direction == types.Long {
		return (em.EntryPrice - em.WorstPrice) / em.EntryPrice
	}
	return (em.WorstPrice - em.EntryPrice) / em.EntryPrice
}

// MaxProfitPct returns the maximum favorable excursion as a percentage of entry price.
func (em *ExitManager) MaxProfitPct() float64 {
	if em.Direction == types.Long {
		return (em.BestPrice - em.EntryPrice) / em.EntryPrice
	}
	return (em.EntryPrice - em.BestPrice) / em.EntryPrice
}

// PnLStd returns the standard deviation of bar-by-bar P&L % during the hold period.
func (em *ExitManager) PnLStd() float64 {
	if len(em.barPnLs) < 2 {
		return 0.0
	}
	// Compute mean
	sum := 0.0
	for _, v := range em.barPnLs {
		sum += v
	}
	mean := sum / float64(len(em.barPnLs))
	// Compute variance (population std, ddof=0)
	varSum := 0.0
	for _, v := range em.barPnLs {
		diff := v - mean
		varSum += diff * diff
	}
	return math.Sqrt(varSum / float64(len(em.barPnLs)))
}

// TrailingStopLevel returns the current trailing stop level.
func (em *ExitManager) TrailingStopLevel() float64 {
	return em.trailingStop
}

// GetExitPrice determines the exit price based on the exit reason.
func GetExitPrice(
	exitReason string,
	direction types.Direction,
	entryPrice float64,
	em *ExitManager,
	closePrice float64,
) float64 {
	switch exitReason {
	case "stop_loss":
		if em.StopDist > 0 {
			if direction == types.Long {
				return entryPrice - em.StopDist
			}
			return entryPrice + em.StopDist
		}
	case "target":
		if em.TargetDist > 0 {
			if direction == types.Long {
				return entryPrice + em.TargetDist
			}
			return entryPrice - em.TargetDist
		}
	case "trailing_stop":
		if em.hasTrail {
			return em.trailingStop
		}
	}
	// Signal exit, time stop, or unknown: exit at close
	return closePrice
}
