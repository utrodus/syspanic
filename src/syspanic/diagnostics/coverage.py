"""Coverage aggregation: completeness, tail gating, limitation wording (docs/04 §9)."""

from syspanic.constants import SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM
from syspanic.domain.enums import SourceState
from syspanic.domain.models import SourceCoverage

UNAVAILABLE_SOURCE_NOTE = "This source was unavailable, so related events could not be assessed."
TAIL_UNRELIABLE_NOTE = (
    "The journal tail was not reliably collected; shutdown-sequence absence could not be assessed."
)
_READ_STATES = (SourceState.AVAILABLE, SourceState.TRUNCATED)


def tail_reliable(coverage: tuple[SourceCoverage, ...]) -> bool:
    by_source = {c.source: c for c in coverage}
    kernel = by_source.get(SOURCE_JOURNAL_KERNEL)
    system = by_source.get(SOURCE_JOURNAL_SYSTEM)
    if kernel is None or system is None:
        return False
    for source in (kernel, system):
        if source.state not in _READ_STATES:
            return False
        if not source.tail_reliable or source.entry_count == 0:
            return False
    return True


def overall_completeness(coverage: tuple[SourceCoverage, ...]) -> str:
    by_source = {c.source: c for c in coverage}
    kernel = by_source.get(SOURCE_JOURNAL_KERNEL)
    system = by_source.get(SOURCE_JOURNAL_SYSTEM)
    journal_ok = (
        kernel is not None
        and system is not None
        and kernel.state in _READ_STATES
        and system.state in _READ_STATES
    )
    if not journal_ok:
        return "minimal"
    for source in coverage:
        if source.source in (SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM):
            continue
        if source.state not in _READ_STATES and source.state is not SourceState.EMPTY:
            return "partial"
    return "complete"
