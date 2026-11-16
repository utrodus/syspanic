"""T-003 domain contract: enums, dataclass invariants, validate_report().

Synthetic fixtures only. Contracts: docs/02-architecture.md §5,
docs/04-diagnostics.md §2/§4/§8/§9/§10.
"""

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from syspanic.domain.enums import (
    ArtifactAssociation,
    EvidenceStrength,
    Severity,
    SourceState,
    TimelineKind,
)
from syspanic.domain.models import (
    RULE_IDS,
    BootInfo,
    CollectionBundle,
    CrashArtifacts,
    EvidenceItem,
    EvidenceRef,
    Finding,
    IncidentReport,
    ReportValidationError,
    SourceCoverage,
    SystemProfile,
    TimelineEvent,
    validate_report,
)

BOOT_ID = "a1b2c3d4" * 4
T0 = datetime(2026, 11, 16, 8, 0, 0, tzinfo=UTC)


def make_boot(is_current=True):
    return BootInfo(
        index=0,
        boot_id=BOOT_ID,
        is_current=is_current,
        first_entry=T0,
        last_entry=T0 + timedelta(hours=1),
        kernel_release="6.17.0-100.fc44.x86_64",
    )


def make_evidence(eid="JRN-1", ts=T0, message="amdgpu: ring timeout", source="journal.kernel"):
    return EvidenceItem(
        evidence_id=eid,
        source=source,
        boot_id=BOOT_ID,
        message=message,
        timestamp=ts,
        priority=4,
        identifier="kernel",
        line_no=1,
        provenance={"_TRANSPORT": "kernel"},
    )


def make_finding(fid="F-1", rule_id="GPU-001", refs=None):
    return Finding(
        finding_id=fid,
        rule_id=rule_id,
        category="gpu",
        title="GPU ring timeout reported",
        severity=Severity.WARNING,
        strength=EvidenceStrength.DIRECT,
        evidence=(EvidenceRef("JRN-1", "amdgpu: ring timeout"),) if refs is None else refs,
        interpretation="The driver reported a ring timeout; a reset attempt is separate.",
        suspected_causes=("Driver hang (unconfirmed)",),
        unknowns=("What triggered the hang",),
        next_steps=("Review driver and firmware versions",),
        sources=("journal.kernel",),
    )


def make_coverage(source="journal.kernel", state=SourceState.AVAILABLE):
    return SourceCoverage(source=source, state=state, detail="collected", entry_count=1)


def make_report(findings=None, timeline=(), coverage=None, evidence_items=None, demo=False):
    return IncidentReport(
        boot=make_boot(),
        findings=(make_finding(),) if findings is None else findings,
        timeline=timeline,
        coverage=(make_coverage(),) if coverage is None else coverage,
        evidence=(make_evidence(),) if evidence_items is None else evidence_items,
        generated_at=T0,
        app_version="0.1.0",
        demo=demo,
    )


def make_bundle(demo=False):
    return CollectionBundle(
        boot=make_boot(),
        boots=(make_boot(),),
        entries=(make_evidence(),),
        coverage=(make_coverage(),),
        demo=demo,
    )


def test_enum_values_match_sot():
    assert {s.value for s in Severity} == {"critical", "warning", "notice", "info"}
    assert {s.value for s in EvidenceStrength} == {"circumstantial", "direct", "corroborated"}
    assert {s.value for s in SourceState} == {
        "available",
        "empty",
        "truncated",
        "permission_denied",
        "not_found",
        "unsupported",
        "timeout",
        "error",
    }
    assert {k.value for k in TimelineKind} == {
        "boot_start",
        "boot_end",
        "rule_match",
        "shutdown_marker",
        "transition",
    }
    assert {a.value for a in ArtifactAssociation} == {"matched", "possibly_related", "unknown"}
    assert isinstance(Severity.CRITICAL, str)
    assert Severity.CRITICAL == "critical"


def test_rule_catalog_has_29_unique_ids():
    expected = {
        "SHD-001", "SHD-002", "SHD-003", "SHD-004",
        "BOT-001",
        "PNC-001", "PNC-002", "PNC-003", "PNC-004",
        "MCE-001", "MCE-002",
        "GPU-001", "GPU-002", "GPU-003", "GPU-004",
        "MEM-001", "MEM-002",
        "PCI-001", "PCI-002", "PCI-003",
        "STO-001", "STO-002", "STO-003",
        "THM-001", "THM-002",
        "ART-001", "ART-002", "ART-003",
        "KRN-001",
    }
    assert set(RULE_IDS) == expected
    assert len(RULE_IDS) == 29


