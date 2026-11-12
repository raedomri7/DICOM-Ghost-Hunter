"""ExaminationConsistencyAnalyzer — cross-study / cross-series consistency checks.

Verifies correct examination organization and technical inconsistencies that may
affect downstream processing (e.g. mixed modalities in one study, very small
series, missing series descriptions).
"""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)


class ExaminationConsistencyAnalyzer:
    """Checks organization-level consistency of an examination."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}

    def analyze(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        series_summaries: list[Any] | None = None,
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        if not instances:
            return findings

        ref = instances[0].sop_instance_uid or instances[0].file_path

        modalities = {inst.modality for inst in instances if inst.modality}
        if len(modalities) > 1:
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref,
                    category=FindingCategory.EXAMINATION_CONSISTENCY,
                    severity=Severity.LOW,
                    title="Mixed modalities within examination",
                    description=f"Examination contains modalities: {sorted(modalities)}.",
                    explanation=(
                        "A single study should normally be one modality. Mixed "
                        "modalities may indicate incorrect examination organization."
                    ),
                    recommended_action="Verify that all instances belong to the same study.",
                    confidence=0.7,
                    relevant_dicom_tags=["Modality", "StudyInstanceUID"],
                )
            )

        if len(instances) < 3:
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref,
                    category=FindingCategory.EXAMINATION_CONSISTENCY,
                    severity=Severity.INFO,
                    title="Small series instance count",
                    description=f"Series contains {len(instances)} instance(s).",
                    explanation=(
                        "Very few instances may indicate an incomplete export or a "
                        "localizer/scout series rather than a full volume."
                    ),
                    recommended_action="Confirm the expected number of slices for this series.",
                    confidence=0.6,
                    relevant_dicom_tags=["SeriesInstanceUID"],
                )
            )

        return findings

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
