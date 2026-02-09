"""Unit tests for ProbeStrategyTrade model, justification generation, and trade mapping."""

import datetime
from dataclasses import field

import numpy as np
import pandas as pd
import pytest

from src.strats_prob.engine import ProbeEngine
from src.strats_prob.exits import ExitManager, RiskProfile, RISK_PROFILES
from src.strats_prob.strategy_def import ConditionFn, ProbeTradeResult, StrategyDef


def _make_trade(
    entry_time: datetime.datetime,
    direction: str = "long",
    pnl_pct: float = 0.01,
    entry_price: float = 100.0,
    bars_held: int = 5,
    entry_justification: str | None = None,
    exit_justification: str | None = None,
) -> ProbeTradeResult:
    """Helper to create a ProbeTradeResult for testing."""
    exit_price = entry_price * (1 + pnl_pct) if direction == "long" else entry_price * (1 - pnl_pct)
    return ProbeTradeResult(
        entry_time=entry_time,
        exit_time=entry_time + datetime.timedelta(hours=bars_held),
        entry_price=entry_price,
        exit_price=exit_price,
        direction=direction,
        pnl_pct=pnl_pct,
        bars_held=bars_held,
        max_drawdown_pct=0.005,
        max_profit_pct=0.015,
        pnl_std=0.002,
        exit_reason="signal_exit",
        entry_justification=entry_justification,
        exit_justification=exit_justification,
    )


class TestProbeTradeResultJustification:
    """Tests for justification fields on ProbeTradeResult."""

    def test_justification_fields_default_none(self):
        """Justification fields default to None when not provided."""
        trade = ProbeTradeResult(
            entry_time=datetime.datetime(2024, 6, 3, 10, 0),
            exit_time=datetime.datetime(2024, 6, 3, 15, 0),
            entry_price=100.0,
            exit_price=101.0,
            direction="long",
            pnl_pct=0.01,
            bars_held=5,
            max_drawdown_pct=0.005,
            max_profit_pct=0.015,
            pnl_std=0.0,
            exit_reason="signal_exit",
        )
        assert trade.entry_justification is None
        assert trade.exit_justification is None

    def test_justification_fields_populated(self):
        """Justification fields can be set."""
        trade = _make_trade(
            entry_time=datetime.datetime(2024, 6, 3, 10, 0),
            entry_justification="EMA20 crossed above EMA50",
            exit_justification="ATR stop hit",
        )
        assert trade.entry_justification == "EMA20 crossed above EMA50"
        assert trade.exit_justification == "ATR stop hit"


class TestEntryJustification:
    """Tests for ProbeEngine._build_entry_justification."""

    def _make_strategy(self, required_indicators: list[str] | None = None) -> StrategyDef:
        """Create a minimal strategy for testing justification."""
        return StrategyDef(
            id=1,
            name="test_strategy",
            display_name="Test Strategy",
            philosophy="For testing",
            category="trend",
            tags=["test"],
            direction="long_short",
            entry_long=[lambda df, i: True],
            entry_short=[],
            required_indicators=required_indicators or ["ema_20", "ema_50"],
        )

    def _make_df(self, n_bars: int = 10) -> pd.DataFrame:
        """Create a minimal DataFrame for justification testing."""
        base_date = pd.Timestamp("2024-06-03 09:30:00")
        index = pd.date_range(start=base_date, periods=n_bars, freq="1h")
        df = pd.DataFrame({
            "open": np.full(n_bars, 100.0),
            "high": np.full(n_bars, 101.0),
            "low": np.full(n_bars, 99.0),
            "close": np.full(n_bars, 100.5),
            "volume": np.full(n_bars, 10000),
            "atr_14": np.full(n_bars, 0.5),
            "ema_20": np.full(n_bars, 100.2),
            "ema_50": np.full(n_bars, 99.8),
        }, index=index)
        return df

    def test_entry_justification_contains_strategy_name(self):
        """Entry justification includes the strategy display name."""
        strat = self._make_strategy()
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        df = self._make_df()

        result = engine._build_entry_justification("long", 100.0, 0.5, df, 5)
        assert "Test Strategy" in result
        assert "long entry" in result

    def test_entry_justification_contains_price_and_atr(self):
        """Entry justification includes entry price and ATR value."""
        strat = self._make_strategy()
        engine = ProbeEngine(strat, RISK_PROFILES["high"])
        df = self._make_df()

        result = engine._build_entry_justification("short", 99.5, 0.75, df, 3)
        assert "99.5000" in result
        assert "ATR=0.7500" in result
        assert "risk=high" in result

    def test_entry_justification_includes_indicator_values(self):
        """Entry justification appends indicator snapshots."""
        strat = self._make_strategy(required_indicators=["ema_20", "ema_50"])
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        df = self._make_df()

        result = engine._build_entry_justification("long", 100.0, 0.5, df, 5)
        assert "ema_20=100.2000" in result
        assert "ema_50=99.8000" in result

    def test_entry_justification_handles_missing_indicator(self):
        """Entry justification gracefully skips missing indicator columns."""
        strat = self._make_strategy(required_indicators=["ema_20", "nonexistent_col"])
        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        df = self._make_df()

        result = engine._build_entry_justification("long", 100.0, 0.5, df, 5)
        assert "ema_20=100.2000" in result
        assert "nonexistent_col" not in result


