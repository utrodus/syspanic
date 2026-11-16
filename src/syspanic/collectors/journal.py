"""Journal collection per docs/02 §8: kernel + system slices, dedupe, truncation.

dmesg is collected only for the current boot; historical boots get `unsupported`
coverage. Entries are EvidenceItems with JRN-/DMS- IDs; no Qt, no writes.
"""

import json
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from syspanic.collectors.base import CollectionContext, CollectorResult
from syspanic.collectors.runner import CommandResult
from syspanic.constants import (
    DMESG_MAX_BYTES,
    DMESG_TIMEOUT_S,
    JOURNAL_TIMEOUT_S,
    KERNEL_ENTRY_CAP,
    KERNEL_MAX_BYTES,
    SOURCE_DMESG,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
    SYSTEM_ENTRY_CAP,
    SYSTEM_MAX_BYTES,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import MAX_MESSAGE_CHARS, BootInfo, EvidenceItem, SourceCoverage

DMESG_ISO_ARGV = ("dmesg", "--time-format", "iso")
DMESG_PLAIN_ARGV = ("dmesg",)

_PROVENANCE_KEYS = ("_TRANSPORT", "_COMM", "_EXE", "_SYSTEMD_UNIT", "SYSLOG_IDENTIFIER")
_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_KERNEL_RELEASE_RE = re.compile(r"Linux version (\S+)")
_DMESG_ISO_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[0-9:.,+-]+)\s+(.*)$")
_DMESG_MONO_RE = re.compile(r"^\[\s*\d+\.\d+\]\s?(.*)$")


@dataclass(frozen=True)
class JournalEntry:
    cursor: str
    timestamp: datetime
    message: str
    source: str
    line_no: int
    priority: int | None = None
    identifier: str | None = None
    provenance: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SliceParse:
    entries: tuple[JournalEntry, ...]
    skipped: int


@dataclass(frozen=True)
class JournalPayload:
    entries: tuple[EvidenceItem, ...]
    boot: BootInfo


def kernel_argv(boot_id: str) -> list[str]:
    return [
        "journalctl",
        f"--boot={boot_id}",
        "--kernel",
        "--output=json",
        "--no-pager",
        "-n",
        str(KERNEL_ENTRY_CAP),
    ]


def system_argv(boot_id: str) -> list[str]:
    return [
        "journalctl",
        f"--boot={boot_id}",
        "--output=json",
        "--no-pager",
        "-n",
        str(SYSTEM_ENTRY_CAP),
    ]


def decode_message(raw: object) -> str:
    if isinstance(raw, list):
        text = bytes(int(b) & 0xFF for b in raw).decode("utf-8", errors="replace")
    elif isinstance(raw, str):
        text = raw
    else:
        text = str(raw)
    text = _CSI_RE.sub("", text)
    text = _OSC_RE.sub("", text)
    text = "".join(c for c in text if (ord(c) >= 32 or c in "\n\t") and ord(c) != 127)
    return text[:MAX_MESSAGE_CHARS]


