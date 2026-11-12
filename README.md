# DICOM Ghost Hunter
# Intelligent DICOM Quality Control and Medical Imaging Analysis Platform

## Project Overview

DICOM Ghost Hunter is a professional desktop application for technical quality control of
DICOM medical imaging examinations. It helps biomedical engineers, radiology technicians,
medical physicists, and researchers identify potential technical problems before
examinations are used for visualization, reconstruction, research, or AI-based analysis.

## Features (MVP)

- Local DICOM folder import (Workflow A)
- DICOM Part 10 parsing with graceful handling of malformed files
- Study/series/instance organization
- Metadata validation (required/optional, UID format, pixel properties)
- Duplicate detection (file-level SHA-256, pixel-level normalized hash, SOPInstanceUID)
- Slice continuity analysis (ImagePositionPatient projected onto slice normal)
- Orientation consistency analysis (direction cosines, orthogonality)
- Geometry validation (dimensions, BitsAllocated, PhotometricInterpretation)
- Image-quality metrics (objective descriptors, SNR/CNR placeholders)
- Privacy metadata inspection (identifying attribute detection)
- Standardized findings with severity (INFO..CRITICAL)
- SQLite persistence (SQLAlchemy, repository pattern)
- Professional PDF reports (ReportLab)
- PyQt5 desktop interface with background workers (non-blocking UI)

## Technology Stack

- Python 3.12
- PyQt5 (desktop UI)
- pydicom (DICOM parsing)
- NumPy / SciPy / OpenCV (numerical processing)
- SQLAlchemy + SQLite (persistence)
- ReportLab (PDF reports)
- PyYAML (configuration)
- pytest + ruff (testing and linting)

## Installation (Windows 11)

```powershell
# 1. Create and activate a virtual environment
py -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
py -m pip install -r requirements.txt

# 3. Configure (optional)
copy .env.example .env
# Edit .env and config/qc_rules.yaml as needed
```

## Running

```powershell
.venv\Scripts\Activate.ps1
py main.py
```

## Project Structure

```
dicom_ghost_hunter/
├── main.py
├── requirements.txt
├── README.md
├── .env.example
├── config/
│   ├── settings.py
│   └── qc_rules.yaml
├── app/
│   ├── core/           # exceptions, logging, application bootstrap
│   ├── domain/         # models, enums, findings
│   ├── dicom/          # reader, parser, metadata, organizer, geometry
│   ├── analysis/       # QC modules + pipeline
│   ├── database/       # connection, models, repositories, migrations
│   ├── services/       # import, analysis, report services
│   ├── reporting/      # PDF generator
│   ├── ui/             # PyQt5 windows, workers
│   ├── pacs/           # Orthanc client (future phase)
│   └── viewer/         # DICOM viewer (future phase)
├── tests/
├── data/               # samples, database, reports, logs
└── docs/               # architecture, database_schema, implementation_plan
```

## Medical Disclaimer

DICOM Ghost Hunter provides preliminary **technical** quality-control indicators only.
Severity levels represent technical priority, not clinical danger. No finding constitutes
a confirmed medical error or a clinical diagnosis. All results require human verification
by a qualified biomedical engineer, radiology technician, or medical physicist.

This application is not a medical device and is not certified for clinical use.

## License

Research and educational use. Respect dataset licenses and privacy conditions.
