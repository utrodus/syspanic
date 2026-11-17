"""T-017: orchestrator — merge, duplicate rejection, failure isolation, budget, cancel."""

import threading
from datetime import UTC, datetime

import pytest

from rule_fixtures import BOOT_ID, entry, make_boot
from syspanic.collectors.base import CollectorResult
from syspanic.collectors.journal import JournalPayload
from syspanic.collectors.orchestrator import ALL_SOURCES, collect_bundle
from syspanic.domain.enums import ArtifactAssociation, SourceState
from syspanic.domain.models import (
    ArtifactInfo,
    CollectionIssue,
    CrashArtifacts,
    SourceCoverage,
    SystemProfile,
)


def ok(source, count=1):
    return SourceCoverage(source=source, state=SourceState.AVAILABLE, entry_count=count)


def boots_result(boots):
    return CollectorResult(payload=boots, coverage=(ok("journal.boots", len(boots)),))


def journal_result(boot):
    payload = JournalPayload(entries=(entry("kernel: Linux version 6.17.8", 0),), boot=boot)
    return CollectorResult(
        payload=payload,
        coverage=(ok("journal.kernel"), ok("journal.system"), ok("dmesg")),
    )


def system_result():
    profile = SystemProfile(
        os_name="Fedora",
        os_version_id="44",
        kernel="6.17.8",
        arch="x86_64",
        cpu_model="Test CPU",
        cpu_cores=4,
        mem_total_kib=1024,
        collected_at=datetime(2026, 11, 16, 12, 0, tzinfo=UTC),
    )
    return CollectorResult(
        payload=profile,
        coverage=tuple(ok(f"system.{name}") for name in ("os", "cpu", "memory", "gpu", "firmware")),
    )


def artifacts_result(boot_id):
    info = ArtifactInfo(
        path="/var/crash/vmcore",
        kind="vmcore",
        size_bytes=10,
        readable=False,
        association=ArtifactAssociation.UNKNOWN,
        association_reason="no boot identity evidence in artifact metadata",
    )
    from syspanic.collectors.artifacts import ArtifactCollection

    payload = ArtifactCollection(CrashArtifacts(vmcore_files=(info,)))
    return CollectorResult(
        payload=payload,
        coverage=tuple(
            ok(name)
            for name in ("crash.vmcore", "crash.vmcore_dmesg", "crash.pstore", "crash.kexec")
        ),
    )


def make_orchestrator(**overrides):
    boot = make_boot()
    params = {
        "boots_collector": lambda ctx: boots_result((boot,)),
        "journal_collector": lambda ctx: journal_result(boot),
        "system_collector": lambda ctx: system_result(),
        "artifacts_collector": lambda ctx: artifacts_result(boot.boot_id),
        "runner": lambda *a, **k: None,
        "read_boot_id": lambda: BOOT_ID,
    }
    params.update(overrides)
    return boot, params


def test_all_thirteen_sources_in_order():
    boot, params = make_orchestrator()
    bundle = collect_bundle(boot, **params)
    assert tuple(c.source for c in bundle.coverage) == ALL_SOURCES
    assert len(ALL_SOURCES) == 13


def test_bundle_assembles_entries_and_metadata():
    boot, params = make_orchestrator()
    bundle = collect_bundle(boot, **params)
    prefixes = {e.evidence_id.split("-")[0] for e in bundle.entries}
    assert {"JRN", "BTM", "AFM"} <= prefixes
    assert bundle.system is not None
    assert bundle.artifacts is not None
    assert bundle.boots == (boot,)


def test_journal_boot_window_applied():
    boot, params = make_orchestrator()
    updated = make_boot(first_entry=datetime(2026, 11, 10, 9, 0, tzinfo=UTC))
    params["journal_collector"] = lambda ctx: journal_result(updated)
    bundle = collect_bundle(boot, **params)
    assert bundle.boot.first_entry == updated.first_entry


def test_duplicate_source_rejected():
    boot, params = make_orchestrator()
    params["system_collector"] = lambda ctx: CollectorResult(
        payload=None, coverage=(ok("journal.kernel"),)
    )
    with pytest.raises(ValueError, match="duplicate"):
        collect_bundle(boot, **params)


def test_collector_failure_isolated():
    boot, params = make_orchestrator()

    def boom(ctx):
        raise RuntimeError("probe failed")

    params["system_collector"] = boom
    bundle = collect_bundle(boot, **params)
    states = {c.source: c.state for c in bundle.coverage}
    assert states["system.os"] is SourceState.ERROR
    assert states["system.firmware"] is SourceState.ERROR
    assert states["journal.kernel"] is SourceState.AVAILABLE
    assert bundle.system is None
    assert any(i.source == "system.os" for i in bundle.issues)


def test_budget_exceeded_marks_remaining_timeout():
    boot, params = make_orchestrator()
    clock = iter([0.0, 0.0, 200.0, 200.0, 200.0, 200.0, 200.0])
    params["monotonic"] = lambda: next(clock)
    bundle = collect_bundle(boot, budget_s=120.0, **params)
    states = {c.source: c.state for c in bundle.coverage}
    assert states["journal.boots"] is SourceState.AVAILABLE
    assert states["system.os"] is SourceState.TIMEOUT
    assert states["crash.kexec"] is SourceState.TIMEOUT
    assert len(bundle.coverage) == 13


def test_pre_cancelled_marks_all_sources():
    boot, params = make_orchestrator()
    cancel = threading.Event()
    cancel.set()
    bundle = collect_bundle(boot, cancel=cancel, **params)
    assert len(bundle.coverage) == 13
    assert all(c.state is SourceState.ERROR for c in bundle.coverage)
    assert all(not c.tail_reliable for c in bundle.coverage)


def test_progress_reports_thirteen_sources():
    boot, params = make_orchestrator()
    calls = []
    collect_bundle(boot, progress=lambda s, i, n: calls.append((s, i, n)), **params)
    assert [c[0] for c in calls] == list(ALL_SOURCES)
    assert [c[1] for c in calls] == list(range(1, 14))
    assert all(c[2] == 13 for c in calls)


def test_hostname_hint_from_provenance():
    boot, params = make_orchestrator()
    item = entry("kernel: msg", 0, extra={"_HOSTNAME": "probe-host"})
    params["journal_collector"] = lambda ctx: CollectorResult(
        payload=JournalPayload(entries=(item,), boot=boot),
        coverage=(ok("journal.kernel"), ok("journal.system"), ok("dmesg")),
    )
    bundle = collect_bundle(boot, **params)
    assert bundle.hostname_hint == "probe-host"


def test_issues_merged():
    boot, params = make_orchestrator()
    issue = CollectionIssue("crash.pstore", "permission denied reading pstore root")
    base = artifacts_result(boot.boot_id)
    params["artifacts_collector"] = lambda ctx: CollectorResult(
        payload=base.payload, coverage=base.coverage, issues=(issue,)
    )
    bundle = collect_bundle(boot, **params)
    assert issue in bundle.issues
