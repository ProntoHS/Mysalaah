"""Drawing the prayer screen: Arabic above English on the left, the posture figure on the right.

Text is drawn rather than baked into pictures, so it can be as large as the screen allows. Each
box picks the biggest font size that fits, never smaller than a size readable from standing.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .theme import palette

# Smallest sizes we accept, as a fraction of screen height at 1080p. Below these, the text is
# split over more pages instead of shrunk. Arabic needs more height for its vowel marks.
MIN_ARABIC_PX = 46      # the size we would like to keep to
MIN_ENGLISH_PX = 30
MAX_ARABIC_PX = 340     # a single short line should fill its box
MAX_ENGLISH_PX = 64
FLOOR_PX = 20           # but a long surah is shown whole, however small that makes it


# Arabic faces the user can pick between, in the order they appear in Settings.
# key -> (font files, name shown on screen). All are SIL Open Font License 1.1.
FONTS = {
    "scheherazade": (("ScheherazadeNew-Bold.ttf", "ScheherazadeNew-Regular.ttf"), "Clear naskh"),
    "noto": (("NotoNaskhArabic-Regular.ttf",), "Noto naskh"),
    "amiri": (("Amiri-Regular.ttf",), "Traditional"),
}
DEFAULT_FONT = "scheherazade"

# Faces for scripts the system font cannot be relied on to have. Raspberry Pi OS ships neither
# Chinese nor Devanagari, so without these the meaning column would come out as empty boxes.
# Each is cut down to only the characters its translation uses, which is why they are a few
# hundred kilobytes rather than the ten megabytes a whole CJK face would cost.
SCRIPT_FONTS = {
    "han": "NotoSansSC-Subset.ttf",
    "devanagari": "NotoSansDevanagari-Subset.ttf",
}


class Fonts:
    """Loads the bundled Arabic faces. Falls back to whatever the system has."""

    families: dict[str, str] = {}
    scripts: dict[str, str] = {}
    english_family = ""

    @classmethod
    def load(cls, assets: Path) -> None:
        for key, (files, _) in FONTS.items():
            for name in files:
                path = assets / "fonts" / name
                if not path.is_file():
                    continue
                fid = QtGui.QFontDatabase.addApplicationFont(str(path))
                families = QtGui.QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
                if families and key not in cls.families:
                    cls.families[key] = families[0]
        for key, name in SCRIPT_FONTS.items():
            path = assets / "fonts" / name
            if not path.is_file():
                continue
            fid = QtGui.QFontDatabase.addApplicationFont(str(path))
            families = QtGui.QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
            if families:
                cls.scripts[key] = families[0]
        cls.english_family = QtWidgets.QApplication.font().family()

    @classmethod
    def arabic(cls, key: str = DEFAULT_FONT) -> str:
        return cls.families.get(key) or cls.families.get(DEFAULT_FONT) or "serif"

    @classmethod
    def for_text(cls, text: str) -> str:
        """The face to write this text in.

        Chosen from the letters themselves rather than from the language, so a translation added
        later gets the right face without anything here being changed, and so a bundled face is
        only used where the system one would have failed.
        """
        if any(is_han(ch) for ch in text):
            return cls.scripts.get("han") or cls.english_family
        if any("ऀ" <= ch <= "ॿ" for ch in text):
            return cls.scripts.get("devanagari") or cls.english_family
        return cls.english_family


LINE_GAP = 0.30   # space between lines, as a share of the font size


def fit_size(lines: list[str], width: int, height: int, family: str, low: int, high: int,
             spacing: float = LINE_GAP, weight: int = 400) -> tuple[int, int]:
    """Largest font size at which [lines] fit in the box, and the height they then take.
    Returns [low] even if that doesn't fit, so text is never shrunk past readable."""
    best = low
    best_h = _height(lines, width, family, low, spacing, weight)
    lo, hi = low, high
    while lo <= hi:
        mid = (lo + hi) // 2
        h = _height(lines, width, family, mid, spacing, weight)
        if h <= height:
            best, best_h, lo = mid, h, mid + 1
        else:
            hi = mid - 1
    return best, best_h


