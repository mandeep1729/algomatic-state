"""Unit tests for ProbeEngine with synthetic data."""

import numpy as np
import pandas as pd
import pytest

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.engine import ProbeEngine
from src.strats_prob.exits import RISK_PROFILES, RiskProfile
from src.strats_prob.strategy_def import ConditionFn, ProbeTradeResult, StrategyDef


def _make_strategy(
    entry_long=None,
    entry_short=None,
    exit_long=None,
    exit_short=None,
    direction="long_short",
    atr_stop_mult=2.0,
    atr_target_mult=None,
    trailing_atr_mult=None,
    time_stop_bars=None,
) -> StrategyDef:
    """Helper to create a minimal StrategyDef for testing."""
    return StrategyDef(
        id=999,
        name="test_strategy",
        display_name="Test Strategy",
        philosophy="Testing",
        category="test",
        tags=["test"],
        direction=direction,
        entry_long=entry_long or [],
        entry_short=entry_short or [],
        exit_long=exit_long or [],
        exit_short=exit_short or [],
        atr_stop_mult=atr_stop_mult,
        atr_target_mult=atr_target_mult,
        trailing_atr_mult=trailing_atr_mult,
        time_stop_bars=time_stop_bars,
    )


def _make_df(closes, atr=1.0, n_warmup=0) -> pd.DataFrame:
    """Create a minimal DataFrame from a list of close prices.

    Args:
        closes: List of close prices.
        atr: Constant ATR value.
        n_warmup: Number of extra warmup bars to prepend.
    """
    all_closes = [closes[0]] * n_warmup + list(closes)
    n = len(all_closes)
    index = pd.date_range("2024-06-03 09:30:00", periods=n, freq="1h")

    df = pd.DataFrame(
        {
            "open": all_closes,
            "high": [c + 0.2 for c in all_closes],
            "low": [c - 0.2 for c in all_closes],
            "close": all_closes,
            "volume": [10000] * n,
            "atr_14": [atr] * n,
        },
        index=index,
    )
    return df


class TestProbeEngineBasic:
    """Basic engine behavior tests."""

    def test_empty_df(self):
        """Engine returns empty list for empty DataFrame."""
        strat = _make_strategy()
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(pd.DataFrame())
        assert result == []

    def test_no_entry_conditions(self):
        """Engine returns empty list when no entry conditions defined."""
        strat = _make_strategy(entry_long=[], entry_short=[])
        df = _make_df([100, 101, 102, 103, 104])
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)
        assert result == []

    def test_always_true_entry_produces_trade(self):
        """Entry that always fires produces at least one trade (with stop exit)."""
        always_true: ConditionFn = lambda df, idx: True
        strat = _make_strategy(
            entry_long=[always_true],
            direction="long_only",
            atr_stop_mult=0.1,  # Very tight stop
        )
        # Prices go up then down to trigger stop
        df = _make_df([100, 101, 102, 103, 102, 101, 99, 98, 97, 96])
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)
        assert len(result) >= 1

    def test_open_trade_at_end_discarded(self):
        """Open trades at end of data are discarded."""
        always_true: ConditionFn = lambda df, idx: True
        strat = _make_strategy(
            entry_long=[always_true],
            direction="long_only",
            atr_stop_mult=None,
            atr_target_mult=None,
            trailing_atr_mult=None,
            time_stop_bars=None,
        )
        # Prices steadily rise; no exit trigger except signal exits (none defined)
        df = _make_df([100, 101, 102, 103, 104, 105])
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)
        # No mechanical exit, no signal exit => trade stays open => discarded
        assert result == []


class TestProbeEngineFillOnNextBar:
    """Tests for fill-on-next-bar entry semantics."""

    def test_entry_price_is_next_bar_open(self):
        """Entry price should be the open of the bar AFTER the signal."""
        # Signal fires at bar where close > 100, entry on next bar
        cond_entry: ConditionFn = lambda df, idx: float(df["close"].iloc[idx]) > 100

        strat = _make_strategy(
            entry_long=[cond_entry],
            direction="long_only",
            atr_stop_mult=0.05,  # Very tight stop to force exit
        )

        closes = [99, 99.5, 101, 102, 100, 98, 97]
        opens = [99, 99.5, 100.5, 101.5, 101, 99, 97.5]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": opens,
                "high": [c + 0.5 for c in closes],
                "low": [c - 0.5 for c in closes],
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) >= 1
        # Signal fires at bar 2 (close=101>100), entry at bar 3 open=101.5
        assert result[0].entry_price == 101.5


class TestProbeEngineExits:
    """Tests for different exit types."""

    def test_stop_loss_exit(self):
        """Stop loss fires when price drops below entry - stop_dist."""
        always_true: ConditionFn = lambda df, idx: idx == 0
        strat = _make_strategy(
            entry_long=[always_true],
            direction="long_only",
            atr_stop_mult=1.0,
            atr_target_mult=None,
            trailing_atr_mult=None,
        )

        # ATR=1.0, stop_dist=1.0. Entry at bar 1 open.
        # Price drops to trigger stop.
        closes = [100, 100, 99, 97, 96]
        opens = [100, 100.5, 99.5, 98, 96]
        lows = [99.5, 99, 98, 96, 95]
        highs = [101, 101, 100, 99, 97]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) == 1
        assert result[0].exit_reason == "stop_loss"
        # Entry at bar 1 open = 100.5, stop at entry - 1*ATR = 99.5
        assert result[0].entry_price == 100.5
        assert result[0].exit_price == pytest.approx(99.5, abs=0.01)

    def test_target_exit(self):
        """Target fires when price reaches entry + target_dist."""
        entry_cond: ConditionFn = lambda df, idx: idx == 0
        strat = _make_strategy(
            entry_long=[entry_cond],
            direction="long_only",
            atr_stop_mult=5.0,  # Wide stop
            atr_target_mult=2.0,
        )

        # Entry at bar 1, target at entry + 2*ATR
        closes = [100, 100.5, 101, 102, 103, 104]
        opens = [100, 100.2, 100.8, 101.5, 102.5, 103.5]
        highs = [101, 101, 102, 103, 103.5, 105]
        lows = [99, 100, 100.5, 101, 102, 103]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) == 1
        assert result[0].exit_reason == "target"
        # Entry at bar 1 open=100.2, target = 100.2 + 2*1.0 = 102.2
        assert result[0].exit_price == pytest.approx(102.2, abs=0.01)

    def test_time_stop_exit(self):
        """Time stop fires after N bars held."""
        entry_cond: ConditionFn = lambda df, idx: idx == 0
        strat = _make_strategy(
            entry_long=[entry_cond],
            direction="long_only",
            atr_stop_mult=None,
            atr_target_mult=None,
            trailing_atr_mult=None,
            time_stop_bars=3,
        )

        closes = [100, 100.1, 100.2, 100.3, 100.4, 100.5]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c + 0.1 for c in closes],
                "low": [c - 0.1 for c in closes],
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) == 1
        assert result[0].exit_reason == "time_stop"
        assert result[0].bars_held == 3

    def test_signal_exit(self):
        """Signal exit fires when exit condition is met."""
        entry_cond: ConditionFn = lambda df, idx: idx == 0
        exit_cond: ConditionFn = lambda df, idx: float(df["close"].iloc[idx]) > 102

        strat = _make_strategy(
            entry_long=[entry_cond],
            exit_long=[exit_cond],
            direction="long_only",
            atr_stop_mult=None,
        )

        closes = [100, 100.5, 101, 102, 103]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c + 0.2 for c in closes],
                "low": [c - 0.2 for c in closes],
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) == 1
        assert result[0].exit_reason == "signal_exit"
        # Signal exit uses close price
        assert result[0].exit_price == 103


