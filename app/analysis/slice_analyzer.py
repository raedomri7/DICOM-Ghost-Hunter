"""SliceContinuityAnalyzer — analyzes spatial organization of slices in CT/MR series.

Projects ImagePositionPatient onto the slice normal derived from
ImageOrientationPatient, orders slices, measures inter-slice distances, and flags
potential spatial discontinuities. Does not declare a missing slice; it reports
"Potential spatial discontinuity requiring verification."
"""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.dicom.geometry import analyze_series_geometry, find_spatial_discontinuities
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)


class SliceContinuityAnalyzer:
    """Analyzes slice continuity within a DICOM series."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.enabled = self.rules.get("enabled", True)
        self.modalities = self.rules.get("modalities", ["CT", "MR"])
        self.max_gap_factor = self.rules.get("max_gap_factor", 2.0)
        self.min_slices = self.rules.get("min_slices_for_analysis", 3)

    def analyze(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None = None,
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if not self.enabled or len(instances) < self.min_slices:
            return findings
        if modality and modality not in self.modalities:
            return findings

        geometry = analyze_series_geometry(instances)

        # Orientation validity findings within the series
        for sl in geometry.slices:
            if not sl.orientation_valid and sl.orientation_error:
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=sl.instance.sop_instance_uid or sl.instance.file_path,
                        category=FindingCategory.SLICE_CONTINUITY,
                        severity=Severity.MEDIUM,
                        title="Invalid slice orientation",
                        description=sl.orientation_error or "Direction-cosine validation failed.",
                        explanation=(
                            "ImageOrientationPatient direction cosines must be unit-norm "
                            "and mutually orthogonal. Invalid values compromise spatial "
                            "positioning and slice ordering."
                        ),
                        recommended_action=(
                            "Verify ImageOrientationPatient in the source and confirm "
                            "the acquisition geometry is supported."
                        ),
                        confidence=0.8,
                        relevant_dicom_tags=["ImageOrientationPatient"],
                    )
                )

        # Orientation consistency across slices
        if not geometry.orientation_consistent and geometry.orientation_errors:
            ref = instances[0].sop_instance_uid or instances[0].file_path
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref,
                    category=FindingCategory.SLICE_CONTINUITY,
                    severity=Severity.MEDIUM,
                    title="Inconsistent slice orientation across series",
                    description=(
                        "Slice normals differ across instances in this series, indicating "
                        "potentially mixed or non-parallel acquisitions."
                    ),
                    explanation=(
                        "All slices in a series should normally share the same slice "
                        "normal (within tolerance). Differing normals may indicate gantry "
                        "tilt changes, mixed protocols, or incorrect series grouping."
                    ),
                    recommended_action=(
                        "Review ImageOrientationPatient for each instance and confirm "
                        "whether the variation is acquisition-intended."
                    ),
                    confidence=0.75,
                    relevant_dicom_tags=["ImageOrientationPatient"],
                    metadata={"errors": geometry.orientation_errors[:5]},
                )
            )

        # Spatial discontinuities (gaps)
        discontinuities = find_spatial_discontinuities(geometry, max_gap_factor=self.max_gap_factor)
        for disc in discontinuities:
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=(
                        f"{disc['instance_before']} -> {disc['instance_after']}"
                    ),
                    category=FindingCategory.SLICE_CONTINUITY,
                    severity=Severity.HIGH,
                    title="Potential spatial discontinuity requiring verification",
                    description=(
                        f"Gap between slices {disc['slice_index_before']} and "
                        f"{disc['slice_index_after']} is {disc['estimated_distance']:.2f} mm "
                        f"(expected ~{disc['expected_spacing']:.2f} mm; "
                        f"{disc['gap_factor']:.1f}x expected)."
                    ),
                    explanation=(
                        "Consecutive slices were projected onto the slice normal and "
                        "ordered. An interval much larger than the typical spacing may "
                        "indicate a missing slice, a changed acquisition parameter, or "
                        "an out-of-order instance. This does not confirm a missing slice."
                    ),
                    recommended_action=(
                        "Compare the estimated distance with SliceThickness and "
                        "SpacingBetweenSlices metadata. Review the acquisition protocol "
                        "and consider re-acquiring or re-ordering instances."
                    ),
                    confidence=0.7,
                    relevant_dicom_tags=[
                        "ImagePositionPatient",
                        "ImageOrientationPatient",
                        "SliceThickness",
                        "SpacingBetweenSlices",
                    ],
                    metadata={
                        "estimated_distance_mm": disc["estimated_distance"],
                        "expected_spacing_mm": disc["expected_spacing"],
                        "gap_factor": disc["gap_factor"],
                    },
                )
            )

        # Spacing metadata cross-check
        if geometry.spacing_estimate and geometry.spacing_metadata and abs(
            geometry.spacing_estimate - geometry.spacing_metadata
        ) > max(0.5, 0.2 * geometry.spacing_metadata):
                ref = instances[0].sop_instance_uid or instances[0].file_path
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.SLICE_CONTINUITY,
                        severity=Severity.LOW,
                        title="Computed vs metadata spacing mismatch",
                        description=(
                            f"Computed inter-slice spacing {geometry.spacing_estimate:.2f} mm "
                            f"differs from metadata {geometry.spacing_metadata:.2f} mm."
                        ),
                        explanation=(
                            "Spacing derived from ImagePositionPatient projections does "
                            "not match the DICOM spacing metadata, suggesting possible "
                            "metadata inconsistency."
                        ),
                        recommended_action=(
                            "Verify SliceThickness and SpacingBetweenSlices against the "
                            "actual image geometry."
                        ),
                        confidence=0.65,
                        relevant_dicom_tags=["SliceThickness", "SpacingBetweenSlices"],
                    )
                )

        return findings

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
