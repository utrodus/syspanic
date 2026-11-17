"""MEM-001/002: EDAC memory errors, line-scoped against MCE (docs/04 §6)."""

import re

from syspanic.diagnostics.rules.common import (
    build_finding,
    has_token,
    kernel_entries,
    mce_edac_side,
)
from syspanic.domain.enums import EvidenceStrength, Severity

_CORRECTED = re.compile(r"\bcorrected\b", re.IGNORECASE)
_UNCORRECTED = re.compile(r"\buncorrected\b", re.IGNORECASE)


def evaluate(bundle):
    corrected = []
    uncorrected = []
    for entry in kernel_entries(bundle):
        if mce_edac_side(entry.message) != "edac":
            continue
        msg = entry.message
        if has_token(msg, "UE") or _UNCORRECTED.search(msg) or "Fatal" in msg:
            uncorrected.append(entry)
        elif has_token(msg, "CE") or _CORRECTED.search(msg):
            corrected.append(entry)

    findings = []
    finding = build_finding(
        "MEM-001",
        "memory",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        corrected,
        title="Corrected memory error (EDAC)",
        interpretation=(
            "EDAC recorded corrected memory errors. The log names the event class; it does "
            "not establish which component is at fault."
        ),
        unknowns=("Whether corrected errors recur under load",),
        next_steps=("Monitor recurrence; review machine-check findings for CPU-side detail.",),
    )
    if finding:
        findings.append(finding)

    finding = build_finding(
        "MEM-002",
        "memory",
        Severity.CRITICAL,
        EvidenceStrength.DIRECT,
        uncorrected,
        title="Uncorrected memory error (EDAC)",
        interpretation=(
            "EDAC recorded an uncorrected memory error. The log names the event class; it does "
            "not establish which component is at fault."
        ),
        unknowns=("Which memory region or component produced the error",),
        next_steps=("Review surrounding EDAC context and crash artifacts.",),
    )
    if finding:
        findings.append(finding)
    return tuple(findings)
