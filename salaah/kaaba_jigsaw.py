"""Kaaba Jigsaw: nine pieces on the board at once, moved by touch.

WHAT CHANGED IN 1.94, and why. Until 1.93 this screen offered ONE piece at a time and three
places it might go, and the ring button scanned those three. That shape came from the mat's
accessibility contract, and it was the right answer while the ring was the only way in. It is
the wrong answer now that both screens take touch: a single button can only choose by cycling,
cycling is the slow part, and a game whose whole input is "wait, then press" is a quiz about
patience rather than a jigsaw.

So the pieces are all on the board from the start, shuffled, and a child moves them by touching
them -- tap one and then another to swap the two, or drag one onto another. That is the whole
vocabulary. There is nothing to wait for.

THE RING IS NOT LOCKED OUT. It scans the nine cells and presses to pick, which is the same
two-step swap by a slower road. It is kept because a child who cannot reach or see the screen
well should still be able to play, not because it is the way the game is meant to be played.

WHAT IS DELIBERATELY NOT HERE.

No per-piece "this one is home" glow while the puzzle is being built. It is the obvious kindness
and it hands the game away: a bot that swaps a cell against each of the others and keeps
whatever turns green wins 300 games out of 300, in a median of 32 swaps, having never looked at
the picture. That is the same fault the 1.93 version was built to avoid, wearing a new costume.

THE COUNT ON THE 7" SCREEN IS A SMALLER HOLE IN THE SAME WALL, and saying so is more use than
pretending otherwise. A bot told only how many pieces are home, never which, still wins about
296 games in 300 -- but it needs a median of 125 swaps to do it, four times the cost, and far
past what a child does by accident while a picture is sitting in front of them. The count stays
because a child needs to see that they are getting closer; what it buys an exploiter is a slow
road, not a free one. Both figures hold across four seeds, and they are nailed down by
tests/test_ui.py, test_a_blind_player_pays_four_times_over_for_the_count. With no feedback at
all the same bot wins once in 500, which is what the picture is for.

No completion chime. The web prototype synthesised one with a WebAudio oscillator, and a
synthesised tone ships no file, so the licence guard would not have minded. It is left out
because this screen has no sound of its own anywhere else and one noise in one game is a
surprise rather than a reward.

NO NEW WORDS. Every string this screen says was already in all ten language packs before 1.94:
jigsaw.title, jigsaw.question, jigsaw.again, jigsaw.image_missing, and corner.item for the
count. That is not thrift, it is the only way this screen could ship. The mat's own test,
test_every_string_the_games_ask_for_exists_in_every_pack, refuses a game that asks for a string
some pack has not got, and it is right to: the alternative is a child reading one English
sentence in the middle of a Bengali screen. Two newly written lines went in and came straight
back out when that test caught them, because the honest way to add a word here is to have
somebody who speaks the language write it, not to have it written by whoever is nearest.
"Where does this piece belong?" is as true of swapping two pieces as it was of placing one.
"""
from __future__ import annotations

import random

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

SIDE = 3
PIECES = SIDE * SIDE

SWAPPED, PICKED, CLEARED, NOTHING = "swapped", "picked", "cleared", "nothing"


class JigsawGame:
    """The rules, free of Qt and of time, so they can be played by a test without a screen.

    `order` is the board: order[where] is the number of the piece sitting in cell `where`. A
    piece is home when order[where] == where, and the puzzle is done when every piece is.
    """

    #: How many pieces a fresh board must have out of place. Eight, not nine: a derangement
    #: of nine is not always reachable by the shuffle, but a board with two pieces already
    #: home is a board a child has been given a third of the answer to.
    MIXED = 8

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.order = list(range(PIECES))
        for _ in range(40):
            self._shuffle(self.order)
            if self.away >= self.MIXED:
                break
        self.moves = 0
        self.picked: int | None = None

    # Reading the board

    @property
    def away(self) -> int:
        return sum(1 for where, piece in enumerate(self.order) if piece != where)

    @property
    def home(self) -> int:
        return PIECES - self.away

    @property
    def done(self) -> bool:
        return self.away == 0

    def piece_at(self, where: int) -> int:
        return self.order[where]

    def is_home(self, where: int) -> bool:
        return self.order[where] == where

    # Playing

    def touch(self, where: int) -> str:
        """One touch on one cell. Two touches make a swap.

        Touching the picked cell again puts it down rather than swapping it with itself, which
        would otherwise spend a move and change nothing.
        """
        if self.done or not 0 <= where < PIECES:
            return NOTHING
        if self.picked is None:
            self.picked = where
            return PICKED
        if self.picked == where:
            self.picked = None
            return CLEARED
        self.swap(self.picked, where)
        self.picked = None
        return SWAPPED

    def swap(self, one: int, two: int) -> bool:
        """Exchange the pieces in two cells. Used by a drag, and by the second touch."""
        if self.done or one == two:
            return False
        if not (0 <= one < PIECES and 0 <= two < PIECES):
            return False
        self.order[one], self.order[two] = self.order[two], self.order[one]
        self.moves += 1
        return True


