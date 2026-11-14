"""The sleep switch on GPIO 17, the screens it puts to sleep, and the light that says which.

THE STATUS LIGHT, added in 2.08: an LED on GPIO 27, lit while the mat is awake and dark while
it sleeps. See StatusLed, and note that it is driven with `pinctrl` rather than gpiozero for a
reason this module is the natural home of -- the two gpiozero Buttons below take ownership of
their pins, and the LED's first home was one of them.


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

#: GPIO 3 is physical pin 5, and it is the ONLY pin that can start a halted Pi: the bootloader
#: watches it and that is hardcoded, so no other pin will do. Harry tested it on his Pi 4B --
#: halt, short pin 5 to a ground, and it boots -- which mattered, because the Pi 4 bootloader
#: did not always support this and a Pi 400 reportedly does not.
WAKE_PIN = 3

#: BOTH pins are watched, and the app acts on whichever one fires. The switch is moving from
#: GPIO 17 to GPIO 3 so that one button can also start the mat from cold, and watching both
#: means the wire can be moved whenever suits rather than in lockstep with an update: there is
#: no moment where the mat is updated but not yet rewired, or rewired but not yet updated, and
#: the button is dead. A pin with nothing on it is pulled up and simply never fires.
PINS = (WAKE_PIN, PIN)

#: Seconds gpiozero ignores further edges after one it has acted on. Mechanical switches chatter
#: for a few milliseconds and would otherwise read as several presses; 80 ms is what was tested
#: on the mat and comfortably longer than the chatter.
BOUNCE = 0.08

#: How long the button has to be held down to mean "shut the mat down" rather than "sleep".
#: Long enough that it cannot be reached by a brisk press, short enough that a child is not
#: left wondering whether anything is happening.
HOLD = 2.0

#: The status LED, BCM numbering. GPIO 27 is physical pin 13, with a ground on pin 14 and a
#: 330R resistor in series -- about 4mA for a red LED on 3V3, well inside the 16mA a pin will
#: give.
#:
#: NOT GPIO 17, WHICH IS WHERE IT STARTED. Harry wired the LED to 17 and it went out on its own
#: a moment after the mat booted: 17 is the sleep switch's pin, and SleepSwitch asks gpiozero
#: for a Button on it at start-up, which reconfigures the pin as an INPUT and drops the output
#: it was holding. Nothing was broken -- the app did exactly what it is for -- and that is the
#: point: two things cannot own one pin. 27 is free, it is not watched by the bootloader like 3,
#: and it is not the fan's 14.
LED_PIN = 27

#: The case fan, BCM numbering. GPIO 14 is physical pin 8, which the wiring brief has reserved
#: for the fan since before there was one on the board.
#:
#: A THREE-WIRE FAN OF THE RASPBERRY PI KIND, which is not the same animal as a three-wire fan
#: out of a PC. On a PC fan the third wire is a TACHOMETER -- a pulse train coming OUT of the
#: fan -- and wiring that to this pin would control nothing and put the fan's own 5V onto a
#: 3V3 input. On the Pi-type fan (the official Case Fan, the HighPi Pro and their like) the
#: third wire is a PWM control INPUT: red to header pin 4 (5V), black to pin 6 (ground), blue
#: to pin 8. Harry has the red/blue/black kind.
#:
#: THE MOTOR DOES NOT DRAW THROUGH THIS PIN and never may. A GPIO will source about 16mA, and
#: roughly 50mA across the whole header; the motor wants several times that and takes it from
#: pin 4. This pin carries a logic signal into the fan's own driver and nothing else.
#:
#: GPIO 14 IS ALSO THE UART's TX. `pinctrl set 14 op` claims it as a plain output and takes it
#: off that alternate function, which is convenient -- but only from the moment something runs
#: it. With a serial console enabled the pin carries boot messages before then, and the fan
#: twitches its way through start-up. The console has to be off.
FAN_PIN = 14

#: Where each pin comes out on the header, for the line the app prints at start-up. A person
#: looking at the board needs the physical pin, not the BCM number.
HEADER = {WAKE_PIN: "header pin 5", PIN: "header pin 11", LED_PIN: "header pin 13",
          FAN_PIN: "header pin 8"}

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

    def __init__(self, on_press: Callable[[], None], on_hold: Callable[[], None] | None = None,
                 pins=PINS, bounce: float = BOUNCE, hold: float = HOLD, button=None):
        self.on_press = on_press
        self.on_hold = on_hold
        self.pins = (pins,) if isinstance(pins, int) else tuple(pins)
        self.bounce = bounce
        self.hold = hold
        self._make = button                 # a stand-in, for the tests
        self.buttons: list = []
        self.watching: tuple[int, ...] = ()
        self._holding: set[int] = set()     # pins whose current press has already been a hold
        self.why: str = ""                  # empty while it is working; otherwise why it is not
        self._lock = threading.Lock()

    @property
    def where(self) -> str:
        return ", ".join(f"GPIO {p} ({HEADER.get(p, 'header')})" for p in self.watching) or "nothing"

    def start(self) -> bool:
        """Begins watching. False, with [why] set, if there is no GPIO to watch at all."""
        make = self._make
        if make is None:
            try:
                from gpiozero import Button
            except ImportError:
                self.why = ("python3-gpiozero is not installed, so the sleep switch does "
                            "nothing; sudo apt install python3-gpiozero")
                return False
            make = Button
        troubles, watching = [], []
        for pin in self.pins:
            try:
                button = make(pin, pull_up=True, bounce_time=self.bounce, hold_time=self.hold)
            except Exception as problem:
                # gpiozero raises BadPinFactory on anything that is not a Pi, and OSError or its
                # own GPIOPinInUse if the pin is taken. Caught broadly on purpose: whatever the
                # reason, the mat should start and say why rather than refuse to run. One pin
                # failing is not fatal now -- the other may well be the one the switch is on.
                troubles.append(f"GPIO {pin}: {problem}")
                continue
            # RELEASE, NOT PRESS. gpiozero fires when_pressed the instant the contact is made,
            # so a hold would put the mat to sleep on its way to the shutdown question and then
            # ask about shutting down a screen it had just blacked out. Acting on release lets
            # the hold be recognised first. For an ordinary quick press the difference is the
            # time a finger spends on a button, which nobody can perceive.
            button.when_held = self._holder(pin)
            button.when_released = self._releaser(pin)
            self.buttons.append(button)
            watching.append(pin)
        self.watching = tuple(watching)
        self.why = "; ".join(troubles)
        return bool(self.buttons)

    def _holder(self, pin: int):
        def held(*_):
            self._holding.add(pin)
            if self.on_hold is not None:
                self.on_hold()
        return held

    def _releaser(self, pin: int):
        def released(*_):
            was_held = pin in self._holding
            self._holding.discard(pin)
            if not was_held:
                self.on_press()
        return released

    def stop(self) -> None:
        with self._lock:
            buttons, self.buttons = self.buttons, []
            self.watching = ()
        for button in buttons:
            try:
                button.when_held = None
                button.when_released = None
                button.close()
            except Exception:
                pass                        # going away; nothing here is worth failing for


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


class Halt:
    """Shuts the computer down cleanly.

    WHY A MAT NEEDS THIS AT ALL, which is not the reason it looks like. A halted Pi is not off:
    it sits in a very deep sleep and still draws from the supply, so this saves little over the
    sleep the button already does. What it saves is the SD card. Pulling the plug on a running
    Pi risks the filesystem, and a corrupted card is a mat that simply stops working one
    morning with nothing on screen to say why.

    It is only worth offering because of what Harry tested on his own board: GPIO 3 really does
    start his Pi 4B from halt. Without that, a shutdown button would be a trap -- a mat that
    can be turned off and not on, by a child, with the plug as the only way back.
    """

    COMMAND = ("sudo", "shutdown", "-h", "now")

    def __init__(self, run=subprocess.run):
        self.run = run
        self.why: str = ""

    def now(self) -> bool:
        """Asks the system to halt. False, with [why] set, if it would not."""
        try:
            done = self.run(list(self.COMMAND), capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            self.why = "shutdown is not available on this machine"
            return False
        except (OSError, subprocess.SubprocessError) as problem:
            self.why = f"shutdown failed: {problem}"
            return False
        if done.returncode != 0:
            self.why = f"shutdown refused: {(done.stderr or '').strip()}"
            return False
        self.why = ""
        return True


class StatusLed:
    """The light on the front that says whether the mat is awake.

    On while the mat is up and awake, off while it sleeps, off on the way to a halt. It answers
    a question nothing else on this mat can: Harry's main display sometimes refuses to come back
    from sleep, and a dark mat with a dark LED looks exactly like a mat that is switched off --
    which has already cost two hard resets. A dark mat with a lit LED says the Pi is alive and
    the screen is the problem.

    PINCTRL RATHER THAN gpiozero, which is not a style preference. gpiozero's LED takes the pin
    through its pin factory and HOLDS it, and this app already keeps two gpiozero Buttons; the
    LED's first home was GPIO 17, where SleepSwitch's Button took the pin as an input and put
    the light out. `pinctrl set` drives the pin and lets go, which is also what the boot service
    uses, so the app and systemd cannot fight over ownership.

    NOTHING HERE MAY EVER STOP THE MAT. Every call swallows its failure and reports it through
    [why]: a missing pinctrl, a refusal, a hang, a bad argument. The exception clause is
    deliberately the broadest in this module, which is normally a thing to avoid -- the reason
    it is right here is that the worst case on one side is a light that does not come on, and on
    the other a mat that will not go to sleep or will not shut down because of a light.
    """

    COMMAND = "/usr/bin/pinctrl"

    #: What this thing is, for the one message that names it. A class attribute because Fan
    #: below is the same pin-driving under another name, and a fan reporting itself as "the
    #: status light" would send somebody to the wrong end of the mat.
    WHAT = "status light"

    #: A second, not the two the brief suggested. It only bites when pinctrl hangs, and this
    #: sits on the path between pressing the button and the screens going dark -- so it is the
    #: longest the mat may pause for a light, not a guess at how long pinctrl takes. In practice
    #: it returns in a few milliseconds.
    TIMEOUT = 1.0

    def __init__(self, pin: int = LED_PIN, command: str = COMMAND, run=subprocess.run):
        self.pin = pin
        self.command = command
        self.run = run
        #: What actually worked. `pinctrl set` may need root depending on how the mat is set
        #: up, and a mat where it does would otherwise have a light that never lights and no
        #: explanation. start() tries the plain command and then `sudo -n` -- -n so that a sudo
        #: wanting a password fails at once instead of sitting there waiting for one that
        #: nobody is going to type into a prayer mat.
        self.prefix: tuple[str, ...] = (command,)
        self.why: str = ""

    def argv(self, on: bool, prefix: tuple[str, ...] | None = None) -> list[str]:
        """The exact command. Its own method so a test can read it rather than guess it."""
        return [*(prefix or self.prefix), "set", str(self.pin), "op", "dh" if on else "dl"]

    def _drive(self, on: bool, prefix: tuple[str, ...]) -> bool:
        try:
            done = self.run(self.argv(on, prefix), capture_output=True, text=True,
                            timeout=self.TIMEOUT)
        except FileNotFoundError:
            self.why = f"{self.command} is not installed, so the {self.WHAT} stays as it is"
            return False
        except Exception as problem:          # see the class docstring: never fatal
            self.why = f"{self.command} failed: {problem}"
            return False
        if done.returncode != 0:
            self.why = f"{self.command} refused: {(done.stderr or '').strip()}"
            return False
        self.why = ""
        return True

    def start(self) -> bool:
        """Light it, working out how the pin can be driven on this machine. False if it cannot.

        Tried once, at start-up, and the answer remembered -- so the sleep and wake paths pay
        for one command rather than two, and a mat that needs sudo is not discovering that
        every time somebody presses the button.
        """
        for prefix in ((self.command,), ("sudo", "-n", self.command)):
            if self._drive(True, prefix):
                self.prefix = prefix
                return True
        return False

    def set(self, on: bool) -> bool:
        """On or off. False, with [why] set, if it would not."""
        return self._drive(on, self.prefix)

    def on(self) -> bool:
        return self.set(True)

    def off(self) -> bool:
        return self.set(False)


class Fan(StatusLed):
    """The case fan on GPIO 14, on while the mat is awake and off while it sleeps.

    THE SAME PIN-DRIVING AS THE LIGHT, deliberately. Harry asked for the fan to follow the app
    "similar to how the led light comes on and off when sleep", and the light had already paid
    for the two hard parts: `pinctrl set` drives a pin and LETS GO, so nothing here owns GPIO 14
    and fights the boot service for it; and every failure is swallowed and reported through
    [why] rather than raised, so a fan can no more stop a sleep than a light can.

    WHY THERE IS NO dtoverlay=gpio-fan, and why there must never be one. That overlay hands
    GPIO 14 to the kernel, which then drives it from the SoC's temperature. The app would go on
    issuing pinctrl calls that the kernel quietly overrules, and the fan would do something
    nobody had asked for while the logs looked perfectly healthy. That is not a guess: it is
    the GPIO 17 story in Harry's own wiring brief, where a gpiozero Button took the LED's pin
    as an input and the light went out while the service still read as running. Two things
    cannot own one pin. Either the kernel runs this fan or the app does.

    THE BACKSTOP, which is the one place this is not simply the light again. A light that is
    wrong costs nothing; a fan that is off while the SoC is working does not. Sleeping is not
    the same as idling -- the mat sleeps on a timer and may still be fetching an update or
    finishing a download -- so [set] and [check] both drive the pin on what the app wants OR
    what the thermometer says, whichever asks for more air.

    IT FAILS QUIET, NOT LOUD. With no thermometer to read, the backstop simply is not there and
    the fan does what the app asked. That is the right way round here because of what is
    actually at stake: a Pi that gets hot protects itself by SLOWING DOWN -- Raspberry Pi's own
    thermal testing describes throttling in terms of clock speed and nothing else -- so the
    backstop is about keeping the mat out of throttling, not about keeping it from harm. The
    alternative, failing loud, would pin a fan on all night in a child's bedroom because a file
    would not read, and that is a worse answer to a smaller problem.
    """

    WHAT = "fan"

    #: Where the SoC's temperature is, in thousandths of a degree.
    THERMOMETER = "/sys/class/thermal/thermal_zone0/temp"

    #: ON above this, OFF below the lower one -- and the gap between them is the point. A single
    #: threshold makes the fan chatter on and off around it, which is both the most irritating
    #: noise a fan can make and the hardest wear on it. Raspberry Pi's own driver for this fan
    #: is a bang-bang controller with hysteresis for the same reason.
    #:
    #: 60 degrees because that is where a Pi 3B+ begins its soft throttle, which makes it a
    #: sensible place to start blowing air rather than a number chosen for the look of it.
    HOT = 60.0
    COOL = 55.0

    def __init__(self, pin: int = FAN_PIN, command: str = StatusLed.COMMAND,
                 run=subprocess.run, thermometer: str | None = None):
        super().__init__(pin=pin, command=command, run=run)
        self.thermometer = thermometer or self.THERMOMETER
        #: What the app last asked for, kept apart from what the pin is actually doing, because
        #: the backstop can hold the fan on after the app has asked for it to stop.
        self.wanted = False
        #: What the pin was last driven to, or None for "not yet driven". The check below runs
        #: every fifteen seconds for as long as the mat is powered, and a subprocess every
        #: fifteen seconds forever to say what it said last time is a cost with no buyer.
        self.driving: bool | None = None
        #: True while the thermometer is holding the fan on past what the app asked for.
        self.because_it_is_hot = False

    def degrees(self) -> float | None:
        """The SoC's temperature, or None if it cannot be read. Never raises: see the class."""
        try:
            with open(self.thermometer) as readings:
                return int(readings.read().strip()) / 1000.0
        except Exception:
            return None

    def too_hot(self) -> bool:
        """Whether the thermometer wants the fan on, with the hysteresis applied.

        Reads the CURRENT state to pick the threshold, which is what makes it hysteresis rather
        than two numbers: once the fan is running it keeps running until 55, and once it has
        stopped it stays stopped until 60.
        """
        now = self.degrees()
        if now is None:
            self.because_it_is_hot = False
            return False
        self.because_it_is_hot = now >= (self.COOL if self.because_it_is_hot else self.HOT)
        return self.because_it_is_hot

    def set(self, on: bool) -> bool:
        """What the app asks for -- the mat waking or sleeping. The thermometer may overrule a
        stop, and may never overrule a start: nothing is served by refusing air."""
        self.wanted = on
        # ASKED FIRST, not left to the right-hand side of an `or` that may never reach it.
        # too_hot() is what keeps the hysteresis current, so skipping it whenever the answer
        # was already settled leaves [because_it_is_hot] remembering a temperature from
        # minutes ago -- and the mat is awake, and therefore skipping it, for most of the day.
        hot = self.too_hot()
        return self.drive(on or hot)

    def check(self) -> bool:
        """Called on the fifteen-second timer that runs whether the mat is awake or asleep.

        Its whole job is the sleeping mat: while the mat is awake [wanted] is already True and
        this can only agree with itself.
        """
        hot = self.too_hot()            # see set(): taken every time, for the same reason
        return self.drive(self.wanted or hot)

    def drive(self, on: bool) -> bool:
        """Put the pin where it is wanted, and spend nothing saying what it already says."""
        if on == self.driving:
            return True
        if not super().set(on):
            return False
        self.driving = on
        return True

    def start(self) -> bool:
        """Work out how the pin can be driven, exactly as the light does, and remember it."""
        lit = super().start()
        self.wanted = lit
        self.driving = True if lit else None
        return lit


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
