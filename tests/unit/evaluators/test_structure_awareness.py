"""Tests for StructureAwarenessEvaluator."""

from datetime import datetime

import pandas as pd
import pytest

from src.evaluators.base import EvaluatorConfig
from src.evaluators.context import ContextPack, KeyLevels, MTFAContext
from src.evaluators.structure_awareness import StructureAwarenessEvaluator
from src.trade.evaluation import Severity
from src.trade.intent import TradeIntent, TradeDirection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evaluator():
    return StructureAwarenessEvaluator()


def _make_intent(direction="long", entry_price=150.0, symbol="AAPL", timeframe="5Min"):
    if direction == "long":
        return TradeIntent(
            user_id=1, symbol=symbol, direction=TradeDirection.LONG,
            timeframe=timeframe, entry_price=entry_price,
            stop_loss=entry_price - 2.0, profit_target=entry_price + 4.0,
        )
    return TradeIntent(
        user_id=1, symbol=symbol, direction=TradeDirection.SHORT,
        timeframe=timeframe, entry_price=entry_price,
        stop_loss=entry_price + 2.0, profit_target=entry_price - 4.0,
    )


def _make_context(
    timeframe="5Min",
    key_levels=None,
    atr=None,
    mtfa=None,
):
    return ContextPack(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        primary_timeframe=timeframe,
        key_levels=key_levels,
        atr=atr,
        mtfa=mtfa,
    )


# ---------------------------------------------------------------------------
# No data → empty results
# ---------------------------------------------------------------------------

class TestStructureAwarenessNoData:

    def test_no_key_levels_returns_empty(self, evaluator):
        intent = _make_intent()
        context = _make_context()
        items = evaluator.evaluate(intent, context)
        assert items == []

    def test_no_mtfa_no_sa004(self, evaluator):
        intent = _make_intent()
        context = _make_context()
        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert sa004 == []


# ---------------------------------------------------------------------------
# SA001: Buying into resistance
# ---------------------------------------------------------------------------

class TestSA001BuyingIntoResistance:

    def test_long_near_r1_triggers(self, evaluator):
        """Entry within 0.5% of R1 triggers SA001."""
        intent = _make_intent("long", entry_price=150.0)
        key_levels = KeyLevels(r1=150.5)  # 0.33% away
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa001 = [i for i in items if i.code == "SA001"]
        assert len(sa001) == 1
        assert sa001[0].severity == Severity.WARNING

    def test_long_very_close_to_resistance_is_critical(self, evaluator):
        """Entry within 0.3% of resistance → CRITICAL."""
        intent = _make_intent("long", entry_price=150.0)
        key_levels = KeyLevels(r1=150.3)  # 0.2% away
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa001 = [i for i in items if i.code == "SA001"]
        assert len(sa001) == 1
        assert sa001[0].severity == Severity.CRITICAL

    def test_long_far_from_resistance_no_trigger(self, evaluator):
        """Entry far from resistance → no SA001."""
        intent = _make_intent("long", entry_price=150.0)
        key_levels = KeyLevels(r1=155.0)  # 3.3% away
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa001 = [i for i in items if i.code == "SA001"]
        assert sa001 == []

    def test_long_checks_multiple_resistance_levels(self, evaluator):
        """Should check r1, r2, prior_day_high, rolling_high_20."""
        intent = _make_intent("long", entry_price=150.0)
        # All levels far except rolling_high_20
        key_levels = KeyLevels(
            r1=160.0, r2=170.0,
            prior_day_high=160.0, rolling_high_20=150.3,
        )
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa001 = [i for i in items if i.code == "SA001"]
        assert len(sa001) == 1
        assert "rolling_high_20" in sa001[0].message

    def test_short_does_not_trigger_sa001(self, evaluator):
        """SA001 only applies to LONG trades."""
        intent = _make_intent("short", entry_price=150.0)
        key_levels = KeyLevels(r1=150.1)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa001 = [i for i in items if i.code == "SA001"]
        assert sa001 == []


