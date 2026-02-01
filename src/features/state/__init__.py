"""State computation features for market regime detection.

This module provides state/regime detection using different approaches:
- HMM: Hidden Markov Model based regime detection
- PCA: PCA + K-means clustering based state detection

Both approaches aim to identify market regimes (trending, ranging, volatile, etc.)
that can inform trade evaluation.
"""

from src.features.state.hmm import (
    InferenceEngine,
    MultiTimeframeInferenceEngine,
    TemporalInferenceEngine,
    create_inference_engine,
)
from src.features.state.pca import (
    PCAStateEngine,
    PCAStateTrainer,
)

__all__ = [
    # HMM
    "InferenceEngine",
    "MultiTimeframeInferenceEngine",
    "TemporalInferenceEngine",
    "create_inference_engine",
    # PCA
    "PCAStateEngine",
    "PCAStateTrainer",
]
