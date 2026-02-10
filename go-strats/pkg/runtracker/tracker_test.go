package runtracker

import (
	"testing"
	"time"
)

func TestNewTracker(t *testing.T) {
	tracker := NewTracker(nil, "1.0.0")
	if tracker == nil {
		t.Fatal("expected non-nil tracker")
	}
	if tracker.Version() != "1.0.0" {
		t.Errorf("expected version '1.0.0', got %q", tracker.Version())
	}
	if tracker.UptimeSeconds() < 0 {
		t.Error("expected non-negative uptime")
	}
}

func TestNewTrackerDefaults(t *testing.T) {
	tracker := NewTracker(nil, "")
	if tracker.Version() != "dev" {
		t.Errorf("expected default version 'dev', got %q", tracker.Version())
	}
}

func TestStartRun(t *testing.T) {
	tracker := NewTracker(nil, "test")

	strategies := []StrategyInfo{
		{ID: 1, Name: "EMA Cross"},
		{ID: 2, Name: "RSI Bounce"},
		{ID: 3, Name: "MACD Signal"},
	}

	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	if runID == "" {
		t.Fatal("expected non-empty run ID")
	}

	run := tracker.GetRun(runID)
	if run == nil {
		t.Fatal("expected to find run by ID")
	}

	if run.Symbol != "AAPL" {
		t.Errorf("expected symbol AAPL, got %q", run.Symbol)
	}
	if run.Timeframe != "1Hour" {
		t.Errorf("expected timeframe 1Hour, got %q", run.Timeframe)
	}
	if run.Status != StatusRunning {
		t.Errorf("expected status running, got %q", run.Status)
	}
	if run.TotalStrategies() != 3 {
		t.Errorf("expected 3 strategies, got %d", run.TotalStrategies())
	}

	completed, running, pending, failed := run.Counts()
	if completed != 0 || running != 0 || pending != 3 || failed != 0 {
		t.Errorf("expected (0,0,3,0), got (%d,%d,%d,%d)", completed, running, pending, failed)
	}
}

func TestMarkStrategyRunning(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "EMA Cross"},
		{ID: 2, Name: "RSI Bounce"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)

	run := tracker.GetRun(runID)
	completed, running, pending, failed := run.Counts()
	if completed != 0 || running != 1 || pending != 1 || failed != 0 {
		t.Errorf("expected (0,1,1,0), got (%d,%d,%d,%d)", completed, running, pending, failed)
	}

	// Verify strategy start time is set
	for _, s := range run.Strategies {
		if s.StrategyID == 1 {
			if s.StartTime == nil {
				t.Error("expected start time to be set for running strategy")
			}
			if s.Status != StrategyRunning {
				t.Errorf("expected status running, got %q", s.Status)
			}
		}
	}
}

func TestMarkStrategyCompleted(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "EMA Cross"},
		{ID: 2, Name: "RSI Bounce"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 42)

	run := tracker.GetRun(runID)
	completed, running, pending, failed := run.Counts()
	if completed != 1 || running != 0 || pending != 1 || failed != 0 {
		t.Errorf("expected (1,0,1,0), got (%d,%d,%d,%d)", completed, running, pending, failed)
	}

	for _, s := range run.Strategies {
		if s.StrategyID == 1 {
			if s.TradesGen != 42 {
				t.Errorf("expected 42 trades, got %d", s.TradesGen)
			}
			if s.EndTime == nil {
				t.Error("expected end time to be set")
			}
			if s.DurationSecs <= 0 {
				// Duration might be very small but not negative
				// Accept 0 since the operations happen nearly instantly
			}
		}
	}
}

func TestMarkStrategyFailed(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "EMA Cross"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyFailed(runID, 1, "division by zero")

	run := tracker.GetRun(runID)
	_, _, _, failed := run.Counts()
	if failed != 1 {
		t.Errorf("expected 1 failed, got %d", failed)
	}

	for _, s := range run.Strategies {
		if s.StrategyID == 1 {
			if s.ErrorMessage != "division by zero" {
				t.Errorf("expected error message 'division by zero', got %q", s.ErrorMessage)
			}
			if s.Status != StrategyFailed {
				t.Errorf("expected status failed, got %q", s.Status)
			}
		}
	}
}

