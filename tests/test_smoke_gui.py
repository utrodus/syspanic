import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLabel

from syspanic.ui.main_window import MainWindow

PAGE_NAMES = ["Overview", "Timeline", "Evidence", "System Information", "Report"]


@pytest.fixture
def window(qapp):
    win = MainWindow(demo=False)
    win.show()
    QApplication.processEvents()
    yield win
    win.close()


def test_window_title(window):
    assert window.windowTitle() == "SysPanic"


def test_default_size(window):
    assert window.size() == QSize(1440, 900)


def test_minimum_size(window):
    assert window.minimumSize() == QSize(1280, 720)


def test_five_pages_in_stack(window):
    assert window.stack.count() == 5
    assert window.nav.count() == 5
    assert [window.nav.item(i).text() for i in range(5)] == PAGE_NAMES


def test_nav_switches_pages(window):
    for row in range(5):
        window.nav.setCurrentRow(row)
        assert window.stack.currentIndex() == row


def test_footer_shows_local_only_and_version(window):
    text = window.footer.text()
    assert "Local only" in text
    assert "v0.1.0" in text


def test_boot_selector_placeholder_disabled(window):
    assert not window.boot_selector.isEnabled()
    assert window.boot_selector.count() >= 1


def test_analyze_placeholder_disabled(window):
    assert not window.analyze_button.isEnabled()


def test_tagline_hidden_at_minimum_width(window):
    window.resize(1280, 720)
    QApplication.processEvents()
    assert window.tagline.isHidden()
    window.resize(1440, 900)
    QApplication.processEvents()
    assert not window.tagline.isHidden()


def test_demo_banner_only_in_demo_mode(qapp):
    demo = MainWindow(demo=True)
    assert demo.demo_banner.isVisibleTo(demo)
    assert "DEMO DATA" in demo.demo_banner.text()
    plain = MainWindow(demo=False)
    assert not plain.demo_banner.isVisibleTo(plain)
    demo.close()
    plain.close()


def test_sidebar_width(window):
    assert window.sidebar.width() == 224


def test_nav_items_have_outline_icons(window):
    for i in range(5):
        assert not window.nav.item(i).icon().isNull()


def test_privacy_indicator(window):
    assert "Read-only" in window.privacy.text()
    assert "Local only" not in window.privacy.text()


def test_session_controls_in_overview(window):
    overview = window.stack.widget(0)
    assert overview.isAncestorOf(window.boot_selector)
    assert overview.isAncestorOf(window.analyze_button)


def test_overview_idle_headline(window):
    overview = window.stack.widget(0)
    headline = overview.findChild(QLabel, "emptyHeadline")
    assert headline is not None
    assert headline.text() == "Every crash leaves a clue."


def test_session_hint_readonly_local(window):
    overview = window.stack.widget(0)
    hint = overview.findChild(QLabel, "sessionHint")
    assert hint is not None
    assert "read-only" in hint.text().lower()


def test_each_page_has_heading_and_subtitle(window):
    for i, name in enumerate(PAGE_NAMES):
        page = window.stack.widget(i)
        heading = page.findChild(QLabel, "pageHeading")
        subtitle = page.findChild(QLabel, "pageSubtitle")
        assert heading is not None and heading.text() == name
        assert subtitle is not None and subtitle.text()


def test_overview_capability_cards(window):
    overview = window.stack.widget(0)
    titles = [w.text() for w in overview.findChildren(QLabel, "sectionTitle")]
    assert "Crash investigation" in titles
    assert "Diagnostic reports" in titles


def test_footer_idle_status_not_ready(window):
    assert "Idle" in window.footer.text()
    assert "Ready" not in window.footer.text()
    assert "Local only" in window.footer.text()


def test_overview_empty_copy_complete(window):
    overview = window.stack.widget(0)
    copy = overview.findChild(QLabel, "emptyCopy")
    assert copy is not None
    assert copy.text() == (
        "Understand Linux crashes with clear, evidence-based insights from your system logs."
    )
    assert copy.wordWrap()


def test_overview_privacy_meta(window):
    overview = window.stack.widget(0)
    meta = overview.findChild(QLabel, "emptyMeta")
    assert meta is not None
    assert meta.text() == "Offline · Read-only · Privacy-first"


def test_session_field_label(window):
    overview = window.stack.widget(0)
    label = overview.findChild(QLabel, "fieldLabel")
    assert label is not None
    assert label.text() == "Boot session"


def test_empty_copy_visible_at_minimum_size(window):
    window.resize(1280, 720)
    QApplication.processEvents()
    overview = window.stack.widget(0)
    copy = overview.findChild(QLabel, "emptyCopy")
    assert copy.isVisibleTo(overview)
    assert copy.height() >= copy.fontMetrics().height()


def test_session_cleanup_destroys_leftover_widgets(qapp):
    from conftest import _destroy_leftover_widgets

    leaked = MainWindow(demo=True)
    leaked.show()
    QApplication.processEvents()
    assert leaked in qapp.topLevelWidgets()
    _destroy_leftover_widgets(qapp)
    assert not qapp.topLevelWidgets()
