"""MCE-001/002: machine-check events, line-scoped against EDAC (docs/04 §6)."""

from syspanic.diagnostics.rules.common import (
    build_finding,
    has_token,
    kernel_entries,
    mce_edac_side,
)
from syspanic.domain.enums import EvidenceStrength, Severity


def evaluate(bundle):
    uncorrected = []
    corrected = []
    unknown = []
    for entry in kernel_entries(bundle):
        if mce_edac_side(entry.message) != "mce":
            continue
        msg = entry.message
        if "Uncorrected" in msg or has_token(msg, "UE") or "Fatal" in msg:
            uncorrected.append(entry)
        elif "Corrected" in msg or has_token(msg, "CE"):
            corrected.append(entry)
        else:
            unknown.append(entry)

    findings = []
    finding = build_finding(
        "MCE-001",
        "cpu_mce",
        Severity.CRITICAL,
        EvidenceStrength.DIRECT,
        uncorrected,
        title="Uncorrected machine-check event",
        interpretation=(
            "The kernel recorded an uncorrected machine-check event. The log names the event "
            "class; it does not establish which component is at fault."
        ),
        unknowns=("Which component produced the uncorrected event",),
        next_steps=("Review surrounding machine-check context and crash artifacts.",),
    )
    if finding:
        findings.append(finding)

    matches = corrected + unknown
    if matches:
        interpretation = "The kernel recorded corrected machine-check events."
        if unknown:
            interpretation += (
                " Correctability is not stated for some events; they are not classified as "
                "uncorrected."
            )
        finding = build_finding(
            "MCE-002",
            "cpu_mce",
            Severity.WARNING if corrected else Severity.NOTICE,
            EvidenceStrength.DIRECT,
            matches,
            title="Corrected machine-check events",
            interpretation=interpretation,
            unknowns=("Whether the corrected events recur under load",),
            next_steps=("Monitor recurrence; review EDAC findings for memory-side detail.",),
        )
        if finding:
            findings.append(finding)
    return tuple(findings)
