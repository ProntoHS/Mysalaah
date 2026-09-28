#!/usr/bin/env python3
"""Finds where each line of the call to prayer falls in a recording.

    python3 tools/build_azaan_times.py assets/audio/azaan.mp3 --call ordinary
    python3 tools/build_azaan_times.py assets/audio/azaan-fajr.mp3 --call fajr

The adhan is chanted line by line with a breath between each, so the lines are IN the recording
as stretches of sound separated by quiet -- they do not have to be guessed at. This measures
them and writes assets/content/azaan/times.json, which the call screen reads to know which line
to light and when.

Why not ffmpeg's silencedetect on its own: it takes one level for the whole file, and a
recording made in a room has a reverb tail that never drops to that level between lines. So the
quiet is measured RELATIVE to how quiet that part of the recording gets: a valley 8 dB above
the local floor is a breath, whatever the absolute level is.

That is still not enough for every recording, and this does not pretend otherwise. A line
chanted loudly with a long tail on it can swallow the breath after it, and then two lines read
as one. Attempts to break such a stretch open by looking for the valley inside it were dropped:
one of them produced the right NUMBER of lines by splitting the wrong stretch, leaving a
1.5-second fragment standing in for a whole line. A count that comes out right is not evidence
that the lines landed in the right places. So when the count does not come out, this writes
nothing and the timings are tapped in by ear instead -- run this again with --tap and tap them in.

It refuses rather than guesses. The ordinary call has twelve stretches and Fajr has fourteen --
the four opening Allahu akbar are chanted in two pairs, as are the closing two. If the count
does not come out, the recording is not the call this was told it was, or the detection needs a
different threshold, and either way writing a mapping would put the wrong words on the screen.
Nothing is written in that case.

Within a line the words are spread by how long each one takes to say, not measured -- so the
whole line is right and the word inside it is close. That is recorded as "estimated": true, and
the screen is free to show only the line if that is not good enough.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMES = ROOT / "assets" / "content" / "azaan" / "times.json"
ADHAN = ROOT / "assets" / "content" / "azaan" / "adhan.json"

RATE = 16000           # what the audio is decoded to; plenty for finding a pause
HOP = 320              # 20 ms frames
ABOVE_FLOOR = 8.0      # dB above the local quietest: below this counts as quiet
QUIET = 0.35           # seconds; shorter than this is a catch of breath mid-line
SOUND = 0.8            # seconds; a stretch shorter than this is a cough, not a line


def envelope(path: Path):
    """The loudness of the recording, in dB, one number every 20 ms."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a",
                          "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True).stdout
    if not raw:
        raise SystemExit(f"Could not decode {path}. Is ffmpeg installed?")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    frames = x[:len(x) // HOP * HOP].reshape(-1, HOP)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    return 20.0 * np.log10(rms)


WINDOW = 12.0          # seconds either side that the local floor is taken over


def local_floor(db):
    """How quiet this recording gets NEAR each moment, rather than across the whole of it.

    This is the whole point. One level for the file is what made silencedetect merge the last
    two lines of azaan.mp3: the closing is chanted louder and with more room on it than the
    opening, so the breath before the tahlil never drops to the level that the quiet early on
    sets. Measured over twelve seconds either side, that same breath is plainly a valley.
    """
    import numpy as np
    span = int(WINDOW * RATE / HOP)
    floor = np.empty_like(db)
    for i in range(len(db)):
        lo, hi = max(0, i - span), min(len(db), i + span + 1)
        floor[i] = np.percentile(db[lo:hi], 5)
    return floor


def stretches(db) -> list[tuple[float, float]]:
    """The stretches of chanting, as (start, end) in seconds."""
    loud = db > local_floor(db) + ABOVE_FLOOR
    runs, start = [], None
    for i, on in enumerate(loud):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(loud)))
    # Join anything separated by less than a breath: a line has quiet moments inside it.
    joined: list[list[int]] = []
    for a, b in runs:
        if joined and (a - joined[-1][1]) * HOP / RATE < QUIET:
            joined[-1][1] = b
        else:
            joined.append([a, b])
    secs = [(a * HOP / RATE, b * HOP / RATE) for a, b in joined]
    return [(a, b) for a, b in secs if b - a >= SOUND]


def spread(line: str, start: float, end: float) -> list[list[int]]:
    """Word times inside a line, by how long each word takes to say.

    Letters, not words: the words of the adhan are wildly different lengths, and splitting the
    line into equal shares would put the red on "akbar" while the muezzin is still on "Allahu".
    """
    words = line.split()
    weights = [max(1, len(w)) for w in words]
    total = sum(weights)
    times, at = [], start
    for weight in weights:
        step = (end - start) * weight / total
        times.append([int(at * 1000), int((at + step) * 1000)])
        at += step
    return times



def read_key(timeout: float = 0.0) -> str | None:
    """One keypress, without waiting for Enter."""
    import select
    import sys as _sys
    import termios
    import tty
    fd = _sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if select.select([_sys.stdin], [], [], timeout)[0]:
            return _sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None


