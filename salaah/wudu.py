"""Wu'du: the seven steps, and a page for each with the drawing moving beside the words.

Two screens. The first is Harry's sheet cut into seven tall columns, one per step, laid across
the big screen -- the same tile widget the du'a and hadith menus use, so it inverts for the dark
screen through the same cache and a tile is the whole target rather than a rectangle inside one.

The second is one step: the animation down the left at the full height of the screen, the step's
number and name across the top right, the explanation underneath it, and a square Back at the
bottom right. The film is the point of the screen, so it gets the height and the words fit
round it rather than the other way about.

The head is the one step with two films, because wiping the head and wiping the ears were drawn
as two pictures and are one step of the wu'du. They are stacked, sharing the same column.
"""
from __future__ import annotations

import json
from pathlib import Path

from .filmsheet import draw_themed
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import ArrowButton, TextSize
from .theme import palette

# How much of the width the drawing takes. Two drawings get more, because they are laid side by
# side: stacked, each one only ever gets half the height, and since these are tall portraits it
# is the height that decides how big they come out -- the head and the ears came out at 320x480
# each in a column 806 wide, which is a lot of empty paper either side of two small pictures.
FILM_SHARE = {1: 0.42, 2: 0.54}

# How large the description is at the first of the three sizes, at 1080p. Named here rather
# than written into the stylesheet alone, because the A buttons multiply it and the two have
# to be the same number -- salaah/ui.py reads it for the rule.
WORDS_PX = 38

# The three sizes the A buttons on a step choose between: how much larger the words are, and
# how much of the films' width is left once they have grown.
#
# The second number is why these are not the Qur'an's 1, 1.5, 2.25. A step has a fixed panel
# and a paragraph that has to stay inside it in one go -- Harry: "ample room for the text to
# be visible in one slide regardless of text size chosen" -- and in the room as it stands only
# a quarter again fits. The tightest of the seven in any language is `head` in French, which
# at the current size already fills a little over half its panel.
#
# So the films give up width as the words grow, and the words rewrap wider: fewer lines, each
# taller. They give up no more than they have to: measured across all seven steps in all seven
# languages, the panel at the third size still has a quarter of its height spare in the worst
# case (Spanish `head`), and the drawing comes out 333px rather than the 255px that handing
# the words half the screen would leave it. The three worst cases are 1.92, 1.49 and 1.24
# times the height the words need, and a test holds them above one.
WUDU_SIZES = ((1.0, 1.0), (1.3, 0.8), (1.6, 0.65))


class Steps:
    """The seven steps, off the disk, and whether anybody qualified has read them."""

    def __init__(self, assets: Path):
        self.path = Path(assets) / "content" / "wudu" / "wudu.json"
        self._steps: list[dict] | None = None
        self._reviewed = True

    @property
    def there(self) -> bool:
        return self.path.is_file()

    @property
    def reviewed(self) -> bool:
        self.steps
        return self._reviewed

    @property
    def steps(self) -> list[dict]:
        if self._steps is not None:
            return self._steps
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._steps = []
            return self._steps
        self._reviewed = bool(raw.get("reviewed", True))
        out = []
        for row in raw.get("steps", []):
            # A step with no film is a step with nothing to show, so it is left out rather than
            # drawn as an empty black panel.
            if not isinstance(row, dict) or not row.get("films"):
                continue
            out.append({
                "key": str(row.get("key", "")),
                "number": int(row.get("number", len(out) + 1)),
                "films": [str(f) for f in row["films"]],
                "text": {k: str(v) for k, v in (row.get("text") or {}).items()},
            })
        self._steps = out
        return self._steps

    def at(self, index: int) -> dict | None:
        return self.steps[index] if 0 <= index < len(self.steps) else None


