"""Builds the pool of short sayings shown when a prayer finishes.

The Arabic is copied verbatim from a public-domain hadith dataset (Unlicense) and cut down to the
saying itself, the part inside the quotation marks, so only the Prophet's words are shown and not
the chain of narrators. Each one keeps its canonical reference, e.g. Sahih al-Bukhari 13, so it can
be checked against sunnah.com or any printed edition.

The English is a plain rendering written for this app. The English translations carried by
sunnah.com are modern copyrighted works and are deliberately not used.

Superseded as a builder -- running it will not write anything. The tables below are kept as
the record of which saying was picked and what English was written for it. To check the file
as it stands, run tools/check_hadith.py.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/content/daily/hadith.json"

SOURCE = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-{collection}.json"
COLLECTIONS = {"bukhari": "Sahih al-Bukhari", "muslim": "Sahih Muslim"}
QUOTE = re.compile(r'"\u200f?(.+?)\u200f?"', re.S)

# collection, number -> a plain English rendering of the saying, written for this app.
CHOSEN = [
    ("bukhari", 13, "None of you truly believes until he loves for his brother what he loves "
                    "for himself."),
    ("bukhari", 11, "A Muslim is one from whose tongue and hand other Muslims are safe."),
    ("bukhari", 69, "Make things easy and do not make them hard. Give good news and do not "
                    "drive people away."),
    ("bukhari", 5997, "Whoever shows no mercy will be shown no mercy."),
    ("bukhari", 6114, "The strong man is not the one who wrestles well. The strong man is the "
                      "one who controls himself when he is angry."),
    ("bukhari", 48, "Abusing a Muslim is wrongdoing, and fighting him is disbelief."),
    ("bukhari", 55, "When a man spends on his family, hoping for its reward, it counts for him "
                    "as charity."),
    ("bukhari", 12, "Feed people, and greet those you know and those you do not."),
    ("bukhari", 9, "Faith has some sixty branches, and modesty is a branch of faith."),
    ("bukhari", 24, "Leave him be. Modesty is part of faith."),
    ("muslim", 158, "Modesty brings nothing but good."),
    ("muslim", 172, "He will not enter the Garden whose neighbour is not safe from his "
                    "mischief."),
    ("muslim", 136, "Whoever dies knowing that there is no god but Allah will enter the Garden."),
    ("muslim", 159, "Say: I believe in Allah. Then hold to that straight."),
    ("muslim", 154, "Modesty is part of faith."),
]


# Added after this script last ran, and verified the same way. Kept here so the record
# of the pool is all in one place.
LATER = [
    ("bukhari", 33, "There are three signs of a hypocrite: when he speaks he lies, when he promises he breaks it, and when he is trusted he betrays."),
    ("bukhari", 1417, "Guard yourselves against the Fire, even with half a date given in charity."),
    ("bukhari", 2443, "Help your brother, whether he is doing wrong or being wronged."),
    ("bukhari", 2447, "Wrongdoing will be darkness on the Day of Resurrection."),
    ("bukhari", 2448, "Beware the prayer of the one you have wronged: there is nothing between it and Allah."),
    ("bukhari", 2457, "The man most hated by Allah is the one who argues the hardest."),
    ("bukhari", 5970, "Prayer at its proper time."),
    ("bukhari", 5973, "Among the greatest of the great sins is that a man should curse his parents."),
    ("bukhari", 6016, "He whose neighbour is not safe from the harm he does."),
    ("bukhari", 6021, "Every good turn is charity."),
    ("bukhari", 6231, "The young greet the old, the one passing greets the one sitting, and the few greet the many."),
    ("bukhari", 6232, "The rider greets the one walking, the one walking greets the one sitting, and the few greet the many."),
    ("bukhari", 6269, "No one should make another man get up from his seat and then sit in it himself."),
    ("bukhari", 6412, "Two blessings that many people waste: good health, and time with nothing to do."),
    ("bukhari", 6416, "Be in this world like a stranger, or like someone passing through."),
    ("bukhari", 6446, "Being rich is not having a great deal; being rich is a contented heart."),
    ("bukhari", 6460, "O Allah, give the family of Muhammad enough to live on."),
    ("muslim", 4519, "Give people good news and do not drive them away; make things easy and do not make them hard."),
    ("muslim", 6501, "Your mother, then your mother, then your mother, then your father, then those closest to you."),
    ("muslim", 6513, "The very best kindness is to keep up with those your father loved."),
    ("muslim", 6516, "Goodness is good character; and wrongdoing is what unsettles your heart and you would hate people to find out."),
    ("muslim", 6519, "Kinship hangs from the Throne, saying: whoever keeps me, Allah keeps him; whoever cuts me off, Allah cuts him off."),
    ("muslim", 6520, "No one who cuts off his relatives will enter the Garden."),
    ("muslim", 6523, "Whoever would like more provision and a longer trace behind him, let him keep up with his relatives."),
    ("muslim", 6534, "It is not right for a believer to keep away from his brother for more than three days."),
    ("muslim", 6535, "There is no keeping away after three days."),
    ("muslim", 6551, "The one who visits the sick is walking in the gardens of the Garden until he returns."),
]

STOP = """tools/build_hadith.py has been superseded and would undo work.

It writes assets/content/daily/hadith.json from CHOSEN alone, which would throw away the sayings
in LATER and put the older English back. Nothing here needs rebuilding.

To check the sayings as they stand:  python3 tools/check_hadith.py
"""


def build(folder=None) -> None:
    raise SystemExit(STOP)


if __name__ == "__main__":
    raise SystemExit(STOP)
