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
from .places import Places
from .prayer_times import PRAYERS, Place, times_for


class PlaceScreen(QtWidgets.QWidget):
    """A postcode, what it would mean, and a way to keep it."""

    saved = Signal(str, float, float)      # outward, latitude, longitude

    def __init__(self, window, places: Places | None = None):
        super().__init__()
        self.win = window
        self.places = places or Places(window.assets)
        self.typed = ""
        self.found = None
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

        self.preview = QtWidgets.QLabel("")
        self.preview.setObjectName("placePreview")
        lay.addWidget(self.preview)

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
        if character.strip() and len(self.typed) < 8:
            self.typed += character.upper()      # postcodes are written in capitals
            self.redraw()

    def rub(self) -> None:
        self.typed = self.typed[:-1]
        self.redraw()

    def redraw(self) -> None:
        self.field.setText(self.typed)
        self.now.setText(self.win.t("place.now", name=self.win.settings.place or "—"))
        self.found = self.places.look_up(self.typed) if self.typed else None
        if not self.places.there:
            self.answer.setText(self.win.t("place.no_table"))
            self.preview.setText("")
        elif not self.typed:
            self.answer.setText(self.win.t("place.ask"))
            self.preview.setText("")
        elif self.found is None:
            self.answer.setText(self.win.t("place.unknown", code=self.typed))
            self.preview.setText("")
        else:
            self.answer.setText(self.win.t("place.found", code=self.found.outward))
            self.preview.setText(self.times_line(self.found))
        self.save.setEnabled(self.found is not None)

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
        self.redraw()

    def retitle(self) -> None:
        self.heading.setText(self.win.t("place.title"))
        self.leave.setText(self.win.t("corner.back"))
        self.save.setText(self.win.t("place.save"))
        self.redraw()
