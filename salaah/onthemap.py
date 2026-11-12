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

import json
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path

#: The service mats check in with. A Cloudflare Worker in front of a key-value store; its
#: whole source is forty lines and it can do exactly three things -- take a check-in, delete
#: a row, and list coordinates. It holds one row per mat: the random name below, and a
#: latitude and longitude in WHOLE DEGREES. It is told nothing else, because it is sent
#: nothing else.
#:
#: Public, and in a public repository, which is worth being plain about: anybody who reads
#: this line can post an invented name and inflate the count. There is no secret that would
#: fix that, because a secret shipped to every mat in a public repository is not a secret.
#: So the number is "mats that reported in", and the screen should not claim more.
SERVICE = "https://salaah-map.square-union-9586.workers.dev"

#: The last answer the service gave, so the globe has something to draw the moment it opens
#: instead of a blank earth and a spinner. Beside the name rather than in settings.json, for
#: the same reason the name is: this is something the service said, not something anybody
#: chose.
CACHE = Path.home() / ".config" / "salaah" / "mats.json"

#: Long enough for a sleepy Pi on a slow line, short enough that a thread does not sit there
#: all evening. Nothing waits on this anyway -- see `in_the_background`.
PATIENCE = 8.0

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


def whole(degrees: float) -> int | None:
    """A coordinate as it is allowed to leave the house: a whole degree and nothing finer.

    THIS IS THE PRIVACY BOUNDARY AND IT IS ONE LINE LONG, which is the point -- there is no
    path out of this module that does not pass through it. A whole degree is about seventy
    miles. On the 400px globe the world screen draws, that is a pixel and a bit: the dot
    lands in the right country and says nothing about which street.

    The mat knows exactly where it is, because it needs to for the sun. The service has no
    use for that precision and so is not given it.
    """
    try:
        rounded = round(float(degrees))
    except (TypeError, ValueError):
        return None
    return rounded if -180 <= rounded <= 180 else None


def _ask(url: str, method: str, body: dict | None, opener=None) -> dict | None:
    """One request, and never an exception to the caller.

    EVERY failure is None: no network, no DNS, a timeout, a 500, a reply that is not JSON, a
    reply that is JSON but not an object. A prayer mat that cannot reach a counting service
    is a prayer mat, and nothing it does next should differ.
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("content-type", "application/json")
    try:
        with (opener or urllib.request.urlopen)(request, timeout=PATIENCE) as answer:
            said = json.loads(answer.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    return said if isinstance(said, dict) else None


def check_in(latitude: float, longitude: float, *, path: Path | None = None,
             service: str | None = None, cache: Path | None = None,
             opener=None) -> int | None:
    """Tell the service this mat is still here, and remember what it says back.

    DOES NOTHING AT ALL IF THERE IS NO NAME, which is how the switch is honoured. A mat that
    has not opted in has no name on disk (salaah/onthemap.py, top), so this returns None
    before it has composed a request, let alone sent one. There is no second check of a
    setting that could drift out of step with the file: no name, no network.

    Returns how many mats the service knows about, or None if anything at all went wrong.
    """
    path, service, cache = path or PATH, service or SERVICE, cache or CACHE
    name = name_of_this_mat(path)
    if not name:
        return None
    north, east = whole(latitude), whole(longitude)
    if north is None or east is None or not -90 <= north <= 90:
        return None
    if _ask(f"{service}/checkin", "POST",
            {"id": name, "lat": north, "lon": east}, opener) is None:
        return None
    return remember(fetch(service=service, opener=opener), cache=cache)


def fetch(*, service: str | None = None, opener=None) -> list[tuple[int, int]] | None:
    """Where the mats are, as whole degrees. No names come back; the service has none to give
    beyond the random one, and does not return that either."""
    said = _ask(f"{service or SERVICE}/mats", "GET", None, opener)
    if said is None:
        return None
    found = []
    for row in said.get("mats", []) or []:
        if isinstance(row, dict):
            north, east = whole(row.get("lat")), whole(row.get("lon"))
            if north is not None and east is not None and -90 <= north <= 90:
                found.append((north, east))
    return found


def remember(places: list[tuple[int, int]] | None, *,
             cache: Path | None = None) -> int | None:
    """Keep the service's answer so the globe can draw it while offline.

    A failed fetch LEAVES THE OLD ANSWER ALONE rather than writing an empty one. A mat that
    loses its wifi for an afternoon should not quietly empty the world.
    """
    if places is None:
        return None
    cache = cache or CACHE
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"mats": [[n, e] for n, e in places]}),
                         encoding="utf-8")
    except OSError:
        return len(places)
    return len(places)


def remembered(cache: Path | None = None) -> list[tuple[int, int]]:
    """The last answer, or nothing. Never raises, never waits, never touches the network."""
    cache = cache or CACHE
    try:
        said = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    found = []
    for row in (said.get("mats", []) if isinstance(said, dict) else []) or []:
        if isinstance(row, (list, tuple)) and len(row) == 2:
            north, east = whole(row[0]), whole(row[1])
            if north is not None and east is not None and -90 <= north <= 90:
                found.append((north, east))
    return found


def forget(cache: Path | None = None) -> None:
    """Drop the remembered map. Used when somebody opts out: a mat that has left the map
    should not keep drawing the community it is no longer part of."""
    try:
        (cache or CACHE).unlink()
    except OSError:
        pass


def stop(*, path: Path | None = None, service: str | None = None,
         cache: Path | None = None, opener=None) -> bool:
    """Leave the map: delete the row from the service, THEN destroy the name.

    THE NAME IS READ BEFORE THE FILE IS DESTROYED, and that is the line to be careful of. It
    is the only thing that says which row on the service belongs to this mat, so a `leave`
    that ran before the read would leave nothing to delete WITH: the row would sit there
    being counted until it expired, while the family who turned the switch off believed they
    had gone. Reading it into `name` first is what prevents that -- not the order of the two
    statements below, which a sabotage run in 2.21 showed can be swapped without harm
    precisely because the read has already happened.

    Returns whether the service confirmed the deletion. FALSE IS NOT A FAILURE OF THE SWITCH:
    the name is destroyed either way and nothing further is ever sent. It means only that the
    row will be counted until the service drops it of its own accord, which it does after
    sixty days of not hearing from a mat. A mat switched off on an aeroplane cannot do better
    than that, and pretending otherwise would be the lie.
    """
    path, service, cache = path or PATH, service or SERVICE, cache or CACHE
    name = name_of_this_mat(path)
    gone = False
    if name:
        gone = _ask(f"{service}/checkin", "DELETE", {"id": name}, opener) is not None
    leave(path)
    forget(cache)
    return gone


def in_the_background(work) -> None:
    """Run one of the above on a thread nobody waits for.

    NOTHING ON THIS MAT MAY WAIT ON A NETWORK. The prayer times come from the sun and the
    clock and are worked out on the mat; the map is a decoration on one screen. A mat on a
    hotel wifi that accepts the connection and then never answers would otherwise freeze the
    interface for as long as the timeout -- during a prayer, on a child's screen.

    A daemon thread, so a mat being shut down is not held open by a request to a counting
    service. If it dies mid-request the row is simply not updated today, and the service
    forgets it after sixty days anyway.

    The exception swallow is deliberate and total. This is the last line of a thread that
    nothing joins and nothing checks: an exception here has nowhere to go and no one to tell.
    """
    import threading

    def quietly():
        try:
            work()
        except Exception:                       # noqa: BLE001 - see above
            pass

    threading.Thread(target=quietly, daemon=True, name="onthemap").start()
