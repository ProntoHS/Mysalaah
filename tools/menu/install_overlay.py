#!/usr/bin/env python3
"""Puts a moving picture into ONE tile of a menu, over the drawing already there.

    python3 tools/menu/install_overlay.py assets/children mosque  snow-maze.gif --all-themes
    python3 tools/menu/install_overlay.py assets/children build   boy-white.gif --theme light
    python3 tools/menu/install_overlay.py assets/children build   boy-black.gif --theme dark colour

WHY NOT JUST REDRAW THE SHEET. Because the sheet is ten sheets. Harry draws the menu again in
every language the mat speaks, with the words baked into the picture, so replacing one tile by
redrawing means ten new films -- and the two tiles he wants replaced here are the two whose
pictures are NOT line art. Journey to the Mosque is his snow maze and Salaah Builder is a
painted boy; both are photographs as far as the mat is concerned, and the mat's answer to a
dark screen is to invert the whole sheet. An inverted painted boy is not a night-time boy, it
is a corpse.

So the tile's PICTURE is replaced and its WORDS are left alone, in all ten languages at once.

    Harry, 25 November 2026: "keep the 3 themes as is. put this mosque gif on all 3 themes.
    the boy on white goes over the current salaah builder in light theme. boy with black
    background goes over dark / coloured theme. everything else stays same"

WHERE THE PICTURE ENDS AND THE WORDS BEGIN, which is measured rather than chosen. Every tile
is a rounded frame with a drawing in the top of it and a caption in the bottom. The caption's
top edge is not the same in every language -- Bengali and Hindi sit 18 rows higher than
English, because their letters hang above and below the line in ways English's do not. This
measures the caption top in EVERY film in the folder and takes the highest of them, then backs
off by MARGIN. Written down because the obvious thing -- measuring the English one -- gives a
number that covers the top of every Hindi caption on the mat, and nothing would have failed:
the words would simply have been under the picture, in two languages, on a mat in a house
where nobody reads either of them.

WHAT IT WRITES

    overlays/<tile>.gif              when one film serves every theme
    overlays/<tile>-<theme>.gif      when a theme wants its own
    menu.json                        an "overlays" block saying where they go

THE FILM IS SCALED TO THE AREA IT WILL FILL, in the sheet's own coordinates. Not to its
original size, which for these three was 19MB between them and more pixels than the sheet they
sit in; and not to the screen, which this tool cannot know. The sheet is scaled as a whole when
it is drawn, so an overlay at the sheet's own resolution stays exactly as sharp as the drawing
around it, at any size, for a sixth of the bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

#: How far inside a tile's box its drawing starts: the rounded frame and its air.
INSET = 26

#: How far above the highest caption the picture is allowed to reach. Three rows of a 461-row
#: tile. Enough that an overlay cannot touch a letter, small enough not to show as a band.
MARGIN = 6

THEMES = ("light", "dark", "colour")


def caption_top(folder: Path, box, films) -> int:
    """The highest row, in tile-inner coordinates, at which any language starts its caption."""
    from PIL import Image
    import numpy as np

    x0, y0, x1, y1 = box
    highest = None
    for name in sorted(set(films)):
        picture = folder / name
        if not picture.is_file():
            continue
        sheet = Image.open(picture)
        sheet.seek(0)
        grey = np.array(sheet.convert("L"))
        inner = grey[y0 + INSET:y1 - INSET, x0 + INSET:x1 - INSET]
        ground = int(np.bincount(inner.ravel()).argmax())
        rows = (np.abs(inner.astype(int) - ground) > 40).sum(axis=1)
        drawn = [i for i, v in enumerate(rows) if v > 3]
        if not drawn:
            continue
        start = drawn[-1]
        for i in range(len(drawn) - 1, 0, -1):
            if drawn[i] - drawn[i - 1] > 6:
                start = drawn[i]
                break
        highest = start if highest is None else min(highest, start)
    if highest is None:
        raise SystemExit("no films to measure the caption against.")
    return highest


def fit(size, area) -> tuple[int, int]:
    """The biggest this picture can be drawn inside [area] without changing its shape."""
    wide, tall = size
    room_w, room_h = area
    scale = min(room_w / wide, room_h / tall)
    return max(1, round(wide * scale)), max(1, round(tall * scale))


def write_film(source: Path, out: Path, size) -> None:
    """The same animation, scaled, with its timing and its looping kept."""
    from PIL import Image, ImageSequence

    frames, times = [], []
    movie = Image.open(source)
    for frame in ImageSequence.Iterator(movie):
        times.append(frame.info.get("duration", movie.info.get("duration", 80)))
        frames.append(frame.convert("RGB").resize(size, Image.LANCZOS))
    if not frames:
        raise SystemExit(f"{source} has no frames.")
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=times,
                   loop=0, optimize=True)

    # READ BACK AND CHECKED, because a GIF written with the wrong palette or a lost frame
    # looks fine in a file listing and wrong on the mat.
    back = Image.open(out)
    count = sum(1 for _ in ImageSequence.Iterator(back))
    if count != len(frames):
        raise SystemExit(f"wrote {len(frames)} frames and read back {count}.")
    back.seek(0)
    if back.size != tuple(size):
        raise SystemExit(f"wrote {size} and read back {back.size}.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="the menu folder, e.g. assets/children")
    ap.add_argument("tile", help="which tile, as menu.json names it")
    ap.add_argument("film", type=Path, help="the moving picture to put in it")
    ap.add_argument("--theme", nargs="+", choices=THEMES,
                    help="which themes this film is for")
    ap.add_argument("--all-themes", action="store_true",
                    help="one film for all three, the same on every screen")
    args = ap.parse_args()

    if bool(args.theme) == bool(args.all_themes):
        raise SystemExit("say either --theme or --all-themes, not both and not neither.")

    folder = args.folder if args.folder.is_absolute() else ROOT / args.folder
    described = json.loads((folder / "menu.json").read_text(encoding="utf-8"))
    if args.tile not in described["tiles"]:
        raise SystemExit(f"{args.tile} is not a tile in {folder / 'menu.json'}: "
                         f"{', '.join(sorted(described['tiles']))}")

    box = described["tiles"][args.tile]
    films = list((described.get("films") or {}).values()) or [described.get("film", "menu.gif")]
    top = caption_top(folder, box, films)
    x0, y0, x1, y1 = box
    area = [x0 + INSET, y0 + INSET, x1 - INSET, y0 + INSET + top - MARGIN]
    room = (area[2] - area[0], area[3] - area[1])

    from PIL import Image
    source = args.film if args.film.is_absolute() else Path.cwd() / args.film
    size = fit(Image.open(source).size, room)

    overlays = described.setdefault("overlays", {})
    entry = overlays.setdefault(args.tile, {})
    entry["area"] = area

    if args.all_themes:
        out = folder / "overlays" / f"{args.tile}.gif"
        write_film(source, out, size)
        entry["film"] = f"overlays/{args.tile}.gif"
        entry.pop("films", None)
        wrote = [out]
    else:
        # ONE FILE FOR THEMES THAT SHARE A FILM. Asked for dark and colour together, the
        # first attempt wrote the same 1.35MB twice under two names -- two files that must
        # stay in step for ever, so that one day one of them is replaced and the other is
        # not. They share a name and both themes point at it.
        per = entry.setdefault("films", {})
        first = args.theme[0]
        out = folder / "overlays" / f"{args.tile}-{first}.gif"
        write_film(source, out, size)
        for theme in args.theme:
            per[theme] = f"overlays/{args.tile}-{first}.gif"
        wrote = [out]
        entry.pop("film", None)

    (folder / "menu.json").write_text(
        json.dumps(described, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"  {args.tile}")
    print(f"     tile box          {box}")
    print(f"     caption starts    inner row {top} (the highest of {len(films)} languages)")
    print(f"     picture area      {area}  = {room[0]}x{room[1]} in sheet pixels")
    print(f"     film drawn at     {size[0]}x{size[1]}")
    for out in wrote:
        was = source.stat().st_size
        now = out.stat().st_size
        print(f"     wrote             {out.relative_to(ROOT)}  "
              f"{now:,} bytes (was {was:,}, {100 * now / was:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
