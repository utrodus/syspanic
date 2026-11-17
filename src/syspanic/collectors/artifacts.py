"""Bounded crash-artifact collection and boot association (docs/02 §10, docs/04 §7).

Binary vmcore is never opened; only names, sizes, mtimes, and association are read.
Text artifacts become VMD-*/PST-* evidence; metadata records become AFM-* upstream.
"""

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from syspanic.collectors.base import CollectionContext, CollectorResult
from syspanic.collectors.journal import decode_message
from syspanic.constants import (
    CRASH_MAX_ENTRIES,
    CRASH_MAX_INCIDENT_DIRS,
    FIXED_READ_MAX_BYTES,
    PSTORE_MAX_BYTES,
    PSTORE_MAX_RECORDS,
    SOURCE_CRASH_KEXEC,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    VMCORE_DMESG_MAX_BYTES,
    VMCORE_DMESG_MAX_LINES,
)
from syspanic.domain.enums import ArtifactAssociation, SourceState
from syspanic.domain.models import (
    ArtifactInfo,
    BootInfo,
    CollectionIssue,
    CrashArtifacts,
    EvidenceItem,
    SourceCoverage,
)

VAR_CRASH_ROOT = "/var/crash"
PSTORE_ROOTS = ("/sys/fs/pstore", "/var/lib/systemd/pstore")
KEXEC_LOADED_PATH = "/sys/kernel/kexec_crash_loaded"
KEXEC_SIZE_PATH = "/sys/kernel/kexec_crash_size"

_WINDOW_MARGIN = timedelta(minutes=5)
_INCIDENT_TS = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2})$")
_ISO_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[0-9:.,+-]+)\s+(.*)$")
_KERNEL_RELEASE = re.compile(r"Linux version (\S+)")


@dataclass(frozen=True)
class ArtifactCollection:
    artifacts: CrashArtifacts
    entries: tuple[EvidenceItem, ...] = ()


