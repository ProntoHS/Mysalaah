"""The Qibla screen shown at start-up, before the main screen.

A compass dial turns as the display is turned. The pointer at the top is the way the mat faces;
the Kaaba sits on the rim in its true direction. Turn until the Kaaba is under the pointer: the
band at the top turns green, and after a moment the main screen comes up by itself. A press of
the ring, or a touch, always goes straight on, so a compass upset by a radiator never keeps
anyone from praying.

With no compass fitted, the dial is drawn with north at the top and the Kaaba at its bearing,
with the number to line up against a phone compass.
"""
from __future__ import annotations

import math
import time

from .qibla import IN_LINE, Facing, compass_point, turn_needed
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

GREEN = QtGui.QColor("#2E8B57")
GOLD = QtGui.QColor("#C9A227")
HOLD = 2.0          # seconds lined up before moving on by itself


class Dial(QtWidgets.QWidget):
    """The compass itself: a rose that turns with the display, a fixed pointer at the top,
    the Kaaba on the rim."""

    def __init__(self, family: str = ""):
        super().__init__()
        self.family = family
        self.heading: float | None = None      # which way the display faces
        self.qibla = 0.0
        self.aligned = False
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def show_state(self, heading: float | None, qibla: float, aligned: bool) -> None:
        self.heading, self.qibla, self.aligned = heading, qibla, aligned
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        colours = palette()
        INK, PAPER = QtGui.QColor(colours.ink), QtGui.QColor(colours.paper)
        FAINT = QtGui.QColor(colours.faint)
        side = min(self.width(), self.height())
        # Upright on the 7" screen the dial is held back by the width, so it takes more of it.
        r = side * (0.44 if self.height() > self.width() * 1.2 else 0.40)
        cx, cy = self.width() / 2, self.height() / 2 + side * 0.03
        facing = self.heading if self.heading is not None else 0.0   # no compass: north up

        # The band at the top: where the Kaaba must be. Green once it is there.
        band = QtGui.QPen(GREEN if self.aligned else FAINT)
        band.setWidthF(r * 0.10)
        band.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(band)
        box = QtCore.QRectF(cx - r * 1.08, cy - r * 1.08, r * 2.16, r * 2.16)
        p.drawArc(box, int((90 - IN_LINE) * 16), int(2 * IN_LINE * 16))

        # The dial's face, and its ring
        ring = QtGui.QPen(GREEN if self.aligned else INK)
        ring.setWidthF(max(2.0, r * 0.03))
        p.setPen(ring)
        p.setBrush(PAPER)
        p.drawEllipse(QtCore.QPointF(cx, cy), r, r)

        # Ticks and letters, turned so that the top of the screen is the way the display faces
        p.save()
        p.translate(cx, cy)
        p.rotate(-facing)
        for deg in range(0, 360, 10):
            p.save()
            p.rotate(deg)
            pen = QtGui.QPen(INK)
            pen.setWidthF(max(1.0, r * (0.018 if deg % 90 == 0 else 0.008)))
            p.setPen(pen)
            length = r * (0.14 if deg % 90 == 0 else 0.08 if deg % 30 == 0 else 0.04)
            p.drawLine(QtCore.QPointF(0, -r), QtCore.QPointF(0, -r + length))
            p.restore()
        font = QtGui.QFont(self.family) if self.family else p.font()
        font.setPixelSize(max(10, int(r * 0.16)))
        font.setWeight(QtGui.QFont.Weight(700))
        p.setFont(font)
        for deg, letter in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            angle = math.radians(deg)
            x, y = math.sin(angle) * r * 0.72, -math.cos(angle) * r * 0.72
            p.save()
            p.translate(x, y)
            p.rotate(facing)                           # letters stay upright
            p.setPen(QtGui.QColor(colours.highlight) if letter == "N" else INK)
            p.drawText(QtCore.QRectF(-r * 0.2, -r * 0.12, r * 0.4, r * 0.24),
                       int(Qt.AlignmentFlag.AlignCenter), letter)
            p.restore()

        # The line to the Kaaba, and the Kaaba on the rim
        angle = math.radians(self.qibla)
        tip = QtCore.QPointF(math.sin(angle) * r * 0.80, -math.cos(angle) * r * 0.80)
        line = QtGui.QPen(GREEN if self.aligned else INK)
        line.setWidthF(max(2.0, r * 0.025))
        line.setStyle(Qt.PenStyle.DashLine)
        p.setPen(line)
        p.drawLine(QtCore.QPointF(0, 0), tip)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        p.drawEllipse(QtCore.QPointF(0, 0), r * 0.035, r * 0.035)
        p.save()
        p.translate(tip)
        p.rotate(facing)                               # the Kaaba stays upright too
        self._kaaba(p, r * 0.22, colours.dark)
        p.restore()
        p.restore()

        # The pointer: the way the mat faces. Fixed at the top.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(GREEN if self.aligned else INK)
        top = cy - r * 1.02
        arrow = QtGui.QPolygonF([QtCore.QPointF(cx, top + r * 0.16),
                                 QtCore.QPointF(cx - r * 0.09, top - r * 0.04),
                                 QtCore.QPointF(cx + r * 0.09, top - r * 0.04)])
        p.drawPolygon(arrow)

    @staticmethod
    def _kaaba(p: QtGui.QPainter, size: float, dark: bool = False) -> None:
        """A small Kaaba: a black cube with its gold band, seen a little from above. The
        Kaaba is black whatever the theme; on a dark screen its edges are drawn in white so
        it still stands out."""
        s = size
        black = QtGui.QColor("black")
        edge = QtGui.QColor("white")
        body = QtCore.QRectF(-s / 2, -s / 2 + s * 0.08, s, s * 0.9)
        roof = QtGui.QPolygonF([QtCore.QPointF(-s / 2, -s / 2 + s * 0.08),
                                QtCore.QPointF(-s / 2 + s * 0.18, -s / 2 - s * 0.06),
                                QtCore.QPointF(s / 2 + s * 0.12, -s / 2 - s * 0.06),
                                QtCore.QPointF(s / 2, -s / 2 + s * 0.08)])
        side = QtGui.QPolygonF([QtCore.QPointF(s / 2, -s / 2 + s * 0.08),
                                QtCore.QPointF(s / 2 + s * 0.12, -s / 2 - s * 0.06),
                                QtCore.QPointF(s / 2 + s * 0.12, s / 2 - s * 0.14),
                                QtCore.QPointF(s / 2, s / 2 - 0.02 * s)])
        p.setPen(QtGui.QPen(edge, max(1.0, s * (0.05 if dark else 0.03))))
        p.setBrush(QtGui.QColor("#2A2A2A"))
        p.drawPolygon(roof)
        p.setBrush(QtGui.QColor("#111111"))
        p.drawPolygon(side)
        p.setBrush(black)
        p.drawRect(body)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(GOLD)
        p.drawRect(QtCore.QRectF(-s / 2, -s / 2 + s * 0.30, s, s * 0.11))
        p.drawRect(QtCore.QRectF(-s * 0.12, -s / 2 + s * 0.55, s * 0.24, s * 0.43))   # the door


