#!/usr/bin/env python3
"""Every picture a game names must be on the mat.

    python3 tools/check_game_art.py salaah/build_the_salaah.py

A game that asks for a file which is not there does not crash and does not fail any test. It
draws an empty box with a word under it, and the child is asked to choose between a picture and
a blank. Build the Salaah arrived asking for `postures/standing.png` and `postures/sitting.png`;
the mat has neither, so three of its six rounds had no picture at all and every checker passed.

WHY THIS AND NOT A PIXEL MEASUREMENT. The first attempt at this compared the three choice cards
as rendered and reported how alike they were. It was thrown away: it called the Charity Counter
confusable, where the three cards are four coins, three coins and two coins in an identical box
-- the box is most of the ink, so they "agree" while the thing being asked about plainly
differs -- and it called Mosque Manners distinct, where two of the three cards are near-identical
speech bubbles. It measured shared furniture rather than the legibility of the difference, and
no threshold fixes that. Whether a drawing can be told from another drawing is a question for
eyes. Whether the drawing EXISTS is arithmetic, and that is what this does.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
# Suffixes that mean "this string is a path to a picture".
PICTURE = (".png", ".gif", ".jpg", ".jpeg", ".svg")


def named_in(path: pathlib.Path) -> list[str]:
    """Every string literal in the module that looks like a picture's path."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.lower().endswith(PICTURE):
                out.append(node.value)
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modules", nargs="+", type=pathlib.Path)
    args = ap.parse_args()

    missing = []
    for module in args.modules:
        path = module if module.is_absolute() else ROOT / module
        if not path.is_file():
            print(f"  no such file: {module}")
            return 2
        wanted = named_in(path)
        print(f"\n  {path.name}: names {len(wanted)} picture(s)")
        for name in wanted:
            # BY NAME ANYWHERE UNDER assets/, not as a path from the top. A module usually
            # assembles its path -- window.assets / "children" / "qibla-quest.png" -- so the
            # string in the source is only the last part of it. The first version of this
            # resolved every literal against assets/ and reported the two games that were
            # working as missing their artwork, which would have had somebody "fixing" a file
            # that was exactly where it should be.
            found = sorted(ASSETS.rglob(pathlib.Path(name).name))
            exact = (ASSETS / name).is_file()
            there = exact or bool(found)
            where = "ok" if exact else (f"ok, at assets/{found[0].relative_to(ASSETS)}"
                                        if found else "NOT ON THE MAT")
            print(f"      {name:34s} {where}")
            if not there:
                folder = (ASSETS / name).parent
                near = sorted(p.name for p in folder.glob("*")
                              if p.is_file()) if folder.is_dir() else []
                missing.append((path.name, name, near))

    print()
    if missing:
        for module, name, near in missing:
            print(f"  WRONG  {module} asks for assets/{name}, which is not there.")
            if near:
                print(f"         that folder holds: {', '.join(near[:10])}")
        print(f"\n{len(missing)} picture(s) missing. A game that names a file the mat has not")
        print("got draws an empty box, passes every other check, and asks a child to choose")
        print("between a picture and nothing.")
        return 1
    print("  every picture these games name is on the mat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
