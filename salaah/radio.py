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
from pathlib import Path

from .audio import Stream
from .qt import QtCore, QtWidgets, Qt, Signal


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
            out.append({
                "key": str(row.get("key", "")),
                "name": str(row.get("name", "")) or str(row.get("key", "")),
                "url": str(row["url"]).strip(),
                "about": str(row.get("about", "")),
                "country": str(row.get("country", "")),
                "lang": str(row.get("lang", "")),
            })
        self._items = out
        return self._items


class RadioScreen(QtWidgets.QWidget):
    """The stations, with one playing at a time.

    The same shape as the shelf it replaces: a row each, press one to play it, press the one
    that is playing to stop. No queue and no shuffle -- this is a radio on a prayer mat and a
    child picks a station.
    """

    back = Signal()
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

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(window.px(20), window.px(10), window.px(20), 0)
        self.title = QtWidgets.QLabel(window.t("corner.radio"))
        self.title.setObjectName("namePlate")
        bar.addWidget(self.title)
        bar.addStretch(1)
        self.back_button = QtWidgets.QPushButton(window.t("corner.back"))
        self.back_button.setObjectName("backButton")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.leaving)
        bar.addWidget(self.back_button)
        outer.addLayout(bar)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")      # the wide, touchable slider
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        self.rows = QtWidgets.QVBoxLayout(inner)
        self.rows.setContentsMargins(window.px(20), window.px(10), window.px(20), window.px(20))
        self.rows.setSpacing(window.px(10))
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

    def fill(self) -> None:
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
        self.rows_for = self.stations.items
        for station in self.rows_for:
            row = QtWidgets.QPushButton(self.said(station))
            row.setObjectName("nasheedRow")      # the same wide row the shelf used
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.setCheckable(True)
            row.clicked.connect(lambda _=False, s=station: self.touched(s))
            self.rows.addWidget(row)
        self.rows.addStretch(1)
        here = self.online() and bool(self.rows_for)
        self.scroll.setVisible(here)
        self.offline.setVisible(not here)
        self.offline_said.setText(self.win.t("radio.offline" if not self.online()
                                             else "radio.empty"))
        self.wifi_button.setVisible(not self.online())
        self.mark()

    def said(self, station: dict) -> str:
        """A station's name, and what it carries underneath it if it says."""
        about = station.get("about", "")
        return f"{station['name']}\n{about}" if about else station["name"]

    def mark(self) -> None:
        """Show which row is playing, and whichever one is not answering."""
        for i, station in enumerate(self.rows_for):
            row = self.rows.itemAt(i).widget()
            if row is None:
                continue
            row.setChecked(station is self.playing)
            said = self.said(station)
            if station is self.silent:
                said = f"{station['name']}\n{self.win.t('radio.silent')}"
            row.setText(said)

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

    def leaving(self) -> None:
        self.quiet()
        self.back.emit()

    def retitle(self) -> None:
        self.title.setText(self.win.t("corner.radio"))
        self.back_button.setText(self.win.t("corner.back"))
        self.wifi_button.setText(self.win.t("radio.connect"))
        self.fill()

    def showEvent(self, ev):
        self.fill()
        self.ask_the_network()
        super().showEvent(ev)

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
