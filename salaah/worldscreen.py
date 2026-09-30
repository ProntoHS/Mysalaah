"""The world tile: the earth turning, with the way to the Kaaba drawn on it.

What it is for. The mat already knows which way to face -- there is a compass in its frame and a
screen that lines you up with it. This answers the question behind that one, which a child asks
first and an adult never quite stops wondering: where IS it, and where am I? A bearing is a
number. A line bending across half a turning planet from your own town to Mecca is the same
fact, and it is the one you remember.

It is drawn on the mat's own place, not on Bury. Set the postcode in Settings and the line
starts from there, because a line that always started in Lancashire would be a picture rather
than an answer.

More than one mat. The screen is built to draw any number of them -- a list of places, a line
from each, and a column at the side counting them -- and for now that list holds exactly one,
this mat, because nothing tells a mat about any other. That takes a service for mats to check
in with, which is a decision about children's home locations before it is a piece of code, so
it is deliberately not here yet. What IS here is the shape it will arrive into: put more mats in
the list and the screen already draws them.

A mat can be in the list and not on the screen, because half the earth is facing away. Bury and
Sydney are a hundred and fifty-three degrees apart, so they share the visible face for six frames
out of seventy-two -- around six tenths of a second in each turn. A count of two beside a single
line would look like a mistake, so the column dims a mat's dot while it is round the back. The
number and the picture then agree with each other.

The globe itself is an animation, and everything else is drawn over the top of it frame by
frame -- see globe.py for how the app knows where anything is on it. The Kaaba end of the line
needs no marker: the animator drew one, it turns with the globe, and the measurement that places
the line was taken from that marker, so the line ends on it.

The line is dotted rather than solid because it is a route and not a border, and blue because
everything drawn over the app's black and white is.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .globe import Globe, KAABA
from .qt import QtCore, QtGui, QtWidgets, Qt
from .theme import palette


@dataclass(frozen=True)
class Mat:
    """One mat on the globe: where it is, and what the column calls it.

    Only this mat is ever named. A remote one would be a dot and nothing else: a town beside a
    dot is a household, and this screen is looked at by children.
    """
    latitude: float
    longitude: float
    name: str
    mine: bool = False


class Pip(QtWidgets.QWidget):
    """The dot beside a mat's name in the column. Lit while that mat is on the near side of the
    earth and faint while it is round the back, so the count and the lines agree."""

    def __init__(self, size: int):
        super().__init__()
        self.lit = True
        self.setFixedSize(size, size)

    def light(self, on: bool) -> None:
        if on != self.lit:
            self.lit = on
            self.update()

    def paintEvent(self, _):
        colours = palette()
        shade = QtGui.QColor(colours.lapis if self.lit else colours.faint)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shade)
        p.drawEllipse(self.rect())


class TurningWorld(QtWidgets.QWidget):
    """The globe, and what is drawn on it."""

    def __init__(self, window, globe: Globe):
        super().__init__()
        self.win = window
        self.globe = globe
        self.mats: list[Mat] = []
        self.film: QtGui.QMovie | None = None
        if globe.there:
            movie = QtGui.QMovie(str(globe.film))
            if movie.isValid() and movie.frameCount() > 1:
                movie.setParent(self)
                # A bound method rather than a lambda, for the reason the call box learned it:
                # a lambda holding this widget outlives it, and a frame arriving after the
                # widget has gone took one of the two Qt kits down with it.
                movie.frameChanged.connect(self.turned)
                self.film = movie
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(window.px(240))

    @property
    def there(self) -> bool:
        return self.film is not None

    @property
    def home(self) -> tuple[float, float]:
        return self.win.settings.latitude, self.win.settings.longitude

    def show_mats(self, mats: list[Mat]) -> None:
        self.mats = list(mats)
        self.update()

    def turned(self, _frame: int) -> None:
        self.update()

    def start(self) -> None:
        if self.film is not None:
            self.film.start()

    def stop(self) -> None:
        if self.film is not None:
            self.film.stop()

    def showEvent(self, ev):
        self.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Off screen means stopped. A film left running is a timer waking the Pi ten times a
        # second to repaint something nobody is looking at.
        self.stop()
        super().hideEvent(ev)

    def circle(self) -> tuple[int, int, int]:
        """Where the globe is drawn in this widget: left, top, and how wide."""
        side = min(self.width(), self.height())
        return (self.width() - side) // 2, (self.height() - side) // 2, side

    def paintEvent(self, _):
        if self.film is None:
            return
        frame = self.film.currentPixmap()
        if frame.isNull():
            return
        colours = palette()
        left, top, side = self.circle()
        drawn = frame.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        if colours.dark:
            # The globe is drawn black on white, like every other picture here. On the dark
            # screen it is turned inside out rather than shipped twice: one pass over a
            # 600-pixel square, ten times a second, which is nothing next to a second copy of
            # the film on every mat.
            shot = drawn.toImage()
            shot.invertPixels()
            drawn = QtGui.QPixmap.fromImage(shot)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.drawPixmap(left, top, drawn)

        at = self.film.currentFrameNumber()
        wide = drawn.width()

        def place(spot):
            return QtCore.QPointF(left + spot.x * wide, top + spot.y * wide)

        # Everything drawn on the globe is sized off the globe, not off the window. The screen
        # it is drawn on can be a 7" panel or a monitor, and a line that is four pixels either
        # way is a rope on one and a thread on the other.
        thick = max(2.0, wide / 85)
        blue = QtGui.QColor(colours.lapis)
        paper = QtGui.QColor(colours.paper)

        def dotted(width: float, colour: QtGui.QColor) -> QtGui.QPen:
            pen = QtGui.QPen(colour, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            # Given in units of the pen's own width, which is why the two pens are given
            # different numbers: it keeps the dots of the casing under the dots of the line.
            pen.setDashPattern([thick * 0.9 / width, thick * 2.0 / width])
            return pen

        # Every line first, then every marker, rather than each mat's pair in turn. With mats
        # close together a line would otherwise be laid over the marker of the mat beside it,
        # and a ring with a dotted line through it reads as a smudge.
        drawn_at = []
        for mat in (self.mats or [Mat(*self.home, "", True)]):
            spot = mat.latitude, mat.longitude
            run = self.globe.route(at, spot, KAABA)
            # Laid down twice: once in the background's own colour a little wider, then the blue
            # over it. The route crosses land and sea, which on this globe are black and white,
            # and one blue would be lost on one of them. The casing gives it an edge on whichever
            # it is crossing and disappears into the other.
            if len(run) > 1:
                line = QtGui.QPolygonF([place(s) for s in run])
                for pen in (dotted(thick * 2.1, paper), dotted(thick, blue)):
                    p.setPen(pen)
                    p.drawPolyline(line)
            here = self.globe.at(at, *spot)
            if here.seen:
                drawn_at.append(place(here))

        # A ring rather than a dot: a dot on a black continent is a hole, and this has to read
        # over land and sea both.
        for middle in drawn_at:
            size = wide / 26
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QtGui.QPen(paper, thick * 2.1))
            p.drawEllipse(middle, size, size)
            p.setPen(QtGui.QPen(blue, thick * 1.1))
            p.drawEllipse(middle, size, size)
            p.setBrush(blue)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(middle, size * 0.36, size * 0.36)
        p.end()


class WorldScreen:
    """The globe with a line of words under it.

    Not a widget itself, deliberately. It makes the two things that go on the page and hands
    them over; being a widget as well would mean a parentless window sitting in the application
    for as long as the mat is on, holding a film.
    """

    ROWS = 8        # as many mats as the column can list before it runs out of page

    def __init__(self, window, page, lay):
        self.win = window
        self.globe = Globe(window.assets / "world")
        self.page = page
        self.world = TurningWorld(window, self.globe)
        self.pips: list[tuple[Pip, Mat]] = []

        # The globe is square and the screen is not, so on every screen the mat has there is
        # spare width beside it -- 275px of it on the 7" panel, because the globe's size is
        # decided by the height left over and never by the width. The column goes in that
        # spare room and costs the globe nothing at all.
        across = QtWidgets.QHBoxLayout()
        across.setContentsMargins(0, 0, 0, 0)
        across.setSpacing(window.px(18))
        across.addWidget(self.world, 1)

        rail = QtWidgets.QFrame()
        rail.setObjectName("worldRail")
        rail.setFixedWidth(max(1, window.px(2)))
        across.addWidget(rail)

        side = QtWidgets.QVBoxLayout()
        side.setContentsMargins(0, window.px(12), 0, 0)
        side.setSpacing(window.px(4))
        self.heading = QtWidgets.QLabel(window.t("world.active"))
        self.heading.setObjectName("worldTallyHead")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.heading)
        self.count = QtWidgets.QLabel("")
        self.count.setObjectName("worldTally")
        self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.count)
        side.addSpacing(window.px(10))
        self.who = QtWidgets.QVBoxLayout()
        self.who.setSpacing(window.px(6))
        # Indented so the list sits under the number rather than against the rail.
        self.who.setContentsMargins(window.px(40), 0, 0, 0)
        side.addLayout(self.who)
        side.addStretch(1)
        self.column = QtWidgets.QWidget()
        self.column.setLayout(side)
        self.column.setFixedWidth(window.px(200))
        across.addWidget(self.column)
        lay.addLayout(across, 1)

        # There was a line of words under the globe -- "Bury to Makkah, about 5,030 km" -- and
        # it is gone at Harry's asking. It was a fact rather than a thing to look at, and it
        # sat across the bottom of a screen whose whole job is the picture above it.
        if self.world.there:
            # The dots follow the film, so they dim on the frame the mat goes over the edge
            # rather than on the next time something else happens to redraw them.
            self.world.film.frameChanged.connect(self.relight)

    @property
    def there(self) -> bool:
        return self.world.there

    def mats(self) -> list[Mat]:
        """Every mat to draw. One for now -- this one.

        The list is the seam the community arrives through: a service that mats check in with
        would add the rest, rounded to the nearest whole degree before it ever leaves a house.
        On a 400px globe one degree is about a pixel and a quarter, so that costs the picture
        nothing and is the difference between a country and a street.
        """
        return [Mat(self.win.settings.latitude, self.win.settings.longitude,
                    self.win.settings.place or self.win.t("world.mine"), mine=True)]

    def relight(self, _frame: int = 0) -> None:
        """Dim the dot of any mat that has gone round the back, so the number beside the globe
        and the lines drawn on it never disagree."""
        if not self.world.there:
            return
        at = self.world.film.currentFrameNumber()
        for pip, mat in self.pips:
            pip.light(self.globe.at(at, mat.latitude, mat.longitude).seen)

    def retell(self) -> None:
        """Fill the column beside the globe."""
        mats = self.mats()
        self.heading.setText(self.win.t("world.active"))
        self.count.setText(f"{len(mats):,}")
        while self.who.count():
            old = self.who.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
            elif old.layout() is not None:
                while old.layout().count():
                    inner = old.layout().takeAt(0)
                    if inner.widget() is not None:
                        inner.widget().deleteLater()
        self.pips = []
        # A row each, up to what the column has room for. One today; the cap is here because a
        # list that grows without a limit is a page that pushes its own Back button off the
        # bottom, and the day the community arrives is not the day to find that out.
        for mat in mats[:self.ROWS]:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(self.win.px(10))
            pip = Pip(self.win.px(16))
            row.addWidget(pip, 0, Qt.AlignmentFlag.AlignVCenter)
            # Only this mat is named. A remote one gets the dot and nothing else.
            name = QtWidgets.QLabel(mat.name if mat.mine else "")
            name.setObjectName("worldWho")
            row.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)
            # Every row left aligned against a shared indent, so the dots line up in a line
            # whether the row beside them carries a name or not.
            row.addStretch(1)
            self.who.addLayout(row)
            self.pips.append((pip, mat))
        self.world.show_mats(mats)
        self.relight()
