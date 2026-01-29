"""Data contracts for the HMM state vector system.

Defines TypedDict and dataclass contracts for:
- FeatureVector: raw engineered features
- LatentStateVector: encoded latent representation
- HMMOutput: regime inference output
- ModelMetadata: model versioning and configuration
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

import numpy as np


class Timeframe(str, Enum):
    """Valid timeframes for state vector models."""

    MIN_1 = "1Min"
    MIN_5 = "5Min"
    MIN_15 = "15Min"
    HOUR_1 = "1Hour"
    DAY_1 = "1Day"


VALID_TIMEFRAMES = frozenset({tf.value for tf in Timeframe})


@dataclass
class FeatureVector:
    """Feature vector computed from OHLCV data.

    Attributes:
        symbol: Ticker symbol
        timestamp: Bar close timestamp (timezone-aware)
        timeframe: Bar timeframe
        features: Dictionary of feature name -> value
        has_gap: Whether this bar follows a data gap
    """

    symbol: str
    timestamp: datetime
    timeframe: str
    features: dict[str, float]
    has_gap: bool = False

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )

    def to_array(self, feature_names: list[str]) -> np.ndarray:
        """Convert to numpy array with specified feature ordering.

        Args:
            feature_names: Ordered list of feature names to include

        Returns:
            1D numpy array of feature values

        Raises:
            KeyError: If a required feature is missing
        """
        return np.array([self.features[name] for name in feature_names])

    @property
    def feature_names(self) -> list[str]:
        """Return sorted list of feature names."""
        return sorted(self.features.keys())


@dataclass
class LatentStateVector:
    """Latent state vector from encoder output.

    Attributes:
        symbol: Ticker symbol
        timestamp: Bar close timestamp
        timeframe: Bar timeframe
        z: Latent vector (numpy array of shape (d,))
        reconstruction_error: Optional reconstruction error from autoencoder
    """

    symbol: str
    timestamp: datetime
    timeframe: str
    z: np.ndarray
    reconstruction_error: Optional[float] = None

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )
        if not isinstance(self.z, np.ndarray):
            self.z = np.array(self.z)
        if self.z.ndim != 1:
            raise ValueError(f"z must be 1D array, got shape {self.z.shape}")

    @property
    def latent_dim(self) -> int:
        """Return dimensionality of latent space."""
        return len(self.z)


@dataclass
class HMMOutput:
    """HMM inference output for a single timestep.

    Attributes:
        symbol: Ticker symbol
        timestamp: Bar close timestamp
        timeframe: Bar timeframe
        model_id: Model version identifier
        state_id: Most likely state (argmax of posterior), or -1 for UNKNOWN
        state_prob: Probability of most likely state (max posterior)
        posterior: Full posterior distribution over states
        log_likelihood: Emission log-likelihood p(z_t | model)
        is_ood: Whether this observation is out-of-distribution
        z: The latent vector used for inference (optional, for diagnostics)
    """

    symbol: str
    timestamp: datetime
    timeframe: str
    model_id: str
    state_id: int
    state_prob: float
    posterior: np.ndarray
    log_likelihood: float
    is_ood: bool = False
    z: Optional[np.ndarray] = None

    # Special state ID for out-of-distribution observations
    UNKNOWN_STATE: int = -1

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )
        if not isinstance(self.posterior, np.ndarray):
            self.posterior = np.array(self.posterior)

    @property
    def n_states(self) -> int:
        """Return number of states in the model."""
        return len(self.posterior)

    @property
    def entropy(self) -> float:
        """Compute entropy of the posterior distribution.

        Higher entropy indicates more uncertainty about the current state.
        """
        p = self.posterior
        p = np.clip(p, 1e-10, 1.0)
        return -np.sum(p * np.log(p))

    @classmethod
    def unknown(
        cls,
        symbol: str,
        timestamp: datetime,
        timeframe: str,
        model_id: str,
        n_states: int,
        log_likelihood: float,
        z: Optional[np.ndarray] = None,
    ) -> "HMMOutput":
        """Create an UNKNOWN state output for OOD observations.

        Args:
            symbol: Ticker symbol
            timestamp: Bar close timestamp
            timeframe: Bar timeframe
            model_id: Model version identifier
            n_states: Number of states in model
            log_likelihood: Emission log-likelihood
            z: Optional latent vector

        Returns:
            HMMOutput with state_id = UNKNOWN_STATE
        """
        uniform_posterior = np.ones(n_states) / n_states
        return cls(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=timeframe,
            model_id=model_id,
            state_id=cls.UNKNOWN_STATE,
            state_prob=1.0 / n_states,
            posterior=uniform_posterior,
            log_likelihood=log_likelihood,
            is_ood=True,
            z=z,
        )


@dataclass
class ModelMetadata:
    """Metadata for a trained state vector model.

    Attributes:
        model_id: Unique model identifier (e.g., "state_v003")
        timeframe: Model timeframe
        version: Semantic version string
        created_at: Training completion timestamp
        training_start: Start of training data window
        training_end: End of training data window
        n_states: Number of HMM states (K)
        latent_dim: Encoder latent dimension (d)
        feature_names: Ordered list of input features
        symbols: Symbols used for training
        scaler_type: Type of scaler used
        encoder_type: Type of encoder used
        covariance_type: HMM covariance type
        state_ttl_bars: State validity TTL in bars
        ood_threshold: Log-likelihood threshold for OOD detection
        state_mapping: Optional semantic labels for states (str(state_id) -> label dict)
        metrics: Training/validation metrics
    """

    model_id: str
    timeframe: str
    version: str
    created_at: datetime
    training_start: datetime
    training_end: datetime
    n_states: int
    latent_dim: int
    feature_names: list[str]
    symbols: list[str]
    scaler_type: Literal["robust", "standard", "yeo_johnson"] = "robust"
    encoder_type: Literal["pca", "temporal_vae", "temporal_dae"] = "pca"
    covariance_type: Literal["full", "diag", "tied", "spherical"] = "diag"
    state_ttl_bars: int = 1
    ood_threshold: float = -50.0
    state_mapping: Optional[dict[str, dict]] = None
    metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Valid options: {VALID_TIMEFRAMES}"
            )
        if self.n_states < 2:
            raise ValueError(f"n_states must be >= 2, got {self.n_states}")
        if self.latent_dim < 1:
            raise ValueError(f"latent_dim must be >= 1, got {self.latent_dim}")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "model_id": self.model_id,
            "timeframe": self.timeframe,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "training_start": self.training_start.isoformat(),
            "training_end": self.training_end.isoformat(),
            "n_states": self.n_states,
            "latent_dim": self.latent_dim,
            "feature_names": self.feature_names,
            "symbols": self.symbols,
            "scaler_type": self.scaler_type,
            "encoder_type": self.encoder_type,
            "covariance_type": self.covariance_type,
            "state_ttl_bars": self.state_ttl_bars,
            "ood_threshold": self.ood_threshold,
            "state_mapping": self.state_mapping,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelMetadata":
        """Create from dictionary (e.g., loaded from JSON)."""
        return cls(
            model_id=data["model_id"],
            timeframe=data["timeframe"],
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            training_start=datetime.fromisoformat(data["training_start"]),
            training_end=datetime.fromisoformat(data["training_end"]),
            n_states=data["n_states"],
            latent_dim=data["latent_dim"],
            feature_names=data["feature_names"],
            symbols=data["symbols"],
            scaler_type=data.get("scaler_type", "robust"),
            encoder_type=data.get("encoder_type", "pca"),
            covariance_type=data.get("covariance_type", "diag"),
            state_ttl_bars=data.get("state_ttl_bars", 1),
            ood_threshold=data.get("ood_threshold", -50.0),
            state_mapping=data.get("state_mapping"),
            metrics=data.get("metrics", {}),
        )
