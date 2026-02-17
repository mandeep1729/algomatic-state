"""Tests for guardrails rules enforcement.

Tests cover:
- Prediction detection in messages
- Message sanitization
- Evaluation result validation
- Warning template formatting
- Non-predictive language enforcement
"""

import pytest

from src.rules.guardrails import (
    contains_prediction,
    sanitize_message,
    validate_evaluation_result,
    sanitize_evaluation_result,
    get_warning_template,
    format_warning,
    WARNING_TEMPLATES,
)
from src.trade.evaluation import (
    EvaluationResult,
    EvaluationItem,
    Severity,
)
from src.trade.intent import TradeIntent, TradeDirection


class TestPredictionDetection:
    """Tests for detecting predictive language."""

    def test_detect_will_go_up(self):
        """Test detection of 'will go up' prediction."""
        assert contains_prediction("The price will go up tomorrow") is True

    def test_detect_will_rise(self):
        """Test detection of 'will rise' prediction."""
        assert contains_prediction("Stock will rise significantly") is True

    def test_detect_will_fall(self):
        """Test detection of 'will fall' prediction."""
        assert contains_prediction("Price will fall next week") is True

    def test_detect_expected_to_reach(self):
        """Test detection of 'expected to reach' prediction."""
        assert contains_prediction("Stock is expected to reach $200") is True

    def test_detect_high_probability(self):
        """Test detection of 'high probability' claim."""
        assert contains_prediction("High probability this stock moves up") is True

    def test_detect_buy_signal(self):
        """Test detection of 'buy signal' language."""
        assert contains_prediction("This is a buy signal") is True

    def test_detect_sell_signal(self):
        """Test detection of 'sell signal' language."""
        assert contains_prediction("Clear sell signal here") is True

    def test_detect_strong_buy(self):
        """Test detection of 'strong buy' language."""
        assert contains_prediction("Strong buy recommendation") is True

    def test_detect_guaranteed(self):
        """Test detection of 'guaranteed' language."""
        assert contains_prediction("Guaranteed profit if you buy now") is True

    def test_detect_case_insensitive(self):
        """Test that prediction detection is case-insensitive."""
        assert contains_prediction("WILL GO UP") is True
        assert contains_prediction("Will Go Up") is True
        assert contains_prediction("will go up") is True

    def test_no_prediction_in_safe_text(self):
        """Test that safe text doesn't trigger prediction detection."""
        safe_messages = [
            "Risk/reward ratio of 1:2",
            "Stop loss is at 145",
            "Position size: 100 shares",
            "Entry price is 150",
            "Market regime is neutral",
        ]

        for message in safe_messages:
            assert contains_prediction(message) is False

    def test_no_prediction_in_risk_focused_text(self):
        """Test that risk-focused language doesn't trigger detection."""
        risk_messages = [
            "This trade risks 2% of your account",
            "Stop loss below support",
            "Risk/reward is favorable",
            "Consider your risk tolerance",
        ]

        for message in risk_messages:
            assert contains_prediction(message) is False

    def test_detect_likely_to_rise(self):
        """Test detection of 'likely to' pattern."""
        assert contains_prediction("Likely to rise in value") is True

    def test_detect_should_reach(self):
        """Test detection of 'should reach' pattern."""
        assert contains_prediction("Should reach $200 target") is True


class TestMessageSanitization:
    """Tests for sanitizing predictive language."""

    def test_sanitize_will_go_up(self):
        """Test sanitizing 'will go up' to safer language."""
        original = "The price will go up"
        sanitized = sanitize_message(original)
        assert "will go up" not in sanitized.lower()
        assert sanitized != original

    def test_sanitize_will_rise(self):
        """Test sanitizing 'will rise' to safer language."""
        original = "Price will rise soon"
        sanitized = sanitize_message(original)
        assert "will rise" not in sanitized.lower()

    def test_sanitize_high_probability(self):
        """Test sanitizing 'high probability' claim."""
        original = "High probability of profit"
        sanitized = sanitize_message(original)
        assert "high probability" not in sanitized.lower()

    def test_sanitize_expected_to_reach(self):
        """Test sanitizing 'expected to reach' language."""
        original = "Expected to reach $200"
        sanitized = sanitize_message(original)
        assert "expected to reach" not in sanitized.lower()

    def test_sanitize_guaranteed(self):
        """Test sanitizing 'guaranteed' claim."""
        original = "Guaranteed returns if you trade this"
        sanitized = sanitize_message(original)
        assert "guaranteed" not in sanitized.lower()
        assert "possible" in sanitized.lower()

    def test_sanitize_case_insensitive(self):
        """Test that sanitization works regardless of case."""
        original1 = "WILL GO UP soon"
        original2 = "Will Go Up soon"
        original3 = "will go up soon"

        sanitized1 = sanitize_message(original1)
        sanitized2 = sanitize_message(original2)
        sanitized3 = sanitize_message(original3)

        assert "will go up" not in sanitized1.lower()
        assert "will go up" not in sanitized2.lower()
        assert "will go up" not in sanitized3.lower()

    def test_sanitize_preserves_safe_content(self):
        """Test that sanitization preserves safe, non-predictive content."""
        safe_message = "Risk per share is $5. Position size should be limited."
        sanitized = sanitize_message(safe_message)
        assert "Risk per share" in sanitized
        assert "Position size" in sanitized

    def test_multiple_predictions_in_one_message(self):
        """Test sanitizing message with multiple predictive phrases."""
        original = "Price will rise and will go up significantly"
        sanitized = sanitize_message(original)
        assert "will rise" not in sanitized.lower()
        assert "will go up" not in sanitized.lower()


