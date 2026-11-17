"""Dual-theme design tokens, QSS, palette, and theme manager (docs/03 §2).

One shared stylesheet structure; theme-specific token values. The only persisted
preference is `appearance/theme` (light|dark) via QSettings; demo mode and tests
use session-only stores so real user preferences are never touched.
"""

from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

THEME_KEY = "appearance/theme"


class Theme(Enum):
    DARK = "dark"
    LIGHT = "light"


DARK_TOKENS = {
    "bg.canvas": "#101115",
    "bg.sidebar": "#16181E",
    "bg.surface": "#191B22",
    "bg.elevated": "#23262F",
    "bg.nav_selected": "#294238",
    "bg.code": "#14161B",
    "border.default": "#30343D",
    "border.hover": "#3A3F4A",
    "text.primary": "#E7EBF1",
    "text.secondary": "#98A1AF",
    "text.muted": "#8A93A4",
    "accent": "#62D8B2",
    "accent.text": "#101115",
    "accent.hover": "#74E0BF",
    "accent.pressed": "#52C9A2",
    "nav_selected_text": "#62D8B2",
    "nav.hover": "#23262F",
    "control.hover": "#2A2E38",
    "control.pressed": "#191B22",
    "focus.ring": "#62D8B2",
    "disabled.fg": "#5C6470",
    "disabled.bg": "#191B22",
    "disabled.border": "#262A33",
    "input.bg": "#23262F",
    "input.selection": "#294238",
    "input.selection_text": "#E7EBF1",
    "evidence.highlight": "#E3D08A",
    "evidence.highlight_text": "#2B2410",
    "scrollbar.track": "transparent",
    "scrollbar.thumb": "#30343D",
    "scrollbar.thumb_hover": "#3A3F4A",
    "tooltip.bg": "#23262F",
    "tooltip.text": "#E7EBF1",
    "tooltip.border": "#30343D",
    "severity.critical": "#e5484d",
    "severity.critical.bg": "#261216",
    "severity.warning": "#f5a524",
    "severity.warning.bg": "#3A2E14",
    "severity.notice": "#6e8efb",
    "severity.notice.bg": "#232A44",
    "severity.info": "#8b949e",
    "severity.info.bg": "#262A33",
    "state.success": "#46a758",
    "state.success.bg": "#16281B",
    "state.warning": "#f5a524",
    "state.warning.bg": "#3A2E14",
    "state.error": "#e5484d",
    "state.error.bg": "#261216",
}

LIGHT_TOKENS = {
    "bg.canvas": "#F3F4F2",
    "bg.sidebar": "#E9ECE9",
    "bg.surface": "#FAFBF9",
    "bg.elevated": "#F0F3EF",
    "bg.nav_selected": "#D8EAE2",
    "bg.code": "#F0F3EF",
    "border.default": "#D9DFDA",
    "border.hover": "#B9C4BB",
    "text.primary": "#26332E",
    "text.secondary": "#55645C",
    "text.muted": "#5F6E65",
    "accent": "#237A62",
    "accent.text": "#FFFFFF",
    "accent.hover": "#1C6A54",
    "accent.pressed": "#175A47",
    "nav_selected_text": "#1B6B55",
    "nav.hover": "#DEE4DD",
    "control.hover": "#E4E9E3",
    "control.pressed": "#DCE2DB",
    "focus.ring": "#237A62",
    "disabled.fg": "#9AA69D",
    "disabled.bg": "#F0F3EF",
    "disabled.border": "#E2E7E1",
    "input.bg": "#F0F3EF",
    "input.selection": "#D8EAE2",
    "input.selection_text": "#26332E",
    "evidence.highlight": "#F4E6A2",
    "evidence.highlight_text": "#33290D",
    "scrollbar.track": "transparent",
    "scrollbar.thumb": "#B4BFB5",
    "scrollbar.thumb_hover": "#97A69B",
    "tooltip.bg": "#FAFBF9",
    "tooltip.text": "#26332E",
    "tooltip.border": "#D9DFDA",
    "severity.critical": "#B3261E",
    "severity.critical.bg": "#F7E4E2",
    "severity.warning": "#8A5D00",
    "severity.warning.bg": "#F6ECD4",
    "severity.notice": "#3D5A99",
    "severity.notice.bg": "#E3E9F7",
    "severity.info": "#566159",
    "severity.info.bg": "#E9ECE9",
    "state.success": "#1B7230",
    "state.success.bg": "#E1F0E4",
    "state.warning": "#8A5D00",
    "state.warning.bg": "#F6ECD4",
    "state.error": "#B3261E",
    "state.error.bg": "#F7E4E2",
}

