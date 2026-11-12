"""Tests for the DICOM reader."""

from __future__ import annotations

import os


def test_read_valid_dicom_file(reader, tmp_dir):
    from tests.conftest import create_normal_series

    files, _, _ = create_normal_series(tmp_dir, num_slices=2)
    result = reader.read_file(files[0])
    assert result.success is True
    assert result.instance is not None
    assert result.instance.sop_instance_uid is not None
    assert result.instance.modality == "CT"
    assert result.instance.rows == 64
    assert result.instance.columns == 64
    assert result.instance.sha256 is not None


def test_read_folder(reader, tmp_dir):
    import os

    from tests.conftest import create_normal_series, write_non_dicom_file

    _files, _, _ = create_normal_series(tmp_dir, num_slices=3)
    # A file with no extension but non-DICOM content IS a candidate and must fail.
    write_non_dicom_file(os.path.join(tmp_dir, "not_dicom_noext"))
    results = reader.read_folder(tmp_dir)
    assert len(results) == 4  # 3 dcm + 1 no-extension candidate
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    assert len(successes) == 3
    assert len(failures) == 1
    assert failures[0].error is not None


def test_read_nonexistent_file(reader):
    result = reader.read_file("C:\\nonexistent\\file.dcm")
    assert result.success is False
    assert result.error is not None


def test_read_invalid_dicom(reader, tmp_dir):
    from tests.conftest import write_non_dicom_file

    path = os.path.join(tmp_dir, "bad.dcm")
    write_non_dicom_file(path)
    result = reader.read_file(path)
    assert result.success is False


def test_sha256_determinism(reader, tmp_dir):
    from tests.conftest import create_normal_series

    files, _, _ = create_normal_series(tmp_dir, num_slices=1)
    r1 = reader.read_file(files[0])
    r2 = reader.read_file(files[0])
    assert r1.instance.sha256 == r2.instance.sha256


def test_pixel_hash_present(reader, tmp_dir):
    from tests.conftest import create_normal_series

    files, _, _ = create_normal_series(tmp_dir, num_slices=1, pixel_value=1500)
    result = reader.read_file(files[0])
    assert result.success is True
    assert result.instance.pixel_hash is not None
    assert result.instance.pixel_shape == (64, 64)
