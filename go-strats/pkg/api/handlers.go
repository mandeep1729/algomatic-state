// Package api provides HTTP handlers for the strategy probe monitoring API.
//
// Endpoints:
//
//	GET /api/v1/status           - Service health check
//	GET /api/v1/runs             - List all runs (with optional filters)
//	GET /api/v1/runs/{run_id}    - Detailed run status
//	GET /api/v1/runs/{run_id}/summary - High-level run summary
package api

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/runtracker"
)

// Server holds dependencies for the API handlers.
type Server struct {
	Tracker        *runtracker.Tracker
	BackendConnected bool
	Logger         *slog.Logger
}

// NewServer creates a new API server.
func NewServer(tracker *runtracker.Tracker, logger *slog.Logger) *Server {
	if logger == nil {
		logger = slog.Default()
	}
	return &Server{
		Tracker: tracker,
		Logger:  logger,
	}
}

// RegisterRoutes registers all API routes on the provided mux.
func (s *Server) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/status", s.HandleStatus)
	mux.HandleFunc("GET /api/v1/runs", s.HandleListRuns)
	// Go 1.22+ pattern matching with path parameters
	mux.HandleFunc("GET /api/v1/runs/{run_id}/summary", s.HandleGetRunSummary)
	mux.HandleFunc("GET /api/v1/runs/{run_id}", s.HandleGetRun)
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

type statusResponse struct {
	Status           string  `json:"status"`
	UptimeSeconds    float64 `json:"uptime_seconds"`
	Version          string  `json:"version"`
	BackendConnected bool    `json:"backend_connected"`
}

type runListItem struct {
	RunID                    string  `json:"run_id"`
	Symbol                   string  `json:"symbol"`
	Timeframe                string  `json:"timeframe"`
	StartTime                string  `json:"start_time"`
	EndTime                  *string `json:"end_time"`
	Status                   string  `json:"status"`
	TotalStrategies          int     `json:"total_strategies"`
	CompletedStrategies      int     `json:"completed_strategies"`
	PendingStrategies        int     `json:"pending_strategies"`
	FailedStrategies         int     `json:"failed_strategies"`
	ProgressPercent          int     `json:"progress_percent"`
	ElapsedTimeSeconds       float64 `json:"elapsed_time_seconds"`
	EstimatedRemainingSeconds float64 `json:"estimated_remaining_seconds"`
}

type runListResponse struct {
	Runs      []runListItem `json:"runs"`
	TotalRuns int           `json:"total_runs"`
}

type strategyItem struct {
	StrategyID   int     `json:"strategy_id"`
	StrategyName string  `json:"strategy_name"`
	Status       string  `json:"status"`
	StartTime    *string `json:"start_time"`
	EndTime      *string `json:"end_time"`
	DurationSecs float64 `json:"duration_seconds"`
	TradesGen    int     `json:"trades_generated"`
	ErrorMessage *string `json:"error_message"`
}

type runDetailResponse struct {
	RunID                    string         `json:"run_id"`
	Symbol                   string         `json:"symbol"`
	Timeframe                string         `json:"timeframe"`
	RiskProfiles             []string       `json:"risk_profiles"`
	StartTime                string         `json:"start_time"`
	EndTime                  *string        `json:"end_time"`
	Status                   string         `json:"status"`
	TotalStrategies          int            `json:"total_strategies"`
	CompletedStrategies      int            `json:"completed_strategies"`
	PendingStrategies        int            `json:"pending_strategies"`
	FailedStrategies         int            `json:"failed_strategies"`
	ProgressPercent          int            `json:"progress_percent"`
	ElapsedTimeSeconds       float64        `json:"elapsed_time_seconds"`
	EstimatedRemainingSeconds float64       `json:"estimated_remaining_seconds"`
	Strategies               []strategyItem `json:"strategies"`
}

type countDetail struct {
	Count   int `json:"count"`
	Percent int `json:"percent"`
}

type runSummaryResponse struct {
	RunID                    string      `json:"run_id"`
	Symbol                   string      `json:"symbol"`
	Timeframe                string      `json:"timeframe"`
	TotalStrategies          int         `json:"total_strategies"`
	Completed                countDetail `json:"completed"`
	Running                  countDetail `json:"running"`
	Pending                  countDetail `json:"pending"`
	Failed                   countDetail `json:"failed"`
	TotalTradesGenerated     int         `json:"total_trades_generated"`
	AvgTradesPerStrategy     float64     `json:"avg_trades_per_strategy"`
	ElapsedTimeSeconds       float64     `json:"elapsed_time_seconds"`
	EstimatedTotalTimeSeconds float64    `json:"estimated_total_time_seconds"`
	ETACompletion            *string     `json:"eta_completion"`
}

