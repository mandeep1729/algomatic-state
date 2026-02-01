"""Operations and monitoring for state vector models.

Implements:
- Monitoring metrics and dashboard data
- Drift detection
- Shadow inference for candidate models
- Model rollout management
- Retraining triggers
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from src.features.state.hmm.artifacts import ArtifactPaths, get_model_path, list_models
from src.features.state.hmm.contracts import HMMOutput, VALID_TIMEFRAMES
from src.features.state.hmm.inference import InferenceEngine, create_inference_engine


logger = logging.getLogger(__name__)


@dataclass
class MonitoringMetrics:
    """Real-time monitoring metrics."""

    timestamp: datetime
    timeframe: str
    model_id: str

    posterior_entropy: float
    max_posterior_prob: float
    log_likelihood: float
    current_state: int
    ood_rate_rolling: float
    state_occupancy: dict[int, float]

    entropy_zscore: float = 0.0
    ll_zscore: float = 0.0
    alerts: list[str] = field(default_factory=list)


@dataclass
class DriftAlert:
    """Alert for detected drift."""

    timestamp: datetime
    alert_type: str
    severity: str
    message: str
    metric_value: float
    threshold: float


class MetricsCollector:
    """Collect and aggregate monitoring metrics."""

    def __init__(
        self,
        window_size: int = 1000,
        entropy_threshold: float = 2.0,
        ll_threshold: float = -3.0,
    ):
        """Initialize metrics collector.

        Args:
            window_size: Rolling window for statistics
            entropy_threshold: Z-score threshold for entropy alerts
            ll_threshold: Z-score threshold for log-likelihood alerts
        """
        self.window_size = window_size
        self.entropy_threshold = entropy_threshold
        self.ll_threshold = ll_threshold

        self._entropies: list[float] = []
        self._log_likelihoods: list[float] = []
        self._states: list[int] = []
        self._ood_flags: list[bool] = []
        self._timestamps: list[datetime] = []

    def update(self, output: HMMOutput) -> MonitoringMetrics:
        """Update metrics with new inference output.

        Args:
            output: HMM inference output

        Returns:
            Current monitoring metrics
        """
        self._entropies.append(output.entropy)
        self._log_likelihoods.append(output.log_likelihood)
        self._states.append(output.state_id)
        self._ood_flags.append(output.is_ood)
        self._timestamps.append(output.timestamp)

        if len(self._entropies) > self.window_size:
            self._entropies.pop(0)
            self._log_likelihoods.pop(0)
            self._states.pop(0)
            self._ood_flags.pop(0)
            self._timestamps.pop(0)

        entropy_mean = np.mean(self._entropies)
        entropy_std = np.std(self._entropies) + 1e-6
        entropy_zscore = (output.entropy - entropy_mean) / entropy_std

        ll_mean = np.mean(self._log_likelihoods)
        ll_std = np.std(self._log_likelihoods) + 1e-6
        ll_zscore = (output.log_likelihood - ll_mean) / ll_std

        ood_rate = sum(self._ood_flags) / len(self._ood_flags)

        state_counts = np.bincount(
            [s for s in self._states if s >= 0],
            minlength=output.n_states,
        )
        state_occupancy = {
            i: count / max(len(self._states), 1)
            for i, count in enumerate(state_counts)
        }

        alerts = []
        if entropy_zscore > self.entropy_threshold:
            alerts.append(f"High entropy spike: z={entropy_zscore:.2f}")
        if ll_zscore < self.ll_threshold:
            alerts.append(f"Low log-likelihood: z={ll_zscore:.2f}")
        if ood_rate > 0.1:
            alerts.append(f"High OOD rate: {ood_rate:.1%}")

        return MonitoringMetrics(
            timestamp=output.timestamp,
            timeframe=output.timeframe,
            model_id=output.model_id,
            posterior_entropy=output.entropy,
            max_posterior_prob=output.state_prob,
            log_likelihood=output.log_likelihood,
            current_state=output.state_id,
            ood_rate_rolling=ood_rate,
            state_occupancy=state_occupancy,
            entropy_zscore=entropy_zscore,
            ll_zscore=ll_zscore,
            alerts=alerts,
        )

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        if not self._entropies:
            return {}

        return {
            "n_samples": len(self._entropies),
            "mean_entropy": float(np.mean(self._entropies)),
            "std_entropy": float(np.std(self._entropies)),
            "mean_log_likelihood": float(np.mean(self._log_likelihoods)),
            "std_log_likelihood": float(np.std(self._log_likelihoods)),
            "ood_rate": sum(self._ood_flags) / len(self._ood_flags),
            "state_distribution": dict(
                zip(*np.unique(self._states, return_counts=True))
            ),
        }

    def reset(self) -> None:
        """Reset all collected metrics."""
        self._entropies.clear()
        self._log_likelihoods.clear()
        self._states.clear()
        self._ood_flags.clear()
        self._timestamps.clear()


class DriftDetector:
    """Detect distribution drift in model inputs/outputs."""

    def __init__(
        self,
        reference_window: int = 5000,
        test_window: int = 500,
        psi_threshold: float = 0.2,
        kl_threshold: float = 0.1,
    ):
        """Initialize drift detector.

        Args:
            reference_window: Size of reference distribution window
            test_window: Size of test distribution window
            psi_threshold: PSI threshold for drift alert
            kl_threshold: KL divergence threshold for drift alert
        """
        self.reference_window = reference_window
        self.test_window = test_window
        self.psi_threshold = psi_threshold
        self.kl_threshold = kl_threshold

        self._reference_states: list[int] = []
        self._recent_states: list[int] = []
        self._reference_features: list[np.ndarray] = []
        self._recent_features: list[np.ndarray] = []

    def update(
        self,
        state: int,
        features: Optional[np.ndarray] = None,
    ) -> Optional[DriftAlert]:
        """Update with new observation and check for drift.

        Args:
            state: Current state ID
            features: Optional feature vector

        Returns:
            DriftAlert if drift detected, None otherwise
        """
        self._recent_states.append(state)
        if features is not None:
            self._recent_features.append(features)

        if len(self._recent_states) > self.test_window:
            self._reference_states.append(self._recent_states.pop(0))
            if self._recent_features:
                self._reference_features.append(self._recent_features.pop(0))

        if len(self._reference_states) > self.reference_window:
            self._reference_states.pop(0)
            if self._reference_features:
                self._reference_features.pop(0)

        if (
            len(self._reference_states) >= self.reference_window
            and len(self._recent_states) >= self.test_window
        ):
            return self._check_drift()

        return None

    def _check_drift(self) -> Optional[DriftAlert]:
        """Check for distribution drift."""
        psi = self._compute_psi(
            self._reference_states,
            self._recent_states,
        )

        if psi > self.psi_threshold:
            return DriftAlert(
                timestamp=datetime.now(),
                alert_type="state_distribution_drift",
                severity="warning" if psi < 0.3 else "critical",
                message=f"State distribution drift detected (PSI={psi:.3f})",
                metric_value=psi,
                threshold=self.psi_threshold,
            )

        if self._reference_features and self._recent_features:
            ref_mean = np.mean(self._reference_features, axis=0)
            recent_mean = np.mean(self._recent_features, axis=0)
            feature_drift = np.mean(np.abs(ref_mean - recent_mean))

            if feature_drift > 1.0:
                return DriftAlert(
                    timestamp=datetime.now(),
                    alert_type="feature_distribution_drift",
                    severity="warning",
                    message=f"Feature distribution drift detected",
                    metric_value=feature_drift,
                    threshold=1.0,
                )

        return None

    def _compute_psi(
        self,
        reference: list[int],
        test: list[int],
    ) -> float:
        """Compute Population Stability Index."""
        all_states = set(reference) | set(test)
        n_states = max(all_states) + 1 if all_states else 1

        ref_counts = np.bincount(reference, minlength=n_states) + 1
        test_counts = np.bincount(test, minlength=n_states) + 1

        ref_pct = ref_counts / ref_counts.sum()
        test_pct = test_counts / test_counts.sum()

        psi = np.sum((test_pct - ref_pct) * np.log(test_pct / ref_pct))

        return float(psi)

    def reset(self) -> None:
        """Reset detector state."""
        self._reference_states.clear()
        self._recent_states.clear()
        self._reference_features.clear()
        self._recent_features.clear()


class ShadowInference:
    """Run shadow inference with candidate model."""

    def __init__(
        self,
        production_engine: InferenceEngine,
        candidate_engine: InferenceEngine,
        comparison_window: int = 1000,
    ):
        """Initialize shadow inference.

        Args:
            production_engine: Current production model
            candidate_engine: Candidate model to evaluate
            comparison_window: Window for comparison metrics
        """
        self.production_engine = production_engine
        self.candidate_engine = candidate_engine
        self.comparison_window = comparison_window

        self._prod_outputs: list[HMMOutput] = []
        self._cand_outputs: list[HMMOutput] = []

    def process(
        self,
        features: dict[str, float],
        symbol: str,
        timestamp: datetime,
    ) -> tuple[HMMOutput, HMMOutput]:
        """Process with both engines.

        Args:
            features: Feature dictionary
            symbol: Ticker symbol
            timestamp: Bar timestamp

        Returns:
            Tuple of (production_output, candidate_output)
        """
        prod_output = self.production_engine.process(features, symbol, timestamp)
        cand_output = self.candidate_engine.process(features, symbol, timestamp)

        self._prod_outputs.append(prod_output)
        self._cand_outputs.append(cand_output)

        if len(self._prod_outputs) > self.comparison_window:
            self._prod_outputs.pop(0)
            self._cand_outputs.pop(0)

        return prod_output, cand_output

    def get_comparison(self) -> dict[str, Any]:
        """Get comparison metrics between models."""
        if not self._prod_outputs:
            return {}

        prod_lls = [o.log_likelihood for o in self._prod_outputs]
        cand_lls = [o.log_likelihood for o in self._cand_outputs]

        prod_entropies = [o.entropy for o in self._prod_outputs]
        cand_entropies = [o.entropy for o in self._cand_outputs]

        prod_ood = sum(o.is_ood for o in self._prod_outputs) / len(self._prod_outputs)
        cand_ood = sum(o.is_ood for o in self._cand_outputs) / len(self._cand_outputs)

        agreement = sum(
            p.state_id == c.state_id
            for p, c in zip(self._prod_outputs, self._cand_outputs)
        ) / len(self._prod_outputs)

        return {
            "production": {
                "mean_log_likelihood": float(np.mean(prod_lls)),
                "mean_entropy": float(np.mean(prod_entropies)),
                "ood_rate": prod_ood,
            },
            "candidate": {
                "mean_log_likelihood": float(np.mean(cand_lls)),
                "mean_entropy": float(np.mean(cand_entropies)),
                "ood_rate": cand_ood,
            },
            "state_agreement": agreement,
            "ll_improvement": float(np.mean(cand_lls) - np.mean(prod_lls)),
        }

    def should_promote(
        self,
        min_improvement: float = 0.05,
        min_agreement: float = 0.7,
    ) -> bool:
        """Check if candidate should be promoted.

        Args:
            min_improvement: Minimum LL improvement required
            min_agreement: Minimum state agreement required

        Returns:
            True if candidate should be promoted
        """
        comparison = self.get_comparison()
        if not comparison:
            return False

        ll_improvement = comparison["ll_improvement"]
        agreement = comparison["state_agreement"]
        cand_ood = comparison["candidate"]["ood_rate"]
        prod_ood = comparison["production"]["ood_rate"]

        return (
            ll_improvement > min_improvement
            and agreement >= min_agreement
            and cand_ood <= prod_ood
        )


class ModelRolloutManager:
    """Manage model rollout and switching."""

    def __init__(
        self,
        models_root: Path = Path("models"),
        min_shadow_samples: int = 1000,
    ):
        """Initialize rollout manager.

        Args:
            models_root: Root directory for models
            min_shadow_samples: Minimum samples before promoting
        """
        self.models_root = models_root
        self.min_shadow_samples = min_shadow_samples

        self._current_model: Optional[str] = None
        self._shadow: Optional[ShadowInference] = None

    def get_current_model(self, symbol: str, timeframe: str) -> Optional[str]:
        """Get current production model ID.

        Args:
            symbol: Ticker symbol
            timeframe: Model timeframe

        Returns:
            Current model ID or None
        """
        models = list_models(symbol, timeframe, self.models_root)
        return models[-1] if models else None

    def start_shadow(
        self,
        symbol: str,
        timeframe: str,
        candidate_model_id: str,
    ) -> bool:
        """Start shadow inference with candidate model.

        Args:
            symbol: Ticker symbol
            timeframe: Model timeframe
            candidate_model_id: Candidate model ID

        Returns:
            True if shadow started successfully
        """
        current_id = self.get_current_model(symbol, timeframe)
        if not current_id:
            return False

        try:
            prod_paths = get_model_path(symbol, timeframe, current_id, self.models_root)
            cand_paths = get_model_path(symbol, timeframe, candidate_model_id, self.models_root)

            prod_engine = create_inference_engine(prod_paths)
            cand_engine = create_inference_engine(cand_paths)

            self._shadow = ShadowInference(prod_engine, cand_engine)
            self._current_model = current_id

            logger.info(f"Started shadow inference: {current_id} -> {candidate_model_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start shadow inference: {e}")
            return False

    def stop_shadow(self) -> dict[str, Any]:
        """Stop shadow inference and return comparison.

        Returns:
            Final comparison metrics
        """
        if not self._shadow:
            return {}

        comparison = self._shadow.get_comparison()
        self._shadow = None
        return comparison

    def promote_candidate(self, timeframe: str) -> bool:
        """Promote candidate to production if criteria met.

        Args:
            timeframe: Model timeframe

        Returns:
            True if promoted successfully
        """
        if not self._shadow:
            return False

        if not self._shadow.should_promote():
            logger.info("Candidate does not meet promotion criteria")
            return False

        comparison = self._shadow.get_comparison()
        logger.info(f"Promoting candidate model. Comparison: {comparison}")

        self._shadow = None
        return True


@dataclass
class RetrainingTrigger:
    """Criteria for triggering model retraining."""

    name: str
    check_fn: Callable[[], bool]
    last_triggered: Optional[datetime] = None
    cooldown_hours: int = 24


class RetrainingScheduler:
    """Schedule and trigger model retraining."""

    def __init__(
        self,
        cadence_days: int = 7,
        ll_decay_threshold: float = 0.1,
        ood_spike_threshold: float = 0.15,
        entropy_spike_threshold: float = 2.0,
    ):
        """Initialize retraining scheduler.

        Args:
            cadence_days: Regular retraining cadence
            ll_decay_threshold: Log-likelihood decay threshold
            ood_spike_threshold: OOD rate spike threshold
            entropy_spike_threshold: Entropy spike z-score threshold
        """
        self.cadence_days = cadence_days
        self.ll_decay_threshold = ll_decay_threshold
        self.ood_spike_threshold = ood_spike_threshold
        self.entropy_spike_threshold = entropy_spike_threshold

        self._last_retrain: Optional[datetime] = None
        self._baseline_ll: Optional[float] = None
        self._metrics_collector: Optional[MetricsCollector] = None

    def set_baseline(self, log_likelihood: float) -> None:
        """Set baseline log-likelihood for comparison.

        Args:
            log_likelihood: Baseline log-likelihood value
        """
        self._baseline_ll = log_likelihood

    def set_metrics_collector(self, collector: MetricsCollector) -> None:
        """Set metrics collector for monitoring.

        Args:
            collector: MetricsCollector instance
        """
        self._metrics_collector = collector

    def check_triggers(self) -> list[str]:
        """Check all retraining triggers.

        Returns:
            List of triggered reasons
        """
        triggered = []

        if self._should_retrain_cadence():
            triggered.append("scheduled_cadence")

        if self._should_retrain_ll_decay():
            triggered.append("log_likelihood_decay")

        if self._should_retrain_ood_spike():
            triggered.append("ood_rate_spike")

        if self._should_retrain_entropy_spike():
            triggered.append("entropy_spike")

        return triggered

    def _should_retrain_cadence(self) -> bool:
        """Check cadence-based trigger."""
        if self._last_retrain is None:
            return False

        days_since = (datetime.now() - self._last_retrain).days
        return days_since >= self.cadence_days

    def _should_retrain_ll_decay(self) -> bool:
        """Check log-likelihood decay trigger."""
        if self._baseline_ll is None or self._metrics_collector is None:
            return False

        summary = self._metrics_collector.get_summary()
        if not summary:
            return False

        current_ll = summary.get("mean_log_likelihood", 0)
        decay = (self._baseline_ll - current_ll) / abs(self._baseline_ll)

        return decay > self.ll_decay_threshold

    def _should_retrain_ood_spike(self) -> bool:
        """Check OOD rate spike trigger."""
        if self._metrics_collector is None:
            return False

        summary = self._metrics_collector.get_summary()
        if not summary:
            return False

        ood_rate = summary.get("ood_rate", 0)
        return ood_rate > self.ood_spike_threshold

    def _should_retrain_entropy_spike(self) -> bool:
        """Check entropy spike trigger."""
        if self._metrics_collector is None:
            return False

        summary = self._metrics_collector.get_summary()
        if not summary:
            return False

        mean_entropy = summary.get("mean_entropy", 0)
        std_entropy = summary.get("std_entropy", 1)

        return mean_entropy > self.entropy_spike_threshold * std_entropy

    def mark_retrained(self) -> None:
        """Mark that retraining was performed."""
        self._last_retrain = datetime.now()


class MonitoringDashboard:
    """Aggregate monitoring data for dashboard display."""

    def __init__(self):
        """Initialize dashboard."""
        self._collectors: dict[str, MetricsCollector] = {}
        self._alerts: list[DriftAlert] = []

    def add_timeframe(self, timeframe: str) -> MetricsCollector:
        """Add a timeframe to monitor.

        Args:
            timeframe: Timeframe string

        Returns:
            MetricsCollector for the timeframe
        """
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        collector = MetricsCollector()
        self._collectors[timeframe] = collector
        return collector

    def add_alert(self, alert: DriftAlert) -> None:
        """Add a drift alert.

        Args:
            alert: DriftAlert to add
        """
        self._alerts.append(alert)

        if len(self._alerts) > 100:
            self._alerts.pop(0)

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for dashboard display.

        Returns:
            Dictionary with dashboard data
        """
        data = {
            "timeframes": {},
            "recent_alerts": [
                {
                    "timestamp": a.timestamp.isoformat(),
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                }
                for a in self._alerts[-10:]
            ],
        }

        for tf, collector in self._collectors.items():
            summary = collector.get_summary()
            data["timeframes"][tf] = summary

        return data
