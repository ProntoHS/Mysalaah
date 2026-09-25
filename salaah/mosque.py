"""The main screen: the mosque, with an arch for each prayer.

On a dark screen the drawing is turned over: a white mosque on a black sky, the time in black on
the white dome. The time sits in white on the dome, and whichever prayer's time it is has its arch lit up. Tap an
arch to start that prayer.
"""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

GREEN = QtGui.QColor("#1E9E57")            # the name of the prayer whose time it is
GREEN_DARK = QtGui.QColor("#4CD187")       # the same, on a dark screen
GLOW = QtGui.QColor(255, 214, 10)          # kept for the minaret glow
GLOW_EDGE = QtGui.QColor(255, 176, 0, 90)  # a soft halo around it
CLOCK_INK = QtGui.QColor("white")          # on the black dome; black on the white one after dark
CLOCK_BOOST = 1.15                         # the time, this much larger than a plain fit
CLOCK_LIFT = 0.07                          # and this much of the box's height higher up
CLOCK_ROOM = 0.35                          # room either side, so a boosted digit is never clipped
SUN = QtGui.QColor(255, 193, 7)
MOON = QtGui.QColor(232, 233, 228)
MOON_EDGE = QtGui.QColor(120, 124, 130)
STARS = 22                                 # twinkling in the night sky
BIRDS = 4                                  # fluttering across by day
SKY_STEP = 200                             # milliseconds between frames: gentle, and cheap


class GearButton(QtWidgets.QWidget):
    """A settings cog, drawn rather than lettered, so it needs no icon font."""
    pressed_signal = Signal()

    def __init__(self, size: int, colour: QtGui.QColor | None = QtGui.QColor("white")):
        super().__init__()
        self.colour = colour          # None: the theme's ink, black by day and white after dark
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        middle = QtCore.QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2 * 0.94

        tooth = QtGui.QPainterPath()
        tooth.addRoundedRect(QtCore.QRectF(-radius * 0.17, -radius, radius * 0.34, radius * 2),
                             radius * 0.07, radius * 0.07)
        gear = QtGui.QPainterPath()
        for i in range(4):     # four bars crossing gives eight teeth
            spin = QtGui.QTransform().translate(middle.x(), middle.y()).rotate(i * 45)
            gear = gear.united(spin.map(tooth))
        body = QtGui.QPainterPath()
        body.addEllipse(middle, radius * 0.68, radius * 0.68)
        gear = gear.united(body)
        hole = QtGui.QPainterPath()
        hole.addEllipse(middle, radius * 0.30, radius * 0.30)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.colour if self.colour is not None else QtGui.QColor(palette().ink))
        painter.drawPath(gear.subtracted(hole))

    def mouseReleaseEvent(self, event):
        if self.rect().contains(event.position().toPoint()):
            self.pressed_signal.emit()