type errorResponse struct {
	Error string `json:"error"`
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

// HandleStatus returns overall service health and readiness.
func (s *Server) HandleStatus(w http.ResponseWriter, r *http.Request) {
	status := "healthy"
	resp := statusResponse{
		Status:           status,
		UptimeSeconds:    s.Tracker.UptimeSeconds(),
		Version:          s.Tracker.Version(),
		BackendConnected: s.BackendConnected,
	}
	writeJSON(w, http.StatusOK, resp)
}

// HandleListRuns returns a list of all strategy runs with summary statistics.
func (s *Server) HandleListRuns(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	statusFilter := q.Get("status")
	symbolFilter := q.Get("symbol")
	limit := 100
	if l := q.Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	runs := s.Tracker.ListRuns(statusFilter, symbolFilter, limit)
	items := make([]runListItem, len(runs))
	for i, run := range runs {
		items[i] = buildRunListItem(run)
	}

	writeJSON(w, http.StatusOK, runListResponse{
		Runs:      items,
		TotalRuns: len(items),
	})
}

// HandleGetRun returns detailed status of a specific run including
// per-strategy execution state.
func (s *Server) HandleGetRun(w http.ResponseWriter, r *http.Request) {
	runID := r.PathValue("run_id")
	if runID == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "run_id is required"})
		return
	}

	run := s.Tracker.GetRun(runID)
	if run == nil {
		writeJSON(w, http.StatusNotFound, errorResponse{Error: "run not found"})
		return
	}

	completed, _, pending, failed := run.Counts()

	stratItems := make([]strategyItem, len(run.Strategies))
	for i, st := range run.Strategies {
		stratItems[i] = buildStrategyItem(st)
	}

	resp := runDetailResponse{
		RunID:                    run.RunID,
		Symbol:                   run.Symbol,
		Timeframe:                run.Timeframe,
		RiskProfiles:             run.RiskProfiles,
		StartTime:                run.StartTime.UTC().Format("2006-01-02T15:04:05Z"),
		EndTime:                  formatOptionalTime(run.EndTime),
		Status:                   string(run.Status),
		TotalStrategies:          run.TotalStrategies(),
		CompletedStrategies:      completed,
		PendingStrategies:        pending,
		FailedStrategies:         failed,
		ProgressPercent:          run.ProgressPercent(),
		ElapsedTimeSeconds:       run.ElapsedSeconds(),
		EstimatedRemainingSeconds: run.EstimatedRemainingSeconds(),
		Strategies:               stratItems,
	}

	writeJSON(w, http.StatusOK, resp)
}

// HandleGetRunSummary returns high-level stats for a run, suitable for
// dashboards.
func (s *Server) HandleGetRunSummary(w http.ResponseWriter, r *http.Request) {
	runID := r.PathValue("run_id")
	if runID == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "run_id is required"})
		return
	}

	run := s.Tracker.GetRun(runID)
	if run == nil {
		writeJSON(w, http.StatusNotFound, errorResponse{Error: "run not found"})
		return
	}

	completed, running, pending, failed := run.Counts()
	total := run.TotalStrategies()
	totalTrades := run.TotalTradesGenerated()

	var avgTrades float64
	if completed > 0 {
		avgTrades = float64(totalTrades) / float64(completed)
	}

	elapsed := run.ElapsedSeconds()
	estimatedTotal := elapsed
	if completed > 0 && total > 0 {
		estimatedTotal = (elapsed / float64(completed)) * float64(total)
	}

	var etaStr *string
	if eta := run.ETACompletion(); eta != nil {
		s := eta.UTC().Format("2006-01-02T15:04:05Z")
		etaStr = &s
	}

	pct := func(count, tot int) int {
		if tot == 0 {
			return 0
		}
		return count * 100 / tot
	}

	resp := runSummaryResponse{
		RunID:           run.RunID,
		Symbol:          run.Symbol,
		Timeframe:       run.Timeframe,
		TotalStrategies: total,
		Completed:       countDetail{Count: completed, Percent: pct(completed, total)},
		Running:         countDetail{Count: running, Percent: pct(running, total)},
		Pending:         countDetail{Count: pending, Percent: pct(pending, total)},
		Failed:          countDetail{Count: failed, Percent: pct(failed, total)},
		TotalTradesGenerated:      totalTrades,
		AvgTradesPerStrategy:      avgTrades,
		ElapsedTimeSeconds:        elapsed,
		EstimatedTotalTimeSeconds: estimatedTotal,
		ETACompletion:             etaStr,
	}

	writeJSON(w, http.StatusOK, resp)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		slog.Warn("Failed to encode JSON response", "error", err)
	}
}

func buildRunListItem(run *runtracker.StrategyRun) runListItem {
	completed, _, pending, failed := run.Counts()
	return runListItem{
		RunID:                    run.RunID,
		Symbol:                   run.Symbol,
		Timeframe:                run.Timeframe,
		StartTime:                run.StartTime.UTC().Format("2006-01-02T15:04:05Z"),
		EndTime:                  formatOptionalTime(run.EndTime),
		Status:                   string(run.Status),
		TotalStrategies:          run.TotalStrategies(),
		CompletedStrategies:      completed,
		PendingStrategies:        pending,
		FailedStrategies:         failed,
		ProgressPercent:          run.ProgressPercent(),
		ElapsedTimeSeconds:       run.ElapsedSeconds(),
		EstimatedRemainingSeconds: run.EstimatedRemainingSeconds(),
	}
}

func buildStrategyItem(st runtracker.StrategyExecutionState) strategyItem {
	item := strategyItem{
		StrategyID:   st.StrategyID,
		StrategyName: st.StrategyName,
		Status:       string(st.Status),
		StartTime:    formatOptionalTime(st.StartTime),
		EndTime:      formatOptionalTime(st.EndTime),
		DurationSecs: st.DurationSecs,
		TradesGen:    st.TradesGen,
	}
	if st.ErrorMessage != "" {
		msg := st.ErrorMessage
		item.ErrorMessage = &msg
	}
	return item
}

func formatOptionalTime(t *time.Time) *string {
	if t == nil {
		return nil
	}
	s := t.UTC().Format("2006-01-02T15:04:05Z")
	return &s
}

// ExtractRunID extracts the run_id from a URL path like /api/v1/runs/{run_id}
// or /api/v1/runs/{run_id}/summary. This is a fallback for Go versions
// before 1.22 that do not support PathValue.
func ExtractRunID(path string) string {
	parts := strings.Split(strings.TrimPrefix(path, "/"), "/")
	// Expected: api/v1/runs/{run_id} or api/v1/runs/{run_id}/summary
	if len(parts) >= 4 && parts[0] == "api" && parts[1] == "v1" && parts[2] == "runs" {
		return parts[3]
	}
	return ""
}