def line_heights(lines: list[str], width: int, family: str, px: int, weight: int = 400) -> list[int]:
    font = QtGui.QFont(family)
    font.setPixelSize(px)
    font.setWeight(QtGui.QFont.Weight(weight))
    fm = QtGui.QFontMetrics(font)
    flags = int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft)
    out = []
    for line in lines:
        r = fm.boundingRect(QtCore.QRect(0, 0, width, 10_000), flags, line)
        out.append(max(r.height(), fm.height()))
    return out


def _height(lines: list[str], width: int, family: str, px: int, spacing: float = LINE_GAP,
            weight: int = 400) -> int:
    """Exactly what TextBox.paintEvent will take up: the lines plus the gaps between them."""
    heights = line_heights(lines, width, family, px, weight)
    if not heights:
        return 0
    return sum(heights) + int(px * spacing) * (len(heights) - 1)


@dataclass
class PlacedWord:
    text: str
    line: int
    x: int
    y: int
    width: int
    height: int


LEADING = 0.80     # the closest the lines may ever be drawn, as a share of the font's line box
INK_ROOM = 0.08    # and always this much of the line box clear of the tallest letters
MEASURE_PX = 120   # the size the letters are measured at; the proportion holds at any size

_ink_share: dict[tuple, float] = {}


def ink_share(lines: list[str], family: str, weight: int) -> float:
    """How much of its own line box this text's letters actually use, at the most.

    A font's line height leaves room for every mark it could ever draw, not the marks this text
    really has. Scheherazade reserves about a third more than these verses need, which on a
    seven-line screen is a third of the height given over to nothing, and the words are fitted
    to the room left. Amiri uses nearly all of its line box, and Al-Fatiha in Amiri genuinely
    needs it. So the room is measured from the text and the font in hand rather than assumed,
    and the lines are only ever closed up as far as the letters allow.
    """
    key = (family, weight, tuple(lines))
    if key not in _ink_share:
        font = QtGui.QFont(family)
        font.setPixelSize(MEASURE_PX)
        font.setWeight(QtGui.QFont.Weight(weight))
        fm = QtGui.QFontMetrics(font)
        box = fm.height() or 1
        tallest = 0
        for line in lines:
            for word in line.split():
                tallest = max(tallest, fm.tightBoundingRect(word).height())
        if len(_ink_share) > 64:                    # a page's worth is plenty to remember
            _ink_share.clear()
        _ink_share[key] = tallest / box
    return _ink_share[key]


def line_box(lines: list[str], family: str, weight: int, fm) -> int:
    """How tall to make each line: as close as these particular letters allow, and never
    further apart than the font itself asks for."""
    share = min(1.0, max(LEADING, ink_share(lines, family, weight) + INK_ROOM))
    return max(1, int(fm.height() * share))


def is_han(ch: str) -> bool:
    """A Chinese character (or Japanese kanji): the ranges that are written without spaces."""
    return ("㐀" <= ch <= "鿿" or "豈" <= ch <= "﫿"
            or "　" <= ch <= "〿")          # and the CJK punctuation with them


def wrappable(text: str) -> list[tuple[str, bool]]:
    """The pieces a line may be broken between, each with whether a space goes before it.

    Words, for a language that writes them with spaces. Chinese does not: a whole verse arrives
    as one long run, and as a single word it would neither wrap - so it ran off the side of the
    column - nor light up a piece at a time with the voice. A run of Han characters is therefore
    broken into its characters, with no space between them, which is where Chinese breaks its
    lines anyway.
    """
    pieces: list[tuple[str, bool]] = []
    gap_next = False
    for word in text.split():
        if any(is_han(ch) for ch in word):
            for ch in word:
                pieces.append((ch, gap_next))
                gap_next = False
        else:
            pieces.append((word, gap_next))
        gap_next = True
    if pieces:
        pieces[0] = (pieces[0][0], False)
    return pieces