class ArchButton(QtWidgets.QWidget):
    """One arch, drawn from the shape taken off the artwork, with its own number and label.

    Drawn rather than pictured, so a prayer can have as many arches as it has units and each
    can say what it is. Tapping it chooses that unit.
    """
    chosen = Signal(object)

    def colours(self) -> tuple[QtGui.QColor, QtGui.QColor, QtGui.QColor]:
        """The panel, the outline and the lettering.

        Straight off the theme rather than shades of its own, so the arch is an outline on the
        page it sits on - white inside by day, black inside after dark - and it can never drift
        out of step with the screen around it. The panel is still painted rather than left
        clear: it covers whatever is behind, which is what lets the walk into the arch dissolve
        into these.
        """
        colours = palette()
        return (QtGui.QColor(colours.paper), QtGui.QColor(colours.ink),
                QtGui.QColor(colours.ink))

    def __init__(self, shape: "ArchShape", count: str, label: str, payload, family: str = ""):
        super().__init__()
        self.shape = shape
        self.count = count
        self.label = label
        self.payload = payload
        self.family = family
        self.pressed = False
        self._drawn: QtGui.QPixmap | None = None
        self._drawn_dark = False
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def aspect(self) -> float:
        return self.shape.aspect

    def resizeEvent(self, _):
        self._drawn = None

    PAD = 0.03     # so the arch's base line is never clipped
    PAD_X = 0.04   # and a little clear either side, so neighbouring arches never touch

    def arch_rect(self) -> QtCore.QRect:
        """The arch, as large as fits, centred in the widget."""
        room_h = int(self.height() * (1 - 2 * self.PAD))
        room_w = int(self.width() * (1 - 2 * self.PAD_X))
        width = min(room_w, int(room_h * self.aspect))
        height = int(width / self.aspect)
        return QtCore.QRect((self.width() - width) // 2, (self.height() - height) // 2,
                            width, height)

    def paintEvent(self, _):
        box = self.arch_rect()
        if box.width() < 4 or box.height() < 4:
            return
        panel, border, text = self.colours()
        if self._drawn is None or self._drawn_dark != palette().dark:
            self._drawn = self.shape.draw(box.size(), panel, border)
            self._drawn_dark = palette().dark
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        if self.pressed:
            painter.setOpacity(0.75)
        painter.drawPixmap(box.topLeft(), self._drawn)
        painter.setOpacity(1.0)

        # The number sits in the belly of the arch, the label under it.
        painter.setPen(text)
        number_font = QtGui.QFont(self.family) if self.family else painter.font()
        number_font.setPixelSize(max(10, int(box.height() * 0.26)))
        number_font.setWeight(QtGui.QFont.Weight(700))
        painter.setFont(number_font)
        top = QtCore.QRect(box.x(), box.y() + int(box.height() * 0.22), box.width(), int(box.height() * 0.30))
        painter.drawText(top, int(Qt.AlignmentFlag.AlignCenter), self.count)

        # The label is as large as fits between the arch's sides, so "Sunnah" is never clipped.
        bottom = QtCore.QRect(box.x() + int(box.width() * 0.08),
                              box.y() + int(box.height() * 0.58),
                              int(box.width() * 0.84), int(box.height() * 0.26))
        label_font = QtGui.QFont(self.family) if self.family else painter.font()
        label_font.setWeight(QtGui.QFont.Weight(700))
        size = max(8, int(box.height() * 0.17))
        label_font.setPixelSize(size)
        while size > 8 and QtGui.QFontMetrics(label_font).horizontalAdvance(self.label) > bottom.width():
            size -= 1
            label_font.setPixelSize(size)
        painter.setFont(label_font)
        painter.drawText(bottom, int(Qt.AlignmentFlag.AlignCenter), self.label)

    def mousePressEvent(self, _):
        self.pressed = True
        self.update()

    def mouseReleaseEvent(self, event):
        self.pressed = False
        self.update()
        if self.rect().contains(event.position().toPoint()):
            self.chosen.emit(self.payload)


