"""The du'as of one kind, laid out so they can all be read at once.

A list of rows was right when there were ten du'as in one heap and you scrolled to find one.
Now they are sorted into kinds and a kind holds two to five, which fits on the screen -- so
there is no reason to make somebody standing over the mat scroll at all, and every good reason
not to: the screen is a few feet away and a thumb on a scrollbar is the fiddliest thing on it.

So: two columns with a thick rule between them, filled down one column and then the other. Each
du'a shows its name, its Arabic, and the meaning under that, with a play mark beside it. Five is
the most any kind holds, which is three down the first column and two down the second.

If a kind ever grows past what fits, the board scrolls rather than shrinking the Arabic to
nothing -- an unreadable du'a is worse than a scrollbar.
"""
from __future__ import annotations

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette

DOWN = 3               # du'as down a column before the next column is started
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
        lay.setContentsMargins(window.px(14), window.px(10), window.px(14), window.px(12))
        lay.setSpacing(window.px(6))

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

        self.arabic = QtWidgets.QLabel(item.arabic)
        self.arabic.setObjectName("duaCardArabic")
        self.arabic.setWordWrap(True)
        self.arabic.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.arabic.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        lay.addWidget(self.arabic)

        # The transliteration, where there is one. The Qur'anic du'as carry it because it came
        # out of the checked Qur'an text; the ones from hadith do not yet, and an empty line is
        # left out rather than shown as a gap.
        self.said = QtWidgets.QLabel(item.said)
        self.said.setObjectName("duaCardSaid")
        self.said.setWordWrap(True)
        lay.addWidget(self.said)
        if not item.said.strip():
            self.said.hide()

        self.meaning = QtWidgets.QLabel(meaning)
        self.meaning.setObjectName("duaCardMeaning")
        self.meaning.setWordWrap(True)
        lay.addWidget(self.meaning)
        lay.addStretch(1)
        self.draw_mark(False)

    def draw_mark(self, playing: bool) -> None:
        from .ui import play_icon
        side = self.win.px(46)
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

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(window.px(20), 0, window.px(20), window.px(14))
        row.addStretch(1)
        self.back_button = QtWidgets.QPushButton(window.t("corner.back"))
        self.back_button.setObjectName("backButton")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row.addWidget(self.back_button)
        outer.addLayout(row)

        self.cards: list[DuaCard] = []
        self.rule = None
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

    def show_only(self, cat: str | None, heading: str = "") -> None:
        self.only = cat or None
        if heading:
            self.title.setText(heading)
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
        want = (self.only, len(self.passages.items), self.language())
        if self.filled == want:
            return
        self.filled = want
        self.clear()
        mine = self.wanted()
        lang = self.language()
        # Shared evenly between the two columns rather than filling the first: three du'as
        # down the left with nothing on the right is not the two columns that were asked for.
        # Three is as far down as a column goes, so a kind that ever grows past six scrolls.
        down = min(DOWN, max(1, (len(mine) + 1) // 2))
        for place, (index, item) in enumerate(mine):
            card = DuaCard(self.win, index, item, item.meaning(lang))
            card.opened.connect(self.chose.emit)
            card.play.connect(self.play.emit)
            (self.left if place < down else self.right).addWidget(card)
            self.cards.append(card)
        self.left.addStretch(1)
        self.right.addStretch(1)
        if len(mine) > 1:
            self.rule = Rule(self.win)
            self.across.insertWidget(1, self.rule)

    def to_the_top(self) -> None:
        self.scroll.verticalScrollBar().setValue(0)

    def showEvent(self, ev):
        self.fill()
        super().showEvent(ev)

    def follow_theme(self) -> None:
        for card in self.cards:
            card.draw_mark(False)
        if self.rule is not None:
            self.rule.update()

    def retitle(self) -> None:
        self.back_button.setText(self.win.t("corner.back"))
        self.filled = None          # the meanings are in a language that may have changed
        self.fill()
