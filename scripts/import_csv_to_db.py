#!/usr/bin/env python3
"""Import CSV or Parquet files into the PostgreSQL database.

This script imports existing market data files into the database.
It supports both CSV and Parquet formats.

Usage:
    python scripts/import_csv_to_db.py AAPL --file data/raw/AAPL_1Min.parquet
    python scripts/import_csv_to_db.py AAPL --file data/AAPL.csv --timeframe 1Min
    python scripts/import_csv_to_db.py --all --dir data/raw  # Import all files
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.helpers.logging_setup import setup_script_logging
from src.data.database.connection import get_db_manager
from src.data.database.models import VALID_TIMEFRAMES
from src.data.loaders.database_loader import DatabaseLoader

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Import CSV or Parquet files into the PostgreSQL database")
    _add_symbol_args(parser)
    _add_file_args(parser)
    _add_directory_args(parser)
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def _add_symbol_args(parser: argparse.ArgumentParser) -> None:
    """Add symbol-related arguments."""
    parser.add_argument("symbol", nargs="?", help="Stock symbol to associate with the data")
    parser.add_argument("--timeframe", default="1Min", choices=list(VALID_TIMEFRAMES), help="Timeframe (default: 1Min)")


def _add_file_args(parser: argparse.ArgumentParser) -> None:
    """Add file-related arguments."""
    parser.add_argument("--file", type=Path, help="Path to CSV or Parquet file")


def _add_directory_args(parser: argparse.ArgumentParser) -> None:
    """Add directory import arguments."""
    parser.add_argument("--all", action="store_true", help="Import all files in directory")
    parser.add_argument("--dir", type=Path, default=project_root / "data" / "raw", help="Directory containing files")
    parser.add_argument("--pattern", default="*.parquet", help="Glob pattern for file matching")


def extract_symbol_timeframe(filename: str) -> tuple[str, str]:
    """Extract symbol and timeframe from filename."""
    stem = Path(filename).stem
    parts = stem.split("_")

    if len(parts) >= 2 and parts[1] in VALID_TIMEFRAMES:
        return parts[0].upper(), parts[1]
    return stem.upper(), "1Min"


def _check_database_connection() -> None:
    """Check database connection and exit on failure."""
    try:
        db_manager = get_db_manager()
        if not db_manager.health_check():
            logger.error("Cannot connect to database")
            logger.error("Make sure PostgreSQL is running: docker-compose up -d postgres")
            sys.exit(1)
        logger.info("Database connection: OK")
    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


def _import_file_with_loader(file_path: Path, symbol: str, timeframe: str, loader: DatabaseLoader) -> int:
    """Import a file using an existing loader. Returns rows imported."""
    try:
        if file_path.suffix.lower() == ".parquet":
            rows = loader.import_parquet(file_path, symbol, timeframe)
        else:
            rows = loader.import_csv(file_path, symbol, timeframe)
        logger.debug(f"Imported {rows} rows from {file_path.name}")
        return rows
    except Exception as e:
        logger.error(f"Error importing {file_path.name}: {e}")
        return 0


def import_file(file_path: Path, symbol: str | None = None, timeframe: str | None = None, loader: DatabaseLoader | None = None) -> int:
    """Import a single file into the database. Returns rows imported."""
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return 0

    if symbol is None or timeframe is None:
        extracted_symbol, extracted_timeframe = extract_symbol_timeframe(file_path.name)
        symbol = symbol or extracted_symbol
        timeframe = timeframe or extracted_timeframe

    logger.info(f"Importing {file_path.name} as {symbol}/{timeframe}")
    loader = loader or DatabaseLoader(validate=True, auto_fetch=False)
    return _import_file_with_loader(file_path, symbol, timeframe, loader)


def import_directory(directory: Path, pattern: str = "*.parquet", timeframe: str | None = None) -> tuple[int, int]:
    """Import all matching files from a directory. Returns (files_imported, total_rows)."""
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return 0, 0

    files = list(directory.glob(pattern))
    if not files:
        logger.warning(f"No files matching '{pattern}' found in {directory}")
        return 0, 0

    logger.info(f"Found {len(files)} files to import")
    return _import_file_list(files, timeframe)


def _import_file_list(files: list[Path], timeframe: str | None) -> tuple[int, int]:
    """Import a list of files. Returns (files_imported, total_rows)."""
    loader = DatabaseLoader(validate=True, auto_fetch=False)
    files_imported = 0
    total_rows = 0

    for file_path in sorted(files):
        rows = import_file(file_path, timeframe=timeframe, loader=loader)
        if rows > 0:
            files_imported += 1
            total_rows += rows

    return files_imported, total_rows


def _print_header() -> None:
    """Print script header."""
    logger.info("=" * 60)
    logger.info("Algomatic State - Data Import")
    logger.info("=" * 60)


def _handle_directory_import(args) -> None:
    """Handle --all directory import mode."""
    timeframe_override = args.timeframe if args.timeframe != "1Min" else None
    files_imported, total_rows = import_directory(args.dir, args.pattern, timeframe_override)
    logger.info(f"Import complete: {files_imported} files, {total_rows} total rows")


def _handle_single_file_import(args) -> None:
    """Handle single file import mode."""
    if not args.symbol:
        args.symbol, _ = extract_symbol_timeframe(args.file.name)

    rows = import_file(args.file, args.symbol, args.timeframe)
    if rows > 0:
        logger.info(f"Import complete: {rows} rows imported for {args.symbol}/{args.timeframe}")
    else:
        logger.error("Import failed")
        sys.exit(1)


def _print_usage() -> None:
    """Print help and usage examples."""
    logger.info("Usage examples:")
    logger.info("  python scripts/import_csv_to_db.py AAPL --file data/raw/AAPL_1Min.parquet")
    logger.info("  python scripts/import_csv_to_db.py --all --dir data/raw --pattern '*.parquet'")


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_script_logging(getattr(args, 'verbose', False), __name__)

    _print_header()
    _check_database_connection()

    if args.all:
        _handle_directory_import(args)
    elif args.file:
        _handle_single_file_import(args)
    else:
        _print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
