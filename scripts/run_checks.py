#!/usr/bin/env python3
"""Run behavioral checks (Risk Sanity + Entry Quality) for a user's fills.

Runs CheckRunner against all fills with decision contexts for the specified
account, using the reviewer service's API-client mode for indicator data.

Usage:
    python scripts/run_checks.py --account-id 8               # All recent fills
    python scripts/run_checks.py --account-id 8 --lookback-days 30
    python scripts/run_checks.py --account-id 8 --dry-run      # List fills only
    python scripts/run_checks.py --account-id 8 -v             # Verbose logging
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "proto" / "gen" / "python"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from config.settings import get_settings
from scripts.helpers.logging_setup import setup_script_logging


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run behavioral checks for a user's fills",
    )
    parser.add_argument(
        "--account-id", type=int, required=True,
        help="Account ID to run checks for",
    )
    parser.add_argument(
        "--lookback-days", type=int, default=90,
        help="Days of fill history to check (default: 90)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List fills that would be checked without running checks",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_script_logging(args.verbose, "run_checks")

    settings = get_settings()
    account_id = args.account_id
    lookback_days = args.lookback_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Build API client for indicator fetching
    import os
    if os.environ.get("REVIEWER_BACKEND_URL"):
        backend_url = settings.reviewer.backend_url
    else:
        backend_url = f"http://localhost:{settings.server.port}"

    logger.info("Backend URL: %s", backend_url)
    logger.info("Account: %d, lookback: %d days", account_id, lookback_days)

    from src.reviewer.api_client import ReviewerApiClient
    api_client = ReviewerApiClient(base_url=backend_url)

    # Get fills with decision contexts
    from src.data.database.dependencies import session_scope
    from src.data.database.broker_repository import BrokerRepository

    with session_scope() as session:
        repo = BrokerRepository(session)
        fill_ids = repo.get_recent_fill_ids(account_id, cutoff)

    logger.info("Found %d fills with decision contexts in last %d days", len(fill_ids), lookback_days)

    if not fill_ids:
        logger.info("No fills to check")
        return

    if args.dry_run:
        logger.info("Dry run — fills that would be checked:")
        for fid in fill_ids:
            logger.info("  fill_id=%d", fid)
        logger.info("Total: %d fills", len(fill_ids))
        return

    # Run checks for each fill
    from src.reviewer.checks.runner import CheckRunner

    total_checks = 0
    total_passed = 0
    total_failed = 0
    fills_processed = 0
    fills_skipped = 0

    for fill_id in fill_ids:
        try:
            with session_scope() as session:
                repo = BrokerRepository(session)

                dc = repo.get_decision_context(fill_id)
                if dc is None:
                    logger.debug("fill_id=%d: no DecisionContext, skipping", fill_id)
                    fills_skipped += 1
                    continue

                fill = repo.get_fill(fill_id)
                if fill is None:
                    logger.debug("fill_id=%d: fill not found, skipping", fill_id)
                    fills_skipped += 1
                    continue

                runner = CheckRunner(session, settings.checks, api_client=api_client)
                checks = runner.run_checks(dc, fill)

                passed = sum(1 for c in checks if c.passed)
                failed = len(checks) - passed
                total_checks += len(checks)
                total_passed += passed
                total_failed += failed
                fills_processed += 1

                # Log summary per fill
                eq_score = None
                for c in checks:
                    if c.details and "entry_quality_score" in (c.details or {}):
                        eq_score = c.details["entry_quality_score"]

                logger.info(
                    "fill_id=%d (%s %s): %d checks (%d passed, %d failed)%s",
                    fill_id, fill.side, fill.symbol,
                    len(checks), passed, failed,
                    f" EQ={eq_score:.0f}" if eq_score is not None else "",
                )

        except Exception:
            logger.exception("fill_id=%d: error running checks", fill_id)
            fills_skipped += 1

    logger.info(
        "Done — %d fills processed, %d skipped. %d total checks (%d passed, %d failed)",
        fills_processed, fills_skipped, total_checks, total_passed, total_failed,
    )


if __name__ == "__main__":
    main()
