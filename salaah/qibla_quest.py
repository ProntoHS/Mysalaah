"""Qibla Quest: choose the direction of Makkah from five cities.

The rules contain no Qt and no clock.  The screen supplies both, so the game can be played
thousands of times by the kit's fairness checker without a display.  Every round deals the
four compass choices afresh: no fixed ring press can learn the position of the answer.

THE 16-INCH IS THE MAP AND NOTHING ELSE; the words and the four choices are on the 7-inch
companion.  This game and Build the Salaah were the last two that never used the second screen
at all, which made them the odd ones out beside the jigsaw, the maze, Pillar Match and Prayer
Day.  The split follows the same rule as those: what you look at stays on the big screen, what
you read and press goes on the panel.  Prayer Day is the precedent for the answers themselves
moving -- its answers are words too.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette
from .winning import announce_if_won


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

    def __init__(self, window, on_side: bool = False):
        super().__init__()
        self.win = window
        #: MEASURED IN THE PANEL'S OWN PIXELS when it lives on the panel. window.px() scales by
        #: the MAIN screen's height; on a 1080x1920 panel beside a 1920x1200 display that makes
        #: every control about half the size it was drawn at, which is the thin strip of
        #: unreadable boxes Harry photographed in 2.00. The box paints itself, so a stylesheet
        #: cannot rescue it the way it rescues a QPushButton -- the scale has to be right here.
        self.on_side = on_side
        self.state = self.IDLE
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(self.px(88 if on_side else 105))

    def px(self, n: float) -> int:
        return self.win.side_px(n) if self.on_side else self.win.px(n)

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # INK AND NOT line FOR THE RESTING EDGE. line is #D9DCD6 on #FFFFFF paper, about
        # 1.2 to 1, which is no visible edge at all -- the same fault Prayer Day's answer
        # buttons had. It survived this long because these boxes were on the 16in, where the
        # test that measures edges does not look; on the panel they are measured, and they
        # should match the bordered controls on the other five panels anyway.
        edge, ink, thick = c.ink, c.ink, self.px(3)
        fill = QtGui.QColor(c.paper)
        if self.state == self.ACTIVE:
            edge, thick, fill = c.lapis, self.px(7), QtGui.QColor(c.pressed)
        elif self.state == self.RIGHT:
            edge, ink, thick, fill = c.green, c.green, self.px(7), QtGui.QColor(c.pressed)
        elif self.state == self.WRONG:
            edge, ink, thick = c.highlight, c.highlight, self.px(7)
        if self.isDown():
            fill = QtGui.QColor(c.pressed)
        box = QtCore.QRectF(self.rect()).adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        radius = self.px(18)
        p.setPen(QtGui.QPen(QtGui.QColor(edge), thick))
        p.setBrush(fill)
        p.drawRoundedRect(box, radius, radius)
        font = QtGui.QFont(Fonts.for_text(self.text()))
        font.setPixelSize(max(12, self.px(self.WORDS_PX)))
        font.setWeight(QtGui.QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QtGui.QColor(ink))
        p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.text())


class MapPanel(QtWidgets.QFrame):
    """Harry's map artwork with the current city and Makkah picked out on top.

    THE MAP TURNS OVER AFTER DARK, like every other drawing on this mat. Harry: "the qibla
    quest map is currently white background and black continents on dark theme but i want
    this reversed... easier on the eye in their respective themes".

    It is not a new convention, it is the one this app already has, and this screen was the
    one place not following it. journey_jigsaw._image sets out where the line is drawn: ship
    the light half and invert it for the dark screen works for LINE ART -- black ink on white
    paper, where the inverse really is the night version of the same drawing -- and not for
    pictures of real places, where it produces a photographic negative. A flat black
    silhouette of the continents on white paper is line art by that test, so it inverts.

    The reason it did not is mechanical rather than a decision: the postures go through
    window.images, a PixmapCache that scales, inverts for the dark palette and caches both
    versions. This loaded its own QPixmap and did all three itself, so it got none of them.
    Asking the cache instead is the fix, and it is the same call the postures make.
    """

    ART = "children/qibla-quest.png"

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.point = (0.5, 0.5)
        self.path = window.assets / "children" / "qibla-quest.png"
        #: Kept only to answer [ready]. What gets DRAWN comes from the cache below, so that the
        #: theme is applied by the one piece of code that knows how.
        self.map = QtGui.QPixmap(str(self.path))
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
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        if self.ready:
            shown = self.win.images.get(self.path, self.size())
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
    """The map on the 16in, with the question and the four answers on the 7in companion."""

    CYCLE = 1350
    SHOWN = 1900
    leave = Signal()
    won = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = QiblaQuest(shuffle)
        self.setObjectName("qiblaQuestScreen")

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(window.px(30), window.px(8), window.px(30), window.px(26))
        column.setSpacing(window.px(9))

        self.map = MapPanel(window)
        column.addWidget(self.map, 1)
        #: STAYS ON THE BIG SCREEN, where the missing artwork is. A note saying the map is not
        #: installed belongs beside the hole, not on the other screen.
        self.map_note = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.map_note.setObjectName("sourceNote")
        self.map_note.setWordWrap(True)
        column.addWidget(self.map_note)

        self.companion = self._build_companion()

        self.stepper = QtCore.QTimer(self)
        self.stepper.setInterval(self.CYCLE)
        self.stepper.timeout.connect(self.step)
        self.waiting = QtCore.QTimer(self)
        self.waiting.setSingleShot(True)
        self.waiting.timeout.connect(self.go_on)
        # STYLED HERE AND NOT LEFT TO THE FIRST THEME CHANGE. SideWindow.show_game calls
        # follow_theme on the COMPANION, and the companion is a bare QWidget -- the method is
        # on the screen. Without this the panel never gets its stylesheet, every label falls
        # through to the app-wide QWidget rule at the main screen's scale, and the panel is
        # the thin strip again. Pillar Match and the jigsaw both style themselves here; this
        # file did not, and the type-scale test caught it at 24px against 48.
        self.follow_theme()
        self.retell()

    def _build_companion(self):
        """The 7in panel: title, where we are, the city, the question, the four answers.

        Every button is a bare value with no label in front of it -- see the note in
        prayer_day_journey.retell. A button does not wrap, so a prefix is width the panel has
        to find in ten languages and the longest translation sets it for everybody.
        """
        panel = QtWidgets.QWidget()
        panel.setObjectName("qiblaQuestCompanion")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.side_px(20), self.win.side_px(18),
                                  self.win.side_px(20), self.win.side_px(18))
        layout.setSpacing(self.win.side_px(10))

        # NAMED, every one of them, or the stylesheet cannot size them: a label matching
        # neither #gameTitle nor #gameStatus falls through to the app-wide QWidget rule, which
        # is the MAIN screen's scale. That omission has now been found in two other games.
        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.where = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.where.setObjectName("gameStatus")
        layout.addWidget(self.where)

        self.city = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.city.setObjectName("gameCity")
        self.city.setWordWrap(True)
        layout.addWidget(self.city)

        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameStatus")
        self.question.setWordWrap(True)
        layout.addWidget(self.question)

        self.boxes: list[DirectionBox] = []
        for i in range(len(DIRECTIONS)):
            box = DirectionBox(self.win, on_side=True)
            box.clicked.connect(lambda _=False, n=i: self.touched(n))
            layout.addWidget(box, 1)
            self.boxes.append(box)

        self.said = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.said.setObjectName("gameStatus")
        self.said.setWordWrap(True)
        layout.addWidget(self.said)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(self.win.side_px(10))
        self.new_button = QtWidgets.QPushButton()
        self.new_button.setObjectName("controlButton")
        self.new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_button.setMinimumHeight(self.win.side_px(64))
        self.new_button.clicked.connect(self.start_again)
        controls.addWidget(self.new_button, 1)
        self.exit_button = QtWidgets.QPushButton()
        self.exit_button.setObjectName("controlButton")
        self.exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_button.setMinimumHeight(self.win.side_px(64))
        self.exit_button.clicked.connect(self.leave.emit)
        controls.addWidget(self.exit_button, 1)
        layout.addLayout(controls)
        return panel

    def _font(self, words, size, bold=False):
        """In the PANEL'S pixels. pillar_match sizes these in the main screen's and is saved
        by its stylesheet; sizing them right here means the two agree instead of one quietly
        overriding the other."""
        font = QtGui.QFont(Fonts.for_text(words))
        font.setPixelSize(max(12, self.win.side_px(size)))
        if bold:
            font.setWeight(QtGui.QFont.Weight.Bold)
        return font

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
        self.new_button.setText(t("qiblaquest.new_game"))
        self.exit_button.setText(t("qiblaquest.exit"))
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
                # NOTHING, where this used to say "wait for your answer to glow, then press
                # the ring". The answers are on a touchscreen now and that is how this is
                # played; the question is directly above the four boxes and says it already.
                # The glow and the ring both still work -- a ring press still answers whichever
                # box is lit -- so nothing has been taken away, but a child should not be told
                # to wait for a light when they can simply press the answer. Left blank rather
                # than reworded because a new sentence would be nine unreviewed translations.
                self.said.setText("")
            else:
                direction = t(f"qiblaquest.direction.{game.round.answer}")
                self.said.setText(t("qiblaquest.right" if game.right else "qiblaquest.wrong",
                                    direction=direction))
            self.map.set_point(game.round.point)
        self.title.setFont(self._font(self.title.text(), 40, True))
        self.where.setFont(self._font(self.where.text(), 22, True))
        self.city.setFont(self._font(self.city.text(), 32, True))
        self.question.setFont(self._font(self.question.text(), 26))
        self.said.setFont(self._font(self.said.text(), 24))
        self.new_button.setFont(self._font(self.new_button.text(), 28, True))
        self.exit_button.setFont(self._font(self.exit_button.text(), 28, True))
        self.show_boxes()
        # No `changed` signal in this file -- retell IS what runs after
        # every change, so the question is asked from here.
        self._look_for_a_win()

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
        c = palette()
        radius = self.win.side_px(11)
        edge = self.win.side_px(3)
        # TYPE SIZES IN THE PANEL'S OWN PIXELS, and paper AND ink rather than panel and paper.
        # Both of those have been got wrong twice in this app: a panel styled background:panel
        # with color:paper reads as black on #1C1C1C after dark, which measured 1.1 to 1, and
        # a button whose border is its own fill has no visible edge at all. paper and ink are
        # the one pair this palette guarantees to be opposites in both themes.
        title = self.win.side_px(40)
        body = self.win.side_px(26)
        city = self.win.side_px(32)
        label = self.win.side_px(28)
        self.companion.setStyleSheet(
            f"QWidget#qiblaQuestCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            f"QPushButton#controlButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; border-radius: {radius}px; }}"
            f"QPushButton#controlButton:pressed {{ background: {c.pressed}; color: {c.ink}; }}"
            f"QLabel#gameTitle {{ font-size: {title}px; font-weight: bold; }}"
            f"QLabel#gameCity {{ font-size: {city}px; font-weight: bold; }}"
            f"QLabel#gameStatus {{ font-size: {body}px; }}"
            f"QPushButton#controlButton {{ font-size: {label}px; font-weight: bold; }}")
        for box in self.boxes:
            box.update()
        self.map.update()
        self.retell()
        self.update()

    def showEvent(self, event):
        self.follow_theme()
        self.stepper.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.stepper.stop()
        self.waiting.stop()
        super().hideEvent(event)

    def _look_for_a_win(self) -> None:
        """Runs after every change. See salaah/winning.py for why it is once and not always."""
        announce_if_won(self, self.game.done)