class TestExitJustification:
    """Tests for ProbeEngine._build_exit_justification."""

    def _make_exit_manager(
        self,
        entry_price: float = 100.0,
        direction: str = "long",
        atr: float = 0.5,
    ) -> ExitManager:
        """Create an ExitManager for testing."""
        return ExitManager(
            entry_price=entry_price,
            direction=direction,
            atr_at_entry=atr,
            atr_stop_mult=2.0,
            atr_target_mult=3.0,
            trailing_atr_mult=2.0,
            time_stop_bars=20,
            risk_profile=RISK_PROFILES["medium"],
        )

    def test_stop_loss_justification(self):
        """Stop loss exit includes stop distance and ATR multiplier."""
        em = self._make_exit_manager()
        result = ProbeEngine._build_exit_justification(
            "stop_loss", "long", 100.0, 99.0, em, 99.0,
        )
        assert "stop_loss" in result
        assert "stop distance" in result
        assert "2.0x ATR" in result

    def test_target_justification(self):
        """Target exit includes target distance and ATR multiplier."""
        em = self._make_exit_manager()
        result = ProbeEngine._build_exit_justification(
            "target", "long", 100.0, 101.5, em, 101.5,
        )
        assert "target" in result
        assert "target distance" in result
        assert "3.0x ATR" in result

    def test_trailing_stop_justification(self):
        """Trailing stop exit includes the trailing stop level."""
        em = self._make_exit_manager()
        # Simulate trailing stop being set
        em._trailing_stop = 100.8
        result = ProbeEngine._build_exit_justification(
            "trailing_stop", "long", 100.0, 100.8, em, 100.5,
        )
        assert "trailing_stop" in result
        assert "trailing stop at 100.8000" in result

    def test_time_stop_justification(self):
        """Time stop exit includes bars held and limit."""
        em = self._make_exit_manager()
        em.bars_held = 20
        result = ProbeEngine._build_exit_justification(
            "time_stop", "long", 100.0, 100.5, em, 100.5,
        )
        assert "time_stop" in result
        assert "20 bars" in result
        assert "limit=20" in result

    def test_signal_exit_justification(self):
        """Signal exit includes the close price."""
        em = self._make_exit_manager()
        result = ProbeEngine._build_exit_justification(
            "signal_exit", "long", 100.0, 101.0, em, 101.0,
        )
        assert "signal_exit" in result
        assert "signal-based exit" in result
        assert "close=101.0000" in result

    def test_pnl_included_in_justification(self):
        """Exit justification includes P&L percentage."""
        em = self._make_exit_manager()
        result = ProbeEngine._build_exit_justification(
            "stop_loss", "long", 100.0, 99.0, em, 99.0,
        )
        assert "pnl=" in result
        assert "exit_price=99.0000" in result

    def test_short_exit_pnl_sign(self):
        """Short exit P&L is computed correctly in justification."""
        em = self._make_exit_manager(direction="short")
        # Short entry at 100, exit at 101 = -1% loss
        result = ProbeEngine._build_exit_justification(
            "stop_loss", "short", 100.0, 101.0, em, 101.0,
        )
        assert "pnl=-1.00%" in result


