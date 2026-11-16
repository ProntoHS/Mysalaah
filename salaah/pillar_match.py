"""Pillar Match: drag each object to the matching pillar of Islam.

The 16-inch touchscreen is artwork-only. The companion widget is for the
7-inch screen. A Bluetooth ring remains usable as an alternative input.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette
from .winning import announce_if_won

PILLARS = ("faith", "prayer", "charity", "fasting", "hajj")

#: How wide a pillar's catching area is, as a fraction of the board. The pillars Harry drew
#: are .143 wide; this is a little more, so the gaps between them belong to somebody rather
#: than to nobody. Five zones of .19 side by side still leave a seam between each pair, so a
#: finger that lands squarely between two pillars is still told it missed rather than being
#: given the nearer one -- which is the right answer in a game about knowing which is which.
WIDE = 0.19


def measure_the_board(board) -> tuple[float, float, tuple[float, ...]]:
    """Find the five pillars in the board picture: (top, bottom, centres), as fractions.

    Reading the artwork rather than trusting numbers typed beside it. See PillarBoard._zones
    for why, and for the check that says this works.

    A board it cannot read -- missing, blank, not five pillars -- falls back to five even
    columns rather than raising. The game is reachable only when the board file is on the mat
    (see Screen.playable), so this is the odd case of a file that is present and not what we
    thought; a playable board with slightly wrong zones beats a game that will not open.
    """
    if board is None or board.isNull():
        return FALLBACK
    picture = board.toImage().convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    wide, tall = picture.width(), picture.height()
    if wide < 10 or tall < 10:
        return FALLBACK
    lit = []
    for y in range(tall):
        line = picture.constScanLine(y)
        line.setsize(wide)
        lit.append(sum(1 for value in bytes(line) if value > 60))
    solid = [y for y, count in enumerate(lit) if count > wide * 0.15]
    if not solid:
        return FALLBACK
    top, bottom = solid[0], solid[-1]
    # The shafts only: the name plates below them run into one another, and a band that
    # included them would read as one pillar five columns wide.
    shaft = (top, top + int((bottom - top) * 0.55))
    columns = [0] * wide
    for y in range(*shaft):
        line = picture.constScanLine(y)
        line.setsize(wide)
        for x, value in enumerate(bytes(line)):
            if value > 60:
                columns[x] += 1
    deep = (shaft[1] - shaft[0]) * 0.05
    runs, start = [], None
    for x in range(wide):
        if columns[x] > deep and start is None:
            start = x
        elif columns[x] <= deep and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, wide))
    runs = [r for r in runs if (r[1] - r[0]) > wide * 0.04]
    if len(runs) != len(PILLARS):
        return FALLBACK
    centers = tuple(((a + b) / 2) / wide for a, b in runs)
    return (top / tall, min(1.0, (bottom + 1) / tall), centers)


#: Five even columns over the lower half, which is what a board nobody can read gets.
FALLBACK = (0.48, 0.85, (0.125, 0.3125, 0.5, 0.6875, 0.875))


@dataclass(frozen=True)
class Item:
    key: str
    pillar: str
    art: str


#: The ten things to sort, two to each pillar. The `art` is the file in assets/children/pillars
#: and it is the same word as the key, because two names for one thing is two things to keep in
#: step; they were different until 2.36 and three of them had already drifted.
#:
#: Harry drew these at 2.36 and three of them replaced what was here: prayer beads for the
#: mosque, giving hands for the coins, the path to the Kaaba for the pilgrimage bag.
ITEMS = (
    Item("testimony", "faith", "testimony"),
    Item("one_finger", "faith", "one_finger"),
    Item("prayer_rug", "prayer", "prayer_rug"),
    Item("prayer_beads", "prayer", "prayer_beads"),
    Item("charity_box", "charity", "charity_box"),
    Item("giving_hands", "charity", "giving_hands"),
    Item("dates", "fasting", "dates"),
    Item("iftar", "fasting", "iftar"),
    Item("kaaba", "hajj", "kaaba"),
    Item("path_to_kaaba", "hajj", "path_to_kaaba"),
)


class Rules:
    """Pure state: no Qt, files, clocks or device knowledge."""

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.sequence = list(ITEMS)
        self._shuffle(self.sequence)
        self.at = 0
        #: Which pillar the drop landed on, for the "not that one" flash. There is no
        #: travelling highlight any more: the ring stepped through the five and pressed to
        #: choose, and Harry took it out at 2.36 -- "remove the ring control for the game.
        #: purely drag & drop." Nothing moves on the board now until a finger moves it.
        self.active = 0
        self.locked = False
        self.done = False
        self.attempted = False
        self.last = "ready"
        self.first_try = 0

    @property
    def rounds(self) -> int:
        return len(self.sequence)

    @property
    def item(self) -> Item:
        return self.sequence[self.at]

    @property
    def correct(self) -> int:
        return PILLARS.index(self.item.pillar)

    def answer(self, which: int) -> str:
        if self.done or self.locked or not 0 <= which < len(PILLARS):
            return "nothing"
        self.active = which
        if which != self.correct:
            self.attempted = True
            self.last = "wrong"
            return "wrong"
        if not self.attempted:
            self.first_try += 1
        self.locked = True
        self.last = "correct"
        return "correct"

    def next_round(self) -> str:
        if not self.locked:
            return "nothing"
        if self.at + 1 >= self.rounds:
            self.done = True
            self.locked = False
            self.last = "complete"
            return "complete"
        self.at += 1
        self.active = 0
        self.locked = False
        self.attempted = False
        self.last = "ready"
        return "next"

    def press(self) -> str:
        """What a button press does, now that it cannot choose a pillar.

        It carries the game on: start again when the round is over, move to the next item when
        one has just been placed. It can no longer ANSWER -- answering is a drag and nothing
        else. The ring used to step a highlight along the five and press to pick one; that is
        gone, and with it the only way to play this without dragging. Written down because it
        was a decision rather than a tidy-up: if that ever matters for somebody's hands, it
        was taken out on purpose and can be put back.
        """
        if self.done:
            self.restart()
            return "again"
        if self.locked:
            return self.next_round()
        return "nothing"


class ItemArt:
    """The ten pictures, loaded from assets/children/pillars once and kept.

    THESE WERE DRAWN IN CODE until 2.36 -- a hundred and thirty lines of arcs and polygons
    making a scroll, a hand, a rug, a dome. Harry drew ten proper icons, so the code went.

    They are kept WHITE ON NOTHING, one file per item rather than one per item per language.
    His pack had a hundred pictures in it and the icon is byte-identical in all ten -- only
    the word underneath changes, and that word is the answer to the question the game is
    asking, so it has no business on the board anyway. Ten files, 173 KB, against 100 and
    3.0 MB.

    White, because THE BOARD IS BLACK IN BOTH THEMES. The board is a photograph of a drawing;
    it does not invert when the mat goes from night to day, so what sits on top of it cannot
    either. That is exactly what was wrong before: the item was painted in the palette's paper
    colour, which is white by day and BLACK AT NIGHT, on a board that is black at both. On the
    mat's own theme the thing the child is meant to drag was drawn black on black. The game
    could only be played by reading the 7in and dragging an object nobody could see.
    """

    CACHE: dict[str, QtGui.QPixmap] = {}

    @classmethod
    def picture(cls, window, kind) -> QtGui.QPixmap:
        if kind not in cls.CACHE:
            path = window.assets / "children" / "pillars" / f"{kind}.png"
            cls.CACHE[kind] = QtGui.QPixmap(str(path))
        return cls.CACHE[kind]

    @classmethod
    def draw(cls, p, kind, rect, window, ink=None, paper=None) -> None:
        """Draw item `kind` to fit `rect`. `ink`, when given, tints it -- for the 7in, whose
        panel IS the theme's paper and where a white picture would be white on white."""
        picture = cls.picture(window, kind)
        if picture.isNull():
            return
        side = min(rect.width(), rect.height())
        box = QtCore.QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2,
                            side, side)
        if ink is None:
            p.drawPixmap(box, picture, QtCore.QRectF(picture.rect()))
            return
        tinted = QtGui.QPixmap(picture.size())
        tinted.fill(Qt.GlobalColor.transparent)
        brush = QtGui.QPainter(tinted)
        brush.drawPixmap(0, 0, picture)
        brush.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        brush.fillRect(tinted.rect(), QtGui.QColor(ink))
        brush.end()
        p.drawPixmap(box, tinted, QtCore.QRectF(tinted.rect()))

    @staticmethod
    def every_one(assets) -> list[str]:
        return [item.art for item in ITEMS]


