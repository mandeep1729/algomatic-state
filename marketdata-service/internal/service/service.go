package service

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/algomatic/marketdata-service/internal/alpaca"
	"github.com/algomatic/marketdata-service/internal/db"
	"github.com/algomatic/marketdata-service/internal/twelvedata"
)

// DBClient abstracts database operations so both db.Client (direct pgx)
// and dataclient.Client (gRPC) can be used.
type DBClient interface {
	GetOrCreateTicker(ctx context.Context, symbol string) (db.TickerInfo, error)
	GetActiveTickers(ctx context.Context) ([]string, error)
	GetLatestTimestamp(ctx context.Context, tickerID int, timeframe string) (*time.Time, error)
	BulkInsertBars(ctx context.Context, tickerID int, timeframe, source string, bars []db.OHLCVBar) (int, error)
	UpdateSyncLog(ctx context.Context, entry db.SyncLogEntry) error
	DeactivateTicker(ctx context.Context, symbol string) error
	HealthCheck(ctx context.Context) error
}

// pendingRequest tracks in-flight requests for request coalescing.
type pendingRequest struct {
	done   chan struct{}
	result map[string]int
	err    error
}

// Service orchestrates market data fetching and aggregation.
type Service struct {
	db         DBClient
	alpaca     *alpaca.Client
	twelvedata *twelvedata.Client
	logger     *slog.Logger

	// Request coalescing: concurrent requests for the same symbol share one fetch.
	pending sync.Map // map[string]*pendingRequest
}

// NewService creates a new market data service.
// twelveDataClient may be nil if TwelveData is not configured.
func NewService(dbClient DBClient, alpacaClient *alpaca.Client, twelveDataClient *twelvedata.Client, logger *slog.Logger) *Service {
	if logger == nil {
		logger = slog.Default()
	}
	return &Service{
		db:         dbClient,
		alpaca:     alpacaClient,
		twelvedata: twelveDataClient,
		logger:     logger,
	}
}

