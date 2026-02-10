// Package backend provides an HTTP client for the Python backend API.
//
// Instead of querying the database directly, the Go strategy engine
// fetches OHLCV bars and computed indicators through the Python backend
// REST API. This decouples the Go service from database credentials and
// schema details.
//
// Usage:
//
//	client := backend.NewClient("http://localhost:8000", nil)
//	bars, err := client.GetBars(ctx, "AAPL", "1Hour", start, end)
//	indicators, err := client.GetIndicators(ctx, "AAPL", "1Hour", start, end)
//	barData, err := client.GetBarData(ctx, "AAPL", "1Hour", start, end)
package backend

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"net/url"
	"sync"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// DefaultTimeout is the per-request timeout applied to API calls.
const DefaultTimeout = 30 * time.Second

// MaxRetries is the number of retry attempts for transient errors.
const MaxRetries = 3

// Config holds optional configuration for the backend client.
type Config struct {
	// Timeout per HTTP request. Zero means DefaultTimeout.
	Timeout time.Duration

	// MaxRetries for transient errors. Zero means the package default.
	MaxRetries int

	// Logger for debug/info output. Nil uses slog.Default().
	Logger *slog.Logger

	// EnableCache enables in-memory caching of responses.
	EnableCache bool
}

// Client is an HTTP client for the Python backend API.
type Client struct {
	baseURL    string
	httpClient *http.Client
	maxRetries int
	logger     *slog.Logger

	// In-memory cache (symbol+timeframe+range -> data)
	cacheMu sync.RWMutex
	cache   map[string]cacheEntry
	cacheOn bool
}

type cacheEntry struct {
	barData   []types.BarData
	fetchedAt time.Time
}

// NewClient creates a new backend API client.
//
// baseURL should include the scheme and host, e.g. "http://localhost:8000".
// A nil config uses sensible defaults.
func NewClient(baseURL string, cfg *Config) *Client {
	timeout := DefaultTimeout
	retries := MaxRetries
	logger := slog.Default()
	enableCache := false

	if cfg != nil {
		if cfg.Timeout > 0 {
			timeout = cfg.Timeout
		}
		if cfg.MaxRetries > 0 {
			retries = cfg.MaxRetries
		}
		if cfg.Logger != nil {
			logger = cfg.Logger
		}
		enableCache = cfg.EnableCache
	}

	logger.Info("Backend client initialised",
		"base_url", baseURL,
		"timeout", timeout,
		"max_retries", retries,
		"cache", enableCache,
	)

	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		maxRetries: retries,
		logger:     logger,
		cache:      make(map[string]cacheEntry),
		cacheOn:    enableCache,
	}
}

// ---------------------------------------------------------------------------
// JSON response shapes (mirrors the Python Pydantic models)
// ---------------------------------------------------------------------------

type barsResponse struct {
	Symbol    string       `json:"symbol"`
	Timeframe string       `json:"timeframe"`
	Count     int          `json:"count"`
	Bars      []barPayload `json:"bars"`
}

type barPayload struct {
	Timestamp string  `json:"timestamp"`
	Open      float64 `json:"open"`
	High      float64 `json:"high"`
	Low       float64 `json:"low"`
	Close     float64 `json:"close"`
	Volume    float64 `json:"volume"`
}

type indicatorsResponse struct {
	Symbol         string              `json:"symbol"`
	Timeframe      string              `json:"timeframe"`
	Count          int                 `json:"count"`
	IndicatorNames []string            `json:"indicator_names"`
	Rows           []indicatorPayload  `json:"rows"`
}

type indicatorPayload struct {
	Timestamp  string             `json:"timestamp"`
	Indicators map[string]float64 `json:"indicators"`
}

type apiError struct {
	Detail string `json:"detail"`
}

// ---------------------------------------------------------------------------
// Public Methods
// ---------------------------------------------------------------------------

