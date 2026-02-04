
"""Tests for Feature Registry."""

import pytest
from src.features.registry import (
    get_calculator,
    list_calculators,
    create_calculators_from_config,
    get_default_calculators,
    ReturnFeatureCalculator,
    VolatilityFeatureCalculator
)

class TestFeatureRegistry:
    """Tests for feature registry functions."""

    def test_list_calculators(self):
        """Test listing available calculators."""
        names = list_calculators()
        expected = [
            "returns", "volatility", "volume", "intrabar", 
            "anchor", "time_of_day", "market_context"
        ]
        for name in expected:
            assert name in names

    def test_get_calculator_success(self):
        """Test getting a registered calculator."""
        cls = get_calculator("returns")
        assert cls == ReturnFeatureCalculator

    def test_get_calculator_failure(self):
        """Test getting an unregistered calculator."""
        with pytest.raises(KeyError):
            get_calculator("non_existent_calc")

    def test_create_calculators_from_config(self):
        """Test creating calculators from config dict."""
        config = {
            "calculators": {
                "returns": {
                    "enabled": True,
                    "params": {"long_window": 100}
                },
                "volatility": {
                    "enabled": False
                }
            }
        }
        
        calcs = create_calculators_from_config(config)
        
        # Should contain returns, but not volatility
        assert len(calcs) == 1
        assert isinstance(calcs[0], ReturnFeatureCalculator)
        assert calcs[0].long_window == 100

    def test_get_default_calculators(self):
        """Test getting default calculators."""
        calcs = get_default_calculators(include_market_context=False)
        # 6 base calculators + TA-Lib/pandas-ta if available
        assert len(calcs) >= 6
        types = [type(c) for c in calcs]
        assert ReturnFeatureCalculator in types
        assert VolatilityFeatureCalculator in types

        calcs_with_market = get_default_calculators(include_market_context=True)
        assert len(calcs_with_market) == len(calcs) + 1
