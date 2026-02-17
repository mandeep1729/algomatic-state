package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// Config holds all configuration for the data service.
type Config struct {
	Database DatabaseConfig
	GRPC     GRPCConfig
	Log      LogConfig
}

// DatabaseConfig holds PostgreSQL connection parameters.
type DatabaseConfig struct {
	Host     string
	Port     int
	Name     string
	User     string
	Password string
	MaxConns int32
	MinConns int32
}

// ConnString builds a PostgreSQL connection string.
func (d DatabaseConfig) ConnString() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=disable",
		d.User, d.Password, d.Host, d.Port, d.Name,
	)
}

// GRPCConfig holds gRPC server parameters.
type GRPCConfig struct {
	Port int
}

// LogConfig holds logging parameters.
type LogConfig struct {
	Level string
}

// Load reads configuration from environment variables with DS_ prefix.
func Load() (*Config, error) {
	cfg := defaults()
	overrideFromEnv(cfg)

	if err := validate(cfg); err != nil {
		return nil, fmt.Errorf("config validation: %w", err)
	}

	return cfg, nil
}

func defaults() *Config {
	return &Config{
		Database: DatabaseConfig{
			Host:     "localhost",
			Port:     5432,
			Name:     "algomatic",
			User:     "algomatic",
			MaxConns: 25,
			MinConns: 2,
		},
		GRPC: GRPCConfig{
			Port: 50051,
		},
		Log: LogConfig{
			Level: "info",
		},
	}
}

func overrideFromEnv(cfg *Config) {
	if v := os.Getenv("DS_DB_HOST"); v != "" {
		cfg.Database.Host = v
	}
	if v := os.Getenv("DS_DB_PORT"); v != "" {
		if p, err := strconv.Atoi(v); err == nil {
			cfg.Database.Port = p
		}
	}
	if v := os.Getenv("DS_DB_NAME"); v != "" {
		cfg.Database.Name = v
	}
	if v := os.Getenv("DS_DB_USER"); v != "" {
		cfg.Database.User = v
	}
	if v := os.Getenv("DS_DB_PASSWORD"); v != "" {
		cfg.Database.Password = v
	}
	if v := os.Getenv("DS_DB_MAX_CONNS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.Database.MaxConns = int32(n)
		}
	}
	if v := os.Getenv("DS_DB_MIN_CONNS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.Database.MinConns = int32(n)
		}
	}
	if v := os.Getenv("DS_GRPC_PORT"); v != "" {
		if p, err := strconv.Atoi(v); err == nil {
			cfg.GRPC.Port = p
		}
	}
	if v := os.Getenv("DS_LOG_LEVEL"); v != "" {
		cfg.Log.Level = v
	}
}

func validate(cfg *Config) error {
	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[strings.ToLower(cfg.Log.Level)] {
		return fmt.Errorf("invalid log level %q: must be debug, info, warn, or error", cfg.Log.Level)
	}

	if cfg.Database.MaxConns < 1 {
		return fmt.Errorf("DS_DB_MAX_CONNS must be >= 1, got %d", cfg.Database.MaxConns)
	}

	if cfg.GRPC.Port < 1 || cfg.GRPC.Port > 65535 {
		return fmt.Errorf("DS_GRPC_PORT must be 1-65535, got %d", cfg.GRPC.Port)
	}

	return nil
}
