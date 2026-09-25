"""Makes a first set of timings for a recitation, by finding the pauses in the audio.

The pauses give reliable anchors; between them the verses are shared out in proportion to how
much text each one has. That is an estimate, not a measurement, so the file it writes is marked
`"estimated": true` and the app says so. Replace it with real timings by ear:

    python3 tools/tap_timings.py assets/audio/fatiha.json

Run: python3 tools/build_audio_timings.py assets/audio/fatiha.mp3 fatiha [--reciter NAME]

If the recording is a lesson or holds several recitations, take the one you want with --from and
--to (in seconds). The chosen stretch is copied into assets/audio as <key>.mp3:

    python3 tools/build_audio_timings.py lesson.mp3 tashahhud --from 79.9 --to 108.4

Needs ffmpeg to decode the audio.
"""
import argparse
import json
import math
import re
import statistics
import subprocess
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Arabic letters only: vowel marks and spaces shouldn't sway the share-out.
LETTERS = re.compile(r"[\u0621-\u064A]")


def envelope(audio: Path, window: float = 0.05) -> tuple[list[float], float]:
    """Loudness of the recording in dB, one reading every [window] seconds.

    ffmpeg's own silencedetect looks at single samples, and quiet room tone between phrases is
    enough to hide a pause from it. Averaging over a window finds the pauses a listener hears.
    """
    raw = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", str(audio), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True).stdout
    samples = array("h")
    samples.frombytes(raw[:len(raw) - len(raw) % 2])
    per = max(1, int(8000 * window))
    levels = []
    for i in range(0, len(samples) - per + 1, per):
        total = 0
        for v in samples[i:i + per]:
            total += (v / 32768) ** 2
        rms = math.sqrt(total / per)
        levels.append(20 * math.log10(max(rms, 1e-6)))
    return levels, window


def speech_gaps(audio: Path, quiet_db: float | None = None,
                min_gap: float = 0.30) -> tuple[float, float, list[tuple[float, float]]]:
    """Returns where speech starts and ends, and the pauses in between.

    With no threshold given, one is worked out from the recording itself: a fixed number of
    decibels below its typical loudness. Recordings differ enormously in level and in how much
    room tone sits under the voice, so a fixed threshold finds every pause in one file and none
    in the next."""
    levels, window = envelope(audio)
    if quiet_db is None:
        quiet_db = statistics.median(levels) - 16
    duration = len(levels) * window
    quiet = [db < quiet_db for db in levels]

    runs, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * window >= min_gap:
                runs.append((start * window, i * window))
            start = None
    if start is not None:
        runs.append((start * window, duration))

    first_speech, last_speech, gaps = 0.0, duration, []
    for s, e in runs:
        if s <= 0.05:
            first_speech = e
        elif e >= duration - 0.05:
            last_speech = s
        else:
            gaps.append((s, e))
    return first_speech, last_speech, gaps


def weight(text: str) -> int:
    return max(1, len(LETTERS.findall(text)))


def share_out(items: list[str], start: float, end: float) -> list[tuple[float, float]]:
    """Splits [start, end] between items in proportion to how much text each holds."""
    weights = [weight(x) for x in items]
    total = sum(weights)
    spans, t = [], start
    for i, w in enumerate(weights):
        length = (end - start) * w / total
        spans.append((t, end if i == len(items) - 1 else t + length))
        t += length
    return spans


def share_words(words: list[str], start: float, end: float, gaps: list[tuple[float, float]],
                pause_after: int | None = None) -> list[tuple[float, float]]:
    """Shares a verse's time between its words, never across a pause inside the verse.

    A reciter sometimes takes a breath part way through a long verse. The words before it and
    the words after it are shared out separately, so no word is lit during the silence. Which
    word the breath comes after is [pause_after] if known (counting from 1), otherwise the word
    boundary that text length puts nearest to it."""
    inside = [g for g in gaps if start < g[0] and g[1] < end]
    if not inside or len(words) < 2:
        return share_out(words, start, end)
    gap = max(inside, key=lambda g: g[1] - g[0])         # the one clear breath
    if pause_after is None:
        speaking = (end - start) - (gap[1] - gap[0])
        before = gap[0] - start
        weights = [weight(w) for w in words]
        total, running, best, distance = sum(weights), 0, 1, float("inf")
        for k in range(1, len(words)):
            running += weights[k - 1]
            d = abs(speaking * running / total - before)
            if d < distance:
                best, distance = k, d
        pause_after = best
    pause_after = max(1, min(len(words) - 1, pause_after))
    return (share_out(words[:pause_after], start, gap[0])
            + share_out(words[pause_after:], gap[1], end))