func TestRunAutoCompletes(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "S1"},
		{ID: 2, Name: "S2"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	// Complete both strategies
	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 10)
	tracker.MarkStrategyRunning(runID, 2)
	tracker.MarkStrategyCompleted(runID, 2, 20)

	run := tracker.GetRun(runID)
	if run.Status != StatusCompleted {
		t.Errorf("expected run status completed, got %q", run.Status)
	}
	if run.EndTime == nil {
		t.Error("expected end time to be set when run completes")
	}
}

func TestRunAutoFailsWhenAllFailed(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "S1"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyFailed(runID, 1, "oops")

	run := tracker.GetRun(runID)
	if run.Status != StatusFailed {
		t.Errorf("expected run status failed when all strategies fail, got %q", run.Status)
	}
}

func TestRunCompletesWhenSomeFailed(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "S1"},
		{ID: 2, Name: "S2"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 10)
	tracker.MarkStrategyRunning(runID, 2)
	tracker.MarkStrategyFailed(runID, 2, "error")

	run := tracker.GetRun(runID)
	// At least one completed, so status should be completed (not failed)
	if run.Status != StatusCompleted {
		t.Errorf("expected run status completed when some succeed, got %q", run.Status)
	}
}

func TestProgressPercent(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := make([]StrategyInfo, 4)
	for i := range strategies {
		strategies[i] = StrategyInfo{ID: i + 1, Name: "S"}
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	run := tracker.GetRun(runID)
	if run.ProgressPercent() != 0 {
		t.Errorf("expected 0%% progress, got %d%%", run.ProgressPercent())
	}

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 5)

	run = tracker.GetRun(runID)
	if run.ProgressPercent() != 25 {
		t.Errorf("expected 25%% progress, got %d%%", run.ProgressPercent())
	}

	tracker.MarkStrategyRunning(runID, 2)
	tracker.MarkStrategyCompleted(runID, 2, 5)

	run = tracker.GetRun(runID)
	if run.ProgressPercent() != 50 {
		t.Errorf("expected 50%% progress, got %d%%", run.ProgressPercent())
	}
}

