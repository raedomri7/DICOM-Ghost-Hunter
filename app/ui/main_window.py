"""Main application window — PyQt5 desktop interface.

Navigation: Dashboard, Import DICOM, Examination Browser, QC Results, DICOM
Viewer, Reports, PACS Connection, Settings, About.

Supports importing either a single DICOM file or a folder of DICOM files.
Heavy work (import, analysis, PDF report) runs in background workers so the
GUI never freezes. A real matplotlib-based DICOM viewer displays images with
window/level and slice navigation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.application import create_application
from app.core.logging_config import get_logger
from app.pacs.connection_manager import ConnectionManager
from app.ui.workers import AnalysisWorker, ImportWorker, ReportWorker, WorkerManager
from app.viewer.image_viewer import DicomImageViewer

logger = get_logger(__name__)

ACCENT = "#1f3a5f"
ACCENT_HOVER = "#2a4a7f"
BACKGROUND = "#12161e"
CARD = "#1c232e"
TEXT = "#eaeaea"
MUTED = "#9aa5b1"


class DICOMGhostHunterWindow(QWidget):
    """Main window of DICOM Ghost Hunter."""

    def __init__(self, application: Any | None = None) -> None:
        super().__init__()
        self.application = application or create_application()
        self.setWindowTitle("DICOM Ghost Hunter — Technical Quality Control")
        self.resize(1400, 900)

        # Application state
        self.current_session_id: str | None = None
        self.valid_instances: list[Any] = []
        self.examinations: list[Any] = []
        self.series_map: dict[str, list[Any]] = {}  # series_instance_uid -> instances
        self._selected_series_id: str | None = None
        self._processing_current_array: Any = None

        self.worker_manager = WorkerManager()
        self.import_worker: ImportWorker | None = None
        self.analysis_worker: AnalysisWorker | None = None
        self.report_worker: ReportWorker | None = None
        self.pacs_manager = ConnectionManager()

        self._apply_theme()
        self._build_ui()
        QTimer.singleShot(0, self._refresh_dashboard)

    # ------------------------------------------------------------------ #
    def _apply_theme(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(BACKGROUND))
        palette.setColor(QPalette.WindowText, QColor(TEXT))
        palette.setColor(QPalette.Base, QColor(CARD))
        palette.setColor(QPalette.AlternateBase, QColor(CARD))
        palette.setColor(QPalette.Text, QColor(TEXT))
        palette.setColor(QPalette.Button, QColor(CARD))
        palette.setColor(QPalette.ButtonText, QColor(TEXT))
        self.setPalette(palette)
        self.setStyleSheet(
            f"""
            QWidget {{ background: {BACKGROUND}; color: {TEXT}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QLabel#title {{ font-size: 22px; font-weight: bold; color: {TEXT}; }}
            QLabel#subtitle {{ color: {MUTED}; font-size: 12px; }}
            QFrame#sidebar {{ background: #1a1f28; border-right: 1px solid #2c3542; }}
            QListWidget {{ background: transparent; border: none; outline: none; }}
            QListWidget::item {{ padding: 10px 14px; border-left: 4px solid transparent; color: {TEXT}; }}
            QListWidget::item:selected {{ background: {ACCENT}; border-left: 4px solid #5b8def; color: white; }}
            QListWidget::item:hover {{ background: #242c3a; }}
            QPushButton#navBtn {{ text-align: left; padding: 8px 12px; background: transparent; border: none; color: {TEXT}; }}
            QPushButton#navBtn:hover {{ background: #242c3a; }}
            QPushButton#primary {{ background: {ACCENT}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: 600; }}
            QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton#primary:disabled {{ background: #555555; color: #aaaaaa; }}
            QPushButton#ghost {{ background: transparent; border: 1px solid #3d4858; color: {TEXT}; padding: 6px 12px; border-radius: 4px; }}
            QPushButton#ghost:hover {{ border-color: {ACCENT}; }}
            QTableWidget {{ background: {CARD}; gridline-color: #2c3542; color: {TEXT}; border: 1px solid #2c3542; }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background: {ACCENT}; }}
            QHeaderView::section {{ background: #1c232e; color: {TEXT}; border: none; border-bottom: 1px solid #2c3542; padding: 6px; font-weight: 600; }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {CARD}; border: 1px solid #3d4858; color: {TEXT}; padding: 6px; border-radius: 4px; }}
            QProgressBar {{ background: #1c232e; border: 1px solid #3d4858; border-radius: 4px; text-align: center; color: {TEXT}; }}
            QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
            QFrame#card {{ background: {CARD}; border: 1px solid #2c3542; border-radius: 8px; }}
            QLabel#kpiValue {{ font-size: 20px; font-weight: bold; color: #5b8def; }}
            QLabel#kpiLabel {{ color: {MUTED}; font-size: 11px; }}
            QTextEdit {{ background: {CARD}; border: 1px solid #2c3542; color: {TEXT}; }}
            """
        )

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(0, 16, 0, 16)
        s_layout.setSpacing(4)

        app_title = QLabel("DICOM\nGhost Hunter")
        app_title.setObjectName("title")
        app_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #5b8def; line-height: 1.2;")
        s_layout.addWidget(app_title)
        s_layout.addSpacing(18)

        self.nav_list = QListWidget()
        self.nav_list.setFocusPolicy(Qt.NoFocus)
        nav_items = [
            ("Dashboard", "dashboard"),
            ("Import DICOM", "import"),
            ("Examination Browser", "browser"),
            ("DICOM Viewer", "viewer"),
            ("QC Results", "qc"),
            ("Image Processing Lab", "processing"),
            ("Reports", "reports"),
            ("PACS Connection", "pacs"),
            ("Settings", "settings"),
            ("About", "about"),
        ]
        for label, key in nav_items:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        s_layout.addWidget(self.nav_list)
        s_layout.addStretch()

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet(f"color: {MUTED}; font-size: 11px; padding: 4px 12px;")
        s_layout.addWidget(self.status_label)

        # Main content
        self.stack = QStackedWidget()
        self.page_dashboard = self._build_dashboard_page()
        self.page_import = self._build_import_page()
        self.page_browser = self._build_browser_page()
        self.page_viewer = self._build_viewer_page()
        self.page_qc = self._build_qc_page()
        self.page_processing = self._build_processing_page()
        self.page_reports = self._build_reports_page()
        self.page_pacs = self._build_pacs_page()
        self.page_settings = self._build_settings_page()
        self.page_about = self._build_about_page()

        for page in (
            self.page_dashboard, self.page_import, self.page_browser, self.page_viewer,
            self.page_qc, self.page_processing, self.page_reports, self.page_pacs, self.page_settings, self.page_about,
        ):
            self.stack.addWidget(page)

        root.addWidget(sidebar)
        root.addWidget(self.stack)

    def _on_nav_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            return
        key = current.data(Qt.UserRole)
        mapping = {
            "dashboard": self.page_dashboard,
            "import": self.page_import,
            "browser": self.page_browser,
            "viewer": self.page_viewer,
            "qc": self.page_qc,
            "processing": self.page_processing,
            "reports": self.page_reports,
            "pacs": self.page_pacs,
            "settings": self.page_settings,
            "about": self.page_about,
        }
        self.stack.setCurrentWidget(mapping.get(key, self.page_dashboard))
        if key == "dashboard":
            self._refresh_dashboard()
        elif key == "browser":
            self._refresh_browser()
        elif key == "viewer":
            pass  # viewer updated when a series is selected
        elif key == "qc":
            self._populate_qc_table("All")

    # ------------------------------------------------------------------ # pages: dashboard
    def _kpi_card(self, title: str, value: str = "0") -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(4)
        val = QLabel(value)
        val.setObjectName("kpiValue")
        val.setProperty("kpiKey", title.lower().replace(" ", "_"))
        lab = QLabel(title)
        lab.setObjectName("kpiLabel")
        lay.addWidget(val)
        lay.addWidget(lab)
        return card

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        title = QLabel("Dashboard")
        title.setObjectName("title")
        sub = QLabel("Overview of analyses and quality-control findings.")
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        cards_lay = QHBoxLayout()
        self.kpi_exams = self._kpi_card("Examinations Analyzed", "0")
        self.kpi_instances = self._kpi_card("DICOM Instances", "0")
        self.kpi_series = self._kpi_card("Series", "0")
        self.kpi_critical = self._kpi_card("Critical Findings", "0")
        self.kpi_high = self._kpi_card("High-Priority Findings", "0")
        self.kpi_duplicates = self._kpi_card("Potential Duplicates", "0")
        self.kpi_discontinuities = self._kpi_card("Potential Spatial Discontinuities", "0")
        for card in (self.kpi_exams, self.kpi_instances, self.kpi_series, self.kpi_critical,
                     self.kpi_high, self.kpi_duplicates, self.kpi_discontinuities):
            cards_lay.addWidget(card)
        lay.addLayout(cards_lay)
        lay.addStretch()
        return page

    def _set_kpi(self, card: QFrame, value: str) -> None:
        for child in card.findChildren(QLabel):
            if child.objectName() == "kpiValue":
                child.setText(value)
                break

    def _refresh_dashboard(self) -> None:
        try:
            session_repo = self.application.session_repo
            finding_repo = self.application.finding_repo
            sessions = session_repo.list_all(limit=1)
            counts = {}
            if sessions:
                session = sessions[0]
                self.current_session_id = session.id
                counts = finding_repo.count_by_severity(session.id)

            self._set_kpi(self.kpi_exams, str(len(self.examinations) if self.examinations else (1 if sessions else 0)))
            self._set_kpi(self.kpi_instances, str(len(self.valid_instances)))
            series_uids = {i.series_instance_uid for i in self.valid_instances if i.series_instance_uid}
            self._set_kpi(self.kpi_series, str(len(series_uids)))
            self._set_kpi(self.kpi_critical, str(counts.get("CRITICAL", 0)))
            self._set_kpi(self.kpi_high, str(counts.get("HIGH", 0)))
            self._set_kpi(self.kpi_duplicates, "0")
            self._set_kpi(self.kpi_discontinuities, "0")
        except Exception as exc:
            logger.exception("Dashboard refresh failed")
            self.status_label.setText(f"Dashboard error: {exc}")

    # ------------------------------------------------------------------ # pages: import
    def _build_import_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        title = QLabel("Import DICOM")
        title.setObjectName("title")
        sub = QLabel("Import a single DICOM file or a folder of DICOM files (Workflow A).")
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        # Path selection
        path_lay = QHBoxLayout()
        self.path_edit = QLabel("No file or folder selected")
        self.path_edit.setStyleSheet(f"color: {MUTED}; padding: 8px; background: {CARD}; border: 1px solid #3d4858; border-radius: 4px;")
        self.path_edit.setMinimumHeight(40)
        self.btn_browse_file = QPushButton("Choose File…")
        self.btn_browse_file.setObjectName("ghost")
        self.btn_browse_file.clicked.connect(self._browse_file)
        self.btn_browse_folder = QPushButton("Choose Folder…")
        self.btn_browse_folder.setObjectName("ghost")
        self.btn_browse_folder.clicked.connect(self._browse_folder)
        path_lay.addWidget(self.path_edit, stretch=1)
        path_lay.addWidget(self.btn_browse_file)
        path_lay.addWidget(self.btn_browse_folder)
        lay.addLayout(path_lay)

        # Import buttons
        btn_row = QHBoxLayout()
        self.btn_import = QPushButton("Start Import")
        self.btn_import.setObjectName("primary")
        self.btn_import.clicked.connect(self._start_import)
        self.btn_import.setEnabled(False)
        btn_row.addWidget(self.btn_import)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.import_progress = QProgressBar()
        self.import_progress.setRange(0, 100)
        self.import_progress.setValue(0)
        lay.addWidget(self.import_progress)

        self.import_log = QLabel("")
        self.import_log.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(self.import_log)
        lay.addStretch()
        return page

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select DICOM file", "", "DICOM files (*.dcm *.dicom);;All files (*)"
        )
        if path:
            self.path_edit.setText(path)
            self.btn_import.setEnabled(True)
            self.status_label.setText(f"File selected: {path}")

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select DICOM folder")
        if folder:
            self.path_edit.setText(folder)
            self.btn_import.setEnabled(True)
            self.status_label.setText(f"Folder selected: {folder}")

    def _start_import(self) -> None:
        path = self.path_edit.text()
        if path == "No file or folder selected" or not path:
            return
        self.btn_import.setEnabled(False)
        self.import_progress.setValue(0)
        self.import_log.setText("Importing…")
        self.status_label.setText("Importing DICOM files…")

        self.import_worker = ImportWorker(self.application.import_service, path)
        self.import_worker.progress.connect(lambda p, m: self.import_progress.setValue(p))
        self.import_worker.result.connect(self._on_import_finished)
        self.import_worker.error.connect(self._on_import_error)
        self.import_worker.finished.connect(lambda: self.btn_import.setEnabled(True))
        self.worker_manager.start(self.import_worker)

    def _on_import_finished(self, result: dict[str, Any]) -> None:
        self.import_progress.setValue(100)
        self.current_session_id = result.get("session_id")
        self.valid_instances = result.get("valid_instances_list", [])
        self.examinations = result.get("examinations_list", [])

        # Build series -> instances map for viewing
        self.series_map = {}
        for inst in self.valid_instances:
            uid = inst.series_instance_uid or "__UNKNOWN__"
            self.series_map.setdefault(uid, []).append(inst)

        self.import_log.setText(
            f"Import complete: {result.get('valid_instances', 0)} valid, "
            f"{result.get('invalid_instances', 0)} invalid, "
            f"{result.get('examinations', 0)} examinations, "
            f"{len(self.series_map)} series."
        )
        self.status_label.setText("Import complete")
        self._refresh_dashboard()
        self._refresh_browser()
        QMessageBox.information(
            self, "Import Complete",
            f"Imported {result.get('valid_instances', 0)} instances across "
            f"{result.get('examinations', 0)} examinations and {len(self.series_map)} series."
        )

    def _on_import_error(self, message: str) -> None:
        self.import_log.setText(f"Import failed: {message}")
        self.status_label.setText("Import failed")
        self.btn_import.setEnabled(True)
        QMessageBox.critical(self, "Import Error", message)

    # ------------------------------------------------------------------ # pages: browser
    def _build_browser_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel("Examination Browser")
        title.setObjectName("title")
        sub = QLabel("Browse imported studies and series. Double-click a series to open it in the DICOM Viewer.")
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        self.browser_table = QTableWidget(0, 6)
        self.browser_table.setHorizontalHeaderLabels(
            ["Study Instance UID", "Modality", "Series Instance UID", "Series Description", "Instances", "Source"]
        )
        self.browser_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.browser_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.browser_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.browser_table.doubleClicked.connect(self._on_browser_double_click)
        lay.addWidget(self.browser_table, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_refresh_browser = QPushButton("Refresh")
        self.btn_refresh_browser.setObjectName("ghost")
        self.btn_refresh_browser.clicked.connect(self._refresh_browser)
        self.btn_view_selected = QPushButton("View Selected Series")
        self.btn_view_selected.setObjectName("primary")
        self.btn_view_selected.clicked.connect(self._view_selected_series)
        self.btn_run_qc = QPushButton("Run QC on Selected")
        self.btn_run_qc.setObjectName("primary")
        self.btn_run_qc.clicked.connect(self._run_qc_selected)
        btn_row.addWidget(self.btn_refresh_browser)
        btn_row.addWidget(self.btn_view_selected)
        btn_row.addWidget(self.btn_run_qc)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._refresh_browser()
        return page

    def _refresh_browser(self) -> None:
        self.browser_table.setRowCount(0)
        for ex in self.examinations:
            for series in ex.series:
                row = self.browser_table.rowCount()
                self.browser_table.insertRow(row)
                vals = [
                    str(ex.study_instance_uid or "-"),
                    str(ex.modality or "-"),
                    str(series.series_instance_uid or "-"),
                    str(series.description or "-"),
                    str(series.instance_count),
                    str(ex.source_path or "-"),
                ]
                for col, v in enumerate(vals):
                    item = QTableWidgetItem(v)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.browser_table.setItem(row, col, item)

    def _selected_series_instances(self) -> list[Any] | None:
        row = self.browser_table.currentRow()
        if row < 0:
            return None
        series_uid_item = self.browser_table.item(row, 2)
        if not series_uid_item:
            return None
        series_uid = series_uid_item.text()
        if series_uid == "-":
            return None
        return self.series_map.get(series_uid, [])

    def _on_browser_double_click(self) -> None:
        self._view_selected_series()

    def _view_selected_series(self) -> None:
        instances = self._selected_series_instances()
        if not instances:
            QMessageBox.information(self, "No Selection", "Please select a series in the browser.")
            return
        # Switch to viewer page and load series
        self.nav_list.setCurrentRow(3)  # viewer index
        self.viewer.load_series(instances)
        self.status_label.setText(f"Viewing series with {len(instances)} instance(s)")

    def _run_qc_selected(self) -> None:
        instances = self._selected_series_instances()
        if not instances:
            QMessageBox.information(self, "No Selection", "Please select a series in the browser.")
            return
        if not self.current_session_id:
            QMessageBox.warning(self, "No Session", "Please import a dataset first.")
            return
        series_uid_item = self.browser_table.item(self.browser_table.currentRow(), 2)
        series_uid = series_uid_item.text() if series_uid_item else None

        study_uid_item = self.browser_table.item(self.browser_table.currentRow(), 0) if self.browser_table.currentRow() >= 0 else None

        self.analysis_worker = AnalysisWorker(
            self.application.analysis_service,
            self.current_session_id,
            [{
                "series_id": series_uid,
                "examination_id": study_uid_item.text() if study_uid_item else None,
                "instances": instances,
                "modality": instances[0].modality,
                "label": series_uid,
                "rules": {},
            }],
        )
        self.analysis_worker.progress.connect(lambda p, m: self.status_label.setText(m))
        self.analysis_worker.result.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.status_label.setText("Running QC pipeline…")
        self.worker_manager.start(self.analysis_worker)

    def _on_analysis_finished(self, result: dict[str, Any]) -> None:
        self.status_label.setText("QC analysis complete")
        total = sum(sr.get("total_findings", 0) for sr in result.get("series_results", []))
        QMessageBox.information(
            self, "Analysis Complete",
            f"QC analysis complete: {total} findings across {len(result.get('series_results', []))} series."
        )
        self._refresh_dashboard()
        self._populate_qc_table("All")

    def _on_analysis_error(self, message: str) -> None:
        self.status_label.setText("Analysis failed")
        QMessageBox.critical(self, "Analysis Error", message)

    # ------------------------------------------------------------------ # pages: viewer
    def _build_viewer_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel("DICOM Viewer")
        title.setObjectName("title")
        sub = QLabel("2D axial DICOM visualization with window/level and slice navigation.")
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        self.viewer = DicomImageViewer()
        lay.addWidget(self.viewer, stretch=1)
        self.viewer.slice_changed.connect(self._on_viewer_slice_changed)

        # Hint when nothing loaded
        self.viewer_hint = QLabel("Select a series from the Examination Browser to view images.")
        self.viewer_hint.setAlignment(Qt.AlignCenter)
        self.viewer_hint.setStyleSheet(f"color: {MUTED}; font-size: 13px; padding: 20px;")
        lay.addWidget(self.viewer_hint)
        return page

    # ------------------------------------------------------------------ # pages: QC
    def _build_qc_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel("Quality-Control Results")
        title.setObjectName("title")
        lay.addWidget(title)

        filter_lay = QHBoxLayout()
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"])
        self.severity_filter.currentTextChanged.connect(self._populate_qc_table)
        filter_lay.addWidget(QLabel("Severity:"))
        filter_lay.addWidget(self.severity_filter)
        filter_lay.addStretch()
        lay.addLayout(filter_lay)

        self.qc_table = QTableWidget(0, 7)
        self.qc_table.setHorizontalHeaderLabels(
            ["ID", "Category", "Severity", "Title", "Description", "Recommended Action", "Instance"]
        )
        self.qc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.qc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.qc_table, stretch=1)

        self.qc_count_label = QLabel("0 findings")
        self.qc_count_label.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(self.qc_count_label)

        self._populate_qc_table("All")
        return page

    def _populate_qc_table(self, severity: str) -> None:
        self.qc_table.setRowCount(0)
        if not self.current_session_id:
            return
        try:
            findings = self.application.finding_repo.list_for_session(self.current_session_id, limit=500)
            if severity != "All":
                findings = [f for f in findings if f.severity == severity]
        except Exception as exc:
            logger.exception("Failed to load findings")
            self.qc_count_label.setText(f"Error loading findings: {exc}")
            return

        self.qc_count_label.setText(f"{len(findings)} findings")
        for f in findings:
            row = self.qc_table.rowCount()
            self.qc_table.insertRow(row)
            vals = [f.id, f.category, f.severity, f.title, f.description, f.recommendation or "-", f.instance_reference or "-"]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.qc_table.setItem(row, col, item)

    # ------------------------------------------------------------------ # pages: image processing lab
    def _build_processing_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel("Image Processing Laboratory")
        title.setObjectName("title")
        sub = QLabel(
            "Apply image-processing operations to DICOM slices. "
            "Original data is preserved; results are derived images."
        )
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        # Source slice info
        self.processing_source_label = QLabel("No slice loaded. Select a series in the Viewer first.")
        self.processing_source_label.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(self.processing_source_label)

        # Operation selection
        op_lay = QHBoxLayout()
        op_lay.addWidget(QLabel("Operation:"))
        self.processing_op_combo = QComboBox()
        self.processing_op_combo.addItems(self.application.processing_service.available_operations())
        self.processing_op_combo.currentTextChanged.connect(self._processing_op_changed)
        op_lay.addWidget(self.processing_op_combo)
        op_lay.addStretch()
        lay.addLayout(op_lay)

        # Dynamic parameter controls
        self.processing_param_widgets: dict[str, QWidget] = {}
        self.processing_params_lay = QVBoxLayout()
        lay.addLayout(self.processing_params_lay)
        self._processing_op_changed(self.processing_op_combo.currentText())

        # Apply / pipeline buttons
        btn_lay = QHBoxLayout()
        self.btn_processing_apply = QPushButton("Apply Operation")
        self.btn_processing_apply.setObjectName("primary")
        self.btn_processing_apply.clicked.connect(self._processing_apply)
        self.btn_processing_clear = QPushButton("Clear History")
        self.btn_processing_clear.setObjectName("ghost")
        self.btn_processing_clear.clicked.connect(self._processing_clear)
        btn_lay.addWidget(self.btn_processing_apply)
        btn_lay.addWidget(self.btn_processing_clear)
        btn_lay.addStretch()
        lay.addLayout(btn_lay)

        # Result display
        self.processing_result_viewer = DicomImageViewer()
        lay.addWidget(self.processing_result_viewer, stretch=1)

        self.processing_log = QLabel("")
        self.processing_log.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(self.processing_log)

        return page

    def _processing_op_changed(self, op_name: str) -> None:
        # Clear existing param widgets
        for widget in self.processing_param_widgets.values():
            widget.setParent(None)
        self.processing_param_widgets.clear()

        # Build parameter controls based on operation

        param_defs = {
            "normalize_minmax": [],
            "normalize_zscore": [],
            "normalize_percentile": [("low", 1.0, 0.0, 100.0), ("high", 99.0, 0.0, 100.0)],
            "contrast_adjust": [("factor", 1.0, 0.0, 10.0)],
            "brightness_adjust": [("offset", 0.0, -1000.0, 1000.0)],
            "gamma_correction": [("gamma", 1.0, 0.1, 10.0)],
            "invert": [],
            "clip": [("low", 0.0, -10000.0, 10000.0), ("high", 1000.0, -10000.0, 10000.0)],
            "gaussian_filter": [("sigma", 1.0, 0.1, 10.0)],
            "median_filter": [("size", 3.0, 1.0, 21.0)],
            "bilateral_filter": [("sigma_color", 10.0, 0.1, 100.0), ("sigma_spatial", 5.0, 0.1, 50.0)],
            "histogram_equalization": [],
            "clahe": [("clip_limit", 2.0, 0.1, 20.0), ("tile_grid", 8.0, 1.0, 64.0)],
            "unsharp_masking": [("sigma", 1.0, 0.1, 10.0), ("strength", 1.0, 0.0, 5.0)],
            "sobel": [],
            "prewitt": [],
            "laplacian": [],
            "canny": [("low_threshold", 50.0, 0.0, 1000.0), ("high_threshold", 150.0, 0.0, 1000.0)],
            "gradient_magnitude": [],
            "erosion": [("iterations", 1.0, 1.0, 10.0)],
            "dilation": [("iterations", 1.0, 1.0, 10.0)],
            "opening": [("iterations", 1.0, 1.0, 10.0)],
            "closing": [("iterations", 1.0, 1.0, 10.0)],
            "morphological_gradient": [("iterations", 1.0, 1.0, 10.0)],
            "fft_spectrum": [],
            "lowpass_filter": [("cutoff", 30.0, 1.0, 500.0)],
            "highpass_filter": [("cutoff", 30.0, 1.0, 500.0)],
        }

        defs = param_defs.get(op_name, [])
        for pname, default, pmin, pmax in defs:
            row = QHBoxLayout()
            label = QLabel(pname.replace("_", " ").title())
            spin = QDoubleSpinBox()
            spin.setRange(pmin, pmax)
            spin.setValue(default)
            spin.setDecimals(2)
            row.addWidget(label)
            row.addWidget(spin)
            row.addStretch()
            self.processing_params_lay.addLayout(row)
            self.processing_param_widgets[pname] = spin

    def _processing_get_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for pname, widget in self.processing_param_widgets.items():
            params[pname] = widget.value()
        return params

    def _processing_apply(self) -> None:
        if self._processing_current_array is None:
            QMessageBox.warning(self, "No Data", "No slice loaded for processing.")
            return
        op_name = self.processing_op_combo.currentText()
        params = self._processing_get_params()
        try:
            result = self.application.processing_service.apply_operation(
                self._processing_current_array, op_name, **params
            )
            self._processing_result_array = result["result"]
            self._show_processing_result(result["result"])
            self.processing_log.setText(
                f"Applied {op_name}: {result['input_shape']} -> {result['output_shape']}"
            )
            self.status_label.setText(f"Processing: {op_name}")
        except Exception as exc:
            logger.exception("Processing failed")
            self.processing_log.setText(f"Processing failed: {exc}")
            QMessageBox.critical(self, "Processing Error", str(exc))

    def _show_processing_result(self, array: np.ndarray) -> None:
        """Show a derived array in the processing result viewer using matplotlib."""
        self.processing_result_viewer.axes.clear()
        vmin, vmax = float(array.min()), float(array.max())
        if vmax > vmin:
            self.processing_result_viewer.axes.imshow(array, cmap="gray", vmin=vmin, vmax=vmax)
        else:
            self.processing_result_viewer.axes.imshow(array, cmap="gray")
        self.processing_result_viewer.axes.set_title("Processed Result")
        self.processing_result_viewer.axes.axis("off")
        self.processing_result_viewer.canvas.draw_idle()

    def _processing_clear(self) -> None:
        self.application.processing_service.clear_history()
        self.processing_log.setText("History cleared")

    # ------------------------------------------------------------------ #
    def _on_viewer_slice_changed(self, index: int, total: int) -> None:
        """Update the processing source array when the viewer slice changes."""
        array = self.viewer.current_array
        self._processing_current_array = array
        if array is not None:
            self.processing_source_label.setText(
                f"Source: slice {index + 1}/{total} | shape {array.shape} | "
                f"min {float(array.min()):.1f} | max {float(array.max()):.1f}"
            )
        else:
            self.processing_source_label.setText("No slice loaded. Select a series in the Viewer first.")

    # ------------------------------------------------------------------ # pages: reports

    def _build_reports_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        title = QLabel("Reports")
        title.setObjectName("title")
        sub = QLabel("Generate a professional PDF quality-control report.")
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        self.report_path_edit = QLabel("No report path selected")
        self.report_path_edit.setStyleSheet(f"color: {MUTED}; padding: 8px; background: {CARD}; border: 1px solid #3d4858; border-radius: 4px;")
        self.report_path_edit.setMinimumHeight(40)
        lay.addWidget(self.report_path_edit)

        btn_row = QHBoxLayout()
        self.btn_report_browse = QPushButton("Choose Location…")
        self.btn_report_browse.setObjectName("ghost")
        self.btn_report_browse.clicked.connect(self._choose_report_location)
        self.btn_generate_report = QPushButton("Generate PDF Report")
        self.btn_generate_report.setObjectName("primary")
        self.btn_generate_report.clicked.connect(self._generate_report)
        btn_row.addWidget(self.btn_report_browse)
        btn_row.addWidget(self.btn_generate_report)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.report_progress = QProgressBar()
        self.report_progress.setRange(0, 100)
        self.report_progress.setValue(0)
        lay.addWidget(self.report_progress)
        self.report_log = QLabel("")
        self.report_log.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(self.report_log)
        lay.addStretch()
        return page

    def _choose_report_location(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", "QC_Report.pdf", "PDF files (*.pdf)")
        if path:
            self.report_path_edit.setText(path)

    def _generate_report(self) -> None:
        if not self.current_session_id:
            QMessageBox.warning(self, "No Session", "Please import and analyze a dataset first.")
            return
        output_path = self.report_path_edit.text()
        if output_path == "No report path selected" or not output_path:
            QMessageBox.warning(self, "No Location", "Please choose a report location.")
            return

        self.btn_generate_report.setEnabled(False)
        self.report_progress.setValue(0)
        self.report_log.setText("Generating report…")

        self.report_worker = ReportWorker(
            self.application.report_service, self.current_session_id, output_path
        )
        self.report_worker.result.connect(self._on_report_finished)
        self.report_worker.error.connect(self._on_report_error)
        self.report_worker.finished.connect(lambda: self.btn_generate_report.setEnabled(True))
        self.worker_manager.start(self.report_worker)

    def _on_report_finished(self, result: dict[str, Any]) -> None:
        self.report_progress.setValue(100)
        self.report_log.setText(f"Report saved: {result.get('file_reference', '')}")
        self.status_label.setText("Report generated")
        QMessageBox.information(self, "Report Generated", f"PDF report saved to:\n{result.get('file_reference', '')}")

    def _on_report_error(self, message: str) -> None:
        self.report_log.setText(f"Report failed: {message}")
        self.status_label.setText("Report failed")
        self.btn_generate_report.setEnabled(True)
        QMessageBox.critical(self, "Report Error", message)

    # ------------------------------------------------------------------ # pages: pacs / settings / about
    def _build_pacs_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel("PACS Connection (Orthanc)")
        title.setObjectName("title")
        sub = QLabel(
            "Optional PACS integration via Orthanc REST API (Workflow B). "
            "Connect to an Orthanc server, list studies/series, and download series for QC analysis."
        )
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)

        # Connection settings
        cfg = QFrame()
        cfg.setObjectName("card")
        clay = QVBoxLayout(cfg)
        clay.setContentsMargins(14, 14, 14, 14)
        clay.setSpacing(8)

        host_lay = QHBoxLayout()
        host_lay.addWidget(QLabel("Host:"))
        self.pacs_host = QLabel("http://localhost:8042")
        self.pacs_host.setStyleSheet(f"color: {TEXT}; padding: 6px; background: {CARD}; border: 1px solid #3d4858; border-radius: 4px;")
        self.pacs_host.setMinimumHeight(30)
        host_lay.addWidget(self.pacs_host)
        host_lay.addStretch()
        clay.addLayout(host_lay)

        cred_lay = QHBoxLayout()
        cred_lay.addWidget(QLabel("Username:"))
        self.pacs_user = QLineEdit()
        self.pacs_user.setPlaceholderText("optional")
        cred_lay.addWidget(self.pacs_user)
        cred_lay.addWidget(QLabel("Password:"))
        self.pacs_pass = QLineEdit()
        self.pacs_pass.setEchoMode(QLineEdit.Password)
        self.pacs_pass.setPlaceholderText("optional")
        cred_lay.addWidget(self.pacs_pass)
        clay.addLayout(cred_lay)

        btn_lay = QHBoxLayout()
        self.btn_pacs_connect = QPushButton("Connect / Test")
        self.btn_pacs_connect.setObjectName("primary")
        self.btn_pacs_connect.clicked.connect(self._pacs_connect)
        self.btn_pacs_refresh = QPushButton("Refresh Studies")
        self.btn_pacs_refresh.setObjectName("ghost")
        self.btn_pacs_refresh.clicked.connect(self._pacs_list_studies)
        self.btn_pacs_refresh.setEnabled(False)
        btn_lay.addWidget(self.btn_pacs_connect)
        btn_lay.addWidget(self.btn_pacs_refresh)
        btn_lay.addStretch()
        clay.addLayout(btn_lay)

        self.pacs_status = QLabel("Not connected")
        self.pacs_status.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        clay.addWidget(self.pacs_status)

        lay.addWidget(cfg)

        # Studies list
        lay.addWidget(QLabel("Studies on server:"))
        self.pacs_studies = QTableWidget(0, 6)
        self.pacs_studies.setHorizontalHeaderLabels(
            ["Study ID", "Patient ID", "Study Date", "Description", "Modality", "Series"]
        )
        self.pacs_studies.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pacs_studies.setSelectionBehavior(QTableWidget.SelectRows)
        self.pacs_studies.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pacs_studies.itemSelectionChanged.connect(self._pacs_on_study_selected)
        lay.addWidget(self.pacs_studies, stretch=1)

        # Series list
        lay.addWidget(QLabel("Series in selected study:"))
        self.pacs_series = QTableWidget(0, 5)
        self.pacs_series.setHorizontalHeaderLabels(
            ["Series ID", "Modality", "Description", "Series Number", "Instances"]
        )
        self.pacs_series.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pacs_series.setSelectionBehavior(QTableWidget.SelectRows)
        self.pacs_series.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pacs_series.itemSelectionChanged.connect(self._pacs_on_series_selected)
        lay.addWidget(self.pacs_series)

        # Download + analyze
        dload_lay = QHBoxLayout()
        self.pacs_download_dir = QLabel("No download folder")
        self.pacs_download_dir.setStyleSheet(f"color: {MUTED}; padding: 6px; background: {CARD}; border: 1px solid #3d4858; border-radius: 4px;")
        self.pacs_download_dir.setMinimumHeight(30)
        self.btn_pacs_choose_dir = QPushButton("Choose Folder…")
        self.btn_pacs_choose_dir.setObjectName("ghost")
        self.btn_pacs_choose_dir.clicked.connect(self._pacs_choose_download_dir)
        self.btn_pacs_download = QPushButton("Download Series")
        self.btn_pacs_download.setObjectName("primary")
        self.btn_pacs_download.clicked.connect(self._pacs_download_series)
        self.btn_pacs_download.setEnabled(False)
        dload_lay.addWidget(self.pacs_download_dir, stretch=1)
        dload_lay.addWidget(self.btn_pacs_choose_dir)
        dload_lay.addWidget(self.btn_pacs_download)
        dload_lay.addStretch()
        lay.addLayout(dload_lay)

        self.pacs_download_log = QLabel("")
        self.pacs_download_log.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(self.pacs_download_log)

        lay.addStretch()
        return page

    # ------------------------------------------------------------------ # PACS handlers
    def _pacs_connect(self) -> None:
        host = self.pacs_host.text().strip() or "http://localhost:8042"
        self.pacs_manager.configure_orthanc(
            host=host,
            username=self.pacs_user.text().strip() or None,
            password=self.pacs_pass.text().strip() or None,
        )
        self.btn_pacs_connect.setEnabled(False)
        self.pacs_status.setText("Connecting…")

        result = self.pacs_manager.test_connection()
        if result.get("ok"):
            self.pacs_status.setText(f"Connected to {host}")
            self.pacs_status.setStyleSheet("color: #6ecb6e; font-size: 12px;")
            self.btn_pacs_connect.setText("Connected")
            self.btn_pacs_connect.setEnabled(False)
            self.btn_pacs_refresh.setEnabled(True)
            info = result.get("server_info") or {}
            self.pacs_status.setText(
                f"Connected to {host} (Orthanc {info.get('Version', '?')})"
            )
        else:
            self.pacs_status.setText(f"Connection failed: {result.get('error', '')}")
            self.pacs_status.setStyleSheet("color: #f48771; font-size: 12px;")
            self.btn_pacs_connect.setEnabled(True)
        logger.info("PACS connect result: %s", result)

    def _pacs_list_studies(self) -> None:
        if not self.pacs_manager.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to Orthanc first.")
            return
        try:
            studies = self.pacs_manager.list_studies()
        except Exception as exc:
            logger.exception("Failed to list studies")
            QMessageBox.critical(self, "PACS Error", str(exc))
            return

        self.pacs_studies.setRowCount(0)
        self.pacs_series.setRowCount(0)
        for s in studies:
            row = self.pacs_studies.rowCount()
            self.pacs_studies.insertRow(row)
            vals = [
                str(s["id"]),
                str(s["patient_id"] or "-"),
                str(s["study_date"] or "-"),
                str(s["study_description"] or "-"),
                str(s["modality"] or "-"),
                str(s["series_count"]),
            ]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.pacs_studies.setItem(row, col, item)
        self.pacs_status.setText(f"{len(studies)} study(ies) found")

    def _pacs_on_study_selected(self) -> None:
        row = self.pacs_studies.currentRow()
        if row < 0:
            return
        study_id = self.pacs_studies.item(row, 0).text()
        self._pacs_load_series(study_id)

    def _pacs_load_series(self, study_id: str) -> None:
        if not self.pacs_manager.connected:
            return
        try:
            series = self.pacs_manager.list_series(study_id)
        except Exception as exc:
            logger.exception("Failed to list series")
            QMessageBox.critical(self, "PACS Error", str(exc))
            return

        self.pacs_series.setRowCount(0)
        self._selected_series_id = None
        for s in series:
            row = self.pacs_series.rowCount()
            self.pacs_series.insertRow(row)
            vals = [
                str(s["id"]),
                str(s["modality"] or "-"),
                str(s["series_description"] or "-"),
                str(s["series_number"] if s["series_number"] is not None else "-"),
                str(s["instance_count"]),
            ]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.pacs_series.setItem(row, col, item)
        self.pacs_status.setText(f"{len(series)} series found")

    def _pacs_on_series_selected(self) -> None:
        row = self.pacs_series.currentRow()
        if row < 0:
            self.btn_pacs_download.setEnabled(False)
            return
        self._selected_series_id = self.pacs_series.item(row, 0).text()
        self.btn_pacs_download.setEnabled(bool(self.pacs_download_dir.text() and self.pacs_download_dir.text() != "No download folder"))

    def _pacs_choose_download_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder")
        if folder:
            self.pacs_download_dir.setText(folder)
            self.btn_pacs_download.setEnabled(bool(self._selected_series_id))

    def _pacs_download_series(self) -> None:
        if not self._selected_series_id:
            QMessageBox.warning(self, "No Selection", "Please select a series.")
            return
        out_dir = self.pacs_download_dir.text()
        if out_dir == "No download folder" or not out_dir:
            QMessageBox.warning(self, "No Folder", "Please choose a download folder.")
            return

        self.btn_pacs_download.setEnabled(False)
        self.pacs_download_log.setText("Downloading series…")
        self.status_label.setText("Downloading series from Orthanc…")

        try:
            saved = self.pacs_manager.download_series(self._selected_series_id, out_dir)
        except Exception as exc:
            logger.exception("Failed to download series")
            self.pacs_download_log.setText(f"Download failed: {exc}")
            self.status_label.setText("Download failed")
            self.btn_pacs_download.setEnabled(True)
            QMessageBox.critical(self, "Download Error", str(exc))
            return

        self.pacs_download_log.setText(f"Downloaded {len(saved)} instance(s) to {out_dir}")
        self.status_label.setText("Download complete")

        # Offer to import the downloaded files into the local session
        reply = QMessageBox.question(
            self,
            "Import downloaded series?",
            f"Downloaded {len(saved)} instance(s). Import them into DICOM Ghost Hunter for QC analysis?",
        )
        if reply == QMessageBox.Yes:
            self.nav_list.setCurrentRow(1)  # import page
            self.path_edit.setText(out_dir)
            self.btn_import.setEnabled(True)
            self.status_label.setText("Ready to import downloaded series")

    # ------------------------------------------------------------------ #

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        title = QLabel("Settings")
        title.setObjectName("title")
        lay.addWidget(title)
        info = QLabel("Configuration is loaded from config/qc_rules.yaml and .env. Edit these files to adjust quality-control rules.")
        info.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        lay.addWidget(info)
        lay.addStretch()
        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        title = QLabel("About DICOM Ghost Hunter")
        title.setObjectName("title")
        lay.addWidget(title)
        text = QLabel(
            "DICOM Ghost Hunter v0.1.0\n\n"
            "An intelligent technical quality-control application for DICOM medical imaging examinations.\n\n"
            "Intended users: biomedical engineers, radiology technicians, medical physicists, and medical imaging researchers.\n\n"
            "IMPORTANT: This software provides preliminary technical quality-control indicators only. "
            "Severity levels represent technical priority, not clinical danger. No finding constitutes "
            "a confirmed medical error or a clinical diagnosis. All results require human verification. "
            "This application is not a medical device and is not certified for clinical use."
        )
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {TEXT}; font-size: 13px; line-height: 1.5;")
        lay.addWidget(text)
        lay.addStretch()
        return page

    def closeEvent(self, event) -> None:
        self.worker_manager.stop_all()
        try:
            self.application.shutdown()
        except Exception:
            logger.exception("Application shutdown failed")
        event.accept()
