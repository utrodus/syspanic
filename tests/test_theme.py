"""Dual-theme (Dark + Soft Light) offscreen tests — T-002 refinement, spec §11.

All settings are isolated: in-memory stores, tmp_path INI files, or subprocesses
with a private XDG_CONFIG_HOME. The user's real preferences are never touched.
"""

import os
import re
import subprocess
import sys

import pytest
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from syspanic.ui import icons
from syspanic.ui.main_window import MainWindow
from syspanic.ui.theme import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    MemorySettings,
    Theme,
    ThemeManager,
    qss,
    tokens,
)

THEME_KEY = "appearance/theme"


@pytest.fixture
def manager(qapp):
    mgr = ThemeManager(qapp, MemorySettings())
    mgr.start()
    yield mgr
    mgr.set_theme(Theme.DARK)


@pytest.fixture
def window(qapp, manager):
    win = MainWindow(demo=False, theme_manager=manager)
    win.show()
    QApplication.processEvents()
    yield win
    win.close()


# --- 1. default and fallback -------------------------------------------------


def test_dark_is_default_when_preference_missing(qapp):
    mgr = ThemeManager(qapp, MemorySettings())
    mgr.start()
    assert mgr.theme is Theme.DARK
    assert tokens()["bg.canvas"] == DARK_TOKENS["bg.canvas"]


@pytest.mark.parametrize("bad", [None, "", "blue", "LIGHT", 42])
def test_invalid_preference_falls_back_to_dark(qapp, bad):
    store = MemorySettings()
    store.setValue(THEME_KEY, bad)
    mgr = ThemeManager(qapp, store)
    mgr.start()
    assert mgr.theme is Theme.DARK


def test_unreadable_preference_falls_back_to_dark(qapp):
    class Unreadable:
        def value(self, key, default=None):
            raise OSError("denied")

    mgr = ThemeManager(qapp, Unreadable())
    mgr.start()
    assert mgr.theme is Theme.DARK


# --- 2/3. applying and repeated switching ------------------------------------


def test_light_theme_applies_palette_and_qss(qapp, manager):
    manager.set_theme(Theme.LIGHT)
    assert manager.theme is Theme.LIGHT
    assert tokens()["bg.canvas"] == LIGHT_TOKENS["bg.canvas"]
    sheet = qapp.styleSheet()
    assert LIGHT_TOKENS["bg.canvas"] in sheet
    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor(LIGHT_TOKENS["bg.canvas"])


def test_repeated_light_dark_light_switching(qapp, manager):
    seen = []
    manager.themeChanged.connect(seen.append)
    for expected in (Theme.LIGHT, Theme.DARK, Theme.LIGHT, Theme.DARK, Theme.LIGHT):
        manager.set_theme(expected)
        assert manager.theme is expected
        t = LIGHT_TOKENS if expected is Theme.LIGHT else DARK_TOKENS
        assert t["bg.canvas"] in qapp.styleSheet()
        assert qapp.palette().color(QPalette.ColorRole.Window) == QColor(t["bg.canvas"])
    assert seen == [Theme.LIGHT, Theme.DARK, Theme.LIGHT, Theme.DARK, Theme.LIGHT]


def test_set_theme_accepts_string_values(manager):
    manager.set_theme("light")
    assert manager.theme is Theme.LIGHT
    manager.set_theme("dark")
    assert manager.theme is Theme.DARK


def test_palette_roles_follow_tokens(qapp, manager):
    for theme in (Theme.LIGHT, Theme.DARK):
        manager.set_theme(theme)
        t = tokens()
        p = qapp.palette()
        assert p.color(QPalette.ColorRole.Window) == QColor(t["bg.canvas"])
        assert p.color(QPalette.ColorRole.WindowText) == QColor(t["text.primary"])
        assert p.color(QPalette.ColorRole.Base) == QColor(t["input.bg"])
        assert p.color(QPalette.ColorRole.Button) == QColor(t["bg.elevated"])
        assert p.color(QPalette.ColorRole.ButtonText) == QColor(t["text.primary"])
        assert p.color(QPalette.ColorRole.ToolTipBase) == QColor(t["tooltip.bg"])
        assert p.color(QPalette.ColorRole.ToolTipText) == QColor(t["tooltip.text"])
        assert p.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText) == QColor(
            t["disabled.fg"]
        )
        assert p.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base) == QColor(
            t["disabled.bg"]
        )


