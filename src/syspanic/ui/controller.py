"""AnalysisController — single-flight QThread ownership, cancel, stale detection."""

import threading

from PySide6.QtCore import QObject, Qt, QThread, Signal

from syspanic.ui.worker import CollectionWorker


class AnalysisController(QObject):
    stateChanged = Signal(str)
    progress = Signal(str, int, int)
    bootsReady = Signal(object)
    reportReady = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    closeReady = Signal()

    def __init__(self, *, demo=False, worker_factory=None, parent=None):
        super().__init__(parent)
        self._demo = demo
        self._factory = worker_factory or (
            lambda mode, boot, *, demo, cancel: CollectionWorker(
                mode, boot, demo=demo, cancel=cancel
            )
        )
        self._thread: QThread | None = None
        self._worker = None
        self._running = False
        self._closing = False
        self._cancel = threading.Event()
        self.state = "idle"
        self.report = None
        self.boots: tuple = ()
        self.analyzed_boot_id: str | None = None

    @property
    def running(self) -> bool:
        return self._running

    def is_stale(self, selected_boot_id: str | None) -> bool:
        return self.report is not None and selected_boot_id != self.analyzed_boot_id

    def refresh_boots(self) -> bool:
        return self._start("boots", None)

    def analyze(self, boot) -> bool:
        return self._start("analyze", boot)

    def cancel(self) -> None:
        self._cancel.set()

    def request_close(self) -> bool:
        self._closing = True
        if not self._running:
            return True
        self.cancel()
        return False

    def _start(self, mode, boot) -> bool:
        if self._running:
            return False
        self._cancel = threading.Event()
        self._thread = QThread()
        self._worker = self._factory(mode, boot, demo=self._demo, cancel=self._cancel)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self._on_report)
        self._worker.bootsFinished.connect(self._on_boots)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        direct = Qt.ConnectionType.DirectConnection
        self._worker.finished.connect(self._thread.quit, direct)
        self._worker.bootsFinished.connect(self._thread.quit, direct)
        self._worker.failed.connect(self._thread.quit, direct)
        self._worker.cancelled.connect(self._thread.quit, direct)
        self._thread.finished.connect(self._on_thread_finished)
        self._running = True
        self._set_state("collecting")
        self._thread.start()
        return True

    def _set_state(self, state: str) -> None:
        self.state = state
        self.stateChanged.emit(state)

    def _on_report(self, report) -> None:
        self.report = report
        self.analyzed_boot_id = report.boot.boot_id
        self._set_state("ready")
        self.reportReady.emit(report)

    def _on_boots(self, boots) -> None:
        self.boots = tuple(boots)
        self._set_state("idle")
        self.bootsReady.emit(self.boots)

    def _on_failed(self, message: str) -> None:
        self._set_state("error")
        self.failed.emit(message)

    def _on_cancelled(self) -> None:
        self._set_state("cancelled")
        self.cancelled.emit()

    def _on_thread_finished(self) -> None:
        self._running = False
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        if self._closing:
            self.closeReady.emit()
