#!/usr/bin/env python3
"""Turns Harry's 2.41 mosque drawings into the Salaah menu and the five prayer pages.

    python3 tools/build_mosque_pack.py <five-prayer-folder> <archway-folder>

    <five-prayer-folder>   five_prayer_mosque_<lang>.png, one per language
    <archway-folder>       mosque_<n>_archways_1920x1080.png for n in 2, 3, 4, 6

Writes assets/mosque (the Salaah menu: five arches, a name drawn in each, the time on the dome)
and assets/prayers/<prayer> (one page per prayer, an empty arch per unit, the prayer's name on
the dome and "2 Sunnah" written into the arches by the app).

EVERYTHING HERE IS MEASURED OFF THE DRAWING. The canvas has gone from 1396x733 to 1920x1080 and
nothing about the old boxes transfers, so a number carried over would put the touch targets, the
clock and the green name somewhere they are not. The two ratios that ARE carried over -- how
wide the clock box is for its dome, and how deep -- are stated as ratios of the dome, measured
off the old drawing, so they mean the same thing on a dome of a different size.

THE SKY. The app paints the sun, the moon, the stars and the birds and then draws the picture
over them, so the sky has to be see-through or it buries the lot. These drawings are solid
black. Worse, the usual cut -- every black pixel joined to the edge is sky -- takes the whole
picture with it here: the brickwork is black mortar lines right through the columns, so an
arch's inside is joined to the one beside it and out to the sky through a gap three pixels wide.
Measured: every black pixel in all fourteen drawings is ONE connected piece.

So the building is found as a shape instead. Close the white up by more than a mortar line is
wide and the bricks become one mass; fill that mass's holes and the arches, two hundred pixels
across, are the holes. What is left outside is the sky, and only the sky. Checked at closing
radii from 2 to 10 pixels: the silhouette moves by half a percent, so this is not a number
tuned until the right answer came out.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
LANGS = ("en", "fr", "es", "ur", "hi", "zh", "ar", "bn", "ru", "pt")

CLOSE = 4            # pixels: more than a mortar line is wide, far less than an arch
OPEN = 4             # and the same again to break the arches apart from one another
SMALLEST = 8000      # pixels; below this an opening is a slot or a vent, not an arch
WHITE = 128          # these drawings are strictly black and white, so anything parts them

# The clock box: the rectangle the lettering FILLS, as ratios of the dome it sits on. Stated
# against the dome rather than the picture because the canvas carries a lot of sky and the
# dome is what the time is written on.
#
# 0.46 of the dome until 2.42, when Harry asked for the time "at least twice as big and
# slightly higher". Twice is 0.92 and the dome will not take it. The limit is not the time --
# "17:46" fits at 0.92 with nothing over the edge -- it is the longest of the names written in
# the same place: the Arabic المغرب reaches further up the dome, where it has begun to curve
# in, and puts half a percent of itself into the sky at 0.87.
#
# 0.84 is the most that leaves EVERY word the mat can write up there -- the time, and the five
# prayers in all ten languages -- wholly on the dome, with nothing over the edge at all. That
# is eighty-three percent bigger rather than a hundred, and the seventeen points it gives up
# are not worth a prayer's name hanging off the dome in one language. Found by measuring, and
# held by test_ui's LetteringOnTheDomeTest, which measures the same thing on every build.
CLOCK_OF_DOME = 0.84
CLOCK_SHAPE = 3.27   # the shape of a five-figure time, so the time fills the box both ways.
                     # A Pi with a different face only makes the time a little smaller than
                     # the box; it cannot make it overflow, because the fit measures the ink.
CLOCK_CLEAR = 0.01   # of the dome's width, kept between the lettering and the band below it

PLAIN = 0.70         # a dome row is plain tiling above this much white; the patterned band
                     # under the dome is 0.36 to 0.61 and this is the gap between the two

# Where the app writes "2" and "Sunnah" into an empty arch, as fractions of the arch's height.
# The opening is straight-sided from about 0.55 down, so both lines sit below that.
NUMBER_BAND = (0.30, 0.56)
LABEL_BAND = (0.63, 0.86)

# The six-kalima menu writes ONE line, a plain digit, so its number band is given no height and
# the digit gets a deep band of its own -- the same arrangement the 1.64 drawing had. Where
# that band SITS is not chosen here: it is where Harry put his own lettering on the five-prayer
# mosque, measured off those ten drawings, so a digit on one menu sits at the height a name
# sits at on the other.

NAME_CLEAR = 0.03    # of the arch's width, kept clear either side of the green tint


def disk(radius: int) -> np.ndarray:
    span = np.arange(-radius, radius + 1)
    y, x = np.meshgrid(span, span, indexing="ij")
    return (x * x + y * y) <= radius * radius


class Drawing:
    """One of the fourteen, with everything that can be measured off it."""

    def __init__(self, path: Path):
        self.path = path
        picture = Image.open(path)
        if picture.size != (1920, 1080):
            raise SystemExit(f"{path.name}: {picture.size[0]}x{picture.size[1]}, wanted 1920x1080")
        self.picture = picture.convert("RGB")
        self.grey = np.array(self.picture.convert("L"))
        self.white = self.grey > WHITE
        closed = ndimage.binary_closing(self.white, structure=disk(CLOSE))
        self.solid = ndimage.binary_fill_holes(closed)
        self.openings = ndimage.binary_opening(self.solid & ~self.white, structure=disk(OPEN))

    # The arches

    def arches(self, want: int) -> list[tuple[int, int, int, int]]:
        """The openings big enough to walk through, left to right. Refuses to guess: if the
        drawing does not hold exactly the number asked for, nothing is written."""
        labels, count = ndimage.label(self.openings)
        sizes = ndimage.sum(self.openings, labels, range(1, count + 1))
        boxes = []
        for i in range(count):
            if sizes[i] <= SMALLEST:
                continue
            ys, xs = np.where(labels == i + 1)
            boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
        boxes.sort()
        if len(boxes) != want:
            raise SystemExit(f"{self.path.name}: found {len(boxes)} arches, wanted {want}")
        return boxes

    # The dome

    def tower(self) -> dict[int, tuple[int, int]]:
        """Each row of the thing in the middle -- finial, dome, drum -- with the run of building
        that holds the middle column. Stops where that run opens out into the roof."""
        height, width = self.solid.shape
        mid = width // 2
        rows: dict[int, tuple[int, int]] = {}
        for y in range(height):
            if not self.solid[y, mid]:
                continue
            left = right = mid
            while left > 0 and self.solid[y, left - 1]:
                left -= 1
            while right < width - 1 and self.solid[y, right + 1]:
                right += 1
            if right - left > width * 0.45:
                break
            rows[y] = (left, right + 1)
        if not rows:
            raise SystemExit(f"{self.path.name}: no dome found")
        return rows

    def dome_body(self, rows: dict[int, tuple[int, int]]) -> tuple[int, int, int, int]:
        """The plain tiled part of the dome: its foot, its widest row, how wide, and its centre.

        THE FOOT IS FOUND FIRST, and that is the whole of the 2.42 fix. It used to look for the
        band BELOW THE WIDEST ROW of the tower -- and the widest row of the tower is not on the
        dome at all. The patterned band flares out past it, so the widest row was the band's
        own base, the search for the band started below the band, found nothing, and the dome's
        foot came out as the bottom of the tower: 696 where the dome ends at 648. The time was
        then hung from a line forty-eight pixels inside the pattern.

        It is found by SHAPE instead, which needs nothing to be assumed about how dark a
        pattern is or how white a tile: an onion dome gets WIDER down to its belly and then
        NARROWER to its foot, and the band under it flares out again. So the foot is the waist
        -- the narrowest row between the dome's belly and the widest row of the whole tower --
        and the dome's widest row is whatever is widest above that.

        A first attempt read the tiling's darkness and started looking a fixed way down the
        tower; it tripped on the first dark course it met near the shoulder, and put the foot
        at 281 where the dome ends at 636. A shape has no such threshold in it.

        Nothing is assumed about there being a band either: on a dome that runs straight into
        the roof the width never turns back up, there is no waist, and the foot is the bottom
        of the tower, as it was.
        """
        order = sorted(rows)
        wide = {y: rows[y][1] - rows[y][0] for y in order}
        # smoothed, because a course of tiles can take a pixel off a row's width and a waist
        # found on raw widths would be whichever row that happened to be
        smooth = {}
        for i, y in enumerate(order):
            near = order[max(0, i - 4):i + 5]
            smooth[y] = sum(wide[z] for z in near) / len(near)
        # The waist is the LOWEST row that is narrower than everything within reach of it. Reach
        # matters: the band's own edge wobbles by twenty pixels from row to row, so a waist
        # found by looking one row each way is whichever row of the band happened to dip.
        reach = max(4, int((order[-1] - order[0]) * 0.05))
        fat = max(smooth.values())
        foot = order[-1]
        for i, y in enumerate(order):
            if smooth[y] < fat * 0.5:          # the finial and the stem narrow too, up top
                continue
            near = [smooth[z] for z in order[max(0, i - reach):i + reach + 1]]
            if smooth[y] <= min(near):
                foot = y
        body = [y for y in order if y <= foot]
        widest = max(body, key=lambda y: wide[y])
        middle = (rows[widest][0] + rows[widest][1]) // 2
        return foot, widest, wide[widest], middle

    def clock(self) -> tuple[int, int, int, int]:
        """Where the time is written: on the dome, the size the 1.84 dome wore it, with its
        foot clear of the band underneath."""
        rows = self.tower()
        foot, _, span, middle = self.dome_body(rows)
        width = int(span * CLOCK_OF_DOME)
        height = int(width / CLOCK_SHAPE)
        bottom = foot - int(span * CLOCK_CLEAR)
        box = (middle - width // 2, bottom - height, middle - width // 2 + width, bottom)
        inside = self.white[box[1]:box[3], box[0]:box[2]]
        if inside.mean() < PLAIN:
            raise SystemExit(f"{self.path.name}: the clock box is only {inside.mean():.0%} "
                             f"plain dome; the time would be written over the pattern")
        return box

    # The minarets, whose tops glow when no prayer is due

    def minarets(self) -> dict[str, list[int]]:
        above = self.solid.copy()
        above[int(above.shape[0] * 0.45):, :] = False
        labels, count = ndimage.label(above)
        sizes = ndimage.sum(above, labels, range(1, count + 1))
        found: dict[str, list[int]] = {}
        for i in np.argsort(sizes)[::-1][:8]:
            ys, xs = np.where(labels == i + 1)
            side = "left" if xs.mean() / above.shape[1] < 0.25 else (
                "right" if xs.mean() / above.shape[1] > 0.75 else None)
            if side is None or side in found:
                continue
            bulb = int(ys.min() + (ys.max() - ys.min()) * 0.38)   # just the lantern on top
            keep = ys <= bulb
            found[side] = [int(xs[keep].min()), int(ys.min()), int(xs[keep].max()) + 1, bulb]
        if len(found) != 2:
            raise SystemExit(f"{self.path.name}: found {len(found)} minarets, wanted 2")
        return found

    # The drawn names, and the band the app may tint green

    def lettering(self, boxes) -> tuple[float, float, float, float]:
        """Where the words Harry drew sit inside their arches, as fractions of the arch.

        Only ink well inside the opening counts: the arch's own white stone runs along the top
        corners of the box, and taking that for lettering would say the words fill the arch.
        """
        low, high, left, right = 1.0, 0.0, 1.0, 0.0
        for x0, y0, x1, y1 in boxes:
            opening = ndimage.binary_fill_holes(self.openings[y0:y1, x0:x1])
            inner = ndimage.binary_erosion(opening, structure=disk(10))
            ys, xs = np.where(self.white[y0:y1, x0:x1] & inner)
            if not len(ys):
                raise SystemExit(f"{self.path.name}: nothing written in the arch at x{x0}")
            low = min(low, ys.min() / (y1 - y0))
            high = max(high, (ys.max() + 1) / (y1 - y0))
            left = min(left, xs.min() / (x1 - x0))
            right = max(right, (xs.max() + 1) / (x1 - x0))
        return low, high, left, right

    # The sky

    def with_a_see_through_sky(self) -> Image.Image:
        out = self.picture.convert("RGBA")
        alpha = np.array(out.getchannel("A"))
        alpha[~self.solid] = 0
        out.putalpha(Image.fromarray(alpha))
        return out


def tint_band(boxes, low: float, high: float, drawing: Drawing) -> tuple[float, float, float, float]:
    """The rectangle inside an arch the app may turn green, as fractions of the arch.

    It has to hold every language's lettering and be nothing but opening, because the green is
    put on by multiplying: black stays black and white goes green, so a white arch edge caught
    inside the band comes out as a green hairline down the side of the arch.
    """
    top = round(float(low) - 0.015, 3)
    bottom = round(float(high) + 0.025, 3)
    band = (NAME_CLEAR, top, round(1 - NAME_CLEAR, 3), bottom)
    worst = 1.0
    for x0, y0, x1, y1 in boxes:
        wide, tall = x1 - x0, y1 - y0
        opening = ndimage.binary_fill_holes(drawing.openings[y0:y1, x0:x1])
        piece = opening[int(tall * band[1]):int(tall * band[3]),
                        int(wide * band[0]):int(wide * band[2])]
        worst = min(worst, float(piece.mean()))
    if worst < 0.999:
        raise SystemExit(f"the green band is only {worst:.4f} opening; it would tint the stone")
    print(f"   green band {band}, {worst:.5f} opening at worst")
    return band


def name_sheet(drawings: dict[str, Drawing], boxes, band, out: Path) -> None:
    """A sheet per language: each arch as it is drawn, with the prayer the app will OPEN when
    that arch is pressed printed under it.

    No machine here reads Bengali. What the app knows is that the leftmost arch is Fajr; what
    the drawing knows is which word is in it; and nothing in the repo can put those two
    together. The same answer the menus got in 1.89: crop the boxes, label them with what the
    app will do, and let a person look. tests/test_ui.py measures what it can of this -- which
    word each arch's shape is nearest to -- and that is a check on this sheet, not a substitute
    for it.
    """
    from PIL import ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    for lang, drawing in drawings.items():
        tiles = []
        for x0, y0, x1, y1 in boxes:
            wide, tall = x1 - x0, y1 - y0
            tiles.append(drawing.picture.crop(
                (x0 + int(wide * band[0]), y0 + int(tall * band[1]),
                 x0 + int(wide * band[2]), y0 + int(tall * band[3]))))
        width = sum(t.width for t in tiles) + 10 * (len(tiles) + 1)
        sheet = Image.new("RGB", (width, tiles[0].height + 70), "black")
        pen = ImageDraw.Draw(sheet)
        x = 10
        for tile, prayer in zip(tiles, PRAYERS):
            sheet.paste(tile, (x, 10))
            pen.text((x + 10, tile.height + 30), f"opens {prayer}", fill="white")
            x += tile.width + 10
        sheet.save(out / f"{lang}.png")
    print(f"   wrote {len(drawings)} sheets to {out} -- SOMEBODY HAS TO LOOK AT THESE")


def same_everywhere(drawings: dict[str, Drawing], boxes: dict[str, list]) -> None:
    """Every language's drawing must be the same canvas with the same arches in the same places,
    or the touch targets belong to one picture and the words to another."""
    first = boxes[LANGS[0]]
    for lang in LANGS:
        if boxes[lang] != first:
            raise SystemExit(f"{lang}: arches at {boxes[lang]}, but {LANGS[0]} has {first}")
    base = drawings[LANGS[0]].grey
    inside = np.zeros(base.shape, bool)
    for x0, y0, x1, y1 in first:
        inside[y0:y1, x0:x1] = True
    for lang in LANGS[1:]:
        differs = drawings[lang].grey != base
        if (differs & ~inside).any():
            where = np.argwhere(differs & ~inside)[0]
            raise SystemExit(f"{lang}: differs from {LANGS[0]} outside the arches, "
                             f"first at x{where[1]} y{where[0]}")
    print(f"   all ten drawings: same canvas, same five arches, "
          f"nothing differing outside them")


def build_menu(folder: Path, out: Path) -> tuple[float, float]:
    print("The Salaah menu")
    drawings, boxes = {}, {}
    for lang in LANGS:
        path = folder / f"five_prayer_mosque_{lang}.png"
        if not path.is_file():
            raise SystemExit(f"missing {path}")
        drawings[lang] = Drawing(path)
        boxes[lang] = drawings[lang].arches(len(PRAYERS))
    same_everywhere(drawings, boxes)

    first = drawings[LANGS[0]]
    arch_boxes = boxes[LANGS[0]]
    # Across ALL TEN, not the English one. The tall scripts are the ones that decide: Bengali
    # and Hindi reach a fifth of an arch higher than the Latin names, and a band measured on
    # English alone would cut the top off them when the arch goes green.
    said = [drawings[lang].lettering(arch_boxes) for lang in LANGS]
    low = min(s[0] for s in said)
    high = max(s[1] for s in said)
    left = min(s[2] for s in said)
    right = max(s[3] for s in said)
    print(f"   the drawn names run y {low:.3f}-{high:.3f}, x {left:.3f}-{right:.3f} of an arch")
    print(f"   (English alone would have said y {said[0][0]:.3f}-{said[0][1]:.3f})")
    band = tint_band(arch_boxes, low, high, first)
    name_sheet(drawings, arch_boxes, band, ROOT / "tools" / "mosque-names")
    clock = first.clock()
    minarets = first.minarets()
    print(f"   clock box x {clock[0]}-{clock[2]} y {clock[1]}-{clock[3]}")
    for side, box in minarets.items():
        print(f"   {side:5s} minaret top x {box[0]}-{box[2]} y {box[1]}-{box[3]}")

    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("arch-*.png"):
        if stale.name in ("arch-outer.png", "arch-inner.png"):
            continue     # the drawn arch, which the fall-back prayer page still uses
        stale.unlink()
        print(f"   dropped {stale.name}, which nothing has read since 1.63")
    for lang in LANGS:
        name = "mosque.png" if lang == "en" else f"mosque.{lang}.png"
        drawings[lang].with_a_see_through_sky().save(out / name, optimize=True)
    (out / "mosque.json").write_text(json.dumps({
        "schema": 1,
        "image": "mosque.png",
        "drawn": "dark",
        "sky": True,
        "names": "drawn",
        # Fajr is in the LEFTMOST arch in all ten, Urdu and Arabic included. The 1.84 mosque
        # was drawn the other way round in those two and the app turns the order round when a
        # drawing says to -- so this says, rather than the app guessing from the language and
        # getting it wrong, which it did: the green landed on Dhuhr when it was Maghrib and a
        # finger on Fajr opened Isha. tools/mosque-names/ has the sheet to check it by.
        "names_in_rtl": "same order",
        "size": [1920, 1080],
        "arches": {prayer: {"box": list(box)} for prayer, box in zip(PRAYERS, arch_boxes)},
        "text": {"name": [round(v, 4) for v in band]},
        "clock": {"box": list(clock), "ink": "dark"},
        "minarets": minarets,
        "images": {lang: ("mosque.png" if lang == "en" else f"mosque.{lang}.png")
                   for lang in LANGS},
    }, indent=2) + "\n", encoding="utf-8")
    return round(float(low), 4), round(float(high), 4)


def build_pages(folder: Path, out: Path, units: dict[str, int]) -> None:
    print("The five prayer pages")
    for prayer, count in units.items():
        path = folder / f"mosque_{count}_archways_1920x1080.png"
        if not path.is_file():
            raise SystemExit(f"{prayer} has {count} units and there is no {path.name}")
        drawing = Drawing(path)
        arch_boxes = drawing.arches(count)
        clock = drawing.clock()
        here = out / prayer
        here.mkdir(parents=True, exist_ok=True)
        for stale in here.glob("arch-*.png"):
            stale.unlink()
        drawing.with_a_see_through_sky().save(here / "mosque.png", optimize=True)
        (here / "mosque.json").write_text(json.dumps({
            "schema": 1,
            "image": "mosque.png",
            "drawn": "dark",
            "sky": True,
            "size": [1920, 1080],
            "arches": {str(i): {"box": list(box)} for i, box in enumerate(arch_boxes, start=1)},
            "text": {"number": list(NUMBER_BAND), "label": list(LABEL_BAND)},
            "clock": {"box": list(clock), "ink": "dark"},
        }, indent=2) + "\n", encoding="utf-8")
        print(f"   {prayer:8s} {count} arches from {path.name}; "
              f"clock x {clock[0]}-{clock[2]} y {clock[1]}-{clock[3]}")


def build_kalima(folder: Path, out: Path, band: tuple[float, float]) -> None:
    """The six-kalima menu, off the same six-archway drawing as Isha's page.

    Not asked for, and done anyway, because replacing the Salaah menu without it would have
    LEFT A GAP rather than avoided one. The two mosques are meant to be the same building --
    there is a test that measures it -- and the 1.64 kalima drawing is a flat white silhouette
    on the old 1396x733 canvas. Beside the new brickwork it is a different building on a
    different canvas: the dome jumps a sixth of the screen and the minarets an eighth as you
    move between the two menus, and the style changes entirely.

    The numbers are still the app's: one line, a plain digit, "1 to 10 is universal regardless
    of language". Hence a number band with no height and a deep band for the digit.
    """
    print("The six kalima")
    path = folder / "mosque_6_archways_1920x1080.png"
    drawing = Drawing(path)
    arch_boxes = drawing.arches(6)
    clock = drawing.clock()
    minarets = drawing.minarets()
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("arch-*.png"):
        stale.unlink()
    drawing.with_a_see_through_sky().save(out / "mosque.png", optimize=True)
    (out / "mosque.json").write_text(json.dumps({
        "schema": 1,
        "image": "mosque.png",
        "drawn": "dark",
        "sky": True,
        "size": [1920, 1080],
        "arches": {str(i): {"box": list(box)} for i, box in enumerate(arch_boxes, start=1)},
        "text": {"number": [band[0], band[0]], "label": list(band)},
        "clock": {"box": list(clock), "ink": "dark"},
        "minarets": minarets,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"   6 arches from {path.name}; clock x {clock[0]}-{clock[2]} y {clock[1]}-{clock[3]}")


def units_per_prayer() -> dict[str, int]:
    """How many units each prayer has, read from the school rather than typed in here. An arch
    per unit or the app draws its own arches instead, so these two must agree."""
    school = json.loads((ROOT / "assets" / "content" / "schools" / "hanafi.json")
                        .read_text(encoding="utf-8"))
    return {prayer: len(school["prayers"][prayer]) for prayer in PRAYERS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mosques", type=Path)
    parser.add_argument("arches", type=Path)
    args = parser.parse_args()
    units = units_per_prayer()
    print("the school says:", ", ".join(f"{p} {n}" for p, n in units.items()))
    lettering = build_menu(args.mosques, ROOT / "assets" / "mosque")
    build_pages(args.arches, ROOT / "assets" / "prayers", units)
    build_kalima(args.arches, ROOT / "assets" / "kalima", lettering)


if __name__ == "__main__":
    main()
