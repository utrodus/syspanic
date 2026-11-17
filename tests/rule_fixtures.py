"""Shared synthetic bundle builders for diagnostic rule tests."""

from datetime import UTC, datetime, timedelta

from syspanic.constants import (
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import (
    BootInfo,
    CollectionBundle,
    EvidenceItem,
    SourceCoverage,
)

BOOT_ID = "11111111111111111111111111111111"
LATER_BOOT_ID = "22222222222222222222222222222222"
BASE = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
KERNEL_RELEASE = "6.17.8-300.fc44.x86_64"


def make_boot(**overrides):
    fields = {
        "index": -1,
        "boot_id": BOOT_ID,
        "is_current": False,
        "first_entry": BASE,
        "last_entry": BASE + timedelta(hours=1),
        "kernel_release": KERNEL_RELEASE,
    }
    fields.update(overrides)
    return BootInfo(**fields)


def entry(
    message,
    index=0,
    *,
    source=SOURCE_JOURNAL_KERNEL,
    transport="kernel",
    extra=None,
    boot_id=BOOT_ID,
    timestamp=None,
    prefix="JRN-",
):
    provenance = {}
    if transport is not None:
        provenance["_TRANSPORT"] = transport
    if extra:
        provenance.update(extra)
    return EvidenceItem(
        evidence_id=f"{prefix}{index:06d}",
        source=source,
        boot_id=boot_id,
        message=message,
        timestamp=timestamp if timestamp is not None else BASE + timedelta(seconds=index),
        provenance=provenance,
    )


def journal_entries(messages, *, source=SOURCE_JOURNAL_KERNEL, transport="kernel", extra=None):
    return [
        entry(msg, index=i, source=source, transport=transport, extra=extra)
        for i, msg in enumerate(messages)
    ]


def default_coverage(
    entries,
    *,
    kernel_state=SourceState.AVAILABLE,
    system_state=SourceState.AVAILABLE,
    kernel_tail=True,
    system_tail=True,
):
    kernel_count = sum(1 for e in entries if e.source == SOURCE_JOURNAL_KERNEL)
    system_count = sum(1 for e in entries if e.source == SOURCE_JOURNAL_SYSTEM)
    return (
        SourceCoverage(
            source=SOURCE_JOURNAL_KERNEL,
            state=kernel_state,
            entry_count=kernel_count,
            tail_reliable=kernel_tail,
        ),
        SourceCoverage(
            source=SOURCE_JOURNAL_SYSTEM,
            state=system_state,
            entry_count=system_count,
            tail_reliable=system_tail,
        ),
    )


def make_bundle(entries=(), *, boot=None, coverage=None, boots=(), artifacts=None, demo=False):
    entries = tuple(entries)
    return CollectionBundle(
        boot=boot if boot is not None else make_boot(),
        boots=tuple(boots),
        entries=entries,
        coverage=coverage if coverage is not None else default_coverage(entries),
        artifacts=artifacts,
        demo=demo,
    )


def filler(count, *, start=0, source=SOURCE_JOURNAL_KERNEL):
    return [
        entry(f"kernel: filler event {i} ok", index=start + i, source=source)
        for i in range(count)
    ]
