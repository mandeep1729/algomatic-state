"""Online inference engine for HMM regime tracking.

Handles:
- Loading trained model artifacts
- Processing new bars in real-time
- Anti-chatter controls (min dwell, switch threshold)
- OOD detection
- Rolling feature buffer for online computation
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.features.state.hmm.artifacts import ArtifactPaths
from src.features.state.hmm.contracts import HMMOutput, LatentStateVector, ModelMetadata, VALID_TIMEFRAMES
from src.features.state.hmm.encoders import BaseEncoder, TemporalPCAEncoder
from src.features.state.hmm.hmm_model import GaussianHMMWrapper
from src.features.state.hmm.scalers import BaseScaler

logger = logging.getLogger(__name__)


@dataclass
class InferenceState:
    """Internal state for online inference.

    Tracks information needed for anti-chatter logic.
    """

    current_state: int
    current_prob: float
    dwell_count: int
    last_timestamp: Optional[datetime]
    recent_states: list[int]


class InferenceEngine:
    """Online inference engine for state vector regime tracking.

    Features:
    - Loads trained model artifacts
    - Processes new feature vectors
    - Anti-chatter controls
    - OOD detection
    """

    def __init__(
        self,
        scaler: BaseScaler,
        encoder: BaseEncoder,
        hmm: GaussianHMMWrapper,
        metadata: ModelMetadata,
        p_switch_threshold: float = 0.6,
        min_dwell_bars: int = 3,
        ood_threshold: Optional[float] = None,
        majority_vote_window: int = 3,
    ):
        """Initialize inference engine.

        Args:
            scaler: Fitted scaler
            encoder: Fitted encoder
            hmm: Fitted HMM
            metadata: Model metadata
            p_switch_threshold: Min probability to switch states
            min_dwell_bars: Min bars to stay in a state before switching
            ood_threshold: Log-likelihood threshold for OOD (None uses metadata)
            majority_vote_window: Window size for majority vote smoothing
        """
        self.scaler = scaler
        self.encoder = encoder
        self.hmm = hmm
        self.metadata = metadata

        self.p_switch_threshold = p_switch_threshold
        self.min_dwell_bars = min_dwell_bars
        self.ood_threshold = ood_threshold or metadata.ood_threshold
        self.majority_vote_window = majority_vote_window

        self._state = InferenceState(
            current_state=-1,
            current_prob=0.0,
            dwell_count=0,
            last_timestamp=None,
            recent_states=[],
        )

    @classmethod
    def from_artifacts(
        cls,
        paths: ArtifactPaths,
        p_switch_threshold: Optional[float] = None,
        min_dwell_bars: Optional[int] = None,
    ) -> "InferenceEngine":
        """Load inference engine from saved artifacts.

        Args:
            paths: ArtifactPaths pointing to model directory
            p_switch_threshold: Override probability threshold
            min_dwell_bars: Override minimum dwell time

        Returns:
            Initialized InferenceEngine
        """
        if not paths.exists():
            logger.error(f"Model artifacts not found at {paths.model_dir}")
            raise FileNotFoundError(f"Model artifacts not found at {paths.model_dir}")

        logger.info(f"Loading model artifacts from {paths.model_dir}")
        metadata = paths.load_metadata()
        logger.debug(f"Loading scaler from {paths.scaler_path}")
        scaler = BaseScaler.load(paths.scaler_path)
        logger.debug(f"Loading encoder from {paths.encoder_path}")
        encoder = BaseEncoder.load(paths.encoder_path)
        logger.debug(f"Loading HMM from {paths.hmm_path}")
        hmm = GaussianHMMWrapper.load(paths.hmm_path)
        logger.info(f"Model loaded: {metadata.model_id} with {metadata.n_states} states, {len(metadata.feature_names)} features")

        return cls(
            scaler=scaler,
            encoder=encoder,
            hmm=hmm,
            metadata=metadata,
            p_switch_threshold=p_switch_threshold or 0.6,
            min_dwell_bars=min_dwell_bars or 3,
        )

    def reset(self) -> None:
        """Reset internal state for new symbol/session."""
        self._state = InferenceState(
            current_state=-1,
            current_prob=0.0,
            dwell_count=0,
            last_timestamp=None,
            recent_states=[],
        )

    def process(
        self,
        features: dict[str, float],
        symbol: str,
        timestamp: datetime,
    ) -> HMMOutput:
        """Process a single bar's features and return regime inference.

        Args:
            features: Dictionary of feature name -> value
            symbol: Ticker symbol
            timestamp: Bar close timestamp

        Returns:
            HMMOutput with state inference
        """
        x = np.array([features.get(name, np.nan) for name in self.metadata.feature_names])
        x = x.reshape(1, -1)

        x_scaled = self.scaler.transform(x)

        z = self.encoder.transform(x_scaled)

        posterior = self.hmm.predict_proba(z)[0]
        log_lik = self.hmm.emission_log_likelihood(z)[0]

        if np.isnan(log_lik) or log_lik < self.ood_threshold:
            self._state.dwell_count += 1
            logger.debug(f"[{symbol}] OOD detected at {timestamp}: log_lik={log_lik:.2f} < threshold={self.ood_threshold}")
            return HMMOutput.unknown(
                symbol=symbol,
                timestamp=timestamp,
                timeframe=self.metadata.timeframe,
                model_id=self.metadata.model_id,
                n_states=self.metadata.n_states,
                log_likelihood=log_lik if not np.isnan(log_lik) else -np.inf,
                z=z[0],
            )

        raw_state = np.argmax(posterior)
        raw_prob = posterior[raw_state]

        final_state = self._apply_anti_chatter(raw_state, raw_prob)

        # Log state transitions
        if final_state != self._state.current_state and self._state.current_state != -1:
            logger.debug(f"[{symbol}] State transition at {timestamp}: {self._state.current_state} -> {final_state} (prob={raw_prob:.3f})")

        self._state.last_timestamp = timestamp
        self._state.recent_states.append(raw_state)
        if len(self._state.recent_states) > self.majority_vote_window:
            self._state.recent_states.pop(0)

        return HMMOutput(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=self.metadata.timeframe,
            model_id=self.metadata.model_id,
            state_id=final_state,
            state_prob=posterior[final_state],
            posterior=posterior,
            log_likelihood=log_lik,
            is_ood=False,
            z=z[0],
        )

    def _apply_anti_chatter(self, raw_state: int, raw_prob: float) -> int:
        """Apply anti-chatter logic to state transition.

        Args:
            raw_state: State from HMM posterior
            raw_prob: Probability of raw state

        Returns:
            Final state after anti-chatter
        """
        if self._state.current_state == -1:
            self._state.current_state = raw_state
            self._state.current_prob = raw_prob
            self._state.dwell_count = 1
            return raw_state

        if raw_state == self._state.current_state:
            self._state.dwell_count += 1
            self._state.current_prob = raw_prob
            return raw_state

        if self._state.dwell_count < self.min_dwell_bars:
            self._state.dwell_count += 1
            return self._state.current_state

        if raw_prob < self.p_switch_threshold:
            self._state.dwell_count += 1
            return self._state.current_state

        if len(self._state.recent_states) >= self.majority_vote_window:
            counts = np.bincount(
                self._state.recent_states[-self.majority_vote_window:],
                minlength=self.hmm.n_states,
            )
            majority_state = np.argmax(counts)
            if majority_state != raw_state:
                self._state.dwell_count += 1
                return self._state.current_state

        self._state.current_state = raw_state
        self._state.current_prob = raw_prob
        self._state.dwell_count = 1
        return raw_state

    def process_batch(
        self,
        features_list: list[dict[str, float]],
        symbol: str,
        timestamps: list[datetime],
    ) -> list[HMMOutput]:
        """Process multiple bars (for backtest/batch inference).

        Note: This processes sequentially to maintain state.

        Args:
            features_list: List of feature dictionaries
            symbol: Ticker symbol
            timestamps: List of bar timestamps

        Returns:
            List of HMMOutput objects
        """
        self.reset()
        outputs = []
        for features, ts in zip(features_list, timestamps):
            output = self.process(features, symbol, ts)
            outputs.append(output)
        return outputs

    def get_latent_vector(
        self,
        features: dict[str, float],
    ) -> LatentStateVector:
        """Get latent vector without state inference.

        Useful for diagnostics and visualization.

        Args:
            features: Dictionary of feature name -> value

        Returns:
            LatentStateVector
        """
        x = np.array([features.get(name, np.nan) for name in self.metadata.feature_names])
        x = x.reshape(1, -1)

        x_scaled = self.scaler.transform(x)
        z = self.encoder.transform(x_scaled)[0]

        return LatentStateVector(
            symbol="",
            timestamp=datetime.now(),
            timeframe=self.metadata.timeframe,
            z=z,
        )


class MultiTimeframeInferenceEngine:
    """Coordinate inference across multiple timeframes.

    Handles:
    - Carrying forward higher timeframe states
    - State validity TTL
    - Hierarchical state combination
    """

    def __init__(self):
        """Initialize multi-timeframe engine."""
        self.engines: dict[str, InferenceEngine] = {}
        self.latest_outputs: dict[str, HMMOutput] = {}
        self.output_timestamps: dict[str, datetime] = {}

    def add_engine(self, timeframe: str, engine: InferenceEngine) -> None:
        """Add an inference engine for a timeframe.

        Args:
            timeframe: Timeframe string
            engine: InferenceEngine for that timeframe
        """
        self.engines[timeframe] = engine

    def process(
        self,
        timeframe: str,
        features: dict[str, float],
        symbol: str,
        timestamp: datetime,
    ) -> HMMOutput:
        """Process features for a specific timeframe.

        Args:
            timeframe: Which timeframe this bar is for
            features: Feature dictionary
            symbol: Ticker symbol
            timestamp: Bar timestamp

        Returns:
            HMMOutput for the timeframe
        """
        if timeframe not in self.engines:
            raise ValueError(f"No engine registered for timeframe {timeframe}")

        engine = self.engines[timeframe]
        output = engine.process(features, symbol, timestamp)

        self.latest_outputs[timeframe] = output
        self.output_timestamps[timeframe] = timestamp

        return output

    def get_current_state(
        self,
        timeframe: str,
        current_time: datetime,
    ) -> Optional[HMMOutput]:
        """Get current state for a timeframe with TTL check.

        Args:
            timeframe: Timeframe to query
            current_time: Current timestamp for TTL check

        Returns:
            Latest valid HMMOutput or None if expired
        """
        if timeframe not in self.latest_outputs:
            return None

        output = self.latest_outputs[timeframe]
        output_time = self.output_timestamps[timeframe]

        engine = self.engines[timeframe]
        ttl_bars = engine.metadata.state_ttl_bars

        from datetime import timedelta
        bar_durations = {
            "1Min": timedelta(minutes=1),
            "5Min": timedelta(minutes=5),
            "15Min": timedelta(minutes=15),
            "1Hour": timedelta(hours=1),
            "1Day": timedelta(days=1),
        }
        bar_dur = bar_durations.get(timeframe, timedelta(minutes=1))
        max_age = bar_dur * ttl_bars

        if current_time - output_time > max_age:
            return None

        return output

    def get_all_states(
        self,
        current_time: datetime,
    ) -> dict[str, Optional[HMMOutput]]:
        """Get current states for all timeframes.

        Args:
            current_time: Current timestamp for TTL checks

        Returns:
            Dictionary mapping timeframe -> HMMOutput (or None if expired)
        """
        return {
            tf: self.get_current_state(tf, current_time)
            for tf in self.engines
        }

    def reset_all(self) -> None:
        """Reset all engines."""
        for engine in self.engines.values():
            engine.reset()
        self.latest_outputs.clear()
        self.output_timestamps.clear()


@dataclass
class BarData:
    """OHLCV bar data for rolling buffer."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    features: dict[str, float] = field(default_factory=dict)