def parse_covers(text: str | None, total: int) -> tuple[int, int]:
    """'1' or '2-7' as a pair of indexes; the whole thing by default."""
    if not text:
        return 0, total - 1
    first, _, last = text.partition("-")
    lo = int(first) - 1
    hi = int(last) - 1 if last else lo
    if not 0 <= lo <= hi < total:
        raise SystemExit(f"--covers {text}: the text has {total} segments")
    return lo, hi


def build(audio: Path, key: str, reciter: str, quiet_db: float | None = None,
          min_gap: float = 0.30, covers: str | None = None, verse_ends: str | None = None,
          pause_after: str | None = None) -> Path:
    all_verses = json.loads((ROOT / "assets/content/core/arabic.json").read_text(encoding="utf-8"))["text"][key]
    first_covered, last_covered = parse_covers(covers, len(all_verses))
    verses = all_verses[first_covered:last_covered + 1]
    # Recordings differ in how quiet their pauses are. If none show up, listen a little less
    # strictly before giving up and sharing the whole thing out by text length.
    for step in (0, 2, 4):
        threshold = None if quiet_db is None and step == 0 else (
            (statistics.median(envelope(audio)[0]) - 16 if quiet_db is None else quiet_db) + step)
        speech_start, speech_end, gaps = speech_gaps(audio, threshold, min_gap)
        if gaps:
            if step:
                print(f"listening {step:.0f}dB less strictly to find the pauses")
            break
    span = speech_end - speech_start
    n = len(verses)

    # Where each verse would end if the reciter kept a steady pace.
    lengths = [weight(v) for v in verses]
    total = sum(lengths)
    running, expected = 0, []
    for length in lengths[:-1]:
        running += length
        expected.append(speech_start + span * running / total)

    # A pause in the audio is either the end of a verse or a breath. Treat it as a verse end only
    # where it lands close to where that verse was expected to end; otherwise ignore it.
    tolerance = span * 0.08
    fixed: dict[int, tuple[float, float]] = {}
    for gap in gaps:
        middle = (gap[0] + gap[1]) / 2
        best, distance = None, tolerance
        for k, when in enumerate(expected):
            if k in fixed:
                continue
            if abs(when - middle) < distance:
                best, distance = k, abs(when - middle)
        if best is not None:
            fixed[best] = gap

    # Fill in the boundaries no pause settled, sharing the time between the fixed ones by length.
    ends = [0.0] * n
    starts = [0.0] * n
    starts[0] = speech_start
    ends[n - 1] = speech_end
    anchors = sorted(fixed)
    previous_index, previous_time = -1, speech_start
    for k in anchors + [n - 1]:
        between = list(range(previous_index + 1, k + 1))
        stop = fixed[k][0] if k in fixed else speech_end
        shares = share_out([verses[i] for i in between], previous_time, stop)
        for i, (vs, ve) in zip(between, shares):
            starts[i], ends[i] = vs, ve
        if k in fixed:
            starts[k + 1] = fixed[k][1]
            previous_time = fixed[k][1]
        previous_index = k

    # Verse ends given by hand win over the guesswork above. An end that falls in a pause ends
    # the verse where the pause begins and starts the next where it finishes.
    if verse_ends:
        given = [float(x) for x in verse_ends.split(",")]
        if len(given) != n - 1:
            raise SystemExit(f"--ends needs {n - 1} times, one after each verse but the last")
        starts, ends_ = [speech_start], []
        for e in given:
            gap = next((g for g in gaps if g[0] - 0.02 <= e <= g[1] + 0.02), None)
            ends_.append(gap[0] if gap else e)
            starts.append(gap[1] if gap else e)
        ends = ends_ + [speech_end]
        fixed = {k: None for k in range(n - 1)}   # every verse end is now settled
    splits = {}
    for item in (pause_after or "").split(","):
        if item.strip():
            verse_no, _, word_no = item.partition(":")
            splits[int(verse_no) - 1] = int(word_no)

    segments = []
    for i, verse in enumerate(all_verses):
        if first_covered <= i <= last_covered:
            j = i - first_covered
            vs, ve = starts[j], ends[j]
            words = share_words(verse.split(), vs, ve, gaps, splits.get(i))
        else:
            # Not in this recording: a moment with no length, so nothing is highlighted for it.
            vs = ve = speech_end if i > last_covered else speech_start
            words = [(vs, ve) for _ in verse.split()]
        segments.append({
            "start": round(vs, 3),
            "end": round(ve, 3),
            "words": [{"start": round(ws, 3), "end": round(we, 3)} for ws, we in words],
        })

    out = ROOT / "assets/audio" / f"{key}.json"
    out.write_text(json.dumps({
        "schema": 1,
        "file": audio.name,
        "reciter": reciter,
        "estimated": True,
        "note": ("Verse ends that line up with a pause in the audio are real; the rest are shared "
                 "out by text length. Replace with timings taken by ear using tools/tap_timings.py."),
        "segments": segments,
    }, indent=2) + "\n", encoding="utf-8")
    covered = "" if len(verses) == len(all_verses) else (
        f" (covering segments {first_covered + 1}-{last_covered + 1} of {len(all_verses)})")
    print(f"{n} verses{covered}, {len(gaps)} pauses found, {len(fixed)} used as verse ends, "
          f"speech {speech_start:.2f}-{speech_end:.2f}s")
    print(f"wrote {out.relative_to(ROOT)}")
    return out


def extract(source: Path, key: str, start: float | None, stop: float | None) -> Path:
    """Copies the wanted stretch of a longer recording into assets/audio/<key>.mp3."""
    out = ROOT / "assets/audio" / f"{key}.mp3"
    if source.resolve() == out.resolve():
        raise SystemExit(f"{out.name} is already the file being read; "
                         "copy it elsewhere first if you want to cut a section from it")
    command = ["ffmpeg", "-v", "error", "-y"]
    if start is not None:
        command += ["-ss", f"{start:.3f}"]
    command += ["-i", str(source)]
    if stop is not None:
        command += ["-t", f"{stop - (start or 0):.3f}"]
    command += ["-c:a", "libmp3lame", "-q:a", "4", str(out)]
    subprocess.run(command, check=True)
    print(f"took {start or 0:.1f}-{stop:.1f}s into {out.relative_to(ROOT)}" if stop
          else f"copied into {out.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("key", help="recitation key, e.g. fatiha")
    ap.add_argument("--reciter", default="")
    ap.add_argument("--quiet-db", type=float, default=None,
                    help="how quiet counts as a pause (default: 16dB below the recording's own level)")
    ap.add_argument("--min-gap", type=float, default=0.30, help="shortest pause worth marking")
    ap.add_argument("--from", dest="start", type=float, default=None,
                    help="take only this part of the recording, from this second")
    ap.add_argument("--to", dest="stop", type=float, default=None, help="...to this second")
    ap.add_argument("--covers", default=None,
                    help="which segments of the text the recording actually holds, e.g. 1 or 2-7. "
                         "The rest are left with no audio.")
    ap.add_argument("--ends", dest="verse_ends", default=None,
                    help="verse ends in seconds, comma separated, one after each verse but the "
                         "last, e.g. 1.6,3.7,5.24 — for recordings that run verses together")
    ap.add_argument("--pause-after", default=None,
                    help="where a reciter breathes part way through a verse: VERSE:WORD, e.g. 7:4 "
                         "for a pause after the 4th word of verse 7 (several, comma separated)")
    args = ap.parse_args()
    audio = args.audio
    wanted = ROOT / "assets/audio" / f"{args.key}.mp3"
    if audio.resolve() != wanted.resolve():
        audio = extract(audio, args.key, args.start, args.stop)
    elif args.start is not None or args.stop is not None:
        raise SystemExit("--from/--to read from a source file outside assets/audio")
    build(audio, args.key, args.reciter, args.quiet_db, args.min_gap, args.covers,
          args.verse_ends, args.pause_after)
