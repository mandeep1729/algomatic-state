"""Training pipeline for state vector models.

Implements end-to-end training workflow:
- Training orchestrator
- Hyperparameter tuning
- Cross-validation framework
- Artifact packaging
- Reproducibility management
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import numpy as np
import pandas as pd

from src.features.state.hmm.artifacts import ArtifactPaths, get_model_path, generate_model_id
from src.features.state.hmm.config import (
    StateVectorConfig,
    StateVectorFeatureSpec,
    load_feature_spec,
    save_config,
)
from src.features.state.hmm.contracts import ModelMetadata, VALID_TIMEFRAMES
from src.features.state.hmm.data_pipeline import (
    DataSplit,
    TimeSplitter,
    validate_no_leakage,
)
from src.features.state.hmm.encoders import (
    BaseEncoder,
    PCAEncoder,
    TemporalPCAEncoder,
    create_windows,
    select_latent_dim,
)
from src.features.state.hmm.hmm_model import (
    GaussianHMMWrapper,
    match_states_hungarian,
    select_n_states,
)
from src.features.state.hmm.scalers import (
    BaseScaler,
    RobustScaler,
    StandardScaler,
    YeoJohnsonScaler,
    create_scaler,
)


logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for a training run.

    Attributes:
        timeframe: Model timeframe
        symbols: Symbols to train on
        train_start: Training data start
        train_end: Training data end
        val_start: Validation data start
        val_end: Validation data end
        feature_names: Features to use
        scaler_type: Type of scaler
        encoder_type: Type of encoder
        latent_dim: Latent dimension (None for auto-selection)
        n_states: Number of HMM states (None for auto-selection)
        covariance_type: HMM covariance type
        window_size: Window size for temporal encoder
        random_seed: Random seed for reproducibility
    """

    timeframe: str
    symbols: list[str]
    train_start: datetime
    train_end: datetime
    val_start: datetime
    val_end: datetime
    feature_names: list[str]
    scaler_type: Literal["robust", "standard", "yeo_johnson"] = "robust"
    encoder_type: Literal["pca", "temporal_pca"] = "pca"
    latent_dim: Optional[int] = None
    n_states: Optional[int] = None
    covariance_type: Literal["full", "diag", "tied", "spherical"] = "diag"
    window_size: int = 1
    random_seed: int = 42

    def __post_init__(self):
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {self.timeframe}")
        if self.train_end >= self.val_start:
            raise ValueError("train_end must be before val_start")


@dataclass
class TrainingResult:
    """Result from a training run.

    Attributes:
        model_id: Generated model ID
        paths: Artifact paths
        metadata: Model metadata
        metrics: Training and validation metrics
        scaler: Fitted scaler
        encoder: Fitted encoder
        hmm: Fitted HMM
    """

    model_id: str
    paths: ArtifactPaths
    metadata: ModelMetadata
    metrics: dict[str, float]
    scaler: BaseScaler
    encoder: BaseEncoder
    hmm: GaussianHMMWrapper


@dataclass
class HyperparameterGrid:
    """Grid of hyperparameters to search.

    Attributes:
        latent_dims: Latent dimensions to try
        n_states_range: Range of state counts to try
        covariance_types: Covariance types to try
    """

    latent_dims: list[int] = field(default_factory=lambda: [6, 8, 10, 12])
    n_states_range: range = field(default_factory=lambda: range(4, 12))
    covariance_types: list[str] = field(default_factory=lambda: ["diag"])


