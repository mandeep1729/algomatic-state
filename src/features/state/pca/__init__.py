"""PCA-based state computation module.

This module provides a simpler alternative to HMM-based state computation
using PCA for dimensionality reduction and K-means clustering for state assignment.

Pipeline:
    Raw Features → Scaler → PCA → K-means → State IDs

Quick Start:
    >>> from src.features.state.pca import PCAStateEngine, train_pca_states
    >>>
    >>> # Train a model
    >>> result = train_pca_states(train_df, n_components=6, n_states=5)
    >>>
    >>> # Run inference
    >>> engine = PCAStateEngine.from_artifacts(model_path)
    >>> output = engine.process(features_dict, symbol, timestamp)
"""

from .engine import PCAStateEngine
from .training import PCAStateTrainer, train_pca_states
from .contracts import PCAStateOutput, PCAModelMetadata, PCATrainingResult, UNKNOWN_STATE
from .labeling import label_pca_states, labels_to_dict, StateLabel
from .artifacts import get_pca_model_path, list_pca_models, get_latest_pca_model

__all__ = [
    # Engine
    "PCAStateEngine",
    # Training
    "PCAStateTrainer",
    "train_pca_states",
    # Contracts
    "PCAStateOutput",
    "PCAModelMetadata",
    "PCATrainingResult",
    "UNKNOWN_STATE",
    # Labeling
    "label_pca_states",
    "labels_to_dict",
    "StateLabel",
    # Artifacts
    "get_pca_model_path",
    "list_pca_models",
    "get_latest_pca_model",
]
