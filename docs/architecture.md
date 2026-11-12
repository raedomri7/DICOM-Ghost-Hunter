# DICOM Ghost Hunter — Professional Software Architecture

## 1. System Architecture Diagram (Mermaid)

```mermaid
graph TD
    subgraph UI [Presentation Layer - PyQt5]
        DASH[Dashboard]
        PACSE[PACS Explorer]
        IMPORT[DICOM Import]
        BROWSER[Examination Browser]
        VIEWER[DICOM Viewer]
        PROC[Image Processing Lab]
        MPR[3D Reconstruction / MPR]
        QC[Quality Control Center]
        AI[AI Laboratory]
        MEAS[Measurements & Annotations]
        REP[Reports]
        HIST[Analysis History]
        PACSC[PACS Configuration]
        SET[Settings]
        WK[Background Workers - QThread/QRunnable]
    end

    subgraph SV [Application Services Layer]
        IS[Import Service]
        SMS[Study Management Service]
        PS[Processing Service]
        AS[Analysis Service]
        AIS[AI Service]
        RS[Reporting Service]
    end

    subgraph CORE [Medical Imaging Core]
        DP[DICOM Parser]
        GEOM[Geometry Engine]
        IP[Image Processing]
        REG[Registration]
        REC[Reconstruction]
        QCENG[Quality Control Engine]
    end

    subgraph PACS [PACS Integration Layer]
        ORTH[Orthanc REST Client]
        DNET[DICOM Networking - pynetdicom]
        DW[DICOMweb - QIDO/WADO/STOW]
    end

    subgraph DATA [Data Infrastructure]
        SQL[(SQLite / PostgreSQL)]
        DS[DICOM Storage - file system]
        CACHE[Image Cache]
        REPORTS[Reports Export]
    end

    subgraph AI [AI Infrastructure]
        PT[PyTorch]
        MON[MONAI]
        REGISTRY[Model Registry]
        SEG[Segmentation]
        ANOM[Anomaly Detection]
    end

    UI --> SV
    SV --> CORE
    SV --> PACS
    SV --> DATA
    SV --> AI
    CORE --> DATA
    PACS --> DATA
    AI --> DATA
    WK -.-> UI
    WK -.-> SV
```

## 2. Data-Flow Diagram (Mermaid)

```mermaid
flowchart TD
    A[User: Select DICOM folder / file] --> B[Import Service]
    B --> C[DICOM Parser - pydicom]
    C --> D[Validate Part 10 / transfer syntax]
    D --> E[Extract metadata + pixel refs]
    E --> F[Organize Patient → Study → Series → Instance]
    F --> G[Persist to SQLite - no pixel data]
    G --> H[Display in Examination Browser]

    H --> I[User selects series for QC]
    I --> J[Quality Control Engine]
    J --> K[Standardized findings INFO..CRITICAL]
    K --> L[Persist findings + Generate PDF]

    H --> M[User opens DICOM Viewer]
    M --> N[Load pixel array on demand]
    N --> O[Window/Level, zoom, pan, measurements]
    O --> P[Display + annotations]

    H --> Q[User runs Image Processing]
    Q --> R[Processing Lab - OpenCV/SimpleITK]
    R --> S[Derived image - separate from original]
    S --> T[Compare original vs processed]

    H --> U[User launches 3D Reconstruction]
    U --> V[Volume construction from DICOM geometry]
    V --> W[MPR: axial/coronal/sagittal]
    W --> X[3D volume rendering - VTK]

    H --> Y[User runs AI Laboratory]
    Y --> Z[PyTorch/MONAI inference]
    Z --> AA[Segmentation masks / heatmaps]
    AA --> BB[Research output - expert review required]

    QCC[User: PACS Configuration] --> CC[Connection Manager]
    CC --> DD[Orthanc REST / pynetdicom / DICOMweb]
    DD --> EE[Remote study listing / retrieval]
    EE --> FF[Import remote series as local DICOM]
    FF --> B
```

## 3. Database Entity Relationship Diagram (Mermaid)

