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

from src.data.loaders.alpaca_loader import AlpacaLoader
from src.data.cache import DataCache
from scripts.helpers.logging_setup import setup_script_logging


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Download historical market data from Alpaca",
    )
    _add_symbol_args(parser)
    _add_date_args(parser)
    _add_output_args(parser)
    return parser.parse_args()


def _add_symbol_args(parser: argparse.ArgumentParser) -> None:
    """Add symbol-related arguments."""
    parser.add_argument(
        "symbols",
        nargs="+",
        help="Symbols to download (e.g., AAPL MSFT)",
    )


def _add_date_args(parser: argparse.ArgumentParser) -> None:
    """Add date-related arguments."""
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to download (default: 30, used if --start not specified)",
    )


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    """Add output-related arguments."""
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
    parser.add_argument("--cache", action="store_true", help="Use cache layer")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def parse_date_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    """Determine start and end dates from arguments."""
    end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=args.days)
    return start_date, end_date


def initialize_loader(use_cache: bool) -> AlpacaLoader:
    """Create and return AlpacaLoader instance."""
    if use_cache:
        cache = DataCache(cache_dir=Path("data/cache"))
        return AlpacaLoader(cache=cache)
    return AlpacaLoader()


def download_symbol(
    loader: AlpacaLoader,
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: str,
    output_dir: Path,
    logger,
) -> bool:
    """Download data for a single symbol. Returns True on success."""
    logger.info(f"Downloading {symbol}...")
    try:
        df = loader.load(symbol=symbol, start=start, end=end, timeframe=timeframe)
        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return False
        return _save_symbol_data(df, symbol, timeframe, output_dir, logger)
    except Exception as e:
        logger.error(f"Failed to download {symbol}: {e}")
        return False


def _save_symbol_data(df, symbol: str, timeframe: str, output_dir: Path, logger) -> bool:
    """Save downloaded data to parquet file."""
    output_path = output_dir / f"{symbol}_{timeframe}.parquet"
    df.to_parquet(output_path)
    logger.info(f"Saved {len(df)} bars to {output_path}")
    return True


def _log_download_info(start, end, symbols, timeframe, logger) -> None:
    """Log download information."""
    logger.info(f"Downloading data from {start.date()} to {end.date()}")
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Timeframe: {timeframe}")


def _download_all_symbols(loader, args, start, end, output_dir, logger) -> int:
    """Download all symbols and return success count."""
    return sum(
        download_symbol(loader, sym, start, end, args.timeframe, output_dir, logger)
        for sym in args.symbols
    )


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_script_logging(args.verbose, "download_data")
    start_date, end_date = parse_date_range(args)
    _log_download_info(start_date, end_date, args.symbols, args.timeframe, logger)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        loader = initialize_loader(args.cache)
    except Exception as e:
        logger.error(f"Failed to initialize loader: {e}")
        return 1

    success = _download_all_symbols(loader, args, start_date, end_date, output_dir, logger)
    logger.info(f"Downloaded {success}/{len(args.symbols)} symbols successfully")
    return 0 if success == len(args.symbols) else 1


if __name__ == "__main__":
    sys.exit(main())

