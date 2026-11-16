"""Local QPainter outline icons (docs/03 §1). No emoji, no remote assets, no new deps.

All glyphs are drawn in a consistent 24x24 coordinate system with a safe stroke margin,
then scaled to the requested logical size and device pixel ratio so nothing clips.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QLabel

from syspanic.ui import theme

_BOX = 24.0
_STROKE = 1.8


def _pulse(p: QPainter) -> None:
    p.drawPolyline(
        QPolygonF(
            [
                QPointF(3, 12),
                QPointF(6, 12),
                QPointF(9, 5),
                QPointF(12, 19),
                QPointF(15, 9),
                QPointF(18, 12),
                QPointF(21, 12),
            ]
        )
    )


def _dashboard(p: QPainter) -> None:
    for x, y in ((3, 3), (14, 3), (3, 14), (14, 14)):
        p.drawRoundedRect(QRectF(x, y, 7, 7), 1.5, 1.5)


def _history(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 8, 8)
    p.drawLine(QPointF(12, 12), QPointF(12, 7))
    p.drawLine(QPointF(12, 12), QPointF(15.5, 13))


def _file_search(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(4, 3, 12, 18), 1.5, 1.5)
    p.drawLine(QPointF(7, 7), QPointF(13, 7))
    p.drawLine(QPointF(7, 10), QPointF(11, 10))
    p.drawEllipse(QPointF(14.5, 14.5), 3.5, 3.5)
    p.drawLine(QPointF(17, 17), QPointF(20.5, 20.5))


def _cpu(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(7, 7, 10, 10), 1.5, 1.5)
    p.drawRoundedRect(QRectF(10, 10, 4, 4), 0.5, 0.5)
    for x in (10, 14):
        p.drawLine(QPointF(x, 7), QPointF(x, 4))
        p.drawLine(QPointF(x, 17), QPointF(x, 20))
    for y in (10, 14):
        p.drawLine(QPointF(7, y), QPointF(4, y))
        p.drawLine(QPointF(17, y), QPointF(20, y))


def _file_text(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(5, 3, 14, 18), 1.5, 1.5)
    p.drawLine(QPointF(8, 8), QPointF(16, 8))
    p.drawLine(QPointF(8, 12), QPointF(16, 12))
    p.drawLine(QPointF(8, 16), QPointF(13, 16))


def _shield_check(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(12, 3)
    path.lineTo(20, 6)
    path.lineTo(20, 11)
    path.cubicTo(20, 16, 16, 20, 12, 21)
    path.cubicTo(8, 20, 4, 16, 4, 11)
    path.lineTo(4, 6)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(9, 12), QPointF(11, 14))
    p.drawLine(QPointF(11, 14), QPointF(15, 9.5))


def _search(p: QPainter) -> None:
    p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
    p.drawLine(QPointF(15.2, 15.2), QPointF(20.5, 20.5))


def _sun(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 4, 4)
    for i in range(8):
        angle = math.radians(i * 45)
        dx, dy = math.cos(angle), math.sin(angle)
        p.drawLine(QPointF(12 + 6 * dx, 12 + 6 * dy), QPointF(12 + 8.5 * dx, 12 + 8.5 * dy))


def _moon(p: QPainter) -> None:
    outer = QPainterPath()
    outer.addEllipse(QRectF(3.5, 3.5, 17, 17))
    bite = QPainterPath()
    bite.addEllipse(QRectF(8, 3.5, 13, 13))
    p.drawPath(outer.subtracted(bite))


_DRAW = {
    "pulse": _pulse,
    "dashboard": _dashboard,
    "history": _history,
    "file_search": _file_search,
    "cpu": _cpu,
    "file_text": _file_text,
    "shield_check": _shield_check,
    "search": _search,
    "sun": _sun,
    "moon": _moon,
}


def pixmap(name: str, color: str, size: int = 24, scale: int = 2) -> QPixmap:
    physical = size * scale
    pm = QPixmap(physical, physical)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(physical / _BOX, physical / _BOX)
    pen = QPen(QColor(color))
    pen.setWidthF(_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _DRAW[name](painter)
    painter.end()
    pm.setDevicePixelRatio(scale)
    return pm


def nav_icon(name: str, normal: str, selected: str) -> QIcon:
    icon = QIcon()
    icon.addPixmap(pixmap(name, normal), QIcon.Mode.Normal)
    icon.addPixmap(pixmap(name, selected), QIcon.Mode.Selected)
    return icon


def set_icon(label: QLabel, name: str, token: str, size: int) -> None:
    label.setProperty("iconName", name)
    label.setProperty("iconToken", token)
    label.setProperty("iconSize", size)
    label.setPixmap(pixmap(name, theme.tokens()[token], size))


def retheme(root) -> None:
    t = theme.tokens()
    for label in root.findChildren(QLabel):
        name = label.property("iconName")
        if name:
            size = label.property("iconSize")
            label.setPixmap(pixmap(name, t[label.property("iconToken")], size))
