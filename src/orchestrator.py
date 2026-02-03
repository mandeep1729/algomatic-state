"""Evaluator orchestrator for coordinating trade evaluation.

The EvaluatorOrchestrator manages loading evaluators, running
evaluations, aggregating results, and generating summaries.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.trade.intent import TradeIntent
from src.trade.evaluation import (
    EvaluationItem,
    EvaluationResult,
    Severity,
    SEVERITY_PRIORITY,
)
from src.evaluators.context import ContextPack, ContextPackBuilder, get_context_builder
from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.registry import get_all_evaluators, get_evaluator

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the EvaluatorOrchestrator.

    Attributes:
        parallel_execution: Whether to run evaluators in parallel
        max_workers: Max threads for parallel execution
        fail_fast: Stop on first blocker
        include_info: Include INFO-level items in results
        evaluator_configs: Per-evaluator configurations
        context_lookback_bars: Number of bars for context
        additional_timeframes: Extra timeframes to include in context
    """

    parallel_execution: bool = False
    max_workers: int = 4
    fail_fast: bool = False
    include_info: bool = True
    evaluator_configs: dict[str, EvaluatorConfig] = field(default_factory=dict)
    context_lookback_bars: int = 100
    additional_timeframes: list[str] = field(default_factory=lambda: ["1Hour", "1Day"])


