"""The prayer-time game: which of the five prayers belongs to which part of the day.

Harry had this built as a separate program -- a little web server and two Chromium windows
driven by the Bluetooth ring, meant to sit beside the mat. It could not run beside this one.
The mat runs labwc, and that program places its two windows by pixel position, which is an X11
thing a Wayland client is not allowed to do; and worse, both it and salaah/buttons.py take an
EXCLUSIVE grab of the ring, so whichever started first would have had it and the other would
have sat there receiving nothing. So the rules came across and the program did not.

Coming across was worth doing for more than the ring. Here it speaks every language the mat
speaks, borrows the mosque Harry drew -- with the sun, the moon and the stars already in it --
and arrives inside the signed release instead of needing Chromium installed underneath it.

ONE THING WAS CHANGED RATHER THAN COPIED. In the original the three answers were written out
in a fixed order, and the right one was the second box in four rounds out of five: a child who
pressed on the second glow every time scored four out of five having learnt nothing. The
choices are dealt in a random order here, so the only way to score is to know.

The rules are in Game and nothing in Game knows about Qt or about time passing. A quiz whose
rules can only be exercised by waiting 1.35 seconds for a highlight to move is a quiz that
cannot really be tested, and the things worth being sure of -- that the answer is where it
says it is, that a late press cannot change a locked answer, that five rounds end -- are all
questions about the rules.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .mosque import MosqueScreen
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


@dataclass(frozen=True)
class Round:
    """One question: a time of day, the prayer that belongs to it, and two that do not.

    The two wrong answers are the ones the original chose, kept as they were. They are not
    random: each is a prayer a child might plausibly reach for at that hour, which is what
    makes the question worth asking, and a pair drawn at random would sometimes offer three
    that nobody would confuse.
    """
    when: str                      # dawn, midday, afternoon, sunset, night
    answer: str                    # the prayer.* key of the right answer
    others: tuple[str, str]        # the two wrong ones
    sun_up: bool                   # whether the sky shows the sun or the moon
    through: float                 # how far across the sky it has travelled, 0 to 1


# Five rounds, in the order of a day. The sky positions are the same ones mosque.py draws from
# on the front door, so dawn here looks like dawn there -- the point of the game is that the
# picture a child sees while answering is the picture they see on the mat every morning.
ROUNDS = (
    Round("dawn", "fajr", ("maghrib", "asr"), sun_up=True, through=0.06),
    Round("midday", "dhuhr", ("maghrib", "fajr"), sun_up=True, through=0.50),
    Round("afternoon", "asr", ("isha", "fajr"), sun_up=True, through=0.78),
    Round("sunset", "maghrib", ("dhuhr", "isha"), sun_up=True, through=0.97),
    Round("night", "isha", ("asr", "fajr"), sun_up=False, through=0.45),
)

ANSWERED, AGAIN, NOTHING = "answered", "again", "nothing"


class Game:
    """The rules. No Qt, no clock: the screen above it supplies both."""

    def __init__(self, shuffle=None):
        # Taken as an argument so a test can deal a known hand. Left alone it is random, which
        # is the whole of the fix to the second-box problem described at the top.
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    # Starting, and starting again

    def restart(self) -> None:
        self.at = 0
        self.score = 0
        self.done = False
        self.deal()

    def deal(self) -> None:
        """Lay out the three answers for the round we are on, in an order nobody can predict."""
        here = ROUNDS[self.at]
        picks = [here.answer, *here.others]
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.locked = False
        self.chosen: int | None = None

    # Where we are

    @property
    def round(self) -> Round:
        return ROUNDS[self.at]

    @property
    def rounds(self) -> int:
        return len(ROUNDS)

    @property
    def correct(self) -> int:
        """Which box holds the right answer this time."""
        return self.choices.index(self.round.answer)

    @property
    def right(self) -> bool | None:
        """Whether the answer given was right, or None while none has been given."""
        return None if self.chosen is None else self.chosen == self.correct

    # What can be done

    def step(self) -> None:
        """Move the highlight on. Does nothing once an answer is locked in, so the box being
        shown as right or wrong is still the box that was pressed."""
        if not (self.locked or self.done):
            self.active = (self.active + 1) % len(self.choices)

    def press(self) -> str:
        """A press on the ring: answer with whatever is lit, or start again when it is over."""
        if self.done:
            self.restart()
            return AGAIN
        return self.answer(self.active)

    def answer(self, which: int) -> str:
        """Lock in one of the three. A touch names its own box; the ring names the lit one."""
        if self.done or self.locked or not 0 <= which < len(self.choices):
            return NOTHING
        self.active = which
        self.chosen = which
        self.locked = True
        if self.right:
            self.score += 1
        return ANSWERED

    def go_on(self) -> None:
        """On to the next round, once the answer has been left on screen long enough to read.

        Only ever from a locked round, so a stray call cannot skip a question that has not
        been answered -- the screen drives this off a one-shot timer started by the answer.
        """
        if not self.locked:
            return
        if self.at + 1 >= len(ROUNDS):
            self.done = True
            self.locked = False
            self.chosen = None
            return
        self.at += 1
        self.deal()


class AnswerBox(QtWidgets.QAbstractButton):
    """One of the three answers, painted rather than styled.

    Painted for the reason knowledge.Tile is: a stylesheet button draws its own frame and
    background, and this has four appearances -- waiting, lit, right and wrong -- which have to
    read across a room in both themes. Doing it here means the colours come from the palette
    the rest of the mat uses rather than from a second set written into a stylesheet.
    """

    IDLE, ACTIVE, RIGHT, WRONG = "idle", "active", "right", "wrong"
    # Named rather than written into paintEvent, because a test measures the three answers in
    # nine languages against the width of their boxes and has to ask for the same size the
    # screen draws at. Two copies of a number is two numbers.
    WORDS_PX = 46

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.state = self.IDLE
        self.setObjectName("answerBox")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(window.px(96))

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
        said = self.text()
        if not said:
            return
        font = QtGui.QFont(Fonts.for_text(said))
        font.setPixelSize(max(12, self.win.px(self.WORDS_PX)))
        font.setWeight(QtGui.QFont.Weight(700))
        p.setFont(font)
        p.setPen(QtGui.QColor(ink))
        p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), said)


class GameScreen(QtWidgets.QWidget):
    """The game as the mat shows it: the sky above, the question and three answers below.

    The highlight steps along on its own and a press takes whatever it is on. That is what
    makes the game playable with one button, which is the whole point of it on a mat -- a
    child wearing the ring never has to reach the screen. Touching an answer works too, for
    anyone close enough, and names its own box rather than the lit one.

    Both timers are stopped the moment the screen is hidden. A quiz left stepping behind the
    screen somebody is actually reading is the Pi doing work for nobody, which is the same
    rule filmsheet.py follows for its films.
    """

    CYCLE = 1350        # how long the highlight rests on each answer, in milliseconds
    SHOWN = 1800        # how long an answer is left up before the next question

    leave = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = Game(shuffle)
        self.setObjectName("gameScreen")

        column = QtWidgets.QVBoxLayout(self)
        # A deeper margin at the foot than the head. The line under the boxes is the one that
        # says whether you were right, and at px(16) it sat on the very edge of the screen.
        column.setContentsMargins(window.px(24), window.px(8), window.px(24), window.px(30))
        column.setSpacing(window.px(10))

        # Harry's own mosque, pointed at the same folder the front door uses, so the game is
        # played under the drawing a child already knows and in the language the mat is set
        # to. Its arches are not connected to anything here: they are the picture, and the
        # answer is given in the boxes below. The one time an arch does anything is the
        # reveal -- the right prayer lights up the moment the answer is locked in.
        self.mosque = MosqueScreen(window.assets, Fonts.english_family, idle_glow=False,
                                   lang=window.settings.lang, rtl=window.pack.rtl)
        if self.mosque.ready:
            column.addWidget(self.mosque, 1)
        else:
            self.mosque.deleteLater()
            self.mosque = None

        self.where = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.where.setObjectName("gameWhere")
        column.addWidget(self.where)

        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameQuestion")
        self.question.setWordWrap(True)
        column.addWidget(self.question)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(window.px(18))
        self.boxes: list[AnswerBox] = []
        for i in range(len(ROUNDS[0].others) + 1):
            box = AnswerBox(window)
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

    # Playing

    def start_again(self) -> None:
        """Back to round one. What opening the game from the menu does, so a game left
        half-played a week ago is not what a child walks up to."""
        self.waiting.stop()
        self.game.restart()
        self.retell()

    def step(self) -> None:
        self.game.step()
        self.show_boxes()

    def touched(self, which: int) -> None:
        """A finger on one of the three. It answers with the box touched, not the lit one."""
        if self.game.done:
            self.press()
            return
        if self.game.answer(which) == ANSWERED:
            self.settled()

    def press(self, action: str = "") -> None:
        """The ring, or a key standing in for it. Whatever is lit is the answer."""
        from .buttons import BACK
        if action == BACK:
            self.leave.emit()
            return
        if self.game.press() in (ANSWERED, AGAIN):
            self.settled()

    def settled(self) -> None:
        """An answer has been locked in, or the game has been started again."""
        if self.game.locked:
            self.waiting.start(self.SHOWN)
        self.retell()

    def go_on(self) -> None:
        self.game.go_on()
        self.retell()

    # Saying it

    def retell(self) -> None:
        """Write the whole screen out of the rules. Everything that shows state goes through
        here, so there is one place where what is on screen is decided and no way for the
        boxes and the words below them to disagree."""
        t = self.win.t
        game = self.game
        if game.done:
            self.where.setText("")
            self.question.setText(t("game.title"))
            self.said.setText(t("game.done", score=game.score, of=game.rounds))
        else:
            self.where.setText(t("corner.item", at=game.at + 1, of=game.rounds))
            self.question.setText(t("game.question", when=t(f"game.when.{game.round.when}")))
            if game.chosen is None:
                self.said.setText(t("game.wait"))
            else:
                named = t(f"prayer.{game.round.answer}")
                self.said.setText(t("game.right" if game.right else "game.wrong", prayer=named))
        self.show_boxes()
        self.show_sky()

    def show_boxes(self) -> None:
        game = self.game
        for i, box in enumerate(self.boxes):
            if game.done:
                box.setText("")
                box.set_state(AnswerBox.IDLE)
                continue
            box.setText(self.win.t(f"prayer.{game.choices[i]}"))
            if not game.locked:
                box.set_state(AnswerBox.ACTIVE if i == game.active else AnswerBox.IDLE)
            elif i == game.correct:
                box.set_state(AnswerBox.RIGHT)
            elif i == game.chosen:
                box.set_state(AnswerBox.WRONG)
            else:
                box.set_state(AnswerBox.IDLE)

    def show_sky(self) -> None:
        """The sun or the moon where that round's prayer falls, and the arch lit once the
        answer is in. Lit only after answering: an arch glowing while the question is up would
        be the picture answering it."""
        if self.mosque is None:
            return
        if self.game.done:
            self.mosque.set_lit(None)
            return
        self.mosque.set_sky(self.game.round.sun_up, self.game.round.through)
        self.mosque.set_lit(self.game.round.answer if self.game.locked else None)

    # Housekeeping

    def follow_theme(self) -> None:
        for box in self.boxes:
            box.update()
        self.update()

    def showEvent(self, ev):
        self.stepper.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        self.stepper.stop()
        self.waiting.stop()
        super().hideEvent(ev)
