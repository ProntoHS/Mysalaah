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

from .audio import WHOLE, Span
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

# How long to wait for a verse to arrive before giving up on it. A verse is 143 KB, so this is
# generous; the point is that a connection which hangs leaves a message rather than a dead
# screen with the play button stuck on stop.
PATIENCE = 30.0

# The recite button. Glyphs, not words: see the note where the button is built.
PLAY = "\u25b6"
STOP = "\u25a0"


# The numbered square beside each surah, in one place so every one of the 114 is identical.
NUMBER_BOX = 64          # the square's side, before scaling
NUMBER_LINE = 4          # and how thick its outline is drawn

# The slider down the side of the lists. Four times the 14px a desktop gives it: this is a
# touchscreen, and 14px is a target for a mouse pointer, not for the side of a thumb. The lists
# resize to whatever the slider leaves, so the rows give up the width rather than the slider
# sitting on top of them.
#
# 42 at first, which was already three times a desktop's, and Harry asked for it thicker again
# after using it. He is the one dragging it on glass: 56px is about a centimetre on the mat's
# screen, which is the width of the thumb doing the dragging rather than the width of the line
# somebody thought looked right.
LIST_BAR = 56


class SurahList(QtWidgets.QWidget):
    """All 114, in Arabic and in English, as a grid of touchable rows."""

    chose = Signal(int)
    COLUMNS = 3

    def __init__(self, window, quran: Quran):
        super().__init__()
        self.win = window
        self.quran = quran
        self.setObjectName("surahList")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # The way out used to sit here. It is in the banner above this screen now, along with
        # the clock and the prayer times, so it is in the same place wherever you are.
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(self.win.px(20), self.win.px(10), self.win.px(20), 0)
        title = QtWidgets.QLabel(self.win.t("corner.surahs"))
        title.setObjectName("readerTitle")
        bar.addWidget(title)
        bar.addStretch(1)
        outer.addLayout(bar)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")
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

        # A square, fixed both ways, so 1 and 114 sit in boxes of exactly the same size and
        # the left-hand edge of every row lines up down the column.
        number = QtWidgets.QLabel(str(surah.number))
        number.setObjectName("surahNumber")
        number.setFixedSize(self.win.px(NUMBER_BOX), self.win.px(NUMBER_BOX))
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
        # by_word so a single word can be lit while it is recited. It costs a word-by-word
        # layout pass instead of a line-by-line one; the page still breaks in the same places.
        self.left = TextBox(Fonts.arabic(self.win.settings.arabic_font), FLOOR_PX, 200,
                            rtl=True, by_word=True)
        self.right = TextBox(Fonts.arabic(self.win.settings.arabic_font), FLOOR_PX, 200,
                             rtl=True, by_word=True)
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
            # measure_as_lines, not measure: see the note on it. Page breaks must not move
            # just because the words can now be lit one at a time.
            if box.lines and box.measure_as_lines(box.lines, floor) > int(box.height() * 0.92):
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

    # Lighting a word

    def page_of(self, index: int) -> int | None:
        """Which page a verse falls on, so reciting can turn to it."""
        for i, (start, end) in enumerate(self.pages):
            if start <= index < end:
                return i
        return None

    def clear_highlight(self) -> None:
        self.parallel.set_highlight(None)
        self.left.set_highlight(None)
        self.right.set_highlight(None)

    def highlight_at(self, index: int, word: int | None) -> None:
        """Light word [word] of the verse at [index], wherever on the spread it has landed.

        With a translation there is one row per verse, so the row is the verse. Without, the
        page is split down the middle -- the right page first, then the left -- so which box
        holds the verse has to be worked out, and it is easy to get off by a half.
        """
        if word is None or not self.pages:
            return self.clear_highlight()
        start, end = self.pages[max(0, min(self.at, len(self.pages) - 1))]
        if not start <= index < end:
            return self.clear_highlight()
        row = index - start
        if self.translated:
            self.left.set_highlight(None)
            self.right.set_highlight(None)
            self.parallel.set_highlight((row, word))
            return
        self.parallel.set_highlight(None)
        half = (end - start + 1) // 2
        if row < half:
            self.right.set_highlight((row, word))
            self.left.set_highlight(None)
        else:
            self.left.set_highlight((row - half, word))
            self.right.set_highlight(None)

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

        # The drawn play mark rather than the word "Recite": spelled out in six languages it
        # crowded the language buttons off the bar and clipped "Arabic only" to "abic on". It is
        # the same mark that sits beside every du'a, so one thing means play across the app.
        # The word is on the tooltip for anyone who wonders.
        self.recite_button = QtWidgets.QPushButton()
        self.recite_button.setObjectName("reciteButton")
        self.recite_button.setToolTip(self.win.t("quran.recite"))
        self.reciting_now = False
        self.draw_recite_mark()

        self.recite_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recite_button.clicked.connect(self.toggle_reciting)
        bar.addWidget(self.recite_button)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("readerTitle")
        bar.addWidget(self.title)
        bar.addStretch(1)

        # There was a row of language buttons here -- "Arabic only", "English", "Français" and
        # the rest -- for setting the meaning beside the Arabic while reading. It has gone.
        #
        # It was a third place to answer a question the mat now asks once. Settings had a
        # language, Settings had a translation, and this bar had its own buttons, and all three
        # wrote to different places: the surah could be in French while the menu that opened it
        # was in Urdu. The page follows the mat's language now, and nothing has to be set to
        # make that happen -- which is also what makes "Arabic only" in Settings reach this
        # screen, where it opens the Arabic across both pages.
        #
        # The room it leaves goes to the title, which was being squeezed by seven buttons.
        self.buttons: dict[str, QtWidgets.QPushButton] = {}
        bar.addStretch(1)

        # No volume slider here: the banner directly above this row has one, and two of them
        # a centimetre apart is one too many.

        # Which page you are on used to be spelled out beside the arrows. It has gone: the
        # arrows say the same thing by greying out at either end, and "Page 1 of 39" was the
        # widest thing in a row that had run out of room.
        self.earlier = QtWidgets.QPushButton("‹")
        self.later = QtWidgets.QPushButton("›")
        for b, forward in ((self.earlier, False), (self.later, True)):
            b.setObjectName("turnPage")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, f=forward: self.spread.turn(f))
        bar.addWidget(self.earlier)
        bar.addWidget(self.later)
        outer.addLayout(bar)

        # Which verse is sounding. The only sign of it on the twelve verses whose words cannot
        # be lit, and a useful one on the rest.
        self.saying = QtWidgets.QLabel()
        self.saying.setObjectName("sayingVerse")
        bar.addWidget(self.saying)

        self.spread = Spread(self.win)
        self.spread.turned.connect(self.say_where)
        outer.addWidget(self.spread, 1)

        # Reciting state. at_verse is an index into the surah, not a verse number.
        self.reciting = False
        self.at_verse = 0
        self.waiting = False            # the recording has been asked for and is not here yet
        self.waited = 0.0               # seconds spent waiting for it
        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(50)     # often enough that a word lights when it is said
        self.follow.timeout.connect(self.tick)

    def open(self, number: int) -> None:
        if self.reciting:
            self.stop_reciting()
        self.number = number
        surah = self.quran.surah(number)
        if surah is not None:
            self.title.setText(f"{surah.number}. {surah.name} · {surah.arabic}")
        self.reload()

    def meaning_language(self) -> str:
        """Which meaning to set beside the Arabic: the mat's own language, or none.

        "" means no meaning, and the spread then opens the Arabic across BOTH pages instead of
        putting the meaning on the left -- which is what "Arabic only" in Settings comes down
        to by the time it reaches this screen. The Qur'an has no Arabic translation of itself,
        so asking for the meaning in Arabic is asking for no meaning.
        """
        from .ui import ARABIC_ONLY
        lang = self.win.settings.lang
        if lang == ARABIC_ONLY or lang not in self.quran.languages():
            return ""
        return lang

    def reload(self) -> None:
        lang = self.meaning_language()
        self.spread.show_surah(self.quran.verses(self.number, lang), rtl_meaning=(lang in RTL))
        self.say_where()

    def match_buttons(self) -> None:
        """Make the play button the same size as Back beside it.

        Done here rather than in the stylesheet because it cannot be written there: "Back" is
        Retour in French and Volver in Spanish, so Back's width is only known once it has been
        styled and laid out, while the glyph is always one character wide. Setting it at build
        time did nothing at all -- the stylesheet had not been applied yet, so it matched a
        size that was about to change.
        """
        wanted = self.back_button.size()
        if wanted.width() > 0:
            # Twice as tall as Back, and square, so the mark inside it can double. Matching
            # Back exactly is what kept it small.
            big = QtCore.QSize(wanted.height() * 2, wanted.height() * 2)
            if self.recite_button.size() != big:
                self.recite_button.setFixedSize(big)
                self.draw_recite_mark()

    def draw_recite_mark(self) -> None:
        """Redraw the mark at the button's size and the theme's ink."""
        from .ui import play_icon
        from .theme import palette
        # The mark keeps its share of the button; the button is what doubled, so the mark
        # doubles with it. Scaling both would draw an icon larger than the square it sits in,
        # and Qt would quietly crop it.
        side = max(self.win.px(30), int(self.recite_button.height() * 0.62))
        icon = play_icon(side, palette().ink, stop=self.reciting_now)
        self.recite_button.setIcon(QtGui.QIcon(icon))
        self.recite_button.setIconSize(icon.size())

    def showEvent(self, ev):
        super().showEvent(ev)
        self.match_buttons()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.match_buttons()

    def say_where(self) -> None:
        """Only the arrows now: live while there is a page that way, greyed out at the end."""
        self.earlier.setEnabled(self.spread.at > 0)
        self.later.setEnabled(self.spread.at < self.spread.pages_count - 1)

    def turn(self, forward: bool) -> bool:
        """The ring button and the arrow keys turn pages too, not only a finger."""
        return self.spread.turn(forward)

    # Reciting

    def can_recite(self) -> bool:
        return (self.win.recitation.available
                and self.win.word_times.known(self.number))

    def toggle_reciting(self) -> None:
        self.stop_reciting() if self.reciting else self.start_reciting()

    def start_reciting(self) -> None:
        """Begin at the top of the page being looked at, not at the top of the surah: somebody
        on page nine of Al-Baqarah wants to hear page nine."""
        if not self.spread.verses:
            return
        if not self.can_recite():
            self.saying.setText(self.win.t("quran.cannot_recite"))
            return
        start, _end = self.spread.pages[max(0, min(self.spread.at, len(self.spread.pages) - 1))]
        self.reciting = True
        self.at_verse = start
        self.reciting_now = True
        self.draw_recite_mark()
        self.recite_button.setToolTip(self.win.t("quran.stop_reciting"))
        self.begin_verse()
        self.follow.start()

    def stop_reciting(self, said: str = "") -> None:
        """Stop, and leave [said] in the bar. Stopping used to clear the bar unconditionally,
        which wiped the very message explaining why it had stopped -- so it reads what it is
        told to read, and the default is nothing."""
        self.follow.stop()
        self.reciting = False
        self.waiting = False
        self.win.recitation.stop()
        self.spread.clear_highlight()
        self.saying.setText(said)
        self.reciting_now = False
        self.draw_recite_mark()
        self.recite_button.setToolTip(self.win.t("quran.recite"))

    def begin_verse(self) -> None:
        """Ask for this verse's recording and the few after it, and play as soon as it lands."""
        verses = self.spread.verses
        if not 0 <= self.at_verse < len(verses):
            return self.stop_reciting()
        page = self.spread.page_of(self.at_verse)
        if page is not None and page != self.spread.at:
            self.spread.go_to(page)          # turn to the verse being recited
        number = verses[self.at_verse].number
        self.saying.setText(f"{self.number}:{number}")
        soon = [(self.number, verses[i].number)
                for i in range(self.at_verse, min(len(verses), self.at_verse + 4))]
        self.win.verses.want(soon)
        self.waiting = True
        self.waited = 0.0
        self.play_now()

    def play_now(self) -> bool:
        """Play the verse if its recording is here. Quietly does nothing if it is not yet."""
        verses = self.spread.verses
        number = verses[self.at_verse].number
        if not self.win.verses.have(self.number, number):
            if self.win.verses.gave_up_on(self.number, number) or self.waited >= PATIENCE:
                self.stop_reciting(self.win.t("quran.cannot_recite"))
            return False
        self.waiting = False
        path = self.win.verses.path_for(self.number, number)
        if not self.win.recitation.play(path, Span(0.0, WHOLE)):
            self.stop_reciting(self.win.t("quran.cannot_recite"))
            return False
        return True

    def tick(self) -> None:
        """Fifty times a second: light the word being said, and move on at the end of a verse."""
        if not self.reciting:
            return
        if self.waiting:
            self.waited += self.follow.interval() / 1000.0
            self.play_now()
            return
        position = self.win.recitation.position()
        if position is None and not self.win.recitation.busy:
            self.at_verse += 1              # that verse is done; on to the next
            self.spread.clear_highlight()
            if self.at_verse >= len(self.spread.verses):
                return self.stop_reciting()
            return self.begin_verse()
        if position is None:
            return
        number = self.spread.verses[self.at_verse].number
        if self.win.word_times.whole_only(self.number, number):
            # One of the twelve where the two texts disagree about where a word ends. Lighting
            # a word here would light the wrong one, so none is lit and the bar says the verse.
            self.spread.clear_highlight()
            return
        word = self.win.word_times.word_at(self.number, number, position)
        self.spread.highlight_at(self.at_verse, word)

    def follow_theme(self) -> None:
        self.spread.follow_theme()
