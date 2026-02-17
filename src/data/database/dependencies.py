"""Unified database access layer.

Single source of truth for all database session management:
- get_db()          — FastAPI Depends generator yielding a Session
- get_trading_repo() — FastAPI Depends returning TradingBuddyRepository
- get_market_repo()  — FastAPI Depends returning OHLCVRepository
- session_scope()   — Context manager for background tasks / non-DI usage
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from src.data.database.connection import get_db_manager

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.

    Usage::

        @router.get("/items")
        async def list_items(db: Session = Depends(get_db)):
            ...
    """
    with get_db_manager().get_session() as session:
        yield session


def get_trading_repo():
    """FastAPI dependency returning a TradingBuddyRepository.

    Usage::

        @router.get("/strategies")
        async def list_strategies(repo: TradingBuddyRepository = Depends(get_trading_repo)):
            ...
    """
    from src.data.database.trading_repository import TradingBuddyRepository

    with get_db_manager().get_session() as session:
        yield TradingBuddyRepository(session)


def get_market_repo():
    """FastAPI dependency returning an OHLCVRepository.

    Usage::

        @router.get("/bars")
        async def get_bars(repo: OHLCVRepository = Depends(get_market_repo)):
            ...
    """
    from src.data.database.market_repository import OHLCVRepository

    with get_db_manager().get_session() as session:
        yield OHLCVRepository(session)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for non-DI database access.

    Use in background tasks, orchestrators, scripts — anywhere
    outside FastAPI's dependency injection.

    Usage::

        with session_scope() as session:
            repo = TradingBuddyRepository(session)
            repo.do_something()
    """
    with get_db_manager().get_session() as session:
        yield session
