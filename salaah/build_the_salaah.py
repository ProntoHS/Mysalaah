"""Build the Salaah: put the broad postures of one rak'ah in order.

The game reuses the mat's existing faceless posture pictures.  One step is built at a time;
three plausible postures are shuffled underneath it, so touch can choose directly and the
single Bluetooth-ring button can choose whichever answer is currently lit.

This is an ordering aid, not an exhaustive lesson in the rulings or words of prayer.  The
sequence and every translation remain explicitly subject to qualified review before release.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


@dataclass(frozen=True)
class Round:
    answer: str
    others: tuple[str, str]


ROUNDS = (
    Round("stand", ("bow", "prostrate")),
    Round("bow", ("stand", "prostrate")),
    Round("stand_upright", ("sit", "prostrate")),
    Round("prostrate", ("bow", "sit")),
    Round("sit", ("stand", "prostrate_again")),
    Round("prostrate_again", ("stand", "bow")),
)
ANSWERED, AGAIN, NOTHING = "answered", "again", "nothing"


def asset_for(action: str) -> str:
    """The picture for each posture, from the mat's own set.

    THE NAMES THIS ARRIVED WITH WERE NOT ON THE MAT. It asked for postures/standing.png and
    postures/sitting.png; the mat has neither, so three of the six rounds drew an empty box with
    a word under it and every checker passed -- a game cannot crash on a picture that is not
    there, it just stops being a game. tools/check_game_art.py now reads the names out of the
    source and looks for them.

    And the mat has BETTER artwork than this assumed. It arrived reusing one standing picture
    for both standing rounds, which would have shown the same drawing for two different
    answers in a game whose whole subject is which comes next. There is a separate drawing for
    each:

      stand           qiyam, the opening stand, arms folded
      stand_upright   i'tidal, standing up again after the bow -- a different drawing, and the
                      one round where telling the two stands apart is the question
      sit             jalsa, the sit between the two prostrations, which is this game's round 5
                      (NOT tashahhud, the sitting at the end -- that is not in one rak'ah's
                      broad postures as this game counts them)
    """
    return {"stand": "postures/standing_folded.png",
            "stand_upright": "postures/standing_itidal.png",
            "bow": "postures/ruku.png",
            "prostrate": "postures/sujood.png",
            "prostrate_again": "postures/sujood.png",
            "sit": "postures/jalsa.png"}[action]


class SalaahBuilder:
    """Rules only: no Qt, time, filesystem or input-device knowledge."""

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.at = 0
        self.score = 0
        self.done = False
        self.deal()

    def deal(self) -> None:
        here = ROUNDS[self.at]
        picks = [here.answer, *here.others]
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.locked = False
        self.chosen: int | None = None

    @property
    def round(self) -> Round:
        return ROUNDS[self.at]

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


class SequenceStrip(QtWidgets.QFrame):
    """Six calm slots that fill from left to right as the rak'ah is built."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.filled = 0
        self.setMinimumHeight(window.px(185))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def set_filled(self, count: int) -> None:
        self.filled = count
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        gap = self.win.px(10)
        total = self.width() - gap * (len(ROUNDS) + 1)
        card_w = max(1, total / len(ROUNDS))
        top = self.win.px(8)
        bottom = self.height() - self.win.px(8)
        for number, round_ in enumerate(ROUNDS):
            x = gap + number * (card_w + gap)
            box = QtCore.QRectF(x, top, card_w, bottom - top)
            p.setPen(QtGui.QPen(QtGui.QColor(c.ink if number < self.filled else c.line),
                                self.win.px(3)))
            p.setBrush(QtGui.QColor(c.paper))
            p.drawRoundedRect(box, self.win.px(12), self.win.px(12))
            if number < self.filled:
                inner = QtCore.QSize(max(1, int(box.width() - self.win.px(18))),
                                     max(1, int(box.height() - self.win.px(18))))
                pix = self.win.images.get(self.win.picture(asset_for(round_.answer)), inner)
                if not pix.isNull():
                    px = int(box.center().x() - pix.width() / 2)
                    py = int(box.bottom() - self.win.px(9) - pix.height())
                    p.drawPixmap(px, py, pix)


