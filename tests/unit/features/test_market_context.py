
"""Tests for Market Context features."""

import numpy as np
import pandas as pd
import pytest

from src.features.market_context import MarketContextFeatureCalculator


class TestMarketContextFeatureCalculator:
    """Tests for MarketContextFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> MarketContextFeatureCalculator:
        return MarketContextFeatureCalculator()

    def test_feature_specs(self, calculator: MarketContextFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        names = [s.name for s in specs]
        expected_names = [
            "mkt_r5", "mkt_r15", "mkt_rv_60", "beta_60", "resid_rv_60"
        ]
        for name in expected_names:
            assert name in names

    def test_compute_without_market_df(self, calculator: MarketContextFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute raises ValueError if market_df is missing."""
        with pytest.raises(ValueError, match="market_df is required"):
            calculator.compute(ohlcv_df)

    def test_output_columns(self, calculator: MarketContextFeatureCalculator, ohlcv_df: pd.DataFrame, market_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df, market_df=market_df)
        expected_columns = [
            "mkt_r5", "mkt_r15", "mkt_rv_60", "beta_60", "resid_rv_60"
        ]
        assert list(result.columns) == expected_columns
        assert len(result) == len(ohlcv_df)

    def test_mkt_returns(self, calculator: MarketContextFeatureCalculator, ohlcv_df: pd.DataFrame, market_df: pd.DataFrame):
        """Test market return features."""
        result = calculator.compute(ohlcv_df, market_df=market_df)
        
        mkt_close = market_df["close"]
        expected_r5 = np.log(mkt_close / mkt_close.shift(5))
        
        # Check alignment
        assert np.allclose(result["mkt_r5"].dropna(), expected_r5.dropna())

    def test_beta_calculation_correlated(self):
        """Test beta calculation with correlated assets."""
        calc = MarketContextFeatureCalculator(long_window=10)
        
        # Perfect correlation: asset = 2 * market
        market_returns = np.random.randn(20) * 0.01
        asset_returns = 2.0 * market_returns
        
        # Construct price series
        market_close = 100 * np.exp(np.cumsum(market_returns))
        asset_close = 100 * np.exp(np.cumsum(asset_returns))
        
        market_df = pd.DataFrame({"close": market_close}, index=pd.date_range("2024-01-01", periods=20, freq="1min"))
        asset_df = pd.DataFrame({"close": asset_close}, index=pd.date_range("2024-01-01", periods=20, freq="1min"))
        
        result = calc.compute(asset_df, market_df=market_df)
        
        # Beta should be close to 2.0
        assert np.isclose(result["beta_60"].iloc[-1], 2.0, atol=0.1)
        # Residual vol should be low
        assert result["resid_rv_60"].iloc[-1] < 1e-3

    def test_beta_calculation_uncorrelated(self):
        """Test beta calculation with uncorrelated assets."""
        calc = MarketContextFeatureCalculator(long_window=50) # Larger window for stability
        
        np.random.seed(42)
        market_returns = np.random.randn(100) * 0.01
        asset_returns = np.random.randn(100) * 0.01 # Random noise
        
        market_close = 100 * np.exp(np.cumsum(market_returns))
        asset_close = 100 * np.exp(np.cumsum(asset_returns))
        
        market_df = pd.DataFrame({"close": market_close}, index=pd.date_range("2024-01-01", periods=100, freq="1min"))
        asset_df = pd.DataFrame({"close": asset_close}, index=pd.date_range("2024-01-01", periods=100, freq="1min"))
        
        result = calc.compute(asset_df, market_df=market_df)
        
        # Beta should be close to 0
        assert abs(result["beta_60"].iloc[-1]) < 0.5
