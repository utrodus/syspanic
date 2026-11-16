"""Bounded subprocess execution per docs/02 §7.

Fixed argv commands only: shell=False, C locale, bounded reads, explicit
timeout, cooperative cancellation (terminate then kill). No temp files,
no writes, no network. stderr is reduced to a short user-safe detail.
"""

import contextlib
import os
import select
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass

from syspanic.domain.enums import SourceState

_READ_CHUNK = 65536
_STDERR_CAP = 4096
_DETAIL_CHARS = 200
_TERM_WAIT_S = 0.5
_KILL_WAIT_S = 1.0
_POLL_SLICE_S = 0.1

_ENV_OVERRIDES = {
    "LC_ALL": "C",
    "LANG": "C",
    "SYSTEMD_PAGER": "cat",
    "SYSTEMD_COLORS": "0",
    "PAGER": "cat",
    "NO_COLOR": "1",
}

_PERMISSION_HINTS = (
    "permission denied",
    "operation not permitted",
    "no journal files were opened due to insufficient permissions",
)


@dataclass(frozen=True)
class CommandResult:
    stdout: bytes
    state: SourceState
    exit_code: int | None
    elapsed_ms: float
    stderr_detail: str = ""
    truncated: bool = False
    cancelled: bool = False
    tail_reliable: bool = False


def _detail(stderr: bytes) -> str:
    text = stderr.decode("utf-8", errors="replace")
    line = text.split("\n", 1)[0]
    line = "".join(c for c in line if ord(c) >= 32 and ord(c) != 127)
    return line[:_DETAIL_CHARS].strip()


def _stop(proc: subprocess.Popen) -> int | None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=_TERM_WAIT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=_KILL_WAIT_S)
    return proc.returncode


def run(
    argv: Sequence[str],
    *,
    timeout_s: float,
    max_bytes: int,
    cancel: threading.Event | None = None,
) -> CommandResult:
    if isinstance(argv, (str, bytes)):
        raise TypeError("argv must be a sequence of argument strings, never a shell string")
    args = list(argv)
    if not args:
        raise ValueError("argv must not be empty")
    if timeout_s <= 0 or max_bytes <= 0:
        raise ValueError("timeout_s and max_bytes must be positive")

    started = time.monotonic()

    def result(
        state: SourceState,
        stdout: bytes = b"",
        exit_code: int | None = None,
        stderr: bytes = b"",
        truncated: bool = False,
        cancelled: bool = False,
    ) -> CommandResult:
        return CommandResult(
            stdout=stdout,
            state=state,
            exit_code=exit_code,
            elapsed_ms=(time.monotonic() - started) * 1000.0,
            stderr_detail=_detail(stderr),
            truncated=truncated,
            cancelled=cancelled,
            tail_reliable=state in (SourceState.AVAILABLE, SourceState.EMPTY) and not cancelled,
        )

    if cancel is not None and cancel.is_set():
        return result(SourceState.ERROR, cancelled=True)

    env = dict(os.environ)
    env.update(_ENV_OVERRIDES)
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=False,
            env=env,
        )
    except FileNotFoundError:
        return result(SourceState.NOT_FOUND)
    except PermissionError:
        return result(SourceState.PERMISSION_DENIED)
    except OSError as exc:
        return result(SourceState.ERROR, stderr=str(exc).encode("utf-8", errors="replace"))

    out_chunks: list[bytes] = []
    err_chunks: list[bytes] = []
    out_total = 0
    err_total = 0
    truncated = False
    cancelled = False
    timed_out = False
    deadline = started + timeout_s
    out_fd = proc.stdout.fileno()
    err_fd = proc.stderr.fileno()
    open_fds = {out_fd, err_fd}
    try:
        while open_fds:
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            if out_total >= max_bytes:
                truncated = True
                break
            ready, _, _ = select.select(sorted(open_fds), [], [], min(remaining, _POLL_SLICE_S))
            for fd in ready:
                chunk = os.read(fd, _READ_CHUNK)
                if not chunk:
                    open_fds.discard(fd)
                    continue
                if fd == out_fd:
                    take = min(len(chunk), max_bytes - out_total)
                    out_chunks.append(chunk[:take])
                    out_total += take
                elif err_total < _STDERR_CAP:
                    take = min(len(chunk), _STDERR_CAP - err_total)
                    err_chunks.append(chunk[:take])
                    err_total += take
            if out_total >= max_bytes:
                truncated = True
                break
    finally:
        exit_code = _stop(proc)
        proc.stdout.close()
        proc.stderr.close()

    stdout = b"".join(out_chunks)
    stderr = b"".join(err_chunks)
    if cancelled:
        return result(SourceState.ERROR, stdout, exit_code, stderr, truncated, True)
    if timed_out:
        return result(SourceState.TIMEOUT, stdout, exit_code, stderr, truncated)
    if truncated:
        return result(SourceState.TRUNCATED, stdout, exit_code, stderr, True)
    if exit_code == 0:
        state = SourceState.AVAILABLE if stdout else SourceState.EMPTY
        return result(state, stdout, exit_code, stderr)
    if any(hint in _detail(stderr).lower() for hint in _PERMISSION_HINTS):
        return result(SourceState.PERMISSION_DENIED, stdout, exit_code, stderr)
    return result(SourceState.ERROR, stdout, exit_code, stderr)
