
"""Tests for Feature Pipeline."""

import pandas as pd
import pytest

from src.features.pipeline import FeaturePipeline, get_minimal_features
from src.features.returns import ReturnFeatureCalculator
from src.features.volatility import VolatilityFeatureCalculator


class TestFeaturePipeline:
    """Tests for FeaturePipeline."""

    def test_init_default(self):
        """Test default initialization."""
        pipeline = FeaturePipeline.default()
        # 6 base calculators + TA-Lib/pandas-ta if available
        assert len(pipeline.calculators) >= 6
        assert not pipeline.config.include_market_context

    def test_init_with_market_context(self):
        """Test initialization with market context."""
        pipeline = FeaturePipeline.default(include_market_context=True)
        # 6 base + market_context + TA-Lib/pandas-ta if available
        assert len(pipeline.calculators) >= 7
        assert pipeline.config.include_market_context

    def test_feature_names(self):
        """Test feature name retrieval."""
        pipeline = FeaturePipeline(calculators=[
            ReturnFeatureCalculator(),
            VolatilityFeatureCalculator() 
        ])
        names = pipeline.feature_names
        assert "r1" in names
        assert "rv_60" in names
        assert "vol1" not in names # Volume not included

    def test_max_lookback(self):
        """Test max lookback calculation."""
        pipeline = FeaturePipeline(calculators=[
            ReturnFeatureCalculator(long_window=60),
            VolatilityFeatureCalculator(long_window=20)
        ])
        # Returns calc has lookback 61 (window + 1)
        assert pipeline.max_lookback == 61

    def test_compute_simple(self, ohlcv_df: pd.DataFrame):
        """Test simple computation flow."""
        pipeline = FeaturePipeline(calculators=[
            ReturnFeatureCalculator(),
            VolatilityFeatureCalculator()
        ])
        
        result = pipeline.compute(ohlcv_df)
        
        # Check columns present
        assert "r1" in result.columns
        assert "rv_60" in result.columns
        
        # Check no index rows were dropped (if drop_leading_na is True by default, it might drop)
        # If drop_leading_na is True, we expect fewer rows
        if pipeline.config.drop_leading_na:
            assert len(result) < len(ohlcv_df)
            assert not result.isna().any().any()
        else:
            assert len(result) == len(ohlcv_df)

    def test_compute_dependency_flow(self, ohlcv_df: pd.DataFrame):
        """Test that r1 is passed to volatility calculator."""
        # This is implicit, but we can verify that volatility features are computed
        # correctly without crashing (which would happen if r1 wasn't available if we didn't calculate it inside vol calc)
        # Actually vol calc computes r1 if not provided. Use pipeline to provide it.
        
        pipeline = FeaturePipeline(calculators=[
            ReturnFeatureCalculator(),
            VolatilityFeatureCalculator()
        ])
        
        result = pipeline.compute(ohlcv_df)
        assert "trend_strength" in result.columns # Uses rv_60
        assert "rv_60" in result.columns # Uses r1

    def test_compute_subset(self, ohlcv_df: pd.DataFrame):
        """Test computing a subset of features."""
        pipeline = FeaturePipeline.default()
        
        # Request only r1 and rv_60
        subset = pipeline.compute_subset(ohlcv_df, feature_names=["r1", "rv_60"])
        
        assert list(subset.columns) == ["r1", "rv_60"]

    def test_get_minimal_features(self):
        """Test getting minimal feature set."""
        features = get_minimal_features()
        assert "r1" in features
        assert "tod_sin" in features
        assert len(features) > 10

