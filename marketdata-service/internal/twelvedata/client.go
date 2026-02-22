package twelvedata

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"time"

	"github.com/algomatic/marketdata-service/internal/db"
)

const (
	baseURL = "https://api.twelvedata.com"

	// TwelveData free tier: 800 requests/day, 8 requests/minute.
	// Conservative rate limit: 1 request every 8 seconds.
	minInterval = 8 * time.Second

	// maxRetries is the number of retry attempts for API calls.
	maxRetries = 3

	// maxOutputSize is the TwelveData API max rows per request.
	maxOutputSize = 5000
)

// Client interacts with the TwelveData time series API.
type Client struct {
	apiKey     string
	httpClient *http.Client
	logger     *slog.Logger
	lastCall   time.Time
}

// NewClient creates a new TwelveData API client.
func NewClient(apiKey string, logger *slog.Logger) *Client {
	if logger == nil {
		logger = slog.Default()
	}
	return &Client{
		apiKey: apiKey,
		httpClient: &http.Client{
			Timeout: 120 * time.Second,
		},
		logger: logger,
	}
}

// FetchBars fetches OHLCV bars from TwelveData for the given symbol and timeframe.
// For large date ranges, fetches in chunks to stay within the 5000-row API limit.
func (c *Client) FetchBars(ctx context.Context, symbol, timeframe string, start, end time.Time) ([]db.OHLCVBar, error) {
	tdInterval := mapTimeframe(timeframe)
	if tdInterval == "" {
		return nil, fmt.Errorf("unsupported timeframe %q for TwelveData", timeframe)
	}

	c.logger.Info("Fetching bars from TwelveData",
		"symbol", symbol,
		"timeframe", timeframe,
		"td_interval", tdInterval,
		"start", start.Format(time.RFC3339),
		"end", end.Format(time.RFC3339),
	)

	var allBars []db.OHLCVBar
	currentEnd := end

	// TwelveData returns bars newest-first. We paginate backward from `end`
	// in chunks of maxOutputSize until we pass `start`.
	for {
		select {
		case <-ctx.Done():
			return allBars, ctx.Err()
		default:
		}

		c.rateLimit()

		bars, err := c.fetchPage(ctx, symbol, tdInterval, start, currentEnd)
		if err != nil {
			return allBars, fmt.Errorf("fetching page ending at %s: %w", currentEnd.Format(time.RFC3339), err)
		}

		if len(bars) == 0 {
			break
		}

		allBars = append(allBars, bars...)

		// If we got fewer than maxOutputSize, we've exhausted the range.
		if len(bars) < maxOutputSize {
			break
		}

		// Move the window back: bars are sorted oldest-first after reversal,
		// so bars[0] is the oldest bar in this batch.
		oldest := bars[0].Timestamp
		if !oldest.After(start) {
			break
		}
		currentEnd = oldest.Add(-time.Second)
	}

	c.logger.Info("TwelveData fetch complete",
		"symbol", symbol,
		"timeframe", timeframe,
		"total_bars", len(allBars),
	)
	return allBars, nil
}

