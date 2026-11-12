"""Tests for the database layer."""

from __future__ import annotations

from app.database.connection import DatabaseConnection
from app.database.repositories import (
    AnalysisSessionRepository,
    ExaminationRepository,
    QCFindingRepository,
    SeriesRepository,
)
from app.domain.findings import QCFinding


def test_sqlite_file(tmp_path):
    db = DatabaseConnection(f"sqlite:///{tmp_path}/test.db")
    db.create_all()
    session = db.get_session()
    try:
        from app.database.models import AnalysisSession
        obj = AnalysisSession(
            id="sess-1", source_type="local_folder", source_reference="x", status="pending"
        )
        session.add(obj)
        session.commit()
        q = session.query(AnalysisSession).filter_by(id="sess-1").first()
        assert q is not None
        assert q.status == "pending"
    finally:
        session.close()
    db.dispose()


def test_repositories(tmp_path):
    db = DatabaseConnection(f"sqlite:///{tmp_path}/test.db")
    db.create_all()
    try:
        sess_repo = AnalysisSessionRepository(db)
        sess = sess_repo.create(source_type="local_folder", source_reference="x")
        assert sess.id is not None
        sess_repo.mark_completed(sess.id, duration_seconds=1.5)
        fetched = sess_repo.get(sess.id)
        assert fetched.status == "completed"

        exam_repo = ExaminationRepository(db)
        exam = exam_repo.create(
            session_id=sess.id, study_instance_uid="1.2.3", modality="CT",
            study_date="20240101", study_description="desc",
            series_count=1, instance_count=3, source_path="/x",
        )
        assert exam.id is not None

        series_repo = SeriesRepository(db)
        series = series_repo.create(
            examination_id=exam.id, series_instance_uid="1.2.3.4",
            modality="CT", description="series desc", instance_count=3,
        )
        assert series.id is not None

        finding_repo = QCFindingRepository(db)
        f = QCFinding(
            finding_id="f-1", session_id=sess.id, examination_id=exam.id,
            series_id=series.id, category="metadata", severity="HIGH",
            title="Test", description="desc", recommended_action="action",
            confidence=0.9, relevant_dicom_tags=["PatientID"],
        )
        finding_repo.add(f)
        listed = finding_repo.list_for_session(sess.id)
        assert len(listed) == 1
        sev_counts = finding_repo.count_by_severity(sess.id)
        assert sev_counts.get("HIGH") == 1
    finally:
        db.dispose()