class TrainingPipeline:
    """End-to-end training pipeline for state vector models."""

    def __init__(
        self,
        models_root: Path = Path("models"),
        random_seed: int = 42,
    ):
        """Initialize training pipeline.

        Args:
            models_root: Root directory for model artifacts
            random_seed: Random seed for reproducibility
        """
        self.models_root = models_root
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def train(
        self,
        config: TrainingConfig,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame,
        model_version: Optional[int] = None,
        previous_model_path: Optional[ArtifactPaths] = None,
    ) -> TrainingResult:
        """Train a state vector model.

        Args:
            config: Training configuration
            train_data: Training features DataFrame (timestamp index, feature columns)
            val_data: Validation features DataFrame
            model_version: Optional model version number
            previous_model_path: Optional previous model for state matching

        Returns:
            TrainingResult with fitted model and metrics
        """
        logger.info(f"Starting training for {config.timeframe}")

        validate_no_leakage(train_data, val_data)

        X_train = train_data[config.feature_names].values
        X_val = val_data[config.feature_names].values

        logger.info(f"Training data shape: {X_train.shape}")
        logger.info(f"Validation data shape: {X_val.shape}")

        scaler = self._fit_scaler(X_train, config.scaler_type)
        X_train_scaled = scaler.transform(X_train)
        X_val_scaled = scaler.transform(X_val)

        if config.encoder_type == "temporal_pca" and config.window_size > 1:
            X_train_windowed = create_windows(X_train_scaled, config.window_size)
            X_val_windowed = create_windows(X_val_scaled, config.window_size)
            encoder = self._fit_encoder(
                X_train_windowed, config, is_windowed=True
            )
            Z_train = encoder.transform(X_train_windowed)
            Z_val = encoder.transform(X_val_windowed)
        else:
            encoder = self._fit_encoder(X_train_scaled, config, is_windowed=False)
            Z_train = encoder.transform(X_train_scaled)
            Z_val = encoder.transform(X_val_scaled)

        hmm = self._fit_hmm(Z_train, config)

        if previous_model_path and previous_model_path.exists():
            self._apply_state_matching(hmm, previous_model_path)

        metrics = self._compute_metrics(hmm, Z_train, Z_val, encoder)

        model_id = generate_model_id(version=model_version or 1)
        # Use first symbol for path (models are trained per-symbol)
        paths = get_model_path(config.symbols[0], config.timeframe, model_id, self.models_root)

        metadata = ModelMetadata(
            model_id=model_id,
            timeframe=config.timeframe,
            version="1.0.0",
            created_at=datetime.now(timezone.utc),
            training_start=config.train_start,
            training_end=config.train_end,
            n_states=hmm.n_states,
            latent_dim=encoder.latent_dim,
            feature_names=config.feature_names,
            symbols=config.symbols,
            scaler_type=config.scaler_type,
            encoder_type=config.encoder_type,
            covariance_type=config.covariance_type,
            metrics=metrics,
        )

        self._save_artifacts(paths, scaler, encoder, hmm, metadata, config)

        logger.info(f"Training complete. Model saved to {paths.model_dir}")

        return TrainingResult(
            model_id=model_id,
            paths=paths,
            metadata=metadata,
            metrics=metrics,
            scaler=scaler,
            encoder=encoder,
            hmm=hmm,
        )

    def _fit_scaler(
        self,
        X: np.ndarray,
        scaler_type: str,
    ) -> BaseScaler:
        """Fit scaler on training data."""
        logger.info(f"Fitting {scaler_type} scaler")
        scaler = create_scaler(scaler_type)

        mask = ~np.any(np.isnan(X), axis=1)
        scaler.fit(X[mask])

        return scaler

    def _fit_encoder(
        self,
        X: np.ndarray,
        config: TrainingConfig,
        is_windowed: bool,
    ) -> BaseEncoder:
        """Fit encoder on scaled training data."""
        latent_dim = config.latent_dim

        if latent_dim is None:
            if is_windowed:
                X_flat = X.reshape(X.shape[0], -1)
                latent_dim = select_latent_dim(X_flat, max_dim=16)
            else:
                latent_dim = select_latent_dim(X, max_dim=16)
            logger.info(f"Auto-selected latent_dim={latent_dim}")

        if is_windowed:
            encoder = TemporalPCAEncoder(
                latent_dim=latent_dim,
                window_size=config.window_size,
            )
        else:
            encoder = PCAEncoder(latent_dim=latent_dim)

        logger.info(f"Fitting {config.encoder_type} encoder with latent_dim={latent_dim}")
        encoder.fit(X)

        return encoder

    def _fit_hmm(
        self,
        Z: np.ndarray,
        config: TrainingConfig,
    ) -> GaussianHMMWrapper:
        """Fit HMM on latent vectors."""
        mask = ~np.any(np.isnan(Z), axis=1)
        Z_clean = Z[mask]

        n_states = config.n_states
        if n_states is None:
            n_states, scores = select_n_states(
                Z_clean,
                state_range=range(3, 15),
                criterion="bic",
                covariance_type=config.covariance_type,
                random_state=self.random_seed,
            )
            logger.info(f"Auto-selected n_states={n_states} (BIC scores: {scores})")

        logger.info(f"Fitting HMM with n_states={n_states}, cov_type={config.covariance_type}")

        hmm = GaussianHMMWrapper(
            n_states=n_states,
            covariance_type=config.covariance_type,
            random_state=self.random_seed,
        )
        hmm.fit(Z_clean)

        return hmm

    def _apply_state_matching(
        self,
        hmm: GaussianHMMWrapper,
        previous_path: ArtifactPaths,
    ) -> None:
        """Apply Hungarian matching to align states with previous model."""
        try:
            previous_hmm = GaussianHMMWrapper.load(previous_path.hmm_path)
            mapping = match_states_hungarian(previous_hmm.means, hmm.means)
            logger.info(f"State mapping from previous model: {mapping}")
        except Exception as e:
            logger.warning(f"Could not apply state matching: {e}")

    def _compute_metrics(
        self,
        hmm: GaussianHMMWrapper,
        Z_train: np.ndarray,
        Z_val: np.ndarray,
        encoder: BaseEncoder,
    ) -> dict[str, float]:
        """Compute training and validation metrics."""
        metrics = {}

        if hmm.metrics_:
            metrics["train_log_likelihood"] = hmm.metrics_.log_likelihood
            metrics["train_aic"] = hmm.metrics_.aic
            metrics["train_bic"] = hmm.metrics_.bic
            metrics["mean_dwell_time"] = float(np.mean(hmm.metrics_.mean_dwell_time))

        mask_val = ~np.any(np.isnan(Z_val), axis=1)
        if mask_val.sum() > 0:
            Z_val_clean = Z_val[mask_val]
            val_ll = hmm.model_.score(Z_val_clean)
            metrics["val_log_likelihood"] = val_ll

        if hasattr(encoder, "metrics_") and encoder.metrics_:
            metrics["explained_variance"] = encoder.metrics_.total_variance_explained
            metrics["reconstruction_error"] = encoder.metrics_.reconstruction_error

        return metrics

    def _save_artifacts(
        self,
        paths: ArtifactPaths,
        scaler: BaseScaler,
        encoder: BaseEncoder,
        hmm: GaussianHMMWrapper,
        metadata: ModelMetadata,
        config: TrainingConfig,
    ) -> None:
        """Save all model artifacts."""
        paths.ensure_dirs()

        scaler.save(paths.scaler_path)
        encoder.save(paths.encoder_path)
        hmm.save(paths.hmm_path)
        paths.save_metadata(metadata)

        feature_spec = {
            "feature_names": config.feature_names,
            "scaler_type": config.scaler_type,
            "encoder_type": config.encoder_type,
            "window_size": config.window_size,
        }
        with open(paths.feature_spec_path, "w") as f:
            json.dump(feature_spec, f, indent=2)

        logger.info(f"Artifacts saved to {paths.model_dir}")


