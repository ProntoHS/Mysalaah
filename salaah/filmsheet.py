"""A menu drawn as one moving picture, with the tiles touchable over the top of it.

The du'a, hadith and 7in menus were eighteen, twelve and eight separate pictures, each found and
cut out of a still sheet. Harry has drawn them again as animations -- the whole sheet moving at
once -- which raises the question of how a drawing that is now one picture gets touched in
eighteen places.

The answer here is: it stays one picture. The film is drawn whole, scaled to the screen and
inverted for the dark one; the tile boxes are read out of menu.json, written there at build time
by the same cutter that used to cut the stills; and a transparent button is laid over each box.
Nothing is cut up at run time, so the drawing is shown exactly as it was made, seams and all --
and there is one timer redrawing one widget rather than eighteen QMovies on a Raspberry Pi.

The buttons are the same Tile the still menus use, kept quiet. That is not a trick to save a
class: a Tile knows its name and its still picture, which is what everything else on the mat
asks it for, and keeping the same object means the menu behaves identically whether it is
showing a film or the stills it falls back to.
"""
from __future__ import annotations

import json
from pathlib import Path

from .knowledge import Tile
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

def draw_themed(painter, film, where: QtCore.QRect) -> None:
    """Draw this frame of [film] into [where], turned inside out if the screen is dark.

    Nothing is kept. The first version of this cached each frame scaled and inverted, which
    looked like good sense and was not: a menu sheet is 1980x1080 and thirty-six frames, so a
    loop's worth is a couple of hundred megabytes, and with QMovie also told to cache all its
    frames a single window cost 135 MB that was never given back. Twelve windows came to 1.7 GB
    and the test suite was killed outright -- which is what a Raspberry Pi would have done too,
    more quietly, in somebody's house.

    So the frame is drawn straight, scaled by the raster engine, and the inversion is one more
    blit: white over the top in Difference mode gives |255 - pixel|, which is exactly inversion
    and costs no memory at all.
    """
    source = film.currentPixmap()
    if source.isNull() or where.isEmpty():
        return
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(where, source)
    if palette().dark:
        was = painter.compositionMode()
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Difference)
        painter.fillRect(where, QtGui.QColor("white"))
        painter.setCompositionMode(was)


class FilmSheet(QtWidgets.QWidget):
    """One animated sheet of tiles. `ready` is False if the film or its boxes are missing."""

    chose = Signal(str)

    def __init__(self, window, folder: str, names):
        super().__init__()
        self.win = window
        self.folder = folder
        self.setObjectName("filmSheet")
        self.tiles: list[Tile] = []
        self.shape = QtCore.QSize()
        self.boxes: dict[str, tuple] = {}
        self.film: QtGui.QMovie | None = None

        where = Path(window.assets) / folder
        try:
            described = json.loads((where / "menu.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        wide, tall = described.get("size", (0, 0))
        if wide < 2 or tall < 2:
            return
        self.shape = QtCore.QSize(int(wide), int(tall))
        self.boxes = {k: tuple(v) for k, v in (described.get("tiles") or {}).items()}
        # Every name the menu asked for must have a box. A sheet redrawn with a tile missing
        # would otherwise show the film with one square that does nothing, which looks like the
        # mat being broken rather than the drawing being wrong.
        if any(name not in self.boxes for name in names):
            self.boxes = {}
            return
        film = QtGui.QMovie(str(where / self.sheet_for(described, window.settings.lang)))
        if not film.isValid() or film.frameCount() < 2:
            self.boxes = {}
            return
        # NOT CacheAll. These sheets are 1980x1080 and three dozen frames; told to cache them
        # all, one menu holds a couple of hundred megabytes of decoded frames for as long as it
        # exists. Decoding a frame of a half-megabyte GIF on the way past is nothing by
        # comparison.
        #
        # Parented, and connected to a bound method rather than a lambda -- which is what
        # mosque.py has said to do since the first animated screen, and what I did not do. An
        # unparented QMovie wired up with a lambda keeps the widget alive through the
        # connection, so neither is ever collected: the suite grew by thirty megabytes a window
        # until the machine killed it two hundred and eighty tests in.
        film.setParent(self)
        film.frameChanged.connect(self.next_frame)
        self.film = film

        for name in names:
            tile = Tile(window.images, where / f"{name}.png", name, quiet=True)
            tile.setParent(self)
            tile.clicked.connect(lambda _=False, n=name: self.chose.emit(n))
            self.tiles.append(tile)

    @staticmethod
    def sheet_for(described: dict, lang: str) -> str:
        """Which drawing of this menu to show, for the language the mat is set to.

        Harry drew every menu again in each language the mat speaks, so the words on the tiles
        are part of the picture rather than text laid over it -- which is why there is a film
        per language rather than one film and a label.

        The BOXES are not per language. Every sheet was drawn to the same grid, and the tiles
        come out within seven pixels of the English across all six: a fiftieth of a tile, and
        a tile is a finger wide. One set of boxes is therefore the truth for all of them, and
        a second copy per language would be six more things to keep in step for no gain.
        There is a test that measures that drift rather than taking my word for it.

        An unknown language, or one with no sheet drawn yet, falls back to the English one --
        a menu in the wrong language still works; a menu that is not there does not.
        """
        films = described.get("films") or {}
        return films.get(lang) or films.get("en") or described.get("film", "menu.gif")

    def next_frame(self, _n: int = 0) -> None:
        self.update()

    @property
    def ready(self) -> bool:
        return self.film is not None and bool(self.boxes) and bool(self.tiles)

    # Where the film is drawn, which is also where the buttons go.

    def placement(self) -> tuple[QtCore.QRect, float]:
        """The rectangle the sheet is drawn in, and what it was scaled by."""
        if self.shape.isEmpty():
            return QtCore.QRect(), 1.0
        scale = min(self.width() / self.shape.width(), self.height() / self.shape.height())
        drawn = QtCore.QSize(max(1, int(self.shape.width() * scale)),
                             max(1, int(self.shape.height() * scale)))
        box = QtCore.QRect(QtCore.QPoint(0, 0), drawn)
        box.moveCenter(self.rect().center())
        return box, scale

    def lay_out_the_targets(self) -> None:
        box, scale = self.placement()
        for tile in self.tiles:
            left, top, right, bottom = self.boxes[tile.name]
            tile.setGeometry(box.x() + int(left * scale), box.y() + int(top * scale),
                             max(1, int((right - left) * scale)),
                             max(1, int((bottom - top) * scale)))
            tile.raise_()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.lay_out_the_targets()

    # Showing it

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(palette().paper))
        if self.film is not None:
            draw_themed(p, self.film, self.placement()[0])

    def follow_theme(self) -> None:
        self.update()

    def showEvent(self, ev):
        if self.film is not None:
            self.film.start()
        self.lay_out_the_targets()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Nobody is looking at it. A menu left turning behind the screen you are reading is the
        # Pi doing work for no one, all day.
        if self.film is not None:
            self.film.stop()
        super().hideEvent(ev)

    def sizeHint(self):
        return self.shape if not self.shape.isEmpty() else QtCore.QSize(1920, 1008)
