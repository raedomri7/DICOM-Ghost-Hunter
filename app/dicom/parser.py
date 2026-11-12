"""DICOM parser: converts ReadResult instances into organized examination data."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging_config import get_logger
from app.domain.models import DICOMInstance, ExaminationSummary, SeriesSummary

logger = get_logger(__name__)


@dataclass
class ParseResult:
    """Outcome of parsing a collection of DICOM read results."""

    examinations: list[ExaminationSummary] = field(default_factory=list)
    valid_instances: list[DICOMInstance] = field(default_factory=list)
    invalid_instances: list[DICOMInstance] = field(default_factory=list)
    total_files: int = 0
    read_errors: list[str] = field(default_factory=list)


class DICOMParser:
    """Parses raw DICOM instances into study/series organization."""

    def parse(self, results) -> ParseResult:
        """Group read results into examinations and series.

        Args:
            results: Iterable of ReadResult objects.

        Returns:
            A ParseResult with examinations, valid/invalid instances, and errors.
        """
        parse_result = ParseResult()
        by_study: dict[str, list[DICOMInstance]] = {}

        for result in results:
            parse_result.total_files += 1
            if not result.success or result.instance is None:
                if result.error:
                    parse_result.read_errors.append(f"{result.file_path}: {result.error}")
                if result.instance is not None:
                    parse_result.invalid_instances.append(result.instance)
                continue

            instance = result.instance
            parse_result.valid_instances.append(instance)

            study_uid = instance.study_instance_uid
            if not study_uid:
                # Cannot organize without a StudyInstanceUID; group under unknown.
                study_uid = "__UNKNOWN_STUDY__"
            by_study.setdefault(study_uid, []).append(instance)

        for study_uid, instances in by_study.items():
            examination = self._build_examination(study_uid, instances)
            parse_result.examinations.append(examination)

        return parse_result

    def _build_examination(self, study_uid: str, instances: list[DICOMInstance]) -> ExaminationSummary:
        modalities = {inst.modality for inst in instances if inst.modality}
        study_dates = {inst.study_date for inst in instances if inst.study_date}
        patient_ids = {inst.patient_id for inst in instances if inst.patient_id}

        examination = ExaminationSummary(
            study_instance_uid=study_uid if study_uid != "__UNKNOWN_STUDY__" else None,
            modality=min(modalities) if modalities else None,
            study_date=min(study_dates) if study_dates else None,
            patient_id=min(patient_ids) if patient_ids else None,
            instance_count=len(instances),
            source_path=instances[0].file_path if instances else None,
        )

        by_series: dict[str, list[DICOMInstance]] = {}
        for inst in instances:
            series_uid = inst.series_instance_uid or "__UNKNOWN_SERIES__"
            by_series.setdefault(series_uid, []).append(inst)

        for series_uid, series_instances in by_series.items():
            series_modalities = {s.modality for s in series_instances if s.modality}
            series = SeriesSummary(
                series_instance_uid=series_uid if series_uid != "__UNKNOWN_SERIES__" else None,
                study_instance_uid=study_uid if study_uid != "__UNKNOWN_STUDY__" else None,
                modality=min(series_modalities) if series_modalities else None,
                instance_count=len(series_instances),
                instances=series_instances,
            )
            examination.series.append(series)
            examination.series_count += 1

        return examination
