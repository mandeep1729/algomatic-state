"""Tests for context infrastructure — MTFAContext, KeyLevels VWAP, ContextPackBuilder helpers,
and MarketDataReader dependency injection."""

import math
from datetime import datetime
from typing import Optional

import pandas as pd
import pytest

from src.evaluators.context import (
    ContextPackBuilder,
    KeyLevels,
    MarketDataReader,
    MTFAContext,
    RegimeContext,
    RepositoryMarketDataReader,
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


# ---------------------------------------------------------------------------
# In-memory MarketDataReader for testing
# ---------------------------------------------------------------------------


class StubMarketDataReader:
    """In-memory reader that returns pre-loaded data.

    Satisfies the ``MarketDataReader`` protocol without touching the DB.
    """

    def __init__(
        self,
        bars: Optional[dict[str, pd.DataFrame]] = None,
        features: Optional[dict[str, pd.DataFrame]] = None,
        states: Optional[dict[str, pd.DataFrame]] = None,
    ):
        self._bars = bars or {}
        self._features = features or {}
        self._states = states or {}

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start=None,
        end=None,
        limit=None,
    ) -> pd.DataFrame:
        key = f"{symbol.upper()}_{timeframe}"
        df = self._bars.get(key, pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))
        if limit is not None and not df.empty:
            df = df.tail(limit)
        return df

    def get_features(
        self,
        symbol: str,
        timeframe: str,
        start=None,
        end=None,
    ) -> pd.DataFrame:
        key = f"{symbol.upper()}_{timeframe}"
        return self._features.get(key, pd.DataFrame())

    def get_latest_states(
        self,
        symbol: str,
        timeframe: str,
    ) -> pd.DataFrame:
        key = f"{symbol.upper()}_{timeframe}"
        return self._states.get(key, pd.DataFrame(columns=["state_id", "state_prob", "log_likelihood", "model_id"]))


