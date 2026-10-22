"""The eighteen kinds of du'a, drawn as tiles on the big screen.

Touching Du'as on the 7" used to drop straight into one long list. That list is only going to
get longer -- there is a du'a for waking, for eating, for setting off, for worry -- and a single
scroll of them is no way to find the one you want while you are stood at the door. So the list
is now reached through a picture: eighteen tiles, and behind each one only the du'as that belong
to it.

The tiles are one drawing cut into eighteen, the same way the 7" menu is, so they share a hand
and the lettering on them is part of the design. Black on white, inverted for the dark screen by
the same cache that inverts the posture figures.

A category with nothing behind it yet still shows. It is drawn, it is touchable, and it lands on
the screen that says there is nothing here yet -- named, so it says WHICH one is empty. Hiding
the empty ones would make the menu change shape every time a du'a is added, and would quietly
tell nobody that the mat is missing most of them.
"""
from __future__ import annotations

from .qt import QtCore, QtWidgets, Qt, Signal
from .filmsheet import FilmSheet
from .knowledge import Tile

# In the order they were drawn: six across, three down. The name is the picture's file name,
# the word the rest of the app knows the category by, and what `cat` says in duas.json.
CATEGORIES = (
    "morning", "evening", "sleep", "waking", "food", "home",
    "mosque", "travel", "prayer", "protection", "forgiveness", "guidance",
    "gratitude", "family", "health", "worry", "knowledge", "kalima",
)
# The last tile is not a kind of du'a. It was "General du'as", which was the bin everything
# that did not fit went into, and Harry took it out; the six kalima have the eighteenth square
# now and it opens their own screen rather than a list of du'as. It is here rather than in a
# list of its own because the menu is one drawing cut into eighteen, so the tile exists whatever
# the app does with it.
NOT_A_KIND = ("kalima",)
ACROSS = 6


# The eighteen headings on the hadith sheet, in the order Harry drew them: six across, three
# down. What `cats` says in hadith.json, and the name of each tile's picture.
#
# Twelve when the section was built, four across. Harry redrew the sheet with six more on a
# third row -- marriage, business, justice, greetings, dress, health -- and the first twelve
# smaller to make room. Read off the drawing rather than remembered: the order here is the
# order the tiles appear in, and the boxes come out of menu.json, cut from that same sheet.
#
# A narration can be filed under several of these at once. `cats` is a list and the board asks
# whether a heading is in it, which is how the du'as have always worked, so nothing here had to
# change for it.
SAYINGS = ("faith", "prayer", "purification", "fasting", "charity", "hajj",
           "knowledge", "character", "family", "community", "daily", "hereafter",
           "marriage", "business", "justice", "greetings", "dress", "health")
SAYINGS_ACROSS = 6


def drawn_in(folder, name: str, lang: str):
    """The picture of this tile in that language, or the English one if it was not drawn.

    The still menus have the same problem the animated ones do: the words are part of the
    drawing, not text laid over it, so following the language means a different FILE. The
    animated sheets solve it with a films map in menu.json; a grid of stills has no such file,
    so the language goes on the end of the name -- step-hands.fr.png beside step-hands.png.

    English keeps the bare name. It is the one every other part of the mat falls back to, and
    renaming it to step-hands.en.png would have meant every folder of stills needing the full
    set before any of it worked.
    """
    if lang and lang != "en":
        said = folder / f"{name}.{lang}.png"
        if said.is_file():
            return said
    return folder / f"{name}.png"


class DuaMenu(QtWidgets.QWidget):
    """A sheet of tiles filling the big screen: eighteen of them, du'as or hadith headings."""

    chose = Signal(str)

    def __init__(self, window, names=CATEGORIES, folder="duas-menu", across=ACROSS):
        # The three arguments are what the hadith menu needed: twelve tiles four across, out of
        # its own drawing. Everything else about the screen -- the grid, the picture cache that
        # inverts for the dark screen, the empty-kind fallback -- is the same, and a second copy
        # of it would have been a second place to fix anything found in the first.
        super().__init__()
        self.win = window
        self.folder = folder
        self.across = across
        self.setObjectName("duaMenu")
        lay = QtWidgets.QGridLayout(self)
        lay.setContentsMargins(window.px(12), window.px(12), window.px(12), window.px(12))
        lay.setSpacing(window.px(10))

        # Drawn as one moving picture if the folder has one, and as the separate stills if it
        # does not. The sheet keeps the same Tile objects for its touch targets, so everything
        # downstream -- the names, the pictures, what a press does -- is the same either way.
        self.sheet = FilmSheet(window, folder, list(names))
        if self.sheet.ready:
            self.sheet.chose.connect(self.chose.emit)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.sheet, 0, 0)
            self.tiles: list[Tile] = self.sheet.tiles
            return
        self.sheet.deleteLater()
        self.sheet = None

        # The grid follows the app's layout direction, so in Urdu and Arabic the first tile is
        # the RIGHTMOST one and the row reads right to left.
        #
        # 1.59 pinned this to left-to-right. That was mine and it was wrong. The reasoning was
        # that Harry had drawn the Urdu and Arabic sheets with step 1 on the left like the
        # others, so mirroring them showed his drawing back to front -- true at the time, and
        # the wrong conclusion: the right fix was the drawing, not the layout. He has redrawn
        # both sheets with step 1 on the right, which is how somebody reading Urdu or Arabic
        # comes to a row of seven things, and they are cut to match. The pin has gone with it.
        self.tiles: list[Tile] = []
        for i, name in enumerate(names):
            tile = Tile(window.images, drawn_in(window.assets / folder, name,
                                                window.settings.lang), name)
            tile.clicked.connect(lambda _=False, n=name: self.chose.emit(n))
            lay.addWidget(tile, i // across, i % across)
            self.tiles.append(tile)

    @property
    def ready(self) -> bool:
        """Whether the drawing is there. Without it the du'as fall back to the plain list
        rather than to eighteen empty rectangles."""
        return all(t.path.is_file() for t in self.tiles)

    def follow_theme(self) -> None:
        if self.sheet is not None:
            self.sheet.follow_theme()
        for tile in self.tiles:
            tile.update()

    def retitle(self) -> None:
        """The words are drawn into the tiles, so there is nothing here to translate. Kept so
        the screen answers the call the rest of the app makes when the language changes."""

    def sizeHint(self):
        return QtCore.QSize(1920, 1008)
