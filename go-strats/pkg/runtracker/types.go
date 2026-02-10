// Package runtracker provides in-memory tracking of strategy probe run
// progress and status. It is designed to be queried by the monitoring API
// endpoints so dashboards can display live run progress, ETA, and per-strategy
// execution state.
package runtracker

import (
	"time"
)

// RunStatus represents the overall status of a strategy run.
type RunStatus string

const (
	StatusRunning   RunStatus = "running"
	StatusCompleted RunStatus = "completed"
	StatusFailed    RunStatus = "failed"
)

// StrategyStatus represents the execution status of an individual strategy
// within a run.
type StrategyStatus string

const (
	StrategyPending   StrategyStatus = "pending"
	StrategyRunning   StrategyStatus = "running"
	StrategyCompleted StrategyStatus = "completed"
	StrategyFailed    StrategyStatus = "failed"
)

// StrategyExecutionState tracks the execution status of a single strategy
// within a run.
type StrategyExecutionState struct {
	StrategyID   int            `json:"strategy_id"`
	StrategyName string         `json:"strategy_name"`
	Status       StrategyStatus `json:"status"`
	StartTime    *time.Time     `json:"start_time"`
	EndTime      *time.Time     `json:"end_time"`
	DurationSecs float64        `json:"duration_seconds"`
	TradesGen    int            `json:"trades_generated"`
	ErrorMessage string         `json:"error_message,omitempty"`
}

// StrategyRun tracks the overall state of a probe run (one symbol + timeframe
// combination across all requested strategies and risk profiles).
type StrategyRun struct {
	RunID        string         `json:"run_id"`
	Symbol       string         `json:"symbol"`
	Timeframe    string         `json:"timeframe"`
	RiskProfiles []string       `json:"risk_profiles"`
	StartTime    time.Time      `json:"start_time"`
	EndTime      *time.Time     `json:"end_time"`
	Status       RunStatus      `json:"status"`
	Strategies   []StrategyExecutionState `json:"strategies"`
}

// Counts returns the number of completed, running, pending, and failed
// strategies in this run.
func (r *StrategyRun) Counts() (completed, running, pending, failed int) {
	for i := range r.Strategies {
		switch r.Strategies[i].Status {
		case StrategyCompleted:
			completed++
		case StrategyRunning:
			running++
		case StrategyPending:
			pending++
		case StrategyFailed:
			failed++
		}
	}
	return
}

// TotalStrategies returns the total number of strategies in this run.
func (r *StrategyRun) TotalStrategies() int {
	return len(r.Strategies)
}

// TotalTradesGenerated returns the sum of trades generated across all
// strategies in this run.
func (r *StrategyRun) TotalTradesGenerated() int {
	total := 0
	for i := range r.Strategies {
		total += r.Strategies[i].TradesGen
	}
	return total
}

// ProgressPercent returns the completion percentage (0-100).
func (r *StrategyRun) ProgressPercent() int {
	total := r.TotalStrategies()
	if total == 0 {
		return 0
	}
	completed, _, _, _ := r.Counts()
	return completed * 100 / total
}

// ElapsedSeconds returns the number of seconds elapsed since the run started.
func (r *StrategyRun) ElapsedSeconds() float64 {
	if r.EndTime != nil {
		return r.EndTime.Sub(r.StartTime).Seconds()
	}
	return time.Since(r.StartTime).Seconds()
}

// EstimatedRemainingSeconds calculates the estimated remaining time based on
// average throughput of completed strategies.
func (r *StrategyRun) EstimatedRemainingSeconds() float64 {
	completed, running, pending, _ := r.Counts()
	done := completed
	if done == 0 {
		return 0
	}

	elapsed := r.ElapsedSeconds()
	avgPerStrategy := elapsed / float64(done)
	remaining := pending + running
	return avgPerStrategy * float64(remaining)
}

// ETACompletion returns the estimated time of completion, or nil if not
// calculable.
func (r *StrategyRun) ETACompletion() *time.Time {
	remaining := r.EstimatedRemainingSeconds()
	if remaining <= 0 {
		return nil
	}
	eta := time.Now().Add(time.Duration(remaining * float64(time.Second)))
	return &eta
}
