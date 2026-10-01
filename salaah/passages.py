"""The du'as and the six kalima: short pieces read whole, on the big screen.

Nothing here paginates. A surah can run to thirty pages and needs a book; a du'a is a few lines
and needs a page. So one passage fills the screen: the Arabic set as large as it will go, the
transliteration under it for somebody still learning the letters, and the meaning under that.

The two sections are the same shape on disk and the same shape on screen, which is why one module
serves both. What differs is where the words came from: the du'as are slices of the Qur'an,
checked verse by verse against it, while the kalima were written out from knowledge and then
read over by Harry, which is what the file's "reviewed" flag records.

The kalima also have a recording each, and per-word times so the word being said goes red. Those
times are estimated rather than measured -- see tools/build_kalima_times.py for exactly which
parts of them are trustworthy.

Correcting either file needs no change to the app. They are read off the disk each time a
passage is opened.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .audio import WHOLE, Span
from .mosque import MosqueScreen
from .qt import QtCore, QtWidgets, Qt, Signal
from .render import Fonts, TextBox

# The Arabic is never drawn smaller than this (at 1080p), nor larger.
ARABIC_FLOOR = 34
ARABIC_CAP = 150

SECTIONS = ("duas", "kalima")
RTL = ("ur",)

# The play button, as a glyph rather than a word: the reader's bar is crowded enough.
PLAY = "\u25b6"
STOP = "\u25a0"


@dataclass(frozen=True)
class Passage:
    key: str
    title: str
    ref: str               # "2:201", or "The Word of Purity"
    arabic: str
    said: str              # the transliteration
    cats: tuple = ()       # the du'a kinds it is filed under; a du'a can sit
                           # under more than one, and most of them do
    text: dict = field(default_factory=dict)      # language -> meaning
    trimmed: tuple = ()    # languages showing only the supplication, not the whole verse
    audio: str = ""        # a file under assets/audio, if there is a recording
    times: tuple = ()      # (start_ms, end_ms) per word of the Arabic
    estimated: bool = True  # whether those times were measured or worked out

    def word_at(self, seconds: float) -> int | None:
        """Which word is sounding, or None between words and after the last."""
        when = seconds * 1000.0
        for i, span in enumerate(self.times):
            if span[0] <= when < span[1]:
                return i
        return None

    def meaning(self, lang: str) -> str:
        """The meaning in that language, or in English if that is all there is.

        The kalima only have English. Showing English to somebody who chose French is not
        ideal, but it beats an empty half of the screen with no explanation.
        """
        got = self.text.get(lang, "")
        return got or self.text.get("en", "")

    def opening(self, words: int = 4) -> str:
        return " ".join(self.arabic.split()[:words])


class Passages:
    """One section read off the disk, and whether its words have been checked."""

    def __init__(self, assets: Path, section: str, folder: str = "duas"):
        # The folder is separate from the section because content/duas already holds a
        # hadith.json -- the thirty-eight du'as lifted out of hadith, which is a build
        # intermediate and not a section of the mat. The sayings have a folder of their own.
        self.path = Path(assets) / "content" / folder / f"{section}.json"
        self.section = section
        self._items: list[Passage] | None = None
        self._reviewed = True

    @property
    def there(self) -> bool:
        return self.path.is_file()

    @property
    def reviewed(self) -> bool:
        self.items                       # reading the file is what settles this
        return self._reviewed

    @property
    def items(self) -> list[Passage]:
        if self._items is not None:
            return self._items
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._items = []
            return self._items
        # Either a plain list, or a wrapper that also says whether it has been checked.
        rows = raw if isinstance(raw, list) else raw.get("items", [])
        if isinstance(raw, dict):
            self._reviewed = bool(raw.get("reviewed", True))
        self._items = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("arabic"):
                continue            # a half-copied file shows what it has, not an error screen
            self._items.append(Passage(
                key=str(row.get("key", "")),
                cats=tuple(str(c) for c in (row.get("cats") or [])),
                title=str(row.get("title", "")),
                ref=str(row.get("ref", "")),
                arabic=str(row["arabic"]),
                said=str(row.get("said", "")),
                text={k: str(v) for k, v in (row.get("text") or {}).items()},
                trimmed=tuple(row.get("trimmed") or ()),
                audio=str(row.get("audio", "")),
                # Only as many word times as there are words: a recording timed against an
                # older wording must not light a word that is no longer there.
                times=tuple(tuple(int(x) for x in pair)
                            for pair in (row.get("times") or [])
                            )[:len(str(row["arabic"]).split())],
                estimated=bool(row.get("estimated", True)),
            ))
        return self._items

    def languages(self) -> tuple:
        """Every language any passage in this section has a meaning in, in the app's order."""
        order = ("en", "fr", "ur", "es", "zh")
        have = {lang for item in self.items for lang, text in item.text.items() if text}
        return tuple(lang for lang in order if lang in have)

    def at(self, index: int) -> Passage | None:
        return self.items[index] if 0 <= index < len(self.items) else None


