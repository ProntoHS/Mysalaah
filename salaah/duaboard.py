"""Two du'as of one kind, side by side, as large as the screen will draw them.

The board used to show every du'a of a kind, up to five, which meant the Arabic had to be small
enough for the worst case. That is the wrong way round: this screen is read from a few feet away
while somebody is stood on the mat, so the words should be as big as the glass allows and the
number on screen should give way, not the size.

So: exactly two, one each side of a thick rule, at more than half again the old size, with
nothing else on the screen -- no Back button along the bottom, because that strip was costing
height that the Arabic wanted and there are two other ways back (the strip above, and the Du'as
tile on the 7in).

Which two is picked fresh every time the kind is opened. Every kind holds at least three, so
the pair changes, and over a few visits the whole kind is seen. Picking at the moment the kind
is opened rather than once at start-up is deliberate: it means going back in gives you different
du'as rather than the same ones until the mat is restarted.
"""
from __future__ import annotations

import random

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts, TextBox
from .theme import palette

ON_SCREEN = 2          # du'as shown at once: one each side of the rule
# The Arabic is drawn as large as its half of the screen will take. A single size cannot serve
# both a two-line du'a and 2:286 -- set big enough for the short one the long one runs off the
# bottom, and set small enough for the long one the short one wastes the glass. So the box picks,
# between these, and every du'a fits by construction rather than by luck.
ARABIC_FLOOR = 30
ARABIC_CAP = 110
RULE = 6               # the line between the columns, in unscaled pixels: thick, as asked