@pytest.mark.parametrize(
    "bad",
    ["A1B2C3D4" * 4, "a" * 31, "a" * 33, "g" * 32, "", BOOT_ID[:8] + "-" + BOOT_ID[8:]],
)
def test_boot_info_rejects_invalid_boot_id(bad):
    with pytest.raises(ValueError):
        BootInfo(index=0, boot_id=bad, is_current=False)


def test_boot_info_accepts_32_lowercase_hex():
    assert make_boot().boot_id == BOOT_ID


def test_models_are_frozen():
    item = make_evidence()
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.message = "changed"
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_finding().title = "changed"


@pytest.mark.parametrize(
    "state", [SourceState.TIMEOUT, SourceState.PERMISSION_DENIED, SourceState.ERROR]
)
def test_unreliable_tail_states_reject_reliable_flag(state):
    with pytest.raises(ValueError):
        SourceCoverage(source="dmesg", state=state, tail_reliable=True)
    assert SourceCoverage(source="dmesg", state=state, tail_reliable=False).tail_reliable is False


def test_head_truncation_preserves_reliable_tail():
    cov = SourceCoverage(
        source="journal.kernel",
        state=SourceState.TRUNCATED,
        head_truncated=True,
        tail_reliable=True,
    )
    assert cov.head_truncated is True and cov.tail_reliable is True


def test_system_profile_has_no_identifier_fields():
    names = {f.name for f in dataclasses.fields(SystemProfile)}
    assert not any("serial" in n or "uuid" in n or "machine_id" in n for n in names)
    assert "collected_at" in names
    profile = SystemProfile(
        os_name="Fedora Linux",
        os_version_id="44",
        kernel="6.17.0",
        arch="x86_64",
        cpu_model="Synthetic CPU",
        cpu_cores=8,
        mem_total_kib=16_000_000,
        collected_at=T0,
    )
    assert profile.collected_at == T0
    with pytest.raises(TypeError):
        SystemProfile(
            os_name="Fedora Linux",
            os_version_id="44",
            kernel="6.17.0",
            arch="x86_64",
            cpu_model="Synthetic CPU",
            cpu_cores=8,
            mem_total_kib=16_000_000,
        )


def test_artifact_and_bundle_defaults():
    arts = CrashArtifacts()
    assert arts.vmcore_files == () and arts.pstore_records == ()
    assert arts.crash_kernel_loaded is None
    bundle = make_bundle()
    assert bundle.demo is False and bundle.hostname_hint is None and bundle.issues == ()


def test_valid_report_passes():
    assert validate_report(make_report()) is None


def test_valid_report_with_timeline_and_bundle_passes():
    events = (
        TimelineEvent(T0, TimelineKind.BOOT_START, "Boot started", Severity.INFO, "BTM-1"),
        TimelineEvent(
            T0 + timedelta(minutes=5),
            TimelineKind.RULE_MATCH,
            "GPU timeout",
            Severity.WARNING,
            "JRN-1",
        ),
    )
    items = (
        make_evidence(),
        make_evidence("BTM-1", ts=None, message="boot 0", source="journal.boots"),
    )
    rep = make_report(timeline=events, evidence_items=items, demo=True)
    assert validate_report(rep, make_bundle(demo=True)) is None


def test_finding_without_evidence_rejected():
    rep = make_report(findings=(make_finding(refs=()),))
    with pytest.raises(ReportValidationError, match="F-1"):
        validate_report(rep)


def test_unknown_rule_rejected():
    rep = make_report(findings=(make_finding(rule_id="XXX-999"),))
    with pytest.raises(ReportValidationError, match="XXX-999"):
        validate_report(rep)


def test_duplicate_finding_ids_rejected():
    rep = make_report(findings=(make_finding(), make_finding()))
    with pytest.raises(ReportValidationError, match="F-1"):
        validate_report(rep)


def test_unresolvable_evidence_ref_rejected():
    rep = make_report(findings=(make_finding(refs=(EvidenceRef("JRN-999", "missing"),)),))
    with pytest.raises(ReportValidationError, match="JRN-999"):
        validate_report(rep)


def test_more_than_three_refs_rejected():
    refs = tuple(EvidenceRef("JRN-1", "line") for _ in range(4))
    rep = make_report(findings=(make_finding(refs=refs),))
    with pytest.raises(ReportValidationError):
        validate_report(rep)


@pytest.mark.parametrize("excerpt", ["l1\nl2\nl3\nl4", "x" * 301, "ok\n" + "y" * 301])
def test_excerpt_bounds_rejected(excerpt):
    rep = make_report(findings=(make_finding(refs=(EvidenceRef("JRN-1", excerpt),)),))
    with pytest.raises(ReportValidationError):
        validate_report(rep)


def test_excerpt_at_bounds_passes():
    excerpt = "\n".join(["z" * 300] * 3)
    rep = make_report(findings=(make_finding(refs=(EvidenceRef("JRN-1", excerpt),)),))
    assert validate_report(rep) is None


