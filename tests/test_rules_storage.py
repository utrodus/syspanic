"""T-012: STO-001..003 — block I/O, NVMe, filesystem errors."""

from rule_fixtures import entry, make_bundle
from syspanic.diagnostics.rules import storage
from syspanic.domain.enums import Severity


def by_rule(findings):
    return {f.rule_id: f for f in findings}


def test_sto001_io_error_variants():
    for message in (
        "blk_update_request: I/O error, dev nvme0n1, sector 12345 op 0x1:(WRITE)",
        "sd 0:0:0:0: [sda] critical medium error, dev sda, sector 99",
        "sd 0:0:0:0: [sda] Medium Error detected",
    ):
        findings = by_rule(storage.evaluate(make_bundle([entry(message, 0)])))
        assert findings["STO-001"].severity is Severity.WARNING


def test_sto002_nvme_timeout_and_reset():
    for message in (
        "nvme nvme0: I/O 12 QID 3 timeout, aborting",
        "nvme nvme0: controller is down; will reset",
        "nvme nvme0: resetting controller",
        "nvme nvme0: Abort status: 0x371",
    ):
        assert "STO-002" in by_rule(storage.evaluate(make_bundle([entry(message, 0)])))


def test_sto003_filesystem_errors():
    for message in (
        "EXT4-fs error (device nvme0n1p3): ext4_find_entry:1455: inode #2: "
        "comm demo-app: reading directory lblock 0",
        "BTRFS error (device nvme0n1p3): parent transid verify failed",
        "XFS (nvme0n1p3): Corruption detected",
        "XFS (nvme0n1p3): metadata I/O error",
    ):
        assert "STO-003" in by_rule(storage.evaluate(make_bundle([entry(message, 0)])))


def test_sto003_recovery_is_not_error():
    entries = [entry("EXT4-fs (nvme0n1p3): recovery complete", 0)]
    assert "STO-003" not in by_rule(storage.evaluate(make_bundle(entries)))


def test_nvme_pci_function_not_timeout():
    entries = [entry("nvme nvme0: pci function 0000:04:00.0", 0)]
    assert storage.evaluate(make_bundle(entries)) == ()


def test_userspace_io_text_ignored():
    from syspanic.constants import SOURCE_JOURNAL_SYSTEM

    entries = [
        entry(
            "I/O error, dev sda, sector 1",
            0,
            source=SOURCE_JOURNAL_SYSTEM,
            transport="stdout",
            extra={"SYSLOG_IDENTIFIER": "kernel"},
        )
    ]
    assert storage.evaluate(make_bundle(entries)) == ()
