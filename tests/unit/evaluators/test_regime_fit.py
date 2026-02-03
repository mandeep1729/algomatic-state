"""Tests for RegimeFitEvaluator."""

from datetime import datetime

import pytest

from src.evaluators.base import EvaluatorConfig
from src.evaluators.context import ContextPack, RegimeContext
from src.evaluators.regime_fit import RegimeFitEvaluator, _is_generic_label
from src.trade.evaluation import Severity
from src.trade.intent import TradeIntent, TradeDirection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evaluator():
    return RegimeFitEvaluator()


def _make_intent(direction="long", symbol="AAPL", timeframe="5Min"):
    if direction == "long":
        return TradeIntent(
            user_id=1, symbol=symbol, direction=TradeDirection.LONG,
            timeframe=timeframe, entry_price=150.0,
            stop_loss=148.0, profit_target=154.0,
        )
    return TradeIntent(
        user_id=1, symbol=symbol, direction=TradeDirection.SHORT,
        timeframe=timeframe, entry_price=150.0,
        stop_loss=152.0, profit_target=146.0,
    )


def _make_context(
    timeframe="5Min",
    regime: RegimeContext | None = None,
    regimes: dict | None = None,
):
    r = regimes or {}
    if regime is not None:
        r[timeframe] = regime
    return ContextPack(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        primary_timeframe=timeframe,
        regimes=r,
    )


def _regime(
    tf="5Min",
    state_id=0,
    state_prob=0.8,
    state_label=None,
    entropy=None,
    transition_risk=None,
    is_ood=False,
):
    return RegimeContext(
        timeframe=tf,
        state_id=state_id,
        state_prob=state_prob,
        state_label=state_label,
        entropy=entropy,
        transition_risk=transition_risk,
        is_ood=is_ood,
    )


# ---------------------------------------------------------------------------
# _is_generic_label
# ---------------------------------------------------------------------------

class TestIsGenericLabel:

    def test_none_is_generic(self):
        assert _is_generic_label(None) is True

    def test_state_prefix_is_generic(self):
        assert _is_generic_label("state_0") is True
        assert _is_generic_label("state_12") is True

    def test_semantic_label_not_generic(self):
        assert _is_generic_label("bullish") is False
        assert _is_generic_label("down_trending") is False
        assert _is_generic_label("ranging") is False


# ---------------------------------------------------------------------------
# No regime → empty results
# ---------------------------------------------------------------------------

class TestRegimeFitNoData:

    def test_no_regime_returns_empty(self, evaluator):
        intent = _make_intent()
        context = _make_context()
        items = evaluator.evaluate(intent, context)
        assert items == []


# ---------------------------------------------------------------------------
# REG001: Direction conflict
# ---------------------------------------------------------------------------

class TestREG001DirectionConflict:

    def test_long_vs_bearish_warns(self, evaluator):
        intent = _make_intent("long")
        regime = _regime(state_label="bearish")
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert len(reg001) == 1
        assert reg001[0].severity == Severity.WARNING

    def test_short_vs_bullish_warns(self, evaluator):
        intent = _make_intent("short")
        regime = _regime(state_label="up_trending")
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert len(reg001) == 1

    def test_long_vs_bullish_no_conflict(self, evaluator):
        intent = _make_intent("long")
        regime = _regime(state_label="bullish")
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert reg001 == []

    def test_short_vs_bearish_no_conflict(self, evaluator):
        intent = _make_intent("short")
        regime = _regime(state_label="down_trending")
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert reg001 == []

    def test_generic_label_skips_check(self, evaluator):
        """Generic labels like 'state_3' should not trigger REG001."""
        intent = _make_intent("long")
        regime = _regime(state_label="state_3")
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert reg001 == []

    def test_none_label_skips_check(self, evaluator):
        intent = _make_intent("long")
        regime = _regime(state_label=None)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert reg001 == []

    def test_neutral_label_no_conflict(self, evaluator):
        """Labels not in BULLISH or BEARISH sets should not conflict."""
        intent = _make_intent("long")
        regime = _regime(state_label="ranging")
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg001 = [i for i in items if i.code == "REG001"]
        assert reg001 == []

    def test_all_bearish_labels_conflict_with_long(self, evaluator):
        from src.evaluators.regime_fit import BEARISH_LABELS
        intent = _make_intent("long")
        for label in BEARISH_LABELS:
            regime = _regime(state_label=label)
            context = _make_context(regime=regime)
            items = evaluator.evaluate(intent, context)
            reg001 = [i for i in items if i.code == "REG001"]
            assert len(reg001) == 1, f"Expected conflict for long vs {label}"

    def test_all_bullish_labels_conflict_with_short(self, evaluator):
        from src.evaluators.regime_fit import BULLISH_LABELS
        intent = _make_intent("short")
        for label in BULLISH_LABELS:
            regime = _regime(state_label=label)
            context = _make_context(regime=regime)
            items = evaluator.evaluate(intent, context)
            reg001 = [i for i in items if i.code == "REG001"]
            assert len(reg001) == 1, f"Expected conflict for short vs {label}"


