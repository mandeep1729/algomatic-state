package backend

import (
	"context"
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func mustTime(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t
}

// newTestServer creates an httptest.Server that returns canned responses
// for /api/bars and /api/indicators.
func newTestServer(barsResp *barsResponse, indResp *indicatorsResponse) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		switch r.URL.Path {
		case "/api/bars":
			if barsResp == nil {
				w.WriteHeader(http.StatusNotFound)
				json.NewEncoder(w).Encode(apiError{Detail: "no data"})
				return
			}
			json.NewEncoder(w).Encode(barsResp)

		case "/api/indicators":
			if indResp == nil {
				w.WriteHeader(http.StatusNotFound)
				json.NewEncoder(w).Encode(apiError{Detail: "no indicators"})
				return
			}
			json.NewEncoder(w).Encode(indResp)

		default:
			w.WriteHeader(http.StatusNotFound)
			json.NewEncoder(w).Encode(apiError{Detail: "unknown path"})
		}
	}))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

func TestGetBars(t *testing.T) {
	canned := &barsResponse{
		Symbol:    "AAPL",
		Timeframe: "1Hour",
		Count:     2,
		Bars: []barPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Open: 100, High: 105, Low: 99, Close: 103, Volume: 1000},
			{Timestamp: "2024-01-02T11:00:00Z", Open: 103, High: 107, Low: 102, Close: 106, Volume: 1200},
		},
	}

	ts := newTestServer(canned, nil)
	defer ts.Close()

	client := NewClient(ts.URL, nil)
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	bars, err := client.GetBars(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("GetBars returned error: %v", err)
	}
	if len(bars) != 2 {
		t.Fatalf("expected 2 bars, got %d", len(bars))
	}
	if bars[0].Open != 100 {
		t.Errorf("expected bar[0].Open=100, got %f", bars[0].Open)
	}
	if bars[1].Close != 106 {
		t.Errorf("expected bar[1].Close=106, got %f", bars[1].Close)
	}
}

func TestGetIndicators(t *testing.T) {
	canned := &indicatorsResponse{
		Symbol:         "AAPL",
		Timeframe:      "1Hour",
		Count:          2,
		IndicatorNames: []string{"atr_14", "rsi_14", "sma_20"},
		Rows: []indicatorPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Indicators: map[string]float64{"atr_14": 2.5, "rsi_14": 55.0, "sma_20": 100.5}},
			{Timestamp: "2024-01-02T11:00:00Z", Indicators: map[string]float64{"atr_14": 2.6, "rsi_14": 60.0, "sma_20": 101.0}},
		},
	}

	ts := newTestServer(nil, canned)
	defer ts.Close()

	client := NewClient(ts.URL, nil)
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	ind, err := client.GetIndicators(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("GetIndicators returned error: %v", err)
	}
	if len(ind) != 2 {
		t.Fatalf("expected 2 indicator rows, got %d", len(ind))
	}

	ts10 := mustTime("2024-01-02T10:00:00Z")
	row, ok := ind[ts10]
	if !ok {
		t.Fatal("expected indicator row for 2024-01-02T10:00:00Z")
	}
	atr, atrOk := row.Get("atr_14")
	if !atrOk {
		t.Fatal("expected atr_14 indicator")
	}
	if math.Abs(atr-2.5) > 0.001 {
		t.Errorf("expected atr_14=2.5, got %f", atr)
	}
}

func TestGetBarData(t *testing.T) {
	barsResp := &barsResponse{
		Symbol:    "AAPL",
		Timeframe: "1Hour",
		Count:     2,
		Bars: []barPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Open: 100, High: 105, Low: 99, Close: 103, Volume: 1000},
			{Timestamp: "2024-01-02T11:00:00Z", Open: 103, High: 107, Low: 102, Close: 106, Volume: 1200},
		},
	}

	indResp := &indicatorsResponse{
		Symbol:         "AAPL",
		Timeframe:      "1Hour",
		Count:          2,
		IndicatorNames: []string{"atr_14", "rsi_14"},
		Rows: []indicatorPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Indicators: map[string]float64{"atr_14": 2.5, "rsi_14": 55.0}},
			{Timestamp: "2024-01-02T11:00:00Z", Indicators: map[string]float64{"atr_14": 2.6, "rsi_14": 60.0}},
		},
	}

	ts := newTestServer(barsResp, indResp)
	defer ts.Close()

	client := NewClient(ts.URL, &Config{EnableCache: true})
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	barData, err := client.GetBarData(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("GetBarData returned error: %v", err)
	}
	if len(barData) != 2 {
		t.Fatalf("expected 2 bar data entries, got %d", len(barData))
	}

	// Verify OHLCV
	if barData[0].Bar.Open != 100 {
		t.Errorf("expected bar[0].Open=100, got %f", barData[0].Bar.Open)
	}

	// Verify indicators merged correctly
	atr, ok := barData[0].Indicators.Get("atr_14")
	if !ok {
		t.Fatal("expected atr_14 indicator on bar[0]")
	}
	if math.Abs(atr-2.5) > 0.001 {
		t.Errorf("expected atr_14=2.5, got %f", atr)
	}

	// Second call should hit cache
	barData2, err := client.GetBarData(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("cached GetBarData returned error: %v", err)
	}
	if len(barData2) != 2 {
		t.Fatalf("expected 2 cached bar data entries, got %d", len(barData2))
	}
}

