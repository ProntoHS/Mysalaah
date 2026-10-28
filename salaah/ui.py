"""Touchscreen interface for the mat display prototype. Runs full screen on the Pi's monitor."""
from __future__ import annotations

import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from . import __version__
from .buttons import BACK, NEXT
from .backlight import Backlight
from .audio import Call, Recitation, Timings, clamp_volume
from .audio import Span
from .content import PRAYERS, Content, LanguagePack, StepRef, UnitEntry
from .filmsheet import turn_inside_out
from .mosque import ArchButton, ArchShape, GearButton, MosqueScreen, ZoomVeil
from .prayer_times import Place, current_prayer, day_fraction, next_prayer, times_for
from .pages import TextPage, build_pages
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import (FONTS, MAX_ARABIC_PX, MIN_ARABIC_PX, Fonts, PixmapCache, PostureView,
                     ParallelText, Switch, TextBox, VolumeBar, load_posture_modes, load_timings)
from .session import Debouncer, Page as SessionPage, PrayerSession
from .tasbih import TasbihScreen
from .timing import TimingScreen
from .compass import CompassScreen
from .side import SideWindow
from .quran import Quran
from .passages import ArchMenu, PassageList, PassageReader, Passages
from .duamenu import DuaMenu, SAYINGS, SAYINGS_ACROSS
from .build_the_salaah import BuildTheSalaahScreen
from .five_pillars_sorter import FivePillarsSorterScreen
from .journey_jigsaw import Screen as JourneyJigsawScreen
from .mosque_maze import Screen as MosqueMazeScreen
from .prayer_day_journey import Screen as PrayerDayJourneyScreen
from .qibla_quest import QiblaQuestScreen
from .wudu import WORDS_PX as WUDU_WORDS_PX, Steps, WuduStep
from .radio import RadioScreen, Stations
from .duaboard import DuaBoard
from .recite import Store, WordTimes
from .call import Adhan, CallBox
from .reading import LIST_BAR, NUMBER_LINE, READING_TEXT_SIZE_PX, Reader, SurahList
from .qibla import MOVED, Facing, NoCompass, bearing_to_kaaba, turn_needed
from .power import Outputs
from .settings import Settings
from . import theme
from types import SimpleNamespace

PAPER = "#F5F6F3"
INK = "#1D2327"
LAPIS = "#274B8F"
# The banner is black whatever the theme, so the place is picked out in a blue that reads on
# black rather than the ink-dark lapis used on paper.
BANNER_BLUE = "#8FB1F0"
# How tall the black strip across the top is, at 1080p. Fixed rather than left to whatever is
# in it, because what is in it differs: the screens with a Main screen button came out five
# pixels taller than the front door and the mosque, and going between them the strip visibly
# grew. Harry saw it the other way round -- the main page's looking thin -- which is the same
# five pixels. It is the slider's own height (52, a finger rather than a mouse) plus the row's
# margins, so the strip is as tall as the tallest thing that HAS to fit in it, and anything
# added later has to fit rather than push it about.
BANNER_TALL = 52 + 10 + 10
# The pair of chevrons that walks a board's cards, at 1080p. Bigger than the reading bar's
# 64, which is what Harry asked for -- a board is read standing in front of it, where the
# reading bar is a bar on a screen you are already close to.
BOARD_ARROW = 88
STONE = "#6B737A"
LINE = "#D9DCD6"
MINT = "#3C8D6B"
BRICK = "#B4443A"
# Joined to a network that cannot reach anything. Neither green nor red would be true, and this
# is the state the mat actually spent an evening in.
AMBER = "#C08A2E"

# How large the Settings page is set. Raised together in 1.83 -- Harry: "increase font sizes to
# take advantage of extra room now" -- with the room coming from the cog, the school picker and
# the recitation note, all three of which went in the same version. They live here rather than
# inline because they have to be chosen together against one question: does the page still fit
# a 1920x1080 monitor in every language the mat speaks? Chinese is the one that decides it, by
# about 100 points over English, because CJK glyphs carry more line height at the same size.
# Raise any of these and the test that measures all seven languages will say so.
SET_HEAD = 37           # a section heading
SET_HINT = 24           # the small print under one, where there still is any
SET_VALUE = 29          # a setting's current value, and the words beside the switches
SET_PICKER = 31         # the dropdowns, and the rows inside them when open
SET_PICKER_TALL = 51    # how tall a dropdown is, which the text size alone does not set
SET_CHOICE = 31         # a row of circles to choose between
SET_KNOB = 35           # the circle itself
SET_PILL = 31           # the four boxes in the two-column block, on this page only

# The posture screen has no backlight of its own, so it is dimmed by drawing a black film over
# it. These ease that off: matched one-for-one to the slider it runs ahead of the monitor, which
# dims for real. 0.6 was picked by looking at the two screens side by side, not by arithmetic.
VEIL_STRENGTH = 0.6
VEIL_MOST = 60          # never darker than this: the postures still have to be followed
NIGHT = "#0B0C0D"
NIGHT_TEXT = "#E6E7E3"

# The seventh row of the language picker: Arabic, and nothing beside it.
#
# It is a language rather than a switch because that is what it is to the person using the mat.
# The six others say "show me the mat in this"; this one says "show me the Arabic and let me
# read it", which is the same kind of answer. Putting it anywhere else would have meant a
# second control saying "...and no meaning, thanks", which is the control that was just taken
# out for asking the same question twice.
#
# What it does: Harry's Arabic menus, the Qur'an across both pages instead of one with the
# meaning beside it, and no translation under anything. Words the mat has no Arabic for -- the
# Settings screen, the update messages -- fall back to English through the pack fallback that
# has always been there, so nothing goes blank.
ARABIC_ONLY = "ar"

NEXT_KEYS = {
    Qt.Key.Key_VolumeUp, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Right,
    Qt.Key.Key_PageDown, Qt.Key.Key_MediaNext, Qt.Key.Key_MediaPlay, Qt.Key.Key_MediaTogglePlayPause,
}
BACK_KEYS = {Qt.Key.Key_VolumeDown, Qt.Key.Key_Left, Qt.Key.Key_PageUp, Qt.Key.Key_MediaPrevious,
             Qt.Key.Key_Backspace}

# The Qibla compass. Off, because the mat has a mechanical compass set into its frame: a needle
# that needs no power, no calibration and no screen, and is easier to trust than a chip. The
# code stays because it works and costs nothing switched off -- turn this back on and the
# compass returns to the 7" screen, to start-up and to Settings exactly as it was.
QIBLA = False

# Two clicks closer together than this leave the prayer.
DOUBLE_CLICK = 0.55

# After the salam of a fardh prayer, before the beads: astaghfirullah (X3), then Ayat al-Kursi.
ISTIGHFAR = "istighfar"
AFTER_FARDH = (ISTIGHFAR, "ayat_kursi")


def no_focus(w: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """Buttons must not steal Space/Enter from the prayer button."""
    w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return w



class Bridge(QtCore.QObject):
    """Carries button events from the reader threads to the screen thread."""
    action = Signal(str)
    devices = Signal(list)
    power = Signal()


class ImageCache:
    """Keeps recently used slides scaled to the screen, so page turns are instant on a Pi."""

    def __init__(self, capacity: int = 14):
        self.capacity = capacity
        self._items: OrderedDict[tuple[str, int, int], QtGui.QPixmap] = OrderedDict()

    def get(self, path: Path, size: QtCore.QSize) -> QtGui.QPixmap:
        key = (str(path), size.width(), size.height())
        pix = self._items.get(key)
        if pix is None:
            src = QtGui.QPixmap(str(path))
            pix = src.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) \
                if not src.isNull() else src
            self._items[key] = pix
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)
        else:
            self._items.move_to_end(key)
        return pix


# Harry's map pin, traced off the drawing he sent rather than guessed at. Half the outline --
# the shape is symmetric, so only the right-hand side is kept -- as (how far down, how far out),
# both as fractions of the pin's own box. Thirty-seven samples, which is more than enough at the
# thirty pixels the banner draws it: the curve between two of them is under a third of a pixel.
#
# Kept as numbers rather than as the PNG for the reason the old drawn pin was drawn: it has to
# take the banner's colour, and it has to be sharp at whatever size the screen asks for. A
# picture would be one size, one colour, and another file in the release.
PIN_SIDE = (
    (0.0000, 0.0229), (0.0050, 0.0858), (0.0100, 0.1257), (0.0150, 0.1494),
    (0.0200, 0.1746), (0.0208, 0.1783), (0.0250, 0.1908), (0.0300, 0.2101),
    (0.0350, 0.2234), (0.0400, 0.2396), (0.0417, 0.2419), (0.0450, 0.2500),
    (0.0500, 0.2648), (0.0550, 0.2744), (0.0600, 0.2855), (0.0625, 0.2899),
    (0.0650, 0.2944), (0.0700, 0.3033), (0.0750, 0.3136), (0.0800, 0.3210),
    (0.0833, 0.3269), (0.0850, 0.3306), (0.0900, 0.3373), (0.0950, 0.3462),
    (0.1000, 0.3521), (0.1042, 0.3595), (0.1250, 0.3854), (0.1458, 0.4068),
    (0.1667, 0.4260), (0.1875, 0.4423), (0.2083, 0.4564), (0.2292, 0.4675),
    (0.2500, 0.4778), (0.2708, 0.4852), (0.2917, 0.4911), (0.3125, 0.4956),
    (0.3333, 0.4985), (0.3542, 0.5000), (0.3750, 0.5000), (0.3958, 0.4985),
    (0.4167, 0.4956), (0.4375, 0.4911), (0.4583, 0.4845), (0.4792, 0.4778),
    (0.5000, 0.4689), (0.5208, 0.4593), (0.5417, 0.4490), (0.5625, 0.4364),
    (0.5833, 0.4246), (0.6042, 0.4098), (0.6250, 0.3942), (0.6458, 0.3787),
    (0.6667, 0.3617), (0.6875, 0.3447), (0.7083, 0.3254), (0.7292, 0.3062),
    (0.7500, 0.2855), (0.7708, 0.2648), (0.7917, 0.2433), (0.8125, 0.2204),
    (0.8333, 0.1982), (0.8542, 0.1738), (0.8750, 0.1509), (0.8958, 0.1257),
    (0.9167, 0.1006), (0.9375, 0.0754), (0.9583, 0.0503), (0.9792, 0.0251),
    (1.0000, 0.0000),
)
PIN_HOLE = (0.3565, 0.1864)      # how far down its middle sits, and its radius
PIN_WIDE = 676 / 892             # the drawing is taller than it is wide


def map_pin(size: int, colour: str) -> QtGui.QPixmap:
    """Harry's map pin, drawn to fit a [size] by [size] box and filled with [colour].

    Drawn rather than loaded, as the one before it was: it takes whatever colour the words
    beside it are in, it is sharp at any size, and it keeps a stock-library picture -- watermark
    and licence and all -- out of the mat. What changed in 1.64 is the shape, which is now his
    rather than four curves of mine that happened to look like a pin.

    The outline is walked down the right-hand side and back up the left, because the pin is
    symmetric and storing half of it is the half that can be wrong.
    """
    pin = QtGui.QPixmap(size, size)
    pin.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pin)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # As tall as the box, as wide as that makes it, and centred in what is left.
    tall = float(size)
    wide = tall * PIN_WIDE
    left = (size - wide) / 2
    middle = left + wide / 2

    body = QtGui.QPainterPath()
    body.moveTo(middle + PIN_SIDE[0][1] * wide, PIN_SIDE[0][0] * tall)
    for down, out in PIN_SIDE[1:]:
        body.lineTo(middle + out * wide, down * tall)
    for down, out in reversed(PIN_SIDE[:-1]):
        body.lineTo(middle - out * wide, down * tall)
    body.closeSubpath()

    hole = QtGui.QPainterPath()
    hole.addEllipse(QtCore.QPointF(middle, PIN_HOLE[0] * tall), PIN_HOLE[1] * wide,
                    PIN_HOLE[1] * wide)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(colour))
    p.drawPath(body.subtracted(hole))
    p.end()
    return pin


def play_icon(size: int, colour: str, stop: bool = False) -> QtGui.QPixmap:
    """A ring with a play triangle inside it, drawn rather than loaded.

    The same mark is wanted beside every du'a and on the Qur'an's recite button, at sizes from a
    row's height to a bar's. Drawn, it is sharp at all of them and takes the colour of whatever
    it sits on, so one icon serves the light screen and the dark one. A picture would need two
    copies and would go soft on the big screen.

    With `stop` it becomes a square in the same ring, so the button does not change shape when
    the recitation starts.
    """
    icon = QtGui.QPixmap(size, size)
    icon.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(icon)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    ink = QtGui.QColor(colour)
    line = max(2.0, size * 0.075)
    middle = QtCore.QPointF(size / 2, size / 2)
    ring = size / 2 - line / 2 - size * 0.04
    pen = QtGui.QPen(ink, line)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(middle, ring, ring)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ink)
    if stop:
        side = size * 0.30
        p.drawRect(QtCore.QRectF(middle.x() - side / 2, middle.y() - side / 2, side, side))
    else:
        # Set a little right of centre: a triangle centred on its bounding box looks left-heavy
        # inside a ring, which is why every play button in the world is nudged across.
        reach = size * 0.21
        mark = QtGui.QPainterPath()
        mark.moveTo(middle.x() - reach * 0.82 + size * 0.03, middle.y() - reach)
        mark.lineTo(middle.x() + reach * 1.02 + size * 0.03, middle.y())
        mark.lineTo(middle.x() - reach * 0.82 + size * 0.03, middle.y() + reach)
        mark.closeSubpath()
        p.drawPath(mark)
    p.end()
    return icon


class Dot(QtWidgets.QWidget):
    """Green when a button is connected, red when not. No words: it is read at a glance."""

    def __init__(self, size: int):
        super().__init__()
        self.color = QtGui.QColor(BRICK)
        self.setFixedSize(size, size)

    def set_color(self, c: str) -> None:
        self.color = QtGui.QColor(c)
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(self.rect())


class ProgressLine(QtWidgets.QWidget):
    def __init__(self, height: int):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(height)

    def set_value(self, v: float) -> None:
        self.value = v
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        colours = theme.palette()
        p.fillRect(self.rect(), QtGui.QColor(colours.progress_track))
        w = int(self.width() * self.value)
        p.fillRect(0, 0, w, self.height(), QtGui.QColor(colours.progress_fill))


class Notice(QtWidgets.QDialog):
    """A message in the middle of the screen that cannot be missed or mistaken for decoration.

    Deliberately not a QMessageBox. Those are drawn by the desktop rather than by us, they
    ignore half of what a stylesheet tells them, and the two Qt kits disagree about the rest --
    so the one thing they will not reliably do is look like part of this app. This is a plain
    dialog we draw ourselves: black, white text, big enough to read across a room, and framed
    so it reads as a thing on top of the screen rather than part of it.

    It stays black in both themes on purpose. A message about the app itself is not part of the
    prayer, and looking different from everything around it is the point.
    """

    def __init__(self, parent, px, title: str):
        super().__init__(parent)
        self.setObjectName("notice")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog#notice {{ background:#000000; border:{px(3)}px solid #FFFFFF;
                              border-radius:{px(20)}px; }}
            QDialog#notice QLabel {{ color:#FFFFFF; background:transparent; }}
            QLabel#noticeTitle {{ font-size:{px(44)}px; font-weight:bold; }}
            QLabel#noticeText {{ font-size:{px(32)}px; }}
            QLabel#noticeNotes {{ font-size:{px(24)}px; color:#C9C9C9; }}
            QDialog#notice QPushButton {{ background:{BRICK}; color:#FFFFFF; border:none;
                                          border-radius:{px(8)}px; font-size:{px(28)}px;
                                          font-weight:bold;
                                          padding:{px(14)}px {px(34)}px; }}
            QDialog#notice QPushButton:pressed {{ background:#8E342C; }}
            QDialog#notice QPushButton#quiet {{ background:transparent;
                                                border:{px(2)}px solid #FFFFFF; }}
            QDialog#notice QPushButton#quiet:pressed {{ background:#333333; }}
        """)
        self.least = px(620)          # never narrower than this, however short the message

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(44), px(40), px(44), px(36))
        lay.setSpacing(px(20))

        head = QtWidgets.QLabel(title)
        head.setObjectName("noticeTitle")
        lay.addWidget(head)

        self.text = QtWidgets.QLabel("")
        self.text.setObjectName("noticeText")
        self.text.setWordWrap(True)
        lay.addWidget(self.text)

        self.notes = QtWidgets.QLabel("")
        self.notes.setObjectName("noticeNotes")
        self.notes.setWordWrap(True)
        self.notes.hide()
        lay.addWidget(self.notes)

        lay.addSpacing(px(8))
        self.buttons = QtWidgets.QHBoxLayout()
        self.buttons.addStretch(1)
        lay.addLayout(self.buttons)

    def say(self, message: str) -> None:
        """Show a message with nothing to press: the app is busy and about to say more."""
        self.text.setText(message)
        self.notes.hide()
        self.clear_buttons()
        self.settle()

    def finish(self, message: str, close_label: str) -> None:
        """The last word. One button, which closes."""
        self.text.setText(message)
        self.notes.hide()
        self.clear_buttons()
        self.add_button(close_label, self.accept, quiet=True)
        self.settle()

    def ask(self, message: str, yes_label: str, no_label: str, notes: str = "") -> None:
        self.text.setText(message)
        self.notes.setText(notes)
        self.notes.setVisible(bool(notes))
        self.clear_buttons()
        self.add_button(no_label, self.reject, quiet=True)
        self.add_button(yes_label, self.accept)
        self.settle()

    def add_button(self, label: str, does, quiet: bool = False) -> QtWidgets.QPushButton:
        b = no_focus(QtWidgets.QPushButton(label))
        if quiet:
            b.setObjectName("quiet")
        b.clicked.connect(does)
        self.buttons.addWidget(b)
        return b

    def clear_buttons(self) -> None:
        while self.buttons.count() > 1:                  # the stretch at the front stays
            item = self.buttons.takeAt(1)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def settle(self) -> None:
        """Size to the words, sit in the middle of the parent, and paint before anything slow
        happens next -- the check runs on this thread, so nothing repaints while it waits.

        The width is fixed first and the heights worked out from it, in that order. A wrapped
        label has no height until it knows its width: asking a layout to size itself around one
        in a single pass gives a box that is too short, and the last line is cut in half.
        """
        parent = self.parentWidget()
        wide = self.least if parent is None else max(self.least, int(parent.width() * 0.55))
        self.setFixedWidth(wide)
        edges = self.layout().contentsMargins()
        inner = wide - edges.left() - edges.right()
        for label in (self.text, self.notes):
            if not label.isVisible():
                label.setMinimumHeight(0)
                continue
            # heightForWidth is the exact minimum, which leaves the last line's descenders
            # sitting on the boundary. A few pixels of air costs nothing and reads far better.
            label.setMinimumHeight(label.heightForWidth(inner)
                                   + max(2, label.fontMetrics().descent()))
        self.adjustSize()

        if parent is not None:
            here = parent.geometry()
            self.move(here.center().x() - self.width() // 2,
                      here.center().y() - self.height() // 2)
        if not self.isVisible():
            self.show()
        self.raise_()
        QtWidgets.QApplication.processEvents()


class BigButton(QtWidgets.QPushButton):
    """A large touch target with a main line and an optional smaller second line."""

    def __init__(self, title: str, detail: str = "", title_px: int = 40, detail_px: int = 20):
        super().__init__()
        no_focus(self)
        self.setObjectName("big")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addStretch(1)
        for text, px, name in ((title, title_px, "bigTitle"), (detail, detail_px, "bigDetail")):
            if not text:
                continue
            lab = QtWidgets.QLabel(text)
            lab.setObjectName(name)      # its colour comes from the stylesheet, with the theme
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setWordWrap(True)
            lab.setStyleSheet(f"font-size:{px}px; background:transparent;")
            lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(lab)
        lay.addStretch(1)


class FrontDoor(QtWidgets.QWidget):
    """The screen the mat opens on: one moving picture, and touching it goes in.

    It was a mosque with MySalaah across its front until 1.76 -- the same drawing machinery as
    the other two mosques, with the sky moving behind it, the clock on its dome and the black
    strip of prayer times above. Harry replaced the lot with his own mark, and asked for
    nothing to be added to it: "dont add banner or anything, keep as is".

    WHAT IT DOES. The word "My" turns over through the seven languages the mat speaks -- My,
    Ma, Mi, صلاتي, میری نماز, मेरी, 我的 -- resting a beat on each and crossing to the next over
    three frames, while the Kaaba and the crescent stand still. Seven seconds round. None of
    that is known here: it is a film, and this plays it.

    IT FOLLOWS THE THEME, like every other drawing on the mat. Harry sent it twice, once black
    on white and once white on black, and the two are the same pixels inverted -- so the light
    one ships and the dark screen gets it turned over, which is one blit and no second file to
    keep in step. See filmsheet.turn_inside_out, which is the same inversion the menu sheets
    use, and tools/make_front_film.py for how the film is cut.

    Nothing is cached. The frame is scaled as it is drawn, which on a 1080p mat is ten scalings
    a second of a 1600x900 picture; the version that kept them cost a menu 135MB (see
    filmsheet.draw_themed) and this screen is up for longer than any menu.
    """

    chosen = Signal(str)

    THANKS_HEIGHT = 0.020     # of the screen's height. 21px on a 1080 screen, 24 on the mat's
                              # 1200: there to be read in a photograph and when somebody looks
                              # for it, not from standing at the mat.
    THANKS_FLOOR = 11         # never smaller than this, whatever the screen
    THANKS_MARGIN = 0.022     # clear of the bottom edge by about the same again

    def __init__(self, picture: Path, film: Path | None = None):
        super().__init__()
        # Who the words on the mat belong to, across the foot of the screen. Harry asked for
        # this screen to carry it: it is the one the mat shows most -- it is what is up while
        # the mat is idle and what it goes to sleep on -- so a publisher's name here is seen
        # more than anywhere else on the device, and a photograph of the mat carries it.
        #
        # Drawn by the app rather than baked into the artwork, which would be ten re-exports
        # now and ten more every time a source changed, with no way to tell that the picture
        # and the files had drifted apart.
        #
        # NO BUTTON, and that is deliberate. A press anywhere on this screen goes in -- see
        # mousePressEvent -- so a control here would be a small rectangle that does something
        # else in the middle of a screen that means "go in", on the screen that gets touched
        # without being looked at to wake the mat. The full list is a tap away in Settings.
        self.thanks = ""
        self.sheet = QtGui.QPixmap(str(picture)) if picture.is_file() else QtGui.QPixmap()
        self.film: QtGui.QMovie | None = None
        if film is not None and film.is_file():
            movie = QtGui.QMovie(str(film))
            if movie.isValid() and movie.frameCount() > 1:
                movie.setParent(self)
                # A bound method rather than a lambda, for the reason the call box and the
                # turning globe both learned it: a lambda holding this widget outlives it, and
                # a frame arriving after the widget has gone took one of the two Qt kits down.
                movie.frameChanged.connect(self.turned)
                self.film = movie
        self.setObjectName("frontDoor")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoFillBackground(True)

    @property
    def ready(self) -> bool:
        """A film, or failing that a still. Either is a front door; neither is not."""
        return self.film is not None or not self.sheet.isNull()

    @property
    def moving(self) -> bool:
        return self.film is not None

    def turned(self, _frame: int) -> None:
        self.update()

    def now(self) -> QtGui.QPixmap:
        """The frame to draw: the film's, or the still it falls back to."""
        if self.film is not None:
            frame = self.film.currentPixmap()
            if not frame.isNull():
                return frame
        return self.sheet

    def paintEvent(self, _):
        shown = self.now()
        if shown.isNull():
            return
        p = QtGui.QPainter(self)
        # The field first, in the colour it was drawn on, so a screen that is not the film's
        # shape has no bar down the side of it -- and so the inversion below takes the whole
        # screen rather than leaving a white edge round a black picture.
        p.fillRect(self.rect(), QtGui.QColor("white"))
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        # Whole, not cropped: the mark keeps the proportions it was drawn in.
        shown = shown.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((self.width() - shown.width()) // 2,
                     (self.height() - shown.height()) // 2, shown)
        if theme.palette().dark:
            turn_inside_out(p, self.rect())
        self.draw_thanks(p)

    def say_thanks(self, said: str) -> None:
        """The acknowledgement to carry. Empty for none, and then nothing is drawn."""
        if said != self.thanks:
            self.thanks = said
            self.update()

    def draw_thanks(self, p: QtGui.QPainter) -> None:
        """AFTER the inversion, not before it.

        Everything else on this screen is drawn and then turned inside out for a dark screen,
        because the artwork ships one way round and is inverted for the other. Text drawn
        before that would be inverted with it -- white would come out black on the dark screen
        and the line would vanish into the black ground it was meant to sit on. So it is drawn
        last, in the colour it is to be: white after dark, black by day.
        """
        if not self.thanks:
            return
        size = max(self.THANKS_FLOOR, int(self.height() * self.THANKS_HEIGHT))
        font = QtGui.QFont(self.font())
        font.setPixelSize(size)
        p.setFont(font)
        p.setPen(QtGui.QColor("white") if theme.palette().dark else QtGui.QColor("black"))
        margin = int(self.height() * self.THANKS_MARGIN)
        where = QtCore.QRect(0, self.height() - margin - size * 2, self.width(), size * 2)
        p.drawText(where, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom),
                   self.thanks)

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
        # Off screen means stopped, the same rule the turning globe follows: a film left
        # running is a timer waking the Pi ten times a second to repaint something nobody is
        # looking at -- and this screen is the one the mat goes to sleep on.
        self.stop()
        super().hideEvent(ev)

    def mousePressEvent(self, _):
        self.chosen.emit("enter")


