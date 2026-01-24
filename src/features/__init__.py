"""Feature engineering module for computing technical indicators from OHLCV data.

This module provides a modular system for computing ~30 technical indicators
organized into groups: returns, volatility, volume, intrabar, anchor,
time-of-day, and market context.

Quick Start:
    >>> from src.features import FeaturePipeline
    >>> pipeline = FeaturePipeline.default()
    >>> features = pipeline.compute(ohlcv_df)

For minimal feature set:
    >>> from src.features import FeaturePipeline, get_minimal_features
    >>> pipeline = FeaturePipeline.default()
    >>> features = pipeline.compute_subset(ohlcv_df, get_minimal_features())
"""

from .anchor import AnchorFeatureCalculator
from .base import (
    EPS,
    BaseFeatureCalculator,
    FeatureSpec,
    ema,
    log_return,
    rolling_beta,
    rolling_regression_slope,
    safe_divide,
    zscore,
)
from .intrabar import IntrabarFeatureCalculator
from .market_context import MarketContextFeatureCalculator
from .pipeline import FeaturePipeline, PipelineConfig, get_minimal_features
from .registry import (
    create_calculators_from_config,
    get_calculator,
    get_default_calculators,
    list_calculators,
    load_feature_config,
    register_calculator,
)
from .returns import ReturnFeatureCalculator
from .time_of_day import TimeOfDayFeatureCalculator
from .volatility import VolatilityFeatureCalculator
from .volume import VolumeFeatureCalculator

# Optional TA-Lib calculator (requires TA-Lib installation)
try:
    from .talib_indicators import TALibIndicatorCalculator, TALIB_AVAILABLE
except ImportError:
    TALibIndicatorCalculator = None  # type: ignore
    TALIB_AVAILABLE = False

__all__ = [
    # Constants
    "EPS",
    # Base classes
    "BaseFeatureCalculator",
    "FeatureSpec",
    # Utility functions
    "safe_divide",
    "zscore",
    "log_return",
    "rolling_regression_slope",
    "ema",
    "rolling_beta",
    # Calculators
    "ReturnFeatureCalculator",
    "VolatilityFeatureCalculator",
    "VolumeFeatureCalculator",
    "IntrabarFeatureCalculator",
    "AnchorFeatureCalculator",
    "TimeOfDayFeatureCalculator",
    "MarketContextFeatureCalculator",
    # Pipeline
    "FeaturePipeline",
    "PipelineConfig",
    "get_minimal_features",
    # Registry
    "register_calculator",
    "get_calculator",
    "list_calculators",
    "load_feature_config",
    "create_calculators_from_config",
    "get_default_calculators",
    # TA-Lib (optional)
    "TALibIndicatorCalculator",
    "TALIB_AVAILABLE",
]
