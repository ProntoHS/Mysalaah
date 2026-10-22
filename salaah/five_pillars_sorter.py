"""Five Pillars Sorter: build the commonly taught sequence of Islam's five pillars.

The rules are independent of Qt so the game kit can play thousands of rounds without a
display.  The screen draws its own restrained black-and-white icons and supports both direct
touch and the existing one-button Bluetooth-ring scan.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


@dataclass(frozen=True)
class Pillar:
    key: str


PILLARS = (
    Pillar("faith"),
    Pillar("prayer"),
    Pillar("charity"),
    Pillar("fasting"),
    Pillar("hajj"),
)
ANSWERED, AGAIN, NOTHING = "answered", "again", "nothing"


class PillarSorter:
    """Rules only: no Qt, time, files or input-device knowledge."""

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.at = 0
        self.score = 0
        self.done = False
        self.deal()

    def deal(self) -> None:
        answer = PILLARS[self.at].key
        distractors = [pillar.key for pillar in PILLARS if pillar.key != answer]
        self._shuffle(distractors)
        picks = [answer, *distractors[:2]]
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.locked = False
        self.chosen: int | None = None

    @property
    def rounds(self) -> int:
        return len(PILLARS)

    @property
    def answer_key(self) -> str:
        return PILLARS[self.at].key

    @property
    def correct(self) -> int:
        return self.choices.index(self.answer_key)

    @property
    def right(self) -> bool | None:
        return None if self.chosen is None else self.chosen == self.correct

    def step(self) -> None:
        if not (self.locked or self.done):
            self.active = (self.active + 1) % len(self.choices)

    def answer(self, which: int) -> str:
        if self.done or self.locked or not 0 <= which < len(self.choices):
            return NOTHING
        self.active = which
        self.chosen = which
        self.locked = True
        if self.right:
            self.score += 1
        return ANSWERED

    def press(self) -> str:
        if self.done:
            self.restart()
            return AGAIN
        return self.answer(self.active)

    def go_on(self) -> None:
        if not self.locked:
            return
        if self.at + 1 >= len(PILLARS):
            self.done = True
            self.locked = False
            self.chosen = None
            return
        self.at += 1
        self.deal()


class PillarArt:
    """Small geometric icons using only the live palette."""

    @staticmethod
    def draw(painter, key: str, rect, window, ink: str, paper: str) -> None:
        p = painter
        p.save()
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        line = max(2, window.px(4))
        p.setPen(QtGui.QPen(QtGui.QColor(ink), line,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QtGui.QColor(ink))
        cx, cy = rect.center().x(), rect.center().y()
        w, h = rect.width(), rect.height()

        if key == "faith":
            # A mosque arch and crescent: an uncluttered visual shorthand for faith.
            body = QtCore.QRectF(cx - w * .29, cy - h * .08, w * .58, h * .42)
            p.drawRect(body)
            p.drawEllipse(QtCore.QRectF(cx - w * .29, cy - h * .32, w * .58, h * .48))
            p.setBrush(QtGui.QColor(paper))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QtCore.QRectF(cx - w * .08, cy + h * .08, w * .16, h * .27),
                              w * .07, w * .07)
            p.setBrush(QtGui.QColor(ink))
            p.drawEllipse(QtCore.QRectF(cx - w * .07, cy - h * .47, w * .21, w * .21))
            p.setBrush(QtGui.QColor(paper))
            p.drawEllipse(QtCore.QRectF(cx - w * .01, cy - h * .49, w * .20, w * .20))

        elif key == "prayer":
            p.setBrush(Qt.BrushStyle.NoBrush)
            mat = QtCore.QRectF(cx - w * .31, cy - h * .38, w * .62, h * .70)
            p.drawRoundedRect(mat, w * .04, w * .04)
            arch = QtGui.QPainterPath()
            arch.moveTo(cx - w * .17, cy + h * .18)
            arch.lineTo(cx - w * .17, cy - h * .10)
            arch.quadTo(cx, cy - h * .34, cx + w * .17, cy - h * .10)
            arch.lineTo(cx + w * .17, cy + h * .18)
            p.drawPath(arch)
            for offset in (-.22, -.11, 0, .11, .22):
                p.drawLine(QtCore.QPointF(cx + w * offset, cy + h * .32),
                           QtCore.QPointF(cx + w * offset, cy + h * .42))

        elif key == "charity":
            box = QtCore.QRectF(cx - w * .34, cy - h * .13, w * .68, h * .45)
            p.drawRoundedRect(box, w * .05, w * .05)
            p.setPen(QtGui.QPen(QtGui.QColor(paper), line))
            p.drawLine(QtCore.QPointF(cx - w * .13, cy - h * .01),
                       QtCore.QPointF(cx + w * .13, cy - h * .01))
            p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
            for x, y in ((-.20, -.35), (.04, -.45), (.25, -.30)):
                p.setBrush(QtGui.QColor(paper))
                p.drawEllipse(QtCore.QRectF(cx + w * x - w * .055, cy + h * y - w * .055,
                                            w * .11, w * .11))

        elif key == "fasting":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QtCore.QRectF(cx - w * .27, cy - h * .05, w * .54, h * .34))
            p.drawArc(QtCore.QRectF(cx - w * .36, cy + h * .12, w * .72, h * .22), 200 * 16, 140 * 16)
            p.setBrush(QtGui.QColor(ink))
            p.drawEllipse(QtCore.QRectF(cx - w * .21, cy - h * .43, w * .30, w * .30))
            p.setBrush(QtGui.QColor(paper))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QtCore.QRectF(cx - w * .12, cy - h * .46, w * .30, w * .30))
            p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
            for dx in (-.12, 0, .12):
                p.drawLine(QtCore.QPointF(cx + w * dx, cy - h * .05),
                           QtCore.QPointF(cx + w * dx, cy - h * .18))

        else:  # hajj
            top = (QtCore.QPointF(cx - w * .28, cy - h * .22),
                   QtCore.QPointF(cx, cy - h * .36),
                   QtCore.QPointF(cx + w * .28, cy - h * .22),
                   QtCore.QPointF(cx, cy - h * .07))
            left = (top[0], top[3], QtCore.QPointF(cx, cy + h * .35),
                    QtCore.QPointF(cx - w * .28, cy + h * .18))
            right = (top[3], top[2], QtCore.QPointF(cx + w * .28, cy + h * .18),
                     QtCore.QPointF(cx, cy + h * .35))
            p.drawPolygon(QtGui.QPolygonF(list(top)))
            p.drawPolygon(QtGui.QPolygonF(list(left)))
            p.drawPolygon(QtGui.QPolygonF(list(right)))
            p.setPen(QtGui.QPen(QtGui.QColor(paper), line))
            p.drawLine(QtCore.QPointF(cx - w * .27, cy - h * .09),
                       QtCore.QPointF(cx, cy + h * .06))
            p.drawLine(QtCore.QPointF(cx, cy + h * .06),
                       QtCore.QPointF(cx + w * .27, cy - h * .09))
        p.restore()


class SortedStrip(QtWidgets.QFrame):
    def __init__(self, window):
        super().__init__()
        self.win = window
        self.filled = 0
        self.setMinimumHeight(window.px(190))
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
        gap = self.win.px(12)
        total = self.width() - gap * 6
        card_w = max(1, total / 5)
        for index, pillar in enumerate(PILLARS):
            x = gap + index * (card_w + gap)
            box = QtCore.QRectF(x, self.win.px(8), card_w, self.height() - self.win.px(16))
            edge = c.ink if index < self.filled else c.line
            p.setPen(QtGui.QPen(QtGui.QColor(edge), self.win.px(3)))
            p.setBrush(QtGui.QColor(c.paper))
            p.drawRoundedRect(box, self.win.px(12), self.win.px(12))
            number = QtCore.QRectF(box.left(), box.top() + self.win.px(5),
                                   box.width(), self.win.px(38))
            font = QtGui.QFont(Fonts.for_text(str(index + 1)))
            font.setPixelSize(max(12, self.win.px(25)))
            font.setWeight(QtGui.QFont.Weight.Bold)
            p.setFont(font)
            p.setPen(QtGui.QColor(edge))
            p.drawText(number, int(Qt.AlignmentFlag.AlignCenter), str(index + 1))
            if index < self.filled:
                art = QtCore.QRectF(box.left() + self.win.px(15), number.bottom(),
                                    box.width() - self.win.px(30),
                                    box.height() - number.height() - self.win.px(12))
                PillarArt.draw(p, pillar.key, art, self.win, c.ink, c.paper)


class PillarChoice(QtWidgets.QAbstractButton):
    IDLE, ACTIVE, RIGHT, WRONG = "idle", "active", "right", "wrong"

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.key = "faith"
        self.state = self.IDLE
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(225))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def show_pillar(self, key: str, text: str) -> None:
        self.key = key
        self.setText(text)
        self.update()

    def set_state(self, state: str) -> None:
        if self.state != state:
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
        label_h = self.win.px(65)
        art = QtCore.QRectF(box.left() + self.win.px(25), box.top() + self.win.px(10),
                            box.width() - self.win.px(50), box.height() - label_h - self.win.px(18))
        PillarArt.draw(p, self.key, art, self.win, ink, c.paper)
        font = QtGui.QFont(Fonts.for_text(self.text()))
        font.setPixelSize(max(12, self.win.px(31)))
        font.setWeight(QtGui.QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QtGui.QColor(ink))
        words = QtCore.QRectF(box.left() + self.win.px(8), box.bottom() - label_h,
                             box.width() - self.win.px(16), label_h)
        p.drawText(words, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.text())


class FivePillarsSorterScreen(QtWidgets.QWidget):
    CYCLE = 1350
    SHOWN = 1800
    leave = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = PillarSorter(shuffle)
        self.setObjectName("fivePillarsSorterScreen")
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

        self.sorted = SortedStrip(window)
        column.addWidget(self.sorted, 1)
        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameQuestion")
        self.question.setWordWrap(True)
        column.addWidget(self.question)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(window.px(16))
        self.boxes: list[PillarChoice] = []
        for index in range(3):
            box = PillarChoice(window)
            box.clicked.connect(lambda _=False, choice=index: self.touched(choice))
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
        self.title.setText(t("pillars.title"))
        if game.done:
            self.where.setText("")
            self.question.setText(t("pillars.done", score=game.score, of=game.rounds))
            self.said.setText(t("pillars.again"))
            self.sorted.set_filled(game.rounds)
        else:
            number = game.at + 1
            self.where.setText(t("corner.item", at=number, of=game.rounds))
            self.question.setText(t("pillars.question", number=number))
            self.sorted.set_filled(number if game.locked else game.at)
            if game.chosen is None:
                self.said.setText(t("pillars.wait"))
            else:
                named = t(f"pillars.name.{game.answer_key}")
                self.said.setText(t("pillars.right" if game.right else "pillars.wrong",
                                    number=number, pillar=named))
        self.show_boxes()

    def show_boxes(self) -> None:
        game = self.game
        for index, box in enumerate(self.boxes):
            if game.done:
                box.setText("")
                box.set_state(PillarChoice.IDLE)
                continue
            key = game.choices[index]
            box.show_pillar(key, self.win.t(f"pillars.name.{key}"))
            if not game.locked:
                box.set_state(PillarChoice.ACTIVE if index == game.active else PillarChoice.IDLE)
            elif index == game.correct:
                box.set_state(PillarChoice.RIGHT)
            elif index == game.chosen:
                box.set_state(PillarChoice.WRONG)
            else:
                box.set_state(PillarChoice.IDLE)

    def follow_theme(self) -> None:
        self.sorted.update()
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