def lay_out_words(lines: list[str], width: int, family: str, px: int, weight: int,
                  rtl: bool, gap_share: float = LINE_GAP) -> tuple[list[PlacedWord], int]:
    """Places every word, wrapping each line. Words are drawn one at a time so the one being
    recited can be shown in red; Arabic shapes within a word, so this does not break the script.
    Returns the words and the total height."""
    font = QtGui.QFont(family)
    font.setPixelSize(px)
    font.setWeight(QtGui.QFont.Weight(weight))
    fm = QtGui.QFontMetrics(font)
    space = fm.horizontalAdvance(" ")
    line_h = line_box(lines, family, weight, fm)
    gap = int(px * gap_share)

    placed: list[PlacedWord] = []
    row = 0
    y = 0
    for index, text in enumerate(lines):
        words = wrappable(text)
        if not words:
            continue
        used = 0
        rowed: list[list[tuple[str, int, int]]] = [[]]
        for word, spaced in words:
            w = fm.horizontalAdvance(word)
            before = space if spaced else 0
            need = w if not rowed[-1] else used + before + w
            if rowed[-1] and need > width:
                rowed.append([(word, w, 0)])        # first of a line: no space in front of it
                used = w
            else:
                rowed[-1].append((word, w, before))
                used = need
        for chunk in rowed:
            if rtl:
                # Arabic reads right to left, so the first word of the line sits at the right
                # edge. A space belongs between a word and the one before it, so it is taken off
                # before the word that follows it, never after the word that precedes it.
                x = width
                for n, (word, w, before) in enumerate(chunk):
                    if n:
                        x -= before
                    x -= w
                    placed.append(PlacedWord(word, index, x, y, w, line_h))
            else:
                x = 0
                for word, w, before in chunk:
                    x += before
                    placed.append(PlacedWord(word, index, x, y, w, line_h))
                    x += w
            y += line_h + gap
            row += 1
    height = max(0, y - gap)
    return placed, height


