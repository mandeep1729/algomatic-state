package main

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"

	"github.com/algomatic/data-service/internal/config"
	"github.com/algomatic/data-service/internal/db"
	"github.com/algomatic/data-service/internal/repository"
	"github.com/algomatic/data-service/internal/server"
	pb "github.com/algomatic/data-service/proto/gen/go/market/v1"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Load configuration.
	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load config: %v\n", err)
		os.Exit(1)
	}

	// Set up structured logger.
	logLevel := slog.LevelInfo
	switch strings.ToLower(cfg.Log.Level) {
	case "debug":
		logLevel = slog.LevelDebug
	case "warn":
		logLevel = slog.LevelWarn
	case "error":
		logLevel = slog.LevelError
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: logLevel}))
	slog.SetDefault(logger)

	logger.Info("Starting data-service",
		"grpc_port", cfg.GRPC.Port,
		"db_host", cfg.Database.Host,
		"db_name", cfg.Database.Name,
		"max_conns", cfg.Database.MaxConns,
	)

	// Create database pool.
	pool, err := db.NewPool(ctx, cfg.Database.ConnString(), cfg.Database.MaxConns, cfg.Database.MinConns, logger)
	if err != nil {
		logger.Error("Failed to create database pool", "error", err)
		os.Exit(1)
	}
	defer pool.Close()

	// Create repositories.
	tickerRepo := repository.NewTickerRepo(pool, logger)
	barRepo := repository.NewBarRepo(pool, logger)
	featureRepo := repository.NewFeatureRepo(pool, logger)
	syncLogRepo := repository.NewSyncLogRepo(pool, logger)

	// Create gRPC server.
	grpcServer := grpc.NewServer()
	marketServer := server.NewMarketServer(tickerRepo, barRepo, featureRepo, syncLogRepo, logger)
	pb.RegisterMarketDataServiceServer(grpcServer, marketServer)

	// Register health check.
	healthServer := health.NewServer()
	healthpb.RegisterHealthServer(grpcServer, healthServer)
	healthServer.SetServingStatus("market.v1.MarketDataService", healthpb.HealthCheckResponse_SERVING)

	// Register reflection for debugging.
	reflection.Register(grpcServer)

	// Start listening.
	addr := fmt.Sprintf(":%d", cfg.GRPC.Port)
	lis, err := net.Listen("tcp", addr)
	if err != nil {
		logger.Error("Failed to listen", "addr", addr, "error", err)
		os.Exit(1)
	}

	// Handle graceful shutdown.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigCh
		logger.Info("Received signal, shutting down", "signal", sig)
		healthServer.SetServingStatus("market.v1.MarketDataService", healthpb.HealthCheckResponse_NOT_SERVING)
		grpcServer.GracefulStop()
		cancel()
	}()

	logger.Info("gRPC server listening", "addr", addr)
	if err := grpcServer.Serve(lis); err != nil {
		logger.Error("gRPC server failed", "error", err)
		os.Exit(1)
	}

	logger.Info("Data service stopped")
}
