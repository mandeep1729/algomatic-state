"""Tests for the EvaluatorOrchestrator.

Tests cover:
- Orchestrator initialization and configuration
- Evaluator loading and management
- Evaluation execution (sequential and parallel)
- Result aggregation and deduplication
- Error handling and logging
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

from src.orchestrator import EvaluatorOrchestrator, OrchestratorConfig
from src.trade.intent import TradeIntent, TradeDirection
from src.trade.evaluation import EvaluationResult, EvaluationItem, Severity
from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.context import ContextPack, ContextPackBuilder


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OrchestratorConfig()
        assert config.parallel_execution is False
        assert config.max_workers == 4
        assert config.fail_fast is False
        assert config.include_info is True
        assert config.context_lookback_bars == 100
        assert config.additional_timeframes == ["1Hour", "1Day"]

    def test_custom_config(self):
        """Test custom configuration."""
        config = OrchestratorConfig(
            parallel_execution=True,
            max_workers=8,
            fail_fast=True,
            include_info=False,
            context_lookback_bars=50,
        )
        assert config.parallel_execution is True
        assert config.max_workers == 8
        assert config.fail_fast is True
        assert config.include_info is False
        assert config.context_lookback_bars == 50


class TestEvaluatorOrchestratorInitialization:
    """Tests for EvaluatorOrchestrator initialization."""

    def test_init_default(self):
        """Test initialization with defaults."""
        orchestrator = EvaluatorOrchestrator()
        assert orchestrator.config is not None
        assert orchestrator.context_builder is not None
        assert orchestrator._evaluators == []

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = OrchestratorConfig(parallel_execution=True)
        orchestrator = EvaluatorOrchestrator(config=config)
        assert orchestrator.config.parallel_execution is True

    def test_init_with_context_builder(self):
        """Test initialization with custom context builder."""
        mock_builder = Mock(spec=ContextPackBuilder)
        orchestrator = EvaluatorOrchestrator(context_builder=mock_builder)
        assert orchestrator.context_builder is mock_builder


class TestEvaluatorLoading:
    """Tests for evaluator loading functionality."""

    @patch('src.orchestrator.get_evaluator')
    @patch('src.orchestrator.get_all_evaluators')
    def test_load_all_evaluators(self, mock_get_all, mock_get_one):
        """Test loading all evaluators."""
        mock_evaluator1 = Mock(spec=Evaluator)
        mock_evaluator1.name = "eval1"
        mock_evaluator1.is_enabled.return_value = True

        mock_evaluator2 = Mock(spec=Evaluator)
        mock_evaluator2.name = "eval2"
        mock_evaluator2.is_enabled.return_value = True

        mock_get_all.return_value = [mock_evaluator1, mock_evaluator2]

        orchestrator = EvaluatorOrchestrator()
        orchestrator.load_evaluators()

        assert len(orchestrator._evaluators) == 2
        mock_get_all.assert_called_once()

    @patch('src.orchestrator.get_evaluator')
    def test_load_specific_evaluators(self, mock_get_evaluator):
        """Test loading specific evaluators by name."""
        mock_eval = Mock(spec=Evaluator)
        mock_eval.name = "specific_eval"
        mock_eval.is_enabled.return_value = True
        mock_get_evaluator.return_value = mock_eval

        orchestrator = EvaluatorOrchestrator()
        orchestrator.load_evaluators(evaluator_names=["specific_eval"])

        assert len(orchestrator._evaluators) == 1
        assert orchestrator._evaluators[0].name == "specific_eval"

    @patch('src.orchestrator.get_evaluator')
    def test_load_evaluator_not_found(self, mock_get_evaluator):
        """Test handling when evaluator is not found."""
        mock_get_evaluator.side_effect = KeyError("evaluator_not_found")

        orchestrator = EvaluatorOrchestrator()
        orchestrator.load_evaluators(evaluator_names=["nonexistent"])

        assert len(orchestrator._evaluators) == 0

    @patch('src.orchestrator.get_evaluator')
    def test_load_disabled_evaluators_filtered(self, mock_get_evaluator):
        """Test that disabled evaluators are filtered when enabled_only=True."""
        mock_eval = Mock(spec=Evaluator)
        mock_eval.name = "disabled_eval"
        mock_eval.is_enabled.return_value = False
        mock_get_evaluator.return_value = mock_eval

        orchestrator = EvaluatorOrchestrator()
        orchestrator.load_evaluators(
            evaluator_names=["disabled_eval"],
            enabled_only=True
        )

        assert len(orchestrator._evaluators) == 0

    @patch('src.orchestrator.get_evaluator')
    def test_load_disabled_evaluators_included(self, mock_get_evaluator):
        """Test that disabled evaluators are included when enabled_only=False."""
        mock_eval = Mock(spec=Evaluator)
        mock_eval.name = "disabled_eval"
        mock_eval.is_enabled.return_value = False
        mock_get_evaluator.return_value = mock_eval

        orchestrator = EvaluatorOrchestrator()
        orchestrator.load_evaluators(
            evaluator_names=["disabled_eval"],
            enabled_only=False
        )

        assert len(orchestrator._evaluators) == 1


class TestTradeIntentEvaluation:
    """Tests for trade intent evaluation."""

    @pytest.fixture
    def mock_evaluators(self):
        """Create mock evaluators."""
        evaluators = []
        for i in range(2):
            mock_eval = Mock(spec=Evaluator)
            mock_eval.name = f"evaluator_{i}"
            mock_eval.is_enabled.return_value = True

            # Mock evaluate method
            item = EvaluationItem(
                evaluator=f"evaluator_{i}",
                code=f"E{i}",
                severity=Severity.WARNING,
                title=f"Test Warning {i}",
                message=f"Test message {i}",
            )
            mock_eval.evaluate.return_value = [item]
            evaluators.append(mock_eval)
        return evaluators

    @pytest.fixture
    def sample_trade_intent(self):
        """Create a sample trade intent."""
        return TradeIntent(
            user_id=1,
            symbol="AAPL",
            direction=TradeDirection.LONG,
            timeframe="1Hour",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
            position_size=100,
        )

    @pytest.fixture
    def mock_context_builder(self):
        """Create a mock context builder."""
        mock_builder = Mock(spec=ContextPackBuilder)
        mock_context = Mock(spec=ContextPack)
        mock_builder.build.return_value = mock_context
        return mock_builder

    def test_evaluate_with_no_evaluators_loads_them(
        self,
        sample_trade_intent,
        mock_context_builder
    ):
        """Test that evaluators are auto-loaded if not already loaded."""
        orchestrator = EvaluatorOrchestrator(context_builder=mock_context_builder)

        with patch.object(orchestrator, 'load_evaluators') as mock_load:
            with patch.object(orchestrator, '_run_sequential', return_value=[]):
                orchestrator.evaluate(sample_trade_intent)
                mock_load.assert_called_once()

    def test_evaluate_sequential_execution(
        self,
        sample_trade_intent,
        mock_evaluators,
        mock_context_builder
    ):
        """Test sequential evaluation execution."""
        config = OrchestratorConfig(parallel_execution=False)
        orchestrator = EvaluatorOrchestrator(config=config, context_builder=mock_context_builder)
        orchestrator._evaluators = mock_evaluators

        result = orchestrator.evaluate(sample_trade_intent)

        assert isinstance(result, EvaluationResult)
        assert result.intent == sample_trade_intent
        assert len(result.items) >= 0
        assert len(result.evaluators_run) == 2

    def test_evaluate_parallel_execution(
        self,
        sample_trade_intent,
        mock_evaluators,
        mock_context_builder
    ):
        """Test parallel evaluation execution."""
        config = OrchestratorConfig(parallel_execution=True, max_workers=2)
        orchestrator = EvaluatorOrchestrator(config=config, context_builder=mock_context_builder)
        orchestrator._evaluators = mock_evaluators

        result = orchestrator.evaluate(sample_trade_intent)

        assert isinstance(result, EvaluationResult)
        assert len(result.evaluators_run) == 2

    def test_evaluate_with_provided_context(
        self,
        sample_trade_intent,
        mock_evaluators,
        mock_context_builder
    ):
        """Test evaluation with pre-built context."""
        orchestrator = EvaluatorOrchestrator(context_builder=mock_context_builder)
        orchestrator._evaluators = mock_evaluators

        mock_context = Mock(spec=ContextPack)
        result = orchestrator.evaluate(sample_trade_intent, context=mock_context)

        # Context builder should not be called when context is provided
        mock_context_builder.build.assert_not_called()
        assert result is not None

    def test_evaluate_filters_info_items(self, sample_trade_intent, mock_context_builder):
        """Test that INFO items are filtered when include_info=False."""
        config = OrchestratorConfig(include_info=False)
        orchestrator = EvaluatorOrchestrator(config=config, context_builder=mock_context_builder)

        mock_eval = Mock(spec=Evaluator)
        mock_eval.name = "test_eval"
        mock_eval.is_enabled.return_value = True

        # Create items with different severities
        items = [
            EvaluationItem(
                evaluator="test_eval",
                code="I001",
                severity=Severity.INFO,
                title="Info",
                message="Info message",
            ),
            EvaluationItem(
                evaluator="test_eval",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Warning message",
            ),
        ]
        mock_eval.evaluate.return_value = items
        orchestrator._evaluators = [mock_eval]

        result = orchestrator.evaluate(sample_trade_intent)

        # Info items should be filtered out
        severities = [item.severity for item in result.items]
        assert Severity.INFO not in severities
        assert Severity.WARNING in severities

    def test_evaluate_fail_fast_on_blocker(
        self,
        sample_trade_intent,
        mock_context_builder
    ):
        """Test fail-fast behavior when blocker is encountered."""
        config = OrchestratorConfig(fail_fast=True)
        orchestrator = EvaluatorOrchestrator(config=config, context_builder=mock_context_builder)

        # First evaluator returns blocker
        mock_eval1 = Mock(spec=Evaluator)
        mock_eval1.name = "eval1"
        blocker_item = EvaluationItem(
            evaluator="eval1",
            code="B001",
            severity=Severity.BLOCKER,
            title="Blocker",
            message="Blocking issue",
        )
        mock_eval1.evaluate.return_value = [blocker_item]

        # Second evaluator should not be called
        mock_eval2 = Mock(spec=Evaluator)
        mock_eval2.name = "eval2"

        orchestrator._evaluators = [mock_eval1, mock_eval2]
        result = orchestrator.evaluate(sample_trade_intent)

        # Verify blocker is in results
        assert len(result.blockers) > 0

    def test_evaluate_handles_evaluator_exception(
        self,
        sample_trade_intent,
        mock_context_builder
    ):
        """Test that evaluator exceptions are caught and reported."""
        orchestrator = EvaluatorOrchestrator(context_builder=mock_context_builder)

        mock_eval = Mock(spec=Evaluator)
        mock_eval.name = "failing_eval"
        mock_eval.evaluate.side_effect = Exception("Evaluation error")

        orchestrator._evaluators = [mock_eval]
        result = orchestrator.evaluate(sample_trade_intent)

        # Should have error item in results
        error_items = [item for item in result.items if item.code == "ERR001"]
        assert len(error_items) > 0

    def test_evaluate_deduplicates_items(
        self,
        sample_trade_intent,
        mock_context_builder
    ):
        """Test that items are deduplicated by evaluator:code key."""
        orchestrator = EvaluatorOrchestrator(context_builder=mock_context_builder)

        # Create evaluator returning same code twice (should deduplicate on evaluator:code)
        mock_eval = Mock(spec=Evaluator)
        mock_eval.name = "eval1"
        item1 = EvaluationItem(
            evaluator="eval1",
            code="SAME_CODE",
            severity=Severity.INFO,
            title="Item",
            message="Message 1",
        )
        item2 = EvaluationItem(
            evaluator="eval1",
            code="SAME_CODE",
            severity=Severity.WARNING,
            title="Item",
            message="Message 2",
        )
        # Both items are returned but with different severity
        mock_eval.evaluate.return_value = [item1, item2]

        orchestrator._evaluators = [mock_eval]
        result = orchestrator.evaluate(sample_trade_intent)

        # Deduplication should keep highest severity (WARNING over INFO)
        same_code_items = [item for item in result.items if item.code == "SAME_CODE"]
        assert len(same_code_items) == 1
        assert same_code_items[0].severity == Severity.WARNING

    def test_evaluate_generates_summary(
        self,
        sample_trade_intent,
        mock_evaluators,
        mock_context_builder
    ):
        """Test that evaluation summary is generated."""
        orchestrator = EvaluatorOrchestrator(context_builder=mock_context_builder)
        orchestrator._evaluators = mock_evaluators

        result = orchestrator.evaluate(sample_trade_intent)

        assert result.summary is not None
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_evaluate_computes_score(
        self,
        sample_trade_intent,
        mock_evaluators,
        mock_context_builder
    ):
        """Test that evaluation score is computed."""
        orchestrator = EvaluatorOrchestrator(context_builder=mock_context_builder)
        orchestrator._evaluators = mock_evaluators

        result = orchestrator.evaluate(sample_trade_intent)

        assert isinstance(result.score, (int, float))
        assert 0 <= result.score <= 100


class TestDeduplication:
    """Tests for item deduplication logic."""

    def test_deduplicate_keeps_highest_severity(self):
        """Test that deduplication keeps highest severity for same evaluator:code key."""
        orchestrator = EvaluatorOrchestrator()

        # Items from same evaluator with same code - second one higher severity
        items = [
            EvaluationItem(
                evaluator="eval1",
                code="SAME",
                severity=Severity.INFO,
                title="Info",
                message="Info message",
            ),
            EvaluationItem(
                evaluator="eval1",
                code="SAME",
                severity=Severity.BLOCKER,
                title="Blocker",
                message="Blocker message",
            ),
        ]

        deduplicated = orchestrator._deduplicate_items(items)

        # Deduplication key is evaluator:code, so should have 1 item
        assert len(deduplicated) == 1
        assert deduplicated[0].severity == Severity.BLOCKER

    def test_deduplicate_different_codes(self):
        """Test that items with different codes are not deduplicated."""
        orchestrator = EvaluatorOrchestrator()

        items = [
            EvaluationItem(
                evaluator="eval1",
                code="CODE1",
                severity=Severity.WARNING,
                title="Item 1",
                message="Message 1",
            ),
            EvaluationItem(
                evaluator="eval2",
                code="CODE2",
                severity=Severity.WARNING,
                title="Item 2",
                message="Message 2",
            ),
        ]

        deduplicated = orchestrator._deduplicate_items(items)

        assert len(deduplicated) == 2


class TestScoreComputation:
    """Tests for score computation."""

    def test_compute_score_with_blockers(self):
        """Test score computation with blockers."""
        orchestrator = EvaluatorOrchestrator()

        items = [
            EvaluationItem(
                evaluator="eval",
                code="B001",
                severity=Severity.BLOCKER,
                title="Blocker",
                message="Blocking issue",
            ),
        ]

        score = orchestrator._compute_score(items)
        # BLOCKER is -40 points: 100 - 40 = 60
        assert score == 60.0

    def test_compute_score_with_no_issues(self):
        """Test score computation with no issues."""
        orchestrator = EvaluatorOrchestrator()

        items = []
        score = orchestrator._compute_score(items)

        assert score > 80  # Clean trade should have high score

    def test_compute_score_with_warnings(self):
        """Test score computation with warnings."""
        orchestrator = EvaluatorOrchestrator()

        items = [
            EvaluationItem(
                evaluator="eval",
                code="W001",
                severity=Severity.WARNING,
                title="Warning",
                message="Warning message",
            ),
        ]

        score = orchestrator._compute_score(items)
        # WARNING is -5 points: 100 - 5 = 95
        assert score == 95.0
