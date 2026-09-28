#!/usr/bin/env python3
"""Turns a drawn mosque into a menu the app can use.

    python3 tools/build_arch_menu.py kalima-mosque.png assets/kalima --arches 6

The main screen's mosque is described by assets/mosque/mosque.json: the picture, a box for the
clock on the dome, and a box plus a mask for every arch. Nothing about that is specific to the
five prayers, so any drawing in the same style can become a menu -- which is how the six kalima
got a screen that looks like the front door.

What this works out for itself, by looking at the picture rather than being told:

  * the arches, as the light shapes cut into the dark building, sorted left to right
  * a mask for each, being that arch's own inside
  * a box for the clock, on the dome, checked to be dark all over so white numerals will read

It refuses rather than guesses: if it cannot find exactly the number of arches asked for, or the
clock would land somewhere light, it says so and writes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIGHT = 128            # brighter than this counts as the light inside of an arch
SMALLEST = 500         # pixels; below this it is a speck, not an arch

# An arch is an upright opening you could walk through. The other light shapes cut into a mosque
# -- the slots in a minaret, the line under the plinth -- are flat slivers, wider than they are
# tall and a fraction of the area. Judged by shape rather than by a threshold tuned until the
# right number came out, because the next drawing will not have the same numbers.
UPRIGHT = 0.7          # at least this tall for its width
ROOMY = 4000           # and at least this many pixels of opening

# The clock box, as fractions of the picture. Taken from the main mosque, where the box is
# about a fifth of the picture each way and sits a little above the middle, on the dome.
CLOCK_WIDE = 0.26
CLOCK_TALL = 0.19
CLOCK_MIDDLE = 0.55   # of the height: the dome's body, above where the roof comes in
DARK_ENOUGH = 0.97    # of the clock box must be dark, or the time will not read on it


def arches_in(grey, least: int, upright: float = UPRIGHT) -> list[tuple[int, int, int, int]]:
    """Every light shape big enough to be an arch, as boxes, ordered left to right."""
    import numpy as np
    from scipy import ndimage
    light = np.array(grey) > LIGHT
    labelled, count = ndimage.label(light)
    found = []
    for mark in range(1, count + 1):
        ys, xs = np.where(labelled == mark)
        if len(ys) < least:
            continue
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        # The sky is light too, and so is the ground: an arch is a shape well inside the
        # picture, not one that reaches its edges.
        if box[0] == 0 or box[1] == 0 or box[2] >= light.shape[1] or box[3] >= light.shape[0]:
            continue
        wide, tall = box[2] - box[0], box[3] - box[1]
        if tall < wide * upright or len(ys) < ROOMY:
            continue
        found.append(box)
    # A panel drawn with a double outline shows up twice -- the white border and the white
    # fill inside it, with the thin dark gap between them keeping them apart. One opening, not
    # two, so anything sitting wholly inside another shape is dropped. Arches standing side by
    # side never contain one another, so this leaves a row of them alone.
    whole = [box for box in found
             if not any(other is not box and other[0] <= box[0] and other[1] <= box[1]
                        and other[2] >= box[2] and other[3] >= box[3] for other in found)]
    whole.sort(key=lambda b: b[0])
    return whole


def landmarks(picture, drawn_dark: bool = False):
    """Where the two minaret tips and the top of the dome are, in this drawing.

    These are what the eye notices when one screen replaces another: if the minarets and the
    dome sit where they did, the change reads as the same building seen again rather than a
    different picture. Measured from the ink rather than guessed, and only from parts that are
    solid, so a see-through sky is not mistaken for the drawing.
    """
    import numpy as np
    cells = np.array(picture)
    solid = cells[..., 3] > 128
    shades = np.array(picture.convert("L"))
    ink = ((shades > LIGHT) if drawn_dark else (shades < LIGHT)) & solid
    height, width = ink.shape
    found = {}
    for side, low, high in (("left", 0, width // 4), ("right", 3 * width // 4, width)):
        ys, xs = np.where(ink[:, low:high])
        if not len(ys):
            return None
        top = ys.min()
        found[side] = (float(np.mean(xs[ys < top + 12])) + low, float(top))
    ys, xs = np.where(ink[:, width // 4:3 * width // 4])
    if not len(ys):
        return None
    top = ys.min()
    found["dome"] = (float(np.mean(xs[ys < top + 12])) + width // 4, float(top))
    return found


def match_to(picture, reference: Path, drawn_dark: bool = False):
    """Redraw this mosque on the reference's canvas, with its minarets over the reference's.

    One number does it: how far apart the two minarets are. Scale by the ratio of the two
    separations and slide the drawing until the left tip lands on the reference's left tip, and
    the right tip and the dome follow of their own accord -- which is the check afterwards, not
    an assumption.
    """
    from PIL import Image
    other = Image.open(reference).convert("RGBA")
    mine, theirs = landmarks(picture, drawn_dark), landmarks(other, drawn_dark)
    if not mine or not theirs:
        return picture, "could not find the minarets in one of the drawings"
    span_mine = mine["right"][0] - mine["left"][0]
    span_theirs = theirs["right"][0] - theirs["left"][0]
    if span_mine <= 1:
        return picture, "the minarets are on top of each other"
    scale = span_theirs / span_mine
    wide, tall = int(round(picture.width * scale)), int(round(picture.height * scale))
    bigger = picture.resize((wide, tall), Image.LANCZOS)
    shift_x = int(round(theirs["left"][0] - mine["left"][0] * scale))
    shift_y = int(round(theirs["left"][1] - mine["left"][1] * scale))
    canvas = Image.new("RGBA", other.size, (255, 255, 255, 0))
    canvas.alpha_composite(bigger, dest=(max(0, shift_x), max(0, shift_y)),
                           source=(max(0, -shift_x), max(0, -shift_y)))
    check = landmarks(canvas, drawn_dark)
    if not check:
        return canvas, "redrawn, but the minarets could not be found again to check"
    drift = max(abs(check[k][i] - theirs[k][i]) for k in theirs for i in (0, 1))
    return canvas, (f"scaled {scale:.3f}, moved ({shift_x}, {shift_y}); "
                    f"minarets and dome now within {drift:.0f}px of the reference")


def knock_out_sky(picture, grey, drawn_dark: bool = False):
    """Make the background see-through, leaving the building and the arch insides solid.

    The sun, moon, stars and birds are drawn BEHIND the mosque, so a drawing with an opaque
    background paints over them and the sky sits empty -- which is exactly what happened the
    first time this ran. Everything the same shade as the background that can be reached from
    the edge of the picture becomes transparent, and anything walled in by the building -- an
    arch's inside, the dome the clock sits on, a slot in a minaret -- stays as it was drawn.

    Which shade the background is depends on which way round the drawing was made. The first
    mosque was dark ink on a light ground; the ones that came after are white lines on black,
    where knocking out the light would have taken the arch panels and left the sky.
    """
    import numpy as np
    from scipy import ndimage
    ground = np.array(grey) < LIGHT if drawn_dark else np.array(grey) > LIGHT
    labelled, count = ndimage.label(ground)
    outside = set(labelled[0, :]) | set(labelled[-1, :]) | set(labelled[:, 0]) | set(labelled[:, -1])
    outside.discard(0)
    if not outside:
        return picture, 0.0
    sky = np.isin(labelled, list(outside))
    cells = np.array(picture)
    cells[..., 3] = np.where(sky, 0, cells[..., 3])
    from PIL import Image
    return Image.fromarray(cells, "RGBA"), float(sky.mean())


# The minaret tips glow on the main screen when no prayer is due. Written from the drawing
# rather than left empty: an empty list is not an error anywhere, so the glow would simply stop
# happening and nothing would say why.
MINARET_WIDE = 0.055     # of the picture, either side of the tip
MINARET_TALL = 0.135     # and down from it


def minaret_boxes(picture, drawn_dark: bool) -> dict:
    found = landmarks(picture, drawn_dark)
    if not found:
        return {}
    wide = int(picture.width * MINARET_WIDE)
    tall = int(picture.height * MINARET_TALL)
    boxes = {}
    for side in ("left", "right"):
        x, y = found[side]
        boxes[side] = [max(0, int(x - wide / 2)), max(0, int(y)),
                       min(picture.width, int(x + wide / 2)), min(picture.height, int(y + tall))]
    return boxes


def clock_box(grey, wanted: int) -> tuple[int, int, int, int] | None:
    """A box on the dome, dark all over. None if nowhere suitable was found."""
    import numpy as np
    dark = np.array(grey) < LIGHT
    height, width = dark.shape
    wide, tall = int(width * CLOCK_WIDE), int(height * CLOCK_TALL)
    # Centred on the arches rather than on the picture: a drawing need not be symmetrical.
    middle = wanted
    for centre_y in range(int(height * CLOCK_MIDDLE), int(height * 0.25), -4):
        x0, y0 = middle - wide // 2, centre_y - tall // 2
        patch = dark[y0:y0 + tall, x0:x0 + wide]
        if patch.size and patch.mean() >= DARK_ENOUGH:
            return (x0, y0, x0 + wide, y0 + tall)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_arch_menu")
    ap.add_argument("picture", type=Path)
    ap.add_argument("out", type=Path, help="the folder to write, e.g. assets/kalima")
    ap.add_argument("--arches", type=int, default=6)
    ap.add_argument("--names", default="", help="comma separated; defaults to 1,2,3...")
    ap.add_argument("--upright", type=float, default=UPRIGHT,
                    help="how tall an opening must be for its width to count as an arch. The "
                         "default rejects the flat slivers a mosque is full of -- the slots in "
                         "a minaret, the line under the plinth. A drawing whose opening is one "
                         "wide panel rather than a row of arches needs this lowered.")
    ap.add_argument("--drawn", choices=("light", "dark"), default="light",
                    help="which screen the drawing was made for: 'dark' for white lines on "
                         "black, which the app then shows as drawn rather than inverting")
    ap.add_argument("--match", type=Path, default=None,
                    help="another mosque.png to line this one up with, so the two screens "
                         "show the same building in the same place")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("This needs Pillow: pip install pillow", file=sys.stderr)
        return 1
    if not args.picture.is_file():
        print(f"No picture at {args.picture}.", file=sys.stderr)
        return 1

    picture = Image.open(args.picture).convert("RGBA")
    if args.match:
        if not args.match.is_file():
            print(f"No reference drawing at {args.match}.", file=sys.stderr)
            return 1
        picture, said = match_to(picture, args.match, args.drawn == "dark")
        print(f"lined up with {args.match}: {said}")
    grey = picture.convert("L")
    boxes = arches_in(grey, SMALLEST, args.upright)
    if len(boxes) != args.arches:
        print(f"Found {len(boxes)} arch-sized shapes, not {args.arches}.", file=sys.stderr)
        for box in boxes:
            print(f"    {box}", file=sys.stderr)
        print("Nothing written.", file=sys.stderr)
        return 1

    names = ([n.strip() for n in args.names.split(",")] if args.names
             else [str(i + 1) for i in range(len(boxes))])
    if len(names) != len(boxes):
        print(f"{len(names)} names for {len(boxes)} arches.", file=sys.stderr)
        return 1

    middle = (boxes[0][0] + boxes[-1][2]) // 2
    clock = clock_box(grey, middle)
    if clock is None:
        print("Could not find a dark enough box on the dome for the clock. Nothing written.",
              file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    picture, see_through = knock_out_sky(picture, grey, args.drawn == "dark")
    picture.save(args.out / "mosque.png")
    for name, box in zip(names, boxes):
        # The mask is this arch's own light inside, at the box's size, which is what the glow
        # is drawn through.
        inside = grey.crop(box).point(lambda v: 255 if v > LIGHT else 0).convert("L")
        inside.save(args.out / f"arch-{name}.png")

    described = {
        "schema": 1,
        "image": "mosque.png",
        "drawn": args.drawn,
        "size": [picture.width, picture.height],
        "arches": {name: {"box": list(box)} for name, box in zip(names, boxes)},
        "clock": {"box": list(clock)},
        "minarets": minaret_boxes(picture, args.drawn == "dark"),
    }
    (args.out / "mosque.json").write_text(json.dumps(described, indent=2) + "\n",
                                          encoding="utf-8")
    print(f"{len(boxes)} arches -> {args.out}")
    print(f"  sky knocked out: {see_through * 100:.1f}% of the picture is now see-through, "
          f"so the stars and birds behind it show")
    for name, box in zip(names, boxes):
        print(f"    {name}: {box}")
    print(f"  clock: {clock}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
