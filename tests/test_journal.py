"""T-006 journal collection — docs/02 §8, plan §2. Injected fake runners only."""

import json
import threading
from datetime import UTC, datetime

import pytest

from syspanic.collectors import journal
from syspanic.collectors.base import CollectionContext
from syspanic.collectors.journal import (
    DMESG_ISO_ARGV,
    DMESG_PLAIN_ARGV,
    collect_journal,
    kernel_argv,
    system_argv,
)
from syspanic.collectors.runner import CommandResult
from syspanic.constants import (
    SOURCE_DMESG,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import BootInfo

CUR = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
PREV = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
T0_US = 1763280000000000


def jline(cursor, message, ts_us=T0_US, **extra):
    obj = {
        "__CURSOR": cursor,
        "__REALTIME_TIMESTAMP": str(ts_us),
        "MESSAGE": message,
        "PRIORITY": "6",
        **extra,
    }
    return json.dumps(obj)


def ok(stdout: bytes) -> CommandResult:
    return CommandResult(
        stdout=stdout, state=SourceState.AVAILABLE, exit_code=0, elapsed_ms=5.0, tail_reliable=True
    )


def failed(state: SourceState, detail: str = "") -> CommandResult:
    return CommandResult(
        stdout=b"",
        state=state,
        exit_code=1,
        elapsed_ms=5.0,
        stderr_detail=detail,
        tail_reliable=False,
    )


KERNEL_TEXT = (
    jline("k1", "Linux version 6.17.9-200.fc44.x86_64 (build@host) #1 SMP", _TRANSPORT="kernel")
    + "\n"
    + jline("k2", "gpu timeout", ts_us=T0_US + 1000, _TRANSPORT="kernel")
)
SYSTEM_TEXT = (
    jline("k1", "Linux version dup", _TRANSPORT="kernel")
    + "\n"
    + jline("s1", "systemd[1]: Started Session", ts_us=T0_US + 2000, SYSLOG_IDENTIFIER="systemd")
    + "\n"
    + jline("s2", "Reached target Shutdown", ts_us=T0_US + 3000)
)
DMESG_TEXT = b"2026-11-16T08:00:00,000000+00:00 Linux version 6.17.9\n"


class FakeRunner:
    def __init__(self, mapping):
        self.mapping = {tuple(k): v for k, v in mapping.items()}
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        return self.mapping.get(tuple(argv), failed(SourceState.ERROR))

    def argvs(self):
        return [c[0] for c in self.calls]


def default_mapping():
    return {
        tuple(kernel_argv(CUR)): ok(KERNEL_TEXT.encode()),
        tuple(system_argv(CUR)): ok(SYSTEM_TEXT.encode()),
        DMESG_ISO_ARGV: ok(DMESG_TEXT),
    }


def cov(result, source):
    return next(c for c in result.coverage if c.source == source)


def test_collect_success_dedupes_sorts_and_derives_boot():
    runner = FakeRunner(default_mapping())
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    entries = result.payload.entries
    assert [e.evidence_id for e in entries if e.source != SOURCE_DMESG] == [
        "JRN-000001",
        "JRN-000002",
        "JRN-000003",
        "JRN-000004",
    ]
    assert entries[0].message.startswith("Linux version")
    assert entries[0].source == SOURCE_JOURNAL_KERNEL
    assert result.payload.boot.kernel_release == "6.17.9-200.fc44.x86_64"
    assert result.payload.boot.first_entry == datetime.fromtimestamp(T0_US / 1e6, tz=UTC)
    assert result.payload.boot.last_entry == datetime.fromtimestamp(
        (T0_US + 3000) / 1e6, tz=UTC
    )
    assert cov(result, SOURCE_JOURNAL_KERNEL).state is SourceState.AVAILABLE
    assert cov(result, SOURCE_JOURNAL_KERNEL).tail_reliable is True
    assert cov(result, SOURCE_JOURNAL_SYSTEM).entry_count == 3
    assert cov(result, SOURCE_DMESG).state is SourceState.AVAILABLE
    assert any(e.evidence_id.startswith("DMS-") for e in entries)


def test_argv_is_fixed_and_undashed():
    assert kernel_argv(CUR) == [
        "journalctl",
        f"--boot={CUR}",
        "--kernel",
        "--output=json",
        "--no-pager",
        "-n",
        "20000",
    ]
    assert system_argv(CUR) == [
        "journalctl",
        f"--boot={CUR}",
        "--output=json",
        "--no-pager",
        "-n",
        "5000",
    ]


def test_entry_cap_sets_head_truncated_reliable_tail(monkeypatch):
    monkeypatch.setattr(journal, "KERNEL_ENTRY_CAP", 3)
    three = "\n".join(jline(f"k{i}", f"line {i}", ts_us=T0_US + i) for i in range(3))
    mapping = default_mapping()
    mapping[tuple(kernel_argv(CUR))] = ok(three.encode())
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    kc = cov(result, SOURCE_JOURNAL_KERNEL)
    assert kc.state is SourceState.TRUNCATED
    assert kc.head_truncated is True
    assert kc.tail_reliable is True
    assert kc.entry_count == 3
    assert runner.argvs()[0][-2:] == ["-n", "3"]


def test_byte_cap_sets_tail_unreliable():
    mapping = default_mapping()
    mapping[tuple(kernel_argv(CUR))] = CommandResult(
        stdout=KERNEL_TEXT.encode(),
        state=SourceState.TRUNCATED,
        exit_code=-15,
        elapsed_ms=5.0,
        truncated=True,
        tail_reliable=False,
    )
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    kc = cov(result, SOURCE_JOURNAL_KERNEL)
    assert kc.state is SourceState.TRUNCATED
    assert kc.head_truncated is False
    assert kc.tail_reliable is False
    assert kc.entry_count == 2


@pytest.mark.parametrize(
    "state", [SourceState.TIMEOUT, SourceState.PERMISSION_DENIED, SourceState.ERROR]
)
def test_failed_slice_maps_state_and_unreliable_tail(state):
    mapping = default_mapping()
    mapping[tuple(system_argv(CUR))] = failed(state, "denied")
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    sc = cov(result, SOURCE_JOURNAL_SYSTEM)
    assert sc.state is state
    assert sc.tail_reliable is False
    assert cov(result, SOURCE_JOURNAL_KERNEL).state is SourceState.AVAILABLE


def test_empty_kernel_slice_maps_empty():
    mapping = default_mapping()
    mapping[tuple(kernel_argv(CUR))] = CommandResult(
        stdout=b"", state=SourceState.EMPTY, exit_code=0, elapsed_ms=1.0, tail_reliable=True
    )
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    kc = cov(result, SOURCE_JOURNAL_KERNEL)
    assert kc.state is SourceState.EMPTY
    assert kc.tail_reliable is True
    assert kc.entry_count == 0


def test_historical_boot_dmesg_unsupported_and_not_run():
    mapping = {
        tuple(kernel_argv(PREV)): ok(KERNEL_TEXT.encode()),
        tuple(system_argv(PREV)): ok(SYSTEM_TEXT.encode()),
    }
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=-1, boot_id=PREV, is_current=False), runner=runner)
    result = collect_journal(ctx)
    dc = cov(result, SOURCE_DMESG)
    assert dc.state is SourceState.UNSUPPORTED
    assert dc.tail_reliable is False
    assert "current boot" in dc.detail
    assert list(DMESG_ISO_ARGV) not in runner.argvs()
    assert not any(e.source == SOURCE_DMESG for e in result.payload.entries)


