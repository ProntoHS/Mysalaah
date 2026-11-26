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

def turn_inside_out(painter, where: QtCore.QRect) -> None:
    """Invert what has been painted into [where]. How the mat turns a drawing over after dark.

    White over the top in Difference mode gives |255 - pixel|, which is exactly inversion and
    costs no memory at all -- see draw_themed for what the memory-keeping version cost.

    Its own function because two things need it and they must not drift: the menu sheets, which
    invert one tile-covered picture, and the front door, which inverts a whole screen.
    """
    was = painter.compositionMode()
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Difference)
    painter.fillRect(where, QtGui.QColor("white"))
    painter.setCompositionMode(was)


#: The three things that can be done to a drawing when the screen goes dark, and which one is
#: right is a property of the drawing rather than of the screen it is on.
#:
#: STAMP   -- white over the top of the rectangle in Difference mode. Costs nothing and is
#:            exactly inversion, and it is right for a line drawing that fills its box.
#: LIFT    -- the frame itself inverted, which leaves transparency alone. For a line drawing on
#:            a see-through ground, where stamping the box would invert the page showing through
#:            it: Harry's 1.84 menus came up as a white sheet before this existed.
#: KEEP    -- nothing at all. For a drawing in colour, which must not be turned over whatever
#:            the screen is doing, because turning it over is not a change of theme, it is a
#:            different picture: Harry, 17 November 2026, "i dont want you to invert the the
#:            actual child and wash basin etc, just the background only if possible".
#:
#: The 2.44 wu'du films are the first KEEP: they are in colour and their paper has been cut
#: away, so the page shows through where the paper was and the boy is the same pixels on both
#: screens. That is the whole of what Harry asked for, and it costs the mat nothing at all --
#: no inversion, no second set of files, no pass over the pixels.
STAMP, LIFT, KEEP = "stamp", "lift", "keep"


def coloured_twin(path: Path) -> Path:
    """The coloured version of this film, whether or not it exists.

    The same naming the rest of the mat uses for a second copy of a picture: PixmapCache
    writes the night version of `boy.png` as `boy-dark.png`, so the coloured version of
    `menu.ur.gif` is `menu.ur-colour.gif`. One rule for every film, so one helper finds any
    of them and nothing has to carry a list.
    """
    return path.with_name(f"{path.stem}-colour{path.suffix}")


def film_now(path: Path) -> Path:
    """The film to play on the screen as it is set now.

    The colour theme shows Harry's coloured drawing where there is one and the black-and-white
    film everywhere else, so a mat part way through an update -- or one whose colour artwork
    has not been drawn yet -- shows the picture it has rather than nothing. Light and dark
    share one film between them, as they always have.

    ASKED OF THE DISK, not of a list. Which screens have a coloured drawing changes with every
    release Harry draws for, and a list is the thing nobody remembers to update.
    """
    if not palette().colour:
        return path
    twin = coloured_twin(path)
    return twin if twin.is_file() else path


def how_it_turns(pix: "QtGui.QPixmap") -> str:
    """Which of the three a drawing wants, asked of the drawing.

    ASKED, NOT LISTED. The list of which pictures invert and which do not has been rewritten
    three times in five releases and been wrong after two of them, because a list is the thing
    nobody remembers to update when the artwork is redrawn. Both questions here are measured:
    whether the drawing is in colour, and whether it lets the page through.

    Answered once per film, off its first frame. Both are a pass over the pixels, which is
    nothing at load and would be everything at twelve frames a second.
    """
    from .render import has_colour
    if pix.isNull():
        return STAMP
    if has_colour(pix):
        return KEEP
    return LIFT if see_through(pix) else STAMP


def see_through(pix: "QtGui.QPixmap") -> bool:
    """Whether this drawing lets the page show through it anywhere.

    Asked once per film rather than once per frame: it is a pass over the pixels, which is
    nothing at load and would be everything at twelve frames a second.
    """
    if pix.isNull() or not pix.hasAlphaChannel():
        return False
    image = pix.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    for y in range(0, image.height(), 4):
        for x in range(0, image.width(), 4):
            if (image.pixel(x, y) >> 24) < 250:
                return True
    return False


