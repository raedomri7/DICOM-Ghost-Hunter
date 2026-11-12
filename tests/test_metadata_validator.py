"""Tests for the metadata validator."""

from __future__ import annotations

import os

from app.analysis.metadata_validator import MetadataValidator
from app.dicom.reader import DICOMReader
from tests.conftest import (
    build_file_meta,
    create_normal_series,
    instances_from_files,
    make_dataset,
    write_dicom_file,
)


def test_valid_series_no_required_findings(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=3)
    instances = instances_from_files(reader, files)
    validator = MetadataValidator()
    findings = validator.validate_series(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    high = [f for f in findings if f.severity == "HIGH"]
    assert len(high) == 0


def test_missing_required_tag(reader, tmp_dir):
    file_meta = build_file_meta()
    ds = make_dataset(
        sop_instance_uid="1.2.3.4.5",
        study_instance_uid="1.2.3.4.6",
        series_instance_uid="1.2.3.4.7",
        missing_tags=("PatientID",),
    )
    path = os.path.join(tmp_dir, "missing_pid.dcm")
    write_dicom_file(ds, file_meta, path)
    instance = DICOMReader().read_file(path).instance
    validator = MetadataValidator()
    findings = validator.validate_series(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=[instance], modality="CT",
    )
    pid_findings = [f for f in findings if "PatientID" in f.title]
    assert len(pid_findings) == 1
    assert pid_findings[0].severity == "HIGH"


def test_invalid_uid(reader, tmp_dir):
    file_meta = build_file_meta()
    ds = make_dataset(
        sop_instance_uid="1.2.3.4.5",
        study_instance_uid="1.2.3.4.6",
        series_instance_uid="1.2.3.4.7",
        invalid_uid=True,
    )
    path = os.path.join(tmp_dir, "bad_uid.dcm")
    write_dicom_file(ds, file_meta, path)
    instance = DICOMReader().read_file(path).instance
    validator = MetadataValidator()
    findings = validator.validate_series(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=[instance], modality="CT",
    )
    uid_findings = [f for f in findings if "UID" in f.title]
    assert len(uid_findings) >= 1


def test_optional_tag_missing_is_info(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=1)
    instances = instances_from_files(reader, files)
    validator = MetadataValidator()
    findings = validator.validate_series(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances, modality="CT",
    )
    critical_or_high = [f for f in findings if f.severity in ("HIGH", "CRITICAL")]
    assert len(critical_or_high) == 0
