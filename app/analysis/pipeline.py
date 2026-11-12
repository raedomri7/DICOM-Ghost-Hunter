"""QC pipeline that orchestrates all analysis modules and produces standardized findings."""

from __future__ import annotations

from typing import Any

from app.analysis.duplicate_detector import DuplicateDetector
from app.analysis.examination_consistency_analyzer import ExaminationConsistencyAnalyzer
from app.analysis.geometry_validator import GeometryValidator
from app.analysis.image_quality import ImageQualityAnalyzer
from app.analysis.metadata_validator import MetadataValidator
from app.analysis.orientation_analyzer import OrientationAnalyzer
from app.analysis.privacy_checker import PrivacyMetadataChecker
from app.analysis.slice_analyzer import SliceContinuityAnalyzer
from app.core.logging_config import get_logger
from app.domain.findings import QCFinding

logger = get_logger(__name__)


class QCModuleResult:
    """Result from a single QC module."""

    def __init__(self, module_name: str, findings: list[QCFinding], duration_ms: float) -> None:
        self.module_name = module_name
        self.findings = findings
        self.duration_ms = duration_ms


class QCPipeline:
    """Runs the configured QC modules over a set of DICOM instances."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.metadata_validator = MetadataValidator(self.rules.get("metadata"))
        self.duplicate_detector = DuplicateDetector(self.rules.get("duplicate"))
        self.slice_analyzer = SliceContinuityAnalyzer(self.rules.get("slice_continuity"))
        self.orientation_analyzer = OrientationAnalyzer(self.rules.get("orientation"))
        self.geometry_validator = GeometryValidator(self.rules.get("geometry"))
        self.image_quality = ImageQualityAnalyzer(self.rules.get("image_quality"))
        self.privacy_checker = PrivacyMetadataChecker(self.rules.get("privacy"))
        self.consistency_analyzer = ExaminationConsistencyAnalyzer(self.rules.get("examination_consistency"))

    def run(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None = None,
        series_summaries: list[Any] | None = None,
    ) -> list[QCModuleResult]:
        """Execute all QC modules for one series and return per-module results."""
        results: list[QCModuleResult] = []
        modules = [
            ("MetadataValidator", lambda: self.metadata_validator.validate_series(
                session_id, examination_id, series_id, instances, modality
            )),
            ("DuplicateDetector", lambda: self.duplicate_detector.detect(
                session_id, examination_id, series_id, instances
            )),
            ("SliceContinuityAnalyzer", lambda: self.slice_analyzer.analyze(
                session_id, examination_id, series_id, instances, modality
            )),
            ("OrientationAnalyzer", lambda: self.orientation_analyzer.analyze(
                session_id, examination_id, series_id, instances
            )),
            ("GeometryValidator", lambda: self.geometry_validator.analyze(
                session_id, examination_id, series_id, instances
            )),
            ("ImageQualityAnalyzer", lambda: self.image_quality.analyze(
                session_id, examination_id, series_id, instances, modality
            )),
            ("PrivacyMetadataChecker", lambda: self.privacy_checker.check(
                session_id, examination_id, series_id, instances
            )),
            ("ExaminationConsistencyAnalyzer", lambda: self.consistency_analyzer.analyze(
                session_id, examination_id, series_id, instances, series_summaries
            )),
        ]

        for name, func in modules:
            import time

            start = time.perf_counter()
            try:
                findings = func()
            except Exception as exc:
                logger.exception("QC module %s failed", name)
                findings = []
                # Record a single finding noting the module failure
                from app.domain.enums import FindingCategory, Severity
                findings.append(
                    QCFinding(
                        finding_id=f"F-pipe-{name}",
                        session_id=session_id,
                        examination_id=examination_id,
                        series_id=series_id,
                        category=FindingCategory.METADATA,
                        severity=Severity.INFO,
                        title=f"QC module {name} encountered an error",
                        description=str(exc),
                        explanation="The module failed during analysis; results may be incomplete.",
                        recommended_action="Review logs and re-run the analysis.",
                        confidence=0.0,
                    )
                )
            duration_ms = (time.perf_counter() - start) * 1000.0
            results.append(QCModuleResult(name, findings, duration_ms))
            logger.info("QC module %s produced %d findings in %.1f ms", name, len(findings), duration_ms)

        return results

    def run_all_findings(self, *args, **kwargs) -> list[QCFinding]:
        """Convenience: flatten all module findings into one list."""
        flat: list[QCFinding] = []
        for result in self.run(*args, **kwargs):
            flat.extend(result.findings)
        return flat
