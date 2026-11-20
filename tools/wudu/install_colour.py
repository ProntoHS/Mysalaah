#!/usr/bin/env python3
"""Puts Harry's 2.44 coloured wu'du artwork in, and the coloured world map with it.

    python3 tools/wudu/install_colour.py <the eight animations> <the ten sheets> <the map>

Harry, 17 November 2026: "i want to give the wu'du page and steps the same treatment. replace
with coloured version, i have included the full languages menu as a zip. the other zip are the
actual animations. also as the background is white, the white can be inverted if on dark theme
and the pictures can stay the same. replace qibla quest world map with this new one, background
again is whit so can be inverted depending on theme." And then, when he saw the first attempt:
"i dont want you to invert the the actual child and wash basin etc, just the background only
if possible."

That is exactly what comes out of here, and the first way I tried it was wrong.

                        ---- THE BACKGROUND, AND ONLY THE BACKGROUND ----

Inverting every pixel that is close to grey LOOKS like "just the background". It is not. Near-
white paper and the near-white of the boy's thobe are the same colour, so the thobe goes with
the paper; his hair is near-black and comes back speckled salt-and-pepper, because the dither
leaves half its pixels just over the line and half just under. I rendered it and looked at it,
and it is visibly wrong.

So the paper is found as a REGION rather than by colour: every near-white pixel that can be
reached from the edge of the picture without crossing an outline. That is the same cut that
took the sky out of the mosques at 2.41, and it has the same property that makes it worth
trusting -- it does not depend on where the threshold is put. The same mask comes out at 20,
28, 40 and 60, because the paper meets the drawing at a hard black outline and there is nothing
in between. Specks of dither stranded inside the paper are absorbed, and that is flat from 16
pixels to 1024.

The paper is then made TRANSPARENT rather than painted. The page shows through it: white by
day, black after dark, and the child, the basin and the tap are the same pixels in both.

                 ---- THE LETTERING IS THE ONE THING THAT MUST TURN OVER ----

The seven step pictures are not only drawings: each has a frame round it, a numbered badge and
a label, all drawn in black. Left alone those are black lettering on a black page. So for the
step pictures a night version is built here, and what turns over in it is decided per DRAWN
SHAPE rather than per pixel: every connected piece of ink is looked at on its own, and a piece
with colour in it is left exactly as drawn while a piece with no colour in it is inverted. The
boy keeps his black hair because his hair is part of a shape that also contains his face.

The films need no night version -- there is no lettering on them -- and neither does the map.
Harry's Kaaba sits on the orange of Arabia rather than on the paper, so it stays visible.

                      ---- THIRTY-THREE MEGABYTES DOWN TO SEVEN ----

The animations arrived at 4.2 MB each, 33 MB for eight, against the 191 KB the eight films they
replace take between them. That is not detail, it is noise: they were saved with the picture
re-dithered on every frame, so the flat colours are stippled with a different random pattern 48
times over. Eighty per cent of the picture swings by more than 40 levels across the loop while
the drawing itself does not move at all. It would have shimmered on the mat.

The cure is the median of the 48 frames, pixel by pixel. Random dither cancels and what is left
is the painting underneath, grain and all -- the plate looks BETTER than any single frame Harry
sent, not worse, and the crops are in tools/ARTWORK-MEASURED.md. Every frame is then rebuilt as
that plate with the frame's own pixels put back only where something genuinely moves.

WHAT GENUINELY MOVES IS FOUND ON THE SIGNED DIFFERENCE FROM THE PLATE, SMOOTHED. Dither is
high-frequency and averages to nothing; a hand moving does not. Done on the ABSOLUTE difference
it does not work at all -- the mean of an absolute dither is a large positive number everywhere
and the mask comes back covering a quarter of the picture, which I measured before I understood
why.

Only then are the two cheap things possible: one palette for the whole film with no dithering,
and each frame carrying only what changed since the last. With the original noise nothing was
ever equal to anything, and both were worth nothing.

                              ---- WHAT THIS DOES NOT DO ----

It does not touch the city pins in qibla_quest.py. That file warns that a redrawn map silently
invalidates every one of them, and it has happened twice. This map is the October one recoloured:
the two silhouettes agree to 96%, their centroids to four decimal places, their extents to two
pixels, and all five cities plus Makkah still land on ink. Checked, not assumed -- and checked
again by --measure, which prints those numbers against whatever map is passed in.

Needs Pillow, NumPy, SciPy and scikit-image, like the other builders here. None of them are
needed on the mat.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence
from scipy.ndimage import (binary_closing, binary_dilation, distance_transform_edt, label,
                           uniform_filter)
from skimage.morphology import disk, remove_small_holes, remove_small_objects

HERE = Path(__file__).resolve().parent.parent.parent
WUDU = HERE / "assets" / "wudu"
CHILDREN = HERE / "assets" / "children"

#: Which of Harry's animations is which step. The sixth and seventh are the two halves of one
#: step: wiping the head and wiping the ears are drawn apart and done together, which is why
#: `head` has a second film and the mat stacks them.
FILMS = {
    "01_wash_hands": "hands.gif",
    "02_rinse_mouth": "mouth.gif",
    "03_rinse_nose": "nose.gif",
    "04_wash_face": "face.gif",
    "05_wash_arm": "arms.gif",
    "06_wipe_head": "head.gif",
    "07_wipe_ears": "head-2.gif",
    "08_wash_foot": "feet.gif",
}

#: The seven steps in the order they are drawn across the sheet, which is the order the wu'du
#: is done in and the order the menu shows them in.
STEPS = ("hands", "mouth", "nose", "face", "arms", "head", "feet")

#: The ten languages the mat speaks. English keeps the bare filename -- see duamenu.drawn_in,
#: which falls back to it -- and the other nine carry theirs before the extension.
LANGUAGES = ("en", "ar", "bn", "es", "fr", "hi", "pt", "ru", "ur", "zh")

NEAR = 28        # how far from white still counts as paper; 20..60 all give the same mask
SPECK = 16       # dither specks stranded inside the paper; 16..1024 all give the same mask

# HOW FAR THE PAPER IS TAKEN BACK INTO THE DRAWING, and it is not the same for the two kinds of
# artwork, because the two kinds have different edges.
#
# Every ink-and-paper boundary in the animations carries a lime-green fringe a pixel or two
# wide -- it is in the files Harry sent, and it is invisible on white paper and a bright rim
# round the boy on a black one. Two pixels takes it off completely; one leaves a trace along
# the top of his hair.
#
# The sheets and the map have no such fringe, and two pixels does real damage to both: it eats
# the frame drawn round each step from five pixels thick to ONE, and it rubs out the smallest
# islands in Indonesia and the Caribbean -- 9% of the map's land, measured. One pixel leaves
# the frame at three and every island where it was, while still taking off the pale halo that
# a nought-pixel cut leaves ringing every coastline.
#
# Both were arrived at by rendering the alternatives onto a black page and looking at them.
FILM_GROW = 2
STILL_GROW = 1
MOVING = 18.0    # how far the smoothed difference from the plate must stray to be motion
SMOOTH = 9       # the window that cancels the dither
SPREAD = 4       # pixels the moving region is grown by, so motion is never clipped
COLOURS = 128    # one palette for a whole film
TILE_COLOURS = 255   # and for a step picture, which keeps a slot for the transparency
SHAPE = 20       # ink pieces smaller than this are left to their neighbours

# ---- PAPER THE EDGE OF THE PICTURE CANNOT REACH, which all three kinds of artwork have and
# ---- which none of them have in the same way. Flooding in from the border alone leaves it
# ---- opaque, and on a black page a patch of opaque paper is a white box.
#
# A FILM has gaps in the drawing: the piece of wall seen through the arch of the tap is the
# biggest, and it came out as a white rectangle under the spout on the night screen. What
# tells a gap from a drawn white line is not its area but its THICKNESS -- a gap is something
# you could see the page through, a highlight down the boy's thobe is a few pixels wide. So an
# enclosed piece of paper is taken when a disc of GAP_DEEP pixels fits inside it. Measured
# across all eight films, the same pieces are taken at 8, 9 and 10, and the set only changes
# at 6 (which starts eating the thobe) and at 12 (which starts leaving gaps behind).
#
# A STEP SHEET has a frame drawn round it, so its paper comes in two pieces -- the margin
# outside the frame, which the border reaches, and the column inside it, which it does not.
# There is exactly one of those and it is enormous: 212,636 pixels against 283 for the largest
# other enclosed piece, a factor of seven hundred and fifty. So it is taken by being the
# biggest, with nothing to tune.
#
# A MAP is land on water, and water is water wherever it is. The Mediterranean, the Black Sea
# and the Caspian are enclosed by land and they are not drawn in: they are the same paper as
# the ocean outside. Nothing is white INSIDE this drawing, so every enclosed piece of paper is
# sea -- except the speckles of near-white inside Greenland and the pale interiors, which are
# what a first attempt at "take all the white" punched holes in. The four seas are 6404, 1688,
# 1374 and 1262 pixels and the largest speckle is 42, so a floor anywhere from 100 to 800
# takes exactly the four.
GAP_DEEP = 9     # how thick a gap in a film must be before the page is let through it
WATER = 100      # how big an enclosed piece of a map must be before it counts as sea
TINT = 8.0       # how far from grey a piece of ink must stray to count as part of the drawing.
                 # It was render.COLOUR_ENOUGH when that was an averaged saturation and this was
                 # written to match it. At 2.46 that measure became a SHARE of clearly coloured
                 # pixels, because averaging judged a drawing partly on how much empty space it
                 # was drawn with. This number stayed where it was: it is a per-pixel threshold
                 # on a piece of ink, which is the job it always did, and it is no longer the
                 # same question as the one render asks.


# ----------------------------------------------------------------- the paper, as a region

def paper_in(frame: np.ndarray, reach: str = "edge", grow: int = STILL_GROW) -> np.ndarray:
    """The page behind a drawing: near-white, and not shut in by the drawing.

    A white thobe is near-white too and IS shut in, which is the whole reason this is a region
    and not a colour.

    [reach] says what to do about paper the border cannot reach, and the three answers are the
    three kinds of artwork -- see the note beside GAP_DEEP for the measurements:

        "edge"   nothing. Only what the border reaches.
        "gaps"   and any enclosed piece thick enough to be a gap in the drawing. The films.
        "inside" and the one big piece a drawn frame encloses. The step sheets.
        "water"  and every enclosed piece bigger than a speckle. The map.
    """
    pale = frame.min(2) >= 255 - NEAR
    patch, _ = label(pale)
    edges = set(patch[0, :]) | set(patch[-1, :]) | set(patch[:, 0]) | set(patch[:, -1])
    edges.discard(0)
    mask = np.isin(patch, list(edges))
    sizes = np.bincount(patch.ravel())
    sizes[0] = 0
    if reach == "inside":
        mask |= patch == sizes.argmax()
    elif reach == "water":
        for piece in np.where(sizes > WATER)[0]:
            if piece not in edges:
                mask |= patch == piece
    elif reach == "gaps":
        # Biggest first and only the big ones: a distance transform per piece is the expensive
        # part of this tool, and nothing under a few hundred pixels can be GAP_DEEP thick.
        for piece in np.argsort(sizes)[::-1][:25]:
            if not sizes[piece] or piece in edges or sizes[piece] < GAP_DEEP ** 2 * 3:
                continue
            if distance_transform_edt(patch == piece).max() >= GAP_DEEP:
                mask |= patch == piece
    mask = remove_small_holes(mask, SPECK)
    return binary_dilation(mask, disk(grow)) if grow else mask


def coloured_shapes(frame: np.ndarray, paper: np.ndarray) -> np.ndarray:
    """Which of the ink is part of the drawing rather than lettering.

    Per connected piece, not per pixel. A pixel of the boy's hair is as grey as a pixel of the
    label above him; the piece of ink his hair belongs to also contains his face, and the piece
    the label belongs to contains nothing but black.
    """
    pieces, many = label(~paper)
    stray = frame.max(2) - frame.min(2)
    drawing = np.zeros(paper.shape, dtype=bool)
    for piece in range(1, many + 1):
        where = pieces == piece
        if where.sum() < SHAPE:
            continue
        if stray[where].mean() >= TINT:
            drawing |= where
    return drawing


# ------------------------------------------------------------------------------- the films

def rebuild(frames: list[np.ndarray]) -> tuple[list[np.ndarray], np.ndarray, float]:
    """The still plate, with each frame's moving part put back on top of it."""
    stack = np.stack(frames).astype(np.float32)
    plate = np.median(stack, 0)
    # The paper is taken where it is paper in EVERY frame. The wobble is a quarter of a per
    # cent, but a frame that had to paint paper back over a drawing could not do it: the film
    # is shipped differenced, and a differenced frame can only add.
    #
    # THE GAPS ARE FOUND ON THE PLATE AND THEN SHARED BY EVERY FRAME. Found frame by frame
    # they would come and go: water falling through the arch of the tap splits that gap into
    # two thinner pieces, neither of them thick enough to count, and the AND below would then
    # drop the gap altogether. The plate is the drawing standing still, which is what a gap is
    # a property of. Checked by looking: the stream and every droplet survive it.
    ground = np.all([paper_in(one.astype(np.int16), grow=FILM_GROW) for one in frames], 0)
    ground |= paper_in(plate.astype(np.int16), reach="gaps", grow=FILM_GROW)
    out, moved = [], []
    for one in stack:
        off = one - plate
        soft = np.abs(np.stack([uniform_filter(off[:, :, c], SMOOTH) for c in range(3)], -1)).max(2)
        mask = binary_closing(soft > MOVING, disk(3))
        mask = remove_small_objects(mask, 200)
        mask = remove_small_holes(mask, 400)
        mask = binary_dilation(mask, disk(SPREAD))
        moved.append(float(mask.mean()))
        out.append(np.where(mask[:, :, None], one, plate))
    return [np.clip(o, 0, 255).astype(np.uint8) for o in out], ground, float(np.mean(moved))


