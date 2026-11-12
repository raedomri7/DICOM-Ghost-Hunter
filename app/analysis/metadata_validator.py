"""MetadataValidator — validates required and recommended DICOM metadata.

Checks:
1. Required attribute presence.
2. Missing-value detection.
3. Invalid/malformed UID detection.
4. Inconsistent metadata within a series.
5. Pixel-property validation.
6. Modality-specific validation rules.

Every finding distinguishes missing required vs missing optional attributes,
invalid values, and unusual-but-valid values. Absence of an optional attribute
is never classified as critical.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging_config import get_logger
from app.dicom.metadata import (
    MODALITY_SPECIFIC_TAGS,
    OPTIONAL_RECOMMENDED_TAGS,
    REQUIRED_TAGS,
)
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)

# Regex for a valid DICOM UID: digits and dots, no leading zero, no trailing dot.
UID_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def _make_finding_id() -> str:
    import uuid

    return f"F-{uuid.uuid4().hex[:12]}"


class MetadataValidator:
    """Validates DICOM metadata for a series of instances."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.required_tags = self.rules.get("required_tags", REQUIRED_TAGS)
        self.optional_tags = self.rules.get("optional_but_recommended_tags", OPTIONAL_RECOMMENDED_TAGS)
        self.modality_specific = self.rules.get("modality_specific", MODALITY_SPECIFIC_TAGS)

    def validate_series(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None = None,
    ) -> list[QCFinding]:
        """Run all metadata checks for one series.

        Returns a list of standardized QCFinding objects.
        """
        findings: list[QCFinding] = []
        if not instances:
            return findings

        modality = modality or instances[0].modality

        # Per-instance checks
        for inst in instances:
            findings.extend(self._check_instance(session_id, examination_id, series_id, inst))

        # Cross-instance consistency checks within the series
        findings.extend(
            self._check_series_consistency(session_id, examination_id, series_id, instances, modality)
        )

        # Modality-specific rules
        findings.extend(
            self._check_modality_specific(session_id, examination_id, series_id, instances, modality)
        )

        return findings

    # ------------------------------------------------------------------ #
    # Per-instance checks
    # ------------------------------------------------------------------ #
    def _check_instance(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        inst: Any,
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        ref = inst.sop_instance_uid or inst.file_path

        # Map tag keyword -> instance value
        tag_values = {
            "PatientID": inst.patient_id,
            "StudyInstanceUID": inst.study_instance_uid,
            "SeriesInstanceUID": inst.series_instance_uid,
            "SOPInstanceUID": inst.sop_instance_uid,
            "Modality": inst.modality,
            "StudyDate": inst.study_date,
            "StudyDescription": None,
            "SeriesDescription": None,
            "Rows": inst.rows,
            "Columns": inst.columns,
            "PixelSpacing": inst.pixel_spacing,
            "ImagePositionPatient": inst.image_position_patient,
            "ImageOrientationPatient": inst.image_orientation_patient,
            "SliceThickness": inst.slice_thickness,
            "SpacingBetweenSlices": inst.spacing_between_slices,
            "BitsAllocated": inst.bits_allocated,
            "BitsStored": inst.bits_stored,
            "PhotometricInterpretation": inst.photometric_interpretation,
            "SamplesPerPixel": inst.samples_per_pixel,
        }

        for keyword in self.required_tags:
            value = tag_values.get(keyword)
            if value is None or (isinstance(value, str) and value == ""):
                findings.append(
                    QCFinding(
                        finding_id=_make_finding_id(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.METADATA,
                        severity=Severity.HIGH,
                        title=f"Missing required attribute: {keyword}",
                        description=(
                            f"The required DICOM attribute '{keyword}' is absent or empty "
                            f"in instance {ref}."
                        ),
                        explanation=(
                            f"'{keyword}' is required for identifying and interpreting the "
                            f"instance. Its absence may prevent correct grouping, display, "
                            f"or downstream processing."
                        ),
                        recommended_action=(
                            f"Verify the source of instance {ref} and re-acquire or "
                            f"re-export with '{keyword}' populated."
                        ),
                        confidence=1.0,
                        relevant_dicom_tags=[keyword],
                    )
                )

        # UID validity for the UID-type required tags
        for keyword in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID"):
            value = tag_values.get(keyword)
            if value and not _is_valid_uid(value):
                findings.append(
                    QCFinding(
                        finding_id=_make_finding_id(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.METADATA,
                        severity=Severity.HIGH,
                        title=f"Invalid UID format: {keyword}",
                        description=(
                            f"The attribute '{keyword}' has value '{value}', which does not "
                            f"conform to the DICOM UID format (dot-separated digits, no "
                            f"leading zeros)."
                        ),
                        explanation=(
                            "Invalid UIDs can break study/series/instance grouping and "
                            "DICOM network references."
                        ),
                        recommended_action=(
                            f"Correct the '{keyword}' value in the source or regenerate "
                            f"valid UIDs before further processing."
                        ),
                        confidence=0.9,
                        relevant_dicom_tags=[keyword],
                    )
                )

        # Pixel-property validation
        if inst.rows is not None and inst.rows < 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref,
                    category=FindingCategory.METADATA,
                    severity=Severity.HIGH,
                    title="Invalid Rows value",
                    description=f"Instance {ref} reports Rows = {inst.rows}.",
                    explanation="Rows must be a positive integer describing image height.",
                    recommended_action="Verify pixel dimensions in the source file.",
                    confidence=0.9,
                    relevant_dicom_tags=["Rows"],
                )
            )
        if inst.columns is not None and inst.columns < 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref,
                    category=FindingCategory.METADATA,
                    severity=Severity.HIGH,
                    title="Invalid Columns value",
                    description=f"Instance {ref} reports Columns = {inst.columns}.",
                    explanation="Columns must be a positive integer describing image width.",
                    recommended_action="Verify pixel dimensions in the source file.",
                    confidence=0.9,
                    relevant_dicom_tags=["Columns"],
                )
            )
        if inst.bits_allocated not in (8, 16, 32) and inst.bits_allocated is not None:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref,
                    category=FindingCategory.METADATA,
                    severity=Severity.MEDIUM,
                    title="Unusual BitsAllocated value",
                    description=f"Instance {ref} reports BitsAllocated = {inst.bits_allocated}.",
                    explanation=(
                        "BitsAllocated of 8, 16, or 32 is typical. Other values may not "
                        "be supported by all viewers."
                    ),
                    recommended_action="Confirm the transfer syntax and pixel representation are supported.",
                    confidence=0.7,
                    relevant_dicom_tags=["BitsAllocated"],
                )
            )

        # Optional-but-recommended tags (INFO only when absent)
        for keyword in self.optional_tags:
            value = tag_values.get(keyword)
            if value is None or (isinstance(value, str) and value == ""):
                findings.append(
                    QCFinding(
                        finding_id=_make_finding_id(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.METADATA,
                        severity=Severity.INFO,
                        title=f"Missing optional attribute: {keyword}",
                        description=(
                            f"The recommended attribute '{keyword}' is absent in instance {ref}."
                        ),
                        explanation=(
                            f"'{keyword}' is not required but improves interpretation and "
                            f"quality-control context. Its absence is not an error."
                        ),
                        recommended_action=(
                            f"Consider populating '{keyword}' at acquisition time if "
                            f"relevant to the workflow."
                        ),
                        confidence=1.0,
                        relevant_dicom_tags=[keyword],
                    )
                )

        return findings

    # ------------------------------------------------------------------ #
    # Cross-instance consistency
    # ------------------------------------------------------------------ #
    def _check_series_consistency(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None,
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if len(instances) < 2:
            return findings

        ref0 = instances[0].sop_instance_uid or instances[0].file_path

        # Modality consistency
        modalities = {inst.modality for inst in instances if inst.modality}
        if len(modalities) > 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.METADATA,
                    severity=Severity.MEDIUM,
                    title="Inconsistent Modality within series",
                    description=(
                        f"Series contains instances with different modalities: "
                        f"{sorted(modalities)}."
                    ),
                    explanation=(
                        "A DICOM series should normally share a single modality. Mixed "
                        "modalities may indicate incorrect series grouping."
                    ),
                    recommended_action="Review series grouping and confirm each instance belongs to this series.",
                    confidence=0.8,
                    relevant_dicom_tags=["Modality"],
                )
            )

        # Rows/Columns consistency
        rows_vals = {inst.rows for inst in instances if inst.rows is not None}
        cols_vals = {inst.columns for inst in instances if inst.columns is not None}
        if len(rows_vals) > 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.METADATA,
                    severity=Severity.MEDIUM,
                    title="Inconsistent Rows within series",
                    description=f"Instances report different Rows values: {sorted(rows_vals)}.",
                    explanation=(
                        "Inconsistent image dimensions within a series may complicate "
                        "volume assembly and downstream processing."
                    ),
                    recommended_action="Verify acquisition parameters and instance grouping.",
                    confidence=0.8,
                    relevant_dicom_tags=["Rows"],
                )
            )
        if len(cols_vals) > 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.METADATA,
                    severity=Severity.MEDIUM,
                    title="Inconsistent Columns within series",
                    description=f"Instances report different Columns values: {sorted(cols_vals)}.",
                    explanation=(
                        "Inconsistent image dimensions within a series may complicate "
                        "volume assembly and downstream processing."
                    ),
                    recommended_action="Verify acquisition parameters and instance grouping.",
                    confidence=0.8,
                    relevant_dicom_tags=["Columns"],
                )
            )

        # StudyInstanceUID / SeriesInstanceUID consistency within the series
        study_uids = {inst.study_instance_uid for inst in instances if inst.study_instance_uid}
        series_uids = {inst.series_instance_uid for inst in instances if inst.series_instance_uid}
        if len(study_uids) > 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.METADATA,
                    severity=Severity.HIGH,
                    title="Inconsistent StudyInstanceUID within series",
                    description=(
                        f"Instances carry different StudyInstanceUID values: "
                        f"{sorted(study_uids)}."
                    ),
                    explanation="Instances in one series should belong to a single study.",
                    recommended_action="Review study/series grouping at the source.",
                    confidence=0.9,
                    relevant_dicom_tags=["StudyInstanceUID"],
                )
            )
        if len(series_uids) > 1:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.METADATA,
                    severity=Severity.HIGH,
                    title="Inconsistent SeriesInstanceUID within series",
                    description=(
                        f"Instances carry different SeriesInstanceUID values: "
                        f"{sorted(series_uids)}."
                    ),
                    explanation="Instances grouped as one series should share a SeriesInstanceUID.",
                    recommended_action="Review series grouping at the source.",
                    confidence=0.9,
                    relevant_dicom_tags=["SeriesInstanceUID"],
                )
            )

        return findings

    # ------------------------------------------------------------------ #
    # Modality-specific rules
    # ------------------------------------------------------------------ #
    def _check_modality_specific(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None,
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if not modality:
            return findings
        expected = self.modality_specific.get(modality, [])
        if not expected:
            return findings

        ref0 = instances[0].sop_instance_uid or instances[0].file_path
        missing = []
        for tag in expected:
            value = None
            if tag == "RescaleSlope":
                value = instances[0].rescale_slope
            elif tag == "RescaleIntercept":
                value = instances[0].rescale_intercept
            if value is None:
                missing.append(tag)

        if missing:
            findings.append(
                QCFinding(
                    finding_id=_make_finding_id(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.METADATA,
                    severity=Severity.LOW,
                    title=f"Missing modality-specific attributes for {modality}",
                    description=(
                        f"Modality {modality} typically includes {', '.join(missing)}, "
                        f"which were not found."
                    ),
                    explanation=(
                        f"These attributes support correct pixel-value interpretation for "
                        f"{modality} (e.g. CT Hounsfield units via rescale slope/intercept)."
                    ),
                    recommended_action=(
                        f"Confirm whether {', '.join(missing)} are required for the intended "
                        f"processing of {modality} images."
                    ),
                    confidence=0.6,
                    relevant_dicom_tags=missing,
                )
            )
        return findings


def _is_valid_uid(value: str) -> bool:
    """Return True if value looks like a valid DICOM UID."""
    if not value or not isinstance(value, str):
        return False
    return bool(UID_PATTERN.match(value)) and not value.startswith("0") and not value.endswith(".")
