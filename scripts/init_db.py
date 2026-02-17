#!/usr/bin/env python3
"""Initialize the PostgreSQL database.

This script:
1. Runs Alembic migrations to create/update tables
2. Optionally seeds the database with app user, benchmark strategies, and tickers

Usage:
    python scripts/init_db.py [--seed]

Options:
    --seed              Seed database with app user, benchmark strategies, and tickers
    --skip-migrations   Skip Alembic migrations (use direct table creation)
"""

import argparse
import csv
import json
import logging
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from scripts.helpers.logging_setup import setup_script_logging
from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.data.database.trading_repository import TradingBuddyRepository

logger = logging.getLogger(__name__)

SEED_CSV_PATH = project_root / "config" / "seed" / "us_tickers.csv"
BENCHMARK_STRATEGIES_PATH = project_root / "benchmark_strategies.json"

# Mapping from JSON signal timeframe descriptions to supported timeframe codes
TIMEFRAME_MAP = {
    "Daily": ["1Day"],
    "15m–1h (intraday) or Daily": ["15Min", "1Hour", "1Day"],
    "Daily or 60m": ["1Hour", "1Day"],
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Initialize the PostgreSQL database")
    parser.add_argument("--seed", action="store_true", help="Seed database with common ticker symbols")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip Alembic migrations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def _print_header() -> None:
    """Print initialization header."""
    logger.info("=" * 60)
    logger.info("Algomatic State - Database Initialization")
    logger.info("=" * 60)


def check_database_connection() -> bool:
    """Check if database is accessible. Returns True if successful."""
    try:
        settings = get_settings()
        logger.info(f"Checking database connection to: {settings.database.host}:{settings.database.port}/{settings.database.name}")
        db_manager = get_db_manager()
        if db_manager.health_check():
            logger.info("Database connection successful!")
            return True
        logger.error("Database connection failed!")
        return False
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False


def _run_alembic_command() -> subprocess.CompletedProcess:
    """Run alembic upgrade command."""
    return subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )


def run_migrations() -> bool:
    """Run Alembic migrations. Returns True if successful."""
    logger.info("Running Alembic migrations...")
    try:
        result = _run_alembic_command()
        if result.returncode == 0:
            logger.info("Migrations completed successfully!")
            if result.stdout:
                logger.debug(result.stdout)
            return True
        logger.error("Migration failed with error:")
        logger.error(result.stderr)
        return False
    except FileNotFoundError:
        logger.error("Alembic not found. Please install it: pip install alembic")
        return False
    except Exception as e:
        logger.error(f"Migration error: {e}")
        return False