class Film(QtWidgets.QWidget):
    """One animation, drawn as large as its box allows and turned inside out on a dark screen.

    Painted here rather than handed to a QLabel with setMovie. Two reasons, and the second is
    the one that matters. A QLabel cannot invert what it is given, and Harry's drawings are
    black lines on white paper: on the night screen they were a slab of white light beside
    words in the opposite colours. Everything else on the mat -- the tiles, the posture figures,
    the mosques -- inverts for the dark screen, and these should too, from the one set of files
    rather than a second set shipped alongside.

    And the old way needed a trick. setScaledSize is only read when a film is STARTED, so a
    resize meant stopping and restarting it to make the new size take. Painting the frame
    ourselves, the size is whatever we draw it at, and there is nothing to remember.
    """

    def __init__(self, path: Path):
        super().__init__()
        self.setObjectName("wuduFilm")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.shape = QtCore.QSize(512, 768)
        self.film = QtGui.QMovie(str(path))
        if self.film.isValid():
            self.film.setParent(self)        # so Qt takes it down with the widget
            self.film.jumpToFrame(0)
            if not self.film.currentPixmap().isNull():
                self.shape = self.film.currentPixmap().size()
            # A bound method, not a lambda: a lambda holds the widget through the connection
            # and neither is ever collected. See the note in filmsheet.py.
            self.film.frameChanged.connect(self.next_frame)

    # A widget showing a film asks for the film's own size, which is the wrong question twice
    # over: it is the box that decides how big the drawing is drawn, not the drawing. Two films
    # sharing a row with equal stretch came out 647px beside 381px, because the one that had
    # already been scaled up asked for more and the layout believed it.
    def sizeHint(self):
        return QtCore.QSize(10, 10)

    def minimumSizeHint(self):
        return QtCore.QSize(10, 10)

    def next_frame(self, _n: int = 0) -> None:
        self.update()

    def drawn_size(self) -> QtCore.QSize:
        """How big the drawing actually comes out, which is what the screen is judged on."""
        if self.shape.isEmpty() or self.width() < 20 or self.height() < 20:
            return QtCore.QSize()
        scale = min(self.width() / self.shape.width(), self.height() / self.shape.height())
        return QtCore.QSize(max(1, int(self.shape.width() * scale)),
                            max(1, int(self.shape.height() * scale)))

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        want = self.drawn_size()
        if want.isEmpty():
            return
        where = QtCore.QRect(QtCore.QPoint(0, 0), want)
        where.moveCenter(self.rect().center())
        draw_themed(p, self.film, where)

    def follow_theme(self) -> None:
        self.update()

    def start(self) -> None:
        if self.film.isValid():
            self.film.start()
            self.update()

    def stop(self) -> None:
        if self.film.isValid():
            self.film.stop()


