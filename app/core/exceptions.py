"""Custom exceptions for the DICOM Ghost Hunter application."""

from __future__ import annotations


class DICOMGhostHunterError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class DICOMReadError(DICOMGhostHunterError):
    """Raised when a DICOM file cannot be read or parsed."""


class InvalidDICOMFileError(DICOMReadError):
    """Raised when a file is not a valid DICOM Part 10 file."""


class UnsupportedTransferSyntaxError(DICOMReadError):
    """Raised when the transfer syntax is not supported."""


class MetadataValidationError(DICOMGhostHunterError):
    """Raised when required metadata is missing or invalid."""


class AnalysisError(DICOMGhostHunterError):
    """Raised when a quality-control analysis step fails."""


class DatabaseError(DICOMGhostHunterError):
    """Raised when a database operation fails."""


class ReportGenerationError(DICOMGhostHunterError):
    """Raised when PDF report generation fails."""


class PACSConnectionError(DICOMGhostHunterError):
    """Raised when a PACS server connection fails."""


class ConfigurationError(DICOMGhostHunterError):
    """Raised when application configuration is invalid or missing."""
