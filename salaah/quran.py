"""Reading the Qur'an off the disk.

The text lives in assets/content/quran: an index of the 114 surahs, then one file per surah per
language. Split that way on purpose -- opening one surah reads a few kilobytes rather than the
three megabytes a whole language would cost, which is what keeps the list instant on a Pi.

Nothing here draws anything. It hands back verses; reading.py decides what a page looks like.

Everything is forgiving about what is missing. A mat whose assets were half copied should show
the surahs it has and say nothing about the rest, rather than refuse to start.
"""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

# Every language a translation could be offered in, in the order they are offered. A language
# is only OFFERED when its text is actually on the mat -- languages() looks -- so naming one
# here costs nothing and leaving one out makes it unofferable. Hindi was left out until 1.84
# for that second reason: the source the shipped five came from has none, so the mat spoke
# Hindi with its Qur'an reader empty and no way to fill it.
LANGS = ("en", "fr", "ur", "es", "zh", "hi", "ru", "pt", "bn")

# Text the owner has a right to read but the mat has no right to pass on. A translation under
# somebody's copyright can be put here, on one mat, for one family, without ever entering the
# repository or a signed release -- which is the whole difference between using something and
# distributing it. Same idea as ~/.salaah/nasheeds, and it is read exactly like the assets
# folder: an index and one file per surah per language.
PRIVATE = Path.home() / ".salaah" / "quran"

RTL = ("ur",)            # translations that read right to left
KEEP = 8                 # surahs held in memory at once; a surah is small, a language is not

# The Noble Qur'an Encyclopedia's editions carry two things the mat has nowhere to put, so they
# are stripped as the verse is handed over rather than edited out of the files. Their terms ask
# that the text not be modified, and the files on disk are byte-for-byte their export -- what
# changes is only what this screen can show.
#
#   [12]   a footnote reference. The footnotes themselves are in NOTES.json beside the surahs,
#          waiting for a screen that can show them. Until then a bare [12] mid-sentence is
#          noise to a child, so it goes.
#   "7. "  a verse number repeated at the head of the verse, which the Spanish edition does and
#          the others do not. The reader already prints the number down the margin.
#
# Only a NUMBER in brackets goes. The translators' own interpolations are in brackets too --
# "[All] praise is [due] to Allah" is Saheeh International writing, not an annotation -- and
# stripping those would take words out of scripture.
NOTE_MARK = re.compile(r"\[\d+\]")
LEAD_NUMBER = re.compile(r"^(\d+)\s*[.,]\s+")


def as_shown(text: str, number: int) -> str:
    """One verse of a translation, as the screen should show it.

    The leading number is only taken off when it IS this verse's number. The Spanish edition
    writes 5:88 as "88, Coman de lo licito..." with a comma rather than a full stop, so the
    pattern allows either -- and the equality test is what stops it eating a verse that opens
    with a numeral of its own.
    """
    out = NOTE_MARK.sub("", text)
    found = LEAD_NUMBER.match(out)
    if found and int(found.group(1)) == number:
        out = out[found.end():]
    return " ".join(out.split())


@dataclass(frozen=True)
class Surah:
    number: int
    arabic: str          # الفاتحة
    name: str            # Al-Fatihah
    meaning: str         # The Opener
    place: str           # meccan or medinan
    verses: int


@dataclass(frozen=True)
class Verse:
    number: int
    arabic: str
    said: str            # the transliteration, for somebody learning to read it
    meaning: str = ""    # empty when no translation is chosen


class Quran:
    """The text, read as it is asked for and kept for a moment in case it is asked for again."""

    def __init__(self, assets: Path, private: Path | None = None):
        self.root = Path(assets) / "content" / "quran"
        # Where this mat's own licensed text lives, if it has any. Taken as an argument so a
        # test can point it somewhere harmless rather than at the home folder of whoever is
        # running the tests.
        self.private = Path(private) if private is not None else PRIVATE
        self._index: list[Surah] | None = None
        self._verses: OrderedDict[tuple[int, str], list] = OrderedDict()

    def where(self, folder: str, number: int) -> Path | None:
        """The file holding this surah in this language, private copy first.

        Private first rather than assets first, because a translation somebody has chosen for
        their own mat is a deliberate act and should win over the one that came in the box.
        """
        for root in (self.private, self.root):
            path = root / folder / f"{number}.json"
            if path.is_file():
                return path
        return None

    @property
    def there(self) -> bool:
        return (self.root / "index.json").is_file()

    @property
    def index(self) -> list[Surah]:
        if self._index is None:
            try:
                raw = json.loads((self.root / "index.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = []
            self._index = [Surah(number=int(s["id"]), arabic=s["arabic"], name=s["name"],
                                 meaning=s.get("meaning", ""), place=s.get("place", ""),
                                 verses=int(s["verses"])) for s in raw]
        return self._index

    def surah(self, number: int) -> Surah | None:
        for s in self.index:
            if s.number == number:
                return s
        return None

    def languages(self) -> tuple:
        """The translations actually on this mat, in the order they are offered.

        A folder with nothing in it is not a translation: an interrupted copy would otherwise
        put a language on the list and then show every surah blank.
        """
        return tuple(lang for lang in LANGS
                     if any((root / lang).is_dir() and any((root / lang).glob("*.json"))
                            for root in (self.private, self.root)))

    def _read(self, folder: str, number: int) -> list:
        key = (number, folder)
        if key in self._verses:
            self._verses.move_to_end(key)
            return self._verses[key]
        path = self.where(folder, number)
        try:
            rows = json.loads(path.read_text(encoding="utf-8")) if path else []
        except (OSError, ValueError):
            rows = []
        self._verses[key] = rows
        while len(self._verses) > KEEP:
            self._verses.popitem(last=False)
        return rows

    def verses(self, number: int, lang: str = "") -> list[Verse]:
        """A surah, with the translation alongside if one is asked for and exists.

        A translation that is missing or short simply leaves the meaning empty, rather than
        lining verses up against the wrong ones -- which is the worst thing this could do.
        """
        arabic = self._read("ar", number)
        meanings = self._read(lang, number) if lang in LANGS else []
        by_number = {row.get("n"): as_shown(row.get("text", ""), row.get("n") or 0)
                     for row in meanings}
        return [Verse(number=row["n"], arabic=row["text"], said=row.get("said", ""),
                      meaning=by_number.get(row["n"], "")) for row in arabic]