def write_film(frames, ground, path: Path, pause: int) -> None:
    ink = np.concatenate([f[~ground] for f in frames])
    taken = np.random.default_rng(0).choice(len(ink), min(200_000, len(ink)), replace=False)
    chosen = Image.fromarray(ink[taken].reshape(-1, 1, 3)).convert(
        "P", palette=Image.Palette.ADAPTIVE, colors=COLOURS)
    # Every index is moved up one so that 0 is free to mean "let the page show through", which
    # is both the paper and, after the first frame, every pixel that has not changed.
    indexed = [np.asarray(Image.fromarray(f).quantize(palette=chosen,
                                                      dither=Image.Dither.NONE)) + 1
               for f in frames]
    for one in indexed:
        one[ground] = 0
    table = [0, 0, 0] + list(chosen.getpalette()[:COLOURS * 3])
    pages = []
    for i, one in enumerate(indexed):
        shown = one.copy()
        if i:
            shown[one == indexed[i - 1]] = 0
        page = Image.fromarray(shown.astype(np.uint8), mode="P")
        page.putpalette(table + [0] * (768 - len(table)))
        pages.append(page)
    # disposal=1, not 2: each frame is left in place for the next one to add to. Disposal 2
    # clears back to the background between frames, which would make every frame have to carry
    # the whole picture again and the differencing worth nothing.
    pages[0].save(path, save_all=True, append_images=pages[1:], duration=pause, loop=0,
                  transparency=0, disposal=1, optimize=True)


