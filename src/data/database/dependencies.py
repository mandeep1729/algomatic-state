"""Unified database access layer.

Single source of truth for all database session management:
- get_db()           — FastAPI Depends generator yielding a Session
- get_trading_repo() — FastAPI Depends returning TradingBuddyRepository
- get_broker_repo()  — FastAPI Depends returning BrokerRepository
- get_journal_repo() — FastAPI Depends returning JournalRepository
- get_probe_repo()   — FastAPI Depends returning ProbeRepository
- get_market_repo()  — FastAPI Depends returning OHLCVRepository
- session_scope()    — Context manager for background tasks / non-DI usage
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


def get_broker_repo():
    """FastAPI dependency returning a BrokerRepository.

    Usage::

        @router.get("/trades")
        async def get_trades(repo: BrokerRepository = Depends(get_broker_repo)):
            ...
    """
    from src.data.database.broker_repository import BrokerRepository

    with get_db_manager().get_session() as session:
        yield BrokerRepository(session)


def get_journal_repo():
    """FastAPI dependency returning a JournalRepository.

    Usage::

        @router.get("/entries")
        async def list_entries(repo: JournalRepository = Depends(get_journal_repo)):
            ...
    """
    from src.data.database.journal_repository import JournalRepository

    with get_db_manager().get_session() as session:
        yield JournalRepository(session)


def get_probe_repo():
    """FastAPI dependency returning a ProbeRepository.

    Usage::

        @router.get("/probe")
        async def get_probe(repo: ProbeRepository = Depends(get_probe_repo)):
            ...
    """
    from src.data.database.probe_repository import ProbeRepository

    with get_db_manager().get_session() as session:
        yield ProbeRepository(session)


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


def get_market_grpc_client():
    """FastAPI dependency returning a MarketDataGrpcClient.

    Uses gRPC to communicate with the data-service instead of direct DB access.

    Usage::

        @router.get("/bars")
        async def get_bars(repo = Depends(get_market_grpc_client)):
            ...
    """
    import grpc
    from config.settings import get_settings
    from src.data.grpc_client import MarketDataGrpcClient

    settings = get_settings()
    channel = grpc.insecure_channel(settings.data_service.target)
    try:
        yield MarketDataGrpcClient(channel)
    finally:
        channel.close()


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


@contextmanager
def grpc_market_client():
    """Context manager for background tasks needing market data via gRPC.

    Use in helpers, orchestrators, scripts — anywhere outside FastAPI's
    dependency injection that needs market data access.

    Usage::

        with grpc_market_client() as repo:
            df = repo.get_bars("AAPL", "1Min")
    """
    import grpc
    from config.settings import get_settings
    from src.data.grpc_client import MarketDataGrpcClient

    settings = get_settings()
    channel = grpc.insecure_channel(settings.data_service.target)
    try:
        yield MarketDataGrpcClient(channel)
    finally:
        channel.close()
