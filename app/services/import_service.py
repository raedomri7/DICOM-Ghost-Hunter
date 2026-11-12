"""Import service: coordinates local DICOM file/folder import and persistence."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.core.exceptions import DICOMReadError
from app.core.logging_config import get_logger
from app.dicom.parser import DICOMParser
from app.dicom.reader import DICOMReader

logger = get_logger(__name__)


class ImportService:
    """Imports local DICOM files or folders and persists examinations/series."""

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

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #
    def import_path(
        self,
        path: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Import a single DICOM file or a folder of DICOM files.

        Detects whether `path` is a file or directory and dispatches accordingly.
        """
        p = Path(path)
        if p.is_dir():
            return self.import_folder(path, session_id=session_id)
        if p.is_file():
            return self.import_file(path, session_id=session_id)
        raise DICOMReadError(f"Path does not exist: {path}")

    def import_file(
        self,
        file_path: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Read, parse, and persist a single DICOM file."""
        start = time.perf_counter()
        reader = DICOMReader()
        results = [reader.read_file(file_path)]

        parser = DICOMParser()
        parse_result = parser.parse(results)

        session = self.session_repo.create(
            session_id=session_id,
            source_type="local_file",
            source_reference=file_path,
        )

        for examination in parse_result.examinations:
            exam_obj = self.examination_repo.create(
                session_id=session.id,
                study_instance_uid=examination.study_instance_uid,
                modality=examination.modality,
                study_date=examination.study_date,
                study_description=examination.description,
                series_count=examination.series_count,
                instance_count=examination.instance_count,
                source_path=examination.source_path,
            )
            for series in examination.series:
                self.series_repo.create(
                    examination_id=exam_obj.id,
                    series_instance_uid=series.series_instance_uid,
                    modality=series.modality,
                    description=series.description,
                    instance_count=series.instance_count,
                )

        duration = time.perf_counter() - start
        self.session_repo.mark_completed(session.id, duration_seconds=duration)

        return {
            "session_id": session.id,
            "status": "completed",
            "total_files": parse_result.total_files,
            "valid_instances": len(parse_result.valid_instances),
            "invalid_instances": len(parse_result.invalid_instances),
            "examinations": len(parse_result.examinations),
            "read_errors": parse_result.read_errors,
            "duration_seconds": duration,
            "valid_instances_list": parse_result.valid_instances,
            "examinations_list": parse_result.examinations,
        }

    def import_folder(
        self,
        folder_path: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Read, parse, and persist all DICOM instances in a folder."""
        start = time.perf_counter()
        reader = DICOMReader()
        try:
            results = reader.read_folder(folder_path)
        except DICOMReadError as exc:
            logger.error("Import failed: %s", exc)
            raise

        parser = DICOMParser()
        parse_result = parser.parse(results)

        session = self.session_repo.create(
            session_id=session_id,
            source_type="local_folder",
            source_reference=folder_path,
        )

        for examination in parse_result.examinations:
            exam_obj = self.examination_repo.create(
                session_id=session.id,
                study_instance_uid=examination.study_instance_uid,
                modality=examination.modality,
                study_date=examination.study_date,
                study_description=examination.description,
                series_count=examination.series_count,
                instance_count=examination.instance_count,
                source_path=examination.source_path,
            )
            for series in examination.series:
                self.series_repo.create(
                    examination_id=exam_obj.id,
                    series_instance_uid=series.series_instance_uid,
                    modality=series.modality,
                    description=series.description,
                    instance_count=series.instance_count,
                )

        duration = time.perf_counter() - start
        self.session_repo.mark_completed(session.id, duration_seconds=duration)

        return {
            "session_id": session.id,
            "status": "completed",
            "total_files": parse_result.total_files,
            "valid_instances": len(parse_result.valid_instances),
            "invalid_instances": len(parse_result.invalid_instances),
            "examinations": len(parse_result.examinations),
            "read_errors": parse_result.read_errors,
            "duration_seconds": duration,
            "valid_instances_list": parse_result.valid_instances,
            "examinations_list": parse_result.examinations,
        }
