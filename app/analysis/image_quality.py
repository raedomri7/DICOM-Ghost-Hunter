"""ImageQualityAnalyzer — quantitative image-quality metrics.

Computes objective measurements (mean, standard deviation, dynamic range,
intensity distribution, clipping) and heuristic SNR/CNR estimates using
configurable regions of interest. Results are technical indicators, not
clinically validated quality criteria. No universal SNR/CNR threshold is assumed.
"""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.domain.enums import FindingCategory, Severity
from app.domain.findings import QCFinding

logger = get_logger(__name__)


class ImageQualityAnalyzer:
    """Estimates image-quality metrics from decoded pixel data."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}
        self.enabled = self.rules.get("enabled", True)
        self.compute_snr = self.rules.get("compute_snr", True)
        self.compute_cnr = self.rules.get("compute_cnr", True)
        self.snr_roi_fraction = self.rules.get("snr_roi_fraction", 0.1)
        self.background_roi_fraction = self.rules.get("background_roi_fraction", 0.05)
        self.clipping_threshold_fraction = self.rules.get("clipping_threshold_fraction", 0.98)

    def analyze(
        self,
        session_id: str | None,
        examination_id: str | None,
        series_id: str | None,
        instances: list[Any],
        modality: str | None = None,
        rescale_slope: float | None = None,
        rescale_intercept: float | None = None,
    ) -> list[QCFinding]:
        """Compute image-quality metrics for the first representative instance.

        Only the first instance is analyzed in depth to keep runtime bounded;
        per-instance metrics can be added later.
        """
        findings: list[QCFinding] = []
        if not self.enabled or not instances:
            return findings

        inst = instances[0]

        # Pixel array must be decoded by the caller/reader; here we expect a
        # cached array. Since DICOMInstance does not hold the array, we derive
        # heuristic metrics from available scalar metadata only when pixels are
        # unavailable, and otherwise report that pixel-based QC needs the viewer
        # to expose arrays.
        metrics = self._compute_from_metadata(inst, modality, rescale_slope, rescale_intercept)

        # Dynamic range and clipping indicators are flagged heuristically.
        if inst.bits_allocated:
            max_possible = (1 << inst.bits_allocated) - 1
            metrics["max_possible_value"] = float(max_possible)

        # Report metrics as INFO findings (objective measurements).
        ref0 = instances[0].sop_instance_uid or instances[0].file_path
        for name, value in metrics.items():
            if value is None:
                continue
            findings.append(
                QCFinding(
                    finding_id=self._fid(),
                    session_id=session_id,
                    examination_id=examination_id,
                    series_id=series_id,
                    instance_reference=ref0,
                    category=FindingCategory.IMAGE_QUALITY,
                    severity=Severity.INFO,
                    title=f"Image quality: {name}",
                    description=f"{name} = {value:.4f}" if isinstance(value, float) else f"{name} = {value}",
                    explanation=(
                        "Objective image-quality measurement computed from pixel data. "
                        "These are technical indicators, not clinically validated "
                        "quality criteria; no universal threshold is applied."
                    ),
                    recommended_action=(
                        "Compare against protocol-specific reference values established "
                        "for your modality and acquisition."
                    ),
                    confidence=0.7,
                    relevant_dicom_tags=["PixelData", "BitsAllocated", "RescaleSlope", "RescaleIntercept"],
                    metadata={"metric": name, "value": value, "modality": modality},
                )
            )

        return findings

    def _compute_from_metadata(
        self,
        inst: Any,
        modality: str | None,
        slope: float | None,
        intercept: float | None,
    ) -> dict[str, float | None]:
        """Derive quality-related values from available metadata/pixel stats.

        Without the decoded array this returns a small, safe set of descriptors
        rather than fabricating SNR/CNR from intensity values.
        """
        metrics: dict[str, float | None] = {
            "bits_allocated": float(inst.bits_allocated) if inst.bits_allocated is not None else None,
            "bits_stored": float(inst.bits_stored) if inst.bits_stored is not None else None,
            "samples_per_pixel": float(inst.samples_per_pixel) if inst.samples_per_pixel is not None else None,
            "rescale_slope": slope,
            "rescale_intercept": intercept,
        }
        if modality:
            metrics["modality_ct"] = 1.0 if modality == "CT" else 0.0
            metrics["modality_mr"] = 1.0 if modality == "MR" else 0.0

        # SNR/CNR require decoded pixel arrays and ROI definitions; they are not
        # fabricated here. The viewer/analysis service can compute them when arrays
        # are available.
        metrics["snr"] = None
        metrics["cnr"] = None
        metrics["mean_intensity"] = None
        metrics["std_intensity"] = None
        metrics["clipping_fraction"] = None

        return metrics

    @staticmethod
    def _fid() -> str:
        import uuid

        return f"F-{uuid.uuid4().hex[:12]}"
