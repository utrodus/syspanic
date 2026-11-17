"""T-006 journal parsing — docs/02 §8.4–7. Synthetic JSON fixtures only."""

import json
from datetime import UTC, datetime

from syspanic.collectors.journal import (
    decode_message,
    extract_kernel_release,
    merge_entries,
    parse_dmesg,
    parse_journal_slice,
    to_evidence,
)
from syspanic.constants import SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM

CUR = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
T0_US = 1763280000000000


def jline(cursor, message, ts_us=T0_US, priority="6", **extra):
    obj = {
        "__CURSOR": cursor,
        "__REALTIME_TIMESTAMP": str(ts_us),
        "MESSAGE": message,
        "PRIORITY": priority,
        **extra,
    }
    return json.dumps(obj)


def test_parse_valid_line():
    text = jline("c1", "hello", _TRANSPORT="kernel", SYSLOG_IDENTIFIER="kernel")
    parsed = parse_journal_slice(text, SOURCE_JOURNAL_KERNEL)
    assert parsed.skipped == 0 and len(parsed.entries) == 1
    entry = parsed.entries[0]
    assert entry.cursor == "c1"
    assert entry.timestamp == datetime.fromtimestamp(T0_US / 1e6, tz=UTC)
    assert entry.priority == 6
    assert entry.message == "hello"
    assert entry.identifier == "kernel"
    assert entry.provenance["_TRANSPORT"] == "kernel"
    assert entry.source == SOURCE_JOURNAL_KERNEL
    assert entry.line_no == 1


def test_byte_array_message_decoded():
    raw = list("héllo".encode())
    text = jline("c1", raw)
    parsed = parse_journal_slice(text, SOURCE_JOURNAL_KERNEL)
    assert parsed.entries[0].message == "héllo"


def test_byte_array_invalid_utf8_replaced():
    text = jline("c1", [0x61, 0xFF, 0x62])
    parsed = parse_journal_slice(text, SOURCE_JOURNAL_KERNEL)
    assert parsed.entries[0].message == "a\ufffdb"


def test_ansi_sequences_stripped():
    assert decode_message("a\x1b[31mb\x1b[0mc") == "abc"
    assert decode_message("x\x1b]0;title\x07y") == "xy"


def test_control_chars_stripped_including_newline_tab():
    assert decode_message("a\x00b\x01c\nd\te\x7f") == "abcde"


def test_tab_newline_messages_pass_report_validation():
    from rule_fixtures import make_bundle
    from syspanic.diagnostics import engine

    text = "\n".join(
        [
            jline("c1", "audit: type=1\tpath=/tmp\tx"),
            jline("c2", "first line\nsecond line", ts_us=T0_US + 1000),
        ]
    )
    parsed = parse_journal_slice(text, SOURCE_JOURNAL_KERNEL)
    evidence = to_evidence(parsed.entries, CUR)
    report = engine.analyze(make_bundle(evidence))
    for item in report.evidence:
        assert not any(ord(c) < 32 or ord(c) == 127 for c in item.message)


def test_message_capped_at_1000():
    assert len(decode_message("x" * 5000)) == 1000


def test_malformed_lines_skipped_and_counted():
    text = "not json\n{bad\n" + jline("c1", "ok") + "\n\n"
    parsed = parse_journal_slice(text, SOURCE_JOURNAL_KERNEL)
    assert parsed.skipped == 2
    assert len(parsed.entries) == 1


def test_missing_cursor_or_timestamp_skipped():
    no_cursor = json.dumps({"__REALTIME_TIMESTAMP": str(T0_US), "MESSAGE": "x"})
    no_ts = json.dumps({"__CURSOR": "c1", "MESSAGE": "x"})
    bad_ts = jline("c2", "x", ts_us="abc")
    parsed = parse_journal_slice("\n".join([no_cursor, no_ts, bad_ts]), SOURCE_JOURNAL_KERNEL)
    assert parsed.entries == ()
    assert parsed.skipped == 3