```mermaid
erDiagram
    PATIENT ||--o{ STUDY : has
    STUDY ||--o{ SERIES : contains
    SERIES ||--o{ INSTANCE : includes
    ANALYSIS_SESSION ||--o{ QC_FINDING : produces
    ANALYSIS_SESSION ||--o{ PROCESSING_JOB : runs
    ANALYSIS_SESSION ||--o{ REPORT : generates
    STUDY ||--o{ QC_FINDING : linked_to
    SERIES ||--o{ QC_FINDING : linked_to
    INSTANCE ||--o{ QC_FINDING : linked_to
    PROCESSING_JOB ||--o{ PROCESSING_RESULT : produces
    AI_MODEL ||--o{ AI_INFERENCE : executed_by
    AI_INFERENCE ||--o{ SEGMENTATION_RESULT : produces
    MEASUREMENT ||--o{ ANNOTATION : groups
    PACS_CONNECTION ||--o{ SYNC_LOG : records

    PATIENT {
        string id PK
        string patient_id UK
        string birth_date
        string sex
        string anonymized_id
    }

    STUDY {
        string id PK
        string patient_id FK
        string study_instance_uid UK
        string modality
        date study_date
        string study_description
        string accession_number
        string source_type
        string source_reference
    }

    SERIES {
        string id PK
        string study_id FK
        string series_instance_uid UK
        string modality
        string series_description
        int series_number
        int instance_count
    }

    INSTANCE {
        string id PK
        string series_id FK
        string sop_instance_uid UK
        string file_path
        string sha256
        string pixel_hash
        int rows
        int columns
        float slice_thickness
        string transfer_syntax
    }

    ANALYSIS_SESSION {
        string id PK
        datetime started_at
        datetime completed_at
        string source_type
        string source_reference
        string status
        text configuration
        float duration_seconds
    }

    QC_FINDING {
        string id PK
        string session_id FK
        string study_id FK
        string series_id FK
        string instance_id FK
        string category
        string severity
        string title
        text description
        text recommendation
        float confidence
        string dicom_tags
        datetime created_at
    }

    PROCESSING_JOB {
        string id PK
        string session_id FK
        string input_instance_id FK
        string operation_type
        string parameters
        string status
        datetime started_at
        datetime completed_at
    }

    PROCESSING_RESULT {
        string id PK
        string job_id FK
        string output_file_path
        text metrics
    }

    AI_MODEL {
        string id PK
        string name
        string version
        string modality
        string framework
        string input_dimensions
        string output_interpretation
        string file_path
    }

    AI_INFERENCE {
        string id PK
        string model_id FK
        string input_instance_id FK
        string status
        text output
        float confidence
        datetime created_at
    }

    SEGMENTATION_RESULT {
        string id PK
        string inference_id FK
        string mask_file_path
        float dice_coefficient
        float iou
        float volume_mm3
    }

    MEASUREMENT {
        string id PK
        string instance_id FK
        string type
        float value
        string unit
        text coordinates
    }

    ANNOTATION {
        string id PK
        string measurement_id FK
        string label
        text coordinates
    }

    REPORT {
        string id PK
        string session_id FK
        string file_reference
        string report_type
        datetime generated_at
    }

    PACS_CONNECTION {
        string id PK
        string name
        string host
        string port
        string auth_type
        boolean is_configured
    }

    SYNC_LOG {
        string id PK
        string connection_id FK
        string operation
        string status
        datetime timestamp
    }

    APPLICATION_SETTINGS {
        string key PK
        string value
        string section
    }

    AUDIT_LOGS {
        string id PK
        string user_id
        string action
        string target
        datetime timestamp
        string details
    }
```

## 4. Module Dependency Diagram (Mermaid)

