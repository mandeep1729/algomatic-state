"""Trade result aggregation for probe system.

Groups trades by (open_day=date, open_hour, long_short) and computes
aggregate statistics for each group.
"""

import logging
from typing import Optional

import numpy as np

from src.strats_prob.strategy_def import ProbeTradeResult

logger = logging.getLogger(__name__)


def aggregate_trades(
    trades: list[ProbeTradeResult],
    strategy_id: int,
    symbol: str,
    timeframe: str,
    risk_profile: str,
    run_id: str,
    period_start,
    period_end,
) -> list[dict]:
    """Aggregate trade results into probe records grouped by dimensions.

    Groups by (open_day=date, open_hour, long_short) and computes:
    - num_trades
    - pnl_mean
    - pnl_std
    - max_drawdown (worst among all trades in group)
    - max_profit (best among all trades in group)

    Args:
        trades: List of ProbeTradeResult from the engine.
        strategy_id: FK to probe_strategies table.
        symbol: Ticker symbol.
        timeframe: Bar timeframe (e.g. "1Hour").
        risk_profile: Risk profile name (low/medium/high).
        run_id: Unique run identifier.
        period_start: Start of the evaluation period.
        period_end: End of the evaluation period.

    Returns:
        List of dicts ready for ProbeRepository.bulk_insert_results().
    """
    if not trades:
        logger.debug(
            "No trades to aggregate for strategy_id=%d, %s/%s/%s",
            strategy_id, symbol, timeframe, risk_profile,
        )
        return []

    # Group trades by dimensions
    groups: dict[tuple, list[ProbeTradeResult]] = {}
    for trade in trades:
        open_day = trade.entry_time.date()  # Full calendar date (YYYY-MM-DD)
        open_hour = trade.entry_time.hour
        long_short = trade.direction[:5]  # "long" or "short"

        key = (open_day, open_hour, long_short)
        if key not in groups:
            groups[key] = []
        groups[key].append(trade)

    # Compute aggregations per group
    records = []
    for (open_day, open_hour, long_short), group_trades in groups.items():
        pnls = [t.pnl_pct for t in group_trades]
        drawdowns = [t.max_drawdown_pct for t in group_trades]
        profits = [t.max_profit_pct for t in group_trades]

        pnl_arr = np.array(pnls)

        records.append({
            "run_id": run_id,
            "symbol": symbol.upper(),
            "strategy_id": strategy_id,
            "period_start": period_start,
            "period_end": period_end,
            "timeframe": timeframe,
            "risk_profile": risk_profile,
            "open_day": open_day,
            "open_hour": open_hour,
            "long_short": long_short,
            "num_trades": len(group_trades),
            "pnl_mean": float(np.mean(pnl_arr)),
            "pnl_std": float(np.std(pnl_arr)) if len(pnl_arr) > 1 else 0.0,
            "max_drawdown": float(max(drawdowns)) if drawdowns else 0.0,
            "max_profit": float(max(profits)) if profits else 0.0,
        })

    logger.debug(
        "Aggregated %d trades into %d groups for strategy_id=%d, %s/%s/%s",
        len(trades), len(records), strategy_id, symbol, timeframe, risk_profile,
    )
    return records
