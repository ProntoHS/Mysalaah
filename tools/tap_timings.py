"""Records real word timings by ear.

The estimated timings drift, because they share the audio out by how much text each verse holds.
This plays the recording and shows the words one at a time; you tap a key as each word begins,
and the timings are written from your taps. Three minutes of tapping is worth any amount of
arithmetic.

    python3 tools/tap_timings.py assets/audio/fatiha.json           # every word
    python3 tools/tap_timings.py assets/audio/fatiha.json --verses  # verse starts only

Tap SPACE (or ENTER, or the ring button, which sends the same) as each word starts. The audio
keeps playing throughout. Press R to start the verse again, S to skip back a word, Q to give up.
"""
import argparse
import json
import sys
import termios
import time
import tty
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salaah.audio import Recitation, Span  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read_keys(timeout: float = 0.0) -> str | None:
    """One keypress, without waiting for Enter."""
    import select
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if select.select([sys.stdin], [], [], timeout)[0]:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None


def verses_for(key: str) -> list[str]:
    text = json.loads((ROOT / "assets/content/core/arabic.json").read_text(encoding="utf-8"))["text"]
    return text[key]


def tap(path: Path, per_word: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    verses = verses_for(path.stem)
    audio = path.parent / data["file"]
    player = Recitation()
    if not player.available:
        raise SystemExit("No audio player found. Install one, e.g. sudo apt install mpg123")

    total = float(data["segments"][-1]["end"]) + 2
    marks: list[list[float]] = []

    print(f"\n{path.stem}: {len(verses)} verses. Tap SPACE as each word begins.")
    print("R replays the verse, Q gives up.\n")

    v = 0
    while v < len(verses):
        words = verses[v].split() if per_word else [verses[v]]
        start = max(0.0, float(data["segments"][v]["start"]) - 0.6)
        print(f"--- verse {v + 1} of {len(verses)}: {verses[v]}")
        player.play(audio, Span(start, total))
        taps: list[float] = []
        begun = time.monotonic()
        i = 0
        while i < len(words):
            print(f"    [{i + 1}/{len(words)}] {words[i]}", end="\r", flush=True)
            key = read_keys(0.02)
            if key is None:
                if not player.playing:
                    break
                continue
            if key in (" ", "\r", "\n"):
                taps.append(start + (time.monotonic() - begun))
                i += 1
            elif key.lower() == "s" and i:
                i -= 1
                taps.pop()
            elif key.lower() == "r":
                taps, i = [], 0
                player.play(audio, Span(start, total))
                begun = time.monotonic()
            elif key.lower() == "q":
                player.stop()
                raise SystemExit("nothing written")
        player.stop()
        if len(taps) < len(words):
            print(f"\n    only {len(taps)} of {len(words)} taps; press R-enter to redo, or ENTER to keep")
            if (input("    ") or "").strip().lower() == "r":
                continue
            taps += [taps[-1] if taps else start] * (len(words) - len(taps))
        marks.append(taps)
        print()
        v += 1

    # A word ends where the next one starts; the last word of a verse ends where the next begins.
    flat = [(vi, wi, t) for vi, taps in enumerate(marks) for wi, t in enumerate(taps)]
    segments = []
    for vi, taps in enumerate(marks):
        words = []
        for wi, t in enumerate(taps):
            nxt = None
            for ovi, owi, ot in flat:
                if (ovi, owi) > (vi, wi):
                    nxt = ot
                    break
            words.append({"start": round(t, 3), "end": round(nxt if nxt else t + 2.0, 3)})
        segments.append({
            "start": words[0]["start"],
            "end": words[-1]["end"],
            "words": words if per_word else [
                {"start": words[0]["start"], "end": words[-1]["end"]}
                for _ in verses[vi].split()
            ],
        })

    data["segments"] = segments
    data["estimated"] = False
    data["note"] = "Timings taken by ear with tools/tap_timings.py."
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(ROOT)} — timings are no longer marked as estimated")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("timings", type=Path)
    ap.add_argument("--verses", action="store_true", help="tap verse starts only, not every word")
    args = ap.parse_args()
    tap(args.timings, per_word=not args.verses)
