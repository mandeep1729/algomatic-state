package service

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// positionSymbolsResponse matches the JSON returned by /api/internal/position-symbols.
type positionSymbolsResponse struct {
	Symbols []string `json:"symbols"`
}

// FetchPositionSymbols calls the Python backend to get symbols with open positions.
// Returns nil slice and no error if backendURL is empty (disabled).
func FetchPositionSymbols(ctx context.Context, backendURL string) ([]string, error) {
	if backendURL == "" {
		return nil, fmt.Errorf("backend URL not configured")
	}

	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	url := backendURL + "/api/internal/position-symbols"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching position symbols: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("backend returned status %d: %s", resp.StatusCode, string(body))
	}

	var result positionSymbolsResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decoding response: %w", err)
	}

	return result.Symbols, nil
}