def install_films(source: Path, out: Path) -> int:
    before = after = 0
    for stem, name in FILMS.items():
        found = sorted(source.glob(f"{stem}*.gif"))
        if not found:
            print(f"  !! nothing in {source} for {stem}", file=sys.stderr)
            return 1
        reel = Image.open(found[0])
        pause = int(reel.info.get("duration", 120))
        frames = [np.asarray(f.convert("RGB")) for f in ImageSequence.Iterator(reel)]
        if len(frames) < 2:
            print(f"  !! {found[0].name} has {len(frames)} frames", file=sys.stderr)
            return 1
        frames, ground, moved = rebuild(frames)
        write_film(frames, ground, out / name, pause)
        was, now = found[0].stat().st_size, (out / name).stat().st_size
        before, after = before + was, after + now
        print(f"  {found[0].name:20s} -> {name:12s} {was // 1024:5d} KB -> {now // 1024:4d} KB"
              f"   paper {100 * ground.mean():4.1f}%   moving {100 * moved:4.1f}%")
    print(f"  eight films: {before // 1024} KB -> {after // 1024} KB")
    return 0


# ------------------------------------------------------------------------- the step pictures

def cut_sheet(sheet_path: Path) -> list[Image.Image]:
    """The seven columns of a sheet, left to right, using the cutter the menus already use."""
    sys.path.insert(0, str(HERE / "tools"))
    from build_tiles import PAD, tiles_in              # noqa: E402  (after the path is set)
    sheet = Image.open(sheet_path).convert("RGB")
    boxes = tiles_in(sheet)
    if len(boxes) != len(STEPS):
        raise SystemExit(f"{sheet_path.name} cut into {len(boxes)} columns, not {len(STEPS)}")
    return [sheet.crop((max(0, left - PAD), max(0, top - PAD),
                        min(sheet.width, right + PAD), min(sheet.height, bottom + PAD)))
            for left, top, right, bottom in boxes]


