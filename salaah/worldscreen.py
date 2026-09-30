"""The world tile: the earth turning, with the way to the Kaaba drawn on it.

What it is for. The mat already knows which way to face -- there is a compass in its frame and a
screen that lines you up with it. This answers the question behind that one, which a child asks
first and an adult never quite stops wondering: where IS it, and where am I? A bearing is a
number. A line bending across half a turning planet from your own town to Mecca is the same
fact, and it is the one you remember.

It is drawn on the mat's own place, not on Bury. Set the postcode in Settings and the line
starts from there, because a line that always started in Lancashire would be a picture rather
than an answer.

The globe itself is an animation, and everything else is drawn over the top of it frame by
frame -- see globe.py for how the app knows where anything is on it. The Kaaba end of the line
needs no marker: the animator drew one, it turns with the globe, and the measurement that places
the line was taken from that marker, so the line ends on it.

The line is dotted rather than solid because it is a route and not a border, and blue because
everything drawn over the app's black and white is.
"""
from __future__ import annotations

from pathlib import Path

from .globe import Globe, KAABA, apart
from .qt import QtCore, QtGui, QtWidgets, Qt
from .theme import palette


class TurningWorld(QtWidgets.QWidget):
    """The globe, and what is drawn on it."""

    def __init__(self, window, globe: Globe):
        super().__init__()
        self.win = window
        self.globe = globe
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

        run = self.globe.route(at, self.home, KAABA)
        # Laid down twice: once in the background's own colour a little wider, then the blue
        # over it. The route crosses land and sea, which on this globe are black and white, and
        # one blue would be lost on one of them. The casing gives it an edge on whichever it is
        # crossing and disappears into the other.
        if len(run) > 1:
            line = QtGui.QPolygonF([place(s) for s in run])
            for pen in (dotted(thick * 2.1, paper), dotted(thick, blue)):
                p.setPen(pen)
                p.drawPolyline(line)

        # Home. A ring rather than a dot: a dot on a black continent is a hole, and this has to
        # read over land and sea both.
        here = self.globe.at(at, *self.home)
        if here.seen:
            middle = place(here)
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

    def __init__(self, window, page, lay):
        self.win = window
        self.globe = Globe(window.assets / "world")
        self.page = page
        self.world = TurningWorld(window, self.globe)
        lay.addWidget(self.world, 1)
        # Made here, put on the page by whoever built it: it shares a row with the Back button
        # so that the globe gets the height that row would otherwise have cost it.
        self.caption = QtWidgets.QLabel("")
        self.caption.setObjectName("settingHead")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @property
    def there(self) -> bool:
        return self.world.there

    def retell(self) -> None:
        """The line under the globe: where the mat is, and how far that is from the Kaaba.

        Rounded to ten kilometres. The mat knows where it is to within a postcode district, and
        writing 5,034 km would be claiming to know it to the street.
        """
        where = self.win.settings.place or self.win.t("world.here")
        km = apart((self.win.settings.latitude, self.win.settings.longitude), KAABA)
        self.caption.setText(self.win.t("world.line", place=where, km=f"{round(km, -1):,.0f}"))
