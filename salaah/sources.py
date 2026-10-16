"""Who the words on this mat belong to.

Not a written list. Every line here is read off the files that are actually installed, so the
acknowledgement cannot drift from the text it acknowledges: a translation copied onto a mat by
hand brings its own SOURCE.json and appears here; one taken off disappears from here with it;
and a translation installed with no SOURCE.json is SHOWN as having none rather than quietly
left out, which is a prompt to go and fix it.

That matters more than tidiness. The publishers whose translations these are asked, reasonably,
how their work would be credited, and a list maintained by hand would be out of date the first
time a file changed. This one is a reading of the disk.

Three things use it: the line across the bottom of the front door, the credit in the Qur'an
reader's bar, and the Sources page in Settings. The first two want something short, the third
wants everything, so there is a short form and a long one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Credit:
    """One source: what it is, who it belongs to, and where it came from."""
    what: str                # "Hindi translation"
    translator: str = ""     # the person who made it, where that is known
    publisher: str = ""      # the house that published it
    where: str = ""          # quranenc.com
    via: str = ""            # the project it was obtained through
    note: str = ""           # anything that has to be said plainly, including "not identified"
    private: bool = False    # on this mat only; not part of the app

    @property
    def who(self) -> str:
        """The shortest honest answer to "whose is this?"."""
        both = [x for x in (self.translator, self.publisher) if x]
        return " · ".join(both) if both else ""

    def line(self) -> str:
        """One line for the Sources page."""
        said = self.who or "source not recorded"
        if self.via and self.where:
            said += f" ({self.via}, {self.where})"
        elif self.via:
            said += f" (via {self.via})"
        elif self.where:
            said += f" ({self.where})"
        return said


def read_credit(folder: Path) -> Credit | None:
    """The SOURCE.json beside a Qur'an text, if it has one."""
    try:
        d = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    return Credit(what=str(d.get("what", "")), translator=str(d.get("translator", "")),
                  publisher=str(d.get("publisher", "")), where=str(d.get("where", "")),
                  via=str(d.get("via", "")), note=str(d.get("note", "")),
                  private=bool(d.get("private", False)))


def for_translation(quran, lang: str) -> Credit | None:
    """The credit for the Qur'an text a reader is looking at.

    Found the same way the text itself is -- this mat's own copy first, then the one that came
    with the app -- so a family that has put their own translation on the mat is shown that
    translation's credit and not the one it replaced.
    """
    if not lang:
        return None
    for root in (getattr(quran, "private", None), getattr(quran, "root", None)):
        if root is None:
            continue
        got = read_credit(Path(root) / lang)
        if got is not None:
            return got
    return None


def scripture(quran) -> list[Credit]:
    """Every Qur'an text installed on this mat: the Arabic, then each translation.

    Arabic first because it is the text; the translations are of it.
    """
    out = []
    arabic = for_translation(quran, "ar")
    if arabic is not None:
        out.append(arabic)
    for lang in quran.languages():
        got = for_translation(quran, lang)
        out.append(got if got is not None else
                   Credit(what=f"{lang} translation",
                          note="This translation is installed with no source recorded."))
    return out


def rest(assets: Path) -> list[Credit]:
    """The sources that are not the Qur'an, read from assets/content/sources.json.

    A written file, unlike the scripture credits, because these are facts about the app rather
    than about something a family can add to their own mat.
    """
    try:
        d = json.loads((Path(assets) / "content" / "sources.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for row in d.get("items", []):
        if isinstance(row, dict) and row.get("what"):
            out.append(Credit(what=str(row["what"]), translator=str(row.get("translator", "")),
                              publisher=str(row.get("publisher", "")),
                              where=str(row.get("where", "")), via=str(row.get("via", "")),
                              note=str(row.get("note", ""))))
    return out


def everything(assets: Path, quran) -> list[Credit]:
    return scripture(quran) + rest(assets)


def short(quran) -> str:
    """The line across the bottom of the front door.

    The houses rather than the people: the mat's own screen is not the place for a list, and
    the names that matter to a publisher are the publishers'. Each one once, in the order they
    were first met, so it reads the same way every time rather than shuffling.

    Publishers only -- not the projects a text was obtained THROUGH. An aggregator is not a
    rights holder, and "Noble Qur'an Encyclopedia · the quran-json project" reads as though the
    two stand in the same relation to the text when they do not. Where it came through is on
    the Sources page, where there is room to say which is which.
    """
    seen, out = set(), []
    for credit in scripture(quran):
        if credit.publisher and credit.publisher not in seen:
            seen.add(credit.publisher)
            out.append(credit.publisher)
    return " · ".join(out)
