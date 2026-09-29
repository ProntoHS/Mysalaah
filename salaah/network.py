"""Joining a wifi network, from the mat, without leaving the app.

Everything here goes through `nmcli`, which is how Raspberry Pi OS has managed networks since
Bookworm. No desktop is involved and no root password is asked for: the pi user may already do
this, and where it may not, the failure comes back as a plain refusal rather than a hang.

Three rules run through the whole file, and all three come from watching the real mat fail.

  1. JOINED IS NOT ONLINE. The mat sat associated to the wifi all evening and still could not
     reach anything -- the name lookup was failing. A screen that says "Connected" the moment
     the radio associates would have lied in exactly that situation, so `online()` resolves a
     name and nothing here calls a connection good until it does.

  2. NEVER COST SOMEBODY THE NETWORK THEY HAD. `nmcli device wifi connect` with a wrong password
     can leave the device disconnected, so a typo in the kitchen would take out the working
     connection. `join()` remembers what was active, and on any failure puts it back.

  3. SAY WHICH THING WENT WRONG. A wrong password, a network out of range and a router that
     never answers are three different problems with three different things to do about them.
     nmcli distinguishes them and so does this.

The commands are run through a `runner` that can be swapped out, so all of this can be tested
against recorded nmcli output on a machine that has no nmcli and no wifi -- which is where it
was written. The real runner is the only part that cannot be tested here, so it is kept to the
smallest thing that could work.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 45           # seconds; joining a network can genuinely take half a minute
LOOKUP = "raw.githubusercontent.com"     # what the mat actually needs to reach to update


@dataclass(frozen=True)
class Network:
    """One wifi network, as offered on the screen."""

    name: str
    strength: int          # 0-100 as nmcli reports it
    secured: bool
    known: bool = False    # already saved, so joining it needs no password

    @property
    def bars(self) -> int:
        """Nought to four, for drawing. Thresholds are the usual ones."""
        for edge, bars in ((80, 4), (55, 3), (30, 2), (5, 1)):
            if self.strength >= edge:
                return bars
        return 0


def run_nmcli(args: list[str], timeout: int = TIMEOUT) -> tuple[int, str, str]:
    """Really run nmcli. The one piece here that cannot be tested without a Pi."""
    if shutil.which("nmcli") is None:
        return 127, "", "nmcli is not installed"
    try:
        done = subprocess.run(["nmcli"] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "nmcli did not answer"
    except OSError as why:
        return 1, "", str(why)
    return done.returncode, done.stdout, done.stderr


def looks_up(name: str = LOOKUP) -> bool:
    """Whether a name can be resolved. The real test of being online."""
    try:
        socket.getaddrinfo(name, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    return True


class Wifi:
    """What the screen talks to."""

    def __init__(self, runner=run_nmcli, resolver=looks_up):
        self.run = runner
        self.resolver = resolver

    # -- looking --------------------------------------------------------------------------

    def there(self) -> bool:
        """Whether this mat can manage its wifi at all. A mat on ethernet with no wifi card
        should not be offered a screen full of nothing."""
        code, out, _ = self.run(["-t", "-f", "TYPE", "device", "status"], timeout=10)
        return code == 0 and any(line.strip() == "wifi" for line in out.splitlines())

    def known_names(self) -> set[str]:
        code, out, _ = self.run(["-t", "-f", "NAME,TYPE", "connection", "show"], timeout=10)
        if code != 0:
            return set()
        names = set()
        for line in out.splitlines():
            parts = unescape(line).split("\x00")
            if len(parts) >= 2 and "wireless" in parts[1]:
                names.add(parts[0])
        return names

    def scan(self) -> list[Network]:
        """The networks in range, strongest first, each one once.

        Deduplicated by name on purpose. A house with a mesh or with 2.4 and 5GHz under one
        name reports the same network several times -- the real mat saw its own five times --
        and a list with five identical rows looks broken. The strongest is kept.
        """
        code, out, _ = self.run(["-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"])
        if code != 0:
            return []
        known = self.known_names()
        best: dict[str, Network] = {}
        for line in out.splitlines():
            parts = unescape(line).split("\x00")
            if len(parts) < 3:
                continue
            name, strength, security = parts[0], parts[1], parts[2]
            if not name.strip():
                continue          # a hidden network has no name to show or to tap
            try:
                signal = int(strength)
            except ValueError:
                continue
            found = Network(name=name, strength=signal,
                            secured=bool(security.strip()) and security.strip() != "--",
                            known=name in known)
            if name not in best or signal > best[name].strength:
                best[name] = found
        return sorted(best.values(), key=lambda n: -n.strength)

    def active(self) -> str:
        """The wifi network in use, or "" for none."""
        code, out, _ = self.run(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
                                timeout=10)
        if code != 0:
            return ""
        for line in out.splitlines():
            parts = unescape(line).split("\x00")
            if len(parts) >= 2 and "wireless" in parts[1]:
                return parts[0]
        return ""

    def online(self) -> bool:
        """Not "is the radio associated" but "can this mat actually reach anything"."""
        return bool(self.resolver())

    # -- joining --------------------------------------------------------------------------

    def join(self, name: str, password: str = "") -> tuple[bool, str]:
        """Join a network. Returns (joined, why-not).

        On any failure the network that was in use beforehand is put back, so trying a new one
        and getting the password wrong cannot cost somebody the connection they already had.
        """
        was = self.active()
        args = ["device", "wifi", "connect", name]
        if password:
            args += ["password", password]
        code, out, err = self.run(args)
        if code == 0 and self.online():
            return True, ""

        why = reason(code, out + " " + err, joined=code == 0)
        if was and was != name:
            self.run(["connection", "up", was], timeout=TIMEOUT)
        return False, why

    def forget(self, name: str) -> bool:
        code, _, _ = self.run(["connection", "delete", name], timeout=10)
        return code == 0


def unescape(line: str) -> str:
    r"""nmcli -t escapes colons in values as \:, so a name with a colon in it does not split the
    row into the wrong number of pieces. Turn the separators into NULs and the escapes back into
    plain colons, which is the only way to read a name like "Joe: Wifi" correctly."""
    out, i = [], 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            out.append(line[i + 1])
            i += 2
        elif line[i] == ":":
            out.append("\x00")
            i += 1
        else:
            out.append(line[i])
            i += 1
    return "".join(out)


# What nmcli says, and what a person on a prayer mat should be told instead. Matched on the
# distinctive part of the message rather than the whole of it, because the wording carries the
# network name and varies between versions.
TROUBLE = (
    ("secrets were required", "password"),
    ("no network with ssid", "range"),
    ("property type mismatch", "password"),
    ("invalid password", "password"),
    ("802.1x supplicant", "password"),
    ("timeout", "slow"),
    ("timed out", "slow"),
    ("not authorized", "permission"),
    ("not permitted", "permission"),
    ("not installed", "missing"),
)


def reason(code: int, said: str, joined: bool = False) -> str:
    """Which kind of failure this was, as a word the screen turns into a sentence."""
    if joined:
        # nmcli was happy and the name still would not resolve: on the network, not on the
        # internet. This is the one the real mat hit, and it has its own word because the
        # thing to do about it is different -- look at the router, not the password.
        return "no_internet"
    low = said.lower()
    for mark, why in TROUBLE:
        if mark in low:
            return why
    if code == 124:
        return "slow"
    return "unknown"


# -- the way in when the screen itself is the thing that is broken -------------------------
#
# Every other fault on this mat can be fixed by shipping a new version. A broken wifi screen on
# a mat that cannot reach the internet cannot: there is no route in. run.sh puts the previous
# version back when a new one CRASHES, but a version that starts perfectly well and has a
# useless wifi screen sails straight past that guard.
#
# So there is a way in that does not involve the app at all. Write two lines on the SD card from
# any computer -- the boot partition is FAT32, so Windows and macOS can both see it -- and the
# mat joins that network next time it starts:
#
#     network: TheirWifi
#     password: whatever it is
#
# The password is wiped from the file as soon as it has been used, and NetworkManager keeps it
# from then on in its own store, which is root-only. So the plain text lives from the moment it
# is written until the mat's next start, and not after. That shortens the exposure; it does not
# remove it, and it is the same trust as the Pi Imager asking for the wifi password when the
# card is first written.

HATCH = Path("/boot/firmware/salaah-wifi.txt")


def read_hatch(path: Path) -> tuple[str, str]:
    """The network and password written on the card, or ("", "")."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "", ""
    found = {}
    for line in lines:
        if line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        found[key.strip().lower()] = value.strip()
    return found.get("network", ""), found.get("password", "")


