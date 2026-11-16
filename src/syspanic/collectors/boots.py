"""Boot enumeration per docs/02 §8.1–3: JSON list, text fallback, /proc fallback.

Boot IDs are stored undashed; --list-boots timestamps are display hints only.
The current boot (index 0) is verified against /proc/sys/kernel/random/boot_id.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime

from syspanic.collectors.base import CollectionContext, CollectorResult
from syspanic.collectors.runner import CommandResult
from syspanic.constants import BOOTS_MAX_BYTES, JOURNAL_TIMEOUT_S, SOURCE_JOURNAL_BOOTS
from syspanic.domain.enums import SourceState
from syspanic.domain.models import BootInfo, CollectionIssue, SourceCoverage

LIST_BOOTS_JSON_ARGV = ("journalctl", "--list-boots", "--output=json", "--no-pager")
LIST_BOOTS_TEXT_ARGV = ("journalctl", "--list-boots", "--no-pager")
PROC_BOOT_ID_PATH = "/proc/sys/kernel/random/boot_id"

_BOOT_ID_RE = re.compile(r"[0-9a-f]{32}")
_DASHED_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def normalize_boot_id(raw: str) -> str | None:
    candidate = raw.strip().lower()
    if _DASHED_BOOT_ID_RE.fullmatch(candidate):
        candidate = candidate.replace("-", "")
    return candidate if _BOOT_ID_RE.fullmatch(candidate) else None


def _from_us(value: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000, tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _boot_from_row(row: dict) -> BootInfo | None:
    boot_id = normalize_boot_id(str(row.get("boot_id", "")))
    if boot_id is None:
        return None
    try:
        index = int(row["index"])
    except (KeyError, TypeError, ValueError):
        return None
    return BootInfo(
        index=index,
        boot_id=boot_id,
        is_current=index == 0,
        first_entry=_from_us(row.get("first_entry")),
        last_entry=_from_us(row.get("last_entry")),
    )


def parse_boots_json(text: str) -> tuple[BootInfo, ...] | None:
    rows: list[dict] = []
    try:
        data = json.loads(text)
    except ValueError:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                return None
            if isinstance(obj, dict):
                rows.append(obj)
    else:
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            rows = [data]
    boots = [b for b in (_boot_from_row(r) for r in rows) if b is not None]
    if not boots:
        return None
    return tuple(sorted(boots, key=lambda b: b.index))


def parse_boots_text(text: str) -> tuple[BootInfo, ...] | None:
    boots: list[BootInfo] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        boot_id = normalize_boot_id(parts[1])
        if boot_id is None:
            continue
        boots.append(BootInfo(index=index, boot_id=boot_id, is_current=index == 0))
    if not boots:
        return None
    return tuple(sorted(boots, key=lambda b: b.index))


def _read_proc_boot_id() -> str | None:
    try:
        with open(PROC_BOOT_ID_PATH, encoding="ascii") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _run_list(ctx: CollectionContext, argv: tuple[str, ...]) -> CommandResult:
    return ctx.runner(
        argv, timeout_s=JOURNAL_TIMEOUT_S, max_bytes=BOOTS_MAX_BYTES, cancel=ctx.cancel
    )


def collect_boots(
    ctx: CollectionContext,
    *,
    read_boot_id: Callable[[], str | None] = _read_proc_boot_id,
) -> CollectorResult:
    proc_raw = read_boot_id()
    proc_id = normalize_boot_id(proc_raw) if proc_raw else None

    res = _run_list(ctx, LIST_BOOTS_JSON_ARGV)
    boots: tuple[BootInfo, ...] | None = None
    details: list[str] = []
    if res.state is SourceState.AVAILABLE:
        boots = parse_boots_json(res.stdout.decode("utf-8", errors="replace"))
    if boots is None:
        text_res = _run_list(ctx, LIST_BOOTS_TEXT_ARGV)
        if text_res.state is SourceState.AVAILABLE:
            boots = parse_boots_text(text_res.stdout.decode("utf-8", errors="replace"))
            if boots is not None:
                details.append("text table fallback")
        if boots is None:
            state = res.state if res.state is not SourceState.AVAILABLE else SourceState.ERROR
            if proc_id is not None:
                boots = (BootInfo(index=0, boot_id=proc_id, is_current=True),)
                details.append(
                    f"boot list unavailable ({state.value}); current boot from /proc fallback"
                )
                coverage = SourceCoverage(
                    source=SOURCE_JOURNAL_BOOTS,
                    state=state,
                    detail="; ".join(details),
                    entry_count=1,
                    tail_reliable=False,
                    elapsed_ms=res.elapsed_ms,
                )
                return CollectorResult(payload=boots, coverage=(coverage,))
            details.append("boot list unavailable; /proc fallback also failed")
            coverage = SourceCoverage(
                source=SOURCE_JOURNAL_BOOTS,
                state=state,
                detail="; ".join(details),
                entry_count=0,
                tail_reliable=False,
                elapsed_ms=res.elapsed_ms,
            )
            issue = CollectionIssue(
                source=SOURCE_JOURNAL_BOOTS,
                detail="boot enumeration failed; no current boot available",
            )
            return CollectorResult(payload=(), coverage=(coverage,), issues=(issue,))

    if proc_id is None:
        details.append("current boot could not be verified against /proc")
    else:
        current = next((b for b in boots if b.index == 0), None)
        if current is None:
            details.append("no index-0 boot in journal list")
        elif current.boot_id != proc_id:
            details.append(
                f"current boot mismatch: journal {current.boot_id[:8]} vs /proc {proc_id[:8]}"
            )
    coverage = SourceCoverage(
        source=SOURCE_JOURNAL_BOOTS,
        state=SourceState.AVAILABLE,
        detail="; ".join(details),
        entry_count=len(boots),
        tail_reliable=True,
        elapsed_ms=res.elapsed_ms,
    )
    return CollectorResult(payload=boots, coverage=(coverage,))
