"""Small reusable UI components (docs/03 §3): card, page header, empty state."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from syspanic.ui import icons
from syspanic.ui.theme import TOKENS


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
        picture.setPixmap(icons.pixmap(icon, TOKENS["accent"], 40))
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
            shield.setPixmap(icons.pixmap("shield_check", TOKENS["text.secondary"], 16))
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


def capability_card(icon: str, title: str, copy: str) -> Card:
    card = Card()
    row = QHBoxLayout()
    row.setSpacing(16)
    picture = QLabel()
    picture.setPixmap(icons.pixmap(icon, TOKENS["text.secondary"], 24))
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