def _read_fixed_path(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(FIXED_READ_MAX_BYTES)
    except OSError:
        return None


def _read_artifact_text(path: str, max_bytes: int = VMCORE_DMESG_MAX_BYTES) -> str:
    with open(path, "rb") as handle:
        data = handle.read(max_bytes)
    return data.decode("utf-8", errors="replace")


def associate(
    boot: BootInfo | None,
    *,
    text: str = "",
    mtime: datetime | None = None,
    incident_dir: str | None = None,
) -> tuple[ArtifactAssociation, str]:
    if boot is None:
        return ArtifactAssociation.UNKNOWN, "no boot selected"
    if boot.boot_id in text or (incident_dir and boot.boot_id in incident_dir):
        return (
            ArtifactAssociation.MATCHED,
            "selected boot ID found in artifact text or incident path",
        )
    window = None
    if boot.first_entry is not None and boot.last_entry is not None:
        window = (boot.first_entry - _WINDOW_MARGIN, boot.last_entry + _WINDOW_MARGIN)
    incident_ts = None
    if incident_dir:
        match = _INCIDENT_TS.search(os.path.basename(incident_dir))
        if match:
            try:
                incident_ts = datetime.strptime(match.group(1), "%Y-%m-%d-%H:%M:%S").replace(
                    tzinfo=UTC
                )
            except ValueError:
                incident_ts = None
    if window and incident_ts and window[0] <= incident_ts <= window[1]:
        release = _KERNEL_RELEASE.search(text)
        if release and boot.kernel_release and release.group(1) == boot.kernel_release:
            return (
                ArtifactAssociation.POSSIBLY_RELATED,
                "incident timestamp within boot window and kernel release matches; "
                "boot identity not proven",
            )
        return (
            ArtifactAssociation.POSSIBLY_RELATED,
            "incident timestamp within boot window; boot identity not proven",
        )
    if window and mtime and window[0] <= mtime <= window[1]:
        return (
            ArtifactAssociation.POSSIBLY_RELATED,
            "mtime near boot window; boot identity not proven",
        )
    return ArtifactAssociation.UNKNOWN, "no boot identity evidence in artifact metadata"


def _text_evidence(
    text: str,
    *,
    prefix: str,
    source: str,
    boot_id: str,
    start_index: int,
    max_lines: int | None = None,
) -> tuple[tuple[EvidenceItem, ...], int, bool]:
    lines = text.splitlines()
    line_capped = max_lines is not None and len(lines) > max_lines
    if max_lines is not None:
        lines = lines[:max_lines]
    items: list[EvidenceItem] = []
    index = start_index
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        timestamp = None
        message = line
        match = _ISO_LINE.match(line)
        if match:
            try:
                timestamp = datetime.fromisoformat(match.group(1))
                message = match.group(2)
            except ValueError:
                timestamp = None
        items.append(
            EvidenceItem(
                evidence_id=f"{prefix}{index:06d}",
                source=source,
                boot_id=boot_id,
                message=decode_message(message),
                timestamp=timestamp,
                line_no=line_no,
            )
        )
        index += 1
    return tuple(items), index, line_capped


def _coverage(source: str, state: SourceState, detail: str = "", count: int = 0) -> SourceCoverage:
    reliable = state not in (
        SourceState.PERMISSION_DENIED,
        SourceState.TIMEOUT,
        SourceState.ERROR,
    )
    return SourceCoverage(
        source=source, state=state, detail=detail, entry_count=count, tail_reliable=reliable
    )


def collect_artifacts(
    ctx: CollectionContext,
    *,
    crash_root: str = VAR_CRASH_ROOT,
    pstore_roots: tuple[str, ...] = PSTORE_ROOTS,
    read_text=_read_fixed_path,
) -> CollectorResult:
    boot = ctx.boot
    boot_id = boot.boot_id if boot else ""
    notes: list[str] = []
    issues: list[CollectionIssue] = []
    vmcore_files: list[ArtifactInfo] = []
    vmcore_dmesg: list[ArtifactInfo] = []
    pstore_records: list[ArtifactInfo] = []
    entries: list[EvidenceItem] = []
    budget = CRASH_MAX_ENTRIES
    budget_noted = False

    def cancelled() -> bool:
        return ctx.cancel is not None and ctx.cancel.is_set()

    if cancelled():
        return CollectorResult(
            payload=ArtifactCollection(CrashArtifacts(notes=("collection cancelled",))),
            coverage=(
                _coverage(SOURCE_CRASH_VMCORE, SourceState.ERROR, "cancelled before scan"),
                _coverage(SOURCE_CRASH_VMCORE_DMESG, SourceState.ERROR, "cancelled before scan"),
                _coverage(SOURCE_CRASH_PSTORE, SourceState.ERROR, "cancelled before scan"),
                _coverage(SOURCE_CRASH_KEXEC, SourceState.ERROR, "cancelled before scan"),
            ),
            issues=(CollectionIssue(SOURCE_CRASH_VMCORE, "collection cancelled before scan"),),
        )

    def take_budget() -> bool:
        nonlocal budget, budget_noted
        if budget <= 0:
            if not budget_noted:
                notes.append(f"artifact entry limit reached ({CRASH_MAX_ENTRIES}); list bounded")
                budget_noted = True
            return False
        budget -= 1
        return True

    def record_vmcore(entry: os.DirEntry, incident_dir: str | None) -> None:
        stat = entry.stat(follow_symlinks=False)
        mtime = datetime.fromtimestamp(stat.st_mtime, UTC)
        association, reason = associate(boot, mtime=mtime, incident_dir=incident_dir)
        vmcore_files.append(
            ArtifactInfo(
                path=entry.path,
                kind="vmcore",
                size_bytes=stat.st_size,
                readable=False,
                association=association,
                association_reason=reason,
                mtime=mtime,
                incident_dir=incident_dir,
                note="binary dump; metadata only, never opened",
            )
        )

    def record_dmesg(entry: os.DirEntry, incident_dir: str | None) -> None:
        nonlocal dmesg_state, dmesg_detail
        stat = entry.stat(follow_symlinks=False)
        mtime = datetime.fromtimestamp(stat.st_mtime, UTC)
        text = ""
        readable = True
        try:
            text = _read_artifact_text(entry.path)
        except PermissionError:
            readable = False
            dmesg_state = SourceState.PERMISSION_DENIED
            dmesg_detail = "permission denied reading vmcore-dmesg.txt"
            issues.append(CollectionIssue(SOURCE_CRASH_VMCORE_DMESG, dmesg_detail))
        except OSError as exc:
            readable = False
            dmesg_state = SourceState.ERROR
            dmesg_detail = f"read failed: {exc.__class__.__name__}"
            issues.append(CollectionIssue(SOURCE_CRASH_VMCORE_DMESG, dmesg_detail))
        association, reason = associate(
            boot, text=text, mtime=mtime, incident_dir=incident_dir
        )
        note = ""
        if readable and stat.st_size > VMCORE_DMESG_MAX_BYTES:
            note = f"byte cap reached ({VMCORE_DMESG_MAX_BYTES} bytes); text truncated"
            notes.append(note)
        vmcore_dmesg.append(
            ArtifactInfo(
                path=entry.path,
                kind="vmcore-dmesg",
                size_bytes=stat.st_size,
                readable=readable,
                association=association,
                association_reason=reason,
                mtime=mtime,
                incident_dir=incident_dir,
                note=note,
            )
        )
        if readable:
            nonlocal vmd_index
            items, vmd_index, line_capped = _text_evidence(
                text,
                prefix="VMD-",
                source=SOURCE_CRASH_VMCORE_DMESG,
                boot_id=boot_id,
                start_index=vmd_index,
                max_lines=VMCORE_DMESG_MAX_LINES,
            )
            entries.extend(items)
            if line_capped:
                notes.append(f"line cap reached ({VMCORE_DMESG_MAX_LINES} lines); text truncated")

    crash_state = SourceState.AVAILABLE
    crash_detail = ""
    dmesg_state: SourceState | None = None
    dmesg_detail = ""
    vmd_index = 0
    root_entries: list[os.DirEntry] = []
    try:
        with os.scandir(crash_root) as iterator:
            root_entries = sorted(iterator, key=lambda e: e.name)
    except FileNotFoundError:
        crash_state = SourceState.NOT_FOUND
        crash_detail = "crash root not present"
    except PermissionError:
        crash_state = SourceState.PERMISSION_DENIED
        crash_detail = "permission denied reading crash root"
        issues.append(CollectionIssue(SOURCE_CRASH_VMCORE, crash_detail))
    except OSError as exc:
        crash_state = SourceState.ERROR
        crash_detail = f"scan failed: {exc.__class__.__name__}"
        issues.append(CollectionIssue(SOURCE_CRASH_VMCORE, crash_detail))

    incident_dirs = 0
    incident_limit_noted = False
    for entry in root_entries:
        if cancelled():
            break
        if entry.is_symlink():
            continue
        if entry.is_file(follow_symlinks=False):
            if entry.name == "vmcore-dmesg.txt":
                if take_budget():
                    record_dmesg(entry, None)
            elif entry.name.startswith("vmcore") and take_budget():
                record_vmcore(entry, None)
        elif entry.is_dir(follow_symlinks=False):
            if incident_dirs >= CRASH_MAX_INCIDENT_DIRS:
                if not incident_limit_noted:
                    notes.append(
                        f"incident directory limit reached ({CRASH_MAX_INCIDENT_DIRS}); "
                        "scan bounded"
                    )
                    incident_limit_noted = True
                continue
            incident_dirs += 1
            try:
                with os.scandir(entry.path) as iterator:
                    children = sorted(iterator, key=lambda e: e.name)
            except OSError:
                issues.append(
                    CollectionIssue(SOURCE_CRASH_VMCORE, f"incident dir not readable: {entry.name}")
                )
                continue
            for child in children:
                if cancelled():
                    break
                if child.is_symlink() or not child.is_file(follow_symlinks=False):
                    continue
                if child.name == "vmcore-dmesg.txt":
                    if take_budget():
                        record_dmesg(child, entry.path)
                elif child.name.startswith("vmcore") and take_budget():
                    record_vmcore(child, entry.path)

    pstore_state = SourceState.NOT_FOUND
    pstore_detail = "pstore roots not present"
    pst_index = 0
    for root in pstore_roots:
        if cancelled():
            break
        try:
            with os.scandir(root) as iterator:
                children = sorted(iterator, key=lambda e: e.name)
        except FileNotFoundError:
            continue
        except PermissionError:
            pstore_state = SourceState.PERMISSION_DENIED
            pstore_detail = "permission denied reading pstore root"
            issues.append(CollectionIssue(SOURCE_CRASH_PSTORE, pstore_detail))
            continue
        except OSError as exc:
            pstore_state = SourceState.ERROR
            pstore_detail = f"scan failed: {exc.__class__.__name__}"
            issues.append(CollectionIssue(SOURCE_CRASH_PSTORE, pstore_detail))
            continue
        if pstore_state is SourceState.NOT_FOUND:
            pstore_state = SourceState.EMPTY
            pstore_detail = ""
        for child in children:
            if cancelled():
                break
            if child.is_symlink() or not child.is_file(follow_symlinks=False):
                continue
            if len(pstore_records) >= PSTORE_MAX_RECORDS:
                notes.append(f"pstore record limit reached ({PSTORE_MAX_RECORDS}); list bounded")
                break
            if not take_budget():
                break
            stat = child.stat(follow_symlinks=False)
            mtime = datetime.fromtimestamp(stat.st_mtime, UTC)
            text = ""
            readable = True
            try:
                text = _read_artifact_text(child.path, max_bytes=PSTORE_MAX_BYTES)
            except OSError:
                readable = False
            association, reason = associate(boot, text=text, mtime=mtime)
            note = ""
            if readable and stat.st_size > PSTORE_MAX_BYTES:
                note = f"byte cap reached ({PSTORE_MAX_BYTES} bytes); text truncated"
                notes.append(note)
            pstore_records.append(
                ArtifactInfo(
                    path=child.path,
                    kind="pstore",
                    size_bytes=stat.st_size,
                    readable=readable,
                    association=association,
                    association_reason=reason,
                    mtime=mtime,
                    note=note,
                )
            )
            if readable:
                items, pst_index, _ = _text_evidence(
                    text,
                    prefix="PST-",
                    source=SOURCE_CRASH_PSTORE,
                    boot_id=boot_id,
                    start_index=pst_index,
                )
                entries.extend(items)
                pstore_state = SourceState.AVAILABLE
                pstore_detail = ""

    loaded_text = read_text(KEXEC_LOADED_PATH)
    read_text(KEXEC_SIZE_PATH)
    loaded: bool | None = None
    if loaded_text is not None:
        stripped = loaded_text.strip()
        if stripped == "1":
            loaded = True
        elif stripped == "0":
            loaded = False
    kexec_state = SourceState.AVAILABLE if loaded_text is not None else SourceState.NOT_FOUND

    if crash_state is SourceState.AVAILABLE and not vmcore_files:
        crash_state = SourceState.EMPTY
    if dmesg_state is None:
        if crash_state is SourceState.NOT_FOUND:
            dmesg_state = SourceState.NOT_FOUND
            dmesg_detail = crash_detail
        elif vmcore_dmesg:
            dmesg_state = SourceState.AVAILABLE
        else:
            dmesg_state = SourceState.EMPTY

    artifacts = CrashArtifacts(
        vmcore_files=tuple(vmcore_files),
        vmcore_dmesg=tuple(vmcore_dmesg),
        pstore_records=tuple(pstore_records),
        crash_kernel_loaded=loaded,
        notes=tuple(notes),
    )
    coverage = (
        _coverage(SOURCE_CRASH_VMCORE, crash_state, crash_detail, len(vmcore_files)),
        _coverage(SOURCE_CRASH_VMCORE_DMESG, dmesg_state, dmesg_detail, len(vmcore_dmesg)),
        _coverage(SOURCE_CRASH_PSTORE, pstore_state, pstore_detail, len(pstore_records)),
        _coverage(
            SOURCE_CRASH_KEXEC,
            kexec_state,
            "" if loaded_text is not None else "kexec state not readable",
        ),
    )
    return CollectorResult(
        payload=ArtifactCollection(artifacts, tuple(entries)),
        coverage=coverage,
        issues=tuple(issues),
    )
