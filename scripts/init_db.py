#!/usr/bin/env python3
"""Initialize the PostgreSQL database.

This script:
1. Runs Alembic migrations to create/update tables
2. Optionally seeds the database with common tickers

Usage:
    python scripts/init_db.py [--seed]

Options:
    --seed              Seed database with common ticker symbols
    --skip-migrations   Skip Alembic migrations (use direct table creation)
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository

SEED_CSV_PATH = project_root / "config" / "seed" / "us_tickers.csv"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Initialize the PostgreSQL database")
    parser.add_argument("--seed", action="store_true", help="Seed database with common ticker symbols")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip Alembic migrations")
    return parser.parse_args()


def _print_header() -> None:
    """Print initialization header."""
    print("=" * 60)
    print("Algomatic State - Database Initialization")
    print("=" * 60)


def check_database_connection() -> bool:
    """Check if database is accessible. Returns True if successful."""
    try:
        settings = get_settings()
        print(f"Checking database connection to: {settings.database.host}:{settings.database.port}/{settings.database.name}")
        db_manager = get_db_manager()
        if db_manager.health_check():
            print("Database connection successful!")
            return True
        print("Database connection failed!")
        return False
    except Exception as e:
        print(f"Database connection error: {e}")
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
    print("\nRunning Alembic migrations...")
    try:
        result = _run_alembic_command()
        if result.returncode == 0:
            print("Migrations completed successfully!")
            if result.stdout:
                print(result.stdout)
            return True
        print(f"Migration failed with error:")
        print(result.stderr)
        return False
    except FileNotFoundError:
        print("Alembic not found. Please install it: pip install alembic")
        return False
    except Exception as e:
        print(f"Migration error: {e}")
        return False


def _load_seed_csv() -> list[dict]:
    """Load tickers from the seed CSV file."""
    with open(SEED_CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def seed_tickers() -> bool:
    """Seed database with tickers from CSV. Returns True if successful."""
    print("\nSeeding database with US-traded tickers...")

    if not SEED_CSV_PATH.exists():
        print(f"Seed CSV not found: {SEED_CSV_PATH}")
        print("Run: python scripts/download_tickers.py")
        return False

    try:
        tickers = _load_seed_csv()
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)
            count = repo.bulk_upsert_tickers(tickers)
        print(f"Seeding completed! Upserted {count} tickers from {SEED_CSV_PATH.name}.")
        return True
    except Exception as e:
        print(f"Seeding error: {e}")
        return False


def create_tables_directly() -> bool:
    """Create tables directly using SQLAlchemy. Returns True if successful."""
    print("\nCreating tables directly...")
    try:
        db_manager = get_db_manager()
        db_manager.create_tables()
        print("Tables created successfully!")
        return True
    except Exception as e:
        print(f"Table creation error: {e}")
        return False


def _print_connection_hint() -> None:
    """Print hint for starting PostgreSQL."""
    print("\nMake sure PostgreSQL is running:")
    print("  docker-compose up -d postgres")


def _print_footer() -> None:
    """Print completion footer."""
    print("\n" + "=" * 60)
    print("Database initialization completed!")
    print("=" * 60)


def _handle_migrations(args) -> bool:
    """Handle migration or direct table creation. Returns True if successful."""
    if args.skip_migrations:
        return create_tables_directly()

    if run_migrations():
        return True

    print("\nTrying direct table creation as fallback...")
    return create_tables_directly()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    _print_header()

    if not check_database_connection():
        _print_connection_hint()
        sys.exit(1)

    if not _handle_migrations(args):
        sys.exit(1)

    if args.seed and not seed_tickers():
        sys.exit(1)

    _print_footer()


if __name__ == "__main__":
    main()
