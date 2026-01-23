#!/usr/bin/env python
"""Run paper trading with the state-enhanced strategy.

Usage:
    python scripts/run_paper_trading.py --symbols AAPL MSFT
    python scripts/run_paper_trading.py --symbols AAPL --model models/autoencoder.pt
    python scripts/run_paper_trading.py --config config/trading.yaml --dry-run
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

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
    parser = argparse.ArgumentParser(description="Run paper trading with state-enhanced strategy")
    _add_symbol_args(parser)
    _add_strategy_args(parser)
    _add_risk_args(parser)
    _add_runtime_args(parser)
    return parser.parse_args()


def _add_symbol_args(parser: argparse.ArgumentParser) -> None:
    """Add symbol-related arguments."""
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], help="Symbols to trade")
    parser.add_argument("--config", type=str, help="Path to YAML configuration file")


def _add_strategy_args(parser: argparse.ArgumentParser) -> None:
    """Add strategy-related arguments."""
    parser.add_argument("--model", type=str, help="Path to trained autoencoder model")
    parser.add_argument("--long-threshold", type=float, default=0.001, help="Long signal threshold")
    parser.add_argument("--short-threshold", type=float, default=-0.001, help="Short signal threshold")


def _add_risk_args(parser: argparse.ArgumentParser) -> None:
    """Add risk management arguments."""
    parser.add_argument("--max-position-pct", type=float, default=0.20, help="Max position as % of portfolio")
    parser.add_argument("--max-daily-loss-pct", type=float, default=0.02, help="Max daily loss as %")


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    """Add runtime arguments."""
    parser.add_argument("--interval", type=int, default=60, help="Signal interval in seconds")
    parser.add_argument("--warmup-bars", type=int, default=100, help="Historical bars for warmup")
    parser.add_argument("--dry-run", action="store_true", help="Generate signals but don't submit orders")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def load_yaml_config(path: str) -> dict:
    """Load configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def apply_yaml_config(args: argparse.Namespace, yaml_config: dict) -> None:
    """Apply YAML config values to args."""
    if "symbols" in yaml_config and not args.symbols:
        args.symbols = yaml_config["symbols"]
    if "strategy" in yaml_config:
        strategy_cfg = yaml_config["strategy"]
        if "long_threshold" in strategy_cfg:
            args.long_threshold = strategy_cfg["long_threshold"]
        if "short_threshold" in strategy_cfg:
            args.short_threshold = strategy_cfg["short_threshold"]


def connect_alpaca(paper: bool, logger) -> tuple:
    """Connect to Alpaca and return client and account."""
    client = AlpacaClient(paper=paper)
    account = client.get_account()
    logger.info(f"Connected to Alpaca {'paper' if paper else 'live'} trading")
    logger.info(f"Account ID: {account.account_id}")
    logger.info(f"Equity: ${account.equity:,.2f}")
    logger.info(f"Buying Power: ${account.buying_power:,.2f}")
    return client, account


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
        base_size=10000.0,
        enable_regime_filter=True,
        enable_pattern_matching=False,
        enable_dynamic_sizing=True,
    )
    return create_state_enhanced_strategy(config, models.clusterer, create_pattern_matcher())


def create_risk_config(args, account_equity: float) -> RiskConfig:
    """Create risk configuration."""
    return RiskConfig(
        max_position_pct=args.max_position_pct,
        max_daily_loss_pct=args.max_daily_loss_pct,
        max_position_value=account_equity * args.max_position_pct,
        max_order_value=account_equity * 0.10,
    )


def create_runner_config(args, risk_config: RiskConfig) -> TradingRunnerConfig:
    """Create trading runner configuration."""
    return TradingRunnerConfig(
        symbols=args.symbols,
        signal_interval_seconds=args.interval,
        warmup_bars=args.warmup_bars,
        paper=True,
        risk_config=risk_config,
        dry_run=args.dry_run,
    )


def _on_signal_callback(logger):
    """Create signal callback."""
    def on_signal(signal):
        logger.info(
            f"Signal generated",
            extra={"symbol": signal.symbol, "direction": str(signal.direction),
                   "strength": signal.strength, "size": signal.size},
        )
    return on_signal


def _on_fill_callback(logger):
    """Create fill callback."""
    def on_fill(update):
        logger.info(
            f"Fill received",
            extra={"symbol": update.order.symbol, "quantity": update.fill_quantity,
                   "price": update.fill_price},
        )
    return on_fill


def register_callbacks(runner, logger) -> None:
    """Register signal. fill, and error callbacks."""
    runner.on_signal(_on_signal_callback(logger))
    runner.on_fill(_on_fill_callback(logger))
    runner.on_error(lambda error: logger.error(f"Trading error: {error}"))


def _init_runner_and_callbacks(args, account, strategy, client, logger):
    """Initialize runner and register callbacks."""
    runner = _setup_runner(args, account, strategy, client)
    register_callbacks(runner, logger)
    logger.info("Initializing trading runner...")
    runner.initialize()
    return runner


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_script_logging(args.verbose, "paper_trading")
    _load_and_apply_config(args, logger)

    try:
        client, account = connect_alpaca(paper=True, logger=logger)
        strategy = create_strategy(args, logger)
        runner = _init_runner_and_callbacks(args, account, strategy, client, logger)
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return 1

    print_trading_status(args, logger)
    return _run_trading_loop(runner, logger)


if __name__ == "__main__":
    sys.exit(main())

