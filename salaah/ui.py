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
from .mosque import ArchButton, ArchShape, GearButton, MosqueScreen, ZoomVeil
from .prayer_times import Place, current_prayer, day_fraction, next_prayer, times_for
from .pages import TextPage, build_pages
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import (FONTS, MAX_ARABIC_PX, MIN_ARABIC_PX, Fonts, PixmapCache, PostureView,
                     ParallelText, TextBox, VolumeBar, load_posture_modes, load_timings)
from .session import Debouncer, Page as SessionPage, PrayerSession
from .tasbih import TasbihScreen
from .timing import TimingScreen
from .compass import CompassScreen
from .side import SideWindow
from .qibla import MOVED, Facing, NoCompass, bearing_to_kaaba, turn_needed
from .power import Outputs
from .settings import Settings
from . import theme
from types import SimpleNamespace

PAPER = "#F5F6F3"
INK = "#1D2327"
LAPIS = "#274B8F"
STONE = "#6B737A"
LINE = "#D9DCD6"
MINT = "#3C8D6B"
BRICK = "#B4443A"

# The posture screen has no backlight of its own, so it is dimmed by drawing a black film over
# it. These ease that off: matched one-for-one to the slider it runs ahead of the monitor, which
# dims for real. 0.6 was picked by looking at the two screens side by side, not by arithmetic.
VEIL_STRENGTH = 0.6
VEIL_MOST = 60          # never darker than this: the postures still have to be followed
NIGHT = "#0B0C0D"
NIGHT_TEXT = "#E6E7E3"

# The prayer-complete screen sets the Arabic and its meaning to one size between them, as large
# as both will fit at. A short passage would otherwise be lettered enormously just because there
# is room: this is the point past which bigger stops helping anyone read it from the mat.
DAILY_MAX_PX = 88

NEXT_KEYS = {
    Qt.Key.Key_VolumeUp, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Right,
    Qt.Key.Key_PageDown, Qt.Key.Key_MediaNext, Qt.Key.Key_MediaPlay, Qt.Key.Key_MediaTogglePlayPause,
}
BACK_KEYS = {Qt.Key.Key_VolumeDown, Qt.Key.Key_Left, Qt.Key.Key_PageUp, Qt.Key.Key_MediaPrevious,
             Qt.Key.Key_Backspace}

