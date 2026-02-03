"""Tests for MTFAEvaluator."""

from datetime import datetime

import pytest

from src.evaluators.base import EvaluatorConfig
from src.evaluators.context import ContextPack, MTFAContext, RegimeContext
from src.evaluators.mtfa import MTFAEvaluator
from src.trade.evaluation import Severity
from src.trade.intent import TradeIntent, TradeDirection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evaluator():
    return MTFAEvaluator()


def _make_intent(direction="long", timeframe="5Min"):
    if direction == "long":
        return TradeIntent(
            user_id=1, symbol="AAPL", direction=TradeDirection.LONG,
            timeframe=timeframe, entry_price=150.0,
            stop_loss=148.0, profit_target=154.0,
        )
    return TradeIntent(
        user_id=1, symbol="AAPL", direction=TradeDirection.SHORT,
        timeframe=timeframe, entry_price=150.0,
        stop_loss=152.0, profit_target=146.0,
    )


def _make_context(
    timeframe="5Min",
    mtfa: MTFAContext | None = None,
    regimes: dict | None = None,
):
    return ContextPack(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        primary_timeframe=timeframe,
        mtfa=mtfa,
        regimes=regimes or {},
    )


def _regime(tf, transition_risk=None, state_id=0, state_prob=0.8):
    return RegimeContext(
        timeframe=tf,
        state_id=state_id,
        state_prob=state_prob,
        transition_risk=transition_risk,
    )


# ---------------------------------------------------------------------------
# No MTFA data → empty results
# ---------------------------------------------------------------------------

class TestMTFANoData:

    def test_none_mtfa_returns_empty(self, evaluator):
        intent = _make_intent()
        context = _make_context(mtfa=None)
        assert evaluator.evaluate(intent, context) == []

    def test_none_alignment_score_returns_empty(self, evaluator):
        intent = _make_intent()
        context = _make_context(mtfa=MTFAContext())
        assert evaluator.evaluate(intent, context) == []


# ---------------------------------------------------------------------------
# MTFA001: Low alignment
# ---------------------------------------------------------------------------

