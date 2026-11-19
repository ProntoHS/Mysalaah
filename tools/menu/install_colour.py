#!/usr/bin/env python3
"""Puts a coloured menu sheet of Harry's in, in all ten languages.

    python3 tools/menu/install_colour.py assets/hadith-menu    hadith.gif
    python3 tools/menu/install_colour.py assets/duas-menu      dua.gif
    python3 tools/menu/install_colour.py assets/knowledge      side.gif
    python3 tools/menu/install_colour.py assets/children       games.gif
    python3 tools/menu/install_colour.py assets/knowledge-menu wudu.gif

Harry draws these menus again in colour on black, in English. The mat ships each of them in ten
languages, so a coloured mat set to Urdu would otherwise read English -- the fault that bit the
coloured mosque at 2.45. So the words come from the films that already ship: HIS DRAWING, THEIR
LETTERING.

WHAT THIS WRITES, and why it is not ten films:

    menu-colour.gif        one coloured film, his sheet with every caption rubbed out
    words/en.png           the English words alone, white on nothing
    words/ur.png           the Urdu words, and so on for all ten

The words go in a folder of their own rather than beside the films, because a menu folder has
an invariant worth keeping: every .png in it is a tile picture, and assets/duas-menu has a test
that says so. Dropping fifty new pictures in beside them would have meant weakening that test
to allow for the exception, which is the wrong direction -- it has been true since the menus
were built and it is the kind of rule that catches a drawing left over from an older cut.

The ten languages differ ONLY in the words at the foot of each tile; everything else is the
same pixels. Shipping ten complete films carried that identical animation ten times over, and
on these sheets it is expensive -- a coloured drawing with glows compresses about four times
worse than the black-and-white line art, so the hadith menu alone came to 13.8MB for its ten.
One film and ten small pictures is 1.6MB for the same menu, and every future coloured menu
costs one film instead of ten. The lettering never moves -- measured at 0.00% across all five
sheets -- so a still picture is not an approximation of it, it is what it is.

The words are painted over the film by salaah/filmsheet.py, which is the only place that knows
these two files belong together.

WHERE THE WORDS ARE, which took three wrong answers to get right. All three are kept because
each one looks reasonable until it is measured:

  what differs between the ten shipped films    -- catches every icon as well. The du'a icons
      are laid out AROUND the label, so a language whose word runs to two lines gets a smaller
      icon pushed higher up: "Worry & Sadness" is two lines in English and one in Urdu, and
      the icon's edges then differ between films as honestly as the lettering does.
  the same, minus whatever moves within a film  -- does not help. It is not a phase problem.
  the floor and ceiling of each film            -- does not help either, and made it worse.

What works is asking BOTH sheets the thing each one knows. The shipped films know where the
words are, because the words are what differ. Harry's sheet knows where his DRAWING is, because
he draws icons in colour and letters in white. The band is the differing rows with every row he
drew in colour taken out, and it may never climb above the lowest row he coloured.

That leaves one leak: the shipped icon sometimes reaches LOWER than his -- the du'a family's
feet, a ray off the gratitude heart -- so a piece of it sits inside the band beside the word. It
cannot be cut by raising the band, because the word is down there too, and it cannot be cut by
counting how many languages share the pixel, because half of them share a Latin alphabet. But a
piece of icon hanging into the band is joined, pixel to pixel, to the drawing above it, and a
letterform is joined to nothing. So the ink is labelled across the whole tile and only the
pieces lying wholly inside the band are kept. No threshold, no sweep.

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

#: Darker than this is ink on a sheet drawn black on white. The figure build_tiles.py cuts on.
INK = 128

#: How far from grey a pixel must stray to be part of a coloured drawing rather than lettering
#: or a frame. Well above the two or three levels a palette shift moves a grey by.
SATURATED = 40

#: Two plates differ here if a channel is this far apart. Lettering is black on white, so the
#: real differences are near 255 and nothing near this is a close call.
DIFFERS = 40

#: Rows kept clear above and below the lettering, for a descender or a Bengali matra sitting a
#: pixel outside what was measured. Never allowed to cross into Harry's drawing.
MARGIN = 4

#: Kept clear of the left and right edges of a tile. The shipped sheets have an outline running
#: down both sides of every row; lifting the full width would bring it across.
EDGE = 14

#: Specks smaller than this are not lettering. The children's maze carries a couple of hundred
#: stray pixels of compression noise that differ between films.
SPECK = 120

#: How far one tile's lettering may sit from the offset the REST of the sheet shows, in pixels.
#: A uniform offset is a sheet drawn differently -- Harry's 7in words sit 6.73px lower than the
#: shipped ones on every tile, and his wu'du word 4.66px lower -- and that is his business. One
#: tile out of line with its neighbours is a tile that has moved, which is a button over the
#: wrong picture. Across the five sheets the worst departure is 1.72px, so this is three and a
#: half times the worst of them.
#:
#: Two geometric tests were tried first and both are the wrong question. "Is the content
#: centred in its box" fails on the 7in Salaah tile at 0.34 of a tile, because that icon is a
#: prayer mat that unrolls out of nothing and there is no icon to balance the word against.
#: "Is the content where the shipped sheet puts it" fails on the same sheet at 0.057, because
#: the shipped tiles have an outline hugging the box and Harry's have none, so it compares his
#: icon against their frame. Insetting the measurement to drop the frame does not settle
#: either: swept at 0, 3, 5, 8 and 12 per cent the five sheets' numbers wander without a
#: plateau, because an inset large enough to lose an outline eats into an icon.
#:
#: The lettering is the right thing to measure. It is what the graft depends on landing, it is
#: present in every tile that has a caption, and it is the same object on both sheets.
DRIFT = 6.0

#: How far outside its box a drawing may reach. NOT zero: the outline round these tiles sits on
#: the edge of the touchable box and spills a pixel, and the films that ship do the same -- the
#: identical 9,468 pixels on Harry's hadith sheet and on the one it stands beside. What matters
#: is that nothing is drawn in the GAPS. Two is the worst of the five sheets.
SPILL = 3

#: How many colours the one coloured film is written in.
COLOURS = 128


def frames_of(path: Path):
    with Image.open(path) as film:
        loop = film.info.get("loop", 0)
        out, held = [], []
        for frame in ImageSequence.Iterator(film):
            out.append(frame.convert("RGB"))
            held.append(frame.info.get("duration", 100))
    return out, held, loop


def plate(path: Path, chunk: int = 120) -> np.ndarray:
    """The still picture under a film: the middle value each pixel takes across it.

    In row chunks. A menu sheet is 1980x1080 and four dozen frames, and np.median over the
    whole stack sorts a float64 copy of it -- most of a gigabyte, and the machine killed the
    first version of this for exactly that.
    """
    with Image.open(path) as film:
        stack = np.array([np.asarray(f.convert("L")) for f in ImageSequence.Iterator(film)],
                         dtype=np.uint8)
    out = np.empty(stack.shape[1:], np.uint8)
    for y in range(0, stack.shape[1], chunk):
        out[y:y + chunk] = np.median(stack[:, y:y + chunk], axis=0).astype(np.uint8)
    return out


def ever_lit(path: Path, dark_on_white: bool, chunk: int = 120) -> np.ndarray:
    """Every pixel the film ever draws on, taken over the whole film.

    OVER THE WHOLE FILM, not frame zero. The 7in menu's Salaah tile is a prayer mat that
    unrolls out of nothing: on frame zero there is no icon at all, only the word, and a layout
    checked on one frame calls that a tile whose content has slid a third of the way down.
    """
    with Image.open(path) as film:
        stack = np.array([np.asarray(f.convert("L")) for f in ImageSequence.Iterator(film)],
                         dtype=np.uint8)
    out = np.zeros(stack.shape[1:], bool)
    for y in range(0, stack.shape[1], chunk):
        part = stack[:, y:y + chunk]
        out[y:y + chunk] = (part < 215).any(0) if dark_on_white else (part >= 40).any(0)
    return out


def his_colour(path: Path, chunk: int = 120) -> np.ndarray:
    """Every pixel Harry drew in colour, over the whole film, so a drawing that moves cannot
    creep under the band between frames."""
    with Image.open(path) as film:
        stack = np.array([np.asarray(f.convert("RGB")) for f in ImageSequence.Iterator(film)],
                         dtype=np.uint8)
    lit = np.zeros(stack.shape[1:3], bool)
    for y in range(0, stack.shape[1], chunk):
        part = stack[:, y:y + chunk].astype(np.int16)
        lit[y:y + chunk] = ((part.max(3) - part.min(3)) > SATURATED).any(0)
    return lit


def despeck(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(mask)
    if count:
        sizes = ndimage.sum(mask, labels, range(1, count + 1))
        small = np.flatnonzero(sizes < SPECK) + 1
        if len(small):
            mask[np.isin(labels, small)] = False
    return mask


def differing(folder: Path, films: dict) -> tuple[np.ndarray, dict]:
    plates = {lang: plate(folder / name) for lang, name in films.items()}
    base = plates["en"].astype(np.int16)
    mask = np.zeros(base.shape, bool)
    for lang, pl in plates.items():
        if lang != "en":
            mask |= np.abs(pl.astype(np.int16) - base) > DIFFERS
    return despeck(mask), plates


def band_for(tile, differs: np.ndarray, coloured: np.ndarray):
    x0, y0, x1, y1 = tile
    tall = y1 - y0
    rows = differs[y0:y1, x0:x1].any(1)
    drawn = coloured[y0:y1, x0:x1].any(1)
    lowest = int(np.nonzero(drawn)[0].max()) if drawn.any() else -1
    keep = np.nonzero(rows & ~drawn & (np.arange(tall) > lowest))[0]
    if len(keep) == 0:
        return None
    return max(lowest + 1, int(keep.min()) - MARGIN), min(tall, int(keep.max()) + 1 + MARGIN)


def letterforms(ink: np.ndarray, top: int, bottom: int) -> np.ndarray:
    """The pieces of ink lying wholly between top and bottom. Anything joined to the drawing
    above the band comes away with it -- which keeps the du'a family's feet out of its caption."""
    labels, count = ndimage.label(ink)
    out = np.zeros_like(ink)
    if not count:
        return out
    for i, where in enumerate(ndimage.find_objects(labels), start=1):
        if where[0].start >= top and where[0].stop <= bottom:
            out[where][labels[where] == i] = True
    return out


def nothing_in_the_gaps(sheet: Path, described: dict) -> None:
    """Nothing may be drawn between the boxes the buttons use.

    Exact on all five sheets. The outline round a tile sits ON the edge of its box and spills a
    pixel or two, and the films that ship spill the identical 9,468 pixels on the hadith sheet,
    so what is asked is how far OUT anything reaches rather than whether anything crosses.
    """
    mine = ever_lit(sheet, dark_on_white=False)
    inside = np.zeros(mine.shape, bool)
    for x0, y0, x1, y1 in described["tiles"].values():
        inside[y0:y1, x0:x1] = True
    reach = ndimage.binary_dilation(inside, np.ones((2 * SPILL + 1, 2 * SPILL + 1), bool))
    stray = int((mine & ~reach).sum())
    edge = int((mine & ~inside).sum())
    print(f"  gaps: {edge:,} lit pixels sit on a box edge, {stray:,} in the gaps between boxes")
    if stray:
        raise SystemExit(f"  {stray:,} lit pixels are drawn more than {SPILL}px outside every "
                         f"box -- a drawing in the gap between buttons rather than an outline "
                         f"on an edge. Nothing written.")


def check_the_lettering(sheet: Path, his: np.ndarray, plates: dict, tiles: dict,
                        bands: dict) -> None:
    """Harry's own words must sit where the shipped words sit, tile for tile.

    This is what the graft depends on: a language's word is painted into the band his word
    occupies, so if his sheet's layout had moved, his word would have moved with it and the
    painted one would land somewhere else. It is also the one thing both sheets undeniably
    have in common -- his icons are coloured and theirs are line art, his tiles are outlined
    and theirs are filled, but a caption is a caption.

    A uniform offset is a sheet drawn differently and is fine. One tile out of line with its
    neighbours is a tile that has moved, and that is a button over the wrong picture.
    """
    seen = []
    for name, (top, bottom) in bands.items():
        x0, y0, x1, y1 = tiles[name]
        theirs = letterforms(plates["en"][y0:y1, x0 + EDGE:x1 - EDGE] < INK, top, bottom)[top:bottom]
        ours = letterforms(his[y0:y1, x0 + EDGE:x1 - EDGE] > INK, top, bottom)[top:bottom]
        if not theirs.any() or not ours.any():
            raise SystemExit(f"  {name}: the shipped sheet has {int(theirs.sum())} pixels of "
                             f"word here and Harry's has {int(ours.sum())}. Nothing written.")
        ty, tx = ndimage.center_of_mass(theirs)
        oy, ox = ndimage.center_of_mass(ours)
        seen.append((name, oy - ty, ox - tx))
    down = float(np.median([d for _, d, _ in seen]))
    across = float(np.median([a for _, _, a in seen]))
    worst, where = 0.0, ""
    for name, d, a in seen:
        off = max(abs(d - down), abs(a - across))
        if off > worst:
            worst, where = off, name
    print(f"  lettering: his words sit {down:+.2f}px down and {across:+.2f}px across from the "
          f"shipped ones; worst tile departs from that by {worst:.2f}px ({where or 'n/a'})")
    if worst > DRIFT:
        raise SystemExit(f"  {where}'s word is {worst:.2f}px out of line with the rest of the "
                         f"sheet, which is a tile that has moved rather than a sheet redrawn. "
                         f"Nothing written.")


def squeeze(frames: list, colours: int) -> list:
    """One palette for the whole film, laid on without dither. An exporter writes every frame in
    a palette built for photographs and re-dithers each one, so a background that never moves is
    different on every frame and the compressor can do nothing with it."""
    step = max(1, len(frames) // 8)
    sample = frames[::step]
    tall = Image.new("RGB", (frames[0].width, frames[0].height * len(sample)))
    for i, frame in enumerate(sample):
        tall.paste(frame, (0, i * frame.height))
    palette = tall.quantize(colors=colours, method=Image.Quantize.MEDIANCUT)
    out = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    for frame in out:
        # The GIF writer cannot pack a tuple transparency into one byte and dies on it; the
        # fault that once ate the English children's film. Nothing to keep: these are opaque.
        frame.info.pop("transparency", None)
    return out


def put_in_place(write, out: Path) -> None:
    """Written beside, read back, then moved into place. Saving straight over the destination
    once left an 800-byte stub where a menu had been, when Pillow raised partway through."""
    beside = out.with_suffix(out.suffix + ".new")
    try:
        write(beside)
        with Image.open(beside) as check:
            check.load()
        beside.replace(out)
    finally:
        beside.unlink(missing_ok=True)


def install(folder: Path, sheet: Path) -> int:
    described = json.loads((folder / "menu.json").read_text(encoding="utf-8"))
    films, tiles = described["films"], described["tiles"]
    wide, tall = described["size"]

    his, held, loop = frames_of(sheet)
    print(f"{folder.name}: {sheet.name} is {his[0].size}, {len(his)} frames, {held[0]}ms")
    if list(his[0].size) != [wide, tall]:
        raise SystemExit(f"  the menu is {wide}x{tall} and this is {his[0].size}; the boxes "
                         f"would not line up. Nothing written.")
    with Image.open(folder / films["en"]) as old:
        theirs = getattr(old, "n_frames", 1)
    if theirs != len(his):
        # Not a refusal. The two films are alternatives -- one is shown or the other is, never
        # both -- so nothing requires them to run together, and the du'a menu ships 36 frames
        # against Harry's 48. 2.46 refused this, which was an assumption rather than a rule.
        print(f"  note: {films['en']} runs {theirs} frames and this runs {len(his)}. They are "
              f"alternatives, so that is allowed; the coloured mat simply animates differently.")

    nothing_in_the_gaps(sheet, described)

    differs, plates = differing(folder, films)
    coloured = his_colour(sheet)
    bands, spare = {}, []
    for name, box in tiles.items():
        if not differs[box[1]:box[3], box[0]:box[2]].any():
            spare.append(name)
            continue
        band = band_for(box, differs, coloured)
        if band is None:
            raise SystemExit(f"  no lettering found below the drawing in {name}. Nothing written.")
        bands[name] = band
    print(f"  lettering is {100 * differs.mean():.2f}% of the sheet; {len(bands)} tiles carry a "
          f"word, {len(spare)} are spare")
    check_the_lettering(sheet, plate(sheet), plates, tiles, bands)

    # The one film: his sheet with every caption rubbed out, so the words can be painted over it
    rubbed = []
    for frame in his:
        canvas = np.asarray(frame).copy()
        for name, (top, bottom) in bands.items():
            x0, y0, x1, y1 = tiles[name]
            canvas[y0 + top:y0 + bottom, x0 + EDGE:x1 - EDGE] = 0
        rubbed.append(Image.fromarray(canvas, "RGB"))
    kept = squeeze(rubbed, COLOURS)
    film_out = folder / f"{Path(films['en']).stem}-colour.gif"
    put_in_place(lambda p: kept[0].save(p, format="GIF", save_all=True, append_images=kept[1:],
                                        loop=loop, duration=held, optimize=True, disposal=1),
                 film_out)
    print(f"  {film_out.name:22s} {film_out.stat().st_size / 1e6:5.2f}MB  "
          f"(one film, every caption rubbed out)")

    total = film_out.stat().st_size
    for lang, name in films.items():
        pl = plates[lang]
        alpha = np.zeros(pl.shape, np.uint8)
        for tile, (top, bottom) in bands.items():
            x0, y0, x1, y1 = tiles[tile]
            ink = pl[y0:y1, x0 + EDGE:x1 - EDGE] < INK
            word = letterforms(ink, top, bottom)[top:bottom]
            # The shipped word is black on white and antialiased. Carried across as the ALPHA
            # of a white letterform, so the smooth edges come with it instead of being
            # thresholded into a staircase.
            faces = 255 - pl[y0 + top:y0 + bottom, x0 + EDGE:x1 - EDGE]
            alpha[y0 + top:y0 + bottom, x0 + EDGE:x1 - EDGE] = np.where(word, faces, 0)
        white = np.full(pl.shape + (3,), 255, np.uint8)
        words = Image.fromarray(np.dstack([white, alpha]), "RGBA")
        out = folder / "words" / f"{lang}.png"
        out.parent.mkdir(exist_ok=True)
        put_in_place(lambda p, w=words: w.save(p, format="PNG", optimize=True), out)
        total += out.stat().st_size
        print(f"  words/{out.name:16s} {out.stat().st_size / 1e3:6.1f}KB  "
              f"({int((alpha > 0).sum()):,} pixels of lettering)")

    stale = sorted(p for p in folder.glob("*-colour.gif") if p != film_out)
    for old in stale:
        old.unlink()
    if stale:
        print(f"  removed {len(stale)} per-language coloured films left by 2.46: "
              f"{', '.join(p.name for p in stale[:3])}"
              f"{' ...' if len(stale) > 3 else ''}")
    before = sum((folder / n).stat().st_size for n in films.values())
    print(f"  this menu in colour: {total / 1e6:.2f}MB, against {before / 1e6:.2f}MB for the "
          f"ten black-and-white films it sits beside")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="the menu folder, e.g. assets/hadith-menu")
    ap.add_argument("sheet", type=Path, help="Harry's coloured sheet, in English")
    args = ap.parse_args()
    folder = args.folder if args.folder.is_absolute() else ROOT / args.folder
    sheet = args.sheet if args.sheet.is_absolute() else ROOT / args.sheet
    return install(folder, sheet)


if __name__ == "__main__":
    raise SystemExit(main())
