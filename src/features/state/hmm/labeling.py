"""Semantic labeling for HMM states.

Analyzes HMM state centroids and assigns human-readable labels
based on feature characteristics like trend direction and volatility.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.features.state.hmm.encoders import BaseEncoder
from src.features.state.hmm.hmm_model import GaussianHMMWrapper
from src.features.state.hmm.scalers import BaseScaler

logger = logging.getLogger(__name__)


@dataclass
class StateLabel:
    """Semantic label for an HMM state.

    Attributes:
        state_id: Original HMM state index
        label: Full semantic label (e.g., "up_trending")
        short_label: Abbreviated label for UI (e.g., "UP-T")
        color: Hex color for visualization
        description: Human-readable description
    """

    state_id: int
    label: str
    short_label: str
    color: str
    description: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "state_id": self.state_id,
            "label": self.label,
            "short_label": self.short_label,
            "color": self.color,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateLabel":
        """Create from dictionary."""
        return cls(
            state_id=data["state_id"],
            label=data["label"],
            short_label=data["short_label"],
            color=data["color"],
            description=data["description"],
        )


# Color palettes for different state types
STATE_COLORS = {
    # Up states - greens
    "up_trending": "#22c55e",      # Green-500
    "up_volatile": "#4ade80",      # Green-400
    "up_breakout": "#15803d",      # Green-700
    "up_consolidation": "#86efac", # Green-300
    # Down states - reds
    "down_trending": "#ef4444",    # Red-500
    "down_volatile": "#f87171",    # Red-400
    "down_breakout": "#b91c1c",    # Red-700
    "down_consolidation": "#fca5a5", # Red-300
    # Neutral states - slates
    "neutral_trending": "#94a3b8",     # Slate-400
    "neutral_volatile": "#64748b",     # Slate-500
    "neutral_breakout": "#475569",     # Slate-600
    "neutral_consolidation": "#cbd5e1", # Slate-300
    # Fallback
    "unknown": "#6b7280",          # Gray-500
}

# Short labels for each state type
SHORT_LABELS = {
    "up_trending": "UP-T",
    "up_volatile": "UP-V",
    "up_breakout": "UP-B",
    "up_consolidation": "UP-C",
    "down_trending": "DN-T",
    "down_volatile": "DN-V",
    "down_breakout": "DN-B",
    "down_consolidation": "DN-C",
    "neutral_trending": "NT-T",
    "neutral_volatile": "NT-V",
    "neutral_breakout": "NT-B",
    "neutral_consolidation": "NT-C",
    "unknown": "UNK",
}

# Descriptions for each state type
STATE_DESCRIPTIONS = {
    "up_trending": "Bullish trend with consistent upward momentum",
    "up_volatile": "Bullish with high volatility and choppy price action",
    "up_breakout": "Strong bullish breakout with expanding volatility",
    "up_consolidation": "Bullish bias but consolidating in a range",
    "down_trending": "Bearish trend with consistent downward momentum",
    "down_volatile": "Bearish with high volatility and choppy price action",
    "down_breakout": "Strong bearish breakdown with expanding volatility",
    "down_consolidation": "Bearish bias but consolidating in a range",
    "neutral_trending": "Neutral with slight directional bias",
    "neutral_volatile": "Range-bound with high volatility",
    "neutral_breakout": "Potential breakout pending direction confirmation",
    "neutral_consolidation": "Low volatility consolidation phase",
    "unknown": "Unclassified market state",
}


class StateLabelingEngine:
    """Engine for computing semantic labels for HMM states.

    Analyzes the feature-space centroids of each HMM state to determine
    trend direction and volatility characteristics, then assigns
    human-readable labels.
    """

    # Feature names used for classification
    RETURN_FEATURES = ["r5", "r15", "r60"]
    VOLATILITY_FEATURES = ["vol_z_60"]

    # Thresholds for classification
    TREND_THRESHOLD = 0.2      # Z-score threshold for trend direction
    VOLATILITY_THRESHOLD = 1.0 # Z-score threshold for high volatility
    BREAKOUT_THRESHOLD = 2.0   # Z-score threshold for breakout

    def __init__(
        self,
        hmm: GaussianHMMWrapper,
        scaler: BaseScaler,
        encoder: BaseEncoder,
        feature_names: list[str],
    ):
        """Initialize the labeling engine.

        Args:
            hmm: Trained HMM model
            scaler: Fitted scaler used during training
            encoder: Fitted encoder (PCA or VAE)
            feature_names: Ordered list of feature names
        """
        self.hmm = hmm
        self.scaler = scaler
        self.encoder = encoder
        self.feature_names = feature_names

        # Create feature name to index mapping
        self._feature_idx = {name: i for i, name in enumerate(feature_names)}

    def _get_state_centroids_latent(self) -> np.ndarray:
        """Get HMM state centroids in latent space.

        Returns:
            Array of shape (n_states, latent_dim)
        """
        return self.hmm.means

    def _inverse_transform_centroids(self) -> np.ndarray:
        """Transform latent centroids back to feature space.

        Returns:
            Array of shape (n_states, n_features) in scaled feature space
        """
        latent_centroids = self._get_state_centroids_latent()

        # Use encoder's inverse_transform method
        scaled_centroids = self.encoder.inverse_transform(latent_centroids)

        return scaled_centroids

    def _get_feature_value(
        self,
        centroids: np.ndarray,
        state_id: int,
        feature_names: list[str],
    ) -> float:
        """Get average feature value for a state across multiple features.

        Args:
            centroids: Feature-space centroids (n_states, n_features)
            state_id: State index
            feature_names: List of feature names to average

        Returns:
            Average feature value (in scaled space)
        """
        values = []
        for name in feature_names:
            if name in self._feature_idx:
                idx = self._feature_idx[name]
                values.append(centroids[state_id, idx])

        if not values:
            return 0.0
        return np.mean(values)

    def _classify_trend(self, return_value: float) -> str:
        """Classify trend direction based on return feature value.

        Args:
            return_value: Average return feature value (scaled)

        Returns:
            One of "up", "down", "neutral"
        """
        if return_value > self.TREND_THRESHOLD:
            return "up"
        elif return_value < -self.TREND_THRESHOLD:
            return "down"
        else:
            return "neutral"

    def _classify_volatility(self, vol_value: float) -> str:
        """Classify volatility character based on volatility feature value.

        Args:
            vol_value: Volatility feature value (scaled)

        Returns:
            One of "trending", "volatile", "breakout", "consolidation"
        """
        if vol_value > self.BREAKOUT_THRESHOLD:
            return "breakout"
        elif vol_value > self.VOLATILITY_THRESHOLD:
            return "volatile"
        elif vol_value < -self.VOLATILITY_THRESHOLD:
            return "consolidation"
        else:
            return "trending"

    def _create_state_label(self, state_id: int, trend: str, volatility: str) -> StateLabel:
        """Create a StateLabel from classification results.

        Args:
            state_id: HMM state index
            trend: Trend classification
            volatility: Volatility classification

        Returns:
            StateLabel instance
        """
        label = f"{trend}_{volatility}"
        color = STATE_COLORS.get(label, STATE_COLORS["unknown"])
        short_label = SHORT_LABELS.get(label, SHORT_LABELS["unknown"])
        description = STATE_DESCRIPTIONS.get(label, STATE_DESCRIPTIONS["unknown"])

        return StateLabel(
            state_id=state_id,
            label=label,
            short_label=short_label,
            color=color,
            description=description,
        )

    def label_states(self) -> dict[int, StateLabel]:
        """Compute semantic labels for all HMM states.

        Returns:
            Dictionary mapping state_id -> StateLabel
        """
        logger.info(f"Labeling {self.hmm.n_states} HMM states based on {len(self.feature_names)} features")

        # Get centroids in scaled feature space
        try:
            scaled_centroids = self._inverse_transform_centroids()
            logger.debug(f"Inverse-transformed centroids shape: {scaled_centroids.shape}")
        except (ValueError, AttributeError) as e:
            # If inverse transform fails, return unknown labels
            logger.warning(f"Failed to inverse transform centroids: {e}. Using unknown labels.")
            return {
                i: StateLabel(
                    state_id=i,
                    label="unknown",
                    short_label=f"S{i}",
                    color=STATE_COLORS["unknown"],
                    description=f"State {i} (classification unavailable)",
                )
                for i in range(self.hmm.n_states)
            }

        labels = {}
        for state_id in range(self.hmm.n_states):
            # Get return and volatility values
            return_value = self._get_feature_value(
                scaled_centroids, state_id, self.RETURN_FEATURES
            )
            vol_value = self._get_feature_value(
                scaled_centroids, state_id, self.VOLATILITY_FEATURES
            )

            # Classify
            trend = self._classify_trend(return_value)
            volatility = self._classify_volatility(vol_value)

            # Create label
            labels[state_id] = self._create_state_label(state_id, trend, volatility)
            logger.debug(f"State {state_id}: {labels[state_id].label} ({labels[state_id].short_label})")

        logger.info(f"Generated labels for {len(labels)} states: {[l.label for l in labels.values()]}")
        return labels

    def get_state_statistics(self) -> dict[int, dict]:
        """Get detailed statistics for each state.

        Returns:
            Dictionary mapping state_id -> statistics dict
        """
        try:
            scaled_centroids = self._inverse_transform_centroids()
        except (ValueError, AttributeError):
            return {}

        stats = {}
        for state_id in range(self.hmm.n_states):
            state_stats = {}

            # Get values for key features
            for feature in self.RETURN_FEATURES + self.VOLATILITY_FEATURES:
                if feature in self._feature_idx:
                    idx = self._feature_idx[feature]
                    state_stats[feature] = float(scaled_centroids[state_id, idx])

            # Get transition probabilities
            trans_probs = self.hmm.transition_matrix[state_id]
            state_stats["self_transition_prob"] = float(trans_probs[state_id])
            state_stats["expected_duration"] = (
                1.0 / (1.0 - trans_probs[state_id])
                if trans_probs[state_id] < 1.0
                else float("inf")
            )

            stats[state_id] = state_stats

        return stats


def label_states_from_artifacts(
    hmm: GaussianHMMWrapper,
    scaler: BaseScaler,
    encoder: BaseEncoder,
    feature_names: list[str],
) -> dict[int, StateLabel]:
    """Convenience function to label states from model artifacts.

    Args:
        hmm: Trained HMM
        scaler: Fitted scaler
        encoder: Fitted encoder
        feature_names: Feature names

    Returns:
        Dictionary mapping state_id -> StateLabel
    """
    engine = StateLabelingEngine(hmm, scaler, encoder, feature_names)
    return engine.label_states()


def state_labels_to_mapping(labels: dict[int, StateLabel]) -> dict[str, dict]:
    """Convert state labels to metadata-compatible format.

    Args:
        labels: Dictionary of state_id -> StateLabel

    Returns:
        Dictionary suitable for ModelMetadata.state_mapping
    """
    return {str(state_id): label.to_dict() for state_id, label in labels.items()}


def state_mapping_to_labels(mapping: dict[str, dict]) -> dict[int, StateLabel]:
    """Convert metadata state_mapping back to StateLabel objects.

    Args:
        mapping: Dictionary from ModelMetadata.state_mapping

    Returns:
        Dictionary of state_id -> StateLabel
    """
    return {int(k): StateLabel.from_dict(v) for k, v in mapping.items()}
