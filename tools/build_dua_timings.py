#!/usr/bin/env python3
"""Works out which word is being said when, for each du'a recording.

    python3 tools/build_dua_timings.py assets/audio/duas

Why this exists. The du'a screen lights each word red as it is spoken, the way the surahs and
the kalima already do, and to do that it needs a start and an end for every word. Nobody types
those in: they are read off the recording.

How it does it. The reliable thing in a recording is silence. Wherever the reciter stops for
breath the audio drops to room tone, and that gives a boundary that is measured rather than
guessed. So the recording is cut at its pauses into runs of speech, the words are dealt out
among those runs, and only inside a run -- where there is nothing to measure -- are the words
shared out in proportion to how much Arabic each one carries.

That last step is the estimate, which is why every file this writes is marked
`"estimated": true` and the app is free to say so. The estimate is a good deal better than
sharing the whole recording out blind: a six second du'a with three breaths in it gets four
measured anchors, and a word can never be lit while nobody is speaking.

Dealing the words out among the runs is the one decision worth explaining. It is done by
trying every way of splitting the words across the runs in order and keeping the one where each
run's share of the letters best matches its share of the speaking time -- a small dynamic
program, because being greedy about it goes wrong on the long ones: an early run that takes one
word too many pushes the error down the line and the last run ends up with a single word and
four seconds to say it in.

Needs ffmpeg to decode the audio.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from build_audio_timings import envelope, speech_gaps, share_out, weight  # noqa: E402

DUAS = ROOT / "assets" / "content" / "duas" / "duas.json"


def runs_of_speech(audio: Path, min_gap: float) -> tuple[list[tuple[float, float]], float]:
    """The stretches where somebody is talking, and how long the recording is."""
    levels, window = envelope(audio)
    duration = len(levels) * window
    first, last, gaps = speech_gaps(audio, min_gap=min_gap)
    runs, at = [], first
    for start, end in gaps:
        if start > at:
            runs.append((at, start))
        at = end
    if last > at:
        runs.append((at, last))
    return (runs or [(first, last)]), duration


def deal_out(words: list[str], runs: list[tuple[float, float]]) -> list[list[str]]:
    """Which words belong to which run of speech.

    Every run must get at least one word and the words stay in order, so this is a matter of
    choosing where to cut. Scored on how far each run's share of the letters is from its share
    of the speaking time, squared so that one badly wrong run counts for more than two slightly
    wrong ones.
    """
    if len(runs) <= 1 or len(words) <= 1:
        return [words]
    if len(runs) >= len(words):
        # More breaths than words: the pauses cannot all be word boundaries, so fall back to
        # treating the whole thing as one stretch rather than inventing splits.
        return [words]

    weights = [weight(w) for w in words]
    total_weight = sum(weights)
    speaking = sum(e - s for s, e in runs)
    want = [(e - s) / speaking for s, e in runs]

    running = [0]
    for w in weights:
        running.append(running[-1] + w)

    def share(lo: int, hi: int) -> float:
        return (running[hi] - running[lo]) / total_weight

    best = {}

    def solve(word_at: int, run_at: int) -> tuple[float, tuple[int, ...]]:
        """The best cost for the words from word_at on, spread over the runs from run_at on."""
        if (word_at, run_at) in best:
            return best[(word_at, run_at)]
        left_runs = len(runs) - run_at
        if left_runs == 1:
            cost = (share(word_at, len(words)) - want[run_at]) ** 2
            answer = (cost, (len(words),))
        else:
            answer = (float("inf"), ())
            # Leave at least one word for each run still to come.
            for cut in range(word_at + 1, len(words) - left_runs + 2):
                here = (share(word_at, cut) - want[run_at]) ** 2
                rest, where = solve(cut, run_at + 1)
                if here + rest < answer[0]:
                    answer = (here + rest, (cut,) + where)
        best[(word_at, run_at)] = answer
        return answer

    _, cuts = solve(0, 0)
    out, at = [], 0
    for cut in cuts:
        out.append(words[at:cut])
        at = cut
    return out


def settle(spans: list[tuple[float, float]], levels: list[float], window: float,
           reach: float = 0.12) -> list[tuple[float, float]]:
    """Nudge each boundary inside a run onto the quietest moment near it.

    Sharing a run out by letter count puts the boundaries roughly right and never exactly
    right, because words are not spoken at a constant number of letters per second. But a
    boundary between two words is nearly always a dip in the sound, even when it is far too
    short to count as a pause -- the mouth closes. So each boundary is allowed to slide up to
    [reach] either way onto the quietest reading it can find, which costs nothing when there is
    no dip there and snaps it onto the join when there is.

    Boundaries stay in order and a word is never squeezed to nothing: each one may only move
    within the room its neighbours leave it.
    """
    if len(spans) < 2:
        return spans
    edges = [spans[0][0]] + [s[1] for s in spans]
    steps = max(1, int(reach / window))
    for i in range(1, len(edges) - 1):
        here = int(edges[i] / window)
        low = max(int(edges[i - 1] / window) + 1, here - steps)
        high = min(int(edges[i + 1] / window) - 1, here + steps, len(levels) - 1)
        if high <= low:
            continue
        quietest = min(range(low, high + 1), key=lambda k: levels[k])
        edges[i] = quietest * window
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def times_for(audio: Path, arabic: str, min_gap: float = 0.18,
              drop: float = 13.0) -> tuple[list[list[int]], float]:
    """A [start, end] in milliseconds for every word, and the length of the recording."""
    import statistics
    words = arabic.split()
    levels, window = envelope(audio)
    duration = len(levels) * window
    quiet_db = statistics.median(levels) - drop
    first, last, gaps = speech_gaps(audio, quiet_db=quiet_db, min_gap=min_gap)
    runs, at = [], first
    for start, end in gaps:
        if start > at:
            runs.append((at, start))
        at = end
    if last > at:
        runs.append((at, last))
    runs = runs or [(first, last)]

    parcels = deal_out(words, runs)
    if len(parcels) != len(runs):
        runs = [(runs[0][0], runs[-1][1])]          # the fallback above: one stretch, one parcel
    spans: list[tuple[float, float]] = []
    for parcel, (start, end) in zip(parcels, runs):
        spans.extend(settle(share_out(parcel, start, end), levels, window))
    return [[int(round(s * 1000)), int(round(e * 1000))] for s, e in spans], duration


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_dua_timings")
    ap.add_argument("folder", type=Path, nargs="?", default=ROOT / "assets/audio/duas",
                    help="where the numbered recordings are")
    ap.add_argument("--min-gap", type=float, default=0.18,
                    help="how long a silence has to be to count as a breath, in seconds")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    book = json.loads(DUAS.read_text(encoding="utf-8"))
    done = 0
    for i, item in enumerate(book["items"], start=1):
        audio = args.folder / f"{i}.mp3"
        if not audio.is_file():
            print(f"{i:3}  no recording at {audio}")
            continue
        times, duration = times_for(audio, item["arabic"])
        item["audio"] = f"duas/{i}.mp3"
        item["seconds"] = round(duration, 3)
        item["times"] = times
        item["estimated"] = True
        words = len(item["arabic"].split())
        print(f"{i:3}  {item['key']:30} {words:3} words  {duration:5.1f}s  "
              f"{len(times):3} timings")
        done += 1

    if args.dry_run:
        print(f"\n(dry run: {done} du'as timed, nothing written)")
        return 0
    DUAS.write_text(json.dumps(book, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n-> {DUAS.relative_to(ROOT)}  ({done} du'as)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
