package db

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Client wraps a pgxpool.Pool for database operations.
type Client struct {
	pool   *pgxpool.Pool
	logger *slog.Logger
}

// NewClient creates a new database client with a connection pool.
func NewClient(ctx context.Context, connStr string, logger *slog.Logger) (*Client, error) {
	if logger == nil {
		logger = slog.Default()
	}

	config, err := pgxpool.ParseConfig(connStr)
	if err != nil {
		return nil, fmt.Errorf("parsing connection string: %w", err)
	}

	config.MaxConns = 10
	config.MinConns = 2
	config.MaxConnLifetime = 30 * time.Minute
	config.MaxConnIdleTime = 5 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("creating connection pool: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("pinging database: %w", err)
	}

	logger.Info("Database connection pool established",
		"max_conns", config.MaxConns,
		"min_conns", config.MinConns,
	)

	return &Client{pool: pool, logger: logger}, nil
}

// Close shuts down the connection pool.
func (c *Client) Close() {
	c.pool.Close()
	c.logger.Info("Database connection pool closed")
}

// HealthCheck verifies database connectivity.
func (c *Client) HealthCheck(ctx context.Context) error {
	return c.pool.Ping(ctx)
}
