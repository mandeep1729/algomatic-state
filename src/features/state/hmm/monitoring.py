"""Operations and monitoring data structures for state vector models.

Provides dataclasses for:
- Monitoring metrics
- Drift alerts
- Retraining triggers
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


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


@dataclass
class RetrainingTrigger:
    """Criteria for triggering model retraining."""

    name: str
    check_fn: Callable[[], bool]
    last_triggered: Optional[datetime] = None
    cooldown_hours: int = 24