class TestEvaluationResultValidation:
    """Tests for validating evaluation results for predictive content."""

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

    def test_validate_clean_result(self, sample_intent):
        """Test that clean result passes validation."""
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="This trade has favorable risk/reward",
        )

        warnings = validate_evaluation_result(result)
        assert len(warnings) == 0

    def test_validate_result_with_predictive_summary(self, sample_intent):
        """Test that predictive summary is detected."""
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Price will go up significantly",
        )

        warnings = validate_evaluation_result(result)
        assert len(warnings) > 0
        assert any("Summary contains predictive" in w for w in warnings)

    def test_validate_result_with_predictive_item_message(self, sample_intent):
        """Test that predictive language in item message is detected."""
        item = EvaluationItem(
            evaluator="test",
            code="T001",
            severity=Severity.INFO,
            title="Test",
            message="Stock will rise due to earnings",
        )

        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[item],
            summary="Clean summary",
        )

        warnings = validate_evaluation_result(result)
        assert len(warnings) > 0
        assert any("message contains predictive" in w for w in warnings)

    def test_validate_result_with_predictive_item_title(self, sample_intent):
        """Test that predictive language in item title is detected."""
        item = EvaluationItem(
            evaluator="test",
            code="T001",
            severity=Severity.INFO,
            title="Expected to reach $200",
            message="Clean message",
        )

        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[item],
            summary="Clean summary",
        )

        warnings = validate_evaluation_result(result)
        assert len(warnings) > 0
        assert any("title contains predictive" in w for w in warnings)

    def test_validate_result_with_multiple_issues(self, sample_intent):
        """Test detection of multiple predictive instances."""
        items = [
            EvaluationItem(
                evaluator="test",
                code="T001",
                severity=Severity.INFO,
                title="Will go up",
                message="Expected to reach $200",
            ),
        ]

        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=items,
            summary="Price will rise tomorrow",
        )

        warnings = validate_evaluation_result(result)
        assert len(warnings) >= 3

    def test_validate_empty_result(self, sample_intent):
        """Test validation of empty result."""
        result = EvaluationResult(
            intent=sample_intent,
            score=100,
            items=[],
            summary="",
        )

        warnings = validate_evaluation_result(result)
        assert len(warnings) == 0


class TestEvaluationResultSanitization:
    """Tests for sanitizing evaluation results."""

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

    def test_sanitize_clean_result_unchanged(self, sample_intent):
        """Test that clean result is not modified."""
        original = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Risk/reward is favorable",
        )

        sanitized = sanitize_evaluation_result(original)

        assert sanitized.summary == original.summary
        assert len(sanitized.items) == len(original.items)

    def test_sanitize_predictive_summary(self, sample_intent):
        """Test sanitizing predictive summary."""
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Price will go up tomorrow",
        )

        sanitized = sanitize_evaluation_result(result)

        assert "will go up" not in sanitized.summary.lower()
        assert sanitized.summary != result.summary

    def test_sanitize_item_message(self, sample_intent):
        """Test sanitizing predictive item message."""
        item = EvaluationItem(
            evaluator="test",
            code="T001",
            severity=Severity.WARNING,
            title="Risk Assessment",
            message="Price will rise above $160",
        )

        result = EvaluationResult(
            intent=sample_intent,
            score=70,
            items=[item],
            summary="Clean",
        )

        sanitized = sanitize_evaluation_result(result)

        assert "will rise" not in sanitized.items[0].message.lower()

    def test_sanitize_preserves_intent(self, sample_intent):
        """Test that sanitization preserves the trade intent."""
        result = EvaluationResult(
            intent=sample_intent,
            score=80,
            items=[],
            summary="Will go up",
        )

        sanitized = sanitize_evaluation_result(result)

        assert sanitized.intent == sample_intent

    def test_sanitize_preserves_metadata(self, sample_intent):
        """Test that sanitization preserves other metadata."""
        result = EvaluationResult(
            intent=sample_intent,
            score=75,
            items=[],
            summary="Will go up",
            evaluators_run=["eval1", "eval2"],
        )

        sanitized = sanitize_evaluation_result(result)

        assert sanitized.score == 75
        assert sanitized.evaluators_run == ["eval1", "eval2"]


