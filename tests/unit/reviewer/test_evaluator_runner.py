"""Unit tests for EvaluatorRunner."""

from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

from src.trade.evaluation import EvaluationItem, Evidence, Severity
from src.reviewer.evaluator_runner import (
    ALL_EVALUATOR_NAMES,
    SYNTHETIC_EVALUATOR_NAMES,
    EvaluatorRunner,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_leg(
    leg_id=1,
    campaign_id=10,
    account_id=1,
    intent_id=None,
    avg_price=150.0,
    quantity=100,
    symbol="AAPL",
    direction="long",
    started_at=None,
):
    """Create a mock CampaignLeg with a related campaign."""
    leg = MagicMock()
    leg.id = leg_id
    leg.campaign_id = campaign_id
    leg.intent_id = intent_id
    leg.avg_price = avg_price
    leg.quantity = quantity
    leg.started_at = started_at or datetime(2025, 1, 15, 10, 30)

    campaign = MagicMock()
    campaign.id = campaign_id
    campaign.account_id = account_id
    campaign.symbol = symbol
    campaign.direction = direction
    leg.campaign = campaign

    return leg


def _make_intent_model(
    intent_id=100,
    account_id=1,
    symbol="AAPL",
    direction="long",
    timeframe="5Min",
    entry_price=150.0,
    stop_loss=145.0,
    profit_target=160.0,
):
    """Create a mock TradeIntent DB model."""
    model = MagicMock()
    model.id = intent_id
    model.account_id = account_id
    model.symbol = symbol
    model.direction = direction
    model.timeframe = timeframe
    model.entry_price = entry_price
    model.stop_loss = stop_loss
    model.profit_target = profit_target
    model.position_size = 100
    model.position_value = 15000.0
    model.rationale = "test"
    model.status = "executed"
    model.created_at = datetime(2025, 1, 15, 10, 0)
    model.intent_metadata = {}
    return model


def _make_item(severity=Severity.WARNING, evaluator="test", code="T001"):
    """Create a simple EvaluationItem."""
    return EvaluationItem(
        evaluator=evaluator,
        code=code,
        severity=severity,
        title="Test finding",
        message="Test message",
        evidence=[],
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestRunEvaluationsWithRealIntent:
    """Legs with intent_id should load the real intent and run all 7 evaluators."""

    @patch("src.reviewer.evaluator_runner.get_evaluator")
    def test_all_evaluators_run(self, mock_get_eval):
        session = MagicMock()
        builder = MagicMock()
        builder.build.return_value = MagicMock()

        # Set up intent query
        intent_model = _make_intent_model()
        session.query.return_value.filter.return_value.first.side_effect = [
            intent_model,  # _load_intent query
            None,          # _persist: no existing evaluation
        ]

        # Each evaluator returns one item
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = [_make_item()]
        mock_evaluator.name = "test_evaluator"
        mock_get_eval.return_value = mock_evaluator

        leg = _make_leg(intent_id=100)

        runner = EvaluatorRunner(session, builder=builder)
        result = runner.run_evaluations(leg)

        assert result is not None
        # get_evaluator called for all 7 evaluator names
        assert mock_get_eval.call_count == len(ALL_EVALUATOR_NAMES)
        # evaluate called for each evaluator
        assert mock_evaluator.evaluate.call_count == len(ALL_EVALUATOR_NAMES)
        # ContextPack built with intent's timeframe
        builder.build.assert_called_once()


class TestRunEvaluationsWithSyntheticIntent:
    """Legs without intent_id should synthesize and run only 4 evaluators."""

    @patch("src.reviewer.evaluator_runner.get_evaluator")
    def test_synthetic_evaluators_run(self, mock_get_eval):
        session = MagicMock()
        builder = MagicMock()
        builder.build.return_value = MagicMock()

        # No intent in DB (intent_id is None on leg)
        session.query.return_value.filter.return_value.first.return_value = None

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = []
        mock_evaluator.name = "test_evaluator"
        mock_get_eval.return_value = mock_evaluator

        leg = _make_leg(intent_id=None, avg_price=150.0)

        runner = EvaluatorRunner(session, builder=builder)
        result = runner.run_evaluations(leg)

        assert result is not None
        assert mock_get_eval.call_count == len(SYNTHETIC_EVALUATOR_NAMES)


class TestRunEvaluationsSkipsNoPrice:
    """Legs without avg_price and without intent should return None."""

    def test_returns_none_when_no_price(self):
        session = MagicMock()
        builder = MagicMock()

        leg = _make_leg(intent_id=None, avg_price=None)

        runner = EvaluatorRunner(session, builder=builder)
        result = runner.run_evaluations(leg)

        assert result is None
        builder.build.assert_not_called()

    def test_returns_none_when_zero_price(self):
        session = MagicMock()
        builder = MagicMock()

        leg = _make_leg(intent_id=None, avg_price=0.0)

        runner = EvaluatorRunner(session, builder=builder)
        result = runner.run_evaluations(leg)

        assert result is None
        builder.build.assert_not_called()


class TestPersistIdempotent:
    """Running evaluations twice should replace, not duplicate."""

    @patch("src.reviewer.evaluator_runner.get_evaluator")
    def test_existing_evaluation_deleted_before_insert(self, mock_get_eval):
        session = MagicMock()
        builder = MagicMock()
        builder.build.return_value = MagicMock()

        # First call: no existing evaluation
        # Second call: existing evaluation found
        existing_eval = MagicMock()
        existing_eval.id = 999

        session.query.return_value.filter.return_value.first.side_effect = [
            None,           # _persist: no existing (1st run)
        ]

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = []
        mock_evaluator.name = "test"
        mock_get_eval.return_value = mock_evaluator

        leg = _make_leg(intent_id=None, avg_price=100.0)

        runner = EvaluatorRunner(session, builder=builder)

        # First run - creates evaluation
        result1 = runner.run_evaluations(leg)
        assert result1 is not None

        # Set up second run: now there's an existing evaluation
        session.query.return_value.filter.return_value.first.side_effect = [
            existing_eval,  # _persist: existing found
        ]
        session.query.return_value.filter.return_value.delete.return_value = 1

        result2 = runner.run_evaluations(leg)
        assert result2 is not None

        # Verify the existing evaluation was deleted
        session.delete.assert_called_once_with(existing_eval)


class TestScoring:
    """Verify the canonical scoring formula."""

    def test_perfect_score_no_items(self):
        score = EvaluatorRunner.compute_score([])
        assert score == 100.0

    def test_blocker_penalty(self):
        items = [_make_item(severity=Severity.BLOCKER)]
        score = EvaluatorRunner.compute_score(items)
        assert score == 60.0  # 100 - 40

    def test_critical_penalty(self):
        items = [_make_item(severity=Severity.CRITICAL)]
        score = EvaluatorRunner.compute_score(items)
        assert score == 80.0  # 100 - 20

    def test_warning_penalty(self):
        items = [_make_item(severity=Severity.WARNING)]
        score = EvaluatorRunner.compute_score(items)
        assert score == 95.0  # 100 - 5

    def test_info_no_penalty(self):
        items = [_make_item(severity=Severity.INFO)]
        score = EvaluatorRunner.compute_score(items)
        assert score == 100.0  # 100 - 0

    def test_mixed_severity(self):
        items = [
            _make_item(severity=Severity.BLOCKER, code="B1"),
            _make_item(severity=Severity.CRITICAL, code="C1"),
            _make_item(severity=Severity.WARNING, code="W1"),
            _make_item(severity=Severity.INFO, code="I1"),
        ]
        score = EvaluatorRunner.compute_score(items)
        # 100 - 40 - 20 - 5 - 0 = 35
        assert score == 35.0

    def test_score_clamped_at_zero(self):
        items = [_make_item(severity=Severity.BLOCKER, code=f"B{i}") for i in range(5)]
        score = EvaluatorRunner.compute_score(items)
        # 100 - 5*40 = -100 → clamped to 0
        assert score == 0.0


class TestContextPackBuiltAtPointInTime:
    """Verify ContextPack is built with as_of=leg.started_at."""

    @patch("src.reviewer.evaluator_runner.get_evaluator")
    def test_as_of_matches_leg_started_at(self, mock_get_eval):
        session = MagicMock()
        builder = MagicMock()
        builder.build.return_value = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = []
        mock_evaluator.name = "test"
        mock_get_eval.return_value = mock_evaluator

        started = datetime(2025, 3, 10, 14, 0)
        leg = _make_leg(intent_id=None, avg_price=200.0, started_at=started)

        runner = EvaluatorRunner(session, builder=builder)
        runner.run_evaluations(leg)

        builder.build.assert_called_once()
        call_kwargs = builder.build.call_args
        assert call_kwargs.kwargs.get("as_of") == started or call_kwargs[1].get("as_of") == started