_TOKENS_BY_THEME = {Theme.DARK: DARK_TOKENS, Theme.LIGHT: LIGHT_TOKENS}
_current = Theme.DARK


def current_theme() -> Theme:
    return _current


def tokens() -> dict:
    return _TOKENS_BY_THEME[_current]


def qss(t: dict) -> str:
    return f"""
QWidget {{ background: transparent; color: {t['text.primary']}; font-size: 14px; }}
QMainWindow, QWidget#canvas {{ background: {t['bg.canvas']}; }}
QWidget#sidebar {{ background: {t['bg.sidebar']}; border-right: 1px solid {t['border.default']}; }}
QFrame#card {{
    background: {t['bg.surface']}; border: 1px solid {t['border.default']}; border-radius: 12px;
}}
QFrame#footerBar {{
    background: {t['bg.sidebar']}; border-top: 1px solid {t['border.default']};
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QLabel#pageHeading {{ font-size: 27px; font-weight: 600; }}
QLabel#pageSubtitle {{ color: {t['text.secondary']}; font-size: 14px; }}
QLabel#sectionTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#brand {{ font-size: 16px; font-weight: 600; }}
QLabel#sectionLabel {{ color: {t['text.secondary']}; font-size: 11px; font-weight: 600; }}
QLabel#tagline {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#muted {{ color: {t['text.muted']}; font-size: 12px; }}
QLabel#emptyHeadline {{ font-size: 16px; font-weight: 600; }}
QLabel#privacy {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#footer {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#sessionHint {{ color: {t['text.muted']}; font-size: 12px; }}
QLabel#fieldLabel {{ color: {t['text.secondary']}; font-size: 12px; font-weight: 500; }}
QLabel#emptyCopy {{ color: {t['text.secondary']}; font-size: 14px; }}
QLabel#emptyMeta {{ color: {t['text.muted']}; font-size: 12px; }}
QLabel#demoBanner {{
    background: {t['bg.elevated']}; color: {t['state.warning']};
    border: 1px solid {t['border.default']}; border-radius: 8px;
    padding: 8px 12px; font-weight: 600;
}}
QLabel#severityCritical, QLabel#severityWarning, QLabel#severityNotice, QLabel#severityInfo,
QLabel#stateSuccess, QLabel#stateWarning, QLabel#stateError, QLabel#chip {{
    border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}}
QLabel#severityCritical {{
    background: {t['severity.critical.bg']}; color: {t['severity.critical']};
}}
QLabel#severityWarning {{
    background: {t['severity.warning.bg']}; color: {t['severity.warning']};
}}
QLabel#severityNotice {{
    background: {t['severity.notice.bg']}; color: {t['severity.notice']};
}}
QLabel#severityInfo {{
    background: {t['severity.info.bg']}; color: {t['severity.info']};
}}
QLabel#stateSuccess {{ background: {t['state.success.bg']}; color: {t['state.success']}; }}
QLabel#stateWarning {{ background: {t['state.warning.bg']}; color: {t['state.warning']}; }}
QLabel#stateError {{ background: {t['state.error.bg']}; color: {t['state.error']}; }}
QLabel#chip {{
    background: {t['bg.elevated']}; color: {t['text.secondary']};
    border: 1px solid {t['border.default']};
}}
QLabel#countCritical, QLabel#countWarning, QLabel#countNotice, QLabel#countInfo {{
    font-size: 24px; font-weight: 600;
}}
QLabel[zero="true"] {{ color: {t['text.muted']}; }}
QLabel#coverageStrip {{ font-weight: 600; }}
QLabel#deniedPanel {{
    background: {t['bg.elevated']}; color: {t['text.secondary']};
    border: 1px solid {t['border.default']}; border-radius: 8px; padding: 10px 12px;
}}
QLabel#excerpt {{
    background: {t['bg.code']}; border: 1px solid {t['border.default']};
    border-radius: 6px; padding: 6px 8px;
}}
QPushButton#chip {{ min-height: 28px; padding: 0 10px; }}
QListWidget#nav {{ background: transparent; border: none; outline: none; }}
QListWidget#nav::item {{
    height: 42px; border-radius: 8px; color: {t['text.secondary']}; padding-left: 12px;
}}
QListWidget#nav::item:hover {{ background: {t['nav.hover']}; color: {t['text.primary']}; }}
QListWidget#nav::item:selected {{
    background: {t['bg.nav_selected']}; color: {t['nav_selected_text']};
}}
QListWidget#nav::item:pressed {{ background: {t['bg.nav_selected']}; }}
QListWidget#nav::item:focus {{ border: 1px solid {t['focus.ring']}; }}
QFrame#themeSwitch {{
    background: {t['bg.surface']}; border: 1px solid {t['border.default']}; border-radius: 8px;
}}
QPushButton#themeOption {{
    background: transparent; border: none; border-radius: 6px;
    min-height: 34px; padding: 0 8px; color: {t['text.secondary']}; font-weight: 500;
}}
QPushButton#themeOption:hover {{ background: {t['nav.hover']}; color: {t['text.primary']}; }}
QPushButton#themeOption:checked {{
    background: {t['bg.nav_selected']}; color: {t['nav_selected_text']};
}}
QPushButton#themeOption:focus {{ border: 1px solid {t['focus.ring']}; }}
QPushButton {{
    background: {t['bg.elevated']}; color: {t['text.primary']};
    border: 1px solid {t['border.default']}; border-radius: 8px;
    min-height: 34px; padding: 0 16px; font-weight: 500;
}}
QPushButton:hover {{ background: {t['control.hover']}; border-color: {t['border.hover']}; }}
QPushButton:pressed {{ background: {t['control.pressed']}; }}
QPushButton:focus {{ border: 1px solid {t['focus.ring']}; }}
QPushButton:disabled {{
    background: {t['disabled.bg']}; color: {t['disabled.fg']}; border-color: {t['disabled.border']};
}}
QPushButton#analyze {{
    background: {t['accent']}; color: {t['accent.text']}; border: none; font-weight: 600;
}}
QPushButton#analyze:hover {{ background: {t['accent.hover']}; }}
QPushButton#analyze:pressed {{ background: {t['accent.pressed']}; }}
QPushButton#analyze:disabled {{ background: {t['disabled.bg']}; color: {t['disabled.fg']}; }}
QComboBox {{
    background: {t['input.bg']}; color: {t['text.primary']};
    border: 1px solid {t['border.default']}; border-radius: 8px; min-height: 34px; padding: 0 12px;
}}
QComboBox:hover {{ border-color: {t['border.hover']}; }}
QComboBox:focus {{ border: 1px solid {t['focus.ring']}; }}
QComboBox:disabled {{
    background: {t['disabled.bg']}; color: {t['disabled.fg']}; border-color: {t['disabled.border']};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {t['bg.elevated']}; border: 1px solid {t['border.default']};
    selection-background-color: {t['input.selection']};
    selection-color: {t['input.selection_text']};
    outline: none;
}}
QLineEdit {{
    background: {t['input.bg']}; color: {t['text.primary']};
    border: 1px solid {t['border.default']}; border-radius: 8px; min-height: 34px; padding: 0 12px;
    selection-background-color: {t['input.selection']};
    selection-color: {t['input.selection_text']};
}}
QLineEdit:focus {{ border: 1px solid {t['focus.ring']}; }}
QLineEdit:disabled {{
    background: {t['disabled.bg']}; color: {t['disabled.fg']}; border-color: {t['disabled.border']};
}}
QPlainTextEdit, QTextEdit {{
    background: {t['bg.code']}; color: {t['text.primary']};
    border: 1px solid {t['border.default']}; border-radius: 8px;
    font-family: "JetBrains Mono", "Noto Sans Mono", monospace; font-size: 13px;
    selection-background-color: {t['input.selection']};
    selection-color: {t['input.selection_text']};
}}
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {t['focus.ring']}; }}
QTableView {{
    background: {t['bg.surface']}; alternate-background-color: {t['bg.elevated']};
    gridline-color: {t['border.default']}; color: {t['text.primary']};
    border: 1px solid {t['border.default']}; border-radius: 8px;
    selection-background-color: {t['input.selection']};
    selection-color: {t['input.selection_text']};
}}
QHeaderView::section {{
    background: {t['bg.elevated']}; color: {t['text.secondary']};
    border: none; border-bottom: 1px solid {t['border.default']};
    padding: 6px 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {t['bg.elevated']}; border: none; }}
QToolTip {{
    background: {t['tooltip.bg']}; color: {t['tooltip.text']};
    border: 1px solid {t['tooltip.border']}; border-radius: 6px; padding: 6px 8px; font-size: 12px;
}}
QProgressBar {{
    background: {t['bg.elevated']}; border: 1px solid {t['border.default']};
    border-radius: 6px; max-height: 8px;
}}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 6px; }}
QScrollBar:vertical {{ background: {t['scrollbar.track']}; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {t['scrollbar.thumb']}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {t['scrollbar.thumb_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: {t['scrollbar.track']};
}}
QScrollBar:horizontal {{ background: {t['scrollbar.track']}; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {t['scrollbar.thumb']}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t['scrollbar.thumb_hover']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: {t['scrollbar.track']};
}}
"""


