"""Plays one prayer unit step by step, keeping count of rakats."""
from __future__ import annotations

from dataclasses import dataclass

from .content import Content, Step, StepRef, Unit


@dataclass(frozen=True)
class Page:
    index: int
    ref: StepRef
    step: Step
    rakat: int


def assign_rakats(postures: list[str]) -> list[int]:
    """A new rakat starts at the first standing step after the current rakat's two sujood.
    Sitting for tashahhud does not start a rakat; rising afterwards does."""
    out, rakat, sujood = [], 1, 0
    for p in postures:
        if p == "standing" and sujood >= 2:
            rakat += 1
            sujood = 0
        if p == "sujood":
            sujood += 1
        out.append(rakat)
    return out


class PrayerSession:
    def __init__(self, unit: Unit, content: Content, overrides: dict[str, str] | None = None):
        overrides = overrides or {}
        steps = [content.steps[overrides.get(r.step_id, r.step_id)] for r in unit.sequence]
        rakats = assign_rakats([s.posture for s in steps])
        self.unit = unit
        self.pages = [Page(i, unit.sequence[i], s, rakats[i]) for i, s in enumerate(steps)]
        self.position = 0
        self.finished = False

    def set_pages(self, pages: list[Page]) -> None:
        """A step can span several screens of text, so the session steps through those instead.
        Each page carries its own rakat, so the counter stays correct."""
        if not pages:
            return
        self.pages = pages
        self.position = min(self.position, len(pages) - 1)

    @property
    def total_rakats(self) -> int:
        return self.unit.rakats

    @property
    def current(self) -> Page:
        return self.pages[self.position]

    @property
    def progress(self) -> float:
        return 1.0 if len(self.pages) <= 1 else self.position / (len(self.pages) - 1)

    def next(self) -> bool:
        """Moves on one step. At the last step it marks the prayer finished instead."""
        if self.finished:
            return False
        if self.position < len(self.pages) - 1:
            self.position += 1
        else:
            self.finished = True
        return True

    def back(self) -> bool:
        if self.finished:
            self.finished = False
            return True
        if self.position > 0:
            self.position -= 1
            return True
        return False


class Debouncer:
    """Ignores presses closer together than [window] seconds. Some buttons send two keys per press."""

    def __init__(self, window: float = 0.3):
        self.window = window
        self._last: float | None = None

    def accept(self, t: float) -> bool:
        if self._last is not None and t - self._last < self.window:
            return False
        self._last = t
        return True
