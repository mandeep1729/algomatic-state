"""Historical pattern matching for state-based trading.

Uses nearest neighbor search to find similar historical market states
and estimate expected outcomes.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

# FAISS is optional - fall back to sklearn if not available
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

from sklearn.neighbors import NearestNeighbors


@dataclass
class PatternMatchConfig:
    """Configuration for pattern matching.

    Attributes:
        k_neighbors: Number of nearest neighbors to find
        distance_metric: Distance metric ('l2' or 'cosine')
        backend: Backend to use ('faiss', 'sklearn', or 'auto')
        min_confidence: Minimum confidence threshold
        distance_threshold: Maximum distance to consider a valid match
        weight_by_distance: Weight outcomes by inverse distance
    """

    k_neighbors: int = 10
    distance_metric: Literal["l2", "cosine"] = "l2"
    backend: Literal["faiss", "sklearn", "auto"] = "auto"
    min_confidence: float = 0.3
    distance_threshold: float = float("inf")
    weight_by_distance: bool = True


@dataclass
class PatternMatch:
    """Result of a pattern matching query.

    Attributes:
        indices: Indices of matched historical patterns
        distances: Distances to matched patterns
        returns: Forward returns following matched patterns
        expected_return: Weighted average expected return
        confidence: Match confidence score (0-1)
        win_rate: Historical win rate of matched patterns
    """

    indices: np.ndarray
    distances: np.ndarray
    returns: np.ndarray
    expected_return: float
    confidence: float
    win_rate: float


class PatternMatcher:
    """Find similar historical market states using nearest neighbor search.

    Supports both FAISS (fast, GPU-capable) and sklearn (always available)
    backends for nearest neighbor search.

    Example:
        >>> matcher = PatternMatcher(config)
        >>> matcher.fit(historical_states, forward_returns)
        >>> match = matcher.query(current_state)
        >>> print(f"Expected return: {match.expected_return:.4f}")
        >>> print(f"Confidence: {match.confidence:.2f}")
    """

    def __init__(self, config: PatternMatchConfig | None = None):
        """Initialize pattern matcher.

        Args:
            config: Pattern matching configuration
        """
        self._config = config or PatternMatchConfig()
        self._index = None
        self._states: np.ndarray | None = None
        self._returns: np.ndarray | None = None
        self._is_fitted = False

        # Determine backend
        if self._config.backend == "auto":
            self._backend = "faiss" if HAS_FAISS else "sklearn"
        else:
            self._backend = self._config.backend
            if self._backend == "faiss" and not HAS_FAISS:
                raise ImportError(
                    "FAISS not installed. Install with: pip install faiss-cpu"
                )

    @property
    def config(self) -> PatternMatchConfig:
        """Return configuration."""
        return self._config

    @property
    def is_fitted(self) -> bool:
        """Check if matcher has been fitted."""
        return self._is_fitted

    @property
    def n_patterns(self) -> int:
        """Return number of stored patterns."""
        return len(self._states) if self._states is not None else 0

    def fit(self, states: np.ndarray, returns: np.ndarray) -> "PatternMatcher":
        """Fit the pattern matcher on historical data.

        Args:
            states: Historical state vectors (n_samples, latent_dim)
            returns: Forward returns following each state (n_samples,)

        Returns:
            self (for method chaining)
        """
        if len(states) != len(returns):
            raise ValueError(
                f"States ({len(states)}) and returns ({len(returns)}) must have same length"
            )

        states = np.ascontiguousarray(states, dtype=np.float32)
        returns = np.asarray(returns, dtype=np.float32)

        self._states = states
        self._returns = returns

        # Build index
        if self._backend == "faiss":
            self._build_faiss_index(states)
        else:
            self._build_sklearn_index(states)

        self._is_fitted = True
        return self

    def _build_faiss_index(self, states: np.ndarray) -> None:
        """Build FAISS index for fast nearest neighbor search."""
        d = states.shape[1]  # dimension

        if self._config.distance_metric == "l2":
            self._index = faiss.IndexFlatL2(d)
        else:  # cosine
            # Normalize vectors and use inner product (equivalent to cosine)
            faiss.normalize_L2(states)
            self._index = faiss.IndexFlatIP(d)

        self._index.add(states)

    def _build_sklearn_index(self, states: np.ndarray) -> None:
        """Build sklearn NearestNeighbors index."""
        metric = "euclidean" if self._config.distance_metric == "l2" else "cosine"
        # Cap n_neighbors at number of samples
        k = min(self._config.k_neighbors, len(states))
        self._index = NearestNeighbors(
            n_neighbors=k,
            metric=metric,
            algorithm="auto",
        )
        self._index.fit(states)

    def query(self, state: np.ndarray) -> PatternMatch:
        """Query for similar historical patterns.

        Args:
            state: Current state vector (latent_dim,) or (1, latent_dim)

        Returns:
            PatternMatch with similar patterns and expected outcomes
        """
        if not self._is_fitted:
            raise RuntimeError("PatternMatcher must be fitted before query")

        # Ensure correct shape
        if state.ndim == 1:
            state = state.reshape(1, -1)
        state = np.ascontiguousarray(state, dtype=np.float32)

        # Normalize for cosine distance if needed
        if self._backend == "faiss" and self._config.distance_metric == "cosine":
            faiss.normalize_L2(state)

        # Find nearest neighbors
        k = min(self._config.k_neighbors, self.n_patterns)

        if self._backend == "faiss":
            distances, indices = self._index.search(state, k)
            distances = distances[0]
            indices = indices[0]
        else:
            distances, indices = self._index.kneighbors(state)
            distances = distances[0]
            indices = indices[0]

        # Filter by distance threshold
        valid_mask = distances <= self._config.distance_threshold
        distances = distances[valid_mask]
        indices = indices[valid_mask]

        # Get corresponding returns
        matched_returns = self._returns[indices] if len(indices) > 0 else np.array([])

        # Calculate expected return and confidence
        expected_return, confidence = self._calculate_expected_return(
            distances, matched_returns
        )

        # Calculate win rate
        win_rate = 0.0
        if len(matched_returns) > 0:
            win_rate = float(np.mean(matched_returns > 0))

        return PatternMatch(
            indices=indices,
            distances=distances,
            returns=matched_returns,
            expected_return=expected_return,
            confidence=confidence,
            win_rate=win_rate,
        )

    def _calculate_expected_return(
        self, distances: np.ndarray, returns: np.ndarray
    ) -> tuple[float, float]:
        """Calculate expected return and confidence from matched patterns.

        Args:
            distances: Distances to matched patterns
            returns: Returns following matched patterns

        Returns:
            Tuple of (expected_return, confidence)
        """
        if len(returns) == 0:
            return 0.0, 0.0

        if self._config.weight_by_distance:
            # Weight by inverse distance (closer patterns matter more)
            weights = 1.0 / (distances + 1e-6)
            weights = weights / weights.sum()
            expected_return = float(np.sum(weights * returns))
        else:
            expected_return = float(np.mean(returns))

        # Calculate confidence based on:
        # 1. Number of matches
        # 2. Agreement of returns (consistency)
        # 3. Average distance quality

        # Number of matches factor
        n_matches = len(returns)
        match_factor = min(1.0, n_matches / self._config.k_neighbors)

        # Consistency factor (low variance = high confidence)
        if len(returns) > 1:
            return_std = float(np.std(returns))
            return_range = float(np.max(np.abs(returns))) + 1e-6
            consistency = 1.0 - min(1.0, return_std / return_range)
        else:
            consistency = 0.5

        # Distance quality factor
        mean_distance = float(np.mean(distances)) if len(distances) > 0 else float("inf")
        if mean_distance < float("inf"):
            # Normalize by a reasonable distance scale
            distance_quality = 1.0 / (1.0 + mean_distance)
        else:
            distance_quality = 0.0

        # Combine factors
        confidence = 0.4 * match_factor + 0.4 * consistency + 0.2 * distance_quality
        confidence = float(np.clip(confidence, 0.0, 1.0))

        return expected_return, confidence

    def query_batch(self, states: np.ndarray) -> list[PatternMatch]:
        """Query for similar patterns for multiple states.

        Args:
            states: State vectors (n_queries, latent_dim)

        Returns:
            List of PatternMatch objects
        """
        return [self.query(state) for state in states]

    def get_return_distribution(
        self, state: np.ndarray, n_bins: int = 20
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get histogram of returns for similar patterns.

        Args:
            state: Current state vector
            n_bins: Number of histogram bins

        Returns:
            Tuple of (bin_edges, counts)
        """
        match = self.query(state)
        if len(match.returns) == 0:
            return np.array([]), np.array([])

        counts, bin_edges = np.histogram(match.returns, bins=n_bins)
        return bin_edges, counts

    def save(self, path: str) -> None:
        """Save pattern matcher to disk.

        Args:
            path: Path to save to
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save unfitted matcher")

        import joblib

        data = {
            "config": self._config,
            "states": self._states,
            "returns": self._returns,
            "backend": self._backend,
        }

        # FAISS index needs special handling
        if self._backend == "faiss":
            # Save FAISS index separately
            index_path = path + ".faiss"
            faiss.write_index(self._index, index_path)
            data["faiss_index_path"] = index_path
        else:
            data["sklearn_index"] = self._index

        joblib.dump(data, path)

    @classmethod
    def load(cls, path: str) -> "PatternMatcher":
        """Load pattern matcher from disk.

        Args:
            path: Path to load from

        Returns:
            Loaded PatternMatcher
        """
        import joblib

        data = joblib.load(path)

        matcher = cls(data["config"])
        matcher._states = data["states"]
        matcher._returns = data["returns"]
        matcher._backend = data["backend"]

        if matcher._backend == "faiss":
            matcher._index = faiss.read_index(data["faiss_index_path"])
        else:
            matcher._index = data["sklearn_index"]

        matcher._is_fitted = True
        return matcher
