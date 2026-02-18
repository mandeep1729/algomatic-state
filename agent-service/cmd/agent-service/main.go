package main

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/algomatic/agent-service/internal/alpaca"
	"github.com/algomatic/agent-service/internal/config"
	"github.com/algomatic/agent-service/internal/db"
	"github.com/algomatic/agent-service/internal/repository"
	"github.com/algomatic/agent-service/internal/runner"
	stratResolver "github.com/algomatic/agent-service/internal/strategy"
	"github.com/algomatic/strats100/go-strats/pkg/backend"

	// Import go-strats strategy registry to register all 100 strategies
	_ "github.com/algomatic/strats100/go-strats/pkg/strategy"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}

	// Set up logger
	logger := setupLogger(cfg.Log.Level)
	logger.Info("Starting agent-service",
		"poll_interval_sec", cfg.Service.PollIntervalSec,
		"max_errors", cfg.Service.MaxConsecutiveErrors,
		"backend_url", cfg.Backend.URL,
		"alpaca_base_url", cfg.Alpaca.BaseURL,
	)

	// Set up graceful shutdown
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Create database pool
	pool, err := db.NewPool(
		ctx,
		cfg.Database.ConnString(),
		cfg.Database.MaxConns,
		cfg.Database.MinConns,
		logger,
	)
	if err != nil {
		logger.Error("Failed to create database pool", "error", err)
		os.Exit(1)
	}
	defer pool.Close()

	// Create repositories
	agentRepo := repository.NewAgentRepo(pool, logger)
	stratRepo := repository.NewStrategyRepo(pool, logger)
	orderRepo := repository.NewOrderRepo(pool, logger)
	activityRepo := repository.NewActivityRepo(pool, logger)

	// Create Alpaca trading client
	alpacaClient := alpaca.NewTradingClient(
		cfg.Alpaca.BaseURL,
		cfg.Alpaca.APIKey,
		cfg.Alpaca.SecretKey,
		logger,
	)

	// Create Python backend client (for bar data + indicators)
	backendClient := backend.NewClient(cfg.Backend.URL, &backend.Config{
		Logger: logger,
	})

	// Create strategy resolver
	resolver := stratResolver.NewResolver(stratRepo, logger)

	// Create orchestrator
	orch := runner.NewOrchestrator(
		agentRepo,
		orderRepo,
		activityRepo,
		resolver,
		alpacaClient,
		backendClient,
		time.Duration(cfg.Service.PollIntervalSec)*time.Second,
		cfg.Service.MaxConsecutiveErrors,
		logger,
	)

	// Start orchestrator in a goroutine
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		orch.Run(ctx)
	}()

	logger.Info("Agent service running", "pid", os.Getpid())

	// Wait for shutdown signal
	<-ctx.Done()
	logger.Info("Shutdown signal received, waiting for orchestrator to finish...")
	wg.Wait()
	logger.Info("Agent service shutdown complete")
}

func setupLogger(level string) *slog.Logger {
	var logLevel slog.Level
	switch strings.ToLower(level) {
	case "debug":
		logLevel = slog.LevelDebug
	case "warn":
		logLevel = slog.LevelWarn
	case "error":
		logLevel = slog.LevelError
	default:
		logLevel = slog.LevelInfo
	}

	opts := &slog.HandlerOptions{Level: logLevel}
	var writer io.Writer = os.Stdout

	return slog.New(slog.NewJSONHandler(writer, opts))
}
