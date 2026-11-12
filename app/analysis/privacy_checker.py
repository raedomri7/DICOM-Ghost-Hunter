"""PrivacyMetadataChecker — identifies selected potentially sensitive DICOM attributes.

Focuses on metadata inspection only. Does not perform DICOM de-identification and
does not detect burned-in information inside pixels. Results indicate which
identifying attributes are present so a human can decide how to handle them.
"""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)


class PrivacyMetadataChecker:
    """Inspects DICOM instances for potentially identifying metadata."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.identifying_tags = self.rules.get(
            "identifying_tags",
            [
                "PatientName",
                "PatientID",
                "PatientBirthDate",
                "InstitutionName",
                "InstitutionAddress",
                "ReferringPhysicianName",
                "PerformingPhysicianName",
                "OperatorsName",
                "PatientAddress",
                "PatientTelephoneNumbers",
                "PatientAge",
            ],
        )

    def check(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if not instances:
            return findings

        tag_values = {
            "PatientName": None,          # not stored in DICOMInstance (de-identified)
            "PatientID": instances[0].patient_id,
            "PatientBirthDate": None,
            "InstitutionName": None,
            "InstitutionAddress": None,
            "ReferringPhysicianName": None,
            "PerformingPhysicianName": None,
            "OperatorsName": None,
            "PatientAddress": None,
            "PatientTelephoneNumbers": None,
            "PatientAge": None,
        }

        # Only PatientID is reliably available in the de-identified model. Other
        # tags would be read from the raw dataset in a full implementation.
        for tag in self.identifying_tags:
            value = tag_values.get(tag)
            if value:
                ref = instances[0].sop_instance_uid or instances[0].file_path
                findings.append(
                    QCFinding(
                        finding_id=self._fid(),
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        instance_reference=ref,
                        category=FindingCategory.PRIVACY,
                        severity=Severity.LOW,
                        title=f"Identifying metadata present: {tag}",
                        description=(
                            f"The identifying attribute '{tag}' is present in this "
                            f"series (value redacted in logs)."
                        ),
                        explanation=(
                            "Metadata inspection detected identifying information. "
                            "This is not de-identification; it only reports presence."
                        ),
                        recommended_action=(
                            "Handle the dataset according to local privacy policy. "
                            "Apply a DICOM de-identification profile before sharing."
                        ),
                        confidence=0.9,
                        relevant_dicom_tags=[tag],
                        metadata={"tag": tag, "present": True},
                    )
                )

        # Note: this module does not guarantee anonymity and does not de-identify.
        return findings

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
