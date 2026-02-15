"""Pydantic settings for configuration management."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class FinnhubConfig(BaseSettings):
    """Finnhub API configuration."""

    model_config = SettingsConfigDict(env_prefix="FINNHUB_")

    api_key: str = Field(default="", description="Finnhub API key")
    rate_limit: int = Field(default=60, description="API calls per minute (free tier)")
    max_retries: int = Field(default=3, description="Maximum retry attempts on failure")


class AlpacaConfig(BaseSettings):
    """Alpaca API configuration."""

    model_config = SettingsConfigDict(env_prefix="ALPACA_")

    api_key: str = Field(default="", description="Alpaca API key")
    secret_key: str = Field(default="", description="Alpaca secret key")
    paper: bool = Field(default=True, description="Use paper trading endpoint")
    base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca API base URL",
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def set_base_url(cls, v: str, info) -> str:
        """Set base URL based on paper mode if not explicitly set."""
        if v:
            return v
        # This will be called during validation
        return "https://paper-api.alpaca.markets"


class DataConfig(BaseSettings):
    """Data loading configuration."""

    model_config = SettingsConfigDict(env_prefix="DATA_")

    cache_dir: Path = Field(
        default=Path("data/cache"),
        description="Directory for cached data",
    )
    raw_dir: Path = Field(
        default=Path("data/raw"),
        description="Directory for raw data files",
    )
    default_timeframe: str = Field(
        default="1Min",
        description="Default bar timeframe",
    )
    max_cache_age_hours: int = Field(
        default=24,
        description="Maximum cache age in hours",
    )
    history_months: int = Field(
        default=3,
        description="How far back to fetch historical data from Alpaca (in months)",
    )


class FeatureConfig(BaseSettings):
    """Feature engineering configuration."""

    model_config = SettingsConfigDict(env_prefix="FEATURE_")

    default_features: list[str] = Field(
        default=[
            "r1", "r5", "r15", "r60",
            "rv_15", "rv_60",
            "vol_z_60", "dvol_z_60",
            "clv", "body_ratio",
            "dist_vwap_60", "breakout_20",
            "tod_sin", "tod_cos",
        ],
        description="Default feature set to compute",
    )
    lookback_buffer: int = Field(
        default=100,
        description="Extra lookback rows to include for feature computation",
    )


class StateConfig(BaseSettings):
    """State representation configuration."""

    model_config = SettingsConfigDict(env_prefix="STATE_")

    window_size: int = Field(default=60, description="Temporal window size")
    stride: int = Field(default=1, description="Window stride")
    latent_dim: int = Field(default=16, description="Autoencoder latent dimension")
    n_regimes: int = Field(default=5, description="Number of regimes for clustering")
    normalization_method: Literal["zscore", "robust"] = Field(
        default="zscore",
        description="Normalization method",
    )
    clip_std: float = Field(default=3.0, description="Standard deviations for clipping")


class StrategyConfig(BaseSettings):
    """Trading strategy configuration."""

    model_config = SettingsConfigDict(env_prefix="STRATEGY_")

    momentum_feature: str = Field(
        default="r5",
        description="Feature to use for momentum signal",
    )
    long_threshold: float = Field(
        default=0.001,
        description="Momentum threshold for long signals",
    )
    short_threshold: float = Field(
        default=-0.001,
        description="Momentum threshold for short signals",
    )
    min_regime_sharpe: float = Field(
        default=0.0,
        description="Minimum regime Sharpe ratio for trading",
    )
    enable_regime_filter: bool = Field(
        default=True,
        description="Enable regime-based trade filtering",
    )
    enable_pattern_matching: bool = Field(
        default=True,
        description="Enable historical pattern matching",
    )
    enable_dynamic_sizing: bool = Field(
        default=True,
        description="Enable dynamic position sizing",
    )


class BacktestConfig(BaseSettings):
    """Backtesting configuration."""

    model_config = SettingsConfigDict(env_prefix="BACKTEST_")

    initial_capital: float = Field(
        default=100000.0,
        description="Initial portfolio capital",
    )
    commission_per_share: float = Field(
        default=0.005,
        description="Commission per share",
    )
    slippage_bps: float = Field(
        default=5.0,
        description="Slippage in basis points",
    )
    walk_forward_train_days: int = Field(
        default=180,
        description="Walk-forward training period in days",
    )
    walk_forward_test_days: int = Field(
        default=30,
        description="Walk-forward test period in days",
    )


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = Field(default="INFO", description="Log level")
    format: Literal["json", "text"] = Field(
        default="json",
        description="Log format",
    )
    file: Path | None = Field(
        default=Path("logs/app.log"),
        description="Log file path (None for stdout only)",
    )
    rotate_size_mb: int = Field(
        default=10,
        description="Log file rotation size in MB",
    )
    retain_count: int = Field(
        default=5,
        description="Number of rotated log files to retain",
    )


class DatabaseConfig(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="algomatic", description="Database name")
    user: str = Field(default="algomatic", description="Database user")
    password: str = Field(default="", description="Database password")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max pool overflow connections")
    pool_recycle: int = Field(default=3600, description="Recycle connections after N seconds (avoids stale connections)")
    pool_timeout: int = Field(default=30, description="Seconds to wait for a connection from pool before timeout")
    echo: bool = Field(default=False, description="Echo SQL statements for debugging")

    @property
    def url(self) -> str:
        """Build PostgreSQL connection URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Build async PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisConfig(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: str = Field(default="", description="Redis password")
    pool_size: int = Field(default=10, description="Connection pool size")
    channel_prefix: str = Field(default="algomatic", description="Prefix for Redis pub/sub channels")
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")

    @property
    def url(self) -> str:
        """Build Redis connection URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class MessagingConfig(BaseSettings):
    """Messaging system configuration."""

    model_config = SettingsConfigDict(env_prefix="MESSAGING_")

    backend: Literal["memory", "redis"] = Field(
        default="memory",
        description="Message bus backend: 'memory' for in-process, 'redis' for cross-process",
    )


class ChecksConfig(BaseSettings):
    """Behavioral checks configuration for campaign leg evaluation.

    severity_overrides maps check codes to custom severity labels.
    Supported severities: info, warn, critical.
    Escalated variants use the suffix '_escalated' (e.g. RS002_escalated).

    Defaults when no override is set:
        RS001        = critical
        RS002        = warn      (RS002_escalated = critical)
        RS003        = warn      (RS003_escalated = critical)
        RS004        = warn
    """

    model_config = SettingsConfigDict(env_prefix="CHECKS_")

    atr_period: int = Field(default=14, description="ATR lookback period (standard = 14)")
    min_rr_ratio: float = Field(default=1.5, description="Minimum acceptable risk:reward ratio")
    max_risk_per_trade_pct: float = Field(
        default=2.0,
        description="Maximum risk per trade as % of account balance",
    )
    min_stop_atr_multiple: float = Field(
        default=0.5,
        description="Minimum stop distance as multiple of ATR",
    )
    severity_overrides: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Override severity per check code, e.g. "
            '{"RS001": "critical", "RS002_escalated": "critical"}'
        ),
    )


class ReviewerConfig(BaseSettings):
    """Reviewer service configuration."""

    model_config = SettingsConfigDict(env_prefix="REVIEWER_")

    enabled: bool = Field(default=True, description="Enable reviewer checks")
    recheck_lookback_days: int = Field(
        default=30,
        description="Days to look back when re-running checks after risk pref changes",
    )


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="AUTH_")

    google_client_id: str = Field(default="", description="Google OAuth client ID")
    jwt_secret_key: str = Field(default="change-me-in-production", description="JWT signing secret")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_hours: int = Field(default=24, description="JWT token expiry in hours")
    dev_mode: bool = Field(default=False, description="Bypass OAuth and use dev user (user_id=1)")

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Warn if using default JWT secret (production safety check)."""
        if v == "change-me-in-production":
            import logging
            logging.getLogger(__name__).warning(
                "AUTH_JWT_SECRET_KEY is set to the default value. "
                "Set a strong secret in .env for production use."
            )
        return v


class ServerConfig(BaseSettings):
    """Backend server configuration."""

    model_config = SettingsConfigDict(env_prefix="SERVER_")

    port: int = Field(default=8729, description="Backend server port")
    host: str = Field(default="0.0.0.0", description="Backend server host")


class Settings(BaseSettings):
    """Main settings class combining all configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "paper", "production"] = Field(
        default="development",
        description="Environment type",
    )

    finnhub: FinnhubConfig = Field(default_factory=FinnhubConfig)
    alpaca: AlpacaConfig = Field(default_factory=AlpacaConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    checks: ChecksConfig = Field(default_factory=ChecksConfig)
    reviewer: ReviewerConfig = Field(default_factory=ReviewerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """Enforce safety invariants for production environments."""
        if self.environment == "production":
            if self.auth.jwt_secret_key == "change-me-in-production":
                raise ValueError(
                    "AUTH_JWT_SECRET_KEY must be changed from the default in production"
                )
            if self.auth.dev_mode:
                raise ValueError(
                    "AUTH_DEV_MODE must not be True in production"
                )
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Settings":
        """Load settings from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Settings instance
        """
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            config_dict = yaml.safe_load(f) or {}

        return cls(**config_dict)

    def to_yaml(self, path: str | Path) -> None:
        """Save settings to YAML file.

        Args:
            path: Path to save configuration
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding secrets
        config_dict = self.model_dump(
            exclude={"alpaca": {"api_key", "secret_key"}},
        )

        with open(path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance
    """
    # Try to load from config file first
    config_path = Path("config/trading.yaml")
    if config_path.exists():
        return Settings.from_yaml(config_path)

    return Settings()
