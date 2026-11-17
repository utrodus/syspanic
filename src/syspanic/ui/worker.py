"""CollectionWorker — owns no widgets; runs collection + analysis off the UI thread."""

import threading

from PySide6.QtCore import QObject, Signal

from syspanic.collectors.base import CollectionContext
from syspanic.collectors.boots import collect_boots
from syspanic.collectors.demo import DemoCollector
from syspanic.collectors.orchestrator import ALL_SOURCES, collect_bundle
from syspanic.collectors.runner import run
from syspanic.diagnostics import engine


class CollectionWorker(QObject):
    progress = Signal(str, int, int)
    finished = Signal(object)
    bootsFinished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, mode, boot, *, demo=False, cancel=None):
        super().__init__()
        self._mode = mode
        self._boot = boot
        self._demo = demo
        self._cancel = cancel if cancel is not None else threading.Event()

    def run(self):
        try:
            if self._demo:
                self._run_demo()
            elif self._mode == "boots":
                result = collect_boots(CollectionContext(cancel=self._cancel))
                if self._cancel.is_set():
                    self.cancelled.emit()
                    return
                self.bootsFinished.emit(result.payload)
            else:
                bundle = collect_bundle(
                    self._boot,
                    runner=run,
                    cancel=self._cancel,
                    progress=self.progress.emit,
                )
                if self._cancel.is_set():
                    self.cancelled.emit()
                    return
                self.finished.emit(engine.analyze(bundle))
        except Exception as exc:
            self.failed.emit(f"{exc.__class__.__name__}: {exc}")

    def _run_demo(self):
        collector = DemoCollector()
        if self._mode == "boots":
            payload = collector.boots()
        else:
            payload = engine.analyze(collector.collect(self._boot.boot_id))
        for index, source in enumerate(ALL_SOURCES, start=1):
            self.progress.emit(source, index, len(ALL_SOURCES))
        if self._cancel.is_set():
            self.cancelled.emit()
            return
        if self._mode == "boots":
            self.bootsFinished.emit(payload)
        else:
            self.finished.emit(payload)
