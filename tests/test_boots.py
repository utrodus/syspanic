"""T-005 boot enumeration — docs/02 §8.1–3, plan §2.

Synthetic fixtures and injected fake runners/readers only; never reads the real host.
"""

import json
from datetime import UTC, datetime

import pytest

from syspanic.collectors.base import CollectionContext
from syspanic.collectors.boots import (
    LIST_BOOTS_JSON_ARGV,
    LIST_BOOTS_TEXT_ARGV,
    collect_boots,
    normalize_boot_id,
    parse_boots_json,
    parse_boots_text,
)
from syspanic.collectors.runner import CommandResult
from syspanic.constants import SOURCE_JOURNAL_BOOTS
from syspanic.domain.enums import SourceState

CUR = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
PREV = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
OTHER = "ffffffffffffffffffffffffffffffff"


def dashed(undashed: str) -> str:
    return (
        f"{undashed[:8]}-{undashed[8:12]}-{undashed[12:16]}-"
        f"{undashed[16:20]}-{undashed[20:]}"
    )


def ok(stdout: bytes) -> CommandResult:
    return CommandResult(
        stdout=stdout, state=SourceState.AVAILABLE, exit_code=0, elapsed_ms=5.0, tail_reliable=True
    )


def failed(state: SourceState, detail: str = "") -> CommandResult:
    return CommandResult(
        stdout=b"",
        state=state,
        exit_code=1,
        elapsed_ms=5.0,
        stderr_detail=detail,
        tail_reliable=False,
    )


class FakeRunner:
    def __init__(self, *results: CommandResult):
        self.results = list(results)
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        return self.results.pop(0)


def json_fixture() -> bytes:
    rows = [
        {
            "index": -1,
            "boot_id": dashed(PREV),
            "first_entry": 1763000000000000,
            "last_entry": 1763003600000000,
        },
        {
            "index": 0,
            "boot_id": CUR,
            "first_entry": 1763280000000000,
            "last_entry": 1763283600000000,
        },
    ]
    return json.dumps(rows).encode()


TEXT_FIXTURE = (
    "IDX BOOT ID                            FIRST ENTRY                    LAST ENTRY\n"
    f" -1 {dashed(PREV)}   Mon 2026-11-10 08:00:00 UTC    Mon 2026-11-10 09:00:00 UTC\n"
    f"  0 {CUR}   Sun 2026-11-16 08:00:00 UTC    Sun 2026-11-16 09:00:00 UTC\n"
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (CUR, CUR),
        (dashed(CUR), CUR),
        (CUR.upper(), CUR),
        (dashed(CUR).upper(), CUR),
        ("  " + dashed(CUR) + "  ", CUR),
    ],
)
def test_normalize_boot_id_accepts(raw, expected):
    assert normalize_boot_id(raw) == expected


@pytest.mark.parametrize("raw", ["", "xyz", CUR[:31], CUR + "0", "gg" * 16, dashed(CUR) + "-"])
def test_normalize_boot_id_rejects(raw):
    assert normalize_boot_id(raw) is None


def test_parse_boots_json_array():
    boots = parse_boots_json(json_fixture().decode())
    assert boots is not None and len(boots) == 2
    prev, cur = boots
    assert prev.index == -1 and prev.boot_id == PREV and prev.is_current is False
    assert cur.index == 0 and cur.boot_id == CUR and cur.is_current is True
    assert cur.first_entry == datetime.fromtimestamp(1763280000000000 / 1e6, tz=UTC)
    assert cur.last_entry == datetime.fromtimestamp(1763283600000000 / 1e6, tz=UTC)


def test_parse_boots_json_lines():
    rows = [
        {
            "index": 0,
            "boot_id": dashed(CUR),
            "first_entry": 1763280000000000,
            "last_entry": 1763283600000000,
        },
    ]
    text = "\n".join(json.dumps(r) for r in rows)
    boots = parse_boots_json(text)
    assert boots is not None and len(boots) == 1
    assert boots[0].boot_id == CUR and boots[0].is_current is True


