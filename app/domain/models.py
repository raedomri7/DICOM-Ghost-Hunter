"""Core domain data models (persistence-independent)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DICOMInstance:
    """Represents a single DICOM instance with its file reference and key metadata."""

    file_path: str
    sop_instance_uid: str | None = None
    study_instance_uid: str | None = None
    series_instance_uid: str | None = None
    modality: str | None = None
    patient_id: str | None = None
    study_date: str | None = None
    rows: int | None = None
    columns: int | None = None
    pixel_spacing: list[float] | None = None
    image_position_patient: list[float] | None = None
    image_orientation_patient: list[float] | None = None
    slice_thickness: float | None = None
    spacing_between_slices: float | None = None
    bits_allocated: int | None = None
    bits_stored: int | None = None
    photometric_interpretation: str | None = None
    samples_per_pixel: int | None = None
    rescale_slope: float | None = None
    rescale_intercept: float | None = None
    sha256: str | None = None
    pixel_hash: str | None = None
    pixel_shape: tuple[int, ...] | None = None
    is_valid: bool = True
    read_error: str | None = None
    raw_tags: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeriesSummary:
    """Aggregated summary of a DICOM series."""

    series_instance_uid: str
    study_instance_uid: str
    modality: str | None = None
    description: str | None = None
    instance_count: int = 0
    instances: list[DICOMInstance] = field(default_factory=list)


@dataclass
class ExaminationSummary:
    """Aggregated summary of a DICOM examination (study)."""

    study_instance_uid: str
    modality: str | None = None
    study_date: str | None = None
    description: str | None = None
    patient_id: str | None = None
    series_count: int = 0
    instance_count: int = 0
    series: list[SeriesSummary] = field(default_factory=list)
    source_path: str | None = None
