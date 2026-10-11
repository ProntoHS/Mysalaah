#!/usr/bin/env python3
"""Puts one new tile into a menu's films, without redrawing them.

    python3 tools/swap_menu_tile.py assets/knowledge nasheeds radio new-sheet.png
    python3 tools/swap_menu_tile.py <folder> salaah salaah old-film.gif --into new-film.gif

A STOPGAP, and it should look like one. The 7in menu is an animated sheet with the words
drawn into it, and there is one per language -- menu.gif, menu.fr.gif, menu.ur.gif and five
more. Harry replaced the Nasheeds tile with Radio and is redrawing all seven, which takes as
long as it takes; meanwhile the mat has a Radio section and a menu that still says Nasheeds.

Falling back to the still pictures is what the app does when the film and the menu disagree,
and that is worse than this: the stills are English, so every one of the seven languages
would lose its words rather than one tile of one of them. So the new tile is pasted over the
old one in every frame of every film, in English, and the mat keeps its animation in six
languages minus one square. When the redrawn sheets arrive, build_menu_film.py replaces the
lot and this tool has nothing left to do.

The tile is pasted FROM A STILL, so it does not move. On this one it hardly matters -- the
radio's sound waves were going to be the only thing animating in that square -- but it is
the reason this is a stopgap and not a way of working.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def swap(folder: Path, was: str, now: str, sheet: Path,
         into: list[Path] | None = None) -> int:
    from PIL import Image, ImageSequence
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_menu_film import GREYS

    described = json.loads((folder / "menu.json").read_text(encoding="utf-8"))
    boxes = described["tiles"]
    if was not in boxes:
        raise SystemExit(f"{folder}/menu.json has no tile called {was}")
    left, top, right, bottom = boxes[was]

    source = Image.open(sheet)
    if list(source.size) != list(described["size"]):
        raise SystemExit(f"{sheet.name} is {source.size}, and the menu is "
                         f"{described['size']}; the boxes would not line up")
    # A still gives one picture of the tile, pasted into every frame, and the tile stops
    # moving. A film of the same length gives frame for frame, and it does not -- which is
    # how a tile is taken out of one drawing and put into another with its animation intact.
    patches = [f.convert("RGB").crop((left, top, right, bottom))
               for f in ImageSequence.Iterator(source)]
    print(f"  from {sheet.name}: {len(patches)} frame{'' if len(patches) == 1 else 's'} "
          f"of {was}")

    shades = Image.new("P", (1, 1))
    shades.putpalette([v for grey in GREYS for v in (grey, grey, grey)]
                      + [0] * (768 - 3 * len(GREYS)))

    # The menu's own films, unless told otherwise. --into is for patching a sheet that is
    # not in the menu yet: a redraw sitting in a scratch folder, on its way to being built.
    films = into or [folder / name for name in
                     sorted({described.get("film", "menu.gif"),
                             *described.get("films", {}).values()})]
    for path in films:
        name = path.name
        if not path.is_file():
            print(f"  {name}: not there, skipped")
            continue
        film = Image.open(path)
        keep = []
        for n, frame in enumerate(ImageSequence.Iterator(film)):
            whole = frame.convert("RGB")
            whole.paste(patches[n % len(patches)], (left, top))
            keep.append(whole.convert("L").convert("RGB").quantize(
                palette=shades, dither=Image.Dither.NONE))
        before = path.stat().st_size
        keep[0].save(path, save_all=True, append_images=keep[1:], loop=0,
                     duration=film.info.get("duration", 100), optimize=True, disposal=1)
        print(f"  {name}: {len(keep)} frames, {before / 1e3:.0f}kB -> "
              f"{path.stat().st_size / 1e3:.0f}kB")

    if now != was:
        # The boxes are the same squares; only the name of one of them changes, and it keeps
        # its place in the file so the reading order the app relies on is undisturbed.
        described["tiles"] = {(now if key == was else key): box for key, box in boxes.items()}
        (folder / "menu.json").write_text(json.dumps(described, indent=2) + "\n",
                                          encoding="utf-8")
        print(f"  menu.json: {was} -> {now}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path, help="e.g. assets/knowledge")
    ap.add_argument("was", help="the tile being replaced")
    ap.add_argument("now", help="what it is called instead")
    ap.add_argument("sheet", type=Path,
                    help="where the tile comes from: a still, or a film of the same length")
    ap.add_argument("--into", type=Path, action="append", default=[],
                    help="patch these films instead of the menu's own")
    args = ap.parse_args()
    return swap(args.folder if args.folder.is_absolute() else ROOT / args.folder,
                args.was, args.now,
                args.sheet if args.sheet.is_absolute() else ROOT / args.sheet,
                [p if p.is_absolute() else ROOT / p for p in args.into] or None)


if __name__ == "__main__":
    raise SystemExit(main())
