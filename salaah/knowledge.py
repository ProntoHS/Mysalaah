"""What the 7" screen offers between prayers: six tiles, chosen here, opened on the big screen.

That division is the point of it. The little screen is within reach of somebody sitting on the
mat, so it holds the controls; the big screen is a few feet away, so it holds the words, at a
size worth reading from there.

Three of the six have something behind them -- the Qur'an, the du'as and the six kalima. The
other three are drawn and touchable and land on a screen that says so. They are here rather
than left out because the menu is one picture cut into six, and because a tile that is coming
is easier to live with than a menu that changes shape later.

It takes the place the Qibla compass used to have. The mat now has a mechanical compass set into
its frame, so the screen no longer has to be one.

The tiles are pictures rather than drawn here, because they were drawn by hand and the lettering
on them is part of the design. They are black on white, so on the dark screen they are inverted
the same way the posture figures are -- three white slabs glowing at Fajr would be no good.
"""
from __future__ import annotations

from pathlib import Path

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

# The tiles, in reading order: two across, three down, the way they were drawn. The name is
# the picture's file name and the word the rest of the app knows the section by.
# "salaah" is not a section of the Knowledge Corner at all: it is the way back to the front
# door, and it took the square the six kalima had until the du'a menu gave them one of its own.
# A tile rather than a button because this menu is six squares and always has been.
# Eight now rather than six: Harry redrew the sheet with Wu'du and Nasheeds on the end and the
# other six smaller. The two new ones have nothing behind them yet and land on the page that
# says so, named -- the same thing Hadith and World did until their sections were built.
TILES = ("quran", "duas", "salaah", "hadith", "settings", "world", "wudu", "nasheeds")
ACROSS = 2


class Tile(QtWidgets.QAbstractButton):
    """One touchable picture, as large as its share of the screen allows.

    An QAbstractButton rather than a QPushButton with an icon: a button draws its own frame and
    background and fights the picture, and on a touchscreen the whole tile should be the target
    rather than a rectangle somewhere inside it.
    """

    def __init__(self, pictures, path: Path, name: str):
        super().__init__()
        self.pictures = pictures
        self.path = path
        self.name = name
        self.setObjectName("tile")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(80)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        colours = palette()
        if self.isDown():
            p.fillRect(self.rect(), QtGui.QColor(colours.pressed))
        # The cache inverts for the dark screen and scales to the box, so the tile is drawn the
        # same way as every other picture in the app rather than by its own rules.
        picture = self.pictures.get(self.path, self.rect().size())
        if picture.isNull():
            p.setPen(QtGui.QColor(colours.strong))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.name)
            return
        where = picture.rect()
        where.moveCenter(self.rect().center())
        p.drawPixmap(where.topLeft(), picture)

    def sizeHint(self):
        return QtCore.QSize(433, 448)      # the size they were drawn at


class KnowledgeScreen(QtWidgets.QWidget):
    """The six tiles, two across and three down, filling the 7" screen.

    No heading over them. The tiles carry their own words, so a title above was saying a third
    thing on a screen that only has room for two -- and it took height the tiles wanted.
    """

    chose = Signal(str)

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("knowledge")
        lay = QtWidgets.QGridLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        self.tiles = []
        for i, name in enumerate(TILES):
            tile = Tile(self.win.images, self.win.assets / "knowledge" / f"{name}.png", name)
            tile.clicked.connect(lambda _=False, n=name: self.chose.emit(n))
            lay.addWidget(tile, i // ACROSS, i % ACROSS)
            self.tiles.append(tile)
        # No row or column stretch set here. A tile is already Expanding in both directions, so
        # the grid shares the screen out between them on its own -- lines that set the stretch
        # as well changed nothing, which was proved by taking them out and measuring.

    def follow_theme(self) -> None:
        for tile in self.tiles:
            tile.update()          # the cache keys on light or dark, so this is all it takes

    def retitle(self) -> None:
        """Nothing to retitle: the words are drawn into the tiles. Kept so the screen still
        answers the call the rest of the app makes when the language changes."""