func TestGetBars_404(t *testing.T) {
	ts := newTestServer(nil, nil)
	defer ts.Close()

	client := NewClient(ts.URL, nil)
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	_, err := client.GetBars(context.Background(), "AAPL", "1Hour", start, end)
	if err == nil {
		t.Fatal("expected error for 404 response")
	}
}

func TestGetBars_ServerError_Retries(t *testing.T) {
	attempts := 0
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 3 {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		// Succeed on 3rd attempt
		resp := barsResponse{
			Symbol:    "AAPL",
			Timeframe: "1Hour",
			Count:     1,
			Bars: []barPayload{
				{Timestamp: "2024-01-02T10:00:00Z", Open: 100, High: 105, Low: 99, Close: 103, Volume: 1000},
			},
		}
		json.NewEncoder(w).Encode(resp)
	}))
	defer ts.Close()

	client := NewClient(ts.URL, &Config{MaxRetries: 3})
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	bars, err := client.GetBars(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("GetBars should succeed after retries: %v", err)
	}
	if len(bars) != 1 {
		t.Fatalf("expected 1 bar, got %d", len(bars))
	}
	if attempts < 3 {
		t.Errorf("expected at least 3 attempts, got %d", attempts)
	}
}

func TestGetBarData_MissingIndicators(t *testing.T) {
	barsResp := &barsResponse{
		Symbol:    "AAPL",
		Timeframe: "1Hour",
		Count:     1,
		Bars: []barPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Open: 100, High: 105, Low: 99, Close: 103, Volume: 1000},
		},
	}

	// Indicators return 404
	ts := newTestServer(barsResp, nil)
	defer ts.Close()

	client := NewClient(ts.URL, nil)
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	barData, err := client.GetBarData(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("GetBarData should succeed even without indicators: %v", err)
	}
	if len(barData) != 1 {
		t.Fatalf("expected 1 bar data entry, got %d", len(barData))
	}
	if len(barData[0].Indicators) != 0 {
		t.Errorf("expected empty indicators, got %d", len(barData[0].Indicators))
	}
}

func TestClearCache(t *testing.T) {
	barsResp := &barsResponse{
		Symbol:    "AAPL",
		Timeframe: "1Hour",
		Count:     1,
		Bars: []barPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Open: 100, High: 105, Low: 99, Close: 103, Volume: 1000},
		},
	}
	indResp := &indicatorsResponse{
		Symbol:    "AAPL",
		Timeframe: "1Hour",
		Count:     1,
		Rows: []indicatorPayload{
			{Timestamp: "2024-01-02T10:00:00Z", Indicators: map[string]float64{"atr_14": 2.5}},
		},
	}

	ts := newTestServer(barsResp, indResp)
	defer ts.Close()

	client := NewClient(ts.URL, &Config{EnableCache: true})
	start := mustTime("2024-01-02T00:00:00Z")
	end := mustTime("2024-01-03T00:00:00Z")

	_, err := client.GetBarData(context.Background(), "AAPL", "1Hour", start, end)
	if err != nil {
		t.Fatalf("first call failed: %v", err)
	}

	client.ClearCache()

	client.cacheMu.RLock()
	cacheLen := len(client.cache)
	client.cacheMu.RUnlock()
	if cacheLen != 0 {
		t.Errorf("expected empty cache after ClearCache, got %d entries", cacheLen)
	}
}

func TestParseTimestamp(t *testing.T) {
	tests := []struct {
		input string
		want  time.Time
	}{
		{"2024-01-02T10:00:00Z", mustTime("2024-01-02T10:00:00Z")},
		{"2024-01-02T10:00:00", time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)},
		{"2024-01-02 10:00:00", time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)},
		{"2024-01-02", time.Date(2024, 1, 2, 0, 0, 0, 0, time.UTC)},
	}

	for _, tt := range tests {
		got, err := parseTimestamp(tt.input)
		if err != nil {
			t.Errorf("parseTimestamp(%q): unexpected error: %v", tt.input, err)
			continue
		}
		if !got.Equal(tt.want) {
			t.Errorf("parseTimestamp(%q) = %v, want %v", tt.input, got, tt.want)
		}
	}
}

// Test that the client type implements the expected interface for consumers.
// This is a compile-time check only.
var _ interface {
	GetBars(context.Context, string, string, time.Time, time.Time) ([]types.Bar, error)
	GetIndicators(context.Context, string, string, time.Time, time.Time) (map[time.Time]types.IndicatorRow, error)
	GetBarData(context.Context, string, string, time.Time, time.Time) ([]types.BarData, error)
} = (*Client)(nil)
