"""Feature pipeline orchestration."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import get_settings
from .base import BaseFeatureCalculator, FeatureSpec
from .registry import (
    create_calculators_from_config,
    get_default_calculators,
    load_feature_config,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for feature pipeline.

    Attributes:
        drop_leading_na: Whether to drop leading rows with NaN (from lookback)
        include_market_context: Whether to include market context features
    """

    drop_leading_na: bool = True
    include_market_context: bool = False


class FeaturePipeline:
    """Orchestrates feature computation across multiple calculators.

    Handles:
    - Running calculators in dependency order
    - Passing intermediate results between calculators (e.g., r1, rv_60)
    - Optionally dropping leading NaN rows from lookback periods

    Example:
        >>> pipeline = FeaturePipeline.default()
        >>> features = pipeline.compute(ohlcv_df)
        >>> print(features.columns.tolist())
    """

    def __init__(
        self,
        calculators: list[BaseFeatureCalculator],
        config: PipelineConfig | None = None,
    ):
        """Initialize FeaturePipeline.

        Args:
            calculators: List of feature calculators to run
            config: Pipeline configuration (defaults to PipelineConfig())
        """
        self.calculators = calculators
        self.config = config or PipelineConfig()

    @classmethod
    def default(cls, include_market_context: bool = False) -> "FeaturePipeline":
        """Create a pipeline with default calculators.

        Args:
            include_market_context: Whether to include market context features

        Returns:
            FeaturePipeline with default calculators
        """
        calculators = get_default_calculators(include_market_context=include_market_context)
        config = PipelineConfig(include_market_context=include_market_context)
        return cls(calculators=calculators, config=config)

    @classmethod
    def from_config(cls, config_path: str | Path) -> "FeaturePipeline":
        """Create a pipeline from YAML configuration file.

        Args:
            config_path: Path to YAML config file

        Returns:
            FeaturePipeline configured from file
        """
        config_dict = load_feature_config(config_path)
        calculators = create_calculators_from_config(config_dict)

        pipeline_config = config_dict.get("pipeline", {})
        config = PipelineConfig(
            drop_leading_na=pipeline_config.get("drop_leading_na", True),
            include_market_context=pipeline_config.get("include_market_context", False),
        )

        return cls(calculators=calculators, config=config)

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        """Get all feature specifications from all calculators.

        Returns:
            Combined list of feature specs from all calculators
        """
        specs = []
        for calc in self.calculators:
            specs.extend(calc.feature_specs)
        return specs

    @property
    def feature_names(self) -> list[str]:
        """Get all feature column names.

        Returns:
            List of feature column names
        """
        return [spec.name for spec in self.feature_specs]

    @property
    def max_lookback(self) -> int:
        """Maximum lookback period across all calculators.

        Returns:
            Maximum lookback period in bars
        """
        if not self.calculators:
            return 0
        return max(calc.max_lookback for calc in self.calculators)

    def compute(
        self,
        df: pd.DataFrame,
        market_df: pd.DataFrame | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Compute all features from OHLCV data.

        The pipeline handles dependencies between calculators:
        - Computes r1 from returns calculator for volatility
        - Computes rv_60 from volatility calculator for returns (trend_strength)

        Args:
            df: DataFrame with datetime index and columns: open, high, low, close, volume
            market_df: Optional market benchmark data (required for market context features)
            **kwargs: Additional arguments passed to calculators

        Returns:
            DataFrame with all computed feature columns

        Raises:
            ValueError: If market_df is required but not provided
        """
        logger.info(f"Computing features for {len(df)} rows using {len(self.calculators)} calculators")
        result = pd.DataFrame(index=df.index)

        # Track intermediate values for cross-calculator dependencies
        intermediates: dict[str, pd.Series] = {}

        for calc in self.calculators:
            calc_name = calc.__class__.__name__
            logger.debug(f"Running calculator: {calc_name}")

            # Build kwargs for this calculator
            calc_kwargs = dict(kwargs)

            # Handle market context calculator
            if calc_name == "MarketContextFeatureCalculator":
                if market_df is None:
                    if self.config.include_market_context:
                        raise ValueError(
                            "market_df is required for MarketContextFeatureCalculator"
                        )
                    continue  # Skip if market context not required
                calc_kwargs["market_df"] = market_df

            # Pass intermediate values
            if "r1" in intermediates:
                calc_kwargs["r1"] = intermediates["r1"]
            if "rv_60" in intermediates:
                calc_kwargs["rv_60"] = intermediates["rv_60"]

            # Compute features
            features = calc.compute(df, **calc_kwargs)
            logger.debug(f"{calc_name} computed {len(features.columns)} features")

            # Store intermediates for dependent calculators
            if "r1" in features.columns:
                intermediates["r1"] = features["r1"]
            if "rv_60" in features.columns:
                intermediates["rv_60"] = features["rv_60"]

            # Add features to result
            for col in features.columns:
                result[col] = features[col]

        # Drop leading NaN rows if configured
        if self.config.drop_leading_na:
            first_valid = result.apply(lambda x: x.first_valid_index()).max()
            if first_valid is not None:
                dropped = len(result) - len(result.loc[first_valid:])
                result = result.loc[first_valid:]
                logger.debug(f"Dropped {dropped} leading rows with NaN values")

        logger.info(f"Feature computation complete: {len(result)} rows, {len(result.columns)} features")
        return result

    def compute_incremental(
        self,
        df: pd.DataFrame,
        new_bars: int,
        market_df: pd.DataFrame | None = None,
        lookback_buffer: int | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Compute features only for new bars, using minimal lookback context.

        Slices the input DataFrame to only include enough rows for
        ``max_lookback + lookback_buffer + new_bars``, computes features on
        that slice, then trims the output to only the ``new_bars`` rows.
        This avoids recomputing features for the entire history.

        When ``new_bars >= len(df)`` (or when the required context window
        exceeds the DataFrame length), this falls through to a full
        ``compute()`` call with no trimming.

        Args:
            df: Full DataFrame with datetime index and OHLCV columns.
            new_bars: Number of new (most recent) bars that need features.
            market_df: Optional market benchmark data.
            lookback_buffer: Extra rows beyond ``max_lookback`` to include
                for safety.  Defaults to ``FeatureConfig.lookback_buffer``
                from settings (typically 100).
            **kwargs: Additional arguments forwarded to ``compute()``.

        Returns:
            DataFrame with features for (at most) the ``new_bars`` most
            recent rows.
        """
        total_rows = len(df)

        if new_bars <= 0:
            logger.debug("compute_incremental called with new_bars=%d, returning empty", new_bars)
            return pd.DataFrame()

        if lookback_buffer is None:
            try:
                lookback_buffer = get_settings().features.lookback_buffer
            except Exception:
                lookback_buffer = 100  # default from FeatureConfig
                logger.debug(
                    "Could not load settings for lookback_buffer, using default=%d",
                    lookback_buffer,
                )

        required_context = self.max_lookback + lookback_buffer + new_bars

        if required_context >= total_rows:
            logger.debug(
                "compute_incremental: required context %d >= total rows %d, "
                "computing full DataFrame",
                required_context, total_rows,
            )
            return self.compute(df, market_df=market_df, **kwargs)

        # Slice to only the rows needed for correct computation
        input_slice = df.iloc[-required_context:]
        logger.info(
            "compute_incremental: sliced %d -> %d rows "
            "(new_bars=%d, max_lookback=%d, buffer=%d)",
            total_rows, len(input_slice), new_bars, self.max_lookback, lookback_buffer,
        )

        features = self.compute(input_slice, market_df=market_df, **kwargs)

        if features.empty:
            return features

        # Trim to only the new_bars most-recent rows
        # Use the original df's last new_bars timestamps as the filter
        target_index = df.index[-new_bars:]
        trimmed = features.loc[features.index.isin(target_index)]

        logger.debug(
            "compute_incremental: trimmed features from %d to %d rows",
            len(features), len(trimmed),
        )

        return trimmed

    def compute_subset(
        self,
        df: pd.DataFrame,
        feature_names: list[str],
        market_df: pd.DataFrame | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Compute only a subset of features.

        Useful for computing only the minimal starter set of features.

        Args:
            df: DataFrame with datetime index and columns: open, high, low, close, volume
            feature_names: List of feature names to compute
            market_df: Optional market benchmark data
            **kwargs: Additional arguments passed to calculators

        Returns:
            DataFrame with requested feature columns
        """
        # Compute all features
        all_features = self.compute(df, market_df=market_df, **kwargs)

        # Filter to requested columns
        available = [col for col in feature_names if col in all_features.columns]
        missing = set(feature_names) - set(available)
        if missing:
            logger.warning("Requested features not available: %s", sorted(missing))
        return all_features[available]


def get_minimal_features() -> list[str]:
    """Get the minimal starter set of features recommended in FEATURE.md.

    Returns:
        List of minimal feature names
    """
    return [
        # Returns
        "r1",
        "r5",
        "r15",
        "r60",
        # Volatility
        "rv_60",
        "range_1",
        "range_z_60",
        # Volume
        "relvol_60",
        "vol_z_60",
        # Intrabar
        "clv",
        "body_ratio",
        # Anchor
        "dist_vwap_60",
        "breakout_20",
        # Time-of-day
        "tod_sin",
        "tod_cos",
    ]
