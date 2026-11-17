"""T-018/T-019/T-020/T-021: page rendering from a real IncidentReport (offscreen)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QPlainTextEdit

from syspanic.collectors.demo import DEMO_CURRENT_BOOT_ID, DEMO_PREVIOUS_BOOT_ID, DemoCollector
from syspanic.domain.enums import Severity, SourceState
from syspanic.domain.models import BootInfo
from syspanic.report.markdown import NO_FINDINGS_TEXT
from syspanic.ui import theme as theme_mod
from syspanic.ui.pages import EvidencePage, OverviewPage, ReportPage, SystemInfoPage, TimelinePage
from syspanic.ui.widgets import PageHeader


def make_boots():
    return DemoCollector().boots()


def make_many_boots(count):
    base = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    return tuple(
        BootInfo(
            index=-i,
            boot_id=f"{i:032x}",
            is_current=i == 0,
            first_entry=base - timedelta(days=i),
            last_entry=base - timedelta(days=i) + timedelta(hours=2),
        )
        for i in range(count)
    )


def test_overview_set_boots_labels(qapp):
    page = OverviewPage()
    page.set_boots(make_boots())
    combo = page.boot_selector
    assert combo.isEnabled()
    assert combo.count() == 2
    current = combo.itemText(0)
    assert current.startswith(f"Current boot · {DEMO_CURRENT_BOOT_ID[:8]} · ")
    assert combo.itemText(1).startswith(f"Previous boot · {DEMO_PREVIOUS_BOOT_ID[:8]} · ")
    assert DEMO_CURRENT_BOOT_ID in combo.itemData(0, Qt.ItemDataRole.ToolTipRole)


def test_overview_zero_previous_boots_disabled_item(qapp):
    page = OverviewPage()
    boots = make_boots()
    page.set_boots(tuple(b for b in boots if b.is_current))
    combo = page.boot_selector
    assert combo.count() == 2
    assert combo.itemText(1) == "No previous boots in the journal"
    item = combo.model().item(1)
    assert not (item.flags() & Qt.ItemFlag.ItemIsEnabled)


def test_overview_severity_counts(qapp, demo_report):
    page = OverviewPage()
    page.apply_report(demo_report)
    for severity, name in (
        (Severity.CRITICAL, "countCritical"),
        (Severity.WARNING, "countWarning"),
        (Severity.NOTICE, "countNotice"),
        (Severity.INFO, "countInfo"),
    ):
        expected = sum(1 for f in demo_report.findings if f.severity is severity)
        label = page.findChild(QLabel, name)
        assert label is not None
        assert label.text() == str(expected)


def test_overview_findings_first_five_and_show_all(qapp, demo_report):
    page = OverviewPage()
    page.apply_report(demo_report)
    total = len(demo_report.findings)
    assert total > 5
    assert len(page.finding_rows) == 5
    assert page.show_all_button.text() == f"Show all {total} findings"
    page.show_all_button.click()
    assert len(page.finding_rows) == total


def test_overview_finding_expand_and_evidence_link(qapp, demo_report):
    page = OverviewPage()
    page.apply_report(demo_report)
    row = page.finding_rows[0]
    assert row.detail.isHidden()
    row.toggle_button.click()
    assert not row.detail.isHidden()
    requested = []
    page.evidenceRequested.connect(requested.append)
    assert row.evidence_buttons
    row.evidence_buttons[0].click()
    assert requested and requested[0] == row.finding.evidence[0].evidence_id


def test_overview_coverage_strip(qapp, demo_report):
    page = OverviewPage()
    page.apply_report(demo_report)
    available = sum(
        1
        for c in demo_report.coverage
        if c.state in (SourceState.AVAILABLE, SourceState.EMPTY, SourceState.TRUNCATED)
    )
    assert page.coverage_strip.text() == f"{available} of 13 sources available"
    switched = []
    page.coverageRequested.connect(lambda: switched.append(True))
    page.view_coverage_button.click()
    assert switched == [True]


def test_overview_artifacts_card_always_notes_binary(qapp, demo_report):
    page = OverviewPage()
    page.apply_report(demo_report)
    texts = [w.text() for w in page.artifacts_card.findChildren(QLabel)]
    assert any("Binary vmcore contents were not analyzed." in t for t in texts)


def test_overview_status_chip_demo(qapp, demo_report):
    page = OverviewPage()
    page.apply_report(demo_report)
    assert page.status_chip.text() == "Demo data"


def test_overview_zero_findings_exact_copy(qapp, empty_report):
    page = OverviewPage()
    page.apply_report(empty_report)
    labels = [w.text() for w in page.findChildren(QLabel)]
    assert NO_FINDINGS_TEXT in labels
    assert page.finding_rows == []


def test_overview_stale_banner(qapp):
    page = OverviewPage()
    page.set_stale("59570339")
    assert page.stale_bar.isVisibleTo(page)
    assert page.stale_bar.text() == (
        "Results are for boot 59570339. Select Analyze to collect the new selection."
    )
    page.set_stale(None)
    assert page.stale_bar.isHidden()


def test_timeline_populated_and_double_click(qapp, demo_report):
    page = TimelinePage()
    page.apply_report(demo_report)
    assert page.model.rowCount() == len(demo_report.timeline)
    requested = []
    page.evidenceRequested.connect(requested.append)
    page.table.doubleClicked.emit(page.model.index(0, 3))
    assert requested == [demo_report.timeline[0].evidence_id]


def test_timeline_filter_buttons_preserve_order(qapp, demo_report):
    page = TimelinePage()
    page.apply_report(demo_report)
    page.filter_buttons["Critical"].click()
    critical_ids = [
        page.model.event_at(r).evidence_id for r in range(page.model.rowCount())
    ]
    expected = [e.evidence_id for e in demo_report.timeline if e.severity is Severity.CRITICAL]
    assert critical_ids == expected
    page.filter_buttons["All"].click()
    assert page.model.rowCount() == len(demo_report.timeline)


def test_timeline_footer_cap_text(qapp, demo_report):
    page = TimelinePage()
    page.apply_report(demo_report)
    assert "key events" in page.footer_label.text()


def test_timeline_empty_and_unavailable(qapp, empty_report):
    page = TimelinePage()
    page.apply_report(empty_report)
    assert page.empty_label.text() == "No timeline events for this boot."
    denied = replace(
        empty_report,
        coverage=tuple(
            replace(c, state=SourceState.PERMISSION_DENIED, tail_reliable=False)
            if c.source in ("journal.kernel", "journal.system")
            else c
            for c in empty_report.coverage
        ),
    )
    page.apply_report(denied)
    assert page.empty_label.text() == (
        "Timeline unavailable — the journal for this boot could not be read."
    )


def test_evidence_sources_include_metadata_groups(qapp, demo_previous_report):
    page = EvidencePage()
    page.apply_report(demo_previous_report)
    names = [page.source_list.item(i).text() for i in range(page.source_list.count())]
    joined = "\n".join(names)
    assert "boot metadata" in joined
    assert "artifact metadata" in joined
    assert "journal.kernel" in joined


def test_evidence_line_format(qapp, demo_report):
    page = EvidencePage()
    page.apply_report(demo_report)
    page.source_list.setCurrentRow(0)
    text = page.viewer.toPlainText()
    assert text
    first = text.splitlines()[0]
    assert first.startswith("[")
    assert "] " in first
    assert isinstance(page.viewer, QPlainTextEdit)
    assert page.viewer.isReadOnly()


def test_evidence_filter_no_match(qapp, demo_report):
    page = EvidencePage()
    page.apply_report(demo_report)
    page.source_list.setCurrentRow(0)
    page.filter.setText("zzz-no-match")
    assert 'No lines match "zzz-no-match".' in page.viewer.toPlainText()


def test_evidence_select_by_id(qapp, demo_report):
    page = EvidencePage()
    page.apply_report(demo_report)
    target = demo_report.evidence[0].evidence_id
    page.select_evidence(target)
    assert target in page.viewer.toPlainText()


def test_evidence_select_highlights_whole_line_soft_yellow(qapp, demo_report):
    from syspanic.ui.theme import tokens

    page = EvidencePage()
    page.apply_report(demo_report)
    target = demo_report.evidence[0].evidence_id
    page.select_evidence(target)
    selections = page.viewer.extraSelections()
    assert len(selections) == 1
    fmt = selections[0].format
    assert fmt.background().color().name().lower() == tokens()["evidence.highlight"].lower()
    assert fmt.foreground().color().name().lower() == tokens()["evidence.highlight_text"].lower()
    selected = selections[0].cursor.selectedText()
    assert selected.startswith(f"[{target}]")
    assert len(selected) > len(f"[{target}]")


def test_evidence_highlight_clears_when_id_absent(qapp, demo_report):
    page = EvidencePage()
    page.apply_report(demo_report)
    page.select_evidence(demo_report.evidence[0].evidence_id)
    assert page.viewer.extraSelections()
    page.select_evidence("JRN-999999")
    assert page.viewer.extraSelections() == []


def test_evidence_denied_panel(qapp, demo_report):
    denied = replace(
        demo_report,
        coverage=tuple(
            replace(c, state=SourceState.PERMISSION_DENIED, tail_reliable=False)
            if c.source == "journal.kernel"
            else c
            for c in demo_report.coverage
        ),
    )
    page = EvidencePage()
    page.apply_report(denied)
    assert page.denied_panel.isVisibleTo(page)
    assert page.denied_panel.text() == (
        "System journal is not readable by this user. "
        "SysPanic will not request elevated privileges."
    )


def test_evidence_historical_dmesg_unsupported(qapp, demo_previous_report):
    page = EvidencePage()
    page.apply_report(demo_previous_report)
    names = [page.source_list.item(i).text() for i in range(page.source_list.count())]
    dmesg_rows = [n for n in names if n.startswith("dmesg")]
    assert dmesg_rows and "Unsupported" in dmesg_rows[0]


def test_system_info_banner_and_fields(qapp, demo_report):
    page = SystemInfoPage()
    page.apply_report(demo_report)
    assert page.banner.text() == "Collected now — this is not a crash-time snapshot."
    texts = [w.text() for w in page.findChildren(QLabel)]
    assert demo_report.system.os_name in texts
    assert demo_report.system.cpu_model in texts


def test_system_info_missing_values_not_available(qapp, demo_report):
    profile = replace(demo_report.system, microcode=None, bios_date=None)
    page = SystemInfoPage()
    page.apply_report(replace(demo_report, system=profile))
    texts = [w.text() for w in page.findChildren(QLabel)]
    assert texts.count("Not available") >= 2


def test_system_info_no_serials(qapp, demo_report):
    page = SystemInfoPage()
    page.apply_report(demo_report)
    joined = "\n".join(w.text() for w in page.findChildren(QLabel))
    assert "Serial" not in joined
    assert "serial" not in joined


def test_boot_refresh_preserves_selection(qapp):
    page = OverviewPage()
    boots = make_boots()
    page.set_boots(boots)
    page.boot_selector.setCurrentIndex(1)
    selected = page.selected_boot_id()
    page.set_boots(boots)
    assert page.selected_boot_id() == selected


def test_overview_boot_popup_capped_at_eight_rows(qapp):
    page = OverviewPage()
    page.set_boots(make_many_boots(30))
    combo = page.boot_selector
    assert combo.count() == 30
    assert combo.maxVisibleItems() == 8
    page.resize(1200, 900)
    page.show()
    qapp.processEvents()
    combo.showPopup()
    qapp.processEvents()
    view = combo.view()
    row_height = view.sizeHintForRow(0)
    assert view.height() <= 8 * row_height + 8
    scrollbar = view.verticalScrollBar()
    assert scrollbar.isVisible()
    scrollbar.setValue(scrollbar.maximum())
    qapp.processEvents()
    last = view.visualRect(view.model().index(combo.count() - 1, 0))
    assert last.top() >= 0
    assert last.bottom() <= view.viewport().height()
    combo.hidePopup()
    qapp.processEvents()
    page.close()


def test_overview_boot_popup_short_list_not_clamped(qapp):
    page = OverviewPage()
    page.set_boots(make_boots())
    combo = page.boot_selector
    page.resize(1200, 900)
    page.show()
    qapp.processEvents()
    combo.showPopup()
    qapp.processEvents()
    view = combo.view()
    row_height = view.sizeHintForRow(0)
    assert view.height() >= combo.count() * row_height
    assert not view.verticalScrollBar().isVisible()
    combo.hidePopup()
    qapp.processEvents()
    page.close()


@pytest.mark.parametrize(
    "theme", [theme_mod.Theme.LIGHT, theme_mod.Theme.DARK], ids=["light", "dark"]
)
def test_overview_boot_popup_scrollers_themed(qapp, theme):
    saved_theme = theme_mod.current_theme()
    saved_qss = qapp.styleSheet()
    theme_mod.apply_theme(qapp, theme)
    try:
        page = OverviewPage()
        page.set_boots(make_many_boots(30))
        page.resize(1200, 900)
        page.show()
        qapp.processEvents()
        combo = page.boot_selector
        combo.showPopup()
        qapp.processEvents()
        view = combo.view()
        scrollbar = view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum() // 2)
        qapp.processEvents()
        image = view.window().grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
        data = bytes(image.constBits())
        stride = image.bytesPerLine()
        width = image.width()
        for y in range(image.height()):
            row = data[y * stride : (y + 1) * stride]
            black = sum(
                1
                for x in range(width)
                if row[x * 4] < 24 and row[x * 4 + 1] < 24 and row[x * 4 + 2] < 24
            )
            assert black <= width // 2, f"unpainted black band at popup row {y}"
        assert image.pixelColor(2, 2) == QColor(theme_mod.tokens()["bg.elevated"])
        combo.hidePopup()
        qapp.processEvents()
        page.close()
    finally:
        theme_mod.apply_theme(qapp, saved_theme)
        qapp.setStyleSheet(saved_qss)


def test_evidence_truncation_and_tail_badges(qapp, demo_report):
    truncated = replace(
        demo_report,
        coverage=tuple(
            replace(c, state=SourceState.TRUNCATED, head_truncated=True)
            if c.source == "journal.kernel"
            else replace(c, state=SourceState.TRUNCATED, tail_reliable=False)
            if c.source == "journal.system"
            else c
            for c in demo_report.coverage
        ),
    )
    page = EvidencePage()
    page.apply_report(truncated)
    names = [page.source_list.item(i).text() for i in range(page.source_list.count())]
    kernel = next(n for n in names if n.startswith("journal.kernel"))
    system = next(n for n in names if n.startswith("journal.system"))
    assert "Truncated (head)" in kernel
    assert "Truncated (tail)" in system
    assert "Tail unreliable" in system


def _measure_top_alignment(page, qapp, wrap):
    page.resize(1200, 900)
    page.show()
    qapp.processEvents()
    header = page.findChild(PageHeader)
    gap = wrap.y() - (header.y() + header.height())
    return header.height(), gap


def test_evidence_report_idle_proportions_match_timeline(qapp):
    reference = TimelinePage()
    ref_height, ref_gap = _measure_top_alignment(reference, qapp, reference.idle_wrap)
    for page in (EvidencePage(), ReportPage()):
        height, gap = _measure_top_alignment(page, qapp, page.idle_wrap)
        assert abs(height - ref_height) <= 2
        assert gap == ref_gap
        layout = page.widget().layout()
        assert layout.itemAt(layout.count() - 1).spacerItem() is not None
        page.close()
    reference.close()


def test_evidence_report_results_proportions_match_timeline(qapp, demo_report):
    reference = TimelinePage()
    reference.apply_report(demo_report)
    ref_height, ref_gap = _measure_top_alignment(reference, qapp, reference.results_wrap)
    for page in (EvidencePage(), ReportPage()):
        page.apply_report(demo_report)
        height, gap = _measure_top_alignment(page, qapp, page.results_wrap)
        assert abs(height - ref_height) <= 2
        assert gap == ref_gap
        layout = page.widget().layout()
        assert layout.itemAt(layout.count() - 1).spacerItem() is not None
        page.close()
    reference.close()
