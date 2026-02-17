"""Shared fixtures for API endpoint tests.

Provides:
- FastAPI TestClient with auth dependency overridden
- SQLite in-memory database session with test tables
- Helper fixtures for creating test data (accounts, profiles, strategies, etc.)
"""

import logging
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker

from src.data.database.models import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLite test engine setup
# ---------------------------------------------------------------------------

# Register a compilation hook so that PostgreSQL JSONB columns are rendered
# as plain TEXT in SQLite DDL.  This avoids "can't render JSONB" errors
# while keeping model source code unchanged.

from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):
    """Render BigInteger as INTEGER in SQLite so AUTOINCREMENT works."""
    return "INTEGER"


_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    # Silence the CheckConstraint warnings that reference PG-only syntax
    # (they are silently ignored by SQLite anyway).
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key support in SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_TEST_ENGINE,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Fixed user ID used by all tests (overrides get_current_user dependency).
TEST_USER_ID = 1
OTHER_USER_ID = 2


@pytest.fixture(autouse=True)
def _create_tables():
    """Create all tables before each test and drop after."""
    # Import all model modules so their tables are registered on Base.metadata.
    import src.data.database.trading_buddy_models  # noqa: F401
    import src.data.database.broker_models  # noqa: F401
    import src.data.database.strategy_models  # noqa: F401
    import src.data.database.journal_models  # noqa: F401
    import src.data.database.trade_lifecycle_models  # noqa: F401

    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session for a test."""
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def test_account(db_session: Session):
    """Create and return a test user account with id=TEST_USER_ID."""
    from src.data.database.trading_buddy_models import UserAccount

    account = UserAccount(
        id=TEST_USER_ID,
        external_user_id="test_ext_001",
        name="Test User",
        email="test@example.com",
        auth_provider="google",
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture()
def other_account(db_session: Session):
    """Create a second user account for multi-tenant isolation tests."""
    from src.data.database.trading_buddy_models import UserAccount

    account = UserAccount(
        id=OTHER_USER_ID,
        external_user_id="test_ext_002",
        name="Other User",
        email="other@example.com",
        auth_provider="google",
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """Create a FastAPI TestClient with dependency overrides.

    - get_current_user always returns TEST_USER_ID
    - All DB dependencies (get_db, get_trading_repo, get_market_repo) use db_session
    """
    from src.api.auth_middleware import get_current_user
    from src.data.database.dependencies import (
        get_db, get_trading_repo, get_market_repo,
        get_broker_repo, get_journal_repo, get_probe_repo,
    )
    from src.data.database.trading_repository import TradingBuddyRepository
    from src.data.database.broker_repository import BrokerRepository
    from src.data.database.journal_repository import JournalRepository
    from src.data.database.probe_repository import ProbeRepository

    # Build a minimal FastAPI app with only the routers under test
    from fastapi import FastAPI

    from src.api.user_profile import router as user_profile_router
    from src.api.strategies import router as strategies_router
    from src.api.journal import router as journal_router
    from src.api.campaigns import router as campaigns_router
    from src.api.broker import router as broker_router

    app = FastAPI()
    app.include_router(user_profile_router)
    app.include_router(strategies_router)
    app.include_router(journal_router)
    app.include_router(campaigns_router)
    app.include_router(broker_router)

    # --- Dependency overrides ---

    def override_get_current_user():
        return TEST_USER_ID

    def override_get_db():
        yield db_session

    def override_get_trading_repo():
        yield TradingBuddyRepository(db_session)

    def override_get_broker_repo():
        yield BrokerRepository(db_session)

    def override_get_journal_repo():
        yield JournalRepository(db_session)

    def override_get_probe_repo():
        yield ProbeRepository(db_session)

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_trading_repo] = override_get_trading_repo
    app.dependency_overrides[get_broker_repo] = override_get_broker_repo
    app.dependency_overrides[get_journal_repo] = override_get_journal_repo
    app.dependency_overrides[get_probe_repo] = override_get_probe_repo

    yield TestClient(app)
