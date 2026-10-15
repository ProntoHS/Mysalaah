"""Pairing a wireless speaker or headset from the mat, without leaving the app.

Everything here goes through `bluetoothctl`, which is how BlueZ is driven from a script. It is
the same shape as network.py, for the same reason: the commands run through a `runner` that can
be swapped out, so all of this is tested against recorded bluetoothctl output on a machine with
no Bluetooth adapter and no BlueZ -- which is where it was written. The real runner is the only
part that cannot be tested here, so it is kept to the smallest thing that could work.

WHAT WAS MEASURED ON THE MAT, AND WHAT IT SETTLED

Harry ran a probe on the mat on 14 October 2026 and sent the output back. Four things in this
file come from that run rather than from a manual:

  1. THE APP DOES NOT HAVE TO ROUTE ANYTHING. The mat runs PipeWire 1.4.2 with WirePlumber. He
     connected a speaker by hand and `wpctl status` showed

         Sinks:
            35. Built-in Audio Digital Stereo (HDMI) [vol: 1.00]
            56. Built-in Audio Digital Stereo (HDMI) [vol: 0.95]
          * 79. XinYi                                [vol: 0.40]

     -- the star had moved to the speaker on its own, and mpg123 played to it without being
     told. So nothing in this file moves an output, and nothing in audio.py changed. Connecting
     is the whole job. `sound_goes_to()` exists only to SAY where the sound is going; if it is
     wrong or missing the mat is unaffected.

  2. `devices Connected` NEEDS THE CAPITAL. `bluetoothctl devices connected` came back
     "Invalid argument connected". The word is a filter name, not a flag, and it is matched
     case-sensitively. CONNECTED below is spelt the way the mat accepted.

  3. pactl IS NOT INSTALLED, wpctl IS. The PulseAudio command-line tools are not on this image,
     so `sound_goes_to()` asks WirePlumber. Anything else that ever needs to know about outputs
     should do the same rather than reaching for pactl.

  4. THE CONTROLLER CAN DRIVE A SPEAKER. `bluetoothctl show` listed Audio Source (0000110a)
     among the controller's UUIDs, which is the profile that sends sound out. Without it this
     screen would have been a button that could never work.

THREE RULES, THE SAME THREE AS THE WIFI SCREEN

  * PAIRED IS NOT CONNECTED AND CONNECTED IS NOT PLAYING. A speaker can be bonded and silent.
    The circle in Settings goes green for a device that is connected AND looks like audio, not
    for one the mat merely remembers.

  * NEVER COST SOMEBODY WHAT THEY HAD. Nothing here disconnects anything the person did not ask
    to disconnect -- and in particular nothing touches the ring, which is a different kind of
    link on the same adapter. `forget()` is the only destructive call and only a button reaches
    it.

  * SAY WHICH THING WENT WRONG. A speaker that is off, one that refused the pairing and one the
    mat is not allowed to pair are three problems with three different things to do about them.
    BlueZ distinguishes them in its error names and so does `reason()`.

WHAT THIS DELIBERATELY DOES NOT DO. It does not type a PIN. A speaker or a headset pairs with
no number ("Just Works") and that is the whole of what this screen is for; a device that wants
a number asks bluetoothctl interactively, which a one-shot command cannot answer, and the
attempt comes back as "refused" rather than hanging. Pairing such a device is still possible
from the Pi's own Bluetooth menu. Adding a number pad here would be easy and would mostly serve
devices this mat has no business connecting to.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

TIMEOUT = 30            # seconds; pairing genuinely takes ten or more
LOOK_FOR = 10           # how long a look round lasts
CONNECTED = "Connected"  # the capital matters -- see the note at the top

# Bluetooth's "major device class" for anything that makes a noise: headsets, speakers,
# headphones, car kits. Bits 8-12 of the class word.
AUDIO_CLASS = 0x04

# What a speaker advertises. A2DP Sink is the one that matters -- it means the device can be
# played TO. The headset profiles come along for headsets with a microphone.
AUDIO_UUIDS = ("0000110b", "0000110a", "0000110d", "0000111e", "00001108")

# Icons BlueZ gives things that make a noise.
AUDIO_ICONS = ("audio-card", "audio-headset", "audio-headphones", "audio-speakers")

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
MAC = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")


@dataclass(frozen=True)
class Speaker:
    """One Bluetooth device, as offered on the screen."""

    mac: str
    name: str = ""
    paired: bool = False
    trusted: bool = False
    connected: bool = False
    audio: bool | None = None       # True, False, or None for "nothing said either way"
    strength: int | None = None     # RSSI in dBm, as the scan reported it; negative, nearer 0
                                    # is closer. None when it was never advertised.

    @property
    def shown(self) -> str:
        """What to write on the row. A device with no name of its own shows its address, which
        is at least something to tell two of them apart by."""
        return self.name or self.mac

    @property
    def nameless(self) -> bool:
        """Whether the thing has no name but its own address.

        BlueZ fills the name in with the address-with-dashes when a device never gave one, and
        a list of those is a list of nothing a person can recognise. They are kept out of the
        screen rather than out of this file: the fact is worth knowing, the row is not worth
        showing.
        """
        if not self.name:
            return True
        plain = self.name.replace("-", ":").replace("_", ":").upper()
        return plain == self.mac.upper()

    @property
    def bars(self) -> int:
        """Nought to four, for drawing, from RSSI. The thresholds are the usual ones: -60dBm is
        the same room, -90 is barely there. Unknown strength draws full, because a device the
        mat already knows about is usually the one being looked for."""
        if self.strength is None:
            return 4
        for edge, bars in ((-60, 4), (-70, 3), (-80, 2), (-95, 1)):
            if self.strength >= edge:
                return bars
        return 0


def run_bluetoothctl(args: list[str], timeout: int = TIMEOUT) -> tuple[int, str, str]:
    """Really run bluetoothctl. The one piece here that cannot be tested without a Pi."""
    if shutil.which("bluetoothctl") is None:
        return 127, "", "bluetoothctl is not installed"
    try:
        done = subprocess.run(["bluetoothctl"] + args,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "bluetoothctl did not answer"
    except OSError as why:
        return 1, "", str(why)
    return done.returncode, done.stdout, done.stderr


def run_wpctl(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Really run wpctl, which is what this image has instead of pactl."""
    if shutil.which("wpctl") is None:
        return 127, "", "wpctl is not installed"
    try:
        done = subprocess.run(["wpctl"] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "wpctl did not answer"
    except OSError as why:
        return 1, "", str(why)
    return done.returncode, done.stdout, done.stderr


def tidy(text: str) -> str:
    """bluetoothctl paints its output when it thinks it has a terminal, and the colour codes
    land in the middle of names. Take them out before anything is read."""
    return ANSI.sub("", text.replace("\r", "\n"))


def is_audio(klass: int | None, icon: str, uuids: list[str]) -> bool | None:
    """Whether this thing makes a noise, from whatever the device said about itself.

    Three sources because no one of them is always there: a scan reports Class and sometimes
    Icon, `info` reports all three, and a device that has only ever been seen by name reports
    none. None means "nothing said either way", which the screen shows rather than hides --
    guessing a speaker is not a speaker would make it unreachable.
    """
    if icon:
        if any(icon.startswith(a) for a in AUDIO_ICONS) or icon.startswith("audio"):
            return True
    low = " ".join(uuids).lower()
    if any(u in low for u in AUDIO_UUIDS):
        return True
    if klass is not None:
        if (klass >> 8) & 0x1F == AUDIO_CLASS:
            return True
        return False        # a class was given and it was not audio: that is an answer
    if icon:
        return False        # an icon was given and it was not audio: also an answer
    return None


def as_class(value: str) -> int | None:
    try:
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    except (TypeError, ValueError):
        return None


class Sound:
    """What the screen talks to."""

    def __init__(self, runner=run_bluetoothctl, outputs=run_wpctl):
        self.run = runner
        self.outputs = outputs

    # -- looking ---------------------------------------------------------------------------

    def there(self) -> bool:
        """Whether this mat has a Bluetooth controller that is switched on.

        A mat with no adapter, or with the adapter turned off, should not be offered a screen
        full of nothing. Powered counts: an adapter that is present and off can find nothing,
        and the honest thing is to say so rather than to show an empty list.
        """
        code, out, err = self.run(["show"], timeout=10)
        if code != 0:
            return False
        text = tidy(out + err)
        if "No default controller" in text:
            return False
        return any(line.strip() == "Powered: yes" for line in text.splitlines())

    def about(self, mac: str) -> Speaker:
        """Everything bluetoothctl knows about one device."""
        code, out, err = self.run(["info", mac], timeout=10)
        if code != 0:
            return Speaker(mac=mac)
        return read_info(mac, tidy(out + err))

    def known(self) -> list[Speaker]:
        """Everything the mat remembers, with what it knows about each.

        `devices` gives names and addresses only, so each one is asked about in turn. The list
        is short -- it is the things somebody has paired to this mat -- so the extra calls cost
        little, and without them there is no way to tell a paired speaker from a paired ring.
        """
        return [self.about(mac) for mac, _ in self.listed([])]

    def connected(self) -> list[Speaker]:
        """Everything connected right now. The capital in CONNECTED is not optional."""
        return [self.about(mac) for mac, _ in self.listed([CONNECTED])]

    def listed(self, extra: list[str]) -> list[tuple[str, str]]:
        """(address, name) for `bluetoothctl devices [filter]`, in the order given."""
        code, out, err = self.run(["devices"] + extra, timeout=10)
        if code != 0:
            return []
        return pairs_in(tidy(out + err))

    def speaking(self) -> Speaker | None:
        """The connected device that makes a noise, if there is one. What the circle reads.

        The ring is connected to this same adapter and must not turn the circle green, which is
        why this asks what each connected thing IS rather than how many there are.
        """
        for device in self.connected():
            if device.audio:
                return device
        return None

    def look(self, seconds: int = LOOK_FOR) -> list[Speaker]:
        """Look round, and report what answered.

        The scan transcript is the source: bluetoothctl prints a line every time a device says
        something about itself, so one command gives names, addresses, signal strengths and
        classes together. Asking `info` about each one instead would be twenty more commands
        and several seconds on a screen somebody is waiting at.

        Everything the mat already knows is merged in afterwards, so a speaker that is paired
        but quiet still appears -- that is the one somebody is usually looking for.
        """
        code, out, err = self.run(["--timeout", str(seconds), "scan", "on"],
                                  timeout=seconds + 20)
        found: dict[str, Speaker] = {}
        if code == 0:
            found = read_scan(tidy(out + err))
        for device in self.known():
            was = found.get(device.mac)
            # What `info` says wins -- it is asked of BlueZ's own record rather than overheard
            # -- except for the signal strength, which only the scan ever has.
            found[device.mac] = (device if was is None
                                 else Speaker(mac=device.mac,
                                              name=device.name or was.name,
                                              paired=device.paired, trusted=device.trusted,
                                              connected=device.connected,
                                              audio=(device.audio if device.audio is not None
                                                     else was.audio),
                                              strength=was.strength))
        return sorted(found.values(), key=ordering)

    # -- joining ---------------------------------------------------------------------------

    def connect(self, mac: str) -> tuple[bool, str]:
        """Pair if need be, trust, and connect. Returns (connected, why-not).

        Trusted on purpose: a speaker that is not trusted has to be connected by hand again
        after every restart, and this mat is switched off at the wall. Trust is what makes it
        come back by itself.

        Pairing a device that is already paired is not an error worth showing -- BlueZ says
        AlreadyExists and the right thing to do is carry on to the connect.
        """
        known = self.about(mac)
        if not known.paired:
            code, out, err = self.run(["pair", mac], timeout=TIMEOUT)
            said = tidy(out + err)
            if code != 0 and not went_well(said, "paired", "AlreadyExists"):
                return False, reason(code, said)
        self.run(["trust", mac], timeout=10)
        code, out, err = self.run(["connect", mac], timeout=TIMEOUT)
        said = tidy(out + err)
        if code == 0 or went_well(said, "connection successful"):
            return True, ""
        return False, reason(code, said)

    def disconnect(self, mac: str) -> bool:
        code, out, err = self.run(["disconnect", mac], timeout=15)
        return code == 0 or went_well(tidy(out + err), "successful")

    def forget(self, mac: str) -> bool:
        """Take the device off the mat for good. The only destructive thing in this file."""
        code, out, err = self.run(["remove", mac], timeout=10)
        return code == 0 or went_well(tidy(out + err), "removed")

    # -- where the sound is actually going --------------------------------------------------

    def sound_goes_to(self) -> str:
        """The name of the default output, or "".

        Decoration, and deliberately so: the mat was measured moving its own default to a
        speaker the moment one connected, so nothing depends on this being right. It is here
        because "it says connected, but is the sound going there?" is the question anybody asks
        next, and one line answers it. Any failure is an empty string.
        """
        code, out, err = self.outputs(["status"], timeout=10)
        if code != 0:
            return ""
        return default_sink(tidy(out + err))


# -- reading what bluetoothctl said ----------------------------------------------------------


def pairs_in(text: str) -> list[tuple[str, str]]:
    """(address, name) for every "Device AA:BB:.. Some Name" line, each address once."""
    found: list[tuple[str, str]] = []
    seen = set()
    for line in text.splitlines():
        where = line.find("Device ")
        if where < 0:
            continue
        rest = line[where + len("Device "):].strip()
        hit = MAC.match(rest)
        if not hit:
            continue
        mac = hit.group(1).upper()
        if mac in seen:
            continue
        seen.add(mac)
        found.append((mac, rest[hit.end():].strip()))
    return found


def read_info(mac: str, text: str) -> Speaker:
    """One `bluetoothctl info` reply."""
    fields: dict[str, str] = {}
    uuids: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "UUID":
            uuids.append(value)
        elif key and key not in fields:
            fields[key] = value
    klass = as_class(fields.get("Class", ""))
    return Speaker(
        mac=mac.upper(),
        name=fields.get("Name") or fields.get("Alias") or "",
        paired=fields.get("Paired") == "yes" or fields.get("Bonded") == "yes",
        trusted=fields.get("Trusted") == "yes",
        connected=fields.get("Connected") == "yes",
        audio=is_audio(klass, fields.get("Icon", ""), uuids),
    )


def read_scan(text: str) -> dict[str, Speaker]:
    """A whole scan transcript, as a picture of what is out there.

    bluetoothctl reports a device piece by piece -- the address first, then whatever it
    overhears afterwards -- so this builds each one up line by line rather than expecting any
    single line to be complete.
    """
    names: dict[str, str] = {}
    classes: dict[str, int] = {}
    icons: dict[str, str] = {}
    rssi: dict[str, int] = {}
    order: list[str] = []
    for line in text.splitlines():
        where = line.find("Device ")
        if where < 0:
            continue
        rest = line[where + len("Device "):].strip()
        hit = MAC.match(rest)
        if not hit:
            continue
        mac = hit.group(1).upper()
        if mac not in order:
            order.append(mac)
        said = rest[hit.end():].strip()
        if not said:
            continue
        key, sep, value = said.partition(":")
        key, value = key.strip(), value.strip()
        if not sep:
            names[mac] = said          # "[NEW] Device AA:.. The Name"
        elif key == "Name" or key == "Alias":
            names[mac] = value
        elif key == "Class":
            got = as_class(value)
            if got is not None:
                classes[mac] = got
        elif key == "Icon":
            icons[mac] = value
        elif key == "RSSI":
            try:
                rssi[mac] = int(value)
            except ValueError:
                pass
    return {mac: Speaker(mac=mac, name=names.get(mac, ""),
                         audio=is_audio(classes.get(mac), icons.get(mac, ""), []),
                         strength=rssi.get(mac))
            for mac in order}


def default_sink(text: str) -> str:
    """The starred output in `wpctl status`, or "".

    wpctl lists sinks under "Sinks:" and marks the default with a star, like

        Sinks:
         *  79. XinYi                            [vol: 0.40]

    It prints the same headings again for video, so the reading stops at the end of the first
    block rather than taking whatever starred line comes last.
    """
    inside = False
    for line in text.splitlines():
        bare = line.strip(" │├└─\t")
        if bare.startswith("Sinks:"):
            inside = True
            continue
        if inside:
            # The block ends at the blank-ish line wpctl puts between sections, or at the next
            # heading if a version ever drops it. Either way the reading stops before "Sources:"
            # and before the whole Video tree, which has a starred line of its own.
            if not bare or bare.endswith(":"):
                break
            if not bare.startswith("*"):
                continue
            after = bare.lstrip("* ")
            _, _, rest = after.partition(".")
            name = (rest or after).strip()
            cut = name.rfind("[")
            if cut > 0:
                name = name[:cut]
            return name.strip()
    return ""


def ordering(device: Speaker) -> tuple:
    """Connected first, then paired, then whatever makes a noise, then the strongest signal,
    then by name so the list does not shuffle itself between scans."""
    return (not device.connected, not device.paired, device.audio is not True,
            -(device.strength if device.strength is not None else -50),
            device.shown.lower())


# What BlueZ says, and what a person on a prayer mat should be told instead. Matched on the
# distinctive part rather than the whole, because the wording carries names and addresses and
# differs between versions.
TROUBLE = (
    ("authenticationfailed", "refused"),
    ("authenticationcanceled", "refused"),
    ("authenticationrejected", "refused"),
    ("authenticationtimeout", "refused"),
    ("page-timeout", "off"),
    ("connectionattemptfailed", "off"),
    ("br-connection-page-timeout", "off"),
    ("br-connection-canceled", "off"),
    ("device not available", "off"),
    ("not available", "off"),
    ("notready", "adapter"),
    ("no default controller", "adapter"),
    ("inprogress", "busy"),
    ("already connected", "already"),
    ("alreadyexists", "already"),
    ("not authorized", "permission"),
    ("not permitted", "permission"),
    ("accessdenied", "permission"),
    ("not installed", "missing"),
    ("profile unavailable", "no_audio"),
    ("unavailable", "no_audio"),
)


def reason(code: int, said: str) -> str:
    """Which kind of failure this was, as a word the screen turns into a sentence."""
    low = said.lower()
    for mark, why in TROUBLE:
        if mark in low:
            return why
    if code == 124:
        return "slow"
    # Belt and braces. The runner's own words for a missing bluetoothctl carry "not installed",
    # so TROUBLE gets there first and this line is not normally reached -- it is here for a
    # version that exits 127 saying something else.
    if code == 127:
        return "missing"
    return "unknown"


def went_well(said: str, *marks: str) -> bool:
    """bluetoothctl has been known to say a thing worked and still exit non-zero. Where it says
    so in words, believe the words."""
    low = said.lower()
    return any(mark.lower() in low for mark in marks)
