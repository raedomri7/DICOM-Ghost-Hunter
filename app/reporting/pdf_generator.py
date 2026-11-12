"""PDF report generator using ReportLab.

Produces a professional, multi-page QC report with examination summary, findings
by category and severity, detailed findings, recommendations, and disclaimers.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.core.logging_config import get_logger

logger = get_logger(__name__)

DISCLAIMER = (
    "DICOM Ghost Hunter provides preliminary technical quality-control indicators only. "
    "Severity levels represent technical priority, not clinical danger. No finding "
    "constitutes a confirmed medical error or a clinical diagnosis. All results require "
    "human verification by a qualified biomedical engineer, radiology technician, or "
    "medical physicist. This application is not a medical device and is not certified "
    "for clinical use."
)

LIMITATIONS = (
    "Limitations: findings are heuristic and based on available DICOM metadata and pixel "
    "data. The application does not perform clinical diagnosis, does not guarantee "
    "anonymity (metadata inspection is not de-identification), and does not detect "
    "burned-in information inside image pixels. SNR/CNR estimates are technical "
    "indicators without universal thresholds. Results must be verified against the "
    "original acquisition protocol."
)


class PDFReportGenerator:
    """Generates a PDF QC report from in-memory analysis data."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        self.styles.add(
            ParagraphStyle(
                name="TitleMain",
                parent=self.styles["Title"],
                fontSize=20,
                spaceAfter=6,
                textColor=colors.HexColor("#1f3a5f"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Subtitle",
                parent=self.styles["Normal"],
                fontSize=11,
                textColor=colors.HexColor("#555555"),
                spaceAfter=14,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Section",
                parent=self.styles["Heading2"],
                fontSize=13,
                textColor=colors.HexColor("#1f3a5f"),
                spaceBefore=14,
                spaceAfter=6,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Small",
                parent=self.styles["Normal"],
                fontSize=8.5,
                leading=11,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Disclaimer",
                parent=self.styles["Normal"],
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#777777"),
            )
        )

    # ------------------------------------------------------------------ #
    def generate_from_data(
        self,
        output_path: str,
        session_info: dict[str, Any],
        examinations: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate a PDF report from in-memory data."""
        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        doc = BaseDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title="DICOM Ghost Hunter - QC Report",
            author="DICOM Ghost Hunter",
        )
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
        doc.addPageTemplates([PageTemplate(id="page", frames=[frame])])

        story = []
        self._header(story)
        self._info_block(story, session_info)
        self._examination_summary(story, examinations)
        self._findings_by_severity(story, findings)
        self._findings_by_category(story, findings)
        self._detailed_findings_table(story, findings)
        self._recommendations_section(story)
        self._disclaimer_section(story)

        doc.build(story)
        logger.info("PDF report written to %s", output_path)
        return {
            "file_reference": output_path,
            "report_type": "pdf",
            "total_findings": len(findings),
        }

    # ------------------------------------------------------------------ #
    def _header(self, story) -> None:
        story.append(Paragraph("DICOM Ghost Hunter", self.styles["TitleMain"]))
        story.append(Paragraph(
            "Technical Quality-Control Report — DICOM Medical Imaging Examination",
            self.styles["Subtitle"],
        ))
        story.append(Spacer(1, 4))

    def _info_block(self, story, session_info: dict[str, Any]) -> None:
        story.append(Paragraph("1. Analysis Identification", self.styles["Section"]))
        data = [
            ["Application", "DICOM Ghost Hunter"],
            ["Session ID", str(session_info.get("session_id", "-"))],
            ["Source type", str(session_info.get("source_type", "-"))],
            ["Source reference", str(session_info.get("source_reference", "-"))],
            ["Status", str(session_info.get("status", "-"))],
            ["Generated", str(session_info.get("generated_at", "-"))],
        ]
        table = Table(data, colWidths=[34 * mm, 130 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(Spacer(1, 6))

    def _examination_summary(self, story, examinations: list[dict[str, Any]]) -> None:
        story.append(Paragraph("2. Examination Summary", self.styles["Section"]))
        if not examinations:
            story.append(Paragraph("No examinations found.", self.styles["Normal"]))
            story.append(Spacer(1, 6))
            return
        data = [["Study Instance UID", "Modality", "Series", "Instances", "Source"]]
        for ex in examinations:
            data.append([
                str(ex.get("study_instance_uid", "-")),
                str(ex.get("modality", "-")),
                str(ex.get("series_count", 0)),
                str(ex.get("instance_count", 0)),
                str(ex.get("source_path", "-")),
            ])
        table = Table(data, colWidths=[55 * mm, 22 * mm, 16 * mm, 18 * mm, 53 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(Spacer(1, 6))

    def _findings_by_severity(self, story, findings: list[dict[str, Any]]) -> None:
        story.append(Paragraph("3. Findings by Severity", self.styles["Section"]))
        counts = Counter(f.get("severity", "INFO") for f in findings)
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        data = [["Severity", "Count"]]
        for sev in order:
            data.append([sev, str(counts.get(sev, 0))])
        data.append(["Total", str(len(findings))])
        table = Table(data, colWidths=[40 * mm, 20 * mm])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f7fa")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dbe5f0")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(Spacer(1, 6))

    def _findings_by_category(self, story, findings: list[dict[str, Any]]) -> None:
        story.append(Paragraph("4. Findings by Category", self.styles["Section"]))
        counts = Counter(f.get("category", "uncategorized") for f in findings)
        data = [["Category", "Count"]] + [[cat.title(), str(cnt)] for cat, cnt in sorted(counts.items())]
        data.append(["Total", str(len(findings))])
        table = Table(data, colWidths=[60 * mm, 20 * mm])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f7fa")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dbe5f0")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(Spacer(1, 6))

    def _detailed_findings_table(self, story, findings: list[dict[str, Any]]) -> None:
        story.append(Paragraph("5. Detailed Findings", self.styles["Section"]))
        if not findings:
            story.append(Paragraph("No QC findings were generated.", self.styles["Normal"]))
            story.append(Spacer(1, 6))
            return
        data = [["ID", "Category", "Severity", "Title", "Instance"]]
        for f in findings:
            data.append([
                str(f.get("finding_id", "-"))[:14],
                str(f.get("category", "-")).title(),
                str(f.get("severity", "-")),
                str(f.get("title", "-"))[:40],
                str(f.get("instance_reference", "-"))[:28],
            ])
        table = Table(data, colWidths=[18 * mm, 24 * mm, 18 * mm, 62 * mm, 42 * mm], repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        sev_colors = {
            "CRITICAL": colors.HexColor("#f8d7da"),
            "HIGH": colors.HexColor("#f5c6cb"),
            "MEDIUM": colors.HexColor("#ffeeba"),
            "LOW": colors.HexColor("#d1ecf1"),
            "INFO": colors.HexColor("#e2e3e5"),
        }
        for i, f in enumerate(findings, start=1):
            sev = str(f.get("severity", "INFO")).upper()
            if sev in sev_colors:
                style.append(("BACKGROUND", (0, i), (-1, i), sev_colors[sev]))
        table.setStyle(TableStyle(style))
        story.append(table)
        story.append(Spacer(1, 8))

        story.append(Paragraph("Finding Details", self.styles["Section"]))
        for f in findings[:15]:
            story.append(Paragraph(
                f"<b>{f.get('finding_id', '-')} — {f.get('title', '-')}</b>"
                f"<br/>Severity: {f.get('severity', '-')} | Category: {f.get('category', '-')}"
                f"<br/>{f.get('description', '-')}"
                f"<br/>Recommended action: {f.get('recommended_action', '-')}",
                self.styles["Small"],
            ))
            story.append(Spacer(1, 4))

    def _recommendations_section(self, story) -> None:
        story.append(Paragraph("6. Recommendations", self.styles["Section"]))
        recs = [
            "Review all CRITICAL and HIGH findings before using the images for visualization, reconstruction, research, or AI-based analysis.",
            "Confirm potential duplicates with the acquisition source; identical pixel data is not always erroneous.",
            "Treat flagged spatial discontinuities as 'potential spatial discontinuity requiring verification' — not as confirmed missing slices.",
            "Verify ImageOrientationPatient consistency across series before multiplanar reconstruction.",
            "Apply a DICOM de-identification profile before sharing any dataset containing identifying metadata.",
            "Establish modality- and protocol-specific reference values for SNR/CNR and other image-quality metrics.",
        ]
        for i, rec in enumerate(recs, 1):
            story.append(Paragraph(f"{i}. {rec}", self.styles["Normal"]))
            story.append(Spacer(1, 2))
        story.append(Spacer(1, 6))

    def _disclaimer_section(self, story) -> None:
        story.append(Paragraph("7. Limitations and Disclaimer", self.styles["Section"]))
        story.append(Paragraph(DISCLAIMER, self.styles["Disclaimer"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(LIMITATIONS, self.styles["Disclaimer"]))
