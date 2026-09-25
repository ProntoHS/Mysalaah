"""The opening logo animation, drawn frame by frame with QPainter.

It follows the original Logo.gif, step for step, but moves smoothly between the steps:

    0.0  the boy on his mat fades up
    0.7  a circle is drawn above him, stroke by stroke
    1.5  it floods with black from the middle
    1.95 hands pressed together appear in it
    2.8  they open, into dua
    3.3  "My" is written in, then "Saalah"
    5.05 "www." and ".com"
    5.8  the hands press together once more and open again, as the old GIF did
    7.2  done: the app then fades through white to the main screen

The pieces come from assets/splash (built by tools/build_splash.py). The circle is drawn here
rather than taken from a picture, so it is perfectly round at any size. Drawing it this way,
rather than playing a video, means no video player is needed on the Pi and the logo is sharp on
any screen.
"""
from __future__ import annotations

import json
from pathlib import Path

from .qt import QtCore, QtGui, Qt

DESIGN_WIDTH = 1813     # a 16:9 frame the height of the original GIF


def ease(x: float) -> float:
    """Slow in, slow out."""
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def span(t: float, start: float, end: float) -> float:
    """How far through [start, end] the time [t] is, from 0 to 1."""
    if end <= start:
        return 1.0 if t >= end else 0.0
    return min(1.0, max(0.0, (t - start) / (end - start)))


class Splash:
    DURATION = 7.2

    # when each thing happens, in seconds
    BOY = (0.0, 0.7)
    OUTLINE = (0.7, 1.5)
    FLOOD = (1.5, 1.95)
    MY = (3.3, 3.85)
    SAALAH = (3.85, 5.0)
    ADDRESS = (5.05, 5.45)
    NEVER = (99.0, 99.0)
    # each pair of hands: when it fades up, and when it fades away again
    HANDS = (
        ("hands_pressed", [((1.95, 2.45), (2.8, 3.02)), ((5.95, 6.15), (6.35, 6.55))]),
        ("hands_open", [((2.98, 3.3), (5.8, 6.0)), ((6.5, 6.75), NEVER)]),
    )

    def __init__(self, assets: Path):
        folder = assets / "splash"
        described = json.loads((folder / "splash.json").read_text(encoding="utf-8"))
        self.design_height = float(described["design_height"])
        c = described["circle"]
        self.circle = (float(c["x"]), float(c["y"]), float(c["r"]))
        self.layers: dict[str, tuple[QtGui.QImage, QtCore.QRectF]] = {}
        for name, layer in described["layers"].items():
            image = QtGui.QImage(str(folder / layer["file"]))
            box = QtCore.QRectF(layer["x"], layer["y"], layer["w"], layer["h"])
            self.layers[name] = (image, box)

    @staticmethod
    def available(assets: Path) -> bool:
        return (assets / "splash" / "splash.json").is_file()

    # -- drawing ------------------------------------------------------------------------------

    def paint(self, p: QtGui.QPainter, rect: QtCore.QRectF, t: float) -> None:
        """Draws the animation as it is [t] seconds in, filling [rect]."""
        p.save()
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(rect, QtGui.QColor("white"))

        # Fit the design into the rect, centred, whatever shape the screen is.
        scale = min(rect.height() / self.design_height, rect.width() / DESIGN_WIDTH)
        p.translate(rect.center().x(), rect.center().y() - self.design_height * scale / 2)
        p.scale(scale, scale)

        # the boy, rising a little as he fades up
        k = ease(span(t, *self.BOY))
        if k > 0:
            p.save()
            p.translate(0, (1 - k) * 22)
            self._layer(p, "boy", k)
            p.restore()

        cx, cy, r = self.circle
        # the circle, drawn round from the top
        drawn = ease(span(t, *self.OUTLINE))
        flood = ease_out(span(t, *self.FLOOD))
        if drawn > 0 and flood < 1:
            pen = QtGui.QPen(QtGui.QColor("black"))
            pen.setWidthF(4.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            box = QtCore.QRectF(cx - r + 2, cy - r + 2, 2 * r - 4, 2 * r - 4)
            p.drawArc(box, 90 * 16, -int(360 * 16 * drawn))
        if flood > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor("black"))
            grow = r * flood
            p.drawEllipse(QtCore.QPointF(cx, cy), grow, grow)

        # the hands: pressed together, then open; and once more at the end. One pair fades
        # most of the way out before the next comes in, so the two are never muddled together.
        for name, shown in self.HANDS:
            opacity = 0.0
            for start, end in shown:
                opacity += self._dip(t, start, end)
            if opacity > 0:
                first = name == "hands_pressed" and t < shown[0][1][0]
                grow = 0.92 + 0.08 * ease(span(t, *shown[0][0])) if first else 1.0
                self._hands(p, name, opacity, grow)

        # the name, written in from the left
        self._wiped(p, "my", ease(span(t, *self.MY)))
        self._wiped(p, "saalah", span(t, *self.SAALAH))
        address = ease(span(t, *self.ADDRESS))
        if address > 0:
            self._layer(p, "www", address)
            self._layer(p, "com", address)
        p.restore()

    def _layer(self, p: QtGui.QPainter, name: str, opacity: float) -> None:
        if name not in self.layers or opacity <= 0:
            return
        image, box = self.layers[name]
        p.setOpacity(min(1.0, opacity))
        p.drawImage(box, image)
        p.setOpacity(1.0)

    @staticmethod
    def _dip(t: float, fade_in: tuple[float, float], fade_out: tuple[float, float]) -> float:
        """Opacity of something that fades up over [fade_in] and away over [fade_out]."""
        return ease(span(t, *fade_in)) * (1 - ease(span(t, *fade_out)))

    def _hands(self, p: QtGui.QPainter, name: str, opacity: float, size: float) -> None:
        """The hands come up slightly small and settle to size the first time they appear."""
        cx, cy, _ = self.circle
        p.save()
        p.translate(cx, cy)
        p.scale(size, size)
        p.translate(-cx, -cy)
        self._layer(p, name, opacity)
        p.restore()

    def _wiped(self, p: QtGui.QPainter, name: str, progress: float) -> None:
        """Reveals a word from left to right with a soft leading edge, like ink going on."""
        if name not in self.layers or progress <= 0:
            return
        image, box = self.layers[name]
        if progress >= 1:
            p.drawImage(box, image)
            return
        soft = 0.12                                   # the soft edge, as a share of the word
        reach = progress * (1 + soft)
        masked = QtGui.QImage(image.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        masked.fill(Qt.GlobalColor.transparent)
        mp = QtGui.QPainter(masked)
        mp.drawImage(0, 0, image)
        mp.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_DestinationIn)
        w = image.width()
        fade = QtGui.QLinearGradient(w * (reach - soft), 0, w * reach, 0)
        fade.setColorAt(0, QtGui.QColor(0, 0, 0, 255))
        fade.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        mp.fillRect(masked.rect(), QtGui.QBrush(fade))
        mp.end()
        p.drawImage(box, masked)
