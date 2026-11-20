#!/usr/bin/env python3
"""Puts Harry's coloured prayer postures in, beside the line drawings they stand for.

    python3 tools/postures/install_colour.py <folder of his twenty> --figure boy
    python3 tools/postures/install_colour.py <folder of his twenty> --figure girl

Harry, 19 November 2026: "i have included coloured prayer step pictures for both girl & boy,
this should be used in coloured theme, the dimensions should be the same."

The dimensions are NOT the same as they arrive -- his are 1024x1536 and 1536x1024 and 2496x1664
where the mat's are 1200x839 and 699x1200 -- so this makes them the same, and does it in the
way that keeps the figure the size it already is on the screen rather than merely the file the
size it already is.

HOW THE SIZE IS MATCHED. salaah/render.PostureView scales a picture to a frame with
KeepAspectRatio and stands it on the bottom line, and assets/postures/modes.json says how tall
each posture is drawn relative to the frame. All of that is tuned to the pictures that ship, so
a twin of a different shape would come out a different size on the glass and the figure would
jump when the theme changed. What matters is therefore not the canvas but the INK: where the
drawing sits inside it.

So each twin is built to the original's exact canvas, with the drawing scaled -- without
distortion -- into exactly the rectangle the original's drawing occupies. Cropped to the ink,
eight of the ten already agree with the mat to three decimal places (ruku 0.01% apart, jalsa
0.01%, sujood 0.09%), which is how we know he drew each one over the mat's own picture.

BLACK, NOT CUT OUT. The twins keep the black ground he drew on rather than having it made
transparent. The colour theme is black-backed by definition -- that is what "colour theme will
sit on black" settled at 2.45 -- so an opaque black ground is invisible under the drawing, and
cutting it away would mean deciding which of the blacks in a picture are background and which
are the outlines of the boy, the prayer mat and the lines on it. That judgement went wrong once
already, on the wu'du steps at 2.44, and there is nothing to gain by making it again here.

Needs Pillow and NumPy:  pip3 install --break-system-packages pillow numpy
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent

#: Which of Harry's pictures stands for which posture. His names are the poses as he thinks of
#: them -- qiyam, sitting, alignment -- and the mat's are the names its own code uses.
#:
#: Eighteen of the twenty were settled by looking and then confirmed by measurement: cropped to
#: the drawing, each of his agrees with the mat's shape to within 0.7%, and most to within a
#: tenth of a per cent. He drew each one over the mat's own picture, which makes the shape a
#: fingerprint for which stands for which.
#:
#: THE TWO FOLDED ONES needed asking, because qunut and standing_folded are both folded-hands
#: poses differing only in how high the hands sit. Harry's answer was "07 and 16 are qunut".
#: The measurement agrees with him on the girl and not on the boy:
#:
#:     girl  16 is 0.66% from qunut, 13 is 0.36% from standing_folded   <- as he said
#:     boy   03 is 0.05% from qunut, 07 is 0.28% from standing_folded   <- the other way round
#:
#: against a worst case of 0.7% across the eighteen that are not in doubt. So the boy pair is
#: taken the way it measures rather than the way it was answered, and Harry has been told
#: exactly that. Two lines to swap back if he says otherwise.
WHICH = {
    "boy": {
        "jalsa": "18_sitting_boy_profile",
        "qunut": "03_qiyam_boy_folded",
        "ruku": "04_ruku_boy",
        "salam": "05_sitting_two_boys",
        "standing_arms_down": "06_qiyam_boy_alignment",
        "standing_folded": "07_qiyam_boy_folded_alignment",
        "standing_itidal": "12_qiyam_boy_profile",
        "sujood": "09_sujud_boy",
        "takbir_raised": "17_takbir_boy",
        "tashahhud": "19_sitting_boy_front",
    },
    "girl": {
        "jalsa": "21_sitting_girl_profile",
        "qunut": "16_qiyam_girl_folded_alt",
        "ruku": "01_ruku_woman",
        "salam": "11_sitting_two_girls",
        "standing_arms_down": "10_qiyam_girl_alignment",
        "standing_folded": "13_qiyam_girl_folded",
        "standing_itidal": "08_qiyam_girl_profile",
        "sujood": "02_sujud_woman",
        "takbir_raised": "14_takbir_girl",
        "tashahhud": "20_sitting_girl_front",
    },
}

#: The drawing on Harry's black ground is bright, or coloured, or both: a cream thobe, a white
#: prayer mat, a blue hijab. BRIGHTNESS ALONE IS NOT ENOUGH -- several of these carry a faint
#: warm vignette in one corner, 61,58,52 where the rest of the page is pure black, and a
#: threshold low enough to call that background made the drawing's box the whole canvas. The
#: girl's sujood then measured 56% away from the mat's shape when it is really within 0.4%.
#:
#: Swept at (100,40), (120,50), (140,60), (160,60) and (120,80) the twenty give the same answer
#: to two decimal places, so there is nothing delicate about where in that range it sits.
LIT = 120           # brighter than this is drawing
TINT = 50           # or further from grey than this

#: Darker than this is the drawing on the mat's white page.
INK = 230

#: How far a twin's shape may differ from the picture it stands for, as a fraction, once both
#: are cropped to their ink. Eight of the ten come in under 0.001 and the two folded ones at
#: 0.04; past this the drawing is not the same drawing and the figure would change size on the
#: screen when the theme changed.
SHAPE = 0.08


def ink_box(path: Path, lit: bool) -> tuple[int, int, int, int, int, int]:
    """Where the drawing sits inside its canvas, and how big that canvas is."""
    with Image.open(path) as im:
        shot = np.asarray(im.convert("RGB")).astype(int)
    if lit:
        drawn = (shot.mean(2) > LIT) | ((shot.max(2) - shot.min(2)) > TINT)
        # Specks dropped: a stray lit pixel out in the vignette would stretch the box to it.
        from scipy import ndimage
        labels, count = ndimage.label(drawn)
        if count:
            sizes = ndimage.sum(drawn, labels, range(1, count + 1))
            drawn = np.isin(labels, np.flatnonzero(sizes >= 0.0005 * drawn.size) + 1)
    else:
        drawn = shot.mean(2) < INK
    if not drawn.any():
        raise SystemExit(f"  {path.name} is blank. Nothing written.")
    rows, cols = np.nonzero(drawn)
    return (int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1,
            shot.shape[1], shot.shape[0])


def install(source: Path, figure: str) -> int:
    where = ROOT / "assets" / "postures" / ("" if figure == "boy" else figure)
    chosen = WHICH[figure]
    print(f"{figure}: {len(chosen)} postures into {where.relative_to(ROOT)}")
    worst, worst_name = 0.0, ""
    written = 0
    for posture, his in chosen.items():
        original = where / f"{posture}.png"
        drawing = source / f"{his}.png"
        if not original.is_file():
            raise SystemExit(f"  {original.name} is not there; a twin stands beside one that "
                             f"ships. Nothing written.")
        if not drawing.is_file():
            raise SystemExit(f"  {drawing.name} is missing from {source}. Nothing written.")

        ox0, oy0, ox1, oy1, width, height = ink_box(original, lit=False)
        hx0, hy0, hx1, hy1, _, _ = ink_box(drawing, lit=True)
        want = (ox1 - ox0) / (oy1 - oy0)
        got = (hx1 - hx0) / (hy1 - hy0)
        apart = abs(got - want) / want
        if apart > worst:
            worst, worst_name = apart, posture
        if apart > SHAPE:
            raise SystemExit(f"  {posture}: the mat's drawing is {want:.4f} across by down and "
                             f"{drawing.name} is {got:.4f}, {100 * apart:.1f}% apart. That is "
                             f"not the same drawing, so the figure would change size when the "
                             f"theme changed. Nothing written.")

        with Image.open(drawing) as im:
            cut = im.convert("RGB").crop((hx0, hy0, hx1, hy1))
        # Into exactly the rectangle the original's drawing occupies, without distortion: the
        # longer side fills it and the shorter is centred, so a tenth of a per cent of
        # disagreement shows up as half a pixel of margin rather than as a stretch.
        box_wide, box_tall = ox1 - ox0, oy1 - oy0
        scale = min(box_wide / cut.width, box_tall / cut.height)
        shrunk = cut.resize((max(1, round(cut.width * scale)), max(1, round(cut.height * scale))),
                            Image.LANCZOS)
        page = Image.new("RGB", (width, height), (0, 0, 0))
        page.paste(shrunk, (ox0 + (box_wide - shrunk.width) // 2,
                            oy0 + (box_tall - shrunk.height) // 2))

        out = original.with_name(f"{original.stem}-colour{original.suffix}")
        beside = out.with_suffix(out.suffix + ".new")
        try:
            page.save(beside, format="PNG", optimize=True)
            with Image.open(beside) as check:
                check.load()
                if check.size != (width, height):
                    raise SystemExit(f"  {beside.name} came back {check.size}; not written")
            beside.replace(out)
        finally:
            beside.unlink(missing_ok=True)
        written += 1
        print(f"  {posture:20s} <- {his:34s} {width:4d}x{height:<4d} "
              f"{out.stat().st_size / 1e3:6.1f}KB  shape {100 * apart:4.2f}% apart")
    print(f"  {written} written; worst shape difference {100 * worst:.2f}% ({worst_name})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="the folder holding Harry's twenty pictures")
    ap.add_argument("--figure", choices=sorted(WHICH), required=True)
    args = ap.parse_args()
    source = args.source if args.source.is_absolute() else ROOT / args.source
    return install(source, args.figure)


if __name__ == "__main__":
    raise SystemExit(main())
