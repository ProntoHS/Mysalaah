"""Turns a prayer into pages of text.

A step's recitation is a list of segments (verses or phrases). A long one, like Al-Fatiha, is
split over several pages so the words stay large enough to read from standing. Pages never break
a segment. The posture picture stays on screen while its text pages turn.
"""
from __future__ import annotations

from dataclasses import dataclass

from .content import Content, LanguagePack, Step, StepRef
from .session import Page as StepPage

# Which posture picture belongs to each step. Keyed by step id, then by posture as a fallback.
POSTURE_BY_STEP = {
    "intention": "standing_arms_down",
    "takbir_tahrimah": "takbir_raised",
    "qunut_1": "qunut",
    "qunut_2": "qunut",
    "takbir_jalsa_a": "jalsa",
    "takbir_jalsa_b": "jalsa",
    "jalsa_dua": "jalsa",
    "takbir_sitting_a": "jalsa",
    "takbir_sitting_b": "jalsa",
}
POSTURE_BY_POSTURE = {
    "standing": "standing_folded",
    "ruku": "ruku",
    "sujood": "sujood",
    "sitting": "tashahhud",
    "salam": "salam",     # one picture showing the turn to each side
}

# Standing straight after bowing, saying "sami'a llahu liman hamidah".
ITIDAL = "tasmi_tahmid"
# The hands stay at the sides from then until prostration; the side view shows that clearly.
ITIDAL_PICTURE = "standing_itidal"


def posture_image(step: Step, variant: str | None, previous: Step | None = None) -> str:
    """[previous] is the step just before this one, which decides where the hands are: after
    bowing the hands stay at the sides, through standing upright and the takbir down to sujood.
    They are only folded again after rising from prostration. [variant] is kept for content that
    still names one."""
    if step.recitation == ITIDAL:
        name = ITIDAL_PICTURE
    elif (step.posture == "standing" and previous is not None
          and (previous.posture == "ruku" or previous.recitation == ITIDAL)):
        name = ITIDAL_PICTURE
    else:
        name = POSTURE_BY_STEP.get(step.id) or POSTURE_BY_POSTURE[step.posture]
    return f"postures/{name}.png"


@dataclass(frozen=True)
class TextPage:
    """One screenful: a posture picture, Arabic lines and their English lines."""
    step_index: int
    ref: StepRef
    step: Step
    rakat: int
    posture_image: str
    arabic: list[str]
    english: list[str]
    page_in_step: int
    pages_in_step: int
    repeat: int
    first_segment: int = 0      # index of this page's first verse within the recitation
    recitation: str = ""
    latin: bool = False         # written in the pack's language (the intention), not Arabic

    @property
    def is_first_of_step(self) -> bool:
        return self.page_in_step == 0

    @property
    def more_to_come(self) -> bool:
        return self.page_in_step < self.pages_in_step - 1


def split(segments: int, per_page: int) -> list[range]:
    if segments <= 0:
        return [range(0, 0)]
    return [range(i, min(i + per_page, segments)) for i in range(0, segments, per_page)]


def group_segments(arabic: list[str], english: list[str], per_page: int,
                   fits=None, one_page: bool = True) -> list[range]:
    """A recitation is one screenful: the whole surah is shown at once, so the recitation can
    play through without the page turning under it. Pass one_page=False to split it instead."""
    n = len(arabic)
    if n == 0:
        return [range(0, 0)]
    if one_page:
        return [range(0, n)]
    if fits is None:
        return split(n, per_page)
    groups, i = [], 0
    while i < n:
        j = i + 1
        while j < n and fits(arabic[i:j + 1], english[i:j + 1]):
            j += 1
        groups.append(range(i, j))
        i = j
    return groups


INTENTION = "intention"


def build_pages(step_pages: list[StepPage], content: Content, pack: LanguagePack,
                fallback: LanguagePack | None = None, per_page: int = 2, fits=None,
                one_page: bool = True, intention: str | None = None,
                translation=None) -> list[TextPage]:
    """One page per recitation by default; see group_segments. [intention] is the sentence
    for the first screen, which names the prayer chosen ("I intend to perform 2 Rakats Sunnah
    of Fajr"), so it is written by whoever knows which prayer that is.

    [translation], when chosen in Settings, gives each page its meaning line for line in
    TextPage.english; without one those lines are left empty and only the Arabic is shown."""
    out: list[TextPage] = []
    for n, sp in enumerate(step_pages):
        previous = step_pages[n - 1].step if n > 0 else None
        key = sp.step.recitation
        if key == INTENTION:
            out.append(TextPage(
                step_index=sp.index, ref=sp.ref, step=sp.step, rakat=sp.rakat,
                posture_image=posture_image(sp.step, sp.ref.variant, previous),
                arabic=[intention or pack.t("intention.plain", fallback)], english=[""],
                page_in_step=0, pages_in_step=1, repeat=1, recitation=key, latin=True))
            continue
        arabic = content.arabic.get(key, [])
        english = translation.for_key(key, len(arabic)) if translation is not None else None
        if english is None:              # none chosen, or out of step: show Arabic only
            english = [""] * len(arabic)
        groups = group_segments(arabic, english, per_page, fits, one_page)
        img = posture_image(sp.step, sp.ref.variant, previous)
        for i, g in enumerate(groups):
            out.append(TextPage(
                step_index=sp.index, ref=sp.ref, step=sp.step, rakat=sp.rakat,
                posture_image=img, arabic=[arabic[j] for j in g], english=[english[j] for j in g],
                page_in_step=i, pages_in_step=len(groups), repeat=sp.step.repeat,
                first_segment=g.start, recitation=key,
            ))
    return out
