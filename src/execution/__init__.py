"""Execution module for live and paper trading.

This module provides components for executing trades via the Alpaca API:
- AlpacaClient: Connection and authentication
- OrderManager: Order submission (market/limit orders)
- OrderTracker: Order status tracking and fill handling
- RiskManager: Pre-trade risk controls and limits
- TradingRunner: Main trading loop orchestration
"""

from src.execution.client import AlpacaClient
from src.execution.orders import Order, OrderSide, OrderType, OrderStatus, OrderTimeInForce
from src.execution.order_manager import OrderManager
from src.execution.order_tracker import OrderTracker, OrderUpdate
from src.execution.risk_manager import RiskManager, RiskConfig, RiskViolation
from src.execution.runner import TradingRunner, TradingRunnerConfig

__all__ = [
    "AlpacaClient",
    "Order",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "OrderTimeInForce",
    "OrderManager",
    "OrderTracker",
    "OrderUpdate",
    "RiskManager",
    "RiskConfig",
    "RiskViolation",
    "TradingRunner",
    "TradingRunnerConfig",
]
