"""DICOM file reader using pydicom.

Reads DICOM Part 10 files, validates readability, decodes pixel data when
supported, and computes a SHA-256 fingerprint plus a normalized pixel hash.
Malformed or unsupported files are reported gracefully without crashing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydicom import dcmread
from pydicom.errors import InvalidDicomError

from app.core.exceptions import (
    DICOMReadError,
    UnsupportedTransferSyntaxError,
)
from app.core.logging_config import get_logger
from app.domain.models import DICOMInstance

logger = get_logger(__name__)


@dataclass
class ReadResult:
    """Outcome of reading a single DICOM file."""

    file_path: str
    instance: DICOMInstance | None = None
    success: bool = False
    error: str | None = None


class DICOMReader:
    """Reads and parses individual DICOM files into DICOMInstance objects."""

    def __init__(self, force_decompress: bool = True) -> None:
        # defer_size=-1 means never defer data elements; pixel data is read
        # inline so pixel_array decoding works immediately.
        self.defer_size = -1

    def _is_dicom_part10(self, path: Path) -> bool:
        """Check the DICOM Part 10 preamble magic (DICM at byte offset 128)."""
        try:
            with path.open("rb") as handle:
                handle.seek(128)
                magic = handle.read(4)
            return magic == b"DICM"
        except OSError:
            return False

    def read_file(self, file_path: str | Path) -> ReadResult:
        """Read a single DICOM file.

        Args:
            file_path: Path to the DICOM file.

        Returns:
            A ReadResult containing the parsed instance or an error.
        """
        path = Path(file_path)
        instance = DICOMInstance(file_path=str(path))

        if not self._is_dicom_part10(path):
            msg = f"Not a valid DICOM Part 10 file (missing DICM preamble): {path}"
            logger.warning("%s", msg)
            instance.is_valid = False
            instance.read_error = msg
            return ReadResult(file_path=str(path), instance=instance, success=False, error=msg)

        try:
            dataset = dcmread(str(path), force=True, defer_size=self.defer_size)
        except InvalidDicomError:
            msg = f"Not a valid DICOM file: {path}"
            logger.warning("%s", msg)
            instance.is_valid = False
            instance.read_error = msg
            return ReadResult(file_path=str(path), instance=instance, success=False, error=msg)
        except Exception as exc:  # noqa: BLE001 - report any read failure gracefully
            msg = f"Failed to read DICOM file {path}: {exc}"
            logger.warning("%s", msg)
            instance.is_valid = False
            instance.read_error = msg
            return ReadResult(file_path=str(path), instance=instance, success=False, error=msg)

        try:
            instance = self._extract(dataset, path)
            instance.is_valid = True
            return ReadResult(file_path=str(path), instance=instance, success=True)
        except UnsupportedTransferSyntaxError as exc:
            instance.is_valid = False
            instance.read_error = str(exc)
            return ReadResult(file_path=str(path), instance=instance, success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            msg = f"Failed to parse DICOM dataset {path}: {exc}"
            logger.warning("%s", msg)
            instance.is_valid = False
            instance.read_error = msg
            return ReadResult(file_path=str(path), instance=instance, success=False, error=msg)

    def read_folder(self, folder_path: str | Path) -> list[ReadResult]:
        """Read every candidate DICOM file in a folder.

        Non-DICOM files are skipped gracefully. Directories are not recursed.
        """
        folder = Path(folder_path)
        results: list[ReadResult] = []
        if not folder.is_dir():
            raise DICOMReadError(f"Not a directory: {folder}")

        # Candidate extensions plus files without extension that may be DICOM.
        candidates = sorted(
            p for p in folder.iterdir()
            if p.is_file() and (p.suffix.lower() in {".dcm", ".dicom", ""} or not p.suffix)
        )
        for candidate in candidates:
            results.append(self.read_file(candidate))
        return results

    def _extract(self, dataset: Any, path: Path) -> DICOMInstance:
        """Extract metadata and pixel fingerprint from a pydicom dataset."""
        instance = DICOMInstance(file_path=str(path))

        def get(tag_name: str) -> Any:
            return getattr(dataset, tag_name, None)

        instance.sop_instance_uid = self._as_str(get("SOPInstanceUID"))
        instance.study_instance_uid = self._as_str(get("StudyInstanceUID"))
        instance.series_instance_uid = self._as_str(get("SeriesInstanceUID"))
        instance.modality = self._as_str(get("Modality"))
        instance.patient_id = self._as_str(get("PatientID"))
        instance.study_date = self._as_str(get("StudyDate"))
        instance.rows = self._as_int(get("Rows"))
        instance.columns = self._as_int(get("Columns"))
        instance.bits_allocated = self._as_int(get("BitsAllocated"))
        instance.bits_stored = self._as_int(get("BitsStored"))
        instance.photometric_interpretation = self._as_str(get("PhotometricInterpretation"))
        instance.samples_per_pixel = self._as_int(get("SamplesPerPixel"))
        instance.slice_thickness = self._as_float(get("SliceThickness"))
        instance.spacing_between_slices = self._as_float(get("SpacingBetweenSlices"))
        instance.rescale_slope = self._as_float(get("RescaleSlope"))
        instance.rescale_intercept = self._as_float(get("RescaleIntercept"))

        instance.pixel_spacing = self._as_float_list(get("PixelSpacing"))
        instance.image_position_patient = self._as_float_list(get("ImagePositionPatient"))
        instance.image_orientation_patient = self._as_float_list(get("ImageOrientationPatient"))

        # SHA-256 of the raw file bytes (file-level duplicate detection).
        instance.sha256 = self._sha256_file(path)

        # Pixel-level fingerprint (decoded pixel content).
        pixel_hash, pixel_shape = self._fingerprint_pixels(dataset)
        instance.pixel_hash = pixel_hash
        instance.pixel_shape = pixel_shape

        # Store a minimal, de-identified tag summary (no patient names).
        instance.raw_tags = {
            "Modality": instance.modality,
            "StudyInstanceUID": instance.study_instance_uid,
            "SeriesInstanceUID": instance.series_instance_uid,
            "SOPInstanceUID": instance.sop_instance_uid,
            "Rows": instance.rows,
            "Columns": instance.columns,
        }

        return instance

    @staticmethod
    def _as_str(value: Any) -> str | None:
        if value is None:
            return None
        try:
            return str(value).strip() or None
        except (ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float_list(value: Any) -> list[float] | None:
        if value is None:
            return None
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Compute SHA-256 fingerprint of a file's raw bytes."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1_048_576), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _fingerprint_pixels(dataset: Any) -> tuple[str | None, tuple[int, ...] | None]:
        """Decode pixel data and compute a stable normalized pixel hash.

        Returns (pixel_hash, pixel_shape) or (None, None) when pixels are
        unavailable or cannot be decoded.
        """
        try:
            if not hasattr(dataset, "PixelData"):
                return None, None
            if dataset.PixelData in (None, ""):
                return None, None

            # Decompress if necessary (pydicom handles common transfer syntaxes
            # when required decompression libraries are present).
            array = dataset.pixel_array  # may raise for unsupported syntax
            if array is None or array.size == 0:
                return None, None

            array = np.asarray(array)
            shape = tuple(int(x) for x in array.shape)

            # Normalize to a stable byte representation for hashing:
            # convert to float64, scale to [0,1] range per array to be robust
            # to rescale slope/intercept differences that do not change content.
            flat = array.astype(np.float64).ravel()
            if flat.size == 0:
                return None, None
            data_min = float(flat.min())
            data_max = float(flat.max())
            if data_max > data_min:
                normalized = (flat - data_min) / (data_max - data_min)
            else:
                normalized = flat
            quantized = (normalized * 255).astype(np.uint8)

            digest = hashlib.sha256(quantized.tobytes()).hexdigest()
            return digest, shape
        except Exception as exc:  # noqa: BLE001 - degradation is acceptable
            logger.debug("Pixel fingerprint unavailable for %s: %s", getattr(dataset, "SOPInstanceUID", "?"), exc)
            return None, None

    # ------------------------------------------------------------------ #
    # Pixel array loading (on demand, for the viewer)
    # ------------------------------------------------------------------ #
    @staticmethod
    def load_pixel_array(file_path: str | Path) -> np.ndarray | None:
        """Decode and return the pixel array for a DICOM file.

        Applies Rescale Slope/Intercept (modality transform, e.g. CT Hounsfield
        units) when present. Returns None if pixels cannot be decoded.
        """
        path = Path(file_path)
        try:
            dataset = dcmread(str(path), force=True, defer_size=-1)
        except Exception:  # noqa: BLE001
            return None

        if not hasattr(dataset, "PixelData") or dataset.PixelData in (None, ""):
            return None

        try:
            array = dataset.pixel_array
        except Exception:  # noqa: BLE001 - unsupported transfer syntax
            return None

        if array is None or array.size == 0:
            return None

        array = np.asarray(array)

        # Apply modality transform (Rescale Slope/Intercept) for CT etc.
        slope = DICOMReader._as_float(getattr(dataset, "RescaleSlope", None))
        intercept = DICOMReader._as_float(getattr(dataset, "RescaleIntercept", None))
        if slope is not None and intercept is not None and slope != 1.0:
            array = array.astype(np.float64) * slope + intercept

        return array
