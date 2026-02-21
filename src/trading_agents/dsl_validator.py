"""Structural validator for DSL condition JSON.

Validates that entry/exit condition arrays are well-formed before
persisting to the database. This catches errors at save time rather
than at agent runtime, when the Go DSL compiler would reject them.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Operators the Go DSL compiler recognises.
KNOWN_OPS = frozenset({
    "crosses_above", "crosses_below", "above", "below",
    "rising", "falling",
    "all_of", "any_of",
    "pullback_to", "pullback_below",
    "bullish_divergence", "bearish_divergence",
    "candle_bullish", "candle_bearish",
    "breaks_above_level", "breaks_below_level",
    "squeeze", "range_exceeds_atr", "bb_width_increasing",
    "gap_up", "gap_down",
    "held_above", "held_below",
    "was_below_then_crosses_above", "was_above_then_crosses_below",
    "adx_in_range",
    "deviation_below", "deviation_above",
    "consecutive_higher_closes", "consecutive_lower_closes",
    "narrowest_range",
    "in_top_pct_of_range", "in_bottom_pct_of_range",
    "close_above_upper_channel", "close_below_lower_channel",
    "ribbon_break_long", "ribbon_break_short",
    "ribbon_exit_long", "ribbon_exit_short",
    "trix_crosses_above_sma", "trix_crosses_below_sma",
    "breaks_above_sma_envelope", "breaks_below_sma_envelope",
    "double_tap_below_bb", "double_tap_above_bb",
    "atr_not_bottom_pct", "atr_below_contracted_sma",
    "flat_slope",
    "mean_rev_long", "mean_rev_short",
    "majority_bull", "majority_bear",
})

# Required fields per operator (beyond 'op').
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "crosses_above": ["col", "ref"],
    "crosses_below": ["col", "ref"],
    "above": ["col", "ref"],
    "below": ["col", "ref"],
    "rising": ["col", "n"],
    "falling": ["col", "n"],
    "all_of": ["conditions"],
    "any_of": ["conditions"],
    "pullback_to": ["level_col"],
    "pullback_below": ["level_col"],
    "bullish_divergence": ["indicator_col"],
    "bearish_divergence": ["indicator_col"],
    "candle_bullish": ["pattern_col"],
    "candle_bearish": ["pattern_col"],
    "breaks_above_level": ["level_col"],
    "breaks_below_level": ["level_col"],
    "squeeze": ["width_col"],
    "bb_width_increasing": ["n"],
    "held_above": ["col", "n"],
    "held_below": ["col", "n"],
    "was_below_then_crosses_above": ["col"],
    "was_above_then_crosses_below": ["col"],
    "deviation_below": ["col", "ref_col"],
    "deviation_above": ["col", "ref_col"],
    "consecutive_higher_closes": ["n"],
    "consecutive_lower_closes": ["n"],
    "narrowest_range": ["lookback"],
    "in_top_pct_of_range": ["pct"],
    "in_bottom_pct_of_range": ["pct"],
    "close_above_upper_channel": ["col"],
    "close_below_lower_channel": ["col"],
    "ribbon_break_long": ["lookback"],
    "ribbon_break_short": ["lookback"],
    "breaks_above_sma_envelope": ["col"],
    "breaks_below_sma_envelope": ["col"],
    "double_tap_below_bb": ["lookback"],
    "double_tap_above_bb": ["lookback"],
    "atr_not_bottom_pct": ["pct", "lookback"],
    "atr_below_contracted_sma": ["factor"],
    "flat_slope": ["col"],
    "mean_rev_long": ["ref_col"],
    "mean_rev_short": ["ref_col"],
}


def validate_conditions(conditions: Any, field_name: str = "conditions") -> list[str]:
    """Validate a DSL condition array.

    Args:
        conditions: The value to validate (should be a list of dicts).
        field_name: Name of the field for error messages.

    Returns:
        List of error strings. Empty list means valid.
    """
    if conditions is None:
        return []

    if not isinstance(conditions, list):
        return [f"{field_name}: must be a list of condition objects, got {type(conditions).__name__}"]

    errors: list[str] = []
    for i, node in enumerate(conditions):
        path = f"{field_name}[{i}]"
        errors.extend(_validate_node(node, path))
    return errors


def _validate_node(node: Any, path: str) -> list[str]:
    """Validate a single condition node recursively."""
    errors: list[str] = []

    if not isinstance(node, dict):
        return [f"{path}: must be a dict, got {type(node).__name__}"]

    op = node.get("op")
    if not op:
        return [f"{path}: missing 'op' field"]

    if not isinstance(op, str):
        return [f"{path}: 'op' must be a string, got {type(op).__name__}"]

    if op not in KNOWN_OPS:
        return [f"{path}: unknown operator '{op}'"]

    # Check required fields
    required = _REQUIRED_FIELDS.get(op, [])
    for field in required:
        if field == "conditions":
            # Composite ops: validate nested conditions
            children = node.get("conditions")
            if not children:
                errors.append(f"{path}: '{op}' requires non-empty 'conditions' array")
            elif not isinstance(children, list):
                errors.append(f"{path}: 'conditions' must be a list")
            else:
                for j, child in enumerate(children):
                    errors.extend(_validate_node(child, f"{path}.conditions[{j}]"))
        elif field == "ref":
            ref = node.get("ref")
            if ref is None:
                errors.append(f"{path}: '{op}' requires 'ref'")
            elif not isinstance(ref, dict):
                errors.append(f"{path}: 'ref' must be a dict with 'col' or 'value'")
            elif not ref.get("col") and ref.get("value") is None:
                errors.append(f"{path}: 'ref' must have 'col' or 'value'")
        else:
            val = node.get(field)
            if val is None and val != 0:
                # Check for snake_case JSON field name
                if node.get(field) is None:
                    errors.append(f"{path}: '{op}' requires '{field}'")

    return errors


def validate_strategy_conditions(data: dict) -> list[str]:
    """Validate all entry/exit condition fields in a strategy dict.

    Args:
        data: Strategy data dict (from request body).

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []
    for field in ("entry_long", "entry_short", "exit_long", "exit_short"):
        val = data.get(field)
        if val is not None:
            errors.extend(validate_conditions(val, field))
    return errors