// GetBars fetches OHLCV bars from the Python backend.
func (c *Client) GetBars(
	ctx context.Context,
	symbol, timeframe string,
	start, end time.Time,
) ([]types.Bar, error) {
	params := url.Values{
		"symbol":          {symbol},
		"timeframe":       {timeframe},
		"start_timestamp": {start.Format(time.RFC3339)},
		"end_timestamp":   {end.Format(time.RFC3339)},
	}

	c.logger.Debug("Fetching bars", "symbol", symbol, "timeframe", timeframe)

	body, err := c.doGet(ctx, "/api/bars", params)
	if err != nil {
		return nil, fmt.Errorf("GetBars: %w", err)
	}

	var resp barsResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("GetBars: decoding response: %w", err)
	}

	bars := make([]types.Bar, 0, len(resp.Bars))
	for _, b := range resp.Bars {
		ts, err := parseTimestamp(b.Timestamp)
		if err != nil {
			c.logger.Warn("Skipping bar with unparseable timestamp", "ts", b.Timestamp, "err", err)
			continue
		}
		bars = append(bars, types.Bar{
			Timestamp: ts,
			Open:      b.Open,
			High:      b.High,
			Low:       b.Low,
			Close:     b.Close,
			Volume:    b.Volume,
		})
	}

	c.logger.Info("Fetched bars", "symbol", symbol, "timeframe", timeframe, "count", len(bars))
	return bars, nil
}

// GetIndicators fetches computed indicator values from the Python backend.
// The returned map is keyed by timestamp (RFC3339) -> indicator column -> value.
func (c *Client) GetIndicators(
	ctx context.Context,
	symbol, timeframe string,
	start, end time.Time,
) (map[time.Time]types.IndicatorRow, error) {
	params := url.Values{
		"symbol":          {symbol},
		"timeframe":       {timeframe},
		"start_timestamp": {start.Format(time.RFC3339)},
		"end_timestamp":   {end.Format(time.RFC3339)},
	}

	c.logger.Debug("Fetching indicators", "symbol", symbol, "timeframe", timeframe)

	body, err := c.doGet(ctx, "/api/indicators", params)
	if err != nil {
		return nil, fmt.Errorf("GetIndicators: %w", err)
	}

	var resp indicatorsResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("GetIndicators: decoding response: %w", err)
	}

	result := make(map[time.Time]types.IndicatorRow, len(resp.Rows))
	for _, row := range resp.Rows {
		ts, err := parseTimestamp(row.Timestamp)
		if err != nil {
			c.logger.Warn("Skipping indicator row with unparseable timestamp",
				"ts", row.Timestamp, "err", err,
			)
			continue
		}
		indRow := make(types.IndicatorRow, len(row.Indicators))
		for k, v := range row.Indicators {
			if !math.IsNaN(v) && !math.IsInf(v, 0) {
				indRow[k] = v
			}
		}
		result[ts] = indRow
	}

	c.logger.Info("Fetched indicators",
		"symbol", symbol, "timeframe", timeframe,
		"rows", len(result), "indicator_count", len(resp.IndicatorNames),
	)
	return result, nil
}

