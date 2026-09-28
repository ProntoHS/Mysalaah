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

from .qt import QtCore, QtWidgets, Signal
from .knowledge import Tile

# In the order they were drawn: six across, three down. The name is the picture's file name,
# the word the rest of the app knows the category by, and what `cat` says in duas.json.
CATEGORIES = (
    "morning", "evening", "sleep", "waking", "food", "home",
    "mosque", "travel", "prayer", "protection", "forgiveness", "guidance",
    "gratitude", "family", "health", "worry", "knowledge", "general",
)
ACROSS = 6


class DuaMenu(QtWidgets.QWidget):
    """The eighteen tiles, six across and three down, filling the big screen."""

    chose = Signal(str)

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("duaMenu")
        lay = QtWidgets.QGridLayout(self)
        lay.setContentsMargins(window.px(12), window.px(12), window.px(12), window.px(12))
        lay.setSpacing(window.px(10))

        self.tiles: list[Tile] = []
        for i, name in enumerate(CATEGORIES):
            tile = Tile(window.images, window.assets / "duas-menu" / f"{name}.png", name)
            tile.clicked.connect(lambda _=False, n=name: self.chose.emit(n))
            lay.addWidget(tile, i // ACROSS, i % ACROSS)
            self.tiles.append(tile)

    @property
    def ready(self) -> bool:
        """Whether the drawing is there. Without it the du'as fall back to the plain list
        rather than to eighteen empty rectangles."""
        return all(t.path.is_file() for t in self.tiles)

    def follow_theme(self) -> None:
        for tile in self.tiles:
            tile.update()

    def retitle(self) -> None:
        """The words are drawn into the tiles, so there is nothing here to translate. Kept so
        the screen answers the call the rest of the app makes when the language changes."""

    def sizeHint(self):
        return QtCore.QSize(1920, 1008)