class TopBar(QtWidgets.QWidget):
    """The row across the top of the prayer screen. Whatever sits at its ends, the prayer's
    name in Arabic stays in the middle of the screen: it is placed by hand, not by a layout,
    so a wide volume bar on one side cannot shift it."""

    def __init__(self):
        super().__init__()
        self.centre: QtWidgets.QWidget | None = None

    def place_centre(self) -> None:
        if self.centre is None:
            return
        hint = self.centre.sizeHint()
        width = min(hint.width(), self.width())
        self.centre.setGeometry((self.width() - width) // 2,
                                (self.height() - hint.height()) // 2, width, hint.height())
        self.centre.raise_()

    def resizeEvent(self, _):
        self.place_centre()


class PrayerPage(QtWidgets.QWidget):
    """The prayer screen: Arabic above English on the left, posture figure on the right.
    Tapping or clicking the start third goes back, the rest goes forward."""
    tapped = Signal(str)

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.win = window
        self.setAutoFillBackground(True)
        self.follow_theme()

        px = window.px
        # Even margins all round. The bottom used to be two and a half times the top, which read
        # as a band of nothing along the bottom of the screen; the words are fitted to whatever
        # box they are given, so that margin was costing letter size as well as looking odd.
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(px(36), px(22), px(36), px(22))
        lay.setSpacing(px(40))

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(px(18))
        self.arabic = TextBox(Fonts.arabic(window.settings.arabic_font), MIN_ARABIC_PX, MAX_ARABIC_PX,
                              rtl=True, weight=700, slack=0.98, by_word=True, gap=0.18)
        self.arabic.scale = window.s
        self.split = window.side is not None
        if self.split:
            # A second screen carries the picture and the X2 / X3 circle, so the words have the
            # whole width of this one. The volume lives in the top bar either way.
            self.posture = window.side.posture
            self.repeat_badge = self.posture.badge
        else:
            # Picture on the left in a frame of its own, words on the right. The circle saying
            # how many times to recite rides inside the picture frame, top right.
            self.posture = PostureView(window.images, Fonts.english_family)
            self.posture.scale = window.s
            self.posture.modes = window.posture_modes
            self.repeat_badge = self.posture.badge
            lay.addWidget(self.posture)

        # With a translation chosen: the Arabic on the right, its meaning on the left.
        self.parallel = ParallelText(Fonts.arabic(window.settings.arabic_font), Fonts.english_family)
        self.parallel.scale = window.s
        self.parallel.hide()
        text_col.addWidget(self.arabic, 1)
        text_col.addWidget(self.parallel, 1)
        lay.addLayout(text_col, 1)

        self.dim = QtWidgets.QWidget(self)
        self.dim.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.dim.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.dim.hide()
        self.done = QtWidgets.QWidget(self)
        self.done.setObjectName("done")
        self.done.hide()
        self.ask = QtWidgets.QWidget(self)
        self.ask.setObjectName("done")
        self.ask.hide()
        # A fardh prayer ends on the counted dhikr. Nothing else ends on anything.
        self.tasbih = TasbihScreen(Fonts.arabic(window.settings.arabic_font),
                                   Fonts.english_family, px)
        self.tasbih.setParent(self)
        self.tasbih.set_scale(window.s)
        self.tasbih.hide()

    def follow_theme(self) -> None:
        pal = self.palette()
        pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(theme.palette().paper))
        self.setPalette(pal)
        if hasattr(self, "tasbih"):
            self.tasbih.follow_theme()

    def set_dim(self, percent: int) -> None:
        if percent <= 0:
            self.dim.hide()
            return
        self.dim.setStyleSheet(f"background: rgba(0,0,0,{int(255 * percent / 100)});")
        self.dim.setGeometry(self.rect())
        self.dim.show()
        self.dim.raise_()

    def show_page(self, page: TextPage, assets: Path) -> None:
        # The intention is written in the pack's language, left to right; everything else is Arabic.
        arabic_face = Fonts.arabic(self.win.settings.arabic_font)
        chosen = self.win.translation
        meaning_rtl = bool(chosen is not None and chosen.rtl)
        # The intention is written in the language of the translation: Urdu takes the Arabic
        # face and runs right to left, English and French the plain face, left to right.
        # The face follows the letters that will be shown: Chinese and Devanagari get a bundled
        # face, because the Pi has neither and would draw empty boxes instead.
        shown = page.arabic if page.latin else page.english
        meaning_face = arabic_face if meaning_rtl else Fonts.for_text("".join(shown))
        self.arabic.set_family(meaning_face if page.latin else arabic_face)
        self.arabic.rtl = meaning_rtl if page.latin else True
        self.arabic.set_lines(page.arabic)
        # The switch in the bar decides whether the meaning is drawn; the pages are built with
        # it either way, which is why flipping it mid-prayer takes effect on the page in front
        # of you rather than at the next unit. It costs nothing to carry: a page is one screen
        # of Arabic whether or not the meaning goes beside it (build_pages is called with
        # one_page), so the English lines being there change neither the paging nor the size
        # the Arabic is set at.
        #
        # The intention is not touched by this. It has no Arabic to stand beside -- it is one
        # sentence saying which prayer you are about to perform -- so hiding "the meaning"
        # there would leave the first screen of every prayer blank.
        side_by_side = not page.latin and any(page.english) and self.win.settings.meaning
        if side_by_side:
            self.parallel.set_family(arabic_face)
            self.parallel.set_meaning_face(meaning_face, meaning_rtl)
            self.parallel.set_lines(page.arabic, page.english, meaning_rtl)
        self.parallel.setVisible(side_by_side)
        self.arabic.setVisible(not side_by_side)
        self.repeat_badge.set_count(page.repeat)
        self.posture.set_image(self.win.picture(page.posture_image))

    def set_highlight(self, where: tuple[int, int] | None) -> None:
        """The word being recited, in whichever of the two ways the words are shown."""
        self.arabic.set_highlight(where)
        self.parallel.set_highlight(where)

    PICTURE_SHARE = 0.30   # the left third of the screen is always the picture frame

    @property
    def volume(self):
        """The volume bar, which lives in the top bar of this screen."""
        return self.win.volume

    def resizeEvent(self, _):
        if not self.split:
            self.posture.setFixedWidth(int(self.width() * self.PICTURE_SHARE))
        for w in (self.done, self.dim, self.ask, self.tasbih):
            w.setGeometry(self.rect())

    def mousePressEvent(self, e):
        if self.done.isVisible() or self.tasbih.isVisible():
            return
        if self.ask.isVisible():
            self.win.move(NEXT)   # a click while the question is up answers it
            return
        x = e.position().x()
        third = self.width() / 3
        # Back is the third at the edge the language starts from: the left for English and
        # French, the right for Urdu, so "back" always means "the way you came".
        back = x > self.width() - third if self.win.pack.rtl else x < third
        self.tapped.emit(BACK if back else NEXT)


