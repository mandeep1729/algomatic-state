"""Output and reporting helpers."""

import json
from pathlib import Path

import pandas as pd


def print_backtest_summary(summary: dict, logger) -> None:
    """Print backtest results summary."""
    logger.info("\n" + "=" * 50)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 50)
    _print_summary_metrics(summary, logger)
    logger.info("=" * 50)


def _print_summary_metrics(summary: dict, logger) -> None:
    """Print individual summary metrics."""
    logger.info(f"Period: {summary['period_start']} to {summary['period_end']}")
    logger.info(f"Initial Capital: ${summary['initial_capital']:,.2f}")
    logger.info(f"Final Capital: ${summary['final_capital']:,.2f}")
    logger.info(f"Total Return: {summary['total_return_pct']:.2f}%")
    logger.info(f"Annualized Return: {summary['annualized_return_pct']:.2f}%")
    logger.info(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
    logger.info(f"Sortino Ratio: {summary['sortino_ratio']:.2f}")
    logger.info(f"Max Drawdown: {summary['max_drawdown_pct']:.2f}%")
    logger.info(f"Calmar Ratio: {summary['calmar_ratio']:.2f}")
    logger.info(f"Total Trades: {summary['total_trades']}")
    logger.info(f"Win Rate: {summary['win_rate_pct']:.1f}%")
    logger.info(f"Profit Factor: {summary['profit_factor']:.2f}")


def save_json_report(report_data: dict, output_dir: Path, logger) -> None:
    """Save report as JSON file."""
    report_path = output_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)
    logger.info(f"Saved report to {report_path}")


def save_equity_curve(equity_curve: pd.Series, output_dir: Path, logger) -> None:
    """Save equity curve as CSV."""
    equity_path = output_dir / "equity_curve.csv"
    equity_curve.to_csv(equity_path)
    logger.info(f"Saved equity curve to {equity_path}")


def save_trades(trades: list, output_dir: Path, logger) -> None:
    """Save trades as CSV if any exist."""
    if not trades:
        return
    trades_path = output_dir / "trades.csv"
    trades_df = pd.DataFrame([t.to_dict() for t in trades])
    trades_df.to_csv(trades_path, index=False)
    logger.info(f"Saved trades to {trades_path}")


def save_all_results(report_data: dict, result, output_dir: Path, logger) -> None:
    """Save all backtest results to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json_report(report_data, output_dir, logger)
    save_equity_curve(result.equity_curve, output_dir, logger)
    save_trades(result.trades, output_dir, logger)
