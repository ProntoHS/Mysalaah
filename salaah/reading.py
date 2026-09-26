"""The Knowledge Corner on the big screen: the list of surahs, and reading one.

A surah is shown as an open book -- two pages side by side, turned by swiping. With a
translation chosen the meaning takes the left page and the Arabic the right, verse level with
verse, so the eye can go straight across. With no translation chosen there is nothing to put on
the left, so the Arabic takes both pages: the right one first, then the left, the way a book
with its spine on the right is read.

Nothing scrolls. A scrollbar on a mat is a poor thing to aim at, and there is no way to tell how
far through you are except by dragging. Pages are countable, and the ring button turns them as
happily as a finger does.

How many verses a page holds is not fixed. It is worked out from the room available and a floor
on how small the Arabic may be drawn -- a page of Al-Baqarah holds fewer verses than a page of
Al-Ikhlas because its verses are longer, which is exactly what a printed mushaf does too.
"""
from __future__ import annotations

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .quran import RTL, Quran, Surah, Verse
from .render import Fonts, ParallelText, TextBox
from .theme import palette

# The Arabic is never drawn smaller than this (at 1080p). Fitting more verses on a page by
# shrinking the script until it cannot be read would be the wrong trade every time.
FLOOR_PX = 30
MOST_VERSES = 40          # a page never holds more than this, however short the verses

# Which way a swipe goes. Right-to-left means forward, as it does in every other touch screen
# the mat's owner uses. An Arabic book turns the other way, so this is the line to change if
# that matters more than the habit does.
FORWARD_IS_LEFT = True
SWIPE = 60                # pixels, at 1080p, before a drag counts as a page turn