def _timestamp(us_raw: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(us_raw) / 1_000_000, tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def parse_journal_slice(text: str, source: str) -> SliceParse:
    entries: list[JournalEntry] = []
    skipped = 0
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(obj, dict):
            skipped += 1
            continue
        cursor = obj.get("__CURSOR")
        timestamp = _timestamp(obj.get("__REALTIME_TIMESTAMP"))
        if not isinstance(cursor, str) or not cursor or timestamp is None:
            skipped += 1
            continue
        try:
            priority = int(obj["PRIORITY"])
        except (KeyError, TypeError, ValueError):
            priority = None
        identifier = obj.get("SYSLOG_IDENTIFIER")
        provenance = {k: str(obj[k]) for k in _PROVENANCE_KEYS if k in obj}
        entries.append(
            JournalEntry(
                cursor=cursor,
                timestamp=timestamp,
                message=decode_message(obj.get("MESSAGE", "")),
                source=source,
                line_no=line_no,
                priority=priority,
                identifier=identifier if isinstance(identifier, str) else None,
                provenance=provenance,
            )
        )
    return SliceParse(entries=tuple(entries), skipped=skipped)


def merge_entries(
    kernel: tuple[JournalEntry, ...], system: tuple[JournalEntry, ...]
) -> tuple[JournalEntry, ...]:
    by_cursor: dict[str, JournalEntry] = {}
    for entry in kernel:
        by_cursor[entry.cursor] = entry
    for entry in system:
        by_cursor.setdefault(entry.cursor, entry)
    return tuple(sorted(by_cursor.values(), key=lambda e: (e.timestamp, e.cursor)))


def to_evidence(entries: tuple[JournalEntry, ...], boot_id: str) -> tuple[EvidenceItem, ...]:
    return tuple(
        EvidenceItem(
            evidence_id=f"JRN-{i:06d}",
            source=entry.source,
            boot_id=boot_id,
            message=entry.message,
            timestamp=entry.timestamp,
            priority=entry.priority,
            identifier=entry.identifier,
            line_no=entry.line_no,
            provenance=dict(entry.provenance),
        )
        for i, entry in enumerate(entries, 1)
    )


def extract_kernel_release(entries: tuple[JournalEntry, ...]) -> str | None:
    for entry in entries:
        match = _KERNEL_RELEASE_RE.search(entry.message)
        if match:
            return match.group(1)
    return None


def parse_dmesg(text: str, boot_id: str) -> tuple[EvidenceItem, ...]:
    entries: list[EvidenceItem] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        timestamp = None
        iso = _DMESG_ISO_RE.match(line)
        if iso:
            try:
                timestamp = datetime.fromisoformat(iso.group(1))
            except ValueError:
                timestamp = None
            message = iso.group(2)
        else:
            mono = _DMESG_MONO_RE.match(line)
            message = mono.group(1) if mono else line
        if not message.strip():
            continue
        if timestamp is not None and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        entries.append(
            EvidenceItem(
                evidence_id=f"DMS-{len(entries) + 1:06d}",
                source=SOURCE_DMESG,
                boot_id=boot_id,
                message=decode_message(message),
                timestamp=timestamp,
                provenance={"_TRANSPORT": "kernel"},
            )
        )
    return tuple(entries)


def _slice_coverage(
    source: str, res: CommandResult, parsed: SliceParse, cap: int
) -> SourceCoverage:
    state = res.state
    head_truncated = False
    tail_reliable = state in (SourceState.AVAILABLE, SourceState.EMPTY)
    details: list[str] = []
    if state is SourceState.AVAILABLE and len(parsed.entries) + parsed.skipped == cap:
        state = SourceState.TRUNCATED
        head_truncated = True
        tail_reliable = True
    elif state is SourceState.TRUNCATED:
        tail_reliable = False
        details.append("byte cap reached")
    if parsed.skipped:
        details.append(f"{parsed.skipped} malformed lines skipped")
    if res.stderr_detail:
        details.append(res.stderr_detail)
    return SourceCoverage(
        source=source,
        state=state,
        detail="; ".join(details),
        entry_count=len(parsed.entries),
        head_truncated=head_truncated,
        tail_reliable=tail_reliable,
        elapsed_ms=res.elapsed_ms,
    )


def _collect_dmesg(
    ctx: CollectionContext, boot_id: str
) -> tuple[tuple[EvidenceItem, ...], SourceCoverage]:
    res = ctx.runner(
        DMESG_ISO_ARGV, timeout_s=DMESG_TIMEOUT_S, max_bytes=DMESG_MAX_BYTES, cancel=ctx.cancel
    )
    details: list[str] = []
    if res.state is SourceState.ERROR and "time format" in res.stderr_detail.lower():
        res = ctx.runner(
            DMESG_PLAIN_ARGV,
            timeout_s=DMESG_TIMEOUT_S,
            max_bytes=DMESG_MAX_BYTES,
            cancel=ctx.cancel,
        )
        details.append("iso time format unsupported; collected without timestamps")
    entries = parse_dmesg(res.stdout.decode("utf-8", errors="replace"), boot_id)
    tail_reliable = res.state in (SourceState.AVAILABLE, SourceState.EMPTY)
    if res.state is SourceState.TRUNCATED:
        details.append("byte cap reached")
    if entries and all(e.timestamp is None for e in entries):
        details.append("no parseable timestamps; excluded from timeline")
    if res.stderr_detail:
        details.append(res.stderr_detail)
    coverage = SourceCoverage(
        source=SOURCE_DMESG,
        state=res.state,
        detail="; ".join(details),
        entry_count=len(entries),
        tail_reliable=tail_reliable,
        elapsed_ms=res.elapsed_ms,
    )
    return entries, coverage


def collect_journal(ctx: CollectionContext) -> CollectorResult:
    boot = ctx.boot
    if boot is None:
        raise ValueError("collect_journal requires a selected boot in ctx")

    kres = ctx.runner(
        kernel_argv(boot.boot_id),
        timeout_s=JOURNAL_TIMEOUT_S,
        max_bytes=KERNEL_MAX_BYTES,
        cancel=ctx.cancel,
    )
    sres = ctx.runner(
        system_argv(boot.boot_id),
        timeout_s=JOURNAL_TIMEOUT_S,
        max_bytes=SYSTEM_MAX_BYTES,
        cancel=ctx.cancel,
    )
    kparse = parse_journal_slice(
        kres.stdout.decode("utf-8", errors="replace"), SOURCE_JOURNAL_KERNEL
    )
    sparse = parse_journal_slice(
        sres.stdout.decode("utf-8", errors="replace"), SOURCE_JOURNAL_SYSTEM
    )
    merged = merge_entries(kparse.entries, sparse.entries)
    journal_evidence = to_evidence(merged, boot.boot_id)

    release = extract_kernel_release(merged)
    updated_boot = replace(
        boot,
        first_entry=merged[0].timestamp if merged else boot.first_entry,
        last_entry=merged[-1].timestamp if merged else boot.last_entry,
        kernel_release=release if release is not None else boot.kernel_release,
    )

    if boot.is_current:
        dmesg_evidence, dmesg_coverage = _collect_dmesg(ctx, boot.boot_id)
    else:
        dmesg_evidence = ()
        dmesg_coverage = SourceCoverage(
            source=SOURCE_DMESG,
            state=SourceState.UNSUPPORTED,
            detail="dmesg covers only the current boot; not available for historical boots",
            tail_reliable=False,
        )

    coverage = (
        _slice_coverage(SOURCE_JOURNAL_KERNEL, kres, kparse, KERNEL_ENTRY_CAP),
        _slice_coverage(SOURCE_JOURNAL_SYSTEM, sres, sparse, SYSTEM_ENTRY_CAP),
        dmesg_coverage,
    )
    payload = JournalPayload(entries=journal_evidence + dmesg_evidence, boot=updated_boot)
    return CollectorResult(payload=payload, coverage=coverage)
