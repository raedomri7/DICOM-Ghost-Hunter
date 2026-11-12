"""Repository pattern for database access.

Repositories encapsulate all SQLAlchemy queries so the rest of the application
remains independent of the ORM, easing a future migration to PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import DatabaseConnection
from app.database.models import (
    AnalysisSession,
    Examination,
    QCFinding,
    Report,
    Series,
)
from app.domain.enums import SessionStatus


class BaseRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db

    def _session(self) -> Session:
        return self.db.get_session()


class AnalysisSessionRepository(BaseRepository):
    def create(
        self,
        session_id: str | None = None,
        source_type: str = "local_folder",
        source_reference: str = "",
        configuration: str | None = None,
    ) -> AnalysisSession:
        sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
        with self._session() as sess:
            obj = AnalysisSession(
                id=sid,
                source_type=source_type,
                source_reference=source_reference,
                status=SessionStatus.PENDING,
                configuration=configuration,
            )
            sess.add(obj)
            sess.commit()
            sess.refresh(obj)
            return obj

    def mark_completed(self, session_id: str, duration_seconds: float | None = None) -> None:
        with self._session() as sess:
            obj = sess.get(AnalysisSession, session_id)
            if obj:
                obj.status = SessionStatus.COMPLETED
                obj.completed_at = datetime.now(UTC)
                if duration_seconds is not None:
                    obj.duration_seconds = duration_seconds
                sess.commit()

    def mark_failed(self, session_id: str) -> None:
        with self._session() as sess:
            obj = sess.get(AnalysisSession, session_id)
            if obj:
                obj.status = SessionStatus.FAILED
                obj.completed_at = datetime.now(UTC)
                sess.commit()

    def get(self, session_id: str) -> AnalysisSession | None:
        with self._session() as sess:
            return sess.get(AnalysisSession, session_id)

    def list_all(self, limit: int = 50) -> list[AnalysisSession]:
        with self._session() as sess:
            return (
                sess.query(AnalysisSession)
                .order_by(AnalysisSession.started_at.desc())
                .limit(limit)
                .all()
            )


class ExaminationRepository(BaseRepository):
    def create(
        self,
        session_id: str,
        study_instance_uid: str | None,
        modality: str | None,
        study_date: str | None,
        study_description: str | None,
        series_count: int,
        instance_count: int,
        source_path: str | None,
        examination_id: str | None = None,
    ) -> Examination:
        eid = examination_id or f"exam-{uuid.uuid4().hex[:12]}"
        with self._session() as sess:
            obj = Examination(
                id=eid,
                session_id=session_id,
                study_instance_uid=study_instance_uid,
                modality=modality,
                study_date=study_date,
                study_description=study_description,
                series_count=series_count,
                instance_count=instance_count,
                source_path=source_path,
            )
            sess.add(obj)
            sess.commit()
            sess.refresh(obj)
            return obj

    def get(self, examination_id: str) -> Examination | None:
        with self._session() as sess:
            return sess.get(Examination, examination_id)


class SeriesRepository(BaseRepository):
    def create(
        self,
        examination_id: str,
        series_instance_uid: str | None,
        modality: str | None,
        description: str | None,
        instance_count: int,
        series_id: str | None = None,
    ) -> Series:
        sid = series_id or f"ser-{uuid.uuid4().hex[:12]}"
        with self._session() as sess:
            obj = Series(
                id=sid,
                examination_id=examination_id,
                series_instance_uid=series_instance_uid,
                modality=modality,
                description=description,
                instance_count=instance_count,
            )
            sess.add(obj)
            sess.commit()
            sess.refresh(obj)
            return obj


class QCFindingRepository(BaseRepository):
    def add(self, finding) -> QCFinding:
        """Persist a domain QCFinding (dataclass) to the database."""
        with self._session() as sess:
            obj = QCFinding(
                id=finding.finding_id,
                session_id=finding.session_id,
                examination_id=finding.examination_id,
                series_id=finding.series_id,
                instance_reference=finding.instance_reference,
                category=finding.category,
                severity=finding.severity,
                title=finding.title,
                description=finding.description,
                recommendation=finding.recommended_action,
                confidence=finding.confidence,
                dicom_tags=",".join(finding.relevant_dicom_tags) if finding.relevant_dicom_tags else None,
                created_at=(
                    datetime.fromisoformat(finding.created_at)
                    if finding.created_at
                    else datetime.now(UTC)
                ),
            )
            sess.add(obj)
            sess.commit()
            sess.refresh(obj)
            return obj

    def list_for_session(
        self,
        session_id: str,
        severity: str | None = None,
        category: str | None = None,
        limit: int = 500,
    ) -> list[QCFinding]:
        with self._session() as sess:
            query = sess.query(QCFinding).filter(QCFinding.session_id == session_id)
            if severity:
                query = query.filter(QCFinding.severity == severity)
            if category:
                query = query.filter(QCFinding.category == category)
            return query.order_by(QCFinding.created_at.desc()).limit(limit).all()

    def count_by_severity(self, session_id: str) -> dict[str, int]:
        with self._session() as sess:
            rows = (
                sess.query(QCFinding.severity, func.count(QCFinding.id))
                .filter(QCFinding.session_id == session_id)
                .group_by(QCFinding.severity)
                .all()
            )
        return {sev or "UNKNOWN": int(cnt) for sev, cnt in rows}

    def count_by_category(self, session_id: str) -> dict[str, int]:
        with self._session() as sess:
            rows = (
                sess.query(QCFinding.category, func.count(QCFinding.id))
                .filter(QCFinding.session_id == session_id)
                .group_by(QCFinding.category)
                .all()
            )
        return {cat or "UNKNOWN": int(cnt) for cat, cnt in rows}


class ReportRepository(BaseRepository):
    def add(self, session_id: str, file_reference: str, report_type: str = "pdf") -> Report:
        with self._session() as sess:
            rid = f"rep-{uuid.uuid4().hex[:12]}"
            obj = Report(
                id=rid,
                session_id=session_id,
                file_reference=file_reference,
                report_type=report_type,
            )
            sess.add(obj)
            sess.commit()
            sess.refresh(obj)
            return obj
