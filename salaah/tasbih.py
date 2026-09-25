"""The screen after a fardh prayer: the dhikr counted on three beads.

The salam dua runs across the top, the tahlil across the bottom, and between them three beads
on a cord, one for each of سبحان الله, الحمد لله and الله أكبر. The bead being said has its name
in red and a count underneath that comes down by one on every click. At nought the next bead
turns red, so the three are worked through left to right exactly as on a real tasbih.
"""
from __future__ import annotations

from .content import Bead
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette


def ink() -> QtGui.QColor:
    return QtGui.QColor(palette().ink)


def paper() -> QtGui.QColor:
    return QtGui.QColor(palette().paper)


def saying() -> QtGui.QColor:
    """The bead being counted, and the ones already said: the recitation's red."""
    return QtGui.QColor(palette().highlight)


def finished() -> QtGui.QColor:
    """A bead with nothing left to count: filled green."""
    return QtGui.QColor(palette().green)


class BeadRow(QtWidgets.QWidget):
    """Three beads on a cord: name above, count below, drawn rather than laid out so the
    proportions hold at any screen size."""

    CORD = 0.010          # cord thickness, as a share of the row's height
    RING = 0.030          # the bead's black outline
    KNOT = 0.055          # the small beads between the big ones, as a share of the height

    def __init__(self, arabic_family: str = "", count_family: str = ""):
        super().__init__()
        self.arabic_family = arabic_family
        self.count_family = count_family
        self.beads: list[Bead] = []
        self.left: list[int] = []
        self.current = 0
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def set_beads(self, beads: list[Bead]) -> None:
        self.beads = list(beads)
        self.reset()

    def reset(self) -> None:
        self.left = [b.count for b in self.beads]
        self.current = 0
        self.update()

    @property
    def done(self) -> bool:
        return bool(self.beads) and self.current >= len(self.beads)

    def press(self) -> bool:
        """Counts one off the bead being said. True while there is still counting left."""
        if self.done or not self.beads:
            return False
        self.left[self.current] = max(0, self.left[self.current] - 1)
        while self.current < len(self.beads) and self.left[self.current] == 0:
            self.current += 1
        self.update()
        return True

    def geometry_for(self, n: int) -> tuple[QtCore.QRectF, QtCore.QRectF, QtCore.QRectF]:
        """Where bead [n]'s name, circle and count go."""
        count = max(1, len(self.beads))
        w, h = self.width(), self.height()
        column = w / count
        name = QtCore.QRectF(column * n, 0, column, h * 0.24)
        number = QtCore.QRectF(column * n, h * 0.82, column, h * 0.18)
        size = min(column * 0.52, h * 0.46)
        circle = QtCore.QRectF(column * (n + 0.5) - size / 2, h * 0.55 - size / 2, size, size)
        return name, circle, number

    def paintEvent(self, _):
        if not self.beads:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        INK, PAPER, SAYING, DONE = ink(), paper(), saying(), finished()
        h = self.height()
        places = [self.geometry_for(n) for n in range(len(self.beads))]

        # the cord, running the whole way across and on out of both sides
        cord = max(1, int(h * self.CORD))
        middle = places[0][1].center().y()
        pen = QtGui.QPen(INK)
        pen.setWidth(cord)
        p.setPen(pen)
        p.drawLine(QtCore.QPointF(0, middle), QtCore.QPointF(self.width(), middle))

        # a small bead between each pair, and one at each end, so it reads as a tasbih
        knot = max(2, int(h * self.KNOT))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        edges = [places[0][1].left() / 2] + \
                [(places[i][1].right() + places[i + 1][1].left()) / 2 for i in range(len(places) - 1)] + \
                [(places[-1][1].right() + self.width()) / 2]
        for x in edges:
            p.drawEllipse(QtCore.QRectF(x - knot / 2, middle - knot / 2, knot, knot))

        ring = max(2, int(h * self.RING))
        for n, (name_box, circle, number_box) in enumerate(places):
            said = n <= self.current          # the one being counted, and the ones behind it
            # the bead: outlined while there is counting left on it, solid green once done
            done = self.left[n] == 0
            pen = QtGui.QPen(INK)
            pen.setWidth(ring)
            p.setPen(pen)
            p.setBrush(DONE if done else PAPER)
            p.drawEllipse(circle.adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2))

            font = QtGui.QFont(self.arabic_family) if self.arabic_family else p.font()
            font.setWeight(QtGui.QFont.Weight(700))
            font.setPixelSize(max(12, int(name_box.height() * 0.78)))
            font = self._shrunk(font, self.beads[n].text, name_box.width() * 0.92)
            p.setFont(font)
            p.setPen(SAYING if said else INK)
            p.drawText(name_box, int(Qt.AlignmentFlag.AlignCenter), self.beads[n].text)

            number = QtGui.QFont(self.count_family) if self.count_family else p.font()
            number.setWeight(QtGui.QFont.Weight(700))
            number.setPixelSize(max(10, int(number_box.height() * 0.80)))
            p.setFont(number)
            p.setPen(SAYING)                   # the count in red, as it comes down
            p.drawText(number_box, int(Qt.AlignmentFlag.AlignCenter), f"X{self.left[n]}")

    @staticmethod
    def _shrunk(font: QtGui.QFont, text: str, room: float) -> QtGui.QFont:
        size = font.pixelSize()
        while size > 12 and QtGui.QFontMetrics(font).horizontalAdvance(text) > room:
            size -= 2
            font.setPixelSize(size)
        return font


