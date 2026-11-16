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

#: How far away a place may be and still count as local, in kilometres.
#:
#: Was 25 while the file held one town. Five since the country went in, and the reason is not
#: that it shortens the list -- MOST does that. It is that THIS LIST CARRIES NO DISTANCES.
#: Sorted nearest first, which is what a distance column would tell you, and no words in ten
#: languages. That omission is clean only while everything on the list is genuinely near: at
#: 25km the screen can put a mosque 400 metres away above one twenty kilometres off with
#: nothing to say which is which, and a reader cannot tell. Five kilometres is what makes a
#: list with no distances on it honest.
#:
#: It costs almost nothing where people live. The fifth-nearest mosque is inside 1.7km in
#: Bury, Birmingham, London, Cardiff and Glasgow. Across fourteen towns measured, dropping 25
#: to 5 changed two: Norwich from five to four, Belfast from three to two.
#:
#: Where it does change things is the sparse end, and there it tells the truth. The nearest
#: mosque to Kendal is 31km away, to Hereford 37, to Aberystwyth 62. Those mats say nothing
#: here yet, which is better than a list implying a forty-minute drive is round the corner.
NEAR = 5.0

#: The most to draw, and it is the height of the screen rather than a judgement. The page has
#: 1,008 pixels; six cards need 1,058 and five need 888, which leaves room for the line at the
#: foot. Six could be made to fit by shrinking the cards, which would mean smaller words on a
#: mat whose other list grew its words this week so that eyesight need not be perfect.
#:
#: At five there is nothing to scroll and Qt draws no slider, which is what Harry was after.
#: The scroll area is left able to show one all the same: if a card ever grows -- a longer
#: name, a bigger type size -- a slider is a far better failure than a card cut in half.
MOST = 5


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
            # `checked` WAS the gate here, and is not any more. It held while the file was
            # seven streets in Bury; at 1,836 it would have had to be set on every row to let
            # anything be drawn, and a field that is always true is not a gate. Harry: "there
            # are thousands of mosques and i wont be ringing every single one."
            #
            # What replaced it is the line at the foot of the screen, which says where these
            # came from and that nobody has checked them. The field stays, and goes back to
            # meaning what it says -- somebody rang this one -- which is a record rather than
            # a filter, and the thing a correction sent back to the directory is drawn from.
            if not isinstance(place, dict):
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

        # NOTHING AROUND THE OUTSIDE. The padding has moved inside the scroll area, onto the
        # column of cards, so that the scroll area itself reaches both edges of the screen and
        # its slider sits hard against the right-hand one -- where the slider on every other
        # list already was. Margins out here inset the whole scroll area, slider and all, and
        # left this one floating 64px in from the edge while the rest were against it.
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # The name plate said "Local" above a page reached by pressing a tile with Local
        # written on it. Harry: "remove the header text 'Local' in local page, this should
        # move everything else up." It was the same caption-above-what-you-are-looking-at that
        # went from the surah list at 1.93, and the room it took is given to the list.
        self.nothing = QtWidgets.QLabel("")
        self.nothing.setObjectName("settingHead")
        self.nothing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nothing.setWordWrap(True)

        self.scroll = QtWidgets.QScrollArea()
        # The wide, touchable slider the lists share. The stylesheet's own note says a fourth
        # screen added later gets it "by joining the list", and I did not join it: this screen
        # shipped with the 14px bar Qt draws for a mouse pointer, on a mat scrolled with a
        # thumb. Harry, straight away: "the scroll bar used on the local page is barely
        # visible". The name is the whole of what makes it the right one.
        self.scroll.setObjectName("listScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.holder = QtWidgets.QWidget()
        self.column = QtWidgets.QVBoxLayout(self.holder)
        # The page's margins live here now, on the cards, not on the scroll area. See above.
        self.column.setContentsMargins(window.px(64), window.px(24), window.px(64),
                                       window.px(24))
        self.column.setSpacing(window.px(10))
        self.column.addStretch(1)
        self.scroll.setWidget(self.holder)

        # The 1 was load-bearing while there was a name plate above this: it was the only thing
        # claiming the room when the list was hidden, and without it the white plate took that
        # room and grew into a tall white slab down the left of the empty screen. The plate has
        # gone, so there is nothing left to stretch -- but the message is still the thing that
        # should have the page when there is no list, and it still says so here.
        # WHERE THESE CAME FROM, AND THAT NOBODY HAS CHECKED THEM.
        #
        # This is the one piece of writing on the page, and it is here because the drawing
        # rule went: at 1,836 places nobody can ring them all, so the screen has to say so
        # rather than imply otherwise by silence. Harry asked for it -- "maybe a disclaimer on
        # the local screen...along the lines the information has been obtained from a 3rd
        # party and may not be accurate" -- and it names the directory rather than saying "a
        # third party", because a name is something a parent can go and check, and because
        # naming them is the acknowledgement their notice asks for. It does both jobs at once.
        #
        # It is translated, which is a cost I spent the whole of 2.32 avoiding on this screen.
        # A warning a reader cannot read is not a warning, it is decoration, so this one gets
        # the ten languages and joins the list of wording nobody qualified has checked. Unlike
        # most of that list it wants a translator rather than a scholar, which is an easier
        # thing to arrange and worth arranging before anybody else's mat carries it.
        #
        # Below the list rather than above it, and outside the scroll area, so it is always on
        # the screen without pushing the mosques down -- Harry had the heading taken off this
        # page the day before to move them up, and this does not give that back.
        self.where_from = QtWidgets.QLabel("")
        self.where_from.setObjectName("settingVersion")   # the quiet grey of the version line
        self.where_from.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.where_from.setWordWrap(True)
        self.where_from.setContentsMargins(window.px(64), window.px(4),
                                           window.px(64), window.px(14))

        lay.addWidget(self.nothing, 1)
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.where_from)
        self.retell()

    def rows(self) -> list[QtWidgets.QWidget]:
        return [self.column.itemAt(i).widget() for i in range(self.column.count())
                if self.column.itemAt(i).widget() is not None]

    def retell(self) -> None:
        """Fill the list for wherever the mat is now, in whatever language it now speaks."""
        w = self.window_
        for row in self.rows():
            row.setParent(None)
            row.deleteLater()

        found = self.nearby.near(w.settings.latitude, w.settings.longitude)
        self.nothing.setText(w.t("corner.not_yet") if not found else "")
        self.nothing.setVisible(not found)
        self.scroll.setVisible(bool(found))
        for place in found:
            self.column.insertWidget(self.column.count() - 1, self.one(place))

        # Nothing listed, nothing to disclaim. A warning under an empty screen is a warning
        # about nothing, and a child who reads warnings about nothing stops reading warnings.
        self.where_from.setText(w.t("local.source") if found else "")
        self.where_from.setVisible(bool(found))

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