def wipe_hatch(path: Path, name: str, when: str) -> bool:
    """Take the password back out, leaving a note of what was joined.

    Rewritten rather than deleted: somebody who put the file there should be able to see that
    the mat read it. If the card is read-only the write fails, which is reported rather than
    thrown -- the mat is on the network either way, and that was the point.
    """
    note = (f"# Read by the mat on {when} and joined: {name}\n"
            f"# The password has been removed. To use this again, write both lines back:\n"
            f"#     network: your wifi name\n"
            f"#     password: your wifi password\n"
            f"network: {name}\n"
            f"password:\n")
    try:
        path.write_text(note, encoding="utf-8")
    except OSError:
        return False
    return True


def join_from_the_card(wifi: "Wifi", path: Path = HATCH, when: str = "") -> str:
    """Join whatever the card says, if anything. Returns a line for the log, or "".

    Runs before the screen is up and must never stop the mat starting, so every failure here is
    a message and nothing else. It does nothing at all when the mat is already online: the file
    is a way in, not something that re-joins a network every time it boots.
    """
    name, password = read_hatch(path)
    if not name:
        return ""
    if wifi.online():
        wipe_hatch(path, name, when or "startup")
        return f"wifi: already online, so {path.name} was not used"
    joined, why = wifi.join(name, password)
    if not joined:
        return f"wifi: {path.name} named {name!r} but joining failed ({why})"
    tidied = wipe_hatch(path, name, when or "startup")
    return (f"wifi: joined {name!r} from {path.name}"
            + ("" if tidied else f"; could not clear the password from {path} (read-only card?)"))
