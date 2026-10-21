"""Kaaba Jigsaw: place nine picture pieces with touch or one ring button.

The first web prototype used drag and drop.  This version follows the mat's accessibility
contract: one piece is offered at a time, three plausible positions are dealt in a random
order, and the ring scans those positions.  A touch still chooses the position touched.
"""
from __future__ import annotations

import random

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette


# For each of the nine positions, two nearby positions that a child could plausibly confuse
# with it.  The choices are shuffled, but the wrong answers themselves are deliberate.
DISTRACTORS = (
    (1, 3), (0, 2), (1, 5),
    (0, 6), (1, 7), (2, 8),
    (3, 7), (4, 6), (5, 7),
)
ANSWERED, AGAIN, NOTHING = "answered", "again", "nothing"


class JigsawGame:
    """Rules for assembling a three-by-three picture, independent of Qt and time.

    TWO THINGS HERE ARE NOT THE OBVIOUS IMPLEMENTATION, and both are there because the obvious
    one could be won without looking at the picture.

    The pieces are offered in a SHUFFLED order.  Offered in reading order, as the first version
    did, the answer was always the next empty hole: 500 of 500 perfect games by a strategy that
    never looked at a piece.  `at` still counts the rounds -- the progress line and the board
    depend on that -- and `piece` says which piece is on offer.

    The wrong answers are drawn from cells that are still EMPTY wherever there are enough of
    them.  Offering a hole that visibly already has a piece in it is not a choice; it is a
    decoration, and it narrows three answers down to two for anybody who notices.
    """

    OFFERED = 3

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.order = list(range(len(DISTRACTORS)))
        self._shuffle(self.order)
        self.at = 0
        self.score = 0
        self.done = False
        self.placed: list[int] = []
        self.deal()

    @property
    def piece(self) -> int:
        """Which of the nine positions the piece now on offer belongs in."""
        return self.order[self.at]

    def deal(self) -> None:
        want = self.piece
        taken = set(self.placed) | {want}
        near = [n for n in DISTRACTORS[want] if n not in taken]
        far = [n for n in range(len(DISTRACTORS)) if n not in taken and n not in near]
        self._shuffle(far)
        full = [n for n in self.placed]
        self._shuffle(full)
        # Neighbours first because they are the plausible confusion, then any other empty
        # cell, and only once nothing is left over does a filled cell appear -- which happens
        # at the very end, when there is nowhere else for it to come from.
        pool = near + far + full
        picks = [want, *pool[:self.OFFERED - 1]]
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.locked = False
        self.chosen: int | None = None

    @property
    def rounds(self) -> int:
        return len(DISTRACTORS)

    @property
    def correct(self) -> int:
        return self.choices.index(self.piece)

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
        # The piece settles into its own place whether the answer was right or wrong, so the
        # picture always comes out whole. That is deliberate: a child who gets one wrong is
        # told so and still sees the Kaaba finished.
        self.placed.append(self.piece)
        if self.at + 1 >= self.rounds:
            self.done = True
            self.locked = False
            self.chosen = None
            return
        self.at += 1
        self.deal()


def piece_of(image, number: int):
    """Crop one of nine equal regions without requiring the artwork to divide exactly."""
    row, col = divmod(number, 3)
    x0 = int(col * image.width() / 3)
    x1 = int((col + 1) * image.width() / 3)
    y0 = int(row * image.height() / 3)
    y1 = int((row + 1) * image.height() / 3)
    return image.copy(x0, y0, max(1, x1 - x0), max(1, y1 - y0))


