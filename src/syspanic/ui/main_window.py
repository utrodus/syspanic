from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from syspanic import __version__
from syspanic.constants import (
    APP_NAME,
    FOOTER_HEIGHT,
    NAV_WIDTH,
    PAGE_NAMES,
    TAGLINE,
    TAGLINE_HIDE_WIDTH,
    WINDOW_DEFAULT_SIZE,
    WINDOW_MIN_SIZE,
)
from syspanic.diagnostics.coverage import tail_reliable
from syspanic.domain.enums import SourceState
from syspanic.ui import icons
from syspanic.ui.controller import AnalysisController
from syspanic.ui.pages import (
    EvidencePage,
    OverviewPage,
    ReportPage,
    SystemInfoPage,
    TimelinePage,
)
from syspanic.ui.theme import ThemeManager, tokens
from syspanic.ui.widgets import NoticeBar, ThemeSwitch

NAV_ICONS = ("dashboard", "history", "file_search", "cpu", "file_text")
_READ_STATES = (SourceState.AVAILABLE, SourceState.EMPTY, SourceState.TRUNCATED)


class MainWindow(QMainWindow):
    def __init__(
        self,
        demo: bool = False,
        theme_manager: ThemeManager | None = None,
        controller: AnalysisController | None = None,
    ):
        super().__init__()
        if theme_manager is None:
            theme_manager = ThemeManager(QApplication.instance())
            theme_manager.start()
        self.theme_manager = theme_manager
        self.controller = controller if controller is not None else AnalysisController(demo=demo)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(QSize(*WINDOW_MIN_SIZE))
        self.resize(*WINDOW_DEFAULT_SIZE)

        central = QWidget()
        central.setObjectName("canvas")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.demo_banner = QLabel("DEMO DATA — synthetic logs; not from this machine.")
        self.demo_banner.setObjectName("demoBanner")
        banner_wrap = QWidget()
        banner_layout = QHBoxLayout(banner_wrap)
        banner_layout.setContentsMargins(24, 16, 24, 0)
        banner_layout.addWidget(self.demo_banner)
        if not demo:
            banner_wrap.hide()
        right_layout.addWidget(banner_wrap)

        notices = QWidget()
        notices_layout = QVBoxLayout(notices)
        notices_layout.setContentsMargins(24, 12, 24, 0)
        notices_layout.setSpacing(8)
        self.partial_bar = NoticeBar("", "warning")
        self.tail_bar = NoticeBar("", "warning")
        self.error_bar = NoticeBar("", "error")
        self.close_wait_label = QLabel("Finishing collection before closing…")
        self.close_wait_label.setObjectName("stateWarning")
        self.close_wait_label.hide()
        for widget in (self.partial_bar, self.tail_bar, self.error_bar, self.close_wait_label):
            notices_layout.addWidget(widget)
        right_layout.addWidget(notices)

        progress_wrap = QWidget()
        progress_layout = QVBoxLayout(progress_wrap)
        progress_layout.setContentsMargins(24, 12, 24, 0)
        progress_layout.setSpacing(6)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("muted")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 13)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        self.progress_wrap = progress_wrap
        progress_wrap.hide()
        right_layout.addWidget(progress_wrap)

        self.stack = QStackedWidget()
        self.overview_page = OverviewPage()
        self.timeline_page = TimelinePage()
        self.evidence_page = EvidencePage()
        self.system_page = SystemInfoPage()
        self.report_page = ReportPage()
        self.boot_selector = self.overview_page.boot_selector
        self.analyze_button = self.overview_page.analyze_button
        self.cancel_button = self.overview_page.cancel_button
        for page in (
            self.overview_page,
            self.timeline_page,
            self.evidence_page,
            self.system_page,
            self.report_page,
        ):
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        right_layout.addWidget(self.stack, 1)

        footer_bar = QFrame()
        footer_bar.setObjectName("footerBar")
        footer_bar.setFixedHeight(FOOTER_HEIGHT)
        footer_layout = QHBoxLayout(footer_bar)
        footer_layout.setContentsMargins(24, 0, 24, 0)
        self.footer = QLabel("")
        self.footer.setObjectName("footer")
        self._set_footer("Idle")
        footer_layout.addWidget(self.footer)
        footer_layout.addStretch(1)
        right_layout.addWidget(footer_bar)

        root.addWidget(right, 1)
        self.setCentralWidget(central)

        for row in range(len(PAGE_NAMES)):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{row + 1}"), self)
            shortcut.activated.connect(lambda row=row: self.nav.setCurrentRow(row))
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._analyze)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.controller.refresh_boots)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self.cancel_collection)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.report_page.save)

        self.analyze_button.clicked.connect(self._analyze)
        self.cancel_button.clicked.connect(self.cancel_collection)
        self.boot_selector.currentIndexChanged.connect(self._update_stale)
        self.overview_page.evidenceRequested.connect(self._jump_to_evidence)
        self.overview_page.coverageRequested.connect(lambda: self.nav.setCurrentRow(2))
        self.timeline_page.evidenceRequested.connect(self._jump_to_evidence)
        self.report_page.reportSaved.connect(lambda: self._set_footer("Report saved."))

        self.controller.stateChanged.connect(self._on_state)
        self.controller.progress.connect(self._on_progress)
        self.controller.bootsReady.connect(self._on_boots)
        self.controller.reportReady.connect(self.apply_report)
        self.controller.failed.connect(self._on_failed)
        self.controller.closeReady.connect(self.close)

        self.theme_manager.themeChanged.connect(self._on_theme_changed)

    def begin(self) -> None:
        self.controller.refresh_boots()

    def cancel_collection(self) -> None:
        if self.controller.running:
            self.controller.cancel()

    def apply_report(self, report) -> None:
        self.overview_page.apply_report(report)
        self.timeline_page.apply_report(report)
        self.evidence_page.apply_report(report)
        self.system_page.apply_report(report)
        self.report_page.apply_report(report)
        self.overview_page.set_stale(None)
        unavailable = sum(1 for c in report.coverage if c.state not in _READ_STATES)
        if unavailable:
            self.partial_bar.show_message(
                f"{unavailable} of {len(report.coverage)} sources were unavailable. "
                "Findings may be incomplete."
            )
        else:
            self.partial_bar.hide()
        if not tail_reliable(report.coverage):
            self.tail_bar.show_message(
                "The journal tail was not reliably collected. "
                "Shutdown-sequence absence is not assessed."
            )
        else:
            self.tail_bar.hide()
        self.error_bar.hide()
        self._set_footer("Ready")

    def _analyze(self) -> None:
        if self.controller.running:
            return
        boot = self.overview_page.selected_boot()
        if boot is not None:
            self.controller.analyze(boot)

    def _jump_to_evidence(self, evidence_id: str) -> None:
        self.nav.setCurrentRow(2)
        self.evidence_page.select_evidence(evidence_id)

    def _update_stale(self, *args) -> None:
        selected = self.overview_page.selected_boot_id()
        if self.controller.is_stale(selected):
            self.overview_page.set_stale(self.controller.analyzed_boot_id[:8])
        else:
            self.overview_page.set_stale(None)

    def _on_state(self, state: str) -> None:
        collecting = state == "collecting"
        self.overview_page.set_collecting(collecting)
        self.analyze_button.setEnabled(not collecting and bool(self.overview_page._boots))
        self.progress_wrap.setVisible(collecting)
        if collecting:
            self._set_footer("Collecting…")
        elif state == "cancelled":
            self._set_footer("Collection cancelled.")
        elif state == "error":
            self._set_footer("Error")
        elif state == "idle":
            self._set_footer("Idle")

    def _on_progress(self, source: str, index: int, total: int) -> None:
        self.progress_label.setText(f"Collecting {source} ({index}/{total})")
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(index)

    def _on_boots(self, boots) -> None:
        self.overview_page.set_boots(boots)
        self.analyze_button.setEnabled(bool(boots))
        self._update_stale()

    def _on_failed(self, message: str) -> None:
        self.error_bar.show_message(
            f"Collection failed: {message}. Partial results are shown where available."
        )

    def _set_footer(self, state: str) -> None:
        self.footer.setText(f"Local only · {state} · v{__version__}")

    def _on_theme_changed(self, theme) -> None:
        icons.retheme(self)
        t = tokens()
        for row, icon_name in enumerate(NAV_ICONS):
            self.nav.item(row).setIcon(
                icons.nav_icon(icon_name, t["text.secondary"], t["nav_selected_text"])
            )
        self.evidence_page.refresh_highlight()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(NAV_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        logo = QLabel()
        logo.setObjectName("brandLogo")
        icons.set_icon(logo, "pulse", "accent", 22)
        brand = QLabel(APP_NAME)
        brand.setObjectName("brand")
        brand_row.addWidget(logo)
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)

        self.tagline = QLabel(TAGLINE)
        self.tagline.setObjectName("tagline")
        self.tagline.setWordWrap(True)
        layout.addWidget(self.tagline)
        layout.addSpacing(12)

        section = QLabel("WORKSPACE")
        section.setObjectName("sectionLabel")
        layout.addWidget(section)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(QSize(20, 20))
        t = tokens()
        for name, icon_name in zip(PAGE_NAMES, NAV_ICONS, strict=True):
            item = QListWidgetItem(
                icons.nav_icon(icon_name, t["text.secondary"], t["nav_selected_text"]), name
            )
            self.nav.addItem(item)
        layout.addWidget(self.nav, 1)

        self.theme_switch = ThemeSwitch(self.theme_manager)
        layout.addWidget(self.theme_switch)

        privacy_row = QHBoxLayout()
        privacy_row.setSpacing(8)
        privacy_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lock = QLabel()
        icons.set_icon(lock, "shield_check", "text.secondary", 16)
        self.privacy = QLabel("Offline · Read-only")
        self.privacy.setObjectName("privacy")
        privacy_row.addWidget(lock)
        privacy_row.addWidget(self.privacy)
        privacy_row.addStretch(1)
        layout.addLayout(privacy_row)

        self.sidebar = sidebar
        return sidebar

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < TAGLINE_HIDE_WIDTH
        self.tagline.setVisible(not narrow)
        self.boot_selector.setMinimumWidth(280 if narrow else 320)

    def closeEvent(self, event):
        if self.controller.request_close():
            self.close_wait_label.hide()
            event.accept()
        else:
            self.close_wait_label.show()
            event.ignore()
