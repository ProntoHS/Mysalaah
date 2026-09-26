"""Turning the monitor's own backlight up and down, over the cable that carries the picture.

Drawing a black veil over the screen only makes it *look* darker. The backlight stays at full
power, which on a mat running off a battery is the one thing that actually matters. Most desktop
monitors accept real brightness commands down the HDMI cable (DDC/CI), and ddcutil speaks that
protocol, so the setting can drive the real thing instead of pretending.

Everything here is best-effort and silent. A mat whose monitor does not answer -- a different
panel, a cable that does not carry the data lines, ddcutil not installed -- must still work. It
simply falls back to the veil, and nobody is shown an error about a monitor.

Two things this has to get right:

    It must never block the screen. DDC/CI is a slow bus: a single command takes the better part
    of a second. Doing that on the thread that draws the screen would freeze the app every time
    the slider moved. So the work happens on a thread of its own.

    It must not queue up. Dragging a slider produces dozens of values, and a monitor asked to
    obey all of them would still be catching up a minute later. Only the newest value is ever
    applied; the ones overtaken on the way are dropped.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import threading

FEATURE = "10"          # the DDC/CI code for brightness
LOOKING = 12.0          # seconds to allow for the first look: the bus is slow to enumerate
SETTING = 8.0           # seconds to allow for one change
LEAST = 10              # never below this: a mat nobody can see is a mat nobody can turn back up


class Backlight:
    """The monitor's brightness, if it will take instruction. [run] and [finder] are there so
    this can be tested without a monitor."""

    def __init__(self, run=None, finder=None):
        self.run = run or subprocess.run
        self.finder = finder or shutil.which
        self.lock = threading.Lock()
        self.looked = False
        self.answers = False
        self.which = None          # which display to talk to, when there is more than one
        self.wanted = None
        self.worker = None
        self.applied = []          # every value actually sent, for tests and for looking at

    @property
    def available(self) -> bool:
        """Whether this monitor takes brightness commands. Worked out once, then remembered:
        the answer cannot change without the cable changing, and asking is slow."""
        with self.lock:
            if self.looked:
                return self.answers
        answer = self.look()
        with self.lock:
            self.looked, self.answers = True, answer
            return self.answers

    def look(self) -> bool:
        """Find a display that will actually talk, and remember which one it is.

        A mat has two screens on the same bus: the monitor the words are on, and the small
        posture screen beside it. The little one has no brightness to set and reports "DDC
        communication failed". With more than one display present, a command that does not say
        which one it means is a command that may go nowhere -- so the number is picked up here
        and quoted on everything sent afterwards.
        """
        if not self.finder("ddcutil"):
            return False
        try:
            done = self.run(["ddcutil", "detect", "--brief"],
                            capture_output=True, text=True, timeout=LOOKING)
        except (OSError, subprocess.SubprocessError):
            return False
        # "Display 1" heads one that answered; "Invalid display" heads one that did not.
        found = re.findall(r"^Display\s+(\d+)", done.stdout or "", re.MULTILINE)
        if not found:
            return False
        self.which = found[0]
        return True

    def set(self, percent: int) -> None:
        """Ask for a brightness and return at once. The monitor is slow; the screen is not."""
        percent = max(LEAST, min(100, int(percent)))
        with self.lock:
            self.wanted = percent
            if self.worker is not None and self.worker.is_alive():
                return                     # the thread already running will pick this up
            self.worker = threading.Thread(target=self.work, daemon=True)
            self.worker.start()

    def work(self) -> None:
        while True:
            with self.lock:
                value, self.wanted = self.wanted, None
                if value is None:
                    self.worker = None
                    return
            if not self.available:
                with self.lock:
                    self.worker = None
                return
            self.apply(value)

    def apply(self, percent: int) -> None:
        said = ["ddcutil", "setvcp"]
        if self.which is not None:
            said += ["--display", self.which]
        try:
            self.run(said + [FEATURE, str(percent)],
                     capture_output=True, text=True, timeout=SETTING)
            self.applied.append(percent)
        except (OSError, subprocess.SubprocessError):
            pass        # a monitor that stops answering is not a reason to stop praying

    def settle(self, seconds: float = 20.0) -> None:
        """Wait for any outstanding change to reach the monitor. For tests and for shutdown."""
        with self.lock:
            worker = self.worker
        if worker is not None:
            worker.join(seconds)
