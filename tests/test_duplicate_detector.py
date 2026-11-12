"""Tests for the duplicate detector."""

from __future__ import annotations

from pydicom import dcmread

from app.analysis.duplicate_detector import DuplicateDetector
from tests.conftest import (
    build_file_meta,
    create_duplicate_files,
    create_normal_series,
    instances_from_files,
    write_dicom_file,
)


def test_file_level_duplicate_detected(reader, tmp_dir):
    files, _, _ = create_duplicate_files(tmp_dir, num_copies=3)
    instances = instances_from_files(reader, files)
    detector = DuplicateDetector()
    findings = detector.detect(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1", instances=instances
    )
    file_dups = [f for f in findings if "file-level" in f.title]
    assert len(file_dups) == 1
    assert file_dups[0].severity == "MEDIUM"
    assert file_dups[0].confidence >= 0.9


def test_metadata_level_duplicate_detected(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=2)
    ds1 = dcmread(files[0])
    ds2 = dcmread(files[1])
    ds2.SOPInstanceUID = ds1.SOPInstanceUID
    write_dicom_file(ds2, build_file_meta(), files[1])
    instances = instances_from_files(reader, files)
    detector = DuplicateDetector()
    findings = detector.detect(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1", instances=instances
    )
    meta_dups = [
        f for f in findings
        if "metadata duplicate" in f.title.lower() or "SOPInstanceUID" in f.title
    ]
    assert len(meta_dups) >= 1


def test_no_duplicates_for_distinct_files(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=3)
    instances = instances_from_files(reader, files)
    detector = DuplicateDetector()
    findings = detector.detect(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1", instances=instances
    )
    dups = [f for f in findings if f.category == "duplicate"]
    assert len(dups) == 0
