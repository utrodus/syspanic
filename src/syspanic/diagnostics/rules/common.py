"""Shared rule helpers: provenance filters, bounded excerpts, finding assembly."""

import re

from syspanic.constants import SOURCE_DMESG, SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM
from syspanic.domain.enums import EvidenceStrength, Severity
from syspanic.domain.models import EvidenceItem, EvidenceRef, Finding

JOURNAL_SOURCES = (SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM)
MAX_REFS = 3
MAX_EXCERPT_LINES = 3
MAX_EXCERPT_LINE_CHARS = 300


def is_kernel(entry: EvidenceItem) -> bool:
    return entry.provenance.get("_TRANSPORT") == "kernel" or entry.source == SOURCE_DMESG


def journal_entries(bundle) -> list[EvidenceItem]:
    return [e for e in bundle.entries if e.source in JOURNAL_SOURCES]


def kernel_entries(bundle) -> list[EvidenceItem]:
    return [
        e
        for e in bundle.entries
        if (e.source in JOURNAL_SOURCES or e.source == SOURCE_DMESG) and is_kernel(e)
    ]


def excerpt(message: str) -> str:
    lines = message.splitlines()[:MAX_EXCERPT_LINES]
    return "\n".join(line[:MAX_EXCERPT_LINE_CHARS] for line in lines)


def build_finding(
    rule_id: str,
    category: str,
    severity: Severity,
    strength: EvidenceStrength,
    matches: list[EvidenceItem],
    *,
    title: str,
    interpretation: str,
    suspected_causes: tuple[str, ...] = (),
    unknowns: tuple[str, ...] = (),
    next_steps: tuple[str, ...] = (),
) -> Finding | None:
    if not matches:
        return None
    refs = tuple(
        EvidenceRef(evidence_id=e.evidence_id, excerpt=excerpt(e.message))
        for e in matches[:MAX_REFS]
    )
    if len(matches) > MAX_REFS:
        interpretation = f"{interpretation} Total matching entries: {len(matches)}."
    sources = tuple(dict.fromkeys(e.source for e in matches))
    return Finding(
        finding_id=rule_id,
        rule_id=rule_id,
        category=category,
        title=title,
        severity=severity,
        strength=strength,
        evidence=refs,
        interpretation=interpretation,
        suspected_causes=suspected_causes,
        unknowns=unknowns,
        next_steps=next_steps,
        sources=sources,
    )


def mce_edac_side(message: str) -> str | None:
    """Line-scoped precedence: the leading marker decides MCE vs EDAC."""
    positions = [message.find(token) for token in ("mce:", "Machine Check", "Machine check")]
    mce_pos = min((p for p in positions if p >= 0), default=-1)
    edac_pos = message.find("EDAC")
    if mce_pos < 0 and edac_pos < 0:
        return None
    if mce_pos < 0:
        return "edac"
    if edac_pos < 0:
        return "mce"
    return "mce" if mce_pos < edac_pos else "edac"


def has_token(message: str, token: str) -> bool:
    return re.search(rf"\b{token}\b", message) is not None
