"""Gaussian HMM for regime tracking.

Implements:
- GaussianHMMWrapper: Wrapper around hmmlearn with proper initialization
- State inference (filtering, Viterbi)
- Covariance regularization
- Model selection (AIC/BIC)
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from sklearn.cluster import KMeans

try:
    from hmmlearn import hmm
    HAS_HMMLEARN = True
except ImportError:
    HAS_HMMLEARN = False


EPS = 1e-9


@dataclass
class HMMMetrics:
    """Metrics from HMM training and evaluation.

    Attributes:
        log_likelihood: Total log-likelihood on training data
        aic: Akaike Information Criterion
        bic: Bayesian Information Criterion
        mean_dwell_time: Mean dwell time per state (in bars)
        transition_diagonal: Diagonal values of transition matrix
        state_occupancy: Fraction of time in each state
    """

    log_likelihood: float
    aic: float
    bic: float
    mean_dwell_time: np.ndarray
    transition_diagonal: np.ndarray
    state_occupancy: np.ndarray


class GaussianHMMWrapper:
    """Wrapper around hmmlearn GaussianHMM with custom initialization.

    Features:
    - K-means initialization for faster convergence
    - Covariance regularization for numerical stability
    - Transition matrix initialization with diagonal bias
    - Filtering (forward algorithm) for online inference
    - Viterbi decoding for offline analysis
    """

    def __init__(
        self,
        n_states: int = 8,
        covariance_type: Literal["full", "diag", "tied", "spherical"] = "diag",
        n_iter: int = 100,
        tol: float = 1e-4,
        diagonal_bias: float = 0.9,
        cov_reg: float = 1e-3,
        random_state: Optional[int] = None,
    ):
        """Initialize HMM wrapper.

        Args:
            n_states: Number of hidden states (K)
            covariance_type: Type of covariance parameters
            n_iter: Maximum number of EM iterations
            tol: Convergence threshold
            diagonal_bias: Initial self-transition probability (encourages persistence)
            cov_reg: Covariance regularization (diagonal loading)
            random_state: Random seed for reproducibility
        """
        if not HAS_HMMLEARN:
            raise ImportError("hmmlearn is required. Install with: pip install hmmlearn")

        self.n_states = n_states
        self.covariance_type = covariance_type
        self.n_iter = n_iter
        self.tol = tol
        self.diagonal_bias = diagonal_bias
        self.cov_reg = cov_reg
        self.random_state = random_state

        self.model_: Optional[hmm.GaussianHMM] = None
        self.metrics_: Optional[HMMMetrics] = None
        self._latent_dim: Optional[int] = None

    @property
    def latent_dim(self) -> int:
        """Return dimensionality of input (latent) space."""
        if self._latent_dim is None:
            raise ValueError("Model not fitted")
        return self._latent_dim

    def _init_transition_matrix(self) -> np.ndarray:
        """Initialize transition matrix with diagonal bias."""
        off_diag = (1.0 - self.diagonal_bias) / (self.n_states - 1)
        A = np.full((self.n_states, self.n_states), off_diag)
        np.fill_diagonal(A, self.diagonal_bias)
        return A

    def _init_from_kmeans(self, Z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Initialize means and covariances from K-means clustering.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Tuple of (means, covariances)
        """
        kmeans = KMeans(
            n_clusters=self.n_states,
            n_init=10,
            random_state=self.random_state,
        )
        labels = kmeans.fit_predict(Z)
        means = kmeans.cluster_centers_

        d = Z.shape[1]

        if self.covariance_type == "full":
            covars = np.zeros((self.n_states, d, d))
            for k in range(self.n_states):
                mask = labels == k
                if mask.sum() > d:
                    covars[k] = np.cov(Z[mask], rowvar=False)
                else:
                    covars[k] = np.eye(d)
                covars[k] += self.cov_reg * np.eye(d)

        elif self.covariance_type == "diag":
            covars = np.zeros((self.n_states, d))
            for k in range(self.n_states):
                mask = labels == k
                if mask.sum() > 1:
                    covars[k] = np.var(Z[mask], axis=0)
                else:
                    covars[k] = np.ones(d)
                covars[k] = np.maximum(covars[k], self.cov_reg)

        elif self.covariance_type == "tied":
            covars = np.cov(Z, rowvar=False)
            covars += self.cov_reg * np.eye(d)

        elif self.covariance_type == "spherical":
            covars = np.zeros(self.n_states)
            for k in range(self.n_states):
                mask = labels == k
                if mask.sum() > 1:
                    covars[k] = np.var(Z[mask])
                else:
                    covars[k] = 1.0
                covars[k] = max(covars[k], self.cov_reg)

        return means, covars

    def fit(self, Z: np.ndarray, lengths: Optional[list[int]] = None) -> "GaussianHMMWrapper":
        """Fit HMM to latent vectors.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)
            lengths: Optional list of sequence lengths for multiple sequences

        Returns:
            Self
        """
        Z = np.asarray(Z)
        if Z.ndim != 2:
            raise ValueError(f"Expected 2D input, got shape {Z.shape}")

        mask = ~np.any(np.isnan(Z), axis=1)
        Z_clean = Z[mask]

        if len(Z_clean) < self.n_states * 2:
            raise ValueError(
                f"Need at least {self.n_states * 2} valid samples, got {len(Z_clean)}"
            )

        self._latent_dim = Z_clean.shape[1]

        means, covars = self._init_from_kmeans(Z_clean)

        self.model_ = hmm.GaussianHMM(
            n_components=self.n_states,
            covariance_type=self.covariance_type,
            n_iter=self.n_iter,
            tol=self.tol,
            random_state=self.random_state,
            init_params="",
        )

        self.model_.startprob_ = np.ones(self.n_states) / self.n_states
        self.model_.transmat_ = self._init_transition_matrix()
        self.model_.means_ = means
        self.model_.covars_ = covars

        if lengths is not None:
            clean_lengths = self._adjust_lengths_for_mask(lengths, mask)
        else:
            clean_lengths = None

        self.model_.fit(Z_clean, lengths=clean_lengths)

        self._regularize_covariances()

        self._compute_metrics(Z_clean, lengths=clean_lengths)

        return self

    def _adjust_lengths_for_mask(
        self,
        lengths: list[int],
        mask: np.ndarray,
    ) -> list[int]:
        """Adjust sequence lengths for removed NaN samples."""
        clean_lengths = []
        idx = 0
        for length in lengths:
            end_idx = idx + length
            clean_length = mask[idx:end_idx].sum()
            if clean_length > 0:
                clean_lengths.append(clean_length)
            idx = end_idx
        return clean_lengths

    def _regularize_covariances(self) -> None:
        """Apply covariance regularization after fitting."""
        if self.covariance_type == "full":
            for k in range(self.n_states):
                eigvals = np.linalg.eigvalsh(self.model_.covars_[k])
                if eigvals.min() < self.cov_reg:
                    self.model_.covars_[k] += self.cov_reg * np.eye(self._latent_dim)

        elif self.covariance_type == "diag":
            # hmmlearn stores diag covars as 3D internally but setter expects 2D
            # Extract diagonals, regularize, and set back
            covars = self.model_.covars_
            if covars.ndim == 3:
                # Extract diagonals from each component's covariance matrix
                diag_covars = np.array([np.diag(c) for c in covars])
            else:
                diag_covars = covars.copy()
            diag_covars = np.maximum(diag_covars, self.cov_reg)
            self.model_.covars_ = diag_covars

        elif self.covariance_type == "spherical":
            covars = np.atleast_1d(self.model_.covars_).copy()
            covars = np.maximum(covars, self.cov_reg)
            self.model_.covars_ = covars

    def _compute_metrics(
        self,
        Z: np.ndarray,
        lengths: Optional[list[int]] = None,
    ) -> None:
        """Compute training metrics."""
        log_likelihood = self.model_.score(Z, lengths=lengths)

        n_samples = len(Z)
        n_params = self._count_parameters()
        aic = 2 * n_params - 2 * log_likelihood
        bic = n_params * np.log(n_samples) - 2 * log_likelihood

        diag = np.diag(self.model_.transmat_)
        mean_dwell = 1.0 / (1.0 - diag + EPS)

        states = self.model_.predict(Z, lengths=lengths)
        occupancy = np.bincount(states, minlength=self.n_states) / len(states)

        self.metrics_ = HMMMetrics(
            log_likelihood=log_likelihood,
            aic=aic,
            bic=bic,
            mean_dwell_time=mean_dwell,
            transition_diagonal=diag,
            state_occupancy=occupancy,
        )

    def _count_parameters(self) -> int:
        """Count number of free parameters in model."""
        n_start = self.n_states - 1
        n_trans = self.n_states * (self.n_states - 1)
        n_means = self.n_states * self._latent_dim

        if self.covariance_type == "full":
            n_cov = self.n_states * self._latent_dim * (self._latent_dim + 1) // 2
        elif self.covariance_type == "diag":
            n_cov = self.n_states * self._latent_dim
        elif self.covariance_type == "tied":
            n_cov = self._latent_dim * (self._latent_dim + 1) // 2
        elif self.covariance_type == "spherical":
            n_cov = self.n_states

        return n_start + n_trans + n_means + n_cov

    def predict(self, Z: np.ndarray) -> np.ndarray:
        """Predict most likely state for each observation (Viterbi).

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            State indices of shape (n_samples,)
        """
        if self.model_ is None:
            raise ValueError("Model not fitted. Call fit() first.")

        Z = np.asarray(Z)
        if Z.ndim == 1:
            Z = Z.reshape(1, -1)

        result = np.full(len(Z), -1, dtype=int)
        mask = ~np.any(np.isnan(Z), axis=1)

        if mask.sum() > 0:
            result[mask] = self.model_.predict(Z[mask])

        return result

    def predict_proba(self, Z: np.ndarray) -> np.ndarray:
        """Compute posterior probabilities over states.

        Uses the forward algorithm (filtering) to compute
        p(s_t = k | z_{1:t}) for each timestep.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Posterior probabilities of shape (n_samples, n_states)
        """
        if self.model_ is None:
            raise ValueError("Model not fitted. Call fit() first.")

        Z = np.asarray(Z)
        if Z.ndim == 1:
            Z = Z.reshape(1, -1)

        result = np.full((len(Z), self.n_states), np.nan)
        mask = ~np.any(np.isnan(Z), axis=1)

        if mask.sum() > 0:
            result[mask] = self.model_.predict_proba(Z[mask])

        return result

    def score_samples(self, Z: np.ndarray) -> np.ndarray:
        """Compute per-sample log-likelihood.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Log-likelihoods of shape (n_samples,)
        """
        if self.model_ is None:
            raise ValueError("Model not fitted. Call fit() first.")

        Z = np.asarray(Z)
        if Z.ndim == 1:
            Z = Z.reshape(1, -1)

        result = np.full(len(Z), np.nan)
        mask = ~np.any(np.isnan(Z), axis=1)

        if mask.sum() > 0:
            log_probs = self.model_.score_samples(Z[mask])[1]
            result[mask] = np.max(log_probs, axis=1)

        return result

    def emission_log_likelihood(self, Z: np.ndarray) -> np.ndarray:
        """Compute emission log-likelihood p(z_t | model).

        This is the log-likelihood under the mixture model,
        useful for OOD detection.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Log-likelihoods of shape (n_samples,)
        """
        if self.model_ is None:
            raise ValueError("Model not fitted. Call fit() first.")

        Z = np.asarray(Z)
        if Z.ndim == 1:
            Z = Z.reshape(1, -1)

        result = np.full(len(Z), np.nan)
        mask = ~np.any(np.isnan(Z), axis=1)

        if mask.sum() == 0:
            return result

        Z_clean = Z[mask]

        log_probs = np.zeros((len(Z_clean), self.n_states))

        for k in range(self.n_states):
            mean = self.model_.means_[k]

            if self.covariance_type == "full":
                cov = self.model_.covars_[k]
            elif self.covariance_type == "diag":
                cov = np.diag(self.model_.covars_[k])
            elif self.covariance_type == "tied":
                cov = self.model_.covars_
            elif self.covariance_type == "spherical":
                cov = self.model_.covars_[k] * np.eye(self._latent_dim)

            diff = Z_clean - mean
            try:
                inv_cov = np.linalg.inv(cov)
                log_det = np.log(np.linalg.det(cov) + EPS)
            except np.linalg.LinAlgError:
                inv_cov = np.eye(self._latent_dim)
                log_det = 0.0

            mahal = np.sum(diff @ inv_cov * diff, axis=1)
            log_probs[:, k] = -0.5 * (
                self._latent_dim * np.log(2 * np.pi) + log_det + mahal
            )

        weights = self.model_.startprob_
        log_mixture = np.log(weights + EPS) + log_probs
        result[mask] = np.logaddexp.reduce(log_mixture, axis=1)

        return result

    @property
    def transition_matrix(self) -> np.ndarray:
        """Return transition matrix."""
        if self.model_ is None:
            raise ValueError("Model not fitted")
        return self.model_.transmat_

    @property
    def means(self) -> np.ndarray:
        """Return state means."""
        if self.model_ is None:
            raise ValueError("Model not fitted")
        return self.model_.means_

    @property
    def covariances(self) -> np.ndarray:
        """Return state covariances."""
        if self.model_ is None:
            raise ValueError("Model not fitted")
        return self.model_.covars_

    def save(self, path: Path | str) -> None:
        """Save model to pickle file.

        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path | str) -> "GaussianHMMWrapper":
        """Load model from pickle file.

        Args:
            path: Input file path

        Returns:
            Loaded model instance
        """
        with open(path, "rb") as f:
            return pickle.load(f)


def select_n_states(
    Z: np.ndarray,
    state_range: range = range(3, 15),
    criterion: Literal["aic", "bic"] = "bic",
    covariance_type: str = "diag",
    n_iter: int = 50,
    random_state: Optional[int] = None,
) -> tuple[int, dict[int, float]]:
    """Select optimal number of states using AIC or BIC.

    Args:
        Z: Latent vectors for model selection
        state_range: Range of state counts to try
        criterion: Selection criterion ('aic' or 'bic')
        covariance_type: HMM covariance type
        n_iter: Max EM iterations per model
        random_state: Random seed

    Returns:
        Tuple of (optimal K, dict mapping K -> criterion value)
    """
    scores = {}

    for n_states in state_range:
        try:
            wrapper = GaussianHMMWrapper(
                n_states=n_states,
                covariance_type=covariance_type,
                n_iter=n_iter,
                random_state=random_state,
            )
            wrapper.fit(Z)

            if criterion == "aic":
                scores[n_states] = wrapper.metrics_.aic
            else:
                scores[n_states] = wrapper.metrics_.bic

        except Exception:
            continue

    if not scores:
        raise ValueError("Failed to fit any models")

    best_k = min(scores, key=scores.get)
    return best_k, scores


def match_states_hungarian(
    old_means: np.ndarray,
    new_means: np.ndarray,
) -> dict[int, int]:
    """Match new HMM states to old states using Hungarian algorithm.

    Useful for maintaining state semantics across retrains.

    Args:
        old_means: State means from old model, shape (K_old, d)
        new_means: State means from new model, shape (K_new, d)

    Returns:
        Dictionary mapping new state index -> old state index
    """
    from scipy.optimize import linear_sum_assignment

    K_old = len(old_means)
    K_new = len(new_means)

    cost_matrix = np.zeros((K_new, K_old))
    for i in range(K_new):
        for j in range(K_old):
            cost_matrix[i, j] = np.linalg.norm(new_means[i] - old_means[j])

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    mapping = {}
    for new_idx, old_idx in zip(row_ind, col_ind):
        mapping[int(new_idx)] = int(old_idx)

    return mapping
