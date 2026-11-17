"""SHD-001..004 + BOT-001: shutdown sequence, absence, filesystem recovery, orientation."""

from datetime import UTC, datetime

from syspanic.diagnostics.coverage import tail_reliable
from syspanic.diagnostics.rules.common import (
    build_finding,
    is_kernel,
    journal_entries,
    kernel_entries,
)
from syspanic.domain.enums import EvidenceStrength, Severity

_TAIL_WINDOW = 20
_MIN_ENTRIES_FOR_ABSENCE = 20


def trusted_marker(entry) -> str | None:
    """Shutdown-marker family, gated on trusted process/unit metadata."""
    msg = entry.message
    prov = entry.provenance
    shutdown_trusted = (
        prov.get("_SYSTEMD_UNIT") == "systemd-shutdown.service"
        or prov.get("_COMM") == "systemd-shutdown"
        or (prov.get("_EXE") or "").endswith("/systemd-shutdown")
    )
    if ("Powering off." in msg or "Rebooting." in msg) and shutdown_trusted:
        return "systemd_shutdown"
    if is_kernel(entry):
        if "reboot: Power down" in msg or "reboot: Restarting system" in msg:
            return "kernel_reboot"
        if "kexec_core: Starting new kernel" in msg:
            return "kexec"
    journald_trusted = (
        prov.get("_SYSTEMD_UNIT") == "systemd-journald.service"
        or prov.get("_COMM") == "systemd-journal"
    )
    if "Journal stopped" in msg and journald_trusted:
        return "journald_stopped"
    return None


def detect_markers(entries) -> list[tuple]:
    found = []
    for entry in entries:
        family = trusted_marker(entry)
        if family:
            found.append((entry, family))
    return found


def _shd001(matches: list, families: set[str]):
    strength = (
        EvidenceStrength.CORROBORATED if len(families) >= 2 else EvidenceStrength.DIRECT
    )
    parts = ["A trusted shutdown-sequence marker was found in the retained journal tail. "]
    if "kexec" in families:
        parts.append(
            "The kexec marker supports an orderly kexec transition to another kernel, "
            "not a power cycle. "
        )
    if families & {"systemd_shutdown", "kernel_reboot"}:
        parts.append(
            "Systemd/kernel markers support an orderly shutdown or reboot sequence. "
        )
    if "journald_stopped" in families:
        parts.append(
            "`Journal stopped` records only that journald stopped; it does not prove a clean "
            "system shutdown. "
        )
    parts.append("A shutdown marker does not prove the boot was error-free.")
    return build_finding(
        "SHD-001",
        "shutdown_boot",
        Severity.INFO,
        strength,
        matches,
        title="Shutdown-sequence marker observed",
        interpretation="".join(parts),
        unknowns=("Whether the shutdown completed without earlier errors",),
        next_steps=(
            "Review earlier findings in this boot before concluding the shutdown was clean.",
        ),
    )


def _shd002(tail: list):
    interpretation = (
        "No trusted shutdown-sequence messages were found in the reliably collected journal "
        "tail. A hard reset, hang, watchdog reset, firmware reset, power loss, journal flush "
        "failure, or journal corruption can produce this absence; the logs cannot distinguish "
        "them."
    )
    return build_finding(
        "SHD-002",
        "shutdown_boot",
        Severity.WARNING,
        EvidenceStrength.CIRCUMSTANTIAL,
        tail[-3:],
        title="No shutdown-sequence markers in retained tail",
        interpretation=interpretation,
        suspected_causes=(
            "Hard reset",
            "System hang",
            "Watchdog reset",
            "Firmware reset",
            "Power loss",
            "Journal flush failure",
            "Journal corruption",
        ),
        unknowns=(
            "Whether the system powered off, reset, or hung",
            "Whether journal persistence is enabled",
        ),
        next_steps=(
            "Check crash artifacts and pstore for this boot window.",
            "Verify journal persistence configuration manually.",
        ),
    )


def evaluate(bundle):
    findings = []
    entries = sorted(
        journal_entries(bundle),
        key=lambda e: e.timestamp or datetime.min.replace(tzinfo=UTC),
    )
    tail = entries[-_TAIL_WINDOW:]
    markers = detect_markers(tail)
    if markers:
        finding = _shd001([e for e, _ in markers], {family for _, family in markers})
        if finding:
            findings.append(finding)
    elif (
        not bundle.boot.is_current
        and tail_reliable(bundle.coverage)
        and len(entries) >= _MIN_ENTRIES_FOR_ABSENCE
    ):
        finding = _shd002(tail)
        if finding:
            findings.append(finding)

    recovery = [
        e
        for e in kernel_entries(bundle)
        if ("EXT4-fs" in e.message and ("recovery" in e.message or "orphan" in e.message))
        or ("BTRFS" in e.message and ("replay" in e.message or "recovery" in e.message))
        or ("XFS" in e.message and "log recovery" in e.message)
    ]
    finding = build_finding(
        "SHD-003",
        "shutdown_boot",
        Severity.NOTICE,
        EvidenceStrength.DIRECT,
        recovery,
        title="Filesystem recovery after unclean stop",
        interpretation=(
            "A filesystem was mounted after an unclean stop. The recovery message often appears "
            "in the boot after the stop, so it may refer to a different boot than the one "
            "selected."
        ),
        unknowns=("Which boot the unclean stop belongs to",),
        next_steps=("Compare the boot window with the recovery timestamp.",),
    )
    if finding:
        findings.append(finding)

    remount = [
        e
        for e in kernel_entries(bundle)
        if "Remounting filesystem read-only" in e.message
        or "Emergency Remount R/O" in e.message
        or ("BTRFS info" in e.message and "forced readonly" in e.message)
    ]
    finding = build_finding(
        "SHD-004",
        "shutdown_boot",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        remount,
        title="Filesystem remounted read-only",
        interpretation=(
            "A filesystem was remounted read-only, often after an I/O or filesystem error. "
            "This observation does not identify which component caused the remount."
        ),
        unknowns=("Which underlying error triggered the remount",),
        next_steps=("Review storage findings near the remount timestamp.",),
    )
    if finding:
        findings.append(finding)

    later = [b for b in bundle.boots if b.index > bundle.boot.index]
    if later:
        from syspanic.constants import SOURCE_JOURNAL_BOOTS

        btm = next(
            (
                e
                for e in bundle.entries
                if e.source == SOURCE_JOURNAL_BOOTS and e.boot_id == later[0].boot_id
            ),
            None,
        )
        if btm is not None:
            finding = build_finding(
                "BOT-001",
                "shutdown_boot",
                Severity.INFO,
                EvidenceStrength.DIRECT,
                [btm],
                title="Selected boot is historical",
                interpretation=(
                    "The selected boot is historical and was followed by another boot. This "
                    "provides orientation, not a fault claim."
                ),
                next_steps=("Select the later boot to inspect the most recent session.",),
            )
            if finding:
                findings.append(finding)
    return tuple(findings)
