"""Small reusable UI components (docs/03 §3): card, page header, empty state, theme switch."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from syspanic.ui import icons
from syspanic.ui.theme import Theme, tokens


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(24, 20, 24, 20)
        self.vbox.setSpacing(12)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        sub = QLabel(subtitle)
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(sub)


class EmptyState(QWidget):
    def __init__(
        self,
        icon: str,
        headline: str,
        copy: str,
        meta: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture = QLabel()
        icons.set_icon(picture, icon, "accent", 40)
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head = QLabel(headline)
        head.setObjectName("emptyHeadline")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(copy)
        body.setObjectName("emptyCopy")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setMaximumWidth(560)
        layout.addWidget(picture)
        layout.addWidget(head)
        layout.addWidget(body, 0, Qt.AlignmentFlag.AlignCenter)
        if meta:
            row = QHBoxLayout()
            row.setSpacing(8)
            shield = QLabel()
            icons.set_icon(shield, "shield_check", "text.secondary", 16)
            label = QLabel(meta)
            label.setObjectName("emptyMeta")
            row.addWidget(shield)
            row.addWidget(label)
            wrap = QWidget()
            wrap.setLayout(row)
            layout.addWidget(wrap, 0, Qt.AlignmentFlag.AlignCenter)


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


class ThemeSwitch(QFrame):
    """Compact Light/Dark segmented control (docs/03 §3); keyboard accessible."""

    def __init__(self, manager, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("themeSwitch")
        self._manager = manager
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.light_button = self._make_button("Light", "sun", "Switch to the light theme")
        self.dark_button = self._make_button("Dark", "moon", "Switch to the dark theme")
        layout.addWidget(self.light_button, 1)
        layout.addWidget(self.dark_button, 1)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.light_button)
        group.addButton(self.dark_button)
        self.light_button.clicked.connect(lambda: manager.set_theme(Theme.LIGHT))
        self.dark_button.clicked.connect(lambda: manager.set_theme(Theme.DARK))
        manager.themeChanged.connect(self._refresh)
        self._refresh(manager.theme)

    def _make_button(self, text: str, icon_name: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("themeOption")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setToolTip(tooltip)
        button.setAccessibleName(f"{text} theme")
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("switchIcon", icon_name)
        return button

    def _refresh(self, theme) -> None:
        t = tokens()
        self.light_button.setChecked(theme is Theme.LIGHT)
        self.dark_button.setChecked(theme is Theme.DARK)
        for button in (self.light_button, self.dark_button):
            color = t["nav_selected_text"] if button.isChecked() else t["text.secondary"]
            button.setIcon(QIcon(icons.pixmap(button.property("switchIcon"), color, 16)))


def capability_card(icon: str, title: str, copy: str) -> Card:
    card = Card()
    row = QHBoxLayout()
    row.setSpacing(16)
    picture = QLabel()
    icons.set_icon(picture, icon, "text.secondary", 24)
    picture.setAlignment(Qt.AlignmentFlag.AlignTop)
    text = QVBoxLayout()
    text.setSpacing(6)
    text.addWidget(section_title(title))
    body = QLabel(copy)
    body.setObjectName("muted")
    body.setWordWrap(True)
    text.addWidget(body)
    row.addWidget(picture)
    row.addLayout(text, 1)
    card.vbox.addLayout(row)
    return card
