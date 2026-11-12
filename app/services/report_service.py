"""Report service: coordinates PDF report generation and persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.exceptions import ReportGenerationError
from app.core.logging_config import get_logger
from app.reporting.pdf_generator import PDFReportGenerator

logger = get_logger(__name__)


class ReportService:
    """Generates and stores QC reports."""

    def __init__(
        self,
        session_repo: Any,
        examination_repo: Any,
        series_repo: Any,
        finding_repo: Any,
        report_repo: Any,
    ) -> None:
        self.session_repo = session_repo
        self.examination_repo = examination_repo
        self.series_repo = series_repo
        self.finding_repo = finding_repo
        self.report_repo = report_repo

    def generate_pdf_report(
        self,
        session_id: str,
        output_path: str | Path,
    ) -> dict[str, Any]:
        """Generate a PDF QC report for a session and persist a reference."""
        try:
            # Gather data from repositories.
            session = self.session_repo.get(session_id)
            if session is None:
                raise ReportGenerationError(f"Session {session_id} not found.")

            examinations = []
            # Examinations are not directly listable per session via a repo method;
            # we reconstruct from findings/exam references if needed. For the MVP,
            # build a minimal examination summary from the session reference.
            examinations.append({
                "study_instance_uid": getattr(session, "study_instance_uid", None) or "-",
                "modality": "-",
                "series_count": 0,
                "instance_count": 0,
                "source_reference": session.source_reference,
            })

            findings = self.finding_repo.list_for_session(session_id, limit=1000)
            findings_dicts = [
                {
                    "finding_id": f.id,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "recommended_action": f.recommendation or "-",
                    "instance_reference": f.instance_reference or "-",
                }
                for f in findings
            ]

            session_info = {
                "session_id": session.id,
                "source_type": session.source_type,
                "source_reference": session.source_reference,
                "status": session.status,
                "generated_at": str(session.started_at) if session.started_at else "-",
            }

            generator = PDFReportGenerator()
            result = generator.generate_from_data(
                output_path=str(output_path),
                session_info=session_info,
                examinations=examinations,
                findings=findings_dicts,
            )
        except ReportGenerationError:
            raise
        except Exception as exc:
            logger.exception("PDF report generation failed for session %s", session_id)
            raise ReportGenerationError(f"Failed to generate PDF report: {exc}") from exc

        try:
            self.report_repo.add(
                session_id=session_id,
                file_reference=str(output_path),
                report_type="pdf",
            )
        except Exception:
            logger.exception("Failed to persist report reference: %s", session_id)

        return result
