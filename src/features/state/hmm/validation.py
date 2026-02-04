"""Validation and diagnostics for state vector models.

Implements:
- Dwell time analysis
- Transition matrix diagnostics
- Posterior confidence analysis
- OOD rate monitoring
- State-conditioned returns
- Walk-forward backtest comparison
- Validation report generation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.features.state.hmm.contracts import HMMOutput
from src.features.state.hmm.hmm_model import GaussianHMMWrapper

logger = logging.getLogger(__name__)


@dataclass
class DwellTimeStats:
    """Statistics about regime dwell times."""

    state_id: int
    mean_dwell: float
    median_dwell: float
    std_dwell: float
    min_dwell: int
    max_dwell: int
    count: int
    dwell_times: list[int] = field(default_factory=list)


@dataclass
class TransitionStats:
    """Statistics about state transitions."""

    transition_matrix: np.ndarray
    diagonal_dominance: float
    most_common_transitions: list[tuple[int, int, float]]
    ergodic_distribution: np.ndarray


@dataclass
class PosteriorStats:
    """Statistics about posterior confidence."""

    mean_max_prob: float
    std_max_prob: float
    mean_entropy: float
    std_entropy: float
    low_confidence_rate: float
    prob_distribution: np.ndarray


@dataclass
class StateConditionedReturns:
    """Returns statistics conditioned on state."""

    state_id: int
    mean_return: float
    std_return: float
    sharpe_ratio: float
    hit_rate: float
    max_drawdown: float
    n_observations: int


@dataclass
class ValidationReport:
    """Complete validation report for a model."""

    model_id: str
    timeframe: str
    created_at: datetime
    dwell_stats: list[DwellTimeStats]
    transition_stats: TransitionStats
    posterior_stats: PosteriorStats
    state_returns: list[StateConditionedReturns]
    ood_rate: float
    n_samples: int
    metrics: dict[str, float] = field(default_factory=dict)


class DwellTimeAnalyzer:
    """Analyze regime dwell times."""

    def analyze(
        self,
        states: np.ndarray,
        n_states: int,
    ) -> list[DwellTimeStats]:
        """Compute dwell time statistics for each state.

        Args:
            states: Array of state IDs
            n_states: Total number of states

        Returns:
            List of DwellTimeStats per state
        """
        dwell_times_by_state: dict[int, list[int]] = {i: [] for i in range(n_states)}

        current_state = states[0]
        current_dwell = 1

        for i in range(1, len(states)):
            if states[i] == current_state:
                current_dwell += 1
            else:
                if current_state >= 0:
                    dwell_times_by_state[current_state].append(current_dwell)
                current_state = states[i]
                current_dwell = 1

        if current_state >= 0:
            dwell_times_by_state[current_state].append(current_dwell)

        stats = []
        for state_id in range(n_states):
            dwells = dwell_times_by_state[state_id]
            if dwells:
                stats.append(DwellTimeStats(
                    state_id=state_id,
                    mean_dwell=float(np.mean(dwells)),
                    median_dwell=float(np.median(dwells)),
                    std_dwell=float(np.std(dwells)),
                    min_dwell=int(np.min(dwells)),
                    max_dwell=int(np.max(dwells)),
                    count=len(dwells),
                    dwell_times=dwells,
                ))
            else:
                stats.append(DwellTimeStats(
                    state_id=state_id,
                    mean_dwell=0.0,
                    median_dwell=0.0,
                    std_dwell=0.0,
                    min_dwell=0,
                    max_dwell=0,
                    count=0,
                    dwell_times=[],
                ))

        return stats


class TransitionAnalyzer:
    """Analyze transition matrix properties."""

    def analyze(
        self,
        hmm: GaussianHMMWrapper,
    ) -> TransitionStats:
        """Compute transition matrix statistics.

        Args:
            hmm: Fitted HMM wrapper

        Returns:
            TransitionStats
        """
        A = hmm.transition_matrix

        diagonal = np.diag(A)
        diagonal_dominance = float(np.mean(diagonal))

        transitions = []
        for i in range(A.shape[0]):
            for j in range(A.shape[1]):
                if i != j:
                    transitions.append((i, j, A[i, j]))
        transitions.sort(key=lambda x: x[2], reverse=True)
        most_common = transitions[:5]

        ergodic = self._compute_ergodic_distribution(A)

        return TransitionStats(
            transition_matrix=A,
            diagonal_dominance=diagonal_dominance,
            most_common_transitions=most_common,
            ergodic_distribution=ergodic,
        )

    def _compute_ergodic_distribution(self, A: np.ndarray) -> np.ndarray:
        """Compute stationary (ergodic) distribution."""
        eigenvalues, eigenvectors = np.linalg.eig(A.T)
        idx = np.argmin(np.abs(eigenvalues - 1.0))
        stationary = np.real(eigenvectors[:, idx])
        stationary = stationary / stationary.sum()
        return stationary


class PosteriorAnalyzer:
    """Analyze posterior confidence distributions."""

    def __init__(self, low_confidence_threshold: float = 0.5):
        """Initialize analyzer.

        Args:
            low_confidence_threshold: Threshold for low confidence
        """
        self.low_confidence_threshold = low_confidence_threshold

    def analyze(
        self,
        posteriors: np.ndarray,
    ) -> PosteriorStats:
        """Compute posterior statistics.

        Args:
            posteriors: Array of posterior distributions (n_samples, n_states)

        Returns:
            PosteriorStats
        """
        max_probs = np.max(posteriors, axis=1)

        entropies = -np.sum(posteriors * np.log(posteriors + 1e-10), axis=1)

        low_conf_count = np.sum(max_probs < self.low_confidence_threshold)
        low_conf_rate = low_conf_count / len(max_probs)

        prob_hist, _ = np.histogram(max_probs, bins=20, range=(0, 1))
        prob_distribution = prob_hist / prob_hist.sum()

        return PosteriorStats(
            mean_max_prob=float(np.mean(max_probs)),
            std_max_prob=float(np.std(max_probs)),
            mean_entropy=float(np.mean(entropies)),
            std_entropy=float(np.std(entropies)),
            low_confidence_rate=float(low_conf_rate),
            prob_distribution=prob_distribution,
        )


class StateConditionedReturnAnalyzer:
    """Analyze returns conditioned on regime state."""

    def analyze(
        self,
        states: np.ndarray,
        returns: np.ndarray,
        n_states: int,
        horizon: int = 1,
    ) -> list[StateConditionedReturns]:
        """Compute return statistics per state.

        Args:
            states: Array of state IDs
            returns: Array of forward returns
            n_states: Number of states
            horizon: Return horizon (for Sharpe calculation)

        Returns:
            List of StateConditionedReturns
        """
        results = []

        for state_id in range(n_states):
            mask = states == state_id
            state_returns = returns[mask]

            if len(state_returns) < 2:
                results.append(StateConditionedReturns(
                    state_id=state_id,
                    mean_return=0.0,
                    std_return=0.0,
                    sharpe_ratio=0.0,
                    hit_rate=0.0,
                    max_drawdown=0.0,
                    n_observations=len(state_returns),
                ))
                continue

            mean_ret = float(np.mean(state_returns))
            std_ret = float(np.std(state_returns))

            if std_ret > 0:
                sharpe = mean_ret / std_ret * np.sqrt(252 / horizon)
            else:
                sharpe = 0.0

            hit_rate = float(np.mean(state_returns > 0))

            cumulative = np.cumsum(state_returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = running_max - cumulative
            max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

            results.append(StateConditionedReturns(
                state_id=state_id,
                mean_return=mean_ret,
                std_return=std_ret,
                sharpe_ratio=sharpe,
                hit_rate=hit_rate,
                max_drawdown=max_dd,
                n_observations=len(state_returns),
            ))

        return results


class OODMonitor:
    """Monitor out-of-distribution rate over time."""

    def __init__(self, window_size: int = 100):
        """Initialize OOD monitor.

        Args:
            window_size: Rolling window for OOD rate calculation
        """
        self.window_size = window_size
        self._ood_flags: list[bool] = []
        self._timestamps: list[datetime] = []

    def update(self, is_ood: bool, timestamp: datetime) -> float:
        """Update with new observation and return current OOD rate.

        Args:
            is_ood: Whether observation is OOD
            timestamp: Observation timestamp

        Returns:
            Current rolling OOD rate
        """
        self._ood_flags.append(is_ood)
        self._timestamps.append(timestamp)

        if len(self._ood_flags) > self.window_size:
            self._ood_flags.pop(0)
            self._timestamps.pop(0)

        return self.current_rate

    @property
    def current_rate(self) -> float:
        """Return current OOD rate."""
        if not self._ood_flags:
            return 0.0
        return sum(self._ood_flags) / len(self._ood_flags)

    @property
    def total_rate(self) -> float:
        """Return total OOD rate across all observations."""
        if not self._ood_flags:
            return 0.0
        return sum(self._ood_flags) / len(self._ood_flags)

    def get_ood_spikes(self, threshold: float = 0.2) -> list[datetime]:
        """Get timestamps where OOD rate exceeded threshold."""
        spikes = []
        for i, (flag, ts) in enumerate(zip(self._ood_flags, self._timestamps)):
            if i >= self.window_size:
                window = self._ood_flags[i - self.window_size:i]
                rate = sum(window) / len(window)
                if rate > threshold:
                    spikes.append(ts)
        return spikes


class ModelValidator:
    """Complete model validation pipeline."""

    def __init__(
        self,
        hmm: GaussianHMMWrapper,
        model_id: str,
        timeframe: str,
    ):
        """Initialize validator.

        Args:
            hmm: Fitted HMM model
            model_id: Model identifier
            timeframe: Model timeframe
        """
        self.hmm = hmm
        self.model_id = model_id
        self.timeframe = timeframe

        self.dwell_analyzer = DwellTimeAnalyzer()
        self.transition_analyzer = TransitionAnalyzer()
        self.posterior_analyzer = PosteriorAnalyzer()
        self.return_analyzer = StateConditionedReturnAnalyzer()
        self.ood_monitor = OODMonitor()

    def validate(
        self,
        Z: np.ndarray,
        returns: Optional[np.ndarray] = None,
        ood_flags: Optional[np.ndarray] = None,
    ) -> ValidationReport:
        """Run complete validation on latent vectors.

        Args:
            Z: Latent vectors (n_samples, latent_dim)
            returns: Optional forward returns for state-conditioned analysis
            ood_flags: Optional pre-computed OOD flags

        Returns:
            ValidationReport
        """
        mask = ~np.any(np.isnan(Z), axis=1)
        Z_clean = Z[mask]

        states = self.hmm.predict(Z_clean)

        posteriors = self.hmm.predict_proba(Z_clean)

        dwell_stats = self.dwell_analyzer.analyze(states, self.hmm.n_states)

        transition_stats = self.transition_analyzer.analyze(self.hmm)

        posterior_stats = self.posterior_analyzer.analyze(posteriors)

        if returns is not None:
            returns_clean = returns[mask]
            state_returns = self.return_analyzer.analyze(
                states, returns_clean, self.hmm.n_states
            )
        else:
            state_returns = []

        if ood_flags is not None:
            ood_rate = float(np.mean(ood_flags[mask]))
        else:
            log_liks = self.hmm.emission_log_likelihood(Z_clean)
            ood_rate = float(np.mean(log_liks < -50))

        metrics = {
            "mean_dwell_time": float(np.mean([s.mean_dwell for s in dwell_stats if s.count > 0])),
            "diagonal_dominance": transition_stats.diagonal_dominance,
            "mean_confidence": posterior_stats.mean_max_prob,
            "mean_entropy": posterior_stats.mean_entropy,
            "ood_rate": ood_rate,
        }

        logger.info(
            "Validation complete for model %s: n_samples=%d, "
            "mean_confidence=%.3f, ood_rate=%.3f",
            self.model_id, len(Z_clean),
            posterior_stats.mean_max_prob, ood_rate,
        )

        return ValidationReport(
            model_id=self.model_id,
            timeframe=self.timeframe,
            created_at=datetime.now(),
            dwell_stats=dwell_stats,
            transition_stats=transition_stats,
            posterior_stats=posterior_stats,
            state_returns=state_returns,
            ood_rate=ood_rate,
            n_samples=len(Z_clean),
            metrics=metrics,
        )


class WalkForwardBacktest:
    """Walk-forward backtest comparison."""

    def __init__(
        self,
        baseline_sharpe: float = 0.0,
    ):
        """Initialize backtest.

        Args:
            baseline_sharpe: Baseline strategy Sharpe ratio
        """
        self.baseline_sharpe = baseline_sharpe

    def compare_strategies(
        self,
        states: np.ndarray,
        returns: np.ndarray,
        good_states: list[int],
        n_states: int,
    ) -> dict[str, Any]:
        """Compare baseline vs state-gated strategies.

        Args:
            states: Array of state IDs
            returns: Array of returns
            good_states: States to trade in
            n_states: Total number of states

        Returns:
            Dictionary with comparison metrics
        """
        baseline_returns = returns
        baseline_metrics = self._compute_metrics(baseline_returns, "baseline")

        mask = np.isin(states, good_states)
        gated_returns = np.where(mask, returns, 0)
        gated_metrics = self._compute_metrics(gated_returns, "state_gated")

        state_sized_returns = np.zeros_like(returns)
        for state_id in range(n_states):
            state_mask = states == state_id
            if state_id in good_states:
                state_sized_returns[state_mask] = returns[state_mask]
            else:
                state_sized_returns[state_mask] = returns[state_mask] * 0.5
        sized_metrics = self._compute_metrics(state_sized_returns, "state_sized")

        return {
            "baseline": baseline_metrics,
            "state_gated": gated_metrics,
            "state_sized": sized_metrics,
            "improvement_vs_baseline": {
                "gated_sharpe_diff": gated_metrics["sharpe"] - baseline_metrics["sharpe"],
                "sized_sharpe_diff": sized_metrics["sharpe"] - baseline_metrics["sharpe"],
            },
        }

    def _compute_metrics(
        self,
        returns: np.ndarray,
        name: str,
    ) -> dict[str, float]:
        """Compute performance metrics."""
        if len(returns) == 0:
            return {
                "name": name,
                "total_return": 0.0,
                "mean_return": 0.0,
                "std_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "turnover": 0.0,
            }

        total_return = float(np.sum(returns))
        mean_return = float(np.mean(returns))
        std_return = float(np.std(returns))

        if std_return > 0:
            sharpe = mean_return / std_return * np.sqrt(252)
        else:
            sharpe = 0.0

        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        position_changes = np.diff(np.abs(returns) > 0).astype(int)
        turnover = float(np.sum(np.abs(position_changes))) / len(returns)

        return {
            "name": name,
            "total_return": total_return,
            "mean_return": mean_return,
            "std_return": std_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "turnover": turnover,
        }


def generate_validation_report(
    hmm: GaussianHMMWrapper,
    Z: np.ndarray,
    model_id: str,
    timeframe: str,
    returns: Optional[np.ndarray] = None,
) -> ValidationReport:
    """Convenience function to generate validation report.

    Args:
        hmm: Fitted HMM
        Z: Latent vectors
        model_id: Model ID
        timeframe: Timeframe
        returns: Optional returns for state-conditioned analysis

    Returns:
        ValidationReport
    """
    validator = ModelValidator(hmm, model_id, timeframe)
    return validator.validate(Z, returns)
