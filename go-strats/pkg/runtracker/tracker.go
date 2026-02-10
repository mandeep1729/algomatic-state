package runtracker

import (
	"crypto/rand"
	"fmt"
	"log/slog"
	"sync"
	"time"
)

// Tracker provides thread-safe management of strategy run state.
// It is the central store queried by the monitoring API endpoints.
type Tracker struct {
	mu     sync.RWMutex
	runs   map[string]*StrategyRun
	logger *slog.Logger

	// startedAt is used by the health endpoint to report uptime.
	startedAt time.Time
	version   string
}

// NewTracker creates a new run tracker.
func NewTracker(logger *slog.Logger, version string) *Tracker {
	if logger == nil {
		logger = slog.Default()
	}
	if version == "" {
		version = "dev"
	}
	return &Tracker{
		runs:      make(map[string]*StrategyRun),
		logger:    logger,
		startedAt: time.Now(),
		version:   version,
	}
}

// StartedAt returns the time the tracker was created.
func (t *Tracker) StartedAt() time.Time {
	return t.startedAt
}

// Version returns the version string.
func (t *Tracker) Version() string {
	return t.version
}

// UptimeSeconds returns seconds since the tracker was created.
func (t *Tracker) UptimeSeconds() float64 {
	return time.Since(t.startedAt).Seconds()
}

// generateRunID produces a short random hex run identifier.
func generateRunID() string {
	b := make([]byte, 5)
	_, _ = rand.Read(b)
	return fmt.Sprintf("%x", b)
}

// StartRun creates a new StrategyRun and returns its run_id.
// strategies is a list of (id, name) pairs for each strategy in the run.
func (t *Tracker) StartRun(
	symbol, timeframe string,
	riskProfiles []string,
	strategies []StrategyInfo,
) string {
	runID := generateRunID()
	now := time.Now()

	execStates := make([]StrategyExecutionState, len(strategies))
	for i, s := range strategies {
		execStates[i] = StrategyExecutionState{
			StrategyID:   s.ID,
			StrategyName: s.Name,
			Status:       StrategyPending,
		}
	}

	run := &StrategyRun{
		RunID:        runID,
		Symbol:       symbol,
		Timeframe:    timeframe,
		RiskProfiles: riskProfiles,
		StartTime:    now,
		Status:       StatusRunning,
		Strategies:   execStates,
	}

	t.mu.Lock()
	t.runs[runID] = run
	t.mu.Unlock()

	t.logger.Info("Run started",
		"run_id", runID,
		"symbol", symbol,
		"timeframe", timeframe,
		"strategies", len(strategies),
	)
	return runID
}

// StrategyInfo holds the minimal info needed to register a strategy in a run.
type StrategyInfo struct {
	ID   int
	Name string
}

// MarkStrategyRunning marks a strategy as running within a given run.
func (t *Tracker) MarkStrategyRunning(runID string, strategyID int) {
	t.mu.Lock()
	defer t.mu.Unlock()

	run, ok := t.runs[runID]
	if !ok {
		t.logger.Warn("MarkStrategyRunning: run not found", "run_id", runID)
		return
	}

	for i := range run.Strategies {
		if run.Strategies[i].StrategyID == strategyID {
			now := time.Now()
			run.Strategies[i].Status = StrategyRunning
			run.Strategies[i].StartTime = &now
			t.logger.Debug("Strategy marked running",
				"run_id", runID,
				"strategy_id", strategyID,
				"strategy_name", run.Strategies[i].StrategyName,
			)
			return
		}
	}
	t.logger.Warn("MarkStrategyRunning: strategy not found in run",
		"run_id", runID, "strategy_id", strategyID,
	)
}