class PassageList(QtWidgets.QWidget):
    """The pieces in a section, one touchable row each."""

    chose = Signal(int)

    def __init__(self, window, passages: Passages, heading: str):
        super().__init__()
        self.win = window
        self.passages = passages
        self.heading_text = heading
        self.setObjectName("passageList")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(self.win.px(20), self.win.px(10), self.win.px(20), 0)
        self.title = QtWidgets.QLabel(heading)
        self.title.setObjectName("readerTitle")
        bar.addWidget(self.title)
        bar.addStretch(1)
        outer.addLayout(bar)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")      # so it gets the wide, touchable slider
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        self.rows = QtWidgets.QVBoxLayout(inner)
        self.rows.setContentsMargins(self.win.px(20), self.win.px(10),
                                     self.win.px(20), self.win.px(20))
        self.rows.setSpacing(self.win.px(10))
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, 1)
        self.only = None            # a category name, or None for the whole section
        self.filled = None          # which filter the rows standing here were built for

    def showEvent(self, ev):
        self.fill()
        super().showEvent(ev)

    def show_only(self, cat: str | None, heading: str = "") -> None:
        """Narrow the list to one category, or widen it again with None.

        The row still carries its place in the WHOLE section, so opening one goes through the
        same door as before -- the filter changes what is listed, not what anything is called.
        """
        self.only = cat or None
        if heading:
            self.title.setText(heading)
        self.fill()

    def wanted(self) -> list[tuple[int, Passage]]:
        return [(i, item) for i, item in enumerate(self.passages.items)
                if self.only is None or self.only in item.cats]

    def fill(self) -> None:
        want = (self.only, len(self.passages.items))
        if self.filled == want:
            return
        self.filled = want
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
        for i, item in self.wanted():
            self.rows.addWidget(self.row(i, item))
        self.rows.addStretch(1)

    def row(self, index: int, item: Passage) -> QtWidgets.QWidget:
        b = QtWidgets.QPushButton()
        b.setObjectName("surahRow")          # the same row as the surah list: one look, not two
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(self.win.px(96))
        b.clicked.connect(lambda _=False, n=index: self.chose.emit(n))

        lay = QtWidgets.QHBoxLayout(b)
        lay.setContentsMargins(self.win.px(16), self.win.px(8), self.win.px(16), self.win.px(8))
        lay.setSpacing(self.win.px(12))

        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        top = QtWidgets.QLabel(item.title)
        top.setObjectName("surahName")
        under = QtWidgets.QLabel(item.ref)
        under.setObjectName("surahMeaning")
        names.addWidget(top)
        names.addWidget(under)
        lay.addLayout(names, 1)

        arabic = QtWidgets.QLabel(item.opening())
        arabic.setObjectName("surahArabic")
        arabic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(arabic)
        return b

    def to_the_top(self) -> None:
        self.fill()
        self.scroll.verticalScrollBar().setValue(0)

    def retitle(self) -> None:
        self.title.setText(self.heading_text)