def reads_right_to_left(lang: str) -> bool:
    """Whether this language's pack says the mat reads right to left.

    Asked of the pack rather than written down here. Which languages those are is the pack's
    business and it is already the answer everything else on the mat uses.
    """
    import json
    pack = HERE / "assets" / "content" / "packs" / lang / "pack.json"
    try:
        return json.loads(pack.read_text(encoding="utf-8")).get("dir") == "rtl"
    except (OSError, ValueError):
        return False


def drawings_in(column: Image.Image) -> int:
    """How many separate drawings are in this column: one for six of the steps, more for the
    head, which is drawn as the head and the ears one above the other."""
    frame = np.asarray(column).astype(np.int16)
    drawing = coloured_shapes(frame, paper_in(frame, reach="inside"))
    pieces, _ = label(drawing)
    sizes = np.bincount(pieces.ravel())
    sizes[0] = 0
    return int((sizes > drawing.size * 0.01).sum())


def in_step_order(columns: list[Image.Image], lang: str, sheet: str) -> list[Image.Image]:
    """The seven columns in the order of the wu'du, whichever way the sheet reads.

    HARRY DRAWS THE URDU AND ARABIC SHEETS THE OTHER WAY ROUND, step 1 on the right, which is
    how somebody reading Urdu or Arabic comes to a row of seven things. duamenu.py says so and
    lays the row out to match, and the first run of this tool put the feet on the hands and the
    hands on the feet in both of those languages for exactly that reason.

    So the order follows the pack, AND IT IS THEN CHECKED AGAINST THE DRAWING -- the head is the
    one step drawn as two pictures, so whichever column holds the most drawings must be the
    sixth. A sheet that disagrees is refused rather than installed back to front: the mat has
    already shipped one screen where an Urdu reader pressing Fajr got Isha, and nothing in the
    app can notice a picture in the wrong place.
    """
    ordered = list(reversed(columns)) if reads_right_to_left(lang) else list(columns)
    many = [drawings_in(column) for column in ordered]
    if many.index(max(many)) != STEPS.index("head"):
        raise SystemExit(
            f"{sheet}: the column with the most drawings in it is number "
            f"{many.index(max(many)) + 1} of seven, and the head is step "
            f"{STEPS.index('head') + 1}. This sheet does not read the way "
            f"{lang}'s pack says it should. Nothing written.")
    return ordered