# --- 4. both themes across the five-page shell -------------------------------


def test_stylesheet_applies_to_whole_shell_without_local_overrides(window, manager):
    for theme in (Theme.LIGHT, Theme.DARK):
        manager.set_theme(theme)
        QApplication.processEvents()
        assert window.stack.count() == 5
        for widget in window.findChildren(QWidget):
            assert widget.styleSheet() == "", f"local stylesheet override on {widget!r}"


def test_qss_uses_only_theme_token_colors():
    for theme_tokens in (DARK_TOKENS, LIGHT_TOKENS):
        allowed = {v.lower() for v in theme_tokens.values()}
        found = set(re.findall(r"#[0-9A-Fa-f]{6}", qss(theme_tokens)))
        assert {c.lower() for c in found} <= allowed


def test_opposite_theme_colors_absent():
    assert DARK_TOKENS["bg.canvas"] not in qss(LIGHT_TOKENS)
    assert LIGHT_TOKENS["bg.canvas"] not in qss(DARK_TOKENS)


def test_icon_labels_retheme_in_place(window, manager):
    def opaque_colors(pm):
        img = pm.toImage()
        return {
            img.pixelColor(x, y).name()
            for y in range(img.height())
            for x in range(img.width())
            if img.pixelColor(x, y).alpha() > 128
        }

    logo = window.sidebar.findChild(QLabel, "brandLogo")
    assert logo is not None
    for theme in (Theme.LIGHT, Theme.DARK):
        manager.set_theme(theme)
        t = tokens()
        assert t["accent"].lower() in opaque_colors(logo.pixmap())
        nav_normal = window.nav.item(0).icon().pixmap(window.nav.iconSize(), QIcon.Mode.Normal)
        assert t["text.secondary"].lower() in opaque_colors(nav_normal)


# --- 5/6. navigation and state preservation ----------------------------------


def test_navigation_works_after_theme_switch(window, manager):
    manager.set_theme(Theme.LIGHT)
    for row in range(5):
        window.nav.setCurrentRow(row)
        assert window.stack.currentIndex() == row
    manager.set_theme(Theme.DARK)
    for row in range(4, -1, -1):
        window.nav.setCurrentRow(row)
        assert window.stack.currentIndex() == row


def test_page_and_placeholder_state_preserved_across_switch(window, manager):
    window.nav.setCurrentRow(2)
    page = window.stack.widget(2)
    selector = window.boot_selector
    size = window.size()
    manager.set_theme(Theme.LIGHT)
    manager.set_theme(Theme.DARK)
    assert window.stack.currentIndex() == 2
    assert window.stack.widget(2) is page
    assert window.boot_selector is selector
    assert not window.boot_selector.isEnabled()
    assert not window.analyze_button.isEnabled()
    assert window.boot_selector.currentText() == "Current boot · placeholder"
    assert window.size() == size


def test_repeated_switching_creates_no_duplicates(window, manager):
    buttons = len(window.findChildren(QPushButton))
    labels = len(window.findChildren(QLabel))
    for _ in range(3):
        manager.set_theme(Theme.LIGHT)
        manager.set_theme(Theme.DARK)
    assert window.nav.count() == 5
    assert window.stack.count() == 5
    assert len(window.findChildren(QPushButton)) == buttons
    assert len(window.findChildren(QLabel)) == labels


# --- 7. persistence with isolated settings -----------------------------------


