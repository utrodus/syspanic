"""T-004 bounded command runner contract — docs/02 §7, plan §2.

Child processes are `.venv/bin/python -c` (sys.executable under pytest), never a shell.
Synthetic programs only; no real host data.
"""

import dataclasses
import sys
import threading

import pytest

from syspanic.collectors.runner import CommandResult, run
from syspanic.domain.enums import SourceState

PY = sys.executable


def test_successful_command_returns_available():
    result = run([PY, "-c", "print('hello')"], timeout_s=10, max_bytes=4096)
    assert isinstance(result, CommandResult)
    assert result.state is SourceState.AVAILABLE
    assert result.stdout == b"hello\n"
    assert result.exit_code == 0
    assert result.tail_reliable is True
    assert result.truncated is False and result.cancelled is False
    assert result.elapsed_ms >= 0


def test_empty_stdout_maps_to_empty():
    result = run([PY, "-c", "pass"], timeout_s=10, max_bytes=4096)
    assert result.state is SourceState.EMPTY
    assert result.stdout == b""
    assert result.exit_code == 0
    assert result.tail_reliable is True


def test_missing_binary_maps_to_not_found():
    result = run(["syspanic-definitely-missing-binary-xyz"], timeout_s=5, max_bytes=1024)
    assert result.state is SourceState.NOT_FOUND
    assert result.exit_code is None
    assert result.tail_reliable is False


def test_permission_error_maps_to_permission_denied(tmp_path):
    script = tmp_path / "noexec.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o644)
    result = run([str(script)], timeout_s=5, max_bytes=1024)
    assert result.state is SourceState.PERMISSION_DENIED
    assert result.tail_reliable is False


def test_nonzero_exit_maps_to_error():
    result = run([PY, "-c", "import sys; sys.exit(3)"], timeout_s=10, max_bytes=1024)
    assert result.state is SourceState.ERROR
    assert result.exit_code == 3
    assert result.tail_reliable is False


@pytest.mark.parametrize(
    "hint",
    [
        "Permission denied",
        "Operation not permitted",
        "No journal files were opened due to insufficient permissions",
    ],
)
def test_stderr_permission_hint_maps_to_permission_denied(hint):
    code = f"import sys; sys.stderr.write({hint!r} + '\\n'); sys.exit(1)"
    result = run([PY, "-c", code], timeout_s=10, max_bytes=1024)
    assert result.state is SourceState.PERMISSION_DENIED
    assert result.tail_reliable is False


def test_timeout_kills_child_quickly():
    result = run([PY, "-c", "import time; time.sleep(30)"], timeout_s=0.5, max_bytes=1024)
    assert result.state is SourceState.TIMEOUT
    assert result.exit_code is not None
    assert result.tail_reliable is False
    assert result.elapsed_ms < 3000


def test_byte_cap_truncates_and_marks_tail_unreliable():
    result = run([PY, "-c", "print('x' * 200000)"], timeout_s=10, max_bytes=1000)
    assert result.state is SourceState.TRUNCATED
    assert len(result.stdout) <= 1000
    assert result.truncated is True
    assert result.tail_reliable is False


def test_stdout_bounded_exactly():
    result = run([PY, "-c", "print('y' * 100)"], timeout_s=10, max_bytes=10)
    assert len(result.stdout) == 10
    assert result.truncated is True


def test_cancel_stops_child():
    cancel = threading.Event()
    timer = threading.Timer(0.2, cancel.set)
    timer.start()
    try:
        result = run(
            [PY, "-c", "import time; time.sleep(30)"],
            timeout_s=10,
            max_bytes=1024,
            cancel=cancel,
        )
    finally:
        timer.cancel()
    assert result.cancelled is True
    assert result.exit_code is not None
    assert result.tail_reliable is False
    assert result.elapsed_ms < 3000


def test_cancel_before_spawn_skips_execution():
    cancel = threading.Event()
    cancel.set()
    result = run([PY, "-c", "print('never')"], timeout_s=5, max_bytes=1024, cancel=cancel)
    assert result.cancelled is True
    assert result.stdout == b""
    assert result.exit_code is None


def test_env_is_normalized():
    code = (
        "import os; print(os.environ['LC_ALL'], os.environ['LANG'], os.environ['NO_COLOR'], "
        "os.environ['SYSTEMD_PAGER'], os.environ['SYSTEMD_COLORS'], os.environ['PAGER'])"
    )
    result = run([PY, "-c", code], timeout_s=10, max_bytes=4096)
    assert result.state is SourceState.AVAILABLE
    assert result.stdout == b"C C 1 cat 0 cat\n"


def test_shell_string_argv_rejected():
    with pytest.raises(TypeError):
        run("echo hi", timeout_s=5, max_bytes=1024)
    with pytest.raises(ValueError):
        run([], timeout_s=5, max_bytes=1024)


@pytest.mark.parametrize("kwargs", [{"timeout_s": 0}, {"timeout_s": -1}, {"max_bytes": 0}])
def test_invalid_bounds_rejected(kwargs):
    args = {"timeout_s": 5, "max_bytes": 1024, **kwargs}
    with pytest.raises(ValueError):
        run([PY, "-c", "pass"], **args)


def test_stderr_detail_is_short_first_line():
    code = "import sys; sys.stderr.write('first line\\nsecond line\\n'); sys.exit(1)"
    result = run([PY, "-c", code], timeout_s=10, max_bytes=1024)
    assert result.stderr_detail == "first line"
    assert len(result.stderr_detail) <= 200


def test_large_stderr_does_not_deadlock():
    code = "import sys; sys.stderr.write('e' * 200000); print('ok')"
    result = run([PY, "-c", code], timeout_s=10, max_bytes=4096)
    assert result.state is SourceState.AVAILABLE
    assert result.stdout == b"ok\n"
    assert 0 < len(result.stderr_detail) <= 200


def test_shell_metacharacters_are_not_interpreted():
    result = run([PY, "-c", "print('; echo injected')"], timeout_s=10, max_bytes=4096)
    assert result.stdout == b"; echo injected\n"


def test_result_is_frozen():
    result = run([PY, "-c", "pass"], timeout_s=10, max_bytes=1024)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.state = SourceState.ERROR


def test_runner_module_is_qt_free():
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src" / "syspanic" / "collectors"
    text = (src / "runner.py").read_text(encoding="utf-8")
    assert "PySide6" not in text and "QtCore" not in text
    assert "shell=True" not in text