class CrossValidator:
    """Walk-forward cross-validation for model selection."""

    def __init__(
        self,
        pipeline: TrainingPipeline,
        n_folds: int = 5,
        train_window_days: int = 180,
        val_window_days: int = 30,
    ):
        """Initialize cross-validator.

        Args:
            pipeline: Training pipeline to use
            n_folds: Number of walk-forward folds
            train_window_days: Training window in days
            val_window_days: Validation window in days
        """
        self.pipeline = pipeline
        self.n_folds = n_folds
        self.train_window_days = train_window_days
        self.val_window_days = val_window_days

    def cross_validate(
        self,
        data: pd.DataFrame,
        config: TrainingConfig,
    ) -> dict[str, Any]:
        """Run walk-forward cross-validation.

        Args:
            data: Full dataset with timestamp index
            config: Training configuration template

        Returns:
            Dictionary with fold results and aggregate metrics
        """
        splitter = TimeSplitter()

        timeframe_bars = {
            "1Min": 390,
            "5Min": 78,
            "15Min": 26,
            "1Hour": 7,
            "1Day": 1,
        }
        bars_per_day = timeframe_bars.get(config.timeframe, 390)

        train_window = self.train_window_days * bars_per_day
        val_window = self.val_window_days * bars_per_day
        step = val_window

        splits = splitter.walk_forward_splits(
            data,
            train_window=train_window,
            val_window=val_window,
            step=step,
        )

        splits = splits[: self.n_folds]

        fold_results = []
        for i, split in enumerate(splits):
            logger.info(f"Training fold {i + 1}/{len(splits)}")

            fold_config = TrainingConfig(
                timeframe=config.timeframe,
                symbols=config.symbols,
                train_start=split.train_start,
                train_end=split.train_end,
                val_start=split.val_start,
                val_end=split.val_end,
                feature_names=config.feature_names,
                scaler_type=config.scaler_type,
                encoder_type=config.encoder_type,
                latent_dim=config.latent_dim,
                n_states=config.n_states,
                covariance_type=config.covariance_type,
                window_size=config.window_size,
                random_seed=config.random_seed + i,
            )

            result = self.pipeline.train(
                fold_config,
                split.train,
                split.val,
                model_version=None,
            )

            fold_results.append({
                "fold": i,
                "train_start": split.train_start.isoformat(),
                "train_end": split.train_end.isoformat(),
                "val_start": split.val_start.isoformat(),
                "val_end": split.val_end.isoformat(),
                "metrics": result.metrics,
            })

        aggregate = self._aggregate_metrics(fold_results)

        return {
            "folds": fold_results,
            "aggregate": aggregate,
            "n_folds": len(splits),
        }

    def _aggregate_metrics(
        self,
        fold_results: list[dict],
    ) -> dict[str, float]:
        """Aggregate metrics across folds."""
        all_metrics = [f["metrics"] for f in fold_results]

        aggregate = {}
        for key in all_metrics[0]:
            values = [m[key] for m in all_metrics if key in m]
            if values:
                aggregate[f"{key}_mean"] = float(np.mean(values))
                aggregate[f"{key}_std"] = float(np.std(values))

        return aggregate