def test_parse_boots_json_invalid_returns_none():
    assert parse_boots_json("not json at all") is None
    assert parse_boots_json("") is None


def test_parse_boots_json_skips_invalid_ids():
    text = json.dumps([{"index": 0, "boot_id": "too-short"}, {"index": -1, "boot_id": PREV}])
    boots = parse_boots_json(text)
    assert boots is not None and len(boots) == 1
    assert boots[0].boot_id == PREV


def test_parse_boots_text_table():
    boots = parse_boots_text(TEXT_FIXTURE)
    assert boots is not None and len(boots) == 2
    assert boots[0].index == -1 and boots[0].boot_id == PREV
    assert boots[1].index == 0 and boots[1].boot_id == CUR and boots[1].is_current is True
    assert boots[1].first_entry is None


def test_parse_boots_text_no_rows_returns_none():
    assert parse_boots_text("IDX BOOT ID FIRST ENTRY LAST ENTRY\n") is None
    assert parse_boots_text("garbage\n") is None


def test_collect_boots_json_success():
    runner = FakeRunner(ok(json_fixture()))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: CUR)
    assert runner.calls == [list(LIST_BOOTS_JSON_ARGV)]
    assert len(result.payload) == 2
    cov = result.coverage[0]
    assert cov.source == SOURCE_JOURNAL_BOOTS
    assert cov.state is SourceState.AVAILABLE
    assert cov.tail_reliable is True
    assert cov.entry_count == 2
    assert result.issues == ()


def test_collect_boots_text_fallback():
    runner = FakeRunner(ok(b"corrupt json"), ok(TEXT_FIXTURE.encode()))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: CUR)
    assert runner.calls == [list(LIST_BOOTS_JSON_ARGV), list(LIST_BOOTS_TEXT_ARGV)]
    assert len(result.payload) == 2
    assert result.coverage[0].state is SourceState.AVAILABLE


def test_collect_boots_zero_previous_boots():
    rows = [
        {
            "index": 0,
            "boot_id": CUR,
            "first_entry": 1763280000000000,
            "last_entry": 1763283600000000,
        },
    ]
    runner = FakeRunner(ok(json.dumps(rows).encode()))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: CUR)
    assert len(result.payload) == 1
    assert result.payload[0].is_current is True


def test_collect_boots_journal_failure_proc_fallback():
    runner = FakeRunner(
        failed(SourceState.PERMISSION_DENIED, "No journal files were opened"),
        failed(SourceState.PERMISSION_DENIED, "No journal files were opened"),
    )
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: dashed(CUR))
    assert len(result.payload) == 1
    boot = result.payload[0]
    assert boot.index == 0 and boot.boot_id == CUR and boot.is_current is True
    cov = result.coverage[0]
    assert cov.state is SourceState.PERMISSION_DENIED
    assert cov.tail_reliable is False
    assert "fallback" in cov.detail


def test_collect_boots_total_failure_yields_issue():
    runner = FakeRunner(failed(SourceState.ERROR), failed(SourceState.ERROR))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: None)
    assert result.payload == ()
    assert result.coverage[0].tail_reliable is False
    assert len(result.issues) == 1
    assert result.issues[0].source == SOURCE_JOURNAL_BOOTS


def test_collect_boots_current_mismatch_recorded():
    runner = FakeRunner(ok(json_fixture()))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: OTHER)
    assert len(result.payload) == 2
    assert "mismatch" in result.coverage[0].detail


def test_collect_boots_unverifiable_current_recorded():
    runner = FakeRunner(ok(json_fixture()))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: None)
    assert len(result.payload) == 2
    assert "verif" in result.coverage[0].detail


def test_collect_boots_parse_failure_both_formats():
    runner = FakeRunner(ok(b"garbage"), ok(b"more garbage"))
    ctx = CollectionContext(boot=None, runner=runner)
    result = collect_boots(ctx, read_boot_id=lambda: CUR)
    assert len(result.payload) == 1
    cov = result.coverage[0]
    assert cov.state is SourceState.ERROR
    assert cov.tail_reliable is False
