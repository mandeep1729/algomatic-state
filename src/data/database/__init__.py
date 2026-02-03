"""Database module for PostgreSQL integration."""

from src.data.database.connection import DatabaseManager, get_db_manager
from src.data.database.models import Base, Ticker, OHLCVBar, DataSyncLog, ComputedFeature
from src.data.database.market_repository import OHLCVRepository
from src.data.database.trading_buddy_models import (
    UserAccount,
    UserRule,
    TradeIntent,
    TradeEvaluation,
    TradeEvaluationItem,
)

__all__ = [
    # Connection
    "DatabaseManager",
    "get_db_manager",
    # Core models
    "Base",
    "Ticker",
    "OHLCVBar",
    "DataSyncLog",
    "ComputedFeature",
    # Repository
    "OHLCVRepository",
    # Trading Buddy models
    "UserAccount",
    "UserRule",
    "TradeIntent",
    "TradeEvaluation",
    "TradeEvaluationItem",
]
