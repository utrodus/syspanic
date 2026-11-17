"""Qt table models for the Timeline page (docs/03 §5.2). No diagnostics logic."""

from PySide6.QtCore import QAbstractTableModel, Qt

from syspanic.domain.models import TimelineEvent

_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
_HEADERS = ("Time", "Event", "Severity", "Evidence")


def format_time(ts) -> str:
    local = ts.astimezone()
    return (
        f"{local.day:02d} {_MONTHS[local.month - 1]} "
        f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}"
    )


class TimelineModel(QAbstractTableModel):
    def __init__(self, events: tuple[TimelineEvent, ...], parent=None):
        super().__init__(parent)
        self._events = tuple(events)
        self._visible = self._events

    def rowCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._visible)

    def columnCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(_HEADERS)

    def event_at(self, row: int) -> TimelineEvent:
        return self._visible[row]

    def set_filter(self, severities) -> None:
        self.beginResetModel()
        if severities:
            self._visible = tuple(e for e in self._events if e.severity in severities)
        else:
            self._visible = self._events
        self.endResetModel()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        event = self._visible[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return format_time(event.timestamp)
            if column == 1:
                return event.summary
            if column == 2:
                return event.severity.value.capitalize()
            return event.evidence_id
        if role == Qt.ItemDataRole.ToolTipRole and column == 0:
            return event.timestamp.astimezone().isoformat()
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return _HEADERS[section]
        return None
