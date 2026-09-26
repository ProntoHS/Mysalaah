#!/usr/bin/env python3
"""Checks the Qur'an in assets/content/quran against what is known about it.

    python3 tools/check_quran.py
    python3 tools/check_quran.py --against /path/to/quran-json/dist/chapters

Two quite different checks live here, and it is worth being clear about which is which.

    The shape can be proved. There are 114 surahs; each has a verse count that has been
    settled for centuries and is written out below; the verses run 1..n with none missing and
    none blank. Any of that being wrong means the data is damaged, and that is not a matter of
    anyone's opinion.

    The words cannot be proved by a program. This checks that every verse has text, not that
    the text is right. With --against it also compares every verse with the source it was
    converted from, which proves the conversion did not corrupt anything -- but a faithful copy
    of a wrong source is still wrong. Someone who reads Arabic has to do that part.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QURAN = ROOT / "assets" / "content" / "quran"
LANGS = ("en", "fr", "ur", "es", "zh")

# The verse count of every surah, in order.
VERSES = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110,
          98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88,
          75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24,
          13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
          29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3,
          9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]
TOTAL = 6236


def read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as why:
        raise SystemExit(f"cannot read {path}: {why}")


def check_shape(wrong: list) -> int:
    """The index, then every surah in Arabic and in each translation."""
    index = read(QURAN / "index.json")
    if len(index) != 114:
        wrong.append(f"the index lists {len(index)} surahs, not 114")
    for entry in index:
        want = VERSES[entry["id"] - 1]
        if entry["verses"] != want:
            wrong.append(f"index: surah {entry['id']} says {entry['verses']} verses, not {want}")
        for field in ("arabic", "name", "meaning"):
            if not str(entry.get(field, "")).strip():
                wrong.append(f"index: surah {entry['id']} has no {field}")

    counted = 0
    for folder in ("ar",) + LANGS:
        here = 0
        for n in range(1, 115):
            path = QURAN / folder / f"{n}.json"
            if not path.is_file():
                wrong.append(f"{folder}: surah {n} is missing")
                continue
            verses = read(path)
            want = VERSES[n - 1]
            if len(verses) != want:
                wrong.append(f"{folder}: surah {n} has {len(verses)} verses, not {want}")
            if [v["n"] for v in verses] != list(range(1, len(verses) + 1)):
                wrong.append(f"{folder}: surah {n} is not numbered 1..{len(verses)}")
            for v in verses:
                if not str(v.get("text", "")).strip():
                    wrong.append(f"{folder}: surah {n} verse {v.get('n')} is empty")
            if folder == "ar":
                for v in verses:
                    if not str(v.get("said", "")).strip():
                        wrong.append(f"ar: surah {n} verse {v['n']} has no transliteration")
            here += len(verses)
        if here != TOTAL:
            wrong.append(f"{folder}: {here} verses in total, not {TOTAL}")
        counted += here
    return counted


def check_against(source: Path, wrong: list) -> int:
    """Every verse, compared with the file it was converted from. Catches a conversion that
    dropped, reordered or mangled something -- which no amount of counting would notice."""
    looked = 0
    for n in range(1, 115):
        original = read(source / f"{n}.json")["verses"]
        ours = read(QURAN / "ar" / f"{n}.json")
        for was, now in zip(original, ours):
            looked += 1
            if was["text"] != now["text"]:
                wrong.append(f"ar: surah {n} verse {was['id']} does not match the source")
        for lang in LANGS:
            theirs = read(source / lang / f"{n}.json")["verses"]
            mine = read(QURAN / lang / f"{n}.json")
            for was, now in zip(theirs, mine):
                looked += 1
                if was["translation"] != now["text"]:
                    wrong.append(f"{lang}: surah {n} verse {was['id']} does not match the source")
    return looked


def main() -> int:
    ap = argparse.ArgumentParser(prog="check_quran")
    ap.add_argument("--against", type=Path, default=None,
                    help="the quran-json chapters folder this was converted from")
    args = ap.parse_args()

    wrong: list = []
    counted = check_shape(wrong)
    print(f"shape      114 surahs, {counted:,} verses across Arabic and {len(LANGS)} translations")

    if args.against:
        looked = check_against(args.against, wrong)
        print(f"against    {looked:,} verses compared with the source, word for word")

    if wrong:
        print(f"\n{len(wrong)} PROBLEMS:", file=sys.stderr)
        for line in wrong[:40]:
            print(f"    {line}", file=sys.stderr)
        if len(wrong) > 40:
            print(f"    ... and {len(wrong) - 40} more", file=sys.stderr)
        return 1

    print("\nThe shape is right: every surah the length it should be, every verse present and\n"
          "numbered, nothing blank. That is not the same as the words being right, which needs\n"
          "somebody who reads Arabic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