class TextBox(QtWidgets.QWidget):
    """Draws a few lines of text, as large as will fit, centred in the box."""

    def __init__(self, family: str, min_px: int, max_px: int, rtl: bool = False, weight: int = 400,
                 slack: float = 0.88, by_word: bool = False, gap: float = LINE_GAP,
                 one_line: bool = False):
        super().__init__()
        self.SLACK = slack
        self.gap = gap
        self.one_line = one_line        # never wrap: shrink until each line fits across the box
        self.family = family
        self.min_px = min_px
        self.max_px = max_px
        self.rtl = rtl
        self.weight = weight
        self.by_word = by_word          # lay out word by word, so one can be highlighted
        self.highlight: tuple[int, int] | None = None   # (line, word being recited)
        self.highlight_color: str | None = None   # None: the theme's red
        self.lines: list[str] = []
        self.scale = 1.0
        # Normally the box picks the biggest size its text will fit at. Pinning overrides that, for
        # when something outside the box has to agree with it -- the daily passages, where the
        # Arabic and the English underneath are set to one size between them.
        self.pinned: int | None = None
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def pin(self, px: int | None) -> None:
        """Draw at exactly this size, or None to go back to filling the box."""
        if px != self.pinned:
            self.pinned = px
            self.update()

    def height_at(self, px: int) -> int:
        """The height the text would take at that size, laid out across this box's width."""
        return self.measure(self.lines, px) if self.lines else 0

    def set_family(self, family: str) -> None:
        if family != self.family:
            self.family = family
            self.update()

    def set_lines(self, lines: list[str]) -> None:
        self.lines = [x for x in lines if x]
        self.highlight = None
        self.update()

    def set_highlight(self, where: tuple[int, int] | None) -> None:
        if where != self.highlight:
            self.highlight = where
            self.update()

    SLACK = 0.88   # never fill the box right to its edge; set per box below

    def measure(self, lines: list[str], px: int) -> int:
        """The height these lines will take when drawn, the same way paintEvent draws them."""
        if self.by_word:
            return lay_out_words(lines, self.width(), self.family, px, self.weight, self.rtl,
                                 self.gap)[1]
        return _height(lines, self.width(), self.family, px, self.gap, self.weight)

    def fits(self, lines: list[str]) -> bool:
        """Would these lines fit in the box at the smallest size we allow, with room to spare?"""
        lines = [x for x in lines if x]
        if not lines or self.width() < 50 or self.height() < 50:
            return True
        return self.measure(lines, int(self.min_px * self.scale)) <= self.height() * self.SLACK

    def unwrapped_size(self) -> int:
        """The biggest size at which every line still fits across the box on its own."""
        low, high = int(FLOOR_PX * self.scale), int(self.max_px * self.scale)
        room = self.width() * 0.97          # a little spare, as words are laid out one by one
        best = low
        while low <= high:
            mid = (low + high) // 2
            font = QtGui.QFont(self.family)
            font.setPixelSize(mid)
            font.setWeight(QtGui.QFont.Weight(self.weight))
            fm = QtGui.QFontMetrics(font)
            if max(fm.horizontalAdvance(line) for line in self.lines) <= room:
                best, low = mid, mid + 1
            else:
                high = mid - 1
        return best

    def fitted_size(self) -> int:
        if not self.lines:
            return 0
        if self.pinned:
            return self.pinned
        if self.one_line:
            return min(self._fitted_size(), self.unwrapped_size())
        return self._fitted_size()

    def _fitted_size(self) -> int:
        if not self.by_word:
            px, _ = fit_size(self.lines, self.width(), int(self.height() * self.SLACK), self.family,
                             int(self.min_px * self.scale), int(self.max_px * self.scale),
                             weight=self.weight)
            return px
        room = int(self.height() * self.SLACK)
        low, high = int(FLOOR_PX * self.scale), int(self.max_px * self.scale)
        best = low
        while low <= high:
            mid = (low + high) // 2
            if self.measure(self.lines, mid) <= room:
                best, low = mid, mid + 1
            else:
                high = mid - 1
        return best

    def paintEvent(self, _):
        if not self.lines:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        px = self.fitted_size()
        font = QtGui.QFont(self.family)
        font.setPixelSize(px)
        font.setWeight(QtGui.QFont.Weight(self.weight))
        p.setFont(font)
        ink = QtGui.QColor(palette().ink)
        lit_ink = QtGui.QColor(self.highlight_color or palette().highlight)
        p.setPen(ink)

        if self.by_word:
            placed, total = lay_out_words(self.lines, self.width(), self.family, px, self.weight,
                                          self.rtl, self.gap)
            top = max(0, (self.height() - total) // 2)
            if self.one_line and placed:             # a line on its own sits in the middle
                left = min(w.x for w in placed)
                right = max(w.x + w.width for w in placed)
                shift = (self.width() - (right - left)) // 2 - left
                placed = [PlacedWord(w.text, w.line, w.x + shift, w.y, w.width, w.height) for w in placed]
            # Each word is drawn on its own, so punctuation at its end (the Arabic comma in the
            # tahlil) takes its side from the painter: right to left for Arabic.
            p.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.rtl
                                 else Qt.LayoutDirection.LeftToRight)
            counts: dict[int, int] = {}
            for word in placed:
                n = counts.get(word.line, 0)
                counts[word.line] = n + 1
                lit = self.highlight == (word.line, n)
                p.setPen(lit_ink if lit else ink)
                p.drawText(QtCore.QRect(word.x, top + word.y, word.width + 2, word.height),
                           int(Qt.AlignmentFlag.AlignLeft) | int(Qt.AlignmentFlag.AlignVCenter), word.text)
            return
        if self.one_line:               # a line on its own reads best in the middle of the box
            flags = int(Qt.AlignmentFlag.AlignHCenter)
        else:
            flags = int(Qt.TextFlag.TextWordWrap) | int(
                Qt.AlignmentFlag.AlignRight if self.rtl else Qt.AlignmentFlag.AlignLeft)

        heights = line_heights(self.lines, self.width(), self.family, px, self.weight)
        gap = int(px * self.gap)
        total = sum(heights) + gap * (len(heights) - 1)
        y = max(0, (self.height() - total) // 2)
        for line, h in zip(self.lines, heights):
            p.drawText(QtCore.QRect(0, y, self.width(), h), flags, line)
            y += h + gap


class ParallelText(QtWidgets.QWidget):
    """The Arabic on the right, its meaning on the left, verse level with verse.

    Each verse is a row: the Arabic wraps in its column from the right edge, the translation in
    its column from the left edge, and the row is as tall as whichever is taller. Both start at
    the top of the row, so the eye can go straight across. One size is picked for the whole
    screen, the largest at which every row fits; the translation is set at a fixed share of the
    Arabic size, since Arabic letters sit smaller on their line than Latin ones.

    While the Arabic is recited, its word turns red and so does the stretch of the translation
    that sits at the same point in the verse: a good guess, not a word-for-word match, as the
    two languages put their words in a different order.
    """

    ARABIC_SHARE = 0.50     # of the width, the rest (less the gap) is the translation
    GAP = 44                # between the columns, at 1080p
    LATIN_RATIO = 0.70      # translation size, as a share of the Arabic size
    LATIN_FLOOR = 24        # but never smaller than this, at 1080p
    LATIN_CAP = 84          # nor bigger than this: a short phrase needs no poster lettering
    ROW_GAP = 0.22          # between verses, as a share of the Arabic size
    SLACK = 0.98
    RULE = 2                # the thin line down the middle, at 1080p

    def __init__(self, arabic_family: str, latin_family: str, weight: int = 700):
        super().__init__()
        self.arabic_family = arabic_family
        self.latin_family = latin_family
        self.meaning_family = latin_family     # an Urdu meaning is set in the Arabic face
        self.weight = weight
        self.arabic: list[str] = []
        self.meaning: list[str] = []
        self.meaning_rtl = False
        self.highlight: tuple[int, int] | None = None
        self.scale = 1.0
        self._cache = None
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def set_family(self, family: str) -> None:
        if family != self.arabic_family:
            self.arabic_family = family
            self._cache = None
            self.update()

    def set_meaning_face(self, family: str, rtl: bool) -> None:
        """Which face the meaning is drawn in, and which way it runs. Urdu is written in the
        Arabic script, right to left, so it takes the Arabic face."""
        if (family, rtl) != (self.meaning_family, self.meaning_rtl):
            self.meaning_family, self.meaning_rtl = family, rtl
            self._cache = None
            self.update()

    def set_lines(self, arabic: list[str], meaning: list[str], rtl: bool = False) -> None:
        self.arabic = list(arabic)
        self.meaning = list(meaning) + [""] * (len(arabic) - len(meaning))
        self.meaning_rtl = rtl
        self.highlight = None
        self._cache = None
        self.update()

    def set_highlight(self, where: tuple[int, int] | None) -> None:
        if where != self.highlight:
            self.highlight = where
            self.update()

    def columns(self) -> tuple[int, int, int]:
        """Width of the Arabic column, of the translation column, and the gap between."""
        gap = int(self.GAP * self.scale)
        arabic = int((self.width() - gap) * self.ARABIC_SHARE)
        return arabic, max(1, self.width() - gap - arabic), gap

    def latin_px(self, arabic_px: int) -> int:
        return max(int(self.LATIN_FLOOR * self.scale),
                   min(int(self.LATIN_CAP * self.scale), int(arabic_px * self.LATIN_RATIO)))

    def _rows(self, px: int):
        """Every verse laid out at Arabic size [px]: (arabic words, translation words, row
        height) per verse, and the total height."""
        wa, wt, _ = self.columns()
        lpx = self.latin_px(px)
        rows, total = [], 0
        for i, line in enumerate(self.arabic):
            ar, ha = lay_out_words([line], wa, self.arabic_family, px, self.weight, True, 0.18)
            tr, ht = lay_out_words([self.meaning[i]], wt, self.meaning_family, lpx, 400,
                                   self.meaning_rtl, 0.22) if self.meaning[i] else ([], 0)
            height = max(ha, ht)
            rows.append((ar, tr, height))
            total += height
        total += int(px * self.ROW_GAP) * max(0, len(rows) - 1)
        return rows, total

    def layout(self):
        key = (self.width(), self.height(), self.arabic_family, self.meaning_family,
               self.meaning_rtl, self.scale)
        if self._cache is not None and self._cache[0] == key:
            return self._cache[1]
        room = int(self.height() * self.SLACK)
        low, high = int(FLOOR_PX * self.scale), int(MAX_ARABIC_PX * self.scale)
        best = low
        while low <= high:
            mid = (low + high) // 2
            if self._rows(mid)[1] <= room:
                best, low = mid, mid + 1
            else:
                high = mid - 1
        rows, total = self._rows(best)
        result = (best, rows, total)
        self._cache = (key, result)
        return result

    def lit_meaning(self, row: int) -> range:
        """Which translation words to light while the Arabic is on its highlighted word: the
        same stretch of the verse, in proportion."""
        if self.highlight is None or self.highlight[0] != row:
            return range(0)
        # Counted the same way the words were laid out, or the red would land on the wrong
        # piece: Chinese is placed character by character, not word by word.
        arabic_words = len(wrappable(self.arabic[row]))
        meaning_words = len(wrappable(self.meaning[row]))
        if not arabic_words or not meaning_words:
            return range(0)
        word = min(self.highlight[1], arabic_words - 1)
        start = word * meaning_words // arabic_words
        end = max(start + 1, (word + 1) * meaning_words // arabic_words)
        return range(start, min(end, meaning_words))

    def paintEvent(self, _):
        if not self.arabic or self.width() < 50:
            return
        px, rows, total = self.layout()
        colours = palette()
        ink, red = QtGui.QColor(colours.ink), QtGui.QColor(colours.highlight)
        wa, wt, gap = self.columns()
        arabic_x = self.width() - wa
        meaning_x = 0
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        # A thin line down the middle of the gap, so the eye knows which side is which. It is
        # the same colour as the words, so it turns white with them after dark.
        #
        # It runs the whole height of the screen, every screen. It used to be drawn only as tall
        # as that screen's words, which meant it grew and shrank from one recitation to the next
        # and drew the eye to itself instead of dividing the two columns quietly.
        rule = QtGui.QPen(ink)
        rule.setWidth(max(1, int(self.RULE * self.scale)))
        p.setPen(rule)
        middle = arabic_x - gap / 2
        p.drawLine(QtCore.QPointF(middle, 0), QtCore.QPointF(middle, self.height()))
        arabic_font = QtGui.QFont(self.arabic_family)
        arabic_font.setPixelSize(px)
        arabic_font.setWeight(QtGui.QFont.Weight(self.weight))
        latin_font = QtGui.QFont(self.meaning_family)
        latin_font.setPixelSize(self.latin_px(px))
        latin_font.setWeight(QtGui.QFont.Weight(400))
        flags = int(Qt.AlignmentFlag.AlignLeft) | int(Qt.AlignmentFlag.AlignVCenter)
        y = max(0, (self.height() - total) // 2)
        for n, (arabic, meaning, height) in enumerate(rows):
            p.setFont(arabic_font)
            p.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            for i, word in enumerate(arabic):
                lit = self.highlight == (n, i)
                p.setPen(red if lit else ink)
                p.drawText(QtCore.QRect(arabic_x + word.x, y + word.y, word.width + 2, word.height),
                           flags, word.text)
            p.setFont(latin_font)
            p.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.meaning_rtl
                                 else Qt.LayoutDirection.LeftToRight)
            lit_words = self.lit_meaning(n)
            for i, word in enumerate(meaning):
                p.setPen(red if i in lit_words else ink)
                p.drawText(QtCore.QRect(meaning_x + word.x, y + word.y, word.width + 2, word.height),
                           flags, word.text)
            y += height + int(px * self.ROW_GAP)


class RepeatBadge(QtWidgets.QWidget):
    """How many times a recitation is said, in a black circle: X3 in ruku and sujood, X2 for
    the salam. It sits in the top right corner inside the picture frame, where the figure
    never reaches."""

    def __init__(self, size: int, family: str = ""):
        super().__init__()
        self.size = size
        self.family = family
        self.count = 1
        self.setFixedSize(max(1, size), max(1, size))

    def set_count(self, count: int) -> None:
        if count != self.count:
            self.count = count
            self.update()

    def set_size(self, size: int) -> None:
        size = max(1, int(size))
        if size != self.size:
            self.size = size
            self.setFixedSize(size, size)
            self.update()

    def paintEvent(self, _):
        if self.count <= 1:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        circle = QtCore.QRect(0, 0, self.size, self.size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(palette().ink))
        painter.drawEllipse(circle)
        font = QtGui.QFont(self.family) if self.family else painter.font()
        font.setPixelSize(max(10, int(self.size * 0.46)))
        font.setWeight(QtGui.QFont.Weight(700))
        painter.setFont(font)
        painter.setPen(QtGui.QColor(palette().paper))
        painter.drawText(circle, int(Qt.AlignmentFlag.AlignCenter), f"X{self.count}")


class VolumeBar(QtWidgets.QWidget):
    """How loud the recitation is, as a rectangle above the picture.

    Ten blocks in a bordered rectangle, filled black up to the level, so it reads from standing
    distance. Tap or drag anywhere along it to set the volume; the far left is silence. Drawn in
    the same black and white as the rest of the prayer screen.
    """
    changed = Signal(int)

    BORDER = 3
    BLOCKS = 10

    def __init__(self, height: int, volume: int = 80, family: str = ""):
        super().__init__()
        self.bar_height = max(1, height)
        self.volume = max(0, min(100, int(volume)))
        self.family = family
        self.scale = 1.0
        self.setFixedHeight(self.bar_height)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                           QtWidgets.QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_volume(self, volume: int, tell: bool = False) -> None:
        volume = max(0, min(100, int(volume)))
        if volume != self.volume:
            self.volume = volume
            self.update()
            if tell:
                self.changed.emit(volume)

    def speaker_width(self) -> int:
        return int(self.height() * 0.92)

    def track(self) -> QtCore.QRect:
        """The blocks, with the speaker mark left of them."""
        left = self.speaker_width() + int(self.height() * 0.24)
        return QtCore.QRect(left, 0, max(1, self.width() - left), self.height())

    def _set_from_x(self, x: float) -> None:
        track = self.track()
        if track.width() <= 0:
            return
        share = (x - track.x()) / track.width()
        step = 100 / self.BLOCKS
        blocks = round(max(0.0, min(1.0, share)) * self.BLOCKS)
        self.set_volume(int(blocks * step), tell=True)

    def mousePressEvent(self, e):
        self._set_from_x(e.position().x())
        e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._set_from_x(e.position().x())
        e.accept()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        black = QtGui.QColor(palette().ink)     # the ink: white on a dark screen
        self._draw_speaker(p, black)

        track = self.track()
        border = max(1, int(self.BORDER * self.scale))
        pen = QtGui.QPen(black)
        pen.setWidth(border)
        p.setPen(pen)
        p.setBrush(QtGui.QColor(palette().paper))
        half = border / 2
        p.drawRect(QtCore.QRectF(track.x() + half, half,
                                 track.width() - border, track.height() - border))

        filled = round(self.volume / 100 * self.BLOCKS)
        if filled <= 0:
            return
        inset = border + max(1, int(3 * self.scale))
        inner = QtCore.QRectF(track.x() + inset, inset,
                              track.width() - 2 * inset, track.height() - 2 * inset)
        gap = inner.width() / self.BLOCKS * 0.22
        block = (inner.width() - gap * (self.BLOCKS - 1)) / self.BLOCKS
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(black)
        for i in range(filled):
            p.drawRect(QtCore.QRectF(inner.x() + i * (block + gap), inner.y(),
                                     block, inner.height()))

    def _draw_speaker(self, p: QtGui.QPainter, colour: QtGui.QColor) -> None:
        """A loudspeaker, so the rectangle is unmistakably the volume."""
        w = self.speaker_width()
        h = self.height()
        body = QtGui.QPainterPath()
        body.moveTo(w * 0.06, h * 0.36)
        body.lineTo(w * 0.30, h * 0.36)
        body.lineTo(w * 0.62, h * 0.12)
        body.lineTo(w * 0.62, h * 0.88)
        body.lineTo(w * 0.30, h * 0.64)
        body.lineTo(w * 0.06, h * 0.64)
        body.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawPath(body)

        pen = QtGui.QPen(colour)
        pen.setWidth(max(1, int(h * 0.07)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.volume <= 0:                       # a cross through it when it is silent
            p.drawLine(QtCore.QPointF(w * 0.70, h * 0.34), QtCore.QPointF(w * 0.96, h * 0.66))
            p.drawLine(QtCore.QPointF(w * 0.96, h * 0.34), QtCore.QPointF(w * 0.70, h * 0.66))
            return
        for i, reach in enumerate((0.20, 0.33)):   # one wave, two when it is well up
            if i and self.volume < 55:
                break
            r = w * reach
            span = QtCore.QRectF(w * 0.62 - r, h * 0.5 - r, r * 2, r * 2)
            p.drawArc(span, -50 * 16, 100 * 16)


class PostureView(QtWidgets.QWidget):
    """The posture figure, in a fixed frame with a black border.

    Standing figures are tall and fill the frame. Bowing, prostrating and sitting figures are
    wide, so they are scaled to the frame's width and left shorter. Every figure sits on the
    bottom of the frame, so the person is always standing on the same line.

    The repeat circle (X3, X2) rides in the frame's top right corner, clear of the figure.
    """

    BORDER = 3
    PAD = 18
    BADGE_SHARE = 0.26      # circle diameter, as a share of the frame's width

    def __init__(self, cache: "PixmapCache", family: str = ""):
        super().__init__()
        self.cache = cache
        self.path: Path | None = None
        self.scale = 1.0
        self.modes: dict[str, float] = {}
        self.badge = RepeatBadge(1, family)
        self.badge.setParent(self)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)

    def set_image(self, path: Path) -> None:
        if path != self.path:
            self.path = path
            self.update()

    def set_repeat(self, count: int) -> None:
        self.badge.set_count(count)

    def resizeEvent(self, _):
        edge = int((self.BORDER + self.PAD) * self.scale)
        size = max(1, int(self.width() * self.BADGE_SHARE))
        self.badge.set_size(size)
        self.badge.move(max(edge, self.width() - edge - size), edge)
        self.badge.raise_()

    def inner(self) -> QtCore.QSize:
        edge = int((self.BORDER + self.PAD) * self.scale)
        return QtCore.QSize(max(1, self.width() - 2 * edge), max(1, self.height() - 2 * edge))

    def target(self) -> QtCore.QSize:
        """A standing figure fills the frame's height. The others get the share of that height
        the posture really takes, and are capped to the frame's width so nothing is cut off."""
        inner = self.inner()
        share = float(self.modes.get(self.path.stem, 1.0)) if self.path is not None else 1.0
        return QtCore.QSize(inner.width(), max(1, int(inner.height() * share)))

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        border = max(1, int(self.BORDER * self.scale))
        pen = QtGui.QPen(QtGui.QColor(palette().ink))
        pen.setWidth(border)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        half = border / 2
        p.drawRect(QtCore.QRectF(half, half, self.width() - border, self.height() - border))

        if self.path is None:
            return
        pix = self.cache.get(self.path, self.target())
        if pix.isNull():
            return
        edge = int((self.BORDER + self.PAD) * self.scale)
        x = (self.width() - pix.width()) // 2
        y = self.height() - edge - pix.height()          # stand every figure on the same line
        p.drawPixmap(x, max(edge, y), pix)


def load_posture_modes(assets: Path, figure: str = "boy") -> dict[str, float]:
    """How each picture is sized: see PostureView.target. Written by tools/build_postures.py.

    A figure set of its own (assets/postures/girl) may bring its own modes.json; anything it
    does not mention falls back to the original set's."""
    def read(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    modes = read(assets / "postures" / "modes.json")
    if figure and figure != "boy":
        modes = {**modes, **read(assets / "postures" / figure / "modes.json")}
    return modes


def load_timings(assets: Path) -> dict:
    """Every recitation that has a recording, keyed by recitation name."""
    from .audio import Timings
    out = {}
    for path in sorted((assets / "audio").glob("*.json")):
        timings = Timings.load(path)
        if timings is not None and timings.audio.is_file():
            out[path.stem] = timings
    return out


class PixmapCache:
    """Posture pictures scaled to the frame. On a dark screen they are drawn inverted, white
    lines on black, so the figure matches the words; both versions are cached."""

    def __init__(self, capacity: int = 12):
        self.capacity = capacity
        self._items: OrderedDict[tuple[str, int, int, bool], QtGui.QPixmap] = OrderedDict()

    def get(self, path: Path, size: QtCore.QSize) -> QtGui.QPixmap:
        dark = palette().dark
        key = (str(path), size.width(), size.height(), dark)
        pix = self._items.get(key)
        if pix is None:
            src = QtGui.QPixmap(str(path))
            pix = src if src.isNull() else src.scaled(
                size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            if dark and not pix.isNull():
                pix = invert(pix)
            self._items[key] = pix
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)
        else:
            self._items.move_to_end(key)
        return pix


def invert(pix: QtGui.QPixmap) -> QtGui.QPixmap:
    """Black for white and white for black, leaving any transparency alone."""
    image = pix.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    image.invertPixels(QtGui.QImage.InvertMode.InvertRgb)
    return QtGui.QPixmap.fromImage(image)
