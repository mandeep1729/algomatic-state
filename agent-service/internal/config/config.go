package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// Config holds all configuration for the agent service.
type Config struct {
	Database DatabaseConfig
	Alpaca   AlpacaConfig
	Backend  BackendConfig
	Service  ServiceConfig
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

// AlpacaConfig holds Alpaca Trading API credentials.
type AlpacaConfig struct {
	APIKey    string
	SecretKey string
	BaseURL   string
}

// BackendConfig holds Python backend API configuration.
type BackendConfig struct {
	URL string
}

// ServiceConfig holds service-level parameters.
type ServiceConfig struct {
	PollIntervalSec     int
	MaxConsecutiveErrors int
}

// LogConfig holds logging parameters.
type LogConfig struct {
	Level string
}

// Load reads configuration from environment variables with AS_ prefix.
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
			MaxConns: 10,
			MinConns: 2,
		},
		Alpaca: AlpacaConfig{
			BaseURL: "https://paper-api.alpaca.markets",
		},
		Backend: BackendConfig{
			URL: "http://localhost:8729",
		},
		Service: ServiceConfig{
			PollIntervalSec:     30,
			MaxConsecutiveErrors: 5,
		},
		Log: LogConfig{
			Level: "info",
		},
	}
}

func overrideFromEnv(cfg *Config) {
	if v := os.Getenv("AS_DB_HOST"); v != "" {
		cfg.Database.Host = v
	}
	if v := os.Getenv("AS_DB_PORT"); v != "" {
		if p, err := strconv.Atoi(v); err == nil {
			cfg.Database.Port = p
		}
	}
	if v := os.Getenv("AS_DB_NAME"); v != "" {
		cfg.Database.Name = v
	}
	if v := os.Getenv("AS_DB_USER"); v != "" {
		cfg.Database.User = v
	}
	if v := os.Getenv("AS_DB_PASSWORD"); v != "" {
		cfg.Database.Password = v
	}
	if v := os.Getenv("AS_DB_MAX_CONNS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.Database.MaxConns = int32(n)
		}
	}
	if v := os.Getenv("AS_DB_MIN_CONNS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.Database.MinConns = int32(n)
		}
	}

	if v := os.Getenv("ALPACA_API_KEY"); v != "" {
		cfg.Alpaca.APIKey = v
	}
	if v := os.Getenv("ALPACA_SECRET_KEY"); v != "" {
		cfg.Alpaca.SecretKey = v
	}
	if v := os.Getenv("ALPACA_BASE_URL"); v != "" {
		cfg.Alpaca.BaseURL = v
	}

	if v := os.Getenv("BACKEND_URL"); v != "" {
		cfg.Backend.URL = v
	}

	if v := os.Getenv("AS_POLL_INTERVAL_SEC"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.Service.PollIntervalSec = n
		}
	}
	if v := os.Getenv("AS_MAX_CONSECUTIVE_ERRORS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.Service.MaxConsecutiveErrors = n
		}
	}

	if v := os.Getenv("AS_LOG_LEVEL"); v != "" {
		cfg.Log.Level = v
	}
}

func validate(cfg *Config) error {
	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[strings.ToLower(cfg.Log.Level)] {
		return fmt.Errorf("invalid log level %q: must be debug, info, warn, or error", cfg.Log.Level)
	}

	if cfg.Database.MaxConns < 1 {
		return fmt.Errorf("AS_DB_MAX_CONNS must be >= 1, got %d", cfg.Database.MaxConns)
	}

	if cfg.Alpaca.APIKey == "" {
		return fmt.Errorf("ALPACA_API_KEY is required")
	}
	if cfg.Alpaca.SecretKey == "" {
		return fmt.Errorf("ALPACA_SECRET_KEY is required")
	}

	return nil
}
