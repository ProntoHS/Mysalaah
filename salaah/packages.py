"""What the Pi's own software has outstanding -- counted, written down, and never acted on.

Harry, 27 November 2026, asking whether the mat should update its packages when it updates
itself: "could i have something in place that updates packages like sudo update. i am thinking
that if the mat is being updated, should packages/software on pi be updated at same time?"

THE ANSWER WAS NO, AND THIS IS WHAT WENT IN INSTEAD. The reasons are worth keeping, because
the question is a reasonable one and will be asked again:

  * The app update is also the repair route. If an OS upgrade breaks Python or Qt the app
    will not start -- and the app is how every future fix reaches the mat. run.sh puts the old
    APP VERSION back when a new one will not start; it cannot put back a Qt or a Python that
    apt replaced. Coupled, one bad night takes out both the product and the way to repair it.
  * PyQt6 is pip-installed on the mat with --break-system-packages. An apt move of python3 to
    a new minor version would strand it in the old interpreter's site-packages and the mat
    would boot to nothing. This is not hypothetical: it happened to Harry's Windows machine on
    26 November, where a Python upgrade overnight left `cryptography` behind and stopped a
    release being signed.
  * An app update runs when a child presses Update. An apt upgrade can pull a kernel or a
    bootloader and want a reboot, possibly at a prayer time, on a device with no keyboard.
  * It is one mat, not a fleet, and Harry has SSH to it. Little to gain by automating; a lot
    to lose when it goes wrong with nobody watching.

So this module COUNTS AND TELLS. It changes nothing, needs no root, and holds no opinion about
whether the updates should be applied -- that stays a decision made by a person sitting in
front of it, which is how Harry took the 77-package upgrade on the evening this was written.

Three rules it must keep, since it runs unattended on a child's device:

  1. NOTHING IS MODIFIED. `apt-get -s` simulates; Debug::NoLocking lets it run without the
     dpkg lock and therefore without root. There is no code path here that installs anything.
  2. NOTHING BLOCKS. The subprocess has a timeout and the whole thing runs off the UI thread.
  3. NOTHING THROWS. A failure writes one line and is otherwise forgotten. A mat must not fail
     to show a prayer time because apt was busy.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

#: Two minutes after the app starts, then once a day. Not at start: the first seconds belong
#: to getting a prayer time on the screen, and apt reading its lists off an SD card is slow
#: enough to be felt.
FIRST_AFTER = 120.0
THEN_EVERY = 24 * 60 * 60.0

#: Long enough for a Pi reading apt's lists off an SD card, short enough that a wedged apt is
#: forgotten rather than waited on.
PATIENCE = 120.0

LISTS = Path("/var/lib/apt/lists")

#: `apt-get -s upgrade` rather than full-upgrade: upgrade never removes a package to satisfy
#: a dependency, so what it counts is the conservative number and nothing in this report can
#: be read as a suggestion to remove something. What full-upgrade would additionally do shows
#: up here as the kept-back count instead.
COMMAND = ("apt-get", "-s", "-o", "Debug::NoLocking=true", "upgrade")

#: EVERY CALL IS MADE IN C. apt's summary line is translated, and the mat runs in whichever of
#: nine languages a child has chosen -- on an Urdu mat the English words below would simply
#: not be there and every count would silently be zero. Forcing the locale is the difference
#: between a report and a decoration.
PLAIN = {"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}

_INST = re.compile(r"^Inst\s+(\S+)\s+.*?\((.*)\)\s*$", re.MULTILINE)
_SUMMARY = re.compile(r"^(\d+) upgraded, (\d+) newly installed, (\d+) to remove"
                      r" and (\d+) not upgraded\.", re.MULTILINE)


@dataclass(frozen=True)
class Outstanding:
    """What apt says is waiting. Every count is -1 when it could not be worked out, never 0:
    zero outstanding updates and "I could not ask" are opposite pieces of news and must not
    read the same in a log."""

    total: int = -1
    security: int = -1
    held: int = -1
    #: How many days since apt last fetched its package lists. None when unknown.
    lists_age: float | None = None
    trouble: str = ""

    @property
    def known(self) -> bool:
        return self.total >= 0


def how_stale(lists: Path = LISTS, now=time.time) -> float | None:
    """Days since apt last fetched its lists, from the newest thing in the lists folder.

    THIS IS NOT A DETAIL. `apt-get -s upgrade` counts against whatever was last fetched, and
    fetching needs root, so this module can never refresh them. On a mat whose apt-daily timer
    is not running, "0 updates outstanding" would mean "nothing new since the last fetch,
    whenever that was" -- which could be a year. The number is worthless without its age, so
    they are reported together or not at all.
    """
    try:
        newest = max((p.stat().st_mtime for p in lists.iterdir() if p.is_file()), default=None)
    except OSError:
        return None
    if newest is None:
        return None
    return max(0.0, (now() - newest) / 86400.0)


def read(output: str) -> tuple[int, int, int]:
    """(total, security, held) out of apt's simulated upgrade.

    The totals come from the summary line and the security count from the Inst lines, which
    name the archive each upgrade would come from -- `Debian-Security:12/stable` and the like.
    Matched on the word rather than on a particular archive name, because Raspberry Pi OS,
    Debian and Ubuntu all spell theirs differently and the mat may yet be any of them.
    """
    summary = _SUMMARY.search(output)
    if summary is None:
        return -1, -1, -1
    total, _new, _gone, held = (int(n) for n in summary.groups())
    security = sum(1 for _name, origin in _INST.findall(output) if "security" in origin.lower())
    return total, security, held


def count(run=subprocess.run, lists: Path = LISTS, now=time.time) -> Outstanding:
    """Ask apt what is waiting. Never raises; a failure comes back as trouble."""
    age = how_stale(lists, now)
    try:
        done = run(list(COMMAND), capture_output=True, text=True,
                   timeout=PATIENCE, env=dict(PLAIN), check=False)
    except FileNotFoundError:
        return Outstanding(lists_age=age, trouble="there is no apt on this machine")
    except subprocess.TimeoutExpired:
        return Outstanding(lists_age=age,
                           trouble=f"apt did not answer within {PATIENCE:.0f}s")
    except Exception as why:                    # noqa: BLE001 - see the module docstring
        return Outstanding(lists_age=age, trouble=f"could not ask apt ({why})")
    if done.returncode != 0:
        first = (done.stderr or done.stdout or "").strip().splitlines()
        return Outstanding(lists_age=age,
                           trouble=f"apt said no ({first[0] if first else 'no reason given'})")
    total, security, held = read(done.stdout or "")
    if total < 0:
        return Outstanding(lists_age=age, trouble="apt's answer did not have a summary in it")
    return Outstanding(total=total, security=security, held=held, lists_age=age)


def sentence(what: Outstanding) -> str:
    """One line for the journal. Read by a person with `journalctl -t salaah`, so it is
    written as a sentence rather than as fields."""
    if not what.known:
        return f"packages: {what.trouble or 'nothing could be worked out'}"
    if what.total == 0:
        body = "nothing outstanding"
    else:
        body = f"{what.total} update{'' if what.total == 1 else 's'} outstanding"
        if what.security > 0:
            body += f", {what.security} of them security"
        elif what.security == 0:
            body += ", none of them security"
    if what.held > 0:
        body += f"; {what.held} held back"
    if what.lists_age is None:
        body += " (package lists: age unknown)"
    else:
        body += f" (lists last fetched {what.lists_age:.1f} days ago)"
    return f"packages: {body}. Nothing has been changed."


def report(log=None, run=subprocess.run, lists: Path = LISTS, now=time.time) -> str:
    """Count and say so. Returns the line as well as logging it, so a test can read it."""
    line = sentence(count(run=run, lists=lists, now=now))
    if log is None:
        print(line, file=sys.stderr)
    else:
        log(line)
    return line


def report_quietly(log=None, run=subprocess.run) -> None:
    """Fire and forget, off the UI thread. The swallow is deliberate and total -- this is the
    last line of a thread nothing joins and nothing checks, exactly as onthemap.py says."""
    import threading

    def quietly():
        try:
            report(log=log, run=run)
        except Exception:                       # noqa: BLE001 - see above
            pass

    threading.Thread(target=quietly, daemon=True, name="packages").start()
