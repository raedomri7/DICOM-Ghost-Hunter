"""Shared fixtures and synthetic DICOM generator for the test suite.

Synthetic DICOM files are generated in-memory / temp dir using pydicom. They are
used to test known conditions without touching real research datasets.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from pydicom import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    generate_uid,
)

from app.dicom.reader import DICOMReader


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def reader():
    return DICOMReader()


def build_file_meta() -> FileMetaDataset:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    return file_meta


def make_dataset(
    *,
    sop_instance_uid=None,
    study_instance_uid=None,
    series_instance_uid=None,
    modality="CT",
    patient_id="PAT001",
    study_date="20240101",
    rows=64,
    columns=64,
    bits_allocated=16,
    bits_stored=16,
    photometric_interpretation="MONOCHROME2",
    samples_per_pixel=1,
    pixel_spacing=None,
    ipp=None,
    iop=None,
    slice_thickness=1.0,
    spacing_between_slices=1.0,
    rescale_slope=1.0,
    rescale_intercept=-1000.0,
    pixel_array=None,
    missing_tags=(),
    invalid_uid=False,
):
    """Build a pydicom Dataset with the given attributes."""
    ds = Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = sop_instance_uid or generate_uid()
    if invalid_uid:
        ds.SOPInstanceUID = "BAD.UID.FORMAT"
    ds.StudyInstanceUID = study_instance_uid or generate_uid()
    ds.SeriesInstanceUID = series_instance_uid or generate_uid()
    ds.Modality = modality
    ds.PatientID = patient_id
    ds.StudyDate = study_date
    ds.Rows = rows
    ds.Columns = columns
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = bits_stored
    ds.PixelRepresentation = 0  # unsigned integer
    ds.PhotometricInterpretation = photometric_interpretation
    ds.SamplesPerPixel = samples_per_pixel
    if pixel_spacing is not None:
        ds.PixelSpacing = pixel_spacing
    if ipp is not None:
        ds.ImagePositionPatient = ipp
    if iop is not None:
        ds.ImageOrientationPatient = iop
    ds.SliceThickness = slice_thickness
    ds.SpacingBetweenSlices = spacing_between_slices
    ds.RescaleSlope = rescale_slope
    ds.RescaleIntercept = rescale_intercept
    if pixel_array is not None:
        ds.PixelData = pixel_array.tobytes()

    # Apply missing tags
    for tag in missing_tags:
        if hasattr(ds, tag):
            delattr(ds, tag)

    return ds


def write_dicom_file(ds: Dataset, file_meta: FileMetaDataset, path: str | Path) -> None:
    """Write a Dataset to a DICOM Part 10 file."""
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fds = FileDataset(str(path), ds, file_meta=file_meta, preamble=b"\x00" * 128)
    fds.save_as(str(path), write_like_original=False)


def make_pixel_array(rows, columns, value=1000, dtype=np.uint16, seed=None):
    if seed is not None:
        rng = np.random.default_rng(seed)
        return rng.integers(0, 4095, size=(rows, columns), dtype=dtype)
    return np.full((rows, columns), value, dtype=dtype)


def create_normal_series(
    tmp_dir,
    num_slices=5,
    study_uid=None,
    series_uid=None,
    modality="CT",
    start_position=0.0,
    spacing=1.0,
    pixel_value=1000,
):
    """Create a normal CT-like series with evenly spaced slices."""
    file_meta = build_file_meta()
    study_uid = study_uid or generate_uid()
    series_uid = series_uid or generate_uid()
    files = []
    for i in range(num_slices):
        sop = generate_uid()
        iop = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ipp = [0.0, 0.0, start_position + i * spacing]
        ds = make_dataset(
            sop_instance_uid=sop,
            study_instance_uid=study_uid,
            series_instance_uid=series_uid,
            modality=modality,
            rows=64,
            columns=64,
            pixel_spacing=[0.5, 0.5],
            ipp=ipp,
            iop=iop,
            slice_thickness=spacing,
            spacing_between_slices=spacing,
            pixel_array=make_pixel_array(64, 64, pixel_value + i * 7, seed=i),
        )
        path = Path(tmp_dir) / f"slice_{i:03d}.dcm"
        write_dicom_file(ds, file_meta, path)
        files.append(str(path))
    return files, study_uid, series_uid


def create_irregular_series(tmp_dir, num_slices=4, study_uid=None, series_uid=None):
    """Create a series with one large gap (potential discontinuity)."""
    file_meta = build_file_meta()
    study_uid = study_uid or generate_uid()
    series_uid = series_uid or generate_uid()
    positions = [0.0, 1.0, 2.0, 10.0]  # big gap between slice 2 and 3
    files = []
    for i in range(num_slices):
        sop = generate_uid()
        iop = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ipp = [0.0, 0.0, positions[i]]
        ds = make_dataset(
            sop_instance_uid=sop,
            study_instance_uid=study_uid,
            series_instance_uid=series_uid,
            modality="CT",
            rows=64,
            columns=64,
            pixel_spacing=[0.5, 0.5],
            ipp=ipp,
            iop=iop,
            slice_thickness=1.0,
            spacing_between_slices=1.0,
            pixel_array=make_pixel_array(64, 64, 1000),
        )
        path = Path(tmp_dir) / f"irreg_{i:03d}.dcm"
        write_dicom_file(ds, file_meta, path)
        files.append(str(path))
    return files, study_uid, series_uid


def create_inconsistent_orientation_series(tmp_dir, num_slices=4, study_uid=None, series_uid=None):
    """Create a series where one slice has a different normal axis (sagittal)."""
    file_meta = build_file_meta()
    study_uid = study_uid or generate_uid()
    series_uid = series_uid or generate_uid()
    files = []
    for i in range(num_slices):
        sop = generate_uid()
        if i == 2:
            # Sagittal orientation: normal along Y axis instead of Z axis.
            iop = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        else:
            iop = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ipp = [0.0, 0.0, float(i)]
        ds = make_dataset(
            sop_instance_uid=sop,
            study_instance_uid=study_uid,
            series_instance_uid=series_uid,
            modality="CT",
            rows=64,
            columns=64,
            pixel_spacing=[0.5, 0.5],
            ipp=ipp,
            iop=iop,
            slice_thickness=1.0,
            spacing_between_slices=1.0,
            pixel_array=make_pixel_array(64, 64, 1000),
        )
        path = Path(tmp_dir) / f"orient_{i:03d}.dcm"
        write_dicom_file(ds, file_meta, path)
        files.append(str(path))
    return files, study_uid, series_uid


def create_duplicate_files(tmp_dir, num_copies=3, study_uid=None, series_uid=None):
    """Create byte-identical DICOM files."""
    files, study_uid, series_uid = create_normal_series(
        tmp_dir, num_slices=1, study_uid=study_uid, series_uid=series_uid
    )
    copies = []
    for i in range(num_copies):
        path = Path(tmp_dir) / f"dup_{i}.dcm"
        with open(files[0], "rb") as src:
            data = src.read()
        with open(path, "wb") as dst:
            dst.write(data)
        copies.append(str(path))
    return copies, study_uid, series_uid


def write_non_dicom_file(path: str | Path, content: bytes = b"not a dicom file") -> None:
    Path(path).write_bytes(content)


def instances_from_files(reader: DICOMReader, files: list[str]):
    results = []
    for f in files:
        result = reader.read_file(f)
        if result.success and result.instance:
            results.append(result.instance)
    return results


class DummySeriesRepo:
    """Minimal stand-in for repo wiring used by services in tests."""


class DummyFindingRepo:
    def __init__(self):
        self.added = []

    def add(self, finding):
        self.added.append(finding)
        return finding


class DummySessionRepo:
    def __init__(self):
        self.created = None

    def create(self, **kwargs):
        self.created = kwargs
        from types import SimpleNamespace
        return SimpleNamespace(id="sess-test-0001")

    def mark_completed(self, session_id, duration_seconds=None):
        pass


class DummyExamRepo:
    def create(self, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(id="exam-test-0001")


class DummyDb:
    class settings:
        qc_rules: ClassVar[dict] = {}
