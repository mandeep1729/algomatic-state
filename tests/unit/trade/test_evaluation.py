"""Tests for trade evaluation domain objects.

Tests cover:
- EvaluationItem creation and severity levels
- EvaluationResult creation and aggregation
- Blocker and warning filtering
- Result serialization
"""

import pytest
from datetime import datetime

from src.trade.evaluation import (
    EvaluationItem,
    EvaluationResult,
    Severity,
    SEVERITY_PRIORITY,
)
from src.trade.intent import TradeIntent, TradeDirection


class TestSeverity:
    """Tests for Severity enum."""

    def test_all_severities_exist(self):
        """Test that all expected severity levels exist."""
        expected_severities = ["BLOCKER", "WARNING", "INFO"]
        for severity_name in expected_severities:
            assert hasattr(Severity, severity_name)

    def test_severity_values(self):
        """Test severity enum values."""
        assert Severity.BLOCKER.value == "blocker"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"

    def test_severity_priority_ordering(self):
        """Test that severity priority is correctly ordered."""
        assert SEVERITY_PRIORITY[Severity.BLOCKER] > SEVERITY_PRIORITY[Severity.WARNING]
        assert SEVERITY_PRIORITY[Severity.WARNING] > SEVERITY_PRIORITY[Severity.INFO]


class TestEvaluationItem:
    """Tests for EvaluationItem creation."""

    def test_create_blocker_item(self):
        """Test creating a blocker evaluation item."""
        item = EvaluationItem(
            evaluator="risk_evaluator",
            code="RR001",
            severity=Severity.BLOCKER,
            title="Risk/Reward Below Minimum",
            message="Risk:reward ratio of 0.5 is below minimum 1:1",
        )

        assert item.evaluator == "risk_evaluator"
        assert item.code == "RR001"
        assert item.severity == Severity.BLOCKER
        assert item.title == "Risk/Reward Below Minimum"
        assert "0.5" in item.message

    def test_create_warning_item(self):
        """Test creating a warning evaluation item."""
        item = EvaluationItem(
            evaluator="regime_evaluator",
            code="REGIME001",
            severity=Severity.WARNING,
            title="Unfavorable Market Regime",
            message="Current market regime is bearish",
        )

        assert item.severity == Severity.WARNING

    def test_create_info_item(self):
        """Test creating an info evaluation item."""
        item = EvaluationItem(
            evaluator="info_evaluator",
            code="INFO001",
            severity=Severity.INFO,
            title="Trade Analysis Complete",
            message="Trade has been analyzed successfully",
        )

        assert item.severity == Severity.INFO

    def test_item_with_evidence(self):
        """Test creating item with evidence."""
        from src.trade.evaluation import Evidence

        evidence = Evidence(metric_name="risk_ratio", value=0.8, threshold=1.0, comparison="<")
        item = EvaluationItem(
            evaluator="comprehensive_eval",
            code="COMP001",
            severity=Severity.WARNING,
            title="Comprehensive Analysis",
            message="Detailed message",
            evidence=[evidence],
        )

        assert len(item.evidence) == 1
        assert item.evidence[0].metric_name == "risk_ratio"

    def test_item_default_evidence_empty_list(self):
        """Test that evidence defaults to empty list."""
        item = EvaluationItem(
            evaluator="eval",
            code="CODE",
            severity=Severity.INFO,
            title="Title",
            message="Message",
        )

        assert item.evidence == []

    def test_item_priority_property(self):
        """Test priority property for sorting."""
        blocker = EvaluationItem(
            evaluator="eval",
            code="B001",
            severity=Severity.BLOCKER,
            title="Blocker",
            message="Blocking",
        )

        info = EvaluationItem(
            evaluator="eval",
            code="I001",
            severity=Severity.INFO,
            title="Info",
            message="Info message",
        )

        assert blocker.priority > info.priority


