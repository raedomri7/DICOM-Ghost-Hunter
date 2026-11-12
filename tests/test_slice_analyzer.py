"""Tests for the slice continuity analyzer."""

from __future__ import annotations

from app.analysis.slice_analyzer import SliceContinuityAnalyzer
from tests.conftest import (
    create_irregular_series,
    create_normal_series,
    instances_from_files,
)


def test_normal_series_no_discontinuity(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=5, spacing=1.0)
    instances = instances_from_files(reader, files)
    analyzer = SliceContinuityAnalyzer()
    findings = analyzer.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    disc = [f for f in findings if "discontinuity" in f.title.lower()]
    assert len(disc) == 0


def test_irregular_series_flags_discontinuity(reader, tmp_dir):
    files, _, _ = create_irregular_series(tmp_dir, num_slices=4)
    instances = instances_from_files(reader, files)
    analyzer = SliceContinuityAnalyzer()
    findings = analyzer.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    disc = [f for f in findings if "discontinuity" in f.title.lower()]
    assert len(disc) >= 1
    assert disc[0].severity == "HIGH"
    assert "Potential spatial discontinuity" in disc[0].title


def test_insufficient_slices_skipped(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=2)
    instances = instances_from_files(reader, files)
    analyzer = SliceContinuityAnalyzer()  # min_slices default 3
    findings = analyzer.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    assert len(findings) == 0