class PuzzleBoard(QtWidgets.QFrame):
    """The picture assembled one correctly placed piece at a time."""

    def __init__(self, window, image):
        super().__init__()
        self.win = window
        self.image = image
        self.placed: set[int] = set()
        self.setMinimumSize(window.px(430), window.px(430))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def set_placed(self, positions) -> None:
        """Which cells hold a piece. A SET of positions, not a count: the pieces arrive in a
        shuffled order, so the filled cells are not the first n."""
        self.placed = set(positions)
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        side = min(self.width(), self.height()) - self.win.px(10)
        left = (self.width() - side) // 2
        top = (self.height() - side) // 2
        cell = side / 3
        gap = self.win.px(3)
        for number in range(9):
            row, col = divmod(number, 3)
            target = QtCore.QRectF(left + col * cell + gap / 2,
                                   top + row * cell + gap / 2,
                                   cell - gap, cell - gap)
            here = number in self.placed
            p.setPen(QtGui.QPen(QtGui.QColor(c.line), self.win.px(2)))
            p.setBrush(QtGui.QColor(c.panel if here else c.paper))
            p.drawRect(target)
            if here and not self.image.isNull():
                tile = piece_of(self.image, number)
                p.drawPixmap(target, tile, QtCore.QRectF(tile.rect()))
        p.setPen(QtGui.QPen(QtGui.QColor(c.ink), self.win.px(4)))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRect(QtCore.QRectF(left, top, side, side))


class PiecePreview(QtWidgets.QFrame):
    def __init__(self, window, image):
        super().__init__()
        self.win = window
        self.image = image
        self.number = 0
        self.setMinimumSize(window.px(170), window.px(170))

    def set_piece(self, number: int) -> None:
        self.number = number
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        box = QtCore.QRectF(self.rect()).adjusted(self.win.px(5), self.win.px(5),
                                                  -self.win.px(5), -self.win.px(5))
        p.setPen(QtGui.QPen(QtGui.QColor(c.ink), self.win.px(4)))
        p.setBrush(QtGui.QColor(c.paper))
        p.drawRoundedRect(box, self.win.px(14), self.win.px(14))
        if not self.image.isNull():
            tile = piece_of(self.image, self.number)
            inner = box.adjusted(self.win.px(7), self.win.px(7),
                                 -self.win.px(7), -self.win.px(7))
            p.drawPixmap(inner, tile, QtCore.QRectF(tile.rect()))


class PositionBox(QtWidgets.QAbstractButton):
    IDLE, ACTIVE, RIGHT, WRONG = "idle", "active", "right", "wrong"

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.position = 0
        self.state = self.IDLE
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(122))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def show_position(self, position: int) -> None:
        self.position = position
        self.update()

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        edge, thick = c.line, self.win.px(3)
        fill = QtGui.QColor(c.paper)
        mark = c.ink
        if self.state == self.ACTIVE:
            edge, thick, fill = c.lapis, self.win.px(7), QtGui.QColor(c.pressed)
        elif self.state == self.RIGHT:
            edge, mark, thick, fill = c.green, c.green, self.win.px(7), QtGui.QColor(c.pressed)
        elif self.state == self.WRONG:
            edge, mark, thick = c.highlight, c.highlight, self.win.px(7)
        if self.isDown():
            fill = QtGui.QColor(c.pressed)
        outer = QtCore.QRectF(self.rect()).adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        p.setPen(QtGui.QPen(QtGui.QColor(edge), thick))
        p.setBrush(fill)
        p.drawRoundedRect(outer, self.win.px(16), self.win.px(16))

        side = min(outer.width(), outer.height()) * 0.72
        left = outer.center().x() - side / 2
        top = outer.center().y() - side / 2
        cell = side / 3
        p.setPen(QtGui.QPen(QtGui.QColor(c.ink), self.win.px(2)))
        for row in range(3):
            for col in range(3):
                square = QtCore.QRectF(left + col * cell, top + row * cell, cell, cell)
                p.setBrush(QtGui.QColor(mark) if row * 3 + col == self.position
                           else QtGui.QColor(c.paper))
                p.drawRect(square)


