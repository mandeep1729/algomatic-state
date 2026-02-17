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

from src.features.state.hmm.artifacts import get_model_path, list_models, ArtifactPaths
from src.features.state.hmm.encoders import BaseEncoder
from src.features.state.hmm.hmm_model import GaussianHMMWrapper
from src.features.state.hmm.scalers import BaseScaler
from src.features.state.hmm.labeling import (
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
        epilog=_get_epilog(),
    )
    _add_model_args(parser)
    _add_output_args(parser)
    return parser.parse_args()


def _get_epilog() -> str:
    """Return command help epilog with examples."""
    return """
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


def _add_model_args(parser: argparse.ArgumentParser) -> None:
    """Add model identification arguments."""
    parser.add_argument("--symbol", "-s", default=None, help="Ticker symbol (e.g., AAPL)")
    parser.add_argument("--model-id", "-m", default=None, help="Model ID to analyze (e.g., state_v001)")
    parser.add_argument("--timeframe", "-t", default="1Min", choices=["1Min", "5Min", "15Min", "1Hour", "1Day"])
    parser.add_argument("--models-dir", default="models", help="Models directory")


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    """Add output control arguments."""
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")
    parser.add_argument("--save", action="store_true", help="Save labels to metadata.json")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed statistics")


def _list_ticker_models(models_root: Path) -> None:
    """List all available models organized by ticker."""
    print("\nAvailable models:")
    print("-" * 50)

    if not models_root.exists():
        print("No models directory found")
        return

    for ticker_dir in sorted(models_root.iterdir()):
        if ticker_dir.is_dir() and ticker_dir.name.startswith("ticker="):
            _print_ticker_models(ticker_dir, models_root)
    print()


def _print_ticker_models(ticker_dir: Path, models_root: Path) -> None:
    """Print all models for a single ticker."""
    symbol = ticker_dir.name.replace("ticker=", "")
    print(f"\n{symbol}:")

    for tf in ["1Min", "5Min", "15Min", "1Hour", "1Day"]:
        model_ids = list_models(symbol, tf, models_root)
        if model_ids:
            _print_timeframe_models(tf, model_ids, symbol, models_root)


def _print_timeframe_models(tf: str, model_ids: list, symbol: str, models_root: Path) -> None:
    """Print models for a specific timeframe."""
    print(f"  {tf}:")
    for model_id in model_ids:
        paths = get_model_path(symbol, tf, model_id, models_root)
        status = "OK" if paths.exists() else "incomplete"
        print(f"    - {model_id} [{status}]")


def load_model_artifacts(paths: ArtifactPaths):
    """Load all model artifacts. Returns (scaler, encoder, hmm, metadata)."""
    if not paths.exists():
        raise FileNotFoundError(f"Model artifacts not found at {paths.model_dir}")

    metadata = paths.load_metadata()
    scaler = BaseScaler.load(paths.scaler_path)
    encoder = BaseEncoder.load(paths.encoder_path)
    hmm = GaussianHMMWrapper.load(paths.hmm_path)
    return scaler, encoder, hmm, metadata


def print_state_labels(labels: dict[int, StateLabel], verbose: bool = False) -> None:
    """Print state labels in a formatted table."""
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


def save_labels_to_metadata(paths: ArtifactPaths, labels: dict[int, StateLabel]) -> None:
    """Save state labels to metadata.json."""
    with open(paths.metadata_path) as f:
        metadata_dict = json.load(f)

    metadata_dict["state_mapping"] = state_labels_to_mapping(labels)

    with open(paths.metadata_path, "w") as f:
        json.dump(metadata_dict, f, indent=2)

    logger.info(f"Saved state labels to {paths.metadata_path}")


def _validate_args(args) -> None:
    """Validate required arguments for analysis."""
    if not args.symbol:
        logger.error("--symbol is required. Use --list-models to see available models.")
        sys.exit(1)

    if not args.model_id:
        logger.error("--model-id is required. Use --list-models to see available models.")
        sys.exit(1)


def _load_and_log_model(paths):
    """Load model artifacts and log info. Returns (scaler, encoder, hmm, metadata)."""
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
    return scaler, encoder, hmm, metadata


def _print_color_legend() -> None:
    """Print the color legend for state labels."""
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


def _analyze_model(args, paths) -> None:
    """Perform model analysis and optionally save labels."""
    scaler, encoder, hmm, metadata = _load_and_log_model(paths)

    engine = StateLabelingEngine(
        hmm=hmm, scaler=scaler, encoder=encoder, feature_names=metadata.feature_names
    )
    labels = engine.label_states()

    print_state_labels(labels, verbose=args.verbose)

    if args.save:
        save_labels_to_metadata(paths, labels)
        logger.info("Labels saved to metadata.json")

    _print_color_legend()


def main():
    """Main entry point."""
    args = parse_args()
    models_root = Path(args.models_dir)

    if args.list_models:
        _list_ticker_models(models_root)
        return

    _validate_args(args)
    paths = get_model_path(args.symbol, args.timeframe, args.model_id, models_root)

    if not paths.exists():
        logger.error(f"Model not found: {paths.model_dir}")
        logger.info("Use --list-models to see available models")
        sys.exit(1)

    _analyze_model(args, paths)


if __name__ == "__main__":
    main()
