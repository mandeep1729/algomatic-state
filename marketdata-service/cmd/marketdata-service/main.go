package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/algomatic/marketdata-service/internal/alpaca"
	"github.com/algomatic/marketdata-service/internal/config"
	"github.com/algomatic/marketdata-service/internal/dataclient"
	"github.com/algomatic/marketdata-service/internal/redisbus"
	"github.com/algomatic/marketdata-service/internal/service"
)

func main() {
	configPath := flag.String("config", "", "Path to config.json")
	mode := flag.String("mode", "", "Run mode: service, listener, or both (overrides config)")
	flag.Parse()

	// Load configuration.
	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}

	if *mode != "" {
		cfg.Service.Mode = *mode
	}

	// Set up logger.
	logger := setupLogger(cfg.Service.LogLevel, cfg.Service.LogFile)
	logger.Info("Starting marketdata-service",
		"mode", cfg.Service.Mode,
		"interval_minutes", cfg.Service.IntervalMinutes,
		"redis_host", cfg.Redis.Host,
		"backend_url", cfg.Service.BackendURL,
	)

	// Set up graceful shutdown.
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Initialize gRPC client to data-service.
	dataServiceAddr := os.Getenv("DATA_SERVICE_ADDR")
	if dataServiceAddr == "" {
		dataServiceAddr = "localhost:50051"
	}
	logger.Info("Connecting to data-service", "addr", dataServiceAddr)

	dbClient, err := dataclient.NewClient(ctx, dataServiceAddr, logger)
	if err != nil {
		logger.Error("Failed to connect to data-service", "error", err)
		os.Exit(1)
	}
	defer dbClient.Close()

	// Initialize Alpaca client.
	alpacaClient := alpaca.NewClient(
		cfg.Alpaca.BaseURL,
		cfg.Alpaca.APIKey,
		cfg.Alpaca.SecretKey,
		logger,
	)

	// Initialize Redis bus.
	bus := redisbus.NewBus(
		cfg.Redis.Addr(),
		cfg.Redis.Password,
		cfg.Redis.DB,
		cfg.Redis.ChannelPrefix,
		logger,
	)
	defer bus.Close()

	// Health checks.
	if err := dbClient.HealthCheck(ctx); err != nil {
		logger.Error("Data service health check failed", "error", err)
		os.Exit(1)
	}
	if err := bus.HealthCheck(ctx); err != nil {
		logger.Error("Redis health check failed", "error", err)
		os.Exit(1)
	}
	logger.Info("Health checks passed")

	// Create the service.
	svc := service.NewService(dbClient, alpacaClient, logger)

	// Launch goroutines based on mode.
	var wg sync.WaitGroup

	switch cfg.Service.Mode {
	case "both":
		wg.Add(2)
		go func() {
			defer wg.Done()
			service.RunPeriodicLoop(ctx, svc,
				time.Duration(cfg.Service.IntervalMinutes)*time.Minute,
				cfg.Service.BackendURL,
				logger,
			)
		}()
		go func() {
			defer wg.Done()
			if err := service.RunListener(ctx, svc, bus, logger); err != nil {
				logger.Error("Listener error", "error", err)
			}
		}()

	case "service":
		wg.Add(1)
		go func() {
			defer wg.Done()
			service.RunPeriodicLoop(ctx, svc,
				time.Duration(cfg.Service.IntervalMinutes)*time.Minute,
				cfg.Service.BackendURL,
				logger,
			)
		}()

	case "listener":
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := service.RunListener(ctx, svc, bus, logger); err != nil {
				logger.Error("Listener error", "error", err)
			}
		}()
	}

	logger.Info("Service running", "mode", cfg.Service.Mode, "pid", os.Getpid())

	// Wait for shutdown signal.
	<-ctx.Done()
	logger.Info("Shutdown signal received, waiting for goroutines to finish...")
	wg.Wait()
	logger.Info("Shutdown complete")
}

func setupLogger(level, logFile string) *slog.Logger {
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
	if logFile != "" {
		f, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: cannot open log file %s: %v, falling back to stdout\n", logFile, err)
		} else {
			// Write to both stdout and file.
			writer = io.MultiWriter(os.Stdout, f)
		}
	}

	return slog.New(slog.NewTextHandler(writer, opts))
}
