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
from src.data.database.market_repository import OHLCVRepository
from src.features.state.hmm.config import create_default_config, load_feature_spec, DEFAULT_FEATURE_SET
from src.features.state.hmm.data_pipeline import GapHandler
from src.features.state.hmm.training import TrainingPipeline, TrainingConfig

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
        epilog=_get_epilog(),
    )
    _add_data_args(parser)
    _add_training_args(parser)
    _add_model_args(parser)
    _add_output_args(parser)
    return parser.parse_args()


def _get_epilog() -> str:
    """Return command help epilog with examples."""
    return """
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


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    """Add data-related arguments."""
    parser.add_argument("--symbol", "-s", required=True, help="Ticker symbol (e.g., AAPL)")
    parser.add_argument("--end", "-e", default=None, help="End date (YYYY-MM-DD). Required unless --list-features")
    parser.add_argument("--start", default=None, help="Start date (default: 1 year before end)")
    parser.add_argument("--timeframe", "-t", default="1Min", choices=["1Min", "5Min", "15Min", "1Hour", "1Day"])
    parser.add_argument("--val-days", type=int, default=30, help="Validation window in days (default: 30)")


def _add_training_args(parser: argparse.ArgumentParser) -> None:
    """Add training-related arguments."""
    parser.add_argument("--n-states", default=None, help="Number of HMM states (default: from config, 'auto' for BIC)")
    parser.add_argument("--latent-dim", type=int, default=None, help="Latent dimension (default: from config)")
    parser.add_argument("--scaler", default="robust", choices=["robust", "standard", "yeo_johnson"])
    parser.add_argument("--covariance", default="diag", choices=["full", "diag", "tied", "spherical"])
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")


def _add_model_args(parser: argparse.ArgumentParser) -> None:
    """Add model output arguments."""
    parser.add_argument("--models-dir", default="models", help="Models output directory")
    parser.add_argument("--list-features", action="store_true", help="List available features and exit")


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    """Add output/verbosity arguments (placeholder for future)."""
    pass


def _list_features(args) -> None:
    """List available features and exit."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)
        sample_df = repo.get_features(symbol=args.symbol, timeframe=args.timeframe, start=None, end=None)

        if sample_df.empty:
            logger.error(f"No features found for {args.symbol}/{args.timeframe}")
            sys.exit(1)

        logger.info(f"Available features for {args.symbol}/{args.timeframe}:")
        for i, col in enumerate(sorted(sample_df.columns), 1):
            print(f"  {i:2d}. {col}")
        logger.info(f"Total: {len(sample_df.columns)} features, {len(sample_df)} rows")
    sys.exit(0)


def _parse_dates(args) -> tuple[datetime, datetime]:
    """Parse and validate start/end dates."""
    if not args.end:
        logger.error("--end date is required for training. Use --list-features to see available data.")
        sys.exit(1)

    end_date = datetime.strptime(args.end, "%Y-%m-%d")
    start_date = datetime.strptime(args.start, "%Y-%m-%d") if args.start else end_date - timedelta(days=365)
    return start_date, end_date


def _get_data_summary(args, db_manager) -> dict:
    """Get data summary for symbol/timeframe and validate availability."""
    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)
        summary = repo.get_data_summary(args.symbol)

        if args.timeframe not in summary:
            logger.error(f"No data found for {args.symbol} at {args.timeframe} timeframe")
            sys.exit(1)

        return summary[args.timeframe]


def _adjust_dates_to_available_data(start_date, end_date, tf_summary) -> tuple[datetime, datetime]:
    """Adjust dates to available data range."""
    data_start = tf_summary['earliest'].replace(tzinfo=None)
    data_end = tf_summary['latest'].replace(tzinfo=None)

    _validate_date_range(start_date, end_date, data_start, data_end)
    start_date, end_date = _clamp_dates(start_date, end_date, data_start, data_end)
    return start_date, end_date


def _validate_date_range(start_date, end_date, data_start, data_end) -> None:
    """Validate requested dates are within available data."""
    if end_date < data_start:
        logger.error(f"Requested end {end_date.date()} is before available data starts ({data_start.date()})")
        logger.info(f"Hint: Use --end {data_end.date()} to use latest available data")
        sys.exit(1)

    if start_date > data_end:
        logger.error(f"Requested start {start_date.date()} is after available data ends ({data_end.date()})")
        sys.exit(1)