class CompassScreen(QtWidgets.QWidget):
    """Full screen: a title, the dial, what to do, and the bearing."""
    done = Signal(bool)            # True when lined up, False when skipped

    def __init__(self, window, facing: Facing):
        super().__init__()
        self.win = window
        self.facing = facing
        self.setObjectName("compassRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        px = window.px
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(40), px(24), px(40), px(28))
        lay.setSpacing(px(10))

        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(window.t("qibla.title"))
        title.setObjectName("compassTitle")
        head.addWidget(title)
        head.addStretch(1)
        arabic = QtWidgets.QLabel("القِبْلَة")
        arabic.setObjectName("compassArabic")
        head.addWidget(arabic)
        lay.addLayout(head)

        from .render import Fonts
        self.dial = Dial(Fonts.english_family)
        lay.addWidget(self.dial, 1)

        # With no compass fitted, the bearing is not a footnote to a turning dial -- it is the
        # whole mechanism. Someone is kneeling on the floor squaring a mat against a compass in
        # their other hand, so the number gets to be the size of the thing you actually use.
        # It is hidden when a compass is fitted, where the dial and "turn right 20" do the work.
        self.bearing = QtWidgets.QLabel()
        self.bearing.setObjectName("compassBearing")
        self.bearing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bearing.hide()
        lay.addWidget(self.bearing)

        self.status = QtWidgets.QLabel()
        self.status.setObjectName("compassStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.detail = QtWidgets.QLabel()
        self.detail.setObjectName("compassDetail")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        lay.addWidget(self.detail)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.lined_up_since: float | None = None
        self.heading: float | None = None
        # On the 7" screen the compass stays up between prayers: it says when the mat is lined
        # up and carries on watching, rather than moving on.
        self.stays = False
        self.told = False

    @property
    def qibla(self) -> float:
        return self.win.qibla_bearing()

    def open(self) -> None:
        self.lined_up_since = None
        self.told = False
        self.tick()
        self.timer.start()

    def close_screen(self) -> None:
        self.timer.stop()

    def tick(self) -> None:
        self.heading = self.facing.read()
        qibla = self.qibla
        place = self.win.settings.place or self.win.t("qibla.here")
        key = "qibla.bearing_only" if self.stays else "qibla.bearing"   # a touch does nothing there
        self.detail.setText(self.win.t(key, place=place, degrees=f"{qibla:.1f}",
                                       point=compass_point(qibla)))
        if self.heading is None:
            self.dial.show_state(None, qibla, False)
            # The number alone. Adding the compass point beside it ran past the edge of the 7"
            # screen, and it is already in the line underneath.
            self.bearing.setText(f"{qibla:.0f}°")
            self.bearing.show()
            self.status.setText(self.win.t("qibla.no_compass"))
            return
        self.bearing.hide()
        turn = turn_needed(self.heading, qibla)
        aligned = abs(turn) <= IN_LINE
        self.dial.show_state(self.heading, qibla, aligned)
        if aligned:
            self.status.setText(self.win.t("qibla.facing"))
            now = time.monotonic()
            if self.lined_up_since is None:
                self.lined_up_since = now
            elif now - self.lined_up_since >= HOLD and not self.told:
                if self.stays:
                    self.told = True           # once, until it is turned away again
                else:
                    self.timer.stop()
                self.done.emit(True)
        else:
            self.lined_up_since = None
            self.told = False
            key = "qibla.turn_right" if turn > 0 else "qibla.turn_left"
            self.status.setText(self.win.t(key, degrees=f"{abs(turn):.0f}"))

    def mousePressEvent(self, e):
        if not self.stays:
            self.skip()
        e.accept()

    def skip(self) -> None:
        self.timer.stop()
        self.done.emit(False)
