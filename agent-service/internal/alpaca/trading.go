package alpaca

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"
)

const (
	maxRetries  = 3
	httpTimeout = 30 * time.Second
)

// Clock represents the Alpaca market clock response.
type Clock struct {
	Timestamp time.Time `json:"timestamp"`
	IsOpen    bool      `json:"is_open"`
	NextOpen  time.Time `json:"next_open"`
	NextClose time.Time `json:"next_close"`
}

// Account represents the Alpaca account response.
type Account struct {
	ID               string  `json:"id"`
	Status           string  `json:"status"`
	Currency         string  `json:"currency"`
	Cash             string  `json:"cash"`
	PortfolioValue   string  `json:"portfolio_value"`
	BuyingPower      string  `json:"buying_power"`
	PatternDayTrader bool    `json:"pattern_day_trader"`
	Equity           string  `json:"equity"`
}

// Position represents an Alpaca position.
type Position struct {
	AssetID      string `json:"asset_id"`
	Symbol       string `json:"symbol"`
	Qty          string `json:"qty"`
	Side         string `json:"side"`
	AvgEntryPrice string `json:"avg_entry_price"`
	MarketValue  string `json:"market_value"`
	UnrealizedPL string `json:"unrealized_pl"`
}

// OrderRequest is the payload for submitting an order.
type OrderRequest struct {
	Symbol        string       `json:"symbol"`
	Qty           string       `json:"qty,omitempty"`
	Notional      string       `json:"notional,omitempty"`
	Side          string       `json:"side"`
	Type          string       `json:"type"`
	TimeInForce   string       `json:"time_in_force"`
	LimitPrice    string       `json:"limit_price,omitempty"`
	StopPrice     string       `json:"stop_price,omitempty"`
	ClientOrderID string       `json:"client_order_id,omitempty"`
	OrderClass    string       `json:"order_class,omitempty"`
	TakeProfit    *TakeProfit  `json:"take_profit,omitempty"`
	StopLoss      *StopLoss    `json:"stop_loss,omitempty"`
}

// TakeProfit specifies the take profit for bracket orders.
type TakeProfit struct {
	LimitPrice string `json:"limit_price"`
}

// StopLoss specifies the stop loss for bracket orders.
type StopLoss struct {
	StopPrice  string `json:"stop_price"`
	LimitPrice string `json:"limit_price,omitempty"`
}

// OrderResponse represents an Alpaca order response.
type OrderResponse struct {
	ID            string     `json:"id"`
	ClientOrderID string     `json:"client_order_id"`
	Status        string     `json:"status"`
	Symbol        string     `json:"symbol"`
	Side          string     `json:"side"`
	Qty           string     `json:"qty"`
	FilledQty     string     `json:"filled_qty"`
	FilledAvgPrice string    `json:"filled_avg_price"`
	Type          string     `json:"type"`
	TimeInForce   string     `json:"time_in_force"`
	CreatedAt     time.Time  `json:"created_at"`
	FilledAt      *time.Time `json:"filled_at"`
}

// TradingClient is a thin REST client for the Alpaca Trading API v2.
type TradingClient struct {
	baseURL    string
	apiKey     string
	secretKey  string
	httpClient *http.Client
	logger     *slog.Logger
}

// NewTradingClient creates a new Alpaca trading client.
func NewTradingClient(baseURL, apiKey, secretKey string, logger *slog.Logger) *TradingClient {
	return &TradingClient{
		baseURL:   baseURL,
		apiKey:    apiKey,
		secretKey: secretKey,
		httpClient: &http.Client{
			Timeout: httpTimeout,
		},
		logger: logger,
	}
}

// GetClock returns the current market clock.
func (c *TradingClient) GetClock(ctx context.Context) (*Clock, error) {
	body, err := c.doRequest(ctx, http.MethodGet, "/v2/clock", nil)
	if err != nil {
		return nil, fmt.Errorf("GetClock: %w", err)
	}
	var clock Clock
	if err := json.Unmarshal(body, &clock); err != nil {
		return nil, fmt.Errorf("GetClock: decoding: %w", err)
	}
	return &clock, nil
}

// GetAccount returns the current account information.
func (c *TradingClient) GetAccount(ctx context.Context) (*Account, error) {
	body, err := c.doRequest(ctx, http.MethodGet, "/v2/account", nil)
	if err != nil {
		return nil, fmt.Errorf("GetAccount: %w", err)
	}
	var account Account
	if err := json.Unmarshal(body, &account); err != nil {
		return nil, fmt.Errorf("GetAccount: decoding: %w", err)
	}
	return &account, nil
}

