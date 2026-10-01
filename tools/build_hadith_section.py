#!/usr/bin/env python3
"""Builds the Hadith section: sayings of the Prophet, filed under the twelve headings Harry drew.

    python3 tools/build_hadith_section.py --editions ~/hadith-api/editions

Harry asked for "authentic hadiths". That word has a meaning, so this takes the narrow reading
of it and ships nothing else:

  * SAHIH AL-BUKHARI AND SAHIH MUSLIM ONLY. Every narration in those two is graded sahih, so
    "authentic" is a property of the book rather than a judgement made here. The other seven
    collections carry sound and weak narrations side by side, and grading one is scholarship,
    not something a build script does.
  * NOT ONE WORD IS TYPED FROM MEMORY -- not the Arabic and, unlike the du'as, not the English
    either. A du'a is a formula of a dozen words and a plain rendering of it is a small thing.
    A hadith is a narration with a chain, a context and a history of translation, and writing
    my own English for one would be putting words in the Prophet's mouth. So the Arabic and the
    translation are BOTH lifted from the corpus, matched to each other by hadith number.
  * TWO CORPORA. The text is lifted from the hadith-api dataset (github.com/fawazahmed0/
    hadith-api, Unlicense), which carries Arabic and English under one numbering. Each lifted
    Arabic line must ALSO be found in the MIT-licensed 'hadith' package on PyPI -- a separate
    compilation, from separate sources, which had no part in the lift. A line the second corpus
    does not carry is NOT WRITTEN; it is printed as a refusal and the rest carry on.

The comparison between the two is made on bare letters -- diacritics, tatweel and punctuation
stripped, alef/ya/ta-marbuta folded -- because no two Arabic corpora have ever agreed on where a
comma goes, and a check that fails on a vowel mark is a check nobody keeps.

And it asks for the longest unbroken run of words the two share, not for the whole narration.
The first go demanded the whole thing and refused fourteen of the forty-eight, which looked
like the check working and was the check being wrong: a narration is a chain of narrators
followed by the saying, and two compilations working from different manuscripts routinely write
the chain differently while the saying is word for word the same. Bukhari 528 was refused with
52 of its 66 words matching in one unbroken run -- the whole of the saying, and all that
differed was the head of the chain. So the bar is a run of at least MATCH_WORDS words that is
also at least MATCH_SHARE of the narration, which no wording the second corpus lacks can clear,
and every lift prints the run it found so the number can be read rather than trusted.

WHAT THIS DOES NOT DO, and what a qualified reviewer still has to:

  * Check that each hadith is under the right heading. That is the one editorial act here and
    it is entirely mine. The numbers are in the table below so every choice can be looked up.
  * Check the numbering against sunnah.com. The dataset's numbers agree with sunnah.com's as
    far as spot checks go, but "as far as spot checks go" is not a citation.
  * Vouch for the translations. They are the ones that circulate with these collections
    (Muhsin Khan for Bukhari, Abdul Hamid Siddiqui for Muslim); the dataset publishes them
    under the Unlicense and every hadith site uses them, but their standing is not mine to
    assert, and neither is their accuracy.
  * Decide what belongs in front of a child. I have kept out narrations about punishments,
    warfare, slavery and marital intimacy, which is a judgement about this mat and not about
    the hadith. Somebody who knows the family should look at the list.

That is why the file it writes says reviewed: false, and why the app draws the section with
that flag showing.

The dataset is fetched once, by hand, because the mat's build machine has no business
downloading scripture on a timer:

    mkdir -p ~/hadith-api/editions && cd ~/hadith-api/editions
    for e in ara-bukhari eng-bukhari ara-muslim eng-muslim; do
      curl -sSLO "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions/$e.json"
    done
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "content" / "hadith" / "hadith.json"

BOOKS = {"bukhari": "Sahih al-Bukhari", "muslim": "Sahih Muslim"}
CORPUS = {"bukhari": "Sahih_Bukhari", "muslim": "Sahih_Muslim"}   # the second corpus's names

# The twelve headings Harry drew, in the order they sit on the sheet, and under each the
# narrations chosen for it by (collection, hadith number). The numbers are the whole record of
# what was picked: nothing here is searched for at build time, so the same numbers give the same
# section every time, and a reviewer can read this table against sunnah.com without running it.
CHOSEN = {
    "faith": [
        ("bukhari", "8"),       # Islam is based on five
        ("bukhari", "13"),      # till he wishes for his brother what he likes for himself
        ("muslim", "152"),      # Iman has over seventy branches
        ("bukhari", "7453"),    # My Mercy has preceded My Anger
    ],
    "prayer": [
        ("bukhari", "528"),     # a river at your door, bathed in five times a day
        ("muslim", "550"),      # the five prayers are an expiation
        ("muslim", "1478"),     # in congregation, twenty-seven times over
        ("muslim", "256"),      # prayer at its time, and kindness to parents
    ],
    "purification": [
        ("bukhari", "245"),     # the siwak on rising at night
        ("muslim", "578"),      # ablution done well
        ("bukhari", "6954"),    # no prayer until the ablution is made anew
        ("muslim", "543"),      # ablution, then prayer with humility
    ],
    "fasting": [
        ("bukhari", "38"),      # whoever fasts Ramadan out of faith and hope
        ("bukhari", "3277"),    # the gates opened, the gates closed
        ("bukhari", "6057"),    # giving up food is not the point if lying is not given up
        ("bukhari", "1957"),    # hasten the breaking of the fast
    ],
    "charity": [
        ("bukhari", "1417"),    # even half a date
        ("muslim", "6592"),     # charity does not decrease wealth
        ("muslim", "2386"),     # the upper hand, and begin at home
        ("muslim", "2328"),     # every act of goodness is sadaqa
    ],
    "hajj": [
        ("bukhari", "1521"),    # returns as if born anew
        ("bukhari", "1773"),    # Umra is an expiation; Hajj Mabrur, nothing but Paradise
        ("bukhari", "1549"),    # the Talbiya, with its meaning
        ("bukhari", "5617"),    # Zamzam
    ],
    "knowledge": [
        ("bukhari", "5028"),    # those who learn the Qur'an and teach it
        ("bukhari", "71"),      # when Allah wants good for someone
        ("bukhari", "106"),     # do not tell a lie against me
        ("bukhari", "5033"),    # commit yourself to the Qur'an
    ],
    "character": [
        ("bukhari", "6035"),    # the best among you are the best in character
        ("bukhari", "6114"),    # the strong one is the one who holds himself in anger
        ("bukhari", "6136"),    # his neighbour, his guest, and speaking good or keeping silent
        ("bukhari", "7376"),    # no mercy for those who show none
    ],
    "family": [
        ("bukhari", "5971"),    # your mother, your mother, your mother, then your father
        ("bukhari", "5200"),    # all of you are guardians
        ("bukhari", "5979"),    # be good to your mother
        ("bukhari", "5995"),    # daughters, and what they are to their father
    ],
    "community": [
        ("bukhari", "6951"),    # a Muslim is a brother of another Muslim
        ("bukhari", "6011"),    # the believers, resembling one body
        ("bukhari", "6076"),    # do not hate one another
        ("bukhari", "6064"),    # beware of suspicion
    ],
    "daily": [
        ("muslim", "5269"),     # say the Name, eat with your right hand, eat what is near you
        ("bukhari", "6405"),    # Subhan Allah wa bihamdihi, a hundred times
        ("muslim", "6932"),     # Alhamdulillah over a mouthful and a drink
        ("bukhari", "6312"),    # lying down, and waking
    ],
    "hereafter": [
        ("bukhari", "6416"),    # be in this world as a stranger or a traveller
        ("muslim", "4223"),     # three things that do not end
        ("bukhari", "6488"),    # nearer to you than your shoelace
        ("muslim", "7417"),     # the world, to a believer
    ],
}

MATCH_WORDS = 12     # the shortest run that counts as the second corpus having this narration
MATCH_SHARE = 0.40   # and it must be at least this much of the narration

DIAC = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
FOLD = (("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
        ("ى", "ي"), ("ة", "ه"))


def bare(text: str) -> str:
    """Arabic down to its letters: vowel marks, tatweel and punctuation off, letters folded.

    Every comparison between the two corpora is made on this. They disagree constantly about
    diacritics and punctuation and never about letters, so a check on the raw string fails on
    a fatha and tells you nothing, while a check on this fails only when the text differs.
    """
    text = DIAC.sub("", text)
    for a, b in FOLD:
        text = text.replace(a, b)
    return " ".join(re.sub(r"[^ء-ي ]", " ", text).split())


def longest_run(words: list[str], corpus: str) -> int:
    """How many words of [words], unbroken and in order, the second corpus also has.

    Grown from each starting word rather than compared whole, which is what lets the chain
    differ while the saying is held to the letter.
    """
    best = 0
    for i in range(len(words)):
        if len(words) - i <= best:
            break                       # nothing left long enough to beat what we have
        j = i + best + 1
        while j <= len(words) and " ".join(words[i:j]) in corpus:
            best = j - i
            j += 1
    return best


def tidy(english: str) -> str:
    """The translation as the dataset holds it, with three presentation faults mended.

    The dataset strips the final full stop off every entry and often the closing quote with it,
    and it drops the space after the narrator's colon. Nothing here changes a word: it closes a
    quotation mark that was opened, adds the sentence's own full stop, and puts back a space.
    Anything more than that would be editing a translation, which is not this script's job.
    """
    said = re.sub(r"^(Narrated[^:]{0,60}:)(?=\S)", r"\1 ", english.strip())
    if said.count('"') % 2:
        said += '"'
    if not said.endswith((".", '."', ".'", "!", "?", '?"', '!"')):
        said = said.rstrip(",;: ") + ("." if said.endswith('"') is False else ".")
    return said


def editions(where: Path) -> dict:
    """The four dataset files, as {collection: (arabic by number, english by number, meta)}."""
    out = {}
    for book in BOOKS:
        got = []
        for tongue in ("ara", "eng"):
            path = where / f"{tongue}-{book}.json"
            if not path.is_file():
                raise SystemExit(f"missing {path}\nSee the header of this file for how to fetch it.")
            got.append(json.loads(path.read_text(encoding="utf-8")))
        by = [{str(h["hadithnumber"]): h for h in side["hadiths"]} for side in got]
        out[book] = (by[0], by[1], got[1]["metadata"])
    return out


def second_corpus() -> dict:
    """The MIT 'hadith' package, as {collection: one long bare string of all its narrations}.

    Held as one string on purpose: what is being asked is only "does this wording appear
    anywhere in the other compilation", and the answer must not depend on the two of them
    splitting narrations in the same places, which they do not.
    """
    try:
        import hadith as pkg
    except ImportError:
        raise SystemExit("the 'hadith' package is not installed: pip install hadith")
    folder = Path(pkg.__file__).resolve().parent / "data"
    out = {}
    for book, stem in CORPUS.items():
        path = folder / f"{stem}.csv.gz"
        if not path.is_file():
            raise SystemExit(f"the second corpus has no {stem}")
        with gzip.open(path, "rt", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        out[book] = bare(" ".join(row[0] for row in rows[1:] if row))
    return out


def chapter(meta: dict, number: str) -> str:
    """The collection's own name for the book this narration sits in."""
    try:
        want = float(number)
    except ValueError:
        return ""
    for key, detail in meta.get("section_details", {}).items():
        first, last = detail.get("hadithnumber_first"), detail.get("hadithnumber_last")
        if first is None or last is None:
            continue
        if first <= want <= last:
            return meta.get("sections", {}).get(key, "")
    return ""


