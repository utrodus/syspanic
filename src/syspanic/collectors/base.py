"""Collector contract per docs/02 §6. No Qt, no I/O beyond the shared runner."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from syspanic.collectors.runner import CommandResult, run
from syspanic.domain.models import BootInfo, CollectionIssue, SourceCoverage


@dataclass(frozen=True)
class CollectionContext:
    boot: BootInfo | None = None
    cancel: threading.Event | None = None
    runner: Callable[..., CommandResult] = run


@dataclass(frozen=True)
class CollectorResult:
    payload: object
    coverage: tuple[SourceCoverage, ...]
    issues: tuple[CollectionIssue, ...] = ()


class Collector(Protocol):
    name: str

    def collect(self, ctx: CollectionContext) -> CollectorResult: ...
