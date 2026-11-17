"""THM-001/002: thermal throttling and critical temperature (kernel only)."""

from syspanic.diagnostics.rules.common import build_finding, kernel_entries
from syspanic.domain.enums import EvidenceStrength, Severity

_THROTTLE_TOKENS = (
    "temperature above threshold",
    "cpu clock throttled",
    "package_throttled",
)
_CRITICAL_TOKENS = ("critical temperature reached", "thermal shutdown", "Critical temperature")


def evaluate(bundle):
    entries = kernel_entries(bundle)
    findings = []

    throttle_matches = [
        e
        for e in entries
        if any(token in e.message.lower() for token in _THROTTLE_TOKENS)
        or ("thermal" in e.message.lower() and "throttl" in e.message.lower())
    ]
    finding = build_finding(
        "THM-001",
        "thermal",
        Severity.WARNING,
        EvidenceStrength.DIRECT,
        throttle_matches,
        title="Thermal throttling reported",
        interpretation=(
            "The kernel reported thermal throttling. Throttling is a protective response; "
            "the log does not establish which component is at fault."
        ),
        unknowns=("Which cooling or workload condition caused the throttling",),
        next_steps=("Review workload and cooling context around the throttling events.",),
    )
    if finding:
        findings.append(finding)

    critical_matches = [
        e
        for e in entries
        if any(token in e.message.lower() for token in (t.lower() for t in _CRITICAL_TOKENS))
    ]
    finding = build_finding(
        "THM-002",
        "thermal",
        Severity.CRITICAL,
        EvidenceStrength.DIRECT,
        critical_matches,
        title="Critical temperature or thermal shutdown",
        interpretation=(
            "The kernel reported a critical temperature or thermal shutdown. This is a "
            "protective action; the log does not establish which component is at fault."
        ),
        unknowns=("Which sensor or condition reached the critical threshold",),
        next_steps=("Review cooling and workload context before the critical event.",),
    )
    if finding:
        findings.append(finding)
    return tuple(findings)
