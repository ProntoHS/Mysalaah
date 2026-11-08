"""Build the Salaah: drag the six postures of one rak'ah into order.

Six empty slots across the top of the 16-inch screen, the six posture drawings jumbled in a
tray underneath, and a child drags each one into its place.  The 7-inch companion carries the
title, where the build has got to, and the two controls.

WHAT THIS REPLACES, AND WHY IT IS A DIFFERENT GAME.  Until 2.11 this was six multiple-choice
rounds: one posture at a time, three pictures to choose between, "what comes next?".  Harry
asked for the whole rak'ah at once with drag and drop, which is not a new layout over the old
rules -- it is different rules, so the rules class is new.  The score is first-try placements
out of six, the same shape Pillar Match already uses.

THE RING CANNOT PLAY THIS, and that is deliberate rather than overlooked.  A six-piece drag
puzzle has no one-button reading, and Harry: "both screens are touch and i want to use it to
our advtage, contraints regarding ring button is moot, the button main design was for salaah
steps".  BACK still leaves the game, so the ring is not dead here, only the playing of it.

TWO OF THE SIX ARE THE SAME DRAWING, which the old game never had to face because the two
prostrations were never offered in the same round.  Jumble all six into a tray and there are
two identical tiles, and no child can tell which one "belongs" in the fourth slot rather than
the sixth.  A question whose right answer is invisible teaches nothing, so either prostration
tile is accepted in either prostration slot -- see [interchangeable], which asks the artwork
rather than hard-coding the pair, so giving prostrate_again its own drawing would change the
rules and the test for it would say so.

This is an ordering aid, not an exhaustive lesson in the rulings or words of prayer.  The
sequence and every translation remain explicitly subject to qualified review before release.
"""
from __future__ import annotations

import random

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette
from .winning import announce_if_won

#: The broad postures of one rak'ah, in the order they are performed. FIXED, DELIBERATELY:
#: the order is the whole lesson, which is why the slots are numbered and the tray is what
#: gets shuffled.
RAKAH = ("stand", "bow", "stand_upright", "prostrate", "sit", "prostrate_again")

#: The sitting at the END of a rak'ah, which is not one of the six above. Until 2.17 this game
#: stopped after the sixth posture and said so: it taught one rak'ah and claimed nothing more.
#: Harry's word, 8 November 2026: "the game has 6 steps and ends on prostration which is not
#: correct". He is right that it ends in mid-air, and the fix he chose is the honest one --
#: build a whole prayer, rak'ah by rak'ah, rather than bolt an ending onto a single rak'ah.
TASHAHHUD = "tashahhud"
SALAAM = "salaam"

PLACED, WRONG, NOTHING = "placed", "wrong", "nothing"

#: How many rak'ahs each level builds. Harry asked for three boxes reading "2 Rakaat",
#: "3 Rakaat" and "4 Rakaat" rather than Beginner/Medium/Expert -- "keep it simple" -- which
#: also happens to name the real thing: 2 is Fajr, 3 is Maghrib, 4 is Dhuhr, Asr and Isha.
#:
#: THIS REVERSES A DECISION HARRY MADE IN 2.12, when he asked for the difficulty button to be
#: left out of this game. It is recorded rather than quietly overwritten because the reason it
#: was left out then still holds for a single rak'ah: there is nothing to vary. What changed is
#: that the game now builds a prayer, and prayers genuinely differ in length.
LEVELS = (2, 3, 4)


