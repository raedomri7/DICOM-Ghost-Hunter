"""DICOM metadata helpers: tag names, keywords, and safe access utilities."""

from __future__ import annotations

# DICOM tags of interest for quality control, expressed as (group, element) and
# keyword. Values are kept de-identified where they refer to patients.
DICOM_TAGS = {
    "PatientID": (0x0010, 0x0020),
    "PatientName": (0x0010, 0x0010),
    "PatientBirthDate": (0x0010, 0x0030),
    "StudyInstanceUID": (0x0020, 0x000D),
    "SeriesInstanceUID": (0x0020, 0x000E),
    "SOPInstanceUID": (0x0008, 0x0018),
    "Modality": (0x0008, 0x0060),
    "StudyDate": (0x0008, 0x0020),
    "StudyDescription": (0x0008, 0x1030),
    "SeriesDescription": (0x0008, 0x103E),
    "Rows": (0x0028, 0x0010),
    "Columns": (0x0028, 0x0011),
    "PixelSpacing": (0x0028, 0x0030),
    "ImagePositionPatient": (0x0020, 0x0032),
    "ImageOrientationPatient": (0x0020, 0x0037),
    "SliceThickness": (0x0018, 0x0050),
    "SpacingBetweenSlices": (0x0018, 0x0088),
    "BitsAllocated": (0x0028, 0x0100),
    "BitsStored": (0x0028, 0x0101),
    "PhotometricInterpretation": (0x0028, 0x0004),
    "SamplesPerPixel": (0x0028, 0x0002),
    "RescaleSlope": (0x0028, 0x1053),
    "RescaleIntercept": (0x0028, 0x1052),
    "InstitutionName": (0x0008, 0x0080),
    "ReferringPhysicianName": (0x0008, 0x0090),
    "PerformingPhysicianName": (0x0008, 0x1050),
    "OperatorsName": (0x0008, 0x1070),
    "PatientAddress": (0x0010, 0x1040),
    "PatientTelephoneNumbers": (0x0010, 0x2154),
    "PatientAge": (0x0010, 0x1010),
}

REQUIRED_TAGS = [
    "PatientID",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "Modality",
    "Rows",
    "Columns",
    "BitsAllocated",
    "BitsStored",
    "PhotometricInterpretation",
    "SamplesPerPixel",
]

OPTIONAL_RECOMMENDED_TAGS = [
    "StudyDate",
    "StudyDescription",
    "SeriesDescription",
    "PixelSpacing",
    "ImagePositionPatient",
    "ImageOrientationPatient",
    "SliceThickness",
    "SpacingBetweenSlices",
]

MODALITY_SPECIFIC_TAGS = {
    "CT": ["RescaleSlope", "RescaleIntercept"],
    "MR": ["EchoTime", "RepetitionTime", "FlipAngle"],
}


def tag_keyword(keyword: str) -> tuple[int, int] | None:
    """Return the (group, element) tuple for a DICOM keyword, or None."""
    return DICOM_TAGS.get(keyword)


def is_required_tag(keyword: str) -> bool:
    return keyword in REQUIRED_TAGS


def is_optional_recommended_tag(keyword: str) -> bool:
    return keyword in OPTIONAL_RECOMMENDED_TAGS
