#!/usr/bin/env python3
"""Puts a redrawn film into a menu, in place of the one a language has now.

    python3 tools/swap_menu_film.py assets/duas-menu fr redrawn-french.gif

For the case build_menu_film.py does not cover: a menu that is already built, drawn again in
one language because something in it was wrong. Rebuilding the lot from sheets would be the
tool for that, and it is the wrong tool here -- the boxes in menu.json were found from the
ENGLISH sheet, every other language is checked against them, and re-cutting one language on
its own is how a set of films quietly stops lining up.

SO THIS CHECKS RATHER THAN CUTS. The new film has to be the menu's own size, the same number of
frames as the film it replaces, and its tiles have to land in the boxes menu.json already
holds. Any of those wrong and nothing is written: a film whose tiles have moved is a menu whose
buttons are over the wrong pictures, which on this mat means a child pressing Travel and getting
Forgiveness.

IT ALSO SAYS WHAT CHANGED, tile by tile, against the film being replaced. That is the part
worth having. Five films came in once described as a fix to one tile; this is how you find out
in one line whether that is what they are.

AND IT SQUEEZES. The films arrive at eight megabytes or so, because an exporter writes every
frame whole in a palette built for photographs. Re-written in the four greys these menus are
drawn in they are about a megabyte, which is the difference between a mat updating over
somebody's home Wi-Fi in a minute and in a quarter of an hour. See build_menu_film.py, where
the palette and the reason for writing it down rather than letting Pillow choose both live.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# How far a tile found in the new film may sit from the box menu.json already holds. Not zero:
# the cutter works off a threshold, and a line that is a shade lighter after a different
# exporter can move an edge by a pixel without moving the drawing at all.
SLACK = 3


def frames_of(path: Path):
    from PIL import Image, ImageSequence
    with Image.open(path) as film:
        kept, held = [], []
        for frame in ImageSequence.Iterator(film):
            kept.append(frame.convert("L"))
            held.append(frame.info.get("duration", 100))
    return kept, held


def boxes_in(frame, described: dict) -> dict:
    """The tiles the cutter finds in this frame, named in the order menu.json names them."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_tiles import tiles_in
    found = tiles_in(frame.convert("RGBA"))
    names = list(described["tiles"])
    if len(found) != len(names):
        raise SystemExit(f"the new film has {len(found)} tiles in it and the menu has "
                         f"{len(names)}. Nothing written.")
    return {name: list(box) for name, box in zip(names, found)}


def swap(folder: Path, lang: str, sheet: Path, force: bool = False) -> int:
    from PIL import Image

    described = json.loads((folder / "menu.json").read_text(encoding="utf-8"))
    films = described.get("films", {})
    if lang not in films:
        raise SystemExit(f"{folder}/menu.json has no film for {lang}; it has "
                         f"{', '.join(sorted(films))}")
    out = folder / films[lang]

    frames, held = frames_of(sheet)
    if not frames:
        raise SystemExit(f"{sheet.name} has no frames in it")
    if list(frames[0].size) != list(described["size"]):
        raise SystemExit(f"{sheet.name} is {frames[0].size} and the menu is "
                         f"{tuple(described['size'])}; the boxes would not line up")
    was, _ = frames_of(out)
    if len(frames) != len(was):
        raise SystemExit(f"{sheet.name} has {len(frames)} frames and {out.name} has "
                         f"{len(was)}; the menu's films should run together")

    # Where the tiles land. Checked on the first frame: these sheets animate within their
    # tiles, not across them, and a drawing that moved between boxes would fail the size
    # check above long before it got here.
    found = boxes_in(frames[0], described)
    moved = {name: (box, described["tiles"][name]) for name, box in found.items()
             if any(abs(a - b) > SLACK for a, b in zip(box, described["tiles"][name]))}
    if moved and not force:
        for name, (now, before) in moved.items():
            print(f"  {name}: {now} where the menu says {before}")
        raise SystemExit(f"{len(moved)} tile(s) have moved. Nothing written. The menu's boxes "
                         f"came from the English sheet and every language is laid over them, "
                         f"so a film whose tiles have shifted puts the buttons over the wrong "
                         f"pictures. Pass --force only if you mean to.")

    # What actually changed, against the film being replaced. The comparison is done on the
    # squeezed frames, so the palette the old one was written in does not count as a change.
    palette = Image.new("P", (1, 1))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_menu_film import GREYS
    palette.putpalette([v for grey in GREYS for v in (grey, grey, grey)]
                       + [0] * (768 - 3 * len(GREYS)))
    keep = [f.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
            for f in frames]
    said = [f.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
            for f in was]

    import numpy as np
    now = np.array([np.asarray(f.convert("L")).astype(int) for f in keep])
    before = np.array([np.asarray(f.convert("L")).astype(int) for f in said])
    print(f"  {sheet.name} -> {out.name}, {len(keep)} frames")
    for name, (x0, y0, x1, y1) in described["tiles"].items():
        apart = np.abs(now[:, y0:y1, x0:x1] - before[:, y0:y1, x0:x1])
        if apart.max() > 0:
            # Counted, not rounded. Fixing the ghost of an English word left under a
            # translation moves a few dozen pixels from black to white -- four hundredths of
            # one per cent of the tile -- and the first version of this line printed that as
            # "0.0% of it differs", which reads as nothing at all. A count cannot do that.
            print(f"    {name}: redrawn, {int((apart > 0).sum()):,} pixels across "
                  f"{len(keep)} frames, worst {int(apart.max())} of 255")

    hold = out.stat().st_size
    keep[0].save(out, save_all=True, append_images=keep[1:], loop=0,
                 duration=held, optimize=True, disposal=1)
    print(f"  {out.name}: {sheet.stat().st_size / 1e6:.2f}MB in, "
          f"{hold / 1e6:.2f}MB before, {out.stat().st_size / 1e6:.2f}MB now")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="e.g. assets/duas-menu")
    ap.add_argument("lang", help="which language's film this replaces")
    ap.add_argument("sheet", type=Path, help="the film as it was drawn")
    ap.add_argument("--force", action="store_true",
                    help="write it even though its tiles have moved")
    args = ap.parse_args()
    return swap(args.folder if args.folder.is_absolute() else ROOT / args.folder,
                args.lang,
                args.sheet if args.sheet.is_absolute() else ROOT / args.sheet,
                args.force)


if __name__ == "__main__":
    raise SystemExit(main())
