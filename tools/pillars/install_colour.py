#!/usr/bin/env python3
"""Put Harry's coloured pillar-game objects in beside the line drawings, as twins.

THE SAME JOB AS tools/postures/install_colour.py, and for the same reason. The app does not
find the object inside its canvas and centre it -- pillar_match.ItemArt.draw scales the WHOLE
canvas into a square on screen. So where the drawing sits inside its canvas is where it lands
in front of the child, and a coloured twin framed differently from its line drawing makes the
object jump and resize at the moment the theme changes.

Harry's set of 21 November 2026 is drawn to a brief and comes in close: sixteen of the
seventeen are inside 2% and the Kaaba at 3.5%. This normalises all of them to nothing, by
dropping each drawing into exactly the fractional rectangle its line drawing occupies.

WHAT THE FIRST ATTEMPT GOT WRONG, recorded because the next set will be tempting to accept:
it arrived painted on solid black with the English name lettered underneath. Neither survives
contact with this app. The name is drawn by the app itself, in ten languages, underneath the
picture -- a painted-in English caption shows English words to a child reading Urdu, and the
name twice to a child reading English. And a solid ground cannot be keyed out afterwards:
the prayer beads form a closed loop, so the background trapped inside the loop is unreachable
from the edge and stays as a black blob in the middle of the beads, while the Kaaba is a
genuinely black object that any rule removing black removes.

Usage:  python3 tools/pillars/install_colour.py <folder-of-his-pngs>
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

#: His filename -> the line drawing it is a twin of. Taken from the brief he was given, and
#: checked by eye against both sets rather than trusted: see CHECKED below.
WHICH = {
    "01-one-god": "one_god",
    "02-declaration-page": "declaration",
    "03-prayer-rug": "prayer_rug",
    "04-prayer-beads": "prayer_beads",
    "05-quran": "quran",
    "06-zakat-2-5-percent": "zakat_share",
    "07-cash-notes-coins": "cash_and_coins",
    "08-ramadan-29-30-days": "ramadan_days",
    "09-water-moon-stars": "water_at_sunset",
    "10-hajj-5-days": "hajj_days",
    "11-kaaba": "kaaba",
    "12-ihram-clothing": "ihram",
    "13-suitcase": "suitcase",
    "14-mosque-silhouette": "mosque",
    "15-minaret-sound-waves": "call_to_prayer",
    "16-child-praying": "child_praying",
    "17-mosque-day-night": "prayer_times",
}

#: How far a twin's shape may differ from the line drawing's, as a fraction, once both are
#: cropped to their drawing. Past this it is not the same picture and the pairing in WHICH is
#: likelier to be wrong than the artwork. Not a bound on the squash the way the postures tool's
#: is -- these are normalised to zero either way -- but a bound on how much squashing is being
#: asked for without anyone looking.
SHAPE = 0.06

#: Below this the object is not opaque enough to be an object. A twin delivered on a solid
#: ground scores near zero here, which is the cheapest way to catch that mistake coming back.
CLEAR = 0.15


def drawing_box(path: pathlib.Path) -> tuple[int, int, int, int, int, int]:
    """Where the drawing is inside its canvas, by its alpha, plus the canvas size."""
    im = Image.open(path)
    if im.mode not in ("RGBA", "LA"):
        raise SystemExit(f"{path.name}: {im.mode}, with no alpha to read. It must be RGBA.")
    alpha = im.getchannel("A")
    box = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if box is None:
        raise SystemExit(f"{path.name}: nothing but transparency.")
    return (*box, im.width, im.height)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=pathlib.Path, help="where his PNGs are")
    ap.add_argument("--root", type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[2])
    args = ap.parse_args()
    here = args.root / "assets" / "children" / "pillars"
    written = 0
    print(f"  from {args.folder}")
    for his, name in sorted(WHICH.items(), key=lambda kv: kv[1]):
        source = args.folder / f"{his}.png"
        plain = here / f"{name}.png"
        if not source.is_file():
            raise SystemExit(f"missing: {source}")
        if not plain.is_file():
            raise SystemExit(f"no line drawing to match: {plain}")

        ox0, oy0, ox1, oy1, width, height = drawing_box(plain)
        hx0, hy0, hx1, hy1, hw, hh = drawing_box(source)
        if hw != hh:
            raise SystemExit(f"{his}: canvas {hw}x{hh}, which is not square.")

        picture = Image.open(source).convert("RGBA")
        clear = sum(1 for a in picture.getchannel("A").getdata() if a == 0) / (hw * hh)
        if clear < CLEAR:
            raise SystemExit(f"{his}: only {100 * clear:.1f}% of the canvas is clear. "
                             f"This looks like artwork on a solid ground.")

        # Both as fractions of their own canvas, so a 1024 twin and a 512 original compare.
        o = ((ox1 - ox0) / width) / ((oy1 - oy0) / height)
        h = ((hx1 - hx0) / hw) / ((hy1 - hy0) / hh)
        apart = abs(h - o) / o
        if apart > SHAPE:
            raise SystemExit(f"{his}: shape {100 * apart:.1f}% from {name}, past {100 * SHAPE:.0f}%. "
                             f"Either the drawing is wrong or this is the wrong pairing.")

        # Into exactly the fraction of the canvas the line drawing's own drawing fills. The
        # twin keeps ITS canvas size -- these are 1024 against the originals' 512, and there is
        # no reason to throw that away -- so the rectangle is scaled into the twin's canvas.
        box = (round(ox0 / width * hw), round(oy0 / height * hh),
               round(ox1 / width * hw), round(oy1 / height * hh))
        cut = picture.crop((hx0, hy0, hx1, hy1))
        page = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))
        page.paste(cut.resize((max(1, box[2] - box[0]), max(1, box[3] - box[1])), Image.LANCZOS),
                   (box[0], box[1]))
        out = here / f"{name}-colour.png"
        page.save(out, optimize=True)
        written += 1
        print(f"  {name:18s} <- {his:24s} {hw}x{hh} {out.stat().st_size / 1e3:7.1f}KB  "
              f"squashed {100 * apart:4.2f}%, clear {100 * clear:4.1f}%")
    print(f"\n  {written} twins written beside their line drawings.")
    print("  The suites are not covered by any of this. Run them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
