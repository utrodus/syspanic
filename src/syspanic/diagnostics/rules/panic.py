"""PNC-001..004: panic, oops/faults, lockups/stalls, SysRq (kernel provenance only)."""

import re

from syspanic.diagnostics.rules.common import build_finding, kernel_entries
from syspanic.domain.enums import EvidenceStrength, Severity

_OOPS_TOKENS = (
    "Oops:",
    "BUG:",
    "kernel BUG at",
    "general protection fault",
    "invalid opcode:",
)
_LOCKUP_TOKENS = (
    "soft lockup",
    "hard LOCKUP",
    "rcu_sched detected stalls",
    "rcu_preempt detected stalls",
)
_BLOCKED = re.compile(r"blocked for more than \d+ seconds")
_SYSRQ = re.compile(r"sysrq:", re.IGNORECASE)


def evaluate(bundle):
    findings = []
    entries = kernel_entries(bundle)

    panic_matches = [e for e in entries if "Kernel panic" in e.message]
    finding = build_finding(
        "PNC-001",
        "panic",
        Severity.CRITICAL,
        EvidenceStrength.DIRECT,
        panic_matches,
        title="Kernel panic reported",
        interpretation=(
            "The kernel reported a panic. The panic string names a trigger at most; it does "
            "not identify a root cause. Inspect findings immediately preceding the panic."
        ),
        unknowns=("Which component or condition triggered the panic",),
        next_steps=(
            "Inspect crash artifacts and pstore for this boot window.",
            "Review earlier kernel findings in the timeline.",
        ),
    )
    if finding:
        findings.append(finding)

    oops_matches = [
        e for e in entries if any(token in e.message for token in _OOPS_TOKENS)
    ]
    finding = build_finding(
        "PNC-002",
        "panic",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        oops_matches,
        title="Oops or kernel fault reported",
        interpretation=(
            "An oops or kernel fault was reported. It may recover or precede a panic. A "
            "function or module in the trace is a lead, not a verdict."
        ),
        unknowns=("Whether the fault recovered or escalated",),
        next_steps=("Inspect the trace and preceding messages for context.",),
    )
    if finding:
        findings.append(finding)

    lockup_matches = [
        e
        for e in entries
        if any(token in e.message for token in _LOCKUP_TOKENS) or _BLOCKED.search(e.message)
    ]
    finding = build_finding(
        "PNC-003",
        "panic",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        lockup_matches,
        title="CPU/task lockup or stall reported",
        interpretation=(
            "A CPU or task stopped making progress; this often precedes a watchdog reset."
        ),
        unknowns=("Which workload or driver stalled",),
        next_steps=("Review the blocked task or stalled CPU context in the excerpts.",),
    )
    if finding:
        findings.append(finding)

    sysrq_matches = [
        e
        for e in entries
        if _SYSRQ.search(e.message) and "Emergency Remount" not in e.message
    ]
    finding = build_finding(
        "PNC-004",
        "panic",
        Severity.NOTICE,
        EvidenceStrength.DIRECT,
        sysrq_matches,
        title="SysRq action recorded",
        interpretation=(
            "An administrator or watchdog invoked SysRq. This is an action, not evidence of a "
            "hardware fault."
        ),
        next_steps=("Correlate the SysRq action with surrounding shutdown or reset messages.",),
    )
    if finding:
        findings.append(finding)
    return tuple(findings)
