"""M8 pages: real report content with designed idle states (docs/03 §5)."""

from datetime import UTC

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from syspanic.constants import (
    SOURCE_CRASH_PSTORE,
    SOURCE_CRASH_VMCORE,
    SOURCE_CRASH_VMCORE_DMESG,
    SOURCE_DMESG,
    SOURCE_JOURNAL_BOOTS,
    SOURCE_JOURNAL_KERNEL,
    SOURCE_JOURNAL_SYSTEM,
)
from syspanic.diagnostics.coverage import tail_reliable
from syspanic.domain.enums import Severity, SourceState
from syspanic.report.markdown import NO_FINDINGS_TEXT, render_report_with_counts
from syspanic.ui import icons
from syspanic.ui.table_models import TimelineModel
from syspanic.ui.theme import tokens
from syspanic.ui.widgets import (
    Card,
    EmptyState,
    NoticeBar,
    PageHeader,
    SeverityBadge,
    capability_card,
    section_title,
)

_READ_STATES = (SourceState.AVAILABLE, SourceState.EMPTY, SourceState.TRUNCATED)
_STATE_LABEL = {
    SourceState.AVAILABLE: "Available",
    SourceState.EMPTY: "Empty",
    SourceState.PERMISSION_DENIED: "Denied",
    SourceState.NOT_FOUND: "Not found",
    SourceState.UNSUPPORTED: "Unsupported",
    SourceState.TIMEOUT: "Timeout",
    SourceState.ERROR: "Error",
}
_ASSOCIATION_LABEL = {
    "matched": "Matched to this boot",
    "possibly_related": "Possibly related",
    "unknown": "Unknown association",
}
_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
DENIED_TEXT = (
    "System journal is not readable by this user. "
    "SysPanic will not request elevated privileges."
)
REDACTION_NOTICE = (
    "Redaction is best-effort. Review the preview before sharing; "
    "unrecognized secrets may remain."
)
_REDACTION_ORDER = ("HOST", "USER", "IP", "MAC", "EMAIL", "SERIAL", "UUID", "CRED")


def _short_time(ts) -> str:
    if ts is None:
        return "time unknown"
    local = ts.astimezone()
    return f"{local.day:02d} {_MONTHS[local.month - 1]} {local.hour:02d}:{local.minute:02d}"


def _line_time(ts) -> str:
    if ts is None:
        return "--:--:--.---"
    local = ts.astimezone()
    return f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}.{local.microsecond // 1000:03d}"


def iec_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TiB"


def mono_font(pixel_size: int = 13) -> QFont:
    font = QFont()
    font.setFamilies(["JetBrains Mono", "Noto Sans Mono", "monospace"])
    font.setPixelSize(pixel_size)
    return font


def state_label(coverage) -> str:
    if coverage.state is SourceState.TRUNCATED:
        return "Truncated (head)" if coverage.head_truncated else "Truncated (tail)"
    return _STATE_LABEL[coverage.state]


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


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


def _field(name: str, value) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    key = QLabel(name)
    key.setObjectName("fieldLabel")
    key.setMinimumWidth(160)
    if value is None or value == "":
        val = QLabel("Not available")
        val.setObjectName("muted")
    else:
        val = QLabel(str(value))
        val.setWordWrap(True)
    row.addWidget(key)
    row.addWidget(val, 1)
    return row


class FindingRow(QWidget):
    def __init__(self, finding, on_evidence, parent: QWidget | None = None):
        super().__init__(parent)
        self.finding = finding
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(SeverityBadge(finding.severity))
        title = QLabel(finding.title)
        title.setStyleSheet("font-weight: 600;")
        header.addWidget(title, 1)
        rule = QLabel(finding.rule_id)
        rule.setObjectName("chip")
        header.addWidget(rule)
        self.toggle_button = QPushButton("Show evidence")
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)
        header.addWidget(self.toggle_button)
        layout.addLayout(header)

        interpretation = QLabel(finding.interpretation)
        interpretation.setObjectName("muted")
        interpretation.setWordWrap(True)
        layout.addWidget(interpretation)

        self.detail = QWidget()
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(0, 4, 0, 4)
        detail_layout.setSpacing(8)
        for ref in finding.evidence:
            excerpt = QLabel(ref.excerpt)
            excerpt.setObjectName("excerpt")
            excerpt.setFont(mono_font(12))
            excerpt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            detail_layout.addWidget(excerpt)
        for heading, items in (
            ("Suspected causes (unconfirmed)", finding.suspected_causes),
            ("Unknowns", finding.unknowns),
            ("Next steps", finding.next_steps),
        ):
            if items:
                head = QLabel(heading)
                head.setObjectName("fieldLabel")
                detail_layout.addWidget(head)
                for item in items:
                    detail_layout.addWidget(_muted(f"• {item}"))
        links = QHBoxLayout()
        links.setSpacing(8)
        self.evidence_buttons = []
        for ref in finding.evidence:
            button = QPushButton(ref.evidence_id)
            button.setObjectName("chip")
            button.clicked.connect(lambda checked=False, eid=ref.evidence_id: on_evidence(eid))
            self.evidence_buttons.append(button)
            links.addWidget(button)
        links.addStretch(1)
        detail_layout.addLayout(links)
        self.detail.hide()
        layout.addWidget(self.detail)

    def _toggle(self, checked: bool) -> None:
        self.detail.setVisible(checked)
        self.toggle_button.setText("Hide evidence" if checked else "Show evidence")


