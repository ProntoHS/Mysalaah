#!/usr/bin/env python3
"""Prepares the wu'du animations and cuts the steps off the drawing.

    python3 tools/build_wudu.py --gifs ~/Downloads/wudu_gifs --sheet ~/Downloads/wudu.png

Writes assets/wudu: a film per step, and a tile per step off the sheet.

The films arrive as 512x768, thirty frames, and weigh forty-six megabytes between them -- more
than the entire rest of the app, on a mat whose card has a few hundred megabytes spare. They are
line drawings: a boy, a basin, a tap, black outlines on white paper, nine grey levels in the
whole thing and most of the picture one of them.

So they are re-encoded, the same way the front door's animation was. Cut to four greys a film
goes from 5.2 MB to 0.08 MB -- sixty-five times smaller -- and keeps the antialiasing along
every curve, which is the only thing more than two greys is for. Two greys loses it and the
drawing comes out ragged; eight doubles the file for nothing anybody can see from a mat.

The size is left alone. 512x768 is what was drawn, and a line drawing stretched past its own
resolution only gets softer -- the panel it goes in is taller than that and will do the
stretching itself, once, at the moment it is drawn.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "wudu"

# The shades kept, named rather than chosen for us. Pillow's median cut picks its palette by
# how many pixels are each colour, and on these drawings that is the wrong question: the picture
# is nine tenths paper, so all four slots went on near-whites and the black lines came out grey.
# The drawing is black ink on white with a little antialiasing in between, so that is the palette
# it gets, written down.
GREYS = (0, 96, 176, 255)

# The seven steps as Harry drew them on the sheet, and which of the eight films belongs to each.
# Step six is two films, because wiping the head and wiping the ears were drawn as two pictures
# in one box and are one step of the wu'du.
STEPS = (
    ("hands",  ("01_wash_hands",)),
    ("mouth",  ("02_rinse_mouth",)),
    ("nose",   ("03_clean_nose",)),
    ("face",   ("04_wash_face",)),
    ("arms",   ("05_wash_arms_to_elbows",)),
    ("head",   ("06_wipe_head", "07_wipe_ears")),
    ("feet",   ("08_wash_feet_ankles",)),
)


def squeeze(source: Path, out: Path) -> tuple[int, int]:
    """Re-encode one film. Returns the size before and after, in bytes."""
    from PIL import Image, ImageSequence
    was = source.stat().st_size
    film = Image.open(source)
    shades = Image.new("P", (1, 1))
    shades.putpalette([v for grey in GREYS for v in (grey, grey, grey)] + [0] * (768 - 3 * len(GREYS)))
    keep = [frame.convert("L").convert("RGB").quantize(palette=shades, dither=Image.Dither.NONE)
            for frame in ImageSequence.Iterator(film)]
    if not keep:
        raise SystemExit(f"{source.name} has no frames in it")
    keep[0].save(out, save_all=True, append_images=keep[1:], loop=0,
                 duration=film.info.get("duration", 80), optimize=True, disposal=1)
    return was, out.stat().st_size


def build(gifs: Path, sheet: Path | None, out: Path = OUT) -> int:
    out.mkdir(parents=True, exist_ok=True)
    before = after = 0
    for step, films in STEPS:
        for n, name in enumerate(films):
            source = gifs / f"{name}.gif"
            if not source.is_file():
                raise SystemExit(f"missing {source}")
            # One film a step, except the head, which has two: head.gif and head-2.gif.
            stem = step if n == 0 else f"{step}-{n + 1}"
            was, now = squeeze(source, out / f"{stem}.gif")
            before, after = before + was, after + now
            print(f"  {stem:<8} {source.name:<28} {was / 1e6:>6.2f} MB -> {now / 1e6:.2f} MB")

    if sheet is not None:
        from build_tiles import build as cut_tiles     # the same cutter the menus use
        print()
        if cut_tiles(sheet, out, [f"step-{step}" for step, _ in STEPS]):
            raise SystemExit("the sheet did not cut into seven steps")

    print(f"\n{before / 1e6:.1f} MB of film becomes {after / 1e6:.2f} MB "
          f"({before / max(after, 1):.0f} times smaller)")
    print(f"-> {out.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_wudu")
    ap.add_argument("--gifs", type=Path, required=True, help="folder holding the eight films")
    ap.add_argument("--sheet", type=Path, help="the drawing of the seven steps")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return build(args.gifs, args.sheet, args.out)


if __name__ == "__main__":
    sys.exit(main())
