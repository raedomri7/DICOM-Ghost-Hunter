"""Database connection and session management using SQLAlchemy.

SQLite is the default backend. The layer is repository-backed and prepared for a
future migration to PostgreSQL by keeping connection string configuration
externalized.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.logging_config import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class DatabaseConnection:
    """Manages the SQLAlchemy engine and scoped sessions."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        connect_args: dict = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self.engine: Engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)

        # Enable foreign keys for SQLite.
        if database_url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        logger.info("Database engine created for %s", database_url)

    def create_all(self) -> None:
        """Create all tables defined on the declarative Base."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created/verified")

    def get_session(self) -> Session:
        """Return a new SQLAlchemy session."""
        return self.SessionLocal()

    def dispose(self) -> None:
        """Dispose of the connection pool."""
        self.engine.dispose()