def keep_the_paper_out(picture: Image.Image, reach: str):
    """A picture with its paper made transparent, and the night version beside it."""
    frame = np.asarray(picture).astype(np.int16)
    paper = paper_in(frame, reach=reach)
    drawing = coloured_shapes(frame, paper)
    clear = np.where(paper, 0, 255).astype(np.uint8)
    day = np.dstack([frame.astype(np.uint8), clear])
    # The night version: the drawing exactly as it is, everything else turned over.
    night = np.dstack([np.where(drawing[:, :, None], frame, 255 - frame).astype(np.uint8), clear])
    return (Image.fromarray(day, "RGBA"), Image.fromarray(night, "RGBA"),
            float(paper.mean()), float(drawing.mean()))


def lettering_in(tile: Image.Image) -> np.ndarray:
    """The frame, the numbered badge and the label of an older step picture, as a mask.

    WHY AN OLDER ONE. Harry's 2.44 sheets are the drawings he wants and the lettering he did
    not mean to send: the labels lost between a third and three quarters of their ink in all
    ten languages, and in Urdu, Arabic and Hindi the letters came apart as well -- the joins
    are not made, so the words do not read. Harry, asked, chose to keep the lettering already
    on the mat and take only the drawings from the new sheets. So the type on these tiles is
    the 2.43 type, which nobody has complained about and which at least reads.

    Two pieces, and neither of them is a guessed row:

    THE FRAME is the one connected piece of ink whose bounding box spans the whole tile. There
    is exactly one in every one of the seventy, 12,376 pixels in each.

    THE BADGE AND THE LABEL are every piece of ink above the drawing. The drawing is the
    tallest run of inked rows, and on all seventy of the 2.43 tiles there is a clear run of at
    least 63 blank rows between the bottom of the label and the top of it -- the tightest being
    Arabic and Urdu's "rinse mouth" at 63, the widest 308. The cut is taken in the middle of
    whatever that run is on the tile in hand, so it has thirty rows of air on either side and
    nothing is hard-coded.
    """
    pixels = np.asarray(tile.convert("RGBA")).astype(int)
    tall, wide = pixels.shape[:2]
    ink = (pixels[:, :, 3] >= 128) & (pixels[:, :, :3].max(2) < 110)

    pieces, _ = label(ink)
    sizes = np.bincount(pieces.ravel())
    sizes[0] = 0
    frame = np.zeros_like(ink)
    for piece in np.argsort(sizes)[::-1][:8]:
        if not sizes[piece]:
            continue
        down, across = np.where(pieces == piece)
        if (across.max() - across.min()) > wide * 0.9 and (down.max() - down.min()) > tall * 0.9:
            frame = pieces == piece
            break
    if not frame.any():
        raise SystemExit(f"no frame found in {tile.size} tile: this is not a 2.43 step picture")

    # Inside the frame only, so its own left and right edges do not fill every row.
    inside = ink[:, int(wide * 0.12):int(wide * 0.88)]
    inked = inside.sum(1) > 2
    runs, start = [], None
    for row, lit in enumerate(inked):
        if lit and start is None:
            start = row
        elif not lit and start is not None:
            if row - start > 3:
                runs.append((start, row))
            start = None
    if start is not None and len(inked) - start > 3:
        runs.append((start, len(inked)))
    if len(runs) < 2:
        raise SystemExit("this tile has no lettering above its drawing")
    picture = max(runs, key=lambda run: run[1] - run[0])
    above = [run for run in runs if run[1] <= picture[0]]
    if not above:
        raise SystemExit("this tile has nothing drawn above its picture")
    cut = (above[-1][1] + picture[0]) // 2

    letters = ink.copy()
    letters[cut:, :] = False
    return letters | frame


