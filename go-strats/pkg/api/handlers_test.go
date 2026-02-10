package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/algomatic/strats100/go-strats/pkg/runtracker"
)

func newTestServer(t *testing.T) (*Server, *runtracker.Tracker) {
	t.Helper()
	tracker := runtracker.NewTracker(nil, "test-v1")
	server := NewServer(tracker, nil)
	server.BackendConnected = true
	return server, tracker
}

func TestHandleStatus(t *testing.T) {
	srv, _ := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/status", nil)
	w := httptest.NewRecorder()

	srv.HandleStatus(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp statusResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Status != "healthy" {
		t.Errorf("expected status 'healthy', got %q", resp.Status)
	}
	if resp.Version != "test-v1" {
		t.Errorf("expected version 'test-v1', got %q", resp.Version)
	}
	if !resp.BackendConnected {
		t.Error("expected backend_connected to be true")
	}
	if resp.UptimeSeconds < 0 {
		t.Error("expected non-negative uptime")
	}
}

func TestHandleListRunsEmpty(t *testing.T) {
	srv, _ := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs", nil)
	w := httptest.NewRecorder()

	srv.HandleListRuns(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp runListResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.TotalRuns != 0 {
		t.Errorf("expected 0 runs, got %d", resp.TotalRuns)
	}
	if len(resp.Runs) != 0 {
		t.Errorf("expected empty runs array, got %d", len(resp.Runs))
	}
}

func TestHandleListRunsWithData(t *testing.T) {
	srv, tracker := newTestServer(t)

	strategies := []runtracker.StrategyInfo{
		{ID: 1, Name: "S1"},
		{ID: 2, Name: "S2"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium"}, strategies)
	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 50)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs", nil)
	w := httptest.NewRecorder()

	srv.HandleListRuns(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp runListResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.TotalRuns != 1 {
		t.Fatalf("expected 1 run, got %d", resp.TotalRuns)
	}

	run := resp.Runs[0]
	if run.Symbol != "AAPL" {
		t.Errorf("expected symbol AAPL, got %q", run.Symbol)
	}
	if run.TotalStrategies != 2 {
		t.Errorf("expected 2 strategies, got %d", run.TotalStrategies)
	}
	if run.CompletedStrategies != 1 {
		t.Errorf("expected 1 completed, got %d", run.CompletedStrategies)
	}
	if run.PendingStrategies != 1 {
		t.Errorf("expected 1 pending, got %d", run.PendingStrategies)
	}
	if run.ProgressPercent != 50 {
		t.Errorf("expected 50%% progress, got %d%%", run.ProgressPercent)
	}
}

func TestHandleListRunsWithFilter(t *testing.T) {
	srv, tracker := newTestServer(t)

	tracker.StartRun("AAPL", "1H", []string{"medium"}, []runtracker.StrategyInfo{{ID: 1, Name: "S1"}})
	tracker.StartRun("GOOG", "1D", []string{"high"}, []runtracker.StrategyInfo{{ID: 1, Name: "S1"}})

	// Filter by symbol
	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs?symbol=GOOG", nil)
	w := httptest.NewRecorder()

	srv.HandleListRuns(w, req)

	var resp runListResponse
	json.NewDecoder(w.Body).Decode(&resp)

	if resp.TotalRuns != 1 {
		t.Errorf("expected 1 GOOG run, got %d", resp.TotalRuns)
	}
	if len(resp.Runs) > 0 && resp.Runs[0].Symbol != "GOOG" {
		t.Errorf("expected GOOG, got %q", resp.Runs[0].Symbol)
	}
}

func TestHandleListRunsWithLimit(t *testing.T) {
	srv, tracker := newTestServer(t)

	for i := 0; i < 5; i++ {
		tracker.StartRun("AAPL", "1H", []string{"medium"}, []runtracker.StrategyInfo{{ID: 1, Name: "S1"}})
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs?limit=2", nil)
	w := httptest.NewRecorder()

	srv.HandleListRuns(w, req)

	var resp runListResponse
	json.NewDecoder(w.Body).Decode(&resp)

	if resp.TotalRuns != 2 {
		t.Errorf("expected 2 runs with limit=2, got %d", resp.TotalRuns)
	}
}

func TestHandleGetRunNotFound(t *testing.T) {
	srv, _ := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs/nonexistent", nil)
	req.SetPathValue("run_id", "nonexistent")
	w := httptest.NewRecorder()

	srv.HandleGetRun(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected status 404, got %d", w.Code)
	}

	var resp errorResponse
	json.NewDecoder(w.Body).Decode(&resp)

	if resp.Error != "run not found" {
		t.Errorf("expected 'run not found', got %q", resp.Error)
	}
}

func TestHandleGetRunDetailed(t *testing.T) {
	srv, tracker := newTestServer(t)

	strategies := []runtracker.StrategyInfo{
		{ID: 1, Name: "EMA Cross"},
		{ID: 2, Name: "RSI Bounce"},
		{ID: 3, Name: "MACD Signal"},
	}
	runID := tracker.StartRun("AAPL", "1Hour", []string{"medium", "high"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 100)
	tracker.MarkStrategyRunning(runID, 2)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs/"+runID, nil)
	req.SetPathValue("run_id", runID)
	w := httptest.NewRecorder()

	srv.HandleGetRun(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp runDetailResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.RunID != runID {
		t.Errorf("expected run_id %q, got %q", runID, resp.RunID)
	}
	if resp.Symbol != "AAPL" {
		t.Errorf("expected symbol AAPL, got %q", resp.Symbol)
	}
	if len(resp.RiskProfiles) != 2 {
		t.Errorf("expected 2 risk profiles, got %d", len(resp.RiskProfiles))
	}
	if resp.TotalStrategies != 3 {
		t.Errorf("expected 3 total strategies, got %d", resp.TotalStrategies)
	}
	if resp.CompletedStrategies != 1 {
		t.Errorf("expected 1 completed, got %d", resp.CompletedStrategies)
	}
	if len(resp.Strategies) != 3 {
		t.Fatalf("expected 3 strategy items, got %d", len(resp.Strategies))
	}

	// Verify individual strategy states
	for _, s := range resp.Strategies {
		switch s.StrategyID {
		case 1:
			if s.Status != "completed" {
				t.Errorf("strategy 1: expected completed, got %q", s.Status)
			}
			if s.TradesGen != 100 {
				t.Errorf("strategy 1: expected 100 trades, got %d", s.TradesGen)
			}
		case 2:
			if s.Status != "running" {
				t.Errorf("strategy 2: expected running, got %q", s.Status)
			}
		case 3:
			if s.Status != "pending" {
				t.Errorf("strategy 3: expected pending, got %q", s.Status)
			}
		}
	}
}

func TestHandleGetRunSummaryNotFound(t *testing.T) {
	srv, _ := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs/nonexistent/summary", nil)
	req.SetPathValue("run_id", "nonexistent")
	w := httptest.NewRecorder()

	srv.HandleGetRunSummary(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected status 404, got %d", w.Code)
	}
}

func TestHandleGetRunSummary(t *testing.T) {
	srv, tracker := newTestServer(t)

	strategies := []runtracker.StrategyInfo{
		{ID: 1, Name: "S1"},
		{ID: 2, Name: "S2"},
		{ID: 3, Name: "S3"},
		{ID: 4, Name: "S4"},
	}
	runID := tracker.StartRun("AAPL", "1Day", []string{"low"}, strategies)

	tracker.MarkStrategyRunning(runID, 1)
	tracker.MarkStrategyCompleted(runID, 1, 50)
	tracker.MarkStrategyRunning(runID, 2)
	tracker.MarkStrategyCompleted(runID, 2, 30)
	tracker.MarkStrategyRunning(runID, 3)
	tracker.MarkStrategyFailed(runID, 3, "timeout")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs/"+runID+"/summary", nil)
	req.SetPathValue("run_id", runID)
	w := httptest.NewRecorder()

	srv.HandleGetRunSummary(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp runSummaryResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.TotalStrategies != 4 {
		t.Errorf("expected 4 total strategies, got %d", resp.TotalStrategies)
	}
	if resp.Completed.Count != 2 {
		t.Errorf("expected 2 completed, got %d", resp.Completed.Count)
	}
	if resp.Failed.Count != 1 {
		t.Errorf("expected 1 failed, got %d", resp.Failed.Count)
	}
	if resp.Pending.Count != 1 {
		t.Errorf("expected 1 pending, got %d", resp.Pending.Count)
	}
	if resp.TotalTradesGenerated != 80 {
		t.Errorf("expected 80 total trades, got %d", resp.TotalTradesGenerated)
	}
	if resp.AvgTradesPerStrategy != 40.0 {
		t.Errorf("expected avg 40 trades/strategy, got %.2f", resp.AvgTradesPerStrategy)
	}
	if resp.ElapsedTimeSeconds < 0 {
		t.Error("expected non-negative elapsed time")
	}
}

func TestHandleGetRunEmptyRunID(t *testing.T) {
	srv, _ := newTestServer(t)

	// PathValue returns "" for missing path parameter
	req := httptest.NewRequest(http.MethodGet, "/api/v1/runs/", nil)
	req.SetPathValue("run_id", "")
	w := httptest.NewRecorder()

	srv.HandleGetRun(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestExtractRunID(t *testing.T) {
	tests := []struct {
		path     string
		expected string
	}{
		{"/api/v1/runs/abc123", "abc123"},
		{"/api/v1/runs/abc123/summary", "abc123"},
		{"/api/v1/runs/", ""},
		{"/api/v1/status", ""},
		{"/other/path", ""},
	}

	for _, tc := range tests {
		result := ExtractRunID(tc.path)
		if result != tc.expected {
			t.Errorf("ExtractRunID(%q) = %q, want %q", tc.path, result, tc.expected)
		}
	}
}

func TestContentTypeJSON(t *testing.T) {
	srv, _ := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/status", nil)
	w := httptest.NewRecorder()

	srv.HandleStatus(w, req)

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type 'application/json', got %q", ct)
	}
}

func TestRouteRegistration(t *testing.T) {
	srv, _ := newTestServer(t)
	mux := http.NewServeMux()
	srv.RegisterRoutes(mux)

	// Verify status endpoint works through mux
	req := httptest.NewRequest(http.MethodGet, "/api/v1/status", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200 from mux, got %d", w.Code)
	}
}