def _make_bars_df(n: int = 5, base_price: float = 100.0) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame with ``n`` bars."""
    timestamps = pd.date_range("2025-01-01", periods=n, freq="5min")
    data = {
        "open": [base_price + i for i in range(n)],
        "high": [base_price + i + 1 for i in range(n)],
        "low": [base_price + i - 1 for i in range(n)],
        "close": [base_price + i + 0.5 for i in range(n)],
        "volume": [1000 * (i + 1) for i in range(n)],
    }
    return pd.DataFrame(data, index=timestamps)


def _make_features_df(n: int = 5, base_price: float = 100.0) -> pd.DataFrame:
    """Create a simple features DataFrame aligned with ``_make_bars_df``."""
    timestamps = pd.date_range("2025-01-01", periods=n, freq="5min")
    data = {
        "atr_14": [1.5 + 0.1 * i for i in range(n)],
        "sma_20": [base_price + i for i in range(n)],
        "vwap_60": [base_price + i + 0.2 for i in range(n)],
    }
    return pd.DataFrame(data, index=timestamps)


def _make_states_df(state_id: int = 2, state_prob: float = 0.85) -> pd.DataFrame:
    """Create a single-row states DataFrame."""
    ts = pd.Timestamp("2025-01-01 00:20:00")
    return pd.DataFrame(
        {
            "state_id": [state_id],
            "state_prob": [state_prob],
            "log_likelihood": [-42.0],
            "model_id": ["test_model_v1"],
        },
        index=pd.DatetimeIndex([ts]),
    )


class TestMarketDataReaderProtocol:
    """Verify the MarketDataReader protocol is satisfied by implementations."""

    def test_stub_reader_satisfies_protocol(self):
        """StubMarketDataReader should satisfy the runtime-checkable protocol."""
        reader = StubMarketDataReader()
        assert isinstance(reader, MarketDataReader)

    def test_repository_reader_satisfies_protocol(self):
        """RepositoryMarketDataReader should satisfy the protocol."""
        reader = RepositoryMarketDataReader()
        assert isinstance(reader, MarketDataReader)


class TestContextPackBuilderWithReader:
    """Tests for ContextPackBuilder.build() using an injected MarketDataReader."""

    def test_build_with_bars_only(self):
        """Builder returns bars when reader provides them."""
        reader = StubMarketDataReader(
            bars={"AAPL_5Min": _make_bars_df()},
        )
        builder = ContextPackBuilder(
            reader=reader,
            include_features=False,
            include_regimes=False,
            include_key_levels=False,
            cache_enabled=False,
        )

        ctx = builder.build("AAPL", "5Min", lookback_bars=100)

        assert ctx.symbol == "AAPL"
        assert ctx.primary_timeframe == "5Min"
        assert ctx.has_bars
        assert not ctx.has_features
        assert not ctx.has_regimes
        assert ctx.current_price == pytest.approx(104.5)
        assert ctx.current_volume == 5000

    def test_build_with_features(self):
        """Builder includes features when reader provides them."""
        bars_df = _make_bars_df()
        features_df = _make_features_df()
        reader = StubMarketDataReader(
            bars={"AAPL_5Min": bars_df},
            features={"AAPL_5Min": features_df},
        )
        builder = ContextPackBuilder(
            reader=reader,
            include_features=True,
            include_regimes=False,
            include_key_levels=False,
            cache_enabled=False,
        )

        ctx = builder.build("AAPL", "5Min")

        assert ctx.has_features
        assert ctx.atr == pytest.approx(1.9)  # Last atr_14 value
        assert ctx.get_feature("sma_20") is not None

    def test_build_with_regimes(self):
        """Builder includes regimes when reader provides state data."""
        reader = StubMarketDataReader(
            bars={"AAPL_5Min": _make_bars_df()},
            states={"AAPL_5Min": _make_states_df(state_id=2, state_prob=0.85)},
        )
        builder = ContextPackBuilder(
            reader=reader,
            include_features=False,
            include_regimes=True,
            include_key_levels=False,
            cache_enabled=False,
        )

        ctx = builder.build("AAPL", "5Min")

        assert ctx.has_regimes
        regime = ctx.primary_regime
        assert regime is not None
        assert regime.state_id == 2
        assert regime.state_prob == 0.85
        assert not regime.is_ood

    def test_build_no_data_returns_empty_context(self):
        """Builder works gracefully when reader has no data at all."""
        reader = StubMarketDataReader()
        builder = ContextPackBuilder(
            reader=reader,
            include_features=True,
            include_regimes=True,
            include_key_levels=True,
            cache_enabled=False,
        )

        ctx = builder.build("AAPL", "5Min")

        assert ctx.symbol == "AAPL"
        assert not ctx.has_bars
        assert not ctx.has_features
        assert not ctx.has_regimes
        assert ctx.current_price is None
        assert ctx.current_volume is None
        assert ctx.atr is None

    def test_build_with_key_levels_from_daily(self):
        """Key levels are computed from daily bars when available."""
        daily_bars = _make_bars_df(n=10, base_price=200.0)
        # Re-create with daily frequency
        daily_bars.index = pd.date_range("2025-01-01", periods=10, freq="D")
        reader = StubMarketDataReader(
            bars={
                "AAPL_5Min": _make_bars_df(),
                "AAPL_1Day": daily_bars,
            },
        )
        builder = ContextPackBuilder(
            reader=reader,
            include_features=False,
            include_regimes=False,
            include_key_levels=True,
            cache_enabled=False,
        )

        ctx = builder.build("AAPL", "5Min", additional_timeframes=["1Day"])

        assert ctx.key_levels is not None
        assert ctx.key_levels.prior_day_high is not None
        assert ctx.key_levels.pivot is not None

    def test_build_vwap_populated_from_features(self):
        """VWAP in key_levels is populated from the vwap_60 feature column."""
        daily_bars = _make_bars_df(n=10, base_price=200.0)
        daily_bars.index = pd.date_range("2025-01-01", periods=10, freq="D")
        bars_5min = _make_bars_df()
        features_5min = _make_features_df()

        reader = StubMarketDataReader(
            bars={
                "AAPL_5Min": bars_5min,
                "AAPL_1Day": daily_bars,
            },
            features={"AAPL_5Min": features_5min},
        )
        builder = ContextPackBuilder(
            reader=reader,
            include_features=True,
            include_regimes=False,
            include_key_levels=True,
            cache_enabled=False,
        )

        ctx = builder.build("AAPL", "5Min", additional_timeframes=["1Day"])

        assert ctx.key_levels is not None
        assert ctx.key_levels.vwap == pytest.approx(104.2)  # Last vwap_60 value

    def test_build_symbol_uppercased(self):
        """Symbol is normalised to uppercase regardless of input case."""
        reader = StubMarketDataReader(bars={"AAPL_5Min": _make_bars_df()})
        builder = ContextPackBuilder(
            reader=reader,
            include_features=False,
            include_regimes=False,
            include_key_levels=False,
            cache_enabled=False,
        )

        ctx = builder.build("aapl", "5Min")
        assert ctx.symbol == "AAPL"

    def test_default_builder_uses_repository_reader(self):
        """Builder created without explicit reader uses RepositoryMarketDataReader."""
        builder = ContextPackBuilder(
            include_features=False,
            include_regimes=False,
            include_key_levels=False,
            cache_enabled=False,
        )
        assert isinstance(builder._reader, RepositoryMarketDataReader)
