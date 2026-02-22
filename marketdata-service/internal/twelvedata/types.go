package twelvedata

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/algomatic/marketdata-service/internal/db"
)

// TwelveDataAPIError represents a non-retryable error from the TwelveData API.
type TwelveDataAPIError struct {
	Code    int
	Message string
	Status  string
}

func (e *TwelveDataAPIError) Error() string {
	return fmt.Sprintf("TwelveData API error: code %d, status %s, message: %s", e.Code, e.Status, e.Message)
}

// IsTwelveDataAPIError checks whether err is (or wraps) a *TwelveDataAPIError.
func IsTwelveDataAPIError(err error) bool {
	var apiErr *TwelveDataAPIError
	return errors.As(err, &apiErr)
}

// IsTwelveDataNoDataError returns true if the error is a TwelveData "no data
// available" response. This happens for valid symbols when the requested date
// range falls on weekends, holidays, or outside trading hours — it should NOT
// be treated as an invalid-symbol error.
func IsTwelveDataNoDataError(err error) bool {
	var apiErr *TwelveDataAPIError
	if !errors.As(err, &apiErr) {
		return false
	}
	return strings.Contains(strings.ToLower(apiErr.Message), "no data is available")
}

// timeSeriesResponse is the TwelveData time_series API response.
type timeSeriesResponse struct {
	Meta    metaData      `json:"meta"`
	Values  []timeValue   `json:"values"`
	Status  string        `json:"status"`
	Message string        `json:"message,omitempty"`
}

type metaData struct {
	Symbol   string `json:"symbol"`
	Interval string `json:"interval"`
	Currency string `json:"currency"`
	Exchange string `json:"exchange"`
	Type     string `json:"type"`
}

// timeValue is a single OHLCV data point from TwelveData.
// All numeric fields are strings in the API response.
type timeValue struct {
	Datetime string `json:"datetime"`
	Open     string `json:"open"`
	High     string `json:"high"`
	Low      string `json:"low"`
	Close    string `json:"close"`
	Volume   string `json:"volume"`
}

// toOHLCVBar converts a TwelveData timeValue to a db.OHLCVBar.
func (v *timeValue) toOHLCVBar() (db.OHLCVBar, error) {
	ts, err := parseTimestamp(v.Datetime)
	if err != nil {
		return db.OHLCVBar{}, fmt.Errorf("parsing timestamp %q: %w", v.Datetime, err)
	}

	open, err := strconv.ParseFloat(v.Open, 64)
	if err != nil {
		return db.OHLCVBar{}, fmt.Errorf("parsing open %q: %w", v.Open, err)
	}

	high, err := strconv.ParseFloat(v.High, 64)
	if err != nil {
		return db.OHLCVBar{}, fmt.Errorf("parsing high %q: %w", v.High, err)
	}

	low, err := strconv.ParseFloat(v.Low, 64)
	if err != nil {
		return db.OHLCVBar{}, fmt.Errorf("parsing low %q: %w", v.Low, err)
	}

	closeVal, err := strconv.ParseFloat(v.Close, 64)
	if err != nil {
		return db.OHLCVBar{}, fmt.Errorf("parsing close %q: %w", v.Close, err)
	}

	// Volume may be "0" or empty for forex/commodity instruments.
	var volume int64
	if v.Volume != "" {
		vol, err := strconv.ParseFloat(v.Volume, 64)
		if err == nil {
			volume = int64(vol)
		}
	}

	return db.OHLCVBar{
		Timestamp: ts,
		Open:      open,
		High:      high,
		Low:       low,
		Close:     closeVal,
		Volume:    volume,
	}, nil
}

// parseTimestamp parses TwelveData datetime strings.
// Intraday: "2024-01-15 14:30:00", Daily: "2024-01-15".
func parseTimestamp(s string) (time.Time, error) {
	if len(s) <= 10 {
		return time.Parse("2006-01-02", s)
	}
	return time.Parse("2006-01-02 15:04:05", s)
}

// errorResponse captures TwelveData error payloads.
type errorResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Status  string `json:"status"`
}
