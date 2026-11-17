"""Run all collectors for one boot; merge coverage, isolate failures (docs/02 §6)."""

import threading
import time
from collections.abc import Callable
from functools import partial

from syspanic.collectors.artifacts import ArtifactCollection, collect_artifacts
from syspanic.collectors.base import CollectionContext, CollectorResult
from syspanic.collectors.boots import collect_boots
from syspanic.collectors.journal import JournalPayload, collect_journal
from syspanic.collectors.metadata import artifacts_to_evidence, boots_to_evidence
from syspanic.collectors.system import collect_system
from syspanic.constants import (
    SOURCE_CRASH_KEXEC,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_DMESG,
    SOURCE_JOURNAL_BOOTS,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_OS,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import (
    BootInfo,
    CollectionBundle,
    CollectionIssue,
    SourceCoverage,
)

RUN_BUDGET_S = 120.0
ALL_SOURCES = (
    SOURCE_JOURNAL_BOOTS,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
    SOURCE_DMESG,
    SOURCE_SYSTEM_OS,
    SOURCE_SYSTEM_CPU,
    SOURCE_SYSTEM_MEMORY,
    SOURCE_SYSTEM_GPU,
    SOURCE_SYSTEM_FIRMWARE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_KEXEC,
)
_STAGE_SOURCES = (
    (SOURCE_JOURNAL_BOOTS,),
    (SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM, SOURCE_DMESG),
    (
        SOURCE_SYSTEM_OS,
        SOURCE_SYSTEM_CPU,
        SOURCE_SYSTEM_MEMORY,
        SOURCE_SYSTEM_GPU,
        SOURCE_SYSTEM_FIRMWARE,
    ),
    (
        SOURCE_CRASH_VMCORE,
        SOURCE_CRASH_VMCORE_DMESG,
        SOURCE_CRASH_PSTORE,
        SOURCE_CRASH_KEXEC,
    ),
)


def _failed_coverage(sources: tuple[str, ...], detail: str) -> tuple[SourceCoverage, ...]:
    return tuple(
        SourceCoverage(
            source=source, state=SourceState.ERROR, detail=detail, tail_reliable=False
        )
        for source in sources
    )


def collect_bundle(
    boot: BootInfo,
    *,
    runner: Callable,
    cancel: threading.Event | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    read_boot_id: Callable[[], str | None] | None = None,
    crash_root: str | None = None,
    pstore_roots: tuple[str, ...] | None = None,
    read_text: Callable | None = None,
    budget_s: float = RUN_BUDGET_S,
    monotonic: Callable[[], float] = time.monotonic,
    boots_collector: Callable = collect_boots,
    journal_collector: Callable = collect_journal,
    system_collector: Callable = collect_system,
    artifacts_collector: Callable = collect_artifacts,
) -> CollectionBundle:
    coverage: list[SourceCoverage] = []
    issues: list[CollectionIssue] = []
    entries = []
    boots: tuple[BootInfo, ...] = ()
    system = None
    artifacts = None
    journal_boot = boot
    seen: set[str] = set()

    def merge(result: CollectorResult) -> None:
        for item in result.coverage:
            if item.source in seen:
                raise ValueError(f"duplicate source name: {item.source}")
            seen.add(item.source)
            coverage.append(item)
        issues.extend(result.issues)

    def remaining_sources(start_stage: int) -> tuple[str, ...]:
        return tuple(s for stage in _STAGE_SOURCES[start_stage:] for s in stage)

    if cancel is not None and cancel.is_set():
        coverage.extend(_failed_coverage(ALL_SOURCES, "cancelled before collection"))
    else:
        deadline = monotonic() + budget_s
        ctx = CollectionContext(boot=boot, cancel=cancel, runner=runner)
        if boots_collector is collect_boots and read_boot_id is not None:
            boots_call = partial(collect_boots, read_boot_id=read_boot_id)
        else:
            boots_call = boots_collector
        artifact_kwargs = {}
        if crash_root is not None:
            artifact_kwargs["crash_root"] = crash_root
        if pstore_roots is not None:
            artifact_kwargs["pstore_roots"] = pstore_roots
        if read_text is not None:
            artifact_kwargs["read_text"] = read_text
        if artifacts_collector is collect_artifacts and artifact_kwargs:
            artifacts_call = partial(collect_artifacts, **artifact_kwargs)
        else:
            artifacts_call = artifacts_collector
        stages = (
            boots_call,
            journal_collector,
            system_collector,
            artifacts_call,
        )
        index = 0
        for stage_no, (sources, collect) in enumerate(zip(_STAGE_SOURCES, stages, strict=True)):
            if monotonic() > deadline:
                rest = remaining_sources(stage_no)
                coverage.extend(
                    SourceCoverage(
                        source=source,
                        state=SourceState.TIMEOUT,
                        detail="overall run budget exceeded",
                        tail_reliable=False,
                    )
                    for source in rest
                )
                issues.append(
                    CollectionIssue(sources[0], "overall run budget exceeded (120 s)")
                )
                break
            for source in sources:
                index += 1
                if progress is not None:
                    progress(source, index, len(ALL_SOURCES))
            try:
                result = collect(ctx)
            except Exception as exc:
                detail = f"collection failed: {exc.__class__.__name__}"
                coverage.extend(_failed_coverage(sources, detail))
                issues.append(CollectionIssue(sources[0], detail))
                continue
            merge(result)
            if stage_no == 0:
                boots = tuple(result.payload)
            elif stage_no == 1:
                payload: JournalPayload = result.payload
                entries.extend(payload.entries)
                journal_boot = payload.boot
            elif stage_no == 2:
                system = result.payload
            else:
                artifact_payload: ArtifactCollection = result.payload
                artifacts = artifact_payload.artifacts
                entries.extend(artifact_payload.entries)
            if cancel is not None and cancel.is_set():
                rest = remaining_sources(stage_no + 1)
                coverage.extend(_failed_coverage(rest, "cancelled during collection"))
                break

    entries.extend(boots_to_evidence(boots))
    if artifacts is not None:
        entries.extend(artifacts_to_evidence(artifacts, journal_boot.boot_id))
    hostname_hint = next(
        (
            e.provenance.get("_HOSTNAME")
            for e in entries
            if e.provenance.get("_HOSTNAME")
        ),
        None,
    )
    return CollectionBundle(
        boot=journal_boot,
        boots=boots,
        entries=tuple(entries),
        coverage=tuple(coverage),
        system=system,
        artifacts=artifacts,
        issues=tuple(issues),
        demo=False,
        hostname_hint=hostname_hint,
    )