def test_preference_roundtrip_with_isolated_qsettings(qapp, tmp_path):
    path = str(tmp_path / "prefs.ini")
    first = ThemeManager(qapp, QSettings(path, QSettings.Format.IniFormat))
    first.start()
    first.set_theme(Theme.LIGHT)
    second = ThemeManager(qapp, QSettings(path, QSettings.Format.IniFormat))
    second.start()
    assert second.theme is Theme.LIGHT
    second.set_theme(Theme.DARK)
    third = ThemeManager(qapp, QSettings(path, QSettings.Format.IniFormat))
    third.start()
    assert third.theme is Theme.DARK


def test_only_theme_key_is_written(tmp_path):
    path = tmp_path / "prefs.ini"
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    mgr = ThemeManager(QApplication.instance(), settings)
    mgr.start()
    mgr.set_theme(Theme.LIGHT)
    settings.sync()
    assert settings.allKeys() == [THEME_KEY]
    assert settings.value(THEME_KEY) == "light"


def test_corrupt_ini_falls_back_to_dark(qapp, tmp_path):
    path = tmp_path / "prefs.ini"
    path.write_text("[appearance]\ntheme=banana\n", encoding="utf-8")
    mgr = ThemeManager(qapp, QSettings(str(path), QSettings.Format.IniFormat))
    mgr.start()
    assert mgr.theme is Theme.DARK


# --- 8. write failures degrade gracefully ------------------------------------


def test_write_failure_does_not_block_session_switching(qapp):
    class Broken:
        def value(self, key, default=None):
            return None

        def setValue(self, key, value):
            raise OSError("read-only config")

        def sync(self):
            raise OSError("read-only config")

    mgr = ThemeManager(qapp, Broken())
    mgr.start()
    mgr.set_theme(Theme.LIGHT)
    assert mgr.theme is Theme.LIGHT
    assert LIGHT_TOKENS["bg.canvas"] in qapp.styleSheet()
    mgr.set_theme(Theme.DARK)
    assert mgr.theme is Theme.DARK


