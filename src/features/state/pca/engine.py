"""Inference engine for PCA-based state computation."""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .contracts import PCAModelMetadata, PCAStateOutput, UNKNOWN_STATE

logger = logging.getLogger(__name__)


class PCAStateEngine:
    """Inference engine for PCA + K-means state computation.

    This engine loads a trained PCA + K-means model and computes states
    for new observations.

    Example:
        >>> engine = PCAStateEngine.from_artifacts(Path("models/pca_states"))
        >>> output = engine.process(features_dict, "AAPL", timestamp)
        >>> print(f"State: {output.state_id}, Distance: {output.distance_to_centroid:.3f}")
    """

    def __init__(
        self,
        scaler,
        pca,
        kmeans,
        metadata: PCAModelMetadata,
    ):
        """Initialize the engine.

        Args:
            scaler: Fitted StandardScaler
            pca: Fitted PCA transformer
            kmeans: Fitted KMeans clusterer
            metadata: Model metadata
        """
        self.scaler = scaler
        self.pca = pca
        self.kmeans = kmeans
        self.metadata = metadata

        # Pre-compute centroid distances for OOD detection
        self._centroid_norms = np.linalg.norm(kmeans.cluster_centers_, axis=1)

        logger.info(
            f"PCAStateEngine initialized: {metadata.n_states} states, "
            f"{metadata.n_components} components"
        )

    @classmethod
    def from_artifacts(cls, model_dir: Path) -> "PCAStateEngine":
        """Load engine from saved artifacts.

        Args:
            model_dir: Directory containing model artifacts

        Returns:
            Loaded PCAStateEngine instance
        """
        model_dir = Path(model_dir)

        # Load scaler
        with open(model_dir / "scaler.pkl", "rb") as f:
            scaler = pickle.load(f)

        # Load PCA
        with open(model_dir / "pca.pkl", "rb") as f:
            pca = pickle.load(f)

        # Load K-means
        with open(model_dir / "kmeans.pkl", "rb") as f:
            kmeans = pickle.load(f)

        # Load metadata
        with open(model_dir / "metadata.json", "r") as f:
            metadata = PCAModelMetadata.from_dict(json.load(f))

        logger.info(f"Loaded PCA state model from {model_dir}")
        return cls(scaler, pca, kmeans, metadata)

    def process(
        self,
        features: dict,
        symbol: str,
        timestamp: datetime,
    ) -> PCAStateOutput:
        """Process a single observation and return state assignment.

        Args:
            features: Dictionary of feature name -> value
            symbol: Ticker symbol
            timestamp: Observation timestamp

        Returns:
            PCAStateOutput with state assignment and diagnostics
        """
        # Extract features in correct order
        feature_vector = np.array([
            features.get(name, np.nan)
            for name in self.metadata.feature_names
        ]).reshape(1, -1)

        # Check for NaN values
        if np.isnan(feature_vector).any():
            logger.warning("NaN values in feature vector for %s at %s, marking output as OOD", symbol, timestamp)
            return PCAStateOutput(
                symbol=symbol,
                timestamp=timestamp,
                timeframe=self.metadata.timeframe,
                model_id=self.metadata.model_id,
                state_id=UNKNOWN_STATE,
                distance_to_centroid=float('inf'),
                pca_components=np.zeros(self.metadata.n_components),
                is_ood=True,
                reconstruction_error=float('inf'),
            )

        # Scale features
        X_scaled = self.scaler.transform(feature_vector)

        # Transform to PCA space
        X_pca = self.pca.transform(X_scaled)

        # Compute reconstruction error
        X_reconstructed = self.pca.inverse_transform(X_pca)
        reconstruction_error = float(np.mean((X_scaled - X_reconstructed) ** 2))

        # Predict cluster
        state_id = int(self.kmeans.predict(X_pca)[0])

        # Compute distance to assigned centroid
        centroid = self.kmeans.cluster_centers_[state_id]
        distance = float(np.linalg.norm(X_pca[0] - centroid))

        # Check if out-of-distribution
        is_ood = distance > self.metadata.ood_threshold

        if is_ood:
            logger.debug(
                f"OOD detected for {symbol} at {timestamp}: "
                f"distance={distance:.3f} > threshold={self.metadata.ood_threshold:.3f}"
            )
            state_id = UNKNOWN_STATE

        return PCAStateOutput(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=self.metadata.timeframe,
            model_id=self.metadata.model_id,
            state_id=state_id,
            distance_to_centroid=distance,
            pca_components=X_pca[0],
            is_ood=is_ood,
            reconstruction_error=reconstruction_error,
        )

    def process_batch(
        self,
        features_df: pd.DataFrame,
        symbol: str,
    ) -> list[PCAStateOutput]:
        """Process a batch of observations.

        Args:
            features_df: DataFrame with features (index is timestamp)
            symbol: Ticker symbol

        Returns:
            List of PCAStateOutput for each row
        """
        outputs = []

        for timestamp, row in features_df.iterrows():
            features = row.to_dict()
            output = self.process(features, symbol, timestamp)
            outputs.append(output)

        return outputs

    def transform(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Transform features to PCA space and get state assignments.

        This is a convenience method for batch processing that returns
        a DataFrame with PCA components and state assignments.

        Args:
            features_df: DataFrame with feature columns

        Returns:
            DataFrame with columns: state_id, distance, pc_0, pc_1, ..., is_ood
        """
        # Extract feature matrix
        X = features_df[self.metadata.feature_names].values

        # Handle NaN rows
        nan_mask = np.isnan(X).any(axis=1)
        valid_mask = ~nan_mask

        # Initialize output arrays
        n_samples = len(features_df)
        state_ids = np.full(n_samples, UNKNOWN_STATE, dtype=int)
        distances = np.full(n_samples, float('inf'))
        is_ood = np.ones(n_samples, dtype=bool)
        pca_components = np.zeros((n_samples, self.metadata.n_components))

        if valid_mask.sum() > 0:
            X_valid = X[valid_mask]

            # Scale and transform
            X_scaled = self.scaler.transform(X_valid)
            X_pca = self.pca.transform(X_scaled)

            # Predict clusters
            labels = self.kmeans.predict(X_pca)

            # Compute distances to centroids
            centroids = self.kmeans.cluster_centers_[labels]
            dists = np.linalg.norm(X_pca - centroids, axis=1)

            # Determine OOD
            ood_mask = dists > self.metadata.ood_threshold

            # Fill results
            state_ids[valid_mask] = np.where(ood_mask, UNKNOWN_STATE, labels)
            distances[valid_mask] = dists
            is_ood[valid_mask] = ood_mask
            pca_components[valid_mask] = X_pca

        # Build result DataFrame
        result = pd.DataFrame(index=features_df.index)
        result["state_id"] = state_ids
        result["distance"] = distances
        result["is_ood"] = is_ood

        for i in range(self.metadata.n_components):
            result[f"pc_{i}"] = pca_components[:, i]

        return result

    def get_state_centroids(self) -> np.ndarray:
        """Get K-means cluster centroids in PCA space.

        Returns:
            Array of shape (n_states, n_components)
        """
        return self.kmeans.cluster_centers_.copy()

    def get_state_info(self) -> dict:
        """Get information about each state.

        Returns:
            Dictionary with state_id -> info dict
        """
        info = {}
        for i in range(self.metadata.n_states):
            centroid = self.kmeans.cluster_centers_[i]
            info[i] = {
                "state_id": i,
                "centroid": centroid.tolist(),
                "label": self.metadata.state_mapping.get(str(i), {}).get("label", f"state_{i}"),
            }
        return info