def thinner(picture: Image.Image, colours: int = TILE_COLOURS) -> Image.Image:
    """The same picture in [colours] colours. FASTOCTREE because it is the one of Pillow's
    quantisers that keeps an alpha channel, and the alpha here is what carries the paper."""
    return picture.quantize(colors=colours, method=Image.Quantize.FASTOCTREE,
                            dither=Image.Dither.NONE)


#: Where the numbered badge sits on a step picture, as a fraction of the tile. It is in the
#: same place on all seventy, in every language and both sets of sheets.
BADGE = (0.025, 0.100, 0.33, 0.67)


def badge_of(tile: Image.Image) -> np.ndarray:
    """The numbered badge, at one size, so that two tiles' badges can be compared."""
    grey = tile.convert("L").resize((285, 1027), Image.LANCZOS)
    top, bottom, left, right = BADGE
    return np.asarray(grey).astype(float)[int(1027 * top):int(1027 * bottom),
                                          int(285 * left):int(285 * right)]


def lettering_for(step: str, older: Path, tail: str) -> Path:
    """Which of the older tiles carries the lettering for this step -- ASKED OF THE BADGE, not
    taken from the filename.

    THE FILENAME CANNOT BE TRUSTED, and the proof is in the 2.43 release itself: its Urdu and
    Arabic step pictures are in reverse. step-hands.ur.png is wholly the seventh tile -- badge
    7, the words for washing the feet, and the boy sitting washing his feet -- and step-feet.ur
    is the first. Harry drew those sheets with step 1 on the right, as an Urdu reader expects,
    and whatever cut them read them left to right. So on an Urdu or Arabic mat the seven steps
    have been shown in reverse order, each tile's number and name contradicting the step it
    opens, since those sheets went in. That is the same fault as the Fajr arch opening Isha at
    2.41 and it is live right now.

    The badge settles it with nothing to trust: the digit in it is the same drawing in every
    language, so the tile whose badge looks most like English step N's badge IS step N. Matched
    across the seventy 2.43 tiles it answers 6,5,4,3,2,1,0 for Urdu and Arabic and 0,1,2,3,4,5,6
    for the other eight, which is exactly the fault and exactly where it is not.
    """
    want = badge_of(Image.open(older / f"step-{step}.png"))
    best, score = None, None
    for other in STEPS:
        candidate = older / f"step-{other}{tail}.png"
        if not candidate.is_file():
            continue
        apart = float(np.abs(badge_of(Image.open(candidate)) - want).mean())
        if score is None or apart < score:
            best, score = candidate, apart
    if best is None:
        raise SystemExit(f"no older tile for {step}{tail} in {older}")
    return best


