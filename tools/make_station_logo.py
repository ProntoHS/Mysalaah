#!/usr/bin/env python3
"""Turns a station's logo into a stencil the mat can draw in either theme.

    python3 tools/make_station_logo.py <source.png> assets/content/radio/logos/<key>.png

WHY A STENCIL AND NOT THE PICTURE. Every logo Harry sent is line art in one colour: white
drawing on a black field, or -- radio Sunnah -- a black disc with the lettering knocked out of
it. Dropped onto the mat as they are, five of the six would be a black square sitting on white
paper by day, and the sixth a white square on black at night. The mat does not have a single
picture anywhere that behaves like that: everything it draws, from the menu sheets to the
chevrons, is one colour of ink on whatever the background happens to be, and flips when the
screen does.

So the colour is thrown away here and only the COVERAGE is kept: the alpha channel says where
the drawing is, and the mat paints its own ink through it at the moment it paints. Black on
white by day, white on black at night, and white over the red of the station that is playing,
all from one file and with no second copy of it to keep in step.

WHICH SIDE IS THE DRAWING is the one judgement in this, and it is made from the border: a logo
framed in black is white-on-black and the light pixels are the drawing; one framed in white is
the other way round and the dark pixels are. Said out loud when it runs, because it is a guess
about somebody's artwork and a wrong one is obvious in a glance at the result. --invert and
--no-invert override it.

The file is then trimmed to what is actually drawn and scaled down. Trimmed because the sources
are padded by wildly different amounts -- one logo sits in a 1254x1504 field with the name
along the bottom -- and untrimmed they would be drawn at six different sizes on six identical
squares. Scaled because a square is at most 400 points on a 1080p mat and a 1200px logo is
three times more picture than can ever be shown.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Where the drawing starts and where it is solid. The sources are strongly two-sided -- better
# than four fifths of every one of them is within a few shades of one end or the other -- but
# not cleanly so: one arrives on a #0D0D0D field rather than black, and all six are drawn with
# antialiased edges that have to stay soft or the result looks cut out with scissors.
FLOOR = 24
CEIL = 230
# A pixel has to be this far up to count as drawing when the edges are trimmed. Low, because
# the faint end of an antialiased stroke is still the stroke.
SHOWS = 8
SIDE = 512


def border_is_light(grey) -> bool:
    """Is the frame round this picture the light side or the dark one?

    The outermost ring of pixels, which on all six of these is field and nothing else. A
    corner alone would be enough for a square logo and is not for one with a name set across
    the bottom, so it is the whole ring, and the middle of it: an average is pulled about by
    a drawing that touches the edge, where the median is not.
    """
    w, h = grey.size
    px = grey.load()
    ring = ([px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)]
            + [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)])
    ring.sort()
    return ring[len(ring) // 2] > 127


def without_the_corners(alpha):
    """Rub out anything drawn that runs into a corner of the picture.

    Buzz Islam's mark is a black rounded square with a white crescent on it, saved on a white
    page, so the four slivers the rounded corners leave are the same white as the crescent and
    come through as drawing: a stencil with solid blocks in its corners, which on the mat is
    four bright wedges round a logo. They are not artwork, they are the page it was drawn on.

    Spreading out from each corner and stopping where the drawing stops is what tells the two
    apart -- the slivers touch the edge of the picture and the crescent does not. A mark that
    genuinely ran into a corner would lose that part of itself, which is why the area taken
    off is printed: on these six it is a fraction of a percent or nothing at all.
    """
    from PIL import Image, ImageDraw
    w, h = alpha.size
    before = sum(alpha.histogram()[SHOWS:])
    reached = 0
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if alpha.getpixel(corner) >= SHOWS:
            reached += 1
            ImageDraw.floodfill(alpha, corner, 0, thresh=255 - SHOWS)
    gone = before - sum(alpha.histogram()[SHOWS:])
    if reached:
        print(f"  the page it was drawn on reached {reached} corner"
              f"{'' if reached == 1 else 's'}: {gone} pixels rubbed out, "
              f"{gone / (w * h):.2%} of the picture")
    return alpha


def stencil(source: Path, out: Path, invert=None, side: int = SIDE, corners=True) -> int:
    from PIL import Image

    whole = Image.open(source)
    grey = whole.convert("L")
    if invert is None:
        invert = border_is_light(grey)
        print(f"  {source.name}: framed in {'white' if invert else 'black'}, so the "
              f"{'dark' if invert else 'light'} pixels are the drawing")
    if invert:
        grey = Image.eval(grey, lambda v: 255 - v)

    # Coverage: nothing below the floor, solid above the ceiling, and the soft edge in
    # between kept as a slope rather than rounded to one side or the other.
    span = CEIL - FLOOR
    alpha = Image.eval(grey, lambda v: 0 if v <= FLOOR else
                       (255 if v >= CEIL else (v - FLOOR) * 255 // span))

    if corners:
        alpha = without_the_corners(alpha)

    box = alpha.point(lambda v: 255 if v >= SHOWS else 0).getbbox()
    if box is None:
        raise SystemExit(f"{source.name} is blank once the field is taken off it")
    alpha = alpha.crop(box)
    print(f"  trimmed {whole.size[0]}x{whole.size[1]} -> {alpha.size[0]}x{alpha.size[1]}")

    if max(alpha.size) > side:
        scale = side / max(alpha.size)
        alpha = alpha.resize((max(1, round(alpha.size[0] * scale)),
                              max(1, round(alpha.size[1] * scale))),
                             Image.Resampling.LANCZOS)

    # White underneath, so a mat that draws the file without tinting it -- or anything else
    # that opens it -- gets the artwork the right way up rather than a black-on-black riddle.
    out.parent.mkdir(parents=True, exist_ok=True)
    made = Image.new("RGBA", alpha.size, (255, 255, 255, 0))
    made.putalpha(alpha)
    made.save(out, optimize=True)
    print(f"  {out.name}: {alpha.size[0]}x{alpha.size[1]}, {out.stat().st_size / 1e3:.0f}kB")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--side", type=int, default=SIDE, help=f"longest side, default {SIDE}")
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--invert", dest="invert", action="store_true", default=None,
                       help="the DARK pixels are the drawing")
    which.add_argument("--no-invert", dest="invert", action="store_false",
                       help="the LIGHT pixels are the drawing")
    ap.add_argument("--keep-corners", dest="corners", action="store_false", default=True,
                    help="this mark really does run into the corners of its picture")
    args = ap.parse_args()
    return stencil(args.source if args.source.is_absolute() else ROOT / args.source,
                   args.out if args.out.is_absolute() else ROOT / args.out,
                   args.invert, args.side, args.corners)


if __name__ == "__main__":
    raise SystemExit(main())
