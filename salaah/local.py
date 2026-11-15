"""Local: the mosques near this mat, from a file somebody has checked.

WHY A FILE AND NOT A LOOKUP, which is the whole design of it.

The obvious build is to ask a map service what is nearby. I tried it: OpenStreetMap, live,
around Bury. It has **one** Muslim place of worship within 5 km and that one has no name on it;
the next twenty-one are eight kilometres away in Bolton and Rochdale, ten of them with an
address and four with a website. A screen built on that shows a child a nameless pin.

The same ground, taken from Mehmood Naqshbandi's UK Mosque Directory and checked by hand, is
seven mosques in Bury with street addresses and six phone numbers. So the data exists; it is
simply not in the places a machine can ask. That makes this a file, and a file has one rule:

    NOTHING GOES IN IT THAT A PERSON HAS NOT CHECKED.

Every entry carries `checked`. An entry that is not checked is not drawn -- not greyed out, not
marked provisional, not drawn -- because the failure this is guarding against is a child walking
to a mosque that shut in 2011, and there is no version of that which a label makes acceptable.
tools/local/draft_places.py makes the drafts; a human ticks them; tools/local/build_content.py
turns the ticked ones into the file this reads.

WHAT IS NOT ON THE SCREEN, and why each one is missing.

**No sect.** The source carries a theme for nearly every entry -- Deobandi, Bareilvi, Shia,
Sufi -- and says itself that those labels are contentious. A mat that prints them turns "where
can I pray" into "whose mosque is this", in a child's bedroom. They are read at build time to
spot one building listed twice, and they do not reach this module.

**No distance in numbers.** The list is nearest first, which is the whole of what a distance
column would tell you, and it costs no word in any language. "2.1 miles away" costs ten
translations nobody qualified has read, and a miles-or-kilometres question on a mat that speaks
Arabic and Chinese.

**No prayer times for the mosque.** Jamaat times change, this file cannot, and a wrong jamaat
time is worse than none. Harry: "i am not too concerned about jamaat times".

**No new words at all**, in fact. The heading is `corner.local`, which the ten packs already
carry because the tile needs it, and the empty screen says `corner.not_yet`, which the mat has
said since 1.89. A section that adds nothing unreviewed to nine languages is a section that
cannot be wrong in nine languages.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .qt import QtWidgets, Qt

#: How far away a place may be and still count as local, in kilometres. Generous on purpose:
#: the file is meant to grow to the whole country, and then this -- not the file -- is what
#: decides what a mat in Bury shows. Twenty-five kilometres is Bury to the far side of
#: Manchester, which is about as far as "local" stretches before it stops meaning anything.
NEAR = 25.0

#: The most to draw. Bury has seven; Birmingham, when the country goes in, has well over a
#: hundred inside the same radius, and a list that long is not a list, it is a phone book.
MOST = 12


def apart(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Kilometres between two points, great-circle."""
    r, rad = 6371.0, math.pi / 180
    dlat, dlon = (lat2 - lat1) * rad, (lon2 - lon1) * rad
    a, b = lat1 * rad, lat2 * rad
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class Nearby:
    """The places file, and the ones near a given point.

    Missing, unreadable or empty are all the same answer -- no places -- because the screen
    behaves identically for all three and a mat whose assets were half copied is a real mat.
    """

    def __init__(self, folder: Path) -> None:
        self.places: list[dict] = []
        self.source: dict = {}
        try:
            book = json.loads((folder / "local" / "places.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(book, dict):
            return
        self.source = book.get("source") or {}
        for place in book.get("places") or []:
            # `checked` is the gate, and it is checked here rather than at build time so that a
            # hand-edited file cannot get round it either. Anything without a name or a point
            # on the earth is no use on a screen whose only job is to say where to go.
            if not isinstance(place, dict) or not place.get("checked"):
                continue
            if not str(place.get("name", "")).strip():
                continue
            try:
                float(place["lat"]), float(place["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            self.places.append(place)

    def near(self, lat: float, lon: float, within: float = NEAR,
             most: int = MOST) -> list[dict]:
        """The nearest first. Ties broken by name, so the order cannot wobble between runs."""
        out = []
        for place in self.places:
            km = apart(lat, lon, float(place["lat"]), float(place["lon"]))
            if km <= within:
                out.append((km, str(place.get("name", "")), place))
        out.sort(key=lambda row: (row[0], row[1]))
        return [place for _, _, place in out[:most]]


class LocalScreen(QtWidgets.QWidget):
    """The list. Built once and refilled, because the mat can be moved and the language changed.

    No way back off it, like the radio and the world: the 7" is showing the menu the whole time
    this is up, so the way out is already under the hand that opened it.
    """

    def __init__(self, window, nearby: Nearby) -> None:
        super().__init__()
        self.window_ = window
        self.nearby = nearby

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(window.px(64), window.px(36), window.px(64), window.px(36))
        lay.setSpacing(window.px(12))

        plate = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel("")
        self.title.setObjectName("namePlate")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plate.addWidget(self.title)
        plate.addStretch(1)
        lay.addLayout(plate)

        self.nothing = QtWidgets.QLabel("")
        self.nothing.setObjectName("settingHead")
        self.nothing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nothing.setWordWrap(True)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.holder = QtWidgets.QWidget()
        self.column = QtWidgets.QVBoxLayout(self.holder)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(window.px(10))
        self.column.addStretch(1)
        self.scroll.setWidget(self.holder)

        # THE 1 IS LOAD-BEARING, and it is not about the message. It is the only thing in the
        # page claiming the room when the list is hidden, and without it the white name plate
        # takes that room instead: on the empty screen the plate grew into a tall white slab
        # down the left of the page with the word Local adrift in the middle of it.
        #
        # Found by looking at the screen as a mat in Birmingham sees it -- which is the state
        # every mat outside the seven streets this file covers is in, so it is the common case
        # and not an edge one. Every test passed while it was broken: the right rows were on
        # screen, which was none of them, and they were named correctly.
        lay.addWidget(self.nothing, 1)
        lay.addWidget(self.scroll, 1)
        self.retell()

    def rows(self) -> list[QtWidgets.QWidget]:
        return [self.column.itemAt(i).widget() for i in range(self.column.count())
                if self.column.itemAt(i).widget() is not None]

    def retell(self) -> None:
        """Fill the list for wherever the mat is now, in whatever language it now speaks."""
        w = self.window_
        self.title.setText(w.t("corner.local"))
        for row in self.rows():
            row.setParent(None)
            row.deleteLater()

        found = self.nearby.near(w.settings.latitude, w.settings.longitude)
        self.nothing.setText(w.t("corner.not_yet") if not found else "")
        self.nothing.setVisible(not found)
        self.scroll.setVisible(bool(found))
        for place in found:
            self.column.insertWidget(self.column.count() - 1, self.one(place))

    def one(self, place: dict) -> QtWidgets.QWidget:
        w = self.window_
        card = QtWidgets.QFrame()
        card.setObjectName("duaCard")
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(w.px(20), w.px(14), w.px(20), w.px(14))
        lay.setSpacing(w.px(2))

        name = QtWidgets.QLabel(str(place.get("name", "")))
        name.setObjectName("duaCardName")
        name.setWordWrap(True)
        lay.addWidget(name)

        # Street and postcode on one line: it is an address, and an address is read as one.
        where = ", ".join(x for x in (str(place.get("street", "")).strip(),
                                      str(place.get("postcode", "")).strip()) if x)
        if where:
            line = QtWidgets.QLabel(where)
            line.setObjectName("duaCardMeaning")
            line.setWordWrap(True)
            lay.addWidget(line)

        # No phone, no line. A row saying "no telephone number" tells a child nothing they can
        # act on and takes a word in ten languages to say it.
        phone = str(place.get("phone", "")).strip()
        if phone:
            tel = QtWidgets.QLabel(phone)
            tel.setObjectName("duaCardMeaning")
            lay.addWidget(tel)
        return card
