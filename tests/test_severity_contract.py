"""Approved severity + certainty contracts for all 27 core rules (docs/04 §6)."""

import pytest

from rule_fixtures import BASE, LATER_BOOT_ID, entry, filler, make_boot, make_bundle
from syspanic.constants import SOURCE_JOURNAL_SYSTEM
from syspanic.diagnostics import registry
from syspanic.domain.enums import ArtifactAssociation, Severity
from syspanic.domain.models import ArtifactInfo, CrashArtifacts


def _k(rule_id, message, severity):
    return (rule_id, make_bundle([entry(message, 0)]), severity)


def _shd001():
    marker = entry(
        "systemd-shutdown[1]: Powering off.",
        0,
        source=SOURCE_JOURNAL_SYSTEM,
        transport="journal",
        extra={"_SYSTEMD_UNIT": "systemd-shutdown.service"},
    )
    return make_bundle([marker])


def _shd002():
    return make_bundle(filler(12) + filler(12, start=100, source=SOURCE_JOURNAL_SYSTEM))


def _bot001():
    boot = make_boot()
    later = make_boot(index=0, boot_id=LATER_BOOT_ID, is_current=True)
    btm = entry(
        f"boot index 0 id {LATER_BOOT_ID}",
        0,
        source="journal.boots",
        transport=None,
        boot_id=LATER_BOOT_ID,
        prefix="BTM-",
    )
    return make_bundle([btm], boot=boot, boots=(boot, later))


def _art001(association):
    incident = "/var/crash/127.0.0.1-2026-11-10-08:30:00"
    record = ArtifactInfo(
        path=f"{incident}/vmcore",
        kind="vmcore",
        size_bytes=1024,
        readable=False,
        association=association,
        association_reason="contract fixture",
        mtime=BASE,
        incident_dir=incident,
        note="binary dump; metadata only, never opened",
    )
    afm = entry(
        f"vmcore {record.path} size=1024 association={association.value}",
        0,
        source="crash.vmcore",
        transport=None,
        prefix="AFM-",
    )
    return make_bundle([afm], artifacts=CrashArtifacts(vmcore_files=(record,)))


CASES = [
    ("SHD-001", _shd001(), Severity.INFO),
    ("SHD-002", _shd002(), Severity.WARNING),
    _k("SHD-003", "EXT4-fs (nvme0n1p3): recovery complete", Severity.NOTICE),
    _k("SHD-004", "EXT4-fs (nvme0n1p3): Remounting filesystem read-only", Severity.WARNING),
    ("BOT-001", _bot001(), Severity.INFO),
    _k("PNC-001", "Kernel panic - not syncing: Fatal exception", Severity.CRITICAL),
    _k("PNC-002", "Oops: 0000 [#1] SMP NOPTI", Severity.WARNING),
    _k("PNC-003", "watchdog: BUG: soft lockup - CPU#3 stuck for 22s!", Severity.WARNING),
    _k("PNC-004", "sysrq: SysRq : Show State", Severity.NOTICE),
    _k(
        "MCE-001",
        "mce: [Hardware Error]: Machine Check Exception Uncorrected (UC) bank 4",
        Severity.CRITICAL,
    ),
    _k("MCE-002", "mce: [Hardware Error]: Corrected error (CE) bank 2", Severity.WARNING),
    _k("MCE-002", "mce: [Hardware Error]: Machine check events logged", Severity.NOTICE),
    _k("GPU-001", "amdgpu 0000:0a:00.0: amdgpu: ring gfx_0.0.0 timeout", Severity.WARNING),
    _k("GPU-002", "amdgpu 0000:0a:00.0: amdgpu: GPU reset begin!", Severity.WARNING),
    _k(
        "GPU-003",
        "amdgpu 0000:0a:00.0: amdgpu: VM fault (0x0000000000000000) detected",
        Severity.WARNING,
    ),
    _k("GPU-004", "NVRM: Xid (PCI:0000:01:00): 31, pid=4321", Severity.WARNING),
    _k(
        "GPU-004",
        "NVRM: Xid (PCI:0000:01:00): 79, GPU has fallen off the bus",
        Severity.CRITICAL,
    ),
    _k("MEM-001", "EDAC MC0: 1 CE correctable error on DIMM#0", Severity.WARNING),
    _k("MEM-002", "EDAC MC0: 1 UE uncorrected error on DIMM#0", Severity.CRITICAL),
    _k(
        "PCI-001",
        "pcieport 0000:00:01.1: AER: Corrected error received: 0000:0a:00.0",
        Severity.NOTICE,
    ),
    _k(
        "PCI-002",
        "pcieport 0000:00:01.1: AER: Uncorrected (Non-Fatal) error received",
        Severity.WARNING,
    ),
    _k(
        "PCI-002",
        "pcieport 0000:00:01.1: AER: Uncorrected (Fatal) error received",
        Severity.CRITICAL,
    ),
    _k("PCI-003", "pcieport 0000:00:01.1: Link Down", Severity.WARNING),
    _k(
        "STO-001",
        "blk_update_request: I/O error, dev nvme0n1, sector 12345 op 0x1:(WRITE)",
        Severity.WARNING,
    ),
    _k("STO-002", "nvme nvme0: I/O 12 QID 3 timeout, aborting", Severity.WARNING),
    _k(
        "STO-003",
        "EXT4-fs error (device nvme0n1p3): ext4_find_entry:1455: inode #2",
        Severity.WARNING,
    ),
    _k("THM-001", "CPU0: Core temperature above threshold, cpu clock throttled", Severity.WARNING),
    _k("THM-002", "CPU0: critical temperature reached, shutting down", Severity.CRITICAL),
    ("ART-001", _art001(ArtifactAssociation.MATCHED), Severity.CRITICAL),
    ("ART-001", _art001(ArtifactAssociation.POSSIBLY_RELATED), Severity.WARNING),
    ("ART-001", _art001(ArtifactAssociation.UNKNOWN), Severity.NOTICE),
    _k("KRN-001", "CPU: 1 PID: 1 Comm: demo Tainted: P O E 6.17.8 #1", Severity.INFO),
]


@pytest.mark.parametrize("rule_id,bundle,expected", CASES, ids=[case[0] for case in CASES])
def test_approved_severity_contract(rule_id, bundle, expected):
    spec = next(s for s in registry.CATALOG if s.rule_id == rule_id)
    findings = registry.RULE_MODULES[spec.module].evaluate(bundle)
    finding = next(f for f in findings if f.rule_id == rule_id)
    assert finding.severity is expected


def test_contract_covers_every_core_rule():
    assert {case[0] for case in CASES} == registry.CORE_RULE_IDS


def test_panic_certainty_wording_contract():
    bundle = make_bundle(
        [
            entry("Oops: 0000 [#1] SMP NOPTI", 0),
            entry("Kernel panic - not syncing: Fatal exception", 1),
        ]
    )
    findings = {f.rule_id: f for f in registry.RULE_MODULES["panic"].evaluate(bundle)}
    assert "does not identify a root cause" in findings["PNC-001"].interpretation
    assert "may recover or precede a panic" in findings["PNC-002"].interpretation
    assert "lead, not a verdict" in findings["PNC-002"].interpretation
