#!/usr/bin/env python3
"""Cuts Harry's coloured station marks out of his radio sheet, one file per station.

    python3 tools/radio/install_colour.py radio-colour.gif

Harry drew the radio page again in colour, over a render of the page as it stands. The page
itself is NOT a drawing -- salaah/radio.py builds it from assets/content/radio/stations.json,
sizes the grid to however many stations answer, and tools/check_stations.py takes out the ones
that do not. Shipping his sheet flat would freeze that: a station that stopped answering would
stay pictured and stay pressable, and adding one would need the sheet redrawn.

So the sheet is taken apart instead. Each square is cut out and kept as that station's coloured
mark, beside the stencil it stands for, and the page goes on being built as it always was.

WHERE THE SQUARES ARE is measured, not assumed: they are found in his sheet as the ten
light-edged squares, and checked against the same ten found in a render of the page the app
draws. All forty edges agreed exactly when this was written, which is what you would expect of
a sheet drawn over that render and is worth confirming rather than trusting.

WHAT A COLOURED MARK IS. The stencils are alpha only -- the colour thrown away, the ink painted
through the shape at the moment of drawing, black by day and white by night (see
assets/content/radio/logos/README.md). A coloured mark cannot work that way, because its colour
is the point. So it is stored as real colour with its own alpha, recovered from the black ground
it was drawn on: a pixel's brightness becomes its alpha and its colour is divided back out, so
the soft edge of every stroke survives and the mark composites correctly over the red of a
station that is playing as well as over black.

Needs Pillow, NumPy and SciPy:  pip3 install --break-system-packages pillow numpy scipy
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent.parent
LOGOS = ROOT / "assets" / "content" / "radio" / "logos"
STATIONS = ROOT / "assets" / "content" / "radio" / "stations.json"

#: Lighter than this is drawn rather than ground, when looking for the squares.
EDGE_LIT = 60

#: A square has to be at least this many pixels across, and near enough square, to be a station
#: rather than a letter or a piece of a mark.
SMALLEST = 200
SQUARISH = (0.8, 1.25)

#: Kept clear of each square's own white border before the mark is cut out of it.
INSIDE = 10

#: Below this, a pixel is the ground rather than part of the mark -- WHEN DECIDING WHERE TO
#: CROP. Several squares carry a faint halo spreading to their edges, and at a low figure that
#: halo is what gets cropped to: mishary came out as a full square, 32% away from the shape of
#: its own stencil, instead of 1.3%.
#:
#: Used for the crop ALONE. Inside it the real alpha is kept, soft edges and all, so a stroke
#: still fades out the way it was drawn. A threshold deciding where a picture ends is a
#: different question from one deciding what is in it, and conflating the two cost an hour.
GROUND = 48

#: How many points of overlap a mark must beat its nearest rival by -- see `goes_with`.
MARGIN = 0.10

#: How far an edge may sit from where the app puts it, in pixels of the rendered page, once the
#: sheet has been scaled to it. Both of Harry's sheets came in at 0.2px, which is rounding: he
#: draws over a render of the page, so the squares are the app's own. The bar is loose enough
#: to allow a sheet exported at an awkward scale and nowhere near loose enough to let a square
#: land on its neighbour, which is 372px away.
EDGES_WITHIN = 8.0


def squares_in(frame: np.ndarray) -> list[list[int]]:
    """The ten station squares, in reading order."""
    lit = frame > EDGE_LIT
    filled = ndimage.binary_fill_holes(lit)
    labels, _ = ndimage.label(filled)
    found = []
    for where in ndimage.find_objects(labels):
        wide = where[1].stop - where[1].start
        tall = where[0].stop - where[0].start
        if wide > SMALLEST and tall > SMALLEST and SQUARISH[0] < wide / tall < SQUARISH[1]:
            found.append([where[1].start, where[0].start, where[1].stop, where[0].stop])
    if not found:
        return []
    tall = min(b[3] - b[1] for b in found)
    found.sort(key=lambda b: b[1])
    rows, row = [], [found[0]]
    for box in found[1:]:
        if box[1] - row[0][1] < tall / 2:
            row.append(box)
        else:
            rows.append(sorted(row, key=lambda b: b[0]))
            row = [box]
    rows.append(sorted(row, key=lambda b: b[0]))
    return [b for line in rows for b in line]


def mark_from(patch: np.ndarray) -> Image.Image | None:
    """One square's coloured mark, lifted off the black it was drawn on.

    Brightness becomes alpha and the colour is divided back out of it, which is the inverse of
    drawing a coloured mark onto black. Laid back over black it is pixel for pixel what Harry
    drew; laid over the red of a playing station it composites as a mark should.
    """
    bright = patch.max(2)
    keep = bright > GROUND
    if not keep.any():
        return None
    rows, cols = np.nonzero(keep)
    top, bottom = int(rows.min()), int(rows.max()) + 1
    left, right = int(cols.min()), int(cols.max()) + 1
    cut = patch[top:bottom, left:right].astype(float)
    alpha = cut.max(2)
    with np.errstate(divide="ignore", invalid="ignore"):
        colour = np.where(alpha[:, :, None] > 0, cut * 255.0 / alpha[:, :, None], 0.0)
    out = np.dstack([np.clip(colour, 0, 255), np.clip(alpha, 0, 255)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


#: The grid both masks are squashed onto before they are compared.
GRID = 48


def squashed(mask: np.ndarray) -> np.ndarray:
    """A mask cropped to itself and squashed onto one small grid, so two drawings of the same
    mark can be compared whatever size either was drawn at."""
    rows, cols = np.nonzero(mask)
    cut = mask[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    small = Image.fromarray((cut * 255).astype(np.uint8)).resize((GRID, GRID), Image.BILINEAR)
    return np.asarray(small) > 110


def overlap(one: np.ndarray, other: np.ndarray) -> float:
    return float((one & other).sum()) / max(int((one | other).sum()), 1)


def goes_with(marks: dict, stencils: dict) -> None:
    """Every mark must look more like its own station's stencil than like any other.

    THE FAULT THIS IS FOR is a mark landing on the wrong station -- a square cut from the wrong
    place, or stations.json reordered without the sheet being redrawn. It would look perfectly
    fine on the glass, and the only person who would notice is a child who pressed Unity FM and
    got Ramadan FM.

    Asked as a comparison rather than against a threshold, because there is no threshold that
    works: the weakest true pairing (radio-seerah, whose mosque glyph Harry redrew) scores 0.61
    and the strongest false one (radio-sunna against unity-fm, two round marks) scores 0.64, so
    any fixed bar either passes a swap or fails a redraw. Every mark beating its own rival is a
    different claim, and the ten pass it by 0.245 at worst.
    """
    for key, mine in marks.items():
        scored = sorted(((overlap(mine, shape), other) for other, shape in stencils.items()),
                        reverse=True)
        (best, whose), (next_best, runner) = scored[0], scored[1]
        if whose != key:
            raise SystemExit(f"  {key}'s mark looks more like {whose}'s stencil ({best:.3f}) "
                             f"than like its own. A mark has landed on the wrong station. "
                             f"Nothing written.")
        if best - next_best < MARGIN:
            raise SystemExit(f"  {key}'s mark matches its own stencil {best:.3f} and "
                             f"{runner}'s {next_best:.3f}, too close to tell apart. "
                             f"Nothing written.")
    print(f"  all {len(marks)} marks match their own station better than any other")


def install(sheet: Path, against: Path | None) -> int:
    described = json.loads(STATIONS.read_text(encoding="utf-8"))
    keys = [s["key"] for s in described["stations"]]

    with Image.open(sheet) as film:
        frames = [f.convert("RGB") for f in ImageSequence.Iterator(film)]
    # THE MIDDLE value each pixel takes, not the brightest. His sheet animates -- a colour runs
    # across the marks -- and the brightest-ever version of a moving highlight is lit
    # everywhere it passes, so every mark came out as a full square and the first one measured
    # 13.8% away from its own stencil. The median is the picture with the sweep taken out of
    # it, which is the mark as drawn.
    #
    # A STILL SHEET IS ONE FRAME and the median of one frame is that frame, so this costs
    # nothing and the code below does not care which it was given. Harry's second sheet, on 20
    # November 2026, was a still PNG precisely because the animation was softening the marks:
    # the median takes the sweep out, but a sweep that has moved a stroke's edge between frames
    # leaves that edge half-lit in every frame, and the middle value of a half-lit edge is a
    # half-lit edge. Cutting the same ten marks out of the still sheet dropped the share of
    # soft-edged pixels from 65% to 45%, and nasheeds and ramadan-fm by better than 45 points
    # each.
    stack = np.array([np.asarray(f) for f in frames], np.uint8)
    brightest = np.median(stack, axis=0).astype(np.uint8)
    print(f"{sheet.name}: {brightest.shape[1]}x{brightest.shape[0]}, {len(frames)} frames")

    boxes = squares_in(brightest.max(2))
    print(f"  found {len(boxes)} squares; stations.json lists {len(keys)}")
    if len(boxes) != len(keys):
        raise SystemExit(f"  those do not match, so a mark would land on the wrong station. "
                         f"Nothing written.")

    if against is not None:
        with Image.open(against) as page:
            shot = np.asarray(page.convert("L"))
        theirs = squares_in(shot)
        if len(theirs) != len(boxes):
            raise SystemExit(f"  {len(theirs)} squares in {against.name} against {len(boxes)} in "
                             f"{sheet.name}. Nothing written.")
        # COMPARED AT WHATEVER SCALE THE SHEET WAS EXPORTED AT, not pixel for pixel. Harry's
        # first coloured page came back at the render's own 1920x1008 and this was an equality
        # check; the second came back at 1512x794, the same drawing exported smaller, and an
        # equality check would have refused it for being 21% too small -- which is not a fault,
        # and not something to ask him to redo. What the check is actually for is a sheet drawn
        # over something OTHER than this page: a different grid, a different number across, the
        # squares in different places. That survives rescaling, and an edge that has moved
        # relative to the page's own width still shows up here.
        wide = shot.shape[1] / brightest.shape[1]
        tall = shot.shape[0] / brightest.shape[0]
        if abs(wide - tall) > 0.01:
            raise SystemExit(f"  {sheet.name} is not the same shape as {against.name} "
                             f"({wide:.3f} across against {tall:.3f} down). Nothing written.")
        worst = max(max(abs(t - b * s) for t, b, s in zip(them, mine, (wide, tall, wide, tall)))
                    for them, mine in zip(theirs, boxes))
        if worst > EDGES_WITHIN:
            raise SystemExit(f"  the squares in {sheet.name} are not where the app puts them in "
                             f"{against.name} -- worst edge out by {worst:.1f}px of the page's "
                             f"own size. Nothing written.")
        print(f"  all {4 * len(boxes)} edges agree with the page the app draws "
              f"(worst {worst:.1f}px, sheet drawn at {1 / wide:.3f} of its size)")

    # Cut first and checked before anything is written, so a sheet that would put a mark on the
    # wrong station leaves the tree exactly as it was.
    cut, stencils = {}, {}
    for key, (x0, y0, x1, y1) in zip(keys, boxes):
        patch = brightest[y0 + INSIDE:y1 - INSIDE, x0 + INSIDE:x1 - INSIDE]
        mark = mark_from(patch)
        if mark is None:
            raise SystemExit(f"  nothing drawn in {key}'s square. Nothing written.")
        cut[key] = mark
        stencil = LOGOS / f"{key}.png"
        if stencil.is_file():
            with Image.open(stencil) as im:
                stencils[key] = squashed(np.asarray(im.convert("RGBA"))[:, :, 3] > 40)
    if len(stencils) == len(cut):
        goes_with({k: squashed(np.asarray(m)[:, :, 3] > GROUND) for k, m in cut.items()},
                  stencils)
    else:
        print(f"  {len(cut) - len(stencils)} station(s) have no stencil to check against")

    for key, mark in cut.items():
        out = LOGOS / f"{key}-colour.png"
        beside = out.with_suffix(out.suffix + ".new")
        try:
            mark.save(beside, format="PNG", optimize=True)
            with Image.open(beside) as check:
                check.load()
            beside.replace(out)
        finally:
            beside.unlink(missing_ok=True)
        print(f"  {out.name:26s} {mark.width:4d}x{mark.height:<4d} "
              f"{out.stat().st_size / 1e3:6.1f}KB")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", type=Path, help="Harry's coloured radio page")
    ap.add_argument("--against", type=Path, default=None,
                    help="a render of the page the app draws, to check the squares line up")
    args = ap.parse_args()
    sheet = args.sheet if args.sheet.is_absolute() else ROOT / args.sheet
    against = args.against
    if against is not None and not against.is_absolute():
        against = ROOT / against
    return install(sheet, against)


if __name__ == "__main__":
    raise SystemExit(main())
