# DICOM Ghost Hunter — Database Schema

## Normalized SQLite Schema (SQLAlchemy)

```
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
```

## Entity Details

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| PATIENT | id, patient_id, anonymized_id | No patient names in logs; anonymized research ID |
| STUDY | id, patient_id, study_instance_uid, modality, study_date | Indexed by study_instance_uid |
| SERIES | id, study_id, series_instance_uid, modality, instance_count | Indexed by series_instance_uid |
| INSTANCE | id, series_id, sop_instance_uid, file_path, sha256, pixel_hash | File path only, no pixel data |
| ANALYSIS_SESSION | id, started_at, status, configuration, duration_seconds | Analysis run tracking |
| QC_FINDING | id, session_id, category, severity, title, confidence | Standardized findings |
| PROCESSING_JOB | id, operation_type, status, parameters | Image processing job queue |
| PROCESSING_RESULT | id, job_id, output_file_path, metrics | Derived processing output |
| AI_MODEL | id, name, version, modality, file_path | Model registry |
| AI_INFERENCE | id, model_id, input_instance_id, confidence | AI execution log |
| SEGMENTATION_RESULT | id, inference_id, mask_file_path, dice_coefficient | Segmentation output |
| MEASUREMENT | id, instance_id, type, value, unit | Image measurements |
| ANNOTATION | id, measurement_id, label, coordinates | Image annotations |
| REPORT | id, session_id, file_reference, report_type, generated_at | PDF report references |
| PACS_CONNECTION | id, name, host, port, auth_type | PACS server profiles |
| SYNC_LOG | id, connection_id, operation, status, timestamp | PACS sync audit |
| APPLICATION_SETTINGS | key, value, section | App configuration |
| AUDIT_LOGS | id, user_id, action, target, timestamp, details | Security audit trail |

## Design Principles

- **No pixel data in SQLite**: Only file paths, hashes, and metadata are stored.
- **No patient names in logs**: PatientID stored minimally; PatientName never logged.
- **Foreign keys**: Enabled via SQLite PRAGMA foreign_keys=ON.
- **Indexes**: On UIDs, timestamps, category, severity for fast queries.
- **Migration path**: SQLAlchemy declarative base; Alembic reserved for PostgreSQL migration.

## Initialization

```powershell
py -c "from app.database import bootstrap_database; bootstrap_database()"
```
