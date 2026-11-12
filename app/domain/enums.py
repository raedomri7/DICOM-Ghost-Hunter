"""Domain-level enumerations used across the application."""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Technical priority of a QC finding (NOT clinical danger)."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingCategory(str, Enum):
    """Category of a QC finding."""

    METADATA = "metadata"
    DUPLICATE = "duplicate"
    SLICE_CONTINUITY = "slice_continuity"
    ORIENTATION = "orientation"
    GEOMETRY = "geometry"
    PIXEL_DATA = "pixel_data"
    IMAGE_QUALITY = "image_quality"
    PRIVACY = "privacy"
    EXAMINATION_CONSISTENCY = "examination_consistency"


class SourceType(str, Enum):
    """Type of source for an analysis session."""

    LOCAL_FOLDER = "local_folder"
    ORTHANC = "orthanc"
    DICOMWEB = "dicomweb"


class SessionStatus(str, Enum):
    """Status of an analysis session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Modality(str, Enum):
    """Common DICOM modalities."""

    CT = "CT"
    MR = "MR"
    XRAY = "XR"
    NM = "NM"
    PT = "PT"
    US = "US"
    UNKNOWN = "UNKNOWN"
