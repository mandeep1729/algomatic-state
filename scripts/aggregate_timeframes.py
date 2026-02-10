#!/usr/bin/env python
"""Aggregate higher-timeframe bars from existing 1Min data.

Builds 15Min and 1Hour bars by resampling 1-minute ticks stored in the
database, and fetches 1Day bars from the configured market data provider.

Usage:
    python scripts/aggregate_timeframes.py --symbols AAPL,SPY
    python scripts/aggregate_timeframes.py --symbols AAPL --timeframes 15Min,1Hour
    python scripts/aggregate_timeframes.py --all --timeframes 15Min,1Hour,1Day
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.helpers.logging_setup import setup_script_logging
from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.timeframe_aggregator import (
    DEFAULT_TARGET_TIMEFRAMES,
    TimeframeAggregator,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate higher-timeframe bars from 1Min data",
    )

    symbol_group = parser.add_mutually_exclusive_group(required=True)
    symbol_group.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of symbols (e.g., AAPL,SPY,MSFT)",
    )
    symbol_group.add_argument(
        "--all",
        action="store_true",
        dest="all_symbols",
        help="Process all active tickers in the database",
    )

    parser.add_argument(
        "--timeframes",
        type=str,
        default=",".join(DEFAULT_TARGET_TIMEFRAMES),
        help=(
            "Comma-separated target timeframes "
            f"(default: {','.join(DEFAULT_TARGET_TIMEFRAMES)})"
        ),
    )
    parser.add_argument(
        "--with-daily",
        action="store_true",
        default=False,
        help="Enable fetching 1Day bars from Alpaca (requires API credentials)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args()


def resolve_symbols(args: argparse.Namespace, logger) -> list[str]:
    """Resolve the list of symbols to process.

    Args:
        args: Parsed CLI arguments.
        logger: Logger instance.

    Returns:
        List of uppercase symbol strings.
    """
    if args.all_symbols:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            tickers = repo.list_tickers(active_only=True)
            symbols = [t.symbol for t in tickers]
        logger.info("Found %d active tickers in database", len(symbols))
        return symbols

    return [s.strip().upper() for s in args.symbols.split(",") if s.strip()]


def build_provider(with_daily: bool, logger):
    """Optionally build an Alpaca provider for daily bar fetching.

    Args:
        with_daily: Whether daily bars should be fetched.
        logger: Logger instance.

    Returns:
        MarketDataProvider or None.
    """
    if not with_daily:
        return None

    try:
        from src.marketdata.alpaca_provider import AlpacaProvider
        provider = AlpacaProvider()
        logger.info("Alpaca provider initialised for daily bar fetching")
        return provider
    except Exception as exc:
        logger.warning("Could not initialise Alpaca provider: %s", exc)
        return None


def aggregate_symbol(
    aggregator: TimeframeAggregator,
    symbol: str,
    timeframes: list[str],
    logger,
) -> dict[str, int]:
    """Run aggregation for a single symbol.

    Args:
        aggregator: Configured TimeframeAggregator.
        symbol: Stock symbol.
        timeframes: Target timeframes.
        logger: Logger instance.

    Returns:
        Mapping of timeframe to bars inserted.
    """
    try:
        return aggregator.aggregate_missing_timeframes(symbol, timeframes)
    except Exception as exc:
        logger.error("Failed to aggregate %s: %s", symbol, exc)
        return {}


def main() -> int:
    """Entry point for the aggregation CLI."""
    args = parse_args()
    logger = setup_script_logging(args.verbose, "aggregate_timeframes")

    symbols = resolve_symbols(args, logger)
    if not symbols:
        logger.error("No symbols to process")
        return 1

    timeframes = [tf.strip() for tf in args.timeframes.split(",") if tf.strip()]
    logger.info("Target timeframes: %s", timeframes)
    logger.info("Symbols to process: %s", ", ".join(symbols))

    provider = build_provider(args.with_daily, logger)

    # Filter out 1Day if no provider and user didn't explicitly ask
    if provider is None and "1Day" in timeframes:
        logger.info(
            "No provider available, removing 1Day from target timeframes. "
            "Pass --with-daily to enable."
        )
        timeframes = [tf for tf in timeframes if tf != "1Day"]

    if not timeframes:
        logger.error("No valid timeframes to process")
        return 1

    aggregator = TimeframeAggregator(provider=provider)

    total_inserted = 0
    for symbol in symbols:
        result = aggregate_symbol(aggregator, symbol, timeframes, logger)
        symbol_total = sum(result.values())
        total_inserted += symbol_total
        if symbol_total > 0:
            logger.info(
                "%s: inserted %d bars (%s)",
                symbol, symbol_total, result,
            )

    logger.info(
        "Aggregation complete. Processed %d symbols, inserted %d total bars.",
        len(symbols), total_inserted,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
