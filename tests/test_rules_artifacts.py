"""T-012: ART-001 core + deferred ART-002/003 tracking; association severity."""

from datetime import UTC, datetime

from rule_fixtures import BASE, entry, make_bundle
from syspanic.diagnostics.rules import artifacts as artifacts_rule
from syspanic.domain.enums import ArtifactAssociation, Severity
from syspanic.domain.models import ArtifactInfo, CrashArtifacts


def vmcore(association, *, path="/var/crash/127.0.0.1-2026-11-10-08:30:00/vmcore"):
    return ArtifactInfo(
        path=path,
        kind="vmcore",
        size_bytes=1024,
        readable=False,
        association=association,
        association_reason="test association reason",
        mtime=BASE,
        incident_dir="/var/crash/127.0.0.1-2026-11-10-08:30:00",
        note="binary dump; metadata only, never opened",
    )


def afm(record, index=0):
    return entry(
        f"{record.kind} {record.path} size={record.size_bytes} "
        f"association={record.association.value}",
        index,
        source="crash.vmcore",
        transport=None,
        prefix="AFM-",
    )


def test_art001_matched_critical():
    record = vmcore(ArtifactAssociation.MATCHED)
    bundle = make_bundle([afm(record)], artifacts=CrashArtifacts(vmcore_files=(record,)))
    findings = artifacts_rule.evaluate(bundle)
    finding = next(f for f in findings if f.rule_id == "ART-001")
    assert finding.severity is Severity.CRITICAL
    assert "test association reason" in finding.interpretation


def test_art001_possibly_related_warning():
    record = vmcore(ArtifactAssociation.POSSIBLY_RELATED)
    bundle = make_bundle([afm(record)], artifacts=CrashArtifacts(vmcore_files=(record,)))
    finding = artifacts_rule.evaluate(bundle)[0]
    assert finding.severity is Severity.WARNING


def test_art001_unknown_notice():
    record = vmcore(ArtifactAssociation.UNKNOWN)
    bundle = make_bundle([afm(record)], artifacts=CrashArtifacts(vmcore_files=(record,)))
    finding = artifacts_rule.evaluate(bundle)[0]
    assert finding.severity is Severity.NOTICE


def test_art001_best_association_wins():
    matched = vmcore(ArtifactAssociation.MATCHED)
    unknown = vmcore(ArtifactAssociation.UNKNOWN, path="/var/crash/vmcore")
    bundle = make_bundle(
        [afm(matched, 0), afm(unknown, 1)],
        artifacts=CrashArtifacts(vmcore_files=(unknown, matched)),
    )
    finding = artifacts_rule.evaluate(bundle)[0]
    assert finding.severity is Severity.CRITICAL


def test_art001_no_vmcore_no_finding():
    bundle = make_bundle([], artifacts=CrashArtifacts())
    assert artifacts_rule.evaluate(bundle) == ()


def test_art001_requires_afm_evidence():
    record = vmcore(ArtifactAssociation.MATCHED)
    bundle = make_bundle([], artifacts=CrashArtifacts(vmcore_files=(record,)))
    assert artifacts_rule.evaluate(bundle) == ()


def test_art001_never_reads_binary_content():
    record = vmcore(ArtifactAssociation.MATCHED)
    bundle = make_bundle([afm(record)], artifacts=CrashArtifacts(vmcore_files=(record,)))
    finding = artifacts_rule.evaluate(bundle)[0]
    assert all(ref.excerpt.startswith("vmcore ") for ref in finding.evidence)
    assert "binary" in finding.interpretation.lower()


def test_deferred_art_rules_not_evaluated():
    from syspanic.diagnostics import registry

    assert frozenset({"ART-002", "ART-003"}) == registry.DEFERRED_RULE_IDS
    record = vmcore(ArtifactAssociation.MATCHED)
    dmesg_record = ArtifactInfo(
        path="/var/crash/inc/vmcore-dmesg.txt",
        kind="vmcore-dmesg",
        size_bytes=100,
        readable=True,
        association=ArtifactAssociation.MATCHED,
        association_reason="boot ID in text",
        mtime=datetime(2026, 11, 10, 8, 30, tzinfo=UTC),
    )
    vmd = entry(
        "Kernel panic - not syncing: Fatal exception",
        0,
        source="crash.vmcore_dmesg",
        transport=None,
        prefix="VMD-",
    )
    bundle = make_bundle(
        [afm(record), vmd],
        artifacts=CrashArtifacts(vmcore_files=(record,), vmcore_dmesg=(dmesg_record,)),
    )
    findings = artifacts_rule.evaluate(bundle)
    assert {f.rule_id for f in findings} == {"ART-001"}
