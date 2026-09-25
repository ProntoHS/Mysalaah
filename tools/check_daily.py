#!/usr/bin/env python3
"""Checks the daily Qur'an passages against a reference text, word by word.

Ten of the passages in assets/content/daily/quran.json are a clause of a verse rather than the
whole of it, because the whole verse would not read across a room. That is the sort of edit that
can go wrong invisibly: a cut in the wrong place, a letter lost while moving the text about. So
this asks a corpus nobody here has touched whether each stored passage is still an unbroken run
of the words of the verse it claims to be.

    pip install quran-text
    python3 tools/check_daily.py

It prints a line per passage that does not check out and exits non-zero. Silence means every one
of them reads as part of its verse, with nothing altered in between.

The comparison is on the bare consonants, so the two texts' different conventions for vowel and
recitation marks cannot raise a false alarm -- and cannot hide a changed letter either, which is
the thing being looked for.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

DAILY = Path(__file__).resolve().parent.parent / "assets/content/daily/quran.json"

MARKS = {chr(c) for c in range(0x600, 0x900) if unicodedata.category(chr(c)) == "Mn"}
MARKS |= {chr(0x640)}                       # tatweel: a stretch of the line, not a letter
SAME = (("ٱ", "ا"), ("آ", "ا"), ("أ", "ا"), ("إ", "ا"),
        ("ئ", "ي"), ("ؤ", "و"), ("ى", "ي"), ("ی", "ي"),
        ("ء", ""), ("ة", "ه"))


def skeleton(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = "".join(c for c in text if c not in MARKS)
    for one, other in SAME:
        text = text.replace(one, other)
    return " ".join(re.sub(r"[^ء-ي\s]", " ", text).split())


def reference_text() -> dict[str, str]:
    """Every verse of the reference corpus, keyed "sura:ayah"."""
    try:
        import quran_text_data
    except ImportError:
        sys.exit("needs the reference text: pip install quran-text")
    book = json.loads((Path(quran_text_data.__file__).parent / "hafs.json").read_text())
    words, starts = book["words"], book["ayah_starts"]
    out = {}
    for number, sura in enumerate(book["surahs"], start=1):
        for ayah in range(1, sura["ayah_count"] + 1):
            i = sura["first_ayah"] + ayah - 1
            end = starts[i + 1] if i + 1 < len(starts) else len(words)
            out[f"{number}:{ayah}"] = " ".join(words[starts[i]:end])
    return out


def main() -> int:
    book = reference_text()
    passages = json.loads(DAILY.read_text())["passages"]
    wrong = []
    part = 0
    for passage in passages:
        ref, stored = passage["reference"], skeleton(passage["arabic"])
        whole = skeleton(book.get(ref, ""))
        if not whole:
            wrong.append(f"{ref}: no such verse in the reference text")
            continue
        if stored == whole:
            continue
        # A clause: it has to sit in the verse on whole words, at one end or between two spaces.
        if whole.startswith(f"{stored} ") or whole.endswith(f" {stored}") \
                or f" {stored} " in whole:
            part += 1
            continue
        wrong.append(f"{ref}: not an unbroken run of that verse's words\n"
                     f"      stored    {stored}\n      reference {whole}")
    print(f"{len(passages)} passages: {len(passages) - part - len(wrong)} whole verses, "
          f"{part} a clause of one, {len(wrong)} wrong")
    for line in wrong:
        print("  FAIL", line)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
