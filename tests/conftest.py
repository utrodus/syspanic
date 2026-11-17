import os
from datetime import UTC, datetime

import pytest
from PySide6.QtWidgets import QApplication


def pytest_configure(config):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


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
