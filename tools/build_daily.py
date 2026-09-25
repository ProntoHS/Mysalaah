"""Built the first twenty of the daily Qur'an passages. Superseded -- do not run it.

The pool is now 58 passages, and ten of them are a clause of a long verse rather than the
whole of it, so that the English beside them can render all of the Arabic and still be read
across a room. This script knows nothing about any of that: it writes the file from the table
below and nothing else, so running it would quietly throw away thirty-eight passages and put
the old, shorter English back on the other twenty.

It is kept because the table is the record of where those first twenty came from. To check
the file as it now stands, run tools/check_daily.py instead.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# chapter, verse -> plain English. Short verses only, so they fit beside the hadith.
PASSAGES = {
    (94, 5): "So truly, with hardship comes ease.",
    (2, 152): "So remember Me, and I will remember you. Be thankful to Me and never ungrateful.",
    (13, 28): "Those who believe, and whose hearts find rest in the remembrance of God. "
              "Surely hearts find rest in the remembrance of God.",
    (2, 286): "God does not burden anyone beyond what they can bear.",
    (29, 69): "Those who strive for Our sake, We will surely guide them to Our ways.",
    (55, 13): "So which of your Lord's blessings would you deny?",
    (2, 45): "Seek help through patience and prayer.",
    (20, 114): "My Lord, increase me in knowledge.",
    (49, 13): "The most honoured of you in the sight of God is the most mindful of Him.",
    (31, 17): "My son, keep up the prayer, command what is right, forbid what is wrong, "
              "and endure whatever happens to you.",
    (3, 139): "Do not lose heart and do not grieve.",
    (39, 53): "Do not despair of God's mercy.",
    (14, 7): "If you are thankful, I will surely give you more.",
    (2, 186): "When My servants ask you about Me, I am near.",
    (65, 3): "Whoever puts their trust in God, He is enough for them.",
    (93, 5): "And your Lord will give to you, and you will be satisfied.",
    (17, 23): "Your Lord has commanded that you worship none but Him, and that you be good "
              "to your parents.",
    (16, 90): "God commands justice, doing good, and generosity to relatives.",
    (103, 3): "Except those who believe, do good, and urge one another to truth and to patience.",
    (76, 9): "We feed you only for the sake of God. We want no reward from you, and no thanks.",
}


STOP = """tools/build_daily.py has been superseded and would undo work.

It writes assets/content/daily/quran.json from the twenty passages listed in it, which would
throw away the other thirty-eight and put the old English back. Nothing here needs rebuilding.

To check the passages as they stand:  python3 tools/check_daily.py
"""


def build(quran: Path) -> Path:
    raise SystemExit(STOP)


if __name__ == "__main__":
    raise SystemExit(STOP)
