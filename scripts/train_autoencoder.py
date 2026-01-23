#!/usr/bin/env python
"""Train state autoencoder model.

Usage:
    python scripts/train_autoencoder.py --data data/raw/AAPL_1Min.parquet
    python scripts/train_autoencoder.py --data data/raw/ --epochs 100
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import numpy as np
import torch

from src.features.pipeline import FeaturePipeline
from src.state.windows import create_windows
from src.state.normalization import Normalizer
from src.state.autoencoder import TemporalAutoencoder, AutoencoderConfig
from src.state.clustering import RegimeClusterer
from scripts.helpers.logging_setup import setup_script_logging
from scripts.helpers.data import load_data_from_path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Train state autoencoder model")
    _add_data_args(parser)
    _add_model_args(parser)
    _add_training_args(parser)
    return parser.parse_args()


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    """Add data-related arguments."""
    parser.add_argument("--data", type=str, required=True, help="Path to data file or directory")
    parser.add_argument("--output", type=str, default="models", help="Output directory (default: models)")


def _add_model_args(parser: argparse.ArgumentParser) -> None:
    """Add model architecture arguments."""
    parser.add_argument("--window-size", type=int, default=60, help="Temporal window size (default: 60)")
    parser.add_argument("--latent-dim", type=int, default=16, help="Latent dimension (default: 16)")
    parser.add_argument("--n-regimes", type=int, default=5, help="Number of regimes for clustering (default: 5)")


def _add_training_args(parser: argparse.ArgumentParser) -> None:
    """Add training-related arguments."""
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs (default: 50)")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size (default: 64)")
    parser.add_argument("--learning-rate", type=float, default=0.001, help="Learning rate (default: 0.001)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def compute_features(df, logger) -> "pd.DataFrame":
    """Compute features from raw data."""
    logger.info("Computing features...")
    pipeline = FeaturePipeline()
    features_df = pipeline.compute(df)
    logger.info(f"Computed {len(features_df.columns)} features")
    return features_df


def prepare_windows(features_df, window_size: int, logger) -> tuple:
    """Create and normalize temporal windows."""
    features_df = features_df.dropna()
    logger.info(f"After dropping NaN: {len(features_df)} rows")

    if len(features_df) < window_size * 2:
        raise ValueError("Not enough data for training")

    logger.info(f"Creating temporal windows (size={window_size})")
    windows, timestamps = create_windows(features_df.values, window_size=window_size, stride=1)
    logger.info(f"Created {len(windows)} windows")
    return windows, timestamps


def normalize_windows(windows, logger) -> tuple[np.ndarray, Normalizer]:
    """Normalize windows and return normalizer."""
    logger.info("Normalizing features...")
    normalizer = Normalizer(method="zscore", clip_std=3.0)
    windows_normalized = normalizer.fit_transform(windows)
    return windows_normalized, normalizer


def split_train_val(windows_normalized: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split windows into train/val sets."""
    train_size = int(0.8 * len(windows_normalized))
    return windows_normalized[:train_size], windows_normalized[train_size:]


def create_autoencoder_model(n_features: int, args) -> TemporalAutoencoder:
    """Create autoencoder model with config."""
    config = AutoencoderConfig(
        window_size=args.window_size,
        n_features=n_features,
        latent_dim=args.latent_dim,
    )
    return TemporalAutoencoder(config)


def train_model(model, train_windows, val_windows, args, logger) -> dict:
    """Train the autoencoder model."""
    logger.info(f"Training for {args.epochs} epochs...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    history = model.fit(
        train_windows,
        val_data=val_windows,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        device=device,
    )
    logger.info(f"Final train loss: {history['train_loss'][-1]:.6f}")
    logger.info(f"Final val loss: {history['val_loss'][-1]:.6f}")
    return history


def extract_states(model, windows_normalized, logger) -> np.ndarray:
    """Extract state representations from windows."""
    logger.info("Extracting state representations...")
    states = model.encode(windows_normalized)
    logger.info(f"State shape: {states.shape}")
    return states


