"""Qibla Quest: choose the direction of Makkah from five cities.

The rules contain no Qt and no clock.  The screen supplies both, so the game can be played
thousands of times by the kit's fairness checker without a display.  Every round deals the
four compass choices afresh: no fixed ring press can learn the position of the answer.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


@dataclass(frozen=True)
class Round:
    city: str
    answer: str
    point: tuple[float, float]


# Bearings are classified into broad quadrants rather than pretending this is a compass.
# The places deliberately span several parts of the world and each wrong answer remains a
# plausible compass direction.  A qualified reviewer has not yet checked the teaching copy.
#
# THE POINTS ARE A FRACTION OF assets/children/qibla-quest.png, and they have now been wrong
# twice, in two different ways, so it is worth writing down how they are arrived at.
#
# The numbers this module arrived with put London in the Mediterranean, Cape Town in the Indian
# Ocean, Istanbul out to sea and Jakarta on Australia -- up to 130 px out, a ninth of the map's
# width.  Those were replaced by the drawing prototype's own coordinates.
#
# Then in October 2026 the map was redrawn, and every one of them was wrong again. Not by a
# mistake: the new drawing is 1672x941 where the old was 1600x786, an aspect of 1.78 against
# 2.04, so it is a different projection and a fraction that meant London on one sheet means the
# Bay of Biscay on the other. A REDRAWN MAP INVALIDATES EVERY POINT HERE. There is nothing in
# the app that can notice, because a fraction is a valid fraction wherever it lands.
#
# How these were derived.  Eleven coastal landmarks were measured off the silhouette -- capes
# and peninsula tips, which are unambiguous on any world map -- and a linear fit taken through
# them:
#
#     x = 4.6825 * longitude + 740.5          residuals under 16 px
#     y = -5.2510 * latitude  + 566.4         residuals under  8 px
#
# Longitude is linear because it has to be: every cylindrical projection makes it so.  Latitude
# is the part that needed checking, and it is linear to within 8 px from 54 S to 59 N -- which
# is the whole band these five cities sit in -- while departing badly above 60 N, where this
# map stretches the Arctic (northern Greenland is 62 px off a linear fit).  Mercator was tried
# and ruled out at 46 px.
#
# Two fits that LOOKED right and were not, which is why none of this is taken on trust: one
# using only southern-hemisphere landmarks put London in Scotland, and a Miller projection put
# it in northern Spain.  Both had respectable residuals against their own reference points.
# What settled it was drawing the five pins on the map and looking at them.  Five of the five
# land on ink; Makkah does too.  tools/ARTWORK-MEASURED.md has the overlay.
#
# The answers do NOT depend on the map.  They are great-circle bearings to 21.4225 N, 39.8262 E
# binned to eight points: London 119.0, Cape Town 23.4, Tashkent 240.3, Jakarta 295.2, Istanbul
# 151.6.  All five agree with the quadrant below, and tests/test_ui.py recomputes them.
ROUNDS = (
    Round("london", "se", (0.4425, 0.3145)),
    Round("cape_town", "ne", (0.4945, 0.7912)),
    Round("tashkent", "sw", (0.6368, 0.3715)),
    Round("jakarta", "nw", (0.7421, 0.6366)),
    Round("istanbul", "se", (0.5240, 0.3731)),
)
DIRECTIONS = ("ne", "se", "sw", "nw")
ANSWERED, AGAIN, NOTHING = "answered", "again", "nothing"


class QiblaQuest:
    """Rules for the five-round direction quiz.

    THE CITIES COME IN A SHUFFLED ORDER.  Asked in a fixed order the five answers were a fixed
    sequence -- south-east, north-east, south-west, north-west, south-east -- and one
    playthrough taught the whole game by heart without teaching anything about where Makkah is.
    The prayer game's fixed dawn-to-night order is right because the order IS the lesson there.
    Here the order carries nothing, so it is shuffled.
    """

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.order = list(range(len(ROUNDS)))
        self._shuffle(self.order)
        self.at = 0
        self.score = 0
        self.done = False
        self.deal()

    def deal(self) -> None:
        picks = list(DIRECTIONS)
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.locked = False
        self.chosen: int | None = None

    @property
    def round(self) -> Round:
        return ROUNDS[self.order[self.at]]

    @property
    def rounds(self) -> int:
        return len(ROUNDS)

    @property
    def correct(self) -> int:
        return self.choices.index(self.round.answer)

    @property
    def right(self) -> bool | None:
        return None if self.chosen is None else self.chosen == self.correct

    def step(self) -> None:
        if not (self.locked or self.done):
            self.active = (self.active + 1) % len(self.choices)

    def press(self) -> str:
        if self.done:
            self.restart()
            return AGAIN
        return self.answer(self.active)

    def answer(self, which: int) -> str:
        if self.done or self.locked or not 0 <= which < len(self.choices):
            return NOTHING
        self.active = which
        self.chosen = which
        self.locked = True
        if self.right:
            self.score += 1
        return ANSWERED

    def go_on(self) -> None:
        if not self.locked:
            return
        if self.at + 1 >= len(ROUNDS):
            self.done = True
            self.locked = False
            self.chosen = None
            return
        self.at += 1
        self.deal()


class DirectionBox(QtWidgets.QAbstractButton):
    IDLE, ACTIVE, RIGHT, WRONG = "idle", "active", "right", "wrong"
    WORDS_PX = 38

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.state = self.IDLE
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(window.px(105))

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        edge, ink, thick = c.line, c.ink, self.win.px(3)
        fill = QtGui.QColor(c.paper)
        if self.state == self.ACTIVE:
            edge, thick, fill = c.lapis, self.win.px(7), QtGui.QColor(c.pressed)
        elif self.state == self.RIGHT:
            edge, ink, thick, fill = c.green, c.green, self.win.px(7), QtGui.QColor(c.pressed)
        elif self.state == self.WRONG:
            edge, ink, thick = c.highlight, c.highlight, self.win.px(7)
        if self.isDown():
            fill = QtGui.QColor(c.pressed)
        box = QtCore.QRectF(self.rect()).adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        radius = self.win.px(18)
        p.setPen(QtGui.QPen(QtGui.QColor(edge), thick))
        p.setBrush(fill)
        p.drawRoundedRect(box, radius, radius)
        font = QtGui.QFont(Fonts.for_text(self.text()))
        font.setPixelSize(max(12, self.win.px(self.WORDS_PX)))
        font.setWeight(QtGui.QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QtGui.QColor(ink))
        p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.text())


class MapPanel(QtWidgets.QFrame):
    """Harry's map artwork with the current city and Makkah picked out on top."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.point = (0.5, 0.5)
        self.map = QtGui.QPixmap(str(window.assets / "children" / "qibla-quest.png"))
        self.setMinimumHeight(window.px(280))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    @property
    def ready(self) -> bool:
        return not self.map.isNull()

    def set_point(self, point: tuple[float, float]) -> None:
        self.point = point
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        if self.ready:
            shown = self.map.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            left = (self.width() - shown.width()) // 2
            top = (self.height() - shown.height()) // 2
            p.drawPixmap(left, top, shown)
            x = left + int(shown.width() * self.point[0])
            y = top + int(shown.height() * self.point[1])
            radius = self.win.px(13)
            p.setPen(QtGui.QPen(QtGui.QColor(c.highlight), self.win.px(5)))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawEllipse(QtCore.QPoint(x, y), radius, radius)
        else:
            p.setPen(QtGui.QPen(QtGui.QColor(c.line), self.win.px(3)))
            p.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(self.win.px(2), self.win.px(2),
                                                                 -self.win.px(2), -self.win.px(2)),
                              self.win.px(18), self.win.px(18))