class MainWindow(QtWidgets.QWidget):
    # Everything is laid out inside a box of this shape, centred in the window. If the screen
    # is a different shape (or the monitor is cutting off an edge), the app stays whole and the
    # spare space becomes a margin, instead of the bottom of the screen disappearing.
    ASPECT = 16 / 9

    def __init__(self, content: Content, packs: dict[str, LanguagePack], settings: Settings,
                 scale: float = 1.0, save_settings: bool = True, aspect: float | None = 16 / 9,
                 compass=None, side: bool = False):
        super().__init__()
        self.aspect = aspect
        Fonts.load(content.root)
        self.assets = content.root
        self.arch_shape = ArchShape(content.root)
        self.posture_modes = load_posture_modes(content.root, settings.figure)
        self.content = content
        self.packs = packs
        self.english = packs["en"]
        self.settings = settings
        self.save_settings = save_settings
        self.s = scale
        self.images = PixmapCache()
        self.debouncer = Debouncer(0.3)
        self.counter_debouncer = Debouncer(0.12)   # counting beads is meant to be quick
        self.session: PrayerSession | None = None
        self.text_pages: list[TextPage] = []
        self.last_click: float | None = None
        self.recitation = Recitation(volume=settings.volume)
        self.timings: dict[str, Timings] = load_timings(content.root)
        self.dhikr_follow = QtCore.QTimer(self)      # the beads screen's recordings
        self.dhikr_follow.setInterval(60)
        self.dhikr_follow.timeout.connect(self.follow_dhikr)
        self.dhikr_now: tuple[str, object] | None = None   # (recording, the line it lights)
        self.dhikr_then = None                              # what plays when it ends
        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(60)
        self.follow.timeout.connect(self.follow_audio)
        self.prayer: str | None = None
        self.kind: str = ""          # the unit being prayed: farz, sunnah, nafl or witr
        self.title = ""
        self.device_names: list[str] = []
        # The connected speaker's name, when one is known. It is the one thing that tells a
        # ring's input device apart from a speaker's media keys, which arrive on the same bus
        # under the same kind of name -- see ring_names.
        self.speaker_name: str = ""

        self.bridge = Bridge()
        self.bridge.action.connect(self.on_button)
        self.bridge.devices.connect(self.on_devices)
        self.bridge.power.connect(self.toggle_sleep)
        self.asleep = False
        self.outputs = Outputs()
        # Screens on, whatever state the last run left them in. The app only ever turned them
        # back on when it woke or shut down cleanly, which was fine while those were the only
        # ways it ended -- and stopped being fine in 1.64, when run.sh learnt to start the app
        # again after a crash. Crash while asleep and the panels are off; the new instance
        # thinks it is awake, never calls wake(), and the mat is dark with nothing wrong with
        # it. This also covers the power going off mid-sleep, and a kill from a terminal.
        if not self.outputs.set(True):
            print(f"start: {self.outputs.why}", file=sys.stderr)
        self.notice = None          # the update dialog, while one is on screen
        self.backlight = Backlight()
        # Every volume slider and every banner on screen, kept so they can be moved and
        # relabelled together: one notion of volume, one notion of what the banner says.
        self.volume_bars: list = []
        self.banner_labels: list = []
        self.quran = Quran(self.assets)
        # The recitation: verse recordings fetched as they are needed, and the word timings
        # that say which word is sounding. Both are quiet about being absent.
        self.verses = Store()
        self.word_times = WordTimes(self.assets)
        self.duas = Passages(self.assets, "duas")
        self.kalima = Passages(self.assets, "kalima")
        self.sayings = Passages(self.assets, "hadith", folder="hadith")
        self.wudu = Steps(self.assets)
        self.stations = Stations(self.assets)
        self.call = Call(volume=settings.volume)   # the call to prayer
        self.adhan = Adhan(self.assets)           # and the words of it, for the screen
        self.call_box = None                       # the TIME TO PRAY notice, while it is up
        self.called: dict[str, object] = {}        # prayer -> the day it was last called

        self.setWindowTitle("Salaah")
        # No layout: the stack is placed by hand in resizeEvent, so the drawing area keeps its
        # shape whatever the screen does. A layout with big margins would fight the window size.
        self.stack = QtWidgets.QStackedWidget(self)
        self.faces: dict[str, str] = {}          # the menu face per interface language
        self.veil = ZoomVeil(self)               # the walk into an arch, laid over the top
        self.facing = Facing(compass or NoCompass(), settings.compass_declination,
                             settings.compass_mounting)
        theme.set_dark(self.wants_dark())
        # The 7" screen, when there is one: the Qibla between prayers, the posture during one.
        self.side: SideWindow | None = None
        if side:
            self.side = SideWindow(self, CompassScreen(self, self.facing) if QIBLA else None)
            if self.side.compass is not None:
                self.side.compass.done.connect(self.side_lined_up)
        self.rebuild()
        QtWidgets.QApplication.instance().installEventFilter(self)

        # These two run whatever else is happening, including while the mat is asleep -- which
        # is the whole point of them. The ten-second clock is stopped when the screens go off,
        # because nobody can see what it draws; a prayer falling due does not stop mattering.
        self.muezzin = QtCore.QTimer(self)
        self.muezzin.setInterval(15_000)
        self.muezzin.timeout.connect(self.check_the_hour)
        self.muezzin.start()
        self.call_watch = QtCore.QTimer(self)       # notices when the call has finished
        self.call_watch.setInterval(500)
        self.call_watch.timeout.connect(self.watch_the_call)
        self.idle = QtCore.QTimer(self)             # nothing pressed for a while -> sleep
        self.idle.setSingleShot(True)
        self.idle.timeout.connect(self.maybe_sleep)
        self.stir()

    def content_box(self) -> QtCore.QRect:
        """The area the app draws in: the largest box of the right shape that fits.

        It used to be inset by a few pixels for a monitor that cut its edges off, set from a
        row in Settings. That went in 1.81 -- see settings.py for why -- and the box is now
        simply the screen.
        """
        w = max(1, self.width())
        h = max(1, self.height())
        if self.aspect:
            if w / h > self.aspect:
                w = int(h * self.aspect)
            else:
                h = int(w / self.aspect)
        return QtCore.QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def resizeEvent(self, event):
        box = self.content_box()
        self.stack.setGeometry(box)
        # Laid out for 1920 x 1080; a taller screen (1920 x 1200) keeps the same sizes and
        # gets the extra height as room.
        scale = max(0.5, min(box.height() / 1080, box.width() / 1920))
        if abs(scale - self.s) > 0.01:
            self.s = scale
            QtCore.QTimer.singleShot(0, self.restyle)
        super().resizeEvent(event)

    def restyle(self) -> None:
        """Text and spacing follow the box size, so the app looks the same on any screen."""
        self.setStyleSheet(self.stylesheet())
        if self.side is not None:
            self.side.setStyleSheet(self.stylesheet())
        if hasattr(self, "volume"):
            self.volume.scale = self.s
        if hasattr(self, "slide"):
            self.slide.arabic.scale = self.s
            self.slide.parallel.scale = self.s
            self.slide.posture.scale = self.s
        # The Qur'an sizes two of its own parts from widgets this has just restyled, so it has
        # to be told after the fact rather than working it out from a resize it saw first --
        # and a turn later again, because setting a stylesheet does not resize anything until
        # the next layout pass. Measured: called here directly, Back is still its old height
        # and the play button matches a size that is about to change, which is the same trap
        # the note on match_buttons describes from the first time round.
        if hasattr(self, "reader"):
            QtCore.QTimer.singleShot(0, self.reader.follow_scale)

    # Sleep

    def toggle_sleep(self) -> bool:
        """The power button: asleep becomes awake and the other way about, from any screen.

        One rule with no exceptions -- press to put the mat away, press to pick it up, and it
        always comes back at the mosque. That includes partway through a prayer, which this used
        to refuse on the grounds that a press then was more likely a knee than a decision. That
        reasoning was borrowed from the wrong button: the ring that gets knelt on lies on the
        mat, while this one is on the box, where a knee will not find it. And a button that does
        nothing is worse than one that does something, particularly for a child, who has no way
        of telling "ignored on purpose" from "broken".

        It doubles as the way out of a screen that has stopped behaving, which on a mat with no
        keyboard is worth more than the case it was guarding against.
        """
        self.wake() if self.asleep else self.sleep()
        return True

    def catch_up_with_the_sky(self, *screens) -> None:
        """Put the time and the sky on a mosque that has only just been built.

        A new MosqueScreen starts at its own defaults -- midday, the sun half way across --
        and waits for the ten-second clock to tell it otherwise. On the two screens built when
        the app starts nobody notices, because the first tick follows immediately. On a
        prayer's own page, which is built the moment an arch is touched, it is the whole of
        what you see: open a prayer after dark and there is a sun in a daylit sky for up to
        ten seconds before it snaps to the moon. Harry saw it as the sky being "different when
        selecting rakats of any prayer", and it was -- it was ten seconds behind.

        Called wherever a mosque is built, so the answer cannot be forgotten in one place and
        remembered in another.
        """
        now = datetime.now()
        times = self.prayer_times(now)
        for screen in screens:
            if screen is None or not getattr(screen, "ready", False):
                continue
            screen.set_sky(*day_fraction(now, times))
            if screen.own_sky:
                screen.flutter.start() if screen.isVisible() else None

    def every_sky(self):
        """Every mosque on the mat that paints a moving sky of its own.

        Written as a list rather than left to each screen's own showEvent because of sleep: a
        hidden screen stops its own sky, but the one still on show when the panels go dark does
        not, and nobody is looking at that either. It used to be just the main mosque, which was
        true when it was the only drawing with a see-through sky; the front door and the five
        prayer pages have one now, so a list that names one of them goes stale the next time a
        drawing is added. Everything that has a flutter is in here by construction.
        """
        found = [getattr(self, "mosque", None), getattr(self, "welcome_mosque", None),
                 getattr(self, "prayer_mosque", None)]
        found += [menu.mosque for menu in getattr(self, "arch_menus", {}).values()]
        return [s for s in found if s is not None and hasattr(s, "flutter")]

    def sleep(self) -> None:
        """Screens off, and everything that was only drawing them stopped.

        The panels are the bulk of what the mat costs to run, so they matter most, but the work
        behind them is worth stopping too: the sky animates several times a second and the clock
        redraws the times, neither of which anyone can see now.
        """
        if self.asleep:
            return
        self.asleep = True
        self.idle.stop()     # nothing to count down to; waking starts it again
        self.stop_audio()
        if not self.outputs.set(False):
            print(f"sleep: {self.outputs.why}", file=sys.stderr)
        # Back to the mosque while nobody can see it happen, so whoever wakes the mat is met by
        # the main menu rather than by wherever the last person left it. The mat gets picked up
        # by whoever is praying next, and a screen left open in the middle of someone else's
        # Settings is no way to greet them. Doing it now rather than on the way back means the
        # panels come up already showing the right thing.
        self.go_home()
        if self.side is not None:
            self.side.show_idle()
        # After go_home, because showing the mosque is what starts the sky animating.
        if hasattr(self, "clock"):
            self.clock.stop()
        for sky in self.every_sky():
            sky.flutter.stop()

    def wake(self) -> None:
        """Screens back on, at the front door.

        It used to come back wherever it had been left, which after a night asleep is a screen
        somebody opened yesterday. The front door is where the mat starts, so it is where it
        starts again -- except when a prayer is what woke it, and the call takes it home itself.
        """
        if not self.asleep:
            return
        self.asleep = False
        if not self.outputs.set(True):
            print(f"wake: {self.outputs.why}", file=sys.stderr)
        if getattr(self, "welcome", None) is not None and not self.playing:
            self.stack.setCurrentWidget(self.welcome)
        if hasattr(self, "clock"):
            self.clock.start()
        for sky in self.every_sky():
            if sky.isVisible():
                sky.flutter.start()
        self.tick()          # the time and the prayer due have moved on while it slept
        self.stir()          # picked up: start the going-to-sleep clock from the top

    def shutdown(self) -> None:
        """Detach from the application before it closes (avoids a crash on exit with PyQt6)."""
        # Never leave the screens dark for the next thing that runs: the app owns their power
        # while it is up, so it has to hand them back before it goes.
        if self.asleep:
            self.outputs.set(True)
            self.asleep = False
        for timer in ("muezzin", "call_watch", "idle"):
            if hasattr(self, timer):
                getattr(self, timer).stop()
        # And the recitation's own clock. It ticks twenty times a second and repaints the page
        # each time, so a window that has been closed but not yet collected would go on drawing
        # a surah nobody is looking at.
        if hasattr(self, "reader") and self.reader.reciting:
            self.reader.stop_reciting()
        self.hush_passages()
        self.call.stop()
        self.stop_audio()
        # The ten-second clock has to be stopped, not just left to be collected. It calls
        # apply_theme, which sets the light-or-dark palette for the whole app, so a window that
        # has been shut down but not yet deleted could still reach out and change the colours
        # under a window that is live. One window at a time is the normal case and never saw it;
        # the tests run several in turn and saw it now and then.
        if hasattr(self, "clock"):
            self.clock.stop()
        if self.veil.running:
            self.veil.stop()
        # An nmcli errand can still be out when the window goes. It holds a signal into this
        # window, so it is waited for rather than left to land on something that has gone.
        errand = getattr(self, "wifi_errand", None)
        if errand is not None:
            errand.wait(5000)
        # The same for Bluetooth, which has two: the one that paints the circle in Settings, and
        # the screen's own, which can be ten seconds into a scan when somebody closes the lid.
        errand = getattr(self, "bt_errand", None)
        if errand is not None:
            errand.wait(5000)
        screen = getattr(self, "bt_screen", None)
        if screen is not None:
            screen.shutdown()
        if self.side is not None:
            self.side.close_screens()
            self.side.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    # Helpers

    def px(self, n: float) -> int:
        return max(1, int(n * self.s))

    def banner_height(self) -> int:
        """How tall the strip across the top is.

        A method rather than a number other files reach in for, because the call box sits
        under it and call.py importing from here would close a circle -- ui imports call.
        """
        return self.px(BANNER_TALL)

    @property
    def pack(self) -> LanguagePack:
        return self.packs.get(self.settings.lang, self.english)

    @property
    def school(self):
        return self.content.schools.get(self.settings.school) or next(iter(self.content.schools.values()))

    def t(self, key: str, **args) -> str:
        return self.pack.t(key, self.english, **args)

    def persist(self) -> None:
        if self.save_settings:
            self.settings.save()

    def rebuild(self) -> None:
        """(Re)creates every screen, e.g. after a language change."""
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.pack.rtl else Qt.LayoutDirection.LeftToRight)
        self.setStyleSheet(self.stylesheet())
        self.home = self.build_home()
        self.welcome = self.build_welcome()
        self.pick = QtWidgets.QWidget()
        self.player = self.build_player()
        self.settings_screen = self.build_settings()
        self.timing_screen = self.build_timing()
        self.corner_screen = self.build_corner()
        # The same banner as the front door, above the whole Knowledge Corner -- the surah
        # list, a surah open, the du'as and the kalima -- so wherever you are on the mat you
        # can see where you are, what is next, and how loud it is.
        self.corner_page = QtWidgets.QWidget()
        corner_lay = QtWidgets.QVBoxLayout(self.corner_page)
        corner_lay.setContentsMargins(0, 0, 0, 0)
        corner_lay.setSpacing(0)
        corner_lay.addWidget(self.make_banner(gear=True, home=True))
        corner_lay.addWidget(self.corner_screen, 1)
        screens = [self.home, self.pick, self.player, self.settings_screen, self.timing_screen,
                   self.corner_page]
        if self.welcome is not None:
            screens.insert(0, self.welcome)
        if QIBLA:
            self.compass_screen = CompassScreen(self, self.facing)
            self.compass_screen.done.connect(self.qibla_done)
            screens.append(self.compass_screen)
        elif hasattr(self, "compass_screen"):
            del self.compass_screen
        for w in screens:
            self.stack.addWidget(w)
        # The front door the mat opens on, if there is one drawn. Everything else -- the way
        # back from a sub screen, waking up, a prayer falling due -- still goes to the mosque
        # with the five arches, because that is the screen the mat is for.
        self.stack.setCurrentWidget(self.welcome if self.welcome is not None else self.home)
        # The monitor is a thing in the world and keeps whatever it was last told, including by
        # somebody else. Say it again at startup so the setting and the screen agree.
        self.apply_brightness()

    def colours(self) -> SimpleNamespace:
        """The stylesheet's colours for the theme in use. By day they are the app's own black
        on white; after dark, white on black, with the blue lifted so it reads on black."""
        if theme.is_dark():
            return SimpleNamespace(paper="black", ink="#F2F2F2", strong="white", line="#3A3D40",
                                   lapis="#8FB1F0", stone="#A7AEB4", pale="#1F2A40",
                                   chip="#262626", hint="#BBBBBB", source="#AAAAAA",
                                   divider="#444444", pressed="#333333",
                                   # the word being recited, taken from the theme rather than
                                   # written again here, so the two can never disagree
                                   highlight=theme.palette().highlight)
        return SimpleNamespace(paper="white", ink=INK, strong="black", line=LINE, lapis=LAPIS,
                               stone=STONE, pale="#E8ECF5", chip="black", hint="#444",
                               source="#555", divider="#CCCCCC", pressed="#DDDDDD",
                               highlight=theme.palette().highlight)

    def pack_face(self) -> str:
        """The face the menus are written in.

        Worked out from the pack's own words, so a language whose script the Pi has not got
        (Chinese, Hindi) gets the bundled face instead of a screenful of empty boxes. Remembered
        per language, because the stylesheet is rebuilt on every resize.
        """
        lang = self.pack.lang
        if lang not in self.faces:
            self.faces[lang] = Fonts.for_text("".join(self.pack.ui.values()))
        return self.faces[lang]

    def stylesheet(self) -> str:
        px = self.px
        c = self.colours()
        # How large the words on the Settings page are set. Named, and in one place, because
        # they were raised together in 1.83 and have to be judged together: the page either
        # fits a 1920x1080 monitor in all seven languages or it does not, and raising any one
        # of these is what spends the margin. Chinese is the language that decides -- CJK
        # glyphs carry more line height than Latin at the same size, so English has room to
        # spare at the size Chinese can just afford. The test that measures all seven is what
        # these numbers were chosen against; raise one and it will say so.
        head, hint, value = px(SET_HEAD), px(SET_HINT), px(SET_VALUE)
        pick, pick_tall = px(SET_PICKER), px(SET_PICKER_TALL)
        choice, knob, knob_round = px(SET_CHOICE), px(SET_KNOB), px(SET_KNOB // 2 + 3)
        pill_text, pill_pad = px(SET_PILL), px(14)
        return f"""
            QWidget {{ background:{c.paper}; color:{c.ink}; font-size:{px(24)}px;
                       font-family:'{self.pack_face()}'; }}
            QPushButton#big {{ background:{c.paper}; border:{px(2)}px solid {c.line}; border-radius:{px(18)}px; }}
            QPushButton#big:pressed {{ background:{c.pale}; border-color:{c.lapis}; }}
            QPushButton#link {{ background:transparent; border:none; color:{c.lapis}; font-size:{px(28)}px;
                                padding:{px(14)}px {px(20)}px; }}
            QPushButton#pill {{ background:{c.paper}; border:{px(2)}px solid {c.line}; border-radius:{px(14)}px;
                                font-size:{px(28)}px; padding:{px(14)}px {px(28)}px; min-width:{px(80)}px; }}
            QPushButton#pill:checked {{ border-color:{c.lapis}; color:{c.lapis}; background:{c.pale}; }}
            QPushButton#primary {{ background:{LAPIS}; color:white; border:none; border-radius:{px(14)}px;
                                   font-size:{px(34)}px; padding:{px(18)}px {px(48)}px; }}
            QLabel#gameWhere {{ font-size:{px(26)}px; color:{c.stone};
                                letter-spacing:{px(2)}px; }}
            QLabel#gameQuestion {{ font-size:{px(48)}px; font-weight:bold; color:{c.strong}; }}
            QLabel#gameSaid {{ font-size:{px(30)}px; color:{c.hint}; }}
            QLabel#bigTitle {{ color:{c.ink}; }}
            QLabel#bigDetail {{ color:{c.stone}; }}
            QLabel#h1 {{ font-size:{px(64)}px; font-weight:bold; }}
            QLabel#wifiName {{ font-size:{px(30)}px; font-weight:bold; color:{c.strong}; }}
            QLabel#wifiLock {{ font-size:{px(26)}px; color:{c.stone}; }}
            QLabel#wifiField {{ font-size:{px(38)}px; color:{c.strong}; letter-spacing:{px(3)}px;
                                border:{px(3)}px solid {c.line}; border-radius:{px(10)}px;
                                padding:{px(8)}px {px(16)}px; }}
            QLabel#wifiTrouble {{ font-size:{px(24)}px; color:{BRICK}; }}
            QPushButton#key {{ background:{c.paper}; color:{c.strong};
                               border:{px(2)}px solid {c.line}; border-radius:{px(10)}px;
                               font-size:{px(32)}px; font-weight:bold; }}
            QPushButton#key:pressed {{ background:{c.pale}; border-color:{c.lapis}; }}
            QPushButton#keyShift {{ background:{c.pale}; color:{c.lapis};
                                    border:{px(3)}px solid {c.lapis}; border-radius:{px(10)}px;
                                    font-size:{px(32)}px; font-weight:bold; }}
            QPushButton#keyDone {{ background:{LAPIS}; color:white; border:none;
                                   border-radius:{px(10)}px; font-size:{px(32)}px;
                                   font-weight:bold; }}
            QLabel#namePlate {{ background:white; color:black; font-size:{px(52)}px;
                              font-weight:bold; padding:{px(14)}px {px(48)}px; }}
            /* The same plate as a frame, for the prayer names, which need two fonts on it:
               the name in the app's lettering and the same name in Arabic. */
            QFrame#namePlate {{ background:white; }}
            QLabel#plateWord {{ background:transparent; color:black; font-size:{px(52)}px;
                                font-weight:bold; }}
            QLabel#plateArabic {{ background:transparent; color:black;
                                  font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                  font-size:{px(52)}px; font-weight:bold; }}
            QFrame#worldRail {{ background:{c.line}; border:none; }}
            QLabel#worldTallyHead {{ font-size:{px(34)}px; font-weight:bold; color:{c.ink}; }}
            QLabel#worldTally {{ font-size:{px(120)}px; font-weight:bold; color:{c.lapis}; }}
            QLabel#worldWho {{ font-size:{px(26)}px; color:{c.ink}; }}
            QFrame#duaCard {{ background:{c.paper}; border:{px(2)}px solid {c.line};
                              border-radius:{px(10)}px; }}
            QLabel#duaCardName {{ font-size:{px(38)}px; font-weight:bold; color:{c.strong};
                                  border:none; }}
            QLabel#duaCardArabic {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                    font-size:{px(66)}px; color:{c.strong}; border:none; }}
            QLabel#duaCardSaid {{ font-size:{px(28)}px; color:{c.stone};
                                  font-style:italic; border:none; }}
            QLabel#duaCardMeaning {{ font-size:{px(32)}px; color:{c.ink}; border:none; }}
            QToolButton#duaPlay {{ background:transparent; border:none; }}
            QToolButton#duaPlay:pressed {{ background:{c.pressed};
                                           border-radius:{px(8)}px; }}
            QLabel#h2 {{ font-size:{px(30)}px; color:{c.lapis}; font-weight:bold; }}
            QLabel#sub {{ font-size:{px(28)}px; color:{c.stone}; }}
            QLabel#note {{ font-size:{px(22)}px; color:{c.stone}; }}
            QWidget#settingsRoot {{ background:{c.paper}; }}
            QWidget#settingsRoot QLabel, QWidget#settingsRoot QRadioButton {{ background:{c.paper}; }}
            QScrollArea#settingsScroll {{ background:{c.paper}; border:none; }}
            QScrollArea#settingsScroll > QWidget > QWidget {{ background:{c.paper}; }}
            QScrollArea#sourcesScroll {{ background:{c.paper}; border:none; }}
            QScrollArea#sourcesScroll > QWidget > QWidget {{ background:{c.paper}; }}
            /* The lists -- the surahs, the du'as, the kalima -- are scrolled with a finger, so
               their slider is three times the width a desktop gives it, and the handle is in
               the colour of the quieter text rather than the divider line, which on the dark
               screen was barely there. The arrow buttons at the ends go: they are a mouse's
               idea of scrolling and at this width they would be two big blank squares.

               SETTINGS AND SOURCES ARE ON THE SAME RULE since 1.95, rather than each carrying
               a slider of its own width. Settings had a 14px bar and Sources had no rule at
               all, so it fell back to whatever Qt draws for a mouse -- three thicknesses of
               slider on one device, on screens that are all scrolled with the same finger.
               One selector list rather than three blocks: three blocks is how they came to
               disagree, and a fourth screen added later gets this by joining the list. */
            QScrollArea#listScroll QScrollBar:vertical,
            QScrollArea#settingsScroll QScrollBar:vertical,
            QScrollArea#sourcesScroll QScrollBar:vertical {{
                background:{c.paper}; width:{px(LIST_BAR)}px; margin:0; border:none; }}
            QScrollArea#listScroll QScrollBar::handle:vertical,
            QScrollArea#settingsScroll QScrollBar::handle:vertical,
            QScrollArea#sourcesScroll QScrollBar::handle:vertical {{
                background:{c.stone}; border-radius:{px(LIST_BAR // 2)}px;
                min-height:{px(110)}px; }}
            QScrollArea#listScroll QScrollBar::add-line:vertical,
            QScrollArea#listScroll QScrollBar::sub-line:vertical,
            QScrollArea#settingsScroll QScrollBar::add-line:vertical,
            QScrollArea#settingsScroll QScrollBar::sub-line:vertical,
            QScrollArea#sourcesScroll QScrollBar::add-line:vertical,
            QScrollArea#sourcesScroll QScrollBar::sub-line:vertical {{ height:0; }}
            QScrollArea#listScroll QScrollBar::add-page:vertical,
            QScrollArea#listScroll QScrollBar::sub-page:vertical,
            QScrollArea#settingsScroll QScrollBar::add-page:vertical,
            QScrollArea#settingsScroll QScrollBar::sub-page:vertical,
            QScrollArea#sourcesScroll QScrollBar::add-page:vertical,
            QScrollArea#sourcesScroll QScrollBar::sub-page:vertical {{ background:transparent; }}
            /* Settings is set larger since 1.83. Harry: "increase font sizes to take
               advantage of extra room now" -- the room being what the cog, the school picker
               and the recitation note gave back. The rise is close to the same proportion on
               every part of the page, so the hierarchy is unchanged, and it is sized to the
               language that needs the most height rather than to English: see the test that
               measures all seven. */
            QLabel#settingHead {{ font-size:{head}px; font-weight:bold; color:{c.strong}; }}
            QLabel#settingHint {{ font-size:{hint}px; color:{c.hint}; }}
            QLabel#settingValue {{ font-size:{value}px; font-weight:bold; color:{c.strong}; }}
            QLabel#sourceWhat {{ font-size:{value}px; font-weight:bold; color:{c.strong}; }}
            QLabel#sourceWho {{ font-size:{value}px; color:{c.strong}; }}
            QLabel#sourceNote {{ font-size:{hint}px; color:{c.hint}; }}
            QComboBox#picker {{ background:{c.paper}; color:{c.strong}; font-size:{pick}px;
                                 border:{px(3)}px solid {c.strong}; border-radius:{px(10)}px;
                                 padding:{px(8)}px {px(16)}px; min-height:{pick_tall}px; }}
            QComboBox#picker::drop-down {{ width:{px(46)}px; border:none; }}
            QComboBox#picker::down-arrow {{ image:none; width:0; height:0;
                                            border-left:{px(11)}px solid transparent;
                                            border-right:{px(11)}px solid transparent;
                                            border-top:{px(14)}px solid {c.strong};
                                            margin-right:{px(14)}px; }}
            QComboBox#picker QAbstractItemView {{ background:{c.paper}; color:{c.strong};
                                                  font-size:{pick}px;
                                                  border:{px(3)}px solid {c.strong};
                                                  selection-background-color:{c.pale};
                                                  selection-color:{c.strong}; }}
            QRadioButton#choice {{ font-size:{choice}px; font-weight:bold; color:{c.strong};
                                   spacing:{px(14)}px; padding:{px(6)}px 0; }}
            QRadioButton#choice::indicator {{ width:{knob}px; height:{knob}px;
                                              border:{px(3)}px solid {c.strong};
                                              border-radius:{knob_round}px; background:{c.paper}; }}
            QRadioButton#choice::indicator:checked {{ background:{c.strong}; }}
            /* The four boxes in the two-column block. #pill is worn on the Wi-Fi, Bluetooth,
               radio and place screens too, and those have their own room to answer for, so the
               larger size is scoped to this page rather than applied to every pill on the
               mat. */
            QWidget#settingsRoot QPushButton#pill {{ font-size:{pill_text}px;
                                                     padding:{pill_pad}px {px(30)}px; }}
            QPushButton#mainScreen {{ background:{BRICK}; color:white; border:none;
                                      border-radius:{px(8)}px; font-size:{px(28)}px;
                                      font-weight:bold; padding:{px(12)}px {px(30)}px; }}
            QPushButton#mainScreen:pressed {{ background:#8E342C; }}
            QPushButton#backButton {{ background:{BRICK}; color:white; border:none;
                                      border-radius:{px(8)}px; font-size:{px(28)}px;
                                      font-weight:bold; padding:{px(12)}px {px(30)}px; }}
            QPushButton#backButton:pressed {{ background:#8E342C; }}
            /* A station on the radio list. A row rather than a tile: these are names with a
               line under them saying what they carry, so the screen scrolls like the surah
               list rather than trying to be a grid. Checked is the one playing -- the same
               red the mat uses for the thing happening now. The name is kept from the shelf
               this replaced, because it is the same row and renaming it would churn every
               screenshot and test for nothing. */
            QPushButton#nasheedRow {{ background:{c.paper}; color:{c.strong}; text-align:left;
                                      border:{px(2)}px solid {c.line}; border-radius:{px(10)}px;
                                      font-size:{px(30)}px; padding:{px(20)}px {px(26)}px; }}
            QPushButton#nasheedRow:pressed {{ background:{c.pressed}; }}
            QPushButton#nasheedRow:checked {{ background:{BRICK}; color:#FFFFFF;
                                              border-color:{BRICK}; font-weight:bold; }}
            /* The same button, given a thumb's worth of height. It is pressed by somebody
               standing over a mat on the floor, and it was 29 pixels tall on the 7" panel --
               a fingernail. Twice that, and a floor under the width as well so that a short
               word cannot shrink it: Chinese has two characters for Back and came out 60 wide
               against 60 tall, which the floor takes to 80. The sizes live here rather than on
               the widget because the scale changes with the window, and it is the stylesheet,
               not the widgets, that gets rebuilt when it does -- a minimum set on the widget
               at build time keeps whatever scale happened to be in force then, which is how
               the first attempt at this came out full size on the 7" screen. */
            QPushButton#bigBack {{ background:{BRICK}; color:white; border:none;
                                   border-radius:{px(8)}px; font-size:{px(28)}px;
                                   font-weight:bold; padding:{px(12)}px {px(30)}px;
                                   min-height:{px(90)}px; min-width:{px(90)}px; }}
            QPushButton#bigBack:pressed {{ background:#8E342C; }}
            /* Wu'du. The heading sits on the same white plate the prayer names and the Hadith
               heading wear, so the three screens read as one mat. */
            QWidget#wuduStep, QWidget#wuduStage {{ background:{c.paper}; }}
            QLabel#wuduHeading {{ background:white; color:black; font-size:{px(52)}px;
                                  font-weight:bold; border-radius:{px(10)}px;
                                  padding:{px(10)}px {px(26)}px; }}
            /* The size here is the FIRST of the three the A buttons on a step offer, and the
               step sets its own on the label when another is chosen -- see wudu.WUDU_SIZES.
               The number comes from there so the two cannot drift apart. */
            QLabel#wuduWords {{ color:{c.ink}; font-size:{px(WUDU_WORDS_PX)}px; }}
            QLabel#prayerNameBig {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                    font-size:{px(64)}px; font-weight:bold; }}
            QWidget#banner {{ background:{c.chip}; }}
            QWidget#compassRoot, QWidget#compassRoot QLabel {{ background:{c.paper}; color:{c.strong}; }}
            QLabel#compassTitle {{ font-size:{px(44)}px; font-weight:bold; }}
            QLabel#compassArabic {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                    font-size:{px(52)}px; font-weight:bold; }}
            /* A step bigger again, and square-ish: it sits in the corner of the screen now
               with nothing beside it, where before it was a block on the end of a row. */
            QPushButton#updateButton {{ background:{BRICK}; color:white; border:none;
                                        font-size:{px(26)}px; font-weight:bold;
                                        padding:{px(10)}px {px(34)}px;
                                        border-radius:{px(8)}px;
                                        min-height:{px(88)}px; min-width:{px(88)}px; }}
            QPushButton#updateButton:pressed {{ background:#8E342C; }}
            QPushButton#updateButton:disabled {{ background:#8E342C; color:#E3BDB9; }}
            QWidget#knowledge {{ background:{c.paper}; }}
            QLabel#cornerTitle {{ font-size:{px(40)}px; font-weight:bold; color:{c.strong}; }}
            QAbstractButton#tile {{ background:transparent; border:none; }}
            QWidget#corner, QWidget#surahList, QWidget#reader {{ background:{c.paper}; }}
            QWidget#passageList, QWidget#passageReader {{ background:{c.paper}; }}
            QLabel#passageSaid {{ font-size:{px(26)}px; color:{c.stone};
                                  font-style:italic; }}
            QLabel#passageMeaning {{ font-size:{px(30)}px; color:{c.strong}; }}
            QScrollArea {{ background:{c.paper}; }}
            QPushButton#surahRow {{ background:{c.paper}; border:{px(2)}px solid {c.line};
                                    border-radius:{px(12)}px; text-align:left; }}
            QPushButton#surahRow:pressed {{ background:{c.pressed}; border-color:{c.lapis}; }}
            QPushButton#surahRow QLabel {{ background:transparent; }}
            QLabel#surahNumber {{ font-size:{px(30)}px; font-weight:bold; color:{c.strong};
                background:transparent; border:{px(NUMBER_LINE)}px solid {c.strong}; }}
            QLabel#surahName {{ font-size:{px(28)}px; font-weight:bold; color:{c.strong}; }}
            QLabel#surahMeaning {{ font-size:{px(20)}px; color:{c.stone}; }}
            QLabel#surahArabic {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                  font-size:{px(34)}px; color:{c.strong}; }}
            QLabel#readerTitle {{ font-size:{px(30)}px; font-weight:bold; color:{c.strong}; }}
            /* Whose translation is on the page. Quieter than the surah's name beside it: it is
               there to be read once and then not to compete with the text. */
            QLabel#readerCredit {{ font-size:{px(19)}px; color:{c.hint}; }}
            /* The same metrics as the Back button beside it, so the pair reads as a pair.
               Its width is matched to Back's at runtime too, because "Back" is a different
               length in every language and the glyph is always one character wide. */
            QPushButton#reciteButton {{ background:transparent; border:none;
                                        padding:{px(4)}px; }}
            QPushButton#reciteButton:pressed {{ background:{c.pale};
                                                border-radius:{px(8)}px; }}
            QLabel#sayingVerse {{ font-size:{px(22)}px; color:{c.highlight};
                                  padding-left:{px(8)}px; }}
            QLabel#readerWhere {{ font-size:{px(24)}px; color:{c.stone};
                                  min-width:{px(200)}px; qproperty-alignment:AlignCenter; }}
            /* White, not c.paper. The chip this sits on is dark in BOTH themes -- "#262626"
               after dark and "black" by day -- so c.paper meant a BLACK arrow on a near-black
               button whenever the screen was dark, which is to say most of the time on a mat.
               The arrow was invisible and the page buttons read as dead. Worse, the DISABLED
               rule underneath was the brighter of the two, so the one that did nothing was the
               one you could see. Harry reported it as "the left and right buttons dont do
               anything?", and they did; you could not see them. */
            /* As tall as the largest of the three A's beside them, which is what Harry asked
               for once those grew: "make them a little bigger so their boxes are the same
               size as the largest A". Their height, the way the wu'du step matches its A's
               to its arrows -- they stay a little wider than they are tall, because an arrow
               in a square is a smaller target for a thumb than an arrow in a pill. */
            QPushButton#turnPage {{ background:{c.chip}; color:white; border:none;
                                    border-radius:{px(10)}px; font-size:{px(36)}px;
                                    font-weight:bold; min-width:{px(READING_TEXT_SIZE_PX)}px;
                                    /* No padding up and down: a stylesheet's min-height is
                                       the room INSIDE the padding, so four pixels top and
                                       bottom made a 64 box come out 72. */
                                    min-height:{px(READING_TEXT_SIZE_PX)}px;
                                    padding:0px {px(16)}px; }}
            /* The pair on a board -- the du'as and the sayings -- is the same button a size
               up and in the mat's red, which is the colour of everything you press on it.
               Harry: "make them angular and bigger too, they should also be in a red box
               instead of grey". The chevron inside is drawn: see ArrowButton. */
            QPushButton#turnBoard {{ background:{BRICK}; color:white; border:none;
                                     border-radius:{px(10)}px;
                                     min-width:{px(BOARD_ARROW)}px;
                                     min-height:{px(BOARD_ARROW)}px;
                                     padding:0px {px(16)}px; }}
            QPushButton#turnBoard:pressed {{ background:#8E342C; }}
            /* Dead at the end of a category: the box fades back to the chip colour and the
               chevron greys with it, the same way the reading bar's pair goes out. */
            QPushButton#turnBoard:disabled {{ background:{c.chip}; }}
            QPushButton#turnPage:hover:enabled {{ background:{BRICK}; }}
            QPushButton#turnPage:pressed {{ background:{BRICK}; }}
            /* The same button with the arrow faded, rather than a differently coloured one:
               nothing moves when you reach the end of a surah, the way on just stops. */
            QPushButton#turnPage:disabled {{ background:{c.chip}; color:#555555; }}
            QPushButton#tongue {{ background:{c.paper}; color:{c.strong};
                                  border:{px(2)}px solid {c.line}; border-radius:{px(10)}px;
                                  font-size:{px(22)}px; padding:{px(6)}px {px(14)}px; }}
            QPushButton#tongue:checked {{ background:{BRICK}; color:white; border-color:{BRICK}; }}
            QSlider#brightness::groove:horizontal {{ height:{px(14)}px; background:{c.line};
                                                     border-radius:{px(7)}px; }}
            QSlider#brightness::sub-page:horizontal {{ background:{BRICK};
                                                       border-radius:{px(7)}px; }}
            QSlider#brightness::handle:horizontal {{ background:{c.strong};
                                                     border:{px(2)}px solid {c.paper};
                                                     width:{px(44)}px; height:{px(44)}px;
                                                     margin:{-px(16)}px 0;
                                                     border-radius:{px(22)}px; }}
            /* The slider's own background, which the blanket QWidget rule paints paper-white.
               On the black banner that showed as a white rectangle with a bar across it rather
               than a slider -- invisible in the layout, obvious the moment it was rendered. */
            QSlider#volume, QSlider#volumeOnDark {{ background:transparent; }}
            QSlider#volume::groove:horizontal {{ height:{px(10)}px; background:{c.line};
                                                 border-radius:{px(5)}px; }}
            QSlider#volume::sub-page:horizontal {{ background:{c.lapis};
                                                   border-radius:{px(5)}px; }}
            QSlider#volume::handle:horizontal {{ background:{c.strong};
                                                 border:{px(2)}px solid {c.paper};
                                                 width:{px(30)}px; height:{px(30)}px;
                                                 margin:{-px(11)}px 0;
                                                 border-radius:{px(15)}px; }}
            /* On the banner, which is a black chip whatever the theme, so the slider has to be
               light on dark rather than following the paper. */
            QSlider#volumeOnDark::groove:horizontal {{ height:{px(10)}px; background:#555555;
                                                       border-radius:{px(5)}px; }}
            QSlider#volumeOnDark::sub-page:horizontal {{ background:white;
                                                         border-radius:{px(5)}px; }}
            QSlider#volumeOnDark::handle:horizontal {{ background:white; border:none;
                                                       width:{px(30)}px; height:{px(30)}px;
                                                       margin:{-px(11)}px 0;
                                                       border-radius:{px(15)}px; }}
            QLabel#volumeRead {{ font-size:{px(22)}px; color:{c.stone}; }}
            QLabel#volumeReadOnDark {{ background:{c.chip}; color:white; font-size:{px(22)}px; }}
            QLabel#compassBearing {{ font-size:{px(150)}px; font-weight:bold; color:{c.strong}; }}
            QLabel#compassStatus {{ font-size:{px(40)}px; font-weight:bold; }}
            QLabel#compassDetail {{ font-size:{px(24)}px; color:{c.hint}; }}
            QWidget#timingRoot, QWidget#timingRoot QLabel {{ background:{c.paper}; color:{c.strong}; }}
            QWidget#timingRoot QLabel#timingTitle {{ background:{c.chip}; color:white; font-size:{px(30)}px;
                                                    font-weight:bold; padding:{px(10)}px {px(24)}px;
                                                    border-radius:{px(8)}px; }}
            QLabel#timingCount {{ font-size:{px(28)}px; font-weight:bold; }}
            QLabel#timingHint {{ font-size:{px(30)}px; font-weight:bold; }}
            QPushButton#timingButton {{ background:{c.paper}; color:{c.strong}; border:{px(3)}px solid {c.strong};
                                        border-radius:{px(8)}px; font-size:{px(28)}px; font-weight:bold;
                                        padding:{px(12)}px {px(34)}px; }}
            QPushButton#timingButton:pressed {{ background:{c.pressed}; }}
            QPushButton#tapTimings {{ background:{c.chip}; color:white; border:none; border-radius:{px(8)}px;
                                      font-size:{px(24)}px; font-weight:bold; padding:{px(10)}px {px(26)}px; }}
            QLabel#bannerText {{ background:{c.chip}; color:white; font-size:{px(28)}px;
                                 font-weight:bold; }}
            /* The pin is drawn with its background left see-through, and it needs saying here
               or it is not: the blanket QWidget rule at the top of this sheet paints every
               widget in the paper colour, and a QLabel is a widget. So the pin's square came
               out black on the strip's dark grey by night, and white on its black by day --
               a box around the pin either way. Harry: "the geo icon has a black background".
               The strip is the one place on the mat where paper is not what is behind you. */
            QLabel#bannerPin {{ background:transparent; }}
            QWidget#playerRoot {{ background:{c.paper}; }}
            QWidget#bar, QWidget#bar QLabel {{ background:{c.paper}; color:{c.strong}; }}
            QWidget#bar QPushButton {{ background:transparent; color:{c.strong}; border:none;
                                       font-size:{px(28)}px; padding:{px(10)}px {px(18)}px; }}
            QWidget#bar QLabel#rakat {{ background:{c.chip}; color:white; font-size:{px(36)}px;
                                        font-weight:bold; padding:0 {px(20)}px;
                                        border-radius:{px(8)}px; min-height:{px(56)}px; }}
            QLabel#prayerName {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                 font-size:{px(54)}px; font-weight:bold; }}
            /* The word beside the switch in the middle of the prayer bar. Smaller than the
               Arabic name that used to sit there: it is a label on a control, not a heading,
               and the control is the thing the eye should land on. */
            QWidget#bar QLabel#meaningWord {{ font-size:{px(30)}px; font-weight:bold; }}
            QWidget#bar QLabel#meaningWord:disabled {{ color:{c.stone}; }}
            QWidget#bar QLabel#title {{ background:{c.chip}; color:white; font-size:{px(26)}px;
                                        font-weight:bold; padding:0 {px(20)}px;
                                        border-radius:{px(8)}px; min-height:{px(56)}px; }}
            QWidget#bar QPushButton#stop {{ background:{BRICK}; color:white; border:none;
                                            border-radius:{px(8)}px; font-size:{px(30)}px;
                                            font-weight:bold; padding:0 {px(34)}px;
                                            min-height:{px(56)}px; }}
            QWidget#bar QPushButton#stop:pressed {{ background:#8E342C; }}
            QWidget#done {{ background:{c.paper}; }}
            QWidget#done QLabel {{ background:transparent; color:{c.strong}; font-size:{px(56)}px; font-weight:bold; }}
            QWidget#tasbih {{ background:{c.paper}; }}
            QLabel#askHint {{ font-size:{px(26)}px; font-weight:normal; color:{c.source}; }}
        """

    def page(self, title: str, subtitle: str = "", back: bool = False) -> tuple[QtWidgets.QWidget, QtWidgets.QVBoxLayout]:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(self.px(64), self.px(36), self.px(64), self.px(36))
        lay.setSpacing(self.px(12))
        if back:
            b = no_focus(QtWidgets.QPushButton(self.t("settings.back")))
            b.setObjectName("link")
            b.clicked.connect(self.go_home)
            row = QtWidgets.QHBoxLayout()
            row.addWidget(b)
            row.addStretch(1)
            lay.addLayout(row)
        h = QtWidgets.QLabel(title)
        h.setObjectName("h1")
        lay.addWidget(h)
        if subtitle:
            s = QtWidgets.QLabel(subtitle)
            s.setObjectName("sub")
            lay.addWidget(s)
        return w, lay

    # Home: five prayers, big enough to tap while kneeling

    def build_welcome(self):
        """The screen the mat opens on: Harry's mark, and touching it goes in.

        The whole screen and nothing else -- no banner, no clock, no sky. It was a mosque with
        a moving sky and the prayer times across the top until 1.76, and Harry replaced it with
        his own drawing and asked for nothing to be put back on it. See FrontDoor.

        The film if there is one, the still if there is not, and None if there is neither --
        and then the mat opens on the mosque with the five arches rather than on an empty
        screen. That matters more than it looks: both arrive in a release, so a mat part way
        through an update meets whichever of the three it has.
        """
        folder = self.assets / "welcome"
        if not (folder / "front.gif").is_file() and not (folder / "front.png").is_file():
            return None
        screen = FrontDoor(folder / "front.png", folder / "front.gif")
        if not screen.ready:
            screen.deleteLater()
            return None
        screen.chosen.connect(self.leave_welcome)
        # Read off the texts that are actually installed rather than written down here, so the
        # line cannot say one thing while the mat holds another. See salaah/sources.py.
        from . import sources
        screen.say_thanks(sources.short(self.quran))
        # There is no mosque on the front door any more, so nothing here to keep a sky or a
        # clock for. The two places that look for one take None for an answer.
        self.welcome_mosque = None
        return screen

    def leave_welcome(self, _which: str = "") -> None:
        """MySalaah was touched. In to the mosque, walking into the name on the way.

        The same walk as stepping into an arch, and built the same way round: the screen is
        changed first and the animation played over the top, so a walk cut short -- or never
        started -- leaves you on the mosque either way.
        """
        self.stir()
        walk = None
        front = getattr(self, "welcome_mosque", None)
        if front is not None and self.stack.currentWidget() is self.welcome:
            focus = front.arch_centre("enter")
            if focus is not None:
                walk = (self.stack.grab(), self.stack.geometry(),
                        front.mapTo(self.stack, focus))
        self.stack.setCurrentWidget(self.home)
        if walk is not None:
            self.veil.start(*walk)

    def name_the_arches(self) -> None:
        """The five prayers' names across the main mosque, from the pack -- unless the drawing
        has them already.

        Three versions of this screen now. The first mosque had the names drawn into it, which
        made them English wherever the mat was set: the one screen that could not follow the
        language, and the first one anybody sees. 1.63 replaced it with empty arches and the
        app wrote the names from the pack. For 1.84 Harry drew the mosque again ten times over,
        once per language, with the names printed in -- so the language follows the picture
        instead, and the app must keep its hands off: writing a second word over his would show
        both.

        The names in the pack are still live and still matter -- they are on the prayer pages,
        the call box, the times banner and the dome -- so there is a test that the pack says
        what the drawings say, arch by arch, in all ten languages.
        """
        mosque = getattr(self, "mosque", None)
        if mosque is None or not mosque.ready or mosque.own_names:
            return
        mosque.set_labels({p: ("", self.t(f"prayer.{p}")) for p in PRAYERS}, self.pack_face())

    def build_home(self) -> QtWidgets.QWidget:
        """The mosque: an arch per prayer, the time on the dome, and the prayer whose time it is
        lit up. If the picture is missing for any reason, fall back to plain buttons."""
        self.mosque = MosqueScreen(self.assets, Fonts.english_family,
                                   lang=self.settings.lang, rtl=self.pack.rtl)
        if not self.mosque.ready:
            return self.build_plain_home()
        self.mosque.chosen.connect(self.enter_prayer)
        self.name_the_arches()
        self.catch_up_with_the_sky(self.mosque)

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # home=True like every other sub screen. This banner was built without it from the days
        # when the mosque WAS the main screen and a button back to it would have pointed at
        # itself. The front door took that job in 1.76 -- go_home goes to the welcome screen,
        # not here -- and this strip was never caught up with, so the five arches were the one
        # screen on the mat whose banner had no way off it. Everywhere else: Main screen.
        banner = self.make_banner(gear=True, home=True)
        # The front door's own label, kept under its old name: it is the one the clock tests
        # and the theme tests reach for, and it is a fair name for the banner you see first.
        self.times_label = self.banner_labels[-1]
        lay.addWidget(banner)
        lay.addWidget(self.mosque, 1)

        # A version is on trial until it has run a while; this is what ends the trial.
        from .update import Installer
        QtCore.QTimer.singleShot(int(Installer.SETTLES * 1000), self.settled)

        self.clock = QtCore.QTimer(self)
        self.clock.setInterval(10_000)
        self.clock.timeout.connect(self.tick)
        self.clock.start()
        self.tick()
        return w

    def build_plain_home(self) -> QtWidgets.QWidget:
        """The old row of buttons, kept for when the mosque picture is not there."""
        w, lay = self.page(self.t("app_name"), self.t("home.subtitle"))
        lay.addSpacing(self.px(24))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(self.px(20))
        for pid in PRAYERS:
            entries = self.school.prayers.get(pid, [])
            detail = "\n".join(self.content.unit_label(e, self.pack, self.english) for e in entries)
            b = BigButton(self.t(f"prayer.{pid}"), detail, self.px(60), self.px(28))
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
            b.clicked.connect(lambda _=False, p=pid: self.open_prayer(p))
            row.addWidget(b)
        lay.addLayout(row, 1)
        lay.addSpacing(self.px(16))
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        settings = no_focus(QtWidgets.QPushButton(self.t("home.settings")))
        settings.setObjectName("link")
        settings.clicked.connect(self.open_settings)
        bottom.addWidget(settings)
        lay.addLayout(bottom)
        return w

    @property
    def needs_a_gear(self) -> bool:
        """Whether the strip has to carry a cog.

        It does not when there is a 7in screen, because its Settings tile is the way in and a
        red cog on every screen was one thing too many. With no second screen there is no tile,
        so the cog stays rather than walling Settings off altogether.
        """
        return self.side is None

    @staticmethod
    def room_on_the_strip(label: QtWidgets.QLabel) -> int:
        """How much width the times really have on the strip [label] sits in.

        Worked out from the strip rather than asked of the label, because a label's own width
        is last layout's answer: set longer text on it and width() still reports what it was
        given before, so "does this fit" compares the new text against the old room and says
        no every time. That is what walked the spacing down to one space however much room
        there was.

        Everything else on the strip keeps its width whatever the times say -- the pin, the
        slider, the buttons are all fixed -- so what is left over is the room, and it can be
        added up without laying anything out.
        """
        strip = label.parentWidget()
        row = strip.layout() if strip is not None else None
        if row is None:
            return 0
        edges = row.contentsMargins()
        taken = edges.left() + edges.right() + row.spacing() * max(0, row.count() - 1)
        for i in range(row.count()):
            item = row.itemAt(i)
            if item.widget() is label:
                continue
            if item.widget() is not None:
                taken += item.widget().sizeHint().width()
            elif item.layout() is not None:
                taken += item.layout().sizeHint().width()
            elif item.spacerItem() is not None and item.spacerItem().sizeHint().width() > 0:
                taken += item.spacerItem().sizeHint().width()
        return max(0, strip.width() - taken)

    def make_banner(self, gear: bool = True, home: bool = False) -> QtWidgets.QWidget:
        """The black strip across the top: where you are, the five prayer times with the
        current one in green, what is next -- and how loud the recitation is.

        Built here rather than written out on each screen, so the Qur'an gets exactly the same
        strip as the front door and the two cannot drift apart. Every label it makes is kept in
        banner_labels and written to by the ten-second clock.
        """
        banner = QtWidgets.QWidget()
        banner.setObjectName("banner")
        banner.setFixedHeight(self.px(BANNER_TALL))
        row = QtWidgets.QHBoxLayout(banner)
        row.setContentsMargins(self.px(28), self.px(10), self.px(28), self.px(10))
        # The pin, then the place, then the times. Its own widget rather than a picture inside
        # the rich text: no file to find, and it is drawn at whatever size the screen is.
        pin = QtWidgets.QLabel()
        pin.setObjectName("bannerPin")
        pin.setPixmap(map_pin(self.px(30), BANNER_BLUE))
        row.addWidget(pin, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addSpacing(self.px(8))
        label = QtWidgets.QLabel()
        label.setObjectName("bannerText")
        label.setTextFormat(Qt.TextFormat.RichText)
        self.banner_labels.append(label)
        row.addWidget(label)
        row.addStretch(1)
        row.addLayout(self.volume_slider(dark=True))
        if home:
            # On the sub screens the way back lived on the screen itself, and once the banner
            # went in above it there was nowhere for it to sit. It belongs up here with the
            # other things that are true wherever you are.
            back = QtWidgets.QPushButton(self.t("settings.main_screen"))
            back.setObjectName("mainScreen")
            back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            back.clicked.connect(self.go_home)
            row.addWidget(back)
        if gear and self.needs_a_gear:
            # Red, the colour everything you press is in: Menu, Main screen, the leave buttons.
            cog = GearButton(self.px(52), QtGui.QColor(BRICK))
            cog.setToolTip(self.t("home.settings"))
            cog.pressed_signal.connect(self.open_settings)
            row.addWidget(cog)
        # Filled in now rather than at the next tick: see write_the_times. A strip built
        # between ticks -- which is every strip but the mosque's -- would otherwise come up
        # blank, and on a prayer's units that is a new one every time an arch is touched.
        self.write_the_times()
        return banner

    # The Knowledge Corner

    def build_corner(self) -> QtWidgets.QWidget:
        """What the big screen shows when something is chosen on the 7": the list of surahs,
        one of them open, or -- for the two sections not filled in yet -- a plain word to that
        effect rather than an empty screen that looks broken."""
        stack = QtWidgets.QStackedWidget()
        stack.setObjectName("corner")

        self.surah_list = SurahList(self, self.quran)
        self.surah_list.chose.connect(self.open_surah)
        stack.addWidget(self.surah_list)

        self.reader = Reader(self, self.quran)
        self.reader.back.connect(self.open_corner_list)
        stack.addWidget(self.reader)

        # The two shorter sections. Same widgets for both, told apart by which file they read
        # and what the list is headed.
        self.section_lists: dict[str, PassageList] = {}
        self.section_readers: dict[str, PassageReader] = {}
        for name, source in (("duas", self.duas), ("kalima", self.kalima),
                             ("hadith", self.sayings)):
            listing = PassageList(self, source, self.t(f"corner.{name}"))
            listing.chose.connect(lambda i, n=name: self.open_passage(n, i))
            stack.addWidget(listing)
            self.section_lists[name] = listing

            reader = PassageReader(self, source)
            reader.back.connect(lambda n=name: self.open_section(n))
            stack.addWidget(reader)
            self.section_readers[name] = reader

        # The kalima are chosen off a mosque with six arches rather than a list, so the sub
        # menu looks like the front door. The list is still there behind it, and is what shows
        # if the drawing is missing.
        # The du'as are chosen by kind before they are chosen by name: eighteen tiles, and
        # behind each only the du'as filed under it. Without the drawing this falls back to
        # the plain list, which is what the mat did before there was a menu.
        self.dua_menu = DuaMenu(self)
        if self.dua_menu.ready:
            self.dua_menu.chose.connect(self.open_dua_category)
            stack.addWidget(self.dua_menu)
        else:
            self.dua_menu.deleteLater()
            self.dua_menu = None

        # The sayings are chosen the same way: twelve headings off Harry's drawing, and behind
        # each one only the hadiths filed under it. Same widget as the du'a menu, four across
        # instead of six and pointed at its own folder.
        self.hadith_menu = DuaMenu(self, names=SAYINGS, folder="hadith-menu",
                                   across=SAYINGS_ACROSS)
        if self.hadith_menu.ready:
            self.hadith_menu.chose.connect(self.open_saying_category)
            stack.addWidget(self.hadith_menu)
        else:
            self.hadith_menu.deleteLater()
            self.hadith_menu = None

        self.arch_menus: dict[str, ArchMenu] = {}
        menu = ArchMenu(self, "kalima", Fonts.english_family)
        if menu.ready:
            menu.chose.connect(lambda n: self.open_passage("kalima", n - 1))
            stack.addWidget(menu)
            self.arch_menus["kalima"] = menu
            self.catch_up_with_the_sky(menu.mosque)
        else:
            menu.deleteLater()

        # The du'as of one kind are shown on a board rather than in a list, two at a time,
        # and walked with the same pair of chevrons as the sayings. They were dealt off a
        # shuffled bag until 1.69: a kind holds two to five, so the bag worked, but "a
        # different two each visit" and "the two I was reading a moment ago" are different
        # things to want and the second is the one you want when you are stood on a mat.
        self.dua_board = DuaBoard(self, self.duas)
        self.dua_board.chose.connect(lambda n: self.open_passage("duas", n))
        stack.addWidget(self.dua_board)

        # Wu'du: the seven steps as a row of tall tiles, and one page behind them that the
        # chosen step is loaded into. One page rather than seven, because each holds a film and
        # seven films sitting in memory for the six nobody is looking at is a waste of a Pi.
        self.wudu_menu = DuaMenu(self, names=[f"step-{x['key']}" for x in self.wudu.steps],
                                 folder="wudu", across=max(1, len(self.wudu.steps)))
        if self.wudu.steps and self.wudu_menu.ready:
            self.wudu_menu.chose.connect(lambda n: self.open_wudu_step(n.removeprefix("step-")))
            stack.addWidget(self.wudu_menu)
        else:
            self.wudu_menu.deleteLater()
            self.wudu_menu = None

        # The children's games. The sheet is drawn for eighteen tiles and eleven of them now
        # carry a game's name and picture, but only the ones BUILT here are asked for, so the
        # rest are drawing and not buttons: a child pressing one gets nothing, which is the
        # truth. The alternative -- wiring all eleven and showing "not filled in yet" -- tells
        # a child they pressed the right thing and the mat let them down.
        #
        # WATCH THE TILE NAMES. The sheet Harry drew for 1.89 moved every one of them: the box
        # the menu used to call "wudu" is now the Prayer Game and the box it called "game" is
        # Qibla Quest, because Wu'du has gone to the Knowledge menu. assets/children/menu.json
        # was renamed to follow the pictures, and tools/check_menu_names.py now reads the
        # words out of the drawing and refuses a menu whose names have drifted from them.
        self.games: dict[str, QtWidgets.QWidget] = {}
        # In the order Harry drew them on the sheet, so the registry reads like the menu.
        # Six games were taken out in October 2026: Charity Counter, Mosque Manners, Ramadan
        # Calendar, Arabic Letter Match, Tasbih Counter and Islamic Pattern Builder. Four of
        # them put an Islamic name on a secular drill -- Tasbih Counter asked which strand had
        # seven beads, Ramadan Calendar asked what came after 29, Islamic Pattern Builder
        # offered circle, square, triangle and diamond. A child who finished them had counted
        # and matched shapes, and the mat had told him he was doing something else. Arabic
        # Letter Match and Mosque Manners did teach something, and may come back built properly
        # -- five of twenty-eight letters as three-way multiple choice was not that.
        # BUILT ON FIRST OPEN, not here. Until 1.97 this loop constructed every game while the
        # window was being built, and the three dual-touch games added in 1.97 made that
        # expensive enough to matter: between them they hold 119 MB of QPixmaps -- five jigsaw
        # pictures at 1600x900, five prayer-day scenes, three maze masks -- and all of it was
        # allocated on a mat whose owner might never open the children's menu. This project has
        # paid that bill before; FrontDoor carries the note about a menu that cost 135 MB by
        # keeping its scaled frames.
        #
        # What made it eager was READINESS. A game whose picture is the question is left off
        # the menu when the picture is not installed, and the only way to ask used to be to
        # build the screen and read its .ready. So each class now answers playable(assets) from
        # the FILESYSTEM instead -- a picture is a file, and whether a file is there is not a
        # question that needs a widget. The tile can then be offered or withheld without
        # building anything, and the widget waits until a child presses it.
        #
        # Qibla Quest and the two sorters have no playable() and are always offered: their
        # answers are words, so with no artwork they are poorer games that still work and say
        # so on their own faces. That is deliberate -- see the note in journey_jigsaw.
        self.game_builders: dict[str, type] = {}
        for tile, build in (("game", PrayerDayJourneyScreen),
                            ("qiblaquest", QiblaQuestScreen),
                            ("jigsaw", JourneyJigsawScreen),
                            ("build", BuildTheSalaahScreen),
                            ("pillars", FivePillarsSorterScreen),
                            ("mosque", MosqueMazeScreen)):
            playable = getattr(build, "playable", None)
            if playable is not None and not playable(self.assets):
                continue
            self.game_builders[tile] = build

        self.children_menu = DuaMenu(self, names=tuple(self.game_builders), folder="children",
                                     across=6)
        if self.children_menu.ready and self.game_builders:
            self.children_menu.chose.connect(self.open_from_the_children_menu)
            stack.addWidget(self.children_menu)
        else:
            self.children_menu.deleteLater()
            self.children_menu = None

        # Knowledge: one tile, Wu'du, on a sheet drawn for eighteen. It is the way back to
        # the wu'du steps now that the children's menu is eleven games and has no Wu'du on it
        # -- without this there is no route to them from anywhere in the app.
        #
        # The film is Harry's children's launcher with the Prayer Game tile rubbed out, because
        # the one-tile sheet does not exist yet and the prayer game has moved under Children.
        # The square it leaves is the drawing's own empty square. When a real Knowledge sheet
        # arrives it goes in over the top with tools/swap_menu_film.py like any other.
        self.knowledge_menu = DuaMenu(self, names=("wudu",), folder="knowledge-menu",
                                      across=1)
        if self.knowledge_menu.ready and self.wudu_menu is not None:
            self.knowledge_menu.chose.connect(lambda _: self.open_the_wudu_steps())
            stack.addWidget(self.knowledge_menu)
        else:
            self.knowledge_menu.deleteLater()
            self.knowledge_menu = None

        self.wudu_step = WuduStep(self)
        self.wudu_step.back.connect(self.open_the_wudu_steps)
        self.wudu_step.stepped.connect(
            lambda n: self.open_wudu_step(self.wudu.steps[n]["key"]))
        stack.addWidget(self.wudu_step)

        # The same board for the sayings, with the play mark carried down beside the
        # translation rather than sitting over the Arabic.
        self.hadith_board = DuaBoard(self, self.sayings, sayings=True)
        self.hadith_board.chose.connect(lambda n: self.open_passage("hadith", n))
        stack.addWidget(self.hadith_board)

        # Radio: a handful of stations, played straight off the internet. It replaced the
        # nasheed shelf in 1.70 -- see the note at the top of radio.py for why a receiver
        # suits this mat where a library never could.
        # No way back off it since 1.75, and no heading: the 7" panel is showing the menu the
        # whole time this is up, so the way out is already under the hand that opened it.
        self.radio_screen = RadioScreen(self, self.stations)
        self.radio_screen.wifi.connect(self.open_wifi)
        stack.addWidget(self.radio_screen)

        self.corner_soon = self.page_soon()
        stack.addWidget(self.corner_soon)

        # The world. Built here rather than when it is first touched, because it holds a film
        # and the first frame of a 72-frame animation is not something to go looking for while
        # somebody is watching an empty screen.
        self.world_screen = self.page_world()
        if self.world_screen is not None:
            stack.addWidget(self.world_page)
        return stack

    def page_world(self):
        """The turning globe, with the way to the Kaaba drawn on it. None if the film is not on
        this mat, and then the tile lands on the empty screen as it did before."""
        from .worldscreen import WorldScreen
        page, lay = self.page("", "")
        blank = next(x for x in page.findChildren(QtWidgets.QLabel) if x.objectName() == "h1")
        blank.hide()

        # NOTHING ON THE PAGE BUT THE GLOBE AND THE TALLY BESIDE IT, as of 1.76. The heading
        # ("MySalaah Community") and the Back button have both gone at Harry's asking, and the
        # globe has the room they were taking: the two rows between them were about 215 points
        # of a 1008-point screen, and the globe's size is whatever height is left over after
        # everything else on the page, so taking them off is most of the 25% he asked for.
        #
        # The way out is the 7" panel, which is showing the menu the whole time this is up --
        # the same reason the radio screen could lose its Back button in 1.75.
        #
        # Tight margins for the same reason: every point not spent on the edge of the page is
        # a point of globe. On a 7" panel there is not much to go round at all.
        lay.setContentsMargins(self.px(28), self.px(12), self.px(28), self.px(12))
        lay.setSpacing(self.px(6))

        screen = WorldScreen(self, page, lay)
        if not screen.there:
            page.deleteLater()
            return None
        self.world_page = page
        return screen

    def page_soon(self) -> QtWidgets.QWidget:
        """The screen a tile with nothing behind it yet lands on.

        It carries the strip above it like every other Knowledge screen, and it is headed with
        the name of the tile that was touched rather than one title for all of them -- so it
        says which of the three it is, not merely that something is missing.
        """
        w, lay = self.page("", "")
        # The page's own heading is emptied and the name goes in a plate of its own, centred
        # at the top: white, filled, black letters.
        blank = next(x for x in w.findChildren(QtWidgets.QLabel) if x.objectName() == "h1")
        blank.hide()
        plate = QtWidgets.QHBoxLayout()
        # Left, like the world screen's. A heading centred over an empty page has nothing to
        # be centred on.
        self.soon_title = QtWidgets.QLabel("")
        self.soon_title.setObjectName("namePlate")
        self.soon_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plate.addWidget(self.soon_title)
        plate.addStretch(1)
        lay.insertLayout(0, plate)

        lay.addStretch(1)
        said = QtWidgets.QLabel(self.t("corner.not_yet"))
        said.setObjectName("settingHead")
        said.setAlignment(Qt.AlignmentFlag.AlignCenter)
        said.setWordWrap(True)
        lay.addWidget(said)
        lay.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        # Back rather than Main screen: you got here from somewhere one step away -- the kinds
        # of du'a, usually -- and being thrown out to the front door to try the next one is a
        # long way round.
        back = no_focus(QtWidgets.QPushButton(self.t("corner.back")))
        back.setObjectName("backButton")
        back.setObjectName("bigBack")
        back.clicked.connect(self.leave_the_empty_screen)
        self.soon_back_button = back
        row.addWidget(back)
        lay.addLayout(row)
        return w

    # Where Back goes from the empty screen. Set when it is opened, so the button leads back
    # the way the person came rather than always to the same place.
    soon_back = None

    def leave_the_empty_screen(self) -> None:
        where = self.soon_back
        if where is None:
            self.go_home()
            return
        where()

    def chose_on_the_small_screen(self, which: str) -> None:
        """A tile was touched on the 7in. Most of them open something to read; Settings is the
        one that is not a reading, so it goes its own way rather than being bent into one."""
        if which == "settings":
            if self.playing or self.asleep:
                return
            self.stir()
            self.open_settings()
            return
        self.open_corner(which)

    def open_corner(self, which: str) -> None:
        """Something was touched on the 7". Open it on the big screen -- unless a prayer is
        going on, when the big screen is busy and the touch is almost certainly a stray knee."""
        if self.playing or self.asleep:
            return
        self.stir()
        # Not a section: the way to the five prayers, where the six kalima used to sit. Straight
        # to the arches rather than out to the front door -- a tile with a prayer mat on it and
        # the word Salaah should land on the prayers, not on the screen you came in by.
        if which == "salaah":
            return self.go_to_prayers()
        if which == "quran" and self.quran.there:
            self.open_corner_list()
            return
        # The kinds are worth offering only if there is something behind them. On a mat whose
        # assets were half copied there are no du'as at all, and eighteen tiles that every one
        # of them lands on "nothing here yet" is a worse answer than saying so once.
        if (which == "duas" and getattr(self, "dua_menu", None) is not None
                and self.section_lists["duas"].passages.items):
            self.open_the_kinds_of_dua()
            return
        if (which == "hadith" and getattr(self, "hadith_menu", None) is not None
                and self.section_lists["hadith"].passages.items):
            self.open_the_kinds_of_saying()
            return
        if which == "knowledge" and getattr(self, "knowledge_menu", None) is not None:
            self.open_the_knowledge_menu()
            return
        if which == "children" and getattr(self, "children_menu", None) is not None:
            self.open_the_children_menu()
            return
        if which in self.section_lists and self.section_lists[which].passages.items:
            self.open_section(which)
            return
        if which == "world" and getattr(self, "world_screen", None) is not None:
            self.open_world()
            return
        if which == "radio" and getattr(self, "radio_screen", None) is not None:
            # Always opens, with or without a connection: the screen says what is wrong and
            # offers the way to fix it, which is more use than a tile that does nothing.
            self.radio_screen.retitle()
            self.corner_screen.setCurrentWidget(self.radio_screen)
            self.stack.setCurrentWidget(self.corner_page)
            return
        # Anything with nothing behind it yet -- the three new tiles, or one of the three old
        # ones whose content is missing -- lands here, named.
        self.soon_title.setText(self.t(f"corner.{which}") if which else "")
        self.soon_back = self.go_home        # nothing behind these tiles to go back to
        self.corner_screen.setCurrentWidget(self.corner_soon)
        self.stack.setCurrentWidget(self.corner_page)

    def open_world(self) -> None:
        # Nothing left on the page to relabel -- the heading and the Back button went in
        # 1.76 -- but the words beside the globe follow the language, and retell writes them.
        self.world_screen.retell()
        self.corner_screen.setCurrentWidget(self.world_page)
        self.stack.setCurrentWidget(self.corner_page)

    def open_corner_list(self) -> None:
        self.surah_list.to_the_top()
        self.corner_screen.setCurrentWidget(self.surah_list)
        self.stack.setCurrentWidget(self.corner_page)

    def hush_passages(self) -> None:
        """Stop a kalima part way through. Leaving the screen, the call to prayer and shutting
        down all go through here, so a voice is never left talking to an empty room."""
        for reader in getattr(self, "section_readers", {}).values():
            if reader.saying:
                reader.stop_saying()
        for board in self.boards():
            if board.saying:
                board.stop_saying()

    def boards(self) -> list:
        """The two-column screens: the du'as' and the sayings'. Both can be reading aloud."""
        return [b for b in (getattr(self, "dua_board", None),
                            getattr(self, "hadith_board", None)) if b is not None]

    def saying_a_passage(self) -> bool:
        """Is anything being listened to that the screens should stay on for?

        The boards count: going to sleep over a du'a is as rude as going to sleep over a
        surah. The radio does not, and that is deliberate -- a station plays until somebody
        turns it off, so a mat that cannot go dark while it is on is a mat left bright all
        evening. Sleep stops the panels and leaves the sound alone; see RadioScreen.saying.
        """
        radio = getattr(self, "radio_screen", None)
        return (any(r.saying for r in getattr(self, "section_readers", {}).values())
                or any(b.saying for b in self.boards())
                or (radio is not None and radio.saying))

    def open_section(self, which: str) -> None:
        """Back out of a du'a or a saying lands on the board it came from; the kalima have
        their arches."""
        for name, board in (("duas", getattr(self, "dua_board", None)),
                            ("hadith", getattr(self, "hadith_board", None))):
            if which == name and board is not None and board.only:
                self.corner_screen.setCurrentWidget(board)
                self.stack.setCurrentWidget(self.corner_page)
                return
        menu = self.arch_menus.get(which)
        if menu is not None:
            self.corner_screen.setCurrentWidget(menu)
            self.stack.setCurrentWidget(self.corner_page)
            return
        listing = self.section_lists.get(which)
        if listing is None:
            return
        listing.to_the_top()
        self.corner_screen.setCurrentWidget(listing)
        self.stack.setCurrentWidget(self.corner_page)

    def open_the_kinds_of_dua(self) -> None:
        """The eighteen tiles. This is where the Du'as tile lands; Back out of a du'a returns
        to the list it came from, so getting here again is a fresh touch of the tile."""
        self.corner_screen.setCurrentWidget(self.dua_menu)
        self.stack.setCurrentWidget(self.corner_page)

    def open_dua_category(self, cat: str) -> None:
        """A kind of du'a was touched. Show the ones filed under it -- or, if none are, say so
        under that kind's own name rather than opening an empty list."""
        if self.playing or self.asleep:
            return
        self.stir()
        # The eighteenth tile is the six kalima, which are not a kind of du'a and have a screen
        # of their own.
        from .duamenu import NOT_A_KIND
        if cat in NOT_A_KIND:
            return self.open_section(cat)
        listing = self.section_lists.get("duas")
        named = self.t(f"dua.{cat}")
        if listing is None or not any(cat in item.cats for item in listing.passages.items):
            self.soon_title.setText(named)
            self.soon_back = self.open_the_kinds_of_dua
            self.corner_screen.setCurrentWidget(self.corner_soon)
            self.stack.setCurrentWidget(self.corner_page)
            return
        self.dua_board.show_only(cat, named)
        self.dua_board.to_the_top()
        self.corner_screen.setCurrentWidget(self.dua_board)
        self.stack.setCurrentWidget(self.corner_page)

    def open_the_kinds_of_saying(self) -> None:
        """The twelve headings. Where the Hadith tile lands."""
        self.corner_screen.setCurrentWidget(self.hadith_menu)
        self.stack.setCurrentWidget(self.corner_page)

    def open_saying_category(self, cat: str) -> None:
        """A heading was touched. The sayings filed under it, two to a row."""
        if self.playing or self.asleep:
            return
        self.stir()
        listing = self.section_lists.get("hadith")
        named = self.t(f"saying.{cat}")
        if listing is None or not any(cat in item.cats for item in listing.passages.items):
            self.soon_title.setText(named)
            self.soon_back = self.open_the_kinds_of_saying
            self.corner_screen.setCurrentWidget(self.corner_soon)
            self.stack.setCurrentWidget(self.corner_page)
            return
        self.hadith_board.show_only(cat, named)
        self.hadith_board.to_the_top()
        self.corner_screen.setCurrentWidget(self.hadith_board)
        self.stack.setCurrentWidget(self.corner_page)

    def open_the_knowledge_menu(self) -> None:
        """Where the Knowledge tile lands: Wu'du, and room for what comes after it."""
        self.corner_screen.setCurrentWidget(self.knowledge_menu)
        self.stack.setCurrentWidget(self.corner_page)

    def open_the_children_menu(self) -> None:
        """The children's games. Where the Children tile lands, and where Exit comes back to.

        Gives the 7in back on the way. The three dual-touch games borrow it for their own
        panel, and a child who left a game and found the jigsaw's hint still sitting on the
        small screen would have no way to get rid of it.
        """
        if self.side is not None and getattr(self.side, "showing_game", False):
            self.side.show_idle()
        self.corner_screen.setCurrentWidget(self.children_menu)
        self.stack.setCurrentWidget(self.corner_page)

    def open_from_the_children_menu(self, which: str) -> None:
        """A tile on the children's own menu. Only the games that can be played have tiles at
        all, so an unknown name here means the sheet and the registry have come apart -- do
        nothing rather than guess, which on this menu would open the wrong game."""
        if which in self.game_builders:
            self.open_a_game(which)

    def build_a_game(self, which: str):
        """The game behind a tile, built the first time it is pressed and kept after that.

        See the note in build_corner about why this is not done up front. Kept rather than
        rebuilt because a child goes in and out of the same game over and over, and because
        start_again() already puts a game back to round one -- a fresh widget each time would
        throw away nothing worth throwing away and churn the stack doing it.
        """
        screen = self.games.get(which)
        if screen is None:
            screen = self.game_builders[which](self)
            screen.leave.connect(self.open_the_children_menu)
            self.corner_screen.addWidget(screen)
            self.games[which] = screen
        return screen

    def open_a_game(self, which: str) -> None:
        """Any of the children's games, always from round one."""
        screen = self.build_a_game(which)
        screen.start_again()
        # The 7in is part of these games, not a decoration beside them: the jigsaw's hint, the
        # prayer-day question and its answer buttons, the maze's tally all live there. A game
        # that brought no companion leaves the 7in showing whatever it was showing.
        companion = getattr(screen, "companion", None)
        if companion is not None and self.side is not None:
            self.side.show_game(companion)
        self.corner_screen.setCurrentWidget(screen)
        self.stack.setCurrentWidget(self.corner_page)

    @property
    def game_in_front(self):
        """Whichever game is on the corner screen now, or None.

        Not "is the prayer game in front" any more. A ring press IS the whole of how a game is
        played, so this is what decides between playing a game and moving a prayer, and with
        three games behind the children's menu a press that always went to the prayer game
        would be a press into a screen nobody is looking at.
        """
        if self.stack.currentWidget() is not self.corner_page:
            return None
        now = self.corner_screen.currentWidget()
        return now if now in getattr(self, "games", {}).values() else None

    @property
    def game_open(self) -> bool:
        return self.game_in_front is not None

    def open_the_wudu_steps(self) -> None:
        """The seven steps. Where the Wu'du tile lands, and where Back on a step returns to."""
        self.wudu_step.stop()
        self.corner_screen.setCurrentWidget(self.wudu_menu)
        self.stack.setCurrentWidget(self.corner_page)

    def open_wudu_step(self, key: str) -> None:
        """One step: its drawing, its number and name, and what to do."""
        if self.playing or self.asleep:
            return
        self.stir()
        step = next((x for x in self.wudu.steps if x["key"] == key), None)
        if step is None:
            return self.open_the_wudu_steps()
        named = self.t(f"wudu.{key}")
        # The same choice the du'a board and the passage reader make, from the same place --
        # and unlike the du'as and the sayings, the explanation is shown in Arabic rather than
        # withheld when the mat is set to Arabic only. It is not a translation OF anything:
        # these are instructions written for this app, so Arabic is simply another language
        # they were written in, and a wu'du step with its explanation taken away is a drawing
        # and a number.
        chosen = self.settings.lang or "en"
        said = step["text"].get(chosen) or step["text"].get("en", "")
        self.wudu_step.show_step(step, f"{step['number']} - {named}", said,
                                 place=self.wudu.steps.index(step), of=len(self.wudu.steps))
        self.corner_screen.setCurrentWidget(self.wudu_step)
        self.stack.setCurrentWidget(self.corner_page)

    def open_passage(self, which: str, index: int) -> None:
        reader = self.section_readers.get(which)
        if reader is None:
            return
        reader.open(index)
        self.corner_screen.setCurrentWidget(reader)
        self.stack.setCurrentWidget(self.corner_page)

    def open_surah(self, number: int) -> None:
        self.reader.open(number)
        self.corner_screen.setCurrentWidget(self.reader)
        self.stack.setCurrentWidget(self.corner_page)

    @property
    def reading(self) -> bool:
        return self.stack.currentWidget() is self.corner_page

    def pack_name(self, lang: str) -> str:
        pack = self.packs.get(lang)
        return pack.native_name if pack is not None else lang.upper()

    # The call to prayer, and going to sleep on its own

    GRACE = 120.0        # seconds after a prayer falls due that the call is still worth making

    def azaan_for(self, prayer: str) -> Path | None:
        """The call to play for this prayer, or None if there is no right one for it.

        Fajr has its own: the call at dawn carries a line the other four do not, so calling
        Fajr with the ordinary recording would be saying the wrong words. Until there was a
        Fajr recording the mat showed the notice and stayed silent, which was the honest way
        round; now there is one, so it speaks.
        """
        own = self.assets / "audio" / f"azaan-{prayer}.mp3"
        if own.is_file():
            return own
        if prayer == "fajr":
            return None                  # rather than the wrong words
        ordinary = self.assets / "audio" / "azaan.mp3"
        return ordinary if ordinary.is_file() else None

    @property
    def azaan_file(self) -> Path:
        """Kept for the four prayers that share the one recording."""
        return self.assets / "audio" / "azaan.mp3"

    def check_the_hour(self) -> None:
        """Has a prayer just fallen due? Runs every fifteen seconds, asleep or awake.

        The grace period matters: the mat may have been busy, or the clock may have jumped
        after an update. Without it a prayer missed by a second is missed for the day. With it,
        a prayer missed by two minutes is not called at all -- which is right, because a call
        long after the time is worse than none.
        """
        if not self.settings.azaan:
            return
        now = datetime.now()
        times = self.prayer_times(now)
        for prayer in PRAYERS:
            due = times.get(prayer)
            if due is None or self.called.get(prayer) == now.date():
                continue
            late = (now - datetime.combine(now.date(), due)).total_seconds()
            if 0 <= late < self.GRACE:
                self.called[prayer] = now.date()      # marked before calling: once a day, even
                self.call_to_prayer(prayer)           # if something below goes wrong
                return

    def call_to_prayer(self, prayer: str) -> None:
        """Wake the mat, say whose time it is, and give the call.

        Nothing happens if somebody is already praying. A call over the top of the prayer it is
        calling for would be absurd, and it is the one moment when an interruption is worst.
        """
        if self.playing:
            return
        # Wherever it was -- asleep, in Settings, at the front door -- the call takes it to the
        # mosque. Waking on its own now comes back at the front door, so this can no longer
        # lean on wake() to land in the right place.
        if self.asleep:
            self.wake()
        # A station playing when a prayer falls due is stopped before the muezzin starts.
        # Two things sounding at once is the worst version of this, and of the two it is not
        # the call that should give way.
        radio = getattr(self, "radio_screen", None)
        if radio is not None:
            radio.stop()
        self.go_home()
        # Fajr has its own recording, because the call at dawn says something the others do
        # not. If a prayer has no recording the notice still appears on its own, so the mat
        # still says it is time rather than passing the moment in silence.
        sound = self.azaan_for(prayer)
        # The call itself on the screen -- the muezzin, the words, and what they mean -- when
        # the words are there to show. Otherwise the plain notice it always was, which says it
        # is time and nothing it cannot back up.
        self.let_go_of_the_box()
        if self.adhan.there:
            box = CallBox(self, prayer, sound.name if sound else "", self.adhan)
        else:
            box = Notice(self, self.px, self.t("call.title"))
            box.finish(self.t(f"prayer.{prayer}"), self.t("call.stop"))
        box.finished.connect(self.end_the_call)
        self.call_box = box
        box.show()
        if sound is not None:
            self.call.volume = self.settings.volume
            if self.call.play(sound):
                self.call_watch.start()

    def watch_the_call(self) -> None:
        """Close the notice when the call ends of its own accord, so nobody has to dismiss it."""
        if self.call_box is not None and not self.call.playing:
            self.call_box.accept()

    def let_go_of_the_box(self) -> None:
        """Close and drop whatever box is up.

        It used to be enough to forget it: the old notice was a few labels and Qt collected it
        with the window. The box that replaced it carries a film, and five of those left over
        from five calls are five timers repainting widgets nobody can see -- and, on one of the
        two Qt kits, a crash on the way out. A mat runs for months and calls five times a day,
        so they have to be let go of as they finish, not at the end.
        """
        box, self.call_box = self.call_box, None
        if box is not None:
            box.close()
            box.deleteLater()

    def end_the_call(self, *_) -> None:
        """Stop, whether the call finished or somebody pressed the button."""
        self.call.stop()
        self.call_watch.stop()
        self.let_go_of_the_box()
        self.stir()

    def stir(self) -> None:
        """Something happened. Start the going-to-sleep clock again from the top."""
        minutes = getattr(self.settings, "sleep_after", 0)
        if minutes and hasattr(self, "idle"):
            self.idle.start(int(minutes * 60_000))
        elif hasattr(self, "idle"):
            self.idle.stop()

    def maybe_sleep(self) -> None:
        """Nothing has been pressed for a while. Sleep -- unless that would be rude."""
        if self.asleep:
            return
        # Mid-prayer the screen is being read, not pressed; the call is being listened to; and a
        # message on screen is waiting to be answered. None of those is idleness.
        if self.playing or self.call_box is not None or self.notice is not None:
            return self.stir()
        # Somebody listening to a surah is not idle. Going to sleep over the recitation would
        # be the rudest possible moment to do it.
        if (hasattr(self, "reader") and self.reader.reciting) or self.saying_a_passage():
            return self.stir()
        self.sleep()

    # The clock and the prayer times

    @property
    def place(self) -> Place:
        return Place(self.settings.latitude, self.settings.longitude, self.settings.place)

    def prayer_times(self, when: datetime | None = None) -> dict:
        """Worked out on the device, so it needs no internet. Cached for the day."""
        when = when or datetime.now()
        key = (when.date(), self.settings.latitude, self.settings.longitude, self.school.id)
        if getattr(self, "_times_key", None) != key:
            self._times_key = key
            self._times = times_for(when.date(), self.place, self.school.id,
                                    high_latitude=self.settings.high_latitude)
        return self._times

    def tick(self) -> None:
        self.apply_theme()
        if not hasattr(self, "mosque") or not self.mosque.ready:
            return
        now = datetime.now()
        times = self.prayer_times(now)
        self.mosque.set_time(now.strftime("%H:%M"))
        self.mosque.set_lit(current_prayer(now, times))
        self.mosque.set_sky(*day_fraction(now, times))
        for menu in getattr(self, "arch_menus", {}).values():
            menu.follow_clock(now.strftime("%H:%M"), *day_fraction(now, times))
        # The front door keeps the same clock and the same sky as the screens behind it. No
        # prayer is lit on it: it is a way in, not a choice of prayer.
        front = getattr(self, "welcome_mosque", None)
        if front is not None:
            front.set_time(now.strftime("%H:%M"))
            front.set_sky(*day_fraction(now, times))
        # A prayer's own page gets the same sky and nothing else: its dome carries the prayer's
        # name, so there is no clock on it to keep.
        units = getattr(self, "prayer_mosque", None)
        if units is not None:
            units.set_sky(*day_fraction(now, times))
        self.write_the_times(now, times)

    def forget_the_strips_that_have_gone(self) -> None:
        """Drop the labels whose page has been taken down.

        A prayer's units are rebuilt every time an arch is touched and the old page is thrown
        away -- so the strip that was on it is thrown away with it, while this list goes on
        holding a Python handle to a widget that is no longer there. Writing the time to one
        of those does not quietly do nothing: both Qt bindings raise, out of a timer, which
        takes the app down. Two prayers and a tick was all it needed.

        There is no asking a dead wrapper whether it is dead, so it is asked something
        harmless and the ones that object are dropped.
        """
        alive = []
        for label in self.banner_labels:
            try:
                label.objectName()
            except RuntimeError:
                continue
            alive.append(label)
        self.banner_labels = alive

    def write_the_times(self, now: datetime | None = None, times: dict | None = None) -> None:
        """The place and the five times onto every strip the window owns.

        Its own method rather than part of the clock because a banner can be built between
        ticks -- the front door's, a prayer's units, every corner screen -- and a label nobody
        has written to yet is blank. That is the sky's fault over again: touch a prayer and
        the strip above it has no place and no times on it until the ten-second clock comes
        round. So make_banner calls this as soon as it has made one.
        """
        now = now or datetime.now()
        times = self.prayer_times(now) if times is None else times
        self.forget_the_strips_that_have_gone()
        # The prayer whose time it is stands out in green; the rest are in the banner's own
        # colour. Written as rich text, since a QLabel takes its colours that way.
        now_praying = current_prayer(now, times)
        green = theme.palette().green
        where = self.settings.place or f"{self.settings.latitude:.2f}, {self.settings.longitude:.2f}"

        def strip(spaces: int) -> str:
            """The place and the five times, with [spaces] between each."""
            gap = "&nbsp;" * spaces      # rich text squeezes plain spaces down to one
            shown = gap.join(
                (f'<span style="color:{green}">{self.t(f"prayer.{name}")} '
                 f'{times[name].strftime("%H:%M")}</span>' if name == now_praying else
                 f'{self.t(f"prayer.{name}")} {times[name].strftime("%H:%M")}')
                for name in PRAYERS if times.get(name) is not None)
            # What is coming next used to be named at the end of the row. It has gone: the five
            # times are already there with the current one in green, so the next one is the one
            # after it, and the words were the widest thing in a banner that had to hold more.
            return f'<span style="color:{BANNER_BLUE}">{where}</span>{gap}{shown}'

        # FOUR spaces, and the room for them comes from the slider rather than from the gaps.
        #
        # The version before this tightened the spacing whenever the strip was short, which
        # looked exactly as bad as it sounds -- "no adequate spacing and distance between the
        # prayers, looks like one long sentence" -- and it did it on every screen at once.
        # Two things were wrong. The squeeze was the wrong answer to begin with: the shortfall
        # was 54 pixels in the worst language and the slider beside it was 320 wide, so there
        # was room to be had without touching the words. And it measured every banner the
        # window owns, including the three sitting on pages that have never been shown, whose
        # width is a default Qt has not laid out yet -- 640 against a real 1021. Those
        # measurements dragged every strip down to one space, including the one on screen.
        #
        # So: one spacing, always, and a net that only reads the banner a person is actually
        # looking at. A hidden page cannot vote.
        room = min([self.room_on_the_strip(x) for x in self.banner_labels
                    if x.isVisible() and x.width() > 1] or [0])
        for spaces in (4, 3, 2, 1):
            said = strip(spaces)
            for label in self.banner_labels:
                label.setText(said)
            if room < 1 or self.banner_labels[0].sizeHint().width() <= room:
                break

    # Light and dark

    def wants_dark(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        mode = self.settings.theme if self.settings.theme in theme.MODES else "auto"
        return theme.wants_dark(mode, now, self.prayer_times(now))

    def apply_theme(self, chosen: bool = False) -> bool:
        """Light or dark, as Settings says. Automatic changes at Maghrib and at sunrise, but
        never in the middle of a prayer: it waits until the prayer is over. Returns True if the
        screen changed."""
        if not chosen and self.playing:
            return False
        # Light or dark is set for the whole application, so a window nobody is looking at must
        # not set it. Ordinarily there is only one window and this never bites; under test
        # several exist at once, and a hidden one whose ten-second clock was still running would
        # quietly put the palette back to light underneath the window being examined.
        if not chosen and not self.isVisible():
            return False
        if not theme.set_dark(self.wants_dark()):
            return False
        self.setStyleSheet(self.stylesheet())
        if hasattr(self, "slide"):
            self.slide.follow_theme()
        if self.side is not None:
            self.side.follow_theme()
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.update()
        return True

    def set_theme(self, mode: str) -> None:
        self.settings.theme = mode
        self.persist()
        self.apply_theme(chosen=True)

    def enter_prayer(self, pid: str) -> None:
        """A tap on an arch of the mosque: walk into it, and come out at that prayer's units.

        The picture is taken while the mosque is still up, the screen is then changed in the
        ordinary way, and the walk is played over the top of it. So the screen is right from the
        first moment whatever the animation does, and anything else that opens a prayer - a
        test, a button - simply gets no animation.
        """
        walk = None
        if getattr(self, "mosque", None) is not None and self.stack.currentWidget() is self.home:
            focus = self.mosque.arch_centre(pid)
            if focus is not None:
                walk = (self.stack.grab(), self.stack.geometry(),
                        self.mosque.mapTo(self.stack, focus))
        self.open_prayer(pid)
        if walk is not None:
            self.veil.start(*walk)

    def touched_unit(self, pid: str, name: str) -> None:
        """An arch on a prayer's own mosque. The arches are numbered left to right and so are
        the prayer's units, so the name is the position -- the drawing never has to know what a
        nafl is, which is what lets one builder handle all five pages."""
        entries = self.school.prayers.get(pid, [])
        try:
            entry = entries[int(name) - 1]
        except (ValueError, IndexError):
            return
        walk = None
        front = getattr(self, "prayer_mosque", None)
        if front is not None and self.stack.currentWidget() is self.pick:
            focus = front.arch_centre(name)
            if focus is not None:
                walk = (self.stack.grab(), self.stack.geometry(),
                        front.mapTo(self.stack, focus))
        self.start(pid, entry)
        if walk is not None:
            self.veil.start(*walk)

    def enter_unit(self, pid: str, entry, arch=None) -> None:
        """A tap on one of a prayer's unit arches: the same walk again, into that arch, and out
        at the first screen of the prayer. Built the same way round as [enter_prayer] - the
        prayer begins first and the walk is played over the top of it."""
        walk = None
        if arch is not None and self.stack.currentWidget() is self.pick:
            walk = (self.stack.grab(), self.stack.geometry(),
                    arch.mapTo(self.stack, arch.arch_rect().center()))
        self.start(pid, entry)
        if walk is not None:
            self.veil.start(*walk)

    def prayer_page(self, pid: str):
        """This prayer's own mosque, if one has been drawn for it.

        The same widget as the front door and the kalima menu, pointed at its own folder: the
        drawing, the sky painted behind it, and a box per unit to touch. What the drawing does
        NOT carry is the words -- they were taken out when it was built -- so the number and the
        kind are written in here, from the pack, in the language the mat is set to.

        None if the folder is not there, and then open_prayer falls back to the arches it has
        always drawn for itself. That matters more than it looks: the drawings arrive in a
        release and the five of them are new, so a mat part way through an update should meet
        the old screen rather than an empty one.
        """
        entries = self.school.prayers.get(pid, [])
        if not entries or not (self.assets / "prayers" / pid / "mosque.json").is_file():
            return None
        screen = MosqueScreen(self.assets, Fonts.english_family, folder=f"prayers/{pid}",
                              idle_glow=False)
        if not screen.ready or len(screen.arches) != len(entries):
            # An arch per unit or nothing: a drawing and a school that disagree about how many
            # units a prayer has would put the wrong number on the wrong arch, and the one place
            # that must never be wrong on this mat is how many rakats you are about to pray.
            if screen.ready:
                print(f"prayers/{pid}: {len(screen.arches)} arches for {len(entries)} units; "
                      f"drawing the arches instead", file=sys.stderr)
            screen.deleteLater()
            return None
        return screen

    def dress_prayer_page(self, pid: str, screen, entries) -> None:
        """The name on the dome and the words in the arches, in the current language."""
        screen.set_dome(self.t(f"prayer.{pid}"))
        said = {}
        for i, entry in enumerate(entries, start=1):
            unit = self.content.units.get(entry.unit_id)
            said[str(i)] = (str(unit.rakats if unit else ""), self.t(f"kind.{entry.kind}"))
        screen.set_labels(said, self.pack_face())

    def open_prayer(self, pid: str) -> None:
        """The units of this prayer, each as an arch like the ones on the mosque."""
        self.prayer = pid
        old = self.pick
        entries = self.school.prayers.get(pid, [])

        drawn = self.prayer_page(pid)
        if drawn is not None:
            self.dress_prayer_page(pid, drawn, entries)
            self.catch_up_with_the_sky(drawn)
            drawn.chosen.connect(lambda name: self.touched_unit(pid, name))
            self.prayer_mosque = drawn
            page = QtWidgets.QWidget()
            box = QtWidgets.QVBoxLayout(page)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(0)
            # The same strip as the front door and the mosque behind it, which is also the way
            # home: there is no Menu button on this page because the banner already has one.
            box.addWidget(self.make_banner(gear=True, home=True))
            box.addWidget(drawn, 1)
            self.pick = page
            self.stack.insertWidget(1, page)
            self.stack.removeWidget(old)
            old.deleteLater()
            self.stack.setCurrentWidget(page)
            return

        self.prayer_mosque = None
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(self.px(48), self.px(16), self.px(48), self.px(20))
        lay.setSpacing(self.px(4))

        # "Menu", the same word as the button that leaves a prayer, rather than "Back": it goes
        # to the same place, so it should read the same wherever you meet it.
        back = no_focus(QtWidgets.QPushButton(self.t("player.menu")))
        back.setObjectName("backButton")
        back.clicked.connect(self.go_home)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(back)
        top.addStretch(1)
        lay.addLayout(top)

        # The prayer's name on a white plate, the same one the Hadith and world screens wear,
        # with the Arabic beside the English rather than thrown to the far side of the screen.
        # They are the same name; having them at opposite edges read as two separate headings.
        plate = QtWidgets.QFrame()
        plate.setObjectName("namePlate")
        inside = QtWidgets.QHBoxLayout(plate)
        inside.setContentsMargins(self.px(30), self.px(6), self.px(30), self.px(6))
        inside.setSpacing(self.px(26))
        english = QtWidgets.QLabel(self.t(f"prayer.{pid}"))
        english.setObjectName("plateWord")
        inside.addWidget(english, 0, Qt.AlignmentFlag.AlignVCenter)
        arabic = QtWidgets.QLabel(self.content.prayer_names.get(pid, ""))
        arabic.setObjectName("plateArabic")
        inside.addWidget(arabic, 0, Qt.AlignmentFlag.AlignVCenter)
        self.prayer_plate = plate
        names = QtWidgets.QHBoxLayout()
        names.addWidget(plate, 0, Qt.AlignmentFlag.AlignLeft)
        names.addStretch(1)
        lay.addLayout(names)

        if self.arch_shape.ready and entries:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(self.px(10))
            for entry in entries:
                unit = self.content.units.get(entry.unit_id)
                arch = ArchButton(self.arch_shape, str(unit.rakats if unit else ""),
                                  self.t(f"kind.{entry.kind}"), entry, self.pack_face())
                arch.chosen.connect(lambda e=entry, a=arch: self.enter_unit(pid, e, a))
                row.addWidget(arch, 1)
            lay.addLayout(row, 1)
        else:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(self.px(24))
            for entry in entries:
                b = BigButton(self.content.unit_label(entry, self.pack, self.english), "", self.px(64))
                b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
                b.clicked.connect(lambda _=False, e=entry: self.start(pid, e))
                row.addWidget(b)
            lay.addLayout(row, 1)

        self.pick = w
        self.stack.insertWidget(1, w)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.setCurrentWidget(w)

    def put_it_all_down(self) -> None:
        """Stop whatever the mat was in the middle of. Shared by the two ways of leaving.

        Not folded into go_home with a flag, because go_home is wired straight to button
        clicked signals and Qt hands those a bool -- a flag here would be set by any button
        that happened to be checkable, which is the kind of bug that takes an evening.
        """
        # Leaving the book stops the recitation. This is also what silences it when a prayer
        # falls due, because the call comes home first before it speaks.
        if hasattr(self, "reader") and self.reader.reciting:
            self.reader.stop_reciting()
        self.hush_passages()
        self.session = None
        if self.veil.running:
            self.veil.stop()        # don't walk into an arch we have just walked back out of
        if hasattr(self, "compass_screen"):
            self.compass_screen.close_screen()

    def go_home(self) -> None:
        self.put_it_all_down()
        # The front door, not the mosque. It is the main page now -- Harry's word -- and
        # everything labelled Menu lands on it: the button off a prayer's units, Main screen
        # from the Knowledge Corner. From there one touch anywhere is the prayers.
        self.stack.setCurrentWidget(self.welcome if self.welcome is not None else self.home)

    def go_to_prayers(self) -> None:
        """Straight to the five arches, past the front door. The Salaah tile on the 7in."""
        self.put_it_all_down()
        self.stack.setCurrentWidget(self.home)

    # The Qibla

    def qibla_bearing(self) -> float:
        return bearing_to_kaaba(self.settings.latitude, self.settings.longitude)

    def begin(self) -> None:
        """What the app shows when it starts: the Qibla compass first, unless it is switched
        off, or a compass shows the display still faces the way it did when last lined up.
        With a second screen, the compass goes there and the main screen comes straight up."""
        if self.side is not None:
            self.side.show_idle()
            return self.go_home()
        if not QIBLA or not self.settings.qibla_start:
            return self.go_home()
        if self.facing.fitted and self.settings.qibla_heading is not None:
            now = self.facing.read()
            if now is not None and abs(turn_needed(now, self.settings.qibla_heading)) <= MOVED:
                return self.go_home()              # not moved since it was lined up
        self.open_qibla()

    def open_qibla(self) -> None:
        if not hasattr(self, "compass_screen"):
            return
        self.stack.setCurrentWidget(self.compass_screen)
        self.compass_screen.open()

    @property
    def qibla_open(self) -> bool:
        return hasattr(self, "compass_screen") and self.stack.currentWidget() is self.compass_screen

    def side_lined_up(self, lined_up: bool) -> None:
        """The 7" compass has been lined up: remember which way the display faces."""
        heading = self.side.compass.heading
        if lined_up and heading is not None:
            self.settings.qibla_heading = round(heading, 1)
            self.persist()

    def qibla_done(self, lined_up: bool) -> None:
        if lined_up and self.compass_screen.heading is not None:
            self.settings.qibla_heading = round(self.compass_screen.heading, 1)
            self.persist()
        self.go_home()

    # Player

    def build_player(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setObjectName("playerRoot")
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Three equal columns, so the Arabic name sits dead centre whatever is either side of it.
        bar = TopBar()
        bar.setObjectName("bar")
        grid = QtWidgets.QGridLayout(bar)
        # Equal margins left and right, so the centre column really is the centre of the screen.
        grid.setContentsMargins(self.px(16), self.px(6), self.px(16), self.px(6))
        grid.setHorizontalSpacing(self.px(12))
        for column in range(3):
            grid.setColumnStretch(column, 1)

        left = QtWidgets.QHBoxLayout()
        left.setSpacing(self.px(12))
        stop = no_focus(QtWidgets.QPushButton(self.t("player.menu")))
        stop.setObjectName("stop")
        stop.clicked.connect(self.stop)
        left.addWidget(stop)
        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        # The rakat reads with the prayer it belongs to - "Dhuhr, 2 Nafl" then "Rakat 2 of 2" -
        # rather than being stranded at the other end of the banner. Centred in the row, not
        # stretched, so its box is the same height as the one beside it.
        left.addSpacing(self.px(10))
        self.rakat_label = QtWidgets.QLabel()
        self.rakat_label.setObjectName("rakat")
        left.addWidget(self.rakat_label, 0, Qt.AlignmentFlag.AlignVCenter)
        left.addStretch(1)
        grid.addLayout(left, 0, 0)

        # Dead centre: the switch that takes the meaning off the screen and leaves the Arabic.
        #
        # The prayer's name in Arabic was here until 1.75, and it was the one thing in the bar
        # that nobody needed: you are three touches into Dhuhr and the English name of it is
        # already in the box at the left-hand end. Harry asked for the switch in its place,
        # and for the reason the rest of this comment is about.
        #
        # Praying with the Arabic alone was possible before -- it is what "Arabic only" in
        # Settings does -- but that is a LANGUAGE, so choosing it turned the menus, the du'as,
        # the sayings and the wu'du steps Arabic too. Somebody who reads English menus and
        # wants the Arabic alone in front of them while they pray had no way to say so. This
        # is that, and nothing else: it hides a column on this screen and touches no setting
        # that any other screen reads.
        #
        # The word beside it for the same reason the Settings switches have one -- a knob on
        # its own, read from a few feet away, says nothing about what it does.
        centre = QtWidgets.QWidget(bar)                # placed by TopBar, dead centre
        middle = QtWidgets.QHBoxLayout(centre)
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(self.px(16))
        self.meaning_word = QtWidgets.QLabel(self.t("player.meaning"))
        self.meaning_word.setObjectName("meaningWord")
        self.meaning_word.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        middle.addWidget(self.meaning_word, 0, Qt.AlignmentFlag.AlignVCenter)
        self.meaning_switch = Switch(self.settings.meaning, scale=self.s)
        self.meaning_switch.setObjectName("meaningSwitch")
        self.meaning_switch.toggled.connect(self.set_meaning)
        middle.addWidget(self.meaning_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        bar.centre = centre
        bar.setMinimumHeight(self.meaning_switch.sizeHint().height() + self.px(24))

        right = QtWidgets.QHBoxLayout()
        right.setSpacing(self.px(16))
        right.addStretch(1)
        # The volume sits in the bar, beside the rakat: one place for it whether or not there
        # is a second screen, and it leaves the 7" to the posture picture alone.
        self.volume = VolumeBar(self.px(54), self.settings.volume, Fonts.english_family)
        self.volume.scale = self.s
        self.volume.setFixedWidth(self.px(300))
        self.volume.changed.connect(self.set_volume)
        right.addWidget(self.volume, 0, Qt.AlignmentFlag.AlignVCenter)
        right.addSpacing(self.px(12))
        self.dot = Dot(self.px(68))
        right.addWidget(self.dot)
        grid.addLayout(right, 0, 2)

        self.bar = bar
        lay.addWidget(bar)

        self.progress = ProgressLine(self.px(6))
        lay.addWidget(self.progress)

        self.slide = PrayerPage(self)
        self.slide.tapped.connect(self.on_tap)
        self.slide.tasbih.tapped.connect(self.tap_bead)
        # Nothing is shown when a prayer finishes. There used to be a hadith and a passage of
        # the Qur'an for the day here, and Harry had it taken out: the mat has a Qur'an section
        # and a hadith section of its own now, so a quotation nobody asked for at the end of a
        # prayer was a page to get past rather than a page to read.
        al = QtWidgets.QVBoxLayout(self.slide.ask)
        al.addStretch(1)
        al.setContentsMargins(self.px(80), 0, self.px(80), 0)
        q = QtWidgets.QLabel(self.t("player.leave_title"))
        q.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q.setWordWrap(True)
        al.addWidget(q)
        hint = QtWidgets.QLabel(self.t("player.leave_hint"))
        hint.setObjectName("askHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        al.addWidget(hint)
        al.addSpacing(self.px(28))
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        stay = no_focus(QtWidgets.QPushButton(self.t("player.stay")))
        stay.setObjectName("pill")
        stay.clicked.connect(self.slide.ask.hide)
        leave = no_focus(QtWidgets.QPushButton(self.t("player.leave")))
        leave.setObjectName("primary")
        leave.clicked.connect(self.stop)
        row.addWidget(stay)
        row.addSpacing(self.px(20))
        row.addWidget(leave)
        row.addStretch(1)
        al.addLayout(row)
        al.addStretch(1)

        lay.addWidget(self.slide, 1)
        self.update_status()
        return w

    def start(self, prayer: str, entry: UnitEntry) -> None:
        unit = self.content.units[entry.unit_id]
        session = PrayerSession(unit, self.content, self.school.step_overrides)
        self.session = session
        self.prayer = prayer
        self.kind = entry.kind
        if self.counts_dhikr:
            self.slide.tasbih.show_dhikr(self.content.dhikr)   # back to 33, 33, 33
        self.title = f"{self.t(f'prayer.{prayer}')}, {self.content.unit_label(entry, self.pack, self.english)}"
        self.title_label.setText(self.title)
        # Greyed out where there is nothing to hide: Arabic only, or a language the mat has no
        # translation file for. A switch that does nothing is worse than no switch, and this
        # is the one screen where the person can see for themselves that it is off.
        self.show_the_meaning_switch()
        self.bar.place_centre()
        self.stack.setCurrentWidget(self.player)
        self.slide.set_dim(self.veil_percent())
        if self.side is not None:
            self.side.show_prayer()
            self.side.set_dim(self.side_veil_percent())
        self.show_volume()
        unit_rakats = self.content.units[entry.unit_id].rakats
        translation = self.translation
        if translation is not None and translation.intention:
            # The intention is said in the language chosen for the translation.
            intention = translation.intend(unit_rakats, entry.kind, prayer)
        else:
            intention = self.t("intention", n=unit_rakats, kind=self.t(f"kind.{entry.kind}"),
                               prayer=self.t(f"prayer.{prayer}"))
        steps = list(session.pages)
        if self.counts_dhikr:
            # After the salam of a fardh prayer, before the beads: astaghfirullah three times,
            # then Ayat al-Kursi. Added here rather than in the units, since the same unit can
            # be fardh or sunnah.
            for step_id in AFTER_FARDH:
                if step_id in self.content.steps:
                    steps.append(SessionPage(len(steps), StepRef(step_id),
                                             self.content.steps[step_id], steps[-1].rakat))
        self.text_pages = build_pages(steps, self.content, self.pack, self.english,
                                      intention=intention, translation=translation)
        session.set_pages([SessionPage(i, p.ref, p.step, p.rakat) for i, p in enumerate(self.text_pages)])
        self.refresh()

    def stop(self) -> None:
        self.stop_audio()
        self.session = None
        if self.side is not None:
            self.side.show_idle()
        self.text_pages = []
        self.last_click = None
        self.slide.ask.hide()
        if self.prayer:
            self.open_prayer(self.prayer)
        else:
            self.go_home()

    def picture(self, name: str) -> Path:
        """Where a posture picture lives for the figure chosen in Settings. A set that is
        short of a picture falls back to the original, so a half-finished set still works."""
        figure = self.settings.figure
        if figure and figure != "boy":
            theirs = self.assets / "postures" / figure / Path(name).name
            if theirs.is_file():
                return theirs
        return self.assets / name

    def set_figure(self, figure: str) -> None:
        self.settings.figure = figure
        self.persist()
        self.posture_modes = load_posture_modes(self.assets, figure)
        self.images = PixmapCache()          # the old figure's pictures are no longer wanted
        for view in (self.slide.posture, getattr(self.side, "posture", None)):
            if view is not None:
                view.cache = self.images
                view.modes = self.posture_modes
        if self.playing:
            self.refresh()
        elif self.side is not None:
            self.side.show_idle()

    def show_the_meaning_switch(self) -> None:
        """Put the switch in the bar the way the settings leave it, and grey it out if there
        is no meaning to be had."""
        there = self.translation is not None
        self.meaning_switch.setEnabled(there)
        self.meaning_word.setEnabled(there)
        was = self.meaning_switch.blockSignals(True)
        self.meaning_switch.setChecked(bool(self.settings.meaning) and there)
        self.meaning_switch.blockSignals(was)

    def set_meaning(self, yes: bool) -> None:
        """The switch in the prayer bar: show the meaning beside the Arabic, or don't.

        Redrawn with show_page rather than refresh, which is the whole of this method that is
        not obvious. refresh also starts the page's recitation again, so flipping the switch
        halfway through Al-Fatiha would take the reciter back to the beginning of it. The red
        word comes back by itself: follow_audio sets it sixteen times a second.
        """
        self.stir()
        self.settings.meaning = bool(yes)
        self.persist()
        page = self.current_page
        if page is not None:
            self.slide.show_page(page, self.assets)

    @property
    def translation(self):
        """The meaning shown beside the Arabic during a prayer, or None for Arabic only.

        It used to be a setting of its own -- "Translation beside Arabic", a second dropdown
        next to the language one. Harry had it taken out: the mat asks which language you read
        in, and then asking again which language you would like the meaning in is the same
        question wearing a hat. One choice now drives the menus, the du'as, the sayings, the
        wu'du steps, the Qur'an and this.

        A PERSONAL translation of the chosen language wins over the public one. That is what
        the old dropdown was really for on this mat: the licensed Clear Qur'an text is keyed
        en-clear, not en, so with the dropdown gone it would have become unreachable on the
        machine of the one person who has a copy. Installing the file is now the whole of
        choosing it.
        """
        if self.settings.lang == ARABIC_ONLY:
            return None
        got = self.content.translations
        wanted = self.settings.lang
        personal = next((t for key, t in sorted(got.items())
                         if getattr(t, "personal", False) and key.split("-")[0] == wanted), None)
        return personal or got.get(wanted)

    @property
    def playing(self) -> bool:
        return self.session is not None and self.stack.currentWidget() is self.player

    @property
    def counts_dhikr(self) -> bool:
        """Only a fardh prayer ends on the beads; the sunnah, nafl and witr units do not."""
        return self.kind == "farz" and self.content.dhikr.usable

    @property
    def counting(self) -> bool:
        return self.playing and self.session.finished and self.counts_dhikr

    @property
    def current_page(self) -> TextPage | None:
        s = self.session
        if s is None or not self.text_pages:
            return None
        return self.text_pages[min(s.position, len(self.text_pages) - 1)]


    def refresh(self) -> None:
        s = self.session
        page = self.current_page
        if s is None or page is None:
            return
        self.rakat_label.setText(self.t("player.rakat", n=page.rakat, total=s.total_rakats))
        self.progress.set_value(1.0 if s.finished else s.progress)
        self.slide.show_page(page, self.assets)
        # A fardh prayer ends on the counted dhikr; everything else simply ends.
        counting = s.finished and self.counts_dhikr
        self.slide.done.setVisible(False)
        self.slide.tasbih.setVisible(counting)
        if counting:
            self.slide.tasbih.raise_()
        self.play_page(page)
        if counting:
            self.play_dhikr(self.content.dhikr.salam_key, self.slide.tasbih.salam)
        QtCore.QTimer.singleShot(0, self.preload)

    def audio_for(self, page: TextPage | None) -> Timings | None:
        """The recording for this page's recitation, if there is one and audio is switched on."""
        if page is None or not self.settings.recitation or not self.recitation.available:
            return None
        return self.timings.get(page.recitation)

    def play_page(self, page: TextPage) -> None:
        """Plays exactly the verses on this screen, then follows them word by word."""
        self.stop_audio()
        timings = self.audio_for(page)
        if timings is None or self.session is None or self.session.finished:
            return
        span = timings.span_for(page.first_segment, page.first_segment + len(page.arabic) - 1)
        # Said more than once (the X3 and X2 screens): play it that many times.
        if span is None or not self.recitation.play(timings.audio, span, times=page.repeat):
            return
        self.follow.start()

    def stop_audio(self) -> None:
        self.follow.stop()
        self.dhikr_follow.stop()
        self.dhikr_now, self.dhikr_then = None, None
        self.recitation.stop()
        self.slide.set_highlight(None)
        self.slide.tasbih.salam.set_highlight(None)
        self.slide.tasbih.tahlil.set_highlight(None)

    # The beads screen: the salam dua as it appears, a recording with every count, the tahlil
    # once the last bead is done.

    def play_dhikr(self, key: str, line=None, then=None) -> None:
        """Plays one of the dhikr recordings, lighting [line]'s words as they are said, and
        then does [then], if given, once it has finished."""
        self.stop_audio()
        timings = self.timings.get(key)
        if timings is None or not self.settings.recitation or not self.recitation.available:
            return
        span = Span(timings.segments[0].start, timings.segments[-1].end)
        if self.recitation.play(timings.audio, span):
            self.dhikr_now, self.dhikr_then = (key, line), then
            self.dhikr_follow.start()

    def follow_dhikr(self) -> None:
        if self.dhikr_now is None:
            self.dhikr_follow.stop()
            return
        key, line = self.dhikr_now
        position = self.recitation.position()
        if position is None and not self.recitation.busy:
            then = self.dhikr_then
            self.dhikr_follow.stop()
            self.dhikr_now, self.dhikr_then = None, None
            if line is not None:
                line.set_highlight(None)
            if then is not None:
                then()
            return
        if line is None:
            return
        # The words are split where the recording pauses but shown as one line, so count
        # through the parts to find the word's place in the line.
        timings, lit, before = self.timings[key], None, 0
        for part in range(len(timings.segments)):
            word = timings.word_at(part, position) if position is not None else None
            if word is not None:
                lit = (0, before + word)
                break
            before += len(timings.words[part])
        line.set_highlight(lit)

    def tap_bead(self) -> None:
        """A touch on the beads screen counts like the ring."""
        if self.counter_debouncer.accept(time.monotonic()):
            self.count_dhikr()

    def count_dhikr(self) -> None:
        """One count: the bead's number comes down and its recording plays. After the last
        of the ninety-nine, the tahlil is recited."""
        screen = self.slide.tasbih
        bead = screen.beads.current
        if not screen.press():
            return
        dhikr = self.content.dhikr
        then = None
        if screen.done:
            then = lambda: self.play_dhikr(dhikr.tahlil_key, screen.tahlil)  # noqa: E731
        self.play_dhikr(dhikr.beads[bead].key, None, then)

    def follow_audio(self) -> None:
        """Colours the word being recited, sixteen times a second."""
        page = self.current_page
        timings = self.audio_for(page)
        position = self.recitation.position()
        if timings is None or position is None:
            if timings is None or not self.recitation.busy:
                self.follow.stop()           # finished; between repeats, keep watching
            self.slide.set_highlight(None)
            return
        for line in range(len(page.arabic)):
            segment = page.first_segment + line
            word = timings.word_at(segment, position)
            if word is not None:
                self.slide.set_highlight((line, word))
                return
        self.slide.set_highlight(None)

    def preload(self) -> None:
        """Scale the next few posture pictures while the person is reading this page."""
        s = self.session
        if s is None:
            return
        for p in self.text_pages[s.position + 1:s.position + 4]:
            self.images.get(self.picture(p.posture_image), self.slide.posture.size())

    def move(self, action: str) -> None:
        """One click steps through the prayer.

        Leaving mid-prayer: two quick clicks ask "Leave the prayer?". One more quick click
        leaves; pausing and clicking carries on where you were. A ring worn on a finger can be
        double-pressed by accident, so a stray double never loses your place. Going back from
        the first page also leaves, which covers starting the wrong prayer.
        """
        now = time.monotonic()
        if not self.playing:
            return

        # On the beads a click counts one dhikr. Counting means many clicks in a row, so the
        # double-click-to-leave gesture is off here (Menu leaves) and the guard against a
        # button sending two keys per press is as short as it can be without letting one
        # through twice. Going back steps into the prayer again, as it does anywhere else.
        if self.counting and action == NEXT:
            self.last_click = None
            if self.counter_debouncer.accept(now):
                self.count_dhikr()
            return

        if not self.debouncer.accept(now):
            return

        # Only forward clicks count towards a double, so a quick "back then forward" is safe.
        double = action == NEXT and self.last_click is not None and now - self.last_click < DOUBLE_CLICK
        self.last_click = now if action == NEXT else None

        if self.slide.ask.isVisible():
            self.last_click = None
            if double:
                self.stop()
            else:
                self.slide.ask.hide()
            return

        if double:
            self.session.back()          # undo the step the first of the two clicks took
            self.refresh()
            self.ask_leave()
            return

        if action == BACK and self.session.position == 0 and not self.session.finished:
            self.stop()
            return

        changed = self.session.next() if action == NEXT else self.session.back()
        if changed:
            self.refresh()

    def ask_leave(self) -> None:
        # last_click stays set, so one more quick click confirms.
        self.slide.ask.setGeometry(self.slide.rect())
        self.slide.ask.show()
        self.slide.ask.raise_()

    def on_tap(self, action: str) -> None:
        self.move(action)

    def on_button(self, action: str) -> None:
        # Asleep, a press on the ring wakes the mat and does nothing else. It used to restart
        # the idle clock and fall through to move(), which returns at once on a sleeping mat --
        # so what a child pressing the ring on a dark mat actually got was nothing at all. The
        # ring is the thing that is in their hand; it should be able to turn the mat on, the
        # same as switching it on does in on_devices. The press that turns a thing on is not
        # also a press on what it turns on, which is the rule a phone follows.
        #
        # The return is a guard rather than something you could see today: move() leaves at
        # once when no prayer is running, and sleep ends the prayer on its way out, so there
        # is currently nothing below here for a waking press to fall into. Sabotaging the
        # return changes no test, which is how that was established rather than assumed. It
        # stays because the next screen wired into on_button would be the one it mattered for.
        if self.asleep:
            self.wake()
            return
        self.stir()
        if self.qibla_open:
            self.compass_screen.skip()             # a press always goes straight on
            return
        if self.timing_open:
            self.timing_press(action)
            return
        # The game is the screen the note above was waiting for: a press here is the whole of
        # how it is played, so it must be caught before move(), which only serves a prayer.
        playing = self.game_in_front
        if playing is not None:
            playing.press(action)
            return
        self.move(action)

    @property
    def timing_open(self) -> bool:
        return hasattr(self, "timing_screen") and self.stack.currentWidget() is self.timing_screen

    def timing_press(self, action: str) -> None:
        """The ring on the tap-along screen. Taps need to be quick, so only the short guard
        against a doubled key press applies."""
        if self.counter_debouncer.accept(time.monotonic()):
            self.timing_screen.press(action == NEXT)

    def on_devices(self, names: list) -> None:
        """The list of Bluetooth buttons the mat can see has changed.

        A NAME THAT WAS NOT THERE BEFORE WAKES THE MAT, which is Harry's: "when the mysalaah
        ring is turned [on] as it will look for the pi, could we wake it up this way also?"

        It can, and this is where: switching the ring on makes the Pi create an input device
        for it, buttons.py notices within two seconds and reports the new list, and arriving
        here is the mat being told the ring has come looking. Reaching for the ring is the
        same intention as reaching for the power button, and it saves crossing the room.

        A name APPEARING, not merely the list changing: a ring switched off, or carried out of
        range, must not wake the mat on its way out. And a ring that reconnects on its own in
        the night will light the mat up -- there is no telling that apart from somebody picking
        it up, and it costs a few minutes of screen before the idle clock puts it back to sleep.
        """
        came = [n for n in names if n not in self.device_names]
        self.device_names = list(names)
        self.update_status()
        if hasattr(self, "devices_label"):
            self.devices_label.setText(self.devices_text())
        if came and self.asleep:
            self.wake()

    def ring_names(self) -> list[str]:
        """The Bluetooth input devices that are a ring rather than a speaker.

        A Bluetooth speaker is an input device too: A/V Remote Control gives it play, pause and
        volume keys, so buttons.py sees it on the same bus as the ring and reports both. Until
        1.83 both names landed in one sentence under "MySalaah Ring", which is what Harry
        reported -- "when both Bluetooth devices are connected they are being displayed both on
        a single sentence". The speaker has a line of its own now, so it comes out of this one.

        Matched by name, because the name is what the two sources have in common: the kernel
        gives the input device a name and BlueZ gives the same device the same name. If no
        speaker is known -- nothing connected, or Settings not opened yet -- nothing is taken
        out, so the worst case is the old behaviour rather than a ring that has gone missing.
        """
        speaker = (getattr(self, "speaker_name", "") or "").strip()
        # Compared whole, not as a substring. An empty speaker name then matches nothing and
        # the list comes back untouched, which is what "no speaker known yet" has to do -- so
        # there is no guard above this for the empty case; it would be a line with no effect.
        # A substring test would do the opposite and drop everything, every name containing "".
        return [n for n in self.device_names if n.strip() != speaker]

    def update_status(self) -> None:
        # The main screen's circle asks "is there a button", and a speaker's media keys are a
        # working button, so it counts every input device. The one beside the ring in Settings
        # asks "is the ring here", so it counts only the ones that are not the speaker. The two
        # questions have different answers on a mat with a speaker and no ring, which is why
        # there are now two lists rather than one.
        any_button = bool(self.device_names)
        ring_here = bool(self.ring_names())
        said = self.t("button.connected") if any_button else self.t("button.disconnected")
        dot = getattr(self, "dot", None)
        if dot is not None:
            dot.set_color(MINT if any_button else BRICK)
            dot.setToolTip(said)
        ring = getattr(self, "ring_dot", None)
        if ring is not None:
            ring.set_color(MINT if ring_here else BRICK)
            ring.setToolTip(self.t("button.connected") if ring_here
                            else self.t("button.disconnected"))

    def eventFilter(self, obj, ev):
        # Anything a person does puts off going to sleep. Touches and presses both, because a
        # mat may have a touchscreen, a keyboard, a Bluetooth button, or all three.
        if ev.type() in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.KeyPress,
                         QtCore.QEvent.Type.TouchBegin):
            self.stir()
        # A tap or a press during the walk into an arch cuts it short, so what was touched is
        # seen at once. The event is not swallowed: the walk is only a picture over the top, and
        # the units underneath have been live since the moment the arch was tapped.
        if self.veil.running and ev.type() in (QtCore.QEvent.Type.MouseButtonPress,
                                               QtCore.QEvent.Type.KeyPress):
            self.veil.stop()
        if ev.type() == QtCore.QEvent.Type.KeyPress:
            key = ev.key()
            if ev.modifiers() & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Q:
                QtWidgets.QApplication.instance().quit()
                return True
            if self.qibla_open:
                stand_in = getattr(self.facing.compass, "turn", None)
                if stand_in and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    stand_in(5 if key == Qt.Key.Key_Right else -5)   # trying it without a chip
                    return True
                if key in NEXT_KEYS or key in BACK_KEYS or key == Qt.Key.Key_Escape:
                    if not ev.isAutoRepeat():
                        self.compass_screen.skip()
                    return True
            if self.timing_open and (key in NEXT_KEYS or key in BACK_KEYS or key == Qt.Key.Key_Escape):
                if not ev.isAutoRepeat():
                    if key == Qt.Key.Key_Escape:
                        self.timing_screen.leave()
                    else:
                        self.timing_press(NEXT if key in NEXT_KEYS else BACK)
                return True
            if self.game_open and (key in NEXT_KEYS or key in BACK_KEYS
                                   or key == Qt.Key.Key_Escape):
                if not ev.isAutoRepeat():
                    if key == Qt.Key.Key_Escape:
                        self.open_the_children_menu()
                    else:
                        self.game_in_front.press(NEXT if key in NEXT_KEYS else BACK)
                return True
            if self.playing:
                if ev.isAutoRepeat() and (key in NEXT_KEYS or key in BACK_KEYS):
                    return True
                if key in NEXT_KEYS:
                    self.move(NEXT)
                    return True
                if key in BACK_KEYS:
                    self.move(BACK)
                    return True
                if key == Qt.Key.Key_Escape:
                    self.stop()
                    return True
            elif key == Qt.Key.Key_Escape and self.stack.currentWidget() is not self.home:
                self.go_home()
                return True
        return super().eventFilter(obj, ev)

    # Settings

    def open_place(self) -> None:
        """Go to the postcode screen. Not while praying."""
        if self.playing or self.asleep:
            return
        self.stir()
        if getattr(self, "place_screen", None) is None:
            from .placescreen import PlaceScreen
            screen = PlaceScreen(self)
            screen.leave.clicked.connect(self.open_settings)
            screen.saved.connect(self.moved_to)
            self.place_screen = screen
            page = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            lay.addWidget(self.make_banner(gear=False, home=True))
            lay.addWidget(screen, 1)
            self.place_page = page
            self.stack.addWidget(page)
        self.place_screen.redraw()
        self.stack.setCurrentWidget(self.place_page)

    def moved_to(self, outward: str, latitude: float, longitude: float) -> None:
        """A postcode was kept. Everything that knows where the mat is has to be told: the
        times are worked out fresh, the strip is redrawn, and it is written down so the mat
        still knows where it is after a restart."""
        self.settings.place = outward
        self.settings.latitude = latitude
        self.settings.longitude = longitude
        self.settings.save()
        # The times cache keys on latitude and longitude, so moving invalidates it by itself.
        # Cleared anyway rather than relied on: a cache that decides for itself when it is stale
        # is exactly the thing that would show the old town's times for the rest of the day.
        self._times_key = None
        if getattr(self, "place_label", None) is not None:
            self.place_label.setText(outward)
        self.tick()
        self.open_settings()

    def open_wifi(self) -> None:
        """Go to the Wi-Fi screen. Not while praying: the big screen is busy and the touch is
        almost certainly a stray knee."""
        if self.playing or self.asleep:
            return
        self.stir()
        if getattr(self, "wifi_screen", None) is None:
            from .wifiscreen import WifiScreen
            screen = WifiScreen(self)
            screen.leave.clicked.connect(self.open_settings)
            self.wifi_screen = screen
            # The same strip as every other screen. Where you are, what is next, how loud it is
            # and the way home belong in the same place wherever you have got to -- a screen
            # without it reads as having left the app, which is the one thing this must not do.
            page = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            lay.addWidget(self.make_banner(gear=False, home=True))
            lay.addWidget(screen, 1)
            self.wifi_page = page
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.wifi_page)

    def open_bluetooth(self) -> None:
        """Go to the Bluetooth screen. Not while praying: the big screen is busy and the touch
        is almost certainly a stray knee."""
        if self.playing or self.asleep:
            return
        self.stir()
        if getattr(self, "bt_screen", None) is None:
            from .btscreen import BluetoothScreen
            screen = BluetoothScreen(self)
            screen.leave.clicked.connect(self.open_settings)
            # Connecting a speaker on that screen is the one thing that changes the circle on
            # this one, so it says so rather than leaving Settings to find out next time it
            # happens to be opened.
            screen.changed.connect(self.ask_the_speaker)
            self.bt_screen = screen
            page = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            lay.addWidget(self.make_banner(gear=False, home=True))
            lay.addWidget(screen, 1)
            self.bt_page = page
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.bt_page)

    def open_sources(self) -> None:
        """Who the words on this mat belong to, in full.

        Built fresh each time it is opened rather than once and kept. It is read off the files
        that are installed, and a mat can gain or lose a translation between one opening and
        the next -- a family putting their own Qur'an translation on it is exactly the case
        this page exists to be honest about.

        Its own row in Settings, not tucked inside an "about" box. A publisher asked how their
        work would be credited, and "two taps down a submenu" is a poor answer to give them.
        """
        if self.playing or self.asleep:
            return
        self.stir()
        from . import sources
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.make_banner(gear=False, home=True))

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("sourcesScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inside = QtWidgets.QWidget()
        rows = QtWidgets.QVBoxLayout(inside)
        rows.setContentsMargins(self.px(40), self.px(24), self.px(40), self.px(32))
        rows.setSpacing(self.px(6))

        head = QtWidgets.QLabel(self.t("sources.title"))
        head.setObjectName("settingHead")
        head.setWordWrap(True)
        rows.addWidget(head)
        said = QtWidgets.QLabel(self.t("sources.said"))
        said.setObjectName("settingHint")
        said.setWordWrap(True)
        rows.addWidget(said)
        rows.addSpacing(self.px(16))

        for credit in sources.everything(self.assets, self.quran):
            what = QtWidgets.QLabel(credit.what + (f"  —  {self.t('sources.this_mat')}"
                                                   if credit.private else ""))
            what.setObjectName("sourceWhat")
            what.setWordWrap(True)
            rows.addWidget(what)
            who = QtWidgets.QLabel(credit.line())
            who.setObjectName("sourceWho")
            who.setWordWrap(True)
            rows.addWidget(who)
            if credit.note:
                note = QtWidgets.QLabel(credit.note)
                note.setObjectName("sourceNote")
                note.setWordWrap(True)
                rows.addWidget(note)
            rows.addSpacing(self.px(12))

        rows.addSpacing(self.px(8))
        for key in ("sources.unaltered", "sources.not_endorsed"):
            small = QtWidgets.QLabel(self.t(key))
            small.setObjectName("sourceNote")
            small.setWordWrap(True)
            rows.addWidget(small)
            rows.addSpacing(self.px(6))
        rows.addStretch(1)
        scroll.setWidget(inside)
        lay.addWidget(scroll, 1)

        if getattr(self, "sources_page", None) is not None:
            self.stack.removeWidget(self.sources_page)
            self.sources_page.deleteLater()
        self.sources_page = page
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)

    def open_settings(self) -> None:
        self.refresh_attached()
        self.ask_the_radio()
        self.ask_the_speaker()
        self.stack.setCurrentWidget(self.settings_screen)

    # -- the Wi-Fi circle in Settings ------------------------------------------------------

    def ask_the_radio(self) -> None:
        """Find out where the wifi stands, for the circle beside the row.

        The circle was drawn and then never told anything, so it sat red on a mat that was
        online -- which is worse than no circle, because it is a confident wrong answer.

        nmcli can take a second or two, and a Settings screen that freezes while it opens would
        be its own bug, so the asking happens on a worker thread and the circle is painted when
        the answer arrives. Only one errand is out at a time: opening Settings twice quickly
        should not start two.
        """
        if getattr(self, "wifi_dot", None) is None or getattr(self, "wifi_errand", None):
            return
        from .network import Wifi
        from .wifiscreen import Errand
        if getattr(self, "wifi", None) is None:
            self.wifi = Wifi()
        wifi = self.wifi

        def look():
            # In this order, and no further than it needs to go: a mat with no wifi card is not
            # asked what it is joined to, and one joined to nothing is not sent looking up names.
            if not wifi.there():
                return None, False
            name = wifi.active()
            return name, bool(name) and wifi.online()

        errand = Errand(look)
        errand.done.connect(self.radio_answered)
        errand.finished.connect(self.radio_errand_finished)
        self.wifi_errand = errand
        errand.start()

    def radio_answered(self, answer) -> None:
        if isinstance(answer, Exception) or answer is None:
            answer = (None, False)
        self.show_wifi_state(*answer)

    def radio_errand_finished(self) -> None:
        # The reference goes before the thread does. Letting deleteLater run while this still
        # pointed at it is how the wifi screen used to die on its second scan.
        errand, self.wifi_errand = getattr(self, "wifi_errand", None), None
        if errand is not None:
            errand.deleteLater()

    def show_wifi_state(self, name: str | None, online: bool) -> None:
        """Green joined and reaching the world, amber joined and reaching nothing, red neither.

        Amber rather than green for the middle one because that is the state the wifi screen was
        built around: the mat sat associated to the router all evening and could not fetch a
        thing, and a green circle would have said everything was fine.
        """
        if getattr(self, "wifi_dot", None) is None:
            return
        if name is None:
            colour, said = BRICK, self.t("wifi.no_card")
            value = self.t("wifi.no_card")
        elif not name:
            colour, said = BRICK, self.t("wifi.offline")
            value = self.t("wifi.offline")
        elif not online:
            colour, said = AMBER, self.t("why.no_internet")
            # The network's name, because that is the "designated value" of this row, with the
            # amber circle beside it carrying the part the name cannot say. Writing the whole
            # sentence here instead would make this the only row whose value is a complaint.
            value = name
        else:
            colour, said = MINT, self.t("wifi.joined", name=name)
            value = name
        self.wifi_dot.set_color(colour)
        self.wifi_dot.setToolTip(said)
        if getattr(self, "wifi_value", None) is not None:
            self.wifi_value.setText(value)

    # -- the Bluetooth circle in Settings ---------------------------------------------------

    def ask_the_speaker(self) -> None:
        """Find out whether a speaker is connected, for the circle beside the row.

        The same shape as ask_the_radio and for the same reason: bluetoothctl takes a moment,
        and a Settings screen that froze while it opened would be its own bug. One errand at a
        time -- opening Settings twice quickly should not start two.
        """
        if getattr(self, "bt_dot", None) is None or getattr(self, "bt_errand", None):
            return
        from .bluetooth import Sound
        from .wifiscreen import Errand
        if getattr(self, "sound", None) is None:
            self.sound = Sound()
        sound = self.sound

        def look():
            # No further than it needs to go: a mat with no controller is not asked what it has
            # connected. False means "no Bluetooth on this mat", which is a different answer
            # from None, "nothing connected", and gets different words for the same red circle.
            if not sound.there():
                return False
            return sound.speaking()

        errand = Errand(look)
        errand.done.connect(self.speaker_answered)
        errand.finished.connect(self.speaker_errand_finished)
        self.bt_errand = errand
        errand.start()

    def speaker_answered(self, answer) -> None:
        self.show_bt_state(False if isinstance(answer, Exception) else answer)

    def speaker_errand_finished(self) -> None:
        errand, self.bt_errand = getattr(self, "bt_errand", None), None
        if errand is not None:
            errand.deleteLater()

    def show_bt_state(self, speaker) -> None:
        """Green when a speaker is connected, red when not.

        It asks what the connected thing IS, not how many there are. The ring is Bluetooth too
        and is nearly always connected; a circle that counted links would sit green on a mat
        with no speaker within a mile of it, which is a confident wrong answer.
        """
        if getattr(self, "bt_dot", None) is None:
            return
        if speaker is False:
            colour, said = BRICK, self.t("bt.no_adapter")
            value, named = self.t("bt.no_adapter"), ""
        elif speaker is None:
            colour, said = BRICK, self.t("bt.off")
            value, named = self.t("bt.off"), ""
        else:
            colour, said = MINT, self.t("bt.connected", name=speaker.shown)
            value, named = speaker.shown, speaker.name or ""
        self.bt_dot.set_color(colour)
        self.bt_dot.setToolTip(said)
        if getattr(self, "bt_value", None) is not None:
            self.bt_value.setText(value)
        # Which speaker is connected is also what decides whether the line above this one is
        # naming a ring or naming the speaker twice, so the ring's line is rewritten from the
        # same answer rather than waiting for the next time Settings happens to be opened.
        if named != getattr(self, "speaker_name", ""):
            self.speaker_name = named
            self.refresh_attached()

    def wrappable(self, label: "QtWidgets.QLabel") -> None:
        """Let a value in the two-column block wrap, and let it give way.

        Without this the block's label column gets squeezed to nothing by a long value. A plain
        QLabel asks for its whole text on one line as a MINIMUM, so "На этом коврике нет
        Bluetooth" demanded 420 points and left the four boxes 253 to share -- which is how
        "MySalaah Ring" came out as "ySalaah Rir" in Russian, and, it turns out, had been losing
        its first and last letters in French and Portuguese since 1.83 without anybody looking.
        A wrapping label asks for one word, so the boxes get what they need and a long value
        takes a second line instead.

        One line, not two. This also set the horizontal policy to Ignored, and the four pill
        buttons had their widths pinned to their own sizeHint besides -- three fixes for one
        fault, each of which cured it on its own. Measured at 1920x1200, 1920x1080, 1280x800
        and 1024x600: with only the wrapping, nothing is clipped at any of them; with the
        wrapping taken away, Russian loses 43 points and Spanish 13. So the wrapping is the fix
        and the other two were decoration -- and worse than decoration, because while any one
        of them stood, breaking the others changed nothing and no test could tell which was
        doing the work.
        """
        label.setWordWrap(True)

    def devices_text(self) -> str:
        """The value beside the ring. The speaker is not in it -- see ring_names."""
        names = self.ring_names()
        if not names:
            return self.t("settings.no_buttons")
        return ", ".join(names)

    def refresh_attached(self) -> None:
        """Rewrite the values in the two-column block from what the mat currently has.

        One place, so the four lines cannot disagree about what is connected: whichever of them
        has just been answered, all four are written from the same reading.
        """
        if getattr(self, "devices_label", None) is not None:
            self.devices_label.setText(self.devices_text())
        if getattr(self, "place_label", None) is not None:
            self.place_label.setText(self.settings.place or "")
        self.update_status()

    def pills(self, options: list[tuple[str, str]], current: str, on_pick) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(self.px(12))
        group = QtWidgets.QButtonGroup(row)
        for value, label in options:
            b = no_focus(QtWidgets.QPushButton(label))
            b.setObjectName("pill")
            b.setCheckable(True)
            b.setChecked(value == current)
            group.addButton(b)
            b.clicked.connect(lambda _=False, v=value: on_pick(v))
            row.addWidget(b)
        row.addStretch(1)
        return row

    def build_settings(self) -> QtWidgets.QWidget:
        """The same black strip as the Knowledge Corner, over white, two columns.

        The strip is built here for the same reason it is built there: where you are, what is
        next, how loud it is and the way home should be in the same place on every screen. No
        cog on it -- it would be a button back to the screen you are already on.
        """
        page = QtWidgets.QWidget()
        page_lay = QtWidgets.QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(0)
        page_lay.addWidget(self.make_banner(gear=False, home=True))

        w = QtWidgets.QWidget()
        w.setObjectName("settingsRoot")
        page_lay.addWidget(w, 1)
        outer = QtWidgets.QVBoxLayout(w)
        # Tighter at the top than it was: the banner above now carries the height the old head
        # row had, and on a 1920x1080 monitor the last section was six pixels below the fold.
        # The bottom margin is thin because the update button in the foot is now a block
        # rather than a strip, and a block brings its own breathing room. The 46 pixels it grew
        # by had to come from somewhere: a 1920x1080 monitor had 28 to spare and started
        # scrolling by 18, which the scroll test caught.
        # Nothing on the right and nothing at the bottom, so the Update button can sit hard
        # in the corner of the glass -- Harry: "to the bottom right completely". Everything
        # above it puts its own 48 back, which is why the margin moved rather than went.
        outer.setContentsMargins(self.px(48), self.px(12), 0, 0)
        outer.setSpacing(self.px(6))

        # No cog at the top any more. It went in 1.83 -- Harry: "remove settings icon ...
        # completely. this should free up space". It was a picture of the button you had just
        # pressed to get here, so it told you where you were and did nothing, and at the size
        # it had grown to it was spending 88 points of a page that was three pixels off
        # scrolling on a 1920x1080 monitor. The cog on the main screen's banner is the one that
        # matters and is untouched; this page's banner never had one, because it would be a
        # button back to the screen you are already on.

        # The two columns go in a scroller. On a 1920x1200 screen everything fits and no
        # scrollbar appears; on a shorter screen it scrolls rather than squeezing the rows of
        # choices until their lettering loses its bottom edge.
        self.settings_scroll = QtWidgets.QScrollArea()
        self.settings_scroll.setObjectName("settingsScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.viewport().setAutoFillBackground(False)
        body = QtWidgets.QWidget()
        body.setObjectName("settingsRoot")           # so it takes the same background
        columns = QtWidgets.QHBoxLayout(body)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(self.px(64))
        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        left.setSpacing(self.px(4))
        right.setSpacing(self.px(4))
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        self.settings_scroll.setWidget(body)
        scrolled = QtWidgets.QHBoxLayout()
        scrolled.setContentsMargins(0, 0, self.px(48), 0)
        scrolled.addWidget(self.settings_scroll, 1)
        outer.addLayout(scrolled, 1)

        def section(column: QtWidgets.QVBoxLayout, key: str, hint: str = "") -> None:
            # The air above a heading, 14 points until 1.78 and 6 since. The cog at the top of
            # this page doubled in size at Harry's asking and took 44 points of screen with
            # it, which on a 1920x1080 monitor is the difference between this page fitting and
            # this page scrolling -- and it was already within 28 points of scrolling before.
            # Six gaps give the 48 back. Nothing is squeezed by it: the headings, the hints and
            # the rows of choices are all the size they were, standing a little closer.
            column.addSpacing(self.px(6))
            heading = QtWidgets.QLabel(self.t(key))
            heading.setObjectName("settingHead")
            column.addWidget(heading)
            if hint:
                note = QtWidgets.QLabel(hint)
                note.setObjectName("settingHint")
                note.setWordWrap(True)
                column.addWidget(note)

        # Left column. No prayer times and no place here: the main screen carries both across
        # its banner, so this was saying it twice and spending the top third of the column on
        # it. Where to set the location is in the README instead.
        #
        # The school picker was the first thing in this column until 1.83. Harry: "remove ...
        # school and hanifi text option completely". There is one school on the mat --
        # assets/content/schools/hanafi.json and nothing else -- so it was a heading reading
        # "School" over a single filled circle reading "Hanafi", which asks a question with one
        # answer. The setting itself is untouched and still decides the prayer times (see the
        # `school` property); only the row that could not change it has gone. If a second school
        # is ever added, this is where its picker goes back, and school.<id> is the wording.

        # One language picker, and no second one under it. "Translation beside Arabic" used to
        # live here and it has gone: it asked the same question as this row, so the mat could
        # sit there with Urdu menus and an English meaning under the Arabic and both settings
        # would have been obeyed. This row now decides every word on the mat.
        section(left, "settings.language")
        self.language_picker = self.dropdown(self.language_choices(),
                                             self.settings.lang, self.set_lang)
        left.addWidget(self.language_picker)

        if len(self.content.figures) > 1:
            section(left, "settings.figure")
            left.addLayout(self.circles(
                [(name, self.t(f"figure.{name}")) for name in self.content.figures],
                self.settings.figure, self.set_figure, across=True))

        section(left, "settings.font", self.t("settings.font_hint"))
        self.font_picker = self.dropdown(
            [(key, self.t(f"font.{key}")) for key in FONTS if key in Fonts.families],
            self.settings.arabic_font, self.set_font)
        left.addWidget(self.font_picker)

        # A dropdown, like the two above it: the three choices are wordy enough that as a row of
        # circles they took a quarter of the column, and the wording made it hard to see at a
        # glance that light and dark were choices at all rather than a note about the automatic one.
        section(left, "settings.theme")
        self.theme_picker = self.dropdown(
            [(mode, self.t(f"settings.theme_{mode}")) for mode in theme.MODES],
            self.settings.theme if self.settings.theme in theme.MODES else "auto", self.set_theme)
        left.addWidget(self.theme_picker)

        section(left, "settings.cursor")
        left.addLayout(self.switch_row(self.settings.cursor,
                                       lambda yes: self.set_cursor("1" if yes else "0"),
                                       "cursorSwitch"))

        # Who the words on the mat belong to. Its own row, named plainly, and NOT inside an
        # "about" box: the publishers whose translations these are asked how they would be
        # credited, and a credit that has to be hunted for is a poor answer to give them.
        #
        # In this column rather than in the block of things the mat is attached to, for two
        # reasons. It is not a thing with a state -- no circle, no value, it is a way in. And
        # the block was already the longer of the two columns: adding a fifth row to it put the
        # right 141 points past the left, which is the imbalance that stops the whole page
        # being set larger. Here it pays for itself; measured, the two now end 9 points apart.
        section(left, "settings.sources")
        self.sources_button = no_focus(QtWidgets.QPushButton(self.t("sources.title")))
        self.sources_button.setObjectName("pill")
        self.sources_button.clicked.connect(self.open_sources)
        left.addWidget(self.sources_button)
        left.addStretch(1)

        # Right column
        if self.timings:
            # No explanation under it since 1.83. Harry: "remove the text under 'Play the
            # recitation' explaining, not required." It was three wrapped lines describing what
            # a switch called "Play the recitation" does, which is the kind of note that is only
            # read once and is in the way every time after.
            section(right, "settings.recitation")
            right.addLayout(self.switch_row(
                self.settings.recitation,
                lambda yes: self.set_recitation("1" if yes else "0"), "recitationSwitch"))
            if not self.recitation.available:
                right.addWidget(self.value_label(self.t("settings.no_player")))
            # No button for tapping the timings in: that is a job for whoever is building the
            # mat, not for whoever is praying on it. Start with --tap-timings to get at it.

        # Directly under the recitation: the two settings that decide whether the mat makes a
        # sound now sit together, instead of one in each column with the page between them.
        section(right, "settings.azaan")
        right.addLayout(self.switch_row(self.settings.azaan,
                                        lambda yes: self.set_azaan("1" if yes else "0"),
                                        "azaanSwitch"))

        # No explanation when it works: a brightness slider explains itself. The words are for
        # the case where it cannot do what it appears to, which is the one that needs saying.
        section(right, "settings.brightness",
                "" if self.backlight.available else self.t("settings.brightness_veil"))
        right.addLayout(self.brightness_slider())

        if QIBLA:
            self.qibla_settings(right, section)

        # What the mat is attached to, in two columns: what it is on the left, what it has got
        # on the right. Harry: "i want 2 columns, on left side we will have MySalaah Ring,
        # Bluetooth, Wi-Fi, Location, on their respective right will their chosen / designated
        # value. keep the same box and text look of W-Fi button. retain the filled circles to
        # the left."
        #
        # A grid rather than four rows of boxes, because the point of the two columns is that
        # the values line up with each other -- in four separate rows each value started
        # wherever the label before it happened to end, which is the mess this replaces. The
        # four labels wear the Wi-Fi button's look because that is what Harry asked for and
        # because all four now do the same thing: they open the screen that sets that setting.
        #
        # THE RING AND BLUETOOTH BOTH OPEN THE BLUETOOTH SCREEN. The ring IS a Bluetooth
        # device, and that screen is where it is listed and where it would be reconnected, so
        # a label that looks pressable and leads nowhere seemed the worse of the two. Say the
        # word and the ring's label becomes an unpressable box in the same style.
        # More air above this than between two ordinary sections. Every other block on the page
        # is a heading with its control under it; this one has no heading, so without a gap of
        # its own the first row reads as though it belonged to the setting above it -- which on
        # the first render was "Mouse pointer", with a green circle apparently answering it.
        right.addSpacing(self.px(24))
        self.attached = QtWidgets.QGridLayout()
        self.attached.setContentsMargins(0, 0, 0, 0)
        self.attached.setHorizontalSpacing(self.px(14))
        self.attached.setVerticalSpacing(self.px(6))
        # The value column takes the slack, so the labels stay in a column of their own width
        # instead of being pushed about by however long a network name happens to be.
        self.attached.setColumnStretch(2, 1)

        # The ring. The circle is the same green-or-red one the main screen carries in its bar,
        # so whether it is connected is read at a glance rather than off the words beside it.
        self.ring_dot = Dot(self.px(28))
        self.ring_button = no_focus(QtWidgets.QPushButton(self.t("settings.buttons")))
        self.ring_button.setObjectName("pill")
        self.ring_button.clicked.connect(self.open_bluetooth)
        self.attached.addWidget(self.ring_dot, 0, 0, Qt.AlignmentFlag.AlignVCenter)
        self.attached.addWidget(self.ring_button, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        self.devices_label = QtWidgets.QLabel(self.devices_text())
        self.devices_label.setObjectName("settingValue")
        self.wrappable(self.devices_label)
        self.attached.addWidget(self.devices_label, 0, 2, Qt.AlignmentFlag.AlignVCenter)
        self.attached.setRowMinimumHeight(0, self.ring_button.sizeHint().height())

        # Bluetooth. The circle answers "is there a speaker", not "is Bluetooth connected to
        # anything" -- the ring is on this adapter too and is nearly always connected.
        self.bt_dot = Dot(self.px(28))
        self.bt_button = no_focus(QtWidgets.QPushButton(self.t("bt.row")))
        self.bt_button.setObjectName("pill")
        self.bt_button.clicked.connect(self.open_bluetooth)
        self.attached.addWidget(self.bt_dot, 1, 0, Qt.AlignmentFlag.AlignVCenter)
        self.attached.addWidget(self.bt_button, 1, 1, Qt.AlignmentFlag.AlignVCenter)
        self.bt_value = QtWidgets.QLabel("")
        self.bt_value.setObjectName("settingValue")
        self.wrappable(self.bt_value)
        self.attached.addWidget(self.bt_value, 1, 2, Qt.AlignmentFlag.AlignVCenter)
        self.attached.setRowMinimumHeight(1, self.bt_button.sizeHint().height())

        # Wi-Fi. A row here rather than a box that appears over whatever is on the mat: this
        # screen shows prayer times in a room, and a dialog seizing it mid-prayer would be
        # worse than no wifi. The only thing that offers it unprompted is the line where
        # something actually failed for want of a network.
        self.wifi_dot = Dot(self.px(28))
        self.wifi_button = no_focus(QtWidgets.QPushButton(self.t("wifi.row")))
        self.wifi_button.setObjectName("pill")
        self.wifi_button.clicked.connect(self.open_wifi)
        self.attached.addWidget(self.wifi_dot, 2, 0, Qt.AlignmentFlag.AlignVCenter)
        self.attached.addWidget(self.wifi_button, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        self.wifi_value = QtWidgets.QLabel("")
        self.wifi_value.setObjectName("settingValue")
        self.wrappable(self.wifi_value)
        self.attached.addWidget(self.wifi_value, 2, 2, Qt.AlignmentFlag.AlignVCenter)
        self.attached.setRowMinimumHeight(2, self.wifi_button.sizeHint().height())

        # Where the mat is. Until this existed the coordinates were whatever was in the settings
        # file and there was no way to change them -- carry the mat anywhere and it kept showing
        # Bury's times with nothing to say so. No circle: unlike the three above it, a location
        # is not a thing that is either connected or not, and an always-green circle would be
        # saying nothing in the shape of an answer.
        self.place_button = no_focus(QtWidgets.QPushButton(self.t("place.row")))
        self.place_button.setObjectName("pill")
        self.place_button.clicked.connect(self.open_place)
        self.attached.addWidget(self.place_button, 3, 1, Qt.AlignmentFlag.AlignVCenter)
        self.place_label = QtWidgets.QLabel(self.settings.place or "")
        self.place_label.setObjectName("settingValue")
        self.wrappable(self.place_label)
        self.attached.addWidget(self.place_label, 3, 2, Qt.AlignmentFlag.AlignVCenter)
        self.attached.setRowMinimumHeight(3, self.place_button.sizeHint().height())

        right.addLayout(self.attached)
        right.addStretch(1)

        # No way out to the desktop: the mat is the product, and there is nothing behind it to
        # go to. Ctrl+Q still quits, for working on it (see eventFilter).
        foot = QtWidgets.QHBoxLayout()
        # The version keeps its breathing room; the button has none on the two sides that
        # face the corner, which is what puts it there. The two pixels above are all the
        # taller button left: a 1920x1080 screen had 28 pixels spare before it scrolls, and
        # a block this size spends most of them.
        foot.setContentsMargins(0, self.px(2), 0, 0)
        version = QtWidgets.QLabel(self.t("settings.version", number=__version__))
        version.setObjectName("settingValue")
        foot.addWidget(version)
        # The version on the left, the button hard against the right-hand edge: the two things
        # in the foot are no longer a pair in the corner with the rest of the row empty.
        foot.addStretch(1)
        self.update_button = no_focus(QtWidgets.QPushButton(self.t("update.check")))
        self.update_button.setObjectName("updateButton")
        self.update_button.clicked.connect(self.check_for_update)
        foot.addWidget(self.update_button)
        outer.addLayout(foot)
        self.update_status()      # so the circle is the right colour the first time it is seen
        return page

    # Updating

    @property
    def root(self) -> Path:
        """The folder holding salaah/ and assets/ -- the one run.sh sits in, and the one an
        update replaces the contents of."""
        return self.assets.resolve().parent

    def update_url(self) -> str:
        from .update import DEFAULT_URL
        return self.settings.update_url or DEFAULT_URL

    def say(self, message: str, title: str = "update.title") -> None:
        """Put a message in front of the person, in a box they cannot overlook.

        The whole business of updating happens on this thread, so nothing repaints while the
        network is being waited on. Every message therefore has to be painted BEFORE the slow
        thing starts, which is what settle() ends with.

        [title] is a pack key, because this box is no longer only for updates: changing the
        language restarts the app, and announcing that under the heading "Update" would tell
        the person something that is not true.
        """
        if self.notice is None:
            self.notice = Notice(self, self.px, self.t(title))
            self.notice.finished.connect(self.notice_closed)
        self.notice.say(message)

    def notice_closed(self, *_) -> None:
        self.notice = None
        self.update_button.setEnabled(True)

    def done_saying(self, message: str) -> None:
        """The last word on this attempt: a message and a way out."""
        if self.notice is None:
            return self.say(message)
        self.notice.finish(message, self.t("update.close"))

    def check_for_update(self) -> None:
        """Ask what is being offered, and say so. Nothing is installed without being asked."""
        from . import update as updater
        if self.playing:
            return self.done_saying(self.t("update.not_now"))
        self.update_button.setEnabled(False)
        self.say(self.t("update.looking"))
        try:
            release = updater.check(self.update_url())
        except updater.Refused as why:
            return self.done_saying(self.t("update.failed", why=str(why)))
        if not updater.newer(release.version, __version__):
            return self.done_saying(self.t("update.current", number=__version__))
        self.offer(release)

    def offer(self, release) -> None:
        """A newer version exists. Say which, and what it changes, and let it be refused."""
        if self.notice is None:
            self.say("")
        self.notice.ask(self.t("update.found", number=release.version),
                        self.t("update.now"), self.t("update.later"), release.notes)
        # Taken off first, or a second press would install twice while the first is still going.
        self.notice.accepted.connect(lambda: self.apply_update(release))

    def apply_update(self, release) -> None:
        from .update import Refused, install
        # ask() closed the dialog when it was accepted, so a fresh one carries the progress.
        self.notice = None
        self.say(self.t("update.downloading", number=release.version))
        try:
            install(release, self.root)
        except Refused as why:
            # Nothing has been changed: install() only swaps once everything has checked out.
            return self.done_saying(self.t("update.failed", why=str(why)))
        self.say(self.t("update.restarting"))
        QtCore.QTimer.singleShot(1200, self.restart)

    def restart(self) -> None:
        """Stand down with the agreed code, so run.sh starts the new version -- and puts this
        one back if it will not go.

        Not quit(). A clean exit is what closing the app looks like, and run.sh rightly stops
        when that happens; an update that quit cleanly left the mat sitting on the desktop.
        """
        from .update import RESTART
        QtWidgets.QApplication.instance().exit(RESTART)

    def start_again(self) -> None:
        """Start the app over from scratch, in place, after a setting the screens are built from.

        WHY NOT rebuild(). It tears down every screen and builds new ones, and it does not get
        the memory back: measured on this machine, each language change cost about twenty
        megabytes that never returned -- 147 MB after the first build, 243 after six changes,
        347 after twelve. On a Pi with the rest of the mat running, that ends with the kernel
        killing the app, which looks from the prayer mat like the screen going out and the
        desktop coming up. Whatever is holding those screens open, a process that starts again
        does not have it, and chasing the last reference around a dozen widgets would leave the
        same trap set for the next screen that gets added.

        WHY NOT exit(RESTART). That code means one thing: an update has been installed. run.sh
        counts those, and the counting is not safe to borrow:

          * a version still on trial that exits before it has settled is taken for a version
            that died, and the guard puts the PREVIOUS one back. Settling takes ten seconds,
            so changing the language just after an update would have rolled the update back;
          * a sixth restart in one run is treated as a failure on purpose, to stop a loop. Six
            language changes in a sitting is a child playing with a dropdown, not a fault, and
            it would have reverted the version.

        And run.sh is deliberately never replaced by an update -- it is the guard -- so a new
        exit code could not have reached a mat that is already out there anyway.

        os.execv replaces this process with a new one. run.sh sees no exit at all: its loop is
        never re-entered, so nothing is counted, nothing is rolled back, and there is no cap on
        how often this can happen. The trial goes on being timed by the new process, which
        settles it as usual.
        """
        import os
        # Let go of the speaker before the process is replaced. execv keeps whatever file
        # handles were not marked close-on-exec, and a sound card still held open by a process
        # that no longer exists is the kind of thing that only shows up on the mat.
        self.hush_passages()
        self.stop_audio()
        # The settings file is what the new process reads to find out what changed, so it has
        # to be on the disk before this process stops existing. persist() has already been
        # called by the setter; this is the flush of the streams, which execv does not do.
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.executable, [sys.executable, "-m", "salaah"] + sys.argv[1:])

    def settled(self) -> None:
        """Called once this version has run long enough to be trusted, so the guard stops
        watching it. Until this happens a restart puts the previous version back."""
        from .update import Installer
        try:
            Installer(self.root).settled()
        except OSError:
            pass

    def qibla_settings(self, right, section) -> None:
        """The Qibla rows in Settings, while the compass is switched on."""
        section(right, "settings.qibla")
        compass = self.facing.compass
        right.addWidget(self.value_label(self.t(
            "settings.qibla_bearing", degrees=f"{self.qibla_bearing():.1f}",
            compass=getattr(compass, "name", "none") if self.facing.fitted
            else self.t("settings.no_compass"))))
        right.addLayout(self.circles([("1", self.t("settings.qibla_at_start")),
                                      ("0", self.t("settings.qibla_not_at_start"))],
                                     "1" if self.settings.qibla_start else "0", self.set_qibla_start))
        # No "Show the Qibla" button: with a 7" screen the compass is already on it, Settings
        # and all, so the button only duplicated what was in front of you.

    def build_timing(self) -> QtWidgets.QWidget:
        words = TextBox(Fonts.arabic(self.settings.arabic_font), MIN_ARABIC_PX, MAX_ARABIC_PX,
                        rtl=True, weight=700, slack=0.98, by_word=True, gap=0.18)
        words.scale = self.s
        return TimingScreen(self, words)

    def open_timing(self) -> None:
        """Tap along with the ring to set the word timings: Settings, under the recitation."""
        if not self.timings:
            return
        self.timing_screen.open(0)
        self.stack.setCurrentWidget(self.timing_screen)

    def value_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("settingValue")
        label.setWordWrap(True)
        return label

    def dropdown(self, options: list[tuple[str, str]], current: str,
                 on_pick) -> QtWidgets.QComboBox:
        """A picker for a list that could grow long: the translations, where circles would
        take over the page as languages are added."""
        box = no_focus(QtWidgets.QComboBox())
        box.setObjectName("picker")
        for value, label in options:
            box.addItem(label, value)
            # Every language is listed under its own name, so one list holds Latin, Chinese,
            # Devanagari and Arabic at once and no single face covers it. Each row is given the
            # face its own letters need, or the ones the Pi has not got come out as boxes.
            face = QtGui.QFont(Fonts.for_text(label))
            face.setPixelSize(self.px(26))
            box.setItemData(box.count() - 1, face, Qt.ItemDataRole.FontRole)
        box.setCurrentIndex(max(0, [v for v, _ in options].index(current)
                                if current in [v for v, _ in options] else 0))
        box.activated.connect(lambda i: on_pick(box.itemData(i)))

        def follow_choice(index: int) -> None:
            """The shut box shows one row, in its own face too."""
            shown = QtGui.QFont(Fonts.for_text(box.itemText(index)))
            shown.setPixelSize(self.px(26))
            box.setFont(shown)

        box.currentIndexChanged.connect(follow_choice)
        follow_choice(box.currentIndex())
        box.setMinimumWidth(self.px(420))
        return box

    def volume_slider(self, dark: bool = False) -> QtWidgets.QHBoxLayout:
        """How loud the recitation is, wherever it is being listened to.

        All the way down is silence, which is the same thing the prayer screen's bar means, so
        the two agree: the app has one notion of volume and every control on screen shows it.
        Every slider built here is kept in a list and moved together, so turning it down in the
        Qur'an does not leave the banner claiming it is still loud.
        """
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(self.px(8))
        bar = no_focus(QtWidgets.QSlider(Qt.Orientation.Horizontal))
        bar.setObjectName("volumeOnDark" if dark else "volume")
        bar.setRange(0, 100)
        bar.setSingleStep(5)
        bar.setPageStep(10)
        bar.setValue(self.settings.volume if self.settings.recitation else 0)
        # 240, not the 320 it was. The strip has to hold a pin, a place, five prayer times,
        # this, a Main screen button and a cog, and at 1920 that came to 54 pixels more than
        # there is in Spanish. Something had to give and for one version it was the spacing
        # between the times, which Harry saw at once: "looks like one long sentence". The
        # slider is a control and still an easy one to hit at 240; the times are the thing
        # people read, so the slider is what gives.
        bar.setFixedWidth(self.px(240))
        bar.setMinimumHeight(self.px(52))       # a finger, not a mouse
        # The figure beside it has gone: where the handle sits says how loud it is, and the
        # number was the only thing on the strip nobody was reading. It is still built, hidden,
        # because everything that keeps the sliders in step is written in terms of the pair.
        read = QtWidgets.QLabel(f"{bar.value()}%")
        read.setObjectName("volumeReadOnDark" if dark else "volumeRead")
        read.hide()
        bar.valueChanged.connect(lambda v: self.volume_moved(v))
        self.volume_bars.append((bar, read))
        row.addWidget(bar)
        row.addWidget(read)
        return row

    def volume_moved(self, volume: int) -> None:
        """One slider moved: tell the app, then bring the others with it."""
        self.set_volume(volume)
        self.show_volume()

    def switch_row(self, on: bool, on_pick, name: str = "") -> QtWidgets.QHBoxLayout:
        """One switch and the word for where it is, instead of two circles to choose between.

        The word is kept because the mat is read from a few feet away and a knob on its own is
        a small thing to judge at that distance; it is not a second control, and pressing it
        does nothing.
        """
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(self.px(14))
        knob = Switch(on, scale=self.s)
        if name:
            knob.setObjectName(name)
        said = QtWidgets.QLabel(self.t("settings.on" if on else "settings.off"))
        said.setObjectName("settingValue")
        said.setMinimumWidth(self.px(90))     # so the row does not shuffle as it is switched

        def flipped(yes: bool) -> None:
            said.setText(self.t("settings.on" if yes else "settings.off"))
            on_pick(yes)
        knob.toggled.connect(flipped)
        row.addWidget(knob)
        row.addWidget(said)
        row.addStretch(1)
        return row

    def circles(self, options: list[tuple[str, str]], current: str, on_pick,
                across: bool = False, per_row: int = 0) -> QtWidgets.QLayout:
        """One circle per choice, filled in solid when it is the one in use. Short choices
        (percentages, pixels) sit side by side to save room; [per_row] wraps a long row onto
        as many lines as it needs."""
        if not across:
            rows = QtWidgets.QVBoxLayout()
            rows.setSpacing(self.px(2))
        else:
            rows = QtWidgets.QGridLayout()
            rows.setHorizontalSpacing(self.px(28))
            rows.setVerticalSpacing(self.px(2))
            rows.setContentsMargins(0, 0, 0, 0)
        width = per_row or len(options)
        group = QtWidgets.QButtonGroup(rows)
        for n, (value, label) in enumerate(options):
            button = no_focus(QtWidgets.QRadioButton(label))
            button.setObjectName("choice")
            button.setChecked(value == current)
            group.addButton(button)
            button.clicked.connect(lambda _=False, v=value: on_pick(v))
            if across:
                rows.addWidget(button, n // width, n % width)
            else:
                rows.addWidget(button)
        if across:
            rows.setColumnStretch(width, 1)
        return rows


    def set_qibla_start(self, v: str) -> None:
        self.settings.qibla_start = v == "1"
        self.persist()

    def brightness_slider(self) -> QtWidgets.QHBoxLayout:
        """One bar rather than five buttons. Brightness is a continuous thing, and a monitor
        that takes real instruction can sit anywhere on the range rather than at five stops."""
        from .backlight import LEAST
        row = QtWidgets.QHBoxLayout()
        bar = no_focus(QtWidgets.QSlider(Qt.Orientation.Horizontal))
        bar.setObjectName("brightness")
        bar.setRange(LEAST, 100)          # never to nothing: a dark mat cannot be turned back up
        bar.setSingleStep(5)
        bar.setPageStep(10)
        bar.setValue(max(LEAST, min(100, self.settings.brightness)))
        bar.setMinimumHeight(self.px(56))     # a finger, not a mouse
        reading = QtWidgets.QLabel(f"{bar.value()}%")
        reading.setObjectName("settingValue")
        reading.setMinimumWidth(self.px(90))   # so the row does not twitch as the number changes
        bar.valueChanged.connect(lambda v: (reading.setText(f"{v}%"), self.set_brightness(v)))
        self.brightness_bar = bar
        row.addWidget(bar, 1)
        row.addWidget(reading)
        return row

    def set_azaan(self, v: str) -> None:
        self.settings.azaan = v == "1"
        self.persist()
        if not self.settings.azaan and self.call_box is not None:
            self.call_box.accept()       # turned off while it was calling: stop calling

    def set_brightness(self, value: int) -> None:
        self.settings.brightness = int(value)
        self.persist()
        self.apply_brightness()

    def veil_percent(self) -> int:
        """How dark to draw the veil on the main screen. Nothing at all when the monitor is
        doing it for real -- veiling a backlight that has already been turned down would darken
        it twice."""
        return 0 if self.backlight.available else self.side_veil_percent()

    def side_veil_percent(self) -> int:
        """How dark to draw the veil on the posture screen.

        Always in software, because that panel has no brightness of its own: it answers on the
        bus with its EDID and refuses every brightness command, even slowed right down. Judging
        this once for the whole mat was wrong -- it left the little screen glaring at full
        power beside a monitor that had properly dimmed.

        The veil is deliberately gentler than the number suggests. Matching it one for one is
        right on paper and wrong in the room: a monitor set to 40 is still fairly bright,
        because makers rarely map that scale to the light it actually emits, while a film 60%
        black is exactly 60% darker. Easing off brings the two screens back together.
        """
        return min(VEIL_MOST, int((100 - self.settings.brightness) * VEIL_STRENGTH))

    def apply_brightness(self) -> None:
        if self.backlight.available:
            self.backlight.set(self.settings.brightness)
        self.slide.set_dim(self.veil_percent())
        if self.side is not None:
            self.side.set_dim(self.side_veil_percent())

    def set_cursor(self, v: str) -> None:
        self.settings.cursor = v == "1"
        self.persist()
        self.apply_cursor()

    def apply_cursor(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        while app.overrideCursor() is not None:
            app.restoreOverrideCursor()
        # A pointing finger when it is shown, not an arrow: everything on the mat is touched
        # rather than clicked, so a mouse stands in for a finger and should look like one.
        app.setOverrideCursor(Qt.CursorShape.PointingHandCursor if self.settings.cursor
                              else Qt.CursorShape.BlankCursor)

    def note_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("note")
        label.setWordWrap(True)
        return label

    def set_recitation(self, value: str) -> None:
        self.settings.recitation = value == "1"
        self.persist()
        if not self.settings.recitation:
            self.stop_audio()
        self.show_volume()

    def set_volume(self, volume: int) -> None:
        """The bar in the top row, which is the volume and the on-off switch in one: all the
        way down is silence. Turning it up takes effect on the next screen rather than straight
        away, so a verse being recited is not cut off part way through."""
        volume = clamp_volume(volume)
        self.settings.recitation = volume > 0
        if volume > 0:
            self.settings.volume = volume          # silence keeps the old level to come back to
            self.recitation.set_volume(volume)
        else:
            self.stop_audio()
        self.persist()

    def show_volume(self) -> None:
        """The bar reads silent whenever the recitation is switched off, so it never shows a
        level with nothing playing."""
        loud = self.settings.volume if self.settings.recitation else 0
        self.volume.set_volume(loud)
        for bar, read in getattr(self, "volume_bars", []):
            if bar.value() != loud:
                was = bar.blockSignals(True)     # moving it must not look like being dragged
                bar.setValue(loud)
                bar.blockSignals(was)
            read.setText(f"{loud}%")

    def set_font(self, key: str) -> None:
        self.settings.arabic_font = key
        self.persist()
        self.slide.arabic.set_family(Fonts.arabic(key))
        self.slide.parallel.set_family(Fonts.arabic(key))
        self.setStyleSheet(self.stylesheet())   # the banner name uses it too

    # Both of these start the app over rather than rebuilding the screens in place. See
    # start_again() for why: rebuild() does not give the memory back, and enough changes in one
    # sitting ended with the mat on the desktop. The setting is written to the disk first, so
    # the new process comes up with the choice already made.

    # set_school went with the picker in 1.83. Nothing called it once the row was gone, and the
    # mat has one school. `settings.school` is still read -- see the `school` property -- so a
    # settings.json naming another one would still be obeyed if the file for it existed, which
    # is why the setting stayed and only the control that could not change it went.

    def language_choices(self) -> list[tuple[str, str]]:
        """The rows of the language picker: the packs, and Arabic on the end.

        Arabic last rather than in its alphabetical place. The six above it are the languages
        the mat is written in; this one is the mat with the writing taken away, which is a
        different kind of choice and reads better at the bottom of the list than buried
        between Chinese and English.
        """
        rows = [(p.lang, p.native_name)
                for p in sorted(self.packs.values(), key=lambda x: x.lang)
                if p.lang != ARABIC_ONLY]
        return rows + [(ARABIC_ONLY, self.t("settings.arabic_only"))]

    def set_lang(self, lang: str) -> None:
        if lang == self.settings.lang:
            return
        self.settings.lang = lang
        self.persist()
        # Said in the language being LEFT, not the one arriving. The box is up for under a
        # second and the person is reading it on their way out of a language they could read
        # well enough to find this screen with.
        self.say_and_start_again("settings.language")

    def say_and_start_again(self, title: str) -> None:
        """Tell the person the app is starting over, then do it.

        A screen that goes black and comes back on its own looks like the mat falling over --
        which is exactly what it used to be doing. One line, under the name of the setting
        that changed, and the mat is back before they have finished reading it.
        """
        self.say(self.t("settings.restarting"), title=title)
        QtCore.QTimer.singleShot(700, self.start_again)