def compute_window_returns(df, window_size: int, n_states: int) -> np.ndarray:
    """Calculate forward returns aligned with windows."""
    close_prices = df["close"].values
    returns = np.zeros(len(df))
    returns[:-1] = np.log(close_prices[1:] / close_prices[:-1])
    return returns[window_size - 1 : window_size - 1 + n_states]


def cluster_states(states, window_returns, n_regimes: int, logger) -> RegimeClusterer:
    """Cluster states into regimes."""
    logger.info(f"Clustering into {n_regimes} regimes...")
    clusterer = RegimeClusterer(n_clusters=n_regimes)
    clusterer.fit(states, window_returns)
    return clusterer


def print_regime_summary(clusterer, logger) -> None:
    """Print regime summary information."""
    logger.info("\nRegime Summary:")
    for info in clusterer.get_regime_summary():
        logger.info(
            f"  Regime {info['label']}: size={info['size']}, "
            f"sharpe={info['sharpe']:.2f}, mean_ret={info['mean_return']*10000:.2f}bps"
        )


def save_models(model, normalizer, clusterer, output_dir: Path, logger) -> None:
    """Save all trained models."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _save_autoencoder(model, output_dir, logger)
    _save_normalizer(normalizer, output_dir, logger)
    _save_clusterer(clusterer, output_dir, logger)


def _save_autoencoder(model, output_dir: Path, logger) -> None:
    """Save autoencoder model."""
    model_path = output_dir / "autoencoder.pt"
    model.save(str(model_path))
    logger.info(f"Saved autoencoder to {model_path}")


def _save_normalizer(normalizer, output_dir: Path, logger) -> None:
    """Save normalizer."""
    path = output_dir / "normalizer.joblib"
    normalizer.save(str(path))
    logger.info(f"Saved normalizer to {path}")


def _save_clusterer(clusterer, output_dir: Path, logger) -> None:
    """Save clusterer."""
    path = output_dir / "clusterer.joblib"
    clusterer.save(str(path))
    logger.info(f"Saved clusterer to {path}")


def _load_data(args, logger):
    """Load data from path."""
    logger.info(f"Loading data from {args.data}")
    df = load_data_from_path(args.data)
    logger.info(f"Loaded {len(df)} bars")
    return df


def _prepare_training_data(df, args, logger):
    """Prepare features, windows, and normalizer."""
    features_df = compute_features(df, logger)
    windows, _ = prepare_windows(features_df, args.window_size, logger)
    windows_normalized, normalizer = normalize_windows(windows, logger)
    train, val = split_train_val(windows_normalized)
    logger.info(f"Train: {len(train)}, Val: {len(val)}")
    return features_df, windows_normalized, normalizer, train, val


def _create_and_train_model(n_features, train, val, args, logger):
    """Create and train autoencoder model."""
    model = create_autoencoder_model(n_features, args)
    logger.info(f"Model: {args.window_size}x{n_features} -> {args.latent_dim}")
    train_model(model, train, val, args, logger)
    return model


def _cluster_and_save(model, windows_norm, normalizer, df, args, logger):
    """Extract states, cluster, and save models."""
    states = extract_states(model, windows_norm, logger)
    returns = compute_window_returns(df, args.window_size, len(states))
    clusterer = cluster_states(states, returns, args.n_regimes, logger)
    print_regime_summary(clusterer, logger)
    save_models(model, normalizer, clusterer, Path(args.output), logger)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_script_logging(args.verbose, "train_autoencoder")

    try:
        df = _load_data(args, logger)
        features_df, windows_norm, normalizer, train, val = _prepare_training_data(df, args, logger)
    except Exception as e:
        logger.error(f"Failed to prepare data: {e}")
        return 1

    model = _create_and_train_model(features_df.shape[1], train, val, args, logger)
    _cluster_and_save(model, windows_norm, normalizer, df, args, logger)
    logger.info("Training complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