class PassageReader(QtWidgets.QWidget):
    """One passage, whole: Arabic, how it is said, and what it means."""

    back = Signal()

    def __init__(self, window, passages: Passages):
        super().__init__()
        self.win = window
        self.passages = passages
        self.at = 0
        self.setObjectName("passageReader")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(self.win.px(16), self.win.px(8), self.win.px(16), self.win.px(16))
        outer.setSpacing(self.win.px(8))

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(self.win.px(12))
        self.back_button = QtWidgets.QPushButton(self.win.t("corner.back_list"))
        self.back_button.setObjectName("backButton")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.back.emit)
        bar.addWidget(self.back_button)

        self.say_button = QtWidgets.QPushButton(PLAY)
        self.say_button.setObjectName("reciteButton")
        self.say_button.setToolTip(self.win.t("quran.recite"))
        self.say_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.say_button.clicked.connect(self.toggle_saying)
        bar.addWidget(self.say_button)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("readerTitle")
        bar.addWidget(self.title)
        bar.addStretch(1)

        self.tongues = QtWidgets.QHBoxLayout()
        self.tongues.setSpacing(self.win.px(6))
        self.buttons: dict[str, QtWidgets.QPushButton] = {}
        bar.addLayout(self.tongues)

        self.earlier = QtWidgets.QPushButton("‹")
        self.later = QtWidgets.QPushButton("›")
        for b, forward in ((self.earlier, False), (self.later, True)):
            b.setObjectName("turnPage")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, f=forward: self.turn(f))
        self.where = QtWidgets.QLabel()
        self.where.setObjectName("readerWhere")
        bar.addWidget(self.earlier)
        bar.addWidget(self.where)
        bar.addWidget(self.later)
        outer.addLayout(bar)

        self.arabic = TextBox(Fonts.arabic(self.win.settings.arabic_font),
                              ARABIC_FLOOR, ARABIC_CAP, rtl=True, by_word=True)
        self.arabic.scale = self.win.s
        outer.addWidget(self.arabic, 3)

        self.said = QtWidgets.QLabel()
        self.said.setObjectName("passageSaid")
        self.said.setWordWrap(True)
        self.said.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.said, 0)

        self.meaning = QtWidgets.QLabel()
        self.meaning.setObjectName("passageMeaning")
        self.meaning.setWordWrap(True)
        self.meaning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.meaning, 0)

        self.saying = False
        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(50)
        self.follow.timeout.connect(self.tick)

        outer.addSpacing(self.win.px(4))

    # Saying it aloud

    def can_say(self) -> bool:
        item = self.passages.at(self.at)
        return bool(item and item.audio and item.times
                    and self.win.recitation.available
                    and (self.win.assets / "audio" / item.audio).is_file())

    def toggle_saying(self) -> None:
        self.stop_saying() if self.saying else self.start_saying()

    def start_saying(self) -> None:
        item = self.passages.at(self.at)
        if item is None or not self.can_say():
            return
        if not self.win.recitation.play(self.win.assets / "audio" / item.audio,
                                        Span(0.0, WHOLE)):
            return
        self.saying = True
        self.say_button.setText(STOP)
        self.say_button.setToolTip(self.win.t("quran.stop_reciting"))
        self.follow.start()

    def stop_saying(self) -> None:
        self.follow.stop()
        self.saying = False
        self.win.recitation.stop()
        self.arabic.set_highlight(None)
        self.say_button.setText(PLAY)
        self.say_button.setToolTip(self.win.t("quran.recite"))

    def tick(self) -> None:
        """Light the word being said. One line of Arabic, so the line is always nought."""
        if not self.saying:
            return
        position = self.win.recitation.position()
        if position is None and not self.win.recitation.busy:
            return self.stop_saying()
        if position is None:
            return
        item = self.passages.at(self.at)
        word = item.word_at(position) if item else None
        self.arabic.set_highlight(None if word is None else (0, word))

    def build_tongues(self) -> None:
        """The language buttons, made once the section's languages are known."""
        if self.buttons:
            return
        for lang in self.passages.languages():
            b = QtWidgets.QPushButton(self.win.pack_name(lang))
            b.setObjectName("tongue")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, l=lang: self.set_language(l))
            self.buttons[lang] = b
            self.tongues.addWidget(b)

    def open(self, index: int) -> None:
        if getattr(self, "saying", False):
            self.stop_saying()
        self.build_tongues()
        self.at = max(0, min(index, len(self.passages.items) - 1))
        self.reload()

    def language(self) -> str:
        """Which meaning to show. The reading language if this section has it, else English."""
        wanted = self.win.settings.quran_lang or "en"
        return wanted if wanted in self.passages.languages() else "en"

    def reload(self) -> None:
        item = self.passages.at(self.at)
        if item is None:
            self.title.setText("")
            self.arabic.set_lines([])
            self.said.setText("")
            self.meaning.setText("")
            self.say_where()
            return
        lang = self.language()
        for key, b in self.buttons.items():
            b.setChecked(key == lang)
        self.title.setText(f"{item.title} · {item.ref}" if item.ref else item.title)
        # The sayings show no Arabic at all. Harry asked for the translation and the play
        # button and nothing else, and a reader that still opened on the Arabic would be the
        # one screen in the section that disagreed with the board in front of it. The Arabic
        # stays in hadith.json, because it is what the wording was checked against and what any
        # reviewer will read first; it is simply not on the glass.
        sayings = self.passages.section == "hadith"
        self.arabic.set_lines([] if sayings else [item.arabic])
        self.arabic.setVisible(not sayings)
        # The du'as show no transliteration; the kalima still do. Same reader, different
        # sections, and the du'as are the ones where it appeared on some and not others.
        self.said.setText("" if self.passages.section in ("duas", "hadith") else item.said)
        self.said.setVisible(self.passages.section not in ("duas", "hadith"))
        self.meaning.setText(item.meaning(lang))
        rtl = lang in RTL
        self.meaning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meaning.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl
                                        else Qt.LayoutDirection.LeftToRight)
        self.say_where()

    def set_language(self, lang: str) -> None:
        self.win.settings.quran_lang = lang
        self.win.persist()
        self.reload()

    def turn(self, forward: bool) -> bool:
        """The next or previous passage. The ring button turns these as it turns pages."""
        wanted = self.at + (1 if forward else -1)
        if not 0 <= wanted < len(self.passages.items):
            return False
        self.at = wanted
        self.reload()
        return True

    def say_where(self) -> None:
        total = max(1, len(self.passages.items))
        self.where.setText(self.win.t("corner.item", at=self.at + 1, of=total))
        self.earlier.setEnabled(self.at > 0)
        self.later.setEnabled(self.at < len(self.passages.items) - 1)

    def follow_theme(self) -> None:
        self.arabic.update()


