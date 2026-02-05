"""Volume and participation features."""

import logging
from typing import Any

import pandas as pd

from .base import EPS, BaseFeatureCalculator, FeatureSpec, safe_divide, zscore

logger = logging.getLogger(__name__)


class VolumeFeatureCalculator(BaseFeatureCalculator):
    """Computes volume and participation features.

    Features:
        - vol1: Raw volume
        - dvol1: Dollar volume (close * volume)
        - relvol_60: Relative volume vs rolling mean
        - vol_z_60: Volume z-score
        - dvol_z_60: Dollar volume z-score

    Participation features help confirm momentum continuation.
    """

    def __init__(self, window: int = 60):
        """Initialize VolumeFeatureCalculator.

        Args:
            window: Rolling window size for z-scores and relative volume
        """
        self.window = window

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="vol1",
                description="Raw volume",
                lookback=1,
                group="volume",
            ),
            FeatureSpec(
                name="dvol1",
                description="Dollar volume: close * volume",
                lookback=1,
                group="volume",
            ),
            FeatureSpec(
                name="relvol_60",
                description="Relative volume: V / mean(V, 60)",
                lookback=self.window,
                group="volume",
            ),
            FeatureSpec(
                name="vol_z_60",
                description="Volume z-score over 60-bar window",
                lookback=self.window,
                group="volume",
            ),
            FeatureSpec(
                name="dvol_z_60",
                description="Dollar volume z-score over 60-bar window",
                lookback=self.window,
                group="volume",
            ),
        ]

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute volume features.

        Args:
            df: DataFrame with columns: close, volume

        Returns:
            DataFrame with columns: vol1, dvol1, relvol_60, vol_z_60, dvol_z_60
        """
        logger.debug("Computing volume features for %d rows", len(df))
        result = pd.DataFrame(index=df.index)

        # Raw volume
        result["vol1"] = df["volume"]

        # Dollar volume
        result["dvol1"] = df["close"] * df["volume"]

        # Relative volume (current vs rolling mean)
        vol_mean = df["volume"].rolling(window=self.window, min_periods=self.window).mean()
        result["relvol_60"] = safe_divide(df["volume"], vol_mean)

        # Volume z-score
        result["vol_z_60"] = zscore(df["volume"], window=self.window)

        # Dollar volume z-score
        result["dvol_z_60"] = zscore(result["dvol1"], window=self.window)

        logger.debug(
            "Volume features computed: relvol_60 range=[%.4f, %.4f], vol_z_60 range=[%.4f, %.4f]",
            result["relvol_60"].min(), result["relvol_60"].max(),
            result["vol_z_60"].min(), result["vol_z_60"].max()
        )
        return result
