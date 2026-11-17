"""ART-001: crash-dump presence with boot association (metadata only).

ART-002/ART-003 (vmcore-dmesg/pstore text classification) are deferred and tracked
disabled in the registry; this module never evaluates them.
"""

from syspanic.constants import SOURCE_CRASH_VMCORE
from syspanic.diagnostics.rules.common import build_finding
from syspanic.domain.enums import ArtifactAssociation, EvidenceStrength, Severity

_RANK = {
    ArtifactAssociation.MATCHED: 0,
    ArtifactAssociation.POSSIBLY_RELATED: 1,
    ArtifactAssociation.UNKNOWN: 2,
}
_SEVERITY = {
    ArtifactAssociation.MATCHED: Severity.CRITICAL,
    ArtifactAssociation.POSSIBLY_RELATED: Severity.WARNING,
    ArtifactAssociation.UNKNOWN: Severity.NOTICE,
}


def evaluate(bundle):
    artifacts = bundle.artifacts
    if artifacts is None or not artifacts.vmcore_files:
        return ()
    afm = [e for e in bundle.entries if e.source == SOURCE_CRASH_VMCORE]
    if not afm:
        return ()
    best = min(artifacts.vmcore_files, key=lambda a: _RANK[a.association])
    finding = build_finding(
        "ART-001",
        "artifacts",
        _SEVERITY[best.association],
        EvidenceStrength.DIRECT,
        afm,
        title="Crash dump present",
        interpretation=(
            "A crash dump exists. Only name, size, mtime, and association are read; binary "
            f"contents are not analyzed. Association: {best.association.value} — "
            f"{best.association_reason}."
        ),
        unknowns=("What the dump contains",),
        next_steps=(
            "Analyze the dump with an external tool if boot association is verified.",
        ),
    )
    return (finding,) if finding else ()
