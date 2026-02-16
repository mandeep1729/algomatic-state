#!/usr/bin/env python
"""Batch-publish review events for campaign legs.

Queries campaign leg IDs from the database (with optional filters),
groups them by account_id, and publishes REVIEW_CAMPAIGNS_POPULATED
events so the reviewer service runs both behavioral checks AND
evaluator checks.

Usage:
    python scripts/review_legs.py                        # All legs
    python scripts/review_legs.py --dry-run              # Preview only
    python scripts/review_legs.py --symbol AAPL          # Filter by symbol
    python scripts/review_legs.py --account-id 1         # Filter by account
"""

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database.connection import get_db_manager
from src.data.database.trade_lifecycle_models import (
    CampaignLeg as CampaignLegModel,
    PositionCampaign as PositionCampaignModel,
)
from src.reviewer.publisher import publish_campaigns_populated

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish review events for campaign legs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be published without actually publishing",
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

    db_manager = get_db_manager()

    with db_manager.get_session() as session:
        query = (
            session.query(
                CampaignLegModel.id,
                PositionCampaignModel.account_id,
                PositionCampaignModel.symbol,
            )
            .join(
                PositionCampaignModel,
                CampaignLegModel.campaign_id == PositionCampaignModel.id,
            )
        )
        if args.symbol:
            query = query.filter(PositionCampaignModel.symbol == args.symbol.upper())
        if args.account_id:
            query = query.filter(PositionCampaignModel.account_id == args.account_id)

        rows = query.all()

    if not rows:
        print("No campaign legs found matching filters.")
        return

    # Group leg IDs by account_id
    account_legs: dict[int, list[int]] = defaultdict(list)
    for leg_id, account_id, _symbol in rows:
        account_legs[account_id].append(leg_id)

    # Summary
    total_legs = len(rows)
    total_accounts = len(account_legs)

    print(f"\nFound {total_legs} legs across {total_accounts} account(s)")
    print("-" * 60)

    for account_id, leg_ids in sorted(account_legs.items()):
        print(f"  account_id={account_id}: {len(leg_ids)} legs {leg_ids[:5]}{'...' if len(leg_ids) > 5 else ''}")

    print("-" * 60)

    if args.dry_run:
        print("[DRY-RUN] Would publish REVIEW_CAMPAIGNS_POPULATED for each account above.")
        return

    # Publish events
    published = 0
    for account_id, leg_ids in sorted(account_legs.items()):
        publish_campaigns_populated(account_id, leg_ids)
        published += 1
        logger.info(
            "Published REVIEW_CAMPAIGNS_POPULATED: account_id=%s, %d legs",
            account_id, len(leg_ids),
        )

    print(f"\nPublished {published} REVIEW_CAMPAIGNS_POPULATED event(s).")


if __name__ == "__main__":
    main()