def _status_chip(report) -> str:
    if report.demo:
        return "Demo data"
    if report.boot.is_current:
        return "Current boot"
    if not tail_reliable(report.coverage):
        return "Shutdown assessment incomplete"
    rule_ids = {f.rule_id for f in report.findings}
    if "SHD-002" in rule_ids:
        return "No shutdown-sequence marker observed"
    if "SHD-001" in rule_ids:
        finding = next(f for f in report.findings if f.rule_id == "SHD-001")
        ids = {ref.evidence_id for ref in finding.evidence}
        messages = [e.message for e in report.evidence if e.evidence_id in ids]
        journald_only = any("Journal stopped" in m for m in messages) and not any(
            "Powering off" in m or "Rebooting" in m for m in messages
        )
        return "Journald stopped only" if journald_only else "Shutdown-sequence marker observed"
    return "Insufficient evidence"


class BootSelector(QComboBox):
    # Qt 6.12 showPopup() sizes the container to all rows, ignoring maxVisibleItems.
    def showPopup(self):
        super().showPopup()
        view = self.view()
        row = view.sizeHintForRow(0)
        if row <= 0:
            return
        container = view.window()
        cap = row * self.maxVisibleItems() + (container.height() - view.height())
        if container.height() <= cap:
            return
        delta = container.height() - cap
        upward = container.y() < self.mapToGlobal(QPoint(0, 0)).y()
        container.resize(container.width(), cap)
        if upward:
            container.move(container.x(), container.y() + delta)
        container.layout().activate()


