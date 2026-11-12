"""Analysis service: runs the QC pipeline and persists findings."""

from __future__ import annotations

import time
from typing import Any

from app.analysis.pipeline import QCPipeline
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """Runs the full QC pipeline over parsed examinations and persists findings."""

    def __init__(
        self,
        session_repo: Any,
        examination_repo: Any,
        series_repo: Any,
        finding_repo: Any,
    ) -> None:
        self.session_repo = session_repo
        self.examination_repo = examination_repo
        self.series_repo = series_repo
        self.finding_repo = finding_repo

    def analyze_series(
        self,
        session_id: str,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None = None,
        rules: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run QC modules for one series and persist findings.

        Returns module results and a flattened list of findings as dicts.
        """
        start = time.perf_counter()
        pipeline = QCPipeline(rules=rules)
        module_results = pipeline.run(
            session_id=session_id,
            examination_id=examination_id,
            series_id=series_id,
            instances=instances,
            modality=modality,
        )

        # Persist findings
        for result in module_results:
            for finding in result.findings:
                try:
                    self.finding_repo.add(finding)
                except Exception:
                    logger.exception("Failed to persist finding %s", finding.finding_id)

        duration = time.perf_counter() - start
        flat = [f.to_dict() for result in module_results for f in result.findings]

        return {
            "session_id": session_id,
            "examination_id": examination_id,
            "series_id": series_id,
            "modules": {
                result.module_name: {
                    "finding_count": len(result.findings),
                    "duration_ms": result.duration_ms,
                }
                for result in module_results
            },
            "total_findings": len(flat),
            "findings": flat,
            "duration_seconds": duration,
        }