```mermaid
graph TD
    UI[PyQt5 UI] --> SV[Application Services]
    SV --> IS[Import Service]
    SV --> SMS[Study Management]
    SV --> PS[Processing Service]
    SV --> AS[Analysis Service]
    SV --> AIS[AI Service]
    SV --> RS[Reporting Service]

    IS --> DP[DICOM Parser]
    IS --> DS[DICOM Storage]

    SMS --> DB[(SQLite/PostgreSQL)]

    PS --> IP[Image Processing - OpenCV/SciPy]
    PS --> REG[Registration - SimpleITK]

    AS --> QCENG[QC Engine]
    AS --> GEOM[Geometry Engine]

    AIS --> PT[PyTorch]
    AIS --> MON[MONAI]

    RS --> RPT[ReportLab]

    UI --> VIEWER[DICOM Viewer - matplotlib/PyQtGraph]
    VIEWER --> GEOM

    UI --> MPR3D[3D Reconstruction - VTK]
    MPR3D --> GEOM

    SV --> PACSM[PACS Connection Manager]
    PACSM --> ORTH[Orthanc REST]
    PACSM --> DNET[pynetdicom]
    PACSM --> DW[DICOMweb]

    DB --> MIG[Migrations]
```

## 5. Selected Libraries and Roles

| Library | Role | Justification |
|---------|------|---------------|
| Python 3.12 | Main language | Target environment, type hints, performance |
| PyQt5 | Desktop UI | Professional desktop, mature, Windows-compatible |
| pydicom | DICOM parsing | Reference DICOM library, Part 10 support |
| pynetdicom | DICOM networking | C-STORE, C-FIND, C-MOVE, C-GET |
| requests/httpx | Orthanc REST API | HTTP client for Orthanc |
| NumPy | Numerical processing | Array operations, pixel manipulation |
| OpenCV | Image processing | Filters, morphology, edge detection |
| SciPy | Scientific computing | Signal processing, interpolation |
| SimpleITK | Medical image processing | Registration, resampling, medical I/O |
| VTK | 3D visualization | Volume rendering, MPR, surface extraction |
| matplotlib | 2D visualization | Embedded in PyQt5, viewer backend |
| PyQtGraph | Alternative visualization | High-performance interactive plots |
| SQLAlchemy | ORM | SQLite now, PostgreSQL migration path |
| SQLite | Local database | Zero-config, file-based, Windows-compatible |
| ReportLab | PDF generation | Professional reports |
| PyYAML | Configuration | Human-readable YAML config |
| pytest | Testing | Unit and integration tests |
| Ruff | Code quality | Fast linting and formatting |
| Python logging | Logging | Structured, production-ready |
| PyTorch | Deep learning | AI segmentation / anomaly detection |
| MONAI | Medical AI | Medical imaging AI frameworks |
| PyInstaller | Packaging | Windows executable distribution |

## 6. Technical Feasibility Evaluation

| Component | Feasibility | Notes |
|-----------|-------------|-------|
| DICOM import & parsing | High | pydicom is mature and well-tested |
| Local SQLite database | High | SQLAlchemy + SQLite is straightforward |
| PyQt5 desktop UI | High | Mature, Windows-compatible, used in medical software |
| DICOM viewer (2D) | High | matplotlib + PyQt5 works well |
| Window/Level, zoom, pan | High | Standard matplotlib interactions |
| Measurements (distance, angle, ROI) | Medium | Requires PixelSpacing calibration |
| Orthanc REST integration | High | Well-documented REST API |
| pynetdicom C-STORE/C-FIND | Medium | Requires network configuration, AE titles |
| DICOMweb | Medium | Depends on Orthanc DICOMweb plugin |
| Image processing (filters, morphology) | High | OpenCV + SciPy are robust |
| Image registration | Medium | SimpleITK is good but complex to configure |
| MPR / 3D reconstruction | Medium | VTK has steep learning curve; geometry math required |
| 3D volume rendering | Medium | VTK + PyQt5 integration is non-trivial |
| PyTorch / MONAI AI | Medium | Large dependencies, GPU optional, CPU fallback |
| PDF reporting | High | ReportLab is reliable |
| Synthetic DICOM generation | High | pydicom can create test files |

## 7. Realistic MVP Definition

