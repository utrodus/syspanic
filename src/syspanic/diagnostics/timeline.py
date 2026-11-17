"""Timeline construction: boot boundaries, markers, rule matches (docs/04 §8)."""

from syspanic.constants import (
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_JOURNAL_BOOTS,
)
from syspanic.diagnostics.rules.common import journal_entries
from syspanic.diagnostics.rules.shutdown import trusted_marker
from syspanic.domain.enums import Severity, TimelineKind
from syspanic.domain.models import TimelineEvent

MAX_TIMELINE_EVENTS = 200
_ARTIFACT_SOURCES = (SOURCE_CRASH_VMCORE, SOURCE_CRASH_VMCORE_DMESG, SOURCE_CRASH_PSTORE)


def build_timeline(bundle, findings) -> tuple[TimelineEvent, ...]:
    events: list[TimelineEvent] = []
    btm = next(
        (
            e
            for e in bundle.entries
            if e.source == SOURCE_JOURNAL_BOOTS and e.boot_id == bundle.boot.boot_id
        ),
        None,
    )
    if btm is not None:
        if bundle.boot.first_entry is not None:
            events.append(
                TimelineEvent(
                    timestamp=bundle.boot.first_entry,
                    kind=TimelineKind.BOOT_START,
                    summary="Boot started (journal window)",
                    severity=Severity.INFO,
                    evidence_id=btm.evidence_id,
                )
            )
        if not bundle.boot.is_current and bundle.boot.last_entry is not None:
            events.append(
                TimelineEvent(
                    timestamp=bundle.boot.last_entry,
                    kind=TimelineKind.BOOT_END,
                    summary="Last retained journal entry",
                    severity=Severity.INFO,
                    evidence_id=btm.evidence_id,
                )
            )

    for entry in journal_entries(bundle):
        if entry.timestamp is None:
            continue
        family = trusted_marker(entry)
        if family == "kexec":
            events.append(
                TimelineEvent(
                    timestamp=entry.timestamp,
                    kind=TimelineKind.TRANSITION,
                    summary="kexec: starting new kernel",
                    severity=Severity.INFO,
                    evidence_id=entry.evidence_id,
                )
            )
        elif family:
            events.append(
                TimelineEvent(
                    timestamp=entry.timestamp,
                    kind=TimelineKind.SHUTDOWN_MARKER,
                    summary=f"Shutdown-sequence marker ({family})",
                    severity=Severity.INFO,
                    evidence_id=entry.evidence_id,
                )
            )

    evidence_by_id = {e.evidence_id: e for e in bundle.entries}
    for finding in findings:
        ref = finding.evidence[0]
        item = evidence_by_id.get(ref.evidence_id)
        if item is None or item.timestamp is None or item.source in _ARTIFACT_SOURCES:
            continue
        events.append(
            TimelineEvent(
                timestamp=item.timestamp,
                kind=TimelineKind.RULE_MATCH,
                summary=f"{finding.rule_id}: {finding.title}",
                severity=finding.severity,
                evidence_id=ref.evidence_id,
            )
        )

    events.sort(key=lambda e: e.timestamp)
    seen = set()
    deduped = []
    for event in events:
        key = (event.timestamp, event.kind, event.evidence_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return tuple(deduped[:MAX_TIMELINE_EVENTS])
