#!/usr/bin/env python
"""Train HMM state vector model from command line.

Usage:
    python scripts/train_hmm.py --symbol AAPL --end 2025-01-15 --timeframe 1Min
    python scripts/train_hmm.py --symbol AAPL --end 2025-01-15 --timeframe 1Hour --val-days 14
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database.connection import get_db_manager
from src.data.database.repository import OHLCVRepository
from src.hmm.config import load_feature_spec
from src.hmm.data_pipeline import GapHandler
from src.hmm.training import TrainingPipeline, TrainingConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train HMM state vector model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List available features in database
    python scripts/train_hmm.py --symbol AAPL --timeframe 1Min --list-features

    # Train 1-minute model for AAPL with data up to Jan 15th
    python scripts/train_hmm.py --symbol AAPL --end 2025-01-15 --timeframe 1Min

    # Train hourly model with custom validation window
    python scripts/train_hmm.py --symbol AAPL --end 2025-01-15 --timeframe 1Hour --val-days 14

    # Train with specific start date
    python scripts/train_hmm.py --symbol AAPL --start 2024-01-01 --end 2025-01-15

    # Auto-select number of states via BIC
    python scripts/train_hmm.py --symbol AAPL --end 2025-01-15 --n-states auto
        """
    )

    parser.add_argument(
        "--symbol", "-s",
        required=True,
        help="Ticker symbol (e.g., AAPL)"
    )
    parser.add_argument(
        "--end", "-e",
        default=None,
        help="End date for training data (YYYY-MM-DD). Required unless --list-features"
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Start date for training data (default: 1 year before end)"
    )
    parser.add_argument(
        "--timeframe", "-t",
        default="1Min",
        choices=["1Min", "5Min", "15Min", "1Hour", "1Day"],
        help="Timeframe (default: 1Min)"
    )
    parser.add_argument(
        "--val-days",
        type=int,
        default=30,
        help="Validation window in days (default: 30)"
    )
    parser.add_argument(
        "--n-states",
        default=None,
        help="Number of HMM states (default: from config, 'auto' for BIC selection)"
    )
    parser.add_argument(
        "--latent-dim",
        type=int,
        default=None,
        help="Latent dimension (default: from config, None for auto)"
    )
    parser.add_argument(
        "--scaler",
        default="robust",
        choices=["robust", "standard", "yeo_johnson"],
        help="Scaler type (default: robust)"
    )
    parser.add_argument(
        "--covariance",
        default="diag",
        choices=["full", "diag", "tied", "spherical"],
        help="HMM covariance type (default: diag)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--models-dir",
        default="models",
        help="Models output directory (default: models)"
    )
    parser.add_argument(
        "--list-features",
        action="store_true",
        help="List available features in database and exit"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Handle --list-features option (doesn't require --end)
    if args.list_features:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            # Get a sample of features to list available columns
            sample_df = repo.get_features(
                symbol=args.symbol,
                timeframe=args.timeframe,
                start=None,
                end=None,
            )

            if sample_df.empty:
                logger.error(f"No features found for {args.symbol}/{args.timeframe}")
                sys.exit(1)

            logger.info(f"Available features for {args.symbol}/{args.timeframe}:")
            for i, col in enumerate(sorted(sample_df.columns), 1):
                print(f"  {i:2d}. {col}")
            logger.info(f"Total: {len(sample_df.columns)} features, {len(sample_df)} rows")
        sys.exit(0)

    # Validate --end is provided for training
    if not args.end:
        logger.error("--end date is required for training. Use --list-features to see available data.")
        sys.exit(1)

    # Parse dates
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        # Default to 1 year of data
        start_date = end_date - timedelta(days=365)

    # Calculate train/val split
    val_days = args.val_days
    val_end = end_date
    val_start = val_end - timedelta(days=val_days)
    train_end = val_start - timedelta(days=1)  # Gap of 1 day to prevent leakage
    train_start = start_date

    logger.info(f"Training HMM model for {args.symbol}")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Training period: {train_start.date()} to {train_end.date()}")
    logger.info(f"Validation period: {val_start.date()} to {val_end.date()}")

    # Load feature spec
    feature_spec = None
    try:
        feature_spec = load_feature_spec()
        feature_names = feature_spec.base_features
        logger.info(f"Using {len(feature_names)} features from config")
    except Exception as e:
        logger.warning(f"Could not load feature spec: {e}")
        # Fallback to a minimal feature set
        feature_names = [
            "r5", "r15", "r60", "vol_z_60", "macd", "stoch_k",
            "rv_15", "rv_60", "clv", "bb_width"
        ]
        logger.info(f"Using fallback feature set: {feature_names}")

    # Get timeframe-specific config
    tf_config = None
    if feature_spec is not None and hasattr(feature_spec, 'timeframe_configs'):
        tf_config = feature_spec.timeframe_configs.get(args.timeframe)

    # Determine n_states
    n_states = None
    if args.n_states:
        if args.n_states.lower() == "auto":
            n_states = None  # Auto-select via BIC
            logger.info("Using auto state selection (BIC)")
        else:
            n_states = int(args.n_states)
    elif tf_config:
        n_states = tf_config.n_states
        logger.info(f"Using n_states={n_states} from timeframe config")

    # Determine latent_dim
    latent_dim = args.latent_dim
    if latent_dim is None and tf_config:
        latent_dim = tf_config.latent_dim
        logger.info(f"Using latent_dim={latent_dim} from timeframe config")

    # Load pre-computed features from database
    logger.info("Loading pre-computed features from database...")
    db_manager = get_db_manager()

    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)

        # Check data availability
        summary = repo.get_data_summary(args.symbol)
        if args.timeframe not in summary:
            logger.error(f"No data found for {args.symbol} at {args.timeframe} timeframe")
            sys.exit(1)

        tf_summary = summary[args.timeframe]
        logger.info(f"Available data: {tf_summary['bar_count']} bars, {tf_summary['feature_count']} with features")
        logger.info(f"Date range: {tf_summary['earliest']} to {tf_summary['latest']}")

        if tf_summary['feature_count'] == 0:
            logger.error(f"No computed features found for {args.symbol}/{args.timeframe}")
            logger.error("Run: python scripts/compute_features.py")
            sys.exit(1)

        # Load training features from computed_features table
        train_df = repo.get_features(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start=train_start,
            end=train_end,
        )

        # Load validation features
        val_df = repo.get_features(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start=val_start,
            end=val_end,
        )

    if train_df.empty:
        logger.error(f"No training features found for {args.symbol} between {train_start.date()} and {train_end.date()}")
        logger.error("Make sure features are computed: python scripts/compute_features.py")
        sys.exit(1)

    if val_df.empty:
        logger.error(f"No validation features found for {args.symbol} between {val_start.date()} and {val_end.date()}")
        sys.exit(1)

    logger.info(f"Training data: {len(train_df)} bars ({len(train_df.columns)} features)")
    logger.info(f"Validation data: {len(val_df)} bars")

    # Check which requested features are available in the data
    available_features = set(train_df.columns)
    missing_features = [f for f in feature_names if f not in available_features]

    if missing_features:
        logger.warning(f"Missing features in database: {missing_features}")

    # Use only features that exist in the data
    feature_names = [f for f in feature_names if f in available_features]

    if len(feature_names) < 3:
        logger.error(f"Too few features available. Found: {list(available_features)[:20]}...")
        sys.exit(1)

    logger.info(f"Using {len(feature_names)} features: {feature_names[:5]}...")

    # Handle gaps
    gap_handler = GapHandler(args.timeframe)
    train_df = gap_handler.handle_gaps(train_df)
    val_df = gap_handler.handle_gaps(val_df)

    # Drop rows with any NaN values in selected features
    train_df_clean = train_df[feature_names].dropna()
    val_df_clean = val_df[feature_names].dropna()

    logger.info(f"After cleaning: {len(train_df_clean)} train, {len(val_df_clean)} val")

    if len(train_df_clean) < 100:
        logger.error("Insufficient training data after cleaning (need at least 100 rows)")
        sys.exit(1)

    if len(val_df_clean) < 20:
        logger.error("Insufficient validation data after cleaning (need at least 20 rows)")
        sys.exit(1)

    # Create training config
    config = TrainingConfig(
        timeframe=args.timeframe,
        symbols=[args.symbol],
        train_start=train_df_clean.index.min(),
        train_end=train_df_clean.index.max(),
        val_start=val_df_clean.index.min(),
        val_end=val_df_clean.index.max(),
        feature_names=feature_names,
        scaler_type=args.scaler,
        encoder_type="pca",
        latent_dim=latent_dim,
        n_states=n_states,
        covariance_type=args.covariance,
        random_seed=args.seed,
    )

    # Train model
    logger.info("Starting training...")
    pipeline = TrainingPipeline(
        models_root=Path(args.models_dir),
        random_seed=args.seed,
    )

    try:
        result = pipeline.train(config, train_df_clean, val_df_clean)
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise

    # Print results
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Model ID: {result.model_id}")
    logger.info(f"Model saved to: {result.paths.model_dir}")
    logger.info(f"Number of states: {result.hmm.n_states}")
    logger.info(f"Latent dimension: {result.encoder.latent_dim}")
    logger.info("\nMetrics:")
    for key, value in result.metrics.items():
        logger.info(f"  {key}: {value:.4f}")

    logger.info("\nArtifacts saved:")
    logger.info(f"  Scaler: {result.paths.scaler_path}")
    logger.info(f"  Encoder: {result.paths.encoder_path}")
    logger.info(f"  HMM: {result.paths.hmm_path}")
    logger.info(f"  Metadata: {result.paths.metadata_path}")


if __name__ == "__main__":
    main()
