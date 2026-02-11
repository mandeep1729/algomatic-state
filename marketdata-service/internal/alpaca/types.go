package alpaca

import "time"

// Bar represents a single OHLCV bar from the Alpaca API.
type Bar struct {
	Timestamp  time.Time `json:"t"`
	Open       float64   `json:"o"`
	High       float64   `json:"h"`
	Low        float64   `json:"l"`
	Close      float64   `json:"c"`
	Volume     int64     `json:"v"`
	TradeCount int       `json:"n"`
	VWAP       float64   `json:"vw"`
}

// barsResponse is the raw Alpaca v2 bars API response.
type barsResponse struct {
	Bars          []Bar  `json:"bars"`
	Symbol        string `json:"symbol"`
	NextPageToken string `json:"next_page_token"`
}
