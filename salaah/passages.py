"""The du'as and the six kalima: short pieces read whole, on the big screen.

Nothing here paginates. A surah can run to thirty pages and needs a book; a du'a is a few lines
and needs a page. So one passage fills the screen: the Arabic set as large as it will go, the
transliteration under it for somebody still learning the letters, and the meaning under that.

The two sections are the same shape on disk and the same shape on screen, which is why one module
serves both. What differs is where the words came from, and the screen says so: the du'as are
slices of the Qur'an already checked verse by verse, while the kalima were written out from
knowledge and carry a line saying they are waiting to be read by somebody who reads Arabic. That
line goes when the file says reviewed.

Correcting either file needs no change to the app. They are read off the disk each time a
passage is opened.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .qt import QtWidgets, Qt, Signal
from .render import Fonts, TextBox

# The Arabic is never drawn smaller than this (at 1080p), nor larger.
ARABIC_FLOOR = 34
ARABIC_CAP = 150

SECTIONS = ("duas", "kalima")
RTL = ("ur",)


@dataclass(frozen=True)
class Passage:
    key: str
    title: str
    ref: str               # "2:201", or "The Word of Purity"
    arabic: str
    said: str              # the transliteration
    text: dict = field(default_factory=dict)      # language -> meaning
    trimmed: tuple = ()    # languages showing only the supplication, not the whole verse

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

    def __init__(self, assets: Path, section: str):
        self.path = Path(assets) / "content" / "duas" / f"{section}.json"
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
                title=str(row.get("title", "")),
                ref=str(row.get("ref", "")),
                arabic=str(row["arabic"]),
                said=str(row.get("said", "")),
                text={k: str(v) for k, v in (row.get("text") or {}).items()},
                trimmed=tuple(row.get("trimmed") or ()),
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
    leave = Signal()

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
        home = QtWidgets.QPushButton(self.win.t("settings.main_screen"))
        home.setObjectName("mainScreen")
        home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        home.clicked.connect(self.leave.emit)
        bar.addWidget(home)
        outer.addLayout(bar)

        # Said once, at the top of the list, rather than on every passage: a note repeated six
        # times reads as an apology, and once reads as a fact.
        self.waiting = QtWidgets.QLabel(self.win.t("corner.unchecked"))
        self.waiting.setObjectName("unchecked")
        self.waiting.setWordWrap(True)
        self.waiting.setContentsMargins(self.win.px(20), self.win.px(4), self.win.px(20), 0)
        outer.addWidget(self.waiting)

        self.scroll = QtWidgets.QScrollArea()
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
        self.filled = False

    def showEvent(self, ev):
        self.fill()
        super().showEvent(ev)

    def fill(self) -> None:
        if self.filled:
            return
        self.filled = True
        self.waiting.setVisible(not self.passages.reviewed)
        for i, item in enumerate(self.passages.items):
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
        self.waiting.setVisible(not self.passages.reviewed)
        self.scroll.verticalScrollBar().setValue(0)

    def retitle(self) -> None:
        self.title.setText(self.heading_text)
        self.waiting.setText(self.win.t("corner.unchecked"))


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
                              ARABIC_FLOOR, ARABIC_CAP, rtl=True)
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

        # Also said here, not only on the list. The list is where you choose; this is where you
        # read and believe it, and that is the screen the caveat belongs on.
        self.waiting = QtWidgets.QLabel(self.win.t("corner.unchecked"))
        self.waiting.setObjectName("unchecked")
        self.waiting.setWordWrap(True)
        self.waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting.setVisible(False)
        outer.addWidget(self.waiting, 0)
        outer.addSpacing(self.win.px(4))

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
            self.waiting.setVisible(False)
            self.say_where()
            return
        lang = self.language()
        self.waiting.setVisible(not self.passages.reviewed)
        for key, b in self.buttons.items():
            b.setChecked(key == lang)
        self.title.setText(f"{item.title} · {item.ref}" if item.ref else item.title)
        self.arabic.set_lines([item.arabic])
        self.said.setText(item.said)
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