class DuaCard(QtWidgets.QFrame):
    """One du'a: its name, the Arabic, the meaning underneath, and a play mark."""

    play = Signal(int)
    opened = Signal(int)

    def __init__(self, window, index: int, item, meaning: str):
        super().__init__()
        self.win = window
        self.index = index
        self.item = item
        self.setObjectName("duaCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(window.px(22), window.px(16), window.px(22), window.px(18))
        lay.setSpacing(window.px(10))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(window.px(10))
        self.button = QtWidgets.QToolButton()
        self.button.setObjectName("duaPlay")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.button.setToolTip(window.t("quran.recite"))
        self.button.clicked.connect(lambda: self.play.emit(self.index))
        top.addWidget(self.button, 0, Qt.AlignmentFlag.AlignTop)

        self.name = QtWidgets.QLabel(item.title)
        self.name.setObjectName("duaCardName")
        self.name.setWordWrap(True)
        top.addWidget(self.name, 1)
        lay.addLayout(top)

        # by_word, so a word can go red while it is being said. It costs nothing here: the
        # card holds one du'a and is not paginated, so the tighter word-by-word layout cannot
        # change where anything breaks.
        self.arabic = TextBox(Fonts.arabic(window.settings.arabic_font),
                              ARABIC_FLOOR, ARABIC_CAP, rtl=True, by_word=True)
        self.arabic.scale = window.s
        self.arabic.set_lines([item.arabic])
        lay.addWidget(self.arabic, 1)

        # No transliteration here. Ten of the forty-eight du'as had one and thirty-eight did
        # not, so it was a line that appeared on some cards and not others; and now that every
        # du'a can be heard read aloud, the way to learn how it sounds is to press play rather
        # than to read it in English letters. The room goes to the Arabic.

        self.meaning = QtWidgets.QLabel(meaning)
        self.meaning.setObjectName("duaCardMeaning")
        self.meaning.setWordWrap(True)
        lay.addWidget(self.meaning)
        self.draw_mark(False)

    # Twice what it was. It is the thing on this screen most likely to be aimed at -- there is
    # one per card and it is now the only way to hear a du'a read -- and at 46 it was a quarter
    # of the size of the card it sat on, which on a touchscreen is a thumb hunting for a stamp.
    MARK = 92

    def draw_mark(self, playing: bool) -> None:
        from .ui import play_icon
        side = self.win.px(self.MARK)
        icon = play_icon(side, palette().ink, stop=playing)
        self.button.setIcon(QtGui.QIcon(icon))
        self.button.setIconSize(icon.size())
        self.button.setFixedSize(side + self.win.px(10), side + self.win.px(10))

    def mouseReleaseEvent(self, ev):
        if self.rect().contains(ev.position().toPoint()):
            self.opened.emit(self.index)
        super().mouseReleaseEvent(ev)


class Rule(QtWidgets.QWidget):
    """The line between the columns. A painted widget rather than a styled QFrame, because a
    frame's line is one pixel whatever the stylesheet says on some styles, and this one has to
    be thick enough to read from across the room."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("duaRule")
        self.setFixedWidth(window.px(RULE))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(palette().ink))


class DuaBoard(QtWidgets.QWidget):
    """Every du'a of one kind, in two columns."""

    chose = Signal(int)
    play = Signal(int)

    def __init__(self, window, passages):
        super().__init__()
        self.win = window
        self.passages = passages
        self.only = None
        self.setObjectName("duaBoard")
        # Which card is being read aloud, if any, and the clock that follows the words.
        self.said_by: DuaCard | None = None
        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(50)
        self.follow.timeout.connect(self.tick)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(window.px(20), window.px(10), window.px(20), 0)
        head.addStretch(1)
        self.title = QtWidgets.QLabel("")
        self.title.setObjectName("namePlate")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(self.title)
        head.addStretch(1)
        outer.addLayout(head)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Two boxes side by side rather than one grid. In a grid every card in a row is as tall
        # as the tallest of them, so a short du'a beside 2:286 sat in a great well of empty
        # space. Boxes let each column pack to its own contents.
        inner = QtWidgets.QWidget()
        self.across = QtWidgets.QHBoxLayout(inner)
        self.across.setContentsMargins(window.px(20), window.px(12),
                                       window.px(20), window.px(20))
        self.across.setSpacing(window.px(20))
        self.left = QtWidgets.QVBoxLayout()
        self.left.setSpacing(window.px(14))
        self.right = QtWidgets.QVBoxLayout()
        self.right.setSpacing(window.px(14))
        self.across.addLayout(self.left, 1)
        self.across.addLayout(self.right, 1)
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, 1)

        # No button strip along the bottom. It cost height the Arabic wanted, and there are two
        # other ways out of here: Main screen on the strip above, and the Du'as tile on the 7in,
        # which goes back to the kinds.
        self.cards: list[DuaCard] = []
        self.rule = None
        self.showing: list = []      # the pair picked for this visit
        self.filled = None

    def language(self) -> str:
        """Which meaning to show: the reading language if the du'as have it, else English --
        the same choice the reader makes, so the board and the reader never disagree."""
        wanted = self.win.settings.quran_lang or "en"
        return wanted if wanted in self.passages.languages() else "en"

    def wanted(self) -> list[tuple[int, object]]:
        """The du'as of this kind, each with its place in the WHOLE section -- so opening one
        goes through the same door as it always did."""
        return [(i, item) for i, item in enumerate(self.passages.items)
                if self.only is None or self.only in item.cats]

    def pick(self) -> list:
        """The two to show, chosen fresh. Every kind holds at least three, so this is a real
        choice and not the same pair every time."""
        mine = self.wanted()
        if len(mine) <= ON_SCREEN:
            return mine
        return random.sample(mine, ON_SCREEN)

    def show_only(self, cat: str | None, heading: str = "") -> None:
        """Open a kind. This is where the pair is drawn -- not in fill(), which runs again
        whenever the screen is shown, and would otherwise swap the du'as under somebody who had
        stepped into one and come back."""
        self.only = cat or None
        if heading:
            self.title.setText(heading)
        self.showing = self.pick()
        self.filled = None
        self.fill()

    def clear(self) -> None:
        for box in (self.left, self.right):
            while box.count():
                old = box.takeAt(0)
                if old.widget() is not None:
                    old.widget().deleteLater()
        while self.across.count() > 2:
            old = self.across.takeAt(1)
            if old.widget() is not None:
                old.widget().deleteLater()
        self.cards, self.rule = [], None

    def fill(self) -> None:
        want = (tuple(i for i, _ in self.showing), self.language())
        if self.filled == want:
            return
        self.stop_saying()          # the cards are about to go; the voice must not outlive them
        self.filled = want
        self.clear()
        lang = self.language()
        for place, (index, item) in enumerate(self.showing):
            card = DuaCard(self.win, index, item, item.meaning(lang))
            card.opened.connect(self.chose.emit)
            # Straight to the board's own player, with the card's place bound rather than the
            # du'a's number in the file: the board reads it here, so it is the board's business.
            card.play.connect(lambda _=0, k=place: self.say(k))
            (self.left if place == 0 else self.right).addWidget(card)
            self.cards.append(card)
        if len(self.showing) > 1:
            self.rule = Rule(self.win)
            self.across.insertWidget(1, self.rule)

    def to_the_top(self) -> None:
        self.scroll.verticalScrollBar().setValue(0)

    def showEvent(self, ev):
        self.fill()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Leaving the screen stops the voice. A recording left playing to an empty room is the
        # thing hush_passages exists to prevent, and the board is another way to start one.
        self.stop_saying()
        super().hideEvent(ev)

    def follow_theme(self) -> None:
        for card in self.cards:
            card.draw_mark(card is self.said_by)
        if self.rule is not None:
            self.rule.update()

    def retitle(self) -> None:
        self.filled = None          # the meanings are in a language that may have changed
        self.fill()

    # -- reading one aloud, here on the board -------------------------------------------------

    def can_say(self, card) -> bool:
        item = card.item
        return bool(item.audio and item.times and self.win.recitation.available
                    and (self.win.assets / "audio" / item.audio).is_file())

    def say(self, place: int) -> None:
        """The play mark on a card was pressed.

        It reads the du'a on the card, here, with the word going red as it is said. It used to
        open the du'a's own page and read it there, which meant the two-column screen vanished
        the moment you pressed play -- you lost the du'a beside it and the thing you had been
        looking at was replaced by a different arrangement of the same words. Pressing it again
        stops; pressing the other card's mark moves the voice across.
        """
        card = self.cards[place] if 0 <= place < len(self.cards) else None
        if card is None:
            return
        if card is self.said_by:
            return self.stop_saying()
        self.stop_saying()
        if not self.can_say(card):
            # No recording for this one. Open it rather than doing nothing, which is what the
            # mark did for as long as there were no recordings at all.
            return self.chose.emit(card.index)
        from .audio import WHOLE, Span
        if not self.win.recitation.play(self.win.assets / "audio" / card.item.audio,
                                        Span(0.0, WHOLE)):
            return
        self.said_by = card
        card.draw_mark(True)
        self.follow.start()

    def stop_saying(self) -> None:
        if self.said_by is None:
            return
        self.follow.stop()
        self.win.recitation.stop()
        self.said_by.arabic.set_highlight(None)
        self.said_by.draw_mark(False)
        self.said_by = None

    @property
    def saying(self) -> bool:
        return self.said_by is not None

    def tick(self) -> None:
        """Light the word being said. One du'a on the card, so the line is always nought."""
        if self.said_by is None:
            return
        position = self.win.recitation.position()
        if position is None and not self.win.recitation.busy:
            return self.stop_saying()
        if position is None:
            return
        word = self.said_by.item.word_at(position)
        self.said_by.arabic.set_highlight(None if word is None else (0, word))
