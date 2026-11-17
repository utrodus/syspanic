"""T-013: timeline derivation — kinds, ordering, dedupe, cap, boot isolation."""

from datetime import timedelta

from rule_fixtures import BASE, BOOT_ID, entry, make_boot, make_bundle
from syspanic.constants import SOURCE_JOURNAL_BOOTS, SOURCE_JOURNAL_SYSTEM
from syspanic.diagnostics import engine
from syspanic.diagnostics.timeline import build_timeline
from syspanic.domain.enums import Severity, TimelineKind
from syspanic.domain.models import MAX_TIMELINE_EVENTS


def test_boot_boundaries_from_btm():
    boot = make_boot()
    btm = entry(
        f"boot index -1 id {BOOT_ID}",
        0,
        source=SOURCE_JOURNAL_BOOTS,
        transport=None,
        prefix="BTM-",
    )
    bundle = make_bundle([btm], boot=boot)
    events = build_timeline(bundle, ())
    kinds = [e.kind for e in events]
    assert TimelineKind.BOOT_START in kinds
    assert TimelineKind.BOOT_END in kinds
    assert all(e.evidence_id == "BTM-000000" for e in events)


def test_current_boot_has_no_boot_end():
    boot = make_boot(index=0, is_current=True)
    btm = entry(
        f"boot index 0 id {BOOT_ID}",
        0,
        source=SOURCE_JOURNAL_BOOTS,
        transport=None,
        prefix="BTM-",
    )
    events = build_timeline(make_bundle([btm], boot=boot), ())
    assert TimelineKind.BOOT_END not in [e.kind for e in events]


def test_rule_match_events_reference_first_evidence():
    entries = [entry("Kernel panic - not syncing: Fatal exception", 0)]
    bundle = make_bundle(entries)
    report = engine.analyze(bundle)
    rule_events = [e for e in report.timeline if e.kind is TimelineKind.RULE_MATCH]
    assert rule_events
    panic_event = next(e for e in rule_events if "PNC-001" in e.summary)
    assert panic_event.evidence_id == "JRN-000000"
    assert panic_event.severity is Severity.CRITICAL


def test_shutdown_marker_event():
    entries = [
        entry(
            "systemd-shutdown[1]: Powering off.",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="journal",
            extra={"_SYSTEMD_UNIT": "systemd-shutdown.service"},
        )
    ]
    events = build_timeline(make_bundle(entries), ())
    marker_events = [e for e in events if e.kind is TimelineKind.SHUTDOWN_MARKER]
    assert len(marker_events) == 1
    assert marker_events[0].evidence_id == "JRN-000000"


def test_kexec_transition_event():
    entries = [entry("kexec_core: Starting new kernel", 0)]
    events = build_timeline(make_bundle(entries), ())
    assert any(e.kind is TimelineKind.TRANSITION for e in events)


def test_sorted_ascending_and_deduped():
    entries = [
        entry("Oops: 0000 [#1] SMP", 2),
        entry("Kernel panic - not syncing: Fatal exception", 1),
        entry("amdgpu 0000:0a:00.0: amdgpu: ring gfx timeout", 0),
    ]
    bundle = make_bundle(entries)
    report = engine.analyze(bundle)
    stamps = [e.timestamp for e in report.timeline]
    assert stamps == sorted(stamps)
    keys = [(e.timestamp, e.kind, e.evidence_id) for e in report.timeline]
    assert len(keys) == len(set(keys))


def test_artifact_mtimes_not_on_timeline():
    from datetime import UTC, datetime

    from syspanic.domain.enums import ArtifactAssociation
    from syspanic.domain.models import ArtifactInfo, CrashArtifacts

    record = ArtifactInfo(
        path="/var/crash/vmcore",
        kind="vmcore",
        size_bytes=8,
        readable=False,
        association=ArtifactAssociation.UNKNOWN,
        association_reason="none",
        mtime=datetime(2026, 11, 10, 8, 30, tzinfo=UTC),
    )
    afm = entry(
        "vmcore /var/crash/vmcore size=8 association=unknown",
        0,
        source="crash.vmcore",
        transport=None,
        prefix="AFM-",
        timestamp=record.mtime,
    )
    bundle = make_bundle([afm], artifacts=CrashArtifacts(vmcore_files=(record,)))
    report = engine.analyze(bundle)
    assert all(e.evidence_id != "AFM-000000" for e in report.timeline)


def test_cap_200_events():
    entries = [entry(f"Oops: 0000 [#{i}] SMP", i) for i in range(250)]
    entries += [
        entry(
            f"boot index -1 id {BOOT_ID}",
            300 + i,
            source=SOURCE_JOURNAL_BOOTS,
            transport=None,
            prefix="BTM-",
            timestamp=BASE + timedelta(seconds=300 + i),
        )
        for i in range(5)
    ]
    bundle = make_bundle(entries)
    report = engine.analyze(bundle)
    assert len(report.timeline) <= MAX_TIMELINE_EVENTS


def test_entries_without_timestamp_skipped():
    entries = [entry("Oops: 0000 [#1] SMP", 0, timestamp=None)]
    bundle = make_bundle(entries)
    report = engine.analyze(bundle)
    assert all(e.timestamp is not None for e in report.timeline)
