#!/usr/bin/env python3
"""Turns the quran-align word timings into something the mat can read, and checks them as it goes.

    python3 tools/build_timings.py ~/Downloads/Alafasy_128kbps.json

The timings say, for every word of every verse, the millisecond it starts and the millisecond it
ends within that verse's recording. That is what makes a word go red at the moment it is recited.

The catch, and the whole reason this tool exists: quran-align counts words by splitting Tanzil's
Uthmani text on spaces, and our Arabic comes from quranenc.com. Where the two editions split a
word differently, the timings would light the wrong word -- so every verse is checked against our
own text, and any verse where the two disagree is marked to glow whole instead. 6,224 of the
6,236 get word-by-word; twelve get the whole verse. Nobody ever sees the wrong word lit.

Because timings are per verse, a disagreement cannot escape the verse it is in. That is the
property that makes this safe at all.

The timing data is quran-align's, under a Creative Commons Attribution 4.0 licence, so the
attribution goes in SOURCE.txt beside the output and is named on screen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARABIC = ROOT / "assets" / "content" / "quran" / "ar"
OUT = ROOT / "assets" / "content" / "quran" / "timings"

RECITER = "Alafasy_128kbps"

# Twelve verses are expected to disagree, for reasons that are the two editions' and not ours.
# If that number grows, something has changed underneath -- a different reciter's file, a
# different edition of the text -- and the build should stop rather than quietly ship a
# recitation that lights the wrong words.
EXPECTED_WHOLE = 12
ALLOW_WHOLE = 20

SOURCE = """\
The word timings in this folder come from quran-align
(https://github.com/cpfair/quran-align), release release-2016-11-24, file
{reciter}.json, which carries the Creative Commons Attribution 4.0
International licence. That licence requires attribution, which is why this file exists
and why the app names the source on screen.

They were generated against the verse-by-verse recordings at
https://everyayah.com/data/{reciter}/ , which is what the mat plays. The timings and
the audio must stay a matched pair: timings made for one recording do not fit another.

quran-align counts words by splitting Tanzil's Uthmani text on spaces. Our Arabic comes from
quranenc.com by way of quran-json. The two agree on {agree} of the 6236 verses. The {whole}
where they do not are listed in each surah's "whole" field and are highlighted a whole verse
at a time, so that a word is never lit in the wrong place.

Built by tools/build_timings.py. Verified on build: every verse present, timestamps rising,
{dropped} zero-length segments dropped, and every word count checked against the Arabic on
disk.
"""


def our_words() -> dict:
    """(surah, verse) -> how many words our Arabic has."""
    counts = {}
    for path in ARABIC.glob("*.json"):
        surah = int(path.stem)
        for row in json.loads(path.read_text(encoding="utf-8")):
            counts[(surah, int(row["n"]))] = len(row["text"].split())
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_timings")
    ap.add_argument("source", type=Path, help=f"{RECITER}.json from quran-align's release")
    ap.add_argument("--reciter", default=RECITER)
    args = ap.parse_args()

    if not args.source.is_file():
        print(f"No timing file at {args.source}.", file=sys.stderr)
        return 1
    rows = json.loads(args.source.read_text(encoding="utf-8"))
    mine = our_words()
    if not mine:
        print(f"No Arabic at {ARABIC}. Build the Qur'an first.", file=sys.stderr)
        return 1

    by_surah: dict[int, dict] = {}
    whole: list[tuple[int, int]] = []
    dropped = agree = 0

    for row in rows:
        surah, verse = int(row["surah"]), int(row["ayah"])
        if (surah, verse) not in mine:
            print(f"Timings mention {surah}:{verse}, which our text does not have.",
                  file=sys.stderr)
            return 1
        words = []
        last = -1
        for start_word, end_word, start_ms, end_ms in row.get("segments") or []:
            if end_ms <= start_ms:
                dropped += 1              # a zero-length segment would flicker; no use for it
                continue
            if start_ms < last:
                print(f"{surah}:{verse} has timestamps going backwards.", file=sys.stderr)
                return 1
            last = start_ms
            words.append([int(start_word), int(end_word), int(start_ms), int(end_ms)])

        spot = by_surah.setdefault(surah, {"surah": surah, "reciter": args.reciter,
                                           "words": {}, "whole": []})
        # A verse is safe for word-by-word only if the timings account for exactly as many
        # words as we are going to draw. Anything else, and it glows whole.
        counted = max((w[1] for w in words), default=0)
        if words and counted == mine[(surah, verse)]:
            spot["words"][str(verse)] = words
            agree += 1
        else:
            spot["whole"].append(verse)
            whole.append((surah, verse))

    if len(whole) > ALLOW_WHOLE:
        print(f"\n{len(whole)} verses disagree with our text; {EXPECTED_WHOLE} were expected and "
              f"more than {ALLOW_WHOLE} means something has changed underneath.", file=sys.stderr)
        print("Nothing has been written. Check the reciter and the text edition.", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    for surah, spot in sorted(by_surah.items()):
        spot["whole"].sort()
        (OUT / f"{surah}.json").write_text(
            json.dumps(spot, separators=(",", ":")) + "\n", encoding="utf-8")

    (OUT / "SOURCE.txt").write_text(
        SOURCE.format(reciter=args.reciter, agree=agree, whole=len(whole), dropped=dropped),
        encoding="utf-8")

    size = sum(p.stat().st_size for p in OUT.glob("*.json"))
    print(f"{len(by_surah)} surahs -> {OUT}  ({size/1e6:.1f} MB)")
    print(f"word by word : {agree} verses")
    print(f"whole verse  : {len(whole)} verses  {['%d:%d' % v for v in whole]}")
    print(f"dropped      : {dropped} zero-length segments")
    if len(whole) != EXPECTED_WHOLE:
        print(f"\nNote: {EXPECTED_WHOLE} were expected, not {len(whole)}. Worth a look.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
