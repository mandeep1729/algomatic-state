"""CLI entry point for the strategy probe system.

Usage:
    python -m src.strats_prob.cli --symbols AAPL --start 2025-01-01 --end 2025-12-31
    python -m src.strats_prob.cli --seed-strategies
    python -m src.strats_prob.cli --symbols SPY --strategies 1,2,3 --timeframes 1Hour --risk-profiles medium
"""

import argparse
import logging
import sys
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run strategy probes across symbols, timeframes, and risk profiles.",
    )
    parser.add_argument(
        "--symbols", type=str, default="",
        help="Comma-separated list of ticker symbols (e.g., AAPL,SPY,QQQ)",
    )
    parser.add_argument(
        "--timeframes", type=str, default="1Min,15Min,1Hour,1Day",
        help="Comma-separated timeframes (default: 1Min,15Min,1Hour,1Day)",
    )
    parser.add_argument(
        "--risk-profiles", type=str, default="low,medium,high",
        help="Comma-separated risk profiles (default: low,medium,high)",
    )
    parser.add_argument(
        "--strategies", type=str, default="",
        help="Comma-separated strategy IDs to run (default: all)",
    )
    parser.add_argument(
        "--start", type=str, default=None,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--seed-strategies", action="store_true",
        help="Seed strategy catalog to DB without running probes",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Import here to avoid circular imports and trigger strategy registration
    import src.strats_prob  # noqa: F401 - triggers __init__.py registration
    from src.strats_prob.registry import get_all_strategies, seed_strategies_to_db
    from src.strats_prob.runner import ProbeRunConfig, ProbeRunner
    from src.data.database.connection import get_db_manager

    logger.info("Loaded %d strategies", len(get_all_strategies()))

    # Seed strategies to DB
    if args.seed_strategies:
        logger.info("Seeding strategies to database...")
        db = get_db_manager()
        with db.get_session() as session:
            count = seed_strategies_to_db(session)
            logger.info("Seeded %d strategies", count)
        if not args.symbols:
            return 0

    # Validate required args for running probes
    if not args.symbols:
        logger.error("--symbols is required when running probes")
        return 1

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    risk_profiles = [r.strip() for r in args.risk_profiles.split(",") if r.strip()]
    strategy_ids = None
    if args.strategies:
        strategy_ids = [int(s.strip()) for s in args.strategies.split(",") if s.strip()]

    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None

    # Ensure strategies are seeded before running
    db = get_db_manager()
    with db.get_session() as session:
        seed_strategies_to_db(session)

    config = ProbeRunConfig(
        symbols=symbols,
        timeframes=timeframes,
        risk_profiles=risk_profiles,
        strategy_ids=strategy_ids,
        start=start,
        end=end,
    )

    runner = ProbeRunner(config)
    run_id = runner.run()
    logger.info("Run completed with run_id=%s", run_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
