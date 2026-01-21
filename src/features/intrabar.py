"""Intrabar structure features (microstructure-lite)."""

from typing import Any

import pandas as pd

from .base import EPS, BaseFeatureCalculator, FeatureSpec


class IntrabarFeatureCalculator(BaseFeatureCalculator):
    """Computes intrabar structure features.

    Features:
        - clv: Close location value - where close is relative to bar range
        - body_ratio: Candle body size relative to full range
        - upper_wick: Upper wick size relative to full range
        - lower_wick: Lower wick size relative to full range

    These features distinguish orderly trends from noisy reversals.
    """

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="clv",
                description="Close location value: (C - L) / (H - L)",
                lookback=1,
                group="intrabar",
            ),
            FeatureSpec(
                name="body_ratio",
                description="Candle body ratio: |C - O| / (H - L)",
                lookback=1,
                group="intrabar",
            ),
            FeatureSpec(
                name="upper_wick",
                description="Upper wick ratio: (H - max(O, C)) / (H - L)",
                lookback=1,
                group="intrabar",
            ),
            FeatureSpec(
                name="lower_wick",
                description="Lower wick ratio: (min(O, C) - L) / (H - L)",
                lookback=1,
                group="intrabar",
            ),
        ]

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute intrabar structure features.

        Args:
            df: DataFrame with columns: open, high, low, close

        Returns:
            DataFrame with columns: clv, body_ratio, upper_wick, lower_wick
        """
        o = df["open"]
        h = df["high"]
        l = df["low"]
        c = df["close"]

        # Bar range (with EPS to avoid division by zero)
        bar_range = h - l + EPS

        result = pd.DataFrame(index=df.index)

        # Close location value: where is close relative to bar range [0, 1]
        result["clv"] = (c - l) / bar_range

        # Body ratio: how much of the bar is body vs wicks
        result["body_ratio"] = (c - o).abs() / bar_range

        # Upper wick: distance from high to top of body
        result["upper_wick"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / bar_range

        # Lower wick: distance from bottom of body to low
        result["lower_wick"] = (pd.concat([o, c], axis=1).min(axis=1) - l) / bar_range

        return result