@pytest.mark.parametrize(
    "term",
    [
        "defective", "broken", "faulty", "hardware failure", "PSU failure",
        "power supply failure", "confirmed cause", "100%", "guaranteed",
        "must replace", "certainly",
    ],
)
def test_banned_terms_rejected(term):
    base = make_finding()
    bad = dataclasses.replace(base, interpretation=f"The component is {term}.")
    rep = make_report(findings=(bad,))
    with pytest.raises(ReportValidationError):
        validate_report(rep)


def test_banned_term_scan_is_case_insensitive():
    bad = dataclasses.replace(make_finding(), title="DEFECTIVE motherboard")
    with pytest.raises(ReportValidationError):
        validate_report(make_report(findings=(bad,)))


def test_unsorted_timeline_rejected():
    events = (
        TimelineEvent(
            T0 + timedelta(minutes=5),
            TimelineKind.RULE_MATCH,
            "later",
            Severity.WARNING,
            "JRN-1",
        ),
        TimelineEvent(T0, TimelineKind.BOOT_START, "earlier", Severity.INFO, "JRN-1"),
    )
    with pytest.raises(ReportValidationError, match="timeline"):
        validate_report(make_report(timeline=events))


def test_timeline_equal_timestamps_allowed():
    events = (
        TimelineEvent(T0, TimelineKind.BOOT_START, "boot", Severity.INFO, "JRN-1"),
        TimelineEvent(T0, TimelineKind.RULE_MATCH, "match", Severity.WARNING, "JRN-1"),
    )
    assert validate_report(make_report(timeline=events)) is None


def test_timeline_over_cap_rejected():
    events = tuple(
        TimelineEvent(
            T0 + timedelta(seconds=i), TimelineKind.RULE_MATCH, f"e{i}", Severity.INFO, "JRN-1"
        )
        for i in range(201)
    )
    with pytest.raises(ReportValidationError, match="200"):
        validate_report(make_report(timeline=events))


def test_duplicate_timeline_events_rejected():
    event = TimelineEvent(T0, TimelineKind.BOOT_START, "boot", Severity.INFO, "JRN-1")
    with pytest.raises(ReportValidationError):
        validate_report(make_report(timeline=(event, event)))


def test_timeline_unresolvable_evidence_rejected():
    event = TimelineEvent(T0, TimelineKind.BOOT_START, "boot", Severity.INFO, "BTM-9")
    with pytest.raises(ReportValidationError, match="BTM-9"):
        validate_report(make_report(timeline=(event,)))


def test_duplicate_coverage_sources_rejected():
    rep = make_report(coverage=(make_coverage(), make_coverage()))
    with pytest.raises(ReportValidationError, match="journal.kernel"):
        validate_report(rep)


def test_demo_flag_mismatch_rejected():
    with pytest.raises(ReportValidationError, match="demo"):
        validate_report(make_report(demo=False), make_bundle(demo=True))
    assert validate_report(make_report(demo=True), make_bundle(demo=True)) is None


def test_duplicate_evidence_ids_rejected():
    rep = make_report(evidence_items=(make_evidence(), make_evidence()))
    with pytest.raises(ReportValidationError, match="JRN-1"):
        validate_report(rep)


def test_invalid_evidence_prefix_rejected():
    rep = make_report(evidence_items=(make_evidence("LOG-1"),))
    with pytest.raises(ReportValidationError, match="LOG-1"):
        validate_report(rep)


def test_journal_item_requires_timestamp():
    rep = make_report(evidence_items=(make_evidence(ts=None),))
    with pytest.raises(ReportValidationError, match="JRN-1"):
        validate_report(rep)


@pytest.mark.parametrize("eid", ["DMS-1", "VMD-1", "PST-1", "BTM-1", "AFM-1"])
def test_non_journal_items_may_omit_timestamp(eid):
    item = make_evidence(eid, ts=None, message="metadata", source="crash.vmcore_dmesg")
    rep = make_report(findings=(), evidence_items=(item,))
    assert validate_report(rep) is None


def test_overlong_message_rejected():
    rep = make_report(evidence_items=(make_evidence(message="m" * 1001),))
    with pytest.raises(ReportValidationError):
        validate_report(rep)


@pytest.mark.parametrize("char", ["\x00", "\x1b", "\x7f", "\r"])
def test_message_control_characters_rejected(char):
    rep = make_report(evidence_items=(make_evidence(message=f"a{char}b"),))
    with pytest.raises(ReportValidationError):
        validate_report(rep)


def test_domain_package_is_qt_free():
    domain_dir = Path(__file__).resolve().parent.parent / "src" / "syspanic" / "domain"
    for py in domain_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "PySide6" not in text and "QtCore" not in text, py.name