class OverviewPage(ScrollPage):
    evidenceRequested = Signal(str)
    coverageRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._boots = ()
        self._report = None
        content, layout = _content_widget()
        self._layout = layout
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
        icons.set_icon(field_icon, "history", "text.secondary", 16)
        field_label = QLabel("Boot session")
        field_label.setObjectName("fieldLabel")
        field.addWidget(field_icon)
        field.addWidget(field_label)
        field.addStretch(1)
        session.vbox.addLayout(field)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.boot_selector = BootSelector()
        self.boot_selector.setMinimumWidth(320)
        self.boot_selector.setMaxVisibleItems(8)
        self.boot_selector.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.boot_selector.addItem("Loading boot sessions…")
        self.boot_selector.setEnabled(False)
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setObjectName("analyze")
        self.analyze_button.setMinimumWidth(140)
        self.analyze_button.setEnabled(False)
        self.analyze_button.setToolTip("Collect evidence for the selected boot (Ctrl+R).")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(140)
        self.cancel_button.setToolTip("Cancel the running collection (Esc).")
        self.cancel_button.hide()
        row.addWidget(self.boot_selector, 1)
        row.addWidget(self.analyze_button)
        row.addWidget(self.cancel_button)
        session.vbox.addLayout(row)
        hint = QLabel(
            "Collection is read-only and local. Select a boot session, then Analyze."
        )
        hint.setObjectName("sessionHint")
        hint.setWordWrap(True)
        session.vbox.addWidget(hint)
        layout.addWidget(session)

        self.stale_bar = NoticeBar("", "info")
        layout.addWidget(self.stale_bar)

        self.idle_wrap = QWidget()
        idle_layout = QVBoxLayout(self.idle_wrap)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(20)
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
        idle_layout.addWidget(empty)
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
        idle_layout.addLayout(capabilities)
        layout.addWidget(self.idle_wrap)

        self.results_wrap = QWidget()
        self.results_wrap.hide()
        layout.addWidget(self.results_wrap)
        layout.addStretch(1)
        self.set_content(content)

    def set_boots(self, boots) -> None:
        selected = self.selected_boot_id()
        self._boots = tuple(sorted(boots, key=lambda b: (not b.is_current, -b.index)))
        self.boot_selector.clear()
        for boot in self._boots:
            if boot.is_current:
                label = "Current boot"
            elif boot.index == -1:
                label = "Previous boot"
            else:
                label = f"Boot {boot.index}"
            text = f"{label} · {boot.boot_id[:8]} · {_short_time(boot.first_entry)}"
            tooltip = (
                f"Boot ID: {boot.boot_id}\n"
                f"First entry: {boot.first_entry.isoformat() if boot.first_entry else 'unknown'}\n"
                f"Last entry: {boot.last_entry.isoformat() if boot.last_entry else 'unknown'}"
            )
            self.boot_selector.addItem(text, boot.boot_id)
            index = self.boot_selector.count() - 1
            self.boot_selector.setItemData(index, tooltip, Qt.ItemDataRole.ToolTipRole)
        if not any(not b.is_current for b in self._boots):
            self.boot_selector.addItem("No previous boots in the journal")
            item = self.boot_selector.model().item(self.boot_selector.count() - 1)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self.boot_selector.setEnabled(bool(self._boots))
        self.analyze_button.setEnabled(bool(self._boots))
        if selected:
            for i in range(self.boot_selector.count()):
                if self.boot_selector.itemData(i) == selected:
                    self.boot_selector.setCurrentIndex(i)
                    break

    def selected_boot_id(self):
        index = self.boot_selector.currentIndex()
        if index < 0:
            return None
        return self.boot_selector.itemData(index)

    def selected_boot(self):
        boot_id = self.selected_boot_id()
        return next((b for b in self._boots if b.boot_id == boot_id), None)

    def set_stale(self, boot_id8) -> None:
        if boot_id8 is None:
            self.stale_bar.hide()
        else:
            self.stale_bar.show_message(
                f"Results are for boot {boot_id8}. Select Analyze to collect the new selection."
            )

    def set_collecting(self, collecting: bool) -> None:
        self.analyze_button.setVisible(not collecting)
        self.cancel_button.setVisible(collecting)
        self.boot_selector.setEnabled(not collecting and bool(self._boots))

    def apply_report(self, report) -> None:
        self._report = report
        self.idle_wrap.hide()
        old = self.results_wrap
        self.results_wrap = QWidget()
        self._layout.replaceWidget(old, self.results_wrap)
        old.deleteLater()
        layout = QVBoxLayout(self.results_wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        summary = Card()
        summary.vbox.addWidget(section_title("Incident summary"))
        boot = report.boot
        window = "Unknown"
        duration = "Unknown"
        if boot.first_entry and boot.last_entry:
            window = f"{_short_time(boot.first_entry)} → {_short_time(boot.last_entry)}"
            seconds = int((boot.last_entry - boot.first_entry).total_seconds())
            hours, minutes = divmod(seconds // 60, 60)
            duration = f"{hours} h {minutes} m" if hours else f"{minutes} m"
        summary.vbox.addLayout(_field("Boot", boot.boot_id[:8]))
        summary.vbox.addLayout(_field("Observed window", window))
        summary.vbox.addLayout(_field("Duration", duration))
        chip_row = QHBoxLayout()
        self.status_chip = QLabel(_status_chip(report))
        self.status_chip.setObjectName("chip")
        chip_row.addWidget(self.status_chip)
        chip_row.addStretch(1)
        summary.vbox.addLayout(chip_row)
        layout.addWidget(summary)

        counts_row = QHBoxLayout()
        counts_row.setSpacing(16)
        for severity, object_name, label in (
            (Severity.CRITICAL, "countCritical", "Critical"),
            (Severity.WARNING, "countWarning", "Warning"),
            (Severity.NOTICE, "countNotice", "Notice"),
            (Severity.INFO, "countInfo", "Info"),
        ):
            count = sum(1 for f in report.findings if f.severity is severity)
            card = Card()
            number = QLabel(str(count))
            number.setObjectName(object_name)
            number.setProperty("zero", count == 0)
            name = QLabel(label)
            name.setObjectName("muted")
            card.vbox.addWidget(number)
            card.vbox.addWidget(name)
            counts_row.addWidget(card)
        layout.addLayout(counts_row)

        findings_card = Card()
        findings_card.vbox.addWidget(section_title("Findings"))
        self.finding_rows = []
        if not report.findings:
            none_label = QLabel(NO_FINDINGS_TEXT)
            none_label.setObjectName("emptyCopy")
            none_label.setWordWrap(True)
            findings_card.vbox.addWidget(none_label)
            self.show_all_button = None
        else:
            for finding in report.findings[:5]:
                row = FindingRow(finding, self.evidenceRequested.emit)
                self.finding_rows.append(row)
                findings_card.vbox.addWidget(row)
            self.show_all_button = None
            if len(report.findings) > 5:
                self.show_all_button = QPushButton(f"Show all {len(report.findings)} findings")
                self.show_all_button.clicked.connect(self._show_all_findings)
                findings_card.vbox.addWidget(self.show_all_button)
        layout.addWidget(findings_card)
        self._findings_card = findings_card

        coverage_card = Card()
        coverage_card.vbox.addWidget(section_title("Coverage"))
        available = sum(1 for c in report.coverage if c.state in _READ_STATES)
        self.coverage_strip = QLabel(f"{available} of {len(report.coverage)} sources available")
        self.coverage_strip.setObjectName("coverageStrip")
        coverage_card.vbox.addWidget(self.coverage_strip)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for coverage in report.coverage:
            if coverage.state not in _READ_STATES:
                chip = QLabel(f"{coverage.source}: {state_label(coverage)}")
                chip.setObjectName("chip")
                chips.addWidget(chip)
        if not tail_reliable(report.coverage):
            chip = QLabel("tail unreliable")
            chip.setObjectName("stateWarning")
            chips.addWidget(chip)
        chips.addStretch(1)
        coverage_card.vbox.addLayout(chips)
        self.view_coverage_button = QPushButton("View coverage")
        self.view_coverage_button.clicked.connect(self.coverageRequested.emit)
        coverage_card.vbox.addWidget(self.view_coverage_button)
        layout.addWidget(coverage_card)

        self.artifacts_card = Card()
        self.artifacts_card.vbox.addWidget(section_title("Crash artifacts"))
        artifacts = report.artifacts
        if artifacts is None:
            self.artifacts_card.vbox.addWidget(_muted("No crash artifact metadata was collected."))
        else:
            vmcore_count = len(artifacts.vmcore_files)
            vmcore_size = sum(a.size_bytes for a in artifacts.vmcore_files)
            self.artifacts_card.vbox.addLayout(
                _field("vmcore files", f"{vmcore_count} ({iec_size(vmcore_size)})")
            )
            self.artifacts_card.vbox.addLayout(
                _field(
                    "vmcore-dmesg.txt",
                    "present" if artifacts.vmcore_dmesg else "not found",
                )
            )
            self.artifacts_card.vbox.addLayout(
                _field("pstore records", len(artifacts.pstore_records))
            )
            loaded = artifacts.crash_kernel_loaded
            self.artifacts_card.vbox.addLayout(
                _field(
                    "Crash kernel loaded",
                    "yes" if loaded else ("no" if loaded is False else "Not available"),
                )
            )
            for artifact in (
                artifacts.vmcore_files + artifacts.vmcore_dmesg + artifacts.pstore_records
            ):
                label = _ASSOCIATION_LABEL[artifact.association.value]
                self.artifacts_card.vbox.addWidget(
                    _muted(f"{artifact.path} — {label} ({artifact.association_reason})")
                )
        self.artifacts_card.vbox.addWidget(_muted("Binary vmcore contents were not analyzed."))
        layout.addWidget(self.artifacts_card)

        next_card = Card()
        next_card.vbox.addWidget(section_title("Next steps"))
        suggestions = []
        for finding in report.findings:
            for step in finding.next_steps:
                entry = f"{finding.rule_id}: {step}"
                if entry not in suggestions:
                    suggestions.append(entry)
                if len(suggestions) == 3:
                    break
            if len(suggestions) == 3:
                break
        if suggestions:
            for suggestion in suggestions:
                next_card.vbox.addWidget(_muted(f"• {suggestion}"))
        else:
            next_card.vbox.addWidget(
                _muted("No rule-specific next steps were produced for this boot.")
            )
        layout.addWidget(next_card)
        self.results_wrap.show()

    def _show_all_findings(self) -> None:
        if self._report is None:
            return
        for finding in self._report.findings[5:]:
            row = FindingRow(finding, self.evidenceRequested.emit)
            self.finding_rows.append(row)
            self._findings_card.vbox.insertWidget(self._findings_card.vbox.count() - 1, row)
        if self.show_all_button is not None:
            self.show_all_button.hide()


class TimelinePage(ScrollPage):
    evidenceRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        content, layout = _content_widget()
        layout.addWidget(
            PageHeader("Timeline", "When did it happen? Key events in chronological order.")
        )
        self.idle_wrap = QWidget()
        idle_layout = QVBoxLayout(self.idle_wrap)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        card.vbox.addWidget(
            EmptyState(
                "history",
                "No timeline yet.",
                "Boot boundaries, shutdown markers, and the first occurrence of each finding "
                "appear here after the first analysis.",
            )
        )
        idle_layout.addWidget(card)
        layout.addWidget(self.idle_wrap)

        self.results_wrap = QWidget()
        results_layout = QVBoxLayout(self.results_wrap)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(12)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.filter_buttons = {}
        for name in ("All", "Critical", "Warning", "Notice", "Info"):
            button = QPushButton(name)
            button.setObjectName("chip")
            button.setCheckable(True)
            button.setChecked(name == "All")
            button.clicked.connect(lambda checked=False, n=name: self._filter_clicked(n))
            self.filter_buttons[name] = button
            filter_row.addWidget(button)
        filter_row.addStretch(1)
        results_layout.addLayout(filter_row)
        self.model = TimelineModel(())
        self.table = QTableView()
        self.table.setObjectName("timelineTable")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(320)
        self.table.doubleClicked.connect(self._on_double_click)
        results_layout.addWidget(self.table)
        self.empty_label = QLabel("")
        self.empty_label.setObjectName("emptyCopy")
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        results_layout.addWidget(self.empty_label)
        self.footer_label = QLabel("")
        self.footer_label.setObjectName("muted")
        results_layout.addWidget(self.footer_label)
        self.results_wrap.hide()
        layout.addWidget(self.results_wrap)
        layout.addStretch(1)
        self.set_content(content)

    def _filter_clicked(self, name: str) -> None:
        if name == "All":
            for other, button in self.filter_buttons.items():
                button.setChecked(other == "All")
            self.model.set_filter(set())
            return
        self.filter_buttons["All"].setChecked(False)
        active = {
            Severity(n.lower())
            for n, button in self.filter_buttons.items()
            if n != "All" and button.isChecked()
        }
        if not active:
            self.filter_buttons["All"].setChecked(True)
        self.model.set_filter(active)

    def _on_double_click(self, index) -> None:
        if index.isValid():
            self.evidenceRequested.emit(self.model.event_at(index.row()).evidence_id)

    def apply_report(self, report) -> None:
        self.idle_wrap.hide()
        self.results_wrap.show()
        journal_read = any(
            c.source in (SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM) and c.state in _READ_STATES
            for c in report.coverage
        )
        if not journal_read:
            self.table.hide()
            self.footer_label.hide()
            self.empty_label.setText(
                "Timeline unavailable — the journal for this boot could not be read."
            )
            self.empty_label.show()
            self.model = TimelineModel(())
            self.table.setModel(self.model)
            return
        self.empty_label.hide()
        self.table.show()
        self.footer_label.show()
        self.model = TimelineModel(report.timeline)
        self.table.setModel(self.model)
        for button in self.filter_buttons.values():
            button.setChecked(button.text() == "All")
        count = len(report.timeline)
        if count == 0:
            self.table.hide()
            self.empty_label.setText("No timeline events for this boot.")
            self.empty_label.show()
            self.footer_label.setText("0 key events.")
        elif count >= 200:
            self.footer_label.setText(f"Showing first 200 of {count} key events.")
        else:
            self.footer_label.setText(f"{count} key events.")


class EvidencePage(ScrollPage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        content, layout = _content_widget()
        layout.addWidget(
            PageHeader(
                "Evidence", "What is the proof? The exact lines behind every finding."
            )
        )
        self.idle_wrap = QWidget()
        idle_layout = QVBoxLayout(self.idle_wrap)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        card.vbox.addWidget(
            EmptyState(
                "file_search",
                "No evidence yet.",
                "Collected journal slices and crash-artifact metadata are listed here with "
                "their coverage states, so missing evidence is never mistaken for health.",
            )
        )
        idle_layout.addWidget(card)
        layout.addWidget(self.idle_wrap)

        self.results_wrap = QWidget()
        results_layout = QVBoxLayout(self.results_wrap)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(12)
        self.denied_panel = QLabel(DENIED_TEXT)
        self.denied_panel.setObjectName("deniedPanel")
        self.denied_panel.setWordWrap(True)
        self.denied_panel.hide()
        results_layout.addWidget(self.denied_panel)
        self.denied_hint = _muted("")
        self.denied_hint.hide()
        results_layout.addWidget(self.denied_hint)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.source_list = QListWidget()
        self.source_list.setObjectName("evidenceSources")
        self.source_list.currentRowChanged.connect(self._render_group)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self.source_header = QLabel("")
        self.source_header.setObjectName("sectionTitle")
        right_layout.addWidget(self.source_header)
        self.filter = QLineEdit()
        self.filter.setObjectName("evidenceFilter")
        self.filter.setPlaceholderText("Filter lines")
        self.filter.textChanged.connect(lambda _: self._render_group())
        right_layout.addWidget(self.filter)
        self.viewer = QPlainTextEdit()
        self.viewer.setObjectName("evidenceViewer")
        self.viewer.setReadOnly(True)
        self.viewer.setFont(mono_font())
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.viewer.setMinimumHeight(360)
        right_layout.addWidget(self.viewer)
        splitter.addWidget(self.source_list)
        splitter.addWidget(right)
        splitter.setSizes([280, 720])
        results_layout.addWidget(splitter, 1)
        self.results_wrap.hide()
        layout.addWidget(self.results_wrap)
        layout.addStretch(1)
        self.set_content(content)
        self._groups = {}
        self._order = []
        self._selected_id = None

    def apply_report(self, report) -> None:
        self._selected_id = None
        self.idle_wrap.hide()
        self.results_wrap.show()
        coverage_by_source = {c.source: c for c in report.coverage}
        groups = {}
        order = []

        def add(name, line, coverage_source):
            if name not in groups:
                groups[name] = {"lines": [], "coverage": coverage_by_source.get(coverage_source)}
                order.append(name)
            groups[name]["lines"].append(line)

        for item in report.evidence:
            prefix = item.evidence_id.split("-")[0]
            if prefix == "JRN":
                name = item.source
                coverage_source = item.source
                ident = item.identifier or (
                    "kernel"
                    if item.provenance.get("_TRANSPORT") == "kernel"
                    else "journal"
                )
                line = f"[{item.evidence_id}] {_line_time(item.timestamp)} {ident}: {item.message}"
            elif prefix == "DMS":
                name = "dmesg"
                coverage_source = SOURCE_DMESG
                line = f"[{item.evidence_id}] {_line_time(item.timestamp)} kernel: {item.message}"
            elif prefix == "BTM":
                name = "boot metadata"
                coverage_source = SOURCE_JOURNAL_BOOTS
                line = f"[{item.evidence_id}] {item.message}"
            elif prefix == "AFM":
                name = "artifact metadata"
                coverage_source = SOURCE_CRASH_VMCORE
                line = f"[{item.evidence_id}] {item.message}"
            elif prefix == "VMD":
                name = "vmcore-dmesg"
                coverage_source = SOURCE_CRASH_VMCORE_DMESG
                line = f"[{item.evidence_id}] {item.message}"
            else:
                name = "pstore"
                coverage_source = SOURCE_CRASH_PSTORE
                line = f"[{item.evidence_id}] {item.message}"
            add(name, line, coverage_source)

        for source, name in (
            (SOURCE_JOURNAL_KERNEL, "journal.kernel"),
            (SOURCE_JOURNAL_SYSTEM, "journal.system"),
            (SOURCE_DMESG, "dmesg"),
        ):
            if name not in groups and source in coverage_by_source:
                add(name, "", source)
                groups[name]["lines"] = []
        if report.artifacts and report.artifacts.vmcore_files:
            name = "vmcore metadata"
            if name not in groups:
                groups[name] = {
                    "lines": [],
                    "coverage": coverage_by_source.get(SOURCE_CRASH_VMCORE),
                }
                order.append(name)
            for artifact in report.artifacts.vmcore_files:
                groups[name]["lines"].append(
                    f"{artifact.path} size={iec_size(artifact.size_bytes)} "
                    f"association={_ASSOCIATION_LABEL[artifact.association.value]}"
                )

        self._groups = groups
        self._order = order
        self.source_list.clear()
        for name in order:
            group = groups[name]
            coverage = group["coverage"]
            count = len(group["lines"])
            if coverage is None:
                badge = "Available" if count else "Empty"
                tail = ""
            else:
                badge = state_label(coverage)
                tail = (
                    " · Tail unreliable"
                    if not coverage.tail_reliable and coverage.state in _READ_STATES
                    else ""
                )
            self.source_list.addItem(f"{name} · {count} · {badge}{tail}")
        denied = [
            c
            for c in report.coverage
            if c.state is SourceState.PERMISSION_DENIED
            and c.source
            in (SOURCE_JOURNAL_KERNEL, SOURCE_JOURNAL_SYSTEM, SOURCE_DMESG, SOURCE_CRASH_PSTORE)
        ]
        if denied:
            self.denied_panel.show()
            hint = "; ".join(c.detail for c in denied if c.detail)
            self.denied_hint.setText(hint)
            self.denied_hint.setVisible(bool(hint))
        else:
            self.denied_panel.hide()
            self.denied_hint.hide()
        self.filter.clear()
        if order:
            self.source_list.setCurrentRow(0)

    def _render_group(self, *args) -> None:
        self.viewer.setExtraSelections([])
        row = self.source_list.currentRow()
        if row < 0 or row >= len(self._order):
            return
        name = self._order[row]
        group = self._groups[name]
        coverage = group["coverage"]
        detail = coverage.detail if coverage is not None else ""
        self.source_header.setText(f"{name} — {detail}" if detail else name)
        needle = self.filter.text()
        lines = group["lines"]
        if needle:
            lines = [line for line in lines if needle in line]
            if not lines:
                self.viewer.setPlainText(f'No lines match "{needle}".')
                return
        self.viewer.setPlainText("\n".join(lines))
        self._apply_highlight()

    def _apply_highlight(self) -> None:
        self.viewer.setExtraSelections([])
        if not self._selected_id:
            return
        cursor = self.viewer.document().find(f"[{self._selected_id}]")
        if cursor.isNull():
            return
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        t = tokens()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(t["evidence.highlight"]))
        fmt.setForeground(QColor(t["evidence.highlight_text"]))
        selection.format = fmt
        self.viewer.setExtraSelections([selection])

    def refresh_highlight(self) -> None:
        self._apply_highlight()

    def select_evidence(self, evidence_id: str) -> None:
        for row, name in enumerate(self._order):
            if any(line.startswith(f"[{evidence_id}]") for line in self._groups[name]["lines"]):
                self._selected_id = evidence_id
                self.filter.clear()
                self.source_list.setCurrentRow(row)
                self._render_group()
                cursor = self.viewer.document().find(f"[{evidence_id}]")
                if not cursor.isNull():
                    cursor.clearSelection()
                    self.viewer.setTextCursor(cursor)
                    self.viewer.centerCursor()
                return
        self._selected_id = None
        self.viewer.setExtraSelections([])


class SystemInfoPage(ScrollPage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        content, layout = _content_widget()
        layout.addWidget(
            PageHeader(
                "System Information", "What hardware and software context applies?"
            )
        )
        self.banner = QLabel("Collected now — this is not a crash-time snapshot.")
        self.banner.setObjectName("stateWarning")
        self.banner.setWordWrap(True)
        layout.addWidget(self.banner)
        self.idle_wrap = QWidget()
        idle_layout = QVBoxLayout(self.idle_wrap)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        card.vbox.addWidget(
            EmptyState(
                "cpu",
                "No system profile yet.",
                "OS, kernel, CPU, memory, GPU, and firmware details are gathered during "
                "analysis and labeled 'collected now' — never crash-time measurements.",
            )
        )
        idle_layout.addWidget(card)
        layout.addWidget(self.idle_wrap)
        self.results_wrap = QWidget()
        self.results_wrap.hide()
        layout.addWidget(self.results_wrap)
        layout.addStretch(1)
        self.set_content(content)
        self._layout = layout

    def apply_report(self, report) -> None:
        self.idle_wrap.hide()
        old = self.results_wrap
        self.results_wrap = QWidget()
        self._layout.replaceWidget(old, self.results_wrap)
        old.deleteLater()
        layout = QVBoxLayout(self.results_wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        profile = report.system
        if profile is None:
            card = Card()
            card.vbox.addWidget(
                _muted("System profile sources were unavailable for this run.")
            )
            layout.addWidget(card)
            self.results_wrap.show()
            return

        os_card = Card()
        os_card.vbox.addWidget(section_title("OS & kernel"))
        os_card.vbox.addLayout(_field("Distribution", profile.os_name))
        os_card.vbox.addLayout(_field("Version", profile.os_version_id))
        os_card.vbox.addLayout(_field("Kernel release", profile.kernel))
        os_card.vbox.addLayout(_field("Architecture", profile.arch))
        layout.addWidget(os_card)

        cpu_card = Card()
        cpu_card.vbox.addWidget(section_title("CPU"))
        cpu_card.vbox.addLayout(_field("Model", profile.cpu_model))
        cpu_card.vbox.addLayout(_field("Logical cores", profile.cpu_cores))
        cpu_card.vbox.addLayout(_field("Microcode version", profile.microcode))
        layout.addWidget(cpu_card)

        mem_card = Card()
        mem_card.vbox.addWidget(section_title("Memory"))
        mem_card.vbox.addLayout(_field("Total RAM", iec_size(profile.mem_total_kib * 1024)))
        layout.addWidget(mem_card)

        gpu_card = Card()
        gpu_card.vbox.addWidget(section_title("GPUs"))
        if profile.gpus:
            table = QTableWidget(len(profile.gpus), 3)
            table.setHorizontalHeaderLabels(["PCI address", "Model", "Driver in use"])
            table.verticalHeader().hide()
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            for row, gpu in enumerate(profile.gpus):
                table.setItem(row, 0, QTableWidgetItem(gpu.pci_address))
                table.setItem(row, 1, QTableWidgetItem(gpu.model))
                table.setItem(row, 2, QTableWidgetItem(gpu.driver or "Not available"))
            table.setMinimumHeight(40 + 30 * len(profile.gpus))
            gpu_card.vbox.addWidget(table)
        else:
            gpu_card.vbox.addWidget(_muted("Not available"))
        layout.addWidget(gpu_card)

        firmware_card = Card()
        firmware_card.vbox.addWidget(section_title("Firmware & board"))
        firmware_card.vbox.addLayout(_field("BIOS vendor", profile.bios_vendor))
        firmware_card.vbox.addLayout(_field("BIOS version", profile.bios_version))
        firmware_card.vbox.addLayout(_field("BIOS date", profile.bios_date))
        firmware_card.vbox.addLayout(_field("Board vendor", profile.board_vendor))
        firmware_card.vbox.addLayout(_field("Board name", profile.board_name))
        layout.addWidget(firmware_card)

        artifacts_card = Card()
        artifacts_card.vbox.addWidget(section_title("Crash artifacts"))
        artifacts = report.artifacts
        if artifacts is None:
            artifacts_card.vbox.addWidget(_muted("Not available"))
        else:
            for artifact in artifacts.vmcore_files:
                mtime = _short_time(artifact.mtime)
                label = _ASSOCIATION_LABEL[artifact.association.value]
                artifacts_card.vbox.addWidget(
                    _muted(
                        f"{artifact.path} · {iec_size(artifact.size_bytes)} · {mtime} · {label}"
                    )
                )
            if not artifacts.vmcore_files:
                artifacts_card.vbox.addLayout(_field("vmcore files", "none found"))
            artifacts_card.vbox.addLayout(
                _field("vmcore-dmesg.txt", "present" if artifacts.vmcore_dmesg else "not found")
            )
            artifacts_card.vbox.addLayout(
                _field("pstore records", len(artifacts.pstore_records))
            )
            loaded = artifacts.crash_kernel_loaded
            artifacts_card.vbox.addLayout(
                _field(
                    "Crash kernel loaded",
                    "yes" if loaded else ("no" if loaded is False else "Not available"),
                )
            )
        artifacts_card.vbox.addWidget(_muted("Binary vmcore contents were not analyzed."))
        layout.addWidget(artifacts_card)
        self.results_wrap.show()


class ReportPage(ScrollPage):
    reportSaved = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._report = None
        content, layout = _content_widget()
        layout.addWidget(
            PageHeader(
                "Report", "What can you share? A sanitized, evidence-cited report."
            )
        )
        self.idle_wrap = QWidget()
        idle_layout = QVBoxLayout(self.idle_wrap)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        card.vbox.addWidget(
            EmptyState(
                "file_text",
                "No report yet.",
                "A sanitized Markdown report with bounded excerpts becomes available after "
                "analysis. Preview is always required before export.",
            )
        )
        idle_layout.addWidget(card)
        layout.addWidget(self.idle_wrap)

        self.results_wrap = QWidget()
        results_layout = QVBoxLayout(self.results_wrap)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(12)
        self.readiness = QLabel("")
        self.readiness.setObjectName("muted")
        self.readiness.setWordWrap(True)
        results_layout.addWidget(self.readiness)
        self.redaction_summary = QLabel("")
        self.redaction_summary.setObjectName("redactionSummary")
        results_layout.addWidget(self.redaction_summary)
        self.notice = QLabel(REDACTION_NOTICE)
        self.notice.setObjectName("stateWarning")
        self.notice.setWordWrap(True)
        results_layout.addWidget(self.notice)
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("reportPreview")
        self.preview.setReadOnly(True)
        self.preview.setFont(mono_font())
        self.preview.setMinimumHeight(360)
        results_layout.addWidget(self.preview, 1)
        self.error_label = NoticeBar("", "error")
        results_layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.copy_button = QPushButton("Copy Markdown")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy)
        self.save_button = QPushButton("Save Markdown…")
        self.save_button.setObjectName("analyze")
        self.save_button.setEnabled(False)
        self.save_button.setToolTip("Save the sanitized report (Ctrl+E).")
        self.save_button.clicked.connect(self.save)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.save_button)
        actions.addStretch(1)
        results_layout.addLayout(actions)
        self.results_wrap.hide()
        layout.addWidget(self.results_wrap)
        layout.addStretch(1)
        self.set_content(content)
        self.save_dialog = self._default_save_dialog

    def _default_save_dialog(self, default_name: str) -> str:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Markdown report", default_name, "Markdown (*.md)"
        )
        return path

    def apply_report(self, report, *, hostnames=(), usernames=()) -> None:
        self._report = report
        text, counts = render_report_with_counts(report, hostnames=hostnames, usernames=usernames)
        if report.demo:
            text = "> DEMO DATA — not collected from this machine.\n\n" + text
        self.preview.setPlainText(text)
        self.readiness.setText(
            f"Report covers boot {report.boot.boot_id[:8]} · bounded evidence excerpts · "
            "full logs are not included."
        )
        parts = [f"{kind} ×{counts[kind]}" for kind in _REDACTION_ORDER if counts.get(kind)]
        self.redaction_summary.setText("Redacted: " + (", ".join(parts) if parts else "none"))
        self.error_label.hide()
        self.idle_wrap.hide()
        self.results_wrap.show()
        self.copy_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.preview.toPlainText())

    def save(self) -> None:
        if self._report is None:
            return
        stamp = self._report.generated_at.astimezone(UTC).strftime("%Y%m%d-%H%M%SZ")
        default_name = f"syspanic-report-{self._report.boot.boot_id[:8]}-{stamp}.md"
        path = self.save_dialog(default_name)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.preview.toPlainText())
        except OSError as exc:
            self.error_label.show_message(f"Could not save report: {exc}")
            return
        self.error_label.hide()
        self.reportSaved.emit()