class KaabaJigsawScreen(QtWidgets.QWidget):
    """Accessible picture assembly: one piece, three positions, one ring button."""

    CYCLE = 1350
    SHOWN = 1750
    leave = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = JigsawGame(shuffle)
        self.image = QtGui.QPixmap(str(window.assets / "children" / "kaaba-jigsaw.png"))
        self.setObjectName("kaabaJigsawScreen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(window.px(28), window.px(8), window.px(28), window.px(26))
        outer.setSpacing(window.px(8))

        top = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignLeading)
        self.title.setObjectName("gameQuestion")
        self.where = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignTrailing)
        self.where.setObjectName("gameWhere")
        top.addWidget(self.title, 1)
        top.addWidget(self.where)
        outer.addLayout(top)

        middle = QtWidgets.QHBoxLayout()
        middle.setSpacing(window.px(24))
        self.board = PuzzleBoard(window, self.image)
        middle.addWidget(self.board, 3)
        side = QtWidgets.QVBoxLayout()
        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameQuestion")
        self.question.setWordWrap(True)
        side.addWidget(self.question)
        self.preview = PiecePreview(window, self.image)
        side.addWidget(self.preview, 1)
        self.asset_note = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.asset_note.setObjectName("sourceNote")
        self.asset_note.setWordWrap(True)
        side.addWidget(self.asset_note)
        middle.addLayout(side, 2)
        outer.addLayout(middle, 1)

        answers = QtWidgets.QHBoxLayout()
        answers.setSpacing(window.px(16))
        self.boxes: list[PositionBox] = []
        for i in range(3):
            box = PositionBox(window)
            box.clicked.connect(lambda _=False, n=i: self.touched(n))
            answers.addWidget(box, 1)
            self.boxes.append(box)
        outer.addLayout(answers)

        self.said = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.said.setObjectName("gameSaid")
        self.said.setWordWrap(True)
        outer.addWidget(self.said)

        self.stepper = QtCore.QTimer(self)
        self.stepper.setInterval(self.CYCLE)
        self.stepper.timeout.connect(self.step)
        self.waiting = QtCore.QTimer(self)
        self.waiting.setSingleShot(True)
        self.waiting.timeout.connect(self.go_on)
        self.retell()

    @property
    def ready(self) -> bool:
        """Whether the picture is on the mat.

        Without it this game is nine blank squares and a question about which blank square a
        blank square belongs in, so the children's menu leaves the tile off rather than
        offering it. Qibla Quest deliberately does NOT do this: its answers are compass words,
        so with no map it is a poorer game but still a game, and it says so on its own face.
        The difference is whether the picture IS the question.
        """
        return not self.image.isNull()

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
        self.title.setText(t("jigsaw.title"))
        self.asset_note.setText("" if not self.image.isNull() else t("jigsaw.image_missing"))
        if game.done:
            self.where.setText("")
            self.question.setText(t("jigsaw.done", score=game.score, of=game.rounds))
            self.said.setText(t("jigsaw.again"))
            self.board.set_placed(range(game.rounds))
        else:
            self.where.setText(t("corner.item", at=game.at + 1, of=game.rounds))
            self.question.setText(t("jigsaw.question"))
            self.preview.set_piece(game.piece)
            # The board shows the positions actually filled, not a count: once the pieces come
            # in a shuffled order, "the first n cells" is not where they went.
            self.board.set_placed(list(game.placed)
                                  + ([game.piece] if game.locked else []))
            if game.chosen is None:
                self.said.setText(t("jigsaw.wait"))
            else:
                self.said.setText(t("jigsaw.right" if game.right else "jigsaw.wrong"))
        self.show_boxes()

    def show_boxes(self) -> None:
        game = self.game
        for i, box in enumerate(self.boxes):
            if game.done:
                box.show_position(i)
                box.set_state(PositionBox.IDLE)
                continue
            box.show_position(game.choices[i])
            if not game.locked:
                box.set_state(PositionBox.ACTIVE if i == game.active else PositionBox.IDLE)
            elif i == game.correct:
                box.set_state(PositionBox.RIGHT)
            elif i == game.chosen:
                box.set_state(PositionBox.WRONG)
            else:
                box.set_state(PositionBox.IDLE)

    def follow_theme(self) -> None:
        self.board.update()
        self.preview.update()
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
