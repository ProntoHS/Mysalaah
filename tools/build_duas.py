#!/usr/bin/env python3
"""Builds the du'a screen's content out of the Qur'an already on the mat.

    python3 tools/build_duas.py

Every du'a here is a Qur'anic verse, so not one word of Arabic is typed in this file. Each entry
names a surah and verse and says how many words to drop from the front -- 2:201 opens "But among
them is he who says" before the supplication begins, and you do not recite the preamble. The
words themselves are copied out of assets/content/quran, which was checked against its source
verse by verse.

What that buys: a mistake here cannot invent scripture. The worst it can do is start a du'a in
the wrong place, which is visible at a glance and is checked besides -- the builder refuses to
cut inside a word, and the test suite re-derives every du'a from the corpus independently.

Arabic, transliteration and English are trimmed to the supplication. The other four translations
keep the whole verse: trimming those means judging where a sentence turns in Urdu or Chinese,
and guessing at that is worse than a faithful verse with a line of context at the front.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QURAN = ROOT / "assets" / "content" / "quran"
OUT = ROOT / "assets" / "content" / "duas"

# The kinds of du'a the menu offers. Imported rather than repeated so a category cannot be
# filed against here that the menu has no tile for.
sys.path.insert(0, str(ROOT))
from salaah.duamenu import CATEGORIES        # noqa: E402

# Trimmed in these; whole verse in the rest.
CUT = ("ar", "said", "en")

# Quote marks a translation opens with once its preamble is gone.
QUOTES = '"“”«»‘’'

# Ten du'as. 'drop' is how many words to lose from the front of that verse, per language.
# Read off the verified text, never typed from memory -- see the note at the top.
DUAS = [
    dict(key="both_worlds", cats=('general',), title="Good in this world and the next",
         parts=[(2, 201, {"ar": 3, "said": 3, "en": 7})]),
    dict(key="no_burden", cats=('worry', 'forgiveness', 'protection'), title="Do not burden us beyond our strength",
         parts=[(2, 286, {"ar": 12, "said": 12, "en": 35})]),
    dict(key="steady_heart", cats=('guidance', 'general'), title="Let not our hearts turn away",
         parts=[(3, 8, {"en": 2})]),
    dict(key="wronged_ourselves", cats=('forgiveness',), title="We have wronged ourselves",
         parts=[(7, 23, {"ar": 1, "said": 1, "en": 2})]),
    dict(key="steadfast_in_prayer", cats=('prayer', 'family'), title="Make me steadfast in prayer",
         parts=[(14, 40, {}), (14, 41, {})]),
    dict(key="open_my_chest", cats=('worry', 'knowledge'), title="Expand my breast and ease my task",
         parts=[(20, 25, {"ar": 1, "said": 1, "en": 2}), (20, 26, {}),
                (20, 27, {}), (20, 28, {})]),
    # "and say" kept on the front of these two: slicing after it leaves a shadda on رَّبِّ that
    # belongs to the word before, which reads oddly standing alone. Including it is still a
    # plain slice -- nothing edited -- and it is how the verse is usually quoted.
    dict(key="more_knowledge", cats=('knowledge',), title="Increase me in knowledge",
         parts=[(20, 114, {"ar": 13, "said": 13, "en": 30})]),
    dict(key="no_deity_but_you", cats=('worry', 'forgiveness'), title="There is no deity except You",
         parts=[(21, 87, {"ar": 14, "said": 14, "en": 30})]),
    dict(key="forgive_and_mercy", cats=('forgiveness',), title="Forgive, and have mercy",
         parts=[(23, 118, {"ar": 0, "said": 0, "en": 4})]),
    dict(key="comfort_of_family", cats=('family', 'guidance'), title="Comfort in our families",
         parts=[(25, 74, {"ar": 2, "said": 2, "en": 4})]),
]


def languages() -> tuple[str, ...]:
    from json import loads
    order = ("en", "fr", "ur", "es", "zh")
    return tuple(lang for lang in order if (QURAN / lang).is_dir())


def verse(lang: str, surah: int, number: int) -> dict:
    rows = json.loads((QURAN / lang / f"{surah}.json").read_text(encoding="utf-8"))
    for row in rows:
        if int(row["n"]) == number:
            return row
    raise SystemExit(f"{lang} has no verse {surah}:{number}")


def slice_words(text: str, drop: int, where: str) -> str:
    """The text from word [drop] onward. Refuses to cut where there is nothing to cut."""
    words = text.split()
    if drop < 0 or drop >= len(words):
        raise SystemExit(f"{where}: cannot drop {drop} words from {len(words)}")
    kept = " ".join(words[drop:])
    if kept not in " ".join(words):
        raise SystemExit(f"{where}: the slice is not part of the verse -- refusing to write it")
    return kept


def tidy(text: str, trimmed: bool) -> str:
    """Drops quote marks left dangling by the trim. Only in the languages that were trimmed."""
    if trimmed:
        for mark in QUOTES:
            text = text.replace(mark, "")
    return " ".join(text.split())


def build_one(spec: dict, langs: tuple[str, ...]) -> dict:
    arabic, said = [], []
    meanings: dict[str, list[str]] = {lang: [] for lang in langs}
    for surah, number, drop in spec["parts"]:
        where = f"{spec['key']} {surah}:{number}"
        row = verse("ar", surah, number)
        arabic.append(slice_words(row["text"], drop.get("ar", 0), f"{where} ar"))
        said.append(slice_words(row.get("said", ""), drop.get("said", 0), f"{where} said"))
        for lang in langs:
            text = verse(lang, surah, number).get("text", "")
            lose = drop.get(lang, 0) if lang in CUT else 0
            meanings[lang].append(slice_words(text, lose, f"{where} {lang}") if text else "")

    first, last = spec["parts"][0], spec["parts"][-1]
    ref = (f"{first[0]}:{first[1]}" if first is last
           else f"{first[0]}:{first[1]}-{last[1]}")
    for cat in spec["cats"]:
        if cat not in CATEGORIES:
            raise SystemExit(f"{spec['key']}: no such category {cat!r}")
    return {
        "key": spec["key"],
        "cats": list(spec["cats"]),
        "title": spec["title"],
        "ref": ref,
        "verses": [[p[0], p[1]] for p in spec["parts"]],
        "arabic": " ".join(arabic),
        "said": " ".join(said).strip(),
        "text": {lang: tidy(" ".join(meanings[lang]), lang in CUT) for lang in langs},
        "trimmed": [lang for lang in langs if lang in CUT],
    }


def main() -> int:
    if not (QURAN / "index.json").is_file():
        print(f"No Qur'an at {QURAN}. Nothing to build from.", file=sys.stderr)
        return 1
    langs = languages()
    if not langs:
        print("No translations found.", file=sys.stderr)
        return 1
    built = [build_one(spec, langs) for spec in DUAS]

    keys = [d["key"] for d in built]
    if len(set(keys)) != len(keys):
        print("Two du'as share a key.", file=sys.stderr)
        return 1

    # The du'as that come from hadith are built separately, by tools/build_dua_hadith.py, which
    # lifts their Arabic out of two corpora. They are folded in here so the mat still reads one
    # file. If that file is not there the Qur'anic ones are written on their own rather than
    # failing -- but it is said plainly, because most of the kinds would then be empty.
    from_hadith = OUT / "hadith.json"
    extra, reviewed = [], True
    if from_hadith.is_file():
        other = json.loads(from_hadith.read_text(encoding="utf-8"))
        extra = other.get("items", [])
        reviewed = bool(other.get("reviewed", False))
        for d in extra:
            for cat in d.get("cats", []):
                if cat not in CATEGORIES:
                    print(f"{d['key']}: no such category {cat!r}", file=sys.stderr)
                    return 1
    else:
        print(f"No {from_hadith.name}: writing the Qur'anic du'as only. Most of the kinds on "
              f"the menu will have nothing behind them. Run tools/build_dua_hadith.py.",
              file=sys.stderr)
    built = built + extra

    OUT.mkdir(parents=True, exist_ok=True)
    where = OUT / "duas.json"
    where.write_text(json.dumps({
        "schema": 1,
        "reviewed": reviewed,
        "items": built,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(built)} du'as -> {where}")
    print(f"languages: {', '.join(langs)}  (trimmed: {', '.join(l for l in langs if l in CUT)})")
    for d in built:
        print(f"  {d['ref']:>10}  {d['title']}")
        print(f"              {d['arabic'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
