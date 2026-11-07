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

#: The broad postures of one rak'ah, in the order they are performed. FIXED, DELIBERATELY:
#: the order is the whole lesson, which is why the slots are numbered and the tray is what
#: gets shuffled.
RAKAH = ("stand", "bow", "stand_upright", "prostrate", "sit", "prostrate_again")

PLACED, WRONG, NOTHING = "placed", "wrong", "nothing"


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
            "sit": "postures/jalsa.png"}[action]


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

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        tray = list(RAKAH)
        self._shuffle(tray)
        #: The tray, in the jumbled order the tiles are laid out in. A tile keeps its place in
        #: the tray for the whole game: it is lifted out and does not come back, so the gap it
        #: leaves is where it was, and a child can see what is left.
        self.tray = tuple(tray)
        #: One per slot: the index of the tray tile sitting in it, or None.
        self.slots: list[int | None] = [None] * len(RAKAH)
        #: Tiles that have been dropped somewhere wrong at least once. Scoring is per tile and
        #: not per slot, so a tile that went astray and was then placed does not count.
        self.wrongly_tried: set[int] = set()
        self.last = "ready"

    @property
    def rounds(self) -> int:
        return len(RAKAH)

    @property
    def filled(self) -> int:
        return sum(1 for slot in self.slots if slot is not None)

    @property
    def done(self) -> bool:
        return self.filled == len(RAKAH)

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
        if not (0 <= tile < len(self.tray) and 0 <= slot < len(RAKAH)):
            return False
        if self.placed(tile) or self.slots[slot] is not None:
            return False
        return interchangeable(self.tray[tile], RAKAH[slot])

    def place(self, tile: int, slot: int) -> str:
        if self.done or not (0 <= tile < len(self.tray) and 0 <= slot < len(RAKAH)):
            return NOTHING
        if self.placed(tile) or self.slots[slot] is not None:
            return NOTHING
        if not self.accepts(tile, slot):
            self.wrongly_tried.add(tile)
            self.last = WRONG
            return WRONG
        self.slots[slot] = tile
        self.last = "complete" if self.done else PLACED
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
        gap = self.width() * 0.012
        cell = (self.width() - gap * (len(RAKAH) + 1)) / len(RAKAH)
        top = self.height() * top_share
        tall = self.height() * tall_share
        return [QtCore.QRectF(gap + n * (cell + gap), top, max(1.0, cell), max(1.0, tall))
                for n in range(len(RAKAH))]

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
    leave = Signal()

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
        layout.addStretch(1)
        self.rows: list[QtWidgets.QLabel] = []
        for _ in RAKAH:
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

    def _drop(self, tile: int, slot: int) -> None:
        result = self.game.place(tile, slot)
        if result == WRONG:
            self.board.reject(slot)
            self.clearing.start(self.SHOWN)
        else:
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
        for n, row in enumerate(self.rows):
            posture = game.posture_in(n)
            said = t(f"builder.action.{posture}") if posture else "—"
            row.setText(f"{n + 1}.  {said}")
            row.setFont(self._font(said, 27, bool(posture)))
            row.setStyleSheet("" if posture else f"color: {palette().soft};")
        if game.done:
            self.where.setText(t("corner.item", at=game.rounds, of=game.rounds))
            self.said.setText(t("builder.done", score=game.first_try, of=game.rounds)
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
