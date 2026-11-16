import os

import pytest
from PySide6.QtWidgets import QApplication


def pytest_configure(config):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
