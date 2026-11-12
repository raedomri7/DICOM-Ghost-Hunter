"""Orthanc PACS REST API client (optional, Workflow B).

Provides connection testing, study/series/instance listing, and metadata
retrieval from an Orthanc server. Credentials are never hard-coded; they come
from configuration / environment variables. All network calls use timeouts and
secure communication where supported.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app.core.exceptions import PACSConnectionError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class OrthancStudy:
    """Summary of a study returned by Orthanc."""

    id: str
    patient_id: str | None = None
    patient_name: str | None = None
    study_date: str | None = None
    study_description: str | None = None
    modality: str | None = None
    series_count: int = 0
    instance_count: int = 0


@dataclass
class OrthancSeries:
    """Summary of a series returned by Orthanc."""

    id: str
    study_id: str
    modality: str | None = None
    series_description: str | None = None
    series_number: int | None = None
    instance_count: int = 0


@dataclass
class OrthancInstance:
    """Summary of an instance returned by Orthanc."""

    id: str
    series_id: str
    sop_instance_uid: str | None = None
    instance_number: int | None = None


class OrthancClient:
    """Client for the Orthanc REST API.

    Supports:
        - connection configuration & testing
        - study / series / instance listing
        - metadata retrieval
    """

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 30,
        verify_ssl: bool = False,
    ) -> None:
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        if username and password:
            self.session.auth = (username, password)
        self.session.headers.update({"Accept": "application/json"})
        self._connected = False

    # ------------------------------------------------------------------ #
    def test_connection(self) -> dict[str, Any]:
        """Test connectivity to the Orthanc server.

        Returns a dict with 'ok', 'server_info', and optional 'error'.
        """
        try:
            server_info = self._get("/system")
            self._connected = True
            return {
                "ok": True,
                "server_info": server_info,
                "host": self.host,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - report gracefully
            self._connected = False
            logger.warning("Orthanc connection test failed for %s: %s", self.host, exc)
            return {"ok": False, "server_info": None, "host": self.host, "error": str(exc)}

    # ------------------------------------------------------------------ #
    def list_studies(self, limit: int = 100) -> list[OrthancStudy]:
        """List studies on the Orthanc server."""
        data = self._get("/studies", limit=limit)
        studies: list[OrthancStudy] = []
        if not isinstance(data, list):
            return studies
        for item in data:
            if not isinstance(item, dict):
                continue
            studies.append(
                OrthancStudy(
                    id=str(item.get("ID", "")),
                    patient_id=item.get("PatientID"),
                    patient_name=item.get("PatientName"),
                    study_date=item.get("StudyDate"),
                    study_description=item.get("StudyDescription"),
                    modality=item.get("Modality"),
                    series_count=int(item.get("SeriesCount", 0) or 0),
                    instance_count=int(item.get("InstanceCount", 0) or 0),
                )
            )
        return studies

    def list_series(self, study_id: str) -> list[OrthancSeries]:
        """List series within a study."""
        data = self._get(f"/studies/{study_id}/series")
        series: list[OrthancSeries] = []
        if not isinstance(data, list):
            return series
        for item in data:
            if not isinstance(item, dict):
                continue
            series.append(
                OrthancSeries(
                    id=str(item.get("ID", "")),
                    study_id=study_id,
                    modality=item.get("Modality"),
                    series_description=item.get("SeriesDescription"),
                    series_number=self._as_int(item.get("SeriesNumber")),
                    instance_count=int(item.get("Instances", 0) or 0),
                )
            )
        return series

    def list_instances(self, series_id: str) -> list[OrthancInstance]:
        """List instances within a series."""
        data = self._get(f"/series/{series_id}/instances")
        instances: list[OrthancInstance] = []
        if not isinstance(data, list):
            return instances
        for item in data:
            if not isinstance(item, dict):
                continue
            instances.append(
                OrthancInstance(
                    id=str(item.get("ID", "")),
                    series_id=series_id,
                    sop_instance_uid=item.get("SOPInstanceUID"),
                    instance_number=self._as_int(item.get("InstanceNumber")),
                )
            )
        return instances

    def get_study_metadata(self, study_id: str) -> dict[str, Any]:
        """Retrieve full metadata for a study (main tags)."""
        return self._get(f"/studies/{study_id}")

    def get_series_metadata(self, series_id: str) -> dict[str, Any]:
        """Retrieve full metadata for a series."""
        return self._get(f"/series/{series_id}")

    def get_instance_metadata(self, instance_id: str) -> dict[str, Any]:
        """Retrieve full metadata for an instance."""
        return self._get(f"/instances/{instance_id}")

    def download_instance(self, instance_id: str, output_path: str | Path) -> Path:
        """Download a DICOM instance file from Orthanc to output_path.

        Returns the path to the saved file.
        """
        output_path = Path(output_path)
        url = f"{self.host}/instances/{instance_id}/file"
        try:
            response = self.session.get(
                url, timeout=self.timeout, verify=self.verify_ssl
            )
        except requests.RequestException as exc:
            raise PACSConnectionError(f"Failed to download instance {instance_id}: {exc}") from exc

        if response.status_code >= 400:
            raise PACSConnectionError(
                f"Orthanc returned HTTP {response.status_code} downloading {instance_id}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        logger.info("Downloaded instance %s to %s", instance_id, output_path)
        return output_path

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get(self, path: str, **params: Any) -> Any:
        url = f"{self.host}{path}"
        try:
            response = self.session.get(
                url, params=params or None, timeout=self.timeout, verify=self.verify_ssl
            )
        except requests.RequestException as exc:
            raise PACSConnectionError(f"Failed to connect to Orthanc at {url}: {exc}") from exc

        if response.status_code >= 400:
            raise PACSConnectionError(
                f"Orthanc returned HTTP {response.status_code} for {url}: {response.text[:200]}"
            )

        if not response.text.strip():
            return None

        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected
