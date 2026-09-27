#!/usr/bin/env python3
"""Works out when each word of each kalima is said, so the words can go red as they are.

    python3 tools/build_kalima_times.py

Be clear about what this is. The Qur'an's timings were measured, word by word, by somebody who
built a forced aligner and checked it against an independent one. These are ESTIMATED: there is
no aligner here and no published timings for these recordings, because they are Harry's own.

What is measured, and reliable:
  * how long each recording is
  * where the speech starts and stops, found from the silence at either end

What is estimated, and will drift:
  * where one word ends and the next begins, shared out across the speech in proportion to how
    many letters each word has, ignoring the vowel marks, which are written but take no time

So the first word lights when the voice starts and the last finishes when it stops -- those two
moments are right -- and in between the red can run ahead of or behind the voice, more so on the
longer kalima. Every entry is marked estimated, and the honest fix is to tap them in by hand
with the tap-along tool the app already has for the prayer phrases.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "assets" / "audio" / "kalima"
KALIMA = ROOT / "assets" / "content" / "duas" / "kalima.json"

QUIET = "-32dB"        # below this counts as silence
BRIEF = 0.12           # and it has to last this long to be a pause rather than a consonant

# A word needs a moment even if it is two letters, and the gap between words is not nothing.
FLOOR_WEIGHT = 2.0


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def speech_span(path: Path, whole: float) -> tuple[float, float]:
    """When the voice starts and stops, from the silence at either end.

    This is the measured part. Without it the first word would light at zero and sit red
    through however much quiet the recording opens with.
    """
    try:
        found = subprocess.run(
            ["ffmpeg", "-i", str(path), "-af", f"silencedetect=noise={QUIET}:d={BRIEF}",
             "-f", "null", "-"], capture_output=True, text=True).stderr
    except OSError:
        return 0.0, whole
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", found)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", found)]
    # Leading silence: a silence that ends before any silence begins started at the top.
    begin = ends[0] if ends and (not starts or ends[0] <= starts[0]) else 0.0
    # Trailing silence. Not "a silence that never ends" -- ffmpeg closes the last one at the
    # end of the file, so counting starts against ends never spots it and the last word was
    # left running on through the quiet. It is the silence whose end IS the end of the file.
    finish = whole
    if starts and ends and ends[-1] >= whole - 0.05:
        finish = starts[-1]
    elif len(starts) > len(ends):
        finish = starts[-1]
    if finish - begin < whole * 0.3:          # the detector lost its footing; use the lot
        return 0.0, whole
    return max(0.0, begin), min(whole, finish)


def weight(word: str) -> float:
    """Roughly how long a word takes to say: its letters, not its vowel marks.

    Arabic writes short vowels as marks above and below the letters. They are part of the word
    and take no extra time to say, so counting them would make a heavily marked word look
    longer than it sounds.
    """
    letters = sum(1 for ch in word if not unicodedata.combining(ch))
    return max(FLOOR_WEIGHT, float(letters))


def times_for(words: list[str], begin: float, finish: float) -> list[list[int]]:
    """One [start_ms, end_ms] per word, filling the speech in proportion to the letters."""
    weights = [weight(w) for w in words]
    total = sum(weights)
    span = max(0.1, finish - begin)
    out, at = [], begin
    for i, part in enumerate(weights):
        length = span * part / total
        end = finish if i == len(words) - 1 else at + length
        out.append([int(round(at * 1000)), int(round(end * 1000))])
        at = end
    return out


def main() -> int:
    if not KALIMA.is_file():
        print(f"No kalima at {KALIMA}.", file=sys.stderr)
        return 1
    book = json.loads(KALIMA.read_text(encoding="utf-8"))
    items = book.get("items", [])
    missing = [i for i in range(1, len(items) + 1) if not (AUDIO / f"{i}.mp3").is_file()]
    if missing:
        print(f"No recording for kalima {missing}. Nothing written.", file=sys.stderr)
        return 1

    for number, item in enumerate(items, 1):
        path = AUDIO / f"{number}.mp3"
        whole = duration(path)
        begin, finish = speech_span(path, whole)
        words = item["arabic"].split()
        item["audio"] = f"kalima/{number}.mp3"
        item["seconds"] = round(whole, 3)
        item["times"] = times_for(words, begin, finish)
        item["estimated"] = True
        print(f"kalima {number}: {len(words):3} words  {whole:6.2f}s  "
              f"voice {begin:5.2f}-{finish:5.2f}s  "
              f"({(finish - begin) / len(words):.2f}s a word on average)")
        if len(item["times"]) != len(words):
            print("   the timings do not cover the words; nothing written", file=sys.stderr)
            return 1

    KALIMA.write_text(json.dumps(book, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n-> {KALIMA}")
    print("All marked estimated. The first and last moments are measured; the joins are not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
