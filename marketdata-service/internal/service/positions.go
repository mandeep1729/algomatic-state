package service

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// symbolsResponse matches the JSON returned by /api/internal/position-symbols
// and /api/internal/agent-symbols (same shape).
type symbolsResponse struct {
	Symbols []string `json:"symbols"`
}

// FetchPositionSymbols calls the Python backend to get symbols with open positions.
func FetchPositionSymbols(ctx context.Context, backendURL string) ([]string, error) {
	return fetchSymbols(ctx, backendURL, "/api/internal/position-symbols")
}

// FetchAgentSymbols calls the Python backend to get symbols from active trading agents.
func FetchAgentSymbols(ctx context.Context, backendURL string) ([]string, error) {
	return fetchSymbols(ctx, backendURL, "/api/internal/agent-symbols")
}

// FetchFavoriteSymbols calls the Python backend to get symbols from user favorites.
func FetchFavoriteSymbols(ctx context.Context, backendURL string) ([]string, error) {
	return fetchSymbols(ctx, backendURL, "/api/internal/favorite-symbols")
}

// FetchRecentTradeSymbols calls the Python backend to get symbols traded in the last 7 days.
func FetchRecentTradeSymbols(ctx context.Context, backendURL string) ([]string, error) {
	return fetchSymbols(ctx, backendURL, "/api/internal/recent-trade-symbols?days=7")
}

// fetchSymbols is a helper that calls a backend endpoint returning {"symbols": [...]}.
func fetchSymbols(ctx context.Context, backendURL, path string) ([]string, error) {
	if backendURL == "" {
		return nil, fmt.Errorf("backend URL not configured")
	}

	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	url := backendURL + path
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching symbols from %s: %w", path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("backend returned status %d for %s: %s", resp.StatusCode, path, string(body))
	}

	var result symbolsResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decoding response from %s: %w", path, err)
	}

	return result.Symbols, nil
}
