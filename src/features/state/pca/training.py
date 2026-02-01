"""Training pipeline for PCA-based state computation."""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .contracts import PCAModelMetadata, PCATrainingResult

logger = logging.getLogger(__name__)


class PCAStateTrainer:
    """Trains PCA + K-means model for state computation.

    Pipeline:
        1. Scale features using StandardScaler
        2. Reduce dimensionality using PCA
        3. Cluster latent space using K-means

    Example:
        >>> trainer = PCAStateTrainer(n_components=6, n_states=5)
        >>> result = trainer.fit(train_df, feature_names)
        >>> trainer.save(Path("models/pca_states"))
    """

    def __init__(
        self,
        n_components: int = 6,
        n_states: int = 5,
        variance_threshold: float = 0.95,
        auto_select_components: bool = True,
        auto_select_states: bool = True,
        min_states: int = 3,
        max_states: int = 10,
        random_state: int = 42,
    ):
        """Initialize the trainer.

        Args:
            n_components: Number of PCA components (if not auto-selected)
            n_states: Number of K-means clusters (if not auto-selected)
            variance_threshold: Minimum variance to explain (for auto-selection)
            auto_select_components: Auto-select n_components based on variance
            auto_select_states: Auto-select n_states using elbow method
            min_states: Minimum states for auto-selection
            max_states: Maximum states for auto-selection
            random_state: Random seed for reproducibility
        """
        self.n_components = n_components
        self.n_states = n_states
        self.variance_threshold = variance_threshold
        self.auto_select_components = auto_select_components
        self.auto_select_states = auto_select_states
        self.min_states = min_states
        self.max_states = max_states
        self.random_state = random_state

        # Fitted models
        self.scaler: Optional[StandardScaler] = None
        self.pca: Optional[PCA] = None
        self.kmeans: Optional[KMeans] = None
        self.metadata: Optional[PCAModelMetadata] = None

    def fit(
        self,
        df: pd.DataFrame,
        feature_names: list[str],
        model_id: str = "pca_v001",
        timeframe: str = "1Min",
        symbols: Optional[list[str]] = None,
    ) -> PCATrainingResult:
        """Fit the PCA + K-means model.

        Args:
            df: DataFrame with features (index is timestamp)
            feature_names: List of feature column names to use
            model_id: Unique model identifier
            timeframe: Data timeframe
            symbols: List of symbols in training data

        Returns:
            PCATrainingResult with fitted models and metadata
        """
        logger.info(f"Starting PCA state training: {len(df)} samples, {len(feature_names)} features")

        # Extract feature matrix
        X = df[feature_names].values

        # Handle NaN values
        nan_mask = np.isnan(X).any(axis=1)
        if nan_mask.sum() > 0:
            logger.warning(f"Dropping {nan_mask.sum()} rows with NaN values")
            X = X[~nan_mask]

        logger.info(f"Training data shape: {X.shape}")

        # Step 1: Scale features
        logger.info("Fitting StandardScaler")
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Step 2: Fit PCA (possibly with auto-selection)
        if self.auto_select_components:
            n_components = self._select_n_components(X_scaled)
            logger.info(f"Auto-selected n_components={n_components} (explains {self.variance_threshold*100:.0f}% variance)")
        else:
            n_components = min(self.n_components, X_scaled.shape[1])

        logger.info(f"Fitting PCA with n_components={n_components}")
        self.pca = PCA(n_components=n_components, random_state=self.random_state)
        X_pca = self.pca.fit_transform(X_scaled)

        total_variance = sum(self.pca.explained_variance_ratio_)
        logger.info(f"PCA explains {total_variance*100:.1f}% of variance")

        # Step 3: Fit K-means (possibly with auto-selection)
        if self.auto_select_states:
            n_states = self._select_n_states(X_pca)
            logger.info(f"Auto-selected n_states={n_states} using elbow method")
        else:
            n_states = self.n_states

        logger.info(f"Fitting KMeans with n_clusters={n_states}")
        self.kmeans = KMeans(
            n_clusters=n_states,
            random_state=self.random_state,
            n_init=10,
            max_iter=300,
        )
        labels = self.kmeans.fit_predict(X_pca)

        # Compute per-state statistics
        state_counts = {}
        centroid_distances = {}
        for state_id in range(n_states):
            mask = labels == state_id
            state_counts[state_id] = int(mask.sum())

            # Mean distance to centroid for this state
            if mask.sum() > 0:
                state_points = X_pca[mask]
                centroid = self.kmeans.cluster_centers_[state_id]
                distances = np.linalg.norm(state_points - centroid, axis=1)
                centroid_distances[state_id] = float(np.mean(distances))

        # Compute OOD threshold (mean + 3*std of all distances)
        all_distances = np.linalg.norm(
            X_pca - self.kmeans.cluster_centers_[labels], axis=1
        )
        ood_threshold = float(np.mean(all_distances) + 3 * np.std(all_distances))

        # Create metadata
        self.metadata = PCAModelMetadata(
            model_id=model_id,
            model_type="pca_kmeans",
            timeframe=timeframe,
            symbols=symbols or [],
            n_components=n_components,
            n_states=n_states,
            feature_names=feature_names,
            explained_variance_ratio=self.pca.explained_variance_ratio_.tolist(),
            total_variance_explained=total_variance,
            ood_threshold=ood_threshold,
            created_at=datetime.now(),
            train_start=df.index.min() if hasattr(df.index, 'min') else None,
            train_end=df.index.max() if hasattr(df.index, 'max') else None,
            n_train_samples=len(X),
        )

        logger.info(f"Training complete: {n_states} states, {n_components} components")
        for state_id, count in state_counts.items():
            pct = count / len(X) * 100
            logger.info(f"  State {state_id}: {count} samples ({pct:.1f}%)")

        return PCATrainingResult(
            metadata=self.metadata,
            scaler=self.scaler,
            pca=self.pca,
            kmeans=self.kmeans,
            centroid_distances=centroid_distances,
            state_counts=state_counts,
            inertia=self.kmeans.inertia_,
        )

    def _select_n_components(self, X_scaled: np.ndarray) -> int:
        """Auto-select number of PCA components based on variance threshold."""
        # Fit full PCA to get variance ratios
        pca_full = PCA(random_state=self.random_state)
        pca_full.fit(X_scaled)

        cumulative_variance = np.cumsum(pca_full.explained_variance_ratio_)
        n_components = np.argmax(cumulative_variance >= self.variance_threshold) + 1

        # Bound to reasonable range
        n_components = max(2, min(n_components, 16, X_scaled.shape[1]))
        return n_components

    def _select_n_states(self, X_pca: np.ndarray) -> int:
        """Auto-select number of states using elbow method with inertia."""
        inertias = []
        k_range = range(self.min_states, self.max_states + 1)

        for k in k_range:
            kmeans = KMeans(
                n_clusters=k,
                random_state=self.random_state,
                n_init=10,
                max_iter=100,
            )
            kmeans.fit(X_pca)
            inertias.append(kmeans.inertia_)

        # Find elbow using second derivative
        if len(inertias) < 3:
            return self.min_states

        # Compute rate of change
        diffs = np.diff(inertias)
        diffs2 = np.diff(diffs)

        # Elbow is where second derivative is maximum (curve flattens)
        elbow_idx = np.argmax(diffs2) + 1  # +1 because of diff offset
        n_states = list(k_range)[elbow_idx]

        logger.debug(f"Elbow method inertias: {dict(zip(k_range, inertias))}")
        return n_states

    def save(self, model_dir: Path) -> None:
        """Save fitted model artifacts to directory.

        Args:
            model_dir: Directory to save artifacts
        """
        if self.scaler is None or self.pca is None or self.kmeans is None:
            raise ValueError("Model not fitted. Call fit() first.")

        model_dir.mkdir(parents=True, exist_ok=True)

        # Save scaler
        with open(model_dir / "scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)

        # Save PCA
        with open(model_dir / "pca.pkl", "wb") as f:
            pickle.dump(self.pca, f)

        # Save K-means
        with open(model_dir / "kmeans.pkl", "wb") as f:
            pickle.dump(self.kmeans, f)

        # Save metadata
        with open(model_dir / "metadata.json", "w") as f:
            json.dump(self.metadata.to_dict(), f, indent=2)

        logger.info(f"Saved PCA state model to {model_dir}")

    @classmethod
    def load(cls, model_dir: Path) -> "PCAStateTrainer":
        """Load fitted model from directory.

        Args:
            model_dir: Directory containing model artifacts

        Returns:
            Loaded PCAStateTrainer instance
        """
        trainer = cls()

        # Load scaler
        with open(model_dir / "scaler.pkl", "rb") as f:
            trainer.scaler = pickle.load(f)

        # Load PCA
        with open(model_dir / "pca.pkl", "rb") as f:
            trainer.pca = pickle.load(f)

        # Load K-means
        with open(model_dir / "kmeans.pkl", "rb") as f:
            trainer.kmeans = pickle.load(f)

        # Load metadata
        with open(model_dir / "metadata.json", "r") as f:
            trainer.metadata = PCAModelMetadata.from_dict(json.load(f))

        trainer.n_components = trainer.metadata.n_components
        trainer.n_states = trainer.metadata.n_states

        logger.info(f"Loaded PCA state model from {model_dir}")
        return trainer


def train_pca_states(
    df: pd.DataFrame,
    feature_names: list[str],
    model_id: str = "pca_v001",
    timeframe: str = "1Min",
    symbols: Optional[list[str]] = None,
    n_components: int = 6,
    n_states: int = 5,
    auto_select: bool = True,
    save_dir: Optional[Path] = None,
) -> PCATrainingResult:
    """Convenience function to train a PCA state model.

    Args:
        df: DataFrame with features
        feature_names: List of feature column names
        model_id: Unique model identifier
        timeframe: Data timeframe
        symbols: List of symbols in training data
        n_components: Number of PCA components
        n_states: Number of K-means clusters
        auto_select: Auto-select n_components and n_states
        save_dir: Optional directory to save model

    Returns:
        PCATrainingResult with fitted models
    """
    trainer = PCAStateTrainer(
        n_components=n_components,
        n_states=n_states,
        auto_select_components=auto_select,
        auto_select_states=auto_select,
    )

    result = trainer.fit(
        df=df,
        feature_names=feature_names,
        model_id=model_id,
        timeframe=timeframe,
        symbols=symbols,
    )

    if save_dir:
        trainer.save(save_dir)

    return result
