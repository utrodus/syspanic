"""T-011: SHD-001..004 and BOT-001 — trusted markers, tail gating, absence."""


from rule_fixtures import (
    BASE,
    LATER_BOOT_ID,
    entry,
    filler,
    make_boot,
    make_bundle,
)
from syspanic.constants import SOURCE_JOURNAL_SYSTEM
from syspanic.diagnostics.rules import shutdown
from syspanic.domain.enums import EvidenceStrength, Severity, SourceState


def ids(findings):
    return {f.rule_id for f in findings}


def system_filler(count, start=100):
    return filler(count, start=start, source=SOURCE_JOURNAL_SYSTEM)


def test_shd001_trusted_systemd_marker():
    entries = [
        entry(
            "systemd-shutdown[1]: Powering off.",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="journal",
            extra={"_SYSTEMD_UNIT": "systemd-shutdown.service", "_COMM": "systemd-shutdown"},
        )
    ]
    findings = shutdown.evaluate(make_bundle(entries))
    assert "SHD-001" in ids(findings)
    finding = next(f for f in findings if f.rule_id == "SHD-001")
    assert finding.severity is Severity.INFO
    assert finding.strength is EvidenceStrength.DIRECT


def test_shd001_two_families_corroborated():
    entries = [
        entry(
            "systemd-shutdown[1]: Rebooting.",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="journal",
            extra={"_SYSTEMD_UNIT": "systemd-shutdown.service"},
        ),
        entry("reboot: Restarting system", index=1),
    ]
    findings = shutdown.evaluate(make_bundle(entries))
    finding = next(f for f in findings if f.rule_id == "SHD-001")
    assert finding.strength is EvidenceStrength.CORROBORATED


def test_shd001_journal_stopped_alone_not_clean_shutdown():
    entries = [
        entry(
            "Journal stopped",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="journal",
            extra={"_COMM": "systemd-journal"},
        )
    ]
    findings = shutdown.evaluate(make_bundle(entries))
    finding = next(f for f in findings if f.rule_id == "SHD-001")
    assert finding.strength is EvidenceStrength.DIRECT
    assert "does not prove" in finding.interpretation


def test_shd001_spoofed_identifier_ignored():
    entries = [
        entry(
            "reboot: Power down",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        ),
        entry(
            "systemd-shutdown[1]: Powering off.",
            index=1,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "systemd-shutdown"},
        ),
    ]
    assert "SHD-001" not in ids(shutdown.evaluate(make_bundle(entries)))


def test_shd001_userspace_marker_text_ignored():
    entries = [
        entry(
            "demo-app[1]: Powering off.",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"_COMM": "demo-app"},
        )
    ]
    assert "SHD-001" not in ids(shutdown.evaluate(make_bundle(entries)))


def test_shd002_absence_on_completed_boot():
    entries = filler(12) + system_filler(12)
    findings = shutdown.evaluate(make_bundle(entries))
    finding = next(f for f in findings if f.rule_id == "SHD-002")
    assert finding.severity is Severity.WARNING
    assert finding.strength is EvidenceStrength.CIRCUMSTANTIAL
    text = finding.interpretation.lower()
    for alternative in ("hard reset", "hang", "watchdog", "firmware", "power loss", "flush"):
        assert alternative in text


def test_shd002_never_on_current_boot():
    entries = filler(12) + system_filler(12)
    bundle = make_bundle(entries, boot=make_boot(index=0, is_current=True))
    assert "SHD-002" not in ids(shutdown.evaluate(bundle))


def test_shd002_suppressed_when_tail_unreliable():
    entries = filler(12) + system_filler(12)
    bundle = make_bundle(entries)
    from rule_fixtures import default_coverage

    cov = default_coverage(entries, kernel_tail=False)
    bundle = make_bundle(entries, coverage=cov)
    assert "SHD-002" not in ids(shutdown.evaluate(bundle))


def test_shd002_suppressed_when_source_empty():
    entries = filler(25)
    bundle = make_bundle(entries)
    assert "SHD-002" not in ids(shutdown.evaluate(bundle))


def test_shd002_suppressed_below_20_entries():
    entries = filler(8) + system_filler(8)
    assert "SHD-002" not in ids(shutdown.evaluate(make_bundle(entries)))


def test_shd002_head_truncation_alone_does_not_suppress():
    entries = filler(12) + system_filler(12)
    from rule_fixtures import default_coverage

    cov = default_coverage(entries, kernel_state=SourceState.TRUNCATED)
    bundle = make_bundle(entries, coverage=cov)
    assert "SHD-002" in ids(shutdown.evaluate(bundle))


def test_shd002_marker_outside_final_20_still_absent():
    marker = entry(
        "reboot: Power down",
        index=0,
        timestamp=BASE,
    )
    tail = filler(25, start=1) + system_filler(5, start=200)
    bundle = make_bundle([marker, *tail])
    assert "SHD-002" in ids(shutdown.evaluate(bundle))


def test_shd003_filesystem_recovery():
    for message in (
        "EXT4-fs (nvme0n1p3): recovery complete",
        "BTRFS info (device nvme0n1p3): replaying log",
        "XFS (nvme0n1p3): Starting log recovery",
    ):
        findings = shutdown.evaluate(make_bundle([entry(message, index=0)]))
        assert "SHD-003" in ids(findings)


def test_shd003_plain_mount_not_recovery():
    entries = [entry("EXT4-fs (nvme0n1p3): mounted filesystem with ordered data mode", index=0)]
    assert "SHD-003" not in ids(shutdown.evaluate(make_bundle(entries)))


def test_shd004_readonly_remount():
    entries = [entry("EXT4-fs (nvme0n1p3): Remounting filesystem read-only", index=0)]
    findings = shutdown.evaluate(make_bundle(entries))
    assert "SHD-004" in ids(findings)
    assert next(f for f in findings if f.rule_id == "SHD-004").severity is Severity.WARNING


def test_bot001_later_boot_exists():
    boot = make_boot()
    later = make_boot(index=0, boot_id=LATER_BOOT_ID, is_current=True)
    btm = entry(
        f"boot index 0 id {LATER_BOOT_ID}",
        index=0,
        source="journal.boots",
        transport=None,
        boot_id=LATER_BOOT_ID,
        prefix="BTM-",
    )
    bundle = make_bundle([btm], boot=boot, boots=(boot, later))
    findings = shutdown.evaluate(bundle)
    assert "BOT-001" in ids(findings)
    assert next(f for f in findings if f.rule_id == "BOT-001").severity is Severity.INFO


def test_bot001_not_for_latest_boot():
    boot = make_boot(index=0, is_current=True)
    bundle = make_bundle([], boot=boot, boots=(boot,))
    assert "BOT-001" not in ids(shutdown.evaluate(bundle))


def test_kernel_signature_requires_transport():
    entries = [
        entry(
            "EXT4-fs (nvme0n1p3): recovery complete",
            index=0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert "SHD-003" not in ids(shutdown.evaluate(make_bundle(entries)))