// GetBarData fetches both bars and indicators, then merges them into
// []types.BarData ready for the probe engine. This is the primary method
// most callers should use.
//
// Results are cached in memory (if caching is enabled) so repeated calls
// for the same symbol/timeframe/range do not hit the network again.
func (c *Client) GetBarData(
	ctx context.Context,
	symbol, timeframe string,
	start, end time.Time,
) ([]types.BarData, error) {
	cacheKey := fmt.Sprintf("%s|%s|%s|%s", symbol, timeframe,
		start.Format(time.RFC3339), end.Format(time.RFC3339))

	// Check cache
	if c.cacheOn {
		c.cacheMu.RLock()
		entry, ok := c.cache[cacheKey]
		c.cacheMu.RUnlock()
		if ok {
			c.logger.Debug("Cache hit for bar data", "key", cacheKey)
			return entry.barData, nil
		}
	}

	// Fetch bars and indicators in parallel
	type barsResult struct {
		bars []types.Bar
		err  error
	}
	type indResult struct {
		indicators map[time.Time]types.IndicatorRow
		err        error
	}

	barsCh := make(chan barsResult, 1)
	indCh := make(chan indResult, 1)

	go func() {
		bars, err := c.GetBars(ctx, symbol, timeframe, start, end)
		barsCh <- barsResult{bars, err}
	}()

	go func() {
		ind, err := c.GetIndicators(ctx, symbol, timeframe, start, end)
		indCh <- indResult{ind, err}
	}()

	barsRes := <-barsCh
	if barsRes.err != nil {
		// Drain the indicator channel
		<-indCh
		return nil, fmt.Errorf("GetBarData: bars: %w", barsRes.err)
	}

	indRes := <-indCh
	// Indicators are optional; missing indicators are not fatal
	if indRes.err != nil {
		c.logger.Warn("Indicators unavailable, proceeding with bars only",
			"symbol", symbol, "timeframe", timeframe, "err", indRes.err,
		)
	}

	// Merge bars + indicators
	barData := make([]types.BarData, 0, len(barsRes.bars))
	for _, bar := range barsRes.bars {
		ind := types.IndicatorRow{}
		if indRes.indicators != nil {
			if row, ok := indRes.indicators[bar.Timestamp]; ok {
				ind = row
			}
		}
		barData = append(barData, types.BarData{Bar: bar, Indicators: ind})
	}

	// Store in cache
	if c.cacheOn {
		c.cacheMu.Lock()
		c.cache[cacheKey] = cacheEntry{barData: barData, fetchedAt: time.Now()}
		c.cacheMu.Unlock()
	}

	c.logger.Info("Merged bar data",
		"symbol", symbol, "timeframe", timeframe, "total_bars", len(barData),
	)
	return barData, nil
}

// ClearCache removes all cached entries.
func (c *Client) ClearCache() {
	c.cacheMu.Lock()
	c.cache = make(map[string]cacheEntry)
	c.cacheMu.Unlock()
	c.logger.Debug("Cache cleared")
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

// doGet executes a GET request with retries and exponential backoff.
func (c *Client) doGet(ctx context.Context, path string, params url.Values) ([]byte, error) {
	u := c.baseURL + path
	if len(params) > 0 {
		u += "?" + params.Encode()
	}

	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * 500 * time.Millisecond
			c.logger.Debug("Retrying request",
				"attempt", attempt, "backoff", backoff, "url", u,
			)
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
		if err != nil {
			return nil, fmt.Errorf("creating request: %w", err)
		}
		req.Header.Set("Accept", "application/json")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("request failed: %w", err)
			c.logger.Warn("HTTP request failed", "url", u, "attempt", attempt, "err", err)
			continue
		}

		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			lastErr = fmt.Errorf("reading response body: %w", readErr)
			continue
		}

		switch {
		case resp.StatusCode >= 200 && resp.StatusCode < 300:
			return body, nil
		case resp.StatusCode == 400:
			var apiErr apiError
			if json.Unmarshal(body, &apiErr) == nil {
				return nil, fmt.Errorf("bad request: %s", apiErr.Detail)
			}
			return nil, fmt.Errorf("bad request (status %d)", resp.StatusCode)
		case resp.StatusCode == 404:
			var apiErr apiError
			if json.Unmarshal(body, &apiErr) == nil {
				return nil, fmt.Errorf("not found: %s", apiErr.Detail)
			}
			return nil, fmt.Errorf("not found (status %d)", resp.StatusCode)
		case resp.StatusCode >= 500:
			lastErr = fmt.Errorf("server error (status %d)", resp.StatusCode)
			c.logger.Warn("Server error, will retry",
				"status", resp.StatusCode, "attempt", attempt,
			)
			continue
		default:
			return nil, fmt.Errorf("unexpected status %d", resp.StatusCode)
		}
	}

	return nil, fmt.Errorf("all %d retries exhausted: %w", c.maxRetries, lastErr)
}

// parseTimestamp tries multiple timestamp formats.
func parseTimestamp(s string) (time.Time, error) {
	formats := []string{
		time.RFC3339,
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05+00:00",
		"2006-01-02",
	}
	for _, f := range formats {
		t, err := time.Parse(f, s)
		if err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("unrecognised timestamp format: %s", s)
}
