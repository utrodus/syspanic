from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from syspanic.ui import icons

NAMES = [
    "pulse",
    "dashboard",
    "history",
    "file_search",
    "cpu",
    "file_text",
    "shield_check",
    "search",
]


def _bbox(pm):
    img = pm.toImage()
    w, h = img.width(), img.height()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() > 16:
                minx = min(minx, x)
                maxx = max(maxx, x)
                miny = min(miny, y)
                maxy = max(maxy, y)
    return minx, miny, maxx, maxy


def test_semantic_icons_available():
    for name in ("dashboard", "history", "file_search", "cpu", "file_text", "shield_check"):
        assert name in icons._DRAW


def test_icon_bounds_and_dpr(qapp):
    for name in NAMES:
        for size in (16, 24, 40):
            for scale in (1, 2):
                pm = icons.pixmap(name, "#E7EBF1", size, scale)
                assert pm.devicePixelRatio() == scale
                assert pm.width() == size * scale
                assert round(pm.width() / pm.devicePixelRatio()) == size
                minx, miny, maxx, maxy = _bbox(pm)
                assert maxx >= 0, f"{name} drew nothing"
                w, h = pm.width(), pm.height()
                assert minx >= 1 and miny >= 1, f"{name} clipped at origin"
                assert maxx <= w - 2 and maxy <= h - 2, f"{name} clipped at edge"


def test_nav_icon_has_normal_and_selected(qapp):
    icon = icons.nav_icon("dashboard", "#98A1AF", "#62D8B2")
    assert not icon.isNull()
    assert not icon.pixmap(QSize(24, 24), QIcon.Mode.Normal).isNull()
    assert not icon.pixmap(QSize(24, 24), QIcon.Mode.Selected).isNull()
