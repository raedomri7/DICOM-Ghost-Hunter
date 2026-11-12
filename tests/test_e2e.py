"""End-to-end test: import -> analysis -> report (no GUI)."""

import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pydicom import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.database.connection import DatabaseConnection
from app.database.repositories import (
    AnalysisSessionRepository,
    ExaminationRepository,
    QCFindingRepository,
    ReportRepository,
    SeriesRepository,
)
from app.dicom.reader import DICOMReader
from app.services.analysis_service import AnalysisService
from app.services.import_service import ImportService
from app.services.report_service import ReportService


def make_series(tmp: Path, num_slices: int, study_uid: str, series_uid: str, prefix: str = "slice"):
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    files = []
    for i in range(num_slices):
        ds = Dataset()
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.Modality = "CT"
        ds.PatientID = "PAT001"
        ds.Rows = 64
        ds.Columns = 64
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.SamplesPerPixel = 1
        ds.PixelSpacing = [0.5, 0.5]
        ds.ImagePositionPatient = [0.0, 0.0, float(i)]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.SliceThickness = 1.0
        ds.SpacingBetweenSlices = 1.0
        ds.RescaleSlope = 1.0
        ds.RescaleIntercept = -1000.0
        arr = np.full((64, 64), 1000 + i * 10, dtype=np.uint16)
        ds.PixelData = arr.tobytes()
        file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        p = tmp / f"{prefix}_{i:03d}.dcm"
        fds = FileDataset(str(p), ds, file_meta=file_meta, preamble=b"\x00" * 128)
        fds.save_as(str(p), write_like_original=False)
        files.append(str(p))
    return files


def main() -> None:
    tmp = Path(tempfile.mkdtemp())

    study_uid = generate_uid()
    series_uid = generate_uid()
    files = make_series(tmp, 3, study_uid, series_uid)
    # Duplicate of slice 0
    dup = tmp / "dup_slice.dcm"
    shutil.copy(files[0], str(dup))
    files.append(str(dup))

    print(f"Created {len(files)} DICOM files in {tmp}")

    db = DatabaseConnection(f"sqlite:///{tmp / 'test.db'}")
    db.create_all()
    sess_repo = AnalysisSessionRepository(db)
    exam_repo = ExaminationRepository(db)
    ser_repo = SeriesRepository(db)
    find_repo = QCFindingRepository(db)
    rep_repo = ReportRepository(db)

    import_svc = ImportService(sess_repo, exam_repo, ser_repo, find_repo)
    result = import_svc.import_folder(str(tmp))
    print("Import:",
          {k: result[k] for k in ("session_id", "valid_instances", "invalid_instances", "examinations", "total_files")})
    print("Valid instances:")
    for inst in result["valid_instances_list"]:
        print("  - series", (inst.series_instance_uid or "")[:16],
              "sop", (inst.sop_instance_uid or "")[:16],
              "shape", inst.pixel_shape, "hash", (inst.pixel_hash or "")[:12])

    session_id = result["session_id"]
    analy_svc = AnalysisService(sess_repo, exam_repo, ser_repo, find_repo)
    by_series = defaultdict(list)
    for inst in result["valid_instances_list"]:
        by_series[inst.series_instance_uid or "__UNKNOWN__"].append(inst)

    for uid, insts in by_series.items():
        res = analy_svc.analyze_series(
            session_id=session_id,
            examination_id=None,
            series_id=uid,
            instances=insts,
            modality=insts[0].modality,
        )
        print(f"Series {uid[:16]}...: {res['total_findings']} findings, modules={list(res['modules'].keys())}")

    allf = find_repo.list_for_session(session_id)
    print("Total findings:", len(allf))
    print("By severity:", dict(Counter(f.severity for f in allf)))
    print("By category:", dict(Counter(f.category for f in allf)))
    for f in allf[:5]:
        print("  -", f.severity, f.category, "|", f.title, "|", f.instance_reference)

    rep_svc = ReportService(sess_repo, exam_repo, ser_repo, find_repo, rep_repo)
    out = str(tmp / "report.pdf")
    rep_res = rep_svc.generate_pdf_report(session_id, out)
    print("Report:", rep_res)
    print("PDF exists:", Path(out).exists(),
          "size:", Path(out).stat().st_size if Path(out).exists() else 0)

    arr = DICOMReader.load_pixel_array(files[0])
    print("Pixel array:", arr.shape, arr.dtype, "min/max:", arr.min(), arr.max())

    db.dispose()
    print("END-TO-END OK")


if __name__ == "__main__":
    main()
