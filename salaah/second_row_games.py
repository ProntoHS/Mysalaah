"""Six small MySalaah Children games for the second launcher row.

Every game uses the same tested three-choice rules: direct touch chooses a card, while the
Bluetooth ring chooses whichever card is currently lit.  Artwork is geometric, monochrome,
face-free and drawn at runtime from the active palette.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


@dataclass(frozen=True)
class Round:
    answer: str
    others: tuple[str, str]
    prompt: str


@dataclass(frozen=True)
class GameSpec:
    game_id: str
    title_key: str
    question_key: str
    rounds: tuple[Round, ...]


GAME_SPECS = (
    GameSpec("charity", "six.title.charity", "six.question.charity", (
        Round("3", ("2", "4"), "3"), Round("5", ("4", "6"), "5"),
        Round("2", ("1", "3"), "2"), Round("6", ("5", "7"), "6"),
        Round("4", ("3", "5"), "4"),
    )),
    GameSpec("manners", "six.title.manners", "six.question.manners", (
        Round("quiet", ("shout", "phone"), "mosque"),
        Round("shoes", ("litter", "run"), "mosque"),
        Round("clean", ("litter", "shout"), "mosque"),
        Round("walk", ("run", "phone"), "mosque"),
        Round("read", ("shout", "litter"), "mosque"),
    )),
    GameSpec("ramadan", "six.title.ramadan", "six.question.ramadan", (
        Round("4", ("3", "5"), "1,2,3,_"), Round("8", ("7", "9"), "5,6,7,_"),
        Round("12", ("11", "13"), "9,10,11,_"), Round("20", ("19", "21"), "17,18,19,_"),
        Round("30", ("28", "29"), "27,28,29,_"),
    )),
    GameSpec("arabic", "six.title.arabic", "six.question.arabic", (
        Round("ا", ("ب", "ت"), "ا"), Round("ب", ("ت", "ث"), "ب"),
        Round("ت", ("ب", "ث"), "ت"), Round("ج", ("ح", "خ"), "ج"),
        Round("د", ("ذ", "ر"), "د"),
    )),
    GameSpec("tasbih", "six.title.tasbih", "six.question.tasbih", (
        Round("7", ("6", "8"), "7"), Round("9", ("8", "10"), "9"),
        Round("10", ("9", "11"), "10"), Round("12", ("11", "13"), "12"),
        Round("15", ("14", "16"), "15"),
    )),
    GameSpec("pattern", "six.title.pattern", "six.question.pattern", (
        Round("circle", ("square", "triangle"), "circle,square,circle,_"),
        Round("triangle", ("circle", "diamond"), "triangle,diamond,triangle,_"),
        Round("square", ("triangle", "circle"), "square,circle,square,_"),
        Round("diamond", ("square", "circle"), "diamond,triangle,diamond,_"),
        Round("circle", ("triangle", "diamond"), "circle,circle,diamond,circle,circle,_"),
    )),
)
CHARITY, MANNERS, RAMADAN, ARABIC, TASBIH, PATTERN = GAME_SPECS
ANSWERED, AGAIN, NOTHING = "answered", "again", "nothing"


class ChoiceGame:
    """Shared rules only: no Qt, clock, files or device knowledge."""

    def __init__(self, rounds=None, shuffle=None):
        self.items = tuple(rounds if rounds is not None else CHARITY.rounds)
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        # THE QUESTIONS COME IN A SHUFFLED ORDER. These six are independent questions -- which
        # letter is this, how many coins, what comes next in the pattern -- so the order they
        # are asked in teaches nothing, and left fixed it meant one playthrough taught the
        # whole answer sequence by heart. tools/check_lazy.py scored 5.00 of 5 and 400 perfect
        # games out of 400 by replaying the answers from memory, which is exactly the hole
        # Qibla Quest arrived with.
        #
        # Build the Salaah and the Five Pillars Sorter deliberately do NOT do this. There the
        # order IS the lesson -- the postures of a rak'ah, the five pillars in sequence -- and
        # each question names its own position, so answering from position and answering from
        # knowledge are the same act. Same measurement, opposite meaning.
        self.order = list(range(len(self.items)))
        self._shuffle(self.order)
        self.at = 0
        self.score = 0
        self.done = False
        self.deal()

    def deal(self) -> None:
        here = self.round
        picks = [here.answer, *here.others]
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.chosen: int | None = None
        self.locked = False

    @property
    def rounds(self) -> int:
        return len(self.items)

    @property
    def round(self) -> Round:
        return self.items[self.order[self.at]]

    @property
    def correct(self) -> int:
        return self.choices.index(self.round.answer)

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
        if self.at + 1 >= self.rounds:
            self.done = True
            self.locked = False
            self.chosen = None
            return
        self.at += 1
        self.deal()


class MiniArt:
    @staticmethod
    def font(window, words: str, size: int, bold=True):
        font = QtGui.QFont(Fonts.for_text(words))
        font.setPixelSize(max(12, window.px(size)))
        if bold:
            font.setWeight(QtGui.QFont.Weight.Bold)
        return font

    @staticmethod
    def text(p, window, rect, words: str, size: int, ink: str) -> None:
        p.setFont(MiniArt.font(window, words, size))
        p.setPen(QtGui.QColor(ink))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), words)

    @staticmethod
    def coin_box(p, window, rect, count: int, ink: str, paper: str) -> None:
        line = max(2, window.px(4))
        p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
        p.setBrush(QtGui.QColor(ink))
        box = QtCore.QRectF(rect.left() + rect.width() * .18, rect.top() + rect.height() * .48,
                            rect.width() * .64, rect.height() * .38)
        p.drawRoundedRect(box, window.px(9), window.px(9))
        p.setPen(QtGui.QPen(QtGui.QColor(paper), line))
        p.drawLine(QtCore.QPointF(box.center().x() - box.width() * .18, box.top() + box.height() * .18),
                   QtCore.QPointF(box.center().x() + box.width() * .18, box.top() + box.height() * .18))
        p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
        p.setBrush(QtGui.QColor(paper))
        radius = min(rect.width() * .055, rect.height() * .07)
        cols = min(5, count)
        for index in range(count):
            row, col = divmod(index, cols)
            x = rect.center().x() + (col - (cols - 1) / 2) * radius * 2.8
            y = rect.top() + rect.height() * .20 + row * radius * 2.7
            p.drawEllipse(QtCore.QRectF(x - radius, y - radius, radius * 2, radius * 2))

    @staticmethod
    def calendar(p, window, rect, number: str, ink: str, paper: str) -> None:
        line = max(2, window.px(5))
        p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
        p.setBrush(Qt.BrushStyle.NoBrush)
        box = rect.adjusted(rect.width() * .18, rect.height() * .09,
                            -rect.width() * .18, -rect.height() * .08)
        p.drawRoundedRect(box, window.px(10), window.px(10))
        p.drawLine(QtCore.QPointF(box.left(), box.top() + box.height() * .23),
                   QtCore.QPointF(box.right(), box.top() + box.height() * .23))
        for x in (.28, .72):
            p.drawLine(QtCore.QPointF(box.left() + box.width() * x, box.top() - window.px(7)),
                       QtCore.QPointF(box.left() + box.width() * x, box.top() + window.px(11)))
        MiniArt.text(p, window, QtCore.QRectF(box.left(), box.top() + box.height() * .20,
                                             box.width(), box.height() * .78), number, 58, ink)

    @staticmethod
    def beads(p, window, rect, count: int, ink: str) -> None:
        line = max(2, window.px(3))
        p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
        p.setBrush(QtGui.QColor(ink))
        center = rect.center()
        rx, ry = rect.width() * .32, rect.height() * .34
        for index in range(count):
            angle = math.pi * .12 + math.pi * 1.76 * index / max(1, count - 1)
            x = center.x() + rx * math.cos(angle)
            y = center.y() - ry * math.sin(angle)
            radius = min(rect.width(), rect.height()) * .036
            p.drawEllipse(QtCore.QRectF(x - radius, y - radius, radius * 2, radius * 2))
        p.drawLine(QtCore.QPointF(center.x(), center.y() + ry * .92),
                   QtCore.QPointF(center.x(), center.y() + ry * 1.25))
        p.drawEllipse(QtCore.QRectF(center.x() - window.px(6), center.y() + ry * 1.19,
                                    window.px(12), window.px(20)))

    @staticmethod
    def shape(p, window, rect, name: str, ink: str) -> None:
        p.setPen(QtGui.QPen(QtGui.QColor(ink), max(2, window.px(5))))
        p.setBrush(QtGui.QColor(ink))
        cx, cy = rect.center().x(), rect.center().y()
        radius = min(rect.width(), rect.height()) * .25
        if name == "circle":
            p.drawEllipse(QtCore.QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        elif name == "square":
            p.drawRect(QtCore.QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        elif name == "triangle":
            p.drawPolygon(QtGui.QPolygonF([
                QtCore.QPointF(cx, cy - radius), QtCore.QPointF(cx + radius, cy + radius),
                QtCore.QPointF(cx - radius, cy + radius)]))
        else:
            p.drawPolygon(QtGui.QPolygonF([
                QtCore.QPointF(cx, cy - radius), QtCore.QPointF(cx + radius, cy),
                QtCore.QPointF(cx, cy + radius), QtCore.QPointF(cx - radius, cy)]))

    @staticmethod
    def mosque(p, window, rect, ink: str, paper: str) -> None:
        p.setPen(QtGui.QPen(QtGui.QColor(ink), max(2, window.px(4))))
        p.setBrush(QtGui.QColor(ink))
        cx, cy, w, h = rect.center().x(), rect.center().y(), rect.width(), rect.height()
        p.drawRect(QtCore.QRectF(cx - w * .30, cy, w * .60, h * .25))
        p.drawEllipse(QtCore.QRectF(cx - w * .30, cy - h * .25, w * .60, h * .45))
        p.drawRect(QtCore.QRectF(cx - w * .43, cy - h * .18, w * .10, h * .43))
        p.drawRect(QtCore.QRectF(cx + w * .33, cy - h * .18, w * .10, h * .43))
        p.setBrush(QtGui.QColor(paper))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QtCore.QRectF(cx - w * .07, cy + h * .09, w * .14, h * .16),
                          w * .05, w * .05)

    @staticmethod
    def manners(p, window, rect, value: str, ink: str, paper: str) -> None:
        line = max(2, window.px(4))
        p.setPen(QtGui.QPen(QtGui.QColor(ink), line))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy, w, h = rect.center().x(), rect.center().y(), rect.width(), rect.height()
        if value in ("quiet", "shout"):
            bubble = QtCore.QRectF(cx - w * .28, cy - h * .24, w * .56, h * .38)
            p.drawRoundedRect(bubble, window.px(12), window.px(12))
            p.drawLine(QtCore.QPointF(cx + w * .10, bubble.bottom()),
                       QtCore.QPointF(cx + w * .20, cy + h * .28))
            if value == "quiet":
                for dx in (-.10, 0, .10):
                    p.setBrush(QtGui.QColor(ink))
                    p.drawEllipse(QtCore.QRectF(cx + w * dx - window.px(4), cy - window.px(4),
                                                window.px(8), window.px(8)))
            else:
                p.setPen(QtGui.QPen(QtGui.QColor(ink), line * 2))
                p.drawLine(QtCore.QPointF(cx - w * .12, cy), QtCore.QPointF(cx + w * .12, cy))
                for dy in (-.18, 0, .18):
                    p.drawLine(QtCore.QPointF(cx + w * .34, cy + h * dy),
                               QtCore.QPointF(cx + w * .45, cy + h * dy * 1.25))
        elif value == "phone":
            p.drawRoundedRect(QtCore.QRectF(cx - w * .16, cy - h * .35, w * .32, h * .70),
                              window.px(10), window.px(10))
            for factor in (.26, .36, .46):
                p.drawArc(QtCore.QRectF(cx + w * .02, cy - h * factor,
                                        w * factor, h * factor * 2), -70 * 16, 140 * 16)
        elif value in ("shoes", "walk", "run"):
            slope = .12 if value == "run" else 0
            for index in range(2):
                x = cx + (index * 2 - 1) * w * .16
                y = cy + (index * 2 - 1) * h * slope
                p.setBrush(QtGui.QColor(ink))
                p.drawEllipse(QtCore.QRectF(x - w * .09, y - h * .24, w * .18, h * .34))
                p.drawEllipse(QtCore.QRectF(x - w * .06, y + h * .14, w * .12, h * .14))
            if value == "shoes":
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(QtCore.QRectF(cx - w * .36, cy - h * .36, w * .72, h * .75),
                                  window.px(9), window.px(9))
            elif value == "run":
                for dy in (-.20, 0, .20):
                    p.drawLine(QtCore.QPointF(cx - w * .42, cy + h * dy),
                               QtCore.QPointF(cx - w * .29, cy + h * dy))
        elif value in ("clean", "litter"):
            if value == "clean":
                p.drawLine(QtCore.QPointF(cx - w * .25, cy - h * .34),
                           QtCore.QPointF(cx + w * .12, cy + h * .28))
                p.setBrush(QtGui.QColor(ink))
                p.drawPolygon(QtGui.QPolygonF([
                    QtCore.QPointF(cx + w * .03, cy + h * .13),
                    QtCore.QPointF(cx + w * .33, cy + h * .20),
                    QtCore.QPointF(cx + w * .22, cy + h * .39)]))
            else:
                p.setBrush(QtGui.QColor(ink))
                for dx, dy in ((-.22, -.10), (.10, -.22), (.25, .15), (-.10, .24)):
                    p.drawRect(QtCore.QRectF(cx + w * dx, cy + h * dy, w * .10, h * .10))
        else:  # read
            p.setBrush(Qt.BrushStyle.NoBrush)
            left = QtCore.QRectF(cx - w * .35, cy - h * .25, w * .34, h * .50)
            right = QtCore.QRectF(cx + w * .01, cy - h * .25, w * .34, h * .50)
            p.drawRoundedRect(left, window.px(7), window.px(7))
            p.drawRoundedRect(right, window.px(7), window.px(7))
            p.drawLine(QtCore.QPointF(cx, cy - h * .22), QtCore.QPointF(cx, cy + h * .27))

    @staticmethod
    def choice(p, window, game_id: str, value: str, rect, ink: str, paper: str) -> None:
        if game_id == "charity":
            MiniArt.coin_box(p, window, rect, int(value), ink, paper)
        elif game_id == "manners":
            MiniArt.manners(p, window, rect, value, ink, paper)
        elif game_id == "ramadan":
            MiniArt.calendar(p, window, rect, value, ink, paper)
        elif game_id == "arabic":
            MiniArt.text(p, window, rect, value, 96, ink)
        elif game_id == "tasbih":
            MiniArt.beads(p, window, rect, int(value), ink)
        else:
            MiniArt.shape(p, window, rect, value, ink)

    @staticmethod
    def prompt(p, window, spec: GameSpec, round_: Round, rect, ink: str, paper: str) -> None:
        if spec.game_id in ("charity", "tasbih"):
            MiniArt.text(p, window, rect, round_.prompt, 76, ink)
        elif spec.game_id == "manners":
            MiniArt.mosque(p, window, rect, ink, paper)
        elif spec.game_id == "arabic":
            MiniArt.text(p, window, rect, round_.prompt, 94, ink)
        elif spec.game_id == "ramadan":
            MiniArt.text(p, window, rect, round_.prompt.replace(",", "   "), 49, ink)
        else:
            names = round_.prompt.split(",")
            piece_w = rect.width() / len(names)
            for index, name in enumerate(names):
                area = QtCore.QRectF(rect.left() + index * piece_w, rect.top(), piece_w, rect.height())
                if name == "_":
                    p.setPen(QtGui.QPen(QtGui.QColor(ink), max(2, window.px(4)), Qt.PenStyle.DashLine))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(area.adjusted(window.px(15), window.px(15),
                                                    -window.px(15), -window.px(15)),
                                      window.px(8), window.px(8))
                else:
                    MiniArt.shape(p, window, area, name, ink)


class PromptPanel(QtWidgets.QFrame):
    def __init__(self, window, spec):
        super().__init__()
        self.win, self.spec = window, spec
        self.round = spec.rounds[0]
        self.setMinimumHeight(window.px(180))

    def show_round(self, round_: Round) -> None:
        self.round = round_
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        box = QtCore.QRectF(self.rect()).adjusted(self.win.px(4), self.win.px(4),
                                                  -self.win.px(4), -self.win.px(4))
        p.setPen(QtGui.QPen(QtGui.QColor(c.line), self.win.px(3)))
        p.setBrush(QtGui.QColor(c.paper))
        p.drawRoundedRect(box, self.win.px(15), self.win.px(15))
        MiniArt.prompt(p, self.win, self.spec, self.round,
                       box.adjusted(self.win.px(20), self.win.px(14),
                                    -self.win.px(20), -self.win.px(14)), c.ink, c.paper)


class ChoiceCard(QtWidgets.QAbstractButton):
    IDLE, ACTIVE, RIGHT, WRONG = "idle", "active", "right", "wrong"

    def __init__(self, window, game_id):
        super().__init__()
        self.win, self.game_id = window, game_id
        self.value, self.state = "1", self.IDLE
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(250))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def show_choice(self, value: str) -> None:
        self.value = value
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
        MiniArt.choice(p, self.win, self.game_id, self.value,
                       box.adjusted(self.win.px(18), self.win.px(12),
                                    -self.win.px(18), -self.win.px(12)), ink, c.paper)


class MiniGameScreen(QtWidgets.QWidget):
    CYCLE = 1350
    SHOWN = 1700
    leave = Signal()

    def __init__(self, window, spec, shuffle=None):
        super().__init__()
        self.win, self.spec = window, spec
        self.game = ChoiceGame(spec.rounds, shuffle)
        self.setObjectName(f"{spec.game_id}GameScreen")
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
        self.prompt = PromptPanel(window, spec)
        column.addWidget(self.prompt, 1)
        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameQuestion")
        self.question.setWordWrap(True)
        column.addWidget(self.question)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(window.px(16))
        self.boxes: list[ChoiceCard] = []
        for index in range(3):
            box = ChoiceCard(window, spec.game_id)
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
        self.title.setText(t(self.spec.title_key))
        if game.done:
            self.where.setText("")
            self.prompt.hide()
            self.question.setText(t("six.done", score=game.score, of=game.rounds))
            self.said.setText(t("six.again"))
        else:
            self.prompt.show()
            self.prompt.show_round(game.round)
            self.where.setText(t("corner.item", at=game.at + 1, of=game.rounds))
            if self.spec.game_id in ("charity", "tasbih"):
                self.question.setText(t(self.spec.question_key, number=game.round.prompt))
            elif self.spec.game_id == "arabic":
                self.question.setText(t(self.spec.question_key, letter=game.round.prompt))
            else:
                self.question.setText(t(self.spec.question_key))
            if game.chosen is None:
                self.said.setText(t("six.wait"))
            else:
                self.said.setText(t("six.right" if game.right else "six.wrong"))
        self.show_boxes()

    def show_boxes(self) -> None:
        game = self.game
        for index, box in enumerate(self.boxes):
            if game.done:
                box.set_state(ChoiceCard.IDLE)
                continue
            box.show_choice(game.choices[index])
            if not game.locked:
                box.set_state(ChoiceCard.ACTIVE if index == game.active else ChoiceCard.IDLE)
            elif index == game.correct:
                box.set_state(ChoiceCard.RIGHT)
            elif index == game.chosen:
                box.set_state(ChoiceCard.WRONG)
            else:
                box.set_state(ChoiceCard.IDLE)

    def follow_theme(self) -> None:
        self.prompt.update()
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


class CharityCounterScreen(MiniGameScreen):
    _qt_marker = QtWidgets.QWidget

    def __init__(self, window, shuffle=None):
        super().__init__(window, CHARITY, shuffle)


class MosqueMannersScreen(MiniGameScreen):
    _qt_marker = QtWidgets.QWidget

    def __init__(self, window, shuffle=None):
        super().__init__(window, MANNERS, shuffle)


class RamadanCalendarScreen(MiniGameScreen):
    _qt_marker = QtWidgets.QWidget

    def __init__(self, window, shuffle=None):
        super().__init__(window, RAMADAN, shuffle)


class ArabicLetterMatchScreen(MiniGameScreen):
    _qt_marker = QtWidgets.QWidget

    def __init__(self, window, shuffle=None):
        super().__init__(window, ARABIC, shuffle)


class TasbihCounterScreen(MiniGameScreen):
    _qt_marker = QtWidgets.QWidget

    def __init__(self, window, shuffle=None):
        super().__init__(window, TASBIH, shuffle)


class IslamicPatternBuilderScreen(MiniGameScreen):
    _qt_marker = QtWidgets.QWidget

    def __init__(self, window, shuffle=None):
        super().__init__(window, PATTERN, shuffle)
