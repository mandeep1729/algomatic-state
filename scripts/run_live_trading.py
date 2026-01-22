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
from datetime import datetime
from getpass import getpass

import yaml

from src.execution.client import AlpacaClient
from src.execution.runner import TradingRunner, TradingRunnerConfig
from src.execution.risk_manager import RiskConfig
from src.strategy.momentum import MomentumStrategy, MomentumConfig
from src.strategy.state_enhanced import StateEnhancedStrategy, StateEnhancedConfig
from src.strategy.regime_filter import RegimeFilterConfig
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig
from src.strategy.position_sizer import PositionSizerConfig
from src.state.autoencoder import TemporalAutoencoder
from src.state.normalization import Normalizer
from src.state.clustering import RegimeClusterer
from src.utils.logging import setup_logging, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run LIVE trading with state-enhanced strategy",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Symbols to trade (required)",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML configuration file",
    )

    parser.add_argument(
        "--model",
        type=str,
        help="Path to trained autoencoder model (enables state-enhanced strategy)",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Signal generation interval in seconds (default: 60)",
    )

    parser.add_argument(
        "--warmup-bars",
        type=int,
        default=100,
        help="Number of historical bars for warmup (default: 100)",
    )

    parser.add_argument(
        "--long-threshold",
        type=float,
        default=0.001,
        help="Momentum threshold for long signals (default: 0.001)",
    )

    parser.add_argument(
        "--short-threshold",
        type=float,
        default=-0.001,
        help="Momentum threshold for short signals (default: -0.001)",
    )

    parser.add_argument(
        "--max-position-value",
        type=float,
        default=5000.0,
        help="Maximum position value in dollars (default: 5000)",
    )

    parser.add_argument(
        "--max-position-pct",
        type=float,
        default=0.10,
        help="Maximum position as %% of portfolio (default: 0.10)",
    )

    parser.add_argument(
        "--max-daily-loss-pct",
        type=float,
        default=0.01,
        help="Maximum daily loss as %% (default: 0.01)",
    )

    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=0.05,
        help="Maximum drawdown as %% (default: 0.05)",
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm that you want to trade with real money",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def load_yaml_config(path: str) -> dict:
    """Load configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def display_safety_warning(account, args, logger):
    """Display safety warning and get confirmation."""
    print("\n")
    print("=" * 70)
    print("!!! WARNING: LIVE TRADING MODE !!!")
    print("=" * 70)
    print("")
    print("This script will trade with REAL MONEY.")
    print("")
    print(f"  Account ID: {account.account_id}")
    print(f"  Account Equity: ${account.equity:,.2f}")
    print(f"  Buying Power: ${account.buying_power:,.2f}")
    print("")
    print("Trading Configuration:")
    print(f"  Symbols: {', '.join(args.symbols)}")
    print(f"  Max Position Value: ${args.max_position_value:,.2f}")
    print(f"  Max Position %%: {args.max_position_pct:.0%}")
    print(f"  Max Daily Loss: {args.max_daily_loss_pct:.0%}")
    print(f"  Max Drawdown: {args.max_drawdown_pct:.0%}")
    print("")
    print("Maximum potential loss per position: ${:,.2f}".format(
        min(args.max_position_value, account.equity * args.max_position_pct)
    ))
    print("")
    print("=" * 70)
    print("")

    if not args.confirm:
        print("ERROR: You must pass --confirm to acknowledge you want to trade live.")
        print("")
        return False

    # Additional confirmation
    print("Type 'LIVE TRADE' to confirm you want to proceed:")
    confirmation = input("> ").strip()

    if confirmation != "LIVE TRADE":
        print("Confirmation failed. Exiting.")
        return False

    print("")
    print("Starting live trading in 5 seconds... Press Ctrl+C to abort.")
    print("")

    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    return True


def create_strategy(args, logger):
    """Create the trading strategy based on arguments."""
    symbols = args.symbols

    if args.model:
        logger.info("Creating state-enhanced strategy")

        # Load models
        model_dir = Path(args.model).parent
        logger.info(f"Loading models from {model_dir}")

        autoencoder = TemporalAutoencoder.load(args.model)
        normalizer = Normalizer.load(str(model_dir / "normalizer.joblib"))
        clusterer = RegimeClusterer.load(str(model_dir / "clusterer.joblib"))

        # Create pattern matcher
        pattern_matcher = PatternMatcher(PatternMatchConfig(k_neighbors=10, backend="sklearn"))

        # Create config with conservative settings for live trading
        config = StateEnhancedConfig(
            momentum_config=MomentumConfig(
                symbols=symbols,
                long_threshold=args.long_threshold,
                short_threshold=args.short_threshold,
            ),
            regime_filter_config=RegimeFilterConfig(min_sharpe=0.5),  # More conservative
            pattern_match_config=PatternMatchConfig(k_neighbors=10, backend="sklearn"),
            position_sizer_config=PositionSizerConfig(
                base_size=args.max_position_value * 0.5,  # Start conservative
                max_size=args.max_position_value,
            ),
            enable_regime_filter=True,
            enable_pattern_matching=False,
            enable_dynamic_sizing=True,
        )

        return StateEnhancedStrategy(
            config,
            clusterer=clusterer,
            pattern_matcher=pattern_matcher,
        )

    else:
        logger.info("Creating baseline momentum strategy")

        config = MomentumConfig(
            symbols=symbols,
            long_threshold=args.long_threshold,
            short_threshold=args.short_threshold,
        )

        return MomentumStrategy(config)


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging - always verbose for live trading
    setup_logging(
        level="DEBUG" if args.verbose else "INFO",
        format="text",
    )
    logger = get_logger("live_trading")

    # Load YAML config if provided
    if args.config:
        logger.info(f"Loading config from {args.config}")
        yaml_config = load_yaml_config(args.config)
        if "strategy" in yaml_config:
            strategy_config = yaml_config["strategy"]
            if "long_threshold" in strategy_config:
                args.long_threshold = strategy_config["long_threshold"]
            if "short_threshold" in strategy_config:
                args.short_threshold = strategy_config["short_threshold"]

    # Connect to LIVE Alpaca
    try:
        client = AlpacaClient(paper=False)  # LIVE MODE
        account = client.get_account()
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca LIVE: {e}")
        logger.error("Make sure ALPACA_API_KEY and ALPACA_SECRET_KEY are set for your LIVE account")
        return 1

    # Safety confirmation
    if not display_safety_warning(account, args, logger):
        return 1

    logger.info("=" * 50)
    logger.info("LIVE TRADING CONFIRMED")
    logger.info("=" * 50)

    # Create strategy
    try:
        strategy = create_strategy(args, logger)
    except Exception as e:
        logger.error(f"Failed to create strategy: {e}")
        return 1

    # Create CONSERVATIVE risk config for live trading
    risk_config = RiskConfig(
        max_position_value=args.max_position_value,
        max_position_pct=args.max_position_pct,
        max_portfolio_concentration=0.15,  # Conservative
        max_daily_loss_pct=args.max_daily_loss_pct,
        max_drawdown_pct=args.max_drawdown_pct,
        max_symbols=5,  # Limit symbols in live trading
        min_buying_power_pct=0.20,  # Keep more buying power
        max_order_value=args.max_position_value,
        max_order_pct=0.05,  # Small orders
        check_pattern_day_trader=True,
        enabled=True,
    )

    # Create runner config
    runner_config = TradingRunnerConfig(
        symbols=args.symbols,
        signal_interval_seconds=args.interval,
        warmup_bars=args.warmup_bars,
        paper=False,  # LIVE MODE
        risk_config=risk_config,
        dry_run=False,
        log_dir=Path("logs/live_trading"),
    )

    # Create runner
    runner = TradingRunner(runner_config, strategy, client)

    # Register callbacks with enhanced logging for live trading
    def on_signal(signal):
        logger.info(
            f"[LIVE] Signal: {signal.symbol} {signal.direction.value.upper()} "
            f"strength={signal.strength:.2f} size=${signal.size:,.2f}"
        )

    def on_fill(update):
        logger.info(
            f"[LIVE] FILL: {update.order.symbol} "
            f"qty={update.fill_quantity} @ ${update.fill_price:.2f}"
        )
        # Print current account status after each fill
        try:
            acct = client.get_account()
            logger.info(f"[LIVE] Account equity: ${acct.equity:,.2f}")
        except Exception:
            pass

    def on_error(error):
        logger.error(f"[LIVE] ERROR: {error}")

    runner.on_signal(on_signal)
    runner.on_fill(on_fill)
    runner.on_error(on_error)

    # Initialize
    logger.info("Initializing live trading runner...")
    try:
        runner.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize runner: {e}")
        return 1

    # Display final status
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

    # Run trading loop
    try:
        runner.run()
    except KeyboardInterrupt:
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

    except Exception as e:
        logger.error(f"Critical error in live trading: {e}")
        logger.error("Initiating emergency stop...")
        runner.emergency_stop()
        return 1

    finally:
        # Print final status
        try:
            status = runner.get_status()
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
        except Exception:
            pass

    logger.info("Live trading session ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
