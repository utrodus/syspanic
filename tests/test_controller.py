"""T-017: AnalysisController — single-flight, cancel, stale, atomic apply, close safety."""

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from rule_fixtures import make_boot, make_bundle
from syspanic.collectors.demo import DEMO_CURRENT_BOOT_ID, DemoCollector
from syspanic.diagnostics import engine
from syspanic.domain.models import IncidentReport
from syspanic.ui.controller import AnalysisController

BOOT = make_boot()
OTHER_BOOT = make_boot(boot_id="22222222222222222222222222222222", index=-2)


def wait_until(qapp, predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FakeWorker(QObject):
    progress = Signal(str, int, int)
    finished = Signal(object)
    bootsFinished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, mode, boot, *, demo, cancel, behavior):
        super().__init__()
        self.mode = mode
        self.boot = boot
        self.cancel = cancel
        self.behavior = behavior

    def run(self):
        kind = self.behavior.get("kind", "report")
        gate = self.behavior.get("gate")
        respect_cancel = self.behavior.get("respect_cancel", True)
        if gate is not None:
            deadline = time.monotonic() + 5.0
            while not gate.is_set() and time.monotonic() < deadline:
                if respect_cancel and self.cancel.is_set():
                    self.cancelled.emit()
                    return
                gate.wait(timeout=0.02)
        if self.cancel.is_set() and respect_cancel:
            self.cancelled.emit()
            return
        if kind == "fail":
            self.failed.emit("RuntimeError: probe failed")
        elif kind == "boots":
            self.bootsFinished.emit((BOOT,))
        else:
            report = engine.analyze(make_bundle([]), now=None)
            self.finished.emit(report)


def make_controller(qapp, behavior, **kwargs):
    captured = {}

    def factory(mode, boot, *, demo, cancel):
        worker = FakeWorker(mode, boot, demo=demo, cancel=cancel, behavior=behavior)
        captured["worker"] = worker
        return worker

    controller = AnalysisController(worker_factory=factory, **kwargs)
    return controller, captured


def test_analyze_single_flight(qapp):
    gate = threading.Event()
    controller, _ = make_controller(qapp, {"kind": "report", "gate": gate})
    assert controller.analyze(BOOT) is True
    assert controller.running is True
    assert controller.analyze(BOOT) is False
    gate.set()
    assert wait_until(qapp, lambda: not controller.running)
    controller.request_close()


def test_report_applied_atomically_and_stale_detection(qapp):
    controller, _ = make_controller(qapp, {"kind": "report"})
    reports = []
    controller.reportReady.connect(reports.append)
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: reports)
    assert isinstance(reports[0], IncidentReport)
    assert controller.report is reports[0]
    assert controller.analyzed_boot_id == BOOT.boot_id
    assert controller.is_stale(BOOT.boot_id) is False
    assert controller.is_stale(OTHER_BOOT.boot_id) is True
    assert controller.state == "ready"


def test_cancel_acknowledged(qapp):
    gate = threading.Event()
    controller, _ = make_controller(qapp, {"kind": "report", "gate": gate})
    states = []
    controller.stateChanged.connect(states.append)
    controller.analyze(BOOT)
    controller.cancel()
    gate.set()
    assert wait_until(qapp, lambda: not controller.running)
    assert "cancelled" in states
    assert controller.report is None


def test_failed_state(qapp):
    controller, _ = make_controller(qapp, {"kind": "fail"})
    errors = []
    controller.failed.connect(errors.append)
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: errors and not controller.running)
    assert controller.state == "error"
    assert "probe failed" in errors[0]
    assert controller.running is False


def test_boots_mode(qapp):
    controller, _ = make_controller(qapp, {"kind": "boots"})
    received = []
    controller.bootsReady.connect(received.append)
    controller.refresh_boots()
    assert wait_until(qapp, lambda: received and not controller.running)
    assert received[0] == (BOOT,)
    assert controller.boots == (BOOT,)
    assert controller.running is False


def test_request_close_idle_returns_true(qapp):
    controller, _ = make_controller(qapp, {"kind": "report"})
    assert controller.request_close() is True


def test_request_close_cancels_and_defers_until_finished(qapp):
    gate = threading.Event()
    controller, _ = make_controller(qapp, {"kind": "report", "gate": gate})
    ready = []
    controller.closeReady.connect(lambda: ready.append(True))
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    assert controller.request_close() is False
    assert controller.running is True
    assert controller._cancel.is_set()
    gate.set()
    assert wait_until(qapp, lambda: ready)
    assert controller.running is False


def test_request_close_keeps_window_open_then_close_ready(qapp):
    gate = threading.Event()
    controller, _ = make_controller(
        qapp,
        {"kind": "report", "gate": gate, "respect_cancel": False},
    )
    ready = []
    controller.closeReady.connect(lambda: ready.append(True))
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    assert controller.request_close() is False
    assert controller.running is True
    gate.set()
    assert wait_until(qapp, lambda: ready)
    assert controller.running is False


def test_demo_end_to_end_real_worker(qapp):
    controller = AnalysisController(demo=True)
    reports = []
    controller.reportReady.connect(reports.append)
    boot = next(b for b in DemoCollector().boots() if b.boot_id == DEMO_CURRENT_BOOT_ID)
    assert controller.analyze(boot) is True
    assert wait_until(qapp, lambda: reports, timeout=10.0)
    report = reports[0]
    assert report.demo is True
    assert report.findings
    assert controller.state == "ready"
    assert controller.request_close() is True


def test_no_thread_terminate_in_ui_sources():
    root = Path(__file__).resolve().parents[1] / "src" / "syspanic" / "ui"
    for name in ("controller.py", "worker.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert ".terminate()" not in text
