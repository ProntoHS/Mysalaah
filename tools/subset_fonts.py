#!/usr/bin/env python3
"""Cuts a script font down to the characters this mat actually renders.

    python3 tools/subset_fonts.py --source ~/fonts/NotoSansCJKsc-Regular.otf --script han
    python3 tools/subset_fonts.py --check-only

WHY THIS EXISTS. It did not until October 2026, and the cost of that was a rendering fault
nobody could see. assets/fonts/NotoSansSC-Subset.ttf had been cut down by hand at some point,
by some means, with no record of either. Chinese wu'du text added later used ten characters the
cut-down face did not have -- 腕 (wrist), 拇 (thumb), 趾 (toes), 湿 (wet), 吸, 擤, 呛, 仔 and the
quotation marks around 「奉真主之名」 -- so six of the seven Chinese wu'du steps drew empty boxes
on the mat. A font subset is a derived file. Deriving it by hand means it cannot be re-derived
when the content changes, and the content always changes.

WHY THE TEST DID NOT CATCH IT. tests/test_ui.py asked Qt, through QFontMetrics.inFont, whether
the face had each character. On a developer machine Qt answers yes by falling back to a system
CJK font -- this container has 335 fonts installed, several of them Noto Sans CJK -- so the
check passed while the bundled file was short. The Pi has no CJK font at all: the bundled file
is the only thing standing between the reader and a row of boxes, which is precisely the
environment the test was written to protect and the one it could not see.

So nothing here asks Qt anything. It reads the cmap out of the font file, which cannot fall
back on anything.

WHAT COUNTS AS NEEDED. Every character of every string in assets that contains at least one
character of the script -- not every character of the script found anywhere. The face is chosen
per string, not per character, so a Chinese sentence with "(Bismillah)" in the middle of it
needs the Latin letters in the Chinese face too. Licensed *.personal.json text is excluded: it
is on one mat and never in a release, and subsetting a shipped font to fit it would leak what
it says.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"

# The ranges that pick out a script, and the file each script's face lives in. These match
# SCRIPT_FONTS in salaah/render.py; that is the list the app actually loads.
SCRIPTS = {
    "han":        (r"[㐀-䶿一-鿿豈-﫿]", "NotoSansSC-Subset.ttf"),
    "devanagari": (r"[ऀ-ॿ꣠-ꣿ]",              "NotoSansDevanagari-Subset.ttf"),
    "bengali":    (r"[ঀ-৿]",                           "NotoSansBengali-Subset.ttf"),
}

# Which OpenType features each face keeps, and why. Measured, not guessed: every string the mat
# can draw in each script was shaped with harfbuzz against the full face and against the subset,
# and these are the smallest settings under which the two came out identical.
#
#   devanagari, bengali -- everything. These scripts are SHAPED: क् + ष becomes the conjunct
#       क्ष through GSUB, and without those tables the reader would show the letters strung out
#       side by side. Stripping features took Devanagari to 18 KB, which should have been the
#       giveaway: it had thrown away every conjunct glyph in the face.
#
#   han -- ccmp only. Chinese needs no shaping, so dropping the lot looked free and is not:
#       "——" is two em dashes that join into one continuous rule, and 145 of the 6,243 Chinese
#       strings on this mat contain it. Without ccmp they came out as two short dashes with a
#       gap. With ccmp alone, all 6,243 shape exactly as the full face does, and the file is
#       511 KB rather than 991 KB. The rest -- vert, vrt2, vhal, vpal and the other vertical
#       tables -- are for setting Chinese in columns, which this mat never does.
FEATURES = {"han": "ccmp,liga,calt,kern,mark", "devanagari": "*", "bengali": "*"}

# Read but never drawn. fonts/README.md put a stray "x" in the Han set before this was here.
NOT_DRAWN = {".md"}

# Every face carries printable ASCII, whatever the content happens to contain today.
#
# The packs are full of strings like "{name} এর সাথে যুক্ত" -- Bengali around a placeholder that
# a Bluetooth speaker's name goes into at runtime, and speakers are called things like "JBL
# Flip 6". for_text picks the face from the FINISHED string, so that Latin is drawn in the
# Bengali face, and the bundled Bengali face had no Latin letters in it at all: a paired
# speaker would have shown its name as a row of boxes on the Pi, which has no fallback.
#
# The content cannot tell us which letters a device name will use, so the whole of printable
# ASCII goes in. It is about ninety glyphs in a Latin script -- a rounding error beside one
# Chinese ideograph -- and it closes the question permanently.
ALWAYS = {chr(c) for c in range(0x20, 0x7F)}

CAP = 600_000          # the same ceiling tests/test_ui.py holds these to

# Characters that land in a string this face draws and that no face for this script can ever
# supply, because they belong to another script entirely. Left out of the subset deliberately,
# named here so that leaving them out is a decision on the record rather than a silent drop,
# and printed on every run so the reason has to be dealt with rather than forgotten.
#
# Each one is a fault in the CONTENT, not in the font, and the fix belongs upstream.
UNCOVERABLE = {
    "َ": "ARABIC FATHA. Two verses of the Noble Qur'an Encyclopedia's Hindi edition "
              "(hindi_omari v1.1.5) carry a stray Arabic vowel mark on a Devanagari word -- "
              "37:178 and 56:18, both reading َऔर where they mean और. "
              "A publisher's typo. Under the permission they granted, the duty is to report it "
              "to them and not to edit their text, so it stays in the file and out of the face. "
              "It draws as nothing, or as a dotted circle, on two verses out of 6,236.",
}


def leaves(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        yield from (s for v in node.values() for s in leaves(v))
    elif isinstance(node, list):
        yield from (s for v in node for s in leaves(v))


def winner(said: str) -> str:
    """Which bundled face salaah/render.py would draw this string in, or "" for none.

    The same arithmetic as Fonts.for_text: the script with the MOST characters in the string,
    not the first one seen. That matters here and not only there. One Devanagari danda at the
    end of a Bengali sentence does not make it Devanagari, and -- the other way about -- a
    string that is mostly Latin with a single Devanagari word in it IS drawn in the Devanagari
    face, so that face needs the Latin letters as well. Asking only "does this string contain
    any Devanagari" counted a hundred characters as needed that nothing would ever draw in
    that face.
    """
    counts = {name: sum(1 for ch in said if re.match(pattern, ch))
              for name, (pattern, _) in SCRIPTS.items()}
    name, how_many = max(counts.items(), key=lambda pair: pair[1])
    return name if how_many else ""


def needed(script: str) -> set[str]:
    """Every character of every string this face is the one chosen to draw."""
    out: set[str] = set()
    for path in sorted(ASSETS.rglob("*")):
        if not path.is_file() or "personal.json" in path.name:
            continue
        if path.suffix in NOT_DRAWN:
            continue
        if path.suffix == ".json":
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for said in leaves(doc):
                if winner(said) == script:
                    out |= set(said)
        elif path.suffix == ".txt":
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line in text.splitlines():
                if winner(line) == script:
                    out |= set(line)
    # Space is a glyph like any other and the face needs it: dropping it shaped every
    # gap in a sentence as .notdef, which is a box 600 units wide in the middle of a
    # word. isprintable() keeps the space and drops newlines and tabs, which are not
    # drawn and are not in the source faces either.
    # Closed under canonical decomposition. Nothing on this mat contains U+09D7 BENGALI AU
    # LENGTH MARK, so it was left out -- but the ccmp feature decomposes ৌ into ে plus
    # U+09D7 before anything else runs, and with the length mark absent the whole substitution
    # failed: পৌঁছে came out with the vowel sign in its default form,
    # 716 units wide where it should be 321. A character a shaper PRODUCES is as needed as one
    # the text contains.
    out = set(out)
    for ch in list(out):
        out |= set(unicodedata.normalize("NFD", ch))
    keep = {c for c in (out | ALWAYS) if c.isprintable()}
    for ch, why in sorted(UNCOVERABLE.items()):
        if ch in keep:
            keep.discard(ch)
            print(f"  LEFT OUT of {script}: U+{ord(ch):04X}")
            for line in textwrap.wrap(why, 88):
                print(f"      {line}")
    return keep


def mapped(path: pathlib.Path) -> set[str]:
    """The characters a font file maps, read out of its cmap. Nothing here asks Qt."""
    from fontTools.ttLib import TTFont
    return {chr(c) for c in TTFont(path, lazy=True).getBestCmap()}


def report(script: str) -> list[str]:
    want = needed(script)
    face = FONTS / SCRIPTS[script][1]
    if not face.is_file():
        return [f"{script}: {face.name} is not bundled"]
    have = mapped(face)
    short = sorted(want - have)
    size = face.stat().st_size
    print(f"  {script:11} needs {len(want):5,}  face maps {len(have):5,}  "
          f"{size // 1024:5d} KB  missing {len(short)}")
    wrong = []
    if short:
        wrong.append(f"{script}: {face.name} has no glyph for "
                     f"{''.join(short)[:40]} ({len(short)} characters)")
    if size >= CAP:
        wrong.append(f"{script}: {face.name} is {size // 1024} KB, over the {CAP // 1024} KB cap")
    return wrong


def cut(script: str, source: pathlib.Path) -> int:
    want = needed(script)
    if not source.is_file():
        print(f"No source face at {source}", file=sys.stderr)
        return 1
    short = sorted(want - mapped(source))
    if short:
        print(f"The source face itself has no glyph for {''.join(short)[:40]}. "
              f"Subsetting it would bake the gap in.", file=sys.stderr)
        return 1
    out = FONTS / SCRIPTS[script][1]
    with tempfile.TemporaryDirectory() as tmp:
        beside = pathlib.Path(tmp) / out.name
        codes = pathlib.Path(tmp) / "unicodes.txt"
        codes.write_text("\n".join(f"U+{ord(c):04X}" for c in sorted(want)), encoding="utf-8")
        # Vertical metrics and layout tables are for vertical Chinese setting, which the mat
        # never does, and they are a third of the weight.
        run = subprocess.run(
            [sys.executable, "-m", "fontTools.subset", str(source),
             f"--output-file={beside}", f"--unicodes-file={codes}",
             f"--layout-features={FEATURES[script]}", "--no-hinting",
             "--drop-tables+=BASE,VORG,vhea,vmtx",
             # --glyph-names keeps the original names. Without it fontTools renames what it
             # keeps to glyph00123, and the Bengali contextual alternates -- uni09C7.long.init
             # and 222 others -- became unreachable: a long initial vowel sign came out in its
             # default form, 716 units wide where it should be 321.
             "--glyph-names", "--no-prune-unicode-ranges", "--no-prune-codepage-ranges",
             "--layout-scripts=*", "--name-IDs=*", "--recalc-bounds"],
            capture_output=True, text=True)
        if run.returncode != 0:
            print(run.stderr[-2000:], file=sys.stderr)
            return 1
        # Checked before it is allowed anywhere near assets/, and checked by reading the file
        # that was written rather than by trusting the subsetter's exit code.
        got = mapped(beside)
        if want - got:
            print(f"The subset came out short of {''.join(sorted(want - got))[:40]}. "
                  f"Not installing it.", file=sys.stderr)
            return 1
        if beside.stat().st_size >= CAP:
            print(f"The subset is {beside.stat().st_size // 1024} KB, over the "
                  f"{CAP // 1024} KB cap. Not installing it.", file=sys.stderr)
            return 1
        was = out.stat().st_size if out.is_file() else 0
        beside.replace(out)
    now = out.stat().st_size
    print(f"  {out.name}: {was // 1024} KB -> {now // 1024} KB, "
          f"{len(want):,} characters, none missing")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="subset_fonts", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", choices=sorted(SCRIPTS), help="which face to cut")
    ap.add_argument("--source", type=pathlib.Path,
                    help="the full face to cut it from, e.g. NotoSansCJKsc-Regular.otf")
    ap.add_argument("--check-only", action="store_true",
                    help="report what the bundled faces cover and stop")
    args = ap.parse_args()

    if args.check_only or not args.script:
        wrong: list[str] = []
        for script in sorted(SCRIPTS):
            wrong += report(script)
        if wrong:
            print(f"\n{len(wrong)} PROBLEMS:", file=sys.stderr)
            for line in wrong:
                print(f"    {line}", file=sys.stderr)
            return 1
        print("\nEvery bundled face covers every character the mat can draw in it, and all "
              "three are\nunder the cap. Read out of the font files, so a system font cannot "
              "flatter the result.")
        return 0

    if not args.source:
        print("--script needs --source: the full face to cut down.", file=sys.stderr)
        return 1
    return cut(args.script, args.source)


if __name__ == "__main__":
    sys.exit(main())