class HyperparameterTuner:
    """Grid search for hyperparameter tuning."""

    def __init__(
        self,
        pipeline: TrainingPipeline,
        grid: Optional[HyperparameterGrid] = None,
    ):
        """Initialize tuner.

        Args:
            pipeline: Training pipeline
            grid: Hyperparameter grid to search
        """
        self.pipeline = pipeline
        self.grid = grid or HyperparameterGrid()

    def tune(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame,
        base_config: TrainingConfig,
        metric: str = "val_log_likelihood",
        maximize: bool = True,
    ) -> dict[str, Any]:
        """Run hyperparameter grid search.

        Args:
            train_data: Training data
            val_data: Validation data
            base_config: Base configuration template
            metric: Metric to optimize
            maximize: Whether to maximize (True) or minimize (False)

        Returns:
            Dictionary with best params and all results
        """
        results = []

        for latent_dim in self.grid.latent_dims:
            for n_states in self.grid.n_states_range:
                for cov_type in self.grid.covariance_types:
                    logger.info(
                        f"Trying latent_dim={latent_dim}, "
                        f"n_states={n_states}, cov_type={cov_type}"
                    )

                    config = TrainingConfig(
                        timeframe=base_config.timeframe,
                        symbols=base_config.symbols,
                        train_start=base_config.train_start,
                        train_end=base_config.train_end,
                        val_start=base_config.val_start,
                        val_end=base_config.val_end,
                        feature_names=base_config.feature_names,
                        scaler_type=base_config.scaler_type,
                        encoder_type=base_config.encoder_type,
                        latent_dim=latent_dim,
                        n_states=n_states,
                        covariance_type=cov_type,
                        window_size=base_config.window_size,
                        random_seed=base_config.random_seed,
                    )

                    try:
                        result = self.pipeline.train(config, train_data, val_data)
                        score = result.metrics.get(metric, float("-inf") if maximize else float("inf"))

                        results.append({
                            "latent_dim": latent_dim,
                            "n_states": n_states,
                            "covariance_type": cov_type,
                            "score": score,
                            "metrics": result.metrics,
                        })
                    except Exception as e:
                        logger.warning(f"Training failed: {e}")
                        continue

        if not results:
            raise ValueError("All hyperparameter combinations failed")

        if maximize:
            best = max(results, key=lambda x: x["score"])
        else:
            best = min(results, key=lambda x: x["score"])

        return {
            "best_params": {
                "latent_dim": best["latent_dim"],
                "n_states": best["n_states"],
                "covariance_type": best["covariance_type"],
            },
            "best_score": best["score"],
            "all_results": results,
        }


def train_model(
    timeframe: str,
    train_data: pd.DataFrame,
    val_data: pd.DataFrame,
    feature_names: list[str],
    symbols: list[str],
    models_root: Path = Path("models"),
    **kwargs,
) -> TrainingResult:
    """Convenience function to train a model.

    Args:
        timeframe: Model timeframe
        train_data: Training DataFrame
        val_data: Validation DataFrame
        feature_names: Features to use
        symbols: Symbols in training data
        models_root: Models root directory
        **kwargs: Additional TrainingConfig parameters

    Returns:
        TrainingResult
    """
    config = TrainingConfig(
        timeframe=timeframe,
        symbols=symbols,
        train_start=train_data.index.min(),
        train_end=train_data.index.max(),
        val_start=val_data.index.min(),
        val_end=val_data.index.max(),
        feature_names=feature_names,
        **kwargs,
    )

    pipeline = TrainingPipeline(models_root=models_root)
    return pipeline.train(config, train_data, val_data)