class WuduStep(QtWidgets.QWidget):
    """One step: the drawing down the left, the words on the right, Back at the bottom."""

    back = Signal()         # off the first step: out to the seven
    stepped = Signal(int)   # to another step, by its place in the seven

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("wuduStep")
        self.films: list[Film] = []
        self.place, self.of = 0, 1      # which of the seven is up, and how many there are

        across = QtWidgets.QHBoxLayout(self)
        across.setContentsMargins(window.px(24), window.px(14), window.px(24), window.px(18))
        across.setSpacing(window.px(26))

        self.stage = QtWidgets.QWidget()
        self.stage.setObjectName("wuduStage")
        self.reel = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.Direction.LeftToRight, self.stage)
        self.reel.setContentsMargins(0, 0, 0, 0)
        self.reel.setSpacing(window.px(8))
        across.addWidget(self.stage, 0)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(window.px(14))
        self.heading = QtWidgets.QLabel("")
        self.heading.setObjectName("wuduHeading")
        self.heading.setWordWrap(True)
        self.heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.heading)

        self.words = QtWidgets.QLabel("")
        self.words.setObjectName("wuduWords")
        self.words.setWordWrap(True)
        self.words.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        right.addWidget(self.words, 1)

        # Bottom right, as asked, and square: the same shape as the big Back on the world and
        # hadith screens so the mat has one of these rather than a different one per room.
        #
        # Arrows rather than words. They walk the seven steps in order, which is how wu'du is
        # done, so the pair of them is the whole way round the section: < from the first step
        # is the way out to the seven, and > stops at the seventh rather than wrapping round to
        # the first, because the end of wu'du is not the beginning of it.
        # The chevrons are drawn rather than set in type -- see ArrowButton -- and they point
        # the way the screen reads. In Urdu and Arabic the pair mirrors to the other corner,
        # and an arrow that mirrored its position but not its head was pointing away from the
        # step it goes to.
        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(window.px(14))
        bottom.addStretch(1)
        # How large the words are, to the left of the arrows, as Harry asked. In the same row
        # so it is where a thumb already is, and before the arrows so that the pair which
        # walks the steps stays together at the corner.
        self.text_size = TextSize(window, self.chosen_size)
        self.text_size.chose.connect(self.resize_words)
        bottom.addWidget(self.text_size, 0, Qt.AlignmentFlag.AlignVCenter)
        bottom.addSpacing(window.px(18))
        self.back_button = ArrowButton(False, window.pack.rtl)
        self.on_button = ArrowButton(True, window.pack.rtl)
        for button, go in ((self.back_button, self.went_back), (self.on_button, self.went_on)):
            button.setObjectName("bigBack")
            button.clicked.connect(go)
            bottom.addWidget(button)
        # As tall as the arrows beside it, which is what Harry asked for -- the row was drawn
        # for a reading bar and next to two big square buttons it read as a trinket. Asked of
        # the button rather than written down here: how big a square button comes out is the
        # stylesheet's business, and a number copied from it goes stale the first time that
        # changes. Square, as he drew the boxes; the arrow buttons are a little wider.
        self.text_size.stand_as_tall_as(self.back_button.sizeHint().height())
        right.addLayout(bottom)
        across.addLayout(right, 1)

    @property
    def chosen_size(self) -> int:
        """Which of the three is set: 0, 1 or 2, whatever the settings file holds."""
        at = getattr(self.win.settings, "wudu_text_step", 0)
        try:
            at = int(at)
        except (TypeError, ValueError):
            at = 0
        return max(0, min(at, len(WUDU_SIZES) - 1))

    def resize_words(self, at: int) -> None:
        """One of the three A's was touched: set the words, and give the films their share."""
        self.win.settings.wudu_text_step = max(0, min(int(at), len(WUDU_SIZES) - 1))
        self.text_size.set_at(self.chosen_size)
        self.size_the_words()
        self.room_for_the_films()
        self.win.persist()

    def size_the_words(self) -> None:
        """The description at the chosen size.

        Set on the label itself rather than through the window's stylesheet: the app-wide rule
        gives every wu'du step the same size, and this is the one thing on the screen that has
        to differ from it. A rule on the widget beats the app's for that one property and
        leaves the colour alone.
        """
        bigger, _ = WUDU_SIZES[self.chosen_size]
        self.words.setStyleSheet(f"font-size:{max(8, int(self.win.px(WORDS_PX) * bigger))}px;")

    def went_back(self) -> None:
        if self.place > 0:
            self.stepped.emit(self.place - 1)
        else:
            self.back.emit()

    def went_on(self) -> None:
        if self.place < self.of - 1:
            self.stepped.emit(self.place + 1)

    def show_step(self, step: dict, heading: str, words: str,
                  place: int = 0, of: int = 1) -> None:
        self.place, self.of = place, of
        self.text_size.set_at(self.chosen_size)
        self.size_the_words()
        # The last step has nowhere forward to go. Shown but not pressable, rather than taken
        # away: a button that vanishes moves the other one, and a thumb on a touchscreen learns
        # where things are.
        self.on_button.setEnabled(place < of - 1)
        self.stop()
        while self.reel.count():
            old = self.reel.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
        self.films = []
        self.reel.setDirection(QtWidgets.QBoxLayout.Direction.LeftToRight
                               if len(step["films"]) > 1
                               else QtWidgets.QBoxLayout.Direction.TopToBottom)
        for name in step["films"]:
            film = Film(self.win.assets / "wudu" / name)
            self.reel.addWidget(film, 1)
            self.films.append(film)
        self.heading.setText(heading)
        self.words.setText(words)
        self.room_for_the_films()
        self.start()

    def room_for_the_films(self) -> None:
        share = FILM_SHARE.get(len(self.films), max(FILM_SHARE.values()))
        # And narrower again as the words grow, which is what keeps a step on one screen at
        # the larger sizes: the words rewrap into the width the films give up.
        share *= WUDU_SIZES[self.chosen_size][1]
        self.stage.setFixedWidth(max(1, int(self.width() * share)))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # The arrows are sized from the stylesheet, which is rebuilt for the new screen, so
        # the row beside them has to ask again or the two stop matching.
        self.text_size.stand_as_tall_as(self.back_button.sizeHint().height())
        self.room_for_the_films()
        # px() follows the window, so the words' own size has to be worked out again or a
        # resize leaves them set for the screen that is no longer there.
        self.size_the_words()

    def start(self) -> None:
        for film in self.films:
            film.start()

    def stop(self) -> None:
        for film in self.films:
            film.stop()

    def follow_theme(self) -> None:
        for film in self.films:
            film.follow_theme()

    def showEvent(self, ev):
        self.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Thirty frames a second of a drawing nobody can see is the Pi doing work for nothing,
        # and on a mat that is left on all day it is the difference between warm and hot.
        self.stop()
        super().hideEvent(ev)
