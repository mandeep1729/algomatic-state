"""Performance metrics calculation for backtesting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for a trading strategy.

    Attributes:
        total_return: Total return as decimal (e.g., 0.15 = 15%)
        annualized_return: Annualized return
        sharpe_ratio: Annualized Sharpe ratio
        sortino_ratio: Annualized Sortino ratio (downside risk)
        calmar_ratio: Annualized return / max drawdown
        max_drawdown: Maximum drawdown as decimal
        max_drawdown_duration: Duration of max drawdown in days
        max_drawdown_start: Start date of max drawdown
        max_drawdown_end: End date of max drawdown
        volatility: Annualized volatility
        downside_volatility: Annualized downside volatility
        win_rate: Percentage of winning trades
        profit_factor: Gross profit / gross loss
        avg_trade_return: Average return per trade
        avg_win: Average winning trade return
        avg_loss: Average losing trade return
        total_trades: Total number of trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        avg_trade_duration: Average trade duration in bars
        total_commission: Total commission paid
        total_slippage: Total slippage cost
        net_profit: Total net profit
        gross_profit: Total gross profit
        gross_loss: Total gross loss
        custom: Additional custom metrics
    """

    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    max_drawdown_start: datetime | None = None
    max_drawdown_end: datetime | None = None
    volatility: float = 0.0
    downside_volatility: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_duration: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "volatility": self.volatility,
            "downside_volatility": self.downside_volatility,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_trade_return": self.avg_trade_return,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_duration": self.avg_trade_duration,
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,
            "net_profit": self.net_profit,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            **self.custom,
        }


def calculate_metrics(
    equity_curve: pd.Series,
    trades: list[dict[str, Any]],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252 * 390,  # minutes per year
) -> PerformanceMetrics:
    """Calculate comprehensive performance metrics.

    Args:
        equity_curve: Series of portfolio values indexed by timestamp
        trades: List of trade dictionaries with entry/exit info
        risk_free_rate: Annual risk-free rate for Sharpe calculation
        periods_per_year: Number of periods per year for annualization

    Returns:
        PerformanceMetrics object
    """
    if len(equity_curve) < 2:
        return PerformanceMetrics()

    # Calculate returns
    returns = equity_curve.pct_change().dropna()

    if len(returns) == 0:
        return PerformanceMetrics()

    # Basic return metrics
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1

    # Annualized return
    n_periods = len(returns)
    years = n_periods / periods_per_year
    if years > 0:
        annualized_return = (1 + total_return) ** (1 / years) - 1
    else:
        annualized_return = 0.0

    # Volatility (annualized)
    volatility = float(returns.std() * np.sqrt(periods_per_year))

    # Downside volatility (only negative returns)
    downside_returns = returns[returns < 0]
    if len(downside_returns) > 0:
        downside_volatility = float(downside_returns.std() * np.sqrt(periods_per_year))
    else:
        downside_volatility = 0.0

    # Sharpe ratio
    if volatility > 0:
        excess_return = annualized_return - risk_free_rate
        sharpe_ratio = excess_return / volatility
    else:
        sharpe_ratio = 0.0

    # Sortino ratio
    if downside_volatility > 0:
        excess_return = annualized_return - risk_free_rate
        sortino_ratio = excess_return / downside_volatility
    else:
        sortino_ratio = 0.0

    # Drawdown analysis
    dd_metrics = _calculate_drawdown_metrics(equity_curve)

    # Calmar ratio
    if dd_metrics["max_drawdown"] > 0:
        calmar_ratio = annualized_return / dd_metrics["max_drawdown"]
    else:
        calmar_ratio = 0.0

    # Trade statistics
    trade_metrics = _calculate_trade_metrics(trades)

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        max_drawdown=dd_metrics["max_drawdown"],
        max_drawdown_duration=dd_metrics["max_drawdown_duration"],
        max_drawdown_start=dd_metrics["max_drawdown_start"],
        max_drawdown_end=dd_metrics["max_drawdown_end"],
        volatility=volatility,
        downside_volatility=downside_volatility,
        win_rate=trade_metrics["win_rate"],
        profit_factor=trade_metrics["profit_factor"],
        avg_trade_return=trade_metrics["avg_trade_return"],
        avg_win=trade_metrics["avg_win"],
        avg_loss=trade_metrics["avg_loss"],
        total_trades=trade_metrics["total_trades"],
        winning_trades=trade_metrics["winning_trades"],
        losing_trades=trade_metrics["losing_trades"],
        avg_trade_duration=trade_metrics["avg_trade_duration"],
        total_commission=trade_metrics["total_commission"],
        total_slippage=trade_metrics["total_slippage"],
        net_profit=trade_metrics["net_profit"],
        gross_profit=trade_metrics["gross_profit"],
        gross_loss=trade_metrics["gross_loss"],
    )


