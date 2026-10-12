#!/usr/bin/env python3
"""Squeezes the front door's animation, and cuts the still that stands in for it.

    python3 tools/make_front_film.py <harry's.gif> assets/welcome

WHY IT NEEDS SQUEEZING. The film arrives at 7MB for 28 frames of two-tone artwork, which is
what an exporter does when it writes every frame whole in a palette built for photographs. The
mat fetches its updates over somebody's home Wi-Fi and keeps them on an SD card, and 7MB of
that is a picture of the word "My" in seven languages. Re-written in a short palette it is
about a third of a megabyte and looks the same.

SIXTEEN GREYS, where the menu sheets use four. The sheets are line art and four is plenty for
them; this one spends three frames in four crossfading one word into the next, and a crossfade
is nothing but the greys in between. Measured on this film: four greys are out by 1.46 of 255
at worst and visibly darken the half-faded lettering, sixteen are out by 0.92 and do not, and
the difference between them is 180kB.

THE TIMING IS KEPT FRAME BY FRAME, which is the thing a careless re-encode loses. Harry's film
holds each language for 700ms and then crosses to the next over three frames of 100ms; written
out with one duration for all 28 it becomes a flicker with no pauses in it, which is not the
same animation at all.

WHICH WAY ROUND. Harry sent two films, one black on white and one white on black, and they are
the same pixels inverted -- so only the light one is kept and the mat turns it over after dark,
the way it does with every other drawing it has. See filmsheet.draw_themed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Black, white, and fourteen steps between them: enough that a crossfade is a crossfade.
GREYS = tuple(round(i * 255 / 15) for i in range(16))


def shades():
    from PIL import Image
    palette = Image.new("P", (1, 1))
    palette.putpalette([v for grey in GREYS for v in (grey, grey, grey)]
                       + [0] * (768 - 3 * len(GREYS)))
    return palette


def build(source: Path, folder: Path) -> int:
    from PIL import Image, ImageSequence

    film = Image.open(source)
    frames, held = [], []
    for frame in ImageSequence.Iterator(film):
        frames.append(frame.convert("L"))
        held.append(frame.info.get("duration", 100))
    if len(frames) < 2:
        raise SystemExit(f"{source.name} has {len(frames)} frame(s); that is a still")

    # Which way up it is, from the field it is drawn on. The mat keeps its drawings dark on
    # light and turns them over after dark, so a film that arrives the other way round is
    # inverted here once rather than on every frame of every repaint for the life of the mat.
    if frames[0].getpixel((0, 0)) < 128:
        print("  framed in black, so it is the night version: inverting it")
        frames = [Image.eval(f, lambda v: 255 - v) for f in frames]

    palette = shades()
    keep = [f.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
            for f in frames]
    out = folder / "front.gif"
    keep[0].save(out, save_all=True, append_images=keep[1:], loop=0,
                 duration=held, optimize=True, disposal=1)
    print(f"  {out.name}: {len(keep)} frames, {sum(held)}ms round, "
          f"{source.stat().st_size / 1e6:.2f}MB -> {out.stat().st_size / 1e6:.2f}MB")

    # And the one frame that stands in for the whole thing where there is no film to play:
    # the longest-held frame, which is the one the animation rests on.
    rest = held.index(max(held))
    still = folder / "front.png"
    keep[rest].save(still, optimize=True)
    print(f"  {still.name}: frame {rest}, the one it rests on, "
          f"{still.stat().st_size / 1e3:.0f}kB")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="the film as it was drawn")
    ap.add_argument("folder", type=Path, nargs="?", default=Path("assets/welcome"))
    args = ap.parse_args()
    return build(args.source if args.source.is_absolute() else ROOT / args.source,
                 args.folder if args.folder.is_absolute() else ROOT / args.folder)


if __name__ == "__main__":
    raise SystemExit(main())