def stages(rakats: int) -> tuple[tuple[str, ...], ...]:
    """The boards to build, in order, for a prayer of this many rak'ahs.

    A PRAYER IS NOT ITS RAK'AHS REPEATED, and this is the whole reason the game is built in
    stages rather than as one long row. Three things are true that a simple repeat would get
    wrong:

      * Every rak'ah has the same six postures. That part does repeat.
      * In a prayer of three or four rak'ahs there is a SITTING AT THE END OF THE SECOND --
        the first tashahhud -- which has no counterpart in the first rak'ah. A child who has
        built Maghrib learns that the second rak'ah ends differently from the first, which is
        true and is the sort of thing that is hard to pick up from a book.
      * The prayer ends with a tashahhud and the salaam, and those belong to the PRAYER rather
        than to any rak'ah. They get a short board of their own at the end so that nothing
        implies they are the seventh and eighth postures of a rak'ah.

    So Fajr is six, six, then the ending; Maghrib is six, seven, six, then the ending.

    The du'a with open hands that Harry sent artwork for is deliberately not here. It comes
    AFTER the prayer rather than inside it, and putting it in a numbered slot would teach that
    it is part of the salaah. His word on 8 November: "leave du'a hand posture for now."
    """
    if rakats not in LEVELS:
        raise ValueError(f"no prayer has {rakats} rak'ahs in this game")
    boards = []
    for number in range(1, rakats + 1):
        row = list(RAKAH)
        if number == 2 and rakats >= 3:
            row.append(TASHAHHUD)
        boards.append(tuple(row))
    boards.append((TASHAHHUD, SALAAM))
    return tuple(boards)


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
                      one place where telling the two stands apart is the question
      sit             jalsa, the sit between the two prostrations, which is this game's fifth
                      slot (NOT tashahhud, the sitting at the end -- that is not in one
                      rak'ah's broad postures as this game counts them)
    """
    return {"stand": "postures/standing_folded.png",
            "stand_upright": "postures/standing_itidal.png",
            "bow": "postures/ruku.png",
            "prostrate": "postures/sujood.png",
            "prostrate_again": "postures/sujood.png",
            "sit": "postures/jalsa.png",
            # Both already on the mat and both unused by this game until 2.17. jalsa is the
            # sit BETWEEN the prostrations, drawn from the side; tashahhud is the sit at the
            # end, drawn from the front with the finger raised. Two clearly different pictures
            # for two different sittings, which is what makes them safe to have in one game.
            TASHAHHUD: "postures/tashahhud.png",
            # One drawing holding both turns, right then left, which is why the salaam is one
            # tile and not two.
            SALAAM: "postures/salam.png"}[action]


def interchangeable(one: str, two: str) -> bool:
    """Whether a child could be expected to tell these two postures apart on the board.

    ASKS THE ARTWORK rather than naming the pair. The two prostrations are drawn with the same
    file because they are the same posture performed twice, and a tray holding two identical
    tiles cannot fairly insist that one of them belongs in the fourth slot and the other in the
    sixth. Written this way round so that the day prostrate_again gets a drawing of its own,
    the rules change with the art instead of silently disagreeing with it -- and the test that
    pins today's answer fails, which is the alarm.
    """
    return one == two or asset_for(one) == asset_for(two)


class RakahPuzzle:
    """Rules only: no Qt, time, filesystem or input-device knowledge.

    The fairness checker plays this thousands of times with no display, so nothing here may
    reach for a widget, a clock or a file.
    """

    def __init__(self, shuffle=None, rakats: int = LEVELS[0]):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.rakats = rakats if rakats in LEVELS else LEVELS[0]
        self.restart()

    def choose(self, rakats: int) -> None:
        """Pick a prayer length. Always starts the prayer again: there is no sensible way to
        carry half a built Fajr over into a Maghrib."""
        self.rakats = rakats if rakats in LEVELS else LEVELS[0]
        self.restart()

    def restart(self) -> None:
        self.boards = stages(self.rakats)
        self.stage = 0
        #: Right answers first time, added up across every board of the prayer, because the
        #: score a child is told at the end is for the prayer and not for its last six tiles.
        self.right_so_far = 0
        self.asked_so_far = 0
        self._lay_out()

    @property
    def row(self) -> tuple[str, ...]:
        """The board being built now."""
        return self.boards[self.stage]

    @property
    def ending(self) -> bool:
        """Whether this board is the tashahhud-and-salaam that closes the prayer, rather than
        a rak'ah. The screen says so instead of counting it as a rak'ah."""
        return self.stage == len(self.boards) - 1

    @property
    def rakah_number(self) -> int:
        """Which rak'ah is being built, 1-based. Meaningless on the ending board."""
        return self.stage + 1

    @property
    def boards_total(self) -> int:
        return len(self.boards)

    @property
    def board_done(self) -> bool:
        """This board is full. The prayer may still have boards to go."""
        return self.filled == len(self.row)

    @property
    def last_board(self) -> bool:
        return self.stage >= len(self.boards) - 1

    def next_board(self) -> bool:
        """Clear the board and start the next one. False when the prayer is finished.

        The count of right-first-time answers is banked here rather than recomputed at the
        end, because the tray is about to be thrown away.
        """
        if not self.board_done or self.last_board:
            return False
        self.right_so_far += self.first_try
        self.asked_so_far += len(self.row)
        self.stage += 1
        self._lay_out()
        return True

    @property
    def score(self) -> int:
        """Right first time across the whole prayer, including the board in play."""
        return self.right_so_far + self.first_try

    @property
    def asked(self) -> int:
        """How many postures the whole prayer asks for, boards still to come included."""
        return sum(len(board) for board in self.boards)

    def _lay_out(self) -> None:
        tray = list(self.row)
        self._shuffle(tray)
        #: The tray, in the jumbled order the tiles are laid out in. A tile keeps its place in
        #: the tray for the whole game: it is lifted out and does not come back, so the gap it
        #: leaves is where it was, and a child can see what is left.
        self.tray = tuple(tray)
        #: One per slot: the index of the tray tile sitting in it, or None.
        self.slots: list[int | None] = [None] * len(self.row)
        #: Tiles that have been dropped somewhere wrong at least once. Scoring is per tile and
        #: not per slot, so a tile that went astray and was then placed does not count.
        self.wrongly_tried: set[int] = set()
        self.last = "ready"

    @property
    def rounds(self) -> int:
        """Slots on the board in play. Six for a rak'ah, seven for the second rak'ah of a
        longer prayer, two for the ending."""
        return len(self.row)

    @property
    def filled(self) -> int:
        return sum(1 for slot in self.slots if slot is not None)

    @property
    def done(self) -> bool:
        """The whole PRAYER is built, not just the board in play. The screen asks this to
        decide whether to say Well Done, and saying it after Fajr's first rak'ah would be
        wrong."""
        return self.board_done and self.last_board

    @property
    def first_try(self) -> int:
        """Placements made without that tile ever having been dropped in the wrong place."""
        return sum(1 for slot in self.slots
                   if slot is not None and slot not in self.wrongly_tried)

    def placed(self, tile: int) -> bool:
        return tile in self.slots

    def in_hand(self) -> tuple[int, ...]:
        """The tray tiles still to be placed, by their tray index."""
        return tuple(n for n in range(len(self.tray)) if not self.placed(n))

    def accepts(self, tile: int, slot: int) -> bool:
        """Whether this tile belongs in this slot. Any tile may go into any empty slot: a
        child who knows prostration comes fourth can place it first and work outwards, and a
        mistake is recoverable. It is the SLOT that refuses, not the order of play."""
        if not (0 <= tile < len(self.tray) and 0 <= slot < len(self.row)):
            return False
        if self.placed(tile) or self.slots[slot] is not None:
            return False
        return interchangeable(self.tray[tile], self.row[slot])

    def place(self, tile: int, slot: int) -> str:
        if self.board_done or not (0 <= tile < len(self.tray) and 0 <= slot < len(self.row)):
            return NOTHING
        if self.placed(tile) or self.slots[slot] is not None:
            return NOTHING
        if not self.accepts(tile, slot):
            self.wrongly_tried.add(tile)
            self.last = WRONG
            return WRONG
        self.slots[slot] = tile
        if self.done:
            self.last = "complete"            # the whole prayer
        elif self.board_done:
            self.last = "board"               # this rak'ah; there are more to build
        else:
            self.last = PLACED
        return PLACED

    def posture_in(self, slot: int) -> str | None:
        """The posture showing in a slot, which is the TILE's name and not the slot's.

        A child who put 'Prostrate again' in the fourth slot put the right posture there, and
        the board should go on calling it what the tile called it rather than correcting them
        to a word they did not choose.
        """
        tile = self.slots[slot]
        return None if tile is None else self.tray[tile]


