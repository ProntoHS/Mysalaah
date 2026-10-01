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

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

# How much of the width the drawing takes. Two drawings get more, because they are laid side by
# side: stacked, each one only ever gets half the height, and since these are tall portraits it
# is the height that decides how big they come out -- the head and the ears came out at 320x480
# each in a column 806 wide, which is a lot of empty paper either side of two small pictures.
FILM_SHARE = {1: 0.42, 2: 0.54}


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


class Film(QtWidgets.QLabel):
    """One animation, drawn as large as its box allows and no larger.

    A QMovie scaled by setScaledSize rather than a label scaling its own pixmap: the label would
    rescale every one of the thirty frames on the way past, which on a Pi is work done sixty
    times for every second of a drawing nobody is looking at closely.
    """

    def __init__(self, path: Path):
        super().__init__()
        self.setObjectName("wuduFilm")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.film = QtGui.QMovie(str(path))
        self.shape = QtCore.QSize(512, 768)
        if self.film.isValid():
            self.film.jumpToFrame(0)
            if not self.film.currentPixmap().isNull():
                self.shape = self.film.currentPixmap().size()
            self.setMovie(self.film)
        self._at = QtCore.QSize()

    # A QLabel showing a film asks for the film's own size, which here is the WRONG question
    # twice over: it is the box that decides how big the drawing is drawn, not the drawing. Two
    # films sharing a row with equal stretch came out 647 and 381 wide, because the one that had
    # already been scaled up asked for more and the layout believed it.
    def sizeHint(self):
        return QtCore.QSize(10, 10)

    def minimumSizeHint(self):
        return QtCore.QSize(10, 10)

    def fit(self) -> None:
        """Scale the film to the box, keeping its shape. Done on resize, not on every frame."""
        if not self.film.isValid() or self.shape.isEmpty():
            return
        room = self.size()
        if room.width() < 20 or room.height() < 20:
            return
        scale = min(room.width() / self.shape.width(), room.height() / self.shape.height())
        want = QtCore.QSize(max(1, int(self.shape.width() * scale)),
                            max(1, int(self.shape.height() * scale)))
        if want != self._at:
            self._at = want
            self.film.setScaledSize(want)
            # And make it take. setScaledSize is only read when the film is started, so on a
            # film already running the drawing stays at whatever size it was first laid out at
            # -- which on the mat is the wrong size until the next frame, and in a test is the
            # wrong size for ever, because no time passes and nothing ticks. jumpToFrame does
            # NOT do it; only a start does, which was worth finding out before shipping a
            # screen that looked right solely because something was moving.
            if self.film.state() != QtGui.QMovie.MovieState.NotRunning:
                self.film.stop()
                self.film.start()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.fit()

    def start(self) -> None:
        if self.film.isValid():
            self.fit()
            self.film.start()

    def stop(self) -> None:
        if self.film.isValid():
            self.film.stop()


class WuduStep(QtWidgets.QWidget):
    """One step: the drawing down the left, the words on the right, Back at the bottom."""

    back = Signal()

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("wuduStep")
        self.films: list[Film] = []

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
        # hadith screens so the mat has one Back rather than a different one per room.
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        self.back_button = QtWidgets.QPushButton("")
        self.back_button.setObjectName("bigBack")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.back.emit)
        bottom.addWidget(self.back_button)
        right.addLayout(bottom)
        across.addLayout(right, 1)

    def show_step(self, step: dict, heading: str, words: str, back: str) -> None:
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
        self.back_button.setText(back)
        self.room_for_the_films()
        self.start()

    def room_for_the_films(self) -> None:
        share = FILM_SHARE.get(len(self.films), max(FILM_SHARE.values()))
        self.stage.setFixedWidth(max(1, int(self.width() * share)))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.room_for_the_films()

    def start(self) -> None:
        for film in self.films:
            film.start()

    def stop(self) -> None:
        for film in self.films:
            film.stop()

    def showEvent(self, ev):
        self.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Thirty frames a second of a drawing nobody can see is the Pi doing work for nothing,
        # and on a mat that is left on all day it is the difference between warm and hot.
        self.stop()
        super().hideEvent(ev)
