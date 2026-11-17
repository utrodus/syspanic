"""GPU-001..004: timeouts, reset attempts, VM faults, NVIDIA Xid (kernel only)."""

import re

from syspanic.diagnostics.rules.common import build_finding, kernel_entries
from syspanic.domain.enums import EvidenceStrength, Severity

_TIMEOUT_TOKENS = ("ring", "timeout")
_RESET_TOKENS = (
    "GPU reset begin",
    "GPU reset end",
    "gpu reset succeeded",
    "resetting GPU",
)
_RESET_COUNT = re.compile(r"gpu reset\((\d+)\)", re.IGNORECASE)
_FAULT_TOKENS = ("VM fault", "GPU fault detected", "IH ring", "retry page fault")
_XID = re.compile(r"NVRM: Xid.*?: (\d+)")


def evaluate(bundle):
    entries = kernel_entries(bundle)
    findings = []

    timeout_matches = [
        e
        for e in entries
        if all(token in e.message.lower() for token in _TIMEOUT_TOKENS)
        or "amdgpu_job_timedout" in e.message
    ]
    finding = build_finding(
        "GPU-001",
        "gpu",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        timeout_matches,
        title="GPU job or ring timeout",
        interpretation=(
            "A GPU job or ring timed out. This observation is separate from any reset attempt "
            "and does not identify which component is at fault."
        ),
        unknowns=("Which workload or driver condition caused the timeout",),
        next_steps=("Review GPU reset findings and preceding driver messages.",),
    )
    if finding:
        findings.append(finding)

    reset_matches = [
        e
        for e in entries
        if any(token in e.message for token in _RESET_TOKENS) or _RESET_COUNT.search(e.message)
    ]
    finding = build_finding(
        "GPU-002",
        "gpu",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        reset_matches,
        title="GPU reset attempt or completion",
        interpretation=(
            "The driver attempted or completed a GPU reset. The excerpts show whether the "
            "message indicates an attempt, success, or failure; this observation is separate "
            "from any timeout finding."
        ),
        unknowns=("Whether the reset restored normal operation",),
        next_steps=("Check for subsequent timeouts or faults after the reset.",),
    )
    if finding:
        findings.append(finding)

    fault_matches = [
        e for e in entries if any(token in e.message for token in _FAULT_TOKENS)
    ]
    finding = build_finding(
        "GPU-003",
        "gpu",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        fault_matches,
        title="GPU VM or page fault",
        interpretation=(
            "The GPU driver reported a VM or page fault. The log names the fault type; it does "
            "not establish which component is at fault."
        ),
        unknowns=("Which address space or workload triggered the fault",),
        next_steps=("Review the fault context and any preceding timeout or reset.",),
    )
    if finding:
        findings.append(finding)

    xid_matches = []
    codes = set()
    for entry in entries:
        match = _XID.search(entry.message)
        if match:
            xid_matches.append(entry)
            codes.add(int(match.group(1)))
    if xid_matches:
        severity = Severity.CRITICAL if 79 in codes else Severity.WARNING
        code_list = ", ".join(str(c) for c in sorted(codes))
        finding = build_finding(
            "GPU-004",
            "gpu",
            severity,
            EvidenceStrength.DIRECT,
            xid_matches,
            title=f"NVIDIA Xid error (code {code_list})",
            interpretation=(
                f"The NVIDIA driver reported Xid code {code_list}. Meanings vary by code; "
                "code 79 indicates the GPU fell off the bus. No defect claim is made."
            ),
            unknowns=("Which condition produced the Xid code",),
            next_steps=("Consult the NVIDIA Xid reference for the reported codes.",),
        )
        if finding:
            findings.append(finding)
    return tuple(findings)