def palette(t: dict) -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg.canvas"],
        QPalette.ColorRole.WindowText: t["text.primary"],
        QPalette.ColorRole.Base: t["input.bg"],
        QPalette.ColorRole.AlternateBase: t["bg.elevated"],
        QPalette.ColorRole.Text: t["text.primary"],
        QPalette.ColorRole.Button: t["bg.elevated"],
        QPalette.ColorRole.ButtonText: t["text.primary"],
        QPalette.ColorRole.Highlight: t["bg.nav_selected"],
        QPalette.ColorRole.HighlightedText: t["nav_selected_text"],
        QPalette.ColorRole.ToolTipBase: t["tooltip.bg"],
        QPalette.ColorRole.ToolTipText: t["tooltip.text"],
        QPalette.ColorRole.PlaceholderText: t["text.muted"],
        QPalette.ColorRole.Link: t["accent"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.HighlightedText,
        QPalette.ColorRole.PlaceholderText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["disabled.fg"]))
    for role in (
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.Highlight,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["disabled.bg"]))
    return p


def apply_theme(app: QApplication, theme: Theme = Theme.DARK) -> None:
    global _current
    _current = Theme(theme)
    t = tokens()
    families = QFontDatabase.families()
    family = "Inter" if "Inter" in families else "Noto Sans"
    font = QFont(family)
    font.setPixelSize(14)
    app.setFont(font)
    app.setPalette(palette(t))
    app.setStyleSheet(qss(t))


