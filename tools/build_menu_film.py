#!/usr/bin/env python3
"""Turns an animated sheet of menu tiles into something the mat can carry and touch.

    python3 tools/build_menu_film.py sheet.gif assets/hadith-menu \
        faith prayer purification fasting charity hajj knowledge character \
        family community daily hereafter

Writes menu.gif and menu.json beside the tiles the menu already has.

Harry drew the du'a, hadith and 7in menus again as animations -- the whole sheet moving at once,
the tap dripping and the hourglass turning. The mat showed those menus as eighteen, twelve and
eight separate pictures, each one found and cut out of a still sheet, so there are two problems
to solve: the weight, and how a drawing that is now one moving picture gets touched in eighteen
places.

THE WEIGHT. Forty-one megabytes between the three of them. They are black line icons on white
paper and only three per cent of the picture changes between one frame and the next, so the same
re-encoding the wu'du films had -- a written-down palette of four greys rather than one Pillow
picks by pixel count -- takes them down by a factor of thirty or so. The palette is written down
for the reason it was there: by population these sheets are nine tenths paper, so a palette
chosen that way spends every slot on near-whites and the black icons come out grey.

THE TOUCHING. The tiles are found here, at build time, by the same cutter that cut the still
sheets, and their boxes are written into menu.json in the sheet's own pixels. The app then shows
ONE moving picture and lays invisible buttons over it at those boxes. One film per menu rather
than eighteen: eighteen QMovies on a menu would be eighteen timers redrawing eighteen widgets on
a Raspberry Pi, for a drawing that was made as one picture and is nicer left as one.

Finding them here rather than on the mat also keeps SciPy where it belongs. It is what finds the
tiles, it is a big thing to install, and it has never been needed to pray -- only to build.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Written down rather than chosen by population. See the note above, and build_wudu.py, where
# letting Pillow choose turned every black line in the drawing grey.
GREYS = (0, 96, 176, 255)


def squeeze(source: Path, out: Path) -> tuple[int, int]:
    from PIL import Image, ImageSequence
    was = source.stat().st_size
    film = Image.open(source)
    shades = Image.new("P", (1, 1))
    shades.putpalette([v for grey in GREYS for v in (grey, grey, grey)]
                      + [0] * (768 - 3 * len(GREYS)))
    keep = [frame.convert("L").convert("RGB").quantize(palette=shades,
                                                       dither=Image.Dither.NONE)
            for frame in ImageSequence.Iterator(film)]
    if not keep:
        raise SystemExit(f"{source.name} has no frames in it")
    keep[0].save(out, save_all=True, append_images=keep[1:], loop=0,
                 duration=film.info.get("duration", 100), optimize=True, disposal=1)
    return was, out.stat().st_size


def build(sheet: Path, out: Path, names: list[str]) -> int:
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_tiles import tiles_in

    first = Image.open(sheet)
    first.seek(0)
    boxes = tiles_in(first.convert("RGBA"))
    print(f"{sheet.name}: {first.width}x{first.height}, "
          f"{getattr(first, 'n_frames', 1)} frames, {len(boxes)} tiles found")
    if len(boxes) != len(names):
        print(f"\n{len(boxes)} tiles but {len(names)} names. Nothing written.", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    was, now = squeeze(sheet, out / "menu.gif")
    described = {
        "schema": 1,
        "film": "menu.gif",
        "size": [first.width, first.height],
        # In the sheet's own pixels. The app scales them with the picture, so a redrawn sheet at
        # a different size needs nothing changed anywhere else.
        "tiles": {name: list(box) for name, box in zip(names, boxes)},
    }
    (out / "menu.json").write_text(json.dumps(described, indent=2) + "\n", encoding="utf-8")
    for name, box in zip(names, boxes):
        print(f"   {name:14} {box[2] - box[0]:4}x{box[3] - box[1]:<4} at {box[0]},{box[1]}")
    print(f"\n  film  {was / 1e6:.1f} MB -> {now / 1e6:.2f} MB "
          f"({was / max(now, 1):.0f} times smaller)")
    print(f"-> {out.relative_to(ROOT) if ROOT in out.parents or out == ROOT else out}")
    return 0


DRIFT = 7          # how far a language sheet's tiles may sit from the English ones, in pixels


def add_language(sheet: Path, out: Path, lang: str) -> int:
    """Put one translated sheet beside the English one and record it in menu.json.

    The words on these tiles are drawn into the picture, so following the mat's language means
    showing a different film. The BOXES are not per language -- there is one set and it serves
    them all, which is the whole reason this has to be checked rather than copied. A sheet whose
    grid has shifted still looks perfectly right: every tile is drawn, every word is legible,
    and the invisible buttons are simply somewhere else, so a child pressing Kaaba Jigsaw gets
    the prayer game. Nothing in the app can notice, and nor could a person looking at the menu.

    So the tiles are found in the new sheet and compared with the ones already recorded, and
    anything beyond seven pixels is refused. Seven because that is what the first set of
    language sheets came within -- a fiftieth of a tile, and a tile is a finger wide.
    """
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_tiles import tiles_in

    where = out / "menu.json"
    if not where.is_file():
        print(f"No {where}. Build the English sheet first.", file=sys.stderr)
        return 1
    described = json.loads(where.read_text(encoding="utf-8"))
    known = described.get("tiles") or {}

    first = Image.open(sheet)
    first.seek(0)
    boxes = tiles_in(first.convert("RGBA"))
    print(f"{sheet.name}: {first.width}x{first.height}, "
          f"{getattr(first, 'n_frames', 1)} frames, {len(boxes)} tiles found")
    if [first.width, first.height] != list(described.get("size", [])):
        print(f"\nThis sheet is {first.width}x{first.height} and the boxes were cut at "
              f"{described.get('size')}. Nothing written.", file=sys.stderr)
        return 1
    if len(boxes) != len(known):
        print(f"\n{len(boxes)} tiles but menu.json has {len(known)}. Nothing written.",
              file=sys.stderr)
        return 1
    worst, worst_name = 0, ""
    for (name, was), box in zip(known.items(), boxes):
        off = max(abs(a - b) for a, b in zip(was, box))
        if off > worst:
            worst, worst_name = off, name
    print(f"   worst tile drifted {worst} px from the English grid ({worst_name})")
    if worst > DRIFT:
        print(f"\nThat is more than {DRIFT} px. The buttons would not line up with the "
              f"pictures.\nNothing written.", file=sys.stderr)
        return 1

    film = f"menu.{lang}.gif"
    was, now = squeeze(sheet, out / film)
    films = described.get("films") or {}
    films.setdefault("en", described.get("film", "menu.gif"))
    films[lang] = film
    described["films"] = films
    where.write_text(json.dumps(described, indent=2) + "\n", encoding="utf-8")
    print(f"   {film}: {was / 1e6:.2f} MB -> {now / 1e6:.2f} MB")
    print(f"   menu.json now names films for: {', '.join(sorted(films))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_menu_film")
    ap.add_argument("sheet", type=Path, help="the animated drawing, all the tiles on one sheet")
    ap.add_argument("out", type=Path, help="the menu's folder in assets")
    ap.add_argument("names", nargs="*", help="what the tiles are called, in reading order")
    ap.add_argument("--language", metavar="XX",
                    help="this sheet is the same menu drawn in another language: write it as "
                         "menu.XX.gif and record it, rather than rewriting menu.json")
    args = ap.parse_args()
    if args.language:
        if args.names:
            print("--language takes no tile names: the boxes are already recorded.",
                  file=sys.stderr)
            return 1
        return add_language(args.sheet, args.out, args.language)
    if not args.names:
        print("Give the tile names, in reading order.", file=sys.stderr)
        return 1
    return build(args.sheet, args.out, args.names)


if __name__ == "__main__":
    sys.exit(main())
