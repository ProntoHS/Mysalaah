"""Builds assets/content/core/arabic.json and the English pack text.

Qur'anic verses come from a downloaded Uthmani text (see SOURCE below) and are copied verbatim.
The other recitations are long-established wordings, typed here for review.

Run: python3 tools/build_text.py path/to/quran.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = "Qur'anic verses (the surahs, and Ayat al-Kursi, 2:255, split at its pause marks) are the Uthmani text from The Noble Qur'an Encyclopedia (quranenc.com), obtained via the quran-json project, reproduced verbatim."

OTHER_SOURCE = "The remaining recitations (takbir, the opening dua subhanaka llahumma, tashahhud, salawat, qunut, the tasbih of ruku and sujood, rabbi ghfir li) are long-established Hanafi wordings, written as Harry supplied them to match his recordings. Rabbana atina (Qur'an 2:201) is likewise in the spelling he supplied. The prayer's steps otherwise follow quranmualim.com/arabic-prayer. DRAFT: each line still needs checking and approval by a qualified reviewer."

# Each prayer's name in Arabic, shown in the banner during a prayer.
PRAYER_NAMES = {"fajr": "الفَجْر", "dhuhr": "الظُّهْر", "asr": "العَصْر", "maghrib": "المَغْرِب", "isha": "العِشَاء"}

# Recitations that are not Qur'anic verses.
ARABIC_OTHER = {
    "takbir": ["ٱللَّهُ أَكۡبَرُ"],
    "istiftah": [
        "سُبْحَانَكَ اللَّهُمَّ وَبِحَمْدِكَ",
        "وَتَبَارَكَ اسْمُكَ وَتَعَالَى جَدُّكَ",
        "وَلَا إِلَهَ غَيْرُكَ",
    ],
    "ameen": [
        "آمِين",
    ],
    "ruku_tasbih": ["سُبۡحَانَ رَبِّيَ ٱلۡعَظِيمِ"],
    "tasmi_tahmid": ["سَمِعَ ٱللَّهُ لِمَنۡ حَمِدَهُۥ", "رَبَّنَا لَكَ ٱلۡحَمۡدُ"],
    "sujood_tasbih": ["سُبۡحَانَ رَبِّيَ ٱلۡأَعۡلَىٰ"],
    "jalsa_dua": [
        "رَبِّ اغْفِرْ لِي",
    ],
    "tashahhud": [
        "ٱلتَّحِيَّاتُ لِلَّهِ وَٱلصَّلَوَاتُ وَٱلطَّيِّبَاتُ",
        "ٱلسَّلَامُ عَلَيۡكَ أَيُّهَا ٱلنَّبِيُّ وَرَحۡمَةُ ٱللَّهِ وَبَرَكَاتُهُۥ",
        "ٱلسَّلَامُ عَلَيۡنَا وَعَلَىٰ عِبَادِ ٱللَّهِ ٱلصَّٰلِحِينَ",
        "أَشۡهَدُ أَن لَّآ إِلَٰهَ إِلَّا ٱللَّهُ وَأَشۡهَدُ أَنَّ مُحَمَّدًا عَبۡدُهُۥ وَرَسُولُهُۥ",
    ],
    "salawat": [
        "ٱللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٖ وَعَلَىٰٓ ءَالِ مُحَمَّدٖ",
        "كَمَا صَلَّيۡتَ عَلَىٰٓ إِبۡرَٰهِيمَ وَعَلَىٰٓ ءَالِ إِبۡرَٰهِيمَ إِنَّكَ حَمِيدٞ مَّجِيدٞ",
        "ٱللَّهُمَّ بَارِكۡ عَلَىٰ مُحَمَّدٖ وَعَلَىٰٓ ءَالِ مُحَمَّدٖ",
        "كَمَا بَٰرَكۡتَ عَلَىٰٓ إِبۡرَٰهِيمَ وَعَلَىٰٓ ءَالِ إِبۡرَٰهِيمَ إِنَّكَ حَمِيدٞ مَّجِيدٞ",
    ],
    "rabbana_atina": [
        "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً",
        "وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ",
    ],
    "salam": ["ٱلسَّلَامُ عَلَيۡكُمۡ وَرَحۡمَةُ ٱللَّهِ"],
    # After a fardh prayer: astaghfirullah, then the dhikr on the beads screen.
    "istighfar": [
        "أَسْتَغْفِرُ اللَّهَ",
    ],
    "dhikr_salam": [
        "اللَّهُمَّ أَنْتَ السَّلاَمُ وَمِنْكَ السَّلاَمُ",
        "تَبَارَكْتَ يَا ذَا الْجَلاَلِ وَالإِكْرَامِ",
    ],
    "subhanallah": [
        "سُبْحَانَ اللهِ",
    ],
    "alhamdulillah": [
        "ٱلْحَمْدُ لِلّٰهِ",
    ],
    "allahu_akbar": [
        "اللهُ أَكْبَرُ",
    ],
    "dhikr_tahlil": [
        "لاَ إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لاَ شَرِيكَ لَهُ،",
        "لَهُ الْمُلْكُ، وَلَهُ الْحَمْدُ،",
        "وَهُوَ عَلَى كُلِّ شَىْءٍ قَدِيرٌ",
    ],
    "qunut_1": [
        "ٱللَّهُمَّ إِنَّا نَسۡتَعِينُكَ وَنَسۡتَغۡفِرُكَ وَنُؤۡمِنُ بِكَ وَنَتَوَكَّلُ عَلَيۡكَ",
        "وَنُثۡنِي عَلَيۡكَ ٱلۡخَيۡرَ وَنَشۡكُرُكَ وَلَا نَكۡفُرُكَ",
        "وَنَخۡلَعُ وَنَتۡرُكُ مَن يَفۡجُرُكَ",
    ],
    "qunut_2": [
        "ٱللَّهُمَّ إِيَّاكَ نَعۡبُدُ وَلَكَ نُصَلِّي وَنَسۡجُدُ",
        "وَإِلَيۡكَ نَسۡعَىٰ وَنَحۡفِدُ وَنَرۡجُواْ رَحۡمَتَكَ وَنَخۡشَىٰ عَذَابَكَ",
        "إِنَّ عَذَابَكَ بِٱلۡكُفَّارِ مُلۡحِقٞ",
    ],
}

# Plain-English meaning, written for this app rather than copied from a published translation.
ENGLISH = {
    "takbir": ["God is the greatest."],
    "istiftah": [
        "Glory be to You, O God, and all praise is Yours.",
        "Blessed is Your name and exalted is Your majesty.",
        "There is no god but You.",
    ],
    "jalsa_dua": [
        "My Lord, forgive me.",
    ],
    "taawwudh_basmala": [
        "I seek refuge with God from Satan, the rejected.",
    ],
    "fatiha": [
        "In the name of God, the Most Merciful, the Most Compassionate.",
        "All praise belongs to God, Lord of all the worlds,",
        "the Most Merciful, the Most Compassionate,",
        "Master of the Day of Judgement.",
        "You alone we worship, and You alone we ask for help.",
        "Guide us along the straight path,",
        "the path of those You have blessed, not of those who earned anger, nor of those who went astray.",
    ],
    "kawthar": [
        "In the name of God, the Most Merciful, the Most Compassionate.",
        "We have surely given you abundance.",
        "So pray to your Lord and sacrifice.",
        "It is the one who hates you who is cut off.",
    ],
    "ikhlas": [
        "In the name of God, the Most Merciful, the Most Compassionate.",
        "Say: He is God, the One.",
        "God, the Eternal, on whom all depend.",
        "He does not give birth, nor was He born,",
        "and there is none comparable to Him.",
    ],
    "falaq": [
        "In the name of God, the Most Merciful, the Most Compassionate.",
        "Say: I seek refuge with the Lord of the daybreak",
        "from the harm of what He created,",
        "from the harm of darkness as it settles,",
        "from the harm of those who blow on knots,",
        "and from the harm of an envier when he envies.",
    ],
    "nas": [
        "In the name of God, the Most Merciful, the Most Compassionate.",
        "Say: I seek refuge with the Lord of people,",
        "the King of people,",
        "the God of people,",
        "from the harm of the whisperer who withdraws,",
        "who whispers into the hearts of people,",
        "from among jinn and people.",
    ],
    "ameen": [
        "O God, answer our prayer.",
    ],
    "ruku_tasbih": ["Glory to my Lord, the Most Great."],
    "tasmi_tahmid": ["God hears the one who praises Him.", "Our Lord, to You belongs all praise."],
    "sujood_tasbih": ["Glory to my Lord, the Most High."],
    "tashahhud": [
        "All greetings, prayers and good things belong to God.",
        "Peace be upon you, O Prophet, and the mercy of God and His blessings.",
        "Peace be upon us and upon the righteous servants of God.",
        "I bear witness that there is no god but God, and that Muhammad is His servant and messenger.",
    ],
    "salawat": [
        "O God, send Your grace upon Muhammad and upon the family of Muhammad,",
        "as You sent grace upon Abraham and upon the family of Abraham. You are worthy of praise, full of glory.",
        "O God, send Your blessings upon Muhammad and upon the family of Muhammad,",
        "as You blessed Abraham and the family of Abraham. You are worthy of praise, full of glory.",
    ],
    "rabbana_atina": [
        "Our Lord, give us good in this world",
        "and good in the hereafter, and protect us from the punishment of the Fire.",
    ],
    "salam": ["Peace be upon you, and the mercy of God."],
    # After a fardh prayer: astaghfirullah, then the dhikr on the beads screen.
    "istighfar": [
        "I ask God's forgiveness.",
    ],
    "dhikr_salam": [
        "O God, You are Peace and from You comes peace.",
        "Blessed are You, Owner of majesty and honour.",
    ],
    "subhanallah": [
        "Glory be to God.",
    ],
    "alhamdulillah": [
        "All praise is for God.",
    ],
    "allahu_akbar": [
        "God is the greatest.",
    ],
    "dhikr_tahlil": [
        "There is no god but God alone, with no partner.",
        "His is the dominion and His is the praise,",
        "and He has power over all things.",
    ],
    "ayat_kursi": [
        "God: there is no god but Him, the Ever-Living, the Sustainer of all.",
        "Neither drowsiness nor sleep overtakes Him.",
        "To Him belongs whatever is in the heavens and whatever is on the earth.",
        "Who could intercede with Him except by His leave?",
        "He knows what is before them and what is behind them,",
        "and they grasp nothing of His knowledge except what He wills.",
        "His Seat extends over the heavens and the earth,",
        "and guarding them does not tire Him.",
        "He is the Most High, the Tremendous.",
    ],
    "qunut_1": [
        "O God, we ask You for help, we ask Your forgiveness, we believe in You and we rely on You.",
        "We praise You for all good, we thank You and we are not ungrateful to You.",
        "We cast off and leave whoever disobeys You.",
    ],
    "qunut_2": [
        "O God, You alone we worship; for You we pray and prostrate.",
        "To You we strive and hasten. We hope for Your mercy and fear Your punishment.",
        "Your punishment surely reaches those who reject faith.",
    ],
}

# Qur'anic recitations: chapter number, and whether the basmala is recited before it.
SURAHS = {
    "fatiha": (1, False),   # the basmala is verse 1 of Al-Fatiha
    "kawthar": (108, True),
    "ikhlas": (112, True),
    "falaq": (113, True),
    "nas": (114, True),
}

# Single verses said on their own: chapter, verse. Split into lines at the verse's pause marks,
# which is where reciters pause, so each line's recording starts and ends on a real pause.
VERSES = {
    "ayat_kursi": (2, 255),
}
WAQF = re.compile(r"[\u06D6-\u06DC]")


def at_pauses(text: str) -> list[str]:
    lines, current = [], []
    for word in text.split():
        current.append(word)
        if WAQF.search(word):
            lines.append(" ".join(current))
            current = []
    if current:
        lines.append(" ".join(current))
    return lines


def build(quran_path: Path) -> None:
    q = json.loads(quran_path.read_text(encoding="utf-8"))
    basmala = q["1"][0]["text"]

    arabic = dict(ARABIC_OTHER)
    # The basmala is recited at the start of Al-Fatiha, on the screen after this one.
    arabic["taawwudh_basmala"] = ["أَعُوذُ بِٱللَّهِ مِنَ ٱلشَّيۡطَٰنِ ٱلرَّجِيمِ"]
    for key, (chapter, with_basmala) in SURAHS.items():
        verses = [a["text"] for a in q[str(chapter)]]
        arabic[key] = ([basmala] + verses) if with_basmala else verses
    for key, (chapter, number) in VERSES.items():
        arabic[key] = at_pauses(q[str(chapter)][number - 1]["text"])

    steps = json.loads((ROOT / "assets/content/steps.json").read_text(encoding="utf-8"))["steps"]
    # The intention names the prayer chosen, so the app writes it; it has no fixed text here.
    keys = {s["recitation"] for s in steps.values()} - {"intention"}
    missing = (keys - set(arabic), keys - set(ENGLISH))
    if any(missing):
        raise SystemExit(f"missing text for {missing}")
    for k in sorted(keys):
        if len(arabic[k]) != len(ENGLISH[k]):
            raise SystemExit(f"{k}: {len(arabic[k])} Arabic segments but {len(ENGLISH[k])} English")

    (ROOT / "assets/content/core/arabic.json").write_text(json.dumps({
        "schema": 1,
        "note": "Arabic is language-neutral and always bundled. Each key is a list of segments (verses or phrases). 'prayers' holds each prayer's name in Arabic, shown in the banner.",
        "sources": {"quran": SOURCE, "other": OTHER_SOURCE},
        "text": {k: arabic[k] for k in sorted(arabic)},
        "prayers": PRAYER_NAMES,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    pack_path = ROOT / "assets/content/packs/en/pack.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["hasTransliteration"] = False
    pack["transliteration"] = {}
    pack["translation"] = {k: ENGLISH[k] for k in sorted(ENGLISH)}
    pack["translationSource"] = ("Plain-English meaning written for this app, not copied from a published "
                                 "translation. DRAFT: needs review by a qualified reviewer.")
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(arabic)} recitations, {sum(len(v) for v in arabic.values())} segments")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