// EnsureData ensures bars exist in the database for the given symbol, timeframes, and range.
// Uses request coalescing — concurrent calls for the same symbol share a single fetch.
// Returns a map of timeframe -> number of new bars inserted.
func (s *Service) EnsureData(ctx context.Context, symbol string, timeframes []string, start, end time.Time) (map[string]int, error) {
	// Request coalescing: if someone is already fetching this symbol, wait for them.
	req := &pendingRequest{done: make(chan struct{})}
	if existing, loaded := s.pending.LoadOrStore(symbol, req); loaded {
		// Another goroutine is already working on this symbol.
		pending := existing.(*pendingRequest)
		s.logger.Debug("Coalescing request, waiting for existing fetch",
			"symbol", symbol,
		)
		select {
		case <-pending.done:
			return pending.result, pending.err
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}

	// We won the race — do the actual work.
	defer func() {
		close(req.done)
		s.pending.Delete(symbol)
	}()

	result, err := s.doEnsureData(ctx, symbol, timeframes, start, end)
	req.result = result
	req.err = err
	return result, err
}

// doEnsureData is the actual implementation of EnsureData without coalescing.
func (s *Service) doEnsureData(ctx context.Context, symbol string, timeframes []string, start, end time.Time) (map[string]int, error) {
	ticker, err := s.db.GetOrCreateTicker(ctx, symbol)
	if err != nil {
		return nil, fmt.Errorf("get/create ticker %q: %w", symbol, err)
	}

	result := make(map[string]int)

	// Determine what needs to be fetched.
	needs1Min := false
	needs1Day := false

	for _, tf := range timeframes {
		switch tf {
		case "1Min":
			needs1Min = true
		case "1Day":
			needs1Day = true
		case "5Min", "15Min", "1Hour":
			// Continuous aggregates auto-compute these from 1Min data.
			// Just ensure 1Min source data exists.
			needs1Min = true
		default:
			s.logger.Warn("Ignoring unsupported timeframe", "timeframe", tf, "symbol", symbol)
		}
	}

	// Route to the appropriate data source based on asset class.
	useTwelveData := isTwelveDataAsset(ticker.AssetClass)
	if useTwelveData && s.twelvedata == nil {
		return result, fmt.Errorf("TwelveData client not configured for %s (asset_class=%s)", symbol, ticker.AssetClass)
	}

	// Step 1: Ensure 1Min bars (source for continuous aggregates).
	if needs1Min {
		var n int
		if useTwelveData {
			n, err = s.ensureFromTwelveData(ctx, ticker.ID, symbol, "1Min", start, end, time.Minute)
		} else {
			n, err = s.ensureFromAlpaca(ctx, ticker.ID, symbol, "1Min", start, end, time.Minute)
		}
		if err != nil {
			s.handleFetchError(ctx, symbol, err)
			return result, fmt.Errorf("ensure 1Min for %s: %w", symbol, err)
		}
		result["1Min"] = n
	}

	// Step 2: 5Min/15Min/1Hour are handled by TimescaleDB continuous aggregates.
	// No manual aggregation needed.

	// Step 3: Ensure 1Day (fetched directly, not aggregated).
	if needs1Day {
		var n int
		if useTwelveData {
			n, err = s.ensureFromTwelveData(ctx, ticker.ID, symbol, "1Day", start, end, 24*time.Hour)
		} else {
			n, err = s.ensureFromAlpaca(ctx, ticker.ID, symbol, "1Day", start, end, 24*time.Hour)
		}
		if err != nil {
			s.handleFetchError(ctx, symbol, err)
			return result, fmt.Errorf("ensure 1Day for %s: %w", symbol, err)
		}
		result["1Day"] = n
	}

	s.logger.Info("EnsureData complete",
		"symbol", symbol,
		"asset_class", ticker.AssetClass,
		"source", dataSourceName(useTwelveData),
		"result", result,
	)
	return result, nil
}

// isTwelveDataAsset returns true if the asset class should be fetched from TwelveData.
func isTwelveDataAsset(assetClass string) bool {
	return assetClass == "commodity" || assetClass == "fx"
}

// dataSourceName returns a human-readable name for logging.
func dataSourceName(useTwelveData bool) string {
	if useTwelveData {
		return "twelvedata"
	}
	return "alpaca"
}

// handleFetchError checks if a fetch error is a client error (4xx)
// and deactivates the ticker to prevent future polling for invalid symbols.
func (s *Service) handleFetchError(ctx context.Context, symbol string, err error) {
	isClientError := alpaca.IsAlpacaAPIError(err) || twelvedata.IsTwelveDataAPIError(err)
	if !isClientError {
		return
	}
	s.logger.Warn("Deactivating ticker due to API client error",
		"symbol", symbol,
		"error", err,
	)
	if deactivateErr := s.db.DeactivateTicker(ctx, symbol); deactivateErr != nil {
		s.logger.Error("Failed to deactivate ticker",
			"symbol", symbol,
			"error", deactivateErr,
		)
	}
}

// ensureFromAlpaca checks for gaps and fetches missing data from Alpaca.
func (s *Service) ensureFromAlpaca(ctx context.Context, tickerID int, symbol, timeframe string, start, end time.Time, buffer time.Duration) (int, error) {
	latest, err := s.db.GetLatestTimestamp(ctx, tickerID, timeframe)
	if err != nil {
		return 0, fmt.Errorf("getting latest timestamp: %w", err)
	}

	fetchStart := start
	if latest != nil {
		// Data exists — check if we're up to date.
		if end.Before(latest.Add(buffer)) || end.Equal(latest.Add(buffer)) {
			s.logger.Debug("Data up to date, skipping fetch",
				"symbol", symbol,
				"timeframe", timeframe,
				"latest_in_db", latest,
				"requested_end", end,
			)
			return 0, nil
		}
		fetchStart = latest.Add(buffer)
	}

	s.logger.Info("Fetching from Alpaca",
		"symbol", symbol,
		"timeframe", timeframe,
		"start", fetchStart.Format(time.RFC3339),
		"end", end.Format(time.RFC3339),
	)

	bars, err := s.alpaca.FetchBars(ctx, symbol, timeframe, fetchStart, end)
	if err != nil {
		return 0, fmt.Errorf("fetching bars: %w", err)
	}

	if len(bars) == 0 {
		s.logger.Debug("No new bars from Alpaca",
			"symbol", symbol, "timeframe", timeframe,
		)
		return 0, nil
	}

	inserted, err := s.db.BulkInsertBars(ctx, tickerID, timeframe, "alpaca", bars)
	if err != nil {
		return 0, fmt.Errorf("inserting bars: %w", err)
	}

	// Update sync log.
	lastTS := bars[len(bars)-1].Timestamp
	firstTS := bars[0].Timestamp
	if err := s.db.UpdateSyncLog(ctx, db.SyncLogEntry{
		TickerID:            tickerID,
		Timeframe:           timeframe,
		LastSyncedTimestamp:  &lastTS,
		FirstSyncedTimestamp: &firstTS,
		BarsFetched:         inserted,
		Status:              "success",
	}); err != nil {
		s.logger.Warn("Failed to update sync log",
			"symbol", symbol, "timeframe", timeframe, "error", err,
		)
	}

	s.logger.Info("Bars inserted",
		"symbol", symbol,
		"timeframe", timeframe,
		"source", "alpaca",
		"fetched", len(bars),
		"inserted", inserted,
	)
	return inserted, nil
}

// ensureFromTwelveData checks for gaps and fetches missing data from TwelveData.
func (s *Service) ensureFromTwelveData(ctx context.Context, tickerID int, symbol, timeframe string, start, end time.Time, buffer time.Duration) (int, error) {
	latest, err := s.db.GetLatestTimestamp(ctx, tickerID, timeframe)
	if err != nil {
		return 0, fmt.Errorf("getting latest timestamp: %w", err)
	}

	fetchStart := start
	if latest != nil {
		// Data exists — check if we're up to date.
		if end.Before(latest.Add(buffer)) || end.Equal(latest.Add(buffer)) {
			s.logger.Debug("Data up to date, skipping fetch",
				"symbol", symbol,
				"timeframe", timeframe,
				"latest_in_db", latest,
				"requested_end", end,
			)
			return 0, nil
		}
		fetchStart = latest.Add(buffer)
	}

	s.logger.Info("Fetching from TwelveData",
		"symbol", symbol,
		"timeframe", timeframe,
		"start", fetchStart.Format(time.RFC3339),
		"end", end.Format(time.RFC3339),
	)

	bars, err := s.twelvedata.FetchBars(ctx, symbol, timeframe, fetchStart, end)
	if err != nil {
		return 0, fmt.Errorf("fetching bars: %w", err)
	}

	if len(bars) == 0 {
		s.logger.Debug("No new bars from TwelveData",
			"symbol", symbol, "timeframe", timeframe,
		)
		return 0, nil
	}

	inserted, err := s.db.BulkInsertBars(ctx, tickerID, timeframe, "twelvedata", bars)
	if err != nil {
		return 0, fmt.Errorf("inserting bars: %w", err)
	}

	// Update sync log.
	lastTS := bars[len(bars)-1].Timestamp
	firstTS := bars[0].Timestamp
	if err := s.db.UpdateSyncLog(ctx, db.SyncLogEntry{
		TickerID:            tickerID,
		Timeframe:           timeframe,
		LastSyncedTimestamp:  &lastTS,
		FirstSyncedTimestamp: &firstTS,
		BarsFetched:         inserted,
		Status:              "success",
	}); err != nil {
		s.logger.Warn("Failed to update sync log",
			"symbol", symbol, "timeframe", timeframe, "error", err,
		)
	}

	s.logger.Info("Bars inserted",
		"symbol", symbol,
		"timeframe", timeframe,
		"source", "twelvedata",
		"fetched", len(bars),
		"inserted", inserted,
	)
	return inserted, nil
}