def draw_themed(painter, film, where: QtCore.QRect, turns: str = STAMP) -> None:
    """Draw this frame of [film] into [where], turned over or not as [turns] says.

    Nothing is kept. The first version of this cached each frame scaled and inverted, which
    looked like good sense and was not: a menu sheet is 1980x1080 and thirty-six frames, so a
    loop's worth is a couple of hundred megabytes, and with QMovie also told to cache all its
    frames a single window cost 135 MB that was never given back. Twelve windows came to 1.7 GB
    and the test suite was killed outright -- which is what a Raspberry Pi would have done too,
    more quietly, in somebody's house.

    So the frame is drawn straight, scaled by the raster engine, and the inversion is one more
    blit: white over the top in Difference mode gives |255 - pixel|, which is exactly inversion
    and costs no memory at all.

    Three ways of handling a dark screen, then -- see STAMP, LIFT and KEEP above -- and which
    one is right depends on the drawing, not on this function. The white-over-the-top trick
    inverts the RECTANGLE, which is exactly the drawing when the drawing fills it -- and is
    wrong the moment it does not. Harry's 1.84 menus are drawn on a see-through ground, so
    after dark the trick was inverting the page showing through them and the 7in menu came up as
    a white sheet: caught by a test that samples the bottom corner, which is clear in his
    drawing and was reading 255 where it wanted under 30. For those, the frame itself is
    inverted instead -- render.invert leaves transparency alone -- which costs a pass over the
    pixels and is why it is not done for the big opaque sheets.

    And a drawing in colour is simply drawn, on both screens, which costs less than either.
    """
    source = film.currentPixmap()
    if source.isNull() or where.isEmpty():
        return
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    if not palette().dark or turns == KEEP:
        painter.drawPixmap(where, source)
        return
    if turns == LIFT:
        from .render import invert
        painter.drawPixmap(where, invert(source))
        return
    painter.drawPixmap(where, source)
    turn_inside_out(painter, where)


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
        self.sheet: Path | None = None
        self.plain: Path | None = None
        self.lang = "en"
        self.words = QtGui.QPixmap()
        self.turns = STAMP
        self.playing_colour = False
        # Set here, with the rest of the defaults, and not where they are filled in: there are
        # four early returns between this line and that one, and showEvent runs on a menu that
        # took any of them.
        self.overlay_spec: dict = {}
        self.overlays: dict[str, QtGui.QMovie] = {}
        self.overlay_theme: str | None = None
        self.overlay_folder = Path(window.assets) / folder

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
        self.sheet = where / self.sheet_for(described, window.settings.lang)
        #: The English film of this menu. The coloured film is named after THAT one and shared
        #: by every language -- see play().
        self.plain = where / self.sheet_for(described, "en")
        #: NOT falling back to English if this language has no words drawn. A coloured menu
        #: reading English on an Urdu mat is the fault this whole arrangement exists to stop,
        #: and it is worse than no colour at all. play() handles the missing case by keeping
        #: the black-and-white film, which is in the right language.
        self.lang = window.settings.lang
        #: Tiles whose PICTURE is replaced by a film of its own, drawn over the sheet after
        #: the sheet has been themed and before the words go on. See play_overlays.
        self.overlay_spec = {k: dict(v) for k, v in (described.get("overlays") or {}).items()
                             if k in self.boxes}
        if not self.play(self.sheet):
            self.boxes = {}
            return
        self.play_overlays()

        for name in names:
            tile = Tile(window.images, where / f"{name}.png", name, quiet=True)
            tile.setParent(self)
            tile.clicked.connect(lambda _=False, n=name: self.chose.emit(n))
            self.tiles.append(tile)

    def play(self, sheet: Path) -> bool:
        """Open the film for this sheet on the screen as it is set now, and keep it.

        Called at build and again whenever the mat moves into or out of the colour theme, so
        the drawing follows the setting without the menu being rebuilt -- a rebuild would lose
        the tiles, which are the touchable half of this screen.
        """
        # A MENU IN COLOUR IS ONE FILM AND A PICTURE OF ITS WORDS, which is not how any other
        # screen works and is worth saying why. Everywhere else -- the front door, the muezzin,
        # the globe -- a coloured drawing is one more film and filmsheet.film_now finds it. A
        # menu is drawn ten times over, once per language, and the ten differ ONLY in the words
        # at the foot of each tile. Shipping ten coloured films carried the same animation ten
        # times: 41MB for the five menus, against 4.9MB this way, and a coloured drawing
        # compresses about four times worse than the line art it stands beside. The lettering
        # never moves -- measured at 0.00% across all five sheets -- so a still picture of it is
        # not an approximation.
        #
        # So the FILM is named after the English one and shared by every language, and the WORDS
        # come out of a words/ folder keyed by language. If either is missing the mat falls back
        # to the black-and-white film, which is what a half-updated mat should show.
        wanted, words = film_now(sheet), None
        if palette().colour:
            shared = coloured_twin(self.plain)
            spelled = sheet.parent / "words" / f"{self.lang}.png"
            if shared.is_file() and spelled.is_file():
                wanted, words = shared, spelled
            else:
                wanted = sheet
        film = QtGui.QMovie(str(wanted))
        if not film.isValid() or film.frameCount() < 2:
            return False
        self.words = QtGui.QPixmap(str(words)) if words is not None else QtGui.QPixmap()
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
        was, self.film = self.film, film
        if was is not None:
            # The old film goes now rather than when the widget does. It is parented here, so
            # without this a mat switched back and forth between colour and dark collects a
            # QMovie per switch, each still wired to this widget's next_frame and each
            # repainting it on every frame of a film nobody can see.
            was.stop()
            try:
                was.frameChanged.disconnect(self.next_frame)
            except (TypeError, RuntimeError):
                pass
            was.setParent(None)
            was.deleteLater()
        # What this sheet wants done to it after dark, settled here off its first frame -- see
        # how_it_turns. Harry's 1.84 menus are drawn on a clear ground; everything before them
        # is not; and a sheet in colour is left alone. Asked again for every film, because the
        # answer belongs to the drawing and the coloured drawing is a different one.
        film.jumpToFrame(0)
        self.turns = how_it_turns(film.currentPixmap())
        self.playing_colour = palette().colour
        if self.isVisible():
            film.start()
        return True

    #: Which theme the mat is on, in the words menu.json uses for its overlay films. The three
    #: the settings screen offers, and the only three: light, dark, colour.
    @staticmethod
    def theme_now() -> str:
        if palette().colour:
            return "colour"
        return "dark" if palette().dark else "light"

    def play_overlays(self) -> None:
        """Open the overlay film each tile wants on the screen as it is set now.

        WHY THESE EXIST AT ALL. The sheet is one drawing and the mat's answer to a dark screen
        is to turn the whole of it over. That is right for line art and wrong for a painting:
        Harry's snow maze and his painted boy come out as negatives, which is not a night-time
        picture of them, it is a different and much worse picture. Two tiles therefore carry
        their own film, drawn after the sheet has been themed and so never inverted.

        Harry, 25 November 2026: "put this mosque gif on all 3 themes. the boy on white goes
        over the current salaah builder in light theme. boy with black background goes over
        dark / coloured theme. everything else stays same."

        So one tile has a single film for all three, and the other has one per theme. Both
        shapes are in menu.json rather than in here, because which tiles are painted is a fact
        about the artwork and it will change again.

        RELOADED ONLY WHEN THE THEME NAME CHANGES. Light and dark share the sheet but not
        necessarily these, so unlike the sheet this does have to follow a light/dark move --
        and it must not reopen two films on every repaint to do it.
        """
        theme = self.theme_now()
        if theme == self.overlay_theme:
            return
        self.overlay_theme = theme
        for movie in self.overlays.values():
            movie.stop()
            try:
                movie.frameChanged.disconnect(self.next_frame)
            except (TypeError, RuntimeError):
                pass
            movie.setParent(None)
            movie.deleteLater()
        self.overlays = {}
        for name, spec in self.overlay_spec.items():
            wanted = spec.get("film") or (spec.get("films") or {}).get(theme)
            if not wanted:
                # A theme with no film named for it keeps the sheet's own drawing, which is
                # the honest fallback: the tile looks as it did before any of this existed.
                continue
            path = self.overlay_folder / wanted
            if not path.is_file():
                continue
            movie = QtGui.QMovie(str(path))
            if not movie.isValid():
                continue
            movie.setCacheMode(QtGui.QMovie.CacheMode.CacheAll)
            movie.setParent(self)
            movie.frameChanged.connect(self.next_frame)
            self.overlays[name] = movie
            if self.isVisible():
                movie.start()

    def follow_theme(self) -> None:
        """The colour theme reads a different film; light and dark share one.

        Reloaded only when the colour-ness changes, so moving between light and dark is a
        repaint and costs nothing, as it always has.

        THE OVERLAYS ARE ASKED EVERY TIME, because they are the one part of this screen that
        does differ between light and dark: the Salaah Builder boy is painted on white for one
        and on black for the other. play_overlays itself does nothing when the theme name has
        not changed, so this stays the cheap call it has always been.
        """
        if getattr(self, "playing_colour", None) != palette().colour and self.film is not None:
            self.play(self.sheet)
        self.play_overlays()
        self.update()

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

    def on_screen(self, area, box=None) -> QtCore.QRect:
        """A rectangle given in the sheet's own pixels, as it lands on this screen.

        The same arithmetic lay_out_the_targets does for the touchable boxes, pulled out so
        the overlay films and the buttons cannot drift apart: both are rectangles measured off
        the same drawing, and a sheet scaled one way for one and another way for the other
        would put a painted tile beside the square you press for it.
        """
        if box is None:
            box = self.placement()[0]
        scale = self.placement()[1]
        left, top, right, bottom = area
        return QtCore.QRect(box.x() + int(left * scale), box.y() + int(top * scale),
                            max(1, int((right - left) * scale)),
                            max(1, int((bottom - top) * scale)))

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
        if self.film is None:
            return
        box = self.placement()[0]
        draw_themed(p, self.film, box, self.turns)

        # THE PAINTED TILES, OVER THE TOP AND NEVER TURNED OVER. After draw_themed, so the
        # inversion cannot reach them; before the words, so they cannot cover them. Both
        # halves of that sentence are the whole reason this is three lines here rather than a
        # change to the sheets -- see play_overlays.
        if self.overlays:
            p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
            for name, movie in self.overlays.items():
                frame = movie.currentPixmap()
                if frame.isNull():
                    continue
                p.drawPixmap(self.on_screen(self.overlay_spec[name]["area"], box), frame)

        if not self.words.isNull():
            # The coloured film carries no captions; the words go on here, in the mat's own
            # language. One film and ten small pictures instead of ten films -- see
            # tools/menu/install_colour.py. Drawn into the same rectangle, so it scales with
            # the drawing and lands on the tiles whatever screen this is.
            p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(box, self.words)

    def showEvent(self, ev):
        if self.film is not None:
            self.film.start()
        for movie in self.overlays.values():
            movie.start()
        self.lay_out_the_targets()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Nobody is looking at it. A menu left turning behind the screen you are reading is the
        # Pi doing work for no one, all day. The overlay films are stopped with it for exactly
        # the same reason, and they are the expensive ones: the snow maze is sixty frames.
        if self.film is not None:
            self.film.stop()
        for movie in self.overlays.values():
            movie.stop()
        super().hideEvent(ev)

    def sizeHint(self):
        return self.shape if not self.shape.isEmpty() else QtCore.QSize(1920, 1008)
