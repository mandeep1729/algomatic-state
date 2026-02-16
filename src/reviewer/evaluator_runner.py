"""EvaluatorRunner — runs evaluators against a campaign leg.

Extracts evaluator execution logic (intent loading, synthesis,
context building, evaluation, scoring, persistence) so that both
the ReviewerOrchestrator and batch scripts can reuse it.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.data.database.trade_lifecycle_models import (
    CampaignLeg as CampaignLegModel,
    PositionCampaign as PositionCampaignModel,
)
from src.data.database.trading_buddy_models import (
    TradeEvaluation as TradeEvaluationModel,
    TradeEvaluationItem as TradeEvaluationItemModel,
    TradeIntent as TradeIntentModel,
)
from src.evaluators.context import ContextPackBuilder
from src.evaluators.registry import get_evaluator
from src.trade.evaluation import EvaluationItem, Severity, SEVERITY_PRIORITY
from src.trade.intent import TradeDirection, TradeIntent, TradeIntentStatus

logger = logging.getLogger(__name__)

# All 7 evaluators (for legs with real TradeIntent)
ALL_EVALUATOR_NAMES = [
    "risk_reward",
    "exit_plan",
    "regime_fit",
    "mtfa",
    "structure_awareness",
    "volatility_liquidity",
    "stop_placement",
]

# Evaluators that produce meaningful results without real stop/target
SYNTHETIC_EVALUATOR_NAMES = [
    "regime_fit",
    "mtfa",
    "structure_awareness",
    "volatility_liquidity",
]

# Default timeframe when no intent is available
DEFAULT_TIMEFRAME = "5Min"

# Scoring penalties per severity (canonical formula from orchestrator.py)
_SEVERITY_PENALTIES = {
    Severity.BLOCKER: 40.0,
    Severity.CRITICAL: 20.0,
    Severity.WARNING: 5.0,
    Severity.INFO: 0.0,
}


class EvaluatorRunner:
    """Runs evaluators against a campaign leg and persists results.

    Handles the full lifecycle:
    1. Load real TradeIntent (if leg.intent_id exists) or synthesize one
    2. Select evaluator set (all 7 for real intents, 4 for synthetic)
    3. Build ContextPack at point-in-time (as_of=leg.started_at)
    4. Run evaluators and collect EvaluationItem results
    5. Compute score and persist TradeEvaluation + TradeEvaluationItem records
    """

    def __init__(
        self,
        session: Session,
        builder: Optional[ContextPackBuilder] = None,
    ) -> None:
        self.session = session
        self._builder = builder or ContextPackBuilder(
            include_features=True,
            include_regimes=True,
            include_key_levels=True,
            cache_enabled=True,
            ensure_fresh_data=False,
        )

    def run_evaluations(self, leg: CampaignLegModel) -> Optional[TradeEvaluationModel]:
        """Run evaluators for a leg and persist results.

        Returns:
            The persisted TradeEvaluationModel, or None if skipped
            (e.g. no intent and no avg_price to synthesize from).
        """
        campaign = leg.campaign
        symbol = campaign.symbol

        # Determine intent source and evaluator set
        intent = self._load_intent(leg)
        if intent is not None:
            evaluator_names = ALL_EVALUATOR_NAMES
            timeframe = intent.timeframe
            logger.debug(
                "Using real intent id=%s for leg_id=%s",
                intent.intent_id, leg.id,
            )
        else:
            intent = self._synthesize_intent(leg, campaign)
            if intent is None:
                logger.debug(
                    "Skipping evaluations for leg_id=%s: no intent and no avg_price",
                    leg.id,
                )
                return None
            evaluator_names = SYNTHETIC_EVALUATOR_NAMES
            timeframe = DEFAULT_TIMEFRAME
            logger.debug(
                "Using synthetic intent for leg_id=%s", leg.id,
            )

        # Build ContextPack at point-in-time
        context = self._builder.build(
            symbol=symbol,
            timeframe=timeframe,
            lookback_bars=100,
            additional_timeframes=["1Day"],
            as_of=leg.started_at,
        )

        # Run evaluators
        evaluators = [get_evaluator(name) for name in evaluator_names]
        all_items: list[EvaluationItem] = []
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
        evaluation = self._persist(leg, campaign, all_items, evaluator_names)
        logger.info(
            "Evaluator checks complete for leg_id=%s: score=%.0f, %d items (%s evaluators)",
            leg.id, evaluation.score, len(all_items),
            "all" if evaluator_names == ALL_EVALUATOR_NAMES else "synthetic",
        )
        return evaluation

    # ------------------------------------------------------------------
    # Intent loading
    # ------------------------------------------------------------------

    def _load_intent(self, leg: CampaignLegModel) -> Optional[TradeIntent]:
        """Load the TradeIntent domain object linked to a campaign leg."""
        if leg.intent_id is None:
            return None

        model = self.session.query(TradeIntentModel).filter(
            TradeIntentModel.id == leg.intent_id,
        ).first()

        if model is None:
            logger.warning(
                "Intent id=%s not found for leg_id=%s", leg.intent_id, leg.id,
            )
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

    def _synthesize_intent(
        self,
        leg: CampaignLegModel,
        campaign: PositionCampaignModel,
    ) -> Optional[TradeIntent]:
        """Build a synthetic TradeIntent from leg/campaign data.

        Uses leg.avg_price as entry and manufactures stop/target at
        fixed offsets so the TradeIntent constructor doesn't reject it.
        """
        entry_price = leg.avg_price
        if entry_price is None or entry_price <= 0:
            return None

        direction = TradeDirection(campaign.direction)

        # Synthetic stop/target placed far enough to pass validation
        offset = entry_price * 0.05
        if direction == TradeDirection.LONG:
            stop_loss = entry_price - offset
            profit_target = entry_price + offset
        else:
            stop_loss = entry_price + offset
            profit_target = entry_price - offset

        try:
            return TradeIntent(
                user_id=campaign.account_id,
                account_id=campaign.account_id,
                symbol=campaign.symbol,
                direction=direction,
                timeframe=DEFAULT_TIMEFRAME,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target,
                position_size=leg.quantity,
                status=TradeIntentStatus.EXECUTED,
                created_at=leg.started_at,
            )
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Could not synthesize TradeIntent for leg_id=%s: %s",
                leg.id, exc,
            )
            return None

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def compute_score(items: list[EvaluationItem]) -> float:
        """Compute overall evaluation score.

        Score starts at 100 and is reduced by findings:
        - BLOCKER: -40 points each
        - CRITICAL: -20 points each
        - WARNING: -5 points each
        - INFO: -0 points

        Returns:
            Score clamped to 0-100.
        """
        score = 100.0
        for item in items:
            score -= _SEVERITY_PENALTIES.get(item.severity, 0.0)
        return max(0.0, min(100.0, score))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(
        self,
        leg: CampaignLegModel,
        campaign: PositionCampaignModel,
        items: list[EvaluationItem],
        evaluator_names: list[str],
    ) -> TradeEvaluationModel:
        """Persist TradeEvaluation + TradeEvaluationItem records.

        Deletes any existing evaluation for this leg first (idempotent).
        """
        # Delete existing evaluation for idempotency
        existing = self.session.query(TradeEvaluationModel).filter(
            TradeEvaluationModel.leg_id == leg.id,
        ).first()
        if existing:
            self.session.query(TradeEvaluationItemModel).filter(
                TradeEvaluationItemModel.evaluation_id == existing.id,
            ).delete()
            self.session.delete(existing)
            self.session.flush()
            logger.debug(
                "Deleted existing evaluation id=%s for leg_id=%s",
                existing.id, leg.id,
            )

        # Compute counts and score
        blocker_count = sum(1 for i in items if i.severity == Severity.BLOCKER)
        critical_count = sum(1 for i in items if i.severity == Severity.CRITICAL)
        warning_count = sum(1 for i in items if i.severity == Severity.WARNING)
        info_count = sum(1 for i in items if i.severity == Severity.INFO)
        score = self.compute_score(items)

        # Build summary
        summary_parts = []
        if blocker_count:
            summary_parts.append(f"{blocker_count} blocker(s)")
        if critical_count:
            summary_parts.append(f"{critical_count} critical")
        if warning_count:
            summary_parts.append(f"{warning_count} warning(s)")
        if info_count:
            summary_parts.append(f"{info_count} info")
        summary = (
            f"Leg evaluation: {', '.join(summary_parts)}"
            if summary_parts
            else "Leg evaluation: no issues"
        )

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
            evaluators_run=list(evaluator_names),
            evaluated_at=datetime.utcnow(),
        )
        self.session.add(evaluation)
        self.session.flush()

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
            self.session.add(item_model)

        self.session.flush()
        return evaluation
