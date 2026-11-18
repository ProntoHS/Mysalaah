#!/usr/bin/env python3
"""Puts Harry's coloured mosques in beside the black-and-white ones, for the colour theme.

    python3 tools/mosque/install_colour.py <the five-arch drawing> <the folder of variants>

Harry, 18 November 2026: "colour theme will sit on black", "have mat write the five prayer
names into empty arches".

NOTHING IS REPLACED. The light and dark mats go on using exactly the drawings they use today;
these are written alongside as `mosque-colour.png`, and each mosque.json gains a `colour`
block that says what changes when the colour theme is on. A mat that never selects colour
cannot tell this release happened.

WHAT THE COLOUR BLOCK CHANGES, and why each of them:

    "image"       the coloured drawing.
    "images": {}  empties the per-language map, so drawing_for falls back to the one picture.
                  THIS IS THE POINT OF THE EXERCISE: the painted mosques carry the five prayer
                  names in the artwork, which is why there are ten of them. Harry's coloured
                  one has empty arches, the app writes the names in from the pack, and one
                  picture serves all ten languages.
    "names"       dropped, so own_names is false and the app writes rather than the drawing
                  carrying. That path is not new -- it is what the mat did between 1.63 and
                  1.83 and what every archway page does today for "2 Sunnah".
    "text"        where the written name sits in an arch: the band the PAINTED names occupied,
                  so the words land where Harry drew them rather than in the default label
                  band two-tenths of an arch lower.

What it does NOT change is the arch boxes, the clock box or the minarets, because the coloured
drawings are the same composition -- checked rather than assumed, and the overlay is in
tools/ARTWORK-MEASURED.md.

The five-arch drawing arrives at 1672x941 and is written at 1920x1080, because the boxes in
mosque.json are in the picture's own pixels.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent.parent.parent
SIZE = (1920, 1080)

#: Which variant each prayer page wants, by how many archways it has.
BY_ARCHES = {2: "2", 3: "3", 4: "4", 6: "6"}

#: Where a written name sits in an arch, top and bottom as a fraction of the arch. Taken from
#: the band the painted names occupy on the drawings that carry their own, so the app's words
#: land where Harry's did.
NAME_BAND = [0.518, 0.842]


#: Sixteen million colours down to 256, as the jigsaws and the prayer-day skies were at 2.43
#: and the wu'du at 2.44. These are flat cartoon artwork with 183,000 distinct colours in them,
#: almost all of which are the antialiasing along an edge: at 256 the mean error is ONE level
#: out of 255 and the file is 362 KB where the whole thing is 1,327. Six of them, so the colour
#: theme costs the release 2.2 MB rather than 8.1.
COLOURS = 256
#: How dark a pixel has to be to count as the night behind the mosque.
NIGHT = 40


def cut_the_sky(picture: Image.Image) -> Image.Image:
    """Take the night out from behind the mosque and let the page show through it.

    HARRY'S COLOURED MOSQUES ARE PAINTED ON SOLID BLACK, and the mat paints its own sky --
    stars, and a sun or a moon moving along an arc so a glance tells you roughly what time of
    day it is -- UNDERNEATH the drawing. The black-and-white mosques have their sky cut away,
    so it shows through; a solid one hides the lot. Rendered, the colour mat had no stars, no
    moon, and was drawing both every frame for nothing.

    So the same cut the wu'du paper got at 2.44, the other way up: black that the edge of the
    picture can reach, which is the sky and, through the sides, the openings of the arches
    themselves. Everything enclosed by the building is left alone -- the largest such piece
    here is 834 pixels, a slit in a minaret.
    """
    import numpy as np
    from scipy.ndimage import binary_dilation, label
    from skimage.morphology import disk, remove_small_holes

    pixels = np.asarray(picture.convert("RGB")).astype(np.int16)
    night = pixels.max(2) <= NIGHT
    patch, _ = label(night)
    edges = set(patch[0, :]) | set(patch[-1, :]) | set(patch[:, 0]) | set(patch[:, -1])
    edges.discard(0)
    sky = remove_small_holes(np.isin(patch, list(edges)), 16)
    sky = binary_dilation(sky, disk(1))
    clear = np.where(sky, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([pixels.astype(np.uint8), clear]), "RGBA")


def fitted(path: Path) -> Image.Image:
    picture = Image.open(path).convert("RGB")
    if picture.size != SIZE:
        picture = picture.resize(SIZE, Image.LANCZOS)
    # FASTOCTREE because it is the one of Pillow's quantisers that keeps an alpha channel, and
    # the alpha here is the sky.
    return cut_the_sky(picture).quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE,
                                         dither=Image.Dither.NONE)


def add_colour_block(folder: Path, block: dict) -> None:
    """Add or replace the `colour` block in a mosque.json, leaving the rest of the file's own
    formatting alone -- these are hand-kept files and a reserialise churns every line."""
    path = folder / "mosque.json"
    described = json.loads(path.read_text(encoding="utf-8"))
    described["colour"] = block
    path.write_text(json.dumps(described, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(main_drawing: str, variants: str) -> int:
    variants = Path(variants)
    found = {}
    for picture in sorted(variants.glob("*archways*.png")):
        for count in BY_ARCHES.values():
            if f"_{count}_arch" in picture.name:
                found[count] = picture
    missing = set(BY_ARCHES.values()) - set(found)
    if missing:
        print(f"  !! no drawing for {sorted(missing)} archways in {variants}", file=sys.stderr)
        return 1

    home = HERE / "assets" / "mosque"
    fitted(Path(main_drawing)).save(home / "mosque-colour.png", optimize=True)
    # "names": anything but "drawn". own_names is `described.get("names") == "drawn"`, so the
    # colour block has to say something else rather than leave the key out -- the block is
    # merged OVER the description, and a key it does not mention keeps the painted answer.
    # Found by rendering it and seeing the names still painted on. "app" says what it is.
    add_colour_block(home, {"image": "mosque-colour.png", "images": {}, "drawn": "dark",
                            "names": "app", "text": {"label": NAME_BAND},
                            "clock": {"ink": "light"}})
    print(f"  the five-arch mosque -> {(home / 'mosque-colour.png').relative_to(HERE)}"
          f"   {(home / 'mosque-colour.png').stat().st_size // 1024} KB, names written by the app")

    for prayer in sorted((HERE / "assets" / "prayers").iterdir()):
        if not prayer.is_dir():
            continue
        described = json.loads((prayer / "mosque.json").read_text(encoding="utf-8"))
        arches = len(described["arches"])
        if arches not in BY_ARCHES:
            print(f"  !! {prayer.name} has {arches} archways and there is no drawing with "
                  f"that many", file=sys.stderr)
            return 1
        fitted(found[BY_ARCHES[arches]]).save(prayer / "mosque-colour.png", optimize=True)
        add_colour_block(prayer, {"image": "mosque-colour.png", "drawn": "dark",
                                  "clock": {"ink": "light"}})
        print(f"  {prayer.name:9s} {arches} archways -> {found[BY_ARCHES[arches]].name}"
              f"   {(prayer / 'mosque-colour.png').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
