"""GeometryValidator — validates image dimensions and pixel properties."""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)

MIN_DIMENSION = 16
MAX_DIMENSION = 4096
ALLOWED_BITS_ALLOCATED = {8, 16, 32}


class GeometryValidator:
    """Validates image geometry attributes across a series."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.min_dimension = self.rules.get("min_dimension", MIN_DIMENSION)
        self.max_dimension = self.rules.get("max_dimension", MAX_DIMENSION)
        self.allowed_bits = set(self.rules.get("bits_allocated_allowed", sorted(ALLOWED_BITS_ALLOCATED)))

    def analyze(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if not instances:
            return findings

        ref0 = instances[0].sop_instance_uid or instances[0].file_path
        dims: set[tuple[int | None, int | None]] = set()
        bits_values: set[int | None] = set()
        photometric: set[str | None] = set()

        for inst in instances:
            ref = inst.sop_instance_uid or inst.file_path
            dims.add((inst.rows, inst.columns))
            if inst.bits_allocated is not None:
                bits_values.add(inst.bits_allocated)
            if inst.photometric_interpretation:
                photometric.add(inst.photometric_interpretation)

            # Dimension bounds
            if inst.rows is not None and (inst.rows < self.min_dimension or inst.rows > self.max_dimension):
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.GEOMETRY,
                        severity=Severity.MEDIUM,
                        title="Rows out of expected range",
                        description=f"Instance {ref} reports Rows = {inst.rows}.",
                        explanation=(
                            f"Rows outside [{self.min_dimension}, {self.max_dimension}] may "
                            "indicate corrupted metadata or an unsupported image."
                        ),
                        recommended_action="Verify pixel dimensions and file integrity.",
                        confidence=0.75,
                        relevant_dicom_tags=["Rows"],
                    )
                )
            if inst.columns is not None and (inst.columns < self.min_dimension or inst.columns > self.max_dimension):
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.GEOMETRY,
                        severity=Severity.MEDIUM,
                        title="Columns out of expected range",
                        description=f"Instance {ref} reports Columns = {inst.columns}.",
                        explanation=(
                            f"Columns outside [{self.min_dimension}, {self.max_dimension}] may "
                            "indicate corrupted metadata or an unsupported image."
                        ),
                        recommended_action="Verify pixel dimensions and file integrity.",
                        confidence=0.75,
                        relevant_dicom_tags=["Columns"],
                    )
                )

        # Cross-instance dimension consistency
        if len(dims) > 1:
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.GEOMETRY,
                    severity=Severity.MEDIUM,
                    title="Inconsistent image dimensions within series",
                    description=f"Series contains different (Rows, Columns): {sorted(dims)}.",
                    explanation=(
                        "Inconsistent dimensions complicate volume assembly and display."
                    ),
                    recommended_action="Verify acquisition parameters and instance grouping.",
                    confidence=0.8,
                    relevant_dicom_tags=["Rows", "Columns"],
                )
            )

        # BitsAllocated check
        unknown_bits = bits_values - self.allowed_bits
        if unknown_bits:
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.GEOMETRY,
                    severity=Severity.LOW,
                    title="Unusual BitsAllocated values",
                    description=f"Series uses BitsAllocated values {sorted(unknown_bits)}.",
                    explanation=(
                        f"Typical values are {sorted(self.allowed_bits)}. Other values may "
                        "not be supported by all viewers."
                    ),
                    recommended_action="Confirm the transfer syntax and pixel representation are supported.",
                    confidence=0.7,
                    relevant_dicom_tags=["BitsAllocated"],
                )
            )

        # Photometric consistency
        if len(photometric) > 1:
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.GEOMETRY,
                    severity=Severity.LOW,
                    title="Inconsistent PhotometricInterpretation within series",
                    description=f"Series uses {sorted(photometric)}.",
                    explanation=("Mixed photometric interpretations may affect grayscale rendering."),
                    recommended_action="Confirm photometric interpretation is consistent across the series.",
                    confidence=0.6,
                    relevant_dicom_tags=["PhotometricInterpretation"],
                )
            )

        return findings

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
