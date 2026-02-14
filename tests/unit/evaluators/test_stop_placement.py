"""Tests for StopPlacementEvaluator."""

from datetime import datetime

import pandas as pd
import pytest

from src.evaluators.base import EvaluatorConfig
from src.evaluators.context import ContextPack, KeyLevels
from src.evaluators.stop_placement import StopPlacementEvaluator
from src.trade.evaluation import Severity
from src.trade.intent import TradeIntent, TradeDirection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evaluator():
    return StopPlacementEvaluator()


def _make_intent(
    direction="long",
    entry_price=150.0,
    stop_loss=None,
    symbol="AAPL",
    timeframe="5Min",
):
    if direction == "long":
        sl = stop_loss if stop_loss is not None else entry_price - 2.0
        return TradeIntent(
            user_id=1, symbol=symbol, direction=TradeDirection.LONG,
            timeframe=timeframe, entry_price=entry_price,
            stop_loss=sl, profit_target=entry_price + 4.0,
        )
    sl = stop_loss if stop_loss is not None else entry_price + 2.0
    return TradeIntent(
        user_id=1, symbol=symbol, direction=TradeDirection.SHORT,
        timeframe=timeframe, entry_price=entry_price,
        stop_loss=sl, profit_target=entry_price - 4.0,
    )


def _make_bars(low=147.0, high=153.0, timeframe="5Min"):
    """Create a minimal bars DataFrame with one row."""
    df = pd.DataFrame({
        "open": [149.0],
        "high": [high],
        "low": [low],
        "close": [150.0],
        "volume": [10000],
    })
    return {timeframe: df}


def _make_context(
    timeframe="5Min",
    key_levels=None,
    atr=None,
    bars=None,
):
    return ContextPack(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        primary_timeframe=timeframe,
        key_levels=key_levels,
        atr=atr,
        bars=bars or {},
    )


# ---------------------------------------------------------------------------
# No data → empty results
# ---------------------------------------------------------------------------

class TestStopPlacementNoData:

    def test_no_data_returns_empty(self, evaluator):
        intent = _make_intent()
        context = _make_context()
        items = evaluator.evaluate(intent, context)
        assert items == []

    def test_no_key_levels_skips_sp001(self, evaluator):
        intent = _make_intent()
        context = _make_context(atr=2.0, bars=_make_bars())
        items = evaluator.evaluate(intent, context)
        sp001 = [i for i in items if i.code == "SP001"]
        assert sp001 == []

    def test_no_atr_skips_sp002(self, evaluator):
        intent = _make_intent()
        context = _make_context(bars=_make_bars())
        items = evaluator.evaluate(intent, context)
        sp002 = [i for i in items if i.code == "SP002"]
        assert sp002 == []

    def test_no_bars_skips_sp003(self, evaluator):
        intent = _make_intent()
        context = _make_context(atr=2.0)
        items = evaluator.evaluate(intent, context)
        sp003 = [i for i in items if i.code == "SP003"]
        assert sp003 == []


# ---------------------------------------------------------------------------
# SP001: Stop at obvious liquidity level
# ---------------------------------------------------------------------------

class TestSP001LiquidityLevel:

    def test_long_stop_near_prior_day_low_triggers(self, evaluator):
        """Long stop within 0.3% of prior_day_low → SP001."""
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        key_levels = KeyLevels(prior_day_low=148.1)  # 0.07% from stop
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sp001 = [i for i in items if i.code == "SP001"]
        assert len(sp001) == 1
        assert sp001[0].severity == Severity.WARNING
        assert "prior_day_low" in sp001[0].message

    def test_long_stop_near_rolling_low_triggers(self, evaluator):
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        key_levels = KeyLevels(rolling_low_20=148.05)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sp001 = [i for i in items if i.code == "SP001"]
        assert len(sp001) == 1
        assert "rolling_low_20" in sp001[0].message

    def test_short_stop_near_prior_day_high_triggers(self, evaluator):
        intent = _make_intent("short", entry_price=150.0, stop_loss=152.0)
        key_levels = KeyLevels(prior_day_high=152.1)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sp001 = [i for i in items if i.code == "SP001"]
        assert len(sp001) == 1
        assert "prior_day_high" in sp001[0].message

    def test_short_stop_near_rolling_high_triggers(self, evaluator):
        intent = _make_intent("short", entry_price=150.0, stop_loss=152.0)
        key_levels = KeyLevels(rolling_high_20=151.95)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sp001 = [i for i in items if i.code == "SP001"]
        assert len(sp001) == 1

    def test_stop_far_from_levels_no_trigger(self, evaluator):
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        key_levels = KeyLevels(prior_day_low=145.0, rolling_low_20=144.0)
        context = _make_context(key_levels=key_levels)

        items = evaluator.evaluate(intent, context)
        sp001 = [i for i in items if i.code == "SP001"]
        assert sp001 == []


# ---------------------------------------------------------------------------
# SP002: Stop too tight for recent range
# ---------------------------------------------------------------------------

