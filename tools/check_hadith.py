#!/usr/bin/env python3
"""Checks every daily saying against a second, independent copy of the collections.

The sayings in assets/content/daily/hadith.json were taken from one public-domain dataset. One
dataset can carry a typo, and a saying of the Prophet is not something to take on a single
source, so each one is also looked for in a corpus that had no part in producing this file: the
MIT-licensed 'hadith' package, 62,178 narrations across the nine collections.

    pip install hadith
    python3 tools/check_hadith.py

It prints a line per saying that cannot be found and exits non-zero. Silence means every one of
them appears, word for word, in the other corpus as well.

What it does not check: that the reference number is right, or that the saying is sound. Only
that the Arabic in this file is Arabic that really appears in the collections. The numbering can
be checked a line at a time on sunnah.com, and the content by a qualified reviewer -- neither of
which a script can do.
"""
import csv
import glob
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

DAILY = Path(__file__).resolve().parent.parent / "assets/content/daily/hadith.json"

# The marks the two corpora write differently: vowels, the recitation marks, the stretch of the
# line. Taking them off compares the letters, which is where a typo would be.
DROP = {chr(c) for c in range(0x600, 0x700) if unicodedata.category(chr(c)) == "Mn"}
DROP |= {chr(0x640), chr(0x670), chr(0x200e), chr(0x200f)}
PUNCT = set("،.,:;!?()[]«»\"'‘’“”-–—")
SAME = (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"),
        ("ى", "ي"), ("ة", "ه"), ("ﷺ", ""))


def bare(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFC", text)
                   if c not in DROP and c not in PUNCT)
    for one, other in SAME:
        text = text.replace(one, other)
    return re.sub(r"\s+", " ", text).strip()


def corpus() -> str:
    try:
        import hadith
    except ImportError:
        sys.exit("needs the second corpus: pip install hadith")
    folder = Path(hadith.__file__).parent / "data"
    files = sorted(glob.glob(str(folder / "*.csv.gz")))
    if not files:
        sys.exit(f"the hadith package has no data in {folder}")
    parts = []
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            parts.append(" || ".join(row[0] for row in csv.reader(f) if row))
    return bare(" || ".join(parts))


def main() -> int:
    everything = corpus()
    sayings = json.loads(DAILY.read_text())["sayings"]
    missing = [s for s in sayings if bare(s["arabic"]) not in everything]
    print(f"{len(sayings)} sayings: {len(sayings) - len(missing)} found in the second corpus, "
          f"{len(missing)} not")
    for s in missing:
        print(f"  FAIL {s['reference']}: not found\n       {s['arabic']}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