class ItemPreview(QtWidgets.QFrame):
    def __init__(self, window):
        super().__init__()
        self.win = window
        self.kind = "scroll"
        self.setMinimumHeight(window.px(200))

    def show_kind(self, kind) -> None:
        self.kind = kind
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        margin = self.win.px(8)
        box = QtCore.QRectF(self.rect()).adjusted(margin, margin, -margin, -margin)
        p.setPen(QtGui.QPen(QtGui.QColor(c.paper), self.win.px(3)))
        p.setBrush(QtGui.QColor(c.paper))
        p.drawRoundedRect(box, self.win.px(14), self.win.px(14))
        art = box.adjusted(box.width() * .18, box.height() * .12,
                           -box.width() * .18, -box.height() * .12)
        ItemArt.draw(p, self.kind, art, self.win, c.ink, c.paper)


class PillarBoard(QtWidgets.QFrame):
    """Artwork-only board with a draggable current item."""

    dropped = Signal(int)

    def __init__(self, window, game, board):
        super().__init__()
        self.win = window
        self.game = game
        self.board = board
        self.dragging = False
        self.drag_position = None
        self.wrong_zone = None
        self._ignore_mouse_release = False
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _zones(self):
        """Where the five pillars are, READ OFF THE PICTURE rather than typed in here.

        These were five numbers in this file -- .125, .3125, .5, .6875, .875 -- measured once
        by hand against the board of the day. Harry redrew the board at 2.36 with the pillars
        further down and further apart, and those numbers would have put the catching areas
        for the two outside pillars SIXTY-SIX PIXELS off the pillars they belong to: a child
        aiming at Shahadah, hitting it, and being told they were wrong.

        So the board is measured when it loads. How I know it reads pictures rather than
        produces plausible numbers: run it on the OLD board and it gives .125, .313, .500,
        .688, .875 -- the five numbers that were typed in here by hand, to three decimals. It
        reproduces the old answer from the old picture and a different, correct one from the
        new. Redraw the board again and the zones follow it on their own.
        """
        found = measure_the_board(self.board)
        top, bottom, centers = found
        return [QtCore.QRectF(self.width() * (center - WIDE / 2), self.height() * top,
                              self.width() * WIDE, self.height() * (bottom - top))
                for center in centers]

    def _home(self):
        """Centre top, in the room Harry's board freed up by sitting the pillars lower.

        His pillars start at 57.8% of the height where the old ones started at 49.5%, which
        turns the clear strip above them from 26% of the screen into 36% -- about 110 pixels
        more, and a drag of 393 rather than 262. His reason, and it is the right one: "as my
        pillars sit further down, dragging them is easier as you have more space to move
        finger on screen".
        """
        return QtCore.QPointF(self.width() * .5, self.height() * .20)

    def _item_rect(self, center=None, small=False):
        center = center or self._home()
        side = min(self.width() * (.082 if small else .11),
                   self.height() * (.20 if small else .27))
        return QtCore.QRectF(center.x() - side / 2, center.y() - side / 2, side, side)

    def reset_item(self) -> None:
        self.dragging = False
        self.drag_position = None
        self.wrong_zone = None
        self.update()

    def reject(self, which) -> None:
        self.dragging = False
        self.drag_position = None
        self.wrong_zone = which
        self.update()

    def _zone_at(self, point):
        for index, zone in enumerate(self._zones()):
            if zone.contains(point):
                return index
        return None

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QtGui.QColor(c.ink))
        if not self.board.isNull():
            p.drawPixmap(QtCore.QRectF(self.rect()), self.board,
                         QtCore.QRectF(self.board.rect()))
        zones = self._zones()
        if not self.game.done:
            if self.wrong_zone is not None:
                p.setPen(QtGui.QPen(QtGui.QColor(c.highlight), self.win.px(7)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(zones[self.wrong_zone], self.win.px(12), self.win.px(12))
            center = self.drag_position or self._home()
            small = False
            if self.game.locked:
                center = zones[self.game.correct].center()
                small = True
            ItemArt.draw(p, self.game.item.art, self._item_rect(center, small), self.win)

    def _start_drag(self, point):
        if self.game.done or self.game.locked:
            return False
        target = self._item_rect(self.drag_position or self._home()).adjusted(
            -self.win.px(24), -self.win.px(24), self.win.px(24), self.win.px(24))
        if not target.contains(point):
            return False
        self.wrong_zone = None
        self.dragging = True
        self.drag_position = point
        self.update()
        return True

    def _move_drag(self, point):
        if self.dragging:
            self.drag_position = point
            self.update()

    def _finish_drag(self, point):
        if not self.dragging:
            return
        self.dragging = False
        self.drag_position = point
        which = self._zone_at(point)
        if which is None:
            self.drag_position = None
            self.update()
        else:
            self.dropped.emit(which)

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


class Screen(QtWidgets.QWidget):
    """Main 16-inch game screen with its 7-inch companion attached."""

    CYCLE = 1350
    SHOWN = 1050
    leave = Signal()
    changed = Signal()
    won = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = Rules(shuffle)
        self.setObjectName("pillarMatchMain")
        self.board_image = QtGui.QPixmap(str(window.assets / "children" / self.BOARD))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.board = PillarBoard(window, self.game, self.board_image)
        self.board.dropped.connect(self._drop)
        layout.addWidget(self.board)
        self._advance = QtCore.QTimer(self)
        self._advance.setSingleShot(True)
        self._advance.timeout.connect(self._next)
        self.companion = self._build_companion()
        self.changed.connect(self.board.update)
        self.changed.connect(self._look_for_a_win)
        self.changed.connect(self.retell)
        self.follow_theme()
        self.start_again()

    #: The one picture this game needs, named once so the loader and playable() cannot drift.
    BOARD = "pillar-match-board.png"

    @property
    def ready(self) -> bool:
        """Whether the board is on the mat. See journey_jigsaw.Screen.ready."""
        return not self.board_image.isNull()

    @staticmethod
    def playable(assets) -> bool:
        """Can this game be built at all? Asked of the DISK, before anything is constructed.

        Added here; the pack did not offer it. Since 1.97 the children's menu builds a game only
        when a child first opens it, and decides whether to offer the tile at all by asking the
        filesystem for the artwork -- see ui.build_corner. A module with no playable() is taken
        to be always playable, so without this a mat that never received the board would show a
        tile that opens a screen with a blank rectangle on it.
        """
        return (assets / "children" / Screen.BOARD).is_file()

    def _build_companion(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("pillarMatchCompanion")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.side_px(20), self.win.side_px(18),
                                  self.win.side_px(20), self.win.side_px(18))
        layout.setSpacing(self.win.side_px(10))
        # NAMED, or the stylesheet below cannot size them. Its QLabel#gameTitle and
        # QLabel#gameStatus rules only match a label that carries the name, and a label that
        # matches neither falls through to the app-wide QWidget rule -- font-size px(24), the
        # MAIN screen's scale -- which on a 1080x1920 panel is 24px beside lettering at 75.
        # This file had the same omission as prayer_day_journey.py and nobody had noticed,
        # because the one Harry photographed was the other one.
        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.progress = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.progress.setObjectName("gameStatus")
        layout.addWidget(self.progress)
        # The running score, which Harry asked the 7in to keep: "the hint screen can keep
        # score." It borrows the sentence the end of the game already uses rather than
        # inventing one, so a whole new line arrives on this screen in ten languages without a
        # word of it being new. It stays hidden until a round has actually been finished --
        # "First try: 0 / 0" is not a score, it is an arithmetic accident.
        self.score = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.score.setObjectName("gameStatus")
        layout.addWidget(self.score)
        self.preview = ItemPreview(self.win)
        layout.addWidget(self.preview, 1)
        self.item_name = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.item_name.setObjectName("gameStatus")
        self.item_name.setWordWrap(True)
        layout.addWidget(self.item_name)
        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setObjectName("gameStatus")
        self.question.setWordWrap(True)
        layout.addWidget(self.question)
        self.feedback = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.feedback.setObjectName("gameStatus")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(self.win.side_px(10))
        self.new_button = QtWidgets.QPushButton()
        self.new_button.setObjectName("controlButton")
        self.new_button.setMinimumHeight(self.win.side_px(64))
        self.new_button.clicked.connect(self.start_again)
        controls.addWidget(self.new_button, 1)
        self.exit_button = QtWidgets.QPushButton()
        self.exit_button.setObjectName("controlButton")
        self.exit_button.setMinimumHeight(self.win.side_px(64))
        self.exit_button.clicked.connect(self.leave.emit)
        controls.addWidget(self.exit_button, 1)
        layout.addLayout(controls)
        return panel

    def _font(self, words, size, bold=False):
        font = QtGui.QFont(Fonts.for_text(words))
        font.setPixelSize(self.win.px(size))
        if bold:
            font.setWeight(QtGui.QFont.Weight.Bold)
        return font

    def _pillar_name(self, key):
        return self.win.t("pillar_match.pillar." + key)

    def retell(self) -> None:
        t, game = self.win.t, self.game
        self.title.setText(t("pillar_match.title"))
        self.new_button.setText(t("pillar_match.new_game"))
        self.exit_button.setText(t("pillar_match.exit"))
        if game.done:
            self.progress.setText(t("pillar_match.progress", at=str(game.rounds),
                                    of=str(game.rounds)))
            self.item_name.clear()
            self.question.setText(t("pillar_match.complete"))
            self.feedback.setText(t("pillar_match.complete_score",
                                    score=str(game.first_try), of=str(game.rounds)))
            self.score.clear()
            self.score.setVisible(False)
            self.preview.hide()
        else:
            self.preview.show()
            self.preview.show_kind(game.item.art)
            self.progress.setText(t("pillar_match.progress", at=str(game.at + 1),
                                    of=str(game.rounds)))
            # THE NAME WAITS UNTIL IT HAS BEEN PLACED, and this is not tidiness.
            #
            # In six of the ten languages an item's name contains its pillar's name. Spanish
            # calls the rug "Alfombra de oracion" and the pillar "Oracion"; Urdu calls it
            # "jaa-e namaz" and the pillar "namaz"; Arabic cannot say prayer rug without
            # saying prayer. That is not bad translation -- it is what those objects are
            # called -- so it cannot be written around without inventing names nobody uses.
            #
            # Shown before the drop, the 7in was printing the answer beside the question on
            # six of the ten mats, and had been since the game went in. Shown after, every
            # language is sound and nothing needed rewording. It is also the better teaching
            # moment: the name and the pillar arrive together, once the child has committed.
            self.item_name.setText(t("pillar_match.item." + game.item.key)
                                   if game.locked else "")
            self.question.setText(t("pillar_match.question"))
            # Rounds FINISHED, which is `at` -- not at + 1, which is the one being played and
            # has not been scored yet. Shown from the second item onwards.
            done = game.at + (1 if game.locked else 0)
            self.score.setVisible(done > 0)
            self.score.setText(t("pillar_match.complete_score",
                                 score=str(game.first_try), of=str(done)) if done else "")
            if game.last == "correct":
                self.feedback.setText(t("pillar_match.correct",
                                        pillar=self._pillar_name(game.item.pillar)))
            elif game.last == "wrong":
                self.feedback.setText(t("pillar_match.wrong"))
            else:
                self.feedback.setText(t("pillar_match.instruction"))
        self.title.setFont(self._font(self.title.text(), 31, True))
        self.progress.setFont(self._font(self.progress.text(), 20, True))
        self.score.setFont(self._font(self.score.text(), 20, True))
        self.item_name.setFont(self._font(self.item_name.text(), 25, True))
        self.question.setFont(self._font(self.question.text(), 23, True))
        self.feedback.setFont(self._font(self.feedback.text(), 19, True))
        self.new_button.setFont(self._font(self.new_button.text(), 20, True))
        self.exit_button.setFont(self._font(self.exit_button.text(), 20, True))

    def follow_theme(self) -> None:
        c = palette()
        radius = self.win.side_px(11)
        edge = self.win.side_px(3)
        # TYPE SIZES IN THE PANEL'S OWN PIXELS. Without these the panel inherits the app
        # stylesheet's QWidget rule -- font-size px(24) -- which is scaled by the MAIN screen.
        # On a 1080x1920 panel beside a 1920x1200 display that lettering is about half the
        # size it was drawn at, which is the other half of why Harry's photographs showed a
        # thin strip of unreadable controls. Sized against the 1024-tall panel these were
        # designed on, so they come out the same on any panel.
        title = self.win.side_px(40)
        body = self.win.side_px(28)
        label = self.win.side_px(30)
        self.companion.setStyleSheet(
            # PAPER, not ink. This arrived inverted against the rest of the mat -- a white panel
            # at night and a black one by day -- which is how Prayer Day Journey arrived too.
            # The 7in beside this game would have been the opposite colour to the other five
            # and to every other screen.
            f"QWidget#pillarMatchCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            # AND THE EDGE IS INK, not paper. It was the same colour as the button's own fill,
            # so New Game and Exit had no visible outline at all -- the same fault, again, as
            # Prayer Day's answer buttons. paper and ink are the one pair this palette
            # guarantees to be opposites in both themes.
            f"QPushButton#controlButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; border-radius: {radius}px; }}"
            f"QPushButton:pressed {{ background: {c.pressed}; color: {c.ink}; }}"
            f"QLabel#gameTitle {{ font-size: {title}px; font-weight: bold; }}"
            f"QLabel#gameStatus {{ font-size: {body}px; }}"
            f"QPushButton {{ font-size: {label}px; font-weight: bold; }}")
        self.retell()
        self.board.update()
        self.preview.update()

    def start_again(self) -> None:
        self._advance.stop()
        self.game.restart()
        self.board.reset_item()
        self.changed.emit()

    def _drop(self, which) -> None:
        result = self.game.answer(which)
        if result == "correct":
            self.board.drag_position = None
            self.changed.emit()
            self._advance.start(self.SHOWN)
        elif result == "wrong":
            self.board.reject(which)
            self.changed.emit()

    def _next(self) -> None:
        self.game.next_round()
        self.board.reset_item()
        self.changed.emit()

    def press(self, action="") -> None:
        from .buttons import BACK
        if action == BACK or str(action).lower() in ("back", "exit", "escape"):
            self._advance.stop()
            self.leave.emit()
            return
        # A press cannot answer any more -- answering is a drag. All this carries on with:
        # the next item once one has been placed, or a fresh round once they are all done.
        result = self.game.press()
        if result in ("next", "complete"):
            self._advance.stop()
            self.board.reset_item()
        elif result == "again":
            self.board.reset_item()
        self.changed.emit()

    def showEvent(self, event):
        self.follow_theme()
        super().showEvent(event)

    def hideEvent(self, event):
        self._advance.stop()
        super().hideEvent(event)

    def _look_for_a_win(self) -> None:
        """Runs after every change. See salaah/winning.py for why it is once and not always."""
        announce_if_won(self, self.game.done)
