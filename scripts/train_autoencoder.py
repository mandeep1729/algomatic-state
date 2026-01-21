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
import pandas as pd
import torch

from src.features.pipeline import FeaturePipeline
from src.state.windows import create_windows
from src.state.normalization import Normalizer
from src.state.autoencoder import TemporalAutoencoder, AutoencoderConfig
from src.state.clustering import RegimeClusterer
from src.utils.logging import setup_logging, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train state autoencoder model",
    )

    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to data file or directory",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="models",
        help="Output directory for trained model (default: models)",
    )

    parser.add_argument(
        "--window-size",
        type=int,
        default=60,
        help="Temporal window size (default: 60)",
    )

    parser.add_argument(
        "--latent-dim",
        type=int,
        default=16,
        help="Latent dimension (default: 16)",
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs (default: 50)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size (default: 64)",
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
        help="Learning rate (default: 0.001)",
    )

    parser.add_argument(
        "--n-regimes",
        type=int,
        default=5,
        help="Number of regimes for clustering (default: 5)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def load_data(path: str) -> pd.DataFrame:
    """Load data from file or directory.

    Args:
        path: Path to file or directory

    Returns:
        Combined DataFrame
    """
    path = Path(path)

    if path.is_file():
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        elif path.suffix == ".csv":
            return pd.read_csv(path, index_col=0, parse_dates=True)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    elif path.is_dir():
        # Load all parquet files
        dfs = []
        for file in path.glob("*.parquet"):
            df = pd.read_parquet(file)
            dfs.append(df)

        if not dfs:
            raise ValueError(f"No parquet files found in {path}")

        return pd.concat(dfs).sort_index()

    else:
        raise ValueError(f"Path does not exist: {path}")


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(
        level="DEBUG" if args.verbose else "INFO",
        format="text",
    )
    logger = get_logger("train_autoencoder")

    # Load data
    logger.info(f"Loading data from {args.data}")
    try:
        df = load_data(args.data)
        logger.info(f"Loaded {len(df)} bars")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return 1

    # Compute features
    logger.info("Computing features...")
    pipeline = FeaturePipeline()
    features_df = pipeline.compute(df)
    logger.info(f"Computed {len(features_df.columns)} features")

    # Drop NaN rows
    features_df = features_df.dropna()
    logger.info(f"After dropping NaN: {len(features_df)} rows")

    if len(features_df) < args.window_size * 2:
        logger.error("Not enough data for training")
        return 1

    # Create windows
    logger.info(f"Creating temporal windows (size={args.window_size})")
    windows, timestamps = create_windows(
        features_df.values,
        window_size=args.window_size,
        stride=1,
    )
    logger.info(f"Created {len(windows)} windows")

    # Normalize
    logger.info("Normalizing features...")
    normalizer = Normalizer(method="zscore", clip_std=3.0)
    windows_normalized = normalizer.fit_transform(windows)

    # Split train/val
    train_size = int(0.8 * len(windows_normalized))
    train_windows = windows_normalized[:train_size]
    val_windows = windows_normalized[train_size:]

    logger.info(f"Train: {len(train_windows)}, Val: {len(val_windows)}")

    # Create model
    n_features = features_df.shape[1]
    config = AutoencoderConfig(
        window_size=args.window_size,
        n_features=n_features,
        latent_dim=args.latent_dim,
    )
    model = TemporalAutoencoder(config)

    logger.info(f"Model architecture: {args.window_size}x{n_features} -> {args.latent_dim}")

    # Train
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

    # Extract states
    logger.info("Extracting state representations...")
    states = model.encode(windows_normalized)
    logger.info(f"State shape: {states.shape}")

    # Cluster into regimes
    logger.info(f"Clustering into {args.n_regimes} regimes...")

    # Calculate forward returns for regime labeling
    close_prices = df["close"].values
    returns = np.zeros(len(df))
    returns[:-1] = np.log(close_prices[1:] / close_prices[:-1])

    # Align returns with windows
    window_returns = returns[args.window_size - 1 : args.window_size - 1 + len(states)]

    clusterer = RegimeClusterer(n_clusters=args.n_regimes)
    clusterer.fit(states, window_returns)

    # Print regime summary
    logger.info("\nRegime Summary:")
    for info in clusterer.get_regime_summary():
        logger.info(
            f"  Regime {info['label']}: size={info['size']}, "
            f"sharpe={info['sharpe']:.2f}, mean_ret={info['mean_return']*10000:.2f}bps"
        )

    # Save models
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "autoencoder.pt"
    model.save(str(model_path))
    logger.info(f"Saved autoencoder to {model_path}")

    normalizer_path = output_dir / "normalizer.joblib"
    normalizer.save(str(normalizer_path))
    logger.info(f"Saved normalizer to {normalizer_path}")

    clusterer_path = output_dir / "clusterer.joblib"
    clusterer.save(str(clusterer_path))
    logger.info(f"Saved clusterer to {clusterer_path}")

    logger.info("Training complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