# The Qibla compass: at start-up it goes on the 7" screen when there is one, with the main menu
# coming straight up on the big screen, and it keeps watching there between prayers. With no
# compass chip fitted it shows the bearing to line up against (118.5 from Bury), which is
# useful on its own. False takes it out altogether, along with its rows in Settings.
QIBLA = True

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
        # After a fardh prayer, the counted dhikr takes the place of the daily passage.
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
        side_by_side = not page.latin and any(page.english)
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
                 inset: int = 0, compass=None, side: bool = False):
        super().__init__()
        self.aspect = aspect
        self.inset = inset
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

        self.bridge = Bridge()
        self.bridge.action.connect(self.on_button)
        self.bridge.devices.connect(self.on_devices)
        self.bridge.power.connect(self.toggle_sleep)
        self.asleep = False
        self.outputs = Outputs()
        self.notice = None          # the update dialog, while one is on screen
        self.backlight = Backlight()
        self.call = Call(volume=settings.volume)   # the call to prayer
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
        """The area the app draws in: the largest box of the right shape that fits, inset a
        little if the monitor is cutting off the edges."""
        w = max(1, self.width() - 2 * self.inset)
        h = max(1, self.height() - 2 * self.inset)
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
        # The daily passages are lettered to the room they have, so a new shape wants a new size.
        # Once the columns have their new width, not now, hence the timer.
        if hasattr(self, "quran_arabic"):
            QtCore.QTimer.singleShot(0, self.match_daily_sizes)
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
        if getattr(self, "mosque", None) is not None:
            self.mosque.flutter.stop()

    def wake(self) -> None:
        """Screens back on, at whatever was showing when it went to sleep."""
        if not self.asleep:
            return
        self.asleep = False
        if not self.outputs.set(True):
            print(f"wake: {self.outputs.why}", file=sys.stderr)
        if hasattr(self, "clock"):
            self.clock.start()
        if getattr(self, "mosque", None) is not None and self.mosque.isVisible():
            self.mosque.flutter.start()
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
        if self.side is not None:
            self.side.close_screens()
            self.side.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    # Helpers

    def px(self, n: float) -> int:
        return max(1, int(n * self.s))

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
        self.pick = QtWidgets.QWidget()
        self.player = self.build_player()
        self.settings_screen = self.build_settings()
        self.timing_screen = self.build_timing()
        screens = [self.home, self.pick, self.player, self.settings_screen, self.timing_screen]
        if QIBLA:
            self.compass_screen = CompassScreen(self, self.facing)
            self.compass_screen.done.connect(self.qibla_done)
            screens.append(self.compass_screen)
        elif hasattr(self, "compass_screen"):
            del self.compass_screen
        for w in screens:
            self.stack.addWidget(w)
        self.stack.setCurrentWidget(self.home)
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
                                   divider="#444444", pressed="#333333")
        return SimpleNamespace(paper="white", ink=INK, strong="black", line=LINE, lapis=LAPIS,
                               stone=STONE, pale="#E8ECF5", chip="black", hint="#444",
                               source="#555", divider="#CCCCCC", pressed="#DDDDDD")

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
            QLabel#bigTitle {{ color:{c.ink}; }}
            QLabel#bigDetail {{ color:{c.stone}; }}
            QLabel#h1 {{ font-size:{px(64)}px; font-weight:bold; }}
            QLabel#h2 {{ font-size:{px(30)}px; color:{c.lapis}; font-weight:bold; }}
            QLabel#sub {{ font-size:{px(28)}px; color:{c.stone}; }}
            QLabel#note {{ font-size:{px(22)}px; color:{c.stone}; }}
            QWidget#settingsRoot {{ background:{c.paper}; }}
            QWidget#settingsRoot QLabel, QWidget#settingsRoot QRadioButton {{ background:{c.paper}; }}
            QScrollArea#settingsScroll {{ background:{c.paper}; border:none; }}
            QScrollArea#settingsScroll > QWidget > QWidget {{ background:{c.paper}; }}
            QScrollArea#settingsScroll QScrollBar:vertical {{
                background:{c.paper}; width:{px(14)}px; margin:0; border:none; }}
            QScrollArea#settingsScroll QScrollBar::handle:vertical {{
                background:{c.line}; border-radius:{px(7)}px; min-height:{px(60)}px; }}
            QScrollArea#settingsScroll QScrollBar::add-line:vertical,
            QScrollArea#settingsScroll QScrollBar::sub-line:vertical {{ height:0; }}
            QLabel#settingHead {{ font-size:{px(30)}px; font-weight:bold; color:{c.strong}; }}
            QLabel#settingHint {{ font-size:{px(20)}px; color:{c.hint}; }}
            QLabel#settingValue {{ font-size:{px(24)}px; font-weight:bold; color:{c.strong}; }}
            QComboBox#picker {{ background:{c.paper}; color:{c.strong}; font-size:{px(26)}px;
                                 border:{px(3)}px solid {c.strong}; border-radius:{px(10)}px;
                                 padding:{px(8)}px {px(16)}px; min-height:{px(44)}px; }}
            QComboBox#picker::drop-down {{ width:{px(46)}px; border:none; }}
            QComboBox#picker::down-arrow {{ image:none; width:0; height:0;
                                            border-left:{px(11)}px solid transparent;
                                            border-right:{px(11)}px solid transparent;
                                            border-top:{px(14)}px solid {c.strong};
                                            margin-right:{px(14)}px; }}
            QComboBox#picker QAbstractItemView {{ background:{c.paper}; color:{c.strong};
                                                  font-size:{px(26)}px;
                                                  border:{px(3)}px solid {c.strong};
                                                  selection-background-color:{c.pale};
                                                  selection-color:{c.strong}; }}
            QRadioButton#choice {{ font-size:{px(26)}px; font-weight:bold; color:{c.strong};
                                   spacing:{px(14)}px; padding:{px(6)}px 0; }}
            QRadioButton#choice::indicator {{ width:{px(30)}px; height:{px(30)}px;
                                              border:{px(3)}px solid {c.strong};
                                              border-radius:{px(18)}px; background:{c.paper}; }}
            QRadioButton#choice::indicator:checked {{ background:{c.strong}; }}
            QPushButton#mainScreen {{ background:{BRICK}; color:white; border:none;
                                      border-radius:{px(8)}px; font-size:{px(28)}px;
                                      font-weight:bold; padding:{px(12)}px {px(30)}px; }}
            QPushButton#mainScreen:pressed {{ background:#8E342C; }}
            QPushButton#backButton {{ background:{BRICK}; color:white; border:none;
                                      border-radius:{px(8)}px; font-size:{px(28)}px;
                                      font-weight:bold; padding:{px(12)}px {px(30)}px; }}
            QPushButton#backButton:pressed {{ background:#8E342C; }}
            QLabel#prayerNameBig {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                    font-size:{px(64)}px; font-weight:bold; }}
            QWidget#banner {{ background:{c.chip}; }}
            QWidget#compassRoot, QWidget#compassRoot QLabel {{ background:{c.paper}; color:{c.strong}; }}
            QLabel#compassTitle {{ font-size:{px(44)}px; font-weight:bold; }}
            QLabel#compassArabic {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                    font-size:{px(52)}px; font-weight:bold; }}
            QPushButton#updateButton {{ background:{BRICK}; color:white; border:none;
                                        font-size:{px(22)}px; font-weight:bold;
                                        padding:{px(10)}px {px(24)}px;
                                        border-radius:{px(8)}px; }}
            QPushButton#updateButton:pressed {{ background:#8E342C; }}
            QPushButton#updateButton:disabled {{ background:#8E342C; color:#E3BDB9; }}
            QSlider#brightness::groove:horizontal {{ height:{px(14)}px; background:{c.line};
                                                     border-radius:{px(7)}px; }}
            QSlider#brightness::sub-page:horizontal {{ background:{BRICK};
                                                       border-radius:{px(7)}px; }}
            QSlider#brightness::handle:horizontal {{ background:{c.strong};
                                                     border:{px(2)}px solid {c.paper};
                                                     width:{px(44)}px; height:{px(44)}px;
                                                     margin:{-px(16)}px 0;
                                                     border-radius:{px(22)}px; }}
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
            QWidget#playerRoot {{ background:{c.paper}; }}
            QWidget#bar, QWidget#bar QLabel {{ background:{c.paper}; color:{c.strong}; }}
            QWidget#bar QPushButton {{ background:transparent; color:{c.strong}; border:none;
                                       font-size:{px(28)}px; padding:{px(10)}px {px(18)}px; }}
            QWidget#bar QLabel#rakat {{ background:{c.chip}; color:white; font-size:{px(36)}px;
                                        font-weight:bold; padding:0 {px(20)}px;
                                        border-radius:{px(8)}px; min-height:{px(56)}px; }}
            QLabel#prayerName {{ font-family:'{Fonts.arabic(self.settings.arabic_font)}';
                                 font-size:{px(54)}px; font-weight:bold; }}
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
            QWidget#done QLabel#dailyHead {{ background:{c.chip}; color:white; font-size:{px(38)}px;
                                             font-weight:bold; padding:{px(8)}px {px(22)}px;
                                             border-radius:{px(8)}px; }}
            /* No font-size here: match_daily_sizes() sets it, to whatever the Arabic above it
               came out at. A size in the stylesheet would win over that. */
            QWidget#done QLabel#dailyEnglish {{ font-weight:normal; color:{c.strong}; }}
            QWidget#done QLabel#dailySource {{ font-size:{px(19)}px; font-weight:normal;
                                               color:{c.source}; }}
            QFrame#dailyDivider {{ background:{c.divider}; border:none; }}
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

    def build_home(self) -> QtWidgets.QWidget:
        """The mosque: an arch per prayer, the time on the dome, and the prayer whose time it is
        lit up. If the picture is missing for any reason, fall back to plain buttons."""
        self.mosque = MosqueScreen(self.assets, Fonts.english_family)
        if not self.mosque.ready:
            return self.build_plain_home()
        self.mosque.chosen.connect(self.enter_prayer)

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        banner = QtWidgets.QWidget()
        banner.setObjectName("banner")
        row = QtWidgets.QHBoxLayout(banner)
        row.setContentsMargins(self.px(28), self.px(10), self.px(28), self.px(10))
        self.times_label = QtWidgets.QLabel()
        self.times_label.setObjectName("bannerText")
        row.addWidget(self.times_label)
        row.addStretch(1)
        # Red, the colour everything you press is in: Menu, Main screen, the leave buttons.
        gear = GearButton(self.px(52), QtGui.QColor(BRICK))
        gear.setToolTip(self.t("home.settings"))
        gear.pressed_signal.connect(self.open_settings)
        row.addWidget(gear)
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

    # The call to prayer, and going to sleep on its own

    GRACE = 120.0        # seconds after a prayer falls due that the call is still worth making

    @property
    def azaan_file(self) -> Path:
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
        if self.asleep:
            self.wake()         # which comes back at the mosque, by its own design
        else:
            self.go_home()
        box = Notice(self, self.px, self.t("call.title"))
        box.finish(self.t(f"prayer.{prayer}"), self.t("call.stop"))
        box.finished.connect(self.end_the_call)
        self.call_box = box
        # No azaan for Fajr: the words differ there, and calling Fajr with the wrong ones is
        # worse than not calling it. The notice still appears, so the mat still says it is time.
        if prayer != "fajr":
            self.call.volume = self.settings.volume
            if self.call.play(self.azaan_file):
                self.call_watch.start()

    def watch_the_call(self) -> None:
        """Close the notice when the call ends of its own accord, so nobody has to dismiss it."""
        if self.call_box is not None and not self.call.playing:
            self.call_box.accept()

    def end_the_call(self, *_) -> None:
        """Stop, whether the call finished or somebody pressed the button."""
        self.call.stop()
        self.call_watch.stop()
        self.call_box = None
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
            self._times = times_for(when.date(), self.place, self.school.id)
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
        # The prayer whose time it is stands out in green; the rest are in the banner's own
        # colour. Written as rich text, since a QLabel takes its colours that way.
        now_praying = current_prayer(now, times)
        green = theme.palette().green
        gap = "&nbsp;" * 4          # rich text squeezes plain spaces down to one
        shown = gap.join(
            (f'<span style="color:{green}">{self.t(f"prayer.{name}")} '
             f'{times[name].strftime("%H:%M")}</span>' if name == now_praying else
             f'{self.t(f"prayer.{name}")} {times[name].strftime("%H:%M")}')
            for name in PRAYERS if times.get(name) is not None)
        where = self.settings.place or f"{self.settings.latitude:.2f}, {self.settings.longitude:.2f}"
        following = next_prayer(now, times)
        after = (gap + self.t("home.next", prayer=self.t(f"prayer.{following}"))
                 if following else "")
        self.times_label.setText(f"{where}{gap}{shown}{after}")
        self.times_label.setTextFormat(Qt.TextFormat.RichText)

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

    def open_prayer(self, pid: str) -> None:
        """The units of this prayer, each as an arch like the ones on the mosque."""
        self.prayer = pid
        old = self.pick
        entries = self.school.prayers.get(pid, [])
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

        # The prayer's name in English on one side, in Arabic on the other.
        names = QtWidgets.QHBoxLayout()
        english = QtWidgets.QLabel(self.t(f"prayer.{pid}"))
        english.setObjectName("h1")
        arabic = QtWidgets.QLabel(self.content.prayer_names.get(pid, ""))
        arabic.setObjectName("prayerNameBig")
        names.addWidget(english)
        names.addStretch(1)
        names.addWidget(arabic)
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

    def go_home(self) -> None:
        self.session = None
        if self.veil.running:
            self.veil.stop()        # don't walk into an arch we have just walked back out of
        if hasattr(self, "compass_screen"):
            self.compass_screen.close_screen()
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

        name_font = QtGui.QFont(Fonts.arabic(self.settings.arabic_font))
        name_font.setPixelSize(self.px(54))
        self.arabic_name = QtWidgets.QLabel(bar)       # placed by TopBar, dead centre
        self.arabic_name.setObjectName("prayerName")   # size and family come from the stylesheet
        self.arabic_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Arabic vowel marks sit well above and below the letters; give them room.
        self.arabic_name.setMinimumHeight(QtGui.QFontMetrics(name_font).height())
        bar.centre = self.arabic_name
        bar.setMinimumHeight(QtGui.QFontMetrics(name_font).height() + self.px(12))

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
        # When the prayer finishes: a saying on the left, a passage of the Qur'an on the right.
        dl = QtWidgets.QVBoxLayout(self.slide.done)
        dl.setContentsMargins(self.px(56), self.px(28), self.px(56), self.px(24))
        dl.setSpacing(self.px(10))
        # No "Prayer complete" heading: the two passages are the screen, and you know you have
        # finished because you just did.
        pair = QtWidgets.QHBoxLayout()
        pair.setSpacing(self.px(56))

        hadith = QtWidgets.QVBoxLayout()
        hadith.setSpacing(self.px(8))
        hadith_head = QtWidgets.QLabel(self.t("daily.hadith"))
        hadith_head.setObjectName("dailyHead")
        self.hadith_arabic = TextBox(Fonts.arabic(self.settings.arabic_font), MIN_ARABIC_PX,
                                     MAX_ARABIC_PX, rtl=True, weight=700, slack=0.98,
                                     by_word=True, gap=0.18)
        self.hadith_arabic.scale = self.s
        self.hadith_text = QtWidgets.QLabel()
        self.hadith_text.setObjectName("dailyEnglish")
        self.hadith_text.setWordWrap(True)
        self.hadith_source = QtWidgets.QLabel()
        self.hadith_source.setObjectName("dailySource")
        # The Arabic and its English are set at one size, so the Arabic is no longer stretched to
        # fill the column. Each block hangs from its heading, which keeps the two columns' first
        # lines level with each other however differently long the two passages are; the spare
        # room goes to the bottom.
        hadith.addWidget(hadith_head, 0, Qt.AlignmentFlag.AlignHCenter)
        hadith.addWidget(self.hadith_arabic, 0)
        hadith.addWidget(self.hadith_text)
        hadith.addWidget(self.hadith_source)
        hadith.addStretch(1)
        pair.addLayout(hadith, 1)

        divider = QtWidgets.QFrame()
        divider.setObjectName("dailyDivider")
        divider.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        divider.setFixedWidth(max(1, self.px(2)))
        pair.addWidget(divider)

        quran = QtWidgets.QVBoxLayout()
        quran.setSpacing(self.px(8))
        quran_head = QtWidgets.QLabel(self.t("daily.quran"))
        quran_head.setObjectName("dailyHead")
        self.quran_arabic = TextBox(Fonts.arabic(self.settings.arabic_font), MIN_ARABIC_PX,
                                    MAX_ARABIC_PX, rtl=True, weight=700, slack=0.98,
                                    by_word=True, gap=0.18)
        self.quran_arabic.scale = self.s
        self.quran_english = QtWidgets.QLabel()
        self.quran_english.setObjectName("dailyEnglish")
        self.quran_english.setWordWrap(True)
        self.quran_source = QtWidgets.QLabel()
        self.quran_source.setObjectName("dailySource")
        quran.addWidget(quran_head, 0, Qt.AlignmentFlag.AlignHCenter)
        quran.addWidget(self.quran_arabic, 0)
        quran.addWidget(self.quran_english)
        quran.addWidget(self.quran_source)
        quran.addStretch(1)
        pair.addLayout(quran, 1)
        dl.addLayout(pair, 1)
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
        self.arabic_name.setText(self.content.prayer_names.get(prayer, ""))
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

    @property
    def translation(self):
        """The translation shown beside the Arabic, or None for Arabic only."""
        return self.content.translations.get(self.settings.translation or "")

    def set_translation(self, lang: str) -> None:
        """Takes effect from the next prayer started."""
        self.settings.translation = "" if lang == "none" else lang
        self.persist()

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
        # A fardh prayer ends on the counted dhikr, anything else on the daily passage.
        counting = s.finished and self.counts_dhikr
        if s.finished and not counting:
            self.show_daily()
        self.slide.done.setVisible(s.finished and not counting)
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

    def show_daily(self) -> None:
        """The passage and the saying for today. The same all day, different tomorrow."""
        passage, saying = self.content.daily.for_day(datetime.now().date())
        if saying:
            self.hadith_arabic.set_lines([saying.get("arabic", "")])
            self.hadith_text.setText(saying.get("english", ""))
            self.hadith_source.setText(saying.get("reference", ""))
        if passage:
            self.quran_arabic.set_lines([passage.get("arabic", "")])
            self.quran_english.setText(passage.get("english", ""))
            self.quran_source.setText(self.t("daily.quran_ref", ref=passage.get("reference", "")))
        self.match_daily_sizes()

    def match_daily_sizes(self) -> None:
        """Sets the Arabic and the English of both daily passages to one size between them.

        They are quotations, read one under the other, so a small English caption under a huge
        line of Arabic makes the meaning look like a footnote to the words. One size for all four
        blocks: the largest at which each column's Arabic, English and reference all still fit in
        the room that column has. Both columns take the smaller of the two answers, so the screen
        reads as one thing rather than two columns lettered differently.
        """
        columns = [(self.hadith_arabic, self.hadith_text, self.hadith_source),
                   (self.quran_arabic, self.quran_english, self.quran_source)]
        room = self.daily_room()
        if room <= 0 or any(box.width() < 50 for box, _, _ in columns):
            return                      # not laid out yet; show_daily runs again once it is

        def english_height(label, size: int) -> int:
            """The height the meaning takes at that size, and a little over.

            Built from the face the stylesheet gives it, not label.font(), which does not reflect
            a stylesheet. The bit over matters: measured exactly, a descender on the last line
            comes out a single pixel clear of the bottom, which is the sort of thing that fits
            here and clips on the Pi.
            """
            font = QtGui.QFont(self.pack_face())
            font.setPixelSize(size)
            box = QtGui.QFontMetrics(font).boundingRect(
                0, 0, label.width(), 0,
                int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft),
                label.text()).height()
            return box + max(2, size // 10)

        def fits(column, size: int) -> bool:
            box, english, source = column
            return (box.height_at(size) + english_height(english, size)
                    + source.sizeHint().height()) <= room

        low, high = self.px(20), self.px(DAILY_MAX_PX)
        best = low
        while low <= high:
            mid = (low + high) // 2
            if all(fits(column, mid) for column in columns):
                best, low = mid, mid + 1
            else:
                high = mid - 1
        for box, english, source in columns:
            box.pin(best)
            box.setFixedHeight(box.height_at(best))
            # Set through the widget's own stylesheet: a font-size in an ancestor's stylesheet
            # (QWidget#done QLabel) would otherwise win over setFont and nothing would change.
            english.setStyleSheet(f"font-size:{best}px;")
            english.setFixedHeight(english_height(english, best))

    def daily_room(self) -> int:
        """The height in one column of the prayer-complete screen left for the words themselves,
        once the heading, the gaps between the rows and the margins are taken out."""
        page = self.slide.done
        lay = page.layout()
        if lay is None or page.height() < 100:
            return 0
        margins = lay.contentsMargins()
        heads = [x for x in page.findChildren(QtWidgets.QLabel) if x.objectName() == "dailyHead"]
        heading = max((x.sizeHint().height() for x in heads), default=0)
        gaps = self.px(8) * 3           # heading to Arabic, Arabic to English, English to source
        return page.height() - margins.top() - margins.bottom() - heading - gaps

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
        self.stir()
        if self.qibla_open:
            self.compass_screen.skip()             # a press always goes straight on
            return
        if self.timing_open:
            self.timing_press(action)
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
        self.device_names = list(names)
        self.update_status()
        if hasattr(self, "devices_label"):
            self.devices_label.setText(self.devices_text())

    def update_status(self) -> None:
        connected = bool(self.device_names)
        self.dot.set_color(MINT if connected else BRICK)
        self.dot.setToolTip(self.t("button.connected") if connected else self.t("button.disconnected"))

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

    def open_settings(self) -> None:
        self.devices_label.setText(self.devices_text())
        self.stack.setCurrentWidget(self.settings_screen)

    def devices_text(self) -> str:
        if not self.device_names:
            return self.t("settings.no_buttons")
        return ", ".join(self.device_names)

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
        """White, two columns, a cog for a heading and a way straight back to the mosque."""
        w = QtWidgets.QWidget()
        w.setObjectName("settingsRoot")
        outer = QtWidgets.QVBoxLayout(w)
        outer.setContentsMargins(self.px(48), self.px(24), self.px(48), self.px(24))
        outer.setSpacing(self.px(10))

        head = QtWidgets.QHBoxLayout()
        cog = GearButton(self.px(52), QtGui.QColor(BRICK))   # matching the one on the banner
        cog.setToolTip(self.t("settings.title"))
        head.addWidget(cog)
        head.addStretch(1)
        home = no_focus(QtWidgets.QPushButton(self.t("settings.main_screen")))
        home.setObjectName("mainScreen")
        home.clicked.connect(self.go_home)
        head.addWidget(home)
        outer.addLayout(head)

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
        outer.addWidget(self.settings_scroll, 1)

        def section(column: QtWidgets.QVBoxLayout, key: str, hint: str = "") -> None:
            column.addSpacing(self.px(14))
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
        section(left, "settings.school")
        left.addLayout(self.circles(
            [(sid, self.t(f"school.{sid}")) for sid in sorted(self.content.schools)],
            self.school.id, self.set_school))

        section(left, "settings.language")
        self.language_picker = self.dropdown(
            [(p.lang, p.native_name) for p in sorted(self.packs.values(), key=lambda x: x.lang)],
            self.pack.lang, self.set_lang)
        left.addWidget(self.language_picker)

        if self.content.translations:
            section(left, "settings.translation")
            self.translation_picker = self.dropdown(
                [("none", self.t("settings.translation_none"))]
                + [(lang, tr.native_name) for lang, tr in sorted(self.content.translations.items())],
                self.settings.translation or "none", self.set_translation)
            left.addWidget(self.translation_picker)

        if len(self.content.figures) > 1:
            section(left, "settings.figure")
            left.addLayout(self.circles(
                [(name, self.t(f"figure.{name}")) for name in self.content.figures],
                self.settings.figure, self.set_figure, across=True))

        section(left, "settings.font", self.t("settings.font_hint"))
        left.addLayout(self.circles(
            [(key, self.t(f"font.{key}")) for key in FONTS if key in Fonts.families],
            self.settings.arabic_font, self.set_font, across=True, per_row=2))

        # A dropdown, like the two above it: the three choices are wordy enough that as a row of
        # circles they took a quarter of the column, and the wording made it hard to see at a
        # glance that light and dark were choices at all rather than a note about the automatic one.
        section(left, "settings.azaan")
        left.addLayout(self.circles([("1", self.t("settings.on")), ("0", self.t("settings.off"))],
                                    "1" if self.settings.azaan else "0",
                                    self.set_azaan, across=True))

        section(left, "settings.theme")
        self.theme_picker = self.dropdown(
            [(mode, self.t(f"settings.theme_{mode}")) for mode in theme.MODES],
            self.settings.theme if self.settings.theme in theme.MODES else "auto", self.set_theme)
        left.addWidget(self.theme_picker)
        left.addStretch(1)

        # Right column
        if self.timings:
            section(right, "settings.recitation", self.t("settings.recitation_hint"))
            right.addLayout(self.circles([("1", self.t("settings.on")), ("0", self.t("settings.off"))],
                                         "1" if self.settings.recitation else "0",
                                         self.set_recitation, across=True))
            if not self.recitation.available:
                right.addWidget(self.value_label(self.t("settings.no_player")))
            # No button for tapping the timings in: that is a job for whoever is building the
            # mat, not for whoever is praying on it. Start with --tap-timings to get at it.

        # No explanation when it works: a brightness slider explains itself. The words are for
        # the case where it cannot do what it appears to, which is the one that needs saying.
        section(right, "settings.brightness",
                "" if self.backlight.available else self.t("settings.brightness_veil"))
        right.addLayout(self.brightness_slider())

        section(right, "settings.inset")
        right.addLayout(self.circles([(str(v), f"{v} px") for v in (0, 20, 40, 60)],
                                     str(self.settings.inset), self.set_inset, across=True))

        section(right, "settings.cursor")
        right.addLayout(self.circles(
            [("1", self.t("settings.cursor_shown")), ("0", self.t("settings.cursor_hidden"))],
            "1" if self.settings.cursor else "0", self.set_cursor))

        if QIBLA:
            self.qibla_settings(right, section)

        section(right, "settings.buttons")
        self.devices_label = QtWidgets.QLabel(self.devices_text())
        self.devices_label.setObjectName("settingValue")
        right.addWidget(self.devices_label)
        right.addStretch(1)

        # No way out to the desktop: the mat is the product, and there is nothing behind it to
        # go to. Ctrl+Q still quits, for working on it (see eventFilter).
        outer.addSpacing(self.px(12))        # so the version never sits against the last option
        foot = QtWidgets.QHBoxLayout()
        version = QtWidgets.QLabel(self.t("settings.version", number=__version__))
        version.setObjectName("settingValue")
        foot.addWidget(version)
        foot.addSpacing(self.px(24))
        self.update_button = no_focus(QtWidgets.QPushButton(self.t("update.check")))
        self.update_button.setObjectName("updateButton")
        self.update_button.clicked.connect(self.check_for_update)
        foot.addWidget(self.update_button)
        foot.addStretch(1)
        outer.addLayout(foot)
        return w

    # Updating

    @property
    def root(self) -> Path:
        """The folder holding salaah/ and assets/ -- the one run.sh sits in, and the one an
        update replaces the contents of."""
        return self.assets.resolve().parent

    def update_url(self) -> str:
        from .update import DEFAULT_URL
        return self.settings.update_url or DEFAULT_URL

    def say(self, message: str) -> None:
        """Put a message in front of the person, in a box they cannot overlook.

        The whole business of updating happens on this thread, so nothing repaints while the
        network is being waited on. Every message therefore has to be painted BEFORE the slow
        thing starts, which is what settle() ends with.
        """
        if self.notice is None:
            self.notice = Notice(self, self.px, self.t("update.title"))
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
        if not self.settings.cursor:
            app.setOverrideCursor(Qt.CursorShape.BlankCursor)

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
        self.volume.set_volume(self.settings.volume if self.settings.recitation else 0)

    def set_inset(self, value: str) -> None:
        self.settings.inset = int(value)
        self.inset = int(value)
        self.persist()
        self.resizeEvent(QtGui.QResizeEvent(self.size(), self.size()))

    def set_font(self, key: str) -> None:
        self.settings.arabic_font = key
        self.persist()
        self.slide.arabic.set_family(Fonts.arabic(key))
        self.slide.parallel.set_family(Fonts.arabic(key))
        self.setStyleSheet(self.stylesheet())   # the banner name uses it too

    def set_school(self, sid: str) -> None:
        self.settings.school = sid
        self.persist()
        self.rebuild()
        self.open_settings()

    def set_lang(self, lang: str) -> None:
        self.settings.lang = lang
        self.persist()
        self.rebuild()
        self.open_settings()
