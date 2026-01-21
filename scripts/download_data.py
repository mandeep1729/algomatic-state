#!/usr/bin/env python
"""Download historical market data from Alpaca.

Usage:
    python scripts/download_data.py AAPL --start 2024-01-01 --end 2024-06-01
    python scripts/download_data.py AAPL MSFT GOOGL --days 30
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import pandas as pd

from src.data.loaders.alpaca_loader import AlpacaLoader
from src.data.cache import DataCache
from src.utils.logging import setup_logging, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Download historical market data from Alpaca",
    )

    parser.add_argument(
        "symbols",
        nargs="+",
        help="Symbols to download (e.g., AAPL MSFT)",
    )

    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to download (default: 30, used if --start not specified)",
    )

    parser.add_argument(
        "--timeframe",
        type=str,
        default="1Min",
        choices=["1Min", "5Min", "15Min", "1Hour", "1Day"],
        help="Bar timeframe (default: 1Min)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Output directory (default: data/raw)",
    )

    parser.add_argument(
        "--cache",
        action="store_true",
        help="Use cache layer",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(
        level="DEBUG" if args.verbose else "INFO",
        format="text",
    )
    logger = get_logger("download_data")

    # Determine date range
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=args.days)

    logger.info(f"Downloading data from {start_date.date()} to {end_date.date()}")
    logger.info(f"Symbols: {', '.join(args.symbols)}")
    logger.info(f"Timeframe: {args.timeframe}")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize loader
    try:
        if args.cache:
            cache = DataCache(cache_dir=Path("data/cache"))
            loader = AlpacaLoader(cache=cache)
        else:
            loader = AlpacaLoader()
    except Exception as e:
        logger.error(f"Failed to initialize loader: {e}")
        logger.error("Make sure ALPACA_API_KEY and ALPACA_SECRET_KEY are set")
        return 1

    # Download data for each symbol
    success_count = 0
    for symbol in args.symbols:
        logger.info(f"Downloading {symbol}...")

        try:
            df = loader.load(
                symbol=symbol,
                start=start_date,
                end=end_date,
                timeframe=args.timeframe,
            )

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                continue

            # Save to parquet
            output_path = output_dir / f"{symbol}_{args.timeframe}.parquet"
            df.to_parquet(output_path)

            logger.info(f"Saved {len(df)} bars to {output_path}")
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to download {symbol}: {e}")

    logger.info(f"Downloaded {success_count}/{len(args.symbols)} symbols successfully")

    return 0 if success_count == len(args.symbols) else 1


if __name__ == "__main__":
    sys.exit(main())