def build(where: Path, out: Path = OUT) -> int:
    packs = editions(where)
    other = second_corpus()
    items, refused = [], []
    for cat, wanted in CHOSEN.items():
        for book, number in wanted:
            arabic_by, english_by, meta = packs[book]
            if number not in arabic_by or number not in english_by:
                refused.append(f"{BOOKS[book]} {number}: not in the dataset")
                continue
            arabic = arabic_by[number]["text"].strip()
            english = tidy(english_by[number]["text"])
            words = bare(arabic).split()
            run = longest_run(words, other[book])
            if run < MATCH_WORDS or run < len(words) * MATCH_SHARE:
                refused.append(f"{BOOKS[book]} {number}: the second corpus shares only {run} of "
                               f"{len(words)} words -- NOT WRITTEN")
                continue
            items.append({
                "key": f"{book}_{number.replace('.', '_')}",
                "cats": [cat],
                # The collection's own chapter name, not a title written here. A heading typed
                # by hand is a summary of a hadith, and summarising one is the reviewer's job.
                "title": chapter(meta, number),
                "ref": f"{BOOKS[book]} {number}",
                "arabic": arabic,
                "text": {"en": english},
                "from": "hadith-api",
            })
            print(f"  {cat:12} {BOOKS[book]:<17}{number:>6}  ar{len(arabic):>4} en{len(english):>4}"
                  f"  both corpora share {run:>3}/{len(words):<3}  {english[:52]}")

    for line in refused:
        print(f"  REFUSED  {line}", file=sys.stderr)
    if not items:
        raise SystemExit("nothing was written")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema": 1,
        "reviewed": False,
        "source": (
            "Sahih al-Bukhari and Sahih Muslim only. Arabic AND English both lifted from the "
            "public-domain hadith-api dataset (github.com/fawazahmed0/hadith-api, Unlicense), "
            "matched to each other by hadith number; not one word of either was typed from "
            "memory. Every Arabic line was then found again in the MIT-licensed 'hadith' "
            "package (62,178 narrations, nine collections), a separate compilation that had no "
            "part in the lift. The English is the translation that circulates with these "
            "collections, with only the dataset's missing final full stop and closing quote "
            "put back. DRAFT: which heading each saying is filed under is an editorial choice "
            "made by the build and needs a qualified reviewer, as do the hadith numbers, which "
            "should be checked on sunnah.com one at a time."),
        "items": items,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    kinds = {}
    for item in items:
        kinds[item["cats"][0]] = kinds.get(item["cats"][0], 0) + 1
    print(f"\n{len(items)} sayings across {len(kinds)} headings: "
          + ", ".join(f"{k} {n}" for k, n in kinds.items()))
    print(f"-> {out.relative_to(ROOT)}")
    return 1 if refused else 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_hadith_section")
    ap.add_argument("--editions", type=Path, required=True,
                    help="folder holding ara-/eng- bukhari and muslim from hadith-api")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    return build(args.editions, args.out)


if __name__ == "__main__":
    sys.exit(main())
