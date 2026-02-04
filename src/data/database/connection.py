"""Database connection management with connection pooling."""

import logging
from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from config.settings import DatabaseConfig, get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage database connections with connection pooling.

    Provides a centralized way to manage database connections,
    sessions, and connection pooling for the application.
    """

    def __init__(self, config: DatabaseConfig):
        """Initialize database manager.

        Args:
            config: Database configuration settings
        """
        self.config = config
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None

    @property
    def engine(self) -> Engine:
        """Get or create the database engine with connection pooling."""
        if self._engine is None:
            logger.info(
                "Creating database engine (pool_size=%d, max_overflow=%d)",
                self.config.pool_size, self.config.max_overflow,
            )
            self._engine = create_engine(
                self.config.url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_pre_ping=True,  # Enable connection health checks
                echo=self.config.echo,
            )
            # Set timezone to UTC for all connections
            @event.listens_for(self._engine, "connect")
            def set_timezone(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET timezone = 'UTC'")
                cursor.close()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get or create the session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        return self._session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup.

        Usage:
            with db_manager.get_session() as session:
                # Use session for database operations
                session.add(...)
                # Commit happens automatically on success

        Yields:
            Session: SQLAlchemy session for database operations

        Raises:
            Exception: Re-raises any exception after rollback
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            logger.warning("Database session error, rolling back")
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self) -> None:
        """Create all database tables.

        Note: In production, use Alembic migrations instead.
        This is useful for testing or initial setup.
        """
        from src.data.database.models import Base
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self) -> None:
        """Drop all database tables.

        Warning: This will delete all data. Use with caution.
        """
        from src.data.database.models import Base
        Base.metadata.drop_all(bind=self.engine)

    def dispose(self) -> None:
        """Dispose of the connection pool.

        Call this when shutting down the application to
        properly close all database connections.
        """
        if self._engine is not None:
            logger.info("Disposing database connection pool")
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def health_check(self) -> bool:
        """Check if database connection is healthy.

        Returns:
            bool: True if database is reachable, False otherwise
        """
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.error("Database health check failed", exc_info=True)
            return False


# Global database manager instance (lazy loaded)
_db_manager: DatabaseManager | None = None


@lru_cache
def get_db_manager() -> DatabaseManager:
    """Get the singleton database manager instance.

    Returns:
        DatabaseManager: Configured database manager
    """
    global _db_manager
    if _db_manager is None:
        settings = get_settings()
        _db_manager = DatabaseManager(settings.database)
    return _db_manager


def reset_db_manager() -> None:
    """Reset the database manager instance.

    Useful for testing or when configuration changes.
    """
    global _db_manager
    if _db_manager is not None:
        _db_manager.dispose()
        _db_manager = None
    get_db_manager.cache_clear()
