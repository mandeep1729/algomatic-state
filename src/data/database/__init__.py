"""Database module for PostgreSQL integration."""

from src.data.database.connection import DatabaseManager, get_db_manager
from src.data.database.dependencies import get_db, get_trading_repo, get_market_repo, session_scope
from src.data.database.models import Base, Ticker, OHLCVBar, DataSyncLog, ComputedFeature
from src.data.database.market_repository import OHLCVRepository
from src.data.database.trading_buddy_models import (
    UserAccount,
    UserRule,
)
from src.data.database.broker_models import TradeFill
from src.data.database.strategy_models import Strategy
from src.data.database.trade_lifecycle_models import (
    DecisionContext,
    CampaignCheck,
    CampaignFill,
)
from src.data.database.probe_models import ProbeStrategy, StrategyProbeResult

__all__ = [
    # Connection
    "DatabaseManager",
    "get_db_manager",
    # Dependencies (unified DB access)
    "get_db",
    "get_trading_repo",
    "get_market_repo",
    "session_scope",
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
    # Strategy model
    "Strategy",
    # Trade lifecycle models
    "TradeFill",
    "DecisionContext",
    "CampaignCheck",
    "CampaignFill",
    # Probe system
    "ProbeStrategy",
    "StrategyProbeResult",
]
