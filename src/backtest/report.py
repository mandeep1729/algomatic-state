"""Performance reporting and visualization for backtests."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult
from src.backtest.metrics import PerformanceMetrics, calculate_monthly_returns

logger = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """Configuration for performance reports.

    Attributes:
        title: Report title
        include_equity_curve: Include equity curve plot
        include_drawdown: Include drawdown plot
        include_monthly_heatmap: Include monthly returns heatmap
        include_trade_analysis: Include trade analysis section
        include_regime_breakdown: Include regime performance breakdown
        output_format: Output format ('html', 'markdown', 'dict')
    """

    title: str = "Backtest Performance Report"
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_monthly_heatmap: bool = True
    include_trade_analysis: bool = True
    include_regime_breakdown: bool = True
    output_format: str = "dict"


class PerformanceReport:
    """Generate performance reports from backtest results.

    Example:
        >>> report = PerformanceReport(config)
        >>> output = report.generate(result)
        >>> report.save(output, "report.html")
    """

    def __init__(self, config: ReportConfig | None = None):
        """Initialize report generator.

        Args:
            config: Report configuration
        """
        self._config = config or ReportConfig()

    @property
    def config(self) -> ReportConfig:
        """Return configuration."""
        return self._config

    def generate(self, result: BacktestResult) -> dict[str, Any]:
        """Generate performance report.

        Args:
            result: Backtest result

        Returns:
            Report data dictionary
        """
        logger.debug("Generating performance report: %s", self._config.title)
        report = {
            "title": self._config.title,
            "generated_at": datetime.now().isoformat(),
            "summary": self._generate_summary(result),
            "metrics": result.metrics.to_dict(),
        }

        if self._config.include_equity_curve:
            report["equity_curve"] = self._generate_equity_data(result)

        if self._config.include_drawdown:
            report["drawdown"] = self._generate_drawdown_data(result)

        if self._config.include_monthly_heatmap:
            report["monthly_returns"] = self._generate_monthly_data(result)

        if self._config.include_trade_analysis:
            report["trade_analysis"] = self._generate_trade_analysis(result)

        if self._config.include_regime_breakdown:
            report["regime_breakdown"] = self._generate_regime_breakdown(result)

        logger.debug("Report generated with sections: %s", list(report.keys()))
        return report

    def _generate_summary(self, result: BacktestResult) -> dict[str, Any]:
        """Generate summary statistics.

        Args:
            result: Backtest result

        Returns:
            Summary dictionary
        """
        metrics = result.metrics
        equity = result.equity_curve

        return {
            "period_start": str(equity.index[0]) if len(equity) > 0 else None,
            "period_end": str(equity.index[-1]) if len(equity) > 0 else None,
            "initial_capital": result.config.initial_capital,
            "final_capital": float(equity.iloc[-1]) if len(equity) > 0 else 0,
            "total_return_pct": metrics.total_return * 100,
            "annualized_return_pct": metrics.annualized_return * 100,
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
            "max_drawdown_pct": metrics.max_drawdown * 100,
            "calmar_ratio": metrics.calmar_ratio,
            "total_trades": metrics.total_trades,
            "win_rate_pct": metrics.win_rate * 100,
            "profit_factor": metrics.profit_factor,
        }

    def _generate_equity_data(self, result: BacktestResult) -> dict[str, Any]:
        """Generate equity curve data.

        Args:
            result: Backtest result

        Returns:
            Equity curve data
        """
        equity = result.equity_curve

        # Resample for plotting (reduce data points if too many)
        if len(equity) > 10000:
            equity_plot = equity.resample("1H").last().dropna()
        else:
            equity_plot = equity

        return {
            "timestamps": [str(t) for t in equity_plot.index],
            "values": equity_plot.tolist(),
            "initial": float(equity.iloc[0]) if len(equity) > 0 else 0,
            "final": float(equity.iloc[-1]) if len(equity) > 0 else 0,
            "peak": float(equity.max()) if len(equity) > 0 else 0,
            "trough": float(equity.min()) if len(equity) > 0 else 0,
        }

    def _generate_drawdown_data(self, result: BacktestResult) -> dict[str, Any]:
        """Generate drawdown data.

        Args:
            result: Backtest result

        Returns:
            Drawdown data
        """
        equity = result.equity_curve

        if len(equity) == 0:
            return {"timestamps": [], "values": [], "max_drawdown_pct": 0}

        # Calculate drawdown series
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100  # As percentage

        # Resample for plotting
        if len(drawdown) > 10000:
            drawdown_plot = drawdown.resample("1H").min().dropna()
        else:
            drawdown_plot = drawdown

        return {
            "timestamps": [str(t) for t in drawdown_plot.index],
            "values": drawdown_plot.tolist(),
            "max_drawdown_pct": float(abs(drawdown.min())),
            "current_drawdown_pct": float(abs(drawdown.iloc[-1])),
        }

    def _generate_monthly_data(self, result: BacktestResult) -> dict[str, Any]:
        """Generate monthly returns data.

        Args:
            result: Backtest result

        Returns:
            Monthly returns data
        """
        equity = result.equity_curve

        if len(equity) < 30:  # Less than a month of data
            return {"years": [], "data": {}}

        try:
            monthly_matrix = calculate_monthly_returns(equity)

            return {
                "years": monthly_matrix.index.tolist(),
                "months": monthly_matrix.columns.tolist(),
                "data": {
                    int(year): {
                        month: float(val) * 100 if not pd.isna(val) else None
                        for month, val in row.items()
                    }
                    for year, row in monthly_matrix.iterrows()
                },
            }
        except Exception:
            return {"years": [], "data": {}}

    def _generate_trade_analysis(self, result: BacktestResult) -> dict[str, Any]:
        """Generate trade analysis.

        Args:
            result: Backtest result

        Returns:
            Trade analysis data
        """
        trades = result.trades

        if not trades:
            return {
                "total_trades": 0,
                "by_direction": {},
                "pnl_distribution": {},
                "duration_distribution": {},
            }

        # Separate by direction
        long_trades = [t for t in trades if t.direction.value == "long"]
        short_trades = [t for t in trades if t.direction.value == "short"]

        # PnL distribution
        pnls = [t.pnl for t in trades]
        pnl_stats = {
            "mean": float(np.mean(pnls)),
            "std": float(np.std(pnls)),
            "median": float(np.median(pnls)),
            "min": float(np.min(pnls)),
            "max": float(np.max(pnls)),
            "percentile_25": float(np.percentile(pnls, 25)),
            "percentile_75": float(np.percentile(pnls, 75)),
        }

        # Duration distribution
        durations = []
        for t in trades:
            duration = (t.exit_time - t.entry_time).total_seconds() / 60
            durations.append(duration)

        duration_stats = {
            "mean_minutes": float(np.mean(durations)) if durations else 0,
            "median_minutes": float(np.median(durations)) if durations else 0,
            "min_minutes": float(np.min(durations)) if durations else 0,
            "max_minutes": float(np.max(durations)) if durations else 0,
        }

        # By direction analysis
        def direction_stats(trade_list):
            if not trade_list:
                return {"count": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0}
            pnls = [t.pnl for t in trade_list]
            wins = [p for p in pnls if p > 0]
            return {
                "count": len(trade_list),
                "win_rate": len(wins) / len(trade_list) if trade_list else 0,
                "avg_pnl": float(np.mean(pnls)),
                "total_pnl": float(sum(pnls)),
            }

        return {
            "total_trades": len(trades),
            "by_direction": {
                "long": direction_stats(long_trades),
                "short": direction_stats(short_trades),
            },
            "pnl_distribution": pnl_stats,
            "duration_distribution": duration_stats,
            "best_trade": {
                "pnl": float(max(pnls)),
                "index": pnls.index(max(pnls)),
            },
            "worst_trade": {
                "pnl": float(min(pnls)),
                "index": pnls.index(min(pnls)),
            },
        }

    def _generate_regime_breakdown(self, result: BacktestResult) -> dict[str, Any]:
        """Generate performance breakdown by regime.

        Args:
            result: Backtest result

        Returns:
            Regime breakdown data
        """
        signals = result.signals
        trades = result.trades

        if not signals:
            return {"by_regime": {}}

        # Group signals by regime
        regime_signals: dict[int, list] = {}
        for s in signals:
            regime = s.metadata.regime_label
            if regime is not None:
                if regime not in regime_signals:
                    regime_signals[regime] = []
                regime_signals[regime].append(s)

        # Calculate stats by regime
        by_regime = {}
        for regime, sigs in regime_signals.items():
            entry_signals = [s for s in sigs if s.direction.value != "flat"]
            by_regime[regime] = {
                "total_signals": len(sigs),
                "entry_signals": len(entry_signals),
                "long_signals": len([s for s in sigs if s.direction.value == "long"]),
                "short_signals": len([s for s in sigs if s.direction.value == "short"]),
                "avg_strength": float(np.mean([s.strength for s in entry_signals])) if entry_signals else 0,
            }

        return {"by_regime": by_regime}

    def to_markdown(self, report: dict[str, Any]) -> str:
        """Convert report to markdown format.

        Args:
            report: Report dictionary

        Returns:
            Markdown string
        """
        lines = [
            f"# {report['title']}",
            f"Generated: {report['generated_at']}",
            "",
            "## Summary",
            "",
        ]

        summary = report.get("summary", {})
        lines.extend([
            f"- **Period**: {summary.get('period_start')} to {summary.get('period_end')}",
            f"- **Initial Capital**: ${summary.get('initial_capital', 0):,.2f}",
            f"- **Final Capital**: ${summary.get('final_capital', 0):,.2f}",
            f"- **Total Return**: {summary.get('total_return_pct', 0):.2f}%",
            f"- **Annualized Return**: {summary.get('annualized_return_pct', 0):.2f}%",
            f"- **Sharpe Ratio**: {summary.get('sharpe_ratio', 0):.2f}",
            f"- **Sortino Ratio**: {summary.get('sortino_ratio', 0):.2f}",
            f"- **Max Drawdown**: {summary.get('max_drawdown_pct', 0):.2f}%",
            f"- **Total Trades**: {summary.get('total_trades', 0)}",
            f"- **Win Rate**: {summary.get('win_rate_pct', 0):.1f}%",
            f"- **Profit Factor**: {summary.get('profit_factor', 0):.2f}",
            "",
        ])

        # Trade analysis
        if "trade_analysis" in report:
            analysis = report["trade_analysis"]
            lines.extend([
                "## Trade Analysis",
                "",
                "### By Direction",
                "",
            ])

            for direction, stats in analysis.get("by_direction", {}).items():
                lines.append(f"**{direction.title()}**: {stats['count']} trades, "
                           f"{stats['win_rate']*100:.1f}% win rate, "
                           f"${stats['total_pnl']:,.2f} total PnL")

            lines.append("")

            pnl = analysis.get("pnl_distribution", {})
            lines.extend([
                "### PnL Distribution",
                "",
                f"- Mean: ${pnl.get('mean', 0):,.2f}",
                f"- Median: ${pnl.get('median', 0):,.2f}",
                f"- Std Dev: ${pnl.get('std', 0):,.2f}",
                f"- Best: ${pnl.get('max', 0):,.2f}",
                f"- Worst: ${pnl.get('min', 0):,.2f}",
                "",
            ])

        return "\n".join(lines)

    def save(
        self,
        report: dict[str, Any],
        path: str | Path,
    ) -> None:
        """Save report to file.

        Args:
            report: Report dictionary
            path: Output file path
        """
        import json

        path = Path(path)
        logger.debug("Saving report to %s (format=%s)", path, self._config.output_format)

        if self._config.output_format == "markdown" or path.suffix == ".md":
            content = self.to_markdown(report)
            path.write_text(content)
            logger.info("Report saved as markdown: %s", path)
        else:
            # Default to JSON
            with open(path, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info("Report saved as JSON: %s", path)
