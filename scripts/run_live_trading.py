#!/usr/bin/env python
"""Run LIVE trading with the state-enhanced strategy.

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!  WARNING: THIS SCRIPT TRADES WITH REAL MONEY                      !!
!!  Double-check all settings before running                         !!
!!  Start with small position sizes and monitor closely              !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Usage:
    python scripts/run_live_trading.py --symbols AAPL --confirm
    python scripts/run_live_trading.py --symbols AAPL MSFT --model models/autoencoder.pt --confirm
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import time

import yaml

from src.execution.client import AlpacaClient
from src.execution.runner import TradingRunner, TradingRunnerConfig
from src.execution.risk_manager import RiskConfig
from scripts.helpers.logging_setup import setup_script_logging
from scripts.helpers.state_models import load_all_models
from scripts.helpers.strategy_factory import (
    create_momentum_strategy,
    create_state_enhanced_config,
    create_state_enhanced_strategy,
    create_pattern_matcher,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run LIVE trading with state-enhanced strategy")
    _add_symbol_args(parser)
    _add_strategy_args(parser)
    _add_risk_args(parser)
    _add_runtime_args(parser)
    return parser.parse_args()


def _add_symbol_args(parser: argparse.ArgumentParser) -> None:
    """Add symbol-related arguments."""
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols to trade")
    parser.add_argument("--config", type=str, help="Path to YAML configuration file")


def _add_strategy_args(parser: argparse.ArgumentParser) -> None:
    """Add strategy-related arguments."""
    parser.add_argument("--model", type=str, help="Path to trained autoencoder model")
    parser.add_argument("--long-threshold", type=float, default=0.001, help="Long signal threshold")
    parser.add_argument("--short-threshold", type=float, default=-0.001, help="Short signal threshold")


def _add_risk_args(parser: argparse.ArgumentParser) -> None:
    """Add risk management arguments."""
    parser.add_argument("--max-position-value", type=float, default=5000.0, help="Max position value in dollars")
    parser.add_argument("--max-position-pct", type=float, default=0.10, help="Max position as % of portfolio")
    parser.add_argument("--max-daily-loss-pct", type=float, default=0.01, help="Max daily loss as %")
    parser.add_argument("--max-drawdown-pct", type=float, default=0.05, help="Max drawdown as %")


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    """Add runtime arguments."""
    parser.add_argument("--interval", type=int, default=60, help="Signal interval in seconds")
    parser.add_argument("--warmup-bars", type=int, default=100, help="Historical bars for warmup")
    parser.add_argument("--confirm", action="store_true", help="Confirm live trading")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def load_yaml_config(path: str) -> dict:
    """Load configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def apply_yaml_config(args: argparse.Namespace, yaml_config: dict) -> None:
    """Apply YAML config values to args."""
    if "strategy" in yaml_config:
        strategy_cfg = yaml_config["strategy"]
        if "long_threshold" in strategy_cfg:
            args.long_threshold = strategy_cfg["long_threshold"]
        if "short_threshold" in strategy_cfg:
            args.short_threshold = strategy_cfg["short_threshold"]


def print_account_info(account, args) -> None:
    """Print account information."""
    print(f"  Account ID: {account.account_id}")
    print(f"  Account Equity: ${account.equity:,.2f}")
    print(f"  Buying Power: ${account.buying_power:,.2f}")


def print_trading_config(args) -> None:
    """Print trading configuration."""
    print("Trading Configuration:")
    print(f"  Symbols: {', '.join(args.symbols)}")
    print(f"  Max Position Value: ${args.max_position_value:,.2f}")
    print(f"  Max Position %: {args.max_position_pct:.0%}")
    print(f"  Max Daily Loss: {args.max_daily_loss_pct:.0%}")
    print(f"  Max Drawdown: {args.max_drawdown_pct:.0%}")


def print_max_loss_warning(args, account) -> None:
    """Print maximum potential loss warning."""
    max_loss = min(args.max_position_value, account.equity * args.max_position_pct)
    print(f"\nMaximum potential loss per position: ${max_loss:,.2f}\n")


def get_live_confirmation() -> bool:
    """Get user confirmation for live trading."""
    print("Type 'LIVE TRADE' to confirm you want to proceed:")
    confirmation = input("> ").strip()
    return confirmation == "LIVE TRADE"


