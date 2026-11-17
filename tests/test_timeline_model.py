"""T-019: TimelineModel — columns, order-preserving severity filter, evidence IDs."""

from datetime import UTC, datetime, timedelta

from PySide6.QtCore import Qt

from syspanic.domain.enums import Severity, TimelineKind
from syspanic.domain.models import TimelineEvent
from syspanic.ui.table_models import TimelineModel

BASE = datetime(2026, 11, 10, 8, 33, 37, tzinfo=UTC)


def make_events():
    rows = (
        (Severity.INFO, TimelineKind.BOOT_START, "BTM-000000"),
        (Severity.CRITICAL, TimelineKind.RULE_MATCH, "JRN-000010"),
        (Severity.WARNING, TimelineKind.RULE_MATCH, "JRN-000011"),
        (Severity.NOTICE, TimelineKind.RULE_MATCH, "JRN-000012"),
        (Severity.CRITICAL, TimelineKind.RULE_MATCH, "JRN-000013"),
        (Severity.INFO, TimelineKind.SHUTDOWN_MARKER, "JRN-000020"),
    )
    return tuple(
        TimelineEvent(
            timestamp=BASE + timedelta(seconds=i),
            kind=kind,
            summary=f"event {i}",
            severity=severity,
            evidence_id=eid,
        )
        for i, (severity, kind, eid) in enumerate(rows)
    )


def test_columns_and_headers(qapp):
    model = TimelineModel(make_events())
    assert model.columnCount() == 4
    headers = [
        model.headerData(c, Qt.Orientation.Horizontal) for c in range(4)
    ]
    assert headers == ["Time", "Event", "Severity", "Evidence"]


def test_rows_match_events_in_order(qapp):
    events = make_events()
    model = TimelineModel(events)
    assert model.rowCount() == len(events)
    for row, event in enumerate(events):
        assert model.event_at(row) is event
        assert model.data(model.index(row, 3)) == event.evidence_id
        assert model.data(model.index(row, 1)) == event.summary


def test_severity_column_uses_text_labels(qapp):
    model = TimelineModel(make_events())
    assert model.data(model.index(1, 2)) == "Critical"
    assert model.data(model.index(2, 2)) == "Warning"


def test_filter_multiselect_retains_order(qapp):
    model = TimelineModel(make_events())
    model.set_filter({Severity.CRITICAL, Severity.WARNING})
    ids = [model.data(model.index(r, 3)) for r in range(model.rowCount())]
    assert ids == ["JRN-000010", "JRN-000011", "JRN-000013"]


def test_filter_single_severity(qapp):
    model = TimelineModel(make_events())
    model.set_filter({Severity.CRITICAL})
    assert model.rowCount() == 2
    assert all(model.event_at(r).severity is Severity.CRITICAL for r in range(2))


def test_empty_filter_shows_all(qapp):
    model = TimelineModel(make_events())
    model.set_filter({Severity.CRITICAL})
    model.set_filter(set())
    assert model.rowCount() == 6


def test_time_tooltip_contains_full_timestamp(qapp):
    model = TimelineModel(make_events())
    tooltip = model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
    assert "2026-11-10" in tooltip
    display = model.data(model.index(0, 0))
    local = BASE.astimezone()
    assert f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}" in display


def test_empty_model(qapp):
    model = TimelineModel(())
    assert model.rowCount() == 0