def test_dmesg_unsupported_time_format_falls_back_to_plain():
    mapping = default_mapping()
    mapping[DMESG_ISO_ARGV] = failed(SourceState.ERROR, "dmesg: unsupported time format: iso")
    mapping[DMESG_PLAIN_ARGV] = ok(b"[    0.000000] Linux version 6.17.9\n")
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    dc = cov(result, SOURCE_DMESG)
    assert dc.state is SourceState.AVAILABLE
    assert "timestamp" in dc.detail
    dms = [e for e in result.payload.entries if e.source == SOURCE_DMESG]
    assert len(dms) == 1 and dms[0].timestamp is None
    assert list(DMESG_PLAIN_ARGV) in runner.argvs()


def test_dmesg_permission_denied_mapped():
    mapping = default_mapping()
    mapping[DMESG_ISO_ARGV] = failed(SourceState.PERMISSION_DENIED, "Operation not permitted")
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    dc = cov(result, SOURCE_DMESG)
    assert dc.state is SourceState.PERMISSION_DENIED
    assert dc.tail_reliable is False


def test_malformed_count_in_coverage_detail():
    mapping = default_mapping()
    mapping[tuple(kernel_argv(CUR))] = ok((KERNEL_TEXT + "\ngarbage line").encode())
    runner = FakeRunner(mapping)
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    assert "1 malformed" in cov(result, SOURCE_JOURNAL_KERNEL).detail


def test_cancel_event_passed_to_runner():
    runner = FakeRunner(default_mapping())
    cancel = threading.Event()
    ctx = CollectionContext(
        boot=BootInfo(index=0, boot_id=CUR, is_current=True), cancel=cancel, runner=runner
    )
    collect_journal(ctx)
    assert all(kwargs.get("cancel") is cancel for _, kwargs in runner.calls)


def test_provenance_preserved_in_evidence():
    runner = FakeRunner(default_mapping())
    ctx = CollectionContext(boot=BootInfo(index=0, boot_id=CUR, is_current=True), runner=runner)
    result = collect_journal(ctx)
    kernel_entries = [e for e in result.payload.entries if e.source == SOURCE_JOURNAL_KERNEL]
    assert kernel_entries[0].provenance["_TRANSPORT"] == "kernel"
    system_entries = [e for e in result.payload.entries if e.source == SOURCE_JOURNAL_SYSTEM]
    assert system_entries[0].identifier == "systemd"


def test_collect_requires_selected_boot():
    ctx = CollectionContext(boot=None, runner=FakeRunner({}))
    with pytest.raises(ValueError):
        collect_journal(ctx)
