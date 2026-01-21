#!/usr/bin/env python
"""Run strategy backtest.

Usage:
    python scripts/run_backtest.py --data data/raw/AAPL_1Min.parquet
    python scripts/run_backtest.py --data data/raw/ --model models/autoencoder.pt
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json

import pandas as pd

from src.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig
from src.backtest.report import PerformanceReport, ReportConfig
from src.features.pipeline import FeaturePipeline
from src.state.windows import create_windows
from src.state.normalization import Normalizer
from src.state.autoencoder import TemporalAutoencoder
from src.state.clustering import RegimeClusterer
from src.strategy.momentum import MomentumStrategy, MomentumConfig
from src.strategy.state_enhanced import StateEnhancedStrategy, StateEnhancedConfig
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig
from src.strategy.regime_filter import RegimeFilterConfig
from src.strategy.position_sizer import PositionSizerConfig
from src.utils.logging import setup_logging, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run strategy backtest",
    )

    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to data file or directory",
    )

    parser.add_argument(
        "--model",
        type=str,
        help="Path to trained autoencoder model (enables state-enhanced strategy)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="backtest_results",
        help="Output directory for results (default: backtest_results)",
    )

    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000.0,
        help="Initial portfolio capital (default: 100000)",
    )

    parser.add_argument(
        "--commission",
        type=float,
        default=0.005,
        help="Commission per share (default: 0.005)",
    )

    parser.add_argument(
        "--slippage",
        type=float,
        default=5.0,
        help="Slippage in basis points (default: 5)",
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
        "--baseline-only",
        action="store_true",
        help="Run baseline strategy only (no state enhancements)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def load_data(path: str) -> dict[str, pd.DataFrame]:
    """Load data from file or directory.

    Args:
        path: Path to file or directory

    Returns:
        Dictionary of DataFrames by symbol
    """
    path = Path(path)
    data = {}

    if path.is_file():
        symbol = path.stem.split("_")[0]
        if path.suffix == ".parquet":
            data[symbol] = pd.read_parquet(path)
        elif path.suffix == ".csv":
            data[symbol] = pd.read_csv(path, index_col=0, parse_dates=True)

    elif path.is_dir():
        for file in path.glob("*.parquet"):
            symbol = file.stem.split("_")[0]
            data[symbol] = pd.read_parquet(file)

    return data


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(
        level="DEBUG" if args.verbose else "INFO",
        format="text",
    )
    logger = get_logger("run_backtest")

    # Load data
    logger.info(f"Loading data from {args.data}")
    try:
        data = load_data(args.data)
        if not data:
            logger.error("No data files found")
            return 1
        logger.info(f"Loaded {len(data)} symbols: {', '.join(data.keys())}")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return 1

    # Compute features
    logger.info("Computing features...")
    pipeline = FeaturePipeline()
    features = {}
    for symbol, df in data.items():
        features[symbol] = pipeline.compute(df).dropna()
        logger.info(f"  {symbol}: {len(features[symbol])} rows")

    # Initialize strategy
    if args.baseline_only or not args.model:
        logger.info("Using baseline momentum strategy")
        config = MomentumConfig(
            symbols=list(data.keys()),
            long_threshold=args.long_threshold,
            short_threshold=args.short_threshold,
        )
        strategy = MomentumStrategy(config)
        states = None

    else:
        logger.info("Using state-enhanced strategy")

        # Load models
        model_dir = Path(args.model).parent
        logger.info(f"Loading models from {model_dir}")

        autoencoder = TemporalAutoencoder.load(args.model)
        normalizer = Normalizer.load(str(model_dir / "normalizer.joblib"))
        clusterer = RegimeClusterer.load(str(model_dir / "clusterer.joblib"))

        # Compute states
        logger.info("Computing state representations...")
        states = {}
        window_size = autoencoder.config.window_size

        for symbol, feat_df in features.items():
            windows, _ = create_windows(
                feat_df.values,
                window_size=window_size,
                stride=1,
            )
            windows_norm = normalizer.transform(windows)
            symbol_states = autoencoder.encode(windows_norm)
            states[symbol] = symbol_states
            logger.info(f"  {symbol}: {len(symbol_states)} states")

        # Create pattern matcher
        logger.info("Building pattern matcher...")
        all_states = []
        all_returns = []
        for symbol, feat_df in features.items():
            close = data[symbol]["close"].values
            returns = np.zeros(len(close))
            returns[:-1] = np.log(close[1:] / close[:-1])
            window_returns = returns[window_size - 1 : window_size - 1 + len(states[symbol])]
            all_states.append(states[symbol])
            all_returns.append(window_returns)

        import numpy as np
        combined_states = np.vstack(all_states)
        combined_returns = np.hstack(all_returns)

        pattern_matcher = PatternMatcher(PatternMatchConfig(k_neighbors=10, backend="sklearn"))
        pattern_matcher.fit(combined_states, combined_returns)

        # Create strategy
        config = StateEnhancedConfig(
            momentum_config=MomentumConfig(
                symbols=list(data.keys()),
                long_threshold=args.long_threshold,
                short_threshold=args.short_threshold,
            ),
            regime_filter_config=RegimeFilterConfig(min_sharpe=0.0),
            pattern_match_config=PatternMatchConfig(k_neighbors=10, backend="sklearn"),
            position_sizer_config=PositionSizerConfig(
                base_size=args.initial_capital * 0.1,
            ),
            enable_regime_filter=True,
            enable_pattern_matching=True,
            enable_dynamic_sizing=True,
        )
        strategy = StateEnhancedStrategy(
            config,
            clusterer=clusterer,
            pattern_matcher=pattern_matcher,
        )

    # Configure backtest engine
    engine_config = EngineConfig(
        initial_capital=args.initial_capital,
        commission_per_share=args.commission,
        slippage_bps=args.slippage,
    )
    engine = BacktestEngine(engine_config)

    # Run backtest
    logger.info("Running backtest...")
    result = engine.run(data, strategy, features=features, states=states)

    # Generate report
    logger.info("Generating report...")
    report = PerformanceReport()
    report_data = report.generate(result)

    # Print summary
    summary = report_data["summary"]
    logger.info("\n" + "=" * 50)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 50)
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
    logger.info("=" * 50)

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON report
    report_path = output_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)
    logger.info(f"Saved report to {report_path}")

    # Save equity curve
    equity_path = output_dir / "equity_curve.csv"
    result.equity_curve.to_csv(equity_path)
    logger.info(f"Saved equity curve to {equity_path}")

    # Save trades
    if result.trades:
        trades_path = output_dir / "trades.csv"
        trades_df = pd.DataFrame([t.to_dict() for t in result.trades])
        trades_df.to_csv(trades_path, index=False)
        logger.info(f"Saved trades to {trades_path}")

    logger.info("Backtest complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
