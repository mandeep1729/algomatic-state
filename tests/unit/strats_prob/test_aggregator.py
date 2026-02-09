"""Unit tests for trade aggregation logic."""

import datetime

import numpy as np
import pytest

from src.strats_prob.aggregator import aggregate_trades
from src.strats_prob.strategy_def import ProbeTradeResult


def _make_trade(
    entry_time: datetime.datetime,
    direction: str = "long",
    pnl_pct: float = 0.01,
    max_drawdown_pct: float = 0.005,
    max_profit_pct: float = 0.015,
    bars_held: int = 5,
) -> ProbeTradeResult:
    """Helper to create a ProbeTradeResult for testing."""
    return ProbeTradeResult(
        entry_time=entry_time,
        exit_time=entry_time + datetime.timedelta(hours=bars_held),
        entry_price=100.0,
        exit_price=100.0 * (1 + pnl_pct),
        direction=direction,
        pnl_pct=pnl_pct,
        bars_held=bars_held,
        max_drawdown_pct=max_drawdown_pct,
        max_profit_pct=max_profit_pct,
        pnl_std=0.0,
        exit_reason="signal_exit",
    )


class TestAggregateTradesBasic:
    """Basic aggregation tests."""

    def test_empty_trades(self):
        """No trades returns empty list."""
        result = aggregate_trades(
            trades=[],
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test-run",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )
        assert result == []

    def test_single_trade(self):
        """Single trade produces one aggregation record."""
        # Monday at 10am
        trade = _make_trade(
            entry_time=datetime.datetime(2024, 6, 3, 10, 0),  # Monday
            direction="long",
            pnl_pct=0.02,
            max_drawdown_pct=0.01,
            max_profit_pct=0.03,
        )

        result = aggregate_trades(
            trades=[trade],
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test-run",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 1
        record = result[0]
        assert record["run_id"] == "test-run"
        assert record["symbol"] == "AAPL"
        assert record["strategy_id"] == 1
        assert record["timeframe"] == "1Hour"
        assert record["risk_profile"] == "medium"
        assert record["open_day"] == datetime.date(2024, 6, 3)  # Full calendar date
        assert record["open_hour"] == 10
        assert record["long_short"] == "long"
        assert record["num_trades"] == 1
        assert record["pnl_mean"] == pytest.approx(0.02)
        assert record["pnl_std"] == 0.0  # Single trade => 0 std
        assert record["max_drawdown"] == pytest.approx(0.01)
        assert record["max_profit"] == pytest.approx(0.03)


class TestAggregateTradesGrouping:
    """Tests for grouping by dimensions."""

    def test_groups_by_day(self):
        """Trades on different days go into separate groups."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0)),  # Monday
            _make_trade(datetime.datetime(2024, 6, 4, 10, 0)),  # Tuesday
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 2
        days = {r["open_day"] for r in result}
        assert days == {datetime.date(2024, 6, 3), datetime.date(2024, 6, 4)}

    def test_groups_by_hour(self):
        """Trades at different hours go into separate groups."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0)),
            _make_trade(datetime.datetime(2024, 6, 3, 14, 0)),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 2
        hours = {r["open_hour"] for r in result}
        assert hours == {10, 14}

    def test_groups_by_direction(self):
        """Long and short trades go into separate groups."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0), direction="long"),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0), direction="short"),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 2
        directions = {r["long_short"] for r in result}
        assert directions == {"long", "short"}

    def test_same_group_aggregated(self):
        """Multiple trades on the same date/hour/direction are aggregated together."""
        trades = [
            _make_trade(
                datetime.datetime(2024, 6, 3, 10, 0),
                pnl_pct=0.02,
                max_drawdown_pct=0.01,
                max_profit_pct=0.03,
            ),
            _make_trade(
                datetime.datetime(2024, 6, 3, 10, 30),  # Same date, same hour
                pnl_pct=0.04,
                max_drawdown_pct=0.02,
                max_profit_pct=0.05,
            ),
            _make_trade(
                datetime.datetime(2024, 6, 3, 10, 45),  # Same date, same hour
                pnl_pct=-0.01,
                max_drawdown_pct=0.03,
                max_profit_pct=0.01,
            ),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 1
        record = result[0]
        assert record["num_trades"] == 3
        assert record["open_day"] == datetime.date(2024, 6, 3)
        assert record["open_hour"] == 10
        assert record["long_short"] == "long"

    def test_different_dates_same_weekday_separate_groups(self):
        """Trades on different dates but same weekday go into separate groups."""
        trades = [
            _make_trade(
                datetime.datetime(2024, 6, 3, 10, 0),  # Monday June 3
                pnl_pct=0.02,
            ),
            _make_trade(
                datetime.datetime(2024, 6, 10, 10, 0),  # Monday June 10
                pnl_pct=0.04,
            ),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 2
        days = {r["open_day"] for r in result}
        assert days == {datetime.date(2024, 6, 3), datetime.date(2024, 6, 10)}


class TestAggregateTradesStatistics:
    """Tests for aggregate statistics computation."""

    def test_pnl_mean(self):
        """Mean P&L is correctly computed."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0), pnl_pct=0.02),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 15), pnl_pct=0.04),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 30), pnl_pct=-0.01),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 1
        expected_mean = (0.02 + 0.04 + (-0.01)) / 3
        assert result[0]["pnl_mean"] == pytest.approx(expected_mean, abs=1e-10)

    def test_pnl_std(self):
        """Std P&L is correctly computed (population std)."""
        pnls = [0.02, 0.04, -0.01]
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, i * 15), pnl_pct=p)
            for i, p in enumerate(pnls)
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 1
        expected_std = float(np.std(pnls))
        assert result[0]["pnl_std"] == pytest.approx(expected_std, abs=1e-10)

    def test_pnl_std_single_trade(self):
        """Std P&L for a single trade is 0."""
        trades = [_make_trade(datetime.datetime(2024, 6, 3, 10, 0), pnl_pct=0.02)]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert result[0]["pnl_std"] == 0.0

    def test_max_drawdown(self):
        """Max drawdown is the worst drawdown in the group."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0), max_drawdown_pct=0.01),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 15), max_drawdown_pct=0.05),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 30), max_drawdown_pct=0.03),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert result[0]["max_drawdown"] == pytest.approx(0.05)

    def test_max_profit(self):
        """Max profit is the best profit in the group."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0), max_profit_pct=0.03),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 15), max_profit_pct=0.08),
            _make_trade(datetime.datetime(2024, 6, 3, 10, 30), max_profit_pct=0.05),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert result[0]["max_profit"] == pytest.approx(0.08)


