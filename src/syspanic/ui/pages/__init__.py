"""M0 pages: designed idle/empty states (docs/03 §5). Real content arrives in M8."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from syspanic.ui import icons
from syspanic.ui.theme import TOKENS
from syspanic.ui.widgets import Card, EmptyState, PageHeader, capability_card, section_title


class ScrollPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pageScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def set_content(self, content: QWidget) -> None:
        self.setWidget(content)


def _content_widget() -> tuple[QWidget, QVBoxLayout]:
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(32, 28, 32, 28)
    layout.setSpacing(20)
    return content, layout


class OverviewPage(ScrollPage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        content, layout = _content_widget()
        layout.addWidget(
            PageHeader(
                "Overview",
                "What happened? A plain-language answer built from local journal and crash "
                "evidence.",
            )
        )

        session = Card()
        session.vbox.addWidget(section_title("Analysis session"))
        field = QHBoxLayout()
        field.setSpacing(8)
        field_icon = QLabel()
        field_icon.setPixmap(icons.pixmap("history", TOKENS["text.secondary"], 16))
        field_label = QLabel("Boot session")
        field_label.setObjectName("fieldLabel")
        field.addWidget(field_icon)
        field.addWidget(field_label)
        field.addStretch(1)
        session.vbox.addLayout(field)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.boot_selector = QComboBox()
        self.boot_selector.setMinimumWidth(320)
        self.boot_selector.addItem("Current boot · placeholder")
        self.boot_selector.setEnabled(False)
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setObjectName("analyze")
        self.analyze_button.setMinimumWidth(140)
        self.analyze_button.setEnabled(False)
        self.analyze_button.setToolTip("Analyze becomes available when collection is implemented.")
        row.addWidget(self.boot_selector, 1)
        row.addWidget(self.analyze_button)
        session.vbox.addLayout(row)
        hint = QLabel(
            "Boot selection and analysis are placeholders in this build — diagnostics arrive "
            "with the collection milestones."
        )
        hint.setObjectName("sessionHint")
        hint.setWordWrap(True)
        session.vbox.addWidget(hint)
        layout.addWidget(session)

        empty = Card()
        empty.vbox.addWidget(
            EmptyState(
                "pulse",
                "Every crash leaves a clue.",
                "Understand Linux crashes with clear, evidence-based insights from your "
                "system logs.",
                meta="Offline · Read-only · Privacy-first",
            )
        )
        layout.addWidget(empty)

        capabilities = QHBoxLayout()
        capabilities.setSpacing(16)
        capabilities.addWidget(
            capability_card(
                "search",
                "Crash investigation",
                "Trace boot boundaries, shutdown markers, and kernel signatures in a "
                "chronological incident view.",
            )
        )
        capabilities.addWidget(
            capability_card(
                "file_text",
                "Diagnostic reports",
                "Share a sanitized Markdown report with bounded excerpts and an honest "
                "coverage summary.",
            )
        )
        layout.addLayout(capabilities)
        layout.addStretch(1)
        self.set_content(content)


class EmptyStatePage(ScrollPage):
    def __init__(
        self,
        title: str,
        subtitle: str,
        icon: str,
        headline: str,
        copy: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        content, layout = _content_widget()
        layout.addWidget(PageHeader(title, subtitle))
        card = Card()
        card.vbox.addWidget(EmptyState(icon, headline, copy))
        layout.addWidget(card)
        layout.addStretch(1)
        self.set_content(content)


def TimelinePage() -> EmptyStatePage:
    return EmptyStatePage(
        "Timeline",
        "When did it happen? Key events in chronological order.",
        "history",
        "No timeline yet.",
        "Boot boundaries, shutdown markers, and the first occurrence of each finding appear "
        "here after the first analysis.",
    )


def EvidencePage() -> EmptyStatePage:
    return EmptyStatePage(
        "Evidence",
        "What is the proof? The exact lines behind every finding.",
        "file_search",
        "No evidence yet.",
        "Collected journal slices and crash-artifact metadata are listed here with their "
        "coverage states, so missing evidence is never mistaken for health.",
    )


def SystemInfoPage() -> EmptyStatePage:
    return EmptyStatePage(
        "System Information",
        "What hardware and software context applies?",
        "cpu",
        "No system profile yet.",
        "OS, kernel, CPU, memory, GPU, and firmware details are gathered during analysis and "
        "labeled 'collected now' — never crash-time measurements.",
    )


def ReportPage() -> EmptyStatePage:
    return EmptyStatePage(
        "Report",
        "What can you share? A sanitized, evidence-cited report.",
        "file_text",
        "No report yet.",
        "A sanitized Markdown report with bounded excerpts becomes available after analysis. "
        "Preview is always required before export.",
    )
