package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// Config holds all configuration for the marketdata service.
type Config struct {
	Database   DatabaseConfig   `json:"database"`
	Redis      RedisConfig      `json:"redis"`
	Alpaca     AlpacaConfig     `json:"alpaca"`
	TwelveData TwelveDataConfig `json:"twelvedata"`
	Service    ServiceConfig    `json:"service"`
}

// TwelveDataConfig holds TwelveData API credentials.
type TwelveDataConfig struct {
	APIKey string `json:"api_key"`
}

// DatabaseConfig holds PostgreSQL connection parameters.
type DatabaseConfig struct {
	Host     string `json:"host"`
	Port     int    `json:"port"`
	Name     string `json:"name"`
	User     string `json:"user"`
	Password string `json:"password"`
}

// ConnString builds a PostgreSQL connection string.
func (d DatabaseConfig) ConnString() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=disable",
		d.User, d.Password, d.Host, d.Port, d.Name,
	)
}

// RedisConfig holds Redis connection parameters.
type RedisConfig struct {
	Host          string `json:"host"`
	Port          int    `json:"port"`
	DB            int    `json:"db"`
	Password      string `json:"password"`
	ChannelPrefix string `json:"channel_prefix"`
}

// Addr returns host:port for Redis.
func (r RedisConfig) Addr() string {
	return fmt.Sprintf("%s:%d", r.Host, r.Port)
}

// AlpacaConfig holds Alpaca API credentials.
type AlpacaConfig struct {
	APIKey    string `json:"api_key"`
	SecretKey string `json:"secret_key"`
	BaseURL   string `json:"base_url"`
}

// ServiceConfig holds operational parameters.
type ServiceConfig struct {
	Mode            string `json:"mode"`
	IntervalMinutes int    `json:"interval_minutes"`
	LogLevel        string `json:"log_level"`
	LogFile         string `json:"log_file"`
	BackendURL      string `json:"backend_url"`
}

// Load reads config from a JSON file, then overrides with environment variables.
func Load(path string) (*Config, error) {
	cfg := defaults()

	if path != "" {
		data, err := os.ReadFile(path)
		if err != nil {
			if !os.IsNotExist(err) {
				return nil, fmt.Errorf("reading config file %s: %w", path, err)
			}
			// File not found is fine — we'll rely on env vars.
		} else {
			if err := json.Unmarshal(data, cfg); err != nil {
				return nil, fmt.Errorf("parsing config file %s: %w", path, err)
			}
		}
	}

	overrideFromEnv(cfg)

	if err := validate(cfg); err != nil {
		return nil, fmt.Errorf("config validation: %w", err)
	}

	return cfg, nil
}

func defaults() *Config {
	return &Config{
		Database: DatabaseConfig{
			Host: "localhost",
			Port: 5432,
			Name: "algomatic",
			User: "algomatic",
		},
		Redis: RedisConfig{
			Host:          "localhost",
			Port:          6379,
			ChannelPrefix: "algomatic",
		},
		Alpaca: AlpacaConfig{
			BaseURL: "https://data.alpaca.markets",
		},
		Service: ServiceConfig{
			Mode:            "both",
			IntervalMinutes: 60,
			LogLevel:        "info",
		},
	}
}

func overrideFromEnv(cfg *Config) {
	if v := os.Getenv("DB_HOST"); v != "" {
		cfg.Database.Host = v
	}
	if v := os.Getenv("DB_PORT"); v != "" {
		if p, err := strconv.Atoi(v); err == nil {
			cfg.Database.Port = p
		}
	}
	if v := os.Getenv("DB_NAME"); v != "" {
		cfg.Database.Name = v
	}
	if v := os.Getenv("DB_USER"); v != "" {
		cfg.Database.User = v
	}
	if v := os.Getenv("DB_PASSWORD"); v != "" {
		cfg.Database.Password = v
	}

	if v := os.Getenv("REDIS_HOST"); v != "" {
		cfg.Redis.Host = v
	}
	if v := os.Getenv("REDIS_PORT"); v != "" {
		if p, err := strconv.Atoi(v); err == nil {
			cfg.Redis.Port = p
		}
	}
	if v := os.Getenv("REDIS_PASSWORD"); v != "" {
		cfg.Redis.Password = v
	}

	if v := os.Getenv("ALPACA_API_KEY"); v != "" {
		cfg.Alpaca.APIKey = v
	}
	if v := os.Getenv("ALPACA_SECRET_KEY"); v != "" {
		cfg.Alpaca.SecretKey = v
	}

	if v := os.Getenv("TWELVEDATA_API_KEY"); v != "" {
		cfg.TwelveData.APIKey = v
	}

	if v := os.Getenv("SERVICE_MODE"); v != "" {
		cfg.Service.Mode = v
	}
	if v := os.Getenv("SERVICE_INTERVAL_MINUTES"); v != "" {
		if m, err := strconv.Atoi(v); err == nil {
			cfg.Service.IntervalMinutes = m
		}
	}
	if v := os.Getenv("SERVICE_LOG_LEVEL"); v != "" {
		cfg.Service.LogLevel = v
	}
	if v := os.Getenv("SERVICE_LOG_FILE"); v != "" {
		cfg.Service.LogFile = v
	}
	if v := os.Getenv("BACKEND_URL"); v != "" {
		cfg.Service.BackendURL = v
	}
}

func validate(cfg *Config) error {
	validModes := map[string]bool{"service": true, "listener": true, "both": true}
	if !validModes[cfg.Service.Mode] {
		return fmt.Errorf("invalid mode %q: must be service, listener, or both", cfg.Service.Mode)
	}

	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[strings.ToLower(cfg.Service.LogLevel)] {
		return fmt.Errorf("invalid log level %q: must be debug, info, warn, or error", cfg.Service.LogLevel)
	}

	if cfg.Service.IntervalMinutes < 1 {
		return fmt.Errorf("interval_minutes must be >= 1, got %d", cfg.Service.IntervalMinutes)
	}

	return nil
}