class TestAggregateTradesMetadata:
    """Tests for metadata fields in output records."""

    def test_symbol_uppercased(self):
        """Symbol is uppercased in output."""
        trades = [_make_trade(datetime.datetime(2024, 6, 3, 10, 0))]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="aapl",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert result[0]["symbol"] == "AAPL"

    def test_period_timestamps_preserved(self):
        """Period start and end are preserved in output."""
        trades = [_make_trade(datetime.datetime(2024, 6, 3, 10, 0))]
        start = datetime.datetime(2024, 1, 1)
        end = datetime.datetime(2024, 6, 30)

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=start,
            period_end=end,
        )

        assert result[0]["period_start"] == start
        assert result[0]["period_end"] == end

    def test_all_required_fields_present(self):
        """Output records have all required fields."""
        trades = [_make_trade(datetime.datetime(2024, 6, 3, 10, 0))]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        required_fields = {
            "run_id", "symbol", "strategy_id", "period_start", "period_end",
            "timeframe", "risk_profile", "open_day", "open_hour", "long_short",
            "num_trades", "pnl_mean", "pnl_std", "max_drawdown", "max_profit",
        }
        assert required_fields.issubset(set(result[0].keys()))


class TestAggregateTradesDateDimension:
    """Tests for open_day date dimension."""

    def test_open_day_is_date_object(self):
        """open_day stores a datetime.date, not an integer."""
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0)),
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert isinstance(result[0]["open_day"], datetime.date)
        assert result[0]["open_day"] == datetime.date(2024, 6, 3)

    def test_each_date_gets_separate_group(self):
        """Trades on different dates produce separate groups."""
        # Monday through Friday
        trades = [
            _make_trade(datetime.datetime(2024, 6, 3, 10, 0)),   # Mon
            _make_trade(datetime.datetime(2024, 6, 4, 10, 0)),   # Tue
            _make_trade(datetime.datetime(2024, 6, 5, 10, 0)),   # Wed
            _make_trade(datetime.datetime(2024, 6, 6, 10, 0)),   # Thu
            _make_trade(datetime.datetime(2024, 6, 7, 10, 0)),   # Fri
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        days = sorted([r["open_day"] for r in result])
        expected = [
            datetime.date(2024, 6, 3),
            datetime.date(2024, 6, 4),
            datetime.date(2024, 6, 5),
            datetime.date(2024, 6, 6),
            datetime.date(2024, 6, 7),
        ]
        assert days == expected

    def test_cross_month_dates_not_conflated(self):
        """Trades on same day-of-month in different months are separate groups."""
        trades = [
            _make_trade(datetime.datetime(2024, 5, 15, 10, 0)),  # May 15
            _make_trade(datetime.datetime(2024, 6, 15, 10, 0)),  # June 15
        ]

        result = aggregate_trades(
            trades=trades,
            strategy_id=1,
            symbol="AAPL",
            timeframe="1Hour",
            risk_profile="medium",
            run_id="test",
            period_start=datetime.datetime(2024, 1, 1),
            period_end=datetime.datetime(2024, 6, 30),
        )

        assert len(result) == 2
        days = {r["open_day"] for r in result}
        assert days == {datetime.date(2024, 5, 15), datetime.date(2024, 6, 15)}
