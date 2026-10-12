"""Radio: a short list of stations, and one of them playing.

WHY THIS AND NOT A SHELF OF RECORDINGS, which is the whole design of it.

The tile here was Nasheeds until 1.70, and that section existed in an awkward shape: the mat
could not ship any recordings, because the artists worth listening to are on labels and the
"copyright free" collections of them are put up by people who do not hold the rights, so it
was a player pointed at a folder the owner had to fill themselves. A shelf with nothing on it
and a note explaining why.

A station is the other way round. Nothing is copied, nothing is stored, nothing is passed on:
the mat opens a public stream the way a radio set does, and the station carries its own music
licences because broadcasting is what it does. Harry: "this way i dont need to store anything,
no violation etc". He is right, and the Zain Bhikha question goes with it.

TWO THINGS THAT FOLLOW FROM IT BEING A RADIO.

It needs the internet, which the mat may not have -- and "has a Wi-Fi network" is not the same
as "can reach anything", which is a distinction network.py already makes. With nothing to
reach, the screen says so and offers the way to the Wi-Fi screen rather than listing stations
that cannot play.

And a station can be off the air. A file either plays or is missing; a stream can be listed,
addressed correctly, and simply not answer this evening. So the screen waits a couple of
seconds and then says that one is not answering -- see audio.Stream.

WHAT IS IN THE LIST. assets/content/radio/stations.json, which ships and can be replaced by a
release when an address changes, because they do: stations move host and the old URL goes
quiet. tools/check_stations.py is how that is found out before somebody's child finds it out.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .audio import Stream
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal

# A station's square, at 1080p: how big it is allowed to get, and how little it may shrink
# to before the grid gives up a column instead. The number of columns follows from those two
# and how many stations there are -- see RadioScreen.across.
BOX_MOST = 400
BOX_LEAST = 240
BOX_GAP = 24
# The white line round a square, and how round its corners are. Bold, as asked: this is the
# same look as the tiles on the 7" menu, which is where somebody has just come from.
BOX_EDGE = 6
BOX_ROUND = 18
# How much of the square the logo is allowed, across and down, inside the border. Short of
# the whole of it on purpose: these are marks drawn by as many different people as there are
# stations, and the breathing room is what makes them look like one set.
#
# Wider than tall because the allowances do different jobs. A square or upright mark is
# settled by the height and never comes near the width, so the width only ever binds on the
# wide ones -- Unity FM's wordmark is nearly four times as wide as it is tall -- and holding
# them to the same 0.74 made them small in a way that read as a worse logo rather than a
# wider one.
LOGO_WIDE = 0.86
LOGO_TALL = 0.74


class StationBox(QtWidgets.QAbstractButton):
    """One station: a square with a bold white border and the station's mark in the middle.

    Painted rather than built out of a styled QPushButton with a label or two inside it,
    because what goes in the square has to stay inside it at whatever size the grid hands it,
    and because what goes in the square is not always the same thing: the logo if there is
    one, the name wrapped across two or three lines if there is not, and underneath either of
    them, when it happens, the word that the station is not answering. A stylesheet cannot
    wrap a button's text, and a button with labels laid out inside it stops being one thing
    to press.

    THE LOGO IS A STENCIL, not a picture -- see assets/content/radio/logos/README.md. Only
    its alpha is kept, and the ink is painted through it here, at the moment of drawing. That
    is what lets one file be black on the day screen, white on the night one and white again
    over the red of the station that is playing, instead of three files that have to be kept
    in step with each other and with the theme.

    Red when it is playing -- the colour the mat uses for the thing happening now, the same
    as a lit prayer arch or a station's row before this was squares.
    """

    def __init__(self, window, station: dict):
        super().__init__()
        self.win = window
        self.station = station
        self.about = station.get("about", "")
        # Set when this station was pressed and nothing came back. Kept as a fact of its own
        # rather than worked out from the line of text, which is what the first version did:
        # the message and the station's own description went through the same field and the
        # square had to compare its text against a translation to know which it was holding.
        self.silent = False
        self.logo = QtGui.QPixmap(station["logo"]) if station.get("logo") else QtGui.QPixmap()
        if self.logo.isNull():
            self.logo = None
        # The name is set on the button even when it is never drawn: it is what the station
        # is called, and anything that asks a button what it says -- a test, a screen reader,
        # somebody debugging a list of six identical squares -- should get an answer.
        self.setText(station["name"])
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def stencilled(self, where: QtCore.QRect, ink: QtGui.QColor) -> QtGui.QPixmap:
        """The logo at [where]'s size, in [ink].

        Scaled and tinted every time it is drawn rather than kept: a square is repainted when
        it is pressed, when the theme turns over and when the grid is relaid, which is not
        often enough to be worth a cache, and a cache here is six pixmaps per window held for
        the life of the app on a machine with a gigabyte in it. The scale is the expensive
        half and the raster engine does it at the size asked for, once.
        """
        small = self.logo.scaled(where.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        # SourceIn keeps what is already there as a shape and replaces its colour, which is
        # the whole trick: the alpha survives, including the soft edge of every stroke, and
        # the white underneath it is thrown away.
        p = QtGui.QPainter(small)
        p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(small.rect(), ink)
        p.end()
        return small

    def say(self, about: str) -> None:
        """The line under the name, on a square that has no logo: what the station carries."""
        if about != self.about:
            self.about = about
            self.update()

    def not_answering(self, yes: bool) -> None:
        """Whether this station was pressed and stayed silent. The one thing a square says in
        words now, and it only says it when something has gone wrong."""
        if yes != self.silent:
            self.silent = yes
            self.update()

    def paintEvent(self, _):
        # Imported here rather than at the top: ui imports this module, so a plain import
        # would close the circle. The same dodge duaboard uses for ARABIC_ONLY.
        from .theme import palette
        from .ui import BRICK
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        edge = max(2, self.win.px(BOX_EDGE))
        box = QtCore.QRectF(self.rect()).adjusted(edge / 2, edge / 2, -edge / 2, -edge / 2)
        pen = QtGui.QPen(QtGui.QColor(c.ink))
        pen.setWidthF(edge)
        p.setPen(pen)
        p.setBrush(QtGui.QColor(BRICK) if self.isChecked()
                   else QtGui.QColor(c.pressed if self.isDown() else c.paper))
        p.drawRoundedRect(box, self.win.px(BOX_ROUND), self.win.px(BOX_ROUND))

        room = box.adjusted(edge * 2, edge * 2, -edge * 2, -edge * 2)
        ink = QtGui.QColor("white") if self.isChecked() else QtGui.QColor(c.ink)
        quiet = QtGui.QColor("#F0D6D3") if self.isChecked() else QtGui.QColor(c.soft)

        # One line of text ever gets drawn on a square now, and only when something is wrong:
        # that the station is not answering. Harry: "the icons should be self explanatory so
        # no text needed underneath". A fault is not self-explanatory, so the message keeps
        # its place and the logo moves up out of its way to make the room.
        trouble = self.win.t("radio.silent") if self.silent else ""
        under = QtCore.QRectF(room.x(), room.bottom() - room.height() * 0.22,
                              room.width(), room.height() * 0.22)
        if trouble:
            room = QtCore.QRectF(room.x(), room.y(), room.width(), room.height() * 0.76)

        if self.logo is not None:
            shape = QtCore.QRect(0, 0, int(room.width() * LOGO_WIDE),
                                 int(room.height() * LOGO_TALL))
            drawn = self.stencilled(shape, ink)
            p.drawPixmap(int(room.center().x() - drawn.width() / 2),
                         int(room.center().y() - drawn.height() / 2), drawn)
        else:
            # No artwork for this one, which is what every station had before 1.74: its name
            # as large as it will go, wrapped, and the line about what it carries underneath.
            name = QtCore.QRectF(room.x(), room.y(), room.width(),
                                 room.height() * (1.0 if trouble else 0.66))
            p.setPen(ink)
            p.setFont(self.fitted(self.station["name"], name, bold=True,
                                  most=int(room.height() * 0.22)))
            p.drawText(name, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                       self.station["name"])
            if self.about and not trouble:
                p.setPen(quiet)
                said = QtCore.QRectF(room.x(), room.bottom() - room.height() * 0.30,
                                     room.width(), room.height() * 0.30)
                p.setFont(self.fitted(self.about, said, bold=False,
                                      most=int(room.height() * 0.11)))
                p.drawText(said, int(Qt.AlignmentFlag.AlignHCenter
                                     | Qt.AlignmentFlag.AlignTop
                                     | Qt.TextFlag.TextWordWrap), self.about)

        if trouble:
            p.setPen(quiet)
            p.setFont(self.fitted(trouble, under, bold=False,
                                  most=int(under.height() * 0.46)))
            p.drawText(under, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                       trouble)

    def fitted(self, words: str, where: QtCore.QRectF, bold: bool, most: int) -> QtGui.QFont:
        """The largest size that puts [words] inside [where], wrapped, and no larger."""
        font = QtGui.QFont(self.win.pack_face())
        font.setBold(bold)
        size = max(10, most)
        while size > 10:
            font.setPixelSize(size)
            metrics = QtGui.QFontMetrics(font)
            needs = metrics.boundingRect(where.toRect(),
                                         int(Qt.AlignmentFlag.AlignCenter
                                             | Qt.TextFlag.TextWordWrap), words)
            if needs.height() <= where.height() and needs.width() <= where.width():
                break
            size -= 2
        font.setPixelSize(size)
        return font


class Stations:
    """The stations on the list, off the disk, and whether anybody has checked them."""

    def __init__(self, assets: Path):
        self.path = Path(assets) / "content" / "radio" / "stations.json"
        self._items: list[dict] | None = None
        self._reviewed = True

    @property
    def there(self) -> bool:
        return self.path.is_file()

    @property
    def reviewed(self) -> bool:
        """False until somebody has actually listened to every station on the list."""
        self.items
        return self._reviewed

    @property
    def items(self) -> list[dict]:
        if self._items is not None:
            return self._items
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._items = []
            return self._items
        self._reviewed = bool(raw.get("reviewed", True))
        out = []
        for row in raw.get("stations", []):
            # A station with no address is not a station. It would draw a row that does
            # nothing, which is worse than a list one shorter.
            if not isinstance(row, dict) or not str(row.get("url", "")).strip():
                continue
            key = str(row.get("key", ""))
            # The artwork is found by name rather than named in the row: a station's logo is
            # logos/<key>.png or there isn't one, and a station added to this file by hand --
            # which is the point of it being a file -- needs no second entry to remember. A
            # missing file is not a fault; the square carries the station's name instead,
            # which is what all of them did until 1.74.
            logo = self.path.parent / "logos" / f"{key}.png"
            out.append({
                "key": key,
                "name": str(row.get("name", "")) or key,
                "url": str(row["url"]).strip(),
                "about": str(row.get("about", "")),
                "country": str(row.get("country", "")),
                "lang": str(row.get("lang", "")),
                "logo": str(logo) if key and logo.is_file() else "",
            })
        self._items = out
        return self._items


class RadioScreen(QtWidgets.QWidget):
    """The stations, with one playing at a time.

    The same shape as the shelf it replaces: press one to play it, press the one that is
    playing to stop. No queue and no shuffle -- this is a radio on a prayer mat and a child
    picks a station.

    NOTHING ON IT BUT THE STATIONS, as of 1.75: no heading, no way out. Harry asked for both
    to go, and they can go here where they could not on any other screen, because the way out
    is on the other screen -- the 7" panel beside the mat is showing the menu the whole time,
    and touching any tile on it leaves. A heading saying "Radio" over eight station logos was
    saying what the pictures already say, and a Back button was a ninth thing to press on a
    screen whose whole point is that you press a station.

    Leaving still stops the sound: hideEvent does that, and it fires whichever way you leave.
    """

    wifi = Signal()         # "connect Wi-Fi" was pressed: the window knows where that is

    def __init__(self, window, stations: Stations):
        super().__init__()
        self.win = window
        self.stations = stations
        self.player = Stream(volume=window.settings.volume)
        self.playing: dict | None = None
        # The station that was pressed and did not answer, kept until something else is.
        # Not worked out from `playing` when the row is drawn: a station that has fallen
        # silent is no longer playing, so the two cannot be the same fact, and the version
        # that tried showed the message for one repaint and then lost it again.
        self.silent: dict | None = None
        self.rows_for: list[dict] = []
        self.boxes: list[StationBox] = []
        self.columns = 0
        # What the mat could reach when it was last asked. True to begin with: a screen that
        # opens saying "connect to Wi-Fi" and then fills in with stations a second later
        # looks broken, where one that lists them and then says it cannot reach them reads
        # as the truth arriving.
        self.reachable = True
        self.errand = None
        self.setObjectName("radioScreen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")      # the wide, touchable slider
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        inner.setObjectName("radioRoot")
        # A grid of squares rather than a list of rows, as Harry asked. Centred, and -- with
        # the heading gone -- centred down the screen as well, because there is no longer
        # anything for the block to sit under. Stretch above and below rather than only
        # below, so eight squares are a block in the middle of the screen and not a block
        # pushed against the top of it.
        held = QtWidgets.QVBoxLayout(inner)
        held.setContentsMargins(window.px(20), window.px(20), window.px(20), window.px(20))
        self.rows = QtWidgets.QGridLayout()
        self.rows.setSpacing(window.px(BOX_GAP))
        self.rows.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        held.addStretch(1)
        held.addLayout(self.rows)
        held.addStretch(1)
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, 1)

        # What the screen says when there is nothing to reach: not an error, a next step. The
        # button goes to the Wi-Fi screen the mat already has, which is one touch rather than
        # a notice saying "connect to Wi-Fi" and leaving somebody to find where.
        self.offline = QtWidgets.QWidget()
        off = QtWidgets.QVBoxLayout(self.offline)
        off.addStretch(1)
        self.offline_said = QtWidgets.QLabel(window.t("radio.offline"))
        self.offline_said.setObjectName("soonText")
        self.offline_said.setWordWrap(True)
        self.offline_said.setAlignment(Qt.AlignmentFlag.AlignCenter)
        off.addWidget(self.offline_said)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self.wifi_button = QtWidgets.QPushButton(window.t("radio.connect"))
        self.wifi_button.setObjectName("updateButton")      # the mat's big red block
        self.wifi_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.wifi_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wifi_button.clicked.connect(self.wifi.emit)
        row.addWidget(self.wifi_button)
        row.addStretch(1)
        off.addSpacing(window.px(24))
        off.addLayout(row)
        off.addStretch(1)
        outer.addWidget(self.offline, 1)

        # Watches the station that is playing: whether it answered, and whether it has since
        # fallen over. Both are the same question asked at different moments.
        self.watch = QtCore.QTimer(self)
        self.watch.setInterval(400)
        self.watch.timeout.connect(self.look)

    # What is on the list

    # Can this mat reach anything

    def online(self) -> bool:
        """What the screen last heard. Never asked here and now -- see ask_the_network."""
        return self.reachable

    def ask_the_network(self) -> None:
        """Find out whether the mat can reach anything, off this thread.

        Off the thread because the test is a name lookup, and a name lookup on a mat with no
        route anywhere can sit there for several seconds before it gives up. On the screen's
        own thread that is the whole app stopped -- including the clock -- at the exact
        moment somebody has pressed a tile. So the stations are listed on what was last
        heard, and the answer rearranges the screen when it arrives.

        One errand at a time: pressing the tile twice should not start two lookups.
        """
        if self.errand is not None and self.errand.isRunning():
            return
        from .network import Wifi
        from .wifiscreen import Errand
        if getattr(self.win, "wifi", None) is None:
            self.win.wifi = Wifi()
        wifi = self.win.wifi
        self.errand = Errand(lambda: wifi.there() and wifi.online())
        self.errand.done.connect(self.heard_back)
        self.errand.start()

    def heard_back(self, answer) -> None:
        was, self.reachable = self.reachable, answer is True
        if was != self.reachable:
            self.fill()

    def across(self, how_many: int) -> int:
        """How many squares to a row.

        As square an arrangement as the stations allow -- four go two by two, nine go three
        by three -- and then as many as the screen can take at a size worth pressing. The
        block is squarer than a single row of eight would be, and it grows down the screen
        rather than off the side of it as the list gets longer.

        WITH NO GAP IN IT, which is the part that is not just the square root. Eight stations
        rounded up to three a row is three, three and two: a block with a corner missing,
        which reads as a station having failed to load rather than as eight stations. So the
        count that divides the list evenly is preferred, taking the first one at or above the
        square root -- eight goes four and four, six goes three and three, nine stays three
        by three. A prime number of stations has no such count worth having (seven would go
        in one long row), so past twice the square root it gives up and takes the ragged
        block, which is the better of the two bad answers.
        """
        if how_many < 1:
            return 1
        tidy = math.ceil(math.sqrt(how_many))
        room = max(self.width() - self.win.px(40), self.win.px(BOX_LEAST))
        fits = max(1, (room + self.win.px(BOX_GAP))
                   // (self.win.px(BOX_LEAST) + self.win.px(BOX_GAP)))
        whole = next((n for n in range(tidy, min(how_many, 2 * tidy) + 1)
                      if how_many % n == 0), tidy)
        return max(1, min(whole, fits))

    def size_the_boxes(self) -> None:
        """Every square the same size, as large as the row allows and no larger."""
        if not self.boxes:
            return
        across = self.across(len(self.boxes))
        room = max(self.width() - self.win.px(40), self.win.px(BOX_LEAST))
        side = (room - self.win.px(BOX_GAP) * (across - 1)) // across
        side = max(self.win.px(BOX_LEAST), min(self.win.px(BOX_MOST), side))
        for box in self.boxes:
            box.setFixedSize(side, side)
        # And laid out again if the number of columns has changed under a resize.
        if across != self.columns:
            self.columns = across
            for i, box in enumerate(self.boxes):
                self.rows.addWidget(box, i // across, i % across)

    def fill(self) -> None:
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
        self.boxes = []
        self.columns = 0
        self.rows_for = self.stations.items
        across = self.across(len(self.rows_for))
        for i, station in enumerate(self.rows_for):
            box = StationBox(self.win, station)
            box.clicked.connect(lambda _=False, s=station: self.touched(s))
            self.rows.addWidget(box, i // across, i % across)
            self.boxes.append(box)
        self.columns = across
        self.size_the_boxes()
        here = self.online() and bool(self.rows_for)
        self.scroll.setVisible(here)
        self.offline.setVisible(not here)
        self.offline_said.setText(self.win.t("radio.offline" if not self.online()
                                             else "radio.empty"))
        self.wifi_button.setVisible(not self.online())
        self.mark()

    def mark(self) -> None:
        """Show which square is playing, and whichever one is not answering."""
        for box in self.boxes:
            station = box.station
            box.setChecked(station is self.playing)
            box.not_answering(station is self.silent)
            box.say(station.get("about", ""))
            box.update()

    # Playing one

    def touched(self, station: dict) -> None:
        if station is self.playing:
            return self.stop()
        self.play(station)

    def play(self, station: dict) -> None:
        self.win.stir()
        self.silent = None
        self.player.volume = self.win.settings.volume
        self.playing = station if self.player.play(station["url"]) else None
        self.mark()
        if self.playing is not None:
            self.watch.start()

    def stop(self) -> None:
        self.player.stop()
        self.playing = None
        self.watch.stop()
        self.mark()

    def quiet(self) -> None:
        """Stop, and forget that anything failed: the screen starts clean next time."""
        self.silent = None
        self.stop()

    def look(self) -> None:
        """The station stopped sounding. Either it never answered or it has dropped; both are
        shown the same way, because to somebody stood in front of it they are the same thing."""
        if self.playing is None:
            return
        if self.player.playing:
            return self.mark()      # still going
        self.watch.stop()
        self.silent, self.playing = self.playing, None
        self.mark()

    @property
    def saying(self) -> bool:
        """Whether something is sounding, for the sleep timer.

        Always False, and that is the one deliberate difference from the shelf this replaced.
        A nasheed is a few minutes and the screens stayed on for it; a station plays until it
        is turned off, and a mat that cannot ever go dark while the radio is on is a mat left
        bright all evening. Harry asked for the sound to carry on when the screens do go
        dark, which is what this returning False gets: sleep stops the panels, not the player.
        """
        return False

    def retitle(self) -> None:
        """The language changed, or the screen is being opened. There is no heading to
        rewrite any more -- the only words left are on the Wi-Fi notice, and they are only
        ever seen by somebody who cannot reach a station."""
        self.wifi_button.setText(self.win.t("radio.connect"))
        self.fill()

    def showEvent(self, ev):
        self.fill()
        self.ask_the_network()
        super().showEvent(ev)

    def resizeEvent(self, ev):
        # The squares are sized from the screen, so a different screen is a different size.
        super().resizeEvent(ev)
        self.size_the_boxes()

    def hideEvent(self, ev):
        """Walking off this screen stops the station -- unless the mat is going to sleep.

        A station playing on from behind the Qur'an could only be stopped by coming back here
        to find it, so leaving stops it. Sleep is not leaving: the panels go dark and the
        screen underneath is swapped back to the front door on the way, which fires this
        exactly as though somebody had walked away. Harry asked for the sound to carry on
        through that, so the one case is excepted. Waking lands at the front door with the
        radio still on, and the tile shows which station when you go back to it.
        """
        if not getattr(self.win, "asleep", False):
            self.stop()
        super().hideEvent(ev)
