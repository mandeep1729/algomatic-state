"""Semantic labeling for PCA-based states."""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Color palette for states
STATE_COLORS = {
    "up_trending": "#22c55e",      # Green
    "up_volatile": "#4ade80",      # Light green
    "up_breakout": "#15803d",      # Dark green
    "down_trending": "#ef4444",    # Red
    "down_volatile": "#f87171",    # Light red
    "down_breakout": "#b91c1c",    # Dark red
    "neutral_consolidation": "#94a3b8",  # Slate
    "neutral_ranging": "#64748b",  # Darker slate
    "high_volatility": "#f59e0b",  # Amber
    "low_volatility": "#3b82f6",   # Blue
}

DEFAULT_COLOR = "#6b7280"  # Gray


@dataclass
class StateLabel:
    """Semantic label for a PCA state."""

    state_id: int
    label: str
    short_label: str
    color: str
    description: str
    characteristics: dict


def label_pca_states(
    engine,
    features_df: pd.DataFrame,
    feature_names: Optional[list[str]] = None,
) -> dict[int, StateLabel]:
    """Generate semantic labels for PCA states based on feature characteristics.

    Args:
        engine: Fitted PCAStateEngine
        features_df: DataFrame with features used for context
        feature_names: Optional subset of features to analyze

    Returns:
        Dictionary mapping state_id -> StateLabel
    """
    if feature_names is None:
        feature_names = engine.metadata.feature_names

    # Transform features to get state assignments
    result_df = engine.transform(features_df)

    # Merge with original features for analysis
    analysis_df = features_df[feature_names].copy()
    analysis_df["state_id"] = result_df["state_id"]

    labels = {}

    for state_id in range(engine.metadata.n_states):
        state_mask = analysis_df["state_id"] == state_id

        if state_mask.sum() == 0:
            # No samples in this state
            labels[state_id] = StateLabel(
                state_id=state_id,
                label=f"state_{state_id}",
                short_label=f"S{state_id}",
                color=DEFAULT_COLOR,
                description=f"State {state_id} (no samples)",
                characteristics={},
            )
            continue

        state_data = analysis_df[state_mask]

        # Analyze key characteristics
        characteristics = _analyze_state_characteristics(state_data, feature_names)

        # Generate label based on characteristics
        label, short_label, description = _generate_label(characteristics)

        # Assign color based on label
        color = _get_color_for_label(label)

        labels[state_id] = StateLabel(
            state_id=state_id,
            label=label,
            short_label=short_label,
            color=color,
            description=description,
            characteristics=characteristics,
        )

        logger.info(f"State {state_id}: {label} ({state_mask.sum()} samples)")

    return labels


def _analyze_state_characteristics(
    state_data: pd.DataFrame,
    feature_names: list[str],
) -> dict:
    """Analyze characteristics of a state based on feature means."""
    characteristics = {}

    # Key features to analyze
    return_features = ["r1", "r5", "r15", "r60"]
    volatility_features = ["rv_60", "atr_14", "vol_z_60", "range_z_60"]
    trend_features = ["slope_60", "trend_strength", "adx_14"]
    volume_features = ["relvol_60", "dvol_z_60"]

    # Analyze returns (trend direction)
    available_returns = [f for f in return_features if f in feature_names]
    if available_returns:
        mean_returns = state_data[available_returns].mean()
        characteristics["mean_return"] = float(mean_returns.mean())
        characteristics["return_sign"] = "positive" if characteristics["mean_return"] > 0.0001 else (
            "negative" if characteristics["mean_return"] < -0.0001 else "neutral"
        )

    # Analyze volatility
    available_vol = [f for f in volatility_features if f in feature_names]
    if available_vol:
        mean_vol = state_data[available_vol].mean()
        characteristics["mean_volatility"] = float(mean_vol.mean())
        characteristics["volatility_level"] = (
            "high" if characteristics["mean_volatility"] > 1.0 else (
                "low" if characteristics["mean_volatility"] < -0.5 else "normal"
            )
        )

    # Analyze trend strength
    available_trend = [f for f in trend_features if f in feature_names]
    if available_trend:
        mean_trend = state_data[available_trend].mean()
        characteristics["mean_trend_strength"] = float(mean_trend.mean())
        characteristics["trending"] = characteristics["mean_trend_strength"] > 0.3

    # Analyze volume
    available_volume = [f for f in volume_features if f in feature_names]
    if available_volume:
        mean_volume = state_data[available_volume].mean()
        characteristics["mean_volume"] = float(mean_volume.mean())
        characteristics["high_volume"] = characteristics["mean_volume"] > 1.0

    # RSI for overbought/oversold
    if "rsi_14" in feature_names:
        mean_rsi = state_data["rsi_14"].mean()
        characteristics["mean_rsi"] = float(mean_rsi)
        characteristics["rsi_zone"] = (
            "overbought" if mean_rsi > 70 else (
                "oversold" if mean_rsi < 30 else "neutral"
            )
        )

    return characteristics


def _generate_label(characteristics: dict) -> tuple[str, str, str]:
    """Generate semantic label from characteristics.

    Returns:
        Tuple of (label, short_label, description)
    """
    parts = []
    description_parts = []

    # Direction component
    return_sign = characteristics.get("return_sign", "neutral")
    if return_sign == "positive":
        parts.append("up")
        description_parts.append("Upward movement")
    elif return_sign == "negative":
        parts.append("down")
        description_parts.append("Downward movement")
    else:
        parts.append("neutral")
        description_parts.append("Sideways movement")

    # Volatility/character component
    vol_level = characteristics.get("volatility_level", "normal")
    trending = characteristics.get("trending", False)
    high_volume = characteristics.get("high_volume", False)

    if vol_level == "high":
        if high_volume:
            parts.append("breakout")
            description_parts.append("with high volatility and volume (breakout)")
        else:
            parts.append("volatile")
            description_parts.append("with high volatility")
    elif trending:
        parts.append("trending")
        description_parts.append("with strong trend")
    elif vol_level == "low":
        parts.append("consolidation")
        description_parts.append("with low volatility (consolidation)")
    else:
        parts.append("ranging")
        description_parts.append("with normal volatility")

    label = "_".join(parts)
    short_label = "".join([p[0].upper() for p in parts]) + "-" + parts[-1][:3].upper()
    description = " ".join(description_parts)

    return label, short_label, description


def _get_color_for_label(label: str) -> str:
    """Get color for a label."""
    if label in STATE_COLORS:
        return STATE_COLORS[label]

    # Try partial matching
    for key, color in STATE_COLORS.items():
        if key in label or label in key:
            return color

    # Default based on direction
    if label.startswith("up"):
        return "#22c55e"
    elif label.startswith("down"):
        return "#ef4444"
    else:
        return DEFAULT_COLOR


def labels_to_dict(labels: dict[int, StateLabel]) -> dict[str, dict]:
    """Convert labels to dictionary format for metadata storage.

    Args:
        labels: Dictionary of state_id -> StateLabel

    Returns:
        Dictionary suitable for JSON serialization
    """
    result = {}
    for state_id, label in labels.items():
        result[str(state_id)] = {
            "state_id": label.state_id,
            "label": label.label,
            "short_label": label.short_label,
            "color": label.color,
            "description": label.description,
        }
    return result
