#!/usr/bin/env python
"""Compute all features (engineered + TA indicators) for all tickers and timeframes.

Features computed:
- Engineered: r1, r5, r15, r60, clv, vol_z_60, rv_60, range_z_60, etc.
- TA indicators: RSI, MACD, BB, ADX, stoch_k, etc.

Usage:
    python scripts/compute_features.py                    # Compute missing features
    python scripts/compute_features.py --force            # Recompute all features
    python scripts/compute_features.py --symbols AAPL     # Specific symbols only
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.database.models import VALID_TIMEFRAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Compute features for all tickers and timeframes")
    _add_args(parser)
    return parser.parse_args()


def _add_args(parser: argparse.ArgumentParser) -> None:
    """Add command line arguments."""
    parser.add_argument("--force", "-f", action="store_true", help="Force recompute all features")
    parser.add_argument("--symbols", "-s", nargs="+", help="Only process specific symbols")
    parser.add_argument("--timeframes", "-t", nargs="+", choices=VALID_TIMEFRAMES, help="Only process specific timeframes")
    parser.add_argument("--version", "-v", default="v2.0", help="Feature version string")


def _create_pipeline():
    """Create feature pipeline and log info."""
    from src.features import FeaturePipeline
    pipeline = FeaturePipeline.default()
    logger.info(f"Using FeaturePipeline with {len(pipeline.feature_names)} features")
    logger.info(f"Max lookback: {pipeline.max_lookback} bars")
    return pipeline


def _init_stats() -> dict:
    """Initialize statistics dictionary."""
    return {
        "tickers_processed": 0,
        "timeframes_processed": 0,
        "timeframes_skipped": 0,
        "features_stored": 0,
        "errors": [],
    }


def _get_tickers(repo, symbols: list[str] | None):
    """Get list of tickers to process."""
    all_tickers = repo.list_tickers(active_only=True)
    if not symbols:
        return all_tickers

    symbols_upper = [s.upper() for s in symbols]
    return [t for t in all_tickers if t.symbol in symbols_upper]


def _normalize_timestamps(index) -> set:
    """Convert timestamps to timezone-naive for comparison."""
    return set(
        ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
        for ts in index
    )


def _get_missing_timestamps(df, repo, ticker, timeframe, force: bool) -> set | None:
    """Determine which timestamps need feature computation."""
    df_timestamps = _normalize_timestamps(df.index)

    if force:
        logger.info(f"  {timeframe}: {len(df)} bars (force recompute)")
        return df_timestamps

    existing = repo.get_existing_feature_timestamps(ticker_id=ticker.id, timeframe=timeframe)
    missing = df_timestamps - existing

    if not missing:
        logger.info(f"  {timeframe}: All {len(df)} bars already have features, skipping")
        return None

    logger.info(f"  {timeframe}: {len(df)} bars total, {len(existing)} have features, {len(missing)} need computation")
    return missing


def _filter_features_to_store(features_df, missing_timestamps):
    """Filter features DataFrame to only rows that need storing."""
    return features_df[
        features_df.index.map(
            lambda ts: (ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts)
            in missing_timestamps
        )
    ]


def _process_timeframe(repo, ticker, timeframe, pipeline, version, force, stats) -> None:
    """Process a single timeframe for a ticker."""
    df = repo.get_bars(ticker.symbol, timeframe)
    if df.empty:
        logger.debug(f"  {timeframe}: No data, skipping")
        return

    missing = _get_missing_timestamps(df, repo, ticker, timeframe, force)
    if missing is None:
        stats["timeframes_skipped"] += 1
        return

    features_df = pipeline.compute_incremental(df, new_bars=len(missing))
    if features_df.empty:
        logger.warning(f"  {timeframe}: No features computed")
        return

    filtered = _filter_features_to_store(features_df, missing)
    if filtered.empty:
        logger.debug(f"  {timeframe}: No new features to store")
        return

    rows = repo.store_features(features_df=filtered, ticker_id=ticker.id, timeframe=timeframe, version=version)
    stats["timeframes_processed"] += 1
    stats["features_stored"] += rows
    logger.info(f"  {timeframe}: Stored {rows} new rows ({len(features_df.columns)} indicators)")


def _process_ticker(repo, ticker, timeframes, pipeline, version, force, stats) -> None:
    """Process all timeframes for a single ticker."""
    logger.info(f"\n{'='*50}")
    logger.info(f"Processing {ticker.symbol}...")
    stats["tickers_processed"] += 1

    for timeframe in timeframes:
        try:
            _process_timeframe(repo, ticker, timeframe, pipeline, version, force, stats)
        except Exception as e:
            error_msg = f"{ticker.symbol}/{timeframe}: {str(e)}"
            logger.error(f"  {timeframe}: ERROR - {e}")
            stats["errors"].append(error_msg)


def compute_all_features(
    version: str = "v2.0",
    force: bool = False,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
) -> dict:
    """Compute all features for all tickers and timeframes."""
    if force:
        logger.info("Force mode: will recompute all features")

    pipeline = _create_pipeline()
    stats = _init_stats()
    target_timeframes = timeframes or VALID_TIMEFRAMES
    db_manager = get_db_manager()

    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)
        tickers = _get_tickers(repo, symbols)

        if not tickers:
            logger.error(f"No matching tickers found for: {symbols}")
            return stats

        logger.info(f"Processing {len(tickers)} tickers")

        for ticker in tickers:
            _process_ticker(repo, ticker, target_timeframes, pipeline, version, force, stats)

        session.commit()

    return stats


def _log_results(stats: dict) -> None:
    """Log computation results."""
    logger.info("\n" + "="*50)
    logger.info("COMPUTATION COMPLETE")
    logger.info("="*50)
    logger.info(f"Tickers processed: {stats.get('tickers_processed', 0)}")
    logger.info(f"Timeframes processed: {stats.get('timeframes_processed', 0)}")
    logger.info(f"Timeframes skipped (already computed): {stats.get('timeframes_skipped', 0)}")
    logger.info(f"Feature rows stored: {stats.get('features_stored', 0)}")

    if stats.get("errors"):
        logger.warning(f"Errors encountered: {len(stats['errors'])}")
        for err in stats["errors"]:
            logger.warning(f"  - {err}")


def main():
    """Main entry point."""
    args = parse_args()
    logger.info("Starting feature computation...")

    stats = compute_all_features(
        version=args.version,
        force=args.force,
        symbols=args.symbols,
        timeframes=args.timeframes,
    )

    _log_results(stats)

    if "error" in stats:
        logger.error(f"Fatal error: {stats['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
