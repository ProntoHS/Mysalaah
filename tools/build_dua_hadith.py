#!/usr/bin/env python3
"""Builds the du'as that come from hadith rather than the Qur'an.

    python3 tools/build_dua_hadith.py --second ~/hadith-api/editions

The Qur'anic du'as are copied out of the Qur'an already on the mat, so not one word of Arabic is
typed in tools/build_duas.py. The du'as for waking, for eating, for setting off are not in the
Qur'an, and the same rule has to hold for them: nothing here is typed from memory either.

How that is managed. Each du'a below carries two ANCHORS -- a few words at its start and a few at
its end. The anchors are only a way of pointing; they are never what gets stored. This looks for
a narration containing both, in that order, and lifts the text BETWEEN them out of the corpus,
vowels and all. So the Arabic that reaches the screen is the corpus's own, letter for letter, and
the worst a wrong anchor can do is point at the wrong stretch -- which is visible, because every
lift is printed.

Why anchors instead of typing the du'a out and checking it. That was tried first and it fails in
a way worth recording: the wording for leaving the house came out as
"بسم الله توكلت على الله ولا حول ولا قوة إلا بالله" and was not found, because the collections have
"لا حول" there and not "ولا حول". One letter. Typing it out and searching for it finds nothing and
tells you nothing; anchoring on the opening and lifting the rest gives you what is actually
written. The same check caught the long morning wording, which is not in the collections at all
in the form it is usually quoted.

Two corpora, because one dataset can carry a typo and a du'a is not something to take on a single
source:

  * the MIT-licensed 'hadith' package on PyPI, 62,178 narrations across nine collections, which
    is where the text is lifted from
  * the public-domain hadith-api dataset (github.com/fawazahmed0/hadith-api, Unlicense), which
    had no part in the lift, and in which every lifted line must also appear

A du'a that cannot be lifted, or that the second corpus does not have, is NOT WRITTEN. It is
printed as a refusal and the rest carry on. Nothing is patched to make the count come out.

What this does not check: that the reference is right, that the narration is sound, or that a
du'a has been put under the right heading. The English is a plain rendering written for this app,
not a published translation. All of that needs a qualified reviewer, which is why the file it
writes says reviewed: false.
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import importlib.util
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "content" / "duas" / "hadith.json"

_spec = importlib.util.spec_from_file_location("check_hadith", Path(__file__).parent / "check_hadith.py")
_ch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ch)
bare = _ch.bare

CAP = 420          # characters; a lift longer than this has run past the du'a into the story


# key, the kinds it belongs under, a title, the two anchors, and the English.
# A du'a can sit under more than one kind: the one said after a prayer is both a prayer du'a and
# a du'a of thanks, and the one said over food is also one of thanks.
DUAS = [
    dict(key="morning_kingdom", cats=("morning",), title="Morning has come, and the dominion is Allah's",
         start="أصبحنا وأصبح الملك لله", end="الملك لله",
         en="We have entered upon the morning, and the dominion belongs to Allah."),
    dict(key="evening_kingdom", cats=("evening",), title="Evening has come, and the dominion is Allah's",
         start="أمسينا وأمسى الملك لله", end="وحده لا شريك له",
         en="We have entered upon the evening, and the dominion belongs to Allah. Praise "
            "belongs to Allah. There is no god but Allah alone, who has no partner."),
    dict(key="by_you_we_wake", cats=("morning", "evening"), title="By You we wake and by You we sleep",
         start="اللهم بك أصبحنا وبك أمسينا", end="وإليك المصير",
         en="O Allah, by You we enter the morning and by You we enter the evening; by You we "
            "live and by You we die, and to You is the return."),
    dict(key="sleep_in_your_name", cats=("sleep",), title="In Your name I die and I live",
         start="باسمك اللهم أموت وأحيا", end="أموت وأحيا",
         en="In Your name, O Allah, I die and I live."),
    dict(key="sleep_your_name_live", cats=("sleep",), title="In Your name I live and I die",
         start="اللهم باسمك أحيا وباسمك أموت", end="وباسمك أموت",
         en="O Allah, in Your name I live and in Your name I die."),
    dict(key="waking_praise", cats=("waking",), title="Praise to Him who gave us life again",
         start="الحمد لله الذي أحيانا", end="وإليه النشور",
         en="Praise belongs to Allah, who gave us life after He had caused us to die, and to "
            "Him is the rising."),
    dict(key="waking_in_the_night", cats=("waking", "general"), title="Waking in the night",
         start="لا إله إلا الله وحده لا شريك له له الملك", end="إلا بالله",
         en="There is no god but Allah alone, who has no partner. His is the dominion and His "
            "is the praise, and He has power over all things. Glory be to Allah, and praise "
            "belongs to Allah, and Allah is greatest, and there is no power and no strength "
            "except by Allah."),
    dict(key="after_eating", cats=("food", "gratitude"), title="After eating",
         start="الحمد لله الذي أطعمني هذا", end="ولا قوة",
         en="Praise belongs to Allah, who fed me this and provided it for me with no strength "
            "or power of my own."),
    dict(key="bless_this_food", cats=("food",), title="Bless this for us",
         start="اللهم بارك لنا فيه", end="خيرا منه",
         en="O Allah, bless it for us and feed us better than it."),
    dict(key="entering_the_house", cats=("home",), title="Going in",
         start="اللهم إني أسألك خير المولج", end="ربنا توكلنا",
         en="O Allah, I ask You for the best of entrances and the best of exits. In the name of "
            "Allah we enter, and in the name of Allah we leave, and upon Allah our Lord we rely."),
    dict(key="leaving_the_house", cats=("home", "protection"), title="Setting out",
         start="بسم الله توكلت على الله", end="إلا بالله",
         en="In the name of Allah. I rely upon Allah. There is no power and no strength except "
            "by Allah."),
    dict(key="entering_the_mosque", cats=("mosque",), title="Going into the mosque",
         start="اللهم افتح لي أبواب رحمتك", end="أبواب رحمتك",
         en="O Allah, open for me the doors of Your mercy."),
    dict(key="leaving_the_mosque", cats=("mosque",), title="Coming out of the mosque",
         start="اللهم إني أسألك من فضلك", end="من فضلك",
         en="O Allah, I ask You of Your bounty."),
    dict(key="setting_off", cats=("travel",), title="Setting off on a journey",
         start="اللهم إنا نسألك في سفرنا هذا", end="ما ترضى",
         en="O Allah, we ask You on this journey of ours for righteousness and mindfulness of "
            "You, and for deeds that please You."),
    dict(key="ease_the_journey", cats=("travel",), title="Make the journey easy",
         start="اللهم هون علينا سفرنا هذا", end="عنا بعده",
         en="O Allah, make this journey of ours easy for us, and fold up its distance for us."),
    dict(key="companion_on_the_road", cats=("travel", "family"), title="Companion on the road",
         start="اللهم أنت الصاحب في السفر", end="في الأهل",
         en="O Allah, You are the companion on the journey and the guardian of the family left "
            "behind."),
    dict(key="perfect_words", cats=("protection", "sleep"), title="The perfect words of Allah",
         start="أعوذ بكلمات الله التامات", end="من شر ما خلق",
         en="I take refuge in the perfect words of Allah from the evil of what He has created."),
    dict(key="from_worry", cats=("worry",), title="From worry and grief",
         start="اللهم إني أعوذ بك من الهم", end="وغلبة الرجال",
         en="O Allah, I take refuge in You from worry and grief, from helplessness and idleness, "
            "from cowardice and miserliness, from being weighed down by debt and overpowered by "
            "men."),
    dict(key="take_away_the_harm", cats=("health",), title="Take away the harm",
         start="أذهب الباس رب الناس", end="لا يغادر سقما",
         en="Take away the harm, Lord of mankind, and heal; You are the Healer. There is no "
            "healing but Your healing -- a healing that leaves no illness behind."),
    dict(key="ask_the_lord_of_the_throne", cats=("health",), title="For somebody who is ill",
         start="أسأل الله العظيم رب العرش العظيم", end="أن يشفيك",
         en="I ask Allah the Mighty, Lord of the Mighty Throne, to heal you."),
    dict(key="help_me_remember_you", cats=("gratitude", "prayer"), title="Help me to remember You",
         start="اللهم أعني على ذكرك", end="وحسن عبادتك",
         en="O Allah, help me to remember You, to thank You, and to worship You well."),
    dict(key="benefit_me", cats=("knowledge",), title="Benefit me by what You taught me",
         start="اللهم انفعني بما علمتني", end="وزدني علما",
         en="O Allah, benefit me by what You have taught me, teach me what benefits me, and "
            "increase me in knowledge."),
    dict(key="best_way_to_ask_pardon", cats=("forgiveness", "morning", "evening"),
         title="The best way of asking pardon",
         start="اللهم أنت ربي لا إله إلا أنت خلقتني", end="إلا أنت",
         en="O Allah, You are my Lord. There is no god but You. You created me and I am Your "
            "servant, and I hold to Your covenant and Your promise as much as I can. I "
            "acknowledge Your favour upon me and I acknowledge my sin; forgive me, for none "
            "forgives sins but You."),
    # --- added so no kind has fewer than three: with two shown at a time, a kind holding only
    # two shows the same pair every visit and the shuffling has nothing to do.
    dict(key="no_harm_with_his_name", cats=("protection", "morning", "evening"),
         title="With His name nothing can harm",
         start="بسم الله الذي لا يضر مع اسمه شيء", end="السميع العليم",
         en="In the name of Allah, with whose name nothing on earth or in heaven can cause "
            "harm, and He is the All-Hearing, the All-Knowing."),
    dict(key="guidance_and_enough", cats=("guidance", "general"),
         title="Guidance, mindfulness and enough",
         start="اللهم إني أسألك الهدى والتقى", end="والغنى",
         en="O Allah, I ask You for guidance, mindfulness of You, restraint, and sufficiency."),
    dict(key="content_with_allah", cats=("morning", "evening", "gratitude"),
         title="Content with Allah as Lord",
         start="رضيت بالله ربا", end="نبيا",
         en="I am content with Allah as Lord, with Islam as religion, and with Muhammad as "
            "Prophet."),
    dict(key="wellbeing_in_my_body", cats=("health", "morning", "evening"),
         title="Wellbeing in body, hearing and sight",
         start="اللهم عافني في بدني", end="في بصري",
         en="O Allah, grant me wellbeing in my body. O Allah, grant me wellbeing in my "
            "hearing. O Allah, grant me wellbeing in my sight."),
    dict(key="waking_restored", cats=("waking", "gratitude"),
         title="He gave me back my soul",
         start="الحمد لله الذي عافاني في جسدي", end="بذكره",
         en="Praise belongs to Allah, who restored my body to health, returned my soul to me, "
            "and permitted me to remember Him."),
    dict(key="opening_the_prayer", cats=("prayer",), title="At the opening of the prayer",
         start="اللهم باعد بيني وبين خطاياي", end="والبرد",
         en="O Allah, put distance between me and my sins as You have put distance between "
            "east and west. O Allah, cleanse me of my sins as a white garment is cleansed of "
            "dirt. O Allah, wash me of my sins with snow and water and hail."),
    dict(key="from_the_grave_and_the_fire", cats=("prayer", "protection"),
         title="Refuge from the grave and the fire",
         start="اللهم إني أعوذ بك من عذاب القبر وعذاب النار", end="المسيح الدجال",
         en="O Allah, I take refuge in You from the punishment of the grave and the punishment "
            "of the Fire, from the trial of living and of dying, and from the trial of the "
            "false messiah."),
    dict(key="mosque_refuge", cats=("mosque", "protection"),
         title="Refuge on going in",
         start="أعوذ بالله العظيم وبوجهه الكريم", end="الشيطان الرجيم",
         en="I take refuge in Allah the Mighty, in His noble face and His eternal authority, "
            "from the outcast devil."),
    dict(key="spare_me_that_day", cats=("sleep",), title="Lying down",
         start="اللهم قني عذابك يوم تبعث", end="عبادك",
         en="O Allah, spare me Your punishment on the day You raise up Your servants."),
    dict(key="coming_home", cats=("travel", "gratitude"), title="Coming back",
         start="آيبون تائبون عابدون", end="حامدون",
         en="Returning, repenting, worshipping, and praising our Lord."),
    dict(key="knowledge_that_does_not_help", cats=("knowledge",),
         title="From knowledge that is no use",
         start="اللهم إني أعوذ بك من علم لا ينفع", end="لا يخشع",
         en="O Allah, I take refuge in You from knowledge that is of no benefit and from a "
            "heart that is not humbled."),
    dict(key="feed_the_one_who_fed_me", cats=("food", "gratitude"),
         title="For whoever fed you",
         # end anchor is "أسقاني", not "سقاني": Muslim has وَأَسْقِ مَنْ أَسْقَانِي and the alif is
         # not one of the letters bare() folds, so the shorter spelling finds nothing.
         start="اللهم أطعم من أطعمني", end="أسقاني",
         en="O Allah, feed the one who fed me and give drink to the one who gave me drink."),
    dict(key="breaking_the_fast", cats=("food", "gratitude"), title="Breaking the fast",
         start="ذهب الظمأ وابتلت العروق", end="إن شاء الله",
         en="The thirst has gone, the veins are moistened, and the reward is certain, if Allah "
            "wills."),
    dict(key="from_the_house_falling", cats=("home", "protection"),
         title="From collapse, falling and fire",
         start="اللهم إني أعوذ بك من الهدم", end="والهرم",
         en="O Allah, I take refuge in You from being crushed, from falling, and from frailty."),
    dict(key="much_good_praise", cats=("prayer", "gratitude"),
         title="Praise, much and good",
         start="الحمد لله حمدا كثيرا طيبا مباركا", end="مباركا فيه",
         en="Praise belongs to Allah -- much praise, good and blessed."),
]


def bare_map(text: str) -> tuple[str, list[int]]:
    """bare(), plus where each character of the result came from in the original.

    Needed because the corpus is vowelled and bare() is not: without the map, a match found in
    the stripped text cannot be cut back out of the real one with its vowels on.
    """
    out, where = [], []
    for i, c in enumerate(unicodedata.normalize("NFC", text)):
        if c in _ch.DROP or c in _ch.PUNCT:
            continue
        for one, other in _ch.SAME:
            if c == one:
                c = other
                break
        if c == "":
            continue
        if c.isspace():
            if out and out[-1] == " ":
                continue
            out.append(" ")
        else:
            out.append(c)
        where.append(i)
    s = "".join(out)
    a, b = 0, len(s)
    while a < b and s[a] == " ":
        a += 1
    while b > a and s[b - 1] == " ":
        b -= 1
    return s[a:b], where[a:b]


def agrees_with_bare() -> None:
    """The map must produce exactly what the rest of the project's bare() produces.

    If these two ever drift, every lift is cut at the wrong place and nothing else here notices.
    """
    for sample in ("حَدَّثَنَا عُثْمَانُ", "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ", "  a  b  ", "أ إ آ ٱ ى ة"):
        mine = bare_map(sample)[0]
        if mine != bare(sample):
            raise SystemExit(f"bare_map has drifted from bare(): {mine!r} != {bare(sample)!r}")


def lift(text: str, start: str, end: str) -> str | None:
    """The stretch of `text` from `start` to the end of `end`, with its vowels."""
    b, m = bare_map(text)
    s, e = bare(start), bare(end)
    i = b.find(s)
    if i < 0:
        return None
    # From `i`, not from the end of the start anchor: a short du'a's two anchors overlap, and
    # for the shortest of all they are the same words. What matters is that the end anchor
    # finishes at or after the start anchor does, so the lift never runs backwards.
    j = b.find(e, i)
    while j >= 0 and j + len(e) < i + len(s):
        j = b.find(e, j + 1)
    if j < 0:
        return None
    if (j + len(e)) - i > CAP:
        return None
    stop = m[j + len(e) - 1] + 1
    # The marks that sit ON the last letter follow it in the string and are dropped by bare(),
    # so without this the lift ends one vowel short.
    while stop < len(text) and text[stop] in _ch.DROP:
        stop += 1
    return text[m[i]:stop]


# Only the collections BOTH corpora carry, strongest first. The lifting corpus also holds
# Musnad Ahmad and Sunan al-Darami, and the checking one does not -- so a wording lifted from
# either of those could only be "confirmed" by turning up somewhere else by chance, which is no
# confirmation at all. They are left out rather than checked against nothing.
SHARED = (
    ("Sahih_Bukhari", "Sahih al-Bukhari"),
    ("Sahih_Muslim", "Sahih Muslim"),
    ("Sunan_Abu_Dawud", "Sunan Abu Dawud"),
    ("Sunan_al_Tirmidhi", "Jami` at-Tirmidhi"),
    ("Sunan_al-Nasai", "Sunan an-Nasa'i"),
    ("Sunan_Ibn_Maja", "Sunan Ibn Majah"),
    ("Maliks_Muwatta", "Muwatta Malik"),
)


def narrations() -> list[tuple[str, str]]:
    try:
        import hadith
    except ImportError:
        raise SystemExit("needs the corpus to lift from: pip install hadith")
    folder = Path(hadith.__file__).parent / "data"
    rows = []
    for stem, named in SHARED:
        path = folder / f"{stem}.csv.gz"
        if not path.is_file():
            raise SystemExit(f"the hadith package is missing {path.name}")
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if row:
                    rows.append((named, row[0]))
    if not rows:
        raise SystemExit(f"the hadith package has no data in {folder}")
    return rows


def second_corpus(folder: Path) -> str:
    """The other dataset, as one stripped string to look lines up in."""
    files = sorted(folder.glob("ara-*.json"))
    if not files:
        raise SystemExit(
            f"No second corpus in {folder}. Fetch the Arabic editions of hadith-api first:\n"
            "  for e in bukhari muslim abudawud tirmidhi nasai ibnmajah; do\n"
            "    curl -sSo ara-$e.json "
            "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions/ara-$e.json\n"
            "  done")
    parts = []
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("hadiths", [])
        if not rows:
            raise SystemExit(f"{path.name} holds no narrations -- a failed download?")
        for row in rows:
            parts.append(str(row.get("text", "")))
    return bare(" || ".join(parts))


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_dua_hadith")
    ap.add_argument("--second", type=Path, required=True,
                    help="folder holding the other dataset's ara-*.json editions")
    ap.add_argument("--dry-run", action="store_true", help="say what was found, write nothing")
    args = ap.parse_args()

    agrees_with_bare()
    rows = narrations()
    print(f"lifting from {len(rows)} narrations")
    other = second_corpus(args.second)
    print(f"checking against a second corpus of {len(other):,} characters\n")

    built, refused = [], []
    for spec in DUAS:
        got = where = None
        for book, text in rows:
            got = lift(text, spec["start"], spec["end"])
            if got:
                where = book
                break
        if not got:
            refused.append((spec["key"], "no narration holds both anchors, in that order"))
            continue
        if bare(got) not in other:
            refused.append((spec["key"], "the second corpus does not have this wording"))
            continue
        built.append({
            "key": spec["key"],
            "cats": list(spec["cats"]),
            "title": spec["title"],
            "ref": where,
            "arabic": got,
            "text": {"en": spec["en"]},
            "from": "hadith",
        })
        print(f"  {spec['key']:26s} {where:24s} {len(got):3d} chars")
        print(f"      {got[:88]}")

    print()
    for key, why in refused:
        print(f"  REFUSED  {key}: {why}. Nothing written for it.", file=sys.stderr)

    if args.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema": 1,
        "reviewed": False,
        "source": (
            "Arabic lifted verbatim from the MIT-licensed 'hadith' package (62,178 narrations, "
            "nine collections) between two anchors, and each line then found again in the "
            "public-domain hadith-api dataset (github.com/fawazahmed0/hadith-api, Unlicense), "
            "which had no part in the lift. Not one word was typed from memory. English: a "
            "plain rendering written for this app, not a published translation. DRAFT: the "
            "English, the choice of where each du'a starts and stops, and which kind each one "
            "is filed under all need a qualified reviewer. 'ref' names the collection the "
            "wording was lifted from, not a hadith number -- those need checking on sunnah.com "
            "one at a time."),
        "items": built,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n{len(built)} du'as -> {OUT.relative_to(ROOT)}"
          + (f", {len(refused)} refused" if refused else ""))
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
