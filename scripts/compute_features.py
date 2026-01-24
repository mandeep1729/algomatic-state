#!/usr/bin/env python
"""Compute technical indicators for all tickers and timeframes in the database."""

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


def compute_all_features(version: str = "v1.0") -> dict:
    """Compute technical indicators for all tickers and timeframes.

    Args:
        version: Feature version string for tracking

    Returns:
        Dictionary with computation statistics
    """
    # Check for available indicator calculators (prefer TA-Lib, fallback to pandas-ta)
    calculator = None
    calculator_name = None

    try:
        from src.features import TALibIndicatorCalculator, TALIB_AVAILABLE
        if TALIB_AVAILABLE:
            logger.info("Initializing TA-Lib calculator...")
            calculator = TALibIndicatorCalculator()
            calculator_name = "TA-Lib"
    except ImportError:
        pass

    if calculator is None:
        try:
            from src.features import PandasTAIndicatorCalculator, PANDAS_TA_AVAILABLE
            if PANDAS_TA_AVAILABLE:
                logger.info("TA-Lib not available, using pandas-ta calculator...")
                calculator = PandasTAIndicatorCalculator()
                calculator_name = "pandas-ta"
        except ImportError:
            pass

    if calculator is None:
        logger.error("No indicator calculator available. Install TA-Lib or pandas-ta.")
        return {"error": "No indicator calculator available"}

    logger.info(f"Using {calculator_name} for indicator computation")

    db_manager = get_db_manager()
    stats = {
        "tickers_processed": 0,
        "timeframes_processed": 0,
        "timeframes_skipped": 0,
        "features_stored": 0,
        "errors": [],
    }

    with db_manager.get_session() as session:
        repo = OHLCVRepository(session)

        # Get all tickers
        tickers = repo.list_tickers(active_only=True)
        logger.info(f"Found {len(tickers)} tickers in database")

        for ticker in tickers:
            symbol = ticker.symbol
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing {symbol}...")
            stats["tickers_processed"] += 1

            for timeframe in VALID_TIMEFRAMES:
                try:
                    # Get OHLCV data
                    df = repo.get_bars(symbol, timeframe)

                    if df.empty:
                        logger.debug(f"  {timeframe}: No data, skipping")
                        continue

                    # Check which bars already have features computed
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

                    # Compute indicators on full dataframe (needed for lookback periods)
                    features_df = calculator.compute(df)

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
    logger.info("Starting technical indicator computation for all tickers...")

    stats = compute_all_features(version="v1.0")

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
