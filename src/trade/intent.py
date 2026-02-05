"""Trade intent domain objects.

Defines the core data contracts for proposing trades.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TradeDirection(str, Enum):
    """Direction of a trade."""

    LONG = "long"
    SHORT = "short"


class TradeIntentStatus(str, Enum):
    """Status of a trade intent in the workflow."""

    DRAFT = "draft"
    PENDING_EVALUATION = "pending_evaluation"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


@dataclass
class TradeIntent:
    """A user's proposed trade for evaluation.

    Captures all parameters needed to evaluate a trade idea
    before execution.

    Attributes:
        user_id: User who created this intent
        symbol: Ticker symbol (e.g., 'AAPL')
        direction: Trade direction (long or short)
        timeframe: Setup timeframe (e.g., '5Min', '1Hour')
        entry_price: Planned entry price
        stop_loss: Stop loss price
        profit_target: Profit target price
        position_size: Number of shares/contracts
        position_value: Total position value in dollars
        rationale: User's reasoning for the trade
        created_at: Timestamp of creation
        status: Current workflow status
        intent_id: Unique identifier (set after persistence)
        account_id: Associated user account ID
        metadata: Additional flexible data
    """

    user_id: int
    symbol: str
    direction: TradeDirection
    timeframe: str
    entry_price: float
    stop_loss: float
    profit_target: float
    position_size: Optional[float] = None
    position_value: Optional[float] = None
    rationale: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TradeIntentStatus = TradeIntentStatus.DRAFT
    intent_id: Optional[int] = None
    account_id: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate trade intent parameters."""
        logger.debug(
            "Creating TradeIntent: symbol=%s, direction=%s, entry=%.2f, stop=%.2f, target=%.2f",
            self.symbol, self.direction, self.entry_price, self.stop_loss, self.profit_target
        )
        self.symbol = self.symbol.upper()

        if isinstance(self.direction, str):
            self.direction = TradeDirection(self.direction.lower())
        if isinstance(self.status, str):
            self.status = TradeIntentStatus(self.status.lower())

        # Validate price relationships
        if self.direction == TradeDirection.LONG:
            if self.stop_loss >= self.entry_price:
                logger.error(
                    "Invalid long trade: stop_loss (%.2f) >= entry_price (%.2f)",
                    self.stop_loss, self.entry_price
                )
                raise ValueError(
                    f"Long trade: stop_loss ({self.stop_loss}) must be below "
                    f"entry_price ({self.entry_price})"
                )
            if self.profit_target <= self.entry_price:
                logger.error(
                    "Invalid long trade: profit_target (%.2f) <= entry_price (%.2f)",
                    self.profit_target, self.entry_price
                )
                raise ValueError(
                    f"Long trade: profit_target ({self.profit_target}) must be above "
                    f"entry_price ({self.entry_price})"
                )
        else:  # SHORT
            if self.stop_loss <= self.entry_price:
                logger.error(
                    "Invalid short trade: stop_loss (%.2f) <= entry_price (%.2f)",
                    self.stop_loss, self.entry_price
                )
                raise ValueError(
                    f"Short trade: stop_loss ({self.stop_loss}) must be above "
                    f"entry_price ({self.entry_price})"
                )
            if self.profit_target >= self.entry_price:
                logger.error(
                    "Invalid short trade: profit_target (%.2f) >= entry_price (%.2f)",
                    self.profit_target, self.entry_price
                )
                raise ValueError(
                    f"Short trade: profit_target ({self.profit_target}) must be below "
                    f"entry_price ({self.entry_price})"
                )

        logger.debug(
            "TradeIntent validated: R:R=%.2f, risk_per_share=%.4f",
            self.risk_reward_ratio, self.risk_per_share
        )

    @property
    def risk_per_share(self) -> float:
        """Calculate risk per share (distance to stop loss)."""
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward_per_share(self) -> float:
        """Calculate reward per share (distance to target)."""
        return abs(self.profit_target - self.entry_price)

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk:reward ratio (higher is better)."""
        risk = self.risk_per_share
        if risk == 0:
            return float('inf')
        return self.reward_per_share / risk

    @property
    def total_risk(self) -> Optional[float]:
        """Calculate total dollar risk if position size is known."""
        if self.position_size is None:
            return None
        return self.risk_per_share * self.position_size

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "intent_id": self.intent_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "timeframe": self.timeframe,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "profit_target": self.profit_target,
            "position_size": self.position_size,
            "position_value": self.position_value,
            "rationale": self.rationale,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "risk_reward_ratio": self.risk_reward_ratio,
            "total_risk": self.total_risk,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TradeIntent":
        """Create from dictionary."""
        logger.debug("Creating TradeIntent from dict: symbol=%s", data.get("symbol"))
        return cls(
            intent_id=data.get("intent_id"),
            user_id=data["user_id"],
            account_id=data.get("account_id"),
            symbol=data["symbol"],
            direction=TradeDirection(data["direction"]),
            timeframe=data["timeframe"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            profit_target=data["profit_target"],
            position_size=data.get("position_size"),
            position_value=data.get("position_value"),
            rationale=data.get("rationale"),
            status=TradeIntentStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
        )
