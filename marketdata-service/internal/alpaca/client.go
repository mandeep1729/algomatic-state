package alpaca

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
	// MaxDaysPerChunk matches Python MAX_DAYS_PER_CHUNK = 25.
	MaxDaysPerChunk = 25

	// maxRetries is the number of retry attempts for API calls.
	maxRetries = 3

	// minInterval is the minimum delay between API calls (200 calls/min ≈ 300ms).
	minInterval = 300 * time.Millisecond

	// maxBarsPerPage is the Alpaca API page limit.
	maxBarsPerPage = 10000
)

// Client interacts with the Alpaca v2 market data API.
type Client struct {
	baseURL    string
	apiKey     string
	secretKey  string
	httpClient *http.Client
	logger     *slog.Logger

	// lastCall tracks the timestamp of the last API call for rate limiting.
	lastCall time.Time
}

// NewClient creates a new Alpaca API client.
func NewClient(baseURL, apiKey, secretKey string, logger *slog.Logger) *Client {
	if logger == nil {
		logger = slog.Default()
	}
	if baseURL == "" {
		baseURL = "https://data.alpaca.markets"
	}

	return &Client{
		baseURL:   baseURL,
		apiKey:    apiKey,
		secretKey: secretKey,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		logger: logger,
	}
}

// FetchBars fetches OHLCV bars from Alpaca for the given symbol and timeframe.
// Large date ranges are chunked into MaxDaysPerChunk windows.
// Returns bars as db.OHLCVBar for direct database insertion.
func (c *Client) FetchBars(ctx context.Context, symbol, timeframe string, start, end time.Time) ([]db.OHLCVBar, error) {
	chunks := generateDateChunks(start, end, MaxDaysPerChunk)
	c.logger.Info("Fetching bars from Alpaca",
		"symbol", symbol,
		"timeframe", timeframe,
		"start", start.Format(time.RFC3339),
		"end", end.Format(time.RFC3339),
		"chunks", len(chunks),
	)

	var allBars []db.OHLCVBar
	for i, chunk := range chunks {
		bars, err := c.fetchChunk(ctx, symbol, timeframe, chunk[0], chunk[1])
		if err != nil {
			return allBars, fmt.Errorf("chunk %d/%d (%s to %s): %w",
				i+1, len(chunks),
				chunk[0].Format("2006-01-02"),
				chunk[1].Format("2006-01-02"),
				err,
			)
		}
		allBars = append(allBars, bars...)
		c.logger.Debug("Chunk complete",
			"chunk", i+1,
			"total_chunks", len(chunks),
			"bars_in_chunk", len(bars),
			"running_total", len(allBars),
		)
	}

	c.logger.Info("Alpaca fetch complete",
		"symbol", symbol,
		"timeframe", timeframe,
		"total_bars", len(allBars),
	)
	return allBars, nil
}

// fetchChunk dispatches to stock or crypto fetch based on the symbol.
func (c *Client) fetchChunk(ctx context.Context, symbol, timeframe string, start, end time.Time) ([]db.OHLCVBar, error) {
	if IsCrypto(symbol) {
		return c.fetchChunkCrypto(ctx, symbol, timeframe, start, end)
	}
	return c.fetchChunkStock(ctx, symbol, timeframe, start, end)
}

// fetchChunkStock fetches bars for a single date chunk from the stocks endpoint.
func (c *Client) fetchChunkStock(ctx context.Context, symbol, timeframe string, start, end time.Time) ([]db.OHLCVBar, error) {
	var allBars []db.OHLCVBar
	pageToken := ""

	alpacaTF := mapTimeframe(timeframe)

	for {
		c.rateLimit()

		params := url.Values{
			"timeframe": {alpacaTF},
			"start":     {start.Format(time.RFC3339)},
			"end":       {end.Format(time.RFC3339)},
			"feed":      {"iex"},
			"limit":     {fmt.Sprintf("%d", maxBarsPerPage)},
		}
		if pageToken != "" {
			params.Set("page_token", pageToken)
		}

		reqURL := fmt.Sprintf("%s/v2/stocks/%s/bars?%s", c.baseURL, symbol, params.Encode())

		body, err := c.doRawRequest(ctx, reqURL)
		if err != nil {
			return allBars, err
		}

		var resp barsResponse
		if err := json.Unmarshal(body, &resp); err != nil {
			return allBars, fmt.Errorf("decoding stock bars response: %w", err)
		}

		bars := convertBars(resp.Bars)
		allBars = append(allBars, bars...)

		if resp.NextPageToken == "" {
			break
		}
		pageToken = resp.NextPageToken
	}

	return allBars, nil
}

