"""Application bootstrap and wiring of services and repositories."""

from __future__ import annotations

from app.core.logging_config import configure_logging, get_logger
from app.database.connection import DatabaseConnection
from app.database.repositories import (
    AnalysisSessionRepository,
    ExaminationRepository,
    QCFindingRepository,
    ReportRepository,
    SeriesRepository,
)
from app.services.analysis_service import AnalysisService
from app.services.import_service import ImportService
from app.services.processing_service import ProcessingService
from app.services.report_service import ReportService

logger = get_logger(__name__)


class Application:
    """Central application container wiring dependencies together."""

    def __init__(self, database_url: str | None = None) -> None:
        configure_logging()
        self.logger = get_logger(self.__class__.__name__)

        from config.settings import settings

        settings.ensure_directories()
        self.database_url = database_url or settings.database_url
        self.db = DatabaseConnection(self.database_url)
        self.db.create_all()

        # Repositories
        self.session_repo = AnalysisSessionRepository(self.db)
        self.examination_repo = ExaminationRepository(self.db)
        self.series_repo = SeriesRepository(self.db)
        self.finding_repo = QCFindingRepository(self.db)
        self.report_repo = ReportRepository(self.db)

        # Services
        self.import_service = ImportService(
            session_repo=self.session_repo,
            examination_repo=self.examination_repo,
            series_repo=self.series_repo,
            finding_repo=self.finding_repo,
        )
        self.analysis_service = AnalysisService(
            session_repo=self.session_repo,
            examination_repo=self.examination_repo,
            series_repo=self.series_repo,
            finding_repo=self.finding_repo,
        )
        self.report_service = ReportService(
            session_repo=self.session_repo,
            examination_repo=self.examination_repo,
            series_repo=self.series_repo,
            finding_repo=self.finding_repo,
            report_repo=self.report_repo,
        )
        self.processing_service = ProcessingService()

        self.logger.info("Application initialized with database %s", self.database_url)

    def shutdown(self) -> None:
        """Dispose of database engine and other resources."""
        self.db.dispose()
        self.logger.info("Application shutdown complete")


def create_application(database_url: str | None = None) -> Application:
    """Factory to create a fully wired Application instance."""
    return Application(database_url=database_url)