def _calculate_drawdown_metrics(equity_curve: pd.Series) -> dict[str, Any]:
    """Calculate drawdown-related metrics.

    Args:
        equity_curve: Series of portfolio values

    Returns:
        Dictionary with drawdown metrics
    """
    # Running maximum
    running_max = equity_curve.expanding().max()

    # Drawdown at each point
    drawdown = (equity_curve - running_max) / running_max

    # Maximum drawdown
    max_drawdown = float(abs(drawdown.min()))

    # Find drawdown periods
    in_drawdown = drawdown < 0
    drawdown_starts = []
    drawdown_ends = []

    in_dd = False
    dd_start = None

    for i, (timestamp, is_dd) in enumerate(in_drawdown.items()):
        if is_dd and not in_dd:
            # Start of new drawdown
            in_dd = True
            dd_start = timestamp
        elif not is_dd and in_dd:
            # End of drawdown
            in_dd = False
            drawdown_starts.append(dd_start)
            drawdown_ends.append(timestamp)

    # If still in drawdown at end
    if in_dd:
        drawdown_starts.append(dd_start)
        drawdown_ends.append(equity_curve.index[-1])

    # Find max drawdown period
    max_dd_duration = 0
    max_dd_start = None
    max_dd_end = None

    for start, end in zip(drawdown_starts, drawdown_ends):
        duration = (end - start).total_seconds() / 86400  # days
        if duration > max_dd_duration:
            max_dd_duration = duration
            max_dd_start = start
            max_dd_end = end

    return {
        "max_drawdown": max_drawdown,
        "max_drawdown_duration": int(max_dd_duration),
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
    }


def _calculate_trade_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate trade-related metrics.

    Args:
        trades: List of trade dictionaries

    Returns:
        Dictionary with trade metrics
    """
    if not trades:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_return": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_trade_duration": 0.0,
            "total_commission": 0.0,
            "total_slippage": 0.0,
            "net_profit": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
        }

    total_trades = len(trades)

    # Separate wins and losses
    pnls = [t.get("pnl", 0.0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    winning_trades = len(wins)
    losing_trades = len(losses)

    # Win rate
    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    # Gross profit/loss
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0

    # Profit factor
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    # Average returns
    avg_trade_return = np.mean(pnls) if pnls else 0.0
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0

    # Trade duration
    durations = []
    for t in trades:
        if "entry_time" in t and "exit_time" in t:
            entry = t["entry_time"]
            exit_ = t["exit_time"]
            if isinstance(entry, str):
                entry = pd.Timestamp(entry)
            if isinstance(exit_, str):
                exit_ = pd.Timestamp(exit_)
            duration = (exit_ - entry).total_seconds() / 60  # minutes
            durations.append(duration)

    avg_trade_duration = np.mean(durations) if durations else 0.0

    # Costs
    total_commission = sum(t.get("commission", 0.0) for t in trades)
    total_slippage = sum(t.get("slippage", 0.0) for t in trades)

    # Net profit
    net_profit = gross_profit - gross_loss

    return {
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_trade_return": float(avg_trade_return),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "avg_trade_duration": float(avg_trade_duration),
        "total_commission": total_commission,
        "total_slippage": total_slippage,
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
    }


def calculate_rolling_sharpe(
    returns: pd.Series,
    window: int = 252,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> pd.Series:
    """Calculate rolling Sharpe ratio.

    Args:
        returns: Series of returns
        window: Rolling window size
        periods_per_year: Periods per year for annualization
        risk_free_rate: Annual risk-free rate

    Returns:
        Series of rolling Sharpe ratios
    """
    rolling_mean = returns.rolling(window=window).mean()
    rolling_std = returns.rolling(window=window).std()

    # Annualize
    ann_return = rolling_mean * periods_per_year
    ann_vol = rolling_std * np.sqrt(periods_per_year)

    # Sharpe
    sharpe = (ann_return - risk_free_rate) / ann_vol

    return sharpe


def calculate_monthly_returns(equity_curve: pd.Series) -> pd.DataFrame:
    """Calculate monthly returns matrix.

    Args:
        equity_curve: Series of portfolio values

    Returns:
        DataFrame with years as index, months as columns
    """
    # Resample to monthly
    monthly = equity_curve.resample("ME").last()
    monthly_returns = monthly.pct_change().dropna()

    # Create year/month structure
    monthly_returns.index = pd.MultiIndex.from_arrays(
        [monthly_returns.index.year, monthly_returns.index.month],
        names=["Year", "Month"],
    )

    # Pivot to matrix form
    monthly_matrix = monthly_returns.unstack(level="Month")

    # Rename columns to month names
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_matrix.columns = [month_names[m - 1] for m in monthly_matrix.columns]

    return monthly_matrix
