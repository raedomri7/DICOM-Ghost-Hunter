"""Standardized quality-control finding structure.

A finding is the atomic output of every analysis module. Severity represents
technical priority, not clinical danger. Every finding is traceable to a
technical rule or algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QCFinding:
    """A single quality-control finding."""

    finding_id: str
    session_id: str | None = None
    examination_id: str | None = None
    series_id: str | None = None
    instance_reference: str | None = None
    category: str = ""
    severity: str = "INFO"
    title: str = ""
    description: str = ""
    explanation: str = ""
    recommended_action: str = ""
    confidence: float | None = None
    relevant_dicom_tags: list[str] = field(default_factory=list)
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the finding to a plain dictionary."""
        return {
            "finding_id": self.finding_id,
            "session_id": self.session_id,
            "examination_id": self.examination_id,
            "series_id": self.series_id,
            "instance_reference": self.instance_reference,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "relevant_dicom_tags": self.relevant_dicom_tags,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
