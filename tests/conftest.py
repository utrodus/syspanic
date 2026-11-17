import gc
import os
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


def pytest_configure(config):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _destroy_leftover_widgets(app):
    # PySide's atexit sweep of wrappers surviving interpreter finalization can
    # double-delete QObjects (SIGSEGV/SIGABRT after the pass summary); destroy
    # test widgets deterministically while the QApplication is still alive.
    # processEvents() alone does not deliver DeferredDelete at loop level 0.
    gc.collect()
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    _destroy_leftover_widgets(app)


@pytest.fixture(autouse=True)
def _isolated_local_identity(monkeypatch):
    monkeypatch.setattr(
        "syspanic.report.markdown.local_identity_seeds",
        lambda: (("unit-host",), ("unit-user",)),
        raising=False,
    )


@pytest.fixture(scope="session")
def demo_report():
    from syspanic.collectors.demo import DEMO_CURRENT_BOOT_ID, DemoCollector
    from syspanic.diagnostics import engine

    bundle = DemoCollector().collect(DEMO_CURRENT_BOOT_ID)
    return engine.analyze(bundle, now=datetime(2026, 11, 16, 12, 0, tzinfo=UTC))


@pytest.fixture(scope="session")
def demo_previous_report():
    from syspanic.collectors.demo import DEMO_PREVIOUS_BOOT_ID, DemoCollector
    from syspanic.diagnostics import engine

    bundle = DemoCollector().collect(DEMO_PREVIOUS_BOOT_ID)
    return engine.analyze(bundle, now=datetime(2026, 11, 16, 12, 0, tzinfo=UTC))


@pytest.fixture(scope="session")
def empty_report():
    from rule_fixtures import make_bundle
    from syspanic.diagnostics import engine

    return engine.analyze(make_bundle([]), now=datetime(2026, 11, 16, 12, 0, tzinfo=UTC))
