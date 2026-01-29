#!/usr/bin/env python
"""Analyze HMM states and generate semantic labels.

Usage:
    # Print state analysis for a model
    python scripts/analyze_hmm_states.py --symbol AAPL --model-id state_v001 --timeframe 1Min

    # Save labels to metadata.json
    python scripts/analyze_hmm_states.py --symbol AAPL --model-id state_v001 --timeframe 1Min --save

    # List available models
    python scripts/analyze_hmm_states.py --list-models
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.hmm.artifacts import get_model_path, list_models, ArtifactPaths
from src.hmm.encoders import BaseEncoder
from src.hmm.hmm_model import GaussianHMMWrapper
from src.hmm.scalers import BaseScaler
from src.hmm.labeling import (
    StateLabelingEngine,
    state_labels_to_mapping,
    StateLabel,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze HMM states and generate semantic labels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List available models
    python scripts/analyze_hmm_states.py --list-models

    # Print state analysis
    python scripts/analyze_hmm_states.py --symbol AAPL --model-id state_v001 --timeframe 1Min

    # Save labels to model metadata
    python scripts/analyze_hmm_states.py --symbol AAPL --model-id state_v001 --timeframe 1Min --save

    # Show detailed statistics for each state
    python scripts/analyze_hmm_states.py --symbol AAPL --model-id state_v001 --verbose
        """
    )

    parser.add_argument(
        "--symbol", "-s",
        default=None,
        help="Ticker symbol (e.g., AAPL)"
    )
    parser.add_argument(
        "--model-id", "-m",
        default=None,
        help="Model ID to analyze (e.g., state_v001)"
    )
    parser.add_argument(
        "--timeframe", "-t",
        default="1Min",
        choices=["1Min", "5Min", "15Min", "1Hour", "1Day"],
        help="Timeframe (default: 1Min)"
    )
    parser.add_argument(
        "--models-dir",
        default="models",
        help="Models directory (default: models)"
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save labels to metadata.json"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed statistics for each state"
    )

    return parser.parse_args()


def load_model_artifacts(paths: ArtifactPaths):
    """Load all model artifacts.

    Args:
        paths: ArtifactPaths instance

    Returns:
        Tuple of (scaler, encoder, hmm, metadata)
    """
    if not paths.exists():
        raise FileNotFoundError(f"Model artifacts not found at {paths.model_dir}")

    metadata = paths.load_metadata()
    scaler = BaseScaler.load(paths.scaler_path)
    encoder = BaseEncoder.load(paths.encoder_path)
    hmm = GaussianHMMWrapper.load(paths.hmm_path)

    return scaler, encoder, hmm, metadata


def print_state_labels(labels: dict[int, StateLabel], verbose: bool = False):
    """Print state labels in a formatted table.

    Args:
        labels: Dictionary of state_id -> StateLabel
        verbose: Whether to show detailed info
    """
    print("\n" + "=" * 70)
    print("STATE LABELS")
    print("=" * 70)
    print(f"{'State':<8} {'Label':<25} {'Short':<8} {'Color':<10}")
    print("-" * 70)

    for state_id in sorted(labels.keys()):
        label = labels[state_id]
        print(f"{state_id:<8} {label.label:<25} {label.short_label:<8} {label.color:<10}")
        if verbose:
            print(f"         {label.description}")

    print("=" * 70)


def print_state_statistics(engine: StateLabelingEngine):
    """Print detailed statistics for each state.

    Args:
        engine: StateLabelingEngine instance
    """
    stats = engine.get_state_statistics()
    if not stats:
        print("\nStatistics not available (inverse transform failed)")
        return

    print("\n" + "=" * 70)
    print("STATE STATISTICS (scaled feature space)")
    print("=" * 70)

    for state_id in sorted(stats.keys()):
        s = stats[state_id]
        print(f"\nState {state_id}:")
        print(f"  Return features (r5, r15, r60):")
        for feat in ["r5", "r15", "r60"]:
            if feat in s:
                print(f"    {feat}: {s[feat]:+.4f}")
        print(f"  Volatility features:")
        for feat in ["vol_z_60"]:
            if feat in s:
                print(f"    {feat}: {s[feat]:+.4f}")
        print(f"  Transition dynamics:")
        print(f"    Self-transition prob: {s['self_transition_prob']:.3f}")
        print(f"    Expected duration: {s['expected_duration']:.1f} bars")

    print("=" * 70)


