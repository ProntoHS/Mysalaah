"""Builds the sub-menu arch's two masks from one clean drawing of the arch.

The arches on the unit screen ("2 Sunnah", "4 Fardh") are drawn rather than pictured, so a
prayer can have as many as it has units. They are drawn from two grayscale masks:

    arch-outer.png   the whole arch, painted in the border colour
    arch-inner.png   the panel inside it, painted on top in the panel colour

The gap between the two is what you see as the outline. This tool makes both from a single
silhouette of the arch, so the outline comes out an even width all the way round instead of
following whatever the drawing's own line did.

Give it a drawing of the arch as a solid shape - any colour, on a transparent or white
background - at the largest size you have. It is the shape that matters, not the colours:

    python3 tools/build_arch.py path/to/arch.png

    python3 tools/build_arch.py path/to/arch.png --border 0.036 --height 1400

The base is left open on purpose: the arch stands on the ground like the ones on the mosque,
rather than being closed along the bottom like a shield.

Needs Pillow, NumPy and SciPy:  pip3 install --break-system-packages pillow numpy scipy
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BORDER = 0.036      # the outline's width, as a fraction of the arch's own width
HEIGHT = 1400       # what the masks are saved at: enough to stay sharp when drawn large
HERE = Path(__file__).resolve().parent.parent / "assets" / "mosque"


def shape_of(path: Path):
    """The drawing as a true/false mask of what is inside the arch.

    A drawing with transparency is taken by its alpha. One on a white background is taken by
    what is darker than white, so a plain black-on-white drawing works too.
    """
    import numpy as np
    from PIL import Image

    picture = Image.open(path).convert("RGBA")
    alpha = np.array(picture.split()[3])
    if alpha.min() < 250:                       # it has transparency: that is the shape
        return alpha > 128
    grey = np.array(picture.convert("L"))       # otherwise: anything that is not white
    return grey < 240


def trim(mask):
    """Cuts the blank space off, so the arch fills its own picture."""
    import numpy as np

    rows, cols = np.where(mask)
    if not rows.size:
        raise SystemExit("that drawing is empty")
    return mask[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def eaten_in(mask, border: int):
    """The panel inside the arch: the shape with [border] pixels taken off every edge but the
    base, measured as a true distance so the outline is the same width on a curve as on a
    straight.

    The arch fills its picture, so its sides sit hard against the edge. Distance is only
    measured to the empty pixels the picture actually holds, so without a margin of empty space
    around it the sides would count as deep inside and get no outline at all. Hence the ring of
    empty pixels on the two sides and the top. The base instead stands on a block of itself, so
    nothing is eaten off the bottom and the arch stands open on the ground.
    """
    import numpy as np
    from scipy import ndimage

    room = border + 2
    height, width = mask.shape
    tall = np.vstack([np.zeros((room, width), bool), mask, np.repeat(mask[-1:], room, axis=0)])
    edge = np.zeros((tall.shape[0], room), bool)
    padded = np.hstack([edge, tall, edge])
    inside = ndimage.distance_transform_edt(padded) > border
    return inside[room:room + height, room:room + width]


def as_picture(mask, height: int):
    """A mask at the size it is saved, its edges smoothed by the shrinking itself."""
    from PIL import Image

    picture = Image.fromarray((mask * 255).astype("uint8"), mode="L")
    width = max(1, round(picture.width * height / picture.height))
    return picture.resize((width, height), Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("drawing", type=Path, help="a picture of the arch as a solid shape")
    ap.add_argument("--out", type=Path, default=HERE, help="where the masks go")
    ap.add_argument("--border", type=float, default=BORDER,
                    help=f"outline width as a fraction of the arch's width (default {BORDER})")
    ap.add_argument("--height", type=int, default=HEIGHT,
                    help=f"pixels tall to save the masks at (default {HEIGHT})")
    args = ap.parse_args(argv)

    if not args.drawing.is_file():
        print(f"no such file: {args.drawing}", file=sys.stderr)
        return 1
    shape = trim(shape_of(args.drawing))
    height, width = shape.shape
    border = max(1, round(width * args.border))
    print(f"arch {width} x {height}, outline {border}px ({args.border:.1%} of the width)")

    args.out.mkdir(parents=True, exist_ok=True)
    for name, mask in (("arch-outer.png", shape), ("arch-inner.png", eaten_in(shape, border))):
        picture = as_picture(mask, args.height)
        picture.save(args.out / name)
        print(f"  {name}  {picture.width} x {picture.height}")
    print(f"aspect {width / height:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