class PostureBox(QtWidgets.QAbstractButton):
    IDLE, ACTIVE, RIGHT, WRONG = "idle", "active", "right", "wrong"
    WORDS_PX = 31

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.action = "stand"
        self.state = self.IDLE
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(220))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def show_action(self, action: str, words: str) -> None:
        self.action = action
        self.setText(words)
        self.update()

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
        p.setPen(QtGui.QPen(QtGui.QColor(edge), thick))
        p.setBrush(fill)
        p.drawRoundedRect(box, self.win.px(17), self.win.px(17))

        label_h = self.win.px(62)
        picture = QtCore.QRectF(box.left() + self.win.px(12), box.top() + self.win.px(10),
                                box.width() - self.win.px(24), box.height() - label_h - self.win.px(20))
        target = QtCore.QSize(max(1, int(picture.width())), max(1, int(picture.height())))
        pix = self.win.images.get(self.win.picture(asset_for(self.action)), target)
        if not pix.isNull():
            px = int(picture.center().x() - pix.width() / 2)
            py = int(picture.bottom() - pix.height())
            p.drawPixmap(px, py, pix)

        font = QtGui.QFont(Fonts.for_text(self.text()))
        font.setPixelSize(max(12, self.win.px(self.WORDS_PX)))
        font.setWeight(QtGui.QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QtGui.QColor(ink))
        words = QtCore.QRectF(box.left() + self.win.px(7), box.bottom() - label_h,
                             box.width() - self.win.px(14), label_h)
        p.drawText(words, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.text())


class BuildTheSalaahScreen(QtWidgets.QWidget):
    """The complete game screen, driven by touch or the host's existing ring action."""

    CYCLE = 1350
    SHOWN = 1800
    leave = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = SalaahBuilder(shuffle)
        self.setObjectName("buildTheSalaahScreen")

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(window.px(28), window.px(8), window.px(28), window.px(26))
        column.setSpacing(window.px(9))

        top = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignLeading)
        self.title.setObjectName("gameQuestion")
        self.where = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignTrailing)
        self.where.setObjectName("gameWhere")
        top.addWidget(self.title, 1)
        top.addWidget(self.where)
        column.addLayout(top)

        self.sequence = SequenceStrip(window)
        column.addWidget(self.sequence, 1)

        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameQuestion")
        self.question.setWordWrap(True)
        column.addWidget(self.question)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(window.px(16))
        self.boxes: list[PostureBox] = []
        for i in range(3):
            box = PostureBox(window)
            box.clicked.connect(lambda _=False, n=i: self.touched(n))
            row.addWidget(box, 1)
            self.boxes.append(box)
        column.addLayout(row, 2)

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
        self.title.setText(t("builder.title"))
        if game.done:
            self.where.setText("")
            self.question.setText(t("builder.done", score=game.score, of=game.rounds))
            self.said.setText(t("builder.again"))
            self.sequence.set_filled(game.rounds)
        else:
            self.where.setText(t("corner.item", at=game.at + 1, of=game.rounds))
            self.question.setText(t("builder.question"))
            self.sequence.set_filled(game.at + (1 if game.locked else 0))
            if game.chosen is None:
                self.said.setText(t("builder.wait"))
            else:
                named = t(f"builder.action.{game.round.answer}")
                self.said.setText(t("builder.right" if game.right else "builder.wrong",
                                    posture=named))
        self.show_boxes()

    def show_boxes(self) -> None:
        game = self.game
        for i, box in enumerate(self.boxes):
            if game.done:
                box.setText("")
                box.set_state(PostureBox.IDLE)
                continue
            action = game.choices[i]
            box.show_action(action, self.win.t(f"builder.action.{action}"))
            if not game.locked:
                box.set_state(PostureBox.ACTIVE if i == game.active else PostureBox.IDLE)
            elif i == game.correct:
                box.set_state(PostureBox.RIGHT)
            elif i == game.chosen:
                box.set_state(PostureBox.WRONG)
            else:
                box.set_state(PostureBox.IDLE)

    def follow_theme(self) -> None:
        self.sequence.update()
        for box in self.boxes:
            box.update()
        self.update()

    def showEvent(self, event):
        self.stepper.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.stepper.stop()
        self.waiting.stop()
        super().hideEvent(event)