// MarkStrategyCompleted marks a strategy as completed, recording trade count
// and duration.
func (t *Tracker) MarkStrategyCompleted(runID string, strategyID int, tradesGenerated int) {
	t.mu.Lock()
	defer t.mu.Unlock()

	run, ok := t.runs[runID]
	if !ok {
		t.logger.Warn("MarkStrategyCompleted: run not found", "run_id", runID)
		return
	}

	for i := range run.Strategies {
		if run.Strategies[i].StrategyID == strategyID {
			now := time.Now()
			run.Strategies[i].Status = StrategyCompleted
			run.Strategies[i].EndTime = &now
			run.Strategies[i].TradesGen = tradesGenerated
			if run.Strategies[i].StartTime != nil {
				run.Strategies[i].DurationSecs = now.Sub(*run.Strategies[i].StartTime).Seconds()
			}
			t.logger.Debug("Strategy completed",
				"run_id", runID,
				"strategy_id", strategyID,
				"trades", tradesGenerated,
				"duration_secs", run.Strategies[i].DurationSecs,
			)
			t.maybeFinishRunLocked(run)
			return
		}
	}
}

// MarkStrategyFailed marks a strategy as failed with an error message.
func (t *Tracker) MarkStrategyFailed(runID string, strategyID int, errMsg string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	run, ok := t.runs[runID]
	if !ok {
		t.logger.Warn("MarkStrategyFailed: run not found", "run_id", runID)
		return
	}

	for i := range run.Strategies {
		if run.Strategies[i].StrategyID == strategyID {
			now := time.Now()
			run.Strategies[i].Status = StrategyFailed
			run.Strategies[i].EndTime = &now
			run.Strategies[i].ErrorMessage = errMsg
			if run.Strategies[i].StartTime != nil {
				run.Strategies[i].DurationSecs = now.Sub(*run.Strategies[i].StartTime).Seconds()
			}
			t.logger.Warn("Strategy failed",
				"run_id", runID,
				"strategy_id", strategyID,
				"error", errMsg,
			)
			t.maybeFinishRunLocked(run)
			return
		}
	}
}

// maybeFinishRunLocked checks whether all strategies are done and finalises
// the run. Must be called with t.mu held.
func (t *Tracker) maybeFinishRunLocked(run *StrategyRun) {
	completed, running, pending, failed := run.Counts()
	if running > 0 || pending > 0 {
		return
	}
	now := time.Now()
	run.EndTime = &now
	if failed > 0 && completed == 0 {
		run.Status = StatusFailed
	} else {
		run.Status = StatusCompleted
	}
	t.logger.Info("Run finished",
		"run_id", run.RunID,
		"status", run.Status,
		"completed", completed,
		"failed", failed,
		"elapsed_secs", run.ElapsedSeconds(),
	)
}

// GetRun returns a snapshot of the run with the given ID, or nil if not found.
func (t *Tracker) GetRun(runID string) *StrategyRun {
	t.mu.RLock()
	defer t.mu.RUnlock()
	run, ok := t.runs[runID]
	if !ok {
		return nil
	}
	// Return a copy to avoid data races on the caller side.
	cp := *run
	cp.Strategies = make([]StrategyExecutionState, len(run.Strategies))
	copy(cp.Strategies, run.Strategies)
	return &cp
}

// ListRuns returns a snapshot of all runs. Optional filters can narrow the
// results by status and/or symbol.
func (t *Tracker) ListRuns(statusFilter string, symbolFilter string, limit int) []*StrategyRun {
	t.mu.RLock()
	defer t.mu.RUnlock()

	result := make([]*StrategyRun, 0, len(t.runs))
	for _, run := range t.runs {
		if statusFilter != "" && string(run.Status) != statusFilter {
			continue
		}
		if symbolFilter != "" && run.Symbol != symbolFilter {
			continue
		}
		cp := *run
		cp.Strategies = make([]StrategyExecutionState, len(run.Strategies))
		copy(cp.Strategies, run.Strategies)
		result = append(result, &cp)
	}

	// Sort by start time descending (newest first).
	for i := 0; i < len(result); i++ {
		for j := i + 1; j < len(result); j++ {
			if result[j].StartTime.After(result[i].StartTime) {
				result[i], result[j] = result[j], result[i]
			}
		}
	}

	if limit > 0 && len(result) > limit {
		result = result[:limit]
	}
	return result
}