// GetPosition returns the position for a symbol, or nil if no position.
func (c *TradingClient) GetPosition(ctx context.Context, symbol string) (*Position, error) {
	body, err := c.doRequest(ctx, http.MethodGet, "/v2/positions/"+symbol, nil)
	if err != nil {
		// 404 means no position
		return nil, nil
	}
	var pos Position
	if err := json.Unmarshal(body, &pos); err != nil {
		return nil, fmt.Errorf("GetPosition: decoding: %w", err)
	}
	return &pos, nil
}

// ClosePosition closes the entire position for a symbol.
func (c *TradingClient) ClosePosition(ctx context.Context, symbol string) error {
	_, err := c.doRequest(ctx, http.MethodDelete, "/v2/positions/"+symbol, nil)
	if err != nil {
		return fmt.Errorf("ClosePosition %s: %w", symbol, err)
	}
	c.logger.Info("Closed position", "symbol", symbol)
	return nil
}

// SubmitOrder submits an order to Alpaca.
func (c *TradingClient) SubmitOrder(ctx context.Context, req *OrderRequest) (*OrderResponse, error) {
	payload, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("SubmitOrder: encoding: %w", err)
	}
	body, err := c.doRequest(ctx, http.MethodPost, "/v2/orders", payload)
	if err != nil {
		return nil, fmt.Errorf("SubmitOrder: %w", err)
	}
	var resp OrderResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("SubmitOrder: decoding: %w", err)
	}
	c.logger.Info("Submitted order",
		"order_id", resp.ID, "symbol", req.Symbol, "side", req.Side,
		"type", req.Type, "qty", req.Qty,
	)
	return &resp, nil
}

// GetOrder returns the current state of an order.
func (c *TradingClient) GetOrder(ctx context.Context, orderID string) (*OrderResponse, error) {
	body, err := c.doRequest(ctx, http.MethodGet, "/v2/orders/"+orderID, nil)
	if err != nil {
		return nil, fmt.Errorf("GetOrder %s: %w", orderID, err)
	}
	var resp OrderResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("GetOrder: decoding: %w", err)
	}
	return &resp, nil
}

// CancelOrder cancels an order by ID.
func (c *TradingClient) CancelOrder(ctx context.Context, orderID string) error {
	_, err := c.doRequest(ctx, http.MethodDelete, "/v2/orders/"+orderID, nil)
	if err != nil {
		return fmt.Errorf("CancelOrder %s: %w", orderID, err)
	}
	c.logger.Info("Cancelled order", "order_id", orderID)
	return nil
}

// doRequest executes an HTTP request with retries and exponential backoff.
func (c *TradingClient) doRequest(ctx context.Context, method, path string, payload []byte) ([]byte, error) {
	url := c.baseURL + path
	var lastErr error

	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * 500 * time.Millisecond
			c.logger.Debug("Retrying request",
				"method", method, "path", path, "attempt", attempt, "backoff", backoff,
			)
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		var bodyReader io.Reader
		if payload != nil {
			bodyReader = bytes.NewReader(payload)
		}

		req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
		if err != nil {
			return nil, fmt.Errorf("creating request: %w", err)
		}
		req.Header.Set("APCA-API-KEY-ID", c.apiKey)
		req.Header.Set("APCA-API-SECRET-KEY", c.secretKey)
		req.Header.Set("Accept", "application/json")
		if payload != nil {
			req.Header.Set("Content-Type", "application/json")
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("HTTP request failed: %w", err)
			c.logger.Warn("Request failed", "method", method, "path", path, "attempt", attempt, "error", err)
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
		case resp.StatusCode == 404:
			return nil, fmt.Errorf("not found: %s %s", method, path)
		case resp.StatusCode == 422:
			return nil, fmt.Errorf("unprocessable entity: %s", string(body))
		case resp.StatusCode == 429:
			lastErr = fmt.Errorf("rate limited (429)")
			c.logger.Warn("Rate limit hit, retrying", "attempt", attempt)
			continue
		case resp.StatusCode >= 500:
			lastErr = fmt.Errorf("server error (status %d)", resp.StatusCode)
			c.logger.Warn("Server error, retrying", "status", resp.StatusCode, "attempt", attempt)
			continue
		default:
			return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
		}
	}

	return nil, fmt.Errorf("all %d retries exhausted: %w", maxRetries, lastErr)
}
