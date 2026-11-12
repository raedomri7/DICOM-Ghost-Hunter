"""DICOM organizer: groups instances by study and series, computes study-level stats."""

from __future__ import annotations

from app.domain.models import DICOMInstance, ExaminationSummary, SeriesSummary


class DICOMOrganizer:
    """Organizes parsed DICOM instances into a hierarchy of studies and series."""

    def organize(self, instances: list[DICOMInstance]) -> list[ExaminationSummary]:
        """Group instances by StudyInstanceUID then SeriesInstanceUID."""
        by_study: dict[str, list[DICOMInstance]] = {}
        for inst in instances:
            key = inst.study_instance_uid or "__UNKNOWN_STUDY__"
            by_study.setdefault(key, []).append(inst)

        examinations: list[ExaminationSummary] = []
        for study_uid, study_instances in by_study.items():
            examinations.append(self._build_examination(study_uid, study_instances))
        return examinations

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
