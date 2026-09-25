"""The power button on J2, and the screens it puts to sleep.

The Pi 5's power button is not a hardware switch. A short press arrives as an ordinary input
event -- KEY_POWER, from a device the kernel calls "pwr_button" -- and whoever reads that event
decides what it means. Raspberry Pi OS lets systemd-logind read it and shut the machine down.
This reads it first and blanks the screens instead, which is why the mat sleeps and wakes rather
than rebooting. The two things the button does in hardware are untouched: a long hold still
forces the board off, and a press while the board is halted still starts it.

Nothing here needs evdev or any other package: an input event is a fixed-size struct on a file
you can read, and the struct's size follows the platform, so the same code is right on a 32-bit
and a 64-bit Pi.

Two ways to stop logind shutting the mat down when the button is pressed. This grabs the device,
which makes it the only reader, and that is usually enough on its own. The certain way is to tell
logind not to care, which the README explains; grabbing then makes no difference. If the app
stops, the grab goes with it and the button shuts the Pi down again, which is the right way round
for something that has stopped responding.
"""
from __future__ import annotations

import fcntl
import select
import struct
import subprocess
import threading
import time
from typing import Callable

EV_KEY = 0x01
KEY_POWER = 116
EVENT = "llHHi"                     # struct input_event: timeval, type, code, value
EVENT_SIZE = struct.calcsize(EVENT)
EVIOCGRAB = 0x40044590              # _IOW('E', 0x90, int)

LISTING = "/proc/bus/input/devices"
# What the kernel has called this device. Matched loosely, as the name is not a promise.
NAMES = ("pwr_button", "power button", "power-button")


def power_device(listing: str) -> str | None:
    """The input device the power button speaks through, read out of /proc/bus/input/devices.

    Looked up by name rather than by a fixed event number, because the number moves about with
    whatever else is plugged in -- a keyboard, a Bluetooth ring -- and a mat that slept only when
    nothing else was connected would be a puzzling thing to own.
    """
    for block in listing.split("\n\n"):
        name, handlers = "", []
        for line in block.splitlines():
            if line.startswith("N: Name="):
                name = line.partition("=")[2].strip().strip('"').lower()
            elif line.startswith("H: Handlers="):
                handlers = line.partition("=")[2].split()
        if name and any(want in name for want in NAMES):
            for handler in handlers:
                if handler.startswith("event"):
                    return f"/dev/input/{handler}"
    return None


class PressWatch:
    """Turns key down and key up into the one question worth asking: was that a deliberate press?

    Acting on release rather than on press means a hold can be told from a click. A hold longer
    than HOLD is someone leaning on the button to force the board off, so it is left alone -- the
    screens should not blink on the way to a hard shutdown.
    """

    HOLD = 1.5

    def __init__(self, hold: float = HOLD):
        self.hold = hold
        self.down: float | None = None

    def event(self, value: int, now: float) -> bool:
        if value == 1:                      # pressed
            self.down = now
            return False
        if value == 0:                      # released
            began, self.down = self.down, None
            return began is not None and now - began <= self.hold
        return False                        # 2 = auto-repeat while held


class PowerButton:
    """Watches the power button on a background thread and calls [on_press] for each short press.

    [on_press] runs on that thread, so it should do no more than pass the news along; the app
    hands it a Qt signal.
    """

    WAIT = 0.5          # how long to sit in select before looking at whether we have been stopped

    def __init__(self, on_press: Callable[[], None], listing: str = LISTING,
                 hold: float = PressWatch.HOLD):
        self.on_press = on_press
        self.listing = listing
        self.watch = PressWatch(hold)
        self.path: str | None = None
        self.grabbed = False
        self.why: str = ""              # empty while it is working; otherwise why it is not
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def find(self) -> str | None:
        try:
            with open(self.listing, encoding="utf-8", errors="replace") as f:
                return power_device(f.read())
        except OSError:
            return None

    def start(self) -> bool:
        """Begins watching. False, with [why] set, if there is nothing to watch or no way in."""
        self.path = self.find()
        if self.path is None:
            self.why = "no power button among the input devices"
            return False
        try:
            handle = open(self.path, "rb", buffering=0)
        except OSError as problem:
            # Almost always the permissions: these devices belong to the input group.
            self.why = f"cannot read {self.path} ({problem.strerror}); is this user in the "
            self.why += "input group?"
            return False
        try:
            fcntl.ioctl(handle, EVIOCGRAB, 1)
            self.grabbed = True
        except OSError:
            # Still readable. logind will also see the presses, so it has to be told to ignore
            # them; without that the Pi shuts down on the first press.
            self.grabbed = False
        self._thread = threading.Thread(target=self._run, args=(handle,), name="power-button",
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self, handle) -> None:
        try:
            while not self._stop.is_set():
                try:
                    ready, _, _ = select.select([handle], [], [], self.WAIT)
                except (OSError, ValueError):
                    return
                if not ready:
                    continue
                try:
                    data = handle.read(EVENT_SIZE * 8)
                except OSError:
                    return                  # the device went away
                if not data:
                    return
                for start in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _, _, kind, code, value = struct.unpack(
                        EVENT, data[start:start + EVENT_SIZE])
                    if kind == EV_KEY and code == KEY_POWER:
                        if self.watch.event(value, time.monotonic()):
                            self.on_press()
        finally:
            try:
                if self.grabbed:
                    fcntl.ioctl(handle, EVIOCGRAB, 0)
                handle.close()
            except OSError:
                pass


class Outputs:
    """Switches the screens themselves off and on, rather than painting them black.

    A black screen still lights its backlight, which is most of what a panel costs to run, so
    painting black would save almost nothing -- and saving power is the whole point. This asks the
    compositor to power the outputs down instead. labwc, which the mat runs, speaks the protocol
    wlopm uses; without wlopm installed the app still sleeps, but the panels stay lit, so the
    README says to install it.
    """

    COMMAND = "wlopm"

    def __init__(self, command: str = COMMAND, run=subprocess.run):
        self.command = command
        self.run = run
        self.why: str = ""

    def set(self, on: bool) -> bool:
        """Powers every output on or off. False if that could not be done, with [why] set."""
        try:
            done = self.run([self.command, "--on" if on else "--off", "*"],
                            capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            self.why = f"{self.command} is not installed, so the screens stay lit while asleep"
            return False
        except (OSError, subprocess.SubprocessError) as problem:
            self.why = f"{self.command} failed: {problem}"
            return False
        if done.returncode != 0:
            self.why = f"{self.command} refused: {(done.stderr or '').strip()}"
            return False
        self.why = ""
        return True
