"""Tests for VolatilityLiquidityEvaluator."""

from datetime import datetime

import pandas as pd
import pytest

from src.evaluators.base import EvaluatorConfig
from src.evaluators.context import ContextPack
from src.evaluators.volatility_liquidity import VolatilityLiquidityEvaluator
from src.trade.evaluation import Severity
from src.trade.intent import TradeIntent, TradeDirection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evaluator():
    return VolatilityLiquidityEvaluator()


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


def _make_features(relvol_60=None, range_z_60=None, timeframe="5Min"):
    """Build a features dict with a single-row DataFrame."""
    data = {}
    if relvol_60 is not None:
        data["relvol_60"] = [relvol_60]
    if range_z_60 is not None:
        data["range_z_60"] = [range_z_60]
    if not data:
        return {}
    return {timeframe: pd.DataFrame(data)}


def _make_context(timeframe="5Min", features=None):
    return ContextPack(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        primary_timeframe=timeframe,
        features=features or {},
    )


# ---------------------------------------------------------------------------
# No data → empty results
# ---------------------------------------------------------------------------

class TestVolatilityLiquidityNoData:

    def test_no_features_returns_empty(self, evaluator):
        intent = _make_intent()
        context = _make_context()
        items = evaluator.evaluate(intent, context)
        assert items == []

    def test_missing_relvol_feature_skips_vl001(self, evaluator):
        intent = _make_intent()
        features = _make_features(range_z_60=1.0)
        context = _make_context(features=features)
        items = evaluator.evaluate(intent, context)
        vl001 = [i for i in items if i.code == "VL001"]
        assert vl001 == []

    def test_missing_range_z_feature_skips_vl002(self, evaluator):
        intent = _make_intent()
        features = _make_features(relvol_60=1.0)
        context = _make_context(features=features)
        items = evaluator.evaluate(intent, context)
        vl002 = [i for i in items if i.code == "VL002"]
        assert vl002 == []


# ---------------------------------------------------------------------------
# VL001: Low relative volume
# ---------------------------------------------------------------------------

class TestVL001RelativeVolume:

    def test_low_relvol_triggers(self, evaluator):
        intent = _make_intent()
        features = _make_features(relvol_60=0.3)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl001 = [i for i in items if i.code == "VL001"]
        assert len(vl001) == 1
        assert vl001[0].severity == Severity.WARNING
        assert vl001[0].evidence[0].value == 0.3

    def test_normal_relvol_no_trigger(self, evaluator):
        intent = _make_intent()
        features = _make_features(relvol_60=1.2)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl001 = [i for i in items if i.code == "VL001"]
        assert vl001 == []

    def test_relvol_at_threshold_no_trigger(self, evaluator):
        """Exactly at 0.5 → no trigger (>= comparison)."""
        intent = _make_intent()
        features = _make_features(relvol_60=0.5)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl001 = [i for i in items if i.code == "VL001"]
        assert vl001 == []

    def test_custom_relvol_threshold(self, evaluator):
        intent = _make_intent()
        features = _make_features(relvol_60=0.7)
        context = _make_context(features=features)

        # Default 0.5 → no trigger for 0.7
        items = evaluator.evaluate(intent, context)
        vl001 = [i for i in items if i.code == "VL001"]
        assert vl001 == []

        # Custom 0.8 → triggers for 0.7
        config = EvaluatorConfig(thresholds={"min_relative_volume": 0.8})
        items = evaluator.evaluate(intent, context, config=config)
        vl001 = [i for i in items if i.code == "VL001"]
        assert len(vl001) == 1


# ---------------------------------------------------------------------------
# VL002: Extended candle
# ---------------------------------------------------------------------------

class TestVL002ExtendedCandle:

    def test_high_zscore_triggers_warning(self, evaluator):
        intent = _make_intent()
        features = _make_features(range_z_60=2.5)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl002 = [i for i in items if i.code == "VL002"]
        assert len(vl002) == 1
        assert vl002[0].severity == Severity.WARNING

    def test_very_high_zscore_triggers_critical(self, evaluator):
        """Z-score > 3.0 → CRITICAL."""
        intent = _make_intent()
        features = _make_features(range_z_60=3.5)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl002 = [i for i in items if i.code == "VL002"]
        assert len(vl002) == 1
        assert vl002[0].severity == Severity.CRITICAL

    def test_normal_zscore_no_trigger(self, evaluator):
        intent = _make_intent()
        features = _make_features(range_z_60=1.0)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl002 = [i for i in items if i.code == "VL002"]
        assert vl002 == []

    def test_zscore_at_threshold_no_trigger(self, evaluator):
        """Exactly at 2.0 → no trigger (<= comparison)."""
        intent = _make_intent()
        features = _make_features(range_z_60=2.0)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        vl002 = [i for i in items if i.code == "VL002"]
        assert vl002 == []

    def test_custom_zscore_threshold(self, evaluator):
        intent = _make_intent()
        features = _make_features(range_z_60=1.5)
        context = _make_context(features=features)

        config = EvaluatorConfig(thresholds={"extended_candle_zscore": 1.0})
        items = evaluator.evaluate(intent, context, config=config)
        vl002 = [i for i in items if i.code == "VL002"]
        assert len(vl002) == 1


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

class TestVolatilityLiquidityCombined:

    def test_both_checks_fire(self, evaluator):
        intent = _make_intent()
        features = _make_features(relvol_60=0.2, range_z_60=2.5)
        context = _make_context(features=features)

        items = evaluator.evaluate(intent, context)
        codes = {i.code for i in items}
        assert "VL001" in codes
        assert "VL002" in codes

    def test_severity_override(self, evaluator):
        intent = _make_intent()
        features = _make_features(relvol_60=0.2)
        context = _make_context(features=features)

        config = EvaluatorConfig(
            severity_overrides={"VL001": Severity.BLOCKER}
        )
        items = evaluator.evaluate(intent, context, config=config)
        vl001 = [i for i in items if i.code == "VL001"]
        assert vl001[0].severity == Severity.BLOCKER