The MVP (Phase 1-3) must be runnable and tested:

1. **Foundation**: PyQt5 shell, dashboard, navigation, logging, configuration, SQLite initialization, theme system.
2. **DICOM Import**: Single file and folder import, validation, duplicate detection (SHA-256 + pixel hash).
3. **Database**: Patient → Study → Series → Instance hierarchy, no pixel data in DB.
4. **DICOM Viewer**: Axial view, slice navigation, Window/Level, zoom, pan, metadata overlay.
5. **Quality Control**: Metadata validation, duplicate detection, slice continuity, orientation, geometry, privacy inspection.
6. **PACS**: Orthanc REST connection, test, study/series listing (optional, Workflow B).
7. **Reporting**: PDF QC report via ReportLab.
8. **Testing**: 25+ unit tests, synthetic DICOM generator, ruff clean.

**Out of MVP**: AI laboratory, 3D volume rendering, image processing lab, measurements, PostgreSQL, DICOM networking (C-STORE/C-FIND), DICOMweb.

## 8. Detailed Development Roadmap

| Phase | Modules | Deliverables |
|-------|---------|--------------|
| 1 | Foundation | PyQt5 shell, dashboard, navigation, logging, config, SQLite, theme |
| 2 | DICOM & PACS core | Import, parser, organization, metadata, browser, Orthanc REST |
| 3 | DICOM Viewer | 2D visualization, navigation, Window/Level, measurements, metadata |
| 4 | Image Processing Lab | Filters, denoising, enhancement, edge detection, morphology, frequency |
| 5 | 3D Reconstruction | Volume construction, MPR, volume rendering, surface extraction |
| 6 | Quality Control | Full QC engine, SNR/CNR, privacy, integrity |
| 7 | AI Laboratory | PyTorch/MONAI, model registry, segmentation, anomaly detection |
| 8 | Reporting & Management | PDF/CSV/JSON export, history, audit logs, backup |
| 9 | Testing & Optimization | Validation, performance, packaging, documentation |

## 9. Technical Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VTK/PyQt5 integration instability | High | Isolate 3D in separate widget; provide fallback to 2D MPR |
| Large DICOM memory usage | High | Load pixels on demand; cache only active slices; never load full volume into RAM |
| pynetdicom network complexity | Medium | Make PACS networking optional; REST-first via Orthanc |
| PyTorch/MONAI large install | Medium | Optional dependency group; CPU-only models for MVP |
| Universal QC thresholds invalid | High | Configurable thresholds per modality/protocol; no hardcoded clinical limits |
| Incorrect geometry reconstruction | High | Use ImageOrientationPatient + ImagePositionPatient; test with synthetic oblique data |
| GUI freezing during import/analysis | High | All heavy work in QThread/QRunnable workers with progress + cancellation |
| Patient data in logs | High | De-identified logging; never log PatientName/PatientID |
| Windows dependency conflicts | Medium | Loose version pins; test in clean venv |

## 10. TCIA and Synthetic DICOM Data Strategy

- **TCIA**: Use public CT/MRI collections (e.g., NSCLC, LiTS, or similar) for real-data validation. Respect TCIA data use agreements; never modify original datasets.
- **Synthetic DICOM**: Generate with pydicom in `tests/synthetic_dicom/` for known conditions: normal series, duplicates, missing metadata, invalid UIDs, irregular spacing, inconsistent orientation, corrupted files, different dimensions.
- Never modify original research datasets to create test anomalies.

## 11. Orthanc Integration Strategy

- **Mode A (Standalone)**: Local import only; Orthanc not required.
- **Mode B (PACS)**: Orthanc REST API via `requests`/`httpx`; connection test, study/series/instance listing, download instances for local analysis.
- **Future**: pynetdicom C-STORE/C-FIND/C-MOVE/C-GET; DICOMweb QIDO-RS/WADO-RS/STOW-RS.
- Configuration via `.env` and `config/qc_rules.yaml`; no hard-coded credentials; timeouts and SSL verification supported.
