"""DuplicateDetector — file-level, pixel-level, and metadata-based duplicate detection.

Classifies potential duplicates and explains the detection method. Identical pixel
content is not automatically treated as erroneous; two legitimate images can share
pixels. All results are reported as potential duplicates for human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging_config import get_logger
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)


@dataclass
class DuplicateGroup:
    """A group of potentially duplicate instances."""

    group_id: str
    method: str  # "file", "pixel", "metadata"
    instances: list[Any] = field(default_factory=list)
    confidence: float = 0.0


class DuplicateDetector:
    """Detects duplicates at three levels."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.enable_file_level = self.rules.get("enable_file_level", True)
        self.enable_pixel_level = self.rules.get("enable_pixel_level", True)
        self.enable_metadata_level = self.rules.get("enable_metadata_level", True)

    def detect(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        """Run all duplicate-detection methods on a list of instances."""
        findings: list[QCFinding] = []
        if len(instances) < 2:
            return findings

        if self.enable_file_level:
            findings.extend(self._file_level(session_id, examination_id, series_id, instances))
        if self.enable_pixel_level:
            findings.extend(self._pixel_level(session_id, examination_id, series_id, instances))
        if self.enable_metadata_level:
            findings.extend(self._metadata_level(session_id, examination_id, series_id, instances))
        return findings

    # --------------------------------------------------------------- #
    # File-level: SHA-256 of raw bytes
    # --------------------------------------------------------------- #
    def _file_level(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        by_hash: dict[str, list[Any]] = {}
        for inst in instances:
            if inst.sha256:
                by_hash.setdefault(inst.sha256, []).append(inst)

        for digest, group in by_hash.items():
            if len(group) < 2:
                continue
            refs = ", ".join(g.sop_instance_uid or g.file_path for g in group)
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=refs,
                    category=FindingCategory.DUPLICATE,
                    severity=Severity.MEDIUM,
                    title="Potential file-level duplicate (byte-identical)",
                    description=(
                        f"{len(group)} files are byte-identical (SHA-256 {digest[:16]}...): {refs}"
                    ),
                    explanation=(
                        "File-level duplicate detection compared SHA-256 fingerprints of "
                        "the raw file bytes. Byte-identical files contain the same DICOM "
                        "object, including pixel data and metadata."
                    ),
                    recommended_action=(
                        "Review whether these are intentional duplicates (e.g. repeated "
                        "exports) or an accidental copy. Remove or consolidate duplicates "
                        "before downstream analysis if they are not intended."
                    ),
                    confidence=0.95,
                    relevant_dicom_tags=["SOPInstanceUID"],
                    metadata={"method": "file_sha256", "digest": digest, "file_count": len(group)},
                )
            )
        return findings

    # --------------------------------------------------------------- #
    # Pixel-level: hash of normalized decoded pixel array
    # --------------------------------------------------------------- #
    def _pixel_level(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        by_hash: dict[str, list[Any]] = {}
        for inst in instances:
            if inst.pixel_hash:
                key = f"{inst.pixel_hash}|{inst.pixel_shape}"
                by_hash.setdefault(key, []).append(inst)

        for key, group in by_hash.items():
            if len(group) < 2:
                continue
            digest, shape = key.split("|", 1)
            refs = ", ".join(g.sop_instance_uid or g.file_path for g in group)
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=refs,
                    category=FindingCategory.DUPLICATE,
                    severity=Severity.LOW,
                    title="Potential pixel-level duplicate (identical decoded pixels)",
                    description=(
                        f"{len(group)} instances share identical decoded pixel content "
                        f"(shape {shape}): {refs}"
                    ),
                    explanation=(
                        "Pixel-level duplicate detection decoded each instance's pixel "
                        "array, normalized it to a stable representation, and compared "
                        "SHA-256 hashes. Identical decoded pixels can occur for two "
                        "legitimate images and do not by themselves indicate an error."
                    ),
                    recommended_action=(
                        "Compare the instances' metadata (acquisition parameters, "
                        "position, orientation) to determine whether the identical pixel "
                        "content is expected or represents an unintended duplicate."
                    ),
                    confidence=0.8,
                    relevant_dicom_tags=["SOPInstanceUID", "PixelData"],
                    metadata={"method": "pixel_sha256", "digest": digest[:16], "shape": shape, "instance_count": len(group)},
                )
            )
        return findings

    # --------------------------------------------------------------- #
    # Metadata-level: SOPInstanceUID equality
    # --------------------------------------------------------------- #
    def _metadata_level(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
    ) -> list[QCFinding]:
        findings: list[QCFinding] = []
        by_uid: dict[str, list[Any]] = {}
        for inst in instances:
            if inst.sop_instance_uid:
                by_uid.setdefault(inst.sop_instance_uid, []).append(inst)

        for uid, group in by_uid.items():
            if len(group) < 2:
                continue
            refs = ", ".join(g.sop_instance_uid or g.file_path for g in group)
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=refs,
                    category=FindingCategory.DUPLICATE,
                    severity=Severity.MEDIUM,
                    title="Potential metadata duplicate (SOPInstanceUID)",
                    description=(
                        f"{len(group)} instances share the same SOPInstanceUID ({uid}): {refs}"
                    ),
                    explanation=(
                        "SOPInstanceUID should uniquely identify a DICOM SOP Instance. "
                        "Repeated values suggest the same instance was imported multiple "
                        "times or UIDs were incorrectly regenerated."
                    ),
                    recommended_action=(
                        "Verify the provenance of these instances. Keep a single copy "
                        "per SOPInstanceUID unless the duplicates are intentional."
                    ),
                    confidence=0.85,
                    relevant_dicom_tags=["SOPInstanceUID"],
                    metadata={"method": "sop_instance_uid", "uid": uid, "instance_count": len(group)},
                )
            )
        return findings

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
