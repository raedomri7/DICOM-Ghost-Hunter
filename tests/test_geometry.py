"""Tests for the geometry validator."""

from __future__ import annotations

import os

from app.analysis.geometry_validator import GeometryValidator
from app.dicom.reader import DICOMReader
from tests.conftest import (
    build_file_meta,
    create_normal_series,
    instances_from_files,
    make_dataset,
    write_dicom_file,
)


def test_normal_geometry(reader, tmp_dir):
    files, _, _ = create_normal_series(tmp_dir, num_slices=3)
    instances = instances_from_files(reader, files)
    validator = GeometryValidator()
    findings = validator.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=instances,
    )
    geometry_issues = [f for f in findings if f.category == "geometry"]
    assert len(geometry_issues) == 0


def test_dimensions_out_of_range(reader, tmp_dir):
    file_meta = build_file_meta()
    ds = make_dataset(
        sop_instance_uid="1.2.3.4.5",
        study_instance_uid="1.2.3.4.6",
        series_instance_uid="1.2.3.4.7",
        rows=5,  # below min 16
        columns=5,
    )
    path = os.path.join(tmp_dir, "small.dcm")
    write_dicom_file(ds, file_meta, path)
    instance = DICOMReader().read_file(path).instance
    validator = GeometryValidator()
    findings = validator.analyze(
        session_id="sess-1", examination_id="exam-1", series_id="ser-1",
        instances=[instance],
    )
    issues = [f for f in findings if f.category == "geometry"]
    assert len(issues) >= 1
