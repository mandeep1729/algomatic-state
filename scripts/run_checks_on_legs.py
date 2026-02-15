#!/usr/bin/env python
"""Batch-run behavioral checks (CheckRunner) against all campaign legs.

Runs RiskSanityChecker (RS001-RS004) against all legs and persists
CampaignCheck records. Existing checks for each leg are deleted first
so the script is safely re-runnable.

Usage:
    python scripts/run_checks_on_legs.py                      # Run all
    python scripts/run_checks_on_legs.py --dry-run             # Preview only
    python scripts/run_checks_on_legs.py --symbol AAPL         # Filter by symbol
    python scripts/run_checks_on_legs.py --account-id 1        # Filter by account
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from src.data.database.connection import get_db_manager
from src.data.database.trade_lifecycle_models import (
    CampaignCheck as CampaignCheckModel,
    CampaignLeg as CampaignLegModel,
    PositionCampaign as PositionCampaignModel,
)
from src.reviewer.checks.runner import CheckRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-run behavioral checks on campaign legs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without persisting to DB",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Filter legs by symbol (e.g. AAPL)",
    )
    parser.add_argument(
        "--account-id",
        type=int,
        default=None,
        help="Filter legs by account ID",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    settings = get_settings()
    db_manager = get_db_manager()

    total_legs = 0
    processed = 0
    skipped_error = 0
    total_checks = 0
    total_passed = 0
    total_failed = 0
    summary_rows = []

    with db_manager.get_session() as session:
        query = (
            session.query(CampaignLegModel)
            .join(PositionCampaignModel, CampaignLegModel.campaign_id == PositionCampaignModel.id)
        )
        if args.symbol:
            query = query.filter(PositionCampaignModel.symbol == args.symbol.upper())
        if args.account_id:
            query = query.filter(PositionCampaignModel.account_id == args.account_id)

        legs = query.all()
        total_legs = len(legs)
        logger.info("Found %d campaign legs to process", total_legs)

        for leg in legs:
            campaign = leg.campaign
            symbol = campaign.symbol
            direction = campaign.direction

            # Delete existing checks for idempotency
            existing_count = session.query(CampaignCheckModel).filter(
                CampaignCheckModel.leg_id == leg.id,
            ).count()
            if existing_count > 0:
                session.query(CampaignCheckModel).filter(
                    CampaignCheckModel.leg_id == leg.id,
                ).delete()
                session.flush()
                logger.debug(
                    "Deleted %d existing checks for leg_id=%s",
                    existing_count, leg.id,
                )

            if args.dry_run:
                # In dry-run mode, still run the checks but don't persist
                runner = CheckRunner(session, settings.checks)
                try:
                    # Temporarily collect results without persisting
                    intent = runner._load_intent(leg)
                    atr = runner._fetch_atr(leg)
                    account_balance = runner._get_account_balance(leg)

                    all_results = []
                    for checker in runner.checkers:
                        results = checker.run(leg, intent, atr, account_balance)
                        all_results.extend(results)

                    passed = sum(1 for r in all_results if r.passed)
                    failed = len(all_results) - passed

                    logger.info(
                        "[DRY-RUN] leg_id=%s %s %s: %d checks (%d passed, %d failed)",
                        leg.id, symbol, direction, len(all_results), passed, failed,
                    )

                    total_checks += len(all_results)
                    total_passed += passed
                    total_failed += failed

                    codes = [r.code for r in all_results if not r.passed]
                    summary_rows.append({
                        "leg_id": leg.id,
                        "campaign_id": campaign.id,
                        "symbol": symbol,
                        "direction": direction,
                        "leg_type": leg.leg_type,
                        "checks": len(all_results),
                        "passed": passed,
                        "failed": failed,
                        "failed_codes": codes,
                    })
                except Exception:
                    logger.exception(
                        "Failed to run checks for leg_id=%s", leg.id,
                    )
                    skipped_error += 1
                    continue
            else:
                # Normal mode: CheckRunner persists CampaignCheck records
                runner = CheckRunner(session, settings.checks)
                try:
                    checks = runner.run_checks(leg)

                    passed = sum(1 for c in checks if c.passed)
                    failed = len(checks) - passed

                    total_checks += len(checks)
                    total_passed += passed
                    total_failed += failed

                    codes = [c.check_type + ":" + getattr(c, 'check_type', '') for c in checks if not c.passed]
                    # Extract codes from details or use check_type
                    failed_codes = []
                    for c in checks:
                        if not c.passed:
                            # The code is stored in details for CheckRunner results
                            detail_code = (c.details or {}).get("code", c.check_type)
                            failed_codes.append(detail_code)

                    summary_rows.append({
                        "leg_id": leg.id,
                        "campaign_id": campaign.id,
                        "symbol": symbol,
                        "direction": direction,
                        "leg_type": leg.leg_type,
                        "checks": len(checks),
                        "passed": passed,
                        "failed": failed,
                        "failed_codes": failed_codes,
                    })
                except Exception:
                    logger.exception(
                        "Failed to run checks for leg_id=%s", leg.id,
                    )
                    skipped_error += 1
                    continue

            processed += 1

    # Print summary table
    print("\n" + "=" * 100)
    print(f"BEHAVIORAL CHECKS SUMMARY {'(DRY-RUN)' if args.dry_run else ''}")
    print("=" * 100)
    print(f"Total legs:     {total_legs}")
    print(f"Processed:      {processed}")
    print(f"Skipped (err):  {skipped_error}")
    print(f"Total checks:   {total_checks}")
    print(f"Passed:         {total_passed}")
    print(f"Failed:         {total_failed}")
    print("-" * 100)

    if summary_rows:
        print(
            f"{'Leg ID':>8}  {'Campaign':>8}  {'Symbol':<8}  {'Dir':<6}  "
            f"{'Type':<10}  {'Checks':>6}  {'Pass':>4}  {'Fail':>4}  Failed Codes"
        )
        print("-" * 100)
        for row in summary_rows:
            codes_str = ", ".join(row["failed_codes"]) if row["failed_codes"] else "(all passed)"
            print(
                f"{row['leg_id']:>8}  {row['campaign_id']:>8}  {row['symbol']:<8}  "
                f"{row['direction']:<6}  {row['leg_type']:<10}  "
                f"{row['checks']:>6}  {row['passed']:>4}  {row['failed']:>4}  {codes_str}"
            )
    else:
        print("No legs were processed.")

    print("=" * 100)


if __name__ == "__main__":
    main()
