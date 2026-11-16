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
from syspanic.ui import icons
from syspanic.ui.pages import (
    EvidencePage,
    OverviewPage,
    ReportPage,
    SystemInfoPage,
    TimelinePage,
)
from syspanic.ui.theme import ThemeManager, tokens
from syspanic.ui.widgets import ThemeSwitch

NAV_ICONS = ("dashboard", "history", "file_search", "cpu", "file_text")


class MainWindow(QMainWindow):
    def __init__(self, demo: bool = False, theme_manager: ThemeManager | None = None):
        super().__init__()
        if theme_manager is None:
            theme_manager = ThemeManager(QApplication.instance())
            theme_manager.start()
        self.theme_manager = theme_manager
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

        self.stack = QStackedWidget()
        overview = OverviewPage()
        self.boot_selector = overview.boot_selector
        self.analyze_button = overview.analyze_button
        for page in (overview, TimelinePage(), EvidencePage(), SystemInfoPage(), ReportPage()):
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        right_layout.addWidget(self.stack, 1)

        footer_bar = QFrame()
        footer_bar.setObjectName("footerBar")
        footer_bar.setFixedHeight(FOOTER_HEIGHT)
        footer_layout = QHBoxLayout(footer_bar)
        footer_layout.setContentsMargins(24, 0, 24, 0)
        self.footer = QLabel(f"Local only · Idle · v{__version__}")
        self.footer.setObjectName("footer")
        footer_layout.addWidget(self.footer)
        footer_layout.addStretch(1)
        right_layout.addWidget(footer_bar)

        root.addWidget(right, 1)
        self.setCentralWidget(central)

        for row in range(len(PAGE_NAMES)):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{row + 1}"), self)
            shortcut.activated.connect(lambda row=row: self.nav.setCurrentRow(row))

        self.theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme) -> None:
        icons.retheme(self)
        t = tokens()
        for row, icon_name in enumerate(NAV_ICONS):
            self.nav.item(row).setIcon(
                icons.nav_icon(icon_name, t["text.secondary"], t["nav_selected_text"])
            )

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
