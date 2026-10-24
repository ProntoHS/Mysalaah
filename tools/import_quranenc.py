#!/usr/bin/env python3
"""Turns the Noble Qur'an Encyclopedia's own XML export into the Qur'an the mat reads.

    python3 tools/import_quranenc.py ~/Downloads/english_saheeh_v1.1.2-xml.1.xml
    python3 tools/import_quranenc.py ~/Downloads/*.xml

Download the XML from the Downloads row beside a translation on quranenc.com -- the address is
    https://quranenc.com/en/home/d/xml/<edition key>
-- and hand the files to this. It writes assets/content/quran/<lang>/1..114.json and the
SOURCE.json beside them, and refuses to write anything at all if the export is not whole.

WHY XML AND NOT THE API. The API answers one surah at a time and says nothing about which
revision it is answering from. The XML export states the version in three places -- the
filename, the <updated_at> element and a <check_updates> address that answers whether that
version is still current -- so the mat can record what it actually has instead of a guess.
assets/content/quran/SOURCE.txt explains why that matters more than it sounds: Tanzil, where
five of these came from until October 2026, does not version its editions at all, and a text
nobody can ask about cannot be kept correct.

WHAT IS NOT IMPORTED. The <footnotes> beside each verse. There are 6,632 of them across the
five editions and the mat has no screen that can show one, so shipping them put 1.7 MB of
unreadable data on every SD card. They are left where they came from; this will extract them
again the day there is somewhere to put them, and nothing has been lost because the export can
be downloaded again from the address in the SOURCE.json it writes.

WHAT IT REFUSES. Anything short. The shape of the Qur'an is not a matter of opinion: 114
surahs, each with a verse count settled for centuries, verses numbered 1..n with none missing
and none blank. The lengths are taken from the Arabic already on the mat, which was checked
verse by verse when it was converted, so a short export cannot quietly install itself over a
good one. 1.91 went out with 86 hadith instead of 109 because a file that was merely SHORT
looked like a file that was fine.

WHAT IT CANNOT CHECK. Whether the words are right. Nobody who reads Arabic has been over any
of it, every SOURCE.json it writes says reviewed: false, and that is the only honest thing to
say until somebody has.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
QURAN = ROOT / "assets" / "content" / "quran"

# Which edition goes in which folder. An edition not named here is refused rather than guessed
# at: putting a Spanish text in the French folder would be invisible to every check there is.
EDITIONS = {
    "english_saheeh":   ("en", "English translation",    "Saheeh International"),
    "spanish_garcia":   ("es", "Spanish translation",    "Muhammad Isa García"),
    "chinese_makin":    ("zh", "Chinese translation",    "Muhammad Makin (Ma Jian)"),
    "hindi_omari":      ("hi", "Hindi translation",      "Maulana Azizul Haque Al-Omari"),
    "portuguese_nasr":  ("pt", "Portuguese translation", "Helmi Nasr"),
    "urdu_junagarhi":   ("ur", "Urdu translation",       "Muhammad Junagarhi"),
    "french_montada":   ("fr", "French translation",     "Islamic Foundation"),
    "bengali_zakaria":  ("bn", "Bengali translation",    "Abu Bakr Zakaria"),
}

REVIEW = ("The publisher states these are reviewed editions. Nobody engaged by this project "
          "has read a word of it, which is what reviewed: false records.")


def canonical() -> dict[int, int]:
    """How long each surah is, taken from the Arabic on this mat rather than typed here."""
    out = {}
    for number in range(1, 115):
        rows = json.loads((QURAN / "ar" / f"{number}.json").read_text(encoding="utf-8"))
        out[number] = len(rows)
    if sum(out.values()) != 6236:
        raise SystemExit(f"The Arabic on this mat has {sum(out.values())} verses, not 6236. "
                         f"Fix that before importing anything over it.")
    return out


def read(path: pathlib.Path, lengths: dict[int, int]) -> tuple[dict, dict, list[str]]:
    root = ET.parse(path).getroot()
    meta = {child.tag: (child.text or "").strip() for child in root.find("meta")}
    verses: dict[int, list] = {}
    wrong: list[str] = []
    for surah in root.find("sura_list"):
        number = int(surah.get("number"))
        rows = []
        for aya in surah:
            said = (aya.findtext("translation") or "").strip()
            if not said:
                wrong.append(f"{number}:{aya.get('number')} has no translation")
            rows.append({"n": int(aya.get("number")), "text": said})
        if [row["n"] for row in rows] != list(range(1, len(rows) + 1)):
            wrong.append(f"surah {number} is not numbered 1..{len(rows)}")
        if len(rows) != lengths.get(number):
            wrong.append(f"surah {number} has {len(rows)} verses, the Arabic has "
                         f"{lengths.get(number)}")
        verses[number] = rows
    if len(verses) != 114:
        wrong.append(f"{len(verses)} surahs, expected 114")
    total = sum(len(v) for v in verses.values())
    if total != 6236:
        wrong.append(f"{total} verses, expected 6236")
    return meta, verses, wrong


def main() -> int:
    ap = argparse.ArgumentParser(prog="import_quranenc", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=pathlib.Path, help="XML exports from quranenc.com")
    ap.add_argument("--dry-run", action="store_true", help="check them and write nothing")
    args = ap.parse_args()

    lengths = canonical()
    ready = []
    for path in args.files:
        if not path.is_file():
            print(f"  {path}: not there", file=sys.stderr)
            return 1
        meta, verses, wrong = read(path, lengths)
        key = meta.get("id", "")
        if key not in EDITIONS:
            print(f"  {path.name}: edition {key!r} is not one this tool knows where to put. "
                  f"Add it to EDITIONS, with the language it belongs in.", file=sys.stderr)
            return 1
        lang, what, translator = EDITIONS[key]
        version = (re.search(r"\(v([\d.]+)-", meta.get("updated_at", "")) or ["", ""])[1]
        when = (re.match(r"([\d-]{10})", meta.get("updated_at", "")) or ["", ""])[1]
        if wrong:
            print(f"  {key} -> {lang}: REFUSED", file=sys.stderr)
            for line in wrong[:8]:
                print(f"      {line}", file=sys.stderr)
            return 1
        print(f"  {key:18} -> {lang}  v{version or '?'} ({when or 'no date'})  "
              f"6236 verses, every surah the length the Arabic is")
        ready.append((key, lang, what, translator, version, when, meta, verses))

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    for key, lang, what, translator, version, when, meta, verses in ready:
        folder = QURAN / lang
        folder.mkdir(parents=True, exist_ok=True)
        for number in range(1, 115):
            (folder / f"{number}.json").write_text(
                json.dumps(verses[number], ensure_ascii=False), encoding="utf-8")
        # Read back and compared before the source record is written, so a half-written folder
        # cannot end up with a SOURCE.json claiming it is whole.
        for number in range(1, 115):
            back = json.loads((folder / f"{number}.json").read_text(encoding="utf-8"))
            if back != verses[number]:
                print(f"  {lang}: surah {number} did not read back as it was written",
                      file=sys.stderr)
                return 1
        (folder / "SOURCE.json").write_text(json.dumps({
            "schema": 2, "lang": lang, "what": what, "translator": translator,
            "publisher": "Noble Qur'an Encyclopedia", "where": meta.get("url", ""),
            "via": f"quranenc.com official XML export, v{version}",
            "edition": key, "version": version, "updated": when,
            "check_updates": meta.get("check_updates", ""),
            "private": False, "note": "",
            "publisher_reviewed": True, "reviewed": False, "review_note": REVIEW,
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {lang}/: 114 surahs and SOURCE.json written and read back")

    print("\nNow run tools/check_quran.py, and tools/subset_fonts.py --check-only if the text "
          "is in a\nscript the mat bundles a face for. A new language also needs "
          "tools/retext_duas.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