class ArchMenu(QtWidgets.QWidget):
    """A mosque whose arches are a menu, with the clock on its dome.

    The same drawing, the same clock, the same sun and moon and birds and stars as the front
    door -- because it is the same widget, pointed at a different folder. The six kalima are
    chosen by touching an arch, which is a better thing to reach for on a mat than a row of
    words, and it tells a child which of the six he is about to hear before he can read either
    language.

    The minaret glow is off here. On the main screen it means "no prayer is due just now";
    on a menu of things to read it would be saying something that is not about anything.
    """

    chose = Signal(int)        # which arch, counting from one
    leave = Signal()

    def __init__(self, window, folder: str, clock_font: str = ""):
        super().__init__()
        self.win = window
        self.setObjectName("archMenu")
        self.mosque = MosqueScreen(self.win.assets, clock_font, folder=folder, idle_glow=False)
        self.mosque.chosen.connect(self.picked)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(self.win.px(20), self.win.px(10), self.win.px(20), 0)
        # No bar of its own: the way home is in the banner above, so the mosque gets the
        # whole screen and lines up with the front door's.
        outer.addWidget(self.mosque, 1)

    @property
    def ready(self) -> bool:
        return self.mosque.ready

    def picked(self, name: str) -> None:
        """The arches are named for their numbers, so the name is the number."""
        try:
            self.chose.emit(int(name))
        except ValueError:
            pass                    # a drawing whose arches are named something else

    def follow_clock(self, text: str, sun_up: bool, through: float) -> None:
        """Driven from the window's ten-second clock, the same one the front door uses."""
        self.mosque.set_time(text)
        self.mosque.set_sky(sun_up, through)

    # Nothing here starts or stops the birds: MosqueScreen already does that in its own
    # showEvent and hideEvent. Doing it again here looked like care and was dead code -- the
    # test passed just as happily with it deleted, which is how it was found.

    def retitle(self) -> None:
        pass