class TestSP002StopRange:

    def test_tight_stop_triggers(self, evaluator):
        """Stop distance < 0.5x ATR → SP002."""
        # entry=150, stop=149.5 → distance=0.5, ATR=2.0 → 0.25x
        intent = _make_intent("long", entry_price=150.0, stop_loss=149.5)
        context = _make_context(atr=2.0)

        items = evaluator.evaluate(intent, context)
        sp002 = [i for i in items if i.code == "SP002"]
        assert len(sp002) == 1
        assert sp002[0].severity == Severity.WARNING

    def test_adequate_stop_no_trigger(self, evaluator):
        """Stop distance >= 0.5x ATR → no trigger."""
        # entry=150, stop=148 → distance=2.0, ATR=2.0 → 1.0x
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        context = _make_context(atr=2.0)

        items = evaluator.evaluate(intent, context)
        sp002 = [i for i in items if i.code == "SP002"]
        assert sp002 == []

    def test_stop_at_threshold_no_trigger(self, evaluator):
        """Exactly at 0.5x → no trigger (>= comparison)."""
        # entry=150, stop=149.0 → distance=1.0, ATR=2.0 → 0.5x
        intent = _make_intent("long", entry_price=150.0, stop_loss=149.0)
        context = _make_context(atr=2.0)

        items = evaluator.evaluate(intent, context)
        sp002 = [i for i in items if i.code == "SP002"]
        assert sp002 == []

    def test_short_tight_stop_triggers(self, evaluator):
        # entry=150, stop=150.5 → distance=0.5, ATR=2.0 → 0.25x
        intent = _make_intent("short", entry_price=150.0, stop_loss=150.5)
        context = _make_context(atr=2.0)

        items = evaluator.evaluate(intent, context)
        sp002 = [i for i in items if i.code == "SP002"]
        assert len(sp002) == 1

    def test_custom_range_multiple(self, evaluator):
        # entry=150, stop=148 → distance=2.0, ATR=2.0 → 1.0x
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        context = _make_context(atr=2.0)

        # Default 0.5 → no trigger for 1.0x
        items = evaluator.evaluate(intent, context)
        sp002 = [i for i in items if i.code == "SP002"]
        assert sp002 == []

        # Custom 1.5 → triggers for 1.0x
        config = EvaluatorConfig(thresholds={"min_stop_range_multiple": 1.5})
        items = evaluator.evaluate(intent, context, config=config)
        sp002 = [i for i in items if i.code == "SP002"]
        assert len(sp002) == 1


# ---------------------------------------------------------------------------
# SP003: Stop at last candle extremum
# ---------------------------------------------------------------------------

class TestSP003LastCandle:

    def test_long_stop_at_last_bar_low_triggers(self, evaluator):
        """Long stop within 0.2% of last bar low → SP003."""
        # stop=148.0, last bar low=148.1 → 0.07%
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        bars = _make_bars(low=148.1)
        context = _make_context(bars=bars)

        items = evaluator.evaluate(intent, context)
        sp003 = [i for i in items if i.code == "SP003"]
        assert len(sp003) == 1
        assert sp003[0].severity == Severity.INFO
        assert "last bar low" in sp003[0].message

    def test_short_stop_at_last_bar_high_triggers(self, evaluator):
        # stop=152.0, last bar high=151.9 → 0.07%
        intent = _make_intent("short", entry_price=150.0, stop_loss=152.0)
        bars = _make_bars(high=151.9)
        context = _make_context(bars=bars)

        items = evaluator.evaluate(intent, context)
        sp003 = [i for i in items if i.code == "SP003"]
        assert len(sp003) == 1
        assert "last bar high" in sp003[0].message

    def test_stop_far_from_last_candle_no_trigger(self, evaluator):
        # stop=148.0, last bar low=145.0 → 2.07%
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        bars = _make_bars(low=145.0)
        context = _make_context(bars=bars)

        items = evaluator.evaluate(intent, context)
        sp003 = [i for i in items if i.code == "SP003"]
        assert sp003 == []

    def test_custom_candle_proximity(self, evaluator):
        # stop=148.0, last bar low=147.0 → 0.68%
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        bars = _make_bars(low=147.0)
        context = _make_context(bars=bars)

        # Default 0.2% → no trigger for 0.68%
        items = evaluator.evaluate(intent, context)
        sp003 = [i for i in items if i.code == "SP003"]
        assert sp003 == []

        # Custom 1.0% → triggers
        config = EvaluatorConfig(thresholds={"last_candle_proximity_pct": 1.0})
        items = evaluator.evaluate(intent, context, config=config)
        sp003 = [i for i in items if i.code == "SP003"]
        assert len(sp003) == 1


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

class TestStopPlacementCombined:

    def test_all_three_fire(self, evaluator):
        """SP001 + SP002 + SP003 can fire together."""
        # entry=150, stop=148.0
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        key_levels = KeyLevels(prior_day_low=148.05)  # SP001
        bars = _make_bars(low=148.1)  # SP003
        # ATR=5.0, distance=2.0 → 0.4x < 0.5 → SP002
        context = _make_context(
            key_levels=key_levels, atr=5.0, bars=bars,
        )

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "SP001" in codes
        assert "SP002" in codes
        assert "SP003" in codes

    def test_severity_override(self, evaluator):
        intent = _make_intent("long", entry_price=150.0, stop_loss=148.0)
        key_levels = KeyLevels(prior_day_low=148.05)
        context = _make_context(key_levels=key_levels)

        config = EvaluatorConfig(
            severity_overrides={"SP001": Severity.CRITICAL}
        )
        items = evaluator.evaluate(intent, context, config=config)
        sp001 = [i for i in items if i.code == "SP001"]
        assert sp001[0].severity == Severity.CRITICAL