def test_unwritable_qsettings_location_degrades_gracefully(qapp, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        settings = QSettings(str(locked / "prefs.ini"), QSettings.Format.IniFormat)
        mgr = ThemeManager(qapp, settings)
        mgr.start()
        mgr.set_theme(Theme.LIGHT)
        assert mgr.theme is Theme.LIGHT
        assert LIGHT_TOKENS["bg.canvas"] in qapp.styleSheet()
    finally:
        locked.chmod(0o700)


# --- 9. demo isolation --------------------------------------------------------


def test_demo_window_uses_session_only_settings(qapp):
    win = MainWindow(demo=True)
    try:
        assert isinstance(win.theme_manager.settings, MemorySettings)
        win.theme_manager.set_theme(Theme.LIGHT)
        assert win.theme_manager.theme is Theme.LIGHT
        assert win.theme_manager.settings.value(THEME_KEY) == "light"
    finally:
        win.close()
        win.theme_manager.set_theme(Theme.DARK)


def test_direct_window_construction_never_writes_real_settings(qapp):
    win = MainWindow(demo=False)
    try:
        assert isinstance(win.theme_manager.settings, MemorySettings)
    finally:
        win.close()


# --- token completeness and contrast -----------------------------------------

REQUIRED_KEYS = {
    "bg.canvas",
    "bg.sidebar",
    "bg.surface",
    "bg.elevated",
    "bg.nav_selected",
    "bg.code",
    "border.default",
    "border.hover",
    "text.primary",
    "text.secondary",
    "text.muted",
    "accent",
    "accent.text",
    "accent.hover",
    "accent.pressed",
    "nav_selected_text",
    "nav.hover",
    "control.hover",
    "control.pressed",
    "focus.ring",
    "disabled.fg",
    "disabled.bg",
    "disabled.border",
    "input.bg",
    "input.selection",
    "input.selection_text",
    "scrollbar.track",
    "scrollbar.thumb",
    "scrollbar.thumb_hover",
    "tooltip.bg",
    "tooltip.text",
    "tooltip.border",
    "severity.critical",
    "severity.critical.bg",
    "severity.warning",
    "severity.warning.bg",
    "severity.notice",
    "severity.notice.bg",
    "severity.info",
    "severity.info.bg",
    "state.success",
    "state.success.bg",
    "state.warning",
    "state.warning.bg",
    "state.error",
    "state.error.bg",
}


def test_both_themes_define_identical_complete_token_sets():
    assert set(DARK_TOKENS) == set(LIGHT_TOKENS)
    assert set(DARK_TOKENS) >= REQUIRED_KEYS


def _luminance(hex_color: str) -> float:
    c = QColor(hex_color)
    channels = []
    for v in (c.redF(), c.greenF(), c.blueF()):
        channels.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    a, b = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@pytest.mark.parametrize("theme_tokens", [DARK_TOKENS, LIGHT_TOKENS], ids=["dark", "light"])
def test_text_contrast_meets_wcag_aa(theme_tokens):
    t = theme_tokens
    text_pairs = []
    for bg in ("bg.canvas", "bg.sidebar", "bg.surface", "bg.elevated"):
        text_pairs.append((t["text.primary"], t[bg]))
    for bg in ("bg.canvas", "bg.sidebar", "bg.surface"):
        text_pairs.append((t["text.secondary"], t[bg]))
    for bg in ("bg.canvas", "bg.surface"):
        text_pairs.append((t["text.muted"], t[bg]))
    text_pairs += [
        (t["accent.text"], t["accent"]),
        (t["nav_selected_text"], t["bg.nav_selected"]),
        (t["text.primary"], t["input.bg"]),
        (t["input.selection_text"], t["input.selection"]),
        (t["tooltip.text"], t["tooltip.bg"]),
    ]
    for name in ("critical", "warning", "notice", "info"):
        text_pairs.append((t[f"severity.{name}"], t[f"severity.{name}.bg"]))
    for name in ("success", "warning", "error"):
        text_pairs.append((t[f"state.{name}"], t[f"state.{name}.bg"]))
    for fg, bg in text_pairs:
        ratio = _contrast(fg, bg)
        assert ratio >= 4.5, f"{fg} on {bg}: {ratio:.2f} < 4.5"


@pytest.mark.parametrize("theme_tokens", [DARK_TOKENS, LIGHT_TOKENS], ids=["dark", "light"])
def test_accent_and_focus_contrast_meets_non_text_aa(theme_tokens):
    t = theme_tokens
    for bg in ("bg.canvas", "bg.surface", "bg.sidebar"):
        assert _contrast(t["accent"], t[bg]) >= 3.0
        assert _contrast(t["focus.ring"], t[bg]) >= 3.0


def test_dark_palette_preserves_approved_values():
    approved = {
        "bg.canvas": "#101115",
        "bg.sidebar": "#16181E",
        "bg.surface": "#191B22",
        "bg.elevated": "#23262F",
        "bg.nav_selected": "#294238",
        "border.default": "#30343D",
        "text.primary": "#E7EBF1",
        "text.secondary": "#98A1AF",
        "accent": "#62D8B2",
        "accent.text": "#101115",
    }
    for key, value in approved.items():
        assert DARK_TOKENS[key] == value


def test_light_core_matches_spec_table():
    spec = {
        "bg.canvas": "#F3F4F2",
        "bg.sidebar": "#E9ECE9",
        "bg.surface": "#FAFBF9",
        "bg.elevated": "#F0F3EF",
        "border.default": "#D9DFDA",
        "text.primary": "#26332E",
        "accent.text": "#FFFFFF",
        "bg.nav_selected": "#D8EAE2",
    }
    for key, value in spec.items():
        assert LIGHT_TOKENS[key] == value


# --- theme switcher -----------------------------------------------------------


def test_switcher_has_two_keyboard_accessible_choices(window):
    switch = window.theme_switch
    light, dark = switch.light_button, switch.dark_button
    assert light.text() == "Light"
    assert dark.text() == "Dark"
    for button in (light, dark):
        assert button.isCheckable()
        assert button.autoExclusive()
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
        assert button.toolTip()
        assert button.accessibleName()
        assert not button.icon().isNull()


def test_switcher_active_state_follows_theme(window, manager):
    assert window.theme_switch.dark_button.isChecked()
    manager.set_theme(Theme.LIGHT)
    assert window.theme_switch.light_button.isChecked()
    assert not window.theme_switch.dark_button.isChecked()
    manager.set_theme(Theme.DARK)
    assert window.theme_switch.dark_button.isChecked()


def test_switcher_click_applies_theme_immediately(window, manager):
    window.theme_switch.light_button.click()
    assert manager.theme is Theme.LIGHT
    assert LIGHT_TOKENS["bg.canvas"] in QApplication.instance().styleSheet()
    window.theme_switch.dark_button.click()
    assert manager.theme is Theme.DARK


def test_switcher_keyboard_space_activates(window, manager):
    button = window.theme_switch.light_button
    button.setFocus()
    for event_type in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(
            button, QKeyEvent(event_type, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        )
    QApplication.processEvents()
    assert manager.theme is Theme.LIGHT


def test_switcher_lives_above_privacy_indicator(window):
    layout = window.sidebar.layout()
    assert layout.indexOf(window.theme_switch) >= 0
    assert window.theme_switch.y() < window.privacy.y()


# --- sun/moon icons -----------------------------------------------------------


def test_sun_and_moon_icons_exist_and_draw(qapp):
    for name in ("sun", "moon"):
        assert name in icons._DRAW
        pm = icons.pixmap(name, "#26332E", 24, 2)
        img = pm.toImage()
        opaque = any(
            img.pixelColor(x, y).alpha() > 16
            for y in range(img.height())
            for x in range(img.width())
        )
        assert opaque, f"{name} drew nothing"


# --- E2E: real entry point with isolated config -------------------------------

THEME_DRIVER = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

real_exec = QApplication.exec

def exec_and_verify(self):
    win = [w for w in self.topLevelWidgets() if w.isVisible()][0]
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "switch-light":
        win.theme_switch.light_button.click()
        assert win.theme_manager.theme.value == "light"
    elif mode == "expect-light":
        assert win.theme_manager.theme.value == "light", "saved theme not restored"
    elif mode == "expect-dark":
        assert win.theme_manager.theme.value == "dark"
    print("THEME_OK", mode, win.theme_manager.theme.value, flush=True)
    QTimer.singleShot(0, self.quit)
    return real_exec()

QApplication.exec = exec_and_verify

from syspanic.app import main

sys.exit(main(sys.argv[2:]))
"""


def run_theme_app(cfg_dir: str, mode: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = "src"
    env["XDG_CONFIG_HOME"] = cfg_dir
    return subprocess.run(
        [sys.executable, "-c", THEME_DRIVER, mode, *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )


def test_e2e_theme_persists_across_restart(tmp_path):
    cfg = str(tmp_path / "config")
    first = run_theme_app(cfg, "switch-light")
    assert first.returncode == 0, first.stderr
    assert "THEME_OK switch-light light" in first.stdout
    conf = tmp_path / "config" / "SysPanic" / "SysPanic.conf"
    assert conf.exists()
    assert "light" in conf.read_text(encoding="utf-8")
    second = run_theme_app(cfg, "expect-light")
    assert second.returncode == 0, second.stderr
    assert "THEME_OK expect-light light" in second.stdout


def test_e2e_demo_never_writes_real_preferences(tmp_path):
    cfg = str(tmp_path / "config")
    result = run_theme_app(cfg, "switch-light", "--demo")
    assert result.returncode == 0, result.stderr
    assert "THEME_OK switch-light light" in result.stdout
    assert not (tmp_path / "config" / "SysPanic").exists()


def test_e2e_missing_preference_starts_dark(tmp_path):
    result = run_theme_app(str(tmp_path / "config"), "expect-dark")
    assert result.returncode == 0, result.stderr
    assert "THEME_OK expect-dark dark" in result.stdout
