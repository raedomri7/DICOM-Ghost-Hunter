"""DICOM Ghost Hunter — application entry point.

Usage (Windows):
    py main.py
"""

from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from app.core.application import create_application
from app.ui.main_window import DICOMGhostHunterWindow


def main() -> int:
    application = create_application()
    app = QApplication(sys.argv)
    app.setApplicationName("DICOM Ghost Hunter")
    window = DICOMGhostHunterWindow(application=application)
    window.show()
    try:
        return app.exec()
    finally:
        application.shutdown()


if __name__ == "__main__":
    sys.exit(main())