def _load_seed_csv() -> list[dict]:
    """Load tickers from the seed CSV file."""
    with open(SEED_CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def seed_tickers() -> bool:
    """Seed database with tickers from CSV. Returns True if successful."""
    logger.info("Seeding database with US-traded tickers...")

    if not SEED_CSV_PATH.exists():
        logger.error(f"Seed CSV not found: {SEED_CSV_PATH}")
        logger.error("Run: python scripts/download_tickers.py")
        return False

    try:
        tickers = _load_seed_csv()
        logger.debug(f"Loaded {len(tickers)} tickers from seed file")
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            count = repo.bulk_upsert_tickers(tickers)
        logger.info(f"Seeding completed! Upserted {count} tickers from {SEED_CSV_PATH.name}")
        return True
    except Exception as e:
        logger.error(f"Seeding error: {e}")
        return False


def _format_criteria(criteria: dict) -> str:
    """Format entry/exit criteria from JSON into a single text block."""
    parts = []
    for section, rules in criteria.items():
        label = section.replace("_", " ").title()
        parts.append(f"{label}:")
        for rule in rules:
            parts.append(f"- {rule}")
        parts.append("")
    return "\n".join(parts).strip()


def _extract_max_risk_pct(strategy_json: dict) -> float:
    """Extract max risk percentage from strategy ID."""
    risk_map = {
        "momentum_timeframe_trend_following": 1.0,
        "pattern_classic_bull_flag_breakout": 1.0,
        "breakout_20day_donchian": 0.75,
        "mean_reversion_bollinger_revert": 0.75,
        "volume_flow_obv_breakout_confirmed": 0.5,
        "regime_switch_volatility_trend_combo": 0.5,
    }
    return risk_map.get(strategy_json["id"], 1.0)


# Mapping from strategy category to implied_strategy_family
FAMILY_MAP = {
    "momentum": "momentum",
    "pattern": "breakout",
    "breakout": "breakout",
    "mean-reversion": "mean_reversion",
    "volume flow": "breakout",
    "regime": "trend",
}


def _map_timeframes(signal_timeframe: str) -> list[str]:
    """Map JSON signal timeframe to supported timeframe codes."""
    return TIMEFRAME_MAP.get(signal_timeframe, ["1Day"])


def seed_app_user_and_strategies() -> bool:
    """Seed the app user and benchmark strategies. Returns True if successful."""
    logger.info("Seeding app user and benchmark strategies...")

    if not BENCHMARK_STRATEGIES_PATH.exists():
        logger.error(f"Benchmark strategies file not found: {BENCHMARK_STRATEGIES_PATH}")
        return False

    try:
        with open(BENCHMARK_STRATEGIES_PATH) as f:
            data = json.load(f)
        strategies_json = data["strategies"]
        logger.debug(f"Loaded {len(strategies_json)} strategies from benchmark file")

        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = TradingBuddyRepository(session)

            # Ensure app user exists
            app_account = repo.get_account_by_external_id("app")
            if app_account is None:
                app_account = repo.create_account(
                    external_user_id="app",
                    name="App User",
                    email="app@pyrsquare.com",
                    google_id="na",
                    auth_provider="na",
                )
                logger.info(f"Created app user account id={app_account.id}")
            else:
                logger.info(f"App user already exists id={app_account.id}")

            # Seed benchmark strategies
            created_count = 0
            for s in strategies_json:
                name = f"{s['category'].title()}: {s['name']}"
                existing = repo.get_strategy_by_name(app_account.id, name)
                if existing:
                    logger.debug(f"Strategy already exists: {name}")
                    continue

                strategy = repo.create_strategy(
                    account_id=app_account.id,
                    name=name,
                    description=s.get("description"),
                    risk_profile={"tags": s.get("tags", [])},
                )
                # Update additional fields not covered by create_strategy
                strategy.direction = "both"
                strategy.timeframes = _map_timeframes(s["timeframe"]["signal"])
                strategy.entry_criteria = _format_criteria(s["entry_criteria"])
                strategy.exit_criteria = _format_criteria(s["exit_criteria"])
                strategy.max_risk_pct = _extract_max_risk_pct(s)
                strategy.min_risk_reward = 1.5
                strategy.implied_strategy_family = FAMILY_MAP.get(s["category"], "trend")
                session.flush()

                created_count += 1
                logger.info(f"Seeded strategy: {name}")

            session.commit()
            logger.info(f"Seeding completed! Created {created_count} new strategies")
        return True
    except Exception as e:
        logger.error(f"Seeding app user/strategies error: {e}")
        return False


def create_tables_directly() -> bool:
    """Create tables directly using SQLAlchemy. Returns True if successful."""
    logger.info("Creating tables directly...")
    try:
        db_manager = get_db_manager()
        db_manager.create_tables()
        logger.info("Tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"Table creation error: {e}")
        return False


def _print_connection_hint() -> None:
    """Print hint for starting PostgreSQL."""
    logger.info("Make sure PostgreSQL is running:")
    logger.info("  docker-compose up -d postgres")


def _print_footer() -> None:
    """Print completion footer."""
    logger.info("=" * 60)
    logger.info("Database initialization completed!")
    logger.info("=" * 60)


def _handle_migrations(args) -> bool:
    """Handle migration or direct table creation. Returns True if successful."""
    if args.skip_migrations:
        return create_tables_directly()

    if run_migrations():
        return True

    logger.warning("Trying direct table creation as fallback...")
    return create_tables_directly()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_script_logging(args.verbose, __name__)

    _print_header()

    if not check_database_connection():
        _print_connection_hint()
        sys.exit(1)

    if not _handle_migrations(args):
        sys.exit(1)

    if args.seed:
        if not seed_app_user_and_strategies():
            sys.exit(1)
        if not seed_tickers():
            sys.exit(1)

    _print_footer()


if __name__ == "__main__":
    main()
