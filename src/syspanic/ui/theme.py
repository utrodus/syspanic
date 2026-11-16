"""Design tokens and QSS from docs/03-ui-ux.md §2 (single source for both)."""

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

TOKENS = {
    "bg.canvas": "#101115",
    "bg.sidebar": "#16181E",
    "bg.surface": "#191B22",
    "bg.elevated": "#23262F",
    "bg.nav_selected": "#294238",
    "border.default": "#30343D",
    "text.primary": "#E7EBF1",
    "text.secondary": "#98A1AF",
    "text.disabled": "#5C6470",
    "accent": "#62D8B2",
    "accent.text": "#101115",
    "severity.critical": "#e5484d",
    "severity.warning": "#f5a524",
    "severity.notice": "#6e8efb",
    "severity.info": "#8b949e",
    "state.success": "#46a758",
    "state.error": "#e5484d",
}


def qss() -> str:
    t = TOKENS
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
QLabel#muted {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#emptyHeadline {{ font-size: 16px; font-weight: 600; }}
QLabel#privacy {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#footer {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#sessionHint {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#fieldLabel {{ color: {t['text.secondary']}; font-size: 12px; font-weight: 500; }}
QLabel#emptyCopy {{ color: {t['text.secondary']}; font-size: 14px; }}
QLabel#emptyMeta {{ color: {t['text.secondary']}; font-size: 12px; }}
QLabel#demoBanner {{
    background: {t['bg.elevated']}; color: {t['severity.warning']};
    border: 1px solid {t['border.default']}; border-radius: 8px;
    padding: 8px 12px; font-weight: 600;
}}
QListWidget#nav {{ background: transparent; border: none; outline: none; }}
QListWidget#nav::item {{
    height: 42px; border-radius: 8px; color: {t['text.secondary']}; padding-left: 12px;
}}
QListWidget#nav::item:hover {{ background: {t['bg.elevated']}; color: {t['text.primary']}; }}
QListWidget#nav::item:selected {{ background: {t['bg.nav_selected']}; color: {t['text.primary']}; }}
QListWidget#nav::item:pressed {{ background: {t['bg.nav_selected']}; }}
QListWidget#nav::item:focus {{ border: 1px solid {t['accent']}; }}
QPushButton {{
    background: {t['bg.elevated']}; color: {t['text.primary']};
    border: 1px solid {t['border.default']}; border-radius: 8px;
    min-height: 34px; padding: 0 16px; font-weight: 500;
}}
QPushButton:hover {{ background: #2A2E38; border-color: #3A3F4A; }}
QPushButton:pressed {{ background: {t['bg.surface']}; }}
QPushButton:focus {{ border: 1px solid {t['accent']}; }}
QPushButton:disabled {{
    background: {t['bg.surface']}; color: {t['text.disabled']}; border-color: #262A33;
}}
QPushButton#analyze {{
    background: {t['accent']}; color: {t['accent.text']}; border: none; font-weight: 600;
}}
QPushButton#analyze:hover {{ background: #74E0BF; }}
QPushButton#analyze:disabled {{ background: {t['bg.elevated']}; color: {t['text.disabled']}; }}
QComboBox {{
    background: {t['bg.elevated']}; border: 1px solid {t['border.default']};
    border-radius: 8px; min-height: 34px; padding: 0 12px;
}}
QComboBox:hover {{ border-color: #3A3F4A; }}
QComboBox:focus {{ border: 1px solid {t['accent']}; }}
QComboBox:disabled {{
    background: {t['bg.surface']}; color: {t['text.disabled']}; border-color: #262A33;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {t['bg.elevated']}; border: 1px solid {t['border.default']};
    selection-background-color: {t['bg.nav_selected']}; selection-color: {t['text.primary']};
    outline: none;
}}
QPlainTextEdit {{
    background: {t['bg.surface']}; border: 1px solid {t['border.default']}; border-radius: 8px;
    font-family: "JetBrains Mono", "Noto Sans Mono", monospace; font-size: 13px;
}}
QProgressBar {{
    background: {t['bg.elevated']}; border: 1px solid {t['border.default']};
    border-radius: 6px; max-height: 8px;
}}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 6px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {t['border.default']}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #3A3F4A; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {t['border.default']}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
"""


def apply_theme(app: QApplication) -> None:
    families = QFontDatabase.families()
    family = "Inter" if "Inter" in families else "Noto Sans"
    font = QFont(family)
    font.setPixelSize(14)
    app.setFont(font)
    app.setStyleSheet(qss())