class QiblaQuestScreen(QtWidgets.QWidget):
    """Big-screen game, playable by scanning ring press or direct touch."""

    CYCLE = 1350
    SHOWN = 1900
    leave = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = QiblaQuest(shuffle)
        self.setObjectName("qiblaQuestScreen")

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(window.px(30), window.px(8), window.px(30), window.px(26))
        column.setSpacing(window.px(9))

        top = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignLeading)
        self.title.setObjectName("gameQuestion")
        self.where = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignTrailing)
        self.where.setObjectName("gameWhere")
        top.addWidget(self.title, 1)
        top.addWidget(self.where)
        column.addLayout(top)

        self.city = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.city.setObjectName("cornerTitle")
        column.addWidget(self.city)

        self.map = MapPanel(window)
        column.addWidget(self.map, 1)
        self.map_note = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.map_note.setObjectName("sourceNote")
        self.map_note.setWordWrap(True)
        column.addWidget(self.map_note)

        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameQuestion")
        self.question.setWordWrap(True)
        column.addWidget(self.question)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(window.px(15))
        self.boxes: list[DirectionBox] = []
        for i in range(len(DIRECTIONS)):
            box = DirectionBox(window)
            box.clicked.connect(lambda _=False, n=i: self.touched(n))
            row.addWidget(box, 1)
            self.boxes.append(box)
        column.addLayout(row)

        self.said = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.said.setObjectName("gameSaid")
        self.said.setWordWrap(True)
        column.addWidget(self.said)

        self.stepper = QtCore.QTimer(self)
        self.stepper.setInterval(self.CYCLE)
        self.stepper.timeout.connect(self.step)
        self.waiting = QtCore.QTimer(self)
        self.waiting.setSingleShot(True)
        self.waiting.timeout.connect(self.go_on)
        self.retell()

    def start_again(self) -> None:
        self.waiting.stop()
        self.game.restart()
        self.retell()

    def step(self) -> None:
        self.game.step()
        self.show_boxes()

    def touched(self, which: int) -> None:
        if self.game.done:
            self.press()
        elif self.game.answer(which) == ANSWERED:
            self.settled()

    def press(self, action: str = "") -> None:
        from .buttons import BACK
        if action == BACK:
            self.leave.emit()
            return
        if self.game.press() in (ANSWERED, AGAIN):
            self.settled()

    def settled(self) -> None:
        if self.game.locked:
            self.waiting.start(self.SHOWN)
        self.retell()

    def go_on(self) -> None:
        self.game.go_on()
        self.retell()

    def retell(self) -> None:
        t, game = self.win.t, self.game
        self.title.setText(t("qiblaquest.title"))
        self.map_note.setText("" if self.map.ready else t("qiblaquest.map_missing"))
        if game.done:
            self.where.setText("")
            self.city.setText("")
            self.question.setText(t("qiblaquest.done", score=game.score, of=game.rounds))
            self.said.setText(t("qiblaquest.again"))
        else:
            self.where.setText(t("corner.item", at=game.at + 1, of=game.rounds))
            named = t(f"qiblaquest.city.{game.round.city}")
            self.city.setText(named)
            self.question.setText(t("qiblaquest.question", city=named))
            if game.chosen is None:
                self.said.setText(t("qiblaquest.wait"))
            else:
                direction = t(f"qiblaquest.direction.{game.round.answer}")
                self.said.setText(t("qiblaquest.right" if game.right else "qiblaquest.wrong",
                                    direction=direction))
            self.map.set_point(game.round.point)
        self.show_boxes()

    def show_boxes(self) -> None:
        game = self.game
        for i, box in enumerate(self.boxes):
            if game.done:
                box.setText("")
                box.set_state(DirectionBox.IDLE)
                continue
            box.setText(self.win.t(f"qiblaquest.direction.{game.choices[i]}"))
            if not game.locked:
                box.set_state(DirectionBox.ACTIVE if i == game.active else DirectionBox.IDLE)
            elif i == game.correct:
                box.set_state(DirectionBox.RIGHT)
            elif i == game.chosen:
                box.set_state(DirectionBox.WRONG)
            else:
                box.set_state(DirectionBox.IDLE)

    def follow_theme(self) -> None:
        for box in self.boxes:
            box.update()
        self.map.update()
        self.update()

    def showEvent(self, event):
        self.stepper.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.stepper.stop()
        self.waiting.stop()
        super().hideEvent(event)
