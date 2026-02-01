"""Data contracts for PCA-based state computation."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np


# Constant for unknown/OOD state
UNKNOWN_STATE = -1


@dataclass
class PCAStateOutput:
    """Output from PCA state inference.

    Attributes:
        symbol: Ticker symbol
        timestamp: Bar timestamp
        timeframe: Bar timeframe (e.g., "1Min")
        model_id: Model identifier
        state_id: Assigned state (0 to n_states-1, or -1 for OOD)
        distance_to_centroid: Distance to assigned cluster centroid
        pca_components: PCA-transformed feature vector
        is_ood: Whether observation is out-of-distribution
        reconstruction_error: PCA reconstruction error
    """

    symbol: str
    timestamp: datetime
    timeframe: str
    model_id: str
    state_id: int
    distance_to_centroid: float
    pca_components: np.ndarray
    is_ood: bool = False
    reconstruction_error: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "timeframe": self.timeframe,
            "model_id": self.model_id,
            "state_id": self.state_id,
            "distance_to_centroid": float(self.distance_to_centroid),
            "is_ood": self.is_ood,
            "reconstruction_error": float(self.reconstruction_error),
        }
        # Add PCA components as individual columns
        for i, val in enumerate(self.pca_components):
            result[f"pc_{i}"] = float(val)
        return result


@dataclass
class PCAModelMetadata:
    """Metadata for a trained PCA state model.

    Attributes:
        model_id: Unique model identifier
        model_type: Always "pca_kmeans" for this module
        timeframe: Bar timeframe
        symbols: List of symbols used in training
        n_components: Number of PCA components
        n_states: Number of K-means clusters
        feature_names: List of feature names used
        explained_variance_ratio: Variance explained by each component
        total_variance_explained: Total variance explained by all components
        ood_threshold: Distance threshold for OOD detection
        created_at: Model creation timestamp
        train_start: Training data start date
        train_end: Training data end date
        n_train_samples: Number of training samples
    """

    model_id: str
    model_type: str = "pca_kmeans"
    timeframe: str = "1Min"
    symbols: list[str] = field(default_factory=list)
    n_components: int = 6
    n_states: int = 5
    feature_names: list[str] = field(default_factory=list)
    explained_variance_ratio: list[float] = field(default_factory=list)
    total_variance_explained: float = 0.0
    ood_threshold: float = 3.0  # Standard deviations from centroid
    created_at: Optional[datetime] = None
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    n_train_samples: int = 0
    state_mapping: dict = field(default_factory=dict)  # state_id -> label info

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""

        def _convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_convert(v) for v in obj]
            return obj

        return _convert({
            "model_id": self.model_id,
            "model_type": self.model_type,
            "timeframe": self.timeframe,
            "symbols": self.symbols,
            "n_components": self.n_components,
            "n_states": self.n_states,
            "feature_names": self.feature_names,
            "explained_variance_ratio": self.explained_variance_ratio,
            "total_variance_explained": self.total_variance_explained,
            "ood_threshold": self.ood_threshold,
            "created_at": self.created_at,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "n_train_samples": self.n_train_samples,
            "state_mapping": self.state_mapping,
        })

    @classmethod
    def from_dict(cls, data: dict) -> "PCAModelMetadata":
        """Create from dictionary."""
        # Parse datetime fields
        for date_field in ["created_at", "train_start", "train_end"]:
            if data.get(date_field) and isinstance(data[date_field], str):
                data[date_field] = datetime.fromisoformat(data[date_field])
        return cls(**data)


@dataclass
class PCATrainingResult:
    """Result from PCA state model training.

    Attributes:
        metadata: Model metadata
        scaler: Fitted StandardScaler
        pca: Fitted PCA transformer
        kmeans: Fitted KMeans clusterer
        centroid_distances: Mean distance to centroid per state
        state_counts: Number of samples per state
        inertia: K-means inertia (within-cluster sum of squares)
    """

    metadata: PCAModelMetadata
    scaler: object  # sklearn StandardScaler
    pca: object  # sklearn PCA
    kmeans: object  # sklearn KMeans
    centroid_distances: dict[int, float] = field(default_factory=dict)
    state_counts: dict[int, int] = field(default_factory=dict)
    inertia: float = 0.0
