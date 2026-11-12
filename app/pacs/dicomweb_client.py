"""DICOMweb client stub (prepared for future integration).

Supports QIDO-RS, WADO-RS, STOW-RS endpoints conceptually. The first
implementation focuses on Orthanc REST; DICOMweb is kept as a thin placeholder
ready to be wired when a DICOMweb endpoint is available.
"""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DicomwebClient:
    """Minimal DICOMweb client placeholder.

    Not connected in MVP. Instantiate with a base URL when a DICOMweb endpoint
    is available.
    """

    def __init__(self, base_url: str, username: str | None = None, password: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    def test_connection(self) -> dict[str, Any]:
        """Return a not-implemented result until wired to a real endpoint."""
        logger.info("DICOMweb client is a placeholder (base_url=%s)", self.base_url)
        return {
            "ok": False,
            "error": "DICOMweb integration not yet implemented (placeholder).",
            "base_url": self.base_url,
        }