def countdown_start(seconds: int) -> None:
    """Display countdown before starting."""
    print(f"\nStarting live trading in {seconds} seconds... Press Ctrl+C to abort.\n")
    for i in range(seconds, 0, -1):
        print(f"  {i}...")
        time.sleep(1)


def _print_warning_details(account, args) -> None:
    """Print detailed warning info."""
    print("\nThis script will trade with REAL MONEY.\n")
    print_account_info(account, args)
    print()
    print_trading_config(args)
    print_max_loss_warning(args, account)
    print("=" * 70)
    print()


def display_safety_warning(account, args, logger) -> bool:
    """Display safety warning and get confirmation."""
    print("\n" + "=" * 70 + "\n!!! WARNING: LIVE TRADING MODE !!!\n" + "=" * 70)
    _print_warning_details(account, args)

    if not args.confirm:
        print("ERROR: You must pass --confirm to acknowledge you want to trade live.\n")
        return False

    if not get_live_confirmation():
        print("Confirmation failed. Exiting.")
        return False

    countdown_start(5)
    return True


def create_strategy(args, logger):
    """Create trading strategy based on arguments."""
    if args.model:
        return _create_state_enhanced_strategy(args, logger)
    return _create_momentum_strategy(args, logger)


def _create_momentum_strategy(args, logger):
    """Create baseline momentum strategy."""
    logger.info("Creating baseline momentum strategy")
    return create_momentum_strategy(args.symbols, args.long_threshold, args.short_threshold)


def _create_state_enhanced_strategy(args, logger):
    """Create state-enhanced strategy with models."""
    logger.info("Creating state-enhanced strategy")
    models = load_all_models(args.model)
    logger.info(f"Loaded models from {Path(args.model).parent}")

    config = create_state_enhanced_config(
        symbols=args.symbols,
        long_threshold=args.long_threshold,
        short_threshold=args.short_threshold,
        base_size=args.max_position_value * 0.5,
        max_size=args.max_position_value,
        min_sharpe=0.5,  # Conservative for live
        enable_regime_filter=True,
        enable_pattern_matching=False,
        enable_dynamic_sizing=True,
    )
    return create_state_enhanced_strategy(config, models.clusterer, create_pattern_matcher())


def create_live_risk_config(args) -> RiskConfig:
    """Create conservative risk configuration for live trading."""
    return RiskConfig(
        max_position_value=args.max_position_value,
        max_position_pct=args.max_position_pct,
        max_portfolio_concentration=0.15,
        max_daily_loss_pct=args.max_daily_loss_pct,
        max_drawdown_pct=args.max_drawdown_pct,
        max_symbols=5,
        min_buying_power_pct=0.20,
        max_order_value=args.max_position_value,
        max_order_pct=0.05,
        check_pattern_day_trader=True,
        enabled=True,
    )


def create_runner_config(args, risk_config: RiskConfig) -> TradingRunnerConfig:
    """Create trading runner configuration."""
    return TradingRunnerConfig(
        symbols=args.symbols,
        signal_interval_seconds=args.interval,
        warmup_bars=args.warmup_bars,
        paper=False,  # LIVE MODE
        risk_config=risk_config,
        dry_run=False,
        log_dir=Path("logs/live_trading"),
    )


def _on_live_signal(logger):
    """Create live signal callback."""
    def on_signal(signal):
        logger.info(
            f"[LIVE] Signal: {signal.symbol} {signal.direction.value.upper()} "
            f"strength={signal.strength:.2f} size=${signal.size:,.2f}"
        )
    return on_signal


def _on_live_fill(client, logger):
    """Create live fill callback."""
    def on_fill(update):
        logger.info(
            f"[LIVE] FILL: {update.order.symbol} "
            f"qty={update.fill_quantity} @ ${update.fill_price:.2f}"
        )
        _log_account_status(client, logger)
    return on_fill


def register_live_callbacks(runner, client, logger) -> None:
    """Register callbacks with enhanced logging for live trading."""
    runner.on_signal(_on_live_signal(logger))
    runner.on_fill(_on_live_fill(client, logger))
    runner.on_error(lambda error: logger.error(f"[LIVE] ERROR: {error}"))


def _log_account_status(client, logger) -> None:
    """Log current account status."""
    try:
        acct = client.get_account()
        logger.info(f"[LIVE] Account equity: ${acct.equity:,.2f}")
    except Exception:
        pass


def print_live_status(args, logger) -> None:
    """Print live trading status."""
    logger.info("\n" + "=" * 50)
    logger.info("LIVE TRADING ACTIVE")
    logger.info("=" * 50)
    logger.info(f"Symbols: {', '.join(args.symbols)}")
    logger.info(f"Strategy: {'State-Enhanced' if args.model else 'Baseline Momentum'}")
    logger.info(f"Interval: {args.interval}s")
    logger.info(f"Max Position: ${args.max_position_value:,.2f}")
    logger.info(f"Max Daily Loss: {args.max_daily_loss_pct:.0%}")
    logger.info(f"Max Drawdown: {args.max_drawdown_pct:.0%}")
    logger.info("=" * 50)
    logger.info("Press Ctrl+C to stop trading and close positions")
    logger.info("")


def handle_shutdown(runner, logger) -> None:
    """Handle graceful shutdown."""
    logger.info("")
    logger.info("=" * 50)
    logger.info("SHUTDOWN REQUESTED")
    logger.info("=" * 50)

    print("\nDo you want to close all positions? (yes/no)")
    response = input("> ").strip().lower()

    if response == "yes":
        logger.info("Closing all positions...")
        runner.emergency_stop()
    else:
        logger.info("Keeping positions open, cancelling pending orders only...")
        runner.stop()


def print_final_status(runner, logger) -> None:
    """Print final trading status."""
    try:
        status = runner.get_status()
        _log_final_status(status, logger)
    except Exception:
        pass


def _log_final_status(status, logger) -> None:
    """Log final status details."""
    logger.info("\n" + "=" * 50)
    logger.info("FINAL STATUS")
    logger.info("=" * 50)
    logger.info(f"Equity: ${status['account']['equity']:,.2f}")
    logger.info(f"Positions: {status['positions']}")
    logger.info(f"Pending Orders: {status['pending_orders']}")
    if 'risk' in status:
        logger.info(f"Daily P&L: ${status['risk']['daily_pnl']:,.2f}")
        logger.info(f"Drawdown: {status['risk']['drawdown_pct']:.1f}%")
    logger.info("=" * 50)


def _load_and_apply_config(args, logger) -> None:
    """Load YAML config if provided."""
    if args.config:
        logger.info(f"Loading config from {args.config}")
        apply_yaml_config(args, load_yaml_config(args.config))


def _connect_live(logger) -> tuple:
    """Connect to live Alpaca and return client, account."""
    client = AlpacaClient(paper=False)
    account = client.get_account()
    return client, account


def _setup_live_runner(args, strategy, client) -> TradingRunner:
    """Setup and return live trading runner."""
    risk_config = create_live_risk_config(args)
    runner_config = create_runner_config(args, risk_config)
    return TradingRunner(runner_config, strategy, client)


def _run_live_trading_loop(runner, client, logger) -> int:
    """Run the live trading loop."""
    try:
        runner.run()
    except KeyboardInterrupt:
        handle_shutdown(runner, logger)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        runner.emergency_stop()
        return 1
    finally:
        print_final_status(runner, logger)
    return 0


def _init_live_runner(args, strategy, client, logger):
    """Initialize live runner."""
    runner = _setup_live_runner(args, strategy, client)
    register_live_callbacks(runner, client, logger)
    logger.info("Initializing live trading runner...")
    runner.initialize()
    return runner


def _perform_setup(args, logger):
    """Connect, confirm safety, and create strategy."""
    client, account = _connect_live(logger)
    if not display_safety_warning(account, args, logger):
        raise RuntimeError("Safety check failed")
    logger.info("=" * 50 + "\nLIVE TRADING CONFIRMED\n" + "=" * 50)
    strategy = create_strategy(args, logger)
    return client, strategy


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_script_logging(args.verbose, "live_trading")
    _load_and_apply_config(args, logger)

    try:
        client, strategy = _perform_setup(args, logger)
        runner = _init_live_runner(args, strategy, client, logger)
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return 1

    print_live_status(args, logger)
    result = _run_live_trading_loop(runner, client, logger)
    logger.info("Live trading session ended")
    return result


if __name__ == "__main__":
    sys.exit(main())