def tap(recording: Path, call: str, described: dict) -> int:
    """Play the call and take the line starts from somebody listening to it.

    For a recording the measuring above will not take apart. Twelve taps for the ordinary call
    and fourteen for Fajr, over about three minutes -- which is the only way to get it right
    when the recording will not come apart on its own, and is better than a clever guess.
    """
    import time as _time
    sys.path.insert(0, str(ROOT))
    from salaah.audio import Call as Player

    order = described["calls"][call]
    words = {line["key"]: line["arabic"] for line in described["lines"]}
    said = {line["key"]: line["said"] for line in described["lines"]}
    player = Player()
    if not player.available:
        print("No audio player found. Install one with: sudo apt install mpg123", file=sys.stderr)
        return 1

    print(f"\n{recording.name}: tap SPACE as each line BEGINS. Q gives up, nothing is written.")
    print(f"{len(order)} lines to tap.\n")
    for i, key in enumerate(order, 1):
        print(f"  {i:2d}. {said[key]}")
    input("\nPress ENTER to start playing. ")

    if not player.play(recording):
        print("Could not play the recording.", file=sys.stderr)
        return 1
    started, taps = _time.monotonic(), []
    while len(taps) < len(order):
        key = read_key(0.05)
        if key in ("q", "Q"):
            player.stop()
            print("\nGave up. Nothing written.")
            return 1
        if key in (" ", "\r", "\n"):
            taps.append(_time.monotonic() - started)
            at = len(taps)
            print(f"  {at:2d}/{len(order)}  {taps[-1]:7.2f}s  {said[order[at - 1]]}")
        if not player.playing and len(taps) < len(order):
            print(f"\nThe recording ended with {len(taps)} of {len(order)} lines tapped. "
                  f"Nothing written.", file=sys.stderr)
            return 1
    player.stop()

    # Each line runs from its tap to the next one; the last runs to the end of the recording.
    whole = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "default=nw=1:nk=1", str(recording)],
                                 capture_output=True, text=True).stdout or 0)
    edges = [(taps[i], taps[i + 1] if i + 1 < len(taps) else whole) for i in range(len(taps))]
    if any(b <= a for a, b in edges):
        print("Those taps do not run forwards. Nothing written.", file=sys.stderr)
        return 1
    times = json.loads(TIMES.read_text(encoding="utf-8")) if TIMES.is_file() else {}
    times[recording.name] = {
        "call": call,
        "estimated": True,          # the lines are tapped; the word inside a line is still spread
        "tapped": True,
        "lines": [{"key": key, "start": int(a * 1000), "end": int(b * 1000),
                   "words": spread(words[key], a, b)}
                  for key, (a, b) in zip(order, edges)],
    }
    TIMES.write_text(json.dumps(times, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n-> {TIMES.relative_to(ROOT)}, from {len(taps)} taps")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_azaan_times")
    ap.add_argument("recording", type=Path)
    ap.add_argument("--call", required=True, choices=("ordinary", "fajr"),
                    help="which call this recording is: Fajr carries two lines the others do not")
    ap.add_argument("--dry-run", action="store_true", help="say what was found, write nothing")
    ap.add_argument("--tap", action="store_true",
                    help="take the line starts by ear instead, for a recording the measuring "
                         "will not take apart")
    args = ap.parse_args()

    if not args.recording.is_file():
        print(f"No recording at {args.recording}.", file=sys.stderr)
        return 1
    described = json.loads(ADHAN.read_text(encoding="utf-8"))
    order = described["calls"][args.call]
    words = {line["key"]: line["arabic"] for line in described["lines"]}

    if args.tap:
        return tap(args.recording, args.call, described)

    found = stretches(envelope(args.recording))
    print(f"{args.recording.name}: {len(found)} stretches of chanting, "
          f"{args.call} expects {len(order)}")
    for i, (a, b) in enumerate(found, 1):
        said = order[i - 1] if i <= len(order) else "?"
        print(f"  {i:2d}  {a:7.2f} -> {b:7.2f}  {b - a:5.2f}s   {said}")
    if len(found) != len(order):
        print(f"\nRefusing to write: found {len(found)} lines, the {args.call} call has "
              f"{len(order)}. Either this is not that call, or the pauses in this recording "
              f"need a different setting. Nothing written.", file=sys.stderr)
        return 1

    times = json.loads(TIMES.read_text(encoding="utf-8")) if TIMES.is_file() else {}
    times[args.recording.name] = {
        "call": args.call,
        "estimated": True,          # the LINES are measured; the word inside a line is not
        "lines": [{"key": key,
                   "start": int(a * 1000), "end": int(b * 1000),
                   "words": spread(words[key], a, b)}
                  for key, (a, b) in zip(order, found)],
    }
    if args.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    TIMES.parent.mkdir(parents=True, exist_ok=True)
    TIMES.write_text(json.dumps(times, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n-> {TIMES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
