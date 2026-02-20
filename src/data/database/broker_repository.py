"""Repository for broker integration data access.

Covers SnapTrade users, broker connections, trade fills, and decision contexts.
Centralizes all broker-related database queries previously scattered across
src/api/broker.py, src/api/alpaca.py, src/api/campaigns.py, and
src/reviewer/orchestrator.py.
"""

import logging
from datetime import date, datetime
from typing import Literal, Optional

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from src.data.database.broker_models import (
    BrokerConnection,
    SnapTradeUser,
    TradeFill,
)
from src.trading_agents.models import AgentStrategy as Strategy
from src.data.database.trade_lifecycle_models import CampaignCheck, DecisionContext

logger = logging.getLogger(__name__)


class BrokerRepository:
    """Repository for broker, fill, and decision context data operations."""

    def __init__(self, session: Session):
        self.session = session

    # -------------------------------------------------------------------------
    # SnapTrade User Operations
    # -------------------------------------------------------------------------

    def get_snaptrade_user(self, user_id: int) -> Optional[SnapTradeUser]:
        """Get SnapTrade user by user_account_id."""
        return self.session.query(SnapTradeUser).filter(
            SnapTradeUser.user_account_id == user_id,
        ).first()

    def get_or_create_snaptrade_user(
        self,
        user_id: int,
        snaptrade_id: str,
        snaptrade_secret: str,
    ) -> SnapTradeUser:
        """Get existing or create new SnapTrade user."""
        user = self.get_snaptrade_user(user_id)
        if user:
            return user

        user = SnapTradeUser(
            user_account_id=user_id,
            snaptrade_user_id=snaptrade_id,
            snaptrade_user_secret=snaptrade_secret,
        )
        self.session.add(user)
        self.session.flush()
        logger.info("Created SnapTradeUser for user_account_id=%d", user_id)
        return user

    # -------------------------------------------------------------------------
    # Broker Connection Operations
    # -------------------------------------------------------------------------

    def get_connection(
        self,
        snaptrade_user_id: int,
        slug: str,
    ) -> Optional[BrokerConnection]:
        """Get broker connection by snaptrade_user_id and brokerage_slug."""
        return self.session.query(BrokerConnection).filter(
            BrokerConnection.snaptrade_user_id == snaptrade_user_id,
            BrokerConnection.brokerage_slug == slug,
        ).first()

    def get_connection_by_auth_id(
        self,
        auth_id: str,
    ) -> Optional[BrokerConnection]:
        """Get broker connection by authorization_id."""
        return self.session.query(BrokerConnection).filter(
            BrokerConnection.authorization_id == auth_id,
        ).first()

    def get_connections_for_user(
        self,
        snaptrade_user_id: int,
    ) -> list[BrokerConnection]:
        """Get all broker connections for a SnapTrade user."""
        return self.session.query(BrokerConnection).filter(
            BrokerConnection.snaptrade_user_id == snaptrade_user_id,
        ).all()

    def create_connection(self, **kwargs) -> BrokerConnection:
        """Create a new broker connection."""
        conn = BrokerConnection(**kwargs)
        self.session.add(conn)
        self.session.flush()
        logger.info(
            "Created BrokerConnection: brokerage=%s",
            kwargs.get("brokerage_name", "unknown"),
        )
        return conn

    # -------------------------------------------------------------------------
    # Trade Fill Operations
    # -------------------------------------------------------------------------

    def get_fill(
        self,
        fill_id: int,
        account_id: Optional[int] = None,
    ) -> Optional[TradeFill]:
        """Get a trade fill by ID, optionally scoped to account."""
        query = self.session.query(TradeFill).filter(TradeFill.id == fill_id)
        if account_id is not None:
            query = query.filter(TradeFill.account_id == account_id)
        return query.first()

    def get_fills(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        broker: Optional[str] = None,
        limit: Optional[int] = None,
        order_desc: bool = True,
    ) -> list[TradeFill]:
        """Get trade fills for an account with optional filters."""
        query = self.session.query(TradeFill).filter(
            TradeFill.account_id == account_id,
        )
        if symbol:
            query = query.filter(TradeFill.symbol == symbol)
        if broker:
            query = query.filter(TradeFill.broker == broker)

        order_col = TradeFill.executed_at.desc() if order_desc else TradeFill.executed_at.asc()
        query = query.order_by(order_col)

        if limit:
            query = query.limit(limit)
        return query.all()

    def get_fills_paginated(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        broker: Optional[str] = None,
        sort_field: str = "executed_at",
        sort_desc: bool = True,
        uncategorized: bool = False,
        page: int = 1,
        limit: int = 50,
        snaptrade_user_id: Optional[int] = None,
    ) -> tuple[list[TradeFill], int]:
        """Get paginated fills with sorting and optional uncategorized filter.

        When snaptrade_user_id is provided, filters via broker_connection join
        (SnapTrade broker.py pattern). Otherwise filters by account_id directly.

        Returns:
            Tuple of (fills, total_count).
        """
        if snaptrade_user_id is not None:
            query = self.session.query(TradeFill).join(BrokerConnection).filter(
                BrokerConnection.snaptrade_user_id == snaptrade_user_id,
            )
        else:
            query = self.session.query(TradeFill).filter(
                TradeFill.account_id == account_id,
            )

        if symbol:
            query = query.filter(TradeFill.symbol == symbol)
        if broker:
            query = query.filter(TradeFill.broker == broker)

        if uncategorized:
            categorized_subq = (
                select(DecisionContext.fill_id)
                .where(DecisionContext.strategy_id.isnot(None))
                .scalar_subquery()
            )
            query = query.filter(TradeFill.id.notin_(categorized_subq))

        total = query.count()

        column = getattr(TradeFill, sort_field, TradeFill.executed_at)
        query = query.order_by(column.desc() if sort_desc else column.asc())

        offset = (max(page, 1) - 1) * limit
        fills = query.offset(offset).limit(limit).all()
        return fills, total

    def count_fills(
        self,
        account_id: int,
        broker: Optional[str] = None,
    ) -> int:
        """Count trade fills for an account."""
        query = self.session.query(func.count(TradeFill.id)).filter(
            TradeFill.account_id == account_id,
        )
        if broker:
            query = query.filter(TradeFill.broker == broker)
        return query.scalar() or 0

    def get_distinct_symbols(self, account_id: int) -> list[str]:
        """Get distinct traded symbols for an account."""
        rows = (
            self.session.query(distinct(TradeFill.symbol))
            .filter(TradeFill.account_id == account_id)
            .all()
        )
        return [row[0] for row in rows]

    def exists_by_external_id(self, external_id: str) -> bool:
        """Check if a fill with the given external_trade_id exists."""
        return self.session.query(TradeFill).filter(
            TradeFill.external_trade_id == external_id,
        ).first() is not None

    def get_latest_fill(
        self,
        account_id: int,
        broker: Optional[str] = None,
    ) -> Optional[TradeFill]:
        """Get the most recently created fill for an account."""
        query = self.session.query(TradeFill).filter(
            TradeFill.account_id == account_id,
        )
        if broker:
            query = query.filter(TradeFill.broker == broker)
        return query.order_by(TradeFill.created_at.desc()).first()

    def create_fill(self, **kwargs) -> TradeFill:
        """Create a new trade fill."""
        fill = TradeFill(**kwargs)
        self.session.add(fill)
        self.session.flush()
        return fill

    def backfill_account_id(
        self,
        connection_ids: list[int],
        account_id: int,
    ) -> int:
        """Set account_id on fills with NULL account_id for given connections.

        Returns:
            Number of rows updated.
        """
        if not connection_ids:
            return 0
        count = self.session.query(TradeFill).filter(
            TradeFill.broker_connection_id.in_(connection_ids),
            TradeFill.account_id.is_(None),
        ).update({"account_id": account_id}, synchronize_session="fetch")
        if count:
            self.session.flush()
            logger.info("Backfilled account_id=%d on %d fills", account_id, count)
        return count

    # -------------------------------------------------------------------------
    # Decision Context Operations
    # -------------------------------------------------------------------------

    def get_decision_context(self, fill_id: int) -> Optional[DecisionContext]:
        """Get decision context by fill_id."""
        return self.session.query(DecisionContext).filter(
            DecisionContext.fill_id == fill_id,
        ).first()

    def get_context_summaries_for_fills(
        self,
        fill_ids: list[int],
    ) -> dict[int, dict]:
        """Batch-load context + strategy name for a list of fill IDs.

        Returns:
            Dict mapping fill_id -> {hypothesis, feelings_then, strategy_name}.
        """
        if not fill_ids:
            return {}

        rows = (
            self.session.query(
                DecisionContext.fill_id,
                DecisionContext.hypothesis,
                DecisionContext.feelings_then,
                Strategy.name.label("strategy_name"),
            )
            .outerjoin(Strategy, Strategy.id == DecisionContext.strategy_id)
            .filter(DecisionContext.fill_id.in_(fill_ids))
            .all()
        )

        result: dict[int, dict] = {}
        for fill_id, hypothesis, feelings_then, strategy_name in rows:
            if fill_id not in result:
                result[fill_id] = {
                    "hypothesis": hypothesis,
                    "feelings_then": feelings_then,
                    "strategy_name": strategy_name,
                }
        return result

    def get_strategy_by_name(
        self,
        name: str,
        account_id: int,
    ) -> Optional[Strategy]:
        """Get strategy by name and account_id."""
        return self.session.query(Strategy).filter(
            Strategy.name == name,
            Strategy.account_id == account_id,
        ).first()

    def get_strategy_by_id(
        self,
        strategy_id: int,
        account_id: Optional[int] = None,
    ) -> Optional[Strategy]:
        """Get strategy by ID, optionally scoped to account."""
        query = self.session.query(Strategy).filter(Strategy.id == strategy_id)
        if account_id is not None:
            query = query.filter(Strategy.account_id == account_id)
        return query.first()

    def get_existing_check_names(
        self,
        account_id: int,
        decision_context_id: int,
    ) -> set[str]:
        """Get check_name values already recorded for a decision context.

        Used for deduplication: if a check_name already exists for this
        (account_id, decision_context_id) pair, the checker can be skipped.

        Args:
            account_id: Trader's account ID
            decision_context_id: The decision context being evaluated

        Returns:
            Set of check_name strings already persisted.
        """
        rows = (
            self.session.query(distinct(CampaignCheck.check_name))
            .filter(
                CampaignCheck.account_id == account_id,
                CampaignCheck.decision_context_id == decision_context_id,
            )
            .all()
        )
        names = {row[0] for row in rows}
        if names:
            logger.debug(
                "Found %d existing check names for account_id=%s dc_id=%s: %s",
                len(names), account_id, decision_context_id, names,
            )
        return names

    # -------------------------------------------------------------------------
    # Fills with Context (joins)
    # -------------------------------------------------------------------------

    def get_fills_with_context(
        self,
        account_id: int,
        cutoff: datetime,
        symbol: Optional[str] = None,
    ) -> list[tuple]:
        """Get fills with decision contexts and strategy names.

        Returns list of (TradeFill, DecisionContext|None, strategy_name|None).
        """
        query = (
            self.session.query(
                TradeFill,
                DecisionContext,
                Strategy.name.label("strategy_name"),
            )
            .outerjoin(DecisionContext, DecisionContext.fill_id == TradeFill.id)
            .outerjoin(Strategy, Strategy.id == DecisionContext.strategy_id)
            .filter(
                TradeFill.account_id == account_id,
                TradeFill.executed_at >= cutoff,
            )
        )

        if symbol:
            query = query.filter(TradeFill.symbol == symbol.upper())

        return query.order_by(TradeFill.executed_at.asc()).all()

    def get_distinct_strategy_ids(
        self,
        account_id: int,
        symbol: str,
    ) -> list[Optional[int]]:
        """Get distinct strategy IDs for fills of a given account + symbol."""
        rows = (
            self.session.query(distinct(DecisionContext.strategy_id))
            .join(TradeFill, TradeFill.id == DecisionContext.fill_id)
            .filter(
                TradeFill.account_id == account_id,
                TradeFill.symbol == symbol.upper(),
            )
            .all()
        )
        return [row[0] for row in rows]

    def get_recent_fill_ids(
        self,
        account_id: int,
        cutoff: datetime,
    ) -> list[int]:
        """Get fill IDs with decision contexts executed after cutoff."""
        rows = (
            self.session.query(DecisionContext.fill_id)
            .join(TradeFill, TradeFill.id == DecisionContext.fill_id)
            .filter(
                DecisionContext.account_id == account_id,
                TradeFill.executed_at >= cutoff,
            )
            .all()
        )
        return [row[0] for row in rows]

    def get_active_account_ids(self, cutoff: datetime) -> list[int]:
        """Get distinct account IDs with fills after cutoff."""
        rows = (
            self.session.query(distinct(TradeFill.account_id))
            .filter(
                TradeFill.account_id.isnot(None),
                TradeFill.executed_at >= cutoff,
            )
            .all()
        )
        return [row[0] for row in rows]

    # -------------------------------------------------------------------------
    # P&L Aggregation
    # -------------------------------------------------------------------------

    def get_pnl_timeseries(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: Literal["day", "week", "month"] = "day",
    ) -> list[dict]:
        """Get P&L timeseries aggregated by period.

        Returns list of dicts with keys:
            period, sell_proceeds, buy_cost, fees, fill_count.
        """
        if granularity == "week":
            date_trunc = func.date_trunc("week", TradeFill.executed_at)
        elif granularity == "month":
            date_trunc = func.date_trunc("month", TradeFill.executed_at)
        else:
            date_trunc = func.date(TradeFill.executed_at)

        query = self.session.query(
            date_trunc.label("period"),
            func.coalesce(
                func.sum(
                    case(
                        (TradeFill.side == "sell", TradeFill.quantity * TradeFill.price),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("sell_proceeds"),
            func.coalesce(
                func.sum(
                    case(
                        (TradeFill.side == "buy", TradeFill.quantity * TradeFill.price),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("buy_cost"),
            func.coalesce(func.sum(TradeFill.fees), 0.0).label("fees"),
            func.count(TradeFill.id).label("fill_count"),
        ).filter(TradeFill.account_id == account_id)

        if symbol:
            query = query.filter(TradeFill.symbol == symbol.upper())
        if start_date:
            query = query.filter(func.date(TradeFill.executed_at) >= start_date)
        if end_date:
            query = query.filter(func.date(TradeFill.executed_at) <= end_date)

        rows = (
            query.group_by(date_trunc)
            .order_by(date_trunc.asc())
            .all()
        )

        return [
            {
                "period": row.period,
                "sell_proceeds": row.sell_proceeds,
                "buy_cost": row.buy_cost,
                "fees": row.fees,
                "fill_count": row.fill_count,
            }
            for row in rows
        ]
