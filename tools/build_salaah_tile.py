#!/usr/bin/env python3
"""Makes the Salaah tile for the 7" menu.

    python3 tools/build_salaah_tile.py

The six kalima had that square until the du'a menu took them over, and Harry asked for a prayer
mat and the word Salaah in its place, landing on the front door.

The other five tiles on that menu were drawn by hand, and this one is not -- so rather than draw
a mat of my own beside them, it is built out of drawings that already exist: the mat comes off
the Prayer tile on the du'a menu, which is the same hand, and the frame and the lettering are
measured off the tile it replaces so the six still look like one set. Better a borrowed glyph in
the right frame than a new glyph in a frame that nearly matches.

If Harry draws one later, drop it in as assets/knowledge/salaah.png and this can go.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
TILES = ROOT / "assets" / "knowledge"
MAT = ROOT / "assets" / "duas-menu" / "prayer.png"
LIKE = TILES / "quran.png"          # the tile whose frame and lettering this copies
WORD = "Salaah"
INK = 128


def frame_of(tile: Path) -> tuple[int, int, int]:
    """The tile's size and how thick its outline is, measured off it.

    The thickness is the median leading run of ink down the middle third of the columns, not the
    run down one column: the first try read a single column, landed on a two-pixel scrap of
    antialiasing at the very top, and drew a hairline frame beside five heavy ones.
    """
    grey = np.asarray(Image.open(tile).convert("L"))
    ink = grey < INK
    runs = []
    for x in range(grey.shape[1] // 3, grey.shape[1] * 2 // 3):
        column = ink[:, x]
        start = int(np.argmax(column)) if column.any() else 0
        run = 0
        while start + run < len(column) and column[start + run]:
            run += 1
        if run:
            runs.append(run)
    thick = int(np.median(runs)) if runs else 12
    return grey.shape[1], grey.shape[0], max(2, thick)


def label_band(tile: Path) -> tuple[int, int]:
    """Where the word sits on the tile being copied: the top and bottom of its lettering."""
    grey = np.asarray(Image.open(tile).convert("L"))
    ink = grey < INK
    height = grey.shape[0]
    inner = ink[:, int(grey.shape[1] * 0.2):int(grey.shape[1] * 0.8)]
    rows = [y for y in range(int(height * 0.6), int(height * 0.97)) if inner[y].any()]
    return (min(rows), max(rows)) if rows else (int(height * 0.72), int(height * 0.9))


def glyph(source: Path) -> Image.Image:
    """The mat off the Prayer tile: everything inside its frame, trimmed to the drawing."""
    grey = np.asarray(Image.open(source).convert("L"))
    ink = grey < INK
    labels, count = ndimage.label(ink)
    sizes = ndimage.sum(ink, labels, range(1, count + 1))
    H, W = ink.shape
    inside = []
    for k in range(count):
        ys, xs = np.nonzero(labels == k + 1)
        wide = (xs.max() - xs.min()) / W
        tall = (ys.max() - ys.min()) / H
        if wide > 0.8 and tall > 0.8:
            continue                    # the tile's own frame
        inside.append((int(sizes[k]), k + 1))
    if not inside:
        raise SystemExit(f"nothing inside the frame of {source}")
    # The mat is the big shapes; the word under it is a row of small ones. A quarter of the
    # largest separates them by a wide margin -- the mihrab and the mat are thousands of pixels
    # and a letter is hundreds.
    biggest = max(n for n, _ in inside)
    keep = np.zeros_like(ink)
    for n, label in inside:
        if n >= biggest * 0.25:
            keep |= (labels == label)
    ys, xs = np.nonzero(keep)
    if not len(ys):
        raise SystemExit(f"no mat found inside {source}")
    cut = Image.fromarray(np.where(keep, 0, 255).astype(np.uint8)[
        ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return cut


def lettering(size: int) -> ImageFont.FreeTypeFont:
    for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        for where in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/liberation/"):
            try:
                return ImageFont.truetype(where + name, size)
            except OSError:
                pass
    return ImageFont.load_default()


def build(out: Path = TILES / "salaah.png") -> None:
    width, height, thick = frame_of(LIKE)
    top, bottom = label_band(LIKE)
    tile = Image.new("L", (width, height), 255)
    pen = ImageDraw.Draw(tile)
    radius = int(min(width, height) * 0.11)
    pen.rounded_rectangle((thick // 2, thick // 2, width - thick // 2 - 1, height - thick // 2 - 1),
                          radius=radius, outline=0, width=thick)

    mat = glyph(MAT)
    room_w = int(width * 0.74)
    room_h = int((top - thick * 2) * 0.92)
    scale = min(room_w / mat.width, room_h / mat.height)
    mat = mat.resize((max(1, int(mat.width * scale)), max(1, int(mat.height * scale))),
                     Image.LANCZOS).point(lambda v: 0 if v < 160 else 255)
    middle = (top + thick * 2) // 2
    tile.paste(mat, ((width - mat.width) // 2, middle - mat.height // 2), Image.eval(mat, lambda v: 255 - v))

    # Sized by the ink it makes rather than by its point size, so it matches the word on the
    # tile beside it: a point size means different things in different faces, and the first go
    # came out half again as big as "6 Kalima".
    size, font = bottom - top, None
    while size > 8:
        font = lettering(size)
        box = font.getbbox(WORD)
        if (box[3] - box[1]) <= (bottom - top) and (box[2] - box[0]) <= width * 0.78:
            break
        size -= 2
    box = font.getbbox(WORD)
    pen.text(((width - (box[2] - box[0])) // 2 - box[0],
              bottom - (box[3] - box[1]) - box[1]), WORD, font=font, fill=0)

    out.parent.mkdir(parents=True, exist_ok=True)
    tile.convert("RGBA").save(out)
    try:                                  # --out can point anywhere, including outside the repo
        said = out.relative_to(ROOT)
    except ValueError:
        said = out
    print(f"{said}  {width}x{height}, outline {thick}px, "
          f"mat {mat.width}x{mat.height}, '{WORD}' at {size}px")


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_salaah_tile")
    ap.add_argument("--out", type=Path, default=TILES / "salaah.png")
    args = ap.parse_args()
    build(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