def save_labels_to_metadata(paths: ArtifactPaths, labels: dict[int, StateLabel]):
    """Save state labels to metadata.json.

    Args:
        paths: ArtifactPaths instance
        labels: Dictionary of state_id -> StateLabel
    """
    # Load existing metadata
    with open(paths.metadata_path) as f:
        metadata_dict = json.load(f)

    # Convert labels to mapping format
    state_mapping = state_labels_to_mapping(labels)

    # Update metadata
    metadata_dict["state_mapping"] = state_mapping

    # Save back
    with open(paths.metadata_path, "w") as f:
        json.dump(metadata_dict, f, indent=2)

    logger.info(f"Saved state labels to {paths.metadata_path}")


def main():
    """Main entry point."""
    args = parse_args()
    models_root = Path(args.models_dir)

    # Handle --list-models
    if args.list_models:
        print("\nAvailable models:")
        print("-" * 50)
        # List all ticker directories
        if models_root.exists():
            for ticker_dir in sorted(models_root.iterdir()):
                if ticker_dir.is_dir() and ticker_dir.name.startswith("ticker="):
                    symbol = ticker_dir.name.replace("ticker=", "")
                    print(f"\n{symbol}:")
                    for tf in ["1Min", "5Min", "15Min", "1Hour", "1Day"]:
                        model_ids = list_models(symbol, tf, models_root)
                        if model_ids:
                            print(f"  {tf}:")
                            for model_id in model_ids:
                                paths = get_model_path(symbol, tf, model_id, models_root)
                                status = "OK" if paths.exists() else "incomplete"
                                print(f"    - {model_id} [{status}]")
        print()
        return

    # Validate symbol and model-id are provided
    if not args.symbol:
        logger.error("--symbol is required. Use --list-models to see available models.")
        sys.exit(1)

    if not args.model_id:
        logger.error("--model-id is required. Use --list-models to see available models.")
        sys.exit(1)

    # Get model paths
    paths = get_model_path(args.symbol, args.timeframe, args.model_id, models_root)

    if not paths.exists():
        logger.error(f"Model not found: {paths.model_dir}")
        logger.info("Use --list-models to see available models")
        sys.exit(1)

    # Load model artifacts
    logger.info(f"Loading model from {paths.model_dir}")
    try:
        scaler, encoder, hmm, metadata = load_model_artifacts(paths)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)

    logger.info(f"Model: {metadata.model_id}")
    logger.info(f"States: {metadata.n_states}")
    logger.info(f"Latent dim: {metadata.latent_dim}")
    logger.info(f"Features: {len(metadata.feature_names)}")

    # Create labeling engine
    engine = StateLabelingEngine(
        hmm=hmm,
        scaler=scaler,
        encoder=encoder,
        feature_names=metadata.feature_names,
    )

    # Generate labels
    labels = engine.label_states()

    # Print labels
    print_state_labels(labels, verbose=args.verbose)

    # Print statistics if verbose
    if args.verbose:
        print_state_statistics(engine)

    # Save if requested
    if args.save:
        save_labels_to_metadata(paths, labels)
        logger.info("Labels saved to metadata.json")

    # Print color legend
    print("\nColor Legend:")
    print("-" * 40)
    print("  Greens: Bullish states")
    print("  Reds:   Bearish states")
    print("  Slates: Neutral states")
    print()
    print("Character suffixes:")
    print("  -T: Trending (moderate volatility)")
    print("  -V: Volatile (high volatility)")
    print("  -B: Breakout (very high volatility)")
    print("  -C: Consolidation (low volatility)")


if __name__ == "__main__":
    main()
