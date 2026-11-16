"""End-to-end M0 QA: real CLI entry points and full app lifecycle, offscreen only."""

import os
import subprocess
import sys
import tempfile

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from syspanic.ui.main_window import MainWindow

DRIVER = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

real_exec = QApplication.exec

def exec_and_verify(self):
    wins = [w for w in self.topLevelWidgets() if w.isVisible()]
    assert len(wins) == 1, "expected exactly one visible top-level window"
    win = wins[0]
    assert win.windowTitle() == "SysPanic"
    assert win.nav.count() == 5 and win.stack.count() == 5
    for row in range(5):
        win.nav.setCurrentRow(row)
        assert win.stack.currentIndex() == row
    assert "Local only" in win.footer.text() and "v0.1.0" in win.footer.text()
    demo = "--demo" in sys.argv
    assert win.demo_banner.isVisible() == demo
    if demo:
        assert "DEMO DATA" in win.demo_banner.text()
    print("E2E_OK", win.windowTitle(), win.stack.count(), demo, flush=True)
    QTimer.singleShot(0, self.quit)
    return real_exec()

QApplication.exec = exec_and_verify

from syspanic.app import main

sys.exit(main(sys.argv[1:]))
"""


def run_app_offscreen(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = "src"
    with tempfile.TemporaryDirectory(prefix="syspanic-e2e-") as cfg:
        env["XDG_CONFIG_HOME"] = cfg
        return subprocess.run(
            [sys.executable, "-c", DRIVER, *args],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )


def test_cli_version_end_to_end():
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-m", "syspanic", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "SysPanic 0.1.0"


def test_cli_rejects_unknown_flag():
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-m", "syspanic", "--bogus"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=False,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_full_app_lifecycle_normal_mode():
    result = run_app_offscreen()
    assert result.returncode == 0, result.stderr
    assert "E2E_OK SysPanic 5 False" in result.stdout


def test_full_app_lifecycle_demo_mode():
    result = run_app_offscreen("--demo")
    assert result.returncode == 0, result.stderr
    assert "E2E_OK SysPanic 5 True" in result.stdout


@pytest.fixture
def window(qapp):
    win = MainWindow(demo=False)
    win.show()
    QApplication.processEvents()
    yield win
    win.close()


def test_ctrl_1_to_5_shortcuts_switch_pages(window):
    for row in range(5):
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_1 + row, Qt.KeyboardModifier.ControlModifier
        )
        QApplication.sendEvent(window, event)
        QApplication.processEvents()
        assert window.nav.currentRow() == row
        assert window.stack.currentIndex() == row


def test_resize_below_minimum_is_clamped(window):
    window.resize(800, 600)
    QApplication.processEvents()
    assert window.width() >= 1280
    assert window.height() >= 720


def test_close_hides_window(window):
    assert window.isVisible()
    window.close()
    QApplication.processEvents()
    assert not window.isVisible()
