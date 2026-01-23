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

import numpy as np

from src.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig
from src.backtest.report import PerformanceReport
from src.features.pipeline import FeaturePipeline
from src.state.windows import create_windows
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig
from scripts.helpers.logging_setup import setup_script_logging
from scripts.helpers.data import load_multi_symbol_data
from scripts.helpers.state_models import load_all_models
from scripts.helpers.strategy_factory import (
    create_momentum_strategy,
    create_state_enhanced_config,
    create_state_enhanced_strategy,
)
from scripts.helpers.output import print_backtest_summary, save_all_results


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run strategy backtest")
    _add_data_args(parser)
    _add_strategy_args(parser)
    _add_engine_args(parser)
    return parser.parse_args()


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    """Add data-related arguments."""
    parser.add_argument("--data", type=str, required=True, help="Path to data file or directory")
    parser.add_argument("--model", type=str, help="Path to trained autoencoder model")
    parser.add_argument("--output", type=str, default="backtest_results", help="Output directory")


def _add_strategy_args(parser: argparse.ArgumentParser) -> None:
    """Add strategy-related arguments."""
    parser.add_argument("--long-threshold", type=float, default=0.001, help="Long signal threshold")
    parser.add_argument("--short-threshold", type=float, default=-0.001, help="Short signal threshold")
    parser.add_argument("--baseline-only", action="store_true", help="Use baseline strategy only")


def _add_engine_args(parser: argparse.ArgumentParser) -> None:
    """Add backtest engine arguments."""
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="Initial capital")
    parser.add_argument("--commission", type=float, default=0.005, help="Commission per share")
    parser.add_argument("--slippage", type=float, default=5.0, help="Slippage in bps")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def compute_all_features(data: dict, logger) -> dict:
    """Compute features for all symbols."""
    logger.info("Computing features...")
    pipeline = FeaturePipeline()
    features = {}
    for symbol, df in data.items():
        features[symbol] = pipeline.compute(df).dropna()
        logger.info(f"  {symbol}: {len(features[symbol])} rows")
    return features


def compute_symbol_states(features: dict, models, logger) -> dict:
    """Compute state representations for all symbols."""
    logger.info("Computing state representations...")
    states = {}
    window_size = models.autoencoder.config.window_size

    for symbol, feat_df in features.items():
        windows, _ = create_windows(feat_df.values, window_size=window_size, stride=1)
        windows_norm = models.normalizer.transform(windows)
        states[symbol] = models.autoencoder.encode(windows_norm)
        logger.info(f"  {symbol}: {len(states[symbol])} states")

    return states


def build_pattern_matcher(data: dict, features: dict, states: dict, window_size: int) -> PatternMatcher:
    """Build pattern matcher from historical states."""
    all_states, all_returns = [], []

    for symbol, feat_df in features.items():
        close = data[symbol]["close"].values
        returns = np.zeros(len(close))
        returns[:-1] = np.log(close[1:] / close[:-1])
        window_returns = returns[window_size - 1 : window_size - 1 + len(states[symbol])]
        all_states.append(states[symbol])
        all_returns.append(window_returns)

    combined_states = np.vstack(all_states)
    combined_returns = np.hstack(all_returns)

    pattern_matcher = PatternMatcher(PatternMatchConfig(k_neighbors=10, backend="sklearn"))
    pattern_matcher.fit(combined_states, combined_returns)
    return pattern_matcher


def create_baseline_strategy(args, symbols: list):
    """Create baseline momentum strategy."""
    return create_momentum_strategy(symbols, args.long_threshold, args.short_threshold)


def create_enhanced_strategy(args, symbols: list, models, pattern_matcher, logger):
    """Create state-enhanced strategy."""
    logger.info("Using state-enhanced strategy")
    config = create_state_enhanced_config(
        symbols=symbols,
        long_threshold=args.long_threshold,
        short_threshold=args.short_threshold,
        base_size=args.initial_capital * 0.1,
        enable_regime_filter=True,
        enable_pattern_matching=True,
        enable_dynamic_sizing=True,
    )
    return create_state_enhanced_strategy(config, models.clusterer, pattern_matcher)


def run_backtest_engine(data, strategy, features, states, args):
    """Run the backtest engine and return result."""
    engine_config = EngineConfig(
        initial_capital=args.initial_capital,
        commission_per_share=args.commission,
        slippage_bps=args.slippage,
    )
    engine = BacktestEngine(engine_config)
    return engine.run(data, strategy, features=features, states=states)


def _load_data(args, logger) -> tuple[dict, list]:
    """Load data and return data dict and symbols list."""
    logger.info(f"Loading data from {args.data}")
    data = load_multi_symbol_data(args.data)
    if not data:
        raise ValueError("No data files found")
    logger.info(f"Loaded {len(data)} symbols: {', '.join(data.keys())}")
    return data, list(data.keys())


def _create_baseline(args, symbols, features, logger) -> tuple:
    """Create baseline strategy and return (strategy, states)."""
    logger.info("Using baseline momentum strategy")
    return create_baseline_strategy(args, symbols), None


def _create_enhanced(args, symbols, data, features, logger) -> tuple:
    """Create enhanced strategy and return (strategy, states)."""
    models = load_all_models(args.model)
    logger.info(f"Loaded models from {Path(args.model).parent}")
    states = compute_symbol_states(features, models, logger)
    window_size = models.autoencoder.config.window_size
    matcher = build_pattern_matcher(data, features, states, window_size)
    strategy = create_enhanced_strategy(args, symbols, models, matcher, logger)
    return strategy, states


def _generate_report(result, args, logger) -> None:
    """Generate and save backtest report."""
    logger.info("Generating report...")
    report = PerformanceReport()
    report_data = report.generate(result)
    print_backtest_summary(report_data["summary"], logger)
    save_all_results(report_data, result, Path(args.output), logger)


def _setup_and_run_backtest(data, strategy, features, states, args, logger):
    """Run backtest and report generation."""
    logger.info("Running backtest...")
    result = run_backtest_engine(data, strategy, features, states, args)
    _generate_report(result, args, logger)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_script_logging(args.verbose, "run_backtest")

    try:
        data, symbols = _load_data(args, logger)
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return 1

    features = compute_all_features(data, logger)
    if args.baseline_only or not args.model:
        strategy, states = _create_baseline(args, symbols, features, logger)
    else:
        strategy, states = _create_enhanced(args, symbols, data, features, logger)

    _setup_and_run_backtest(data, strategy, features, states, args, logger)
    logger.info("Backtest complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

