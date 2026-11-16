"""Domain dataclasses and validate_report() — docs/02-architecture.md §5.

Qt-free and side-effect-free: validation is a pure function of the report
(and optionally the bundle it was assembled from).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from syspanic.domain.enums import (
    ArtifactAssociation,
    EvidenceStrength,
    Severity,
    SourceState,
    TimelineKind,
)

RULE_IDS = frozenset(
    {
        "SHD-001", "SHD-002", "SHD-003", "SHD-004",
        "BOT-001",
        "PNC-001", "PNC-002", "PNC-003", "PNC-004",
        "MCE-001", "MCE-002",
        "GPU-001", "GPU-002", "GPU-003", "GPU-004",
        "MEM-001", "MEM-002",
        "PCI-001", "PCI-002", "PCI-003",
        "STO-001", "STO-002", "STO-003",
        "THM-001", "THM-002",
        "ART-001", "ART-002", "ART-003",
        "KRN-001",
    }
)

EVIDENCE_PREFIXES = ("JRN-", "DMS-", "VMD-", "PST-", "BTM-", "AFM-")
MAX_EVIDENCE_REFS = 3
MAX_EXCERPT_LINES = 3
MAX_EXCERPT_LINE_CHARS = 300
MAX_MESSAGE_CHARS = 1000
MAX_TIMELINE_EVENTS = 200

BANNED_TERMS = (
    "defective",
    "broken",
    "faulty",
    "hardware failure",
    "PSU failure",
    "power supply failure",
    "confirmed cause",
    "100%",
    "guaranteed",
    "must replace",
    "certainly",
)

_BOOT_ID_RE = re.compile(r"[0-9a-f]{32}")
_UNRELIABLE_TAIL_STATES = frozenset(
    {SourceState.TIMEOUT, SourceState.PERMISSION_DENIED, SourceState.ERROR}
)


class ReportValidationError(ValueError):
    """Aggregated violations found by validate_report()."""


@dataclass(frozen=True)
class BootInfo:
    index: int
    boot_id: str
    is_current: bool
    first_entry: datetime | None = None
    last_entry: datetime | None = None
    kernel_release: str | None = None

    def __post_init__(self):
        if not _BOOT_ID_RE.fullmatch(self.boot_id):
            raise ValueError(f"boot_id must be 32 lowercase hex characters: {self.boot_id!r}")


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source: str
    boot_id: str
    message: str
    timestamp: datetime | None = None
    priority: int | None = None
    identifier: str | None = None
    line_no: int | None = None
    provenance: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceCoverage:
    source: str
    state: SourceState
    detail: str = ""
    entry_count: int = 0
    head_truncated: bool = False
    tail_reliable: bool = True
    elapsed_ms: float = 0.0

    def __post_init__(self):
        if self.state in _UNRELIABLE_TAIL_STATES and self.tail_reliable:
            raise ValueError(
                f"{self.source}: state {self.state.value} requires tail_reliable=False"
            )


@dataclass(frozen=True)
class GpuInfo:
    pci_address: str
    vendor: str
    model: str
    driver: str | None = None


@dataclass(frozen=True)
class SystemProfile:
    os_name: str
    os_version_id: str
    kernel: str
    arch: str
    cpu_model: str
    cpu_cores: int
    mem_total_kib: int
    collected_at: datetime
    microcode: str | None = None
    gpus: tuple[GpuInfo, ...] = ()
    bios_vendor: str | None = None
    bios_version: str | None = None
    bios_date: str | None = None
    board_vendor: str | None = None
    board_name: str | None = None


@dataclass(frozen=True)
class ArtifactInfo:
    path: str
    kind: str
    size_bytes: int
    readable: bool
    association: ArtifactAssociation
    association_reason: str
    mtime: datetime | None = None
    incident_dir: str | None = None
    note: str = ""


@dataclass(frozen=True)
class CrashArtifacts:
    vmcore_files: tuple[ArtifactInfo, ...] = ()
    vmcore_dmesg: tuple[ArtifactInfo, ...] = ()
    pstore_records: tuple[ArtifactInfo, ...] = ()
    crash_kernel_loaded: bool | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    excerpt: str


@dataclass(frozen=True)
class Finding:
    finding_id: str
    rule_id: str
    category: str
    title: str
    severity: Severity
    strength: EvidenceStrength
    evidence: tuple[EvidenceRef, ...]
    interpretation: str
    suspected_causes: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimelineEvent:
    timestamp: datetime
    kind: TimelineKind
    summary: str
    severity: Severity
    evidence_id: str


@dataclass(frozen=True)
class CollectionIssue:
    source: str
    detail: str


@dataclass(frozen=True)
class CollectionBundle:
    boot: BootInfo
    boots: tuple[BootInfo, ...]
    entries: tuple[EvidenceItem, ...]
    coverage: tuple[SourceCoverage, ...]
    system: SystemProfile | None = None
    artifacts: CrashArtifacts | None = None
    issues: tuple[CollectionIssue, ...] = ()
    demo: bool = False
    hostname_hint: str | None = None


@dataclass(frozen=True)
class IncidentReport:
    boot: BootInfo
    findings: tuple[Finding, ...]
    timeline: tuple[TimelineEvent, ...]
    coverage: tuple[SourceCoverage, ...]
    evidence: tuple[EvidenceItem, ...]
    generated_at: datetime
    app_version: str
    system: SystemProfile | None = None
    artifacts: CrashArtifacts | None = None
    demo: bool = False


def _validate_evidence(evidence: tuple[EvidenceItem, ...], errors: list[str]) -> set[str]:
    ids: set[str] = set()
    for item in evidence:
        if item.evidence_id in ids:
            errors.append(f"duplicate evidence id {item.evidence_id}")
        ids.add(item.evidence_id)
        if not item.evidence_id.startswith(EVIDENCE_PREFIXES):
            errors.append(f"invalid evidence namespace: {item.evidence_id}")
        if item.evidence_id.startswith("JRN-") and item.timestamp is None:
            errors.append(f"journal evidence {item.evidence_id} requires a timestamp")
        if len(item.message) > MAX_MESSAGE_CHARS:
            errors.append(
                f"evidence {item.evidence_id} message exceeds {MAX_MESSAGE_CHARS} characters"
            )
        if any(ord(c) < 32 or ord(c) == 127 for c in item.message):
            errors.append(f"evidence {item.evidence_id} message contains control characters")
    return ids


def _validate_findings(findings: tuple[Finding, ...], ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()
    for finding in findings:
        if finding.finding_id in seen:
            errors.append(f"duplicate finding id {finding.finding_id}")
        seen.add(finding.finding_id)
        if finding.rule_id not in RULE_IDS:
            errors.append(f"unknown rule id {finding.rule_id} on finding {finding.finding_id}")
        if not finding.evidence:
            errors.append(f"finding {finding.finding_id} has no evidence")
        if len(finding.evidence) > MAX_EVIDENCE_REFS:
            errors.append(
                f"finding {finding.finding_id} exceeds {MAX_EVIDENCE_REFS} evidence refs"
            )
        for ref in finding.evidence:
            if ref.evidence_id not in ids:
                errors.append(
                    f"finding {finding.finding_id} references unresolved evidence "
                    f"{ref.evidence_id}"
                )
            lines = ref.excerpt.splitlines()
            if len(lines) > MAX_EXCERPT_LINES or any(
                len(line) > MAX_EXCERPT_LINE_CHARS for line in lines
            ):
                errors.append(
                    f"finding {finding.finding_id} excerpt exceeds "
                    f"{MAX_EXCERPT_LINES} lines / {MAX_EXCERPT_LINE_CHARS} chars per line"
                )
        texts = (
            finding.title,
            finding.interpretation,
            *finding.suspected_causes,
            *finding.unknowns,
            *finding.next_steps,
        )
        for text in texts:
            lowered = text.lower()
            for term in BANNED_TERMS:
                if term.lower() in lowered:
                    errors.append(f"finding {finding.finding_id} uses banned term {term!r}")


def _validate_timeline(
    timeline: tuple[TimelineEvent, ...], ids: set[str], errors: list[str]
) -> None:
    if len(timeline) > MAX_TIMELINE_EVENTS:
        errors.append(f"timeline exceeds {MAX_TIMELINE_EVENTS} events")
    seen: set[tuple[datetime, TimelineKind, str]] = set()
    previous: datetime | None = None
    for event in timeline:
        if previous is not None and event.timestamp < previous:
            errors.append("timeline is not sorted ascending by timestamp")
        previous = event.timestamp
        key = (event.timestamp, event.kind, event.evidence_id)
        if key in seen:
            errors.append(
                f"duplicate timeline event {event.evidence_id} at {event.timestamp.isoformat()}"
            )
        seen.add(key)
        if event.evidence_id not in ids:
            errors.append(f"timeline references unresolved evidence {event.evidence_id}")


def validate_report(
    report: IncidentReport, bundle: CollectionBundle | None = None
) -> None:
    """Reject contract violations (docs/02 §5); raise ReportValidationError.

    When the source bundle is supplied, the demo flags must agree.
    """
    errors: list[str] = []
    ids = _validate_evidence(report.evidence, errors)
    _validate_findings(report.findings, ids, errors)
    _validate_timeline(report.timeline, ids, errors)
    seen_sources: set[str] = set()
    for coverage in report.coverage:
        if coverage.source in seen_sources:
            errors.append(f"duplicate coverage source {coverage.source}")
        seen_sources.add(coverage.source)
    if bundle is not None and report.demo != bundle.demo:
        errors.append("demo flag mismatch between report and collection bundle")
    if errors:
        raise ReportValidationError("; ".join(errors))
