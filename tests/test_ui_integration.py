"""T-023: window state matrix — collecting, ready, cancelled, error, stale, close."""

import threading
from dataclasses import replace

from rule_fixtures import make_boot
from syspanic.domain.enums import SourceState
from syspanic.ui.controller import AnalysisController
from syspanic.ui.main_window import MainWindow
from test_controller import FakeWorker, wait_until

BOOT = make_boot()


def make_window(qapp, behavior=None, demo=False):
    captured = {}

    def factory(mode, boot, *, demo, cancel):
        worker = FakeWorker(mode, boot, demo=demo, cancel=cancel, behavior=behavior or {})
        captured["worker"] = worker
        return worker

    controller = AnalysisController(demo=demo, worker_factory=factory)
    win = MainWindow(demo=demo, controller=controller)
    win.show()
    return win, controller, captured


def test_begin_loads_demo_boots(qapp):
    win = MainWindow(demo=True, controller=AnalysisController(demo=True))
    win.show()
    win.begin()
    assert wait_until(qapp, lambda: win.boot_selector.isEnabled())
    assert win.boot_selector.count() == 2
    win.close()


def test_analyze_demo_populates_all_pages(qapp):
    win = MainWindow(demo=True, controller=AnalysisController(demo=True))
    win.show()
    win.begin()
    assert wait_until(qapp, lambda: win.boot_selector.isEnabled())
    win.analyze_button.click()
    assert wait_until(qapp, lambda: win.controller.state == "ready", timeout=10.0)
    assert "Ready" in win.footer.text()
    assert win.overview_page.finding_rows
    assert win.timeline_page.model.rowCount() > 0
    assert win.report_page.preview.toPlainText()
    assert win.evidence_page.source_list.count() > 0
    win.close()


def test_collecting_shows_cancel_and_progress(qapp):
    gate = threading.Event()
    win, controller, _ = make_window(qapp, {"kind": "report", "gate": gate})
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    assert win.cancel_button.isVisibleTo(win)
    assert win.analyze_button.isHidden()
    controller.progress.emit("journal.kernel", 3, 13)
    assert win.progress_label.text() == "Collecting journal.kernel (3/13)"
    assert win.progress_bar.value() == 3
    assert win.progress_bar.maximum() == 13
    gate.set()
    assert wait_until(qapp, lambda: not controller.running)
    assert win.analyze_button.isVisibleTo(win)
    win.close()


def test_cancelled_footer_and_results_retained(qapp):
    gate = threading.Event()
    win, controller, _ = make_window(qapp, {"kind": "report", "gate": gate})
    controller.analyze(BOOT)
    controller.cancel()
    assert wait_until(qapp, lambda: not controller.running)
    assert "Collection cancelled." in win.footer.text()
    win.close()


def test_error_banner_and_analyze_reenabled(qapp):
    win, controller, _ = make_window(qapp, {"kind": "fail"})
    win.overview_page.set_boots((BOOT,))
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: not controller.running)
    assert win.error_bar.isVisibleTo(win)
    assert "Collection failed:" in win.error_bar.text()
    assert "Partial results are shown where available." in win.error_bar.text()
    assert win.analyze_button.isEnabled()
    win.close()


def test_partial_banner_counts_unavailable(qapp, demo_previous_report):
    win, controller, _ = make_window(qapp)
    win.apply_report(demo_previous_report)
    unavailable = sum(
        1
        for c in demo_previous_report.coverage
        if c.state not in (SourceState.AVAILABLE, SourceState.EMPTY, SourceState.TRUNCATED)
    )
    assert win.partial_bar.isVisibleTo(win)
    assert win.partial_bar.text() == (
        f"{unavailable} of 13 sources were unavailable. Findings may be incomplete."
    )
    win.close()


def test_tail_uncertain_banner(qapp, demo_report):
    win, controller, _ = make_window(qapp)
    uncertain = replace(
        demo_report,
        coverage=tuple(
            replace(c, state=SourceState.TRUNCATED, tail_reliable=False)
            if c.source == "journal.system"
            else c
            for c in demo_report.coverage
        ),
    )
    win.apply_report(uncertain)
    assert win.tail_bar.isVisibleTo(win)
    assert win.tail_bar.text() == (
        "The journal tail was not reliably collected. "
        "Shutdown-sequence absence is not assessed."
    )
    win.close()


