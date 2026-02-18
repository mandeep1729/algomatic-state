#!/usr/bin/env python3
"""Compute baseline stats for all active (non-app) user accounts.

Uses the reviewer service's baseline computation to aggregate trading
behavior metrics from fill history. Results are saved to user_profiles.stats.

The system 'app' user is naturally excluded since it has no trade fills.

Usage:
    python scripts/compute_baseline.py                     # All active accounts
    python scripts/compute_baseline.py --account-id 5      # Specific account
    python scripts/compute_baseline.py --lookback-days 60   # Custom lookback
    python scripts/compute_baseline.py --dry-run            # List accounts only
    python scripts/compute_baseline.py -v                   # Verbose logging
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from config.settings import get_settings
from scripts.helpers.logging_setup import setup_script_logging


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute baseline stats for active user accounts",
    )
    parser.add_argument(
        "--account-id", type=int, default=None,
        help="Compute for a single account ID (default: all active accounts)",
    )
    parser.add_argument(
        "--lookback-days", type=int, default=None,
        help="Days of fill history to analyze (default: from settings, typically 90)",
    )
    parser.add_argument(
        "--min-fills", type=int, default=None,
        help="Minimum fills required to compute stats (default: from settings, typically 5)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List accounts that would be processed without computing stats",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_script_logging(args.verbose, "compute_baseline")

    settings = get_settings()
    lookback_days = args.lookback_days or settings.checks.baseline_lookback_days
    min_fills = args.min_fills or settings.checks.baseline_min_fills

    # Use REVIEWER_BACKEND_URL if explicitly set, otherwise derive from SERVER_PORT
    import os
    if os.environ.get("REVIEWER_BACKEND_URL"):
        backend_url = settings.reviewer.backend_url
    else:
        backend_url = f"http://localhost:{settings.server.port}"
    logger.info("Backend URL: %s", backend_url)
    logger.info("Lookback: %d days, min fills: %d", lookback_days, min_fills)

    from src.reviewer.api_client import ReviewerApiClient
    api_client = ReviewerApiClient(base_url=backend_url)

    # Determine which accounts to process
    if args.account_id:
        account_ids = [args.account_id]
        logger.info("Target: account_id=%d", args.account_id)
    else:
        account_ids = api_client.get_active_accounts(active_since_days=lookback_days)
        logger.info("Found %d active accounts with fills in last %d days", len(account_ids), lookback_days)

    if not account_ids:
        logger.info("No accounts to process")
        return

    if args.dry_run:
        logger.info("Dry run — accounts that would be processed:")
        for aid in account_ids:
            logger.info("  account_id=%d", aid)
        logger.info("Total: %d accounts", len(account_ids))
        return

    # Compute baseline stats
    from src.reviewer.baseline import compute_baseline_stats

    succeeded = 0
    skipped = 0
    failed = 0

    for aid in account_ids:
        try:
            stats = compute_baseline_stats(
                account_id=aid,
                api_client=api_client,
                lookback_days=lookback_days,
                min_fills=min_fills,
            )
            if stats is not None:
                succeeded += 1
                logger.info(
                    "account_id=%d: baseline computed (%d fills, fomo=%d, discipline=%d)",
                    aid,
                    stats.get("fill_count", 0),
                    stats.get("psychological", {}).get("fomo_index", 0),
                    stats.get("psychological", {}).get("discipline_score", 0),
                )
            else:
                skipped += 1
                logger.info("account_id=%d: skipped (insufficient data)", aid)
        except Exception:
            failed += 1
            logger.exception("account_id=%d: failed", aid)

    logger.info(
        "Done — %d succeeded, %d skipped, %d failed (out of %d accounts)",
        succeeded, skipped, failed, len(account_ids),
    )


if __name__ == "__main__":
    main()
