#!/usr/bin/env python
"""Batch-run new evaluators (Checks 3,4,5) against all campaign legs.

Runs StructureAwareness, VolatilityLiquidity, and StopPlacement evaluators
retroactively on campaign legs that have a linked TradeIntent. Results are
persisted as TradeEvaluation + TradeEvaluationItem records with eval_scope='leg'.

Usage:
    python scripts/run_new_checks_on_legs.py                      # Run all
    python scripts/run_new_checks_on_legs.py --dry-run             # Preview only
    python scripts/run_new_checks_on_legs.py --symbol AAPL         # Filter by symbol
    python scripts/run_new_checks_on_legs.py --account-id 1        # Filter by account
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database.connection import get_db_manager
from src.data.database.trade_lifecycle_models import (
    CampaignLeg as CampaignLegModel,
    PositionCampaign as PositionCampaignModel,
)
from src.data.database.trading_buddy_models import (
    TradeIntent as TradeIntentModel,
    TradeEvaluation as TradeEvaluationModel,
    TradeEvaluationItem as TradeEvaluationItemModel,
)
from src.trade.intent import TradeIntent, TradeDirection, TradeIntentStatus
from src.trade.evaluation import Severity, SEVERITY_PRIORITY
from src.evaluators.context import ContextPackBuilder
from src.evaluators.registry import get_evaluator

# Trigger evaluator registration
import src.evaluators  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

EVALUATOR_NAMES = ["structure_awareness", "volatility_liquidity", "stop_placement"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-run new evaluators on campaign legs",
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


def load_intent(session, leg: CampaignLegModel) -> TradeIntent | None:
    """Load the TradeIntent domain object linked to a campaign leg.

    Reuses the same conversion pattern as CheckRunner._load_intent().
    """
    if leg.intent_id is None:
        return None

    model = session.query(TradeIntentModel).filter(
        TradeIntentModel.id == leg.intent_id,
    ).first()

    if model is None:
        logger.warning("Intent id=%s not found for leg_id=%s", leg.intent_id, leg.id)
        return None

    try:
        return TradeIntent(
            intent_id=model.id,
            user_id=model.account_id,
            account_id=model.account_id,
            symbol=model.symbol,
            direction=TradeDirection(model.direction),
            timeframe=model.timeframe,
            entry_price=model.entry_price,
            stop_loss=model.stop_loss,
            profit_target=model.profit_target,
            position_size=model.position_size,
            position_value=model.position_value,
            rationale=model.rationale,
            status=TradeIntentStatus(model.status),
            created_at=model.created_at,
            metadata=model.intent_metadata or {},
        )
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Could not construct TradeIntent from model id=%s: %s",
            model.id, exc,
        )
        return None


def persist_evaluation(session, leg, campaign, items, evaluators_run, dry_run):
    """Persist TradeEvaluation + TradeEvaluationItem records for a leg."""
    blocker_count = sum(1 for i in items if i.severity == Severity.BLOCKER)
    critical_count = sum(1 for i in items if i.severity == Severity.CRITICAL)
    warning_count = sum(1 for i in items if i.severity == Severity.WARNING)
    info_count = sum(1 for i in items if i.severity == Severity.INFO)

    # Score: start at 100, deduct per severity
    score = max(0.0, 100.0 - blocker_count * 25 - critical_count * 15 - warning_count * 5 - info_count * 1)

    summary_parts = []
    if blocker_count:
        summary_parts.append(f"{blocker_count} blocker(s)")
    if critical_count:
        summary_parts.append(f"{critical_count} critical")
    if warning_count:
        summary_parts.append(f"{warning_count} warning(s)")
    if info_count:
        summary_parts.append(f"{info_count} info")
    summary = f"Retroactive check: {', '.join(summary_parts)}" if summary_parts else "Retroactive check: no issues"

    if dry_run:
        logger.info(
            "[DRY-RUN] Would persist evaluation for leg_id=%s: score=%.0f, %s",
            leg.id, score, summary,
        )
        return

    evaluation = TradeEvaluationModel(
        intent_id=leg.intent_id,
        campaign_id=campaign.id,
        leg_id=leg.id,
        eval_scope="leg",
        score=score,
        summary=summary,
        blocker_count=blocker_count,
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        evaluators_run=evaluators_run,
        evaluated_at=datetime.utcnow(),
    )
    session.add(evaluation)
    session.flush()

    for item in items:
        item_model = TradeEvaluationItemModel(
            evaluation_id=evaluation.id,
            evaluator=item.evaluator,
            code=item.code,
            severity=item.severity.value,
            severity_priority=SEVERITY_PRIORITY[item.severity],
            title=item.title,
            message=item.message,
            evidence=[e.to_dict() for e in item.evidence],
        )
        session.add(item_model)

    session.flush()
    logger.info("Persisted evaluation id=%s for leg_id=%s", evaluation.id, leg.id)


def main():
    args = parse_args()

    db_manager = get_db_manager()
    builder = ContextPackBuilder(
        include_features=True,
        include_regimes=True,
        include_key_levels=True,
        cache_enabled=True,
        ensure_fresh_data=False,
    )

    evaluators = [get_evaluator(name) for name in EVALUATOR_NAMES]
    evaluators_run = [e.name for e in evaluators]

    # Summary accumulators
    total_legs = 0
    skipped_no_intent = 0
    skipped_error = 0
    processed = 0
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

        # Cache for ContextPacks keyed by (symbol, timeframe)
        context_cache: dict[tuple[str, str], object] = {}

        for leg in legs:
            campaign = leg.campaign
            symbol = campaign.symbol
            direction = campaign.direction

            intent = load_intent(session, leg)
            if intent is None:
                skipped_no_intent += 1
                logger.debug(
                    "Skipping leg_id=%s (no intent): %s %s",
                    leg.id, symbol, direction,
                )
                continue

            timeframe = intent.timeframe
            cache_key = (symbol, timeframe)

            # Build or reuse ContextPack
            if cache_key not in context_cache:
                try:
                    context = builder.build(
                        symbol=symbol,
                        timeframe=timeframe,
                        lookback_bars=100,
                        additional_timeframes=["1Day"],
                    )
                    context_cache[cache_key] = context
                except Exception:
                    logger.exception(
                        "Failed to build ContextPack for %s/%s, skipping leg_id=%s",
                        symbol, timeframe, leg.id,
                    )
                    skipped_error += 1
                    continue

            context = context_cache[cache_key]

            # Run all 3 evaluators
            all_items = []
            for evaluator in evaluators:
                try:
                    items = evaluator.evaluate(intent, context)
                    all_items.extend(items)
                except Exception:
                    logger.exception(
                        "Evaluator %s failed for leg_id=%s",
                        evaluator.name, leg.id,
                    )

            # Persist results
            persist_evaluation(
                session, leg, campaign, all_items, evaluators_run, args.dry_run,
            )
            processed += 1

            # Collect summary row
            codes = [item.code for item in all_items]
            summary_rows.append({
                "leg_id": leg.id,
                "campaign_id": campaign.id,
                "symbol": symbol,
                "direction": direction,
                "leg_type": leg.leg_type,
                "codes": codes,
                "item_count": len(all_items),
            })

    # Print summary table
    print("\n" + "=" * 90)
    print(f"BATCH EVALUATION SUMMARY {'(DRY-RUN)' if args.dry_run else ''}")
    print("=" * 90)
    print(f"Total legs:          {total_legs}")
    print(f"Processed:           {processed}")
    print(f"Skipped (no intent): {skipped_no_intent}")
    print(f"Skipped (error):     {skipped_error}")
    print("-" * 90)

    if summary_rows:
        print(
            f"{'Leg ID':>8}  {'Campaign':>8}  {'Symbol':<8}  {'Dir':<6}  "
            f"{'Type':<10}  {'Findings':>8}  Codes"
        )
        print("-" * 90)
        for row in summary_rows:
            codes_str = ", ".join(row["codes"]) if row["codes"] else "(none)"
            print(
                f"{row['leg_id']:>8}  {row['campaign_id']:>8}  {row['symbol']:<8}  "
                f"{row['direction']:<6}  {row['leg_type']:<10}  "
                f"{row['item_count']:>8}  {codes_str}"
            )
    else:
        print("No legs were processed.")

    print("=" * 90)


if __name__ == "__main__":
    main()
