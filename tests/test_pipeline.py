"""Tests for the QC pipeline orchestration."""

from __future__ import annotations

from app.analysis.pipeline import QCPipeline
from tests.conftest import create_normal_series, instances_from_files


def test_pipeline_runs_all_modules(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=4)
    instances = instances_from_files(reader, files)
    pipeline = QCPipeline()
    results = pipeline.run(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    module_names = {r.module_name for r in results}
    expected = {
        "MetadataValidator", "DuplicateDetector", "SliceContinuityAnalyzer",
        "OrientationAnalyzer", "GeometryValidator", "ImageQualityAnalyzer",
        "PrivacyMetadataChecker", "ExaminationConsistencyAnalyzer",
    }
    assert expected.issubset(module_names)
    total = sum(r.duration_ms for r in results)
    assert total >= 0


def test_pipeline_flat_findings(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=3)
    instances = instances_from_files(reader, files)
    pipeline = QCPipeline()
    findings = pipeline.run_all_findings(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    assert isinstance(findings, list)
    for f in findings:
        assert f.finding_id is not None
        assert f.severity in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
