"""Prepares the mosque picture used as the main screen.

Finds the five arches and the dome in the drawing, and writes:

  assets/mosque/mosque.png        the picture itself, trimmed to the building with a little sky
                                  above it, and with that sky made see-through so the sun or moon
                                  can be drawn behind it
  assets/mosque/arch-<prayer>.png a mask of each arch's inside, used to light it up
  assets/mosque/mosque.json       where each arch and the clock area sit in the picture

The arches are the light panels along the bottom, in order from the left: Fajr, Dhuhr, Asr,
Maghrib, Isha. The clock area is the widest part of the dome, where the time is written in white.

Run: python3 tools/build_mosque.py path/to/Main_Screen.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "mosque"

PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]
PANEL_LIGHT = 200                   # the arch panels are light, whether white or grey
DARK = 80                           # the mosque itself
CLOCK_INSET = 0.10                  # keep the time clear of the dome's curved edge
SKY_ABOVE = 0.06                    # sliver of sky kept over the dome, as a share of the height


def find_arches(grey: np.ndarray) -> list[tuple[int, int, int, int]]:
    """The five panels along the bottom: light areas enclosed by the building, so the sky around
    it is ignored however light or dark the drawing makes it."""
    light = grey > PANEL_LIGHT
    labels, count = ndimage.label(light)
    outside = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    outside.discard(0)
    inside = [i for i in range(1, count + 1) if i not in outside]
    if not inside:
        raise SystemExit("no arch panels found")
    sizes = ndimage.sum(light, labels, inside)
    biggest = [inside[k] - 1 for k in np.argsort(sizes)[::-1][:len(PRAYERS)]]
    boxes = []
    for index in biggest:
        ys, xs = np.where(labels == index + 1)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    if len(boxes) != len(PRAYERS):
        raise SystemExit(f"found {len(boxes)} arches, expected {len(PRAYERS)}")
    return sorted(boxes), labels, np.array(biggest)


def find_clock(grey: np.ndarray) -> tuple[int, int, int, int]:
    """The largest rectangle that fits inside the dome, where the time is written.

    Measured rather than guessed, so the box stays inside the curve however the dome is drawn.
    Wide-ish shapes are preferred, because a clock reads as one line.
    """
    dark = grey < DARK
    height, width = grey.shape
    centre = width // 2

    runs: dict[int, tuple[int, int]] = {}
    for y in range(int(height * 0.05), int(height * 0.72)):
        if not dark[y, centre]:
            continue
        left = centre
        while left > 0 and dark[y, left - 1]:
            left -= 1
        right = centre
        while right < width - 1 and dark[y, right + 1]:
            right += 1
        # Below the dome the run opens out into the roof, which spans the whole building.
        if right - left > width * 0.45:
            continue
        runs[y] = (left, right + 1)
    if not runs:
        raise SystemExit("no dome found for the clock")

    rows = sorted(runs)
    best, best_score = None, 0.0
    for i, top in enumerate(rows):
        left, right = runs[top]
        for bottom in rows[i + 1:]:
            if bottom != rows[i] + (bottom - top):   # only unbroken stretches of dome
                pass
            left = max(left, runs[bottom][0])
            right = min(right, runs[bottom][1])
            box_width, box_height = right - left, bottom - top
            if box_width <= 0:
                break
            if box_height <= 0:
                continue
            if box_width < box_height * 1.6:         # a clock wants a wide box, not a tall one
                continue
            score = box_width * box_height
            if score > best_score:
                best, best_score = (left, top, right, bottom), score
    if best is None:
        raise SystemExit("no room in the dome for the clock")

    left, top, right, bottom = best
    inset_x = int((right - left) * CLOCK_INSET)
    inset_y = int((bottom - top) * CLOCK_INSET)
    return left + inset_x, top + inset_y, right - inset_x, bottom - inset_y


def find_minarets(grey: np.ndarray) -> dict[str, list[int]]:
    """The two towers either side. Their tops light up when no prayer is due."""
    dark = grey < DARK
    top = dark.copy()
    top[int(grey.shape[0] * 0.45):, :] = False     # above the roof, where they stand apart
    labels, count = ndimage.label(top)
    sizes = ndimage.sum(top, labels, range(1, count + 1))
    towers = {}
    for index in np.argsort(sizes)[::-1][:6]:
        ys, xs = np.where(labels == index + 1)
        middle = xs.mean() / grey.shape[1]
        side = "left" if middle < 0.25 else ("right" if middle > 0.75 else None)
        if side is None or side in towers:
            continue
        # just the bulb on top, which is what gets lit
        height = ys.max() - ys.min()
        bulb = ys.min() + int(height * 0.38)
        keep = ys <= bulb
        towers[side] = [int(xs[keep].min()), int(ys.min()), int(xs[keep].max()) + 1, int(bulb)]
    if len(towers) != 2:
        raise SystemExit(f"found {len(towers)} minarets, expected 2")
    return towers


def make_sky_clear(picture: Image.Image) -> Image.Image:
    """Makes the white around the building see-through, leaving the white inside it alone."""
    grey = np.array(picture.convert("L"))
    white = grey > 235
    labels, _ = ndimage.label(white)
    edges = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    edges.discard(0)
    background = np.isin(labels, list(edges))
    out = picture.convert("RGBA")
    alpha = np.array(out.getchannel("A"))
    alpha[background] = 0
    out.putalpha(Image.fromarray(alpha))
    return out


def build(source: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    picture = Image.open(source).convert("RGB")
    grey = np.array(picture).mean(axis=2)

    boxes, labels, indexes = find_arches(grey)
    # Match each box back to its labelled region, so the mask is the arch shape, not a rectangle.
    lookup = {}
    for index in indexes:
        ys, xs = np.where(labels == index + 1)
        lookup[(int(xs.min()), int(ys.min()))] = index + 1

    arches = {}
    for prayer, box in zip(PRAYERS, boxes):
        label = lookup[(box[0], box[1])]
        inside = (labels[box[1]:box[3], box[0]:box[2]] == label)
        mask = Image.fromarray(np.where(inside, 255, 0).astype("uint8"), mode="L")
        mask.save(OUT / f"arch-{prayer}.png", optimize=True)
        arches[prayer] = {"box": list(box)}
        print(f"{prayer:8} arch at x {box[0]}-{box[2]}, y {box[1]}-{box[3]}")

    clock = find_clock(grey)
    print(f"clock area x {clock[0]}-{clock[2]}, y {clock[1]}-{clock[3]}")

    minarets = find_minarets(grey)
    for side, box in minarets.items():
        print(f"{side:8} minaret top x {box[0]}-{box[2]}, y {box[1]}-{box[3]}")

    clear = make_sky_clear(picture)

    # Trim the empty sky so the dome sits near the top of the screen, keeping a sliver above it
    # for the sun and moon to cross.
    solid = np.array(clear.getchannel("A")) > 0
    ys, xs = np.where(solid)
    margin = int((ys.max() - ys.min()) * SKY_ABOVE)
    box = (max(0, int(xs.min()) - 2), max(0, int(ys.min()) - margin),
           min(clear.width, int(xs.max()) + 3), min(clear.height, int(ys.max()) + 3))
    clear = clear.crop(box)
    print(f"trimmed to {clear.width}x{clear.height} (was {picture.width}x{picture.height})")

    def moved(values: list[int]) -> list[int]:
        return [values[0] - box[0], values[1] - box[1], values[2] - box[0], values[3] - box[1]]

    clear.save(OUT / "mosque.png", optimize=True)
    (OUT / "mosque.json").write_text(json.dumps({
        "schema": 1,
        "image": "mosque.png",
        "size": list(clear.size),
        "arches": {prayer: {"box": moved(arch["box"])} for prayer, arch in arches.items()},
        "clock": {"box": moved(list(clock))},
        "minarets": {side: moved(values) for side, values in minarets.items()},
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