def test_stale_banner_on_boot_change(qapp):
    win = MainWindow(demo=True, controller=AnalysisController(demo=True))
    win.show()
    win.begin()
    assert wait_until(qapp, lambda: win.boot_selector.isEnabled())
    win.analyze_button.click()
    assert wait_until(qapp, lambda: win.controller.state == "ready", timeout=10.0)
    win.boot_selector.setCurrentIndex(1)
    assert win.overview_page.stale_bar.isVisibleTo(win)
    assert win.controller.analyzed_boot_id[:8] in win.overview_page.stale_bar.text()
    win.close()


def test_close_waits_for_worker_then_closes(qapp):
    gate = threading.Event()
    win, controller, _ = make_window(
        qapp, {"kind": "report", "gate": gate, "respect_cancel": False}
    )
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    win.close()
    assert win.isVisible()
    assert win.close_wait_label.text() == "Finishing collection before closing…"
    gate.set()
    assert wait_until(qapp, lambda: not win.isVisible())
    assert not controller.running


def test_close_during_collection_keeps_window_open_with_label(qapp):
    gate = threading.Event()
    win, controller, _ = make_window(qapp, {"kind": "report", "gate": gate})
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    win.close()
    assert win.isVisible()
    assert win.close_wait_label.isVisibleTo(win)
    assert controller.running
    gate.set()
    assert wait_until(qapp, lambda: not win.isVisible())
    assert not controller.running


def test_close_wait_keeps_gui_responsive(qapp):
    gate = threading.Event()
    win, controller, _ = make_window(
        qapp, {"kind": "report", "gate": gate, "respect_cancel": False}
    )
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    win.close()
    assert win.isVisible()
    assert win.close_wait_label.isVisibleTo(win)
    controller.progress.emit("journal.kernel", 7, 13)
    qapp.processEvents()
    assert win.progress_label.text() == "Collecting journal.kernel (7/13)"
    gate.set()
    assert wait_until(qapp, lambda: not win.isVisible())


def test_evidence_highlight_follows_theme_switch(qapp, demo_report):
    from syspanic.ui import theme

    win, controller, _ = make_window(qapp)
    win.apply_report(demo_report)
    target = demo_report.evidence[0].evidence_id
    win.evidence_page.select_evidence(target)
    win.theme_manager.set_theme(theme.Theme.LIGHT)
    selections = win.evidence_page.viewer.extraSelections()
    assert selections
    assert (
        selections[0].format.background().color().name().lower()
        == theme.LIGHT_TOKENS["evidence.highlight"].lower()
    )
    win.theme_manager.set_theme(theme.Theme.DARK)
    win.close()


def test_escape_cancels_collection(qapp):
    gate = threading.Event()
    win, controller, _ = make_window(qapp, {"kind": "report", "gate": gate})
    controller.analyze(BOOT)
    assert wait_until(qapp, lambda: controller.running)
    win.cancel_collection()
    assert wait_until(qapp, lambda: not controller.running)
    assert "Collection cancelled." in win.footer.text()
    win.close()


def test_report_saved_footer(qapp):
    win, controller, _ = make_window(qapp)
    win.report_page.reportSaved.emit()
    assert "Report saved." in win.footer.text()
    win.close()


def test_evidence_link_navigates_to_evidence_page(qapp, demo_report):
    win, controller, _ = make_window(qapp)
    win.apply_report(demo_report)
    target = demo_report.evidence[0].evidence_id
    win.overview_page.evidenceRequested.emit(target)
    assert win.nav.currentRow() == 2
    assert win.stack.currentIndex() == 2
    assert target in win.evidence_page.viewer.toPlainText()
    win.close()


def test_view_coverage_navigates_to_evidence(qapp, demo_report):
    win, controller, _ = make_window(qapp)
    win.apply_report(demo_report)
    win.overview_page.view_coverage_button.click()
    assert win.nav.currentRow() == 2
    win.close()


def test_timeline_double_click_navigates(qapp, demo_report):
    win, controller, _ = make_window(qapp)
    win.apply_report(demo_report)
    event = demo_report.timeline[0]
    win.timeline_page.table.doubleClicked.emit(win.timeline_page.model.index(0, 3))
    assert win.nav.currentRow() == 2
    assert event.evidence_id in win.evidence_page.viewer.toPlainText()
    win.close()
