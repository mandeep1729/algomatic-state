"""Feature registry and configuration loading."""

from pathlib import Path
from typing import Any

import yaml

from .anchor import AnchorFeatureCalculator
from .base import BaseFeatureCalculator
from .intrabar import IntrabarFeatureCalculator
from .market_context import MarketContextFeatureCalculator
from .returns import ReturnFeatureCalculator
from .time_of_day import TimeOfDayFeatureCalculator
from .volatility import VolatilityFeatureCalculator
from .volume import VolumeFeatureCalculator


# Global registry of calculator classes
_CALCULATOR_REGISTRY: dict[str, type[BaseFeatureCalculator]] = {}


def register_calculator(name: str):
    """Decorator to register a feature calculator class.

    Args:
        name: Registry name for the calculator

    Returns:
        Decorator function
    """

    def decorator(cls: type[BaseFeatureCalculator]) -> type[BaseFeatureCalculator]:
        _CALCULATOR_REGISTRY[name] = cls
        return cls

    return decorator


def get_calculator(name: str) -> type[BaseFeatureCalculator]:
    """Get a calculator class by name.

    Args:
        name: Registry name of the calculator

    Returns:
        Calculator class

    Raises:
        KeyError: If calculator name is not registered
    """
    if name not in _CALCULATOR_REGISTRY:
        raise KeyError(
            f"Calculator '{name}' not found. Available: {list(_CALCULATOR_REGISTRY.keys())}"
        )
    return _CALCULATOR_REGISTRY[name]


def list_calculators() -> list[str]:
    """List all registered calculator names.

    Returns:
        List of registered calculator names
    """
    return list(_CALCULATOR_REGISTRY.keys())


# Register all built-in calculators
register_calculator("returns")(ReturnFeatureCalculator)
register_calculator("volatility")(VolatilityFeatureCalculator)
register_calculator("volume")(VolumeFeatureCalculator)
register_calculator("intrabar")(IntrabarFeatureCalculator)
register_calculator("anchor")(AnchorFeatureCalculator)
register_calculator("time_of_day")(TimeOfDayFeatureCalculator)
register_calculator("market_context")(MarketContextFeatureCalculator)

# TA-Lib indicators (optional, requires TA-Lib installation)
try:
    import talib  # Check if actual TA-Lib library is available
    from .talib_indicators import TALibIndicatorCalculator
    register_calculator("talib_indicators")(TALibIndicatorCalculator)
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

# Pandas-TA indicators (pure Python alternative)
try:
    import pandas_ta  # Check if pandas_ta is available
    from .pandas_ta_indicators import PandasTAIndicatorCalculator
    register_calculator("pandas_ta_indicators")(PandasTAIndicatorCalculator)
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False


def load_feature_config(config_path: str | Path) -> dict[str, Any]:
    """Load feature configuration from YAML file.

    Config format:
    ```yaml
    calculators:
      returns:
        enabled: true
        params:
          long_window: 60
      volatility:
        enabled: true
        params:
          short_window: 15
          long_window: 60
    pipeline:
      drop_na: true
      drop_leading: true
    ```

    Args:
        config_path: Path to YAML config file

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file does not exist
        yaml.YAMLError: If config file is invalid YAML
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    return config


def create_calculators_from_config(
    config: dict[str, Any]
) -> list[BaseFeatureCalculator]:
    """Create calculator instances from configuration.

    Args:
        config: Configuration dictionary (from load_feature_config)

    Returns:
        List of instantiated calculator objects
    """
    calculators = []
    calc_configs = config.get("calculators", {})

    for name, calc_config in calc_configs.items():
        if not calc_config.get("enabled", True):
            continue

        calc_class = get_calculator(name)
        params = calc_config.get("params", {})
        calculators.append(calc_class(**params))

    return calculators


def get_default_calculators(
    include_market_context: bool = False,
    include_ta_indicators: bool = True,
) -> list[BaseFeatureCalculator]:
    """Get default set of feature calculators.

    Args:
        include_market_context: Whether to include market context calculator
                                (requires market_df)
        include_ta_indicators: Whether to include TA-Lib/pandas-ta indicators

    Returns:
        List of default calculator instances
    """
    calculators = [
        ReturnFeatureCalculator(),
        VolatilityFeatureCalculator(),
        VolumeFeatureCalculator(),
        IntrabarFeatureCalculator(),
        AnchorFeatureCalculator(),
        TimeOfDayFeatureCalculator(),
    ]

    if include_market_context:
        calculators.append(MarketContextFeatureCalculator())

    # Add TA indicators (prefer TA-Lib, fallback to pandas-ta)
    if include_ta_indicators:
        if TALIB_AVAILABLE:
            ta_calc_class = get_calculator("talib_indicators")
            calculators.append(ta_calc_class())
        elif PANDAS_TA_AVAILABLE:
            ta_calc_class = get_calculator("pandas_ta_indicators")
            calculators.append(ta_calc_class())

    return calculators
