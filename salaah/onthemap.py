"""The mat's identity on the community map, and the switch that creates it.

WHAT THIS IS FOR. The world screen draws a dot and a line to Makkah for every mat it knows
about, and for now it knows about one, because nothing tells a mat about any other. Telling
them needs a service for mats to check in with, and a mat that checks in has to call itself
something. This module is that name, and nothing else: there is no network code here, no
server address, and nothing in this release sends anything anywhere.

THE NAME IS MADE WHEN SOMEBODY SAYS YES, AND DESTROYED WHEN THEY SAY NO. That is the whole
design and it is worth being plain about why.

A mat that generated an identifier at first boot would be carrying one whether or not anybody
ever agreed to be counted -- a thing that exists only to make this device recognisable, sitting
on a child's mat, created before the question was asked. So it is not made until the switch is
turned on, and it is deleted when the switch is turned off. A mat that never opts in has no
identifier at all: there is nothing to leak, nothing to subpoena, and nothing to explain.

Turning it off and on again gives a DIFFERENT name on purpose. It means the service cannot
join the two periods together into one history of a household, and it means "stop counting me"
really stops rather than pausing. The cost is that the count cannot tell a returning mat from
a new one, which is a cost worth paying and one the screen should be honest about.

IT IS RANDOM, NEVER DERIVED. Not the MAC address, not the serial number, not a hash of either.
A derived identifier cannot be reset by the person it identifies, survives every attempt to
start again, and is the same across every app that thinks of the same trick. uuid4 is 122 bits
of randomness and means nothing on its own.

WHAT IT IS NOT. It is not a user. A mat is a household -- a child, a parent, whoever else
prays on it -- and any count built on this file counts MATS THAT CHECKED IN, which is the only
thing it can honestly claim.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

#: Beside settings.json rather than inside it. A preference is something the person chose;
#: this is a name the mat was given, and the two keep better apart -- deleting it has to be
#: possible without rewriting their settings, and reading their settings has to be possible
#: without handling an identifier.
PATH = Path.home() / ".config" / "salaah" / "install-id"

#: 32 hex characters, which is what uuid4().hex gives. Anything else in the file is treated as
#: damage rather than guessed at.
LOOKS_RIGHT = re.compile(r"\A[0-9a-f]{32}\Z")


def name_of_this_mat(path: Path = PATH) -> str | None:
    """The mat's name on the map, or None if it has never agreed to be on it.

    A file that is missing, unreadable or does not hold 32 hex characters all answer None.
    None is the safe answer in every one of those cases: the worst that follows is that a
    mat which had opted in stops being counted, where guessing at a damaged file risks
    sending something that is not an identifier to a service that will store it.
    """
    try:
        said = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return said if LOOKS_RIGHT.match(said) else None


def join(path: Path = PATH) -> str | None:
    """Agree to be counted: make a name if there is not one already, and return it.

    Returns the existing name unchanged when there is one, so that turning the switch on
    twice -- or an upgrade re-running this -- does not quietly become a different mat.
    Returns None if it cannot be written, because a name that is not on disk would be a new
    mat on every restart and would inflate the count forever.
    """
    already = name_of_this_mat(path)
    if already:
        return already
    name = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name + "\n", encoding="utf-8")
    except OSError:
        return None
    return name_of_this_mat(path)      # read back: a name that cannot be read is no name


def leave(path: Path = PATH) -> None:
    """Stop being counted, and destroy the name.

    Deleting rather than keeping-and-ignoring is the point. A name kept against the day
    somebody changes their mind is a name that still exists on a device whose owner has said
    no, and it would let a later opt-in be joined to an earlier one.

    A file that is already gone is success. A file that cannot be deleted is not raised at
    the caller: the switch has still been turned off and nothing will be sent, and there is
    nothing useful a prayer mat can do about a read-only disk at that moment.
    """
    try:
        path.unlink()
    except OSError:
        pass
