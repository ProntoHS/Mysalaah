"""The sleep switch on GPIO 17, and the screens it puts to sleep.

A plain normally-open momentary switch between **GPIO 17 (header pin 11)** and **ground (header
pin 9)**. Pressing it blanks both screens; pressing it again brings them back.

WHY NOT THE PI'S OWN POWER BUTTON ANY MORE. Until 1.98 this read the Pi 5's power button: a
short press on J2 arrives as an ordinary input event -- KEY_POWER, from a device the kernel
calls "pwr_button" -- and whoever reads that event first decides what it means, so this read it
before systemd-logind could shut the machine down. That worked, and it only worked on a Pi 5.
A Pi 4B has no such circuit and no such input device, so on a Pi 4 the app found nothing to
watch and said so, and the switch did nothing at all.

The mat runs on a Pi 4B now. A switch on a GPIO pin needs no power-button circuit, no input
group membership and no argument with logind, and it works the same on both boards -- GPIO 17
is in the same place on a Pi 4 and a Pi 5 -- so this is the more portable answer as well as the
one that works today. The three set-up steps the README used to list for logind and /dev/input
are gone with it.

WHAT WAS GIVEN UP. On a Pi 5 the onboard button did three things: a short press (read here), a
long hold (hardware force-off) and a press while halted (hardware start). Only the first was
ever software. Those other two still belong to whatever is wired to J2 and are untouched by
this -- but on a Pi 5 running this version, a short press on J2 goes back to logind and shuts
the mat down, unless logind is still told to ignore it. Worth knowing before moving the card
back to a Pi 5.

A PRESS, NOT A RELEASE. The old reader acted on release and ignored a hold longer than a second
and a half, and the reason was specific: on a Pi 5 a long hold is someone leaning on the button
to force the board off, and the screens should not blink on the way to a hard shutdown. A GPIO
switch has no hardware force-off behind it, so that reason has gone, and with it the delay --
a button whose job is to wake the screens should wake them when it is pressed rather than when
it is let go. The press filter that did that work has gone too; it had no other user.

gpiozero is imported where it is needed rather than at the top, because this module is also
imported by the tests, on machines with no GPIO at all.
"""
from __future__ import annotations

import subprocess
import threading
from typing import Callable

#: BCM numbering, which is what gpiozero speaks. GPIO 17 is physical pin 11; the ground beside
#: it is physical pin 9. Harry wired and tested this pair before it was written down here.
PIN = 17

#: Seconds gpiozero ignores further edges after one it has acted on. Mechanical switches chatter
#: for a few milliseconds and would otherwise read as several presses; 80 ms is what was tested
#: on the mat and comfortably longer than the chatter.
BOUNCE = 0.08


