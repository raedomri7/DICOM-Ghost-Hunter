"""DICOM geometry utilities for slice continuity and orientation analysis.

Computes the slice normal from ImageOrientationPatient direction cosines,
projects ImagePositionPatient onto that normal, and orders slices by their
projected position. Supports oblique acquisitions (gantry tilt) and does not
rely solely on the Z coordinate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Tolerances for direction-cosine validation.
NORM_TOLERANCE = 0.01
ORTHOGONALITY_TOLERANCE = 0.01


@dataclass
class SliceGeometry:
    """Geometric description of a single DICOM slice."""

    instance: Any  # DICOMInstance
    image_position_patient: list[float] | None
    image_orientation_patient: list[float] | None
    slice_normal: list[float] | None
    projected_position: float | None
    orientation_valid: bool = False
    orientation_error: str | None = None


@dataclass
class SeriesGeometry:
    """Aggregated geometry for a DICOM series."""

    series_instance_uid: str
    slices: list[SliceGeometry] = None
    slice_normal: list[float] | None = None
    spacing_estimate: float | None = None
    spacing_metadata: float | None = None
    orientation_consistent: bool = False
    orientation_errors: list[str] = None

    def __post_init__(self) -> None:
        if self.slices is None:
            self.slices = []
        if self.orientation_errors is None:
            self.orientation_errors = []


def direction_cosines(image_orientation_patient: list[float] | None) -> tuple[list[float], list[float]] | None:
    """Split ImageOrientationPatient into row and column direction cosines.

    IOP = [row_x, row_y, row_z, col_x, col_y, col_z].
    """
    if image_orientation_patient is None or len(image_orientation_patient) != 6:
        return None
    try:
        row = [float(v) for v in image_orientation_patient[0:3]]
        col = [float(v) for v in image_orientation_patient[3:6]]
        return row, col
    except (TypeError, ValueError):
        return None


def compute_slice_normal(row: list[float], col: list[float]) -> list[float] | None:
    """Compute the slice normal as the cross product of row and column cosines."""
    try:
        r = np.array(row, dtype=np.float64)
        c = np.array(col, dtype=np.float64)
        normal = np.cross(r, c)
        norm = float(np.linalg.norm(normal))
        if norm < 1e-6:
            return None
        return (normal / norm).tolist()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to compute slice normal: %s", exc)
        return None


def validate_orientation(row: list[float], col: list[float]) -> tuple[bool, str | None]:
    """Validate direction-cosine norms and orthogonality within tolerance.

    Returns (is_valid, error_message).
    """
    try:
        r = np.array(row, dtype=np.float64)
        c = np.array(col, dtype=np.float64)
        r_norm = float(np.linalg.norm(r))
        c_norm = float(np.linalg.norm(c))
        dot = float(np.dot(r, c))

        if abs(r_norm - 1.0) > NORM_TOLERANCE:
            return False, f"Row direction cosine norm {r_norm:.4f} deviates from 1.0"
        if abs(c_norm - 1.0) > NORM_TOLERANCE:
            return False, f"Column direction cosine norm {c_norm:.4f} deviates from 1.0"
        if abs(dot) > ORTHOGONALITY_TOLERANCE:
            return False, f"Row and column cosines not orthogonal (dot={dot:.4f})"
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"Orientation validation error: {exc}"


def project_position(position: list[float] | None, normal: list[float] | None) -> float | None:
    """Project ImagePositionPatient onto the slice normal.

    Returns the signed distance along the normal from the origin.
    """
    if position is None or normal is None or len(position) != 3 or len(normal) != 3:
        return None
    try:
        p = np.array(position, dtype=np.float64)
        n = np.array(normal, dtype=np.float64)
        return float(np.dot(p, n))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Projection failed: %s", exc)
        return None


def analyze_series_geometry(instances: list[Any]) -> SeriesGeometry:
    """Analyze geometry for a list of DICOM instances in one series.

    Computes slice normals, projects positions, estimates spacing, and checks
    orientation consistency.
    """
    series_uid = instances[0].series_instance_uid if instances else ""
    geometry = SeriesGeometry(series_instance_uid=series_uid)

    slice_normals: list[list[float]] = []
    for inst in instances:
        iop = inst.image_orientation_patient
        ipp = inst.image_position_patient
        row_col = direction_cosines(iop)
        normal = None
        orientation_valid = False
        orientation_error = None
        if row_col is not None:
            row, col = row_col
            orientation_valid, orientation_error = validate_orientation(row, col)
            normal = compute_slice_normal(row, col)
            if normal is not None:
                slice_normals.append(normal)

        projected = None
        if normal is not None and ipp is not None:
            projected = project_position(ipp, normal)

        geometry.slices.append(
            SliceGeometry(
                instance=inst,
                image_position_patient=ipp,
                image_orientation_patient=iop,
                slice_normal=normal,
                projected_position=projected,
                orientation_valid=orientation_valid,
                orientation_error=orientation_error,
            )
        )

    # Series-level normal: use the first valid normal as reference.
    valid_slices = [s for s in geometry.slices if s.slice_normal is not None]
    if valid_slices:
        geometry.slice_normal = valid_slices[0].slice_normal

    # Orientation consistency: compare normals across slices.
    if len(valid_slices) >= 2:
        reference = np.array(valid_slices[0].slice_normal, dtype=np.float64)
        consistent = True
        for sl in valid_slices[1:]:
            n = np.array(sl.slice_normal, dtype=np.float64)
            # Dot close to 1 or -1 means same/opposite normal orientation.
            dot = abs(float(np.dot(reference, n)))
            if dot < (1.0 - ORTHOGONALITY_TOLERANCE):
                consistent = False
                geometry.orientation_errors.append(
                    f"Slice normal mismatch at {sl.instance.sop_instance_uid}: dot={dot:.4f}"
                )
        geometry.orientation_consistent = consistent

    # Order slices by projected position.
    projectable = [s for s in geometry.slices if s.projected_position is not None]
    projectable.sort(key=lambda s: s.projected_position or 0.0)

    # Estimate spacing from consecutive projected positions (robust: median of gaps).
    if len(projectable) >= 2:
        positions = [s.projected_position for s in projectable]
        gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        gaps = [g for g in gaps if g != 0]
        if gaps:
            gaps_arr = np.array(gaps, dtype=np.float64)
            geometry.spacing_estimate = float(np.median(np.abs(gaps_arr)))

    # Spacing metadata from first instance with SliceThickness/SpacingBetweenSlices.
    for inst in instances:
        if inst.slice_thickness is not None:
            geometry.spacing_metadata = inst.slice_thickness
            break
        if inst.spacing_between_slices is not None:
            geometry.spacing_metadata = inst.spacing_between_slices
            break

    return geometry


def find_spatial_discontinuities(
    geometry: SeriesGeometry,
    max_gap_factor: float = 2.0,
) -> list[dict[str, Any]]:
    """Identify unusually large or irregular intervals between consecutive slices.

    Returns a list of discontinuity descriptors with estimated distance, expected
    spacing, and affected instance positions. Does not declare a missing slice;
    it flags a potential spatial discontinuity requiring verification.
    """
    projectable = [s for s in geometry.slices if s.projected_position is not None]
    projectable.sort(key=lambda s: s.projected_position or 0.0)

    discontinuities: list[dict[str, Any]] = []
    if len(projectable) < 2:
        return discontinuities

    positions = [s.projected_position for s in projectable]
    gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
    if not gaps:
        return discontinuities

    gaps_arr = np.array(gaps, dtype=np.float64)
    expected = float(np.median(np.abs(gaps_arr))) if gaps_arr.size else 0.0
    if expected <= 0:
        expected = geometry.spacing_metadata or 0.0

    for i, gap in enumerate(gaps):
        abs_gap = abs(gap)
        if expected > 0 and abs_gap > max_gap_factor * expected:
            discontinuities.append(
                {
                    "slice_index_before": i,
                    "slice_index_after": i + 1,
                    "instance_before": projectable[i].instance.sop_instance_uid,
                    "instance_after": projectable[i + 1].instance.sop_instance_uid,
                    "estimated_distance": abs_gap,
                    "expected_spacing": expected,
                    "gap_factor": abs_gap / expected if expected else None,
                    "position_before": positions[i],
                    "position_after": positions[i + 1],
                }
            )
    return discontinuities