# ---------------------------------------------------------------------------
# SA002: Shorting into support
# ---------------------------------------------------------------------------

class TestSA002ShortingIntoSupport:

    def test_short_near_s1_triggers(self, evaluator):
        intent = _make_intent("short", entry_price=150.0)
        key_levels = KeyLevels(s1=149.5)  # 0.33% away
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa002 = [i for i in items if i.code == "SA002"]
        assert len(sa002) == 1
        assert sa002[0].severity == Severity.WARNING

    def test_short_very_close_to_support_is_critical(self, evaluator):
        intent = _make_intent("short", entry_price=150.0)
        key_levels = KeyLevels(s1=149.7)  # 0.2% away
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa002 = [i for i in items if i.code == "SA002"]
        assert len(sa002) == 1
        assert sa002[0].severity == Severity.CRITICAL

    def test_short_far_from_support_no_trigger(self, evaluator):
        intent = _make_intent("short", entry_price=150.0)
        key_levels = KeyLevels(s1=140.0)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa002 = [i for i in items if i.code == "SA002"]
        assert sa002 == []

    def test_short_checks_rolling_low(self, evaluator):
        intent = _make_intent("short", entry_price=150.0)
        key_levels = KeyLevels(
            s1=140.0, s2=135.0,
            prior_day_low=140.0, rolling_low_20=150.2,
        )
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa002 = [i for i in items if i.code == "SA002"]
        assert len(sa002) == 1
        assert "rolling_low_20" in sa002[0].message

    def test_long_does_not_trigger_sa002(self, evaluator):
        intent = _make_intent("long", entry_price=150.0)
        key_levels = KeyLevels(s1=150.1)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sa002 = [i for i in items if i.code == "SA002"]
        assert sa002 == []


# ---------------------------------------------------------------------------
# SA003: Entry far from VWAP
# ---------------------------------------------------------------------------

class TestSA003VWAPDistance:

    def test_entry_far_from_vwap_triggers(self, evaluator):
        intent = _make_intent("long", entry_price=155.0)
        key_levels = KeyLevels(vwap=150.0)
        # distance = 5.0, ATR = 2.0 → 2.5 ATR > 2.0 threshold
        context = _make_context(key_levels=key_levels, atr=2.0)

        items = evaluator.evaluate(intent, context)
        sa003 = [i for i in items if i.code == "SA003"]
        assert len(sa003) == 1
        assert sa003[0].severity == Severity.WARNING

    def test_entry_close_to_vwap_no_trigger(self, evaluator):
        intent = _make_intent("long", entry_price=151.0)
        key_levels = KeyLevels(vwap=150.0)
        # distance = 1.0, ATR = 2.0 → 0.5 ATR < 2.0 threshold
        context = _make_context(key_levels=key_levels, atr=2.0)

        items = evaluator.evaluate(intent, context)
        sa003 = [i for i in items if i.code == "SA003"]
        assert sa003 == []

    def test_no_vwap_skips(self, evaluator):
        intent = _make_intent("long")
        key_levels = KeyLevels()  # No VWAP
        context = _make_context(key_levels=key_levels, atr=2.0)

        items = evaluator.evaluate(intent, context)
        sa003 = [i for i in items if i.code == "SA003"]
        assert sa003 == []

    def test_no_atr_skips(self, evaluator):
        intent = _make_intent("long")
        key_levels = KeyLevels(vwap=150.0)
        context = _make_context(key_levels=key_levels, atr=None)

        items = evaluator.evaluate(intent, context)
        sa003 = [i for i in items if i.code == "SA003"]
        assert sa003 == []

    def test_custom_vwap_threshold(self, evaluator):
        intent = _make_intent("long", entry_price=153.0)
        key_levels = KeyLevels(vwap=150.0)
        # distance = 3.0, ATR = 2.0 → 1.5 ATR
        # Default 2.0 would not trigger, but custom 1.0 will
        context = _make_context(key_levels=key_levels, atr=2.0)

        config = EvaluatorConfig(thresholds={"vwap_atr_max": 1.0})
        items = evaluator.evaluate(intent, context, config=config)
        sa003 = [i for i in items if i.code == "SA003"]
        assert len(sa003) == 1

    def test_short_far_from_vwap_also_triggers(self, evaluator):
        intent = _make_intent("short", entry_price=145.0)
        key_levels = KeyLevels(vwap=150.0)
        # distance = 5.0, ATR = 2.0 → 2.5 ATR
        context = _make_context(key_levels=key_levels, atr=2.0)

        items = evaluator.evaluate(intent, context)
        sa003 = [i for i in items if i.code == "SA003"]
        assert len(sa003) == 1


