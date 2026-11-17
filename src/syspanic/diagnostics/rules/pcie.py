"""PCI-001..003: AER corrected/uncorrected, link resets (kernel provenance only)."""

import re

from syspanic.diagnostics.rules.common import build_finding, kernel_entries
from syspanic.domain.enums import EvidenceStrength, Severity

_CORRECTED = re.compile(r"\bcorrected\b", re.IGNORECASE)
_LINK_TOKENS = ("Link Down", "link down", "slot reset", "bus reset", "reset")


def evaluate(bundle):
    entries = kernel_entries(bundle)
    findings = []

    corrected = [
        e
        for e in entries
        if ("AER" in e.message and _CORRECTED.search(e.message))
        or ("PCIe Bus Error" in e.message and "severity=Corrected" in e.message)
    ]
    finding = build_finding(
        "PCI-001",
        "pcie",
        Severity.NOTICE,
        EvidenceStrength.DIRECT,
        corrected,
        title="PCIe corrected error (AER)",
        interpretation=(
            "AER recorded a corrected PCIe error. Corrected errors are retried by hardware; "
            "the log does not establish which component is at fault."
        ),
        unknowns=("Whether corrected errors recur",),
        next_steps=("Monitor recurrence; review uncorrected-error findings if present.",),
    )
    if finding:
        findings.append(finding)

    nonfatal = [e for e in entries if "AER: Uncorrected (Non-Fatal)" in e.message]
    fatal = [e for e in entries if "AER: Uncorrected (Fatal)" in e.message]
    finding = build_finding(
        "PCI-002",
        "pcie",
        Severity.CRITICAL if fatal else Severity.WARNING,
        EvidenceStrength.DIRECT,
        nonfatal + fatal,
        title="PCIe uncorrected error (AER)",
        interpretation=(
            "AER recorded an uncorrected PCIe error. The severity field distinguishes "
            "non-fatal from fatal; the log does not establish which component is at fault."
        ),
        unknowns=("Which link or device produced the error",),
        next_steps=("Review the AER context and any following link reset.",),
    )
    if finding:
        findings.append(finding)

    link = [
        e
        for e in entries
        if "pcieport" in e.message and any(token in e.message for token in _LINK_TOKENS)
    ]
    finding = build_finding(
        "PCI-003",
        "pcie",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        link,
        title="PCIe link reset or link down",
        interpretation=(
            "A PCIe port reported a link reset or link-down event. `PCIe Bus Error` alone is "
            "not a link reset; this finding requires explicit reset or link-down wording."
        ),
        unknowns=("Whether the link recovered",),
        next_steps=("Check for device re-enumeration or repeated resets after the event.",),
    )
    if finding:
        findings.append(finding)
    return tuple(findings)
