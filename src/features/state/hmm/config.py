"""Configuration loading for state vector models.

Handles loading and validation of:
- Feature specifications (YAML)
- Model configurations
- Per-timeframe settings
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from src.features.state.hmm.contracts import VALID_TIMEFRAMES

logger = logging.getLogger(__name__)


# Default feature set for state vector training (from implementation plan)
DEFAULT_FEATURE_SET = [
    "clv",
    "pullback_depth",
    "r5",
    "r15",
    "r60",
    "vwap_60",
    "dist_vwap_60",
    "tod_sin",
    "macd",
    "stoch_k",
    "sma_20",
    "ema_20",
    "vol_of_vol",
    "vol_z_60",
    "range_1",
    "rv_15",
    "rv_60",
    "relvol_60",
    "range_z_60",
    "bb_middle",
    "bb_width",
]


class FeatureSpecEntry(BaseModel):
    """Specification for a single feature."""

    name: str = Field(..., description="Feature column name")
    description: str = Field(default="", description="Human-readable description")
    lookback: int = Field(default=1, ge=1, description="Minimum lookback in bars")
    group: str = Field(default="misc", description="Feature category group")
    scaling: Literal["robust", "standard", "none"] = Field(
        default="robust", description="Scaling method"
    )
    differencing: bool = Field(
        default=False, description="Apply first differencing for stationarity"
    )
    clip_std: Optional[float] = Field(
        default=5.0, ge=0, description="Clip outliers beyond N std devs"
    )


class TimeframeConfig(BaseModel):
    """Per-timeframe model configuration."""

    n_states: int = Field(default=8, ge=2, le=32, description="Number of HMM states")
    latent_dim: int = Field(default=8, ge=2, le=32, description="Latent dimension")
    feature_budget: Optional[int] = Field(
        default=None, ge=1, description="Max features for this timeframe"
    )
    features_include: list[str] = Field(
        default_factory=list, description="Additional features to include"
    )
    features_exclude: list[str] = Field(
        default_factory=list, description="Features to exclude"
    )
    covariance_type: Literal["full", "diag", "tied", "spherical"] = Field(
        default="diag", description="HMM covariance type"
    )
    min_dwell_bars: int = Field(
        default=3, ge=1, description="Minimum dwell time for anti-chatter"
    )
    p_switch_threshold: float = Field(
        default=0.6, ge=0.5, le=1.0, description="Probability threshold for state switch"
    )


class StateVectorConfig(BaseModel):
    """Complete state vector model configuration."""

    # Global settings
    encoder_type: Literal["pca", "temporal_vae", "temporal_dae"] = Field(
        default="pca", description="Encoder architecture"
    )
    scaler_type: Literal["robust", "standard", "yeo_johnson"] = Field(
        default="robust", description="Feature scaling method"
    )
    ood_threshold: float = Field(
        default=-50.0, description="Log-likelihood threshold for OOD detection"
    )
    state_ttl_bars: int = Field(
        default=1, ge=1, description="State validity TTL in bars"
    )

    # Feature settings
    base_features: list[str] = Field(
        default_factory=lambda: DEFAULT_FEATURE_SET.copy(),
        description="Base feature set",
    )
    feature_specs: dict[str, FeatureSpecEntry] = Field(
        default_factory=dict, description="Per-feature specifications"
    )

    # Per-timeframe overrides
    timeframe_configs: dict[str, TimeframeConfig] = Field(
        default_factory=dict, description="Per-timeframe configurations"
    )

    @field_validator("timeframe_configs", mode="before")
    @classmethod
    def validate_timeframes(cls, v):
        if v is None:
            return {}
        for tf in v:
            if tf not in VALID_TIMEFRAMES:
                raise ValueError(
                    f"Invalid timeframe '{tf}'. Valid options: {VALID_TIMEFRAMES}"
                )
        return v

    def get_timeframe_config(self, timeframe: str) -> TimeframeConfig:
        """Get configuration for a specific timeframe.

        Returns defaults if no override is specified.
        """
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. Valid options: {VALID_TIMEFRAMES}"
            )
        return self.timeframe_configs.get(timeframe, TimeframeConfig())

    def get_features_for_timeframe(self, timeframe: str) -> list[str]:
        """Get the feature list for a specific timeframe.

        Applies includes, excludes, and budget constraints.
        """
        tf_config = self.get_timeframe_config(timeframe)

        features = set(self.base_features)
        features.update(tf_config.features_include)
        features -= set(tf_config.features_exclude)

        feature_list = sorted(features)

        if tf_config.feature_budget and len(feature_list) > tf_config.feature_budget:
            feature_list = feature_list[: tf_config.feature_budget]

        return feature_list


@dataclass
class StateVectorFeatureSpec:
    """Loaded and validated feature specification.

    This is the runtime representation used by the training pipeline.
    """

    features: list[FeatureSpecEntry]
    timeframe: str
    config: StateVectorConfig

    @property
    def feature_names(self) -> list[str]:
        """Return ordered list of feature names."""
        return [f.name for f in self.features]

    @property
    def max_lookback(self) -> int:
        """Return maximum lookback required across all features."""
        return max((f.lookback for f in self.features), default=1)

    def get_feature(self, name: str) -> Optional[FeatureSpecEntry]:
        """Get feature specification by name."""
        for f in self.features:
            if f.name == name:
                return f
        return None


def load_feature_spec(
    config_path: Path | str,
    timeframe: str,
) -> StateVectorFeatureSpec:
    """Load and validate feature specification from YAML config.

    Args:
        config_path: Path to state_vector_feature_spec.yaml
        timeframe: Timeframe to load configuration for

    Returns:
        Validated StateVectorFeatureSpec

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_path = Path(config_path)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.debug(f"Loading feature spec from {config_path} for timeframe={timeframe}")
    with open(config_path) as f:
        raw_config = yaml.safe_load(f) or {}

    config = StateVectorConfig(**raw_config)

    feature_names = config.get_features_for_timeframe(timeframe)

    features = []
    for name in feature_names:
        if name in config.feature_specs:
            features.append(config.feature_specs[name])
        else:
            features.append(FeatureSpecEntry(name=name))

    logger.info(f"Loaded feature spec for {timeframe} with {len(features)} features")
    return StateVectorFeatureSpec(
        features=features,
        timeframe=timeframe,
        config=config,
    )


def create_default_config() -> StateVectorConfig:
    """Create a default configuration with recommended settings.

    Returns:
        StateVectorConfig with sensible defaults
    """
    return StateVectorConfig(
        encoder_type="pca",
        scaler_type="robust",
        ood_threshold=-50.0,
        state_ttl_bars=1,
        base_features=DEFAULT_FEATURE_SET.copy(),
        timeframe_configs={
            "1Min": TimeframeConfig(n_states=12, latent_dim=10),
            "5Min": TimeframeConfig(n_states=8, latent_dim=8),
            "15Min": TimeframeConfig(n_states=8, latent_dim=8),
            "1Hour": TimeframeConfig(n_states=6, latent_dim=6),
            "1Day": TimeframeConfig(n_states=5, latent_dim=5),
        },
    )


def save_config(config: StateVectorConfig, path: Path | str) -> None:
    """Save configuration to YAML file.

    Args:
        config: Configuration to save
        path: Output file path
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Saving config to {path}")
    with open(path, "w") as f:
        yaml.dump(
            config.model_dump(exclude_none=True),
            f,
            default_flow_style=False,
            sort_keys=False,
        )
    logger.info(f"Config saved to {path}")
