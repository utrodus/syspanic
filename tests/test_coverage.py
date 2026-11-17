"""T-014: coverage aggregation, completeness, tail gating, limitation strings."""

from rule_fixtures import entry, make_bundle
from syspanic.constants import (
    SOURCE_DMESG,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
    SOURCE_SYSTEM_GPU,
)
from syspanic.diagnostics.coverage import (
    TAIL_UNRELIABLE_NOTE,
    UNAVAILABLE_SOURCE_NOTE,
    overall_completeness,
    tail_reliable,
)
from syspanic.domain.enums import SourceState
from syspanic.domain.models import SourceCoverage


def cov(source, state, *, tail=True, count=1):
    return SourceCoverage(
        source=source, state=state, entry_count=count, tail_reliable=tail
    )


def test_complete_when_required_available():
    coverage = (
        cov(SOURCE_JOURNAL_KERNEL, SourceState.AVAILABLE),
        cov(SOURCE_JOURNAL_SYSTEM, SourceState.AVAILABLE),
        cov(SOURCE_SYSTEM_GPU, SourceState.AVAILABLE),
    )
    assert overall_completeness(coverage) == "complete"


def test_truncated_counts_as_read():
    coverage = (
        cov(SOURCE_JOURNAL_KERNEL, SourceState.TRUNCATED),
        cov(SOURCE_JOURNAL_SYSTEM, SourceState.AVAILABLE),
    )
    assert overall_completeness(coverage) == "complete"


def test_partial_when_optional_missing():
    coverage = (
        cov(SOURCE_JOURNAL_KERNEL, SourceState.AVAILABLE),
        cov(SOURCE_JOURNAL_SYSTEM, SourceState.AVAILABLE),
        cov(SOURCE_SYSTEM_GPU, SourceState.NOT_FOUND),
    )
    assert overall_completeness(coverage) == "partial"


def test_unsupported_dmesg_makes_partial():
    coverage = (
        cov(SOURCE_JOURNAL_KERNEL, SourceState.AVAILABLE),
        cov(SOURCE_JOURNAL_SYSTEM, SourceState.AVAILABLE),
        cov(SOURCE_DMESG, SourceState.UNSUPPORTED, tail=False),
    )
    assert overall_completeness(coverage) == "partial"


def test_empty_optional_is_not_missing():
    coverage = (
        cov(SOURCE_JOURNAL_KERNEL, SourceState.AVAILABLE),
        cov(SOURCE_JOURNAL_SYSTEM, SourceState.AVAILABLE),
        cov(SOURCE_DMESG, SourceState.EMPTY, count=0),
    )
    assert overall_completeness(coverage) == "complete"


def test_minimal_when_journal_unavailable():
    coverage = (
        cov(SOURCE_JOURNAL_KERNEL, SourceState.PERMISSION_DENIED, tail=False),
        cov(SOURCE_JOURNAL_SYSTEM, SourceState.ERROR, tail=False),
    )
    assert overall_completeness(coverage) == "minimal"


def test_minimal_when_journal_missing_entirely():
    assert overall_completeness(()) == "minimal"


def test_tail_reliable_requires_both_sources():
    entries = [entry("kernel: ok", 0)]
    bundle = make_bundle(entries)
    assert tail_reliable(bundle.coverage) is False


def test_tail_reliable_true_for_clean_slices():
    from rule_fixtures import filler

    entries = filler(5) + filler(5, start=10, source=SOURCE_JOURNAL_SYSTEM)
    bundle = make_bundle(entries)
    assert tail_reliable(bundle.coverage) is True


def test_tail_unreliable_on_byte_cap_state():
    from rule_fixtures import default_coverage, filler

    entries = filler(5) + filler(5, start=10, source=SOURCE_JOURNAL_SYSTEM)
    coverage = default_coverage(entries, kernel_state=SourceState.TIMEOUT, kernel_tail=False)
    assert tail_reliable(coverage) is False


def test_limitation_strings_exact():
    assert UNAVAILABLE_SOURCE_NOTE == (
        "This source was unavailable, so related events could not be assessed."
    )
    assert TAIL_UNRELIABLE_NOTE == (
        "The journal tail was not reliably collected; "
        "shutdown-sequence absence could not be assessed."
    )
