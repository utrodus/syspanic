"""T-022: Report page — mandatory preview, redaction summary, copy/save, errors."""

import re
from dataclasses import replace

from PySide6.QtWidgets import QPlainTextEdit

from syspanic.collectors.demo import DEMO_HOSTNAME
from syspanic.ui.pages import ReportPage


def make_page(qapp, report):
    page = ReportPage()
    page.apply_report(report, hostnames=(DEMO_HOSTNAME,))
    return page


def test_idle_buttons_disabled(qapp):
    page = ReportPage()
    assert not page.copy_button.isEnabled()
    assert not page.save_button.isEnabled()
    assert page.preview.toPlainText() == ""


def test_preview_is_plain_readonly_monospace(qapp, demo_report):
    page = make_page(qapp, demo_report)
    assert isinstance(page.preview, QPlainTextEdit)
    assert page.preview.isReadOnly()
    assert "Mono" in page.preview.font().family()
    text = page.preview.toPlainText()
    assert text.startswith("> DEMO DATA — not collected from this machine.")
    assert "# SysPanic Diagnostic Report" in text


def test_demo_preview_prepends_notice(qapp, demo_report):
    page = make_page(qapp, demo_report)
    assert "> DEMO DATA — not collected from this machine." in page.preview.toPlainText()


def test_buttons_enabled_after_preview(qapp, demo_report):
    page = make_page(qapp, demo_report)
    assert page.copy_button.isEnabled()
    assert page.save_button.isEnabled()


def test_readiness_line(qapp, demo_report):
    page = make_page(qapp, demo_report)
    text = page.readiness.text()
    assert demo_report.boot.boot_id[:8] in text
    assert "bounded evidence excerpts" in text
    assert "full logs are not included" in text


def test_redaction_notice_exact(qapp, demo_report):
    page = make_page(qapp, demo_report)
    assert page.notice.text() == (
        "Redaction is best-effort. Review the preview before sharing; "
        "unrecognized secrets may remain."
    )


def test_redaction_summary_nonzero_only(qapp, demo_previous_report):
    page = make_page(qapp, demo_previous_report)
    text = page.redaction_summary.text()
    assert text.startswith("Redacted:")
    assert "IP ×1" in text
    assert "×0" not in text


def test_redaction_summary_none(qapp, demo_report):
    page = make_page(qapp, demo_report)
    assert page.redaction_summary.text() == "Redacted: none"


def test_copy_puts_markdown_on_clipboard(qapp, demo_report):
    page = make_page(qapp, demo_report)
    page.copy()
    assert qapp.clipboard().text() == page.preview.toPlainText()


def test_save_writes_utf8_and_emits_saved(qapp, demo_report, tmp_path):
    page = make_page(qapp, demo_report)
    target = tmp_path / "report.md"
    seen = {}

    def dialog(default_name):
        seen["name"] = default_name
        return str(target)

    page.save_dialog = dialog
    saved = []
    page.reportSaved.connect(lambda: saved.append(True))
    page.save()
    assert saved == [True]
    assert target.read_text(encoding="utf-8") == page.preview.toPlainText()
    assert re.fullmatch(
        r"syspanic-report-[0-9a-f]{8}-\d{8}-\d{6}Z\.md", seen["name"]
    )


def test_save_cancel_writes_nothing(qapp, demo_report, tmp_path):
    page = make_page(qapp, demo_report)
    page.save_dialog = lambda default_name: ""
    saved = []
    page.reportSaved.connect(lambda: saved.append(True))
    page.save()
    assert saved == []
    assert list(tmp_path.iterdir()) == []


def test_save_failure_shows_inline_error(qapp, demo_report, tmp_path):
    page = make_page(qapp, demo_report)
    page.save_dialog = lambda default_name: str(tmp_path / "missing-dir" / "r.md")
    saved = []
    page.reportSaved.connect(lambda: saved.append(True))
    page.save()
    assert saved == []
    assert page.error_label.isVisibleTo(page)
    assert page.error_label.text()


def test_non_demo_report_has_no_demo_notice(qapp, demo_report):
    page = ReportPage()
    page.apply_report(replace(demo_report, demo=False), hostnames=(DEMO_HOSTNAME,))
    assert "> DEMO DATA" not in page.preview.toPlainText()
