"""Online inference engine for HMM regime tracking.

Handles:
- Loading trained model artifacts
- Processing new bars in real-time
- Anti-chatter controls (min dwell, switch threshold)
- OOD detection
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np

from src.features.state.hmm.artifacts import ArtifactPaths
from src.features.state.hmm.contracts import HMMOutput, LatentStateVector, ModelMetadata
from src.features.state.hmm.encoders import BaseEncoder
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
            logger.info("[%s] OOD detected at %s: log_lik=%.2f < threshold=%s", symbol, timestamp, log_lik, self.ood_threshold)
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


def create_inference_engine(
    paths: ArtifactPaths,
    **kwargs,
) -> InferenceEngine:
    """Factory function to create an inference engine from saved artifacts.

    Args:
        paths: Model artifact paths
        **kwargs: Additional InferenceEngine arguments

    Returns:
        InferenceEngine
    """
    metadata = paths.load_metadata()
    scaler = BaseScaler.load(paths.scaler_path)
    encoder = BaseEncoder.load(paths.encoder_path)
    hmm = GaussianHMMWrapper.load(paths.hmm_path)

    return InferenceEngine(
        scaler=scaler,
        encoder=encoder,
        hmm=hmm,
        metadata=metadata,
        **kwargs,
    )
