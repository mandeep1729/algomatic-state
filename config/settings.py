"""Pydantic settings for configuration management."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


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
        default=None,
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
    echo: bool = Field(default=False, description="Echo SQL statements for debugging")

    @property
    def url(self) -> str:
        """Build PostgreSQL connection URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Build async PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


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

    alpaca: AlpacaConfig = Field(default_factory=AlpacaConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

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
