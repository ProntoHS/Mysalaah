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
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

# The languages a translation exists for. Hindi is not among them: the source this came from
# has no Hindi, and showing English to somebody who asked for Hindi would be worse than
# offering five and saying so.
LANGS = ("en", "fr", "ur", "es", "zh")

RTL = ("ur",)            # translations that read right to left
KEEP = 8                 # surahs held in memory at once; a surah is small, a language is not


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

    def __init__(self, assets: Path):
        self.root = Path(assets) / "content" / "quran"
        self._index: list[Surah] | None = None
        self._verses: OrderedDict[tuple[int, str], list] = OrderedDict()

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
        """The translations actually on this mat, in the order they are offered."""
        return tuple(lang for lang in LANGS if (self.root / lang).is_dir())

    def _read(self, folder: str, number: int) -> list:
        key = (number, folder)
        if key in self._verses:
            self._verses.move_to_end(key)
            return self._verses[key]
        try:
            rows = json.loads((self.root / folder / f"{number}.json").read_text(encoding="utf-8"))
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
        by_number = {row.get("n"): row.get("text", "") for row in meanings}
        return [Verse(number=row["n"], arabic=row["text"], said=row.get("said", ""),
                      meaning=by_number.get(row["n"], "")) for row in arabic]
