#!/usr/bin/env python3
"""Merge a game's strings manifest into the nine language packs.

    python3 tools/add_game_strings.py <manifest.json> [--rename qibla.=qiblaquest.] [--write]

Without --write it says what it would do and changes nothing.

IT REFUSES ON A COLLISION. A game that ships a key the app already uses does not add a string,
it RENAMES one, in every language at once. Qibla Quest arrived with `qibla.title`, which is the
compass screen's "Face the Qibla" -- nine languages of it would have become "Qibla Quest". The
--rename option moves a game's keys into their own prefix; the refusal is what makes you use it.

Arabic is not written to. The games' copy is authored in nine languages and the kit falls back
to English for Arabic deliberately; inventing an Arabic string here would be worse than the
fallback, because it would look reviewed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

PACKS = pathlib.Path(__file__).resolve().parent.parent / "assets" / "content" / "packs"
NOT_WRITTEN = {"ar"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=pathlib.Path)
    ap.add_argument("--rename", default="", help="old-prefix=new-prefix")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    book = json.loads(args.manifest.read_text(encoding="utf-8"))
    strings = book["strings"]
    if args.rename:
        was, now = args.rename.split("=", 1)
        strings = {(now + k[len(was):] if k.startswith(was) else k): v
                   for k, v in strings.items()}
        print(f"  renamed {was}* -> {now}*")

    langs = sorted(p.name for p in PACKS.iterdir() if p.is_dir())
    print(f"  {args.manifest.name}: {len(strings)} keys, for {len(langs)} packs "
          f"({', '.join(sorted(NOT_WRITTEN))} left alone)")

    clash: list[str] = []
    missing: dict[str, list[str]] = {}
    for lang in langs:
        if lang in NOT_WRITTEN:
            continue
        pack = json.loads((PACKS / lang / "pack.json").read_text(encoding="utf-8"))
        ui = pack["ui"]
        for key, by_lang in strings.items():
            if key in ui and ui[key] != by_lang.get(lang):
                clash.append(f"{lang}: {key} already says {ui[key]!r}")
            if lang not in by_lang:
                missing.setdefault(lang, []).append(key)

    if clash:
        for c in clash[:12]:
            print(f"  REFUSED  {c}")
        print(f"\n{len(clash)} collision(s). Use --rename to give this game its own prefix;\n"
              f"tools/check_game.py and reference/keys-already-taken.txt list what is taken.")
        return 1
    if missing:
        for lang, keys in missing.items():
            print(f"  REFUSED  {lang} has no translation for: {', '.join(keys[:5])}")
        return 1
    print("  no collisions, and every pack has every key")

    if not args.write:
        print("\n  nothing written (pass --write)")
        return 0

    for lang in langs:
        if lang in NOT_WRITTEN:
            continue
        path = PACKS / lang / "pack.json"
        pack = json.loads(path.read_text(encoding="utf-8"))
        before = len(pack["ui"])
        for key, by_lang in strings.items():
            pack["ui"][key] = by_lang[lang]
        pack["ui"] = dict(sorted(pack["ui"].items()))
        path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"  {lang}: {before} -> {len(pack['ui'])} strings")
    print("\n  reviewed: false stands. Nobody qualified has read any of this.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
