"""Pillar Match: drag each object to the matching pillar of Islam.

The 16-inch touchscreen is artwork-only. The companion widget is for the
7-inch screen. A Bluetooth ring remains usable as an alternative input.
"""
from __future__ import annotations

import pathlib
import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import mode as theme_mode, palette
from .winning import announce_if_won

PILLARS = ("faith", "prayer", "charity", "fasting", "hajj")

#: How wide a pillar's catching area is, as a fraction of the board. The pillars Harry drew
#: are .143 wide; this is a little more, so the gaps between them belong to somebody rather
#: than to nobody. Five zones of .19 side by side still leave a seam between each pair, so a
#: finger that lands squarely between two pillars is still told it missed rather than being
#: given the nearer one -- which is the right answer in a game about knowing which is which.
WIDE = 0.19


def board_ground(picture) -> int:
    """The grey the board's background is, read off its four corners.

    WHY THIS EXISTS. measure_the_board used to look for pixels "brighter than 60", which is
    the same thing as "not the background" only while the background is black -- and it was,
    on every board this game has ever had. Harry's jewelled pair of 21 November 2026 is the
    same artwork on two grounds, white for the light theme and black for the other two, and
    on the white one every pixel is brighter than 60. The five shafts then merge into a
    single run the width of the picture, the run count is 1 rather than 5, and the function
    returns FALLBACK -- five evenly spaced guesses -- without saying a word.

    The guesses are close enough to look right and wrong enough to matter: the fallback puts
    the top of the pillars at .48 where they start at .61, so the item would be released into
    mid-air rather than onto a capital. This is the fault the docstring of _zones warns about,
    arriving by a different door.

    The corners rather than a histogram: a board is a picture of five pillars standing on a
    plain ground, and its corners are the one part guaranteed to be that ground. The median of
    the four shrugs off a corner that happens to carry a flourish.
    """
    wide, tall = picture.width(), picture.height()
    corners = []
    for y in (0, tall - 1):
        line = picture.constScanLine(y)
        line.setsize(wide)
        row = bytes(line)
        corners += [row[0], row[wide - 1]]
    return sorted(corners)[len(corners) // 2]


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
    ground = board_ground(picture)
    mark = lambda value: abs(value - ground) > 60
    lit = []
    for y in range(tall):
        line = picture.constScanLine(y)
        line.setsize(wide)
        lit.append(sum(1 for value in bytes(line) if mark(value)))
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
            if mark(value):
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
    #: EVERY PILLAR THIS THING BELONGS TO, and a drop on any of them is right.
    #:
    #: It was a single pillar until 2.37. Harry: "some objects can & should fall into
    #: multiple categories." He is right, and the single field was quietly teaching
    #: otherwise -- a mosque is where zakat is collected, where taraweeh is prayed and
    #: where people break their fast, and making a child pick one of those and calling
    #: the other two mistakes teaches something false about what a mosque is.
    #:
    #: Order matters for one thing only: the first is the one the game names back when
    #: the child drops on a pillar that was not the one they chose. Nothing else reads it.
    pillars: tuple[str, ...]
    art: str


#: The seventeen things to sort. The `art` is the file in assets/children/pillars and it is
#: the same word as the key, because two names for one thing is two things to keep in step;
#: they were different until 2.36 and three of them had already drifted.
#:
#: Harry drew all seventeen for 2.37 and they replace the ten that were here. The old set was
#: drawn too loosely to tell apart -- his words: "i cant distinguish what i am looking at
#: which actually makes it difficult."
#:
#: WHICH THING BELONGS TO WHICH PILLAR IS NOT MINE TO DECIDE and none of it has been read by
#: anybody qualified. Fifteen of the seventeen are the plain reading of the picture. The two
#: that are not -- the mosque and the Qur'an -- are Harry's own words, and they are the reason
#: an item can now hold more than one pillar at all.
ITEMS = (
    Item("one_god", ("faith",), "one_god"),
    Item("declaration", ("faith",), "declaration"),
    Item("prayer_rug", ("prayer",), "prayer_rug"),
    Item("prayer_beads", ("prayer",), "prayer_beads"),
    Item("call_to_prayer", ("prayer",), "call_to_prayer"),
    Item("child_praying", ("prayer",), "child_praying"),
    Item("prayer_times", ("prayer",), "prayer_times"),
    Item("zakat_share", ("charity",), "zakat_share"),
    Item("cash_and_coins", ("charity",), "cash_and_coins"),
    Item("ramadan_days", ("fasting",), "ramadan_days"),
    Item("water_at_sunset", ("fasting",), "water_at_sunset"),
    Item("hajj_days", ("hajj",), "hajj_days"),
    Item("kaaba", ("hajj",), "kaaba"),
    Item("ihram", ("hajj",), "ihram"),
    Item("suitcase", ("hajj",), "suitcase"),
    # Harry's two, and his reasons: a mosque is "where zakat is collected, where taraweeh is
    # prayed and where people break their fast"; the Qur'an is "recited in prayer but was
    # revealed in Ramadan". Unreviewed, like everything else here.
    Item("mosque", ("charity", "prayer", "fasting"), "mosque"),
    Item("quran", ("prayer", "fasting"), "quran"),
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
    def correct_pillars(self) -> frozenset[int]:
        """EVERY pillar this item may be dropped on. More than one since 2.37."""
        return frozenset(PILLARS.index(p) for p in self.item.pillars)

    @property
    def correct(self) -> int:
        """One pillar that is right -- the first, which is the one the game names back.

        Kept alongside correct_pillars because a caller asking "where does this go?" wants
        somewhere to put it, not a set to choose from. Anything DECIDING whether a drop was
        right must use correct_pillars: on the mosque, `which == correct` is false for two
        of the three pillars it belongs to.
        """
        return PILLARS.index(self.item.pillars[0])

    def answer(self, which: int) -> str:
        if self.done or self.locked or not 0 <= which < len(PILLARS):
            return "nothing"
        self.active = which
        if which not in self.correct_pillars:
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
    """The seventeen pictures, loaded from assets/children/pillars once and kept.

    THESE WERE DRAWN IN CODE until 2.36 -- a hundred and thirty lines of arcs and polygons
    making a scroll, a hand, a rug, a dome. Harry drew proper icons, so the code went, and
    at 2.37 he redrew the lot because the first set could not be told apart on the mat.

    They are kept WHITE ON NOTHING, one file per item rather than one per item per language.
    His pack ships 170 cards and the picture is byte-identical in all ten -- checked pixel by
    pixel by tools/pillars/extract_cards.py before a single one is written, because keeping
    one copy of something that is not actually the same would throw nine away in silence.
    Seventeen files against 170, and 91 MB down to 1.2.

    White, because THE LINE-ART BOARD IS BLACK IN EVERY THEME. That board is a photograph of
    a drawing; it does not invert when the mat goes from night to day, so what sits on top of
    it cannot either. That is exactly what was wrong before: the item was painted in the
    palette's paper colour, which is white by day and BLACK AT NIGHT, on a board that is black
    at both. On the mat's own theme the thing the child is meant to drag was drawn black on
    black. The game could only be played by reading the 7in and dragging an object nobody
    could see.

    SINCE 2.52 THERE IS A COLOURED TWIN OF EACH, and the white reasoning above applies only to
    the line drawings it falls back to. Harry's painted set is used wherever it is present,
    in all three themes, because the boards it sits on are painted in all three themes too.
    A coloured picture must NOT be tinted: the tint is a SourceIn fill, so tinting a painting
    flattens it to one flat silhouette of whatever colour was asked for -- it exists to make a
    white line drawing visible on the 7in's pale panel, and a painting needs no such help.
    """

    CACHE: dict[str, QtGui.QPixmap] = {}
    #: Which kinds resolved to a painted twin rather than a line drawing. Recorded as they
    #: load, so draw() can tell without asking the filesystem on every frame.
    PAINTED: set[str] = set()

    @classmethod
    def picture(cls, window, kind) -> QtGui.QPixmap:
        if kind not in cls.CACHE:
            here = window.assets / "children" / "pillars"
            painted = here / f"{kind}-colour.png"
            if painted.is_file():
                picture = QtGui.QPixmap(str(painted))
                if not picture.isNull():
                    cls.PAINTED.add(kind)
                    cls.CACHE[kind] = picture
                    return cls.CACHE[kind]
            cls.CACHE[kind] = QtGui.QPixmap(str(here / f"{kind}.png"))
        return cls.CACHE[kind]

    @classmethod
    def draw(cls, p, kind, rect, window, ink=None, paper=None) -> None:
        """Draw item `kind` to fit `rect`. `ink`, when given, tints it -- for the 7in, whose
        panel IS the theme's paper and where a white LINE DRAWING would be white on white. A
        painted twin is never tinted; see the class docstring."""
        picture = cls.picture(window, kind)
        if picture.isNull():
            return
        if kind in cls.PAINTED:
            ink = None
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

class WordArt:
    """What the thing is called, in the mat's own language, as a picture of Harry's lettering.

    THESE ARE NOT TYPED OUT, AND THAT IS DELIBERATE. They are cropped from the cards Harry
    drew, one per item per language, by tools/pillars/extract_cards.py. The alternative was
    to read 170 words off his artwork and re-type them into the ten pack files, and in at
    least three of these scripts -- Bengali, Hindi, Urdu -- I cannot proof-read my own typing
    closely enough to swear a letter has not gone astray. These are religious terms. A
    crop has no transcription step in it to get wrong, and it carries the right shaping and
    joining for free, which hand-typed Arabic and Urdu very often do not.

    The cost is that they are pictures: they do not resize with the text-size setting and
    they are not in the pack, so Fonts.for_text never sees them and no font has to cover
    them. For a word that is always the same words, that is a fair trade.

    WHAT THE WORD DOES AND DOES NOT SAY. Harry: "i dont want them to know what pillar it
    belongs just the name of the item ... the word will say what the object is, thats all."
    In seven of the ten languages that is exactly what happens. In Arabic, Urdu and Hindi it
    cannot: a prayer mat in Arabic is sajjadat AL-SALAH and the pillar is AL-SALAH, so naming
    the object names the pillar. That is the language, not the translation. Two cards name
    their pillar in every language including English -- the 2.5% card says Zakat and the five
    days card says Hajj. Harry was told and chose consistency: "add it anyway, makes it
    consistent, and its a teaching aid not aiming for high scores".
    """

    CACHE: dict[tuple[str, str], QtGui.QPixmap] = {}

    @classmethod
    def picture(cls, window, lang, key) -> QtGui.QPixmap:
        at = (lang, key)
        if at not in cls.CACHE:
            path = window.assets / "children" / "pillars" / "words" / lang / f"{key}.png"
            cls.CACHE[at] = QtGui.QPixmap(str(path))
        return cls.CACHE[at]

    @classmethod
    def draw(cls, p, window, lang, key, rect, ink) -> None:
        """Draw the word inside `rect`, tinted `ink`, as large as it goes without overflowing.

        Fitted by WIDTH as well as height, smaller wins: these strips are five or six times
        wider than they are tall, and the long ones -- Bengali's prayer mat, Spanish's --
        would run off the side of a 7in panel if only the height were honoured.
        """
        picture = cls.picture(window, lang, key)
        if picture.isNull():
            return
        scale = min(rect.width() / picture.width(), rect.height() / picture.height())
        wide, tall = picture.width() * scale, picture.height() * scale
        box = QtCore.QRectF(rect.center().x() - wide / 2, rect.center().y() - tall / 2,
                            wide, tall)
        tinted = QtGui.QPixmap(picture.size())
        tinted.fill(Qt.GlobalColor.transparent)
        brush = QtGui.QPainter(tinted)
        brush.drawPixmap(0, 0, picture)
        brush.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        brush.fillRect(tinted.rect(), QtGui.QColor(ink))
        brush.end()
        p.drawPixmap(box, tinted, QtCore.QRectF(tinted.rect()))

class WordStrip(QtWidgets.QWidget):
    """The line on the 7in that says what the thing is. A picture, not a label -- see WordArt."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.key = ""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(window.side_px(52))

    def show_key(self, key) -> None:
        self.key = key
        self.update()

    def paintEvent(self, _):
        if not self.key:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        WordArt.draw(p, self.win, self.win.pack.lang, self.key,
                     QtCore.QRectF(self.rect()), palette().ink)


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
        self._measured = None
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
        # MEASURED ONCE PER BOARD, not once per frame. measure_the_board walks every pixel of
        # a 1920x1080 picture in Python and takes 132ms here -- and _zones is called from
        # paintEvent, so until 2.52 every repaint while a child was dragging an object paid
        # that, about seven frames a second on a machine far quicker than the mat. Nobody had
        # noticed because the game is playable at seven frames a second; it just feels like
        # treacle. What is cached is the MEASUREMENT, in fractions, not the rectangles: those
        # still come from the current width, so this survives a resize.
        if self._measured is None:
            self._measured = measure_the_board(self.board)
        top, bottom, centers = self._measured
        zones = []
        for center in centers:
            left = self.width() * (center - WIDE / 2)
            right = self.width() * (center + WIDE / 2)
            # KEPT ON THE BOARD. Harry's pillars sit nearer the edges than the old board's --
            # the outer centres are at .091 and .902 against .125 and .875 -- and half of
            # WIDE is .095, so the left-hand zone began eight pixels off the side of the
            # screen. Nothing could be dropped out there, so Shahadah was quietly the hardest
            # of the five to hit, and the "not that one" flash was drawn with its left edge
            # cut off. Found because a test reading ink across the zone asked the picture for
            # a pixel at x = -8 and was handed black.
            left, right = max(0.0, left), min(float(self.width()), right)
            zones.append(QtCore.QRectF(left, self.height() * top, right - left,
                                       self.height() * (bottom - top)))
        return zones

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

    def set_board(self, board) -> None:
        """Hand the widget a different board picture, and forget where the pillars were.

        Both halves matter. The zones are measured off the picture, so a new board with the
        pillars in different places must drop the old measurement, or every catching area
        stays where the previous board's pillars were -- the fault _zones exists to prevent,
        arriving from the other direction.
        """
        self.board = board
        self._measured = None
        self.update()

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
                # The pillar the child actually chose, not the item's first one. They are the
                # same for fifteen of the seventeen; for the mosque and the Qur'an they are
                # not, and settling the picture onto a pillar the child did not pick would
                # tell them they had been wrong when they had not.
                #
                # JUST ABOVE THE PILLAR, NOT ON IT. On it, the item was drawn white on the
                # pillar's white shaft and about a seventh of it survived -- a faint outline
                # where it happened to cross the dark arch. The same fault as the one that
                # made this game unplayable for six releases, in the one place the 2.36 test
                # was not looking: that test checks the item where it WAITS, on black, and
                # never where it LANDS. The band above the capitals is black in both themes
                # and empty on Harry's board, so the picture is whole there, it still sits
                # over the pillar it was given to, and his artwork is not drawn on.
                zone = zones[self.game.active]
                side = min(self.width() * .082, self.height() * .20)
                center = QtCore.QPointF(zone.center().x(), zone.top() - side * .60)
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
        self.board_image = QtGui.QPixmap(str(self.board_for(window.assets, theme_mode())))
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
    #: Still the line-art board, and still what playable() asks for: it has shipped since the
    #: game existed, so a mat that has it can always open the game even if the painted pair
    #: below never arrived.
    BOARD = "pillar-match-board.png"

    #: Harry's jewelled boards of 21 November 2026, by theme: "one for coloured / black theme,
    #: and the other for light theme". The same five pillars on two grounds, white and black,
    #: so dark and colour share one and light has the other. A theme with no entry, or an
    #: entry not on the mat, falls back to BOARD.
    PAINTED_BOARDS = {"light": "pillar-match-board-light.png",
                      "dark": "pillar-match-board-dark.png",
                      "colour": "pillar-match-board-dark.png"}

    @classmethod
    def board_for(cls, assets, mode: str) -> pathlib.Path:
        """Which board picture this theme gets. Falls back to the line-art one."""
        painted = assets / "children" / cls.PAINTED_BOARDS.get(mode, "")
        return painted if painted.is_file() else assets / "children" / cls.BOARD

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
        # What the thing is called, in the mat's language. A picture of Harry's own lettering
        # rather than a label -- WordArt says why. It sits directly under the picture of the
        # thing, which is where it sat on the card he drew it on.
        self.item_name = WordStrip(self.win)
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
            self.item_name.show_key("")
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
            # THE NAME IS THERE FROM THE START, and that is a decision taken with its cost
            # known rather than by accident.
            #
            # It waited until after the drop for exactly one release. 2.36 found that in six
            # of the ten languages an item's name contains its pillar's name -- Spanish calls
            # the rug "Alfombra de oracion" beside a pillar called "Oracion", Arabic cannot
            # say prayer rug without saying prayer -- so showing it early printed the answer
            # beside the question on six of the ten mats.
            #
            # Harry asked for it back at 2.37 and gave the reason: the pictures are what tell
            # a child what they are holding, and a picture they cannot name is a picture they
            # cannot think about. He was told plainly which languages leak and that two cards
            # -- the 2.5% one and the five days one -- name their pillar in every language
            # including English. His answer: "add it anyway, makes it consistent, and its a
            # teaching aid not aiming for high scores".
            #
            # So the leak is real, it is known, and it is the price of the thing being
            # teachable. Do not quietly "fix" this by hiding the word again.
            self.item_name.show_key(game.item.key)
            self.question.setText(t("pillar_match.question"))
            # Rounds FINISHED, which is `at` -- not at + 1, which is the one being played and
            # has not been scored yet. Shown from the second item onwards.
            done = game.at + (1 if game.locked else 0)
            self.score.setVisible(done > 0)
            self.score.setText(t("pillar_match.complete_score",
                                 score=str(game.first_try), of=str(done)) if done else "")
            if game.last == "correct":
                # The pillar they CHOSE, not the item's first one. The mosque belongs to
                # three; telling a child who put it on Zakah that it belongs to Salaah would
                # be correcting an answer that was right.
                self.feedback.setText(t("pillar_match.correct",
                                        pillar=self._pillar_name(PILLARS[game.active])))
            elif game.last == "wrong":
                self.feedback.setText(t("pillar_match.wrong"))
            else:
                self.feedback.setText(t("pillar_match.instruction"))
        self.title.setFont(self._font(self.title.text(), 31, True))
        self.progress.setFont(self._font(self.progress.text(), 20, True))
        self.score.setFont(self._font(self.score.text(), 20, True))
        self.question.setFont(self._font(self.question.text(), 23, True))
        self.feedback.setFont(self._font(self.feedback.text(), 19, True))
        self.new_button.setFont(self._font(self.new_button.text(), 20, True))
        self.exit_button.setFont(self._font(self.exit_button.text(), 20, True))

    def follow_theme(self) -> None:
        # THE BOARD ITSELF CHANGES NOW. Until 2.52 there was one board for all three themes,
        # so nothing here had to touch it; with a white board for light and a black one for
        # the other two, a theme change while the game is open has to swap the picture. The
        # zones are measured off whichever board is loaded, so they follow it without being
        # told -- but only if the new picture actually reaches PillarBoard, which is why the
        # board widget is handed it rather than just being repainted.
        wanted = self.board_for(self.win.assets, theme_mode())
        if wanted != getattr(self, "board_path", None):
            self.board_path = wanted
            self.board_image = QtGui.QPixmap(str(wanted))
            self.board.set_board(self.board_image)
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
