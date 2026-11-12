"""Tests for PDF reporting."""

from __future__ import annotations

import os

from app.reporting.pdf_generator import PDFReportGenerator


def test_pdf_generation(tmp_path):
    generator = PDFReportGenerator()
    output = os.path.join(tmp_path, "report.pdf")
    session_info = {
        "session_id": "sess-1",
        "source_type": "local_folder",
        "source_reference": "/some/folder",
        "status": "completed",
        "generated_at": "2024-01-01",
    }
    examinations = [
        {
            "study_instance_uid": "1.2.3",
            "modality": "CT",
            "series_count": 2,
            "instance_count": 10,
            "source_path": "/some/folder",
        }
    ]
    findings = [
        {
            "finding_id": "f-1",
            "category": "metadata",
            "severity": "HIGH",
            "title": "Missing PatientID",
            "description": "PatientID is missing.",
            "recommended_action": "Re-export with PatientID.",
            "instance_reference": "1.2.3.4.5",
        },
        {
            "finding_id": "f-2",
            "category": "duplicate",
            "severity": "MEDIUM",
            "title": "Potential duplicate",
            "description": "Byte-identical files.",
            "recommended_action": "Review provenance.",
            "instance_reference": "1.2.3.4.6",
        },
    ]
    result = generator.generate_from_data(
        output_path=output,
        session_info=session_info,
        examinations=examinations,
        findings=findings,
    )
    assert os.path.exists(output)
    assert result["report_type"] == "pdf"
    assert result["total_findings"] == 2
