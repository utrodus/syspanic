"""KRN-001: kernel taint flags, informational (G is not adverse)."""

import re

from syspanic.diagnostics.rules.common import build_finding, kernel_entries
from syspanic.domain.enums import EvidenceStrength, Severity

_TAINT = re.compile(r"Tainted:\s*([A-Za-z ]+)")
_ACTIVE_FLAGS = set("POEWDBCML")


def evaluate(bundle):
    matches = [e for e in kernel_entries(bundle) if "Tainted:" in e.message]
    if not matches:
        return ()
    flags = set()
    for entry in matches:
        match = _TAINT.search(entry.message)
        if match:
            flags.update(c for c in match.group(1) if c in _ACTIVE_FLAGS)
    if flags:
        interpretation = (
            f"The kernel was tainted by active flags: {', '.join(sorted(flags))}. "
            "This is informational and does not assert a fault."
        )
    else:
        interpretation = (
            "The kernel taint line shows no adverse flags; G is the untainted "
            "proprietary-slot placeholder, not an adverse taint. This is informational."
        )
    finding = build_finding(
        "KRN-001",
        "kernel_health",
        Severity.INFO,
        EvidenceStrength.DIRECT,
        matches,
        title="Kernel taint flags",
        interpretation=interpretation,
        next_steps=("Review loaded out-of-tree modules if taint flags are present.",),
    )
    return (finding,) if finding else ()