def piece_of(image, number: int):
    """Crop one of nine equal regions without requiring the artwork to divide exactly."""
    row, col = divmod(number, SIDE)
    x0 = int(col * image.width() / SIDE)
    x1 = int((col + 1) * image.width() / SIDE)
    y0 = int(row * image.height() / SIDE)
    y1 = int((row + 1) * image.height() / SIDE)
    return image.copy(x0, y0, max(1, x1 - x0), max(1, y1 - y0))


class JigsawBoard(QtWidgets.QFrame):
    """The nine cells. Owns the touching, and knows nothing about what a swap means."""

    touched = Signal(int)
    dragged = Signal(int, int)

    def __init__(self, window, image, game):
        super().__init__()
        self.win = window
        self.image = image
        self.game = game
        self.scanning: int | None = None     # the ring's cursor, None when the ring is idle
        self._from: int | None = None
        self._at = QtCore.QPoint()
        self.setMinimumSize(window.px(430), window.px(430))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

    # Geometry. One function, so the painting and the hit testing cannot disagree -- they did
    # in the web prototype, where the picture was laid out by one rule and cut by another.

    def square(self) -> QtCore.QRectF:
        side = min(self.width(), self.height()) - self.win.px(10)
        return QtCore.QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

    def cell_rect(self, where: int) -> QtCore.QRectF:
        box = self.square()
        cell = box.width() / SIDE
        row, col = divmod(where, SIDE)
        return QtCore.QRectF(box.left() + col * cell, box.top() + row * cell, cell, cell)

    def cell_at(self, point) -> int | None:
        for where in range(PIECES):
            if self.cell_rect(where).contains(QtCore.QPointF(point)):
                return where
        return None

    # Touch

    def mousePressEvent(self, event):
        where = self.cell_at(event.position() if hasattr(event, "position") else event.pos())
        if where is not None:
            self._from = where
            self._at = (event.position().toPoint() if hasattr(event, "position")
                        else event.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        start, self._from = self._from, None
        if start is None:
            return super().mouseReleaseEvent(event)
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        where = self.cell_at(point)
        moved = (point - self._at).manhattanLength() > self.win.px(18)
        if where is not None and moved and where != start:
            self.dragged.emit(start, where)        # a drag: straight to a swap
        elif where is not None:
            self.touched.emit(where)               # a tap: one half of a swap
        super().mouseReleaseEvent(event)

    # Painting

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        if self.game.done and not self.image.isNull():
            # Drawn as ONE picture, not as nine pieces that happen to touch. Nine abutting
            # QRectFs leave hairlines along the joins wherever the board's width does not
            # divide by three, and a finished jigsaw with faint lines across it still looks
            # like a jigsaw. This is the moment it stops being one.
            p.drawPixmap(self.square(), self.image, QtCore.QRectF(self.image.rect()))
            p.setPen(QtGui.QPen(QtGui.QColor(c.green), self.win.px(4)))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRect(self.square())
            return
        gap = self.win.px(3)
        for where in range(PIECES):
            box = self.cell_rect(where).adjusted(gap / 2, gap / 2, -gap / 2, -gap / 2)
            p.setBrush(QtGui.QColor(c.panel))
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.drawRect(box)
            if not self.image.isNull():
                tile = piece_of(self.image, self.game.piece_at(where))
                p.drawPixmap(box, tile, QtCore.QRectF(tile.rect()))
            # The picked piece and the ring's cursor are the only marks on a piece. Nothing
            # says "this one is home": see the note at the top of this file.
            if where == self.game.picked:
                p.setPen(QtGui.QPen(QtGui.QColor(c.lapis), self.win.px(7)))
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawRect(box.adjusted(self.win.px(3), self.win.px(3),
                                        -self.win.px(3), -self.win.px(3)))
            elif where == self.scanning:
                p.setPen(QtGui.QPen(QtGui.QColor(c.ink), self.win.px(4),
                                    QtCore.Qt.PenStyle.DashLine))
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawRect(box.adjusted(self.win.px(3), self.win.px(3),
                                        -self.win.px(3), -self.win.px(3)))
        edge = c.green if self.game.done else c.ink
        p.setPen(QtGui.QPen(QtGui.QColor(edge), self.win.px(4)))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRect(self.square())


class JigsawHint(QtWidgets.QWidget):
    """What the 7" screen shows while the jigsaw is open: the finished picture and how close.

    The picture is the whole point of it being there. A child building a jigsaw needs to see
    what it is meant to become, and on a single screen that means covering part of the board
    with a thumbnail or hiding it behind a button. The second screen was carrying a standing
    figure and nothing else while this game was on, so it was free.
    """

    def __init__(self, window, image, standalone=True):
        super().__init__()
        self.win = window
        self.image = image
        self.home = 0
        # On the 7" this IS the screen, so it says what it is and how far along the child is.
        # In the main screen's margin it is a picture beside a board that already carries both,
        # and repeating them there just prints the title twice.
        self.standalone = standalone
        self.setObjectName("jigsawHint")
        self.setAutoFillBackground(True)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(window.px(16), window.px(20), window.px(16), window.px(20))
        column.setSpacing(window.px(14))

        self.heading = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.heading.setObjectName("gameQuestion")
        self.heading.setWordWrap(True)
        column.addWidget(self.heading)

        self.picture = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.picture.setMinimumHeight(window.px(260))
        self.picture.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                   QtWidgets.QSizePolicy.Policy.Expanding)
        column.addWidget(self.picture, 1)

        self.count = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.count.setObjectName("gameSaid")
        self.count.setWordWrap(True)
        column.addWidget(self.count)
        # No trailing stretch. The web prototype had the equivalent and left the bottom 45% of
        # the 7" black, which is the same waste this screen was built to stop.

    def set_home(self, home: int) -> None:
        self.home = home
        self.retell()

    def retell(self) -> None:
        t = self.win.t
        self.heading.setText(t("jigsaw.title") if self.standalone else "")
        self.heading.setVisible(self.standalone)
        self.count.setText(t("corner.item", at=self.home, of=PIECES) if self.standalone else "")
        self.count.setVisible(self.standalone)
        self.redraw()

    def redraw(self) -> None:
        if self.image.isNull():
            self.picture.setText(self.win.t("jigsaw.image_missing"))
            return
        side = max(self.win.px(120), min(self.picture.width(), self.picture.height()))
        self.picture.setPixmap(self.image.scaled(
            side, side, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def follow_theme(self) -> None:
        self.setStyleSheet(self.win.stylesheet())
        self.update()

    def resizeEvent(self, event):
        self.redraw()
        super().resizeEvent(event)


class KaabaJigsawScreen(QtWidgets.QWidget):
    """Nine pieces, moved by touch; the 7" screen carries the picture and the count."""

    CYCLE = 1100          # how fast the ring's cursor walks the cells
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

        # The board is square and the screen is not, so on a 16:9 panel a board sized to the
        # height leaves about 420 px spare on each side. That margin carries the picture when
        # there is no 7" screen to carry it -- A MAT WITH ONE SCREEN MUST STILL SHOW THE CHILD
        # WHAT THEY ARE BUILDING. Moving the hint to the second screen and stopping there would
        # have quietly taken the reference picture away from every single-screen mat.
        middle = QtWidgets.QHBoxLayout()
        middle.setSpacing(window.px(18))
        self.board = JigsawBoard(window, self.image, self.game)
        self.board.touched.connect(self.touch)
        self.board.dragged.connect(self.drag)
        self.inline = JigsawHint(window, self.image, standalone=False)
        self.inline.setMaximumWidth(window.px(380))
        middle.addStretch(1)
        middle.addWidget(self.board, 6)
        middle.addWidget(self.inline, 3)
        outer.addLayout(middle, 1)

        self.said = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.said.setObjectName("gameSaid")
        self.said.setWordWrap(True)
        outer.addWidget(self.said)

        self.asset_note = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.asset_note.setObjectName("sourceNote")
        self.asset_note.setWordWrap(True)
        outer.addWidget(self.asset_note)

        # Only runs while the ring is being used: see press().
        self.stepper = QtCore.QTimer(self)
        self.stepper.setInterval(self.CYCLE)
        self.stepper.timeout.connect(self.step)
        self.hint: JigsawHint | None = None
        self.retell()

    @property
    def ready(self) -> bool:
        """Whether the picture is on the mat.

        Without it this game is nine blank squares to shuffle into a different blank square,
        so the children's menu leaves the tile off rather than offering it. Qibla Quest
        deliberately does NOT do this: its answers are compass words, so with no map it is a
        poorer game but still a game. The difference is whether the picture IS the question.
        """
        return not self.image.isNull()

    def start_again(self) -> None:
        self.game.restart()
        self.board.scanning = None
        self.stepper.stop()
        self.retell()

    # Touch

    def touch(self, where: int) -> None:
        if self.game.done:
            self.start_again()
            return
        self.game.touch(where)
        self.retell()

    def drag(self, start: int, end: int) -> None:
        if self.game.done:
            return
        self.game.picked = None
        self.game.swap(start, end)
        self.retell()

    # The ring, kept as a way in rather than as the way in

    def press(self, action: str = "") -> None:
        from .buttons import BACK
        if action == BACK:
            self.leave.emit()
            return
        if self.game.done:
            self.start_again()
            return
        if self.board.scanning is None:          # first press wakes the cursor up
            self.board.scanning = 0
            self.stepper.start()
        else:
            self.game.touch(self.board.scanning)
        self.retell()

    def step(self) -> None:
        if self.board.scanning is None or self.game.done:
            return
        self.board.scanning = (self.board.scanning + 1) % PIECES
        self.board.update()

    # Saying where things are

    def retell(self) -> None:
        t, game = self.win.t, self.game
        self.title.setText(t("jigsaw.title"))
        self.asset_note.setText("" if not self.image.isNull() else t("jigsaw.image_missing"))
        self.where.setText(t("corner.item", at=game.home, of=PIECES))
        if game.done:
            self.said.setText(t("jigsaw.again"))
            self.stepper.stop()
            self.board.scanning = None
        else:
            self.said.setText(t("jigsaw.question"))
        self.board.update()
        for panel in (self.hint, self.inline):
            if panel is not None:
                panel.set_home(game.home)

    def follow_theme(self) -> None:
        self.board.update()
        for panel in (self.hint, self.inline):
            if panel is not None:
                panel.follow_theme()
        self.update()

    # Coming and going. The 7" screen is lent to this game while it is open and given back
    # afterwards, so leaving by any road -- the ring, the tile, a language change -- puts the
    # posture figure back rather than stranding a jigsaw hint on it.

    def showEvent(self, event):
        side = getattr(self.win, "side", None)
        if side is not None and hasattr(side, "show_jigsaw"):
            self.hint = side.show_jigsaw(self.image)
            self.hint.set_home(self.game.home)
        # Shown in exactly one place. With a 7" screen the picture belongs there, and keeping
        # a second copy in the margin as well would be two answers to the same question.
        self.inline.setVisible(self.hint is None)
        super().showEvent(event)

    def hideEvent(self, event):
        side = getattr(self.win, "side", None)
        if side is not None and hasattr(side, "show_idle") and self.hint is not None:
            side.show_idle()
        self.hint = None
        self.stepper.stop()
        super().hideEvent(event)