# ---------------------------------------------------------------------------
# REG002: Transition risk
# ---------------------------------------------------------------------------

class TestREG002TransitionRisk:

    def test_high_transition_risk_warns(self, evaluator):
        intent = _make_intent()
        regime = _regime(transition_risk=0.45)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg002 = [i for i in items if i.code == "REG002"]
        assert len(reg002) == 1
        assert reg002[0].severity == Severity.WARNING
        assert reg002[0].evidence[0].value == 0.45

    def test_low_transition_risk_no_warning(self, evaluator):
        intent = _make_intent()
        regime = _regime(transition_risk=0.15)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg002 = [i for i in items if i.code == "REG002"]
        assert reg002 == []

    def test_transition_risk_at_threshold_no_warning(self, evaluator):
        """Exactly at threshold (0.3) should NOT trigger."""
        intent = _make_intent()
        regime = _regime(transition_risk=0.3)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg002 = [i for i in items if i.code == "REG002"]
        assert reg002 == []

    def test_transition_risk_none_skips(self, evaluator):
        intent = _make_intent()
        regime = _regime(transition_risk=None)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg002 = [i for i in items if i.code == "REG002"]
        assert reg002 == []

    def test_custom_threshold(self, evaluator):
        intent = _make_intent()
        regime = _regime(transition_risk=0.25)
        context = _make_context(regime=regime)

        config = EvaluatorConfig(thresholds={"transition_risk_threshold": 0.2})
        items = evaluator.evaluate(intent, context, config=config)
        reg002 = [i for i in items if i.code == "REG002"]
        assert len(reg002) == 1


# ---------------------------------------------------------------------------
# REG003: Entropy
# ---------------------------------------------------------------------------

class TestREG003Entropy:

    def test_high_entropy_info(self, evaluator):
        intent = _make_intent()
        regime = _regime(entropy=2.0)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg003 = [i for i in items if i.code == "REG003"]
        assert len(reg003) == 1
        assert reg003[0].severity == Severity.INFO

    def test_low_entropy_no_finding(self, evaluator):
        intent = _make_intent()
        regime = _regime(entropy=0.5)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg003 = [i for i in items if i.code == "REG003"]
        assert reg003 == []

    def test_entropy_at_threshold_no_finding(self, evaluator):
        intent = _make_intent()
        regime = _regime(entropy=1.5)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg003 = [i for i in items if i.code == "REG003"]
        assert reg003 == []

    def test_entropy_none_skips(self, evaluator):
        intent = _make_intent()
        regime = _regime(entropy=None)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg003 = [i for i in items if i.code == "REG003"]
        assert reg003 == []

    def test_custom_entropy_threshold(self, evaluator):
        intent = _make_intent()
        regime = _regime(entropy=1.2)
        context = _make_context(regime=regime)

        config = EvaluatorConfig(thresholds={"entropy_threshold": 1.0})
        items = evaluator.evaluate(intent, context, config=config)
        reg003 = [i for i in items if i.code == "REG003"]
        assert len(reg003) == 1


# ---------------------------------------------------------------------------
# REG004: OOD
# ---------------------------------------------------------------------------

class TestREG004OOD:

    def test_ood_warns(self, evaluator):
        intent = _make_intent()
        regime = _regime(is_ood=True, state_id=-1)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg004 = [i for i in items if i.code == "REG004"]
        assert len(reg004) == 1
        assert reg004[0].severity == Severity.WARNING

    def test_not_ood_no_finding(self, evaluator):
        intent = _make_intent()
        regime = _regime(is_ood=False)
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        reg004 = [i for i in items if i.code == "REG004"]
        assert reg004 == []


# ---------------------------------------------------------------------------
# Multiple checks firing together
# ---------------------------------------------------------------------------

class TestRegimeFitCombined:

    def test_multiple_checks_fire(self, evaluator):
        """Multiple regime issues can fire simultaneously."""
        intent = _make_intent("long")
        regime = _regime(
            state_label="bearish",
            transition_risk=0.5,
            entropy=2.0,
            is_ood=False,
        )
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "REG001" in codes  # direction conflict
        assert "REG002" in codes  # transition risk
        assert "REG003" in codes  # entropy

    def test_all_four_fire(self, evaluator):
        intent = _make_intent("long")
        regime = _regime(
            state_label="bearish",
            transition_risk=0.5,
            entropy=2.0,
            is_ood=True,
            state_id=-1,
        )
        context = _make_context(regime=regime)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        # REG001 skips because is_ood label check — but state_label "bearish"
        # is not generic so it should still fire.
        # Actually: _is_generic_label("bearish") is False, so REG001 fires
        assert "REG001" in codes
        assert "REG002" in codes
        assert "REG003" in codes
        assert "REG004" in codes

    def test_severity_override_from_config(self, evaluator):
        intent = _make_intent("long")
        regime = _regime(state_label="bearish")
        context = _make_context(regime=regime)

        config = EvaluatorConfig(
            severity_overrides={"REG001": Severity.BLOCKER}
        )
        items = evaluator.evaluate(intent, context, config=config)
        reg001 = [i for i in items if i.code == "REG001"]
        assert reg001[0].severity == Severity.BLOCKER
