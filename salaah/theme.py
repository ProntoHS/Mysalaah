"""Screen colours: black on white, white on black, or Harry's colour on black.

Everything the app draws itself reads its colours from here at the moment it paints, so a change
of theme is a repaint, never a rebuild, and a prayer in progress keeps its place.

Settings offers three choices, and from 2.45 they are the only three:

    light   black on white, always
    dark    white on black, always
    colour  Harry's coloured artwork, on black

The few colours with a meaning (the red of the word being recited, the green once facing the
Qibla, the gold of the lit arch) stay as they are; the red is a touch brighter on black so it
reads as clearly.

COLOUR IS A DARK PALETTE, and that is not a fudge -- Harry drew the coloured mosques on black.
"as the background is white, the white can be inverted", then "colour theme will sit on black".
So `dark` is true in colour, every one of the ten places on the mat that asks whether the screen
is dark keeps working untouched, and the only places that need the new question are the two that
choose a PICTURE and the lettering on the dome.

AUTO IS GONE. Harry, 18 November 2026: "remove auto from screen mode selection. keep it simple
3 modes to choose from." It meant dark from Maghrib until sunrise, with a 7pm-to-7am fallback
for places so far north the sun does not set. Nothing changes the screen on its own any more.
Two of the three modes are black-backed, so the mat is still kind at Fajr unless light is
chosen -- which is now a choice somebody makes rather than one the clock makes for them.

The one thing auto still does is decide what a mat that SAYS "auto" becomes when it upgrades:
see resolve_auto below. It runs once, at the moment of the upgrade, so nobody's screen jumps
under them, and then never again.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MODES = ("light", "dark", "colour")


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
    #: Last, and with a default, because every field before it has none and a dataclass will
    #: not take a defaulted field ahead of a bare one. Only the two places that choose a
    #: picture and the lettering on the dome ask this; everything else asks `dark`, which is
    #: true in colour as well.
    colour: bool = False


LIGHT = Palette(dark=False, paper="#FFFFFF", ink="#000000", soft="#444444", faint="#BBBBBB",
                line="#D9DCD6", pressed="#DDDDDD", panel="#000000", lapis="#274B8F",
                highlight="#C0392B", green="#3DD07A", progress_track="#2A2E31",
                progress_fill="#5B7FC7")
DARK = Palette(dark=True, paper="#000000", ink="#FFFFFF", soft="#BBBBBB", faint="#555555",
               line="#3A3D40", pressed="#333333", panel="#1C1C1C", lapis="#8FB1F0",
               highlight="#FF5A47", green="#4CD187", progress_track="#2A2E31",
               progress_fill="#5B7FC7")
#: THE SAME COLOURS AS DARK, deliberately, every one of them. What the colour theme changes is
#: which PICTURES are shown, not what the app draws around them -- the words, the banner, the
#: buttons and the rules are the dark ones because Harry's coloured artwork is drawn on black.
#: A separate set of chrome colours would be a third thing to keep in step with the other two
#: for no gain anybody asked for; if the colour mat ever wants its own, this is where it goes
#: and it is one line.
COLOUR = Palette(dark=True, paper="#000000", ink="#FFFFFF", soft="#BBBBBB", faint="#555555",
                 line="#3A3D40", pressed="#333333", panel="#1C1C1C", lapis="#8FB1F0",
                 highlight="#FF5A47", green="#4CD187", progress_track="#2A2E31",
                 progress_fill="#5B7FC7", colour=True)

#: Which palette each mode uses. The one place that knows.
PALETTES = {"light": LIGHT, "dark": DARK, "colour": COLOUR}


class _Current:
    """The palette in use. A holder rather than a variable, so every module that imported it
    sees a change."""
    palette: Palette = LIGHT


def palette() -> Palette:
    return _Current.palette


def set_mode(mode: str) -> bool:
    """Switches the palette to one of the three modes. Returns True if that changed anything.

    An unknown mode -- an older settings file saying "auto", a typo somebody put in by hand --
    lands on light, which is what the mat did before any of this existed.
    """
    wanted = PALETTES.get(mode, LIGHT)
    if _Current.palette is wanted:
        return False
    _Current.palette = wanted
    return True


def set_dark(dark: bool) -> bool:
    """Light or dark, the two-way switch this had before there were three modes.

    Kept because it says exactly what it means and a good deal of the suite is written in terms
    of it. It cannot reach the colour palette; set_mode is for that.
    """
    return set_mode("dark" if dark else "light")


def mode() -> str:
    """Which of MODES is in use, by name.

    is_dark() answers two-thirds of this and has since before there were three modes, but
    "not dark" is not the same as "light" now that colour exists, and pillar_match needs to
    tell colour from dark to pick a board. Read back off the palette rather than stored
    beside it, so it cannot drift from what set_mode actually did.
    """
    for name, chosen in PALETTES.items():
        if _Current.palette is chosen:
            return name
    return "light"


def is_dark() -> bool:
    return _Current.palette.dark


def is_colour() -> bool:
    return _Current.palette.colour


# THERE IS NO other(). 2.06 had one -- the strip across the top was deliberately the inverse
# of the mat, white at night and black by day -- and 2.07 takes it out at Harry's asking after
# he saw it on the mat. The strip is the mat's own theme again: black with white lettering when
# the mat is dark, white with black when it is light.
#
# It is noted rather than simply deleted because the idea was sound and the colours were
# already there for it, so it will look tempting again. What it cost was legibility of a
# different kind: a strip that disagrees with everything under it reads as a separate device
# bolted to the top of the screen. If it ever comes back, it comes back because somebody looked
# at the mat and wanted it, not because the palette makes it easy.


def resolve_auto(mode: str, now: datetime, times: dict) -> str:
    """What a mat that says "auto" becomes, worked out once and then written down.

    Auto was the default, so every mat in the world says it, including Harry's. Dropping the
    mode without this would move everybody to whatever the fallback is at the moment they
    happen to upgrade -- a white screen at Fajr for somebody who had chosen auto precisely so
    that would not happen.

    So auto gets to make one last decision: the mode the mat is on at the instant it upgrades
    is the mode it keeps. Upgrade after Maghrib and it lands on dark, at noon on light, and
    from then on it stays where it is put. Anything that is already one of the three modes is
    left alone.
    """
    if mode in MODES:
        return mode
    return "dark" if _auto_is_dark(now, times) else "light"


def _auto_is_dark(now: datetime, times: dict) -> bool:
    """Auto's rule, for the last time it is ever asked: dark from Maghrib until sunrise, and
    without the times (a place so far north the sun does not set) the clock, 7pm to 7am."""
    sunrise, maghrib = times.get("sunrise"), times.get("maghrib")
    if sunrise is None or maghrib is None:
        return now.hour >= 19 or now.hour < 7
    clock = now.time()
    return clock >= _time(maghrib) or clock < _time(sunrise)


def _time(value):
    return value.time() if isinstance(value, datetime) else value
