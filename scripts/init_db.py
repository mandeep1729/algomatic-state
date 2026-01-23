#!/usr/bin/env python3
"""Initialize the PostgreSQL database.

This script:
1. Runs Alembic migrations to create/update tables
2. Optionally seeds the database with common tickers

Usage:
    python scripts/init_db.py [--seed]

Options:
    --seed    Seed database with common ticker symbols
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from src.data.database.connection import get_db_manager
from src.data.database.repository import OHLCVRepository


COMMON_TICKERS = [
    ("SPY", "SPDR S&P 500 ETF Trust", "NYSE Arca", "etf"),
    ("QQQ", "Invesco QQQ Trust", "NASDAQ", "etf"),
    ("IWM", "iShares Russell 2000 ETF", "NYSE Arca", "etf"),
    ("AAPL", "Apple Inc.", "NASDAQ", "stock"),
    ("MSFT", "Microsoft Corporation", "NASDAQ", "stock"),
    ("GOOGL", "Alphabet Inc.", "NASDAQ", "stock"),
    ("AMZN", "Amazon.com Inc.", "NASDAQ", "stock"),
    ("TSLA", "Tesla Inc.", "NASDAQ", "stock"),
    ("NVDA", "NVIDIA Corporation", "NASDAQ", "stock"),
    ("META", "Meta Platforms Inc.", "NASDAQ", "stock"),
]


def check_database_connection() -> bool:
    """Check if database is accessible."""
    try:
        settings = get_settings()
        print(f"Checking database connection to: {settings.database.host}:{settings.database.port}/{settings.database.name}")

        db_manager = get_db_manager()
        if db_manager.health_check():
            print("Database connection successful!")
            return True
        else:
            print("Database connection failed!")
            return False
    except Exception as e:
        print(f"Database connection error: {e}")
        return False


def run_migrations():
    """Run Alembic migrations."""
    print("\nRunning Alembic migrations...")

    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("Migrations completed successfully!")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"Migration failed with error:")
            print(result.stderr)
            return False

    except FileNotFoundError:
        print("Alembic not found. Please install it: pip install alembic")
        return False
    except Exception as e:
        print(f"Migration error: {e}")
        return False

    return True


def seed_tickers():
    """Seed database with common tickers."""
    print("\nSeeding database with common tickers...")

    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            for symbol, name, exchange, asset_type in COMMON_TICKERS:
                ticker = repo.get_or_create_ticker(
                    symbol=symbol,
                    name=name,
                    exchange=exchange,
                    asset_type=asset_type,
                )
                print(f"  Added/verified ticker: {ticker.symbol} ({ticker.name})")

        print(f"Seeding completed! Added {len(COMMON_TICKERS)} tickers.")
        return True

    except Exception as e:
        print(f"Seeding error: {e}")
        return False


def create_tables_directly():
    """Create tables directly using SQLAlchemy (alternative to Alembic)."""
    print("\nCreating tables directly...")

    try:
        db_manager = get_db_manager()
        db_manager.create_tables()
        print("Tables created successfully!")
        return True
    except Exception as e:
        print(f"Table creation error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Initialize the PostgreSQL database")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed database with common ticker symbols",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip Alembic migrations (use direct table creation)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Algomatic State - Database Initialization")
    print("=" * 60)

    # Check database connection
    if not check_database_connection():
        print("\nMake sure PostgreSQL is running:")
        print("  docker-compose up -d postgres")
        sys.exit(1)

    # Run migrations or create tables directly
    if args.skip_migrations:
        if not create_tables_directly():
            sys.exit(1)
    else:
        if not run_migrations():
            print("\nTrying direct table creation as fallback...")
            if not create_tables_directly():
                sys.exit(1)

    # Seed if requested
    if args.seed:
        if not seed_tickers():
            sys.exit(1)

    print("\n" + "=" * 60)
    print("Database initialization completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