class EvaluatorOrchestrator:
    """Orchestrates trade intent evaluation across multiple evaluators.

    Responsibilities:
    - Load and configure evaluators
    - Build market context
    - Execute evaluations (sequentially or in parallel)
    - Aggregate and deduplicate results
    - Compute overall score
    - Generate summary

    Usage:
        orchestrator = EvaluatorOrchestrator()
        result = orchestrator.evaluate(trade_intent)
    """

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        context_builder: Optional[ContextPackBuilder] = None,
    ):
        """Initialize orchestrator.

        Args:
            config: Orchestrator configuration
            context_builder: Custom context builder (uses default if not provided)
        """
        self.config = config or OrchestratorConfig()
        self.context_builder = context_builder or get_context_builder()
        self._evaluators: list[Evaluator] = []

    def load_evaluators(
        self,
        evaluator_names: Optional[list[str]] = None,
        enabled_only: bool = True,
    ) -> None:
        """Load evaluators from registry.

        Args:
            evaluator_names: Specific evaluators to load (all if None)
            enabled_only: Only load enabled evaluators
        """
        if evaluator_names:
            # Load specific evaluators
            self._evaluators = []
            for name in evaluator_names:
                config = self.config.evaluator_configs.get(name)
                try:
                    evaluator = get_evaluator(name, config)
                    if enabled_only and not evaluator.is_enabled():
                        continue
                    self._evaluators.append(evaluator)
                except KeyError as e:
                    logger.warning(f"Evaluator not found: {e}")
        else:
            # Load all registered evaluators
            self._evaluators = get_all_evaluators(
                configs=self.config.evaluator_configs,
                enabled_only=enabled_only,
            )

        logger.info(f"Loaded {len(self._evaluators)} evaluators")

    def evaluate(
        self,
        intent: TradeIntent,
        context: Optional[ContextPack] = None,
    ) -> EvaluationResult:
        """Evaluate a trade intent against all loaded evaluators.

        Args:
            intent: Trade intent to evaluate
            context: Pre-built context (will build if not provided)

        Returns:
            Aggregated evaluation result
        """
        start_time = datetime.utcnow()

        # Build context if not provided
        if context is None:
            context = self._build_context(intent)

        # Ensure evaluators are loaded
        if not self._evaluators:
            self.load_evaluators()

        # Run evaluations
        if self.config.parallel_execution and len(self._evaluators) > 1:
            all_items = self._run_parallel(intent, context)
        else:
            all_items = self._run_sequential(intent, context)

        # Filter INFO items if configured
        if not self.config.include_info:
            all_items = [i for i in all_items if i.severity != Severity.INFO]

        # Deduplicate items (by code)
        unique_items = self._deduplicate_items(all_items)

        # Sort by severity (most severe first)
        unique_items.sort(key=lambda x: SEVERITY_PRIORITY[x.severity], reverse=True)

        # Compute score
        score = self._compute_score(unique_items)

        # Generate summary
        summary = self._generate_summary(intent, unique_items, score)

        # Build result
        evaluators_run = [e.name for e in self._evaluators]

        result = EvaluationResult(
            intent=intent,
            score=score,
            items=unique_items,
            summary=summary,
            evaluated_at=start_time,
            evaluators_run=evaluators_run,
        )

        logger.info(
            f"Evaluation complete for {intent.symbol}: "
            f"score={score:.1f}, items={len(unique_items)}, "
            f"blockers={len(result.blockers)}"
        )

        return result

    def _build_context(self, intent: TradeIntent) -> ContextPack:
        """Build context for the trade intent.

        Args:
            intent: Trade intent

        Returns:
            ContextPack
        """
        return self.context_builder.build(
            symbol=intent.symbol,
            timeframe=intent.timeframe,
            lookback_bars=self.config.context_lookback_bars,
            additional_timeframes=self.config.additional_timeframes,
        )

    def _run_sequential(
        self,
        intent: TradeIntent,
        context: ContextPack,
    ) -> list[EvaluationItem]:
        """Run evaluators sequentially.

        Args:
            intent: Trade intent
            context: Market context

        Returns:
            List of all evaluation items
        """
        all_items: list[EvaluationItem] = []

        for evaluator in self._evaluators:
            try:
                config = self.config.evaluator_configs.get(evaluator.name)
                items = evaluator.evaluate(intent, context, config)
                all_items.extend(items)

                # Check fail-fast
                if self.config.fail_fast:
                    blockers = [i for i in items if i.severity == Severity.BLOCKER]
                    if blockers:
                        logger.info(
                            f"Fail-fast triggered by {evaluator.name}: "
                            f"{len(blockers)} blockers"
                        )
                        break

            except Exception as e:
                logger.exception(f"Evaluator {evaluator.name} failed: {e}")
                # Add error item
                all_items.append(EvaluationItem(
                    evaluator=evaluator.name,
                    code="ERR001",
                    severity=Severity.WARNING,
                    title="Evaluator Error",
                    message=f"Evaluator {evaluator.name} encountered an error: {str(e)}",
                ))

        return all_items

    def _run_parallel(
        self,
        intent: TradeIntent,
        context: ContextPack,
    ) -> list[EvaluationItem]:
        """Run evaluators in parallel.

        Args:
            intent: Trade intent
            context: Market context

        Returns:
            List of all evaluation items
        """
        all_items: list[EvaluationItem] = []

        def run_evaluator(evaluator: Evaluator) -> list[EvaluationItem]:
            config = self.config.evaluator_configs.get(evaluator.name)
            return evaluator.evaluate(intent, context, config)

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_evaluator = {
                executor.submit(run_evaluator, e): e for e in self._evaluators
            }

            for future in as_completed(future_to_evaluator):
                evaluator = future_to_evaluator[future]
                try:
                    items = future.result()
                    all_items.extend(items)
                except Exception as e:
                    logger.exception(f"Evaluator {evaluator.name} failed: {e}")
                    all_items.append(EvaluationItem(
                        evaluator=evaluator.name,
                        code="ERR001",
                        severity=Severity.WARNING,
                        title="Evaluator Error",
                        message=f"Evaluator {evaluator.name} encountered an error: {str(e)}",
                    ))

        return all_items

    def _deduplicate_items(
        self,
        items: list[EvaluationItem],
    ) -> list[EvaluationItem]:
        """Deduplicate items by code, keeping highest severity.

        Args:
            items: List of evaluation items

        Returns:
            Deduplicated list
        """
        seen: dict[str, EvaluationItem] = {}

        for item in items:
            key = f"{item.evaluator}:{item.code}"
            if key not in seen:
                seen[key] = item
            else:
                # Keep higher severity version
                existing = seen[key]
                if SEVERITY_PRIORITY[item.severity] > SEVERITY_PRIORITY[existing.severity]:
                    seen[key] = item

        return list(seen.values())

    def _compute_score(self, items: list[EvaluationItem]) -> float:
        """Compute overall evaluation score.

        Score starts at 100 and is reduced by findings:
        - BLOCKER: -40 points each (capped at 0)
        - CRITICAL: -20 points each
        - WARNING: -5 points each
        - INFO: -0 points

        Args:
            items: Evaluation items

        Returns:
            Score from 0-100
        """
        score = 100.0

        # Penalty weights
        penalties = {
            Severity.BLOCKER: 40.0,
            Severity.CRITICAL: 20.0,
            Severity.WARNING: 5.0,
            Severity.INFO: 0.0,
        }

        for item in items:
            score -= penalties.get(item.severity, 0.0)

        # Clamp to 0-100
        return max(0.0, min(100.0, score))

    def _generate_summary(
        self,
        intent: TradeIntent,
        items: list[EvaluationItem],
        score: float,
    ) -> str:
        """Generate a text summary of the evaluation.

        Args:
            intent: Trade intent
            items: Evaluation items
            score: Computed score

        Returns:
            Summary text
        """
        blockers = [i for i in items if i.severity == Severity.BLOCKER]
        criticals = [i for i in items if i.severity == Severity.CRITICAL]
        warnings = [i for i in items if i.severity == Severity.WARNING]

        parts = []

        # Overall assessment
        if blockers:
            parts.append(
                f"BLOCKED: {len(blockers)} blocker issue(s) must be resolved."
            )
        elif criticals:
            parts.append(
                f"CAUTION: {len(criticals)} critical issue(s) require attention."
            )
        elif warnings:
            parts.append(
                f"REVIEW: {len(warnings)} warning(s) to consider."
            )
        else:
            parts.append("CLEAR: No significant issues detected.")

        # Score context
        if score >= 80:
            parts.append(f"Score: {score:.0f}/100 (Good)")
        elif score >= 60:
            parts.append(f"Score: {score:.0f}/100 (Fair)")
        elif score >= 40:
            parts.append(f"Score: {score:.0f}/100 (Poor)")
        else:
            parts.append(f"Score: {score:.0f}/100 (Critical)")

        # Top issue
        if items:
            top = items[0]
            parts.append(f"Top issue: {top.title}")

        return " ".join(parts)

    @property
    def evaluator_count(self) -> int:
        """Return number of loaded evaluators."""
        return len(self._evaluators)


# Convenience function for simple evaluations
def evaluate_trade(
    intent: TradeIntent,
    evaluator_names: Optional[list[str]] = None,
) -> EvaluationResult:
    """Convenience function to evaluate a trade intent.

    Args:
        intent: Trade intent to evaluate
        evaluator_names: Specific evaluators to use (all if None)

    Returns:
        Evaluation result
    """
    orchestrator = EvaluatorOrchestrator()
    orchestrator.load_evaluators(evaluator_names)
    return orchestrator.evaluate(intent)