class SleepSwitch:
    """Watches the switch and calls [on_press] once for each press.

    REPLACES PowerButton. [on_press] runs on gpiozero's own callback thread, so it should do no
    more than pass the news along; the app hands it a Qt signal, which is queued onto the GUI
    thread and is the only safe thing to do from here.
    """

    def __init__(self, on_press: Callable[[], None], pin: int = PIN, bounce: float = BOUNCE,
                 button=None):
        self.on_press = on_press
        self.pin = pin
        self.bounce = bounce
        self._make = button                 # a stand-in, for the tests
        self.button = None
        self.why: str = ""                  # empty while it is working; otherwise why it is not
        self._lock = threading.Lock()

    @property
    def where(self) -> str:
        return f"GPIO {self.pin} (header pin 11)"

    def start(self) -> bool:
        """Begins watching. False, with [why] set, if there is no GPIO to watch."""
        make = self._make
        if make is None:
            try:
                from gpiozero import Button
            except ImportError:
                self.why = ("python3-gpiozero is not installed, so the sleep switch does "
                            "nothing; sudo apt install python3-gpiozero")
                return False
            make = Button
        try:
            self.button = make(self.pin, pull_up=True, bounce_time=self.bounce)
        except Exception as problem:
            # gpiozero raises BadPinFactory on anything that is not a Pi, and OSError or its own
            # GPIOPinInUse if the pin is taken. Caught broadly on purpose: whatever the reason,
            # the mat should start and say why the switch is quiet rather than refuse to run.
            self.why = f"cannot watch GPIO {self.pin}: {problem}"
            self.button = None
            return False
        self.button.when_pressed = self._pressed
        self.why = ""
        return True

    def _pressed(self, *_) -> None:
        """gpiozero passes the Button; the app does not care which one it was."""
        self.on_press()

    def stop(self) -> None:
        with self._lock:
            button, self.button = self.button, None
        if button is None:
            return
        try:
            button.when_pressed = None
            button.close()
        except Exception:
            pass                            # going away; nothing here is worth failing for


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

    def listing(self) -> dict[str, bool] | None:
        """What wlopm can see: {output name: whether it is on}. None if it could not be asked.

        wlopm with no arguments prints one line per output it has power over -- "HDMI-A-1 on".
        An output it cannot switch is simply absent, and that absence is the whole point of
        asking: see cannot_bring_back.
        """
        try:
            done = self.run([self.command], capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            self.why = f"{self.command} is not installed, so the screens stay lit while asleep"
            return None
        except (OSError, subprocess.SubprocessError) as problem:
            self.why = f"{self.command} failed: {problem}"
            return None
        if done.returncode != 0:
            self.why = f"{self.command} refused: {(done.stderr or '').strip()}"
            return None
        seen: dict[str, bool] = {}
        for line in (done.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("on", "off"):
                seen[parts[0]] = parts[1] == "on"
        self.why = ""
        return seen

    def cannot_bring_back(self, names) -> list[str]:
        """Which of [names] wlopm has no power over, and so must not be switched off.

        THE RULE THIS EXISTS FOR: never turn off a screen you cannot prove you can turn back
        on. Harry's main display reports a malformed EDID -- "Invalid Vendor Codename - RTK
        HDMI" with Serial: (null) -- and after a sleep both outputs read "Enabled: no" while
        `wlopm --on '*'` brings only the 7in panel back. `wlopm` then lists HDMI-A-2 alone,
        because an output that has been disabled drops out of its list entirely.

        So the mat blanked a screen it had no way to unblank, and said it had succeeded: set()
        returns True when the wildcard command returns 0, whether or not the wildcard actually
        covered the screen you were looking at. Three minutes of idleness was enough to leave
        a child's prayer mat dark until somebody pulled the plug.

        An empty list when wlopm cannot be asked at all is deliberate, not an oversight: with
        wlopm missing, set() fails by itself and nothing is ever blanked, so there is nothing
        here to warn about.
        """
        seen = self.listing()
        if seen is None:
            return []
        return [name for name in names if name and name not in seen]

    def set(self, on: bool, names=None) -> bool:
        """Powers outputs on or off. False if that could not be done, with [why] set.

        [names] limits it to particular outputs; the default is the wildcard, every output.

        BY NAME MATTERS ON A MAT WITH TWO UNEQUAL SCREENS. Harry's 7in panel sleeps and wakes
        perfectly, while his main display will not come back at all -- so the wildcard, which
        can only treat them alike, had to take the good screen down with the bad one. Sleep now
        switches off only what it should, and the main display is simply never asked.
        """
        wanted = [name for name in (names or ()) if name] or ["*"]
        for name in wanted:
            try:
                done = self.run([self.command, "--on" if on else "--off", name],
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


class Layout:
    """Switches outputs back ON by name, which powering them cannot always do.

    WHY THIS IS NOT PART OF Outputs. The two speak different Wayland protocols and can do
    different things. wlopm speaks output POWER: it blanks a screen that is enabled, and brings
    a blanked one back. It cannot enable an output that has been DISABLED, and on Harry's mat
    that is where the main display ends up -- after a sleep both outputs read "Enabled: no" in
    wlr-randr, and `wlopm --on '*'` recovers only the 7in. Enabling a disabled output needs the
    output-MANAGEMENT protocol, which is what wlr-randr speaks.

    Setting a mode is NOT enough and this is the expensive lesson of 2.01: display-setup.sh
    reconfigured both outputs without `--on`, which on a disabled output reconfigures something
    that is still off. Run against a dark mat it cleared the 7in's held image and recovered
    nothing, and the mat had to be power-cycled. `--on` is the whole operation here.

    This asks for nothing but the power state. It deliberately sets no mode, transform or
    position: those are facts about one particular mat's desk, they live in that mat's own
    display-setup.sh, and an app that guessed them would be overruling a layout somebody chose.
    """

    COMMAND = "wlr-randr"

    def __init__(self, command: str = COMMAND, run=subprocess.run):
        self.command = command
        self.run = run
        self.why: str = ""

    def switch_on(self, names) -> bool:
        """Enables each named output. True if there was nothing to do or it was done."""
        wanted = [name for name in names if name]
        if not wanted:
            self.why = ""
            return True
        argv = [self.command]
        for name in wanted:
            argv += ["--output", name, "--on"]
        try:
            done = self.run(argv, capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            self.why = (f"{self.command} is not installed, so a screen that has been disabled "
                        f"rather than blanked cannot be switched back on")
            return False
        except (OSError, subprocess.SubprocessError) as problem:
            self.why = f"{self.command} failed: {problem}"
            return False
        if done.returncode != 0:
            self.why = f"{self.command} refused: {(done.stderr or '').strip()}"
            return False
        self.why = ""
        return True
