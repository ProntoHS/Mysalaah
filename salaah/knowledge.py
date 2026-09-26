"""The Knowledge Corner: what the 7" screen offers between prayers.

Three things to read -- the Qur'an, du'as, and the six kalima -- chosen on the small screen,
with what was chosen opening on the big one. That division is the point of it. The little screen
is within reach of somebody sitting on the mat, so it holds the controls; the big screen is a
few feet away, so it holds the words, at a size worth reading from there.

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

# What the three tiles are, in the order they are shown. The name is the folder its picture
# lives in and the word the rest of the app knows the section by.
TILES = ("quran", "duas", "kalima")


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
        return QtCore.QSize(574, 307)      # the size they were drawn at


class KnowledgeScreen(QtWidgets.QWidget):
    """The three tiles, stacked down the 7" screen."""

    chose = Signal(str)

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("knowledge")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        self.heading = QtWidgets.QLabel(self.win.t("corner.title"))
        self.heading.setObjectName("cornerTitle")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.heading)

        self.tiles = []
        for name in TILES:
            tile = Tile(self.win.images, self.win.assets / "knowledge" / f"{name}.png", name)
            tile.clicked.connect(lambda _=False, n=name: self.chose.emit(n))
            lay.addWidget(tile, 1)
            self.tiles.append(tile)

    def follow_theme(self) -> None:
        for tile in self.tiles:
            tile.update()          # the cache keys on light or dark, so this is all it takes

    def retitle(self) -> None:
        self.heading.setText(self.win.t("corner.title"))