// fetchPage fetches a single page of bars from TwelveData.
// Returns bars sorted oldest-first (we reverse TwelveData's newest-first order).
func (c *Client) fetchPage(ctx context.Context, symbol, interval string, start, end time.Time) ([]db.OHLCVBar, error) {
	params := url.Values{
		"symbol":      {symbol},
		"interval":    {interval},
		"start_date":  {start.Format("2006-01-02 15:04:05")},
		"end_date":    {end.Format("2006-01-02 15:04:05")},
		"outputsize":  {fmt.Sprintf("%d", maxOutputSize)},
		"format":      {"JSON"},
		"timezone":    {"UTC"},
		"apikey":      {c.apiKey},
	}

	reqURL := fmt.Sprintf("%s/time_series?%s", baseURL, params.Encode())

	body, err := c.doRequest(ctx, reqURL)
	if err != nil {
		return nil, err
	}

	// Check for API error response.
	var errResp errorResponse
	if err := json.Unmarshal(body, &errResp); err == nil && errResp.Code != 0 {
		return nil, &TwelveDataAPIError{
			Code:    errResp.Code,
			Message: errResp.Message,
			Status:  errResp.Status,
		}
	}

	var resp timeSeriesResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("decoding time_series response: %w", err)
	}

	if resp.Status != "ok" {
		return nil, fmt.Errorf("TwelveData returned status %q: %s", resp.Status, resp.Message)
	}

	// Convert and reverse to oldest-first order.
	bars := make([]db.OHLCVBar, 0, len(resp.Values))
	for i := len(resp.Values) - 1; i >= 0; i-- {
		v := resp.Values[i]
		bar, err := v.toOHLCVBar()
		if err != nil {
			c.logger.Warn("Skipping bar with parse error",
				"symbol", symbol,
				"datetime", v.Datetime,
				"error", err,
			)
			continue
		}
		bars = append(bars, bar)
	}

	return bars, nil
}

// doRequest executes an HTTP GET with exponential backoff retries.
func (c *Client) doRequest(ctx context.Context, reqURL string) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * time.Second
			c.logger.Debug("Retrying TwelveData request",
				"attempt", attempt,
				"backoff", backoff,
			)
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		// Per-request timeout to prevent hanging on slow responses.
		reqCtx, cancel := context.WithTimeout(ctx, 90*time.Second)

		req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, reqURL, nil)
		if err != nil {
			cancel()
			return nil, fmt.Errorf("creating request: %w", err)
		}

		c.logger.Info("Sending TwelveData HTTP request", "attempt", attempt)
		resp, err := c.httpClient.Do(req)
		if err != nil {
			cancel()
			lastErr = fmt.Errorf("HTTP request failed: %w", err)
			c.logger.Warn("TwelveData request failed", "attempt", attempt, "error", err)
			continue
		}

		c.logger.Info("Reading TwelveData response body", "status", resp.StatusCode)
		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		cancel()
		if readErr != nil {
			lastErr = fmt.Errorf("reading response body: %w", readErr)
			c.logger.Warn("TwelveData body read failed", "attempt", attempt, "error", readErr)
			continue
		}
		c.logger.Info("TwelveData response received", "body_bytes", len(body))

		switch {
		case resp.StatusCode >= 200 && resp.StatusCode < 300:
			return body, nil

		case resp.StatusCode == 429:
			lastErr = fmt.Errorf("rate limited (429)")
			c.logger.Warn("TwelveData rate limit hit, retrying", "attempt", attempt)
			// Wait longer on rate limit.
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(minInterval):
			}
			continue

		case resp.StatusCode >= 500:
			lastErr = fmt.Errorf("server error (status %d)", resp.StatusCode)
			c.logger.Warn("TwelveData server error, retrying",
				"status", resp.StatusCode, "attempt", attempt,
			)
			continue

		default:
			return nil, &TwelveDataAPIError{
				Code:    resp.StatusCode,
				Message: string(body),
				Status:  "error",
			}
		}
	}

	return nil, fmt.Errorf("all %d retries exhausted: %w", maxRetries, lastErr)
}

// rateLimit enforces the minimum interval between API calls.
func (c *Client) rateLimit() {
	elapsed := time.Since(c.lastCall)
	if elapsed < minInterval {
		time.Sleep(minInterval - elapsed)
	}
	c.lastCall = time.Now()
}

// mapTimeframe converts our timeframe strings to TwelveData interval format.
func mapTimeframe(tf string) string {
	switch tf {
	case "1Min":
		return "1min"
	case "5Min":
		return "5min"
	case "15Min":
		return "15min"
	case "1Hour":
		return "1h"
	case "1Day":
		return "1day"
	default:
		return ""
	}
}
