"""Context infrastructure for trade evaluation.

Provides the ContextPack data container and ContextPackBuilder
for assembling market context data used by evaluators.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.data.database.connection import get_db_manager
from src.data.database.market_repository import OHLCVRepository
from src.features.state.hmm.contracts import Timeframe, VALID_TIMEFRAMES

logger = logging.getLogger(__name__)


@dataclass
class RegimeContext:
    """HMM regime context for a single timeframe.

    Attributes:
        timeframe: The timeframe this context applies to
        state_id: Current regime state ID (-1 for unknown)
        state_prob: Probability of the current state
        state_label: Semantic label (e.g., 'up_trending')
        entropy: Posterior entropy (uncertainty measure)
        transition_risk: Probability of state transition
        is_ood: Whether current observation is out-of-distribution
    """

    timeframe: str
    state_id: int
    state_prob: float
    state_label: Optional[str] = None
    entropy: Optional[float] = None
    transition_risk: Optional[float] = None
    is_ood: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timeframe": self.timeframe,
            "state_id": self.state_id,
            "state_prob": self.state_prob,
            "state_label": self.state_label,
            "entropy": self.entropy,
            "transition_risk": self.transition_risk,
            "is_ood": self.is_ood,
        }


@dataclass
class MTFAContext:
    """Multi-timeframe alignment context.

    Attributes:
        alignment_score: Fraction of timeframes agreeing (0-1), None if insufficient data
        conflicts: List of conflict descriptions between timeframes
        htf_trend: Trend from the highest available timeframe
    """

    alignment_score: Optional[float] = None
    conflicts: list[str] = field(default_factory=list)
    htf_trend: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "alignment_score": self.alignment_score,
            "conflicts": self.conflicts,
            "htf_trend": self.htf_trend,
        }


@dataclass
class KeyLevels:
    """Key price levels for context.

    Attributes:
        prior_day_high: Previous day's high
        prior_day_low: Previous day's low
        prior_day_close: Previous day's close
        pivot: Classic pivot point
        r1, r2: Resistance levels 1 and 2
        s1, s2: Support levels 1 and 2
        rolling_high_20: 20-day high
        rolling_low_20: 20-day low
        vwap: Current session VWAP (if available)
    """

    prior_day_high: Optional[float] = None
    prior_day_low: Optional[float] = None
    prior_day_close: Optional[float] = None
    pivot: Optional[float] = None
    r1: Optional[float] = None
    r2: Optional[float] = None
    s1: Optional[float] = None
    s2: Optional[float] = None
    rolling_high_20: Optional[float] = None
    rolling_low_20: Optional[float] = None
    vwap: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prior_day_high": self.prior_day_high,
            "prior_day_low": self.prior_day_low,
            "prior_day_close": self.prior_day_close,
            "pivot": self.pivot,
            "r1": self.r1,
            "r2": self.r2,
            "s1": self.s1,
            "s2": self.s2,
            "rolling_high_20": self.rolling_high_20,
            "rolling_low_20": self.rolling_low_20,
            "vwap": self.vwap,
        }

    def distance_to_nearest_level(self, price: float) -> tuple[str, float]:
        """Find the nearest key level to a given price.

        Returns:
            Tuple of (level_name, distance_percentage)
        """
        levels = {
            "pivot": self.pivot,
            "r1": self.r1,
            "r2": self.r2,
            "s1": self.s1,
            "s2": self.s2,
            "prior_day_high": self.prior_day_high,
            "prior_day_low": self.prior_day_low,
            "prior_day_close": self.prior_day_close,
            "vwap": self.vwap,
        }

        nearest_level = None
        nearest_distance = float("inf")
        nearest_name = "none"

        for name, level in levels.items():
            if level is not None:
                distance = abs(price - level) / price * 100  # As percentage
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_level = level
                    nearest_name = name

        return nearest_name, nearest_distance


@dataclass
class ContextPack:
    """Market context data container for trade evaluation.

    Aggregates all market context needed by evaluators:
    - OHLCV bars at multiple timeframes
    - Technical indicators/features
    - Regime states (HMM or PCA)
    - Key price levels
    - Current market snapshot

    Attributes:
        symbol: Ticker symbol
        timestamp: Context snapshot timestamp
        primary_timeframe: The main timeframe for evaluation
        bars: OHLCV bars by timeframe
        features: Technical indicators by timeframe
        regimes: Regime context by timeframe
        key_levels: Key price levels
        current_price: Latest price
        current_volume: Latest volume
        atr: Current ATR value (if available)
        metadata: Additional flexible data
    """

    symbol: str
    timestamp: datetime
    primary_timeframe: str
    bars: dict[str, pd.DataFrame] = field(default_factory=dict)
    features: dict[str, pd.DataFrame] = field(default_factory=dict)
    regimes: dict[str, RegimeContext] = field(default_factory=dict)
    key_levels: Optional[KeyLevels] = None
    current_price: Optional[float] = None
    current_volume: Optional[int] = None
    atr: Optional[float] = None
    mtfa: Optional[MTFAContext] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize."""
        self.symbol = self.symbol.upper()
        if self.primary_timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {self.primary_timeframe}")

    @property
    def has_bars(self) -> bool:
        """Check if any bars are available."""
        return len(self.bars) > 0 and any(not df.empty for df in self.bars.values())

    @property
    def has_features(self) -> bool:
        """Check if any features are available."""
        return len(self.features) > 0 and any(not df.empty for df in self.features.values())

    @property
    def has_regimes(self) -> bool:
        """Check if regime data is available."""
        return len(self.regimes) > 0

    @property
    def primary_regime(self) -> Optional[RegimeContext]:
        """Get regime context for primary timeframe."""
        return self.regimes.get(self.primary_timeframe)

    @property
    def primary_bars(self) -> Optional[pd.DataFrame]:
        """Get bars for primary timeframe."""
        return self.bars.get(self.primary_timeframe)

    @property
    def primary_features(self) -> Optional[pd.DataFrame]:
        """Get features for primary timeframe."""
        return self.features.get(self.primary_timeframe)

    def get_feature(self, name: str, timeframe: Optional[str] = None) -> Optional[float]:
        """Get the latest value of a specific feature.

        Args:
            name: Feature name
            timeframe: Timeframe (defaults to primary)

        Returns:
            Latest feature value or None
        """
        tf = timeframe or self.primary_timeframe
        features_df = self.features.get(tf)
        if features_df is None or features_df.empty:
            return None
        if name not in features_df.columns:
            return None
        value = features_df[name].iloc[-1]
        return float(value) if not pd.isna(value) else None

    def get_feature_series(
        self,
        name: str,
        timeframe: Optional[str] = None,
        lookback: Optional[int] = None,
    ) -> Optional[pd.Series]:
        """Get a feature series.

        Args:
            name: Feature name
            timeframe: Timeframe (defaults to primary)
            lookback: Number of bars to include (defaults to all)

        Returns:
            Feature series or None
        """
        tf = timeframe or self.primary_timeframe
        features_df = self.features.get(tf)
        if features_df is None or features_df.empty:
            return None
        if name not in features_df.columns:
            return None

        series = features_df[name]
        if lookback is not None:
            series = series.tail(lookback)
        return series

    def to_dict(self) -> dict:
        """Convert to dictionary (for caching/serialization)."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "primary_timeframe": self.primary_timeframe,
            "has_bars": self.has_bars,
            "has_features": self.has_features,
            "has_regimes": self.has_regimes,
            "regimes": {tf: r.to_dict() for tf, r in self.regimes.items()},
            "key_levels": self.key_levels.to_dict() if self.key_levels else None,
            "current_price": self.current_price,
            "current_volume": self.current_volume,
            "atr": self.atr,
            "mtfa": self.mtfa.to_dict() if self.mtfa else None,
            "metadata": self.metadata,
        }


class ContextPackBuilder:
    """Builder for assembling ContextPack from data sources.

    Integrates with OHLCVRepository for OHLCV and features,
    and optionally with InferenceEngine for regime data.

    Usage:
        builder = ContextPackBuilder()
        context = builder.build(
            symbol="AAPL",
            timeframe="5Min",
            lookback_bars=100,
        )
    """

    # Cache TTL in seconds
    CACHE_TTL = 60

    def __init__(
        self,
        include_features: bool = True,
        include_regimes: bool = True,
        include_key_levels: bool = True,
        cache_enabled: bool = True,
    ):
        """Initialize builder.

        Args:
            include_features: Whether to include technical indicators
            include_regimes: Whether to include regime data
            include_key_levels: Whether to compute key levels
            cache_enabled: Whether to cache context packs
        """
        self.include_features = include_features
        self.include_regimes = include_regimes
        self.include_key_levels = include_key_levels
        self.cache_enabled = cache_enabled
        self._cache: dict[str, tuple[datetime, ContextPack]] = {}

    def build(
        self,
        symbol: str,
        timeframe: str,
        lookback_bars: int = 100,
        additional_timeframes: Optional[list[str]] = None,
        as_of: Optional[datetime] = None,
    ) -> ContextPack:
        """Build a ContextPack for the given symbol and timeframe.

        Args:
            symbol: Ticker symbol
            timeframe: Primary timeframe
            lookback_bars: Number of bars to include
            additional_timeframes: Additional timeframes to include
            as_of: Point-in-time for context (defaults to now)

        Returns:
            Assembled ContextPack
        """
        symbol = symbol.upper()
        as_of = as_of or datetime.utcnow()

        # Check cache
        cache_key = f"{symbol}_{timeframe}_{lookback_bars}"
        if self.cache_enabled and cache_key in self._cache:
            cached_time, cached_pack = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self.CACHE_TTL:
                logger.debug(f"Using cached ContextPack for {cache_key}")
                return cached_pack

        # Build context
        timeframes = [timeframe]
        if additional_timeframes:
            timeframes.extend([tf for tf in additional_timeframes if tf != timeframe])

        bars: dict[str, pd.DataFrame] = {}
        features: dict[str, pd.DataFrame] = {}
        regimes: dict[str, RegimeContext] = {}

        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            repo = OHLCVRepository(session)

            for tf in timeframes:
                # Get OHLCV bars
                df = repo.get_bars(symbol, tf, limit=lookback_bars)
                if not df.empty:
                    bars[tf] = df

                # Get features
                if self.include_features:
                    features_df = repo.get_features(symbol, tf)
                    if not features_df.empty:
                        # Align with bars
                        if tf in bars:
                            features_df = features_df[features_df.index.isin(bars[tf].index)]
                        features[tf] = features_df.tail(lookback_bars)

                # Get regime states
                if self.include_regimes:
                    states_df = repo.get_latest_states(symbol, tf)
                    if not states_df.empty:
                        latest = states_df.iloc[0]
                        state_id = int(latest.get("state_id", -1))
                        state_prob = float(latest.get("state_prob", 0.0))
                        model_id = latest.get("model_id")

                        state_label, transition_risk, entropy = self._load_regime_enrichment(
                            symbol, tf, state_id, state_prob, model_id
                        )

                        regimes[tf] = RegimeContext(
                            timeframe=tf,
                            state_id=state_id,
                            state_prob=state_prob,
                            state_label=state_label,
                            entropy=entropy,
                            transition_risk=transition_risk,
                            is_ood=state_id == -1,
                        )

        # Compute key levels
        key_levels = None
        if self.include_key_levels and "1Day" in bars:
            key_levels = self._compute_key_levels(bars["1Day"])
        elif self.include_key_levels and timeframe in bars:
            # Fall back to primary timeframe
            key_levels = self._compute_key_levels(bars[timeframe])

        # Populate VWAP from features if available
        if key_levels is not None and timeframe in features and not features[timeframe].empty:
            tf_features = features[timeframe]
            if "vwap_60" in tf_features.columns:
                vwap_val = tf_features["vwap_60"].iloc[-1]
                if not pd.isna(vwap_val):
                    key_levels.vwap = float(vwap_val)

        # Compute MTFA alignment
        mtfa = self._compute_mtfa(regimes, timeframe)

        # Get current price and volume
        current_price = None
        current_volume = None
        atr = None

        if timeframe in bars and not bars[timeframe].empty:
            latest_bar = bars[timeframe].iloc[-1]
            current_price = float(latest_bar["close"])
            current_volume = int(latest_bar["volume"])

        if timeframe in features and not features[timeframe].empty:
            atr_col = "atr_14" if "atr_14" in features[timeframe].columns else None
            if atr_col:
                atr_val = features[timeframe][atr_col].iloc[-1]
                atr = float(atr_val) if not pd.isna(atr_val) else None

        # Build context pack
        context = ContextPack(
            symbol=symbol,
            timestamp=as_of,
            primary_timeframe=timeframe,
            bars=bars,
            features=features,
            regimes=regimes,
            key_levels=key_levels,
            current_price=current_price,
            current_volume=current_volume,
            atr=atr,
            mtfa=mtfa,
        )

        # Cache result
        if self.cache_enabled:
            self._cache[cache_key] = (datetime.utcnow(), context)

        logger.debug(
            f"Built ContextPack for {symbol}/{timeframe}: "
            f"bars={len(bars)}, features={len(features)}, regimes={len(regimes)}"
        )

        return context

    def _compute_key_levels(self, daily_bars: pd.DataFrame) -> KeyLevels:
        """Compute key price levels from daily bars.

        Args:
            daily_bars: Daily OHLCV DataFrame

        Returns:
            KeyLevels with computed values
        """
        if daily_bars.empty or len(daily_bars) < 2:
            return KeyLevels()

        # Prior day values
        prior_bar = daily_bars.iloc[-2] if len(daily_bars) >= 2 else daily_bars.iloc[-1]
        prior_high = float(prior_bar["high"])
        prior_low = float(prior_bar["low"])
        prior_close = float(prior_bar["close"])

        # Classic pivot points
        pivot = (prior_high + prior_low + prior_close) / 3
        r1 = 2 * pivot - prior_low
        s1 = 2 * pivot - prior_high
        r2 = pivot + (prior_high - prior_low)
        s2 = pivot - (prior_high - prior_low)

        # Rolling high/low (20 days)
        lookback = min(20, len(daily_bars))
        rolling_high = float(daily_bars["high"].tail(lookback).max())
        rolling_low = float(daily_bars["low"].tail(lookback).min())

        return KeyLevels(
            prior_day_high=prior_high,
            prior_day_low=prior_low,
            prior_day_close=prior_close,
            pivot=pivot,
            r1=r1,
            r2=r2,
            s1=s1,
            s2=s2,
            rolling_high_20=rolling_high,
            rolling_low_20=rolling_low,
        )

    @staticmethod
    def _compute_approximate_entropy(state_prob: float, n_states: int) -> Optional[float]:
        """Approximate posterior entropy from the max state probability.

        Since only the argmax probability is stored in the DB (not the full
        posterior), we approximate entropy assuming maximum-entropy distribution
        consistent with the observed max probability:
            H = -p*log(p) - (n-1)*q*log(q)  where q = (1-p)/(n-1)

        Args:
            state_prob: Probability of the most likely state
            n_states: Number of HMM states

        Returns:
            Approximate entropy in nats, or None if inputs are invalid
        """
        if n_states < 2 or state_prob <= 0 or state_prob > 1:
            return None

        p = min(state_prob, 1.0 - 1e-10)
        q = (1.0 - p) / (n_states - 1)

        entropy = -p * math.log(p)
        if q > 1e-10:
            entropy -= (n_states - 1) * q * math.log(q)

        return entropy

    def _load_regime_enrichment(
        self,
        symbol: str,
        timeframe: str,
        state_id: int,
        state_prob: float,
        model_id: Optional[str],
    ) -> tuple[Optional[str], Optional[float], Optional[float]]:
        """Best-effort loading of regime enrichment from HMM model artifacts.

        Loads state labels, transition risk, and computes approximate entropy.
        Degrades gracefully if model artifacts are unavailable.

        Args:
            symbol: Ticker symbol
            timeframe: Bar timeframe
            state_id: Current regime state ID
            state_prob: Probability of current state
            model_id: Model identifier from the DB

        Returns:
            Tuple of (state_label, transition_risk, entropy)
        """
        state_label: Optional[str] = None
        transition_risk: Optional[float] = None
        n_states = 8  # Default if metadata unavailable

        try:
            from src.features.state.hmm.artifacts import get_latest_model

            artifact_paths = get_latest_model(symbol, timeframe)
            if artifact_paths is not None and artifact_paths.exists():
                metadata = artifact_paths.load_metadata()
                n_states = metadata.n_states

                # State label from metadata mapping
                if metadata.state_mapping and str(state_id) in metadata.state_mapping:
                    mapping = metadata.state_mapping[str(state_id)]
                    if isinstance(mapping, dict):
                        state_label = mapping.get("label", f"state_{state_id}")
                    else:
                        state_label = str(mapping)

                # Transition risk from HMM transition matrix
                if state_id >= 0:
                    try:
                        from src.features.state.hmm.hmm_model import GaussianHMMWrapper

                        hmm_model = GaussianHMMWrapper.load(artifact_paths.hmm_path)
                        transmat = hmm_model.transition_matrix
                        if state_id < transmat.shape[0]:
                            row = transmat[state_id].copy()
                            row[state_id] = 0.0  # Zero out self-transition
                            transition_risk = float(row.max())
                    except Exception as e:
                        logger.debug(f"Could not load HMM transition matrix for {symbol}/{timeframe}: {e}")

        except Exception as e:
            logger.debug(f"Could not load model artifacts for {symbol}/{timeframe}: {e}")

        # Fall back to generic label
        if state_label is None and state_id >= 0:
            state_label = f"state_{state_id}"

        # Entropy is always computable from state_prob
        entropy = self._compute_approximate_entropy(state_prob, n_states)

        return state_label, transition_risk, entropy

    # Timeframe ordering for MTFA (lowest to highest)
    _TF_ORDER = ["1Min", "5Min", "15Min", "1Hour", "1Day"]

    def _compute_mtfa(
        self,
        regimes: dict[str, RegimeContext],
        primary_timeframe: str,
    ) -> MTFAContext:
        """Compute multi-timeframe alignment from regime data.

        Args:
            regimes: Regime context by timeframe
            primary_timeframe: The primary trading timeframe

        Returns:
            MTFAContext with alignment score, conflicts, and HTF trend
        """
        # Filter to regimes with valid (non-OOD) state data
        valid_regimes = {
            tf: r for tf, r in regimes.items()
            if r.state_id != -1
        }

        if len(valid_regimes) < 2:
            return MTFAContext()

        # Extract directional labels for each timeframe
        directions: dict[str, str] = {}
        for tf, regime in valid_regimes.items():
            directions[tf] = regime.state_label or f"state_{regime.state_id}"

        # Determine majority direction
        label_counts: dict[str, int] = {}
        for label in directions.values():
            label_counts[label] = label_counts.get(label, 0) + 1

        majority_label = max(label_counts, key=label_counts.get)
        agreeing = sum(1 for label in directions.values() if label == majority_label)
        alignment_score = agreeing / len(directions)

        # Build conflict list
        conflicts = []
        for tf in self._TF_ORDER:
            if tf in directions and directions[tf] != majority_label:
                conflicts.append(f"{tf}: {directions[tf]} (vs majority: {majority_label})")

        # HTF trend = trend from highest available timeframe
        htf_trend = None
        for tf in reversed(self._TF_ORDER):
            if tf in directions:
                htf_trend = directions[tf]
                break

        return MTFAContext(
            alignment_score=alignment_score,
            conflicts=conflicts,
            htf_trend=htf_trend,
        )

    def clear_cache(self) -> None:
        """Clear the context cache."""
        self._cache.clear()
        logger.debug("Cleared ContextPack cache")


# Singleton builder instance
_default_builder: Optional[ContextPackBuilder] = None


def get_context_builder() -> ContextPackBuilder:
    """Get the default ContextPackBuilder instance."""
    global _default_builder
    if _default_builder is None:
        _default_builder = ContextPackBuilder()
    return _default_builder
