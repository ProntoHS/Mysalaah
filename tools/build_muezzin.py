#!/usr/bin/env python3
"""Prepares the muezzin for the call-to-prayer box.

    python3 tools/build_muezzin.py path/to/drawing.gif

The drawing arrives as black lines on white, the way it was drawn, and at a size meant for
looking at rather than for a mat: seven megabytes of it. Two things have to happen before it
can be shown.

It is turned inside out. The call box is black with a white border, because the call is not
part of the prayer screen and should not look as though it is. A black-on-white film in that
box is a white rectangle with a boy somewhere in it. So the film is inverted -- white lines on
black -- which is how the muezzin has always been drawn here.

And it is cut down. The box gives the muezzin two parts in seven of its width; on the 7" screen
that is about two hundred pixels and on a 1920 monitor about four hundred. Shipping a picture
four times wider than it will ever be drawn costs every mat a download and buys nothing, so it
comes down to a size with a little headroom over the largest it can appear.

The still (muezzin.png) is built from the same drawing, as a stencil: only its shape is kept,
and the app fills it with whatever colour it wants. That is what shows on a mat whose film is
missing, so the two have to be the same picture.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "azaan"

WIDE = 440        # a little over the ~400px the box gives it on a 1920 monitor
INK = 128         # darker than this is a line


def frames(source: Path):
    film = Image.open(source)
    for frame in ImageSequence.Iterator(film):
        yield frame.convert("L")
    film.close()


def build(source: Path, out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    shots = list(frames(source))
    if not shots:
        raise SystemExit(f"no frames in {source}")
    wide = WIDE
    tall = round(shots[0].height * wide / shots[0].width)

    turned = []
    for shot in shots:
        small = shot.resize((wide, tall), Image.LANCZOS)
        # Inverted, and flattened back to two colours: a grey halo left by the scaling would be
        # a grey halo on screen, and this drawing is lines, not shading.
        turned.append(small.point(lambda v: 255 if v < INK else 0).convert("L"))

    first = turned[0].convert("P", palette=Image.Palette.ADAPTIVE, colors=2)
    first.save(out / "muezzin.gif", save_all=True,
               append_images=[f.convert("P", palette=Image.Palette.ADAPTIVE, colors=2)
                              for f in turned[1:]],
               duration=Image.open(source).info.get("duration", 80), loop=0, optimize=True)

    # The still: the shape only. Transparent where the paper was, opaque where the ink was, in
    # white -- though the colour is never used, since the app fills the shape itself.
    shape = Image.new("RGBA", (wide, tall), (255, 255, 255, 0))
    shape.putalpha(turned[0])
    shape.save(out / "muezzin.png", optimize=True)

    for name in ("muezzin.gif", "muezzin.png"):
        size = (out / name).stat().st_size
        print(f"{name:14} {wide}x{tall}  {size / 1024:.0f} KB")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