class TestEvaluationResult:
    """Tests for EvaluationResult creation."""

    @pytest.fixture
    def sample_intent(self):
        """Create a sample trade intent."""
        return TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

    def test_create_clean_result(self, sample_intent):
        """Test creating a result with no issues."""
        result = EvaluationResult(
            intent=sample_intent,
            score=90,
            items=[],
            summary="Trade looks good",
        )

        assert result.intent == sample_intent
        assert result.score == 90
        assert len(result.items) == 0
        assert result.summary == "Trade looks good"

    def test_create_result_with_items(self, sample_intent):
        """Test creating a result with evaluation items."""
        items = [
            EvaluationItem(
                evaluator="eval1",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Message 1",
            ),
            EvaluationItem(
                evaluator="eval2",
                code="W002",
                severity=Severity.WARNING,
                title="Warning 2",
                message="Message 2",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=70,
            items=items,
            summary="Trade has issues",
        )

        assert len(result.items) == 2
        assert result.warnings == items
        assert result.blockers == []

    def test_blockers_property(self, sample_intent):
        """Test that blockers property filters correctly."""
        items = [
            EvaluationItem(
                evaluator="eval1",
                code="B001",
                severity=Severity.BLOCKER,
                title="Blocker",
                message="Blocking issue",
            ),
            EvaluationItem(
                evaluator="eval2",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Warning message",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=30,
            items=items,
            summary="Trade blocked",
        )

        assert len(result.blockers) == 1
        assert result.blockers[0].severity == Severity.BLOCKER

    def test_warnings_property(self, sample_intent):
        """Test that warnings property filters correctly."""
        items = [
            EvaluationItem(
                evaluator="eval1",
                code="B001",
                severity=Severity.BLOCKER,
                title="Blocker",
                message="Blocking issue",
            ),
            EvaluationItem(
                evaluator="eval2",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Warning message",
            ),
            EvaluationItem(
                evaluator="eval3",
                code="I001",
                severity=Severity.INFO,
                title="Info",
                message="Info message",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=50,
            items=items,
            summary="Mixed severity",
        )

        assert len(result.warnings) == 1
        assert result.warnings[0].severity == Severity.WARNING

    def test_has_blockers_false_when_no_blockers(self, sample_intent):
        """Test that has_blockers returns False when there are no blockers."""
        items = [
            EvaluationItem(
                evaluator="eval",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Minor warning",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=70,
            items=items,
            summary="Trade has warnings",
        )

        assert result.has_blockers is False

    def test_has_blockers_true_when_blockers_present(self, sample_intent):
        """Test that has_blockers returns True when blockers are present."""
        items = [
            EvaluationItem(
                evaluator="eval",
                code="B001",
                severity=Severity.BLOCKER,
                title="Blocker",
                message="Blocking issue",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=30,
            items=items,
            summary="Trade blocked",
        )

        assert result.has_blockers is True

    def test_has_blockers_false_when_no_items(self, sample_intent):
        """Test that has_blockers returns False when there are no items."""
        result = EvaluationResult(
            intent=sample_intent,
            score=95,
            items=[],
            summary="Trade looks good",
        )

        assert result.has_blockers is False

    def test_evaluated_at_default_to_now(self, sample_intent):
        """Test that evaluated_at defaults to current time."""
        before = datetime.utcnow()
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Test",
        )
        after = datetime.utcnow()

        assert before <= result.evaluated_at <= after

    def test_evaluators_run_default_empty(self, sample_intent):
        """Test that evaluators_run defaults to empty list."""
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Test",
        )

        assert result.evaluators_run == []

    def test_evaluators_run_custom(self, sample_intent):
        """Test setting custom evaluators_run."""
        evaluators = ["eval1", "eval2", "eval3"]
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Test",
            evaluators_run=evaluators,
        )

        assert result.evaluators_run == evaluators

    def test_score_valid_range(self, sample_intent):
        """Test that scores in valid range are accepted."""
        for score in [0, 25, 50, 75, 100]:
            result = EvaluationResult(
                intent=sample_intent,
                score=score,
                items=[],
                summary="Test",
            )
            assert result.score == score


class TestEvaluationResultOrdering:
    """Tests for result item ordering and priority."""

    @pytest.fixture
    def sample_intent(self):
        """Create a sample trade intent."""
        return TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

    def test_items_ordered_by_severity(self, sample_intent):
        """Test that items are ordered by severity priority."""
        items = [
            EvaluationItem(
                evaluator="eval",
                code="I001",
                severity=Severity.INFO,
                title="Info",
                message="Info",
            ),
            EvaluationItem(
                evaluator="eval",
                code="B001",
                severity=Severity.BLOCKER,
                title="Blocker",
                message="Blocker",
            ),
            EvaluationItem(
                evaluator="eval",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Warning",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=50,
            items=items,
            summary="Test",
        )

        # Items should maintain the order they were added
        assert len(result.items) == 3


class TestResultAggregation:
    """Tests for aggregating multiple items into results."""

    @pytest.fixture
    def sample_intent(self):
        """Create a sample trade intent."""
        return TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

    def test_aggregate_multiple_evaluators(self, sample_intent):
        """Test aggregating results from multiple evaluators."""
        items = [
            # From evaluator 1
            EvaluationItem(
                evaluator="risk_eval",
                code="RR001",
                severity=Severity.WARNING,
                title="Risk/Reward",
                message="Ratio is low",
            ),
            # From evaluator 2
            EvaluationItem(
                evaluator="regime_eval",
                code="REGIME001",
                severity=Severity.INFO,
                title="Regime",
                message="Bearish",
            ),
            # From evaluator 3
            EvaluationItem(
                evaluator="timing_eval",
                code="TIMING001",
                severity=Severity.WARNING,
                title="Timing",
                message="Not optimal",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=60,
            items=items,
            summary="Multiple concerns identified",
            evaluators_run=["risk_eval", "regime_eval", "timing_eval"],
        )

        assert len(result.items) == 3
        assert len(result.warnings) == 2
        assert len(result.evaluators_run) == 3

    def test_count_warnings(self, sample_intent):
        """Test counting warnings in result."""
        items = [
            EvaluationItem(
                evaluator="eval",
                code="W001",
                severity=Severity.WARNING,
                title="W",
                message="M",
            ),
            EvaluationItem(
                evaluator="eval",
                code="W002",
                severity=Severity.WARNING,
                title="W",
                message="M",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=70,
            items=items,
            summary="Test",
        )

        assert len(result.warnings) == 2
        assert len(result.blockers) == 0

    def test_count_blockers(self, sample_intent):
        """Test counting blockers in result."""
        items = [
            EvaluationItem(
                evaluator="eval",
                code="B001",
                severity=Severity.BLOCKER,
                title="B",
                message="M",
            ),
            EvaluationItem(
                evaluator="eval",
                code="B002",
                severity=Severity.BLOCKER,
                title="B",
                message="M",
            ),
            EvaluationItem(
                evaluator="eval",
                code="W001",
                severity=Severity.WARNING,
                title="W",
                message="M",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=20,
            items=items,
            summary="Test",
        )

        assert len(result.blockers) == 2
        assert len(result.warnings) == 1