def _clamp_dates(start_date, end_date, data_start, data_end) -> tuple[datetime, datetime]:
    """Clamp dates to available data range with warnings."""
    if start_date < data_start:
        logger.warning(f"Requested start {start_date.date()} is before available data {data_start.date()}")
        start_date = data_start
        logger.info(f"Auto-adjusted start date to {start_date.date()}")

    if end_date > data_end:
        logger.warning(f"Requested end {end_date.date()} is after available data {data_end.date()}")
        end_date = data_end
        logger.info(f"Auto-adjusted end date to {end_date.date()}")

    return start_date, end_date


def _calculate_train_val_split(start_date, end_date, val_days) -> tuple:
    """Calculate train/validation date splits."""
    val_end = end_date
    val_start = val_end - timedelta(days=val_days)
    train_end = val_start - timedelta(days=1)
    train_start = start_date

    if train_start >= train_end:
        logger.error(f"Not enough data for training. Start {train_start.date()} >= End {train_end.date()}")
        logger.error(f"Try reducing --val-days (currently {val_days}) or providing more data")
        sys.exit(1)

    return train_start, train_end, val_start, val_end


def _log_training_info(args, train_start, train_end, val_start, val_end) -> None:
    """Log training configuration."""
    logger.info(f"Training HMM model for {args.symbol}")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Training period: {train_start.date()} to {train_end.date()}")
    logger.info(f"Validation period: {val_start.date()} to {val_end.date()}")


def _load_feature_spec(args) -> tuple[list[str], object, object]:
    """Load feature specification from config or defaults."""
    config = None
    config_path = Path("config/state_vector_feature_spec.yaml")

    try:
        if config_path.exists():
            feature_spec = load_feature_spec(config_path, args.timeframe)
            feature_names = feature_spec.feature_names
            config = feature_spec.config
            logger.info(f"Loaded {len(feature_names)} features from {config_path}")
        else:
            config = create_default_config()
            feature_names = config.get_features_for_timeframe(args.timeframe)
            logger.info(f"Using {len(feature_names)} default features")
    except Exception as e:
        logger.warning(f"Could not load feature spec: {e}")
        feature_names = DEFAULT_FEATURE_SET.copy()
        logger.info(f"Using fallback feature set ({len(feature_names)} features)")
        return feature_names, None, None

    tf_config = config.get_timeframe_config(args.timeframe) if config else None
    return feature_names, config, tf_config


def _determine_n_states(args, tf_config) -> int | None:
    """Determine number of HMM states from args or config."""
    if args.n_states:
        if args.n_states.lower() == "auto":
            logger.info("Using auto state selection (BIC)")
            return None
        return int(args.n_states)
    if tf_config:
        logger.info(f"Using n_states={tf_config.n_states} from timeframe config")
        return tf_config.n_states
    return None


def _determine_latent_dim(args, tf_config) -> int | None:
    """Determine latent dimension from args or config."""
    if args.latent_dim is not None:
        return args.latent_dim
    if tf_config:
        logger.info(f"Using latent_dim={tf_config.latent_dim} from timeframe config")
        return tf_config.latent_dim
    return None


def _load_features_from_db(db_manager, args, train_start, train_end, val_start, val_end, tf_summary):
    """Load training and validation features from database."""
    logger.info("Loading pre-computed features from database...")
    logger.info(f"Available data: {tf_summary['bar_count']} bars, {tf_summary['feature_count']} with features")

    if tf_summary['feature_count'] == 0:
        logger.error(f"No computed features found for {args.symbol}/{args.timeframe}")
        logger.error("Run: python scripts/compute_features.py")
        sys.exit(1)

    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)
        train_df = repo.get_features(symbol=args.symbol, timeframe=args.timeframe, start=train_start, end=train_end)
        val_df = repo.get_features(symbol=args.symbol, timeframe=args.timeframe, start=val_start, end=val_end)

    return train_df, val_df


