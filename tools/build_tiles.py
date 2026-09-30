#!/usr/bin/env python3
"""Cuts a sheet of drawn tiles into the separate pictures the menus use.

    python3 tools/build_tiles.py duas-menu.png assets/duas-menu \
        morning evening sleep waking food home \
        mosque travel prayer protection forgiveness guidance \
        gratitude family health worry knowledge kalima

The du'a menu and the 7" menu are each one drawing, so that the tiles share a hand and the
lettering on them is part of the design. That leaves the job of getting eighteen pictures out of
one, which used to be done by measuring the sheet by hand -- and a drawing redone at a different
size means measuring it again.

So the tiles are found rather than measured. Each one is a rounded rectangle drawn as a single
unbroken outline, which is a connected run of ink enclosing white, and nothing else in the sheet
is anywhere near that size. Anything sitting wholly inside another tile is an icon, not a tile:
the compass in Guidance is one closed ring big enough to be mistaken for a small tile otherwise.

They are then handed out in reading order -- left to right, top to bottom -- to the names given
on the command line, and it refuses if the count does not match. A drawing with seventeen tiles
and eighteen names is a mistake worth stopping for, not something to fill in with a blank.

Needs Pillow, NumPy and SciPy.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INK = 128          # darker than this is a line
SMALLEST = 150     # a tile is at least this wide and this tall
PAD = 11           # a little white round each tile, so the outline is not flush to the edge


def tiles_in(sheet) -> list[tuple[int, int, int, int]]:
    """Every tile in the sheet, as (left, top, right, bottom), in reading order."""
    import numpy as np
    from scipy import ndimage

    dark = np.asarray(sheet.convert("L")) < INK
    labels, count = ndimage.label(dark)
    found = []
    for i, where in enumerate(ndimage.find_objects(labels), start=1):
        top, bottom = where[0].start, where[0].stop
        left, right = where[1].start, where[1].stop
        if right - left >= SMALLEST and bottom - top >= SMALLEST:
            found.append([left, top, right, bottom])

    # An icon that happens to be big and closed -- the compass -- sits wholly inside its tile.
    kept = [box for box in found
            if not any(other is not box and other[0] <= box[0] and other[1] <= box[1]
                       and other[2] >= box[2] and other[3] >= box[3] for other in found)]

    # Reading order. Rows are grouped by the tops falling within half a tile of each other,
    # rather than by dividing the sheet up, so a sheet with a different number of rows works.
    tall = min(b[3] - b[1] for b in kept)
    kept.sort(key=lambda b: b[1])
    rows, row = [], [kept[0]]
    for box in kept[1:]:
        if box[1] - row[0][1] > tall * 0.5:
            rows.append(row); row = [box]
        else:
            row.append(box)
    rows.append(row)
    out = []
    for row in rows:
        out.extend(sorted(row, key=lambda b: b[0]))
    return [tuple(b) for b in out]


def build(sheet_path: Path, out: Path, names: list[str], dry: bool = False) -> int:
    from PIL import Image
    sheet = Image.open(sheet_path).convert("RGBA")
    boxes = tiles_in(sheet)
    print(f"{sheet_path.name}: {sheet.width}x{sheet.height}, {len(boxes)} tiles found")
    if len(boxes) != len(names):
        print(f"\n{len(boxes)} tiles but {len(names)} names. Nothing written.", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    for name, (left, top, right, bottom) in zip(names, boxes):
        cut = sheet.crop((max(0, left - PAD), max(0, top - PAD),
                          min(sheet.width, right + PAD), min(sheet.height, bottom + PAD)))
        print(f"   {name:14} {cut.width:3}x{cut.height:3}")
        if not dry:
            cut.save(out / f"{name}.png", optimize=True)
    if dry:
        print("\n(dry run: nothing written)")
    else:
        print(f"\n-> {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_tiles")
    ap.add_argument("sheet", type=Path, help="the drawing, all the tiles on one sheet")
    ap.add_argument("out", type=Path, help="where the separate pictures go")
    ap.add_argument("names", nargs="+", help="what to call them, in reading order")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return build(args.sheet, args.out, args.names, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
