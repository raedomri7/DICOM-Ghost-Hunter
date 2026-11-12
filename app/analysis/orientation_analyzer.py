"""OrientationAnalyzer — verifies ImageOrientationPatient consistency within a series.

Checks direction-cosine norms, orthogonality, orientation changes, and potentially
mixed image orientations. Accounts for numerical precision and valid acquisition
variation.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.core.logging_config import get_logger
from app.dicom.geometry import direction_cosines, validate_orientation
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)

NORM_TOLERANCE = 0.01
ORTHOGONALITY_TOLERANCE = 0.01


class OrientationAnalyzer:
    """Analyzes orientation consistency for a DICOM series."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.enabled = self.rules.get("enabled", True)
        self.orthogonality_tolerance = self.rules.get("orthogonality_tolerance", ORTHOGONALITY_TOLERANCE)
        self.norm_tolerance = self.rules.get("norm_tolerance", NORM_TOLERANCE)

    def analyze(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if not self.enabled or not instances:
            return findings

        reference_normal: np.ndarray | None = None
        reference_iop: list[float] | None = None
        inconsistent = False

        for inst in instances:
            ref = inst.sop_instance_uid or inst.file_path
            iop = inst.image_orientation_patient
            if iop is None:
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.ORIENTATION,
                        severity=Severity.MEDIUM,
                        title="Missing ImageOrientationPatient",
                        description=f"Instance {ref} has no ImageOrientationPatient.",
                        explanation=(
                            "Without orientation vectors, spatial positioning and slice "
                            "ordering cannot be verified."
                        ),
                        recommended_action=(
                            "Confirm whether ImageOrientationPatient should be present "
                            "for this modality and acquisition."
                        ),
                        confidence=0.9,
                        relevant_dicom_tags=["ImageOrientationPatient"],
                    )
                )
                continue

            row_col = direction_cosines(iop)
            if row_col is None:
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.ORIENTATION,
                        severity=Severity.MEDIUM,
                        title="Invalid ImageOrientationPatient format",
                        description=f"Instance {ref} has malformed ImageOrientationPatient: {iop}.",
                        explanation="ImageOrientationPatient must contain six values.",
                        recommended_action="Review the source DICOM file for orientation metadata.",
                        confidence=0.9,
                        relevant_dicom_tags=["ImageOrientationPatient"],
                    )
                )
                continue

            row, col = row_col
            valid, error = validate_orientation(row, col)
            if not valid:
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.ORIENTATION,
                        severity=Severity.MEDIUM,
                        title="Non-unit or non-orthogonal direction cosines",
                        description=error or "Orientation validation failed.",
                        explanation=(
                            "Row and column direction cosines should be unit vectors and "
                            "mutually orthogonal (within tolerance)."
                        ),
                        recommended_action=(
                            "Verify ImageOrientationPatient values in the source file."
                        ),
                        confidence=0.85,
                        relevant_dicom_tags=["ImageOrientationPatient"],
                    )
                )
                continue

            normal = np.cross(np.array(row, dtype=np.float64), np.array(col, dtype=np.float64))
            normal = normal / np.linalg.norm(normal)

            if reference_normal is None:
                reference_normal = normal
                reference_iop = iop
            else:
                dot = abs(float(np.dot(reference_normal, normal)))
                if dot < (1.0 - self.orthogonality_tolerance):
                    inconsistent = True
                    findings.append(
                        QCFinding(
                            finding_id=self._fid(),
                            session_id=session_id,
                            examination_id=examination_id,
                            series_id=series_id,
                            instance_reference=ref,
                            category=FindingCategory.ORIENTATION,
                            severity=Severity.MEDIUM,
                            title="Orientation change within series",
                            description=(
                                f"Instance {ref} has a different slice normal "
                                f"(dot={dot:.4f}) than the series reference."
                            ),
                            explanation=(
                                "Direction cosines changed between instances, which may "
                                "indicate gantry tilt variation, mixed acquisitions, or "
                                "incorrect series grouping."
                            ),
                            recommended_action=(
                                "Compare ImageOrientationPatient across the series and "
                                "confirm whether the variation is intended."
                            ),
                            confidence=0.75,
                            relevant_dicom_tags=["ImageOrientationPatient"],
                            metadata={"dot_product": dot, "reference_iop": reference_iop},
                        )
                    )

        if inconsistent and reference_iop is not None:
            ref0 = instances[0].sop_instance_uid or instances[0].file_path
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.ORIENTATION,
                    severity=Severity.MEDIUM,
                    title="Potentially mixed image orientations in series",
                    description=(
                        "Not all instances share a consistent ImageOrientationPatient."
                    ),
                    explanation=(
                        "Mixed orientations can corrupt volume reconstruction and "
                        "spatial measurements. Verify whether this reflects a legitimate "
                        "multi-orientation acquisition or a grouping error."
                    ),
                    recommended_action=(
                        "Review each instance's ImageOrientationPatient and re-group if "
                        "necessary before reconstruction."
                    ),
                    confidence=0.7,
                    relevant_dicom_tags=["ImageOrientationPatient"],
                )
            )

        return findings

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
