#!/usr/bin/env python3
"""Re-reads the translations of the Qur'anic du'as out of the Qur'an now on the mat.

    python3 tools/retext_duas.py

WHY THIS EXISTS AND build_duas.py IS NOT THE ANSWER. build_duas.py writes duas.json from
scratch, and duas.json is not its output any more: build_dua_hadith.py folds in 38 more du'as
and build_dua_timings.py then adds "audio", "seconds", "times" and "estimated" to every one of
the 48. Re-running the first of those three throws away the work of the third. Doing exactly
that turned a suite with 7 known failures into one with 106, which is how this file came to be.

So this changes one field. For each du'a that names verses, "text" is re-derived from
assets/content/quran with the same word-drop counts build_duas.py uses -- imported from it,
not copied, so the two cannot disagree -- and every other field is left exactly as it was.
The Arabic, the transliteration and the per-word timings are untouched, because changing a
translation does not move an Arabic word.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from build_duas import CUT, DUAS, QUOTES, languages, slice_words, tidy, verse  # noqa: E402

OUT = ROOT / "assets" / "content" / "duas" / "duas.json"


def text_for(spec: dict, langs: tuple[str, ...]) -> dict:
    got: dict[str, list[str]] = {lang: [] for lang in langs}
    for surah, number, drop in spec["parts"]:
        for lang in langs:
            said = verse(lang, surah, number).get("text", "")
            lose = drop.get(lang, 0) if lang in CUT else 0
            got[lang].append(slice_words(said, lose, f"{spec['key']} {surah}:{number} {lang}")
                             if said else "")
    return {lang: tidy(" ".join(got[lang]), lang in CUT) for lang in langs}


def main() -> int:
    whole = json.loads(OUT.read_text(encoding="utf-8"))
    langs = languages()
    by_key = {s["key"]: s for s in DUAS}
    changed = added = 0
    for item in whole["items"]:
        if not item.get("verses"):
            continue
        spec = by_key.get(item["key"])
        if spec is None:
            print(f"  {item['key']} names verses but build_duas.py has no recipe for it")
            return 1
        before = dict(item["text"])
        item["text"] = text_for(spec, langs)
        item["trimmed"] = [lang for lang in langs if lang in CUT]
        for lang, said in item["text"].items():
            if lang not in before:
                added += 1
            elif before[lang] != said:
                changed += 1
    OUT.write_text(json.dumps(whole, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    kept = sorted(set(whole["items"][0]) - {"key", "cats", "title", "ref", "verses",
                                            "arabic", "said", "text", "trimmed"})
    print(f"  languages: {', '.join(langs)}")
    print(f"  {changed} translations rewritten, {added} added")
    print(f"  fields left untouched on every du'a: {', '.join(kept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
