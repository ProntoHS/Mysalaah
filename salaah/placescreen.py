"""Telling the mat where it is, by postcode.

Reached from a row in Settings that shows where it currently thinks it is. Type a postcode, see
the prayer times it would give BEFORE saving anything, then keep it or go back.

Showing the times first is the point of the screen rather than a flourish. The failure this
exists to stop is a mat that is confidently wrong -- Bury's times in Birmingham, with nothing on
screen to suggest it. Typing a postcode and being shown a Fajr that is plainly forty minutes out
is how somebody catches a typo before it becomes the timetable they pray to for a fortnight.

It shares the keyboard with the Wi-Fi screen, which is why that one was built first.
"""
from __future__ import annotations

from datetime import date

from .qt import QtWidgets, Qt, Signal
from .keys import Keyboard
from .places import Cities, OUTWARD, PARTIAL, Places, clock_disagrees, tidy
from .prayer_times import PRAYERS, Place, times_for


class PlaceScreen(QtWidgets.QWidget):
    """A postcode, what it would mean, and a way to keep it."""

    saved = Signal(str, float, float)      # name or postcode, latitude, longitude

    #: Long enough for "Sydney Central Business District" and short enough that a stuck key
    #: cannot fill the screen.
    MOST = 34

    def __init__(self, window, places: Places | None = None,
                 cities: Cities | None = None):
        super().__init__()
        self.win = window
        self.places = places or Places(window.assets)
        self.cities = cities or Cities(window.assets)
        self.typed = ""
        self.found = None
        #: The town tapped in the list, if any. A postcode needs no tapping -- there is only
        #: ever one answer -- so this stays None on that path.
        self.chosen = None
        #: What the list is currently offering, so a tap knows what it tapped.
        self.towns: list = []
        self.setObjectName("placeScreen")

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(window.px(20), window.px(14), window.px(20), window.px(10))
        lay.setSpacing(window.px(8))

        top = QtWidgets.QHBoxLayout()
        self.heading = QtWidgets.QLabel(window.t("place.title"))
        self.heading.setObjectName("h1")
        top.addWidget(self.heading)
        top.addStretch(1)
        self.now = QtWidgets.QLabel("")
        self.now.setObjectName("sub")
        top.addWidget(self.now)
        lay.addLayout(top)

        self.field = QtWidgets.QLabel("")
        self.field.setObjectName("wifiField")
        self.field.setMinimumHeight(window.px(70))
        lay.addWidget(self.field)

        self.answer = QtWidgets.QLabel(window.t("place.ask"))
        self.answer.setObjectName("settingHead")
        self.answer.setWordWrap(True)
        lay.addWidget(self.answer)

        # The towns matching what has been typed, as buttons rather than a list widget: they
        # are tapped with a finger on glass, and every other choice on this mat is a button.
        self.matches = QtWidgets.QVBoxLayout()
        self.matches.setSpacing(window.px(4))
        self.town_buttons: list[QtWidgets.QPushButton] = []
        for n in range(Cities.SHOW):
            button = QtWidgets.QPushButton("")
            button.setObjectName("pill")
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setMinimumHeight(window.px(52))
            button.clicked.connect(lambda _c=False, at=n: self.pick(at))
            button.setVisible(False)
            self.matches.addWidget(button)
            self.town_buttons.append(button)
        lay.addLayout(self.matches)

        self.preview = QtWidgets.QLabel("")
        self.preview.setObjectName("placePreview")
        lay.addWidget(self.preview)

        # Only ever filled when the chosen town's timezone and the Pi's own clock disagree.
        self.clock = QtWidgets.QLabel("")
        self.clock.setObjectName("placeWarning")
        self.clock.setWordWrap(True)
        self.clock.setVisible(False)
        lay.addWidget(self.clock)

        self.keys = Keyboard(window)
        self.keys.typed.connect(self.add)
        self.keys.rubbed_out.connect(self.rub)
        self.keys.finished.connect(self.keep)
        lay.addWidget(self.keys, 1)

        feet = QtWidgets.QHBoxLayout()
        self.leave = QtWidgets.QPushButton(window.t("corner.back"))
        self.leave.setObjectName("backButton")
        self.leave.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        feet.addWidget(self.leave)
        feet.addStretch(1)
        self.save = QtWidgets.QPushButton(window.t("place.save"))
        self.save.setObjectName("primary")
        self.save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save.clicked.connect(self.keep)
        feet.addWidget(self.save)
        lay.addLayout(feet)
        self.redraw()

    # -- typing ------------------------------------------------------------------------------

    def add(self, character: str) -> None:
        """A letter typed. Kept AS TYPED, which it was not before 2.20.

        This used to force upper case and stop at eight characters, which is right for a
        postcode and wrong for everywhere else: "Bury St Edmunds" is fifteen characters and
        "BURY ST EDMUNDS" is not how anybody writes it. The postcode path upper-cases what
        it needs through tidy(), so nothing is lost by leaving the field alone.
        """
        if character and len(self.typed) < self.MOST:
            self.typed += character
            self.chosen = None          # typing again means the old choice is stale
            self.redraw()

    def rub(self) -> None:
        self.typed = self.typed[:-1]
        self.chosen = None
        self.redraw()

    def still_could_be_a_postcode(self) -> bool:
        """Whether what has been typed so far could yet GROW into an outward code.

        Only here to decide one thing: whether the box shows capitals. Harry had postcodes
        written in capitals from the start and they should stay that way -- BL9, not bl9 --
        but the same box now takes "Bury St Edmunds", and SHOUTING A TOWN'S NAME BACK is not
        how anybody writes one.

        So the box capitalises only while it could still be holding a postcode. "B" and "BL"
        and "BL9" all could; "Bur" could not, because after two letters an outward code wants
        a digit. In practice that means a town's name is capitalised for its first letter or
        two and then left alone, which reads as ordinary capitalisation rather than as a mode
        the person has to notice.
        """
        return bool(PARTIAL.match(tidy(self.typed)))

    def looks_like_a_postcode(self) -> bool:
        """Whether what has been typed is a UK outward code rather than a name.

        ONE BOX AND NO MODE SWITCH, which is the whole design. Harry kept the postcode path
        because it is offline, already tested, and puts a British mat within a mile or two
        where the nearest town of 15,000 people can be twenty miles off. But a box with two
        buttons over it saying which kind of thing you are about to type is a thing for a
        child to get wrong, so the box simply works out which it is.

        They cannot be confused for each other: an outward code always has a digit in it and
        no town in the table starts with one.
        """
        return bool(OUTWARD.match(tidy(self.typed)))

    def pick(self, at: int) -> None:
        """A town tapped in the list."""
        if 0 <= at < len(self.towns):
            self.chosen = self.towns[at]
            self.redraw()

    def redraw(self) -> None:
        self.field.setText(self.typed.upper() if self.still_could_be_a_postcode()
                           else self.typed)
        self.now.setText(self.win.t("place.now", name=self.win.settings.place or "—"))
        self.towns = []

        if self.looks_like_a_postcode():
            self.found = self.places.look_up(self.typed)
        else:
            self.towns = self.cities.search(self.typed) if self.typed else []
            # A name typed in full with one answer needs no tap. "Bury" is Bury.
            if self.chosen is None and len(self.towns) == 1:
                self.chosen = self.towns[0]
            self.found = self.chosen

        for n, button in enumerate(self.town_buttons):
            showing = n < len(self.towns) and self.found is not self.towns[n]
            button.setVisible(showing)
            if showing:
                button.setText(self.said_as(self.towns[n]))

        if not self.places.there and not self.cities.there:
            self.answer.setText(self.win.t("place.no_table"))
            self.preview.setText("")
        elif not self.typed:
            self.answer.setText(self.win.t("place.ask"))
            self.preview.setText("")
        elif self.found is not None:
            self.answer.setText(self.win.t("place.found", code=self.said_as(self.found)))
            self.preview.setText(self.times_line(self.found))
        elif self.towns:
            self.answer.setText(self.win.t("place.which"))
            self.preview.setText("")
        else:
            self.answer.setText(self.win.t("place.unknown", code=self.typed))
            self.preview.setText("")

        # The warning that makes a world-wide list safe to offer at all.
        wrong_clock = self.found is not None and clock_disagrees(self.found.timezone)
        self.clock.setVisible(wrong_clock)
        self.clock.setText(self.win.t("place.clock", zone=self.found.timezone)
                           if wrong_clock else "")
        self.save.setEnabled(self.found is not None)

    def said_as(self, found) -> str:
        """A place as a person would read it: Bury, or Springfield, MO (United States)."""
        if not found.is_a_town:
            return found.outward
        name = ", ".join(part for part in (found.outward, found.region) if part)
        country = self.cities.country_called(found.country)
        return f"{name} ({country})" if country else name

    def times_line(self, found) -> str:
        """What today would look like there. Shown before anything is saved, so a typo is
        caught by the times looking wrong rather than a fortnight later."""
        where = Place(found.latitude, found.longitude, found.outward)
        when = times_for(date.today(), where, self.win.school.id,
                         high_latitude=self.win.settings.high_latitude)
        parts = []
        for prayer in PRAYERS:
            at = when.get(prayer)
            parts.append(f"{self.win.t('prayer.' + prayer)} {at:%H:%M}" if at else
                         f"{self.win.t('prayer.' + prayer)} —")
        return "    ".join(parts)

    def keep(self) -> None:
        if self.found is None:
            return
        self.saved.emit(self.found.outward, self.found.latitude, self.found.longitude)
        self.typed = ""
        self.chosen = None
        self.redraw()

    def retitle(self) -> None:
        self.heading.setText(self.win.t("place.title"))
        self.leave.setText(self.win.t("corner.back"))
        self.save.setText(self.win.t("place.save"))
        self.redraw()
