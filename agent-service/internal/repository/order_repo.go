package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// AgentOrderRow represents a row in the agent_orders table.
type AgentOrderRow struct {
	ID              int64
	AgentID         int
	AccountID       int
	Symbol          string
	Side            string
	Quantity        float64
	OrderType       string
	LimitPrice      *float64
	StopPrice       *float64
	ClientOrderID   string
	BrokerOrderID   *string
	Status          string
	FilledQuantity  *float64
	FilledAvgPrice  *float64
	SignalDirection  *string
	SignalMetadata  json.RawMessage
	RiskViolations  json.RawMessage
	SubmittedAt     *time.Time
	FilledAt        *time.Time
}

// OrderRepo provides database access for agent orders.
type OrderRepo struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewOrderRepo creates a new OrderRepo.
func NewOrderRepo(pool *pgxpool.Pool, logger *slog.Logger) *OrderRepo {
	return &OrderRepo{pool: pool, logger: logger}
}

// CreateOrder inserts a new order row and returns the generated ID.
func (r *OrderRepo) CreateOrder(ctx context.Context, o *AgentOrderRow) (int64, error) {
	var id int64
	err := r.pool.QueryRow(ctx, `
		INSERT INTO agent_orders (
			agent_id, account_id, symbol, side, quantity, order_type,
			limit_price, stop_price, client_order_id, broker_order_id,
			status, signal_direction, signal_metadata, risk_violations,
			submitted_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
		RETURNING id
	`,
		o.AgentID, o.AccountID, o.Symbol, o.Side, o.Quantity, o.OrderType,
		o.LimitPrice, o.StopPrice, o.ClientOrderID, o.BrokerOrderID,
		o.Status, o.SignalDirection, o.SignalMetadata, o.RiskViolations,
		o.SubmittedAt,
	).Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("creating order: %w", err)
	}

	r.logger.Info("Created order",
		"order_id", id, "agent_id", o.AgentID, "symbol", o.Symbol, "side", o.Side,
	)
	return id, nil
}

// UpdateOrder updates status and fill information for an order.
func (r *OrderRepo) UpdateOrder(
	ctx context.Context,
	id int64,
	status string,
	filledQty *float64,
	filledAvgPrice *float64,
	filledAt *time.Time,
) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE agent_orders
		SET status = $2, filled_quantity = $3, filled_avg_price = $4, filled_at = $5
		WHERE id = $1
	`, id, status, filledQty, filledAvgPrice, filledAt)
	if err != nil {
		return fmt.Errorf("updating order %d: %w", id, err)
	}
	return nil
}