class SurahList(QtWidgets.QWidget):
    """All 114, in Arabic and in English, as a grid of touchable rows."""

    chose = Signal(int)
    leave = Signal()
    COLUMNS = 3

    def __init__(self, window, quran: Quran):
        super().__init__()
        self.win = window
        self.quran = quran
        self.setObjectName("surahList")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # A way out. Without it the only escape from 114 surahs is the power button, which is
        # no way to leave a screen somebody opened on purpose.
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(self.win.px(20), self.win.px(10), self.win.px(20), 0)
        title = QtWidgets.QLabel(self.win.t("corner.surahs"))
        title.setObjectName("readerTitle")
        bar.addWidget(title)
        bar.addStretch(1)
        home = QtWidgets.QPushButton(self.win.t("settings.main_screen"))
        home.setObjectName("mainScreen")
        home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        home.clicked.connect(self.leave.emit)
        bar.addWidget(home)
        outer.addLayout(bar)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(inner)
        self.grid.setContentsMargins(self.win.px(20), self.win.px(10),
                                     self.win.px(20), self.win.px(20))
        self.grid.setSpacing(self.win.px(10))
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, 1)
        self.filled = False

    def showEvent(self, ev):
        # Built the first time it is looked at, not at start-up. 114 rows is the better part of
        # six hundred widgets, and most times the mat is switched on nobody opens this at all.
        self.fill()
        super().showEvent(ev)

    def fill(self) -> None:
        if self.filled:
            return
        self.filled = True
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for i, surah in enumerate(self.quran.index):
            self.grid.addWidget(self.row(surah), i // self.COLUMNS, i % self.COLUMNS)

    def row(self, surah: Surah) -> QtWidgets.QWidget:
        b = QtWidgets.QPushButton()
        b.setObjectName("surahRow")
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(self.win.px(96))
        b.clicked.connect(lambda _=False, n=surah.number: self.chose.emit(n))

        lay = QtWidgets.QHBoxLayout(b)
        lay.setContentsMargins(self.win.px(16), self.win.px(8), self.win.px(16), self.win.px(8))
        lay.setSpacing(self.win.px(12))

        number = QtWidgets.QLabel(str(surah.number))
        number.setObjectName("surahNumber")
        number.setFixedWidth(self.win.px(64))
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(number)

        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        english = QtWidgets.QLabel(surah.name)
        english.setObjectName("surahName")
        meaning = QtWidgets.QLabel(f"{surah.meaning} · {surah.verses}")
        meaning.setObjectName("surahMeaning")
        names.addWidget(english)
        names.addWidget(meaning)
        lay.addLayout(names, 1)

        arabic = QtWidgets.QLabel(surah.arabic)
        arabic.setObjectName("surahArabic")
        arabic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(arabic)
        return b

    def to_the_top(self) -> None:
        self.fill()
        self.scroll.verticalScrollBar().setValue(0)


class Spread(QtWidgets.QWidget):
    """Two pages of one surah, and the working out of where the pages fall."""

    turned = Signal()

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("spread")
        self.verses: list[Verse] = []
        self.rtl_meaning = False
        self.pages: list[tuple[int, int]] = []     # (first verse index, one past the last)
        self.at = 0
        self._measured = None                      # the size the pages were worked out for
        self._down: QtCore.QPoint | None = None

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # With a translation: one widget holding both columns, so each verse's two halves stay
        # level with each other. Without: two Arabic boxes, read right first.
        self.parallel = ParallelText(Fonts.arabic(self.win.settings.arabic_font),
                                     Fonts.english_family)
        self.left = TextBox(Fonts.arabic(self.win.settings.arabic_font), FLOOR_PX, 200, rtl=True)
        self.right = TextBox(Fonts.arabic(self.win.settings.arabic_font), FLOOR_PX, 200, rtl=True)
        for w in (self.parallel, self.left, self.right):
            w.scale = self.win.s
        lay.addWidget(self.parallel, 1)
        lay.addWidget(self.left, 1)
        lay.addWidget(self.right, 1)
        self.parallel.hide()

    # What is being read

    def show_surah(self, verses: list[Verse], rtl_meaning: bool) -> None:
        self.verses = verses
        self.rtl_meaning = rtl_meaning
        self.at = 0
        self._measured = None
        self.repaginate()

    @property
    def translated(self) -> bool:
        return any(v.meaning for v in self.verses)

    @property
    def pages_count(self) -> int:
        return max(1, len(self.pages))

    # Where the pages fall

    def room(self) -> QtCore.QSize:
        return self.size()

    def repaginate(self) -> None:
        """Work out where each page starts and ends, for the room there is now."""
        key = (self.width(), self.height(), self.translated, len(self.verses),
               self.win.settings.arabic_font, self.win.s)
        if self._measured == key:
            return
        self._measured = key
        self.parallel.setVisible(self.translated)
        self.left.setVisible(not self.translated)
        self.right.setVisible(not self.translated)
        if not self.verses or self.width() < 50 or self.height() < 50:
            self.pages = [(0, len(self.verses))]
            self.show_page()
            self.turned.emit()
            return
        self.pages = list(self.walk())
        self.at = min(self.at, len(self.pages) - 1)
        self.show_page()
        # Where the pages fall is not known until the widget has a size, and a surah is often
        # opened before it has one. Saying so here is what keeps "page 1 of 8" from being the
        # answer to a question asked when the page was a few pixels tall.
        self.turned.emit()

    def walk(self):
        """Pages, one after another, each as full as it can be and still be readable."""
        start, total = 0, len(self.verses)
        while start < total:
            end = self.fits_from(start)
            yield (start, end)
            start = end

    def fits_from(self, start: int) -> int:
        """One past the last verse that fits on a page beginning at [start]. Never fewer than
        one: a verse too long for a whole page still has to be shown somewhere."""
        low, high = start + 1, min(len(self.verses), start + MOST_VERSES)
        if low >= high:
            return high if high > start else start + 1
        best = low
        while low <= high:
            mid = (low + high) // 2
            if self.holds(start, mid):
                best, low = mid, mid + 1
            else:
                high = mid - 1
        return best

    def holds(self, start: int, end: int) -> bool:
        floor = max(1, int(FLOOR_PX * self.win.s))
        some = self.verses[start:end]
        if self.translated:
            self.parallel.arabic = [self.numbered(v) for v in some]
            self.parallel.meaning = [v.meaning for v in some]
            self.parallel.meaning_rtl = self.rtl_meaning
            self.parallel._cache = None
            return self.parallel._rows(floor)[1] <= int(self.parallel.height() * 0.96)
        # Two Arabic columns: the right page, then the left. A page holds what both will take.
        half = (len(some) + 1) // 2
        for box, lines in ((self.right, some[:half]), (self.left, some[half:])):
            box.lines = [self.numbered(v) for v in lines]
            if box.lines and box.measure(box.lines, floor) > int(box.height() * 0.92):
                return False
        return True

    @staticmethod
    def numbered(verse: Verse) -> str:
        """The verse with its number after it, in the Arabic way -- ﴿1﴾ closing the verse."""
        return f"{verse.arabic} ۝{verse.number}"

    # Showing one

    def show_page(self) -> None:
        if not self.pages:
            self.pages = [(0, len(self.verses))]
        start, end = self.pages[max(0, min(self.at, len(self.pages) - 1))]
        some = self.verses[start:end]
        if self.translated:
            self.parallel.set_lines([self.numbered(v) for v in some],
                                    [v.meaning for v in some], self.rtl_meaning)
        else:
            half = (len(some) + 1) // 2
            self.right.set_lines([self.numbered(v) for v in some[:half]])
            self.left.set_lines([self.numbered(v) for v in some[half:]])
        self.update()

    def turn(self, forward: bool) -> bool:
        wanted = self.at + (1 if forward else -1)
        if not 0 <= wanted < len(self.pages):
            return False
        self.at = wanted
        self.show_page()
        self.turned.emit()
        return True

    def go_to(self, page: int) -> None:
        self.at = max(0, min(page, len(self.pages) - 1))
        self.show_page()
        self.turned.emit()

    # Turning them

    def mousePressEvent(self, ev):
        self._down = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()

    def mouseReleaseEvent(self, ev):
        if self._down is None:
            return
        here = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()
        moved = here.x() - self._down.x()
        self._down = None
        if abs(moved) < int(SWIPE * self.win.s):
            return
        went_left = moved < 0
        self.turn(forward=(went_left == FORWARD_IS_LEFT))

    def resizeEvent(self, ev):
        self._measured = None
        self.repaginate()
        super().resizeEvent(ev)

    def follow_theme(self) -> None:
        for w in (self.parallel, self.left, self.right):
            w.update()


class Reader(QtWidgets.QWidget):
    """One surah, open: a bar saying where you are, and the two pages under it."""

    back = Signal()

    def __init__(self, window, quran: Quran):
        super().__init__()
        self.win = window
        self.quran = quran
        self.number = 1
        self.setObjectName("reader")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(self.win.px(16), self.win.px(8), self.win.px(16), self.win.px(8))
        outer.setSpacing(self.win.px(8))

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(self.win.px(12))
        self.back_button = QtWidgets.QPushButton(self.win.t("corner.back"))
        self.back_button.setObjectName("backButton")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.back.emit)
        bar.addWidget(self.back_button)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("readerTitle")
        bar.addWidget(self.title)
        bar.addStretch(1)

        # Which meaning to set beside the Arabic, chosen here rather than buried in Settings:
        # it is the thing most likely to be changed while reading.
        self.tongues = QtWidgets.QHBoxLayout()
        self.tongues.setSpacing(self.win.px(6))
        self.buttons: dict[str, QtWidgets.QPushButton] = {}
        for lang in ("",) + self.quran.languages():
            b = QtWidgets.QPushButton(self.win.t("quran.arabic_only") if not lang
                                      else self.win.pack_name(lang))
            b.setObjectName("tongue")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, l=lang: self.set_language(l))
            self.buttons[lang] = b
            self.tongues.addWidget(b)
        bar.addLayout(self.tongues)
        bar.addStretch(1)

        self.earlier = QtWidgets.QPushButton("‹")
        self.later = QtWidgets.QPushButton("›")
        for b, forward in ((self.earlier, False), (self.later, True)):
            b.setObjectName("turnPage")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, f=forward: self.spread.turn(f))
        self.where = QtWidgets.QLabel()
        self.where.setObjectName("readerWhere")
        bar.addWidget(self.earlier)
        bar.addWidget(self.where)
        bar.addWidget(self.later)
        outer.addLayout(bar)

        self.spread = Spread(self.win)
        self.spread.turned.connect(self.say_where)
        outer.addWidget(self.spread, 1)

    def open(self, number: int) -> None:
        self.number = number
        surah = self.quran.surah(number)
        if surah is not None:
            self.title.setText(f"{surah.number}. {surah.name} · {surah.arabic}")
        self.reload()

    def reload(self) -> None:
        lang = self.win.settings.quran_lang
        if lang and lang not in self.quran.languages():
            lang = ""
        for key, b in self.buttons.items():
            b.setChecked(key == lang)
        self.spread.show_surah(self.quran.verses(self.number, lang), rtl_meaning=(lang in RTL))
        self.say_where()

    def set_language(self, lang: str) -> None:
        self.win.settings.quran_lang = lang
        self.win.persist()
        self.reload()

    def say_where(self) -> None:
        self.where.setText(self.win.t("quran.page", at=self.spread.at + 1,
                                      of=self.spread.pages_count))
        self.earlier.setEnabled(self.spread.at > 0)
        self.later.setEnabled(self.spread.at < self.spread.pages_count - 1)

    def turn(self, forward: bool) -> bool:
        """The ring button and the arrow keys turn pages too, not only a finger."""
        return self.spread.turn(forward)

    def follow_theme(self) -> None:
        self.spread.follow_theme()
