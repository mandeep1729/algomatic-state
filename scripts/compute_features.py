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
from src.data.database.repository import OHLCVRepository
from src.data.database.models import VALID_TIMEFRAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute features for all tickers and timeframes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force recompute all features (ignore existing)"
    )
    parser.add_argument(
        "--symbols", "-s",
        nargs="+",
        help="Only process specific symbols (default: all)"
    )
    parser.add_argument(
        "--timeframes", "-t",
        nargs="+",
        choices=VALID_TIMEFRAMES,
        help="Only process specific timeframes (default: all)"
    )
    parser.add_argument(
        "--version", "-v",
        default="v2.0",
        help="Feature version string (default: v2.0)"
    )
    return parser.parse_args()


def compute_all_features(
    version: str = "v2.0",
    force: bool = False,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
) -> dict:
    """Compute all features (engineered + TA indicators) for all tickers and timeframes.

    Uses FeaturePipeline which computes:
    - Engineered features: r1, r5, r15, r60, clv, vol_z_60, rv_60, etc.
    - TA indicators: RSI, MACD, BB, ADX, etc.

    Args:
        version: Feature version string for tracking
        force: If True, recompute all features (ignore existing)
        symbols: If provided, only process these symbols
        timeframes: If provided, only process these timeframes

    Returns:
        Dictionary with computation statistics
    """
    from src.features import FeaturePipeline

    # Use FeaturePipeline for full feature set (engineered + TA indicators)
    pipeline = FeaturePipeline.default()
    logger.info(f"Using FeaturePipeline with {len(pipeline.feature_names)} features")
    logger.info(f"Max lookback: {pipeline.max_lookback} bars")
    if force:
        logger.info("Force mode: will recompute all features")

    db_manager = get_db_manager()
    stats = {
        "tickers_processed": 0,
        "timeframes_processed": 0,
        "timeframes_skipped": 0,
        "features_stored": 0,
        "errors": [],
    }

    # Determine which timeframes to process
    target_timeframes = timeframes or VALID_TIMEFRAMES

    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)

        # Get tickers to process
        all_tickers = repo.list_tickers(active_only=True)
        if symbols:
            symbols_upper = [s.upper() for s in symbols]
            tickers = [t for t in all_tickers if t.symbol in symbols_upper]
            if not tickers:
                logger.error(f"No matching tickers found for: {symbols}")
                return stats
        else:
            tickers = all_tickers

        logger.info(f"Processing {len(tickers)} tickers")

        for ticker in tickers:
            symbol = ticker.symbol
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing {symbol}...")
            stats["tickers_processed"] += 1

            for timeframe in target_timeframes:
                try:
                    # Get OHLCV data
                    df = repo.get_bars(symbol, timeframe)

                    if df.empty:
                        logger.debug(f"  {timeframe}: No data, skipping")
                        continue

                    # Check which bars already have features computed
                    if force:
                        # Force mode: recompute all
                        missing_timestamps = set(
                            ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
                            for ts in df.index
                        )
                        logger.info(f"  {timeframe}: {len(df)} bars (force recompute)")
                    else:
                        existing_timestamps = repo.get_existing_feature_timestamps(
                            ticker_id=ticker.id,
                            timeframe=timeframe,
                        )

                        # Normalize df index for comparison (ensure timezone-naive)
                        df_timestamps = set(
                            ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts
                            for ts in df.index
                        )

                        # Find bars that need features computed
                        missing_timestamps = df_timestamps - existing_timestamps

                        if not missing_timestamps:
                            logger.info(
                                f"  {timeframe}: All {len(df)} bars already have features, skipping"
                            )
                            stats["timeframes_skipped"] += 1
                            continue

                        logger.info(
                            f"  {timeframe}: {len(df)} bars total, "
                            f"{len(existing_timestamps)} have features, "
                            f"{len(missing_timestamps)} need computation"
                        )

                    # Compute all features on full dataframe (needed for lookback periods)
                    features_df = pipeline.compute(df)

                    if features_df.empty:
                        logger.warning(f"  {timeframe}: No features computed")
                        continue

                    # Filter to only store features for bars that don't have them yet
                    features_df_filtered = features_df[
                        features_df.index.map(
                            lambda ts: (ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo else ts)
                            in missing_timestamps
                        )
                    ]

                    if features_df_filtered.empty:
                        logger.debug(f"  {timeframe}: No new features to store")
                        continue

                    # Store only the new features
                    rows_stored = repo.store_features(
                        features_df=features_df_filtered,
                        ticker_id=ticker.id,
                        timeframe=timeframe,
                        version=version,
                    )

                    stats["timeframes_processed"] += 1
                    stats["features_stored"] += rows_stored

                    logger.info(
                        f"  {timeframe}: Stored {rows_stored} new rows "
                        f"({len(features_df.columns)} indicators)"
                    )

                except Exception as e:
                    error_msg = f"{symbol}/{timeframe}: {str(e)}"
                    logger.error(f"  {timeframe}: ERROR - {e}")
                    stats["errors"].append(error_msg)

        # Commit all changes
        session.commit()

    return stats


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

    if "error" in stats:
        logger.error(f"Fatal error: {stats['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
