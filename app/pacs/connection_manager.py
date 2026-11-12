"""PACS connection manager.

Holds the active PACS client (Orthanc or DICOMweb) and exposes a unified
interface to the UI. Reads configuration from settings / environment variables;
credentials are never hard-coded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.exceptions import PACSConnectionError
from app.core.logging_config import get_logger
from app.pacs.dicomweb_client import DicomwebClient
from app.pacs.orthanc_client import OrthancClient
from config.settings import settings

logger = get_logger(__name__)


class ConnectionManager:
    """Manages PACS connections (Orthanc / DICOMweb)."""

    def __init__(self) -> None:
        self.client: OrthancClient | DicomwebClient | None = None
        self.client_type: str | None = None  # "orthanc" | "dicomweb"
        self.connected = False
        self.last_error: str | None = None

    # ------------------------------------------------------------------ #
    def configure_orthanc(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: int | None = None,
        verify_ssl: bool | None = None,
    ) -> None:
        """Configure an Orthanc client from args or settings/env."""
        host = host or settings.orthanc_host or "http://localhost:8042"
        username = username or settings.orthanc_username
        password = password or settings.orthanc_password
        timeout = timeout if timeout is not None else settings.orthanc_timeout
        verify_ssl = verify_ssl if verify_ssl is not None else settings.orthanc_verify_ssl

        self.client = OrthancClient(
            host=host,
            username=username,
            password=password,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        self.client_type = "orthanc"
        self.connected = False
        self.last_error = None
        logger.info("Orthanc client configured for %s", host)

    def configure_dicomweb(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Configure a DICOMweb client (placeholder)."""
        base_url = base_url or settings.dicomweb_base_url
        username = username or settings.dicomweb_username
        password = password or settings.dicomweb_password

        self.client = DicomwebClient(base_url=base_url or "", username=username, password=password)
        self.client_type = "dicomweb"
        self.connected = False
        self.last_error = None
        logger.info("DICOMweb client configured for %s", base_url)

    # ------------------------------------------------------------------ #
    def test_connection(self) -> dict[str, Any]:
        """Test the currently configured PACS connection."""
        if self.client is None:
            self.last_error = "No PACS client configured."
            return {"ok": False, "error": self.last_error}

        try:
            result = self.client.test_connection()
        except PACSConnectionError as exc:
            self.last_error = str(exc)
            self.connected = False
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.connected = False
            return {"ok": False, "error": str(exc)}

        self.connected = bool(result.get("ok", False))
        self.last_error = result.get("error")
        return result

    # ------------------------------------------------------------------ #
    # Study / series / instance listing (Orthanc only for now)
    # ------------------------------------------------------------------ #
    def list_studies(self, limit: int = 100) -> list[dict[str, Any]]:
        if self.client_type != "orthanc" or not isinstance(self.client, OrthancClient):
            raise PACSConnectionError("Study listing is only available for Orthanc in this release.")
        if not self.connected:
            raise PACSConnectionError("Not connected to a PACS server.")
        studies = self.client.list_studies(limit=limit)
        return [self._study_to_dict(s) for s in studies]

    def list_series(self, study_id: str) -> list[dict[str, Any]]:
        if self.client_type != "orthanc" or not isinstance(self.client, OrthancClient):
            raise PACSConnectionError("Series listing is only available for Orthanc in this release.")
        if not self.connected:
            raise PACSConnectionError("Not connected to a PACS server.")
        series = self.client.list_series(study_id)
        return [self._series_to_dict(s) for s in series]

    def list_instances(self, series_id: str) -> list[dict[str, Any]]:
        if self.client_type != "orthanc" or not isinstance(self.client, OrthancClient):
            raise PACSConnectionError("Instance listing is only available for Orthanc in this release.")
        if not self.connected:
            raise PACSConnectionError("Not connected to a PACS server.")
        instances = self.client.list_instances(series_id)
        return [self._instance_to_dict(i) for i in instances]

    def get_study_metadata(self, study_id: str) -> dict[str, Any]:
        if self.client_type != "orthanc" or not isinstance(self.client, OrthancClient):
            raise PACSConnectionError("Metadata retrieval is only available for Orthanc in this release.")
        return self.client.get_study_metadata(study_id)

    def download_series(self, series_id: str, output_dir: str | Path) -> list[Path]:
        """Download all instances of a series to output_dir.

        Returns the list of saved file paths.
        """
        if self.client_type != "orthanc" or not isinstance(self.client, OrthancClient):
            raise PACSConnectionError("Series download is only available for Orthanc in this release.")
        if not self.connected:
            raise PACSConnectionError("Not connected to a PACS server.")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        instances = self.client.list_instances(series_id)
        saved: list[Path] = []
        for inst in instances:
            out = output_dir / f"{inst.id}.dcm"
            try:
                self.client.download_instance(inst.id, out)
                saved.append(out)
            except PACSConnectionError as exc:
                logger.warning("Failed to download instance %s: %s", inst.id, exc)
        return saved

    # ------------------------------------------------------------------ #
    @staticmethod
    def _study_to_dict(study) -> dict[str, Any]:
        return {
            "id": study.id,
            "patient_id": study.patient_id,
            "patient_name": study.patient_name,
            "study_date": study.study_date,
            "study_description": study.study_description,
            "modality": study.modality,
            "series_count": study.series_count,
            "instance_count": study.instance_count,
        }

    @staticmethod
    def _series_to_dict(series) -> dict[str, Any]:
        return {
            "id": series.id,
            "study_id": series.study_id,
            "modality": series.modality,
            "series_description": series.series_description,
            "series_number": series.series_number,
            "instance_count": series.instance_count,
        }

    @staticmethod
    def _instance_to_dict(instance) -> dict[str, Any]:
        return {
            "id": instance.id,
            "series_id": instance.series_id,
            "sop_instance_uid": instance.sop_instance_uid,
            "instance_number": instance.instance_number,
        }
