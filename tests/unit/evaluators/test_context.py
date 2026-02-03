"""Tests for context infrastructure — MTFAContext, KeyLevels VWAP, and ContextPackBuilder helpers."""

import math
from datetime import datetime

import pytest

from src.evaluators.context import (
    ContextPackBuilder,
    KeyLevels,
    MTFAContext,
    RegimeContext,
)


class TestMTFAContext:
    """Tests for the MTFAContext dataclass."""

    def test_default_values(self):
        ctx = MTFAContext()
        assert ctx.alignment_score is None
        assert ctx.conflicts == []
        assert ctx.htf_trend is None

    def test_to_dict(self):
        ctx = MTFAContext(
            alignment_score=0.75,
            conflicts=["1Hour: bearish (vs majority: bullish)"],
            htf_trend="bearish",
        )
        d = ctx.to_dict()
        assert d["alignment_score"] == 0.75
        assert len(d["conflicts"]) == 1
        assert d["htf_trend"] == "bearish"

    def test_to_dict_empty(self):
        d = MTFAContext().to_dict()
        assert d["alignment_score"] is None
        assert d["conflicts"] == []
        assert d["htf_trend"] is None


class TestKeyLevelsVWAP:
    """Tests for VWAP integration in KeyLevels."""

    def test_vwap_in_distance_to_nearest_level(self):
        levels = KeyLevels(vwap=100.0)
        name, dist = levels.distance_to_nearest_level(100.5)
        assert name == "vwap"
        assert dist == pytest.approx(0.4975, abs=0.01)

    def test_vwap_nearest_over_other_levels(self):
        levels = KeyLevels(
            pivot=95.0,
            r1=105.0,
            vwap=100.1,
        )
        name, dist = levels.distance_to_nearest_level(100.0)
        assert name == "vwap"

    def test_vwap_none_not_considered(self):
        levels = KeyLevels(pivot=100.0, vwap=None)
        name, _ = levels.distance_to_nearest_level(100.0)
        assert name == "pivot"

    def test_vwap_in_to_dict(self):
        levels = KeyLevels(vwap=150.25)
        d = levels.to_dict()
        assert d["vwap"] == 150.25

    def test_vwap_none_in_to_dict(self):
        d = KeyLevels().to_dict()
        assert d["vwap"] is None


class TestComputeApproximateEntropy:
    """Tests for ContextPackBuilder._compute_approximate_entropy."""

    def test_high_confidence_low_entropy(self):
        """High state_prob should yield low entropy."""
        entropy = ContextPackBuilder._compute_approximate_entropy(0.95, 4)
        assert entropy is not None
        assert entropy > 0
        assert entropy < 0.5

    def test_low_confidence_high_entropy(self):
        """Low state_prob should yield high entropy."""
        entropy = ContextPackBuilder._compute_approximate_entropy(0.3, 8)
        assert entropy is not None
        assert entropy > 1.0

    def test_uniform_distribution_max_entropy(self):
        """Probability = 1/n should give max entropy = log(n)."""
        n = 4
        entropy = ContextPackBuilder._compute_approximate_entropy(1.0 / n, n)
        assert entropy is not None
        assert entropy == pytest.approx(math.log(n), abs=0.01)

    def test_certain_state_zero_entropy(self):
        """Probability near 1.0 should give near-zero entropy."""
        entropy = ContextPackBuilder._compute_approximate_entropy(0.999, 4)
        assert entropy is not None
        assert entropy < 0.02

    def test_inverse_relationship(self):
        """Higher prob -> lower entropy for same n_states."""
        e_high = ContextPackBuilder._compute_approximate_entropy(0.9, 8)
        e_low = ContextPackBuilder._compute_approximate_entropy(0.4, 8)
        assert e_high < e_low

    def test_more_states_higher_entropy(self):
        """More states -> higher entropy for same probability."""
        e_few = ContextPackBuilder._compute_approximate_entropy(0.5, 3)
        e_many = ContextPackBuilder._compute_approximate_entropy(0.5, 10)
        assert e_few < e_many

    def test_invalid_n_states(self):
        assert ContextPackBuilder._compute_approximate_entropy(0.5, 1) is None
        assert ContextPackBuilder._compute_approximate_entropy(0.5, 0) is None

    def test_invalid_prob(self):
        assert ContextPackBuilder._compute_approximate_entropy(0.0, 4) is None
        assert ContextPackBuilder._compute_approximate_entropy(-0.1, 4) is None
        assert ContextPackBuilder._compute_approximate_entropy(1.1, 4) is None

    def test_prob_exactly_one(self):
        """Probability of exactly 1.0 should still work (clamped)."""
        entropy = ContextPackBuilder._compute_approximate_entropy(1.0, 4)
        assert entropy is not None
        assert entropy >= 0


