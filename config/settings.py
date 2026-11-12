"""Application settings loaded from YAML config and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
DATABASE_DIR = DATA_DIR / "database"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"

DEFAULT_QC_RULES_FILE = CONFIG_DIR / "qc_rules.yaml"


def _get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


@dataclass
class Settings:
    """Centralized application settings."""

    app_name: str = "DICOM Ghost Hunter"
    app_version: str = "0.1.0"
    app_env: str = "development"

    log_level: str = "INFO"
    log_file: Path = LOGS_DIR / "dicom_ghost_hunter.log"

    database_url: str = f"sqlite:///{DATABASE_DIR / 'dicom_ghost_hunter.db'}"

    qc_rules_file: Path = DEFAULT_QC_RULES_FILE

    orthanc_host: str | None = _get_env("ORTHANC_HOST", "http://localhost:8042")
    orthanc_username: str | None = _get_env("ORTHANC_USERNAME", None)
    orthanc_password: str | None = _get_env("ORTHANC_PASSWORD", None)
    orthanc_timeout: int = int(_get_env("ORTHANC_TIMEOUT", "30") or "30")
    orthanc_verify_ssl: bool = _get_env("ORTHANC_VERIFY_SSL", "false").lower() == "true"

    dicomweb_base_url: str | None = _get_env("DICOMWEB_BASE_URL", None)
    dicomweb_username: str | None = _get_env("DICOMWEB_USERNAME", None)
    dicomweb_password: str | None = _get_env("DICOMWEB_PASSWORD", None)

    data_retention_days: int = int(_get_env("DATA_RETENTION_DAYS", "90") or "90")

    ui_theme: str = _get_env("UI_THEME", "dark") or "dark"
    ui_max_recent_examinations: int = int(
        _get_env("UI_MAX_RECENT_EXAMINATIONS", "10") or "10"
    )

    qc_rules: dict[str, Any] = field(default_factory=dict)

    def load_qc_rules(self) -> dict[str, Any]:
        """Load quality-control rules from the YAML configuration file."""
        rules_path = self.qc_rules_file
        if rules_path.exists():
            with rules_path.open("r", encoding="utf-8") as handle:
                self.qc_rules = yaml.safe_load(handle) or {}
        else:
            self.qc_rules = {}
        return self.qc_rules

    def ensure_directories(self) -> None:
        """Create required data directories if they do not exist."""
        for directory in (
            DATA_DIR,
            DATABASE_DIR,
            REPORTS_DIR,
            LOGS_DIR,
            SAMPLES_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