class TestProbeEngineShort:
    """Tests for short positions."""

    def test_short_entry_and_stop(self):
        """Short entry with stop loss exit."""
        entry_cond: ConditionFn = lambda df, idx: idx == 0
        strat = _make_strategy(
            entry_short=[entry_cond],
            direction="short_only",
            atr_stop_mult=1.0,
        )

        # Price goes up to trigger short stop
        closes = [100, 100, 101, 102, 103]
        opens = [100, 99.8, 100.5, 101.5, 102.5]
        highs = [101, 101, 102, 103, 104]
        lows = [99, 99, 100, 101, 102]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) == 1
        assert result[0].direction == "short"
        assert result[0].exit_reason == "stop_loss"
        # Short entry at bar 1 open=99.8, stop at 99.8 + 1*1.0 = 100.8
        assert result[0].entry_price == 99.8
        assert result[0].exit_price == pytest.approx(100.8, abs=0.01)

    def test_short_pnl_calculation(self):
        """Short P&L is (entry - exit) / entry."""
        entry_cond: ConditionFn = lambda df, idx: idx == 0
        exit_cond: ConditionFn = lambda df, idx: idx >= 3

        strat = _make_strategy(
            entry_short=[entry_cond],
            exit_short=[exit_cond],
            direction="short_only",
            atr_stop_mult=None,
        )

        closes = [100, 100, 98, 96, 94]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c + 0.5 for c in closes],
                "low": [c - 0.5 for c in closes],
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        assert len(result) == 1
        # Entry at bar 1 open=100, exit at bar 3 close=96
        # Short PnL = (100 - 96) / 100 = 0.04
        assert result[0].pnl_pct == pytest.approx(0.04, abs=0.001)


class TestProbeEngineRiskProfiles:
    """Tests for risk profile scaling."""

    def test_low_risk_tighter_stop(self):
        """Low risk profile has tighter stop (0.75x)."""
        entry_cond: ConditionFn = lambda df, idx: idx == 0
        strat = _make_strategy(
            entry_long=[entry_cond],
            direction="long_only",
            atr_stop_mult=2.0,
        )

        # Price drops gradually
        closes = [100, 100, 99.5, 99, 98.5, 98, 97.5, 97]
        opens = [100, 100, 99.8, 99.3, 98.8, 98.3, 97.8, 97.3]
        lows = [99.5, 99.5, 99, 98.5, 98, 97.5, 97, 96.5]
        highs = [101, 101, 100, 99.5, 99, 98.5, 98, 97.5]
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine_low = ProbeEngine(strat, RISK_PROFILES["low"])
        engine_high = ProbeEngine(strat, RISK_PROFILES["high"])

        result_low = engine_low.run(df)
        result_high = engine_high.run(df)

        # Low risk should stop out sooner (tighter stop)
        assert len(result_low) >= 1
        if len(result_high) >= 1:
            # Low risk exits earlier
            assert result_low[0].bars_held <= result_high[0].bars_held


class TestProbeEngineMultipleTrades:
    """Tests for multiple trades in a single run."""

    def test_multiple_trades_generated(self):
        """Engine can generate multiple trades when entry fires after exit."""
        # Entry fires every time close > ema, exit via tight stop
        entry_cond: ConditionFn = lambda df, idx: float(df["close"].iloc[idx]) > 100
        strat = _make_strategy(
            entry_long=[entry_cond],
            direction="long_only",
            atr_stop_mult=0.3,  # Very tight stop
        )

        # Oscillating prices to generate multiple entries/exits
        closes = [99, 101, 102, 100, 99, 101, 102, 100, 99, 101, 102, 100, 99]
        opens = closes.copy()
        n = len(closes)
        index = pd.date_range("2024-06-03", periods=n, freq="1h")
        df = pd.DataFrame(
            {
                "open": opens,
                "high": [c + 0.5 for c in closes],
                "low": [c - 0.5 for c in closes],
                "close": closes,
                "volume": [10000] * n,
                "atr_14": [1.0] * n,
            },
            index=index,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        result = engine.run(df)

        # Should get at least 2 trades from the oscillating pattern
        assert len(result) >= 2


class TestProbeTradeResult:
    """Tests for ProbeTradeResult dataclass."""

    def test_trade_result_fields(self):
        """ProbeTradeResult has all expected fields."""
        import datetime
        result = ProbeTradeResult(
            entry_time=datetime.datetime(2024, 1, 1, 10, 0),
            exit_time=datetime.datetime(2024, 1, 1, 14, 0),
            entry_price=100.0,
            exit_price=102.0,
            direction="long",
            pnl_pct=0.02,
            bars_held=4,
            max_drawdown_pct=0.005,
            max_profit_pct=0.025,
            exit_reason="signal_exit",
        )

        assert result.pnl_pct == 0.02
        assert result.direction == "long"
        assert result.exit_reason == "signal_exit"
        assert result.bars_held == 4