# ---------------------------------------------------------------------------
# SA004: Against HTF trend
# ---------------------------------------------------------------------------

class TestSA004HTFTrend:

    def test_long_vs_bearish_htf_triggers(self, evaluator):
        intent = _make_intent("long")
        mtfa = MTFAContext(htf_trend="bearish")
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert len(sa004) == 1
        assert sa004[0].severity == Severity.WARNING

    def test_short_vs_bullish_htf_triggers(self, evaluator):
        intent = _make_intent("short")
        mtfa = MTFAContext(htf_trend="up_trending")
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert len(sa004) == 1

    def test_long_vs_bullish_htf_no_trigger(self, evaluator):
        intent = _make_intent("long")
        mtfa = MTFAContext(htf_trend="bullish")
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert sa004 == []

    def test_short_vs_bearish_htf_no_trigger(self, evaluator):
        intent = _make_intent("short")
        mtfa = MTFAContext(htf_trend="down_trending")
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert sa004 == []

    def test_neutral_htf_no_trigger(self, evaluator):
        intent = _make_intent("long")
        mtfa = MTFAContext(htf_trend="ranging")
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert sa004 == []

    def test_no_mtfa_skips(self, evaluator):
        intent = _make_intent("long")
        context = _make_context(mtfa=None)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert sa004 == []

    def test_mtfa_with_none_trend_skips(self, evaluator):
        intent = _make_intent("long")
        mtfa = MTFAContext(htf_trend=None)
        context = _make_context(mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        sa004 = [i for i in items if i.code == "SA004"]
        assert sa004 == []


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------

class TestStructureAwarenessCustomConfig:

    def test_custom_level_proximity(self, evaluator):
        """Tighter proximity threshold catches more."""
        intent = _make_intent("long", entry_price=150.0)
        key_levels = KeyLevels(r1=151.2)  # 0.8% away — default won't trigger
        context = _make_context(key_levels=key_levels)

        # Default 0.5% → no trigger
        items = evaluator.evaluate(intent, context)
        sa001 = [i for i in items if i.code == "SA001"]
        assert sa001 == []

        # Custom 1.0% → triggers
        config = EvaluatorConfig(thresholds={"level_proximity_pct": 1.0})
        items = evaluator.evaluate(intent, context, config=config)
        sa001 = [i for i in items if i.code == "SA001"]
        assert len(sa001) == 1

    def test_severity_override(self, evaluator):
        intent = _make_intent("long", entry_price=150.0)
        key_levels = KeyLevels(r1=150.5)
        context = _make_context(key_levels=key_levels)

        config = EvaluatorConfig(
            severity_overrides={"SA001": Severity.BLOCKER}
        )
        items = evaluator.evaluate(intent, context, config=config)
        sa001 = [i for i in items if i.code == "SA001"]
        assert sa001[0].severity == Severity.BLOCKER


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

class TestStructureAwarenessCombined:

    def test_multiple_checks_fire(self, evaluator):
        """SA001 + SA003 + SA004 can fire together."""
        intent = _make_intent("long", entry_price=155.0)
        key_levels = KeyLevels(r1=155.3, vwap=150.0)
        mtfa = MTFAContext(htf_trend="bearish")
        context = _make_context(key_levels=key_levels, atr=2.0, mtfa=mtfa)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "SA001" in codes
        assert "SA003" in codes
        assert "SA004" in codes
