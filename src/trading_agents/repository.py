"""Repository for trading agent data access.

Provides methods for:
- Strategy CRUD (predefined + custom)
- Agent CRUD and lifecycle management
- Order tracking
- Activity logging
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.trading_agents.models import (
    AgentActivityLog,
    AgentOrder,
    AgentStrategy,
    TradingAgent,
)

logger = logging.getLogger(__name__)


class TradingAgentRepository:
    """Repository for trading agent data operations."""

    def __init__(self, session: Session):
        self.session = session

    # -------------------------------------------------------------------------
    # Strategy Operations
    # -------------------------------------------------------------------------

    def list_strategies(self, account_id: int) -> list[AgentStrategy]:
        """List predefined strategies plus user's custom strategies."""
        return (
            self.session.query(AgentStrategy)
            .filter(
                AgentStrategy.is_active == True,  # noqa: E712
                or_(
                    AgentStrategy.account_id.is_(None),
                    AgentStrategy.account_id == account_id,
                ),
            )
            .order_by(AgentStrategy.source_strategy_id.asc().nullslast(), AgentStrategy.name.asc())
            .all()
        )

    def get_strategy(self, strategy_id: int) -> Optional[AgentStrategy]:
        """Get a strategy by ID."""
        return self.session.query(AgentStrategy).filter(
            AgentStrategy.id == strategy_id
        ).first()

    def create_strategy(
        self,
        account_id: int,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        category: str = "custom",
        direction: str = "long_short",
        entry_long: Optional[dict] = None,
        entry_short: Optional[dict] = None,
        exit_long: Optional[dict] = None,
        exit_short: Optional[dict] = None,
        atr_stop_mult: Optional[float] = None,
        atr_target_mult: Optional[float] = None,
        trailing_atr_mult: Optional[float] = None,
        time_stop_bars: Optional[int] = None,
        required_features: Optional[list] = None,
    ) -> AgentStrategy:
        """Create a custom strategy for an account."""
        strategy = AgentStrategy(
            account_id=account_id,
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            direction=direction,
            entry_long=entry_long,
            entry_short=entry_short,
            exit_long=exit_long,
            exit_short=exit_short,
            atr_stop_mult=atr_stop_mult,
            atr_target_mult=atr_target_mult,
            trailing_atr_mult=trailing_atr_mult,
            time_stop_bars=time_stop_bars,
            required_features=required_features,
            is_predefined=False,
        )
        self.session.add(strategy)
        self.session.flush()
        logger.info(
            "Created custom strategy id=%s name='%s' account_id=%s",
            strategy.id, name, account_id,
        )
        return strategy

    def update_strategy(self, strategy_id: int, **kwargs) -> Optional[AgentStrategy]:
        """Update strategy fields."""
        strategy = self.get_strategy(strategy_id)
        if strategy is None:
            logger.warning("Strategy id=%s not found for update", strategy_id)
            return None

        for key, value in kwargs.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)

        self.session.flush()
        logger.info("Updated strategy id=%s fields=%s", strategy_id, list(kwargs.keys()))
        return strategy

    def clone_strategy(
        self,
        strategy_id: int,
        account_id: int,
        new_name: str,
    ) -> Optional[AgentStrategy]:
        """Clone a strategy (predefined or custom) into a user's custom strategy."""
        source = self.get_strategy(strategy_id)
        if source is None:
            logger.warning("Source strategy id=%s not found for clone", strategy_id)
            return None

        clone = AgentStrategy(
            account_id=account_id,
            name=new_name,
            display_name=f"{source.display_name} (Custom)",
            description=source.description,
            category=source.category,
            direction=source.direction,
            entry_long=source.entry_long,
            entry_short=source.entry_short,
            exit_long=source.exit_long,
            exit_short=source.exit_short,
            atr_stop_mult=source.atr_stop_mult,
            atr_target_mult=source.atr_target_mult,
            trailing_atr_mult=source.trailing_atr_mult,
            time_stop_bars=source.time_stop_bars,
            required_features=source.required_features,
            is_predefined=False,
            source_strategy_id=source.source_strategy_id,
            cloned_from_id=source.id,
        )
        self.session.add(clone)
        self.session.flush()
        logger.info(
            "Cloned strategy id=%s -> id=%s name='%s' account_id=%s",
            strategy_id, clone.id, new_name, account_id,
        )
        return clone

    def seed_predefined_strategies(self, strategies: list[dict]) -> int:
        """Seed predefined strategies (idempotent by source_strategy_id)."""
        created = 0
        for data in strategies:
            existing = (
                self.session.query(AgentStrategy)
                .filter(
                    AgentStrategy.is_predefined == True,  # noqa: E712
                    AgentStrategy.source_strategy_id == data["source_strategy_id"],
                )
                .first()
            )
            if existing:
                continue

            strategy = AgentStrategy(
                account_id=None,
                is_predefined=True,
                **data,
            )
            self.session.add(strategy)
            created += 1

        if created:
            self.session.flush()
            logger.info("Seeded %d predefined strategies", created)
        else:
            logger.debug("All predefined strategies already seeded")

        return created

    # -------------------------------------------------------------------------
    # Agent Operations
    # -------------------------------------------------------------------------

    def list_agents(self, account_id: int) -> list[TradingAgent]:
        """List all agents for an account."""
        return (
            self.session.query(TradingAgent)
            .filter(TradingAgent.account_id == account_id)
            .order_by(TradingAgent.created_at.desc())
            .all()
        )

    def get_agent(self, agent_id: int) -> Optional[TradingAgent]:
        """Get an agent by ID."""
        return self.session.query(TradingAgent).filter(
            TradingAgent.id == agent_id
        ).first()

    def create_agent(
        self,
        account_id: int,
        name: str,
        symbol: str,
        strategy_id: int,
        timeframe: str = "5Min",
        interval_minutes: int = 5,
        lookback_days: int = 30,
        position_size_dollars: float = 1000.0,
        risk_config: Optional[dict] = None,
        exit_config: Optional[dict] = None,
        paper: bool = True,
    ) -> TradingAgent:
        """Create a new trading agent."""
        agent = TradingAgent(
            account_id=account_id,
            name=name,
            symbol=symbol.upper(),
            strategy_id=strategy_id,
            timeframe=timeframe,
            interval_minutes=interval_minutes,
            lookback_days=lookback_days,
            position_size_dollars=position_size_dollars,
            risk_config=risk_config,
            exit_config=exit_config,
            paper=paper,
        )
        self.session.add(agent)
        self.session.flush()
        logger.info(
            "Created agent id=%s name='%s' symbol=%s strategy_id=%s account_id=%s",
            agent.id, name, symbol, strategy_id, account_id,
        )
        return agent

    def update_agent(self, agent_id: int, **kwargs) -> Optional[TradingAgent]:
        """Update agent fields."""
        agent = self.get_agent(agent_id)
        if agent is None:
            logger.warning("Agent id=%s not found for update", agent_id)
            return None

        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)

        self.session.flush()
        logger.info("Updated agent id=%s fields=%s", agent_id, list(kwargs.keys()))
        return agent

    def set_agent_status(
        self,
        agent_id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[TradingAgent]:
        """Update agent status and optionally set error message."""
        agent = self.get_agent(agent_id)
        if agent is None:
            logger.warning("Agent id=%s not found for status update", agent_id)
            return None

        agent.status = status
        if error_message is not None:
            agent.error_message = error_message
        if status in ("active", "paused", "stopped"):
            agent.error_message = None
            agent.consecutive_errors = 0

        self.session.flush()
        logger.info("Set agent id=%s status=%s", agent_id, status)
        return agent

    def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent (must be stopped first)."""
        agent = self.get_agent(agent_id)
        if agent is None:
            return False

        self.session.delete(agent)
        self.session.flush()
        logger.info("Deleted agent id=%s", agent_id)
        return True

    # -------------------------------------------------------------------------
    # Order Operations
    # -------------------------------------------------------------------------

    def list_orders(self, agent_id: int, limit: int = 100) -> list[AgentOrder]:
        """List orders for an agent, most recent first."""
        return (
            self.session.query(AgentOrder)
            .filter(AgentOrder.agent_id == agent_id)
            .order_by(AgentOrder.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_order(self, **kwargs) -> AgentOrder:
        """Create an order record."""
        order = AgentOrder(**kwargs)
        self.session.add(order)
        self.session.flush()
        logger.info(
            "Created order id=%s agent_id=%s symbol=%s side=%s",
            order.id, order.agent_id, order.symbol, order.side,
        )
        return order

    def update_order(self, order_id: int, **kwargs) -> Optional[AgentOrder]:
        """Update order fields (status, fill info)."""
        order = self.session.query(AgentOrder).filter(
            AgentOrder.id == order_id
        ).first()
        if order is None:
            return None

        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)

        self.session.flush()
        return order

    # -------------------------------------------------------------------------
    # Activity Log Operations
    # -------------------------------------------------------------------------

    def list_activity(self, agent_id: int, limit: int = 100) -> list[AgentActivityLog]:
        """List activity log for an agent, most recent first."""
        return (
            self.session.query(AgentActivityLog)
            .filter(AgentActivityLog.agent_id == agent_id)
            .order_by(AgentActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def log_activity(
        self,
        agent_id: int,
        account_id: int,
        activity_type: str,
        message: str,
        details: Optional[dict] = None,
        severity: str = "info",
    ) -> AgentActivityLog:
        """Create an activity log entry."""
        entry = AgentActivityLog(
            agent_id=agent_id,
            account_id=account_id,
            activity_type=activity_type,
            message=message,
            details=details,
            severity=severity,
        )
        self.session.add(entry)
        self.session.flush()
        logger.debug(
            "Logged activity agent_id=%s type=%s severity=%s",
            agent_id, activity_type, severity,
        )
        return entry