def his_drawing_their_lettering(column: Image.Image, older: Path):
    """Harry's new coloured drawing, under the frame, badge and label of the older tile.

    The two are on the same grid -- his 2.44 columns come out 284x1026 against the 285x1027 of
    the sheets before them -- so the older one is simply scaled the pixel it is out, and the
    lettering lands where it was drawn.

    What comes back is the pair: the day picture with the lettering in ink, and the night one
    with the lettering turned over and THE DRAWING UNTOUCHED, which is the whole of what Harry
    asked for.
    """
    fresh = np.asarray(column).astype(np.int16)
    paper = paper_in(fresh, reach="inside")
    drawing = coloured_shapes(fresh, paper)

    with Image.open(older) as opened:
        before = opened.convert("RGBA")
        if before.size != column.size:
            before = before.resize(column.size, Image.LANCZOS)
        letters = lettering_in(before)
        older_pixels = np.asarray(before).astype(np.int16)[:, :, :3]

    # The drawing wins where the two overlap: the old frame is at the edges and the old
    # lettering is above the picture, so they meet only where the old tile's own drawing used
    # to be -- and that is exactly what is being replaced.
    letters = letters & ~drawing
    shown = np.where(drawing[:, :, None], fresh, 255)
    shown = np.where(letters[:, :, None], older_pixels, shown)
    clear = np.where(drawing | letters, 255, 0).astype(np.uint8)

    day = np.dstack([np.clip(shown, 0, 255).astype(np.uint8), clear])
    night_ink = np.where(letters[:, :, None], 255 - older_pixels, shown)
    night = np.dstack([np.clip(night_ink, 0, 255).astype(np.uint8), clear])
    return (Image.fromarray(day, "RGBA"), Image.fromarray(night, "RGBA"),
            float(drawing.mean()), float(letters.mean()))


def install_steps(source: Path, out: Path, lettering: Path | None) -> int:
    total = 0
    for lang in LANGUAGES:
        found = sorted(source.glob(f"*_{lang}.png"))
        if not found:
            print(f"  !! no sheet for {lang} in {source}", file=sys.stderr)
            return 1
        tail = "" if lang == "en" else f".{lang}"
        line, swapped = [], []
        columns = in_step_order(cut_sheet(found[0]), lang, found[0].name)
        for step, column in zip(STEPS, columns):
            if lettering is None:
                day, night, _paper, drawing = keep_the_paper_out(column, reach="inside")
            else:
                older = lettering_for(step, lettering, tail)
                if older.stem != f"step-{step}{tail}":
                    swapped.append(f"{step}<-{older.stem.split('.')[0][5:]}")
                day, night, drawing, _letters = his_drawing_their_lettering(column, older)
            for picture, name in ((day, f"step-{step}{tail}.png"),
                                  (night, f"step-{step}{tail}-dark.png")):
                thinner(picture).save(out / name, optimize=True)
                total += (out / name).stat().st_size
            line.append(f"{100 * drawing:.0f}%")
        way = "right to left" if reads_right_to_left(lang) else "left to right"
        note = f"   lettering taken from {' '.join(swapped)}" if swapped else ""
        print(f"  {found[0].name:28s} -> seven and seven, read {way}   "
              f"drawing {' '.join(line)}{note}")
    print(f"  seventy pictures and their night versions: {total // 1024} KB")
    return 0


# ------------------------------------------------------------------------------- the map

