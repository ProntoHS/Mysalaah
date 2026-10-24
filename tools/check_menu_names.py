#!/usr/bin/env python3
"""Check that a menu's tile NAMES still match the words drawn in its pictures.

    python3 tools/check_menu_names.py assets/children

The names in menu.json are what the app routes on: press the box called "game" and the app
opens the prayer game. The words are drawn INTO the picture, so nothing in the app can tell
that the box called "game" now has "Qibla Quest" written in it.

That is not hypothetical. The children's sheet drawn for 1.89 moved every tile along: the box
the menu called "wudu" became the Prayer Game and the box it called "game" became Qibla Quest,
because Wu'du had gone to the Knowledge menu. Had the names not been changed to follow, every
child pressing Prayer Game would have got a wu'du lesson and every child pressing Qibla Quest
would have got the prayer game -- and every check in the repo would have passed, because the
boxes had not moved and the films all lined up. The pictures changed meaning underneath them.

HOW IT READS THE WORDS. Tesseract if it is installed, which it usually is not. Otherwise it
falls back to asking a person: it crops each named box out of the film and writes a labelled
sheet, and prints what to look for. That is not a cop-out -- a sheet of twelve pictures with
the name the app will route to printed under each is a ten-second job for a person and the
only check that can be trusted here. What it must never do is pass silently.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "menu-names"

# What each tile name is expected to say, in English. Only the names the app routes on need to
# be here; a name not listed is reported as unchecked rather than passed.
EXPECTED = {
    "children": {
        "game": "prayer game", "qiblaquest": "qibla quest", "jigsaw": "kaaba jigsaw",
        "build": "build salaah", "pillars": "five pillars",
        # spare1 is a drawn outline with nothing written in it, waiting for the next game.
        # It is deliberately not listed: a name that is not here is reported as unchecked
        # rather than passed, and an empty tile has no word to check.
    },
    # The 7in main menu. The folder is called "knowledge" for historical reasons -- it was the
    # Knowledge Corner before it was the main menu -- and at 1.89 one of its own TILES is also
    # called knowledge, which is the Wu'du submenu below. Confusing, and renaming the folder
    # would strand the old one on every mat, since a changes zip adds and replaces but never
    # deletes. Left alone deliberately; this comment is the warning.
    "knowledge": {
        "quran": "qur'an", "salaah": "salaah", "hadith": "hadith", "duas": "du'as",
        "children": "children", "learn": "learn", "knowledge": "knowledge",
        "world": "world", "settings": "settings", "radio": "radio",
    },
    # The Knowledge submenu: one tile on a sheet drawn for eighteen.
    "knowledge-menu": {
        "wudu": "wu'du",
    },
}


def words_in(frame: Image.Image, box) -> str:
    """Read the caption out of one tile.

    THE CAPTION BAND, NOT THE WHOLE TILE. Each box is a picture above a word, and handed the
    whole box tesseract tries to make letters out of the mosque or the prayer beads and
    returns things like 'vf game' and 'az)'. Given the bottom of the box on its own, upscaled,
    it reads 'Prayer Game' off any frame of the film. The first version of this checker called
    all eleven names wrong on a sheet where all eleven were right, which is the failure that
    gets a checker switched off.
    """
    x0, y0, x1, y1 = box
    tall = y1 - y0
    band = frame.crop((x0, y0 + int(tall * 0.62), x1, y1 - int(tall * 0.06)))
    band = band.resize((band.width * 3, band.height * 3), Image.LANCZOS)
    # TWO PAGE MODES, both readings returned. tesseract's single-line mode reads the Du'as
    # tile as "putas" at every scale tried, and its block mode reads it as "Du\'as" -- the
    # apostrophe throws the line finder. Reading the tile twice and accepting either is the
    # reader trying harder; loosening the comparison until "putas" counted as "du\'as" would
    # have been the checker grading easier, and would have let a genuinely wrong name past.
    said = []
    for psm in ("7", "6"):
        out = subprocess.run(["tesseract", "stdin", "stdout", "--psm", psm],
                             input=_png(band), capture_output=True, check=False)
        said.append(out.stdout.decode("utf-8", "replace").strip().lower())
    return " | ".join(dict.fromkeys(s for s in said if s)).replace("\n", " ")


def edits(a: str, b: str) -> int:
    """Levenshtein distance. Substitutions, insertions AND deletions."""
    if a == b:
        return 0
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        new = [i]
        for j, cb in enumerate(b, 1):
            new.append(min(row[j] + 1, new[j - 1] + 1, row[j - 1] + (ca != cb)))
        row = new
    return row[-1]


def near(word: str, said: str) -> bool:
    """Whether `said` contains `word`, allowing ONE character's slip.

    A REAL edit distance, not a count of mismatches between equal-length windows. The first
    version did the latter and it cannot see an INSERTION: tesseract reads the Du'as tile as
    "du'‘as", one stray quote mark, and lining "du'as" up against five-character windows of
    that puts every later letter one place out and scores several mismatches. Any slip that
    shifts the rest of the word along was invisible to it.

    One edit is enough for the reader stumbling -- a capital T taken for an r in "tasbih", a
    quote mark invented in "du'as" -- and nowhere near enough to confuse the names this exists
    to tell apart: "prayer game" and "qibla quest" are ten edits apart, "tasbih counter" and
    "pattern builder" eleven, "learn" and "knowledge" nine.
    """
    if word in said:
        return True
    n = len(word)
    for size in (n - 1, n, n + 1):
        if size < 1:
            continue
        for i in range(max(0, len(said) - size + 1)):
            if edits(word, said[i:i + size]) <= 1:
                return True
    return False


def _png(im: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=pathlib.Path, help="e.g. assets/children")
    ap.add_argument("--lang", default="en", help="which film to read (default en)")
    args = ap.parse_args()

    folder = args.folder if args.folder.is_absolute() else ROOT / args.folder
    described = json.loads((folder / "menu.json").read_text(encoding="utf-8"))
    films = described.get("films", {}) or {"en": described["film"]}
    film = folder / films.get(args.lang, described["film"])
    want = EXPECTED.get(folder.name, {})
    if not want:
        print(f"no expected words recorded for {folder.name}; add them to EXPECTED")
        return 2

    with Image.open(film) as f:
        f.seek(0)
        frame = f.convert("RGB")

    tiles = described["tiles"]
    unchecked = [n for n in tiles if n not in want and not n.startswith("spare")]

    if shutil.which("tesseract"):
        bad = []
        for name, phrase in want.items():
            if name not in tiles:
                bad.append(f"{name}: menu.json has no box called that")
                continue
            got = words_in(frame, tiles[name])
            hit = all(near(w, got) for w in phrase.split())
            print(f"  {name:12s} drawing says {got[:40]!r:44s} {'' if hit else '<-- WRONG'}")
            if not hit:
                bad.append(f"{name}: the box says {got[:40]!r}, not {phrase!r}")
        if bad:
            for b in bad:
                print(f"  WRONG  {b}")
            print(f"\n{len(bad)} tile name(s) do not match the drawing. The app routes on the\n"
                  f"NAME and the child reads the WORD, so these open the wrong thing.")
            return 1
        print("\n  every routed tile's name matches the words drawn in it")
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        cell = 300
        names = list(tiles)
        cols = 6
        rows = (len(names) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell, rows * (cell + 26)), "white")
        dr = ImageDraw.Draw(sheet)
        for i, name in enumerate(names):
            x0, y0, x1, y1 = tiles[name]
            r, c = divmod(i, cols)
            sheet.paste(frame.crop((x0, y0, x1, y1)).resize((cell - 8, cell - 8)),
                        (c * cell + 4, r * (cell + 26) + 4))
            dr.rectangle([c * cell + 4, r * (cell + 26) + 4,
                          c * cell + cell - 4, r * (cell + 26) + cell - 4], outline="#999")
            dr.text((c * cell + 8, r * (cell + 26) + cell + 4),
                    f"the app routes this to: {name}", fill="black")
        where = OUT / f"{folder.name}-{args.lang}-names.png"
        sheet.save(where)
        print(f"  tesseract is not installed, so this cannot read the words itself.")
        print(f"  wrote {where}")
        print(f"  LOOK at it: under each picture is the name the app will route that box to.")
        print(f"  Expected, in menu.json order:")
        for name in names:
            if name in want:
                print(f"      {name:12s} should say  {want[name]}")
        print("\n  NOT PASSED -- a person has to say whether the words match the names.")
        return 1

    if unchecked:
        print(f"  unchecked (no expected words recorded): {', '.join(unchecked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
