#!/usr/bin/env python3
"""Rebuilds the opening logo animation's pieces from the original Logo.gif.

    python3 tools/build_splash.py path/to/Logo.gif

The GIF is 1800x1020, dithered, and squashed about 10% wide (its circle is 447 by 407). This
takes the pieces out of it — the boy on his mat, the pressed and the open hands, "My", "Saalah",
"www." and ".com" — and for each one:

  * enlarges it four times, softens the dither grain away and cuts it back to clean black and
    white, so edges are smooth curves rather than stair steps;
  * takes the squash out, so the circle is round again;
  * saves it as a transparent PNG at twice the size a 1080p screen needs.

The circle itself is not taken from the GIF at all: the app draws it, perfectly round, so it can
be drawn on stroke by stroke. Positions go to assets/splash/splash.json in "design units": the
GIF's own pixel rows, with x measured from the middle of the circle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence
from scipy import ndimage as nd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "splash"

DESIGN_HEIGHT = 1020          # the GIF's height; everything is placed in these units
UNSQUASH = 407 / 447          # the circle's height over its width: how much to narrow by
UP = 4                        # work at four times the GIF's size while cleaning
LAYER_SCALE = 2160 / DESIGN_HEIGHT   # saved at twice a 1080p screen's needs


def frames(gif: Path) -> list[np.ndarray]:
    """Every frame as grey, 0 black to 1 white."""
    im = Image.open(gif)
    return [np.asarray(f.convert("L"), dtype=np.float32) / 255 for f in ImageSequence.Iterator(im)]


def find_circle(grey: np.ndarray) -> tuple[float, float, float, float]:
    """The black disc: centre x, centre y, half width, half height."""
    labels, _ = nd.label(grey < 0.5)
    sizes = nd.sum(np.ones_like(grey), labels, index=range(1, labels.max() + 1))
    biggest = int(np.argmax(sizes)) + 1
    ys, xs = np.nonzero(labels == biggest)
    return ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2,
            (xs.max() - xs.min() + 1) / 2, (ys.max() - ys.min() + 1) / 2)


def cleaned(values: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """[values] is how much of the piece each pixel is (0 none, 1 all). Returns coverage at
    four times the size, as clean hard edges: enlarged, softened, cut at half."""
    h, w = values.shape
    big = Image.fromarray((values * 255).astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS)
    big = np.asarray(big, dtype=np.float32) / 255
    big = nd.gaussian_filter(big, sigma=UP * 0.55)
    solid = big > 0.5
    mask = np.asarray(Image.fromarray(keep.astype(np.uint8) * 255).resize((w * UP, h * UP), Image.NEAREST)) > 0
    solid &= mask
    # dither grain that survived: drop specks smaller than a few source pixels
    labels, n = nd.label(solid)
    if n:
        sizes = nd.sum(solid, labels, index=range(1, n + 1))
        small = np.isin(labels, np.nonzero(sizes < UP * UP * 4)[0] + 1)
        solid &= ~small
    return solid


HAND_DETAIL = 90   # source pixels: black flecks inside the hands smaller than this are dither


def without_grain(solid: np.ndarray, smallest: int) -> np.ndarray:
    """The GIF's hands have their creases drawn in dither, which comes out as broken dashes.
    Fill in the small enclosed flecks and keep the big gaps, like those between the fingers,
    so the hands read as clean shapes like the ones in logo.png."""
    holes = nd.binary_fill_holes(solid) & ~solid
    labels, n = nd.label(holes)
    if not n:
        return solid
    sizes = nd.sum(holes, labels, index=range(1, n + 1))
    small = np.isin(labels, np.nonzero(sizes < smallest * UP * UP)[0] + 1)
    solid = solid | small
    # The outline is dithered too, so it comes out ragged. Soften the shape and cut it again:
    # bumps and notches under a couple of source pixels go, the fingers and their gaps stay.
    smooth = nd.gaussian_filter(solid.astype(np.float32), sigma=UP * 1.1)
    return smooth > 0.5


def extend_right(solid: np.ndarray, by: int) -> np.ndarray:
    """The h of "Saalah" runs off the edge of the GIF. Carry its tail on a little along the
    same baseline and finish it the way the script's other strokes end: flat underneath, the
    top sloping down to a point."""
    last = np.nonzero(solid[:, -1])[0]
    if last.size == 0:
        return solid
    top, bottom = last.min(), last.max()
    grown = np.zeros((solid.shape[0], solid.shape[1] + by), dtype=bool)
    grown[:, :solid.shape[1]] = solid
    for k in range(by):
        left = (1 - (k + 1) / (by + 1)) ** 0.7
        lo = int(round(bottom - (bottom - top) * left))
        grown[lo:bottom + 1, solid.shape[1] + k] = True
    return grown


def save_layer(name: str, solid: np.ndarray, colour: tuple[int, int, int], x0: int, y0: int,
               circle_x: float, placed: dict) -> None:
    """Shrinks the clean shape to its saved size (the shrinking gives the soft edge), takes
    the squash out, and records where it goes."""
    h, w = solid.shape
    out_w = max(1, round(w / UP * UNSQUASH * LAYER_SCALE))
    out_h = max(1, round(h / UP * LAYER_SCALE))
    alpha = Image.fromarray(solid.astype(np.uint8) * 255).resize((out_w, out_h), Image.BOX)
    rgba = Image.new("RGBA", (out_w, out_h), colour + (0,))
    rgba.putalpha(alpha)
    rgba.save(OUT / f"{name}.png", optimize=True)
    placed[name] = {
        "file": f"{name}.png",
        "x": round((x0 - circle_x) * UNSQUASH, 2),      # design units, from the circle's middle
        "y": round(float(y0), 2),
        "w": round(w / UP * UNSQUASH, 2),
        "h": round(h / UP, 2),
    }
    print(f"  {name:14s} {out_w}x{out_h}")


def main(gif: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    f = frames(gif)
    if len(f) < 14:
        raise SystemExit(f"{gif.name}: expected the 18-frame logo animation, found {len(f)} frames")
    boy_only, pressed, opened, full = f[0], f[3], f[4], f[13]

    cx, cy, rx, ry = find_circle(full)
    print(f"circle at ({cx:.0f}, {cy:.0f}), {2 * rx:.0f} by {2 * ry:.0f}")
    placed: dict = {}

    # Pieces of ink in the finished frame, sorted by where they sit.
    ink = full < 0.5
    labels, n = nd.label(ink)
    boxes = nd.find_objects(labels)
    groups: dict[str, list[int]] = {"my": [], "saalah": [], "www": [], "com": []}
    for i, box in enumerate(boxes, 1):
        ys, xs = box
        mx, my = (xs.start + xs.stop) / 2, (ys.start + ys.stop) / 2
        if 590 <= my <= 800 and mx < cx - 140 and mx > 380:
            groups["my"].append(i)
        elif 590 <= my <= 760 and mx > cx + 110:
            groups["saalah"].append(i)
        elif 690 <= my <= 770 and mx < 385:
            groups["www"].append(i)
        elif 770 < my <= 840 and mx > cx + 700:
            groups["com"].append(i)

    for name, ids in groups.items():
        if not ids:
            raise SystemExit(f"could not find '{name}' in the logo")
        mask = nd.binary_dilation(np.isin(labels, ids), iterations=2)
        ys, xs = np.nonzero(mask)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        values = np.where(mask, 1 - full, 0)[y0:y1, x0:x1]
        solid = cleaned(values, mask[y0:y1, x0:x1])
        if name == "saalah" and x1 >= full.shape[1]:
            solid = extend_right(solid, by=UP * 11)
        save_layer(name, solid, (0, 0, 0), x0, y0, cx, placed)

    # The boy on his mat, from the first frame where he is on his own.
    boy_ink = boy_only < 0.5
    ys, xs = np.nonzero(boy_ink)
    y0, y1, x0, x1 = ys.min() - 3, ys.max() + 4, xs.min() - 3, xs.max() + 4
    region = np.zeros_like(boy_ink)
    region[y0:y1, x0:x1] = True
    solid = cleaned(np.where(region, 1 - boy_only, 0)[y0:y1, x0:x1], region[y0:y1, x0:x1])
    save_layer("boy", solid, (0, 0, 0), x0, y0, cx, placed)

    # The hands: the white inside the disc, pressed together and then open in dua.
    yy, xx = np.mgrid[0:full.shape[0], 0:full.shape[1]]
    inside = ((xx - cx) / (rx - 4)) ** 2 + ((yy - cy) / (ry - 4)) ** 2 <= 1
    ys, xs = np.nonzero(inside)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    for name, frame in (("hands_pressed", pressed), ("hands_open", opened)):
        values = np.where(inside, frame, 0)[y0:y1, x0:x1]
        solid = cleaned(values, inside[y0:y1, x0:x1])
        solid = without_grain(solid, HAND_DETAIL)
        save_layer(name, solid, (255, 255, 255), x0, y0, cx, placed)

    description = {
        "schema": 1,
        "source": gif.name,
        "note": "Built by tools/build_splash.py. Units: the original GIF's pixel rows, "
                "x from the middle of the circle, with the GIF's 10% squash taken out.",
        "design_height": DESIGN_HEIGHT,
        "circle": {"x": 0.0, "y": round(float(cy), 2), "r": round(float(ry), 2)},
        "layers": placed,
    }
    (OUT / "splash.json").write_text(json.dumps(description, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'splash.json'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
