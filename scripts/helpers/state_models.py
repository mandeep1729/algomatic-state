"""State model loading helpers."""

from pathlib import Path
from typing import NamedTuple

from src.state.autoencoder import TemporalAutoencoder
from src.state.normalization import Normalizer
from src.state.clustering import RegimeClusterer


class StateModels(NamedTuple):
    """Container for loaded state models."""

    autoencoder: TemporalAutoencoder
    normalizer: Normalizer
    clusterer: RegimeClusterer


def load_autoencoder(model_path: str) -> TemporalAutoencoder:
    """Load autoencoder model from path."""
    return TemporalAutoencoder.load(model_path)


def load_normalizer(model_dir: Path) -> Normalizer:
    """Load normalizer from model directory."""
    return Normalizer.load(str(model_dir / "normalizer.joblib"))


def load_clusterer(model_dir: Path) -> RegimeClusterer:
    """Load clusterer from model directory."""
    return RegimeClusterer.load(str(model_dir / "clusterer.joblib"))


def load_all_models(model_path: str) -> StateModels:
    """Load all state models from model path.

    Args:
        model_path: Path to the autoencoder model file

    Returns:
        StateModels namedtuple with autoencoder, normalizer, clusterer
    """
    model_dir = Path(model_path).parent
    return StateModels(
        autoencoder=load_autoencoder(model_path),
        normalizer=load_normalizer(model_dir),
        clusterer=load_clusterer(model_dir),
    )