class RollingFeatureBuffer:
    """Rolling buffer for maintaining feature computation state.

    Maintains a fixed-size window of recent bars and pre-computed
    features for efficient online feature computation.
    """

    def __init__(
        self,
        max_lookback: int = 100,
        feature_names: Optional[list[str]] = None,
    ):
        """Initialize rolling buffer.

        Args:
            max_lookback: Maximum number of bars to retain
            feature_names: Optional list of feature names to track
        """
        self.max_lookback = max_lookback
        self.feature_names = feature_names or []
        self._bars: deque[BarData] = deque(maxlen=max_lookback)
        self._feature_cache: dict[str, deque] = {}

        for name in self.feature_names:
            self._feature_cache[name] = deque(maxlen=max_lookback)

    def add_bar(self, bar: BarData) -> None:
        """Add a new bar to the buffer.

        Args:
            bar: BarData with OHLCV and optional features
        """
        self._bars.append(bar)

        for name in self.feature_names:
            value = bar.features.get(name, np.nan)
            self._feature_cache[name].append(value)

    def add_ohlcv(
        self,
        timestamp: datetime,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        features: Optional[dict[str, float]] = None,
    ) -> None:
        """Add a bar from OHLCV values.

        Args:
            timestamp: Bar timestamp
            open_: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
            features: Optional pre-computed features
        """
        bar = BarData(
            timestamp=timestamp,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            features=features or {},
        )
        self.add_bar(bar)

    def get_closes(self, n: Optional[int] = None) -> np.ndarray:
        """Get recent close prices.

        Args:
            n: Number of bars (None for all)

        Returns:
            Array of close prices
        """
        bars = list(self._bars)
        if n is not None:
            bars = bars[-n:]
        return np.array([b.close for b in bars])

    def get_highs(self, n: Optional[int] = None) -> np.ndarray:
        """Get recent high prices."""
        bars = list(self._bars)
        if n is not None:
            bars = bars[-n:]
        return np.array([b.high for b in bars])

    def get_lows(self, n: Optional[int] = None) -> np.ndarray:
        """Get recent low prices."""
        bars = list(self._bars)
        if n is not None:
            bars = bars[-n:]
        return np.array([b.low for b in bars])

    def get_volumes(self, n: Optional[int] = None) -> np.ndarray:
        """Get recent volumes."""
        bars = list(self._bars)
        if n is not None:
            bars = bars[-n:]
        return np.array([b.volume for b in bars])

    def get_feature(self, name: str, n: Optional[int] = None) -> np.ndarray:
        """Get recent values of a feature.

        Args:
            name: Feature name
            n: Number of bars

        Returns:
            Array of feature values
        """
        if name not in self._feature_cache:
            return np.array([])

        values = list(self._feature_cache[name])
        if n is not None:
            values = values[-n:]
        return np.array(values)

    def get_latest_features(self) -> dict[str, float]:
        """Get the latest feature values.

        Returns:
            Dictionary of feature name -> latest value
        """
        if not self._bars:
            return {}
        return self._bars[-1].features.copy()

    def get_feature_matrix(
        self,
        feature_names: list[str],
        n: Optional[int] = None,
    ) -> np.ndarray:
        """Get feature matrix for multiple features.

        Args:
            feature_names: List of feature names
            n: Number of bars

        Returns:
            2D array of shape (n_bars, n_features)
        """
        arrays = []
        for name in feature_names:
            arr = self.get_feature(name, n)
            arrays.append(arr)

        if not arrays:
            return np.array([])

        return np.column_stack(arrays)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert buffer to DataFrame.

        Returns:
            DataFrame with OHLCV and features
        """
        if not self._bars:
            return pd.DataFrame()

        data = {
            "timestamp": [b.timestamp for b in self._bars],
            "open": [b.open for b in self._bars],
            "high": [b.high for b in self._bars],
            "low": [b.low for b in self._bars],
            "close": [b.close for b in self._bars],
            "volume": [b.volume for b in self._bars],
        }

        for name in self.feature_names:
            data[name] = list(self._feature_cache[name])

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    @property
    def size(self) -> int:
        """Return current buffer size."""
        return len(self._bars)

    @property
    def is_ready(self) -> bool:
        """Check if buffer has enough data for inference."""
        return len(self._bars) >= self.max_lookback

    def clear(self) -> None:
        """Clear the buffer."""
        self._bars.clear()
        for cache in self._feature_cache.values():
            cache.clear()


class TemporalInferenceEngine(InferenceEngine):
    """Inference engine with temporal window support.

    Extends InferenceEngine to handle temporal encoders that
    require a window of past observations.
    """

    def __init__(
        self,
        scaler: BaseScaler,
        encoder: BaseEncoder,
        hmm: GaussianHMMWrapper,
        metadata: ModelMetadata,
        window_size: int = 5,
        **kwargs,
    ):
        """Initialize temporal inference engine.

        Args:
            scaler: Fitted scaler
            encoder: Fitted encoder (should be TemporalPCAEncoder)
            hmm: Fitted HMM
            metadata: Model metadata
            window_size: Size of temporal window
            **kwargs: Additional arguments for InferenceEngine
        """
        super().__init__(scaler, encoder, hmm, metadata, **kwargs)
        self.window_size = window_size
        self._feature_buffer: deque = deque(maxlen=window_size)

    def reset(self) -> None:
        """Reset internal state and feature buffer."""
        super().reset()
        self._feature_buffer.clear()

    def process(
        self,
        features: dict[str, float],
        symbol: str,
        timestamp: datetime,
    ) -> HMMOutput:
        """Process features with temporal windowing.

        Args:
            features: Feature dictionary
            symbol: Ticker symbol
            timestamp: Bar timestamp

        Returns:
            HMMOutput
        """
        x = np.array([features.get(name, np.nan) for name in self.metadata.feature_names])
        x_scaled = self.scaler.transform(x.reshape(1, -1))[0]

        self._feature_buffer.append(x_scaled)

        if len(self._feature_buffer) < self.window_size:
            return HMMOutput.unknown(
                symbol=symbol,
                timestamp=timestamp,
                timeframe=self.metadata.timeframe,
                model_id=self.metadata.model_id,
                n_states=self.metadata.n_states,
                log_likelihood=-np.inf,
                z=None,
            )

        window = np.array(list(self._feature_buffer))
        window = window.reshape(1, self.window_size, -1)

        z = self.encoder.transform(window)

        posterior = self.hmm.predict_proba(z)[0]
        log_lik = self.hmm.emission_log_likelihood(z)[0]

        if np.isnan(log_lik) or log_lik < self.ood_threshold:
            self._state.dwell_count += 1
            return HMMOutput.unknown(
                symbol=symbol,
                timestamp=timestamp,
                timeframe=self.metadata.timeframe,
                model_id=self.metadata.model_id,
                n_states=self.metadata.n_states,
                log_likelihood=log_lik if not np.isnan(log_lik) else -np.inf,
                z=z[0],
            )

        raw_state = np.argmax(posterior)
        raw_prob = posterior[raw_state]

        final_state = self._apply_anti_chatter(raw_state, raw_prob)

        self._state.last_timestamp = timestamp
        self._state.recent_states.append(raw_state)
        if len(self._state.recent_states) > self.majority_vote_window:
            self._state.recent_states.pop(0)

        return HMMOutput(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=self.metadata.timeframe,
            model_id=self.metadata.model_id,
            state_id=final_state,
            state_prob=posterior[final_state],
            posterior=posterior,
            log_likelihood=log_lik,
            is_ood=False,
            z=z[0],
        )


def create_inference_engine(
    paths: ArtifactPaths,
    window_size: Optional[int] = None,
    **kwargs,
) -> InferenceEngine:
    """Factory function to create appropriate inference engine.

    Automatically selects TemporalInferenceEngine if encoder requires it.

    Args:
        paths: Model artifact paths
        window_size: Optional window size override
        **kwargs: Additional InferenceEngine arguments

    Returns:
        InferenceEngine or TemporalInferenceEngine
    """
    metadata = paths.load_metadata()
    scaler = BaseScaler.load(paths.scaler_path)
    encoder = BaseEncoder.load(paths.encoder_path)
    hmm = GaussianHMMWrapper.load(paths.hmm_path)

    if isinstance(encoder, TemporalPCAEncoder):
        ws = window_size or encoder.window_size
        return TemporalInferenceEngine(
            scaler=scaler,
            encoder=encoder,
            hmm=hmm,
            metadata=metadata,
            window_size=ws,
            **kwargs,
        )

    return InferenceEngine(
        scaler=scaler,
        encoder=encoder,
        hmm=hmm,
        metadata=metadata,
        **kwargs,
    )
