#!/usr/bin/env python3
"""Download US-traded ticker symbols from NASDAQ Trader.

Fetches the nasdaqtraded.txt file, parses and filters it, and saves
a clean CSV suitable for seeding the tickers table.

Usage:
    python scripts/download_tickers.py [--output PATH] [--verbose]
"""

import argparse
import csv
import io
import logging
import re
import sys
import urllib.request
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.helpers.logging_setup import setup_script_logging

logger = logging.getLogger(__name__)

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"

DEFAULT_OUTPUT = Path(__file__).parent.parent / "config" / "seed" / "us_tickers.csv"

EXCHANGE_MAP = {
    "N": "NYSE",
    "Q": "NASDAQ",
    "P": "NYSE Arca",
    "Z": "BATS",
    "V": "IEX",
    "A": "NYSE American",
}

# Suffixes to strip from security names
NAME_SUFFIXES = re.compile(r"\s*[-–]\s*Common Stock[s]?$|\s*Common Stock[s]?$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download US-traded ticker symbols from NASDAQ Trader",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return parser.parse_args()


def fetch_nasdaq_traded() -> str:
    """Fetch NASDAQ traded symbols data from the source URL."""
    logger.info(f"Fetching {NASDAQ_TRADED_URL}")
    with urllib.request.urlopen(NASDAQ_TRADED_URL) as resp:
        data = resp.read().decode("utf-8")
    logger.debug(f"Downloaded {len(data)} bytes")
    return data


def _clean_name(raw_name: str) -> str:
    cleaned = NAME_SUFFIXES.sub("", raw_name).strip()
    return cleaned[:255]


def parse_tickers(raw_text: str) -> list[dict]:
    """Parse ticker data from NASDAQ trader text format."""
    reader = csv.DictReader(io.StringIO(raw_text), delimiter="|")
    tickers = []
    skipped = {"test": 0, "not_traded": 0, "preferred": 0, "no_symbol": 0}

    for row in reader:
        symbol = (row.get("Symbol") or row.get("NASDAQ Symbol") or "").strip()
        if not symbol:
            skipped["no_symbol"] += 1
            continue

        # Skip test issues
        if row.get("Test Issue", "").strip().upper() == "Y":
            skipped["test"] += 1
            continue

        # Skip non-traded
        if row.get("Nasdaq Traded", "").strip().upper() != "Y":
            skipped["not_traded"] += 1
            continue

        # Skip preferred shares (contain $)
        if "$" in symbol:
            skipped["preferred"] += 1
            continue

        exchange_code = row.get("Listing Exchange", "").strip()
        exchange = EXCHANGE_MAP.get(exchange_code, exchange_code)

        etf_flag = row.get("ETF", "").strip().upper()
        asset_type = "etf" if etf_flag == "Y" else "stock"

        raw_name = row.get("Security Name", "").strip()
        name = _clean_name(raw_name)

        tickers.append({
            "symbol": symbol.upper(),
            "name": name,
            "exchange": exchange,
            "asset_type": asset_type,
        })

    logger.info(f"Parsed {len(tickers)} tickers")
    for reason, count in skipped.items():
        if count:
            logger.debug(f"Skipped ({reason}): {count}")

    return tickers


def write_csv(tickers: list[dict], output_path: Path) -> None:
    """Write tickers to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name", "exchange", "asset_type"])
        writer.writeheader()
        writer.writerows(tickers)
    logger.debug(f"Wrote {len(tickers)} tickers to {output_path}")


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_script_logging(args.verbose, __name__)

    try:
        raw_text = fetch_nasdaq_traded()
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return 1

    tickers = parse_tickers(raw_text)
    if not tickers:
        logger.error("No tickers parsed - check the data source")
        return 1

    write_csv(tickers, args.output)
    logger.info(f"Saved {len(tickers)} US-traded tickers to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