class TestEngineJustificationIntegration:
    """Integration test that engine populates justification fields on trades."""

    def test_engine_populates_justifications(self):
        """ProbeEngine.run() fills entry/exit justification on trade results."""
        n_bars = 20
        base_date = pd.Timestamp("2024-06-03 09:30:00")
        index = pd.date_range(start=base_date, periods=n_bars, freq="1h")

        df = pd.DataFrame({
            "open": np.full(n_bars, 100.0),
            "high": np.full(n_bars, 101.0),
            "low": np.full(n_bars, 99.0),
            "close": np.full(n_bars, 100.0),
            "volume": np.full(n_bars, 10000),
            "atr_14": np.full(n_bars, 0.5),
            "ema_20": np.full(n_bars, 100.2),
        }, index=index)

        # Strategy that enters long on bar 2 and exits via time stop
        strat = StrategyDef(
            id=99,
            name="test_justification",
            display_name="Justification Test",
            philosophy="Test",
            category="trend",
            tags=["test"],
            direction="long_only",
            entry_long=[lambda df, i: i == 2],
            entry_short=[],
            atr_stop_mult=None,
            atr_target_mult=None,
            trailing_atr_mult=None,
            time_stop_bars=5,
            required_indicators=["ema_20"],
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        trades = engine.run(df)

        assert len(trades) >= 1
        trade = trades[0]

        assert trade.entry_justification is not None
        assert "Justification Test" in trade.entry_justification
        assert "long entry" in trade.entry_justification

        assert trade.exit_justification is not None
        assert "time_stop" in trade.exit_justification


class TestTradeToDbMapping:
    """Tests for mapping ProbeTradeResult to DB dict format used by runner."""

    def test_trade_maps_to_db_dict(self):
        """A ProbeTradeResult can be mapped to a dict suitable for bulk_insert_trades."""
        trade = _make_trade(
            entry_time=datetime.datetime(2024, 6, 3, 10, 0),
            direction="long",
            pnl_pct=0.02,
            entry_price=100.0,
            bars_held=8,
            entry_justification="EMA cross entry at 100.0",
            exit_justification="Stop loss at 98.0",
        )

        # Simulate the mapping logic from runner._store_trades
        pnl_currency = trade.pnl_pct * trade.entry_price
        trade_dict = {
            "strategy_probe_result_id": 42,
            "ticker": "AAPL",
            "open_timestamp": trade.entry_time,
            "close_timestamp": trade.exit_time,
            "direction": trade.direction[:5],
            "open_justification": trade.entry_justification,
            "close_justification": trade.exit_justification,
            "pnl": pnl_currency,
            "pnl_pct": trade.pnl_pct,
            "bars_held": trade.bars_held,
            "max_drawdown": trade.max_drawdown_pct,
            "max_profit": trade.max_profit_pct,
            "pnl_std": trade.pnl_std,
        }

        assert trade_dict["strategy_probe_result_id"] == 42
        assert trade_dict["ticker"] == "AAPL"
        assert trade_dict["direction"] == "long"
        assert trade_dict["pnl"] == pytest.approx(2.0)  # 2% of 100.0
        assert trade_dict["pnl_pct"] == pytest.approx(0.02)
        assert trade_dict["bars_held"] == 8
        assert trade_dict["open_justification"] == "EMA cross entry at 100.0"
        assert trade_dict["close_justification"] == "Stop loss at 98.0"
        assert trade_dict["max_drawdown"] == pytest.approx(0.005)
        assert trade_dict["max_profit"] == pytest.approx(0.015)
        assert trade_dict["pnl_std"] == pytest.approx(0.002)

    def test_trade_group_key_matches_aggregation(self):
        """Trade group key (open_day, open_hour, direction) matches aggregation logic."""
        trade = _make_trade(
            entry_time=datetime.datetime(2024, 6, 3, 14, 30),  # Monday 2pm
            direction="short",
        )

        open_day = trade.entry_time.date()
        open_hour = trade.entry_time.hour
        direction = trade.direction[:5]

        assert open_day == datetime.date(2024, 6, 3)
        assert open_hour == 14
        assert direction == "short"

    def test_pnl_currency_computation(self):
        """P&L in currency is correctly derived from pnl_pct and entry_price."""
        trade = _make_trade(
            entry_time=datetime.datetime(2024, 6, 3, 10, 0),
            direction="long",
            pnl_pct=-0.015,
            entry_price=200.0,
        )

        pnl_currency = trade.pnl_pct * trade.entry_price
        assert pnl_currency == pytest.approx(-3.0)

    def test_short_trade_pnl_currency(self):
        """Short trade P&L currency computation is correct."""
        trade = _make_trade(
            entry_time=datetime.datetime(2024, 6, 3, 10, 0),
            direction="short",
            pnl_pct=0.03,
            entry_price=150.0,
        )

        pnl_currency = trade.pnl_pct * trade.entry_price
        assert pnl_currency == pytest.approx(4.5)


class TestExitManagerPnlStd:
    """Tests for ExitManager.pnl_std property (bar-by-bar P&L std dev)."""

    def _make_exit_manager(
        self,
        entry_price: float = 100.0,
        direction: str = "long",
        atr: float = 1.0,
    ) -> ExitManager:
        """Create an ExitManager with no mechanical exits for pnl_std testing."""
        return ExitManager(
            entry_price=entry_price,
            direction=direction,
            atr_at_entry=atr,
            atr_stop_mult=None,
            atr_target_mult=None,
            trailing_atr_mult=None,
            time_stop_bars=None,
            risk_profile=RISK_PROFILES["medium"],
        )

    def test_pnl_std_zero_for_no_bars(self):
        """pnl_std is 0 when no bars have been processed."""
        em = self._make_exit_manager()
        assert em.pnl_std == 0.0

    def test_pnl_std_zero_for_single_bar(self):
        """pnl_std is 0 for a single bar (std undefined)."""
        em = self._make_exit_manager(entry_price=100.0, direction="long")
        em.check(high=101.0, low=99.0, close=100.5)
        assert em.pnl_std == 0.0

    def test_pnl_std_constant_close(self):
        """pnl_std is 0 when close is constant (all bar P&Ls identical)."""
        em = self._make_exit_manager(entry_price=100.0, direction="long")
        for _ in range(5):
            em.check(high=101.0, low=99.0, close=100.5)
        assert em.pnl_std == pytest.approx(0.0)

    def test_pnl_std_varying_close_long(self):
        """pnl_std reflects variation in bar-by-bar P&L for long trade."""
        em = self._make_exit_manager(entry_price=100.0, direction="long")
        closes = [101.0, 102.0, 100.0, 103.0]
        for c in closes:
            em.check(high=c + 1, low=c - 1, close=c)

        # Expected bar P&Ls: (101-100)/100=0.01, (102-100)/100=0.02,
        # (100-100)/100=0.0, (103-100)/100=0.03
        expected_pnls = [0.01, 0.02, 0.0, 0.03]
        expected_std = float(np.std(expected_pnls, ddof=0))
        assert em.pnl_std == pytest.approx(expected_std, abs=1e-10)

    def test_pnl_std_varying_close_short(self):
        """pnl_std reflects variation in bar-by-bar P&L for short trade."""
        em = self._make_exit_manager(entry_price=100.0, direction="short")
        closes = [99.0, 98.0, 100.0, 97.0]
        for c in closes:
            em.check(high=c + 1, low=c - 1, close=c)

        # Short P&L: (entry-close)/entry
        expected_pnls = [0.01, 0.02, 0.0, 0.03]
        expected_std = float(np.std(expected_pnls, ddof=0))
        assert em.pnl_std == pytest.approx(expected_std, abs=1e-10)


class TestEnginePnlStdIntegration:
    """Integration tests: engine produces trades with pnl_std populated."""

    def test_engine_populates_pnl_std(self):
        """ProbeEngine.run() populates pnl_std on trade results."""
        n_bars = 20
        base_date = pd.Timestamp("2024-06-03 09:30:00")
        index = pd.date_range(start=base_date, periods=n_bars, freq="1h")

        closes = [100.0] * 3 + [101.0, 102.0, 100.5, 103.0, 101.0] + [100.0] * 12
        df = pd.DataFrame({
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": np.full(n_bars, 10000),
            "atr_14": np.full(n_bars, 0.5),
        }, index=index)

        strat = StrategyDef(
            id=99,
            name="test_pnl_std",
            display_name="PnL Std Test",
            philosophy="Test",
            category="trend",
            tags=["test"],
            direction="long_only",
            entry_long=[lambda df, i: i == 2],
            entry_short=[],
            atr_stop_mult=None,
            atr_target_mult=None,
            trailing_atr_mult=None,
            time_stop_bars=5,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        trades = engine.run(df)

        assert len(trades) >= 1
        trade = trades[0]
        # pnl_std should be a non-negative float
        assert isinstance(trade.pnl_std, float)
        assert trade.pnl_std >= 0.0
        # With varying closes, pnl_std should be > 0
        assert trade.pnl_std > 0.0

    def test_engine_pnl_std_is_zero_for_flat_prices(self):
        """pnl_std is 0 when all bar closes are equal."""
        n_bars = 15
        base_date = pd.Timestamp("2024-06-03 09:30:00")
        index = pd.date_range(start=base_date, periods=n_bars, freq="1h")

        df = pd.DataFrame({
            "open": np.full(n_bars, 100.0),
            "high": np.full(n_bars, 101.0),
            "low": np.full(n_bars, 99.0),
            "close": np.full(n_bars, 100.0),
            "volume": np.full(n_bars, 10000),
            "atr_14": np.full(n_bars, 0.5),
        }, index=index)

        strat = StrategyDef(
            id=99,
            name="test_flat_pnl_std",
            display_name="Flat PnL Std Test",
            philosophy="Test",
            category="trend",
            tags=["test"],
            direction="long_only",
            entry_long=[lambda df, i: i == 0],
            entry_short=[],
            atr_stop_mult=None,
            atr_target_mult=None,
            trailing_atr_mult=None,
            time_stop_bars=5,
        )

        engine = ProbeEngine(strat, RISK_PROFILES["medium"])
        trades = engine.run(df)

        assert len(trades) >= 1
        assert trades[0].pnl_std == pytest.approx(0.0)


class TestProbeStrategyTradeModel:
    """Tests for the ProbeStrategyTrade SQLAlchemy model structure."""

    def test_model_has_correct_tablename(self):
        """Model uses the expected table name."""
        from src.data.database.probe_models import ProbeStrategyTrade
        assert ProbeStrategyTrade.__tablename__ == "strategy_probe_trades"

    def test_model_has_required_columns(self):
        """Model defines all required columns."""
        from src.data.database.probe_models import ProbeStrategyTrade
        columns = {c.name for c in ProbeStrategyTrade.__table__.columns}
        expected = {
            "id", "strategy_probe_result_id", "ticker",
            "open_timestamp", "close_timestamp", "direction",
            "open_justification", "close_justification",
            "pnl", "pnl_pct", "bars_held",
            "max_drawdown", "max_profit", "pnl_std",
            "created_at",
        }
        assert expected.issubset(columns)

    def test_model_has_fk_to_results(self):
        """Model has a foreign key to strategy_probe_results."""
        from src.data.database.probe_models import ProbeStrategyTrade
        fks = {
            fk.target_fullname
            for fk in ProbeStrategyTrade.__table__.foreign_keys
        }
        assert "strategy_probe_results.id" in fks

    def test_result_model_has_trades_relationship(self):
        """StrategyProbeResult model has a trades relationship."""
        from src.data.database.probe_models import StrategyProbeResult
        assert hasattr(StrategyProbeResult, "trades")
