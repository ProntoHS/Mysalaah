"""Updating the mat over the internet, without that becoming a way into it.

This is the only part of the app that fetches code and runs it, which makes it the only part
that can brick the mat or be turned against it. Everything here exists to make one of those two
things harder.

    The signature is the point. HTTPS says "this really is the website you asked for". It does
    not say "this file is the one its author meant to publish". If the hosting account is ever
    broken into, or a file is swapped at the host, HTTPS is perfectly happy and every mat
    installs whatever is sitting there. So the manifest is signed with a key only its author
    holds, the mat carries the matching public half, and anything that does not verify is
    refused before a single byte of it is unpacked.

    Nothing is trusted until it is checked. The manifest's signature is checked before the
    manifest is believed. The download's hash is checked against the manifest before it is
    opened. The zip's entries are checked before they are written -- a zip can name a file
    "../../.bashrc" and unpacking it naively writes there.

    Nothing is replaced in place. The new version is unpacked beside the old one and put in
    place with renames, so a download cut off halfway leaves a working mat rather than half of
    two versions.

    The previous version stays on disk. If the new one will not start, run.sh puts it back
    without anyone being asked. That guard deliberately lives OUTSIDE the directories this
    replaces: code from a broken version cannot be trusted to undo its own installation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

# The public half of the key releases are signed with. The private half lives on the author's
# own machine and nowhere else. Replacing this line is how a mat is taught to trust someone
# else, which is exactly why it is in the source rather than in a settings file.
PUBLIC_KEY = "mQwe463MZ8zDcutwC2QJzrrCvqsAIkpJoyqe4ThDZ44="

# Where the manifest is fetched from. A setting can point a mat somewhere else -- at a laptop
# while this is being tested, or at a new home if this one ever has to move -- but the default
# is what every mat uses, so it is the address that has to keep working.
DEFAULT_URL = "https://raw.githubusercontent.com/ProntoHS/Mysalaah/main/latest.json"

TIMEOUT = 20            # seconds for any one request
TRIES = 3               # attempts at a download before giving up: home wifi drops things
PAUSE = 1.0             # seconds between attempts
CHUNK = 64 * 1024

# The largest release this version will pull down. A runaway file is a full disk on a Pi, and
# a full disk is a mat that will not start, so there has to be a number -- but the number has
# to leave room for the artwork to grow, and 64 MiB did not.
#
# 1.84 went out at 68.9 MB, over that cap, and every mat refused it: "the download is far
# larger than it should be", which was the guard doing exactly its job. Raised here, and the
# films re-packed in the same version so the release came back down to about 52 MB.
#
# THE CAP THAT BINDS IS THE ONE IN THE CODE A MAT IS ALREADY RUNNING, not this one. A mat on
# 1.84 or 1.85 has 64 MiB compiled into it and will refuse anything bigger however large this
# number is -- the new value only takes effect once a mat has installed a version that carries
# it, which it can only do if that release fits under the OLD cap. So FIELD_CAP below is the
# number releases are actually checked against, and it stays until no mat is left on 1.85 or
# earlier. Raising this one buys headroom for later; it does not buy any today.
MOST = 256 * 1024 * 1024

# The smallest cap any mat in the field is running. Releases are tested against this, not
# against MOST -- see tests/test_core.py, which refuses a release that comes close to it.
FIELD_CAP = 64 * 1024 * 1024

# What an update replaces. run.sh is not in the list on purpose: it is the guard that puts the
# old version back, so it cannot be one of the things a bad release can break.
REPLACES = ("salaah", "assets")
STATE = "update-state.json"

# The exit code the app uses to say "I have installed an update; start me again". It has to be a
# code of its own rather than an ordinary clean exit, because run.sh cannot otherwise tell the
# difference between an update wanting the new version started and somebody closing the app --
# and getting that wrong means either a mat that will not shut down or, as happened here, one
# that installs an update and then quietly drops to the desktop. run.sh has this number in it.
RESTART = 42


def parts(version: str) -> tuple:
    """A version as something that can be compared. "1.9" is older than "1.12", which is the
    whole reason this is not a string comparison."""
    out = []
    for piece in str(version).split("."):
        out.append((0, int(piece)) if piece.isdigit() else (1, piece))
    return tuple(out)


def newer(offered: str, running: str) -> bool:
    return parts(offered) > parts(running)


class Refused(Exception):
    """The update was not accepted. The message says why, in words fit for the screen."""


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    notes: str = ""
    bytes: int = 0


def verify(signed: bytes, signature: str, key: str = "") -> None:
    """Raises Refused unless [signature] was made over [signed] by the holder of the key."""
    key = key or PUBLIC_KEY
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        raise Refused("this mat cannot check signatures: the cryptography package is missing")
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True))
    except Exception:
        raise Refused("the built-in key is not readable")
    try:
        public.verify(base64.b64decode(signature, validate=True), signed)
    except InvalidSignature:
        raise Refused("this release was not signed by the person who makes this app")
    except Exception:
        raise Refused("the signature is not readable")


def read_manifest(raw: bytes, key: str = "") -> Release:
    """The manifest, checked before it is believed.

    The signature covers the release block exactly as it was written, so it is taken from the
    raw bytes rather than from anything re-encoded: re-encoding is how a signature that should
    have failed comes to pass.
    """
    try:
        whole = json.loads(raw.decode("utf-8"))
        body = whole["release"]
        signature = whole["signature"]
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise Refused("the update file is not readable")
    verify(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"), signature, key)
    try:
        return Release(version=str(body["version"]), url=str(body["url"]),
                       sha256=str(body["sha256"]).lower(), notes=str(body.get("notes", "")),
                       bytes=int(body.get("bytes", 0)))
    except (KeyError, TypeError, ValueError):
        raise Refused("the update file is missing something it needs")


def headers() -> dict:
    """Who we say we are. Python's own default is "Python-urllib/3.x", which a good many
    content networks treat as a robot worth hanging up on -- and hanging up is exactly what a
    reset connection is. Saying plainly what this is, and where it comes from, costs nothing
    and means anyone looking at their logs can tell a prayer mat from a nuisance."""
    from . import __version__
    return {"User-Agent": f"Salaah/{__version__} (+https://github.com/ProntoHS/Mysalaah)",
            "Accept": "*/*"}


def open_url(url: str, timeout: float | None = None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers()),
                                  timeout=timeout)


def fetch(url: str, into: Path | None = None, most: int = MOST, opener=None,
          tries: int = TRIES, missing: str = "") -> bytes | Path:
    """Fetches a URL, giving up rather than filling the disk. Returns the bytes, or the path if
    [into] was given.

    A download cut off part way is not a fault worth showing anyone: home wifi does this, and
    the answer is to ask again rather than to put an error on a prayer mat. So a connection
    that drops is retried. A refusal that would come back the same every time -- a missing
    file, a file that is too big -- is not.
    """
    opener = opener or open_url
    last = None
    for attempt in range(1, max(1, tries) + 1):
        try:
            return fetch_once(url, into, most, opener)
        except Refused:
            raise                       # our own refusals are decisions, not accidents
        except urllib.error.HTTPError as problem:
            # 404 is its own case because it is the ordinary one. Which 404 it is matters:
            # a missing manifest means nothing has been published, a missing zip means a
            # release exists but its file is not where it says. Those are different mistakes
            # with different fixes, and calling them the same thing cost an evening.
            if problem.code == 404:
                raise Refused(missing or "nothing has been published to update to yet")
            if problem.code < 500:
                raise Refused(f"could not reach the update: {problem}")
            last = problem              # the far end is having a bad day; it may pass
        except ValueError as problem:
            raise Refused(f"could not reach the update: {problem}")
        except (urllib.error.URLError, OSError) as problem:
            last = problem              # dropped, reset, timed out: worth another go
        if attempt < max(1, tries):
            time.sleep(PAUSE)
    raise Refused(f"could not reach the update: {last}")


def fetch_once(url: str, into: Path | None, most: int, opener) -> bytes | Path:
    """One attempt. Raises the underlying network error so fetch() can decide about trying
    again; raises Refused only for things that would happen again anyway."""
    with opener(url, timeout=TIMEOUT) as answer:
        if into is None:
            data = answer.read(most + 1)
            if len(data) > most:
                raise Refused("the update file is far larger than it should be")
            return data
        got = 0
        # "wb" truncates, so a retry starts the file again rather than appending to the
        # wreckage of the attempt before it.
        with open(into, "wb") as out:
            while True:
                lump = answer.read(CHUNK)
                if not lump:
                    break
                got += len(lump)
                if got > most:
                    raise Refused("the download is far larger than it should be")
                out.write(lump)
        return into


def check(url: str = "", opener=None, key: str = "") -> Release:
    """What is being offered. Raises Refused if it cannot be fetched or does not verify."""
    raw = fetch(url or DEFAULT_URL, opener=opener,
                missing="nothing has been published to update to yet")
    return read_manifest(raw, key)


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for lump in iter(lambda: f.read(CHUNK), b""):
            sha.update(lump)
    return sha.hexdigest()


def safe_members(zipped: zipfile.ZipFile, wanted: tuple = REPLACES) -> list:
    """The entries we are willing to write, and a refusal if the zip contains anything else.

    A zip can name an entry "../../.bashrc" or "/etc/passwd", and unpacking it without looking
    writes exactly there. It can also carry a symlink pointing anywhere. So every name has to
    sit under one of the directories this replaces, and nothing but plain files and directories
    is allowed through.
    """
    out = []
    for item in zipped.infolist():
        name = item.filename
        if name.endswith("/"):
            continue
        if (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise Refused("the update contains a link, which is not allowed")
        pure = Path(name)
        if pure.is_absolute() or ".." in pure.parts or name.startswith("/") or "\\" in name:
            raise Refused(f"the update tries to write outside itself: {name}")
        if not pure.parts or pure.parts[0] not in wanted:
            raise Refused(f"the update carries something unexpected: {name}")
        out.append(item)
    if not out:
        raise Refused("the update is empty")
    return out


def drop_bytecode(root: Path) -> int:
    """Delete every __pycache__ under root. Returns how many were removed.

    WHY AN UPDATE MUST DO THIS. Python will use a cached .pyc in preference to reading the .py
    beside it, and the whole of its check is that the source's modification time TO THE SECOND
    and its byte size still match what the cache recorded. Neither is a hash. So a .pyc built
    from an older module can sit next to a correct new one and win, and the app then runs code
    that is not in the file you are looking at.

    That is not theoretical: it happened twice in this project. Once while testing, where a
    deliberately broken file of the same length written in the same second left a cache the
    import system considered current, so a check passed against code that had been replaced.
    And once on the mat at 1.89, where the app died on

        ImportError: cannot import name 'ArrowButton' from 'salaah.render'

    with ArrowButton plainly defined in render.py on line 53.

    An update renames whole folders into place, so the mtimes it leaves behind are whatever the
    files were built with -- which is exactly the condition that can match a stale cache. Taking
    the caches out costs nothing: Python rebuilds them on the next import, once.

    Deliberately not fatal. A cache that cannot be removed is better than an update that will
    not install, and the worst case is the fault this prevents, which the guard already catches.
    """
    gone = 0
    for cache in sorted(root.rglob("__pycache__")):
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
            gone += not cache.exists()
    return gone


class Installer:
    """Puts a release in place, keeping the one it replaces so it can be undone.

    [root] is the folder holding salaah/ and assets/ -- the one run.sh sits in.
    """

    TRIAL = "trial"          # the version on trial, until it has run long enough to be trusted
    # Seconds a new version must run before it is considered good. Was sixty, which turned out
    # to be a trap rather than a safeguard: the guard reverts a version that is started a second
    # time without having settled, so ANY interruption inside that minute -- the mat switched
    # off, the app closed to have a look, a power cut -- silently put the previous version back
    # on the next boot. That cost two releases before anybody worked out what was happening,
    # and the mat gave no sign either time.
    #
    # Ten is what the trial is actually for. A version that will not start fails in its first
    # second or two: a bad import, a missing asset, a file that will not parse, Qt refusing a
    # screen. One that has kept a live event loop running for ten seconds has started. Beyond
    # that the trial is not protecting against anything, it is only a window in which a person
    # watching their mat can lose the update by touching it.
    SETTLES = 10.0

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def state_file(self) -> Path:
        return self.root / STATE

    def state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            return {}

    def write_state(self, **fields) -> None:
        # Written whole, through a temporary file, so a power cut cannot leave half a state
        # file -- which the guard would then be unable to read at the moment it matters most.
        spare = self.state_file.with_suffix(".tmp")
        spare.write_text(json.dumps(fields, indent=2))
        os.replace(spare, self.state_file)

    def unpack(self, zip_path: Path, release: Release) -> Path:
        """Checks the download and unpacks it beside the running version. Nothing is moved yet."""
        if digest(zip_path) != release.sha256:
            raise Refused("the download does not match what was promised; it may be damaged")
        staged = Path(tempfile.mkdtemp(prefix="salaah-new-", dir=str(self.root)))
        try:
            with zipfile.ZipFile(zip_path) as zipped:
                members = safe_members(zipped)
                for item in members:
                    zipped.extract(item, staged)
            for name in REPLACES:
                if not (staged / name).is_dir():
                    raise Refused(f"the update has no {name} folder in it")
        except Refused:
            shutil.rmtree(staged, ignore_errors=True)
            raise
        except (zipfile.BadZipFile, OSError) as problem:
            shutil.rmtree(staged, ignore_errors=True)
            raise Refused(f"the update could not be opened: {problem}")
        return staged

    def swap(self, staged: Path, release: Release, running: str) -> None:
        """Puts the new version in place by renaming, and remembers how to undo it.

        Renames rather than copies, so there is no moment where a folder is half written. The
        old version is kept next door under .prev for the guard to put back.
        """
        self.write_state(**{self.TRIAL: release.version, "was": running,
                            "at": time.time(), "attempts": 0})
        for name in REPLACES:
            live, prev = self.root / name, self.root / f"{name}.prev"
            if prev.exists():
                shutil.rmtree(prev, ignore_errors=True)
            if live.exists():
                os.replace(live, prev)
            os.replace(staged / name, live)
        shutil.rmtree(staged, ignore_errors=True)
        drop_bytecode(self.root)

    def settled(self) -> None:
        """Called by the app once it has been running long enough to be believed. Clears the
        trial, so the guard stops watching and the old version can be left alone."""
        state = self.state()
        if state.get(self.TRIAL):
            self.write_state(installed=state[self.TRIAL], at=time.time())

    def roll_back(self) -> bool:
        """Puts the previous version back. Used by the guard, not by the app."""
        state = self.state()
        if not state.get(self.TRIAL):
            return False
        for name in REPLACES:
            live, prev = self.root / name, self.root / f"{name}.prev"
            if not prev.is_dir():
                return False
        for name in REPLACES:
            live, prev = self.root / name, self.root / f"{name}.prev"
            broken = self.root / f"{name}.failed"
            shutil.rmtree(broken, ignore_errors=True)
            if live.exists():
                os.replace(live, broken)
            os.replace(prev, live)
            shutil.rmtree(broken, ignore_errors=True)
        # The same reasoning as in swap(). A rollback puts a different set of modules back under
        # the same names, so any cache left over describes the version that just failed.
        drop_bytecode(self.root)
        self.write_state(rolled_back_from=state[self.TRIAL], at=time.time())
        return True


def install(release: Release, root: Path, opener=None) -> None:
    """Fetch, check and put in place. Raises Refused, having changed nothing, if anything is
    wrong with what came down."""
    from . import __version__
    hold = Path(tempfile.mkdtemp(prefix="salaah-dl-"))
    try:
        zip_path = fetch(release.url, into=hold / "release.zip", opener=opener,
                         missing="this version was announced but its file is not there")
        installer = Installer(root)
        staged = installer.unpack(Path(zip_path), release)
        installer.swap(staged, release, __version__)
    finally:
        shutil.rmtree(hold, ignore_errors=True)