class TasbihScreen(QtWidgets.QWidget):
    """The whole after-prayer screen. Clicks are passed in from the window, so the ring button
    and the touchscreen both count, and each count can play its recording."""
    counted = Signal()
    tapped = Signal()             # a touch on the screen: the window counts it

    def __init__(self, arabic_family: str = "", count_family: str = "", px=lambda v: v):
        super().__init__()
        self.setObjectName("tasbih")
        # A QWidget subclass only takes a background from the stylesheet when asked to.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.follow_theme()
        from .render import MAX_ARABIC_PX, MIN_ARABIC_PX, TextBox

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(44), px(20), px(44), px(20))
        lay.setSpacing(px(12))

        def line(minimum: int, maximum: int) -> "TextBox":
            # One line, whole and unbroken, across the width of the screen.
            # Laid out word by word, so the word being recited can turn red.
            return TextBox(arabic_family, minimum, maximum, rtl=True, weight=700,
                           slack=0.98, by_word=True, gap=0.18, one_line=True)

        self.salam = line(max(18, MIN_ARABIC_PX // 2), MAX_ARABIC_PX)
        self.tahlil = line(max(18, MIN_ARABIC_PX // 2), MAX_ARABIC_PX)
        self.beads = BeadRow(arabic_family, count_family)

        lay.addWidget(self.salam, 3)
        lay.addWidget(self.beads, 8)
        lay.addWidget(self.tahlil, 3)

    def follow_theme(self) -> None:
        pal = self.palette()
        pal.setColor(QtGui.QPalette.ColorRole.Window, paper())
        self.setPalette(pal)
        self.update()

    def set_scale(self, scale: float) -> None:
        self.salam.scale = scale
        self.tahlil.scale = scale

    def show_dhikr(self, dhikr) -> None:
        self.salam.set_lines([dhikr.salam] if dhikr.salam else [])
        self.tahlil.set_lines([dhikr.tahlil] if dhikr.tahlil else [])
        self.beads.set_beads(dhikr.beads)

    @property
    def done(self) -> bool:
        return self.beads.done

    def press(self) -> bool:
        counted = self.beads.press()
        if counted:
            self.counted.emit()
        return counted

    def mousePressEvent(self, e):
        self.tapped.emit()
        e.accept()
