"""STO-001..003: I/O errors, NVMe controller events, filesystem errors (kernel only)."""

from syspanic.diagnostics.rules.common import build_finding, kernel_entries
from syspanic.domain.enums import EvidenceStrength, Severity

_IO_TOKENS = ("I/O error", "critical medium error", "Medium Error", "blk_update_request")
_NVME_TOKENS = ("timeout", "controller is down", "resetting controller", "Abort")


def _is_fs_error(message: str) -> bool:
    if "EXT4-fs error" in message or "BTRFS error" in message:
        return True
    if "corruption" in message.lower():
        return True
    return "XFS" in message and "error" in message.lower()


def evaluate(bundle):
    entries = kernel_entries(bundle)
    findings = []

    io_matches = [
        e for e in entries if any(token in e.message for token in _IO_TOKENS)
    ]
    finding = build_finding(
        "STO-001",
        "storage",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        io_matches,
        title="Storage I/O error",
        interpretation=(
            "The kernel reported a storage I/O error. The log names the device and error "
            "class; it does not establish which component is at fault."
        ),
        unknowns=("Whether the error is media, link, or driver related",),
        next_steps=("Review the device context and any following remount or reset.",),
    )
    if finding:
        findings.append(finding)

    nvme_matches = [
        e
        for e in entries
        if "nvme" in e.message and any(token in e.message for token in _NVME_TOKENS)
    ]
    finding = build_finding(
        "STO-002",
        "storage",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        nvme_matches,
        title="NVMe controller timeout or reset",
        interpretation=(
            "An NVMe controller reported a timeout, reset, or abort. This observation does "
            "not identify which component is at fault."
        ),
        unknowns=("Whether the controller recovered",),
        next_steps=("Check for repeated resets or I/O errors after the event.",),
    )
    if finding:
        findings.append(finding)

    fs_matches = [e for e in entries if _is_fs_error(e.message)]
    finding = build_finding(
        "STO-003",
        "storage",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        fs_matches,
        title="Filesystem error reported",
        interpretation=(
            "A filesystem reported an error or corruption. Recovery messages (SHD-003) are "
            "distinct from errors; this finding requires explicit error wording."
        ),
        unknowns=("Which underlying condition produced the filesystem error",),
        next_steps=("Review storage I/O findings near the error timestamp.",),
    )
    if finding:
        findings.append(finding)
    return tuple(findings)
