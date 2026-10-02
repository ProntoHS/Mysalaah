#!/usr/bin/env python3
"""Builds the Hadith section: sayings of the Prophet, filed under the eighteen headings Harry drew.

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

A narration may be listed under several headings, and is written once carrying all of them. The
app already filed du'as this way -- `cats` is a list and the board asks whether a heading is in
it -- so this needed nothing on the app side. It matters because the alternative is choosing one
heading for a narration that plainly belongs to two, which is how a heading ends up thin and how
the same saying gets copied in twice under different keys.

ONE HEADING, ONE SUBJECT, as far as two Sahihs and my reading allow. Reaching eighteen headings
tempted this table into padding and it gave in three times, and wrote down that it had each
time: "the same, as Abu Huraira has it", "the same, as Muslim has it". Dress carried three
narrations on dragging a garment out of conceit, pairwise 0.69-0.77 alike by shared words; hajj
carried one narration twice out of the two collections; prayer carried the twenty-five and the
twenty-seven side by side, which is not a repeat but a contradiction in front of a child. None
of the existing checks caught any of it: separate hadith numbers, separate Arabic, five to a
heading. The count of five is a floor on how fast a heading comes round, not a licence to fill
it with one saying wearing different chains. There is now a test that measures the overlap.

WHAT THIS DOES NOT DO, and what a qualified reviewer still has to:

  * Check that each hadith is under the right heading, and under ALL the headings it belongs to.
    That is the one editorial act here and it is entirely mine. The numbers are in the table
    below so every choice can be looked up.
  * Check the numbering against sunnah.com. The dataset's numbers agree with sunnah.com's as
    far as spot checks go, but "as far as spot checks go" is not a citation.
  * Vouch for the translations. They are the ones that circulate with these collections
    (Muhsin Khan for Bukhari, Abdul Hamid Siddiqui for Muslim); the dataset publishes them
    under the Unlicense and every hadith site uses them, but their standing is not mine to
    assert, and neither is their accuracy.
  * Decide what belongs in front of a child. This table twice kept things out on my own
    judgement and Harry twice overruled it, correctly both times. First it held back slavery and
    marital intimacy altogether. Then it kept the explicit ones -- the washing that is obligatory
    after intercourse, 'azl, a wife called to her husband's bed, "until he has tasted her
    sweetness" -- on the grounds that the language was explicit rather than instructive. That
    was a distinction I invented. The frankness in these narrations is there because the law
    needs it to be: a ruling about when a bath becomes compulsory cannot be made delicately and
    still be a ruling. They are printed in every copy of Bukhari and Muslim a family owns, and
    leaving them out was me editing the two Sahihs on an authority I do not have. NOTHING is now
    held back on grounds of subject or language; the only filters left are the two Sahihs, the
    two-corpus check, and length.

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
        ("bukhari", "6309"),    # more pleased than a man who finds his lost camel
        ("muslim", "6970"),     # My mercy excels My wrath
        ("muslim", "470"),      # brought out of the Fire and into the Garden
    ],
    "prayer": [
        ("bukhari", "528"),     # a river at your door, bathed in five times a day
        ("muslim", "550"),      # the five prayers are an expiation
        ("bukhari", "723"),     # straighten the rows; it is part of the prayer being right
        ("muslim", "256"),      # prayer at its time, and kindness to parents
        ("muslim", "1755"),     # make Witr the end of the night
        # Muslim 1478 was here as well -- congregation twenty-seven times over, against this
        # one's twenty-five. Both sahih, and the scholars reconcile them; a board dealing two
        # at a time can deal exactly this pair and ask a seven-year-old which number is right.
        # That is a worse failure than a repeat, so the heading carries one of them.
        ("bukhari", "646"),     # in congregation, twenty-five times over
        ("muslim", "912"),      # he who blesses me once
    ],
    "purification": [
        ("bukhari", "245"),     # the siwak on rising at night
        ("muslim", "578"),      # ablution done well
        ("bukhari", "6954"),    # no prayer until the ablution is made anew
        ("muslim", "543"),      # ablution, then prayer with humility
        ("bukhari", "248"),     # how he washed after intimacy
        ("bukhari", "3328"),    # Umm Sulaim asks, and is answered plainly
        ("muslim", "591"),      # the tooth-stick on coming in
        ("bukhari", "291"),     # when the washing becomes obligatory
        ("muslim", "776"),      # and on a seminal emission
        ("bukhari", "270"),     # he went round his wives, and was in ihram by morning
        ("bukhari", "5854"),    # starting from the right -- also under dress
    ],
    "fasting": [
        ("bukhari", "38"),      # whoever fasts Ramadan out of faith and hope
        ("bukhari", "3277"),    # the gates opened, the gates closed
        ("bukhari", "6057"),    # giving up food is not the point if lying is not given up
        ("bukhari", "1957"),    # hasten the breaking of the fast
        ("bukhari", "2017"),    # look for the Night of Qadr in the odd nights
        ("muslim", "2550"),     # the meal before dawn
        ("muslim", "2676"),     # not on the two Eids
        ("muslim", "2585"),     # he kissed his wives while fasting
        ("bukhari", "1930"),    # bathed at dawn, not from a dream, and kept the fast
    ],
    "charity": [
        ("bukhari", "1417"),    # even half a date
        ("muslim", "6592"),     # charity does not decrease wealth
        ("muslim", "2386"),     # the upper hand, and begin at home
        ("muslim", "2328"),     # every act of goodness is sadaqa
        ("bukhari", "6715"),    # freeing a slave, limb for limb
        ("muslim", "2311"),     # of everything you spend, what you spend on your family
        ("muslim", "6690"),     # meeting your brother with a cheerful face
    ],
    "hajj": [
        ("bukhari", "1521"),    # returns as if born anew
        ("bukhari", "1773"),    # Umra is an expiation; Hajj Mabrur, nothing but Paradise
        ("bukhari", "1549"),    # the Talbiya, with its meaning
        ("bukhari", "5617"),    # Zamzam
        # Muslim 3289 was here, and the comment against it read "the same, as Muslim has it":
        # the same narration, the same narrator, out of the other collection. Dropped.
        ("bukhari", "1597"),    # Umar to the Black Stone: a stone, and he kisses it regardless
        ("bukhari", "1552"),    # the Talbiya once he was mounted
    ],
    "knowledge": [
        ("bukhari", "5028"),    # those who learn the Qur'an and teach it
        ("bukhari", "71"),      # when Allah wants good for someone
        ("bukhari", "106"),     # do not tell a lie against me
        ("bukhari", "5033"),    # commit yourself to the Qur'an
        ("bukhari", "75"),      # O Allah, teach him the Book
        # 109 was here -- ascribing to the Prophet what he did not say. The same ruling as 106
        # above it, from a different narrator, and 54% alike by the overlap measure.
        ("bukhari", "1409"),    # no envy except in two: wealth spent right, wisdom taught on
        ("bukhari", "5040"),    # the last two verses of al-Baqara at night
    ],
    "character": [
        ("bukhari", "6035"),    # the best among you are the best in character
        ("bukhari", "6114"),    # the strong one is the one who holds himself in anger
        ("bukhari", "6136"),    # his neighbour, his guest, and speaking good or keeping silent
        ("bukhari", "7376"),    # no mercy for those who show none
        ("bukhari", "6094"),    # truthfulness leads to righteousness
        ("muslim", "4298"),     # he who strikes his slave: the expiation is to free him
        ("bukhari", "2550"),    # a slave who serves well and worships well: two rewards
    ],
    "family": [
        ("bukhari", "5971"),    # your mother, your mother, your mother, then your father
        ("bukhari", "5200"),    # all of you are guardians
        ("bukhari", "5995"),    # daughters, and what they are to their father
        ("bukhari", "5199"),    # your body, your eyes and your wife each have a right over you
        ("bukhari", "5192"),    # the optional fast, and her husband at home
        ("muslim", "3499"),     # freed her, then married her: two rewards
        ("muslim", "3400"),     # young men, those who can support a wife should marry
        ("bukhari", "3237"),    # when he calls her to his bed
        ("muslim", "3529"),     # not until he has tasted her sweetness
        ("muslim", "3561"),     # 'azl, and he did not forbid it
    ],
    "community": [
        ("bukhari", "6951"),    # a Muslim is a brother of another Muslim
        ("bukhari", "6011"),    # the believers, resembling one body
        # 6076 was here and under justice -- "do not hate one another, nor be jealous... be
        # brothers". Nearly all of it is inside 6064 below, which says the same and then adds
        # suspicion and spying. One narration, not two.
        ("bukhari", "481"),     # believers to one another like the bricks of a wall
        ("bukhari", "6064"),    # beware of suspicion
        ("muslim", "4326"),     # freeing your share of a slave leaves you owing the rest
    ],
    "daily": [
        ("muslim", "5269"),     # say the Name, eat with your right hand, eat what is near you
        ("bukhari", "6405"),    # Subhan Allah wa bihamdihi, a hundred times
        ("muslim", "6932"),     # Alhamdulillah over a mouthful and a drink
        ("bukhari", "6312"),    # lying down, and waking
        ("bukhari", "7563"),    # two words, light on the tongue and heavy in the balance
        ("muslim", "5265"),     # the right hand, for eating and for drinking
    ],
    "hereafter": [
        ("bukhari", "6416"),    # be in this world as a stranger or a traveller
        ("muslim", "4223"),     # three things that do not end
        ("bukhari", "6488"),    # nearer to you than your shoelace
        ("muslim", "7417"),     # the world, to a believer
        ("bukhari", "6479"),    # the one who remembers Allah until his eyes brim over
        ("bukhari", "6412"),    # two blessings many are cheated of: health, and time
    ],
    # The six Harry added. A narration listed under more than one heading is written under each
    # of them, and the build folds the repeats into one saying carrying both -- which is the
    # right way round: a hadith about a wife's right over her husband genuinely belongs under
    # Family and under Marriage, and filing it twice would put the same words on one screen.
    "marriage": [
        ("bukhari", "5090"),    # married for four things; take the one with religion
        ("muslim", "3514"),     # accept the invitation to a wedding
        ("muslim", "3400"),     # young men who can support a wife should marry
        ("muslim", "3529"),     # not until he has tasted her sweetness
        ("muslim", "3561"),     # 'azl, and he did not forbid it
        ("bukhari", "3237"),    # when he calls her to his bed
        ("bukhari", "5199"),    # your wife has a right over you
        ("muslim", "3499"),     # freed her, then married her: two rewards
    ],
    "business": [
        ("bukhari", "2076"),    # mercy on the man who is easy buying, selling and asking back
        ("muslim", "284"),      # the wet corn under the dry: he who deceives is not of me
        ("bukhari", "2111"),    # both may still change their minds until they part
        ("bukhari", "2072"),    # no better meal than one earned by your own hands
        ("muslim", "2386"),     # the upper hand, and begin at home
    ],
    "justice": [
        ("bukhari", "2444"),    # help your brother, oppressor or oppressed -- by stopping him
        ("bukhari", "6871"),    # the great sins, and bearing false witness among them
        ("bukhari", "6951"),    # neither oppress him nor hand him to an oppressor
        ("bukhari", "6534"),    # settle what you owe your brother before there is no money left
        ("bukhari", "6064"),    # beware of suspicion
    ],
    "greetings": [
        ("bukhari", "6231"),    # the young greet the old, the passing greet the sitting
        # Muslim 5646 was here: the rider greets the one on foot, the pedestrian the seated,
        # the small group the large. Which is 6231 above, out of the other collection.
        ("muslim", "194"),      # spread the salaam and it will make you love one another
        ("muslim", "6690"),     # meeting your brother with a cheerful face
        ("bukhari", "6136"),    # his neighbour, his guest, and speaking good or keeping silent
        ("bukhari", "1216"),    # he returned the greeting until prayer took all of him
    ],
    # Six, and deliberately six different things. The first cut of this heading was five, of
    # which THREE were the same narration -- Bukhari 5783, 5788 and 3665, all on dragging a
    # garment out of conceit, pairwise 0.69 to 0.77 alike by shared words. They are separate
    # hadith numbers with separate Arabic, so the no-duplicates check passed them and the
    # count-of-five check passed them, and the comment against 5788 in this very table said
    # "the same, as Abu Huraira has it". I padded the heading to reach five and wrote down
    # that I had. A heading dealing two at a time out of five, three of which are
    # interchangeable, shows a child the same point twice as a matter of course.
    #
    # So: one on conceit, not three, and the rest on what he liked to wear, the right shoe
    # first, and the silk. 5854 is filed under purification as well -- starting from the right
    # is the same habit the wu'du section teaches, and a narration belonging to two headings is
    # now something this builder can say.
    "dress": [
        ("bukhari", "5783"),    # Allah will not look at the one who drags his garment in pride
        ("bukhari", "5813"),    # the garment he loved best to wear: the Hibra
        ("bukhari", "5855"),    # the right shoe on first, and off last
        ("bukhari", "5854"),    # starting from the right: ablution, combing, shoes
        ("bukhari", "3249"),    # the silk that astonished them, and what is better than it
        ("muslim", "5422"),     # the silk given away, and torn up for head coverings
    ],
    "health": [
        ("bukhari", "6412"),    # two blessings many are cheated of: health, and time
        ("muslim", "5766"),     # nigella seed, a remedy for everything but death
        ("bukhari", "5682"),    # he liked sweet things, and honey
        ("bukhari", "5732"),    # dying of the plague
        ("bukhari", "3616"),    # visiting the sick: no harm will come to you
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


# The dataset's own translations, by the mat's language code. English is required; the rest are
# lifted if the folder has them and quietly skipped if it has not, so the build still runs for
# somebody who only fetched the two the header used to list.
#
# These are the ONLY languages being added, because these are the ones the dataset publishes for
# both collections. The mat also speaks Spanish, Hindi and Chinese, and there is no Spanish,
# Hindi or Chinese Bukhari or Muslim in this corpus or in any other I can reach. Those three
# fall back to English on screen, which is the same rule the du'as have always used. Writing
# them myself is the one thing the top of this file says never to do: a hadith translation is
# not a phrase to render, it is a published work with a translator's name on it.
TONGUES = {"eng": "en", "fra": "fr", "urd": "ur"}


def editions(where: Path) -> dict:
    """The dataset files, as {collection: (arabic by number, {lang: by number}, meta)}."""
    out = {}
    for book in BOOKS:
        path = where / f"ara-{book}.json"
        if not path.is_file():
            raise SystemExit(f"missing {path}\nSee the header of this file for how to fetch it.")
        arabic = json.loads(path.read_text(encoding="utf-8"))
        said, meta = {}, None
        for tongue, lang in TONGUES.items():
            side = where / f"{tongue}-{book}.json"
            if not side.is_file():
                if lang == "en":
                    raise SystemExit(f"missing {side}\nSee the header of this file.")
                print(f"  (no {side.name}; {lang} will fall back to English)", file=sys.stderr)
                continue
            got = json.loads(side.read_text(encoding="utf-8"))
            said[lang] = {str(h["hadithnumber"]): h for h in got["hadiths"]}
            if lang == "en":
                meta = got["metadata"]
        out[book] = ({str(h["hadithnumber"]): h for h in arabic["hadiths"]}, said, meta)
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
    # Which headings each narration was listed under, in the order the headings are drawn.
    under: dict = {}
    for cat, wanted in CHOSEN.items():
        for book, number in wanted:
            under.setdefault((book, number), []).append(cat)

    items, refused, written = [], [], set()
    for cat, wanted in CHOSEN.items():
        for book, number in wanted:
            if (book, number) in written:
                continue            # already written, with all of its headings on it
            written.add((book, number))
            arabic_by, said_by, meta = packs[book]
            if number not in arabic_by or number not in said_by["en"]:
                refused.append(f"{BOOKS[book]} {number}: not in the dataset")
                continue
            arabic = arabic_by[number]["text"].strip()
            english = tidy(said_by["en"][number]["text"])
            # Every translation the dataset has for this narration, matched to the English by
            # hadith number -- the same join the English itself is made with. A translation
            # the dataset is missing for one narration is left out of that one rather than
            # failing the build: the screen falls back to English per saying, not per section.
            # Tested BEFORE tidy(), not after. tidy() mends a narration the dataset cut the
            # full stop off, so handed an empty string it returns "." -- and "." is not blank,
            # so an empty translation sailed through as a translation. Bukhari 7563 reached
            # the file with its whole Urdu being a full stop, and Muslim 3499 its French.
            said = {}
            for lang, by in said_by.items():
                raw = by[number]["text"] if number in by else ""
                if raw.strip():
                    said[lang] = tidy(raw)
            words = bare(arabic).split()
            run = longest_run(words, other[book])
            if run < MATCH_WORDS or run < len(words) * MATCH_SHARE:
                refused.append(f"{BOOKS[book]} {number}: the second corpus shares only {run} of "
                               f"{len(words)} words -- NOT WRITTEN")
                continue
            items.append({
                "key": f"{book}_{number.replace('.', '_')}",
                "cats": under[(book, number)],
                # The collection's own chapter name, not a title written here. A heading typed
                # by hand is a summary of a hadith, and summarising one is the reviewer's job.
                "title": chapter(meta, number),
                "ref": f"{BOOKS[book]} {number}",
                "arabic": arabic,
                "text": said,
                "from": "hadith-api",
            })
            print(f"  {','.join(under[(book, number)]):22} {BOOKS[book]:<17}{number:>6}  "
                  f"ar{len(arabic):>4} {'+'.join(sorted(said)):>8}  "
                  f"share {run:>3}/{len(words):<3}  {english[:34]}")

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
        for cat in item["cats"]:
            kinds[cat] = kinds.get(cat, 0) + 1
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