class TestMTFA001LowAlignment:

    def test_low_alignment_warns(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(
            alignment_score=0.4,
            conflicts=["1Day: bearish (vs majority: bullish)"],
        )
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa001 = [i for i in items if i.code == "MTFA001"]
        assert len(mtfa001) == 1
        assert mtfa001[0].severity == Severity.WARNING

    def test_low_alignment_includes_conflicts_in_message(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(
            alignment_score=0.5,
            conflicts=["1Hour: ranging (vs majority: bullish)"],
        )
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa001 = [i for i in items if i.code == "MTFA001"]
        assert "1Hour" in mtfa001[0].message
        assert "ranging" in mtfa001[0].message

    def test_at_threshold_no_warning(self, evaluator):
        """Alignment exactly at 0.6 should NOT trigger MTFA001."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.6)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa001 = [i for i in items if i.code == "MTFA001"]
        assert mtfa001 == []

    def test_custom_low_threshold(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.55)
        context = _make_context(mtfa=mtfa)

        config = EvaluatorConfig(thresholds={"low_alignment_threshold": 0.7})
        items = evaluator.evaluate(intent, context, config=config)
        mtfa001 = [i for i in items if i.code == "MTFA001"]
        assert len(mtfa001) == 1

    def test_empty_conflicts_still_warns(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.4, conflicts=[])
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa001 = [i for i in items if i.code == "MTFA001"]
        assert len(mtfa001) == 1


# ---------------------------------------------------------------------------
# MTFA002: High alignment (positive confirmation)
# ---------------------------------------------------------------------------

class TestMTFA002HighAlignment:

    def test_high_alignment_info(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa002 = [i for i in items if i.code == "MTFA002"]
        assert len(mtfa002) == 1
        assert mtfa002[0].severity == Severity.INFO

    def test_at_high_threshold_fires(self, evaluator):
        """Alignment exactly at 0.8 should trigger MTFA002."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.8)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa002 = [i for i in items if i.code == "MTFA002"]
        assert len(mtfa002) == 1

    def test_below_high_threshold_no_info(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.7)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa002 = [i for i in items if i.code == "MTFA002"]
        assert mtfa002 == []

    def test_perfect_alignment(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=1.0)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa002 = [i for i in items if i.code == "MTFA002"]
        assert len(mtfa002) == 1


# ---------------------------------------------------------------------------
# MTFA001 and MTFA002 are mutually exclusive
# ---------------------------------------------------------------------------

class TestMTFA001AndMTFA002Exclusive:

    def test_low_alignment_no_mtfa002(self, evaluator):
        """Low alignment should NOT trigger MTFA002."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.4)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "MTFA001" in codes
        assert "MTFA002" not in codes

    def test_high_alignment_no_mtfa001(self, evaluator):
        """High alignment should NOT trigger MTFA001."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "MTFA001" not in codes
        assert "MTFA002" in codes

    def test_mid_alignment_neither(self, evaluator):
        """Alignment between thresholds triggers neither."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.7)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "MTFA001" not in codes
        assert "MTFA002" not in codes


# ---------------------------------------------------------------------------
# MTFA003: HTF transition risk
# ---------------------------------------------------------------------------

class TestMTFA003HTFTransitionRisk:

    def test_htf_high_transition_risk_warns(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "5Min": _regime("5Min"),
            "1Hour": _regime("1Hour", transition_risk=0.5),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert len(mtfa003) == 1
        assert "1Hour" in mtfa003[0].title

    def test_daily_high_transition_risk_warns(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "5Min": _regime("5Min"),
            "1Day": _regime("1Day", transition_risk=0.4),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert len(mtfa003) == 1
        assert "1Day" in mtfa003[0].title

    def test_both_htf_high_transition_risk(self, evaluator):
        """Both 1Hour and 1Day unstable → two MTFA003 items."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "5Min": _regime("5Min"),
            "1Hour": _regime("1Hour", transition_risk=0.5),
            "1Day": _regime("1Day", transition_risk=0.4),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert len(mtfa003) == 2

    def test_htf_low_transition_risk_no_warning(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "1Hour": _regime("1Hour", transition_risk=0.1),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert mtfa003 == []

    def test_htf_at_threshold_no_warning(self, evaluator):
        """Exactly at 0.3 should NOT trigger."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "1Hour": _regime("1Hour", transition_risk=0.3),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert mtfa003 == []

    def test_ltf_high_transition_risk_ignored(self, evaluator):
        """5Min and 15Min are not HTF timeframes — should not trigger MTFA003."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "5Min": _regime("5Min", transition_risk=0.9),
            "15Min": _regime("15Min", transition_risk=0.9),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert mtfa003 == []

    def test_htf_transition_risk_none_skips(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "1Hour": _regime("1Hour", transition_risk=None),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert mtfa003 == []

    def test_custom_htf_threshold(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {
            "1Hour": _regime("1Hour", transition_risk=0.25),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        config = EvaluatorConfig(thresholds={"htf_transition_risk_threshold": 0.2})
        items = evaluator.evaluate(intent, context, config=config)
        mtfa003 = [i for i in items if i.code == "MTFA003"]
        assert len(mtfa003) == 1


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

class TestMTFACombined:

    def test_low_alignment_plus_htf_risk(self, evaluator):
        """MTFA001 and MTFA003 can fire simultaneously."""
        intent = _make_intent()
        mtfa = MTFAContext(
            alignment_score=0.4,
            conflicts=["1Day: bearish (vs majority: bullish)"],
        )
        regimes = {
            "1Hour": _regime("1Hour", transition_risk=0.5),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "MTFA001" in codes
        assert "MTFA003" in codes
        assert "MTFA002" not in codes

    def test_high_alignment_plus_htf_risk(self, evaluator):
        """MTFA002 and MTFA003 can fire simultaneously."""
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=1.0)
        regimes = {
            "1Day": _regime("1Day", transition_risk=0.5),
        }
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "MTFA002" in codes
        assert "MTFA003" in codes
        assert "MTFA001" not in codes

    def test_severity_override_from_config(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.4)
        context = _make_context(mtfa=mtfa)

        config = EvaluatorConfig(
            severity_overrides={"MTFA001": Severity.CRITICAL}
        )
        items = evaluator.evaluate(intent, context, config=config)
        mtfa001 = [i for i in items if i.code == "MTFA001"]
        assert mtfa001[0].severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# Evidence checks
# ---------------------------------------------------------------------------

class TestMTFAEvidence:

    def test_mtfa001_evidence_has_score_and_threshold(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.4, conflicts=["x"])
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        mtfa001 = [i for i in items if i.code == "MTFA001"][0]
        ev = mtfa001.evidence[0]
        assert ev.metric_name == "mtfa_alignment_score"
        assert ev.value == 0.4
        assert ev.threshold == 0.6
        assert ev.comparison == ">="

    def test_mtfa003_evidence_has_timeframe_context(self, evaluator):
        intent = _make_intent()
        mtfa = MTFAContext(alignment_score=0.9)
        regimes = {"1Hour": _regime("1Hour", transition_risk=0.5)}
        context = _make_context(mtfa=mtfa, regimes=regimes)

        items = evaluator.evaluate(intent, context)
        mtfa003 = [i for i in items if i.code == "MTFA003"][0]
        ev = mtfa003.evidence[0]
        assert ev.metric_name == "htf_transition_risk"
        assert ev.value == 0.5
        assert ev.context["timeframe"] == "1Hour"