class MemorySettings:
    """Session-only settings store: demo mode and tests never write real preferences."""

    def __init__(self):
        self._data = {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value

    def sync(self):
        pass


class ThemeManager(QObject):
    themeChanged = Signal(object)

    def __init__(self, app: QApplication, settings=None, parent=None):
        super().__init__(parent)
        self._app = app
        self._settings = settings if settings is not None else MemorySettings()
        self._theme = Theme.DARK

    @property
    def theme(self) -> Theme:
        return self._theme

    @property
    def settings(self):
        return self._settings

    def start(self) -> None:
        self._theme = self._load()
        apply_theme(self._app, self._theme)
        self.themeChanged.emit(self._theme)

    def set_theme(self, theme, *, persist: bool = True) -> None:
        theme = Theme(theme)
        if theme == self._theme:
            return
        self._theme = theme
        apply_theme(self._app, theme)
        if persist:
            self._save(theme)
        self.themeChanged.emit(theme)

    def _load(self) -> Theme:
        try:
            raw = self._settings.value(THEME_KEY)
        except Exception:
            return Theme.DARK
        try:
            return Theme(raw)
        except (ValueError, TypeError):
            return Theme.DARK

    def _save(self, theme: Theme) -> None:
        try:
            self._settings.setValue(THEME_KEY, theme.value)
            self._settings.sync()
        except Exception:
            # Persistence is best-effort; a write failure must not block switching.
            pass
