"""Screen colours: black on white by day, white on black after dark.

Everything the app draws itself reads its colours from here at the moment it paints, so a change
of theme is a repaint, never a rebuild, and a prayer in progress keeps its place.

Settings offers three choices:

    auto    dark from Maghrib until sunrise, light the rest of the day (the default)
    light   black on white, always
    dark    white on black, always

The few colours with a meaning (the red of the word being recited, the green once facing the
Qibla, the gold of the lit arch) stay as they are; the red is a touch brighter on black so it
reads as clearly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MODES = ("auto", "light", "dark")


@dataclass(frozen=True)
class Palette:
    dark: bool
    paper: str          # the background
    ink: str            # the words and lines
    soft: str           # hints and notes
    faint: str          # dividers, the unlit band on the compass
    line: str           # thin borders
    pressed: str        # a button while it is held
    panel: str          # a surface a step off the background (the banner, a pressed pill)
    lapis: str          # headings and links
    highlight: str      # the word being recited
    green: str          # the prayer whose time it is now
    progress_track: str
    progress_fill: str


LIGHT = Palette(dark=False, paper="#FFFFFF", ink="#000000", soft="#444444", faint="#BBBBBB",
                line="#D9DCD6", pressed="#DDDDDD", panel="#000000", lapis="#274B8F",
                highlight="#C0392B", green="#3DD07A", progress_track="#2A2E31",
                progress_fill="#5B7FC7")
DARK = Palette(dark=True, paper="#000000", ink="#FFFFFF", soft="#BBBBBB", faint="#555555",
               line="#3A3D40", pressed="#333333", panel="#1C1C1C", lapis="#8FB1F0",
               highlight="#FF5A47", green="#4CD187", progress_track="#2A2E31",
               progress_fill="#5B7FC7")


class _Current:
    """The palette in use. A holder rather than a variable, so every module that imported it
    sees a change."""
    palette: Palette = LIGHT


def palette() -> Palette:
    return _Current.palette


def set_dark(dark: bool) -> bool:
    """Switches the palette. Returns True if that changed anything."""
    wanted = DARK if dark else LIGHT
    if _Current.palette is wanted:
        return False
    _Current.palette = wanted
    return True


def is_dark() -> bool:
    return _Current.palette.dark


def wants_dark(mode: str, now: datetime, times: dict) -> bool:
    """Should the screen be dark now? For "auto": from Maghrib until sunrise. Without the times
    (a place so far north the sun does not set), it falls back to the clock: 7pm to 7am."""
    if mode == "dark":
        return True
    if mode != "auto":
        return False
    sunrise, maghrib = times.get("sunrise"), times.get("maghrib")
    if sunrise is None or maghrib is None:
        return now.hour >= 19 or now.hour < 7
    clock = now.time()
    return clock >= _time(maghrib) or clock < _time(sunrise)


def _time(value):
    return value.time() if isinstance(value, datetime) else value