class TestComputeMTFA:
    """Tests for ContextPackBuilder._compute_mtfa."""

    def _make_builder(self):
        return ContextPackBuilder(
            include_features=False,
            include_regimes=False,
            include_key_levels=False,
            cache_enabled=False,
        )

    def _regime(self, tf, state_id=0, state_label=None, state_prob=0.8):
        return RegimeContext(
            timeframe=tf,
            state_id=state_id,
            state_prob=state_prob,
            state_label=state_label or f"state_{state_id}",
        )

    def test_insufficient_timeframes_returns_none_score(self):
        """Fewer than 2 timeframes → alignment_score is None."""
        builder = self._make_builder()
        regimes = {"5Min": self._regime("5Min")}
        result = builder._compute_mtfa(regimes, "5Min")
        assert result.alignment_score is None

    def test_empty_regimes_returns_none_score(self):
        builder = self._make_builder()
        result = builder._compute_mtfa({}, "5Min")
        assert result.alignment_score is None

    def test_all_agree_perfect_alignment(self):
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=2, state_label="bullish"),
            "1Hour": self._regime("1Hour", state_id=2, state_label="bullish"),
            "1Day": self._regime("1Day", state_id=2, state_label="bullish"),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        assert result.alignment_score == 1.0
        assert result.conflicts == []
        assert result.htf_trend == "bullish"

    def test_partial_disagreement(self):
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=1, state_label="bullish"),
            "1Hour": self._regime("1Hour", state_id=1, state_label="bullish"),
            "1Day": self._regime("1Day", state_id=3, state_label="bearish"),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        assert result.alignment_score == pytest.approx(2.0 / 3.0, abs=0.01)
        assert len(result.conflicts) == 1
        assert "1Day" in result.conflicts[0]
        assert "bearish" in result.conflicts[0]

    def test_majority_disagreement(self):
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=1, state_label="bullish"),
            "1Hour": self._regime("1Hour", state_id=3, state_label="bearish"),
            "1Day": self._regime("1Day", state_id=3, state_label="bearish"),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        # bearish is the majority (2/3)
        assert result.alignment_score == pytest.approx(2.0 / 3.0, abs=0.01)
        assert len(result.conflicts) == 1
        assert "5Min" in result.conflicts[0]

    def test_ood_regimes_excluded(self):
        """OOD regimes (state_id == -1) should be excluded."""
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=1, state_label="bullish"),
            "1Hour": self._regime("1Hour", state_id=-1, state_label="unknown"),
            "1Day": self._regime("1Day", state_id=1, state_label="bullish"),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        # Only 5Min and 1Day count (both bullish)
        assert result.alignment_score == 1.0

    def test_all_ood_returns_none_score(self):
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=-1),
            "1Hour": self._regime("1Hour", state_id=-1),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        assert result.alignment_score is None

    def test_htf_trend_picks_highest_timeframe(self):
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=1, state_label="bullish"),
            "15Min": self._regime("15Min", state_id=2, state_label="bearish"),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        assert result.htf_trend == "bearish"  # 15Min > 5Min

    def test_htf_trend_with_daily(self):
        builder = self._make_builder()
        regimes = {
            "1Min": self._regime("1Min", state_id=1, state_label="bullish"),
            "1Hour": self._regime("1Hour", state_id=2, state_label="ranging"),
            "1Day": self._regime("1Day", state_id=3, state_label="bearish"),
        }
        result = builder._compute_mtfa(regimes, "1Min")
        assert result.htf_trend == "bearish"  # 1Day is highest

    def test_conflicts_ordered_by_timeframe(self):
        builder = self._make_builder()
        regimes = {
            "5Min": self._regime("5Min", state_id=1, state_label="bullish"),
            "1Hour": self._regime("1Hour", state_id=1, state_label="bullish"),
            "15Min": self._regime("15Min", state_id=2, state_label="bearish"),
            "1Day": self._regime("1Day", state_id=3, state_label="ranging"),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        # bullish is majority (2/4), conflicts are 15Min and 1Day
        tf_in_conflicts = [c.split(":")[0] for c in result.conflicts]
        assert tf_in_conflicts == ["15Min", "1Day"]

    def test_generic_labels_used_when_state_label_none(self):
        builder = self._make_builder()
        regimes = {
            "5Min": RegimeContext(timeframe="5Min", state_id=1, state_prob=0.8, state_label=None),
            "1Hour": RegimeContext(timeframe="1Hour", state_id=1, state_prob=0.8, state_label=None),
        }
        result = builder._compute_mtfa(regimes, "5Min")
        # Both fall back to "state_1", so perfect alignment
        assert result.alignment_score == 1.0
