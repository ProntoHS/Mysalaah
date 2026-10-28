#!/usr/bin/env python3
"""Points the salaah step screen at the Qur'an translations already installed on the mat.

    python3 tools/retext_salaah_quran.py            # say what would change
    python3 tools/retext_salaah_quran.py --write    # change it

WHAT WAS WRONG. The mat carries two renderings of the same verse and shows them on two
different screens. The Qur'an reading screen shows a published translation by a named
translator -- Saheeh International, Muhammad Isa García, Helmi Nasr. The salaah step screen,
while a child is praying, showed a draft written for this app. Same device, same Fatiha, two
different English texts. Portuguese was worse: a complete licensed Qur'an sitting installed,
and the step screen showing the Arabic with nothing under it.

WHAT THIS DOES. Rebuilds five of the six Qur'anic passages in content/translations/<lang>.json
out of content/quran/<lang>/, so the words a child reads during salaah are the same words the
reading screen gives them, from a translator with a name.

WHICH LANGUAGES, and this is the part that is a judgement rather than a rule:

    en es hi pt zh   SWITCHED. Their Qur'an came from quranenc.com's official export under the
                     permission Harry was granted, and carries publisher_reviewed=true. A
                     publisher's own reviewed edition beats a draft written here, every time.

    fr ur            LEFT ALONE, deliberately. Their step screens already use published work
                     that is beyond doubt out of copyright -- Kazimirski (1840) and Fateh
                     Muhammad Jalandhry (d. 1929). What is installed as their READING screen
                     came from quran-json, not from QuranEnc, and is Hamidullah (d. 2002) and
                     Maududi (d. 1979), both of whom died well inside copyright. Switching
                     would trade text that is certainly free for text that is probably not.
                     That is a worse position on a device meant to be given away, so the
                     reading screen and the step screen are allowed to differ for these two
                     until somebody licenses one or the other properly.

WHICH PASSAGES. Five of the six, and the sixth is the interesting one.

    fatiha      surah 1, verses 1-7
    kawthar     the basmala, then 108:1-3
    ikhlas      the basmala, then 112:1-4
    falaq       the basmala, then 113:1-5
    nas         the basmala, then 114:1-6

The basmala is taken from 1:1 of the same translation, because the short surahs are stored as
verses only -- 112.json holds four, not five -- and a basmala borrowed from another translator
would put two hands in one passage.

    ayat_kursi  NOT DONE, and not by oversight.

Ayat al-Kursi is one verse, 2:255. The Arabic on this mat is split into NINE lines, because a
child learns it in phrases. A published translation of it is one block of prose. Cutting that
block at the same nine places is not copying a translation, it is deciding where a translator's
sentences break in a language nobody here reads -- in Urdu, in Chinese, in Hindi -- and then
printing the result under that translator's name. The draft stays until somebody who reads the
language does the alignment.

HOW IT PROTECTS ITSELF. Every rebuilt passage must come out with the same number of lines as
core/arabic.json has for it, or nothing is written for that language. The line counts are the
contract the screen relies on: Translation.for_key returns None when they disagree, and the mat
then shows Arabic alone rather than meanings beside the wrong lines.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from salaah.quran import as_shown   # noqa: E402  -- the same display rule the reader uses

BASMALA = (1, 1)
PASSAGES = {
    "fatiha":  [(1, n) for n in range(1, 8)],
    "kawthar": [BASMALA] + [(108, n) for n in range(1, 4)],
    "ikhlas":  [BASMALA] + [(112, n) for n in range(1, 5)],
    "falaq":   [BASMALA] + [(113, n) for n in range(1, 6)],
    "nas":     [BASMALA] + [(114, n) for n in range(1, 7)],
}

# Left on their own public-domain text: see the note at the top of this file.
KEEP_PUBLIC_DOMAIN = {"fr", "ur"}


def arabic_counts() -> dict[str, int]:
    text = json.loads((ROOT / "assets" / "content" / "core" / "arabic.json")
                      .read_text(encoding="utf-8"))["text"]
    return {k: len(text[k]) for k in PASSAGES if isinstance(text.get(k), list)}


def verses(lang: str) -> dict[tuple[int, int], str]:
    """Every verse this job needs, as {(surah, number): the text as the mat shows it}."""
    out: dict[tuple[int, int], str] = {}
    folder = ROOT / "assets" / "content" / "quran" / lang
    for surah in sorted({s for places in PASSAGES.values() for s, _ in places}):
        book = json.loads((folder / f"{surah}.json").read_text(encoding="utf-8"))
        for row in book:
            out[(surah, row["n"])] = as_shown(row.get("text", ""), row.get("n") or 0)
    return out


def rebuild(lang: str, want: dict[str, int]):
    """The five passages for one language, or a complaint saying why not."""
    folder = ROOT / "assets" / "content" / "quran" / lang
    if not (folder / "SOURCE.json").is_file():
        return None, "no Qur'an installed"
    source = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    try:
        got = verses(lang)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return None, f"could not read it: {exc}"

    lines: dict[str, list[str]] = {}
    for key, places in PASSAGES.items():
        try:
            lines[key] = [got[place] for place in places]
        except KeyError as missing:
            return None, f"{key}: no verse {missing}"
        if any(not line.strip() for line in lines[key]):
            return None, f"{key}: a verse came out empty"
        if key in want and len(lines[key]) != want[key]:
            return None, (f"{key}: {len(lines[key])} lines against the Arabic's {want[key]} -- "
                          f"the screen would show Arabic alone")
    return (lines, source), ""


def main() -> int:
    ap = argparse.ArgumentParser(prog="retext_salaah_quran", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the changes")
    args = ap.parse_args()

    want = arabic_counts()
    quran = ROOT / "assets" / "content" / "quran"
    langs = sorted(d.name for d in quran.iterdir() if d.is_dir() and d.name != "ar"
                   and (d / "SOURCE.json").is_file())
    changed = 0
    for lang in langs:
        if lang in KEEP_PUBLIC_DOMAIN:
            print(f"  {lang}: left on its public-domain text, deliberately (see the docstring)")
            continue
        built, why = rebuild(lang, want)
        if built is None:
            print(f"  {lang}: SKIPPED -- {why}")
            continue
        lines, source = built
        who = source.get("translator") or "?"
        where = ROOT / "assets" / "content" / "translations" / f"{lang}.json"
        if not where.is_file():
            print(f"  {lang}: no translations file yet -- {who} is ready for one")
            continue
        doc = json.loads(where.read_text(encoding="utf-8"))
        was = doc.get("lines", {})
        moving = [k for k in lines if was.get(k) != lines[k]]
        print(f"  {lang}: {len(moving)} of {len(lines)} passages move to {who}")
        for key in moving:
            before = (was.get(key) or [""])[0]
            print(f"        {key:<10} {before[:52]}")
            print(f"        {'':<10} -> {lines[key][0][:52]}")
        if not args.write or not moving:
            continue
        doc["lines"] = {**was, **lines}
        doc["sources"] = {**doc.get("sources", {}),
                          **{k: f"{who} ({source.get('via', 'installed on the mat')})"
                             for k in lines}}
        where.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        back = json.loads(where.read_text(encoding="utf-8"))   # read it back, do not assume
        for key in lines:
            assert back["lines"][key] == lines[key], f"{lang}/{key} did not survive the write"
            assert len(back["lines"][key]) == want.get(key, len(lines[key])), f"{lang}/{key}"
        changed += 1

    print()
    print(f"  ayat_kursi left as a draft in every language: one verse, nine lines, and cutting "
          f"a translator's prose\n  at nine places is not copying it. See the docstring.")
    if not args.write:
        print("\n  Nothing written. Pass --write to do it.")
    else:
        print(f"\n  {changed} language(s) rewritten, each read back and checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
