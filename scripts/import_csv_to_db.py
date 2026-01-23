#!/usr/bin/env python3
"""Import CSV or Parquet files into the PostgreSQL database.

This script imports existing market data files into the database.
It supports both CSV and Parquet formats.

Usage:
    python scripts/import_csv_to_db.py AAPL --file data/raw/AAPL_1Min.parquet
    python scripts/import_csv_to_db.py AAPL --file data/AAPL.csv --timeframe 1Min
    python scripts/import_csv_to_db.py --all --dir data/raw  # Import all files

Options:
    symbol              Stock symbol to associate with the data
    --file PATH         Path to CSV or Parquet file
    --timeframe TF      Timeframe of the data (default: 1Min)
    --all               Import all files in directory
    --dir PATH          Directory containing files to import
    --pattern GLOB      Glob pattern for file matching (default: *.parquet)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database.connection import get_db_manager
from src.data.database.models import VALID_TIMEFRAMES
from src.data.loaders.database_loader import DatabaseLoader


def extract_symbol_timeframe(filename: str) -> tuple[str, str]:
    """Extract symbol and timeframe from filename.

    Expected format: SYMBOL_TIMEFRAME.parquet or SYMBOL_TIMEFRAME.csv
    Examples: AAPL_1Min.parquet, SPY_1Hour.csv

    Args:
        filename: Name of the file (without directory)

    Returns:
        Tuple of (symbol, timeframe)
    """
    stem = Path(filename).stem  # Remove extension
    parts = stem.split("_")

    if len(parts) >= 2:
        symbol = parts[0].upper()
        timeframe = parts[1]

        # Validate timeframe
        if timeframe in VALID_TIMEFRAMES:
            return symbol, timeframe

    # Default: use entire stem as symbol, assume 1Min timeframe
    return stem.upper(), "1Min"


def import_file(
    file_path: Path,
    symbol: str | None = None,
    timeframe: str | None = None,
    loader: DatabaseLoader | None = None,
) -> int:
    """Import a single file into the database.

    Args:
        file_path: Path to the file
        symbol: Symbol to use (extracted from filename if not provided)
        timeframe: Timeframe to use (extracted from filename if not provided)
        loader: Optional DatabaseLoader instance to reuse

    Returns:
        Number of rows imported
    """
    if not file_path.exists():
        print(f"  Error: File not found: {file_path}")
        return 0

    # Extract symbol and timeframe from filename if not provided
    if symbol is None or timeframe is None:
        extracted_symbol, extracted_timeframe = extract_symbol_timeframe(file_path.name)
        symbol = symbol or extracted_symbol
        timeframe = timeframe or extracted_timeframe

    print(f"  Importing {file_path.name} as {symbol}/{timeframe}...")

    if loader is None:
        loader = DatabaseLoader(validate=True, auto_fetch=False)

    try:
        if file_path.suffix.lower() == ".parquet":
            rows = loader.import_parquet(file_path, symbol, timeframe)
        else:
            rows = loader.import_csv(file_path, symbol, timeframe)

        print(f"    Imported {rows} rows")
        return rows

    except Exception as e:
        print(f"    Error: {e}")
        return 0


def import_directory(
    directory: Path,
    pattern: str = "*.parquet",
    timeframe: str | None = None,
) -> tuple[int, int]:
    """Import all matching files from a directory.

    Args:
        directory: Directory containing files
        pattern: Glob pattern for file matching
        timeframe: Optional timeframe override for all files

    Returns:
        Tuple of (files_imported, total_rows)
    """
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 0, 0

    files = list(directory.glob(pattern))
    if not files:
        print(f"No files matching '{pattern}' found in {directory}")
        return 0, 0

    print(f"Found {len(files)} files to import")

    loader = DatabaseLoader(validate=True, auto_fetch=False)
    files_imported = 0
    total_rows = 0

    for file_path in sorted(files):
        rows = import_file(file_path, timeframe=timeframe, loader=loader)
        if rows > 0:
            files_imported += 1
            total_rows += rows

    return files_imported, total_rows


def main():
    parser = argparse.ArgumentParser(
        description="Import CSV or Parquet files into the PostgreSQL database"
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        help="Stock symbol to associate with the data",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to CSV or Parquet file",
    )
    parser.add_argument(
        "--timeframe",
        default="1Min",
        choices=list(VALID_TIMEFRAMES),
        help="Timeframe of the data (default: 1Min)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import all files in directory",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=project_root / "data" / "raw",
        help="Directory containing files to import (default: data/raw)",
    )
    parser.add_argument(
        "--pattern",
        default="*.parquet",
        help="Glob pattern for file matching (default: *.parquet)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Algomatic State - Data Import")
    print("=" * 60)

    # Check database connection
    try:
        db_manager = get_db_manager()
        if not db_manager.health_check():
            print("Error: Cannot connect to database")
            print("Make sure PostgreSQL is running: docker-compose up -d postgres")
            sys.exit(1)
        print("Database connection: OK")
    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)

    print()

    if args.all:
        # Import all files from directory
        files_imported, total_rows = import_directory(
            args.dir,
            args.pattern,
            args.timeframe if args.timeframe != "1Min" else None,
        )
        print()
        print(f"Import complete: {files_imported} files, {total_rows} total rows")

    elif args.file:
        # Import single file
        if not args.symbol:
            # Extract symbol from filename
            args.symbol, _ = extract_symbol_timeframe(args.file.name)

        rows = import_file(args.file, args.symbol, args.timeframe)
        print()
        if rows > 0:
            print(f"Import complete: {rows} rows imported for {args.symbol}/{args.timeframe}")
        else:
            print("Import failed")
            sys.exit(1)

    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/import_csv_to_db.py AAPL --file data/raw/AAPL_1Min.parquet")
        print("  python scripts/import_csv_to_db.py --all --dir data/raw --pattern '*.parquet'")
        sys.exit(1)


if __name__ == "__main__":
    main()
