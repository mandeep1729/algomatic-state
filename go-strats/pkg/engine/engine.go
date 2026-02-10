// Package engine implements the bar-by-bar probe engine for strategy backtesting.
//
// Produces normalized % P&L per trade for fair comparison across strategies.
// Mirrors Python src/strats_prob/engine.py ProbeEngine.
package engine

import (
	"fmt"
	"log/slog"
	"math"
	"strings"

	"github.com/algomatic/strats100/go-strats/pkg/exits"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// ProbeEngine runs a single strategy definition across a bar series.
type ProbeEngine struct {
	Strategy    *types.StrategyDef
	RiskProfile types.RiskProfile
	logger      *slog.Logger
}

// NewProbeEngine creates a new ProbeEngine for the given strategy and risk profile.
func NewProbeEngine(strategy *types.StrategyDef, riskProfile types.RiskProfile, logger *slog.Logger) *ProbeEngine {
	if logger == nil {
		logger = slog.Default()
	}
	logger.Info("ProbeEngine initialised",
		"strategy", strategy.DisplayName,
		"risk", riskProfile.Name,
	)
	return &ProbeEngine{
		Strategy:    strategy,
		RiskProfile: riskProfile,
		logger:      logger,
	}
}

// Run executes the strategy bar-by-bar on the given data.
//
// Uses fill-on-next-bar semantics: when a signal fires on bar i,
// entry_price = open of bar i+1.
//
// Open trades at end of data are discarded per requirements.
func (e *ProbeEngine) Run(bars []types.BarData) []types.Trade {
	if len(bars) == 0 {
		e.logger.Warn("Empty bar data passed to ProbeEngine.Run()")
		return nil
	}

	trades := make([]types.Trade, 0, 32)
	nBars := len(bars)

	// State: only one trade open at a time (no pyramiding)
	var (
		hasOpenTrade       bool
		position           types.Direction
		exitManager        *exits.ExitManager
		entryBarIdx        int
		entryPrice         float64
		entryJustification string
		pendingSignal      types.Direction // "" = no pending signal
	)

	for i := 0; i < nBars; i++ {
		bar := bars[i].Bar

		// Handle pending entry from previous bar's signal
		if pendingSignal != "" && !hasOpenTrade {
			atrVal := e.getATR(bars, i)
			if atrVal > 0 {
				position = pendingSignal
				hasOpenTrade = true
				entryPrice = bar.Open
				entryBarIdx = i
				exitManager = exits.NewExitManager(
					entryPrice, position, atrVal, e.Strategy, e.RiskProfile,
				)
				entryJustification = e.buildEntryJustification(
					position, entryPrice, atrVal, bars, i,
				)
				e.logger.Debug("Entered trade",
					"direction", position,
					"bar", i,
					"price", entryPrice,
					"atr", atrVal,
				)
			}
			pendingSignal = ""
			// Skip checking exits on entry bar
			continue
		}

		// If in a position, check exits
		if hasOpenTrade && exitManager != nil {
			exitReason := ""

			// Check signal-based exits first
			var signalExits []types.ConditionFn
			if position == types.Long {
				signalExits = e.Strategy.ExitLong
			} else {
				signalExits = e.Strategy.ExitShort
			}
			for _, cond := range signalExits {
				if e.safeCall(cond, bars, i) {
					exitReason = "signal_exit"
					break
				}
			}

			// Check mechanical exits
			if exitReason == "" {
				exitReason = exitManager.Check(bar.High, bar.Low, bar.Close)
			}

			if exitReason != "" {
				exitPrice := exits.GetExitPrice(
					exitReason, position, entryPrice, exitManager, bar.Close,
				)
				pnlPct := calcPnLPct(entryPrice, exitPrice, position)
				exitJustification := buildExitJustification(
					exitReason, position, entryPrice, exitPrice, exitManager, bar.Close,
				)

				trades = append(trades, types.Trade{
					EntryTime:          bars[entryBarIdx].Bar.Timestamp,
					ExitTime:           bar.Timestamp,
					EntryPrice:         entryPrice,
					ExitPrice:          exitPrice,
					Direction:          position,
					PnLPct:             pnlPct,
					BarsHeld:           exitManager.BarsHeld,
					MaxDrawdownPct:     exitManager.MaxDrawdownPct(),
					MaxProfitPct:       exitManager.MaxProfitPct(),
					PnLStd:             exitManager.PnLStd(),
					ExitReason:         exitReason,
					Quantity:           1,
					EntryJustification: entryJustification,
					ExitJustification:  exitJustification,
				})
				e.logger.Debug("Exited trade",
					"direction", position,
					"bar", i,
					"pnl_pct", pnlPct*100,
					"reason", exitReason,
				)

				// Reset state
				hasOpenTrade = false
				position = ""
				exitManager = nil
				entryBarIdx = 0
				entryPrice = 0
				entryJustification = ""
			}
		}

		// If flat, check entry signals (signal fires here, entry on next bar)
		if !hasOpenTrade && i < nBars-1 {
			// Check long entry
			if e.Strategy.Direction == types.LongShort || e.Strategy.Direction == types.LongOnly {
				if e.checkConditions(e.Strategy.EntryLong, bars, i) {
					pendingSignal = types.Long
					continue
				}
			}
			// Check short entry
			if e.Strategy.Direction == types.LongShort || e.Strategy.Direction == types.ShortOnly {
				if e.checkConditions(e.Strategy.EntryShort, bars, i) {
					pendingSignal = types.Short
					continue
				}
			}
		}
	}

	// Open trades at end of data are discarded
	if hasOpenTrade {
		e.logger.Debug("Discarding open trade at end of data", "direction", position)
	}

	return trades
}

// checkConditions checks if all conditions in the list are met.
func (e *ProbeEngine) checkConditions(conditions []types.ConditionFn, bars []types.BarData, idx int) bool {
	if len(conditions) == 0 {
		return false
	}
	for _, cond := range conditions {
		if !e.safeCall(cond, bars, idx) {
			return false
		}
	}
	return true
}

// safeCall calls a condition function with panic recovery.
func (e *ProbeEngine) safeCall(cond types.ConditionFn, bars []types.BarData, idx int) bool {
	defer func() {
		if r := recover(); r != nil {
			e.logger.Warn("Condition function panicked", "error", r, "bar", idx)
		}
	}()
	return cond(bars, idx)
}

// getATR safely retrieves the ATR value at bar idx.
func (e *ProbeEngine) getATR(bars []types.BarData, idx int) float64 {
	if idx < 0 || idx >= len(bars) {
		return 0
	}
	v, ok := bars[idx].Indicators.Get("atr_14")
	if !ok || v <= 0 {
		return 0
	}
	return v
}

// calcPnLPct calculates the normalized P&L percentage.
func calcPnLPct(entryPrice, exitPrice float64, direction types.Direction) float64 {
	if direction == types.Long {
		return (exitPrice - entryPrice) / entryPrice
	}
	return (entryPrice - exitPrice) / entryPrice
}

// buildEntryJustification builds a human-readable justification for a trade entry.
func (e *ProbeEngine) buildEntryJustification(
	direction types.Direction,
	entryPrice, atrVal float64,
	bars []types.BarData,
	idx int,
) string {
	parts := []string{
		fmt.Sprintf("Strategy '%s' %s entry", e.Strategy.DisplayName, direction),
		fmt.Sprintf("at %.4f", entryPrice),
		fmt.Sprintf("(ATR=%.4f, risk=%s)", atrVal, e.RiskProfile.Name),
	}

	// Append key indicator values if available
	var snapshots []string
	for _, col := range e.Strategy.RequiredIndicators {
		v, ok := bars[idx].Indicators.Get(col)
		if ok && !math.IsNaN(v) && !math.IsInf(v, 0) {
			snapshots = append(snapshots, fmt.Sprintf("%s=%.4f", col, v))
		}
		if len(snapshots) >= 6 {
			break
		}
	}
	if len(snapshots) > 0 {
		parts = append(parts, fmt.Sprintf("[%s]", strings.Join(snapshots, ", ")))
	}

	return strings.Join(parts, " ")
}

// buildExitJustification builds a human-readable justification for a trade exit.
func buildExitJustification(
	exitReason string,
	direction types.Direction,
	entryPrice, exitPrice float64,
	em *exits.ExitManager,
	closePrice float64,
) string {
	pnlPct := (exitPrice - entryPrice) / entryPrice * 100
	if direction == types.Short {
		pnlPct = (entryPrice - exitPrice) / entryPrice * 100
	}

	parts := []string{fmt.Sprintf("Exit reason: %s", exitReason)}

	switch exitReason {
	case "stop_loss":
		if em.StopDist > 0 {
			parts = append(parts, fmt.Sprintf(
				"stop distance=%.4f (%.1fx ATR)", em.StopDist, em.StopDist/em.ATR,
			))
		}
	case "target":
		if em.TargetDist > 0 {
			parts = append(parts, fmt.Sprintf(
				"target distance=%.4f (%.1fx ATR)", em.TargetDist, em.TargetDist/em.ATR,
			))
		}
	case "trailing_stop":
		parts = append(parts, fmt.Sprintf("trailing stop at %.4f", em.TrailingStopLevel()))
	case "time_stop":
		parts = append(parts, fmt.Sprintf("after %d bars (limit=%d)", em.BarsHeld, em.TimeLimit))
	case "signal_exit":
		parts = append(parts, fmt.Sprintf("signal-based exit at close=%.4f", closePrice))
	}

	parts = append(parts, fmt.Sprintf("exit_price=%.4f, pnl=%+.2f%%", exitPrice, pnlPct))
	return strings.Join(parts, "; ")
}