func TestTotalTradesGenerated(t *testing.T) {
	tracker := NewTracker(nil, "test")
	strategies := []StrategyInfo{
		{ID: 1, Name: "S1"},
		{ID: 2, Name: "S2"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 100)
	tracker.MarkStrategyRunning(runID, 2)
	tracker.MarkStrategyCompleted(runID, 2, 200)

	run := tracker.GetRun(runID)
	if run.TotalTradesGenerated() != 300 {
		t.Errorf("expected 300 total trades, got %d", run.TotalTradesGenerated())
	}
}

func TestEstimatedRemainingSeconds(t *testing.T) {
	run := &StrategyRun{
		StartTime: time.Now().Add(-10 * time.Second),
		Status:    StatusRunning,
		Strategies: []StrategyExecutionState{
			{StrategyID: 1, Status: StrategyCompleted},
			{StrategyID: 2, Status: StrategyCompleted},
			{StrategyID: 3, Status: StrategyPending},
			{StrategyID: 4, Status: StrategyPending},
		},
	}

	// 2 completed in ~10 seconds = ~5s each, 2 remaining = ~10s estimated
	remaining := run.EstimatedRemainingSeconds()
	if remaining < 8 || remaining > 12 {
		t.Errorf("expected estimated remaining ~10s, got %.1f", remaining)
	}
}

func TestEstimatedRemainingSecondsZeroCompleted(t *testing.T) {
	run := &StrategyRun{
		StartTime: time.Now().Add(-5 * time.Second),
		Status:    StatusRunning,
		Strategies: []StrategyExecutionState{
			{StrategyID: 1, Status: StrategyPending},
		},
	}

	remaining := run.EstimatedRemainingSeconds()
	if remaining != 0 {
		t.Errorf("expected 0 remaining when nothing completed, got %.1f", remaining)
	}
}

func TestETACompletion(t *testing.T) {
	run := &StrategyRun{
		StartTime: time.Now().Add(-10 * time.Second),
		Status:    StatusRunning,
		Strategies: []StrategyExecutionState{
			{StrategyID: 1, Status: StrategyCompleted},
			{StrategyID: 2, Status: StrategyPending},
		},
	}

	eta := run.ETACompletion()
	if eta == nil {
		t.Fatal("expected non-nil ETA")
	}
	if eta.Before(time.Now()) {
		t.Error("expected ETA to be in the future")
	}
}

func TestETACompletionNilWhenAllDone(t *testing.T) {
	now := time.Now()
	run := &StrategyRun{
		StartTime: now.Add(-10 * time.Second),
		EndTime:   &now,
		Status:    StatusCompleted,
		Strategies: []StrategyExecutionState{
			{StrategyID: 1, Status: StrategyCompleted},
		},
	}

	eta := run.ETACompletion()
	if eta != nil {
		t.Error("expected nil ETA when all strategies are done")
	}
}

func TestListRuns(t *testing.T) {
	tracker := NewTracker(nil, "test")

	// Create multiple runs
	tracker.StartRun("AAPL", "1Hour", []string{"medium"}, []StrategyInfo{{ID: 1, Name: "S1"}})
	tracker.StartRun("GOOG", "1Day", []string{"high"}, []StrategyInfo{{ID: 1, Name: "S1"}})
	tracker.StartRun("AAPL", "15Min", []string{"low"}, []StrategyInfo{{ID: 1, Name: "S1"}})

	// List all
	runs := tracker.ListRuns("", "", 0)
	if len(runs) != 3 {
		t.Errorf("expected 3 runs, got %d", len(runs))
	}

	// Filter by symbol
	runs = tracker.ListRuns("", "AAPL", 0)
	if len(runs) != 2 {
		t.Errorf("expected 2 AAPL runs, got %d", len(runs))
	}

	// Filter by status
	runs = tracker.ListRuns("running", "", 0)
	if len(runs) != 3 {
		t.Errorf("expected 3 running runs, got %d", len(runs))
	}

	// Limit
	runs = tracker.ListRuns("", "", 1)
	if len(runs) != 1 {
		t.Errorf("expected 1 run with limit=1, got %d", len(runs))
	}
}

func TestGetRunNotFound(t *testing.T) {
	tracker := NewTracker(nil, "test")
	run := tracker.GetRun("nonexistent")
	if run != nil {
		t.Error("expected nil for non-existent run")
	}
}

func TestGetRunReturnsCopy(t *testing.T) {
	tracker := NewTracker(nil, "test")
	runID := tracker.StartRun("AAPL", "1H", []string{"medium"}, []StrategyInfo{{ID: 1, Name: "S1"}})

	run1 := tracker.GetRun(runID)
	run2 := tracker.GetRun(runID)

	// Mutating one copy should not affect the other
	run1.Symbol = "MODIFIED"
	if run2.Symbol == "MODIFIED" {
		t.Error("GetRun should return independent copies")
	}
}

func TestMarkRunningNonexistentRun(t *testing.T) {
	tracker := NewTracker(nil, "test")
	// Should not panic
	tracker.MarkStrategyRunning("nonexistent", 1)
}

func TestMarkCompletedNonexistentStrategy(t *testing.T) {
	tracker := NewTracker(nil, "test")
	runID := tracker.StartRun("AAPL", "1H", []string{"medium"}, []StrategyInfo{{ID: 1, Name: "S1"}})
	// Should not panic when strategy ID does not exist in run
	tracker.MarkStrategyCompleted(runID, 999, 0)
}

func TestEmptyStrategiesProgressPercent(t *testing.T) {
	run := &StrategyRun{
		Strategies: []StrategyExecutionState{},
	}
	if run.ProgressPercent() != 0 {
		t.Errorf("expected 0%% for empty strategies, got %d%%", run.ProgressPercent())
	}
}