def measure_map(new: Path, old: Path) -> int:
    """How far this map has moved from the one the city pins were measured against.

    qibla_quest.py: "A REDRAWN MAP INVALIDATES EVERY POINT HERE. There is nothing in the app
    that can notice, because a fraction is a valid fraction wherever it lands." So it is
    noticed here instead, before the file is written.
    """
    was = Image.open(old).convert("RGBA")
    now = Image.open(new).convert("RGBA").resize(was.size, Image.LANCZOS)

    def land(im):
        """Where the continents are. Paper is paper whether it is white or transparent: this
        tool's own output has the paper cut away, so a comparison that read a see-through
        pixel's leftover colour as land would answer differently on a second run."""
        pixels = np.asarray(im).astype(np.int16)
        return (pixels[:, :, :3].min(2) < 235) & (pixels[:, :, 3] >= 128)

    if np.asarray(was)[:, :, 3].min() < 128:
        print("  the map already in the repo has had its paper cut away, so it is this tool's\n"
              "  own output and there is nothing to compare against. Measure against the map\n"
              "  the city pins were taken from -- the one in the last published release.")
        return 0
    a, b = land(was), land(now)
    shared = (a & b).sum() / max(1, (a | b).sum())
    print(f"  the old map and the new one share {100 * shared:.1f}% of their land")
    for name, mask in (("old", a), ("new", b)):
        ys, xs = np.where(mask)
        print(f"    {name}: centre ({xs.mean() / mask.shape[1]:.4f}, {ys.mean() / mask.shape[0]:.4f})"
              f"   land {100 * mask.mean():.1f}%   x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}")
    sys.path.insert(0, str(HERE))
    from salaah.qibla_quest import ROUNDS             # noqa: E402  (after the path is set)
    # Measured under the pin the game actually draws -- a filled disc of px(16) on a 1920-wide
    # screen -- rather than a fixed little square, which answers differently on two maps drawn
    # at different sizes. On a first pass it had Jakarta at 4% of a square on one map and 0% on
    # the other, and read as the island having moved; both are a sixth of the drawn pin.
    radius = max(4, round(16 * was.size[0] / 1920))
    down, across = np.ogrid[:b.shape[0], :b.shape[1]]
    worst = 1.0
    for round_ in ROUNDS:
        fx, fy = round_.point
        x, y = int(fx * b.shape[1]), int(fy * b.shape[0])
        pin = (across - x) ** 2 + (down - y) ** 2 <= radius * radius
        here, before = float(b[pin].mean()), float(a[pin].mean())
        worst = min(worst, here)
        print(f"    {round_.city:10s} at ({x:4d},{y:4d})   {100 * here:3.0f}% of the pin on "
              f"land, against {100 * before:3.0f}% on the map it was measured against")
    if shared < 0.90 or worst == 0:
        print("  !! this is a different projection. Every point in qibla_quest.py must be "
              "measured again -- see the note at the top of that file.", file=sys.stderr)
        return 1
    return 0


def install_map(new: Path, out: Path) -> int:
    if measure_map(new, out):
        return 1
    day, _night, paper, drawing = keep_the_paper_out(Image.open(new).convert("RGB"), reach="water")
    was = out.stat().st_size if out.is_file() else 0
    thinner(day).save(out, optimize=True)
    print(f"  {new.name} -> {out.name}   {was // 1024} KB -> {out.stat().st_size // 1024} KB"
          f"   paper {100 * paper:.1f}%   drawing {100 * drawing:.1f}%")
    return 0


# ------------------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(prog="install_colour")
    ap.add_argument("films", type=Path, help="the folder of eight animations")
    ap.add_argument("sheets", type=Path, help="the folder of ten step sheets")
    ap.add_argument("map", type=Path, help="the new world map")
    ap.add_argument("--measure", action="store_true",
                    help="only measure the map against the one in the repo; write nothing")
    ap.add_argument("--lettering", type=Path, default=None,
                    help="a folder of older step pictures to take the frame, badge and label "
                         "from, keeping only the drawings from the new sheets")
    args = ap.parse_args()
    if args.measure:
        return measure_map(args.map, CHILDREN / "qibla-quest.png")
    WUDU.mkdir(parents=True, exist_ok=True)
    print("the films")
    if install_films(args.films, WUDU):
        return 1
    print("\nthe steps")
    if install_steps(args.sheets, WUDU, args.lettering):
        return 1
    print("\nthe map")
    if install_map(args.map, CHILDREN / "qibla-quest.png"):
        return 1
    print(f"\n-> {WUDU.relative_to(HERE)} and {CHILDREN.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