class RakahBoard(QtWidgets.QFrame):
    """The whole 16in board: six slots above, the jumbled tray below, and the drag between.

    ONE WIDGET AND NOT TWELVE. The drag has to be tracked across both rows, and raw touch
    events do not travel between sibling widgets the way a mouse does -- so this paints
    everything and does its own hit testing, which is how PillarBoard already works on this
    hardware. The touch handling below is that file's, including the guard for the synthetic
    mouse release that Qt delivers after a real touch ends.
    """

    dropped = Signal(int, int)
    lifted = Signal()

    #: Where the two rows sit, as a share of the board's height.
    SLOTS_TOP, SLOTS_TALL = 0.06, 0.37
    TRAY_TOP, TRAY_TALL = 0.55, 0.39

    def __init__(self, window, game):
        super().__init__()
        self.win = window
        self.game = game
        self.dragging: int | None = None
        self.drag_position = None
        self.wrong_slot: int | None = None
        self._ignore_mouse_release = False
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    # Geometry

    def _row(self, top_share: float, tall_share: float) -> list[QtCore.QRectF]:
        """The boxes across, for however many this board has.

        THE CELL IS SIZED FOR THE LONGEST BOARD IN THE PRAYER, not for this one. The ending
        has two tiles and a rak'ah has six or seven; sizing each board to its own count would
        blow the salaam up to a third of the screen and then shrink everything back down on
        the next prayer, which is a lot of movement for a child following along. A row shorter
        than the longest is centred in the width instead, so the tiles stay the size they have
        been all game and simply sit in the middle.
        """
        most = max(len(board) for board in self.game.boards)
        here = len(self.game.row)
        gap = self.width() * 0.012
        cell = (self.width() - gap * (most + 1)) / most
        used = here * cell + (here - 1) * gap
        left = (self.width() - used) / 2
        top = self.height() * top_share
        tall = self.height() * tall_share
        return [QtCore.QRectF(left + n * (cell + gap), top, max(1.0, cell), max(1.0, tall))
                for n in range(here)]

    def slot_rects(self) -> list[QtCore.QRectF]:
        return self._row(self.SLOTS_TOP, self.SLOTS_TALL)

    def tray_rects(self) -> list[QtCore.QRectF]:
        return self._row(self.TRAY_TOP, self.TRAY_TALL)

    def _slot_at(self, point):
        for n, box in enumerate(self.slot_rects()):
            if box.contains(point):
                return n
        return None

    def _tile_at(self, point):
        for n, box in enumerate(self.tray_rects()):
            if box.contains(point) and not self.game.placed(n):
                return n
        return None

    # Dragging

    def reset(self) -> None:
        self.dragging = None
        self.drag_position = None
        self.wrong_slot = None
        self.update()

    def reject(self, slot: int) -> None:
        self.dragging = None
        self.drag_position = None
        self.wrong_slot = slot
        self.update()

    def _start_drag(self, point) -> bool:
        if self.game.done:
            return False
        tile = self._tile_at(point)
        if tile is None:
            return False
        self.wrong_slot = None
        self.dragging = tile
        self.drag_position = point
        self.lifted.emit()
        self.update()
        return True

    def _move_drag(self, point) -> None:
        if self.dragging is not None:
            self.drag_position = point
            self.update()

    def _finish_drag(self, point) -> None:
        if self.dragging is None:
            return
        tile = self.dragging
        self.dragging = None
        self.drag_position = None
        slot = self._slot_at(point)
        if slot is None:
            self.update()
            return
        self.dropped.emit(tile, slot)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_drag(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._move_drag(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._ignore_mouse_release:
            self._ignore_mouse_release = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._finish_drag(event.position())
            event.accept()

    @staticmethod
    def _touch_position(event):
        points = event.points() if hasattr(event, "points") else event.touchPoints()
        if not points:
            return None
        point = points[0]
        return point.position() if hasattr(point, "position") else point.pos()

    def event(self, event):
        kind = event.type()
        if kind == QtCore.QEvent.Type.TouchBegin:
            point = self._touch_position(event)
            if point is not None:
                self._start_drag(point)
            event.accept()
            return True
        if kind == QtCore.QEvent.Type.TouchUpdate:
            point = self._touch_position(event)
            if point is not None:
                self._move_drag(point)
            event.accept()
            return True
        if kind == QtCore.QEvent.Type.TouchEnd:
            point = self._touch_position(event)
            if point is not None:
                self._finish_drag(point)
            self._ignore_mouse_release = True
            event.accept()
            return True
        return super().event(event)

    # Painting

    def _draw_posture(self, p, action: str, box: QtCore.QRectF) -> None:
        """One posture in one cell: the drawing above, its name along the bottom."""
        c = palette()
        label_h = min(box.height() * 0.26, self.win.px(54))
        picture = QtCore.QRectF(box.left() + self.win.px(10), box.top() + self.win.px(10),
                                box.width() - self.win.px(20),
                                box.height() - label_h - self.win.px(16))
        if picture.width() > 1 and picture.height() > 1:
            want = QtCore.QSize(max(1, int(picture.width())), max(1, int(picture.height())))
            pix = self.win.images.get(self.win.picture(asset_for(action)), want)
            if not pix.isNull():
                p.drawPixmap(int(picture.center().x() - pix.width() / 2),
                             int(picture.bottom() - pix.height()), pix)
        words = self.win.t(f"builder.action.{action}")
        font = QtGui.QFont(Fonts.for_text(words))
        font.setPixelSize(max(11, self.win.px(25)))
        font.setWeight(QtGui.QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QtGui.QColor(c.ink))
        p.drawText(QtCore.QRectF(box.left() + self.win.px(5), box.bottom() - label_h,
                                 box.width() - self.win.px(10), label_h),
                   int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), words)

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QtGui.QColor(c.paper))
        radius = self.win.px(16)
        thin, thick = self.win.px(3), self.win.px(7)

        for n, box in enumerate(self.slot_rects()):
            action = self.game.posture_in(n)
            edge, width = (c.ink, thin) if action else (c.line, thin)
            if n == self.wrong_slot:
                edge, width = c.highlight, thick
            elif self.dragging is not None and action is None \
                    and self.game.accepts(self.dragging, n):
                # The places this tile could go, while it is in the air. Not a hint about the
                # answer when nothing is being dragged -- that would play the game for them.
                edge, width = c.lapis, thick
            p.setPen(QtGui.QPen(QtGui.QColor(edge), width))
            p.setBrush(QtGui.QColor(c.paper))
            p.drawRoundedRect(box, radius, radius)
            if action:
                self._draw_posture(p, action, box)
            else:
                font = QtGui.QFont(Fonts.english_family)
                font.setPixelSize(max(12, self.win.px(44)))
                font.setWeight(QtGui.QFont.Weight.Bold)
                p.setFont(font)
                # SOFT AND NOT line. The first render of this board had the numbers in line,
                # which is #D9DCD6 on white paper and #3A3D40 on black -- about 1.2 to 1
                # either way, so the only thing telling a child which slot is which was
                # invisible in both themes. The outline of an empty slot can be faint; the
                # number in it cannot. Caught by looking at the picture, not by a test.
                p.setPen(QtGui.QColor(c.soft))
                p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), str(n + 1))

        for n, box in enumerate(self.tray_rects()):
            if self.game.placed(n) or n == self.dragging:
                # The gap it came out of, so what is left to place can be seen at a glance.
                p.setPen(QtGui.QPen(QtGui.QColor(c.line), thin, Qt.PenStyle.DotLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(box, radius, radius)
                continue
            p.setPen(QtGui.QPen(QtGui.QColor(c.ink), thin))
            p.setBrush(QtGui.QColor(c.paper))
            p.drawRoundedRect(box, radius, radius)
            self._draw_posture(p, self.game.tray[n], box)

        if self.dragging is not None and self.drag_position is not None:
            boxes = self.tray_rects()
            size = boxes[self.dragging].size()
            held = QtCore.QRectF(self.drag_position.x() - size.width() / 2,
                                 self.drag_position.y() - size.height() / 2,
                                 size.width(), size.height())
            # PAPER AND NOT pressed. A posture drawing carries its own background, so a tile
            # filled with anything else shows the drawing as a patch of a different tone in
            # the middle of the card -- plainly a seam in both themes when the first render
            # of this was looked at. The thick lapis edge is what says the tile is in the air.
            p.setPen(QtGui.QPen(QtGui.QColor(c.lapis), thick))
            p.setBrush(QtGui.QColor(c.paper))
            p.drawRoundedRect(held, radius, radius)
            self._draw_posture(p, self.game.tray[self.dragging], held)


class BuildTheSalaahScreen(QtWidgets.QWidget):
    """The board on the 16in, with the title and the controls on the 7in companion."""

    #: How long a wrongly dropped slot stays outlined before it goes quiet again.
    SHOWN = 900
    #: How long a finished rak'ah stays up before the next board is laid out. Longer than
    #: SHOWN because this one is not a correction to be read and dismissed -- it is the whole
    #: rak'ah in order, which is the thing the child just worked out and the thing worth
    #: looking at.
    SETTLED = 1800
    leave = Signal()
    won = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = RakahPuzzle(shuffle)
        self.setObjectName("buildTheSalaahScreen")

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        self.board = RakahBoard(window, self.game)
        self.board.dropped.connect(self._drop)
        self.board.lifted.connect(self._lifted)
        column.addWidget(self.board)

        self.clearing = QtCore.QTimer(self)
        self.clearing.setSingleShot(True)
        self.clearing.timeout.connect(self._stop_showing_the_mistake)

        #: How long a completed rak'ah stays on the board before the next one is laid out.
        self.moving_on = QtCore.QTimer(self)
        self.moving_on.setSingleShot(True)
        self.moving_on.timeout.connect(self._next_board)

        self.companion = self._build_companion()
        self.retell()

    def _build_companion(self):
        """The 7in panel: the title, how far the rak'ah has got, and the two controls.

        Harry asked for "just the side screen for title and menu buttons". The line between
        them is where the panel says what has happened, which is what fills the middle of
        every other game's panel rather than leaving two thirds of a tall screen blank.
        """
        panel = QtWidgets.QWidget()
        panel.setObjectName("buildTheSalaahCompanion")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.side_px(20), self.win.side_px(18),
                                  self.win.side_px(20), self.win.side_px(18))
        layout.setSpacing(self.win.side_px(12))

        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.where = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.where.setObjectName("gameStatus")
        layout.addWidget(self.where)

        #: Which rak'ah of the prayer is being built. Harry: "the small screen instead of hint
        #: could keep track i.e 1 rakaat completed."
        self.which = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.which.setObjectName("gameStatus")
        self.which.setWordWrap(True)
        layout.addWidget(self.which)

        # THE RAK'AH IN WORDS, one line per slot, filling as the board fills.
        #
        # Harry asked for "just the side screen for title and menu buttons", and I argued
        # myself out of this on the grounds that the slots on the 16in already are the list.
        # Then the panel was rendered and looked at: a title, "3 of 6", one short line and
        # two buttons left two thirds of a 1080x1920 screen blank white, which is not what
        # the other five panels look like. It is also not redundant -- the big screen shows
        # six PICTURES, and the sequence said in words is the thing being taught. Costs no
        # new strings: these are builder.action.*, which all nine translated packs carry.
        # AlignLeading and not AlignCenter, which is what the rest of this panel uses: a
        # centred numbered list puts every number at a different place down the page, and it
        # stopped looking like a list at all. Leading also turns itself round for Arabic and
        # Urdu, whose packs set dir rtl, which a hard-coded left would not.
        # SEVEN LABELS AND NOT SIX, because the boards are no longer all the same length: the
        # second rak'ah of Maghrib and of the four-rak'ah prayers ends with a tashahhud, and
        # the board that closes the prayer has only two. The spare labels are hidden rather
        # than created and destroyed as the prayer moves on, which keeps the panel from
        # relaying out under a child's finger.
        layout.addStretch(1)
        self.rows: list[QtWidgets.QLabel] = []
        for _ in range(max(len(board) for board in stages(max(LEVELS)))):
            row = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignLeading)
            row.setObjectName("gameStatus")
            row.setWordWrap(True)
            row.setContentsMargins(self.win.side_px(40), 0, self.win.side_px(10), 0)
            layout.addWidget(row)
            self.rows.append(row)
        layout.addStretch(1)

        self.said = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.said.setObjectName("gameStatus")
        self.said.setWordWrap(True)
        layout.addWidget(self.said)

        # HOW LONG A PRAYER TO BUILD: three boxes rather than the cycling Beginner/Medium/
        # Expert button the other three games use. Harry asked for it that way -- "maybe have
        # 3 boxes, 2 rakaat, 3 rakaat and 4 rakaat. keep it simple" -- and it is the better
        # control here for a reason the other games do not have: these are not difficulty
        # settings dressed up, they are the actual lengths of the actual prayers, and three
        # boxes let a child pick the one they are about to pray instead of cycling past it.
        levels = QtWidgets.QHBoxLayout()
        levels.setSpacing(self.win.side_px(10))
        self.level_buttons: dict[int, QtWidgets.QPushButton] = {}
        for rakats in LEVELS:
            # A controlButton like the rest of this panel, with a :checked rule added to
            # the panel's own stylesheet so the chosen box is filled rather than
            # outlined. This went the other way first: "pill" is the mat's style for a
            # chosen option and already has a :checked rule, so the level boxes were
            # pills -- and the panel checker caught it, because #pill lives in the main
            # window's stylesheet and this panel sets its own. The pills came out with
            # no border at all, an edge of 255 against a background of 255, invisible
            # in both themes. Rendering it had shown the CHECKED pill looking right and
            # told me nothing about the other two.
            button = QtWidgets.QPushButton()
            button.setObjectName("controlButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(self.win.side_px(64))
            button.clicked.connect(lambda _checked=False, n=rakats: self.choose_length(n))
            levels.addWidget(button, 1)
            self.level_buttons[rakats] = button
        layout.addLayout(levels)

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
        font = QtGui.QFont(Fonts.for_text(words))
        font.setPixelSize(max(12, self.win.side_px(size)))
        if bold:
            font.setWeight(QtGui.QFont.Weight.Bold)
        return font

    # Playing

    def start_again(self) -> None:
        self.clearing.stop()
        self.game.restart()
        self.board.reset()
        self.retell()

    def _lifted(self) -> None:
        """A tile has been picked up, so last go's red outline stops meaning anything."""
        self.clearing.stop()
        self.retell()

    def choose_length(self, rakats: int) -> None:
        """Pick a two, three or four rak'ah prayer. Always starts over: see RakahPuzzle."""
        self.clearing.stop()
        self.moving_on.stop()
        self.game.choose(rakats)
        self.board.reset()
        self.retell()

    def _drop(self, tile: int, slot: int) -> None:
        result = self.game.place(tile, slot)
        if result == WRONG:
            self.board.reject(slot)
            self.clearing.start(self.SHOWN)
        else:
            self.board.reset()
            # A FINISHED RAK'AH IS LEFT ON THE SCREEN FOR A MOMENT before the board clears.
            # Sweeping it away the instant the sixth tile lands would take away the one view
            # of the whole rak'ah in order that the child has just built, which is the thing
            # the game is for. The pause is also what makes the companion's "Rakat 1 of 3"
            # readable -- it changes while they are looking at it, rather than in the blink
            # where their finger is still moving.
            if self.game.board_done and not self.game.done:
                self.moving_on.start(self.SETTLED)
        self.retell()

    def _next_board(self) -> None:
        if self.game.next_board():
            self.board.reset()
            self.retell()

    def _stop_showing_the_mistake(self) -> None:
        self.board.wrong_slot = None
        self.board.update()

    def press(self, action: str = "") -> None:
        """BACK leaves. NOTHING ELSE DOES ANYTHING, and that is the design.

        A six-piece drag puzzle has no one-button reading. The ring's job on this mat is the
        prayer steps; both of these screens are touch.
        """
        from .buttons import BACK
        if action == BACK or str(action).lower() in ("back", "exit", "escape"):
            self.clearing.stop()
            self.leave.emit()

    def retell(self) -> None:
        t, game = self.win.t, self.game
        self.title.setText(t("builder.title"))
        self.new_button.setText(t("builder.new_game"))
        self.exit_button.setText(t("builder.exit"))
        for rakats, button in self.level_buttons.items():
            button.setText(t("builder.rakats", n=rakats))
            button.setChecked(rakats == game.rakats)
            button.setFont(self._font(button.text(), 24, rakats == game.rakats))
        for n, row in enumerate(self.rows):
            # Rows beyond this board are hidden: the ending has two and a rak'ah six or seven.
            if n >= game.rounds:
                row.setVisible(False)
                continue
            row.setVisible(True)
            posture = game.posture_in(n)
            said = t(f"builder.action.{posture}") if posture else "—"
            row.setText(f"{n + 1}.  {said}")
            row.setFont(self._font(said, 27, bool(posture)))
            row.setStyleSheet("" if posture else f"color: {palette().soft};")
        # WHICH RAK'AH, which is what Harry asked the panel to keep track of. builder.rakat
        # is this game's OWN key carrying the wording that player.rakat already had in all
        # nine translated packs -- "Rakat {n} of {total}" -- so the tracker cost no new
        # wording in any language. It is copied rather than borrowed because a game that
        # reads another screen's string changes silently when that screen is reworded,
        # which is the rule Qibla Quest broke once already. The board that
        # closes the prayer is not a rak'ah and does not claim to be one; it says so instead.
        if game.ending:
            self.which.setText(t("builder.ending"))
        else:
            self.which.setText(t("builder.rakat", n=game.rakah_number, total=game.rakats))
        self.which.setFont(self._font(self.which.text(), 26, True))
        if game.done:
            self.where.setText(t("corner.item", at=game.rounds, of=game.rounds))
            self.said.setText(t("builder.done", score=game.score, of=game.asked)
                              + "\n\n" + t("builder.again"))
        else:
            self.where.setText(t("corner.item", at=game.filled, of=game.rounds))
            # WORDLESS ON A WRONG DROP, on purpose. The slot outlines itself in the warning
            # colour and the tile goes back where it came from, which says it in every
            # language at once -- including Arabic, whose pack carries 47 of the 410 strings
            # and falls back to English for the rest. Nothing new had to be written in nine
            # languages and left unreviewed to make this game speak.
            self.said.setText(t("builder.question"))
        self.title.setFont(self._font(self.title.text(), 40, True))
        self.where.setFont(self._font(self.where.text(), 24, True))
        self.said.setFont(self._font(self.said.text(), 26))
        self.new_button.setFont(self._font(self.new_button.text(), 28, True))
        self.exit_button.setFont(self._font(self.exit_button.text(), 28, True))
        self.board.update()
        # No `changed` signal in this file -- retell IS what runs after
        # every change, so the question is asked from here.
        self._look_for_a_win()

    def follow_theme(self) -> None:
        c = palette()
        radius = self.win.side_px(11)
        edge = self.win.side_px(3)
        # TYPE SIZES IN THE PANEL'S OWN PIXELS, and paper AND ink rather than panel and paper.
        # Both have been got wrong twice in this app: a panel styled background:panel with
        # color:paper reads as black on #1C1C1C after dark, measured at 1.1 to 1, and a button
        # whose border is its own fill has no visible edge at all.
        title = self.win.side_px(40)
        body = self.win.side_px(26)
        label = self.win.side_px(28)
        self.companion.setStyleSheet(
            f"QWidget#buildTheSalaahCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            f"QPushButton#controlButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; border-radius: {radius}px; }}"
            f"QPushButton#controlButton:pressed {{ background: {c.pressed}; color: {c.ink}; }}"
            # THE CHOSEN LENGTH, filled rather than outlined. The three boxes are
            # controlButtons like every other button on this panel -- which is what
            # gives them an edge against the paper, the thing the panel checker
            # measures -- so the only way to show which one is chosen is to fill it.
            # c.ink on c.paper reversed keeps the same two colours and therefore the
            # same contrast in both themes.
            f"QPushButton#controlButton:checked {{ background: {c.ink}; color: {c.paper}; }}"
            f"QLabel#gameTitle {{ font-size: {title}px; font-weight: bold; }}"
            f"QLabel#gameStatus {{ font-size: {body}px; }}"
            f"QPushButton#controlButton {{ font-size: {label}px; font-weight: bold; }}")
        self.retell()
        self.board.update()

    def showEvent(self, event):
        self.follow_theme()
        super().showEvent(event)

    def hideEvent(self, event):
        self.clearing.stop()
        super().hideEvent(event)

    def _look_for_a_win(self) -> None:
        """Runs after every change. See salaah/winning.py for why it is once and not always."""
        announce_if_won(self, self.game.done)
