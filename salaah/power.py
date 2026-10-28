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
