"""Tests for the orientation analyzer."""

from __future__ import annotations

from app.analysis.orientation_analyzer import OrientationAnalyzer
from tests.conftest import (
    create_inconsistent_orientation_series,
    create_normal_series,
    instances_from_files,
)


def test_consistent_orientation(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=4)
    instances = instances_from_files(reader, files)
    analyzer = OrientationAnalyzer()
    findings = analyzer.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances,
    )
    orientation_issues = [f for f in findings if f.category == "orientation"]
    assert len(orientation_issues) == 0


def test_inconsistent_orientation_detected(reader, tmp_dir):
    files, _, _ = create_inconsistent_orientation_series(tmp_dir, num_slices=4)
    instances = instances_from_files(reader, files)
    analyzer = OrientationAnalyzer()
    findings = analyzer.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances,
    )
    orientation_issues = [f for f in findings if f.category == "orientation"]
    assert len(orientation_issues) >= 1