def _validate_loaded_data(train_df, val_df, args, train_start, train_end, val_start, val_end) -> None:
    """Validate that we have sufficient data."""
    if train_df.empty:
        logger.error(f"No training features found for {args.symbol} between {train_start.date()} and {train_end.date()}")
        logger.error("Make sure features are computed: python scripts/compute_features.py")
        sys.exit(1)

    if val_df.empty:
        logger.error(f"No validation features found between {val_start.date()} and {val_end.date()}")
        sys.exit(1)

    logger.info(f"Training data: {len(train_df)} bars ({len(train_df.columns)} features)")
    logger.info(f"Validation data: {len(val_df)} bars")


def _filter_available_features(feature_names, train_df) -> list[str]:
    """Filter feature names to those available in data."""
    available_features = set(train_df.columns)
    missing = [f for f in feature_names if f not in available_features]

    if missing:
        logger.warning(f"Missing features in database: {missing}")

    filtered = [f for f in feature_names if f in available_features]

    if len(filtered) < 3:
        logger.error(f"Too few features available. Found: {list(available_features)[:20]}...")
        sys.exit(1)

    logger.info(f"Using {len(filtered)} features: {filtered[:5]}...")
    return filtered


def _clean_data(train_df, val_df, feature_names, args):
    """Handle gaps and clean NaN values from data."""
    gap_handler = GapHandler(args.timeframe)
    train_df = gap_handler.handle_gaps(train_df)
    val_df = gap_handler.handle_gaps(val_df)

    train_df_clean = train_df[feature_names].dropna()
    val_df_clean = val_df[feature_names].dropna()

    logger.info(f"After cleaning: {len(train_df_clean)} train, {len(val_df_clean)} val")
    _validate_cleaned_data_size(train_df_clean, val_df_clean)
    return train_df_clean, val_df_clean


def _validate_cleaned_data_size(train_df, val_df) -> None:
    """Validate minimum data size after cleaning."""
    if len(train_df) < 100:
        logger.error("Insufficient training data after cleaning (need at least 100 rows)")
        sys.exit(1)

    if len(val_df) < 20:
        logger.error("Insufficient validation data after cleaning (need at least 20 rows)")
        sys.exit(1)


def _create_training_config(args, train_df, val_df, feature_names, n_states, latent_dim) -> TrainingConfig:
    """Create TrainingConfig from arguments and data."""
    return TrainingConfig(
        timeframe=args.timeframe,
        symbols=[args.symbol],
        train_start=train_df.index.min(),
        train_end=train_df.index.max(),
        val_start=val_df.index.min(),
        val_end=val_df.index.max(),
        feature_names=feature_names,
        scaler_type=args.scaler,
        encoder_type="pca",
        latent_dim=latent_dim,
        n_states=n_states,
        covariance_type=args.covariance,
        random_seed=args.seed,
    )


def _run_training(args, config, train_df, val_df):
    """Execute training pipeline and return result."""
    logger.info("Starting training...")
    pipeline = TrainingPipeline(models_root=Path(args.models_dir), random_seed=args.seed)

    try:
        return pipeline.train(config, train_df, val_df)
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


def _log_training_results(result) -> None:
    """Log training results and saved artifacts."""
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


def main():
    """Main entry point."""
    args = parse_args()

    if args.list_features:
        _list_features(args)

    start_date, end_date = _parse_dates(args)
    db_manager = get_db_manager()
    tf_summary = _get_data_summary(args, db_manager)
    start_date, end_date = _adjust_dates_to_available_data(start_date, end_date, tf_summary)
    train_start, train_end, val_start, val_end = _calculate_train_val_split(start_date, end_date, args.val_days)
    _log_training_info(args, train_start, train_end, val_start, val_end)

    feature_names, _, tf_config = _load_feature_spec(args)
    n_states = _determine_n_states(args, tf_config)
    latent_dim = _determine_latent_dim(args, tf_config)

    train_df, val_df = _load_features_from_db(db_manager, args, train_start, train_end, val_start, val_end, tf_summary)
    _validate_loaded_data(train_df, val_df, args, train_start, train_end, val_start, val_end)

    feature_names = _filter_available_features(feature_names, train_df)
    train_df, val_df = _clean_data(train_df, val_df, feature_names, args)

    config = _create_training_config(args, train_df, val_df, feature_names, n_states, latent_dim)
    result = _run_training(args, config, train_df, val_df)
    _log_training_results(result)


if __name__ == "__main__":
    main()