class TestWarningTemplates:
    """Tests for warning template management."""

    def test_warning_templates_not_empty(self):
        """Test that warning templates are defined."""
        assert len(WARNING_TEMPLATES) > 0

    def test_get_existing_template(self):
        """Test retrieving an existing warning template."""
        template = get_warning_template("low_rr")
        assert template is not None
        assert template.code == "RR001"

    def test_get_nonexistent_template(self):
        """Test retrieving a nonexistent template."""
        template = get_warning_template("nonexistent_key")
        assert template is None

    def test_template_has_required_fields(self):
        """Test that templates have all required fields."""
        for key, template in WARNING_TEMPLATES.items():
            assert hasattr(template, "code")
            assert hasattr(template, "title")
            assert hasattr(template, "message_template")
            assert hasattr(template, "severity")
            assert template.code is not None
            assert template.title is not None
            assert template.message_template is not None
            assert template.severity is not None


class TestWarningFormatting:
    """Tests for formatting warning templates."""

    def test_format_low_rr_warning(self):
        """Test formatting low risk:reward warning."""
        result = format_warning("low_rr", ratio=0.8, threshold=1.0)

        assert result is not None
        title, message, severity = result
        assert "Low Risk/Reward" in title
        assert "0.80" in message
        assert "1.0" in message
        assert severity == Severity.WARNING

    def test_format_excessive_risk_warning(self):
        """Test formatting excessive position risk warning."""
        result = format_warning(
            "excessive_risk",
            risk_pct=5.0,
            max_pct=2.0,
            suggested_size=50,
        )

        assert result is not None
        title, message, severity = result
        assert "Excessive Position Risk" in title
        assert "5.0" in message
        assert "2.0" in message
        assert severity == Severity.CRITICAL

    def test_format_tight_stop_warning(self):
        """Test formatting tight stop loss warning."""
        result = format_warning("tight_stop", atr_mult=0.5, min_mult=1.0)

        assert result is not None
        title, message, severity = result
        assert "Tight Stop Loss" in title
        assert "0.50" in message

    def test_format_counter_trend_warning(self):
        """Test formatting counter-trend trade warning."""
        result = format_warning("counter_trend", direction="long", regime="bearish")

        assert result is not None
        title, message, severity = result
        assert "Counter-Trend" in title
        assert "long" in message
        assert "bearish" in message
        assert severity == Severity.WARNING

    def test_format_nonexistent_template(self):
        """Test formatting nonexistent template returns None."""
        result = format_warning("nonexistent")
        assert result is None

    def test_template_format_method(self):
        """Test the format method on templates."""
        template = get_warning_template("low_rr")
        title, message = template.format(ratio=0.8, threshold=1.0)

        assert title == template.title
        assert "0.80" in message
        assert "1.0" in message


class TestNonPredictiveLanguageEnforcement:
    """Tests ensuring output remains non-predictive."""

    def test_all_warning_templates_are_safe(self):
        """Test that all warning templates use safe language."""
        for key, template in WARNING_TEMPLATES.items():
            assert not contains_prediction(template.title), \
                f"Template '{key}' title contains prediction: {template.title}"
            assert not contains_prediction(template.message_template), \
                f"Template '{key}' message contains prediction: {template.message_template}"

    def test_risk_focused_language_examples(self):
        """Test examples of appropriate risk-focused language."""
        safe_phrases = [
            "Risk/reward ratio",
            "Consider your risk tolerance",
            "Stop loss placement",
            "Position size limits",
            "Risk per share",
            "Account risk percentage",
            "Market regime",
            "Support and resistance",
        ]

        for phrase in safe_phrases:
            assert not contains_prediction(phrase), \
                f"Safe phrase '{phrase}' incorrectly flagged as prediction"
