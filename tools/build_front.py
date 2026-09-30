#!/usr/bin/env python3
"""Prepares the front door -- the screen the mat opens on.

    python3 tools/build_front.py path/to/MySalaah.gif

Takes the drawing as supplied and writes assets/welcome:

  mosque.gif    the animation, as drawn
  mosque.png    the same drawing's first frame, as the still the film is laid over
  mosque.json   where the dome's clock goes and where the name is, in the drawing's own pixels
  arch-enter.png  a mask of the name panel, which is what the app lights when it is pressed

Three things are measured off the drawing rather than typed in, because a number typed in is a
number that goes stale the moment the artwork is redrawn:

  the dome     the second largest white shape, and the clock box is the flat middle of it. A
               dome curves away either side of the numbers, so the box is inset from its widest
               row and the app adds its own allowance back on top.
  the name     the enclosed dark shapes sitting in the building's front, which is the lettering.
               Their bounding box, given a margin, is what you touch to go in.
The animation is re-encoded on the way in. It arrives as eighty full frames of dithered grey
and weighs seventeen megabytes, which is most of a release on its own for a drawing that is
black, white and two shades between. Cut to four greys it is half a megabyte, keeps its
antialiasing, and the seven per cent of the picture that actually moves compresses the way GIF
has always meant it to.

Unlike the other two mosques, this drawing's sky is left solid rather than made see-through. It
brings its own sun, its own stars and its own moon, all of them moving, and the app's sky drawn
behind would put a second moon next to the one already there. That also means the app need not
paint a sky for this screen at all, which on a mat that sits on the front door all day is a
timer waking the Pi thirty times a second to draw something nobody can see.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "welcome"

SHAPE = 1920 / 1008   # the screen under the strip, at 1080p
WHITE = 140           # lighter than this is the building
CLOCK_INSET = 0.08    # keep the numbers clear of where the dome curves away
NAME_MARGIN = 0.02    # room round the lettering, as a share of the picture's width
GREYS = 4             # shades kept when the animation is re-encoded


def shapes(mask: np.ndarray):
    """Every separate piece of [mask], largest first, as (size, bounding box)."""
    labels, count = ndimage.label(mask)
    if not count:
        return []
    sizes = ndimage.sum(mask, labels, range(1, count + 1))
    out = []
    for k in np.argsort(sizes)[::-1]:
        ys, xs = np.nonzero(labels == k + 1)
        out.append((int(sizes[k]), (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                    labels == k + 1))
    return out


def dome_clock(white: np.ndarray) -> tuple[int, int, int, int]:
    """The flat middle of the dome: where the time is written.

    The dome is its own white shape -- it is joined to the building only by a neck too thin to
    survive, which is a property of every dome anybody draws. Its widest row is its belly; the
    box is that row inset either side, and tall enough to reach up to where the curve starts
    closing in.
    """
    pieces = shapes(white)
    if len(pieces) < 2:
        raise SystemExit("no dome found: expected the building and then the dome")
    _, (x0, y0, x1, y1), piece = pieces[1]
    widths = [(np.count_nonzero(piece[y]), y) for y in range(y0, y1 + 1)]
    widest, belly = max(widths)
    row = np.nonzero(piece[belly])[0]
    inset = int(widest * CLOCK_INSET)
    left, right = int(row.min()) + inset, int(row.max()) - inset
    # Up as far as the dome is still at least three quarters of its widest, which is where the
    # numbers would start to touch the curve.
    top = belly
    for y in range(belly, y0 - 1, -1):
        if np.count_nonzero(piece[y]) < widest * 0.75:
            break
        top = y
    return left, top, right, min(y1, belly + int((belly - top) * 0.55))


def name_panel(white: np.ndarray, width: int) -> tuple[int, int, int, int]:
    """The lettering across the building's front: what you touch to go in."""
    dark = ~white
    labels, count = ndimage.label(dark)
    edge = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    edge.discard(0)
    inside = [i for i in range(1, count + 1) if i not in edge]
    if not inside:
        raise SystemExit("no lettering found on the front of the building")
    sizes = ndimage.sum(dark, labels, inside)
    # The letters are the big enclosed shapes; the small ones are windows and slots.
    biggest = max(sizes)
    boxes = []
    for k, i in enumerate(inside):
        if sizes[k] < biggest * 0.3:
            continue
        ys, xs = np.nonzero(labels == i)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    pad = int(width * NAME_MARGIN)
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


def build(source: Path, out: Path = OUT) -> None:
    film = Image.open(source)
    frames = getattr(film, "n_frames", 1)
    film.seek(0)

    # Widened to the shape of the screen before anything is measured. The drawing is 1227x733,
    # which is 1.67 wide; the screen under the strip is 1.90, so shown as it came it sits in the
    # middle with a black bar either side. The bars are added here instead, out of the drawing's
    # own sky, which means they invert with everything else and are simply not there to see on
    # either screen.
    def widen(frame: Image.Image) -> Image.Image:
        want = int(round(frame.height * SHAPE))
        if want <= frame.width:
            return frame
        wide = Image.new(frame.mode, (want, frame.height), 0)
        wide.paste(frame, ((want - frame.width) // 2, 0))
        return wide

    still = widen(film.convert("RGBA"))
    grey = np.asarray(widen(film.convert("L")))
    white = grey > WHITE

    out.mkdir(parents=True, exist_ok=True)
    keep = []
    for frame in ImageSequence.Iterator(film):
        # Four greys: enough for the antialiasing along every curve, and no more. Two picks a
        # mid grey for the dome and loses the drawing; eight doubles the file for nothing
        # anybody can see.
        keep.append(widen(frame.convert("L")).quantize(colors=GREYS,
                                                method=Image.Quantize.MEDIANCUT,
                                                dither=Image.Dither.NONE))
    keep[0].save(out / "mosque.gif", save_all=True, append_images=keep[1:], loop=0,
                 duration=film.info.get("duration", 150), optimize=True, disposal=1)
    still.save(out / "mosque.png")

    clock = dome_clock(white)
    name = name_panel(white, still.width)
    # The mask the app lights when the name is pressed: the panel's own rectangle, which for
    # lettering on a flat front is the shape of it.
    Image.new("L", (name[2] - name[0], name[3] - name[1]), 255).save(out / "arch-enter.png")

    described = {
        "schema": 1,
        "image": "mosque.png",
        "drawn": "dark",
        "sky": False,
        "size": [still.width, still.height],
        "arches": {"enter": {"box": list(name)}},
        # The dome is solid white in this drawing rather than an outline, so the numbers on it
        # have to be dark. The other two mosques are outlines and take the default.
        "clock": {"box": list(clock), "ink": "dark"},
        # No minarets. They are where the main screen glows to say no prayer is due, and the
        # front door has never done that; a first attempt at finding them here picked out the
        # sun on one side and a balcony slot on the other, and a wrong box is worse than none.
    }
    (out / "mosque.json").write_text(json.dumps(described, indent=2) + "\n", encoding="utf-8")

    print(f"{source.name}: {still.width}x{still.height}, {frames} frames")
    print(f"  clock on the dome  {clock}")
    print(f"  the name           {name}")
    print(f"  animation          {(out / 'mosque.gif').stat().st_size / 1e6:.2f} MB, "
          f"{frames} frames at {GREYS} greys")
    print(f"\n-> {out.relative_to(ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_front")
    ap.add_argument("drawing", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    build(args.drawing, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