def test_empty_text_parses_to_nothing():
    parsed = parse_journal_slice("", SOURCE_JOURNAL_KERNEL)
    assert parsed.entries == () and parsed.skipped == 0


def test_priority_optional_and_invalid_is_none():
    missing = json.dumps({"__CURSOR": "c1", "__REALTIME_TIMESTAMP": str(T0_US), "MESSAGE": "x"})
    invalid = jline("c2", "x", priority="high")
    parsed = parse_journal_slice(missing + "\n" + invalid, SOURCE_JOURNAL_KERNEL)
    assert all(e.priority is None for e in parsed.entries)


def test_merge_dedupes_by_cursor_preferring_kernel():
    kernel = parse_journal_slice(
        jline("c1", "kernel view", _TRANSPORT="kernel"), SOURCE_JOURNAL_KERNEL
    ).entries
    system = parse_journal_slice(
        jline("c1", "system view") + "\n" + jline("c2", "only system", ts_us=T0_US + 1000),
        SOURCE_JOURNAL_SYSTEM,
    ).entries
    merged = merge_entries(kernel, system)
    assert len(merged) == 2
    assert merged[0].message == "kernel view"
    assert merged[0].source == SOURCE_JOURNAL_KERNEL


def test_merge_sorts_by_timestamp_then_cursor():
    system = parse_journal_slice(
        jline("c2", "later", ts_us=T0_US + 1000) + "\n" + jline("c1", "earlier"),
        SOURCE_JOURNAL_SYSTEM,
    ).entries
    merged = merge_entries((), system)
    assert [e.cursor for e in merged] == ["c1", "c2"]


def test_to_evidence_assigns_unique_sequential_ids():
    parsed = parse_journal_slice(
        jline("c1", "a") + "\n" + jline("c2", "b", ts_us=T0_US + 1000),
        SOURCE_JOURNAL_KERNEL,
    )
    evidence = to_evidence(parsed.entries, CUR)
    assert [e.evidence_id for e in evidence] == ["JRN-000001", "JRN-000002"]
    assert all(e.boot_id == CUR for e in evidence)
    assert evidence[0].source == SOURCE_JOURNAL_KERNEL
    assert evidence[0].timestamp is not None


def test_extract_kernel_release():
    parsed = parse_journal_slice(
        jline("c1", "Linux version 6.17.9-200.fc44.x86_64 (build@host) #1 SMP"),
        SOURCE_JOURNAL_KERNEL,
    )
    assert extract_kernel_release(parsed.entries) == "6.17.9-200.fc44.x86_64"
    assert extract_kernel_release(()) is None


def test_parse_dmesg_iso_timestamps():
    text = (
        "2026-11-16T08:00:00,000000+00:00 Linux version 6.17.9\n"
        "2026-11-16T08:00:01,500000+00:00 audit: ok\n"
    )
    entries = parse_dmesg(text, CUR)
    assert len(entries) == 2
    assert entries[0].evidence_id == "DMS-000001"
    assert entries[0].timestamp == datetime(2026, 11, 16, 8, 0, 0, tzinfo=UTC)
    assert entries[1].timestamp == datetime(2026, 11, 16, 8, 0, 1, 500000, tzinfo=UTC)
    assert entries[0].message == "Linux version 6.17.9"
    assert entries[0].provenance["_TRANSPORT"] == "kernel"


def test_parse_dmesg_monotonic_plain_no_timestamp():
    text = "[    0.000000] Linux version 6.17.9\n[    1.234567] usb 1-1: new device\n"
    entries = parse_dmesg(text, CUR)
    assert len(entries) == 2
    assert all(e.timestamp is None for e in entries)
    assert entries[0].message == "Linux version 6.17.9"


def test_parse_dmesg_skips_blank_lines():
    assert parse_dmesg("\n  \n", CUR) == ()