class ArchShape:
    """The arch outline and the panel inside it, ready to be drawn at any size."""

    def __init__(self, assets: Path):
        folder = assets / "mosque"
        self.outer = QtGui.QImage(str(folder / "arch-outer.png"))
        self.inner = QtGui.QImage(str(folder / "arch-inner.png"))
        self._cache: dict[tuple[int, int, str, str], QtGui.QPixmap] = {}

    @property
    def ready(self) -> bool:
        return not self.outer.isNull() and not self.inner.isNull()

    @property
    def aspect(self) -> float:
        return self.outer.width() / self.outer.height() if self.ready else 0.68

    KEEP = 8        # how many sizes to remember; a resize or a theme change makes new ones

    def draw(self, size: QtCore.QSize, panel: QtGui.QColor,
             border: QtGui.QColor) -> QtGui.QPixmap:
        key = (size.width(), size.height(), panel.name(), border.name())
        if key not in self._cache:
            picture = QtGui.QPixmap(size)
            picture.fill(Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(picture)
            for mask, colour in ((self.outer, border), (self.inner, panel)):
                # The mask is shrunk to size first and the colour put on afterwards. Colouring
                # first would mean shrinking a picture four times the weight for the same
                # result, which the Pi feels. The shrinking is what smooths the edge.
                small = mask.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                layer = QtGui.QImage(small.size(), QtGui.QImage.Format.Format_ARGB32)
                layer.fill(colour)
                layer.setAlphaChannel(small.convertToFormat(QtGui.QImage.Format.Format_Grayscale8))
                painter.drawImage(0, 0, layer)
            painter.end()
            if len(self._cache) >= self.KEEP:
                self._cache.clear()
            self._cache[key] = picture
        return self._cache[key]


class ZoomVeil(QtWidgets.QWidget):
    """Walks into the arch: the mosque swells towards the arch that was tapped and fades out,
    leaving the prayer's own arches behind it.

    It is only a picture laid over the top. The screen underneath has already changed before
    this starts, so if it is cut short, or never runs at all, nothing is left half done - the
    worst that happens is that the change is instant. That matters on a mat: an animation is
    never allowed to be the thing that decides which screen you are on.

    The picture is taken once, at half size, and blown up without smoothing. Nothing stands
    still long enough to see the difference, and it saves the Pi three quarters of the work on
    every frame.
    """
    finished = Signal()

    MS = 1000           # how long the walk takes
    STEP = 33           # milliseconds a frame: about 30 a second, which is plenty this quick
    ZOOM = 2.8          # how much nearer the arch ends up
    DISSOLVE = 0.45     # the last of the walk over which the mosque thins away
    COARSE = 2          # the picture is taken at one part in this of full size

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.picture = QtGui.QPixmap()
        self.focus = QtCore.QPointF()
        self.began = 0.0
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.STEP)
        self.timer.timeout.connect(self.tick)
        self.hide()

    def start(self, shot: QtGui.QPixmap, area: QtCore.QRect, focus: QtCore.QPoint) -> None:
        """Walks into the point [focus] of [shot], a picture of the screen as it was a moment
        ago, laid over [area]. The picture is taken by the caller, before the screen changes."""
        if shot.isNull() or area.width() < 8 or area.height() < 8:
            return self.give_up()
        self.picture = shot.scaled(shot.size() / self.COARSE,
                                   Qt.AspectRatioMode.IgnoreAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        self.focus = QtCore.QPointF(focus) / self.COARSE
        self.setGeometry(area)
        self.began = time.monotonic()
        self.show()
        self.raise_()
        self.timer.start()
        self.update()

    def give_up(self) -> None:
        """Nothing to show: say it is over, so whoever is waiting carries on regardless."""
        self.stop()

    def stop(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        self.picture = QtGui.QPixmap()
        self.hide()
        self.finished.emit()

    @property
    def running(self) -> bool:
        return self.timer.isActive()

    def how_far(self) -> float:
        """How far through the walk, nought to one.

        It builds and then eases off, rather than starting at full pelt: a step that begins
        fast reads as a jolt, where a walk towards something gathers pace.
        """
        gone = (time.monotonic() - self.began) * 1000 / self.MS
        step = min(1.0, max(0.0, gone))
        return step * step * (3 - 2 * step)

    def tick(self) -> None:
        if self.how_far() >= 1.0:
            return self.stop()
        self.update()

    def frame(self, along: float) -> tuple[QtCore.QRectF, float]:
        """Where the picture goes this frame, and how solid it is.

        The arch drifts from where it was tapped to the middle of the screen while everything
        swells around it, which is what reading as walking towards it depends on. It thins out
        late, so the mosque is still there for most of the move.
        """
        grown = 1 + (self.ZOOM - 1) * along
        middle = QtCore.QPointF(self.width() / 2, self.height() / 2)
        here = QtCore.QPointF(self.focus.x() * self.COARSE, self.focus.y() * self.COARSE)
        aim = here + (middle - here) * along
        wide, tall = self.picture.width() * self.COARSE, self.picture.height() * self.COARSE
        box = QtCore.QRectF(aim.x() - self.focus.x() * self.COARSE * grown,
                            aim.y() - self.focus.y() * self.COARSE * grown,
                            wide * grown, tall * grown)
        return box, max(0.0, min(1.0, (1 - along) / self.DISSOLVE))

    def paintEvent(self, _):
        if self.picture.isNull():
            return
        box, solid = self.frame(self.how_far())
        painter = QtGui.QPainter(self)
        painter.setClipRect(self.rect())        # no work on the part that has left the screen
        painter.setOpacity(solid)
        painter.drawPixmap(box, self.picture, QtCore.QRectF(self.picture.rect()))


class Sky:
    """What moves in the sky behind the mosque: stars that twinkle after dark, birds that
    flutter across by day. Everything is held as fractions of the picture, so it lands in the
    same place whatever the screen size, and is drawn behind the mosque."""

    def __init__(self, seed: int = 7):
        chance = random.Random(seed)
        # Stars sit in the upper part of the sky, away from the very edges.
        self.stars = [(chance.uniform(0.04, 0.96), chance.uniform(0.04, 0.46),
                       chance.uniform(0.6, 1.0), chance.uniform(0, 6.28))
                      for _ in range(STARS)]
        # Birds: where they start, how fast they drift, how high, how fast they flap.
        self.birds = [(chance.uniform(0, 1), chance.uniform(0.012, 0.022),
                       chance.uniform(0.10, 0.32), chance.uniform(0, 6.28))
                      for _ in range(BIRDS)]

    @staticmethod
    def now() -> float:
        return time.monotonic()

    def star_alpha(self, twinkle: float, phase: float, moment: float) -> int:
        """How bright a star is just now: a slow breath in and out, each on its own beat."""
        wave = (math.sin(moment * 1.6 + phase) + 1) / 2
        return int(90 + 160 * twinkle * wave)

    def bird_at(self, bird, moment: float) -> tuple[float, float, float]:
        """Where a bird is, as fractions across and down, and how far through a wingbeat."""
        start, speed, height, phase = bird
        across = (start + moment * speed) % 1.25 - 0.12     # off one side, back on the other
        up_down = height + 0.012 * math.sin(moment * 0.9 + phase)
        return across, up_down, math.sin(moment * 7.0 + phase)


@dataclass(frozen=True)
class Arch:
    prayer: str
    box: QtCore.QRect
    mask: QtGui.QImage


class MosqueScreen(QtWidgets.QWidget):
    """Draws the mosque to fit, and turns taps on an arch into a prayer."""
    chosen = Signal(str)

    def __init__(self, assets: Path, clock_font: str = ""):
        super().__init__()
        self.arches: list[Arch] = []
        self.picture = QtGui.QPixmap()
        self.clock_box = QtCore.QRect()
        self.lit: str | None = None
        self.minarets: dict[str, QtCore.QRect] = {}
        self.sun_up = True
        self.sky = Sky()
        self.flutter = QtCore.QTimer(self)      # only while the main screen is on show
        self.flutter.setInterval(SKY_STEP)
        self.flutter.timeout.connect(self.update)
        self.through = 0.5      # how far across the sky the sun or moon has travelled
        self.time_text = ""
        self.clock_font = clock_font
        self._scaled: QtGui.QPixmap | None = None
        self._scaled_dark = False
        self._glows: dict[str, QtGui.QPixmap] = {}
        self._names: dict[tuple, QtGui.QPixmap] = {}
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.load(assets)

    # Loading

    def load(self, assets: Path) -> None:
        folder = assets / "mosque"
        try:
            described = json.loads((folder / "mosque.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.picture = QtGui.QPixmap(str(folder / described["image"]))
        box = described["clock"]["box"]
        self.clock_box = QtCore.QRect(box[0], box[1], box[2] - box[0], box[3] - box[1])
        for side, box in described.get("minarets", {}).items():
            self.minarets[side] = QtCore.QRect(box[0], box[1], box[2] - box[0], box[3] - box[1])
        for prayer, arch in described["arches"].items():
            x0, y0, x1, y1 = arch["box"]
            mask = QtGui.QImage(str(folder / f"arch-{prayer}.png"))
            self.arches.append(Arch(prayer, QtCore.QRect(x0, y0, x1 - x0, y1 - y0), mask))

    @property
    def ready(self) -> bool:
        return not self.picture.isNull() and bool(self.arches)

    # What to show

    def set_time(self, text: str) -> None:
        if text != self.time_text:
            self.time_text = text
            self.update()

    def set_lit(self, prayer: str | None) -> None:
        """The prayer that may be prayed now. None lights the minarets instead: no prayer is due."""
        if prayer != self.lit:
            self.lit = prayer
            self.update()

    def set_sky(self, sun_up: bool, through: float) -> None:
        if (sun_up, round(through, 3)) != (self.sun_up, round(self.through, 3)):
            self.sun_up, self.through = sun_up, max(0.0, min(1.0, through))
            self.update()

    # Drawing

    def placement(self) -> tuple[QtGui.QPixmap, QtCore.QPoint, float]:
        """The picture scaled to fit, where it sits, and by how much it was scaled."""
        dark = palette().dark
        if self._scaled is None or self._scaled_dark != dark or (
                self._scaled.width() != self.width() and self._scaled.height() != self.height()):
            self._scaled = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            if dark:
                from .render import invert
                self._scaled = invert(self._scaled)
            self._scaled_dark = dark
            self._glows.clear()
            self._names.clear()
        scale = self._scaled.width() / self.picture.width()
        origin = QtCore.QPoint((self.width() - self._scaled.width()) // 2,
                               (self.height() - self._scaled.height()) // 2)
        return self._scaled, origin, scale

    def clock_type(self, box: QtCore.QRect, text: str,
                   fallback: QtGui.QFont | None = None) -> QtGui.QFont:
        """The time, as large as the dome allows: fitted to the flat middle of the dome, then
        CLOCK_BOOST larger again, since the dome curves out wider either side of the numbers."""
        font = QtGui.QFont(self.clock_font) if self.clock_font else QtGui.QFont(fallback or QtGui.QFont())
        font.setWeight(QtGui.QFont.Weight(700))
        size = max(8, int(box.height() * 1.10))
        font.setPixelSize(size)
        while size > 8 and QtGui.QFontMetrics(font).horizontalAdvance(text) > box.width() * 0.94:
            size -= 2
            font.setPixelSize(size)
        font.setPixelSize(max(8, int(size * CLOCK_BOOST)))
        return font

    def clock_rect(self, box: QtCore.QRect) -> QtCore.QRect:
        """Where the time is drawn: the dome's flat middle, lifted a little towards the centre
        of the dome, and given room either side so the boosted lettering is not clipped."""
        room = int(box.width() * CLOCK_ROOM)
        lift = int(box.height() * CLOCK_LIFT)
        return QtCore.QRect(box.x() - room, box.y() - lift, box.width() + 2 * room, box.height())

    def name_in_green(self, arch: Arch, scale: float) -> QtGui.QPixmap:
        """The prayer's name lifted off the artwork and painted green, ready to lay over it.

        The names are part of the picture, so they cannot simply be restyled. Each arch has a
        mask of its inside with the lettering cut out of it, so the letters are exactly the
        holes: fill each row of the mask between its first and last marked pixel, and whatever
        the filled shape covers but the mask does not is the name. How dark the artwork is
        there gives each pixel its strength, so the edges stay smooth.

        Worked out once per prayer at the artwork's own size and then scaled, so the screen's
        size costs nothing and it is never worked out twice.
        """
        green = GREEN_DARK if palette().dark else GREEN
        key = (arch.prayer, green.name())
        if key not in self._names:
            self._names[key] = self._stencil(arch, green)
        size = QtCore.QSize(max(1, int(arch.box.width() * scale)),
                            max(1, int(arch.box.height() * scale)))
        return self._names[key].scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)

    def _stencil(self, arch: Arch, green: QtGui.QColor) -> QtGui.QPixmap:
        mask = arch.mask.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
        width, height = mask.width(), mask.height()
        # The artwork's panels are transparent, so lay the patch on white first: only what is
        # really drawn counts as ink.
        flat = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
        flat.fill(QtGui.QColor("white"))
        painter = QtGui.QPainter(flat)
        painter.drawImage(QtCore.QRect(0, 0, width, height), self.picture.copy(arch.box).toImage())
        painter.end()

        letters = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
        letters.fill(Qt.GlobalColor.transparent)   # a QColor with alpha 0 does not clear it
        for y in range(height):
            row = [QtGui.qGray(mask.pixel(x, y)) for x in range(width)]
            marked = [x for x, v in enumerate(row) if v > 128]
            if not marked:
                continue
            for x in range(marked[0], marked[-1] + 1):     # the arch's own shape, holes filled
                if row[x] > 128:
                    continue                                # the mask itself: not a letter
                ink = 255 - QtGui.qGray(flat.pixel(x, y))   # how dark the artwork is here
                if ink > 24:
                    letters.setPixelColor(x, y, QtGui.QColor(green.red(), green.green(),
                                                             green.blue(), ink))
        return QtGui.QPixmap.fromImage(letters)

    def glow_for(self, arch: Arch, scale: float) -> QtGui.QPixmap:
        """The arch's inside, filled with yellow, ready to lay over the picture."""
        if arch.prayer not in self._glows:
            coloured = QtGui.QImage(arch.mask.size(), QtGui.QImage.Format.Format_ARGB32)
            coloured.fill(GLOW)
            coloured.setAlphaChannel(arch.mask.convertToFormat(QtGui.QImage.Format.Format_Grayscale8))
            size = QtCore.QSize(max(1, int(arch.box.width() * scale)),
                                max(1, int(arch.box.height() * scale)))
            self._glows[arch.prayer] = QtGui.QPixmap.fromImage(
                coloured.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
        return self._glows[arch.prayer]

    def sky_body(self, scaled: QtGui.QPixmap, origin: QtCore.QPoint) -> tuple[QtCore.QPointF, float]:
        """Where the sun or moon sits: along an arc across the sky, rising and setting at the
        sides and highest in the middle, so a glance tells you roughly what time of day it is."""
        width, height = scaled.width(), scaled.height()
        radius = max(8.0, width * 0.035)
        left = origin.x() + width * 0.14
        span = width * 0.72
        x = left + span * self.through
        import math
        top = origin.y() + height * 0.06
        bottom = origin.y() + height * 0.46
        y = bottom - (bottom - top) * math.sin(math.pi * self.through)
        return QtCore.QPointF(x, y), radius

    def showEvent(self, event):
        super().showEvent(event)
        self.flutter.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.flutter.stop()

    def draw_stars(self, painter: QtGui.QPainter, scaled: QtGui.QPixmap,
                   origin: QtCore.QPoint) -> None:
        """Twinkling stars, drawn in the ink of the day: white on the night screen, black on
        the white one, so they suit the line-drawn style either way."""
        moment = self.sky.now()
        ink = QtGui.QColor(palette().ink)
        size = max(1.6, scaled.width() * 0.0026)
        painter.setPen(Qt.PenStyle.NoPen)
        for across, down, twinkle, phase in self.sky.stars:
            ink.setAlpha(self.sky.star_alpha(twinkle, phase, moment))
            painter.setBrush(ink)
            middle = QtCore.QPointF(origin.x() + scaled.width() * across,
                                    origin.y() + scaled.height() * down)
            painter.drawEllipse(middle, size * twinkle, size * twinkle)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def draw_birds(self, painter: QtGui.QPainter, scaled: QtGui.QPixmap,
                   origin: QtCore.QPoint) -> None:
        """A few little birds, each a pair of wings that flap as it drifts across."""
        moment = self.sky.now()
        pen = QtGui.QPen(QtGui.QColor(palette().ink))
        span = max(4.0, scaled.width() * 0.012)
        pen.setWidthF(max(1.2, span * 0.16))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for bird in self.sky.birds:
            across, down, beat = self.sky.bird_at(bird, moment)
            if not -0.1 <= across <= 1.1:
                continue
            x = origin.x() + scaled.width() * across
            y = origin.y() + scaled.height() * down
            rise = span * 0.75 * beat                 # both wings go up and down together
            wing = QtGui.QPainterPath()                # a gull: two strokes meeting at the body
            wing.moveTo(x - span, y)
            wing.quadTo(x - span * 0.5, y - rise, x, y - rise * 0.12)
            wing.quadTo(x + span * 0.5, y - rise, x + span, y)
            painter.drawPath(wing)

    def draw_sky(self, painter: QtGui.QPainter, scaled: QtGui.QPixmap, origin: QtCore.QPoint) -> None:
        centre, radius = self.sky_body(scaled, origin)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.sun_up:
            painter.setBrush(QtGui.QColor(255, 193, 7, 60))
            painter.drawEllipse(centre, radius * 1.7, radius * 1.7)
            painter.setBrush(SUN)
            painter.drawEllipse(centre, radius, radius)
        else:
            # A crescent: the moon's disc with a second disc taken out of it.
            painter.setBrush(MOON)
            pen = QtGui.QPen(MOON_EDGE)
            pen.setWidthF(max(1.0, radius * 0.06))
            painter.setPen(pen)
            path = QtGui.QPainterPath()
            path.addEllipse(centre, radius, radius)
            bite = QtGui.QPainterPath()
            bite.addEllipse(QtCore.QPointF(centre.x() + radius * 0.42, centre.y() - radius * 0.18),
                            radius * 0.92, radius * 0.92)
            painter.drawPath(path.subtracted(bite))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def draw_minaret_glow(self, painter: QtGui.QPainter, origin: QtCore.QPoint, scale: float) -> None:
        """With no prayer due, the tops of the two minarets glow instead of an arch."""
        painter.setPen(Qt.PenStyle.NoPen)
        for box in self.minarets.values():
            where = QtCore.QRectF(origin.x() + box.x() * scale, origin.y() + box.y() * scale,
                                  box.width() * scale, box.height() * scale)
            middle = where.center()
            for step, alpha in ((2.0, 40), (1.5, 70), (1.15, 120)):
                painter.setBrush(QtGui.QColor(255, 193, 7, alpha))
                painter.drawEllipse(middle, where.width() * step * 0.5, where.height() * step * 0.5)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(palette().paper))
        if not self.ready:
            return
        scaled, origin, scale = self.placement()
        if self.sun_up:
            self.draw_birds(painter, scaled, origin)
        else:
            self.draw_stars(painter, scaled, origin)
        self.draw_sky(painter, scaled, origin)
        if self.lit is None:
            self.draw_minaret_glow(painter, origin, scale)
        painter.drawPixmap(origin, scaled)

        # Which prayer it is now: its name on the arch in green, and its time in green in the
        # banner. No box over the arch; that was more shout than help.
        if self.lit:
            for arch in self.arches:
                if arch.prayer != self.lit:
                    continue
                where = QtCore.QPoint(origin.x() + int(arch.box.x() * scale),
                                      origin.y() + int(arch.box.y() * scale))
                painter.drawPixmap(where, self.name_in_green(arch, scale))
        if self.time_text:
            box = QtCore.QRect(origin.x() + int(self.clock_box.x() * scale),
                               origin.y() + int(self.clock_box.y() * scale),
                               int(self.clock_box.width() * scale),
                               int(self.clock_box.height() * scale))
            painter.setFont(self.clock_type(box, self.time_text, painter.font()))
            painter.setPen(QtGui.QColor("black") if palette().dark else CLOCK_INK)
            painter.drawText(self.clock_rect(box),
                             int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextDontClip),
                             self.time_text)

    # Choosing

    def arch_centre(self, prayer: str) -> QtCore.QPoint | None:
        """The middle of one arch, in this widget's own pixels. The zoom uses it to know what
        it is walking towards."""
        if not self.ready:
            return None
        _, origin, scale = self.placement()
        for arch in self.arches:
            if arch.prayer == prayer:
                middle = arch.box.center()
                return QtCore.QPoint(origin.x() + int(middle.x() * scale),
                                     origin.y() + int(middle.y() * scale))
        return None

    def arch_at(self, point: QtCore.QPoint) -> str | None:
        if not self.ready:
            return None
        _, origin, scale = self.placement()
        x = (point.x() - origin.x()) / scale
        y = (point.y() - origin.y()) / scale
        for arch in self.arches:
            if arch.box.contains(int(x), int(y)):
                return arch.prayer
        return None

    def mousePressEvent(self, event):
        prayer = self.arch_at(event.position().toPoint())
        if prayer:
            self.chosen.emit(prayer)
