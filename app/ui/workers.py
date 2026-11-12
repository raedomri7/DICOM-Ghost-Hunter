"""Background worker architecture using QThread and QRunnable.

All heavy work (DICOM import, QC analysis, PDF generation) runs off the GUI
thread. Results are delivered back through PyQt signals so the interface never
freezes. Long operations support progress reporting and cancellation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt5.QtCore import QObject, QRunnable, QThread, pyqtSignal, pyqtSlot

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class WorkerSignals(QObject):
    """Signals emitted by a background worker."""

    started = pyqtSignal()
    progress = pyqtSignal(int, str)  # percent, message
    result = pyqtSignal(object)
    error = pyqtSignal(str, str)  # error message, traceback-ish
    finished = pyqtSignal()


class Worker(QRunnable):
    """Generic QRunnable that executes a callable in the thread pool."""

    def __init__(self, fn: Callable[..., Any], *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @pyqtSlot()
    def run(self) -> None:
        self.signals.started.emit()
        try:
            if self._cancelled:
                return
            result = self.fn(*self.args, **self.kwargs)
            if not self._cancelled:
                self.signals.result.emit(result)
        except Exception as exc:
            logger.exception("Worker error")
            self.signals.error.emit(str(exc), "")
        finally:
            if not self._cancelled:
                self.signals.finished.emit()


class ImportWorker(QObject):
    """Worker that imports a DICOM folder via ImportService."""

    started = pyqtSignal()
    progress = pyqtSignal(int, str)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, import_service: Any, folder_path: str) -> None:
        super().__init__()
        self.import_service = import_service
        self.folder_path = folder_path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @pyqtSlot()
    def run(self) -> None:
        self.started.emit()
        try:
            result = self.import_service.import_path(self.folder_path)
            if not self._cancelled:
                self.result.emit(result)
        except Exception as exc:
            logger.exception("Import worker failed")
            self.error.emit(str(exc))
        finally:
            if not self._cancelled:
                self.finished.emit()


class AnalysisWorker(QObject):
    """Worker that runs the QC pipeline for one or more series."""

    started = pyqtSignal()
    progress = pyqtSignal(int, str)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        analysis_service: Any,
        session_id: str,
        series_items: list[dict[str, Any]],
    ) -> None:
        super().__init__()
        self.analysis_service = analysis_service
        self.session_id = session_id
        self.series_items = series_items
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @pyqtSlot()
    def run(self) -> None:
        self.started.emit()
        all_results: list[dict[str, Any]] = []
        total = max(len(self.series_items), 1)
        try:
            for idx, item in enumerate(self.series_items):
                if self._cancelled:
                    break
                pct = int((idx / total) * 100)
                self.progress.emit(pct, f"Analyzing {item.get('label', 'series')}...")
                result = self.analysis_service.analyze_series(
                    session_id=self.session_id,
                    examination_id=item.get("examination_id"),
                    series_id=item.get("series_id"),
                    instances=item.get("instances", []),
                    modality=item.get("modality"),
                    rules=item.get("rules"),
                )
                all_results.append(result)
            if not self._cancelled:
                self.progress.emit(100, "Analysis complete")
                self.result.emit(
                    {
                        "session_id": self.session_id,
                        "series_results": all_results,
                    }
                )
        except Exception as exc:
            logger.exception("Analysis worker failed")
            self.error.emit(str(exc))
        finally:
            if not self._cancelled:
                self.finished.emit()


class ReportWorker(QObject):
    """Worker that generates a PDF report."""

    started = pyqtSignal()
    progress = pyqtSignal(int, str)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, report_service: Any, session_id: str, output_path: str) -> None:
        super().__init__()
        self.report_service = report_service
        self.session_id = session_id
        self.output_path = output_path

    @pyqtSlot()
    def run(self) -> None:
        self.started.emit()
        try:
            result = self.report_service.generate_pdf_report(self.session_id, self.output_path)
            self.result.emit(result)
        except Exception as exc:
            logger.exception("Report worker failed")
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class WorkerManager:
    """Manages QThread lifetimes for move-to-thread workers."""

    def __init__(self) -> None:
        self.threads: list[QThread] = []

    def start(self, worker: QObject) -> QThread:
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.threads.append(thread)
        thread.start()
        return thread

    def stop_all(self) -> None:
        for thread in self.threads:
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)
