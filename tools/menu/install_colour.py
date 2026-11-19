#!/usr/bin/env python3
"""Puts Harry's coloured menu sheet in, in all ten languages.

    python3 tools/menu/install_colour.py assets/knowledge sidemenu.gif
    python3 tools/menu/install_colour.py assets/children  games.gif

Harry drew the two film menus again in colour on black, in English. The mat ships each of these
menus in ten languages, so a coloured mat set to Urdu would otherwise read English -- which is
the fault that bit the coloured mosque at 2.45, and it is worth not shipping twice.

So the ten coloured films are made here: HIS DRAWING, THEIR LETTERING. Each language's words are
lifted out of the film that already ships and laid into his coloured tiles. Harry chose this at
2.44 over redrawing the lettering, and it is the same reasoning -- the shipped words have been
through ten exports and a reading, and nothing about colouring an icon should disturb them.

WHERE THE WORDS ARE IS MEASURED, and it took four attempts to measure it honestly, so the ones
that failed are worth writing down:

    the last run of ink down the tile      -- finds the tile's own bottom border
    the last run, with the border cut off  -- finds the corner marks on the children's sheet
    what differs between the languages     -- finds every animated icon as well, because the
                                              ten films are NOT phase-aligned: frame 0 of the
                                              Urdu sheet is at a different point in the loop
                                              from frame 0 of the English one

What works is both of the last two at once. The lettering is the part of a tile that DIFFERS
BETWEEN FILMS and DOES NOT MOVE WITHIN ONE. The icons are the same drawing in all ten and they
animate; the words are different in all ten and they are still. Fifteen of the sixteen tiles
then come out as a single block at the foot of the tile, and the sixteenth -- Journey to the
Mosque -- comes out as one block plus a couple of hundred stray pixels of compression noise up
in the maze, which SPECK clears.

Needs Pillow, NumPy and SciPy:  pip3 install --break-system-packages pillow numpy scipy
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent.parent

#: How far a tile in the new sheet may sit from the box menu.json holds, ON TOP OF the uniform
#: inset the sheet is found to have. Harry's tiles have no black outline, so their white starts
#: where the old sheet's ink ended -- every one of the sixteen is inset by exactly six pixels on
#: all four sides. A uniform inset is the drawing being drawn differently; a tile that has moved
#: on its own is a button over the wrong picture, and that is what this refuses.
SLACK = 3

#: Darker than this is ink, lighter is paper. The same figure build_tiles.py cuts on.
INK = 128

#: A pixel that swings more than this across a film is moving. Set well above the few levels a
#: palette change moves a still pixel by, and well below a drawn line appearing or going.
MOVES = 20

#: Two plates differ here if a channel is this far apart. Lettering is black on white, so the
#: real differences are near 255 and nothing near this threshold is a close call.
DIFFERS = 40

#: Specks smaller than this are not lettering. The children's maze carries a couple of hundred
#: stray pixels of compression noise that are still in every film and differ between them, and
#: without this they drag the Mosque tile's band up from row 359 to row 40 -- which would paste
#: a language's maze over Harry's.
SPECK = 120

#: Rows kept clear above and below the lettering, so a descender or a Bengali matra that sits a
#: pixel outside what was measured still comes across.
MARGIN = 4

#: Kept clear of the left and right edges of a tile when the band is lifted. The shipped sheets
#: have a black outline running down both sides of every row; Harry's do not. Lifting the full
#: width would paste that outline into his tiles.
EDGE = 14

#: How many colours the finished films are written in. Measured rather than chosen: see
#: `squeeze`, which reports what the picture actually lost.
COLOURS = 128


def film_frames(path: Path) -> tuple[list[Image.Image], list[int], int]:
    frames, held = [], []
    with Image.open(path) as film:
        loop = film.info.get("loop", 0)
        for frame in ImageSequence.Iterator(film):
            frames.append(frame.convert("RGB"))
            held.append(frame.info.get("duration", 100))
    return frames, held, loop


def plate_and_swing(path: Path, chunk: int = 120) -> tuple[np.ndarray, np.ndarray]:
    """The still picture under a film, and how far each pixel moves across it.

    In row chunks. A menu sheet is 1980x1080 and forty-eight frames, and np.median over the
    whole stack at once sorts a float64 copy of it -- most of a gigabyte, and the machine
    killed the first version of this for exactly that.
    """
    with Image.open(path) as film:
        stack = np.array([np.asarray(f.convert("L")) for f in ImageSequence.Iterator(film)],
                         dtype=np.uint8)
    plate = np.empty(stack.shape[1:], np.uint8)
    swing = np.empty(stack.shape[1:], np.uint8)
    for y in range(0, stack.shape[1], chunk):
        part = stack[:, y:y + chunk]
        plate[y:y + chunk] = np.median(part, axis=0).astype(np.uint8)
        swing[y:y + chunk] = part.max(0) - part.min(0)
    return plate, swing


def lettering_in(folder: Path, films: dict) -> np.ndarray:
    """The mask of every word on the sheet: different between films, still within one."""
    from scipy import ndimage

    plates, still = {}, None
    for lang, name in films.items():
        plate, swing = plate_and_swing(folder / name)
        plates[lang] = plate
        quiet = swing <= MOVES
        still = quiet if still is None else (still & quiet)
    base = plates["en"].astype(np.int16)
    differs = np.zeros(base.shape, bool)
    for lang, plate in plates.items():
        if lang == "en":
            continue
        differs |= np.abs(plate.astype(np.int16) - base) > DIFFERS
    mask = differs & still
    labels, count = ndimage.label(mask)
    if count:
        sizes = ndimage.sum(mask, labels, range(1, count + 1))
        small = np.flatnonzero(sizes < SPECK) + 1
        if len(small):
            mask[np.isin(labels, small)] = False
    return mask, plates


def tiles_on_black(frame: Image.Image, wanted: int) -> list[list[int]]:
    """The tiles in a sheet drawn light on black, in reading order.

    tools/build_tiles.py finds tiles as dark outlines enclosing white, because that is how the
    sheets were drawn. Harry's coloured sheets are the same tiles with the paper cut away and
    set on black, so the tile is the LIGHT region and the ground is the ink. Same job, figure
    and ground swapped.
    """
    from scipy import ndimage

    light = np.asarray(frame.convert("L")) >= INK
    labels, _ = ndimage.label(light)
    found = []
    for where in ndimage.find_objects(labels):
        top, bottom = where[0].start, where[0].stop
        left, right = where[1].start, where[1].stop
        if right - left >= 150 and bottom - top >= 150:
            found.append([left, top, right, bottom])
    kept = [box for box in found
            if not any(other is not box and other[0] <= box[0] and other[1] <= box[1]
                       and other[2] >= box[2] and other[3] >= box[3] for other in found)]
    if len(kept) != wanted:
        return kept
    tall = min(b[3] - b[1] for b in kept)
    kept.sort(key=lambda b: b[1])
    rows, row = [], [kept[0]]
    for box in kept[1:]:
        if box[1] - row[0][1] < tall / 2:
            row.append(box)
        else:
            rows.append(sorted(row, key=lambda b: b[0]))
            row = [box]
    rows.append(sorted(row, key=lambda b: b[0]))
    return [box for line in rows for box in line]


def check_the_tiles(his: Image.Image, described: dict) -> int:
    """Harry's tiles must be the menu's tiles. Returns the uniform inset, or stops.

    A tile that has moved is a button over the wrong picture, which on this mat means a child
    pressing Qibla Quest and getting the jigsaw. An inset that is the SAME on all four sides of
    all the tiles is not that: it is the black outline the old cutter counted and his sheet does
    not have.
    """
    names = list(described["tiles"])
    found = tiles_on_black(his, len(names))
    if len(found) != len(names):
        raise SystemExit(f"  found {len(found)} tiles in the new sheet and the menu has "
                         f"{len(names)}. Nothing written.")
    offs = []
    for name, box in zip(names, found):
        want = described["tiles"][name]
        offs.append([box[0] - want[0], box[1] - want[1], want[2] - box[2], want[3] - box[3]])
    flat = [v for off in offs for v in off]
    inset = round(sum(flat) / len(flat))
    worst, where = 0, ""
    for name, off in zip(names, offs):
        for side, v in zip(("left", "top", "right", "bottom"), off):
            if abs(v - inset) > worst:
                worst, where = abs(v - inset), f"{name} {side} ({v} against {inset})"
    print(f"  tiles: all {len(names)} inset by {inset}px, worst departure {worst}px "
          f"{'(' + where + ')' if worst else ''}")
    if worst > SLACK:
        raise SystemExit(f"  a tile has moved: {where}. The menu's boxes came from the English "
                         f"sheet and every language is laid over them, so this would put the "
                         f"buttons over the wrong pictures. Nothing written.")
    return inset


def bands_for(described: dict, mask: np.ndarray) -> dict:
    """The rectangle of each tile that holds its word."""
    out = {}
    for name, (x0, y0, x1, y1) in described["tiles"].items():
        inside = mask[y0:y1, x0:x1]
        rows = np.nonzero(inside.any(1))[0]
        if len(rows) == 0:
            raise SystemExit(f"  no lettering found in {name}. Nothing written.")
        blocks = int((np.diff(rows) > 1).sum()) + 1
        top = max(0, int(rows.min()) - MARGIN)
        bottom = min(y1 - y0, int(rows.max()) + 1 + MARGIN)
        out[name] = (top, bottom, blocks)
    return out


def squeeze(frames: list[Image.Image], colours: int) -> list[Image.Image]:
    """One palette for the whole film, laid on without dither.

    The exporters write every frame in a palette built for photographs and re-dither each one,
    so a background that never moves is different on every frame and the compressor can do
    nothing with it. One palette and no dither is what makes these files small -- and it is
    also what keeps a still tile still, which is the thing the mat's own menus rely on.
    """
    step = max(1, len(frames) // 8)
    sample = frames[::step]
    tall = Image.new("RGB", (frames[0].width, frames[0].height * len(sample)))
    for i, frame in enumerate(sample):
        tall.paste(frame, (0, i * frame.height))
    palette = tall.quantize(colors=colours, method=Image.Quantize.MEDIANCUT)
    out = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    for frame in out:
        # The GIF writer cannot pack a tuple transparency into one byte and dies on it; this is
        # the fault that once ate the English children's film. Nothing to keep: these sheets are
        # opaque.
        frame.info.pop("transparency", None)
    return out


def write_film(frames: list[Image.Image], held: list[int], loop: int, out: Path) -> None:
    """Written beside, checked, then moved into place.

    Saving straight over the destination once left an 800-byte stub where a menu had been, when
    Pillow raised partway through. Every check in this tool is worth nothing if the write itself
    can destroy what it is replacing.
    """
    beside = out.with_suffix(out.suffix + ".new")
    try:
        frames[0].save(beside, format="GIF", save_all=True, append_images=frames[1:],
                       loop=loop, duration=held, optimize=True, disposal=1)
        with Image.open(beside) as check:
            if check.size != frames[0].size or getattr(check, "n_frames", 1) != len(frames):
                raise SystemExit(f"  {beside.name} came back as {check.size} with "
                                 f"{getattr(check, 'n_frames', 1)} frames; not written")
        beside.replace(out)
    finally:
        beside.unlink(missing_ok=True)


def install(folder: Path, sheet: Path) -> int:
    described = json.loads((folder / "menu.json").read_text(encoding="utf-8"))
    films = described["films"]
    tiles = described["tiles"]
    wide, tall = described["size"]

    his, held, loop = film_frames(sheet)
    print(f"{folder.name}: {sheet.name} is {his[0].size}, {len(his)} frames")
    if list(his[0].size) != [wide, tall]:
        raise SystemExit(f"  the menu is {wide}x{tall} and this is {his[0].size}; the boxes "
                         f"would not line up. Nothing written.")
    english, _, _ = film_frames(folder / films["en"])
    if len(his) != len(english):
        raise SystemExit(f"  {sheet.name} has {len(his)} frames and {films['en']} has "
                         f"{len(english)}; the menu's films should run together. Nothing written.")

    inset = check_the_tiles(his[0], described)

    mask, plates = lettering_in(folder, films)
    bands = bands_for(described, mask)
    _, his_swing = plate_and_swing(sheet)
    print(f"  lettering is {100 * mask.mean():.2f}% of the sheet")
    for name, (top, bottom, blocks) in bands.items():
        x0, y0, x1, y1 = tiles[name]
        moving = his_swing[y0 + top:y0 + bottom, x0 + EDGE:x1 - EDGE] > MOVES
        note = "" if blocks == 1 else f"  <- {blocks} blocks"
        print(f"    {name:11s} rows {top:4d}-{bottom:4d} of {y1 - y0}; "
              f"{100 * moving.mean():.2f}% of that band moves in his sheet{note}")
        if moving.mean() > 0.001:
            raise SystemExit(f"  {name}'s word band moves in {sheet.name}. Lifting a still band "
                             f"into a moving one would freeze part of the drawing. Nothing written.")

    total_before = total_after = 0
    for lang, name in films.items():
        source = Path(name)
        out = folder / f"{source.stem}-colour{source.suffix}"
        plate = plates[lang]
        frames = []
        changed = 0
        for frame in his:
            canvas = np.asarray(frame).copy()
            for tile, (top, bottom, _) in bands.items():
                x0, y0, x1, y1 = tiles[tile]
                words = plate[y0 + top:y0 + bottom, x0 + EDGE:x1 - EDGE]
                patch = np.dstack([words, words, words])
                here = canvas[y0 + top:y0 + bottom, x0 + EDGE:x1 - EDGE]
                changed += int((np.abs(here.astype(np.int16) - patch.astype(np.int16)) > DIFFERS)
                               .any(2).sum())
                here[:] = patch
            frames.append(Image.fromarray(canvas, "RGB"))
        kept = squeeze(frames, COLOURS)
        write_film(kept, held, loop, out)
        was = (folder / name).stat().st_size
        now = out.stat().st_size
        total_before += was
        total_after += now
        print(f"  {out.name:22s} {now / 1e6:5.2f}MB  "
              f"({changed // max(len(his), 1):,} pixels of lettering a frame)")
    print(f"  ten films: {total_after / 1e6:.2f}MB in colour, against "
          f"{total_before / 1e6:.2f}MB for the ten that ship")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="assets/knowledge or assets/children")
    ap.add_argument("sheet", type=Path, help="Harry's coloured sheet, in English")
    args = ap.parse_args()
    folder = args.folder if args.folder.is_absolute() else ROOT / args.folder
    sheet = args.sheet if args.sheet.is_absolute() else ROOT / args.sheet
    return install(folder, sheet)


if __name__ == "__main__":
    raise SystemExit(main())
