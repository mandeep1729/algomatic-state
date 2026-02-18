package runner

import (
	"log/slog"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// Signal represents the result of signal evaluation.
type Signal struct {
	Direction types.Direction // "long" or "short"
	Action    string         // "entry_long", "entry_short", "exit_long", "exit_short"
}

// PositionState tracks the agent's current position.
type PositionState struct {
	Direction  types.Direction `json:"direction"`
	Qty        float64         `json:"qty"`
	EntryPrice float64         `json:"entry_price"`
	EntryTime  string          `json:"entry_time"`
	OrderID    string          `json:"order_id"`
}

// evaluateSignal checks entry/exit conditions at the latest bar.
// If in position: any exit condition triggers exit.
// If flat: all entry conditions must be true for entry.
func evaluateSignal(
	barData []types.BarData,
	stratDef *types.StrategyDef,
	position *PositionState,
	logger *slog.Logger,
) *Signal {
	if len(barData) < 2 {
		logger.Debug("Not enough bar data for signal evaluation", "bars", len(barData))
		return nil
	}

	idx := len(barData) - 1

	// If in position, check exit conditions
	if position != nil {
		if position.Direction == types.Long && len(stratDef.ExitLong) > 0 {
			for _, cond := range stratDef.ExitLong {
				if safeCall(cond, barData, idx, logger) {
					logger.Info("Exit long signal triggered", "bar_idx", idx)
					return &Signal{Direction: types.Long, Action: "exit_long"}
				}
			}
		}
		if position.Direction == types.Short && len(stratDef.ExitShort) > 0 {
			for _, cond := range stratDef.ExitShort {
				if safeCall(cond, barData, idx, logger) {
					logger.Info("Exit short signal triggered", "bar_idx", idx)
					return &Signal{Direction: types.Short, Action: "exit_short"}
				}
			}
		}
		return nil
	}

	// If flat, check entry conditions (all must be true)
	if stratDef.Direction != types.ShortOnly && len(stratDef.EntryLong) > 0 {
		allTrue := true
		for _, cond := range stratDef.EntryLong {
			if !safeCall(cond, barData, idx, logger) {
				allTrue = false
				break
			}
		}
		if allTrue {
			logger.Info("Entry long signal triggered", "bar_idx", idx)
			return &Signal{Direction: types.Long, Action: "entry_long"}
		}
	}

	if stratDef.Direction != types.LongOnly && len(stratDef.EntryShort) > 0 {
		allTrue := true
		for _, cond := range stratDef.EntryShort {
			if !safeCall(cond, barData, idx, logger) {
				allTrue = false
				break
			}
		}
		if allTrue {
			logger.Info("Entry short signal triggered", "bar_idx", idx)
			return &Signal{Direction: types.Short, Action: "entry_short"}
		}
	}

	return nil
}

// safeCall wraps a condition function in a recover() for robustness.
func safeCall(fn types.ConditionFn, bars []types.BarData, idx int, logger *slog.Logger) (result bool) {
	defer func() {
		if r := recover(); r != nil {
			logger.Warn("Condition function panicked", "panic", r, "idx", idx)
			result = false
		}
	}()
	return fn(bars, idx)
}
