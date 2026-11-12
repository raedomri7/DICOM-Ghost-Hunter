"""Database package exports and initialization."""

from __future__ import annotations

from app.core.logging_config import get_logger
from app.database.connection import Base, DatabaseConnection
from app.database.migrations import SCHEMA_VERSION
from app.database.models import (
    AnalysisSession,
    Examination,
    QCFinding,
    Report,
    Series,
)
from app.database.repositories import (
    AnalysisSessionRepository,
    ExaminationRepository,
    QCFindingRepository,
    ReportRepository,
    SeriesRepository,
)

logger = get_logger(__name__)


def bootstrap_database(database_url: str | None = None) -> DatabaseConnection:
    """Create the database connection and initialize all tables."""
    from config.settings import settings

    settings.ensure_directories()
    url = database_url or settings.database_url
    db = DatabaseConnection(url)
    db.create_all()
    logger.info("Database bootstrapped at %s", url)
    return db


__all__ = [
    "SCHEMA_VERSION",
    "AnalysisSession",
    "AnalysisSessionRepository",
    "Base",
    "DatabaseConnection",
    "Examination",
    "ExaminationRepository",
    "QCFinding",
    "QCFindingRepository",
    "Report",
    "ReportRepository",
    "Series",
    "SeriesRepository",
    "bootstrap_database",
]