// fetchChunkCrypto fetches bars for a single date chunk from the crypto endpoint.
func (c *Client) fetchChunkCrypto(ctx context.Context, symbol, timeframe string, start, end time.Time) ([]db.OHLCVBar, error) {
	var allBars []db.OHLCVBar
	pageToken := ""

	alpacaTF := mapTimeframe(timeframe)
	alpacaSymbol := CryptoAlpacaSymbol(symbol)

	for {
		c.rateLimit()

		params := url.Values{
			"symbols":   {alpacaSymbol},
			"timeframe": {alpacaTF},
			"start":     {start.Format(time.RFC3339)},
			"end":       {end.Format(time.RFC3339)},
			"limit":     {fmt.Sprintf("%d", maxBarsPerPage)},
		}
		if pageToken != "" {
			params.Set("page_token", pageToken)
		}

		reqURL := fmt.Sprintf("%s/v1beta3/crypto/us/bars?%s", c.baseURL, params.Encode())

		body, err := c.doRawRequest(ctx, reqURL)
		if err != nil {
			return allBars, err
		}

		var resp cryptoBarsResponse
		if err := json.Unmarshal(body, &resp); err != nil {
			return allBars, fmt.Errorf("decoding crypto bars response: %w", err)
		}

		// Extract bars for our symbol from the map.
		if symbolBars, ok := resp.Bars[alpacaSymbol]; ok {
			allBars = append(allBars, convertBars(symbolBars)...)
		}

		if resp.NextPageToken == "" {
			break
		}
		pageToken = resp.NextPageToken
	}

	c.logger.Debug("Crypto fetch complete",
		"symbol", symbol,
		"alpaca_symbol", alpacaSymbol,
		"bars", len(allBars),
	)

	return allBars, nil
}

// doRawRequest executes an HTTP GET with exponential backoff retries.
// Returns the raw response body on success.
func (c *Client) doRawRequest(ctx context.Context, reqURL string) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * time.Second
			c.logger.Debug("Retrying Alpaca request",
				"attempt", attempt,
				"backoff", backoff,
				"url", reqURL,
			)
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
		if err != nil {
			return nil, fmt.Errorf("creating request: %w", err)
		}
		req.Header.Set("APCA-API-KEY-ID", c.apiKey)
		req.Header.Set("APCA-API-SECRET-KEY", c.secretKey)
		req.Header.Set("Accept", "application/json")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("HTTP request failed: %w", err)
			c.logger.Warn("Alpaca request failed", "attempt", attempt, "error", err)
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

		case resp.StatusCode == 429:
			lastErr = fmt.Errorf("rate limited (429)")
			c.logger.Warn("Alpaca rate limit hit, retrying", "attempt", attempt)
			continue

		case resp.StatusCode >= 500:
			lastErr = fmt.Errorf("server error (status %d)", resp.StatusCode)
			c.logger.Warn("Alpaca server error, retrying",
				"status", resp.StatusCode, "attempt", attempt,
			)
			continue

		default:
			return nil, &AlpacaAPIError{
				StatusCode: resp.StatusCode,
				Body:       string(body),
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

// mapTimeframe converts our timeframe strings to Alpaca API format.
func mapTimeframe(tf string) string {
	switch tf {
	case "1Min":
		return "1Min"
	case "5Min":
		return "5Min"
	case "15Min":
		return "15Min"
	case "1Hour":
		return "1Hour"
	case "1Day":
		return "1Day"
	default:
		return tf
	}
}

// convertBars converts Alpaca API bars to db.OHLCVBar.
func convertBars(apiBars []Bar) []db.OHLCVBar {
	bars := make([]db.OHLCVBar, 0, len(apiBars))
	for _, b := range apiBars {
		bars = append(bars, db.OHLCVBar{
			Timestamp: b.Timestamp.UTC(),
			Open:      b.Open,
			High:      b.High,
			Low:       b.Low,
			Close:     b.Close,
			Volume:    b.Volume,
		})
	}
	return bars
}

// generateDateChunks splits a date range into chunks of maxDays.
func generateDateChunks(start, end time.Time, maxDays int) [][2]time.Time {
	var chunks [][2]time.Time
	current := start
	for current.Before(end) {
		chunkEnd := current.AddDate(0, 0, maxDays)
		if chunkEnd.After(end) {
			chunkEnd = end
		}
		chunks = append(chunks, [2]time.Time{current, chunkEnd})
		current = chunkEnd
	}
	return chunks
}
