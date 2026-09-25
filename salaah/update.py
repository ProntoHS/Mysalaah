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
MOST = 64 * 1024 * 1024  # the largest release we will pull down: a runaway file is a full disk
CHUNK = 64 * 1024

# What an update replaces. run.sh is not in the list on purpose: it is the guard that puts the
# old version back, so it cannot be one of the things a bad release can break.
REPLACES = ("salaah", "assets")
STATE = "update-state.json"


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


def fetch(url: str, into: Path | None = None, most: int = MOST, opener=None) -> bytes | Path:
    """Fetches a URL, giving up rather than filling the disk. Returns the bytes, or the path if
    [into] was given."""
    opener = opener or urllib.request.urlopen
    try:
        with opener(url, timeout=TIMEOUT) as answer:
            if into is None:
                data = answer.read(most + 1)
                if len(data) > most:
                    raise Refused("the update file is far larger than it should be")
                return data
            got = 0
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
    except Refused:
        raise
    except urllib.error.HTTPError as problem:
        if problem.code == 404:
            raise Refused("nothing has been published to update to yet")
        raise Refused(f"could not reach the update: {problem}")
    except (urllib.error.URLError, OSError, ValueError) as problem:
        raise Refused(f"could not reach the update: {problem}")


def check(url: str = "", opener=None, key: str = "") -> Release:
    """What is being offered. Raises Refused if it cannot be fetched or does not verify."""
    raw = fetch(url or DEFAULT_URL, opener=opener)
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


class Installer:
    """Puts a release in place, keeping the one it replaces so it can be undone.

    [root] is the folder holding salaah/ and assets/ -- the one run.sh sits in.
    """

    TRIAL = "trial"          # the version on trial, until it has run long enough to be trusted
    SETTLES = 60.0           # seconds a new version must run before it is considered good

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
        self.write_state(rolled_back_from=state[self.TRIAL], at=time.time())
        return True


def install(release: Release, root: Path, opener=None) -> None:
    """Fetch, check and put in place. Raises Refused, having changed nothing, if anything is
    wrong with what came down."""
    from . import __version__
    hold = Path(tempfile.mkdtemp(prefix="salaah-dl-"))
    try:
        zip_path = fetch(release.url, into=hold / "release.zip", opener=opener)
        installer = Installer(root)
        staged = installer.unpack(Path(zip_path), release)
        installer.swap(staged, release, __version__)
    finally:
        shutil.rmtree(hold, ignore_errors=True)
