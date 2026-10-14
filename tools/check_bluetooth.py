#!/usr/bin/env python3
"""Asks the mat what it can actually do with Bluetooth, and where its sound goes.

    python3 tools/check_bluetooth.py              # read-only; changes nothing
    python3 tools/check_bluetooth.py --scan       # and look round for ten seconds

RUN IT ON THE MAT. It cannot be run where the app is written: that machine has no Bluetooth
adapter, no BlueZ, no sound card and no speakers, so everything this prints is a thing that
can only be found out on the Pi. It is the same job tools/check_stations.py does for the
radio -- turn a question nobody can answer from here into one command and an answer.

WHAT IT IS FOR. Harry wants a Bluetooth button on the Settings page so somebody can pair a
speaker or a headset from the mat, with the ring still connected and still working. Three
things have to be true for that, and none of them can be assumed:

  1. THE ADAPTER WILL HOLD BOTH AT ONCE. The ring is a Bluetooth Low Energy keyboard and a
     speaker is a Classic audio link; they are different enough that they are usually fine
     together, and "usually" is not something to design on. This prints what is connected now
     and what the controller says it supports.

  2. THE SOUND FOLLOWS THE SPEAKER. The app does not play audio itself -- it shells out to
     mpg123 or ffplay (see salaah/audio.py), and those play to whatever the system calls its
     default output. On a Pi running PipeWire a speaker that connects becomes the default and
     everything follows it with no help from the app at all. On a Pi where mpg123 is talking
     to ALSA directly it will not, and the app would have to say where to send it. Which of
     those this mat is deciding what gets built.

  3. THERE IS SOMETHING TO DRIVE IT WITH. bluetoothctl is how the app would pair, the way
     nmcli is how it joins wifi (see salaah/network.py). If it is missing the button cannot
     work and it is better to know now.

IT CHANGES NOTHING. Nothing is paired, nothing is disconnected, no default output is moved
and the ring is not touched. --scan turns discovery on for ten seconds and off again, which
is what the mat would do when the button is pressed; it is the one thing here that puts the
radio to work, and it still connects to nothing.

PASTE THE WHOLE OUTPUT BACK. The exact wording bluetoothctl uses is what the app will have to
read, and it differs between BlueZ versions. The wifi screen was built against recorded nmcli
output and tested against it on a machine with no wifi; this is the recording session for the
Bluetooth one.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess


def run(command: list[str], seconds: int = 15) -> tuple[int, str]:
    """A command and everything it said. Never raises: a tool that is not installed is an
    answer, not a crash."""
    if not shutil.which(command[0]):
        return 127, f"({command[0]} is not installed)"
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=seconds)
    except subprocess.TimeoutExpired:
        return 124, f"({' '.join(command)} did not finish in {seconds}s)"
    except OSError as e:
        return 1, f"({e})"
    return done.returncode, (done.stdout + done.stderr).strip() or "(nothing)"


def say(title: str, command: list[str] | None = None, seconds: int = 15) -> str:
    print(f"\n--- {title} " + "-" * max(0, 62 - len(title)))
    if command is None:
        return ""
    print(f"$ {' '.join(command)}")
    code, out = run(command, seconds)
    for line in out.splitlines() or ["(nothing)"]:
        print(f"  {line}")
    if code not in (0, 127):
        print(f"  [exit {code}]")
    return out


def macs_in(text: str) -> list[str]:
    """Every address bluetoothctl named, in the order it named them."""
    found = []
    for line in text.splitlines():
        bits = line.split()
        if len(bits) >= 2 and bits[0] == "Device" and bits[1].count(":") == 5:
            if bits[1] not in found:
                found.append(bits[1])
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan", action="store_true",
                    help="look round for ten seconds (connects to nothing)")
    args = ap.parse_args()

    print("=" * 70)
    print("What this mat can do with Bluetooth, and where its sound goes.")
    print("Nothing here changes anything. Paste the whole lot back.")
    print("=" * 70)

    # 1. Is there an adapter, and what does it say about itself
    say("the machine", ["uname", "-a"])
    say("is bluetoothctl here", ["bluetoothctl", "--version"])
    say("the controller", ["bluetoothctl", "show"])
    say("the adapter, as the kernel sees it", ["hciconfig", "-a"])
    say("is the service running", ["systemctl", "is-active", "bluetooth"])

    # 2. What is connected NOW -- the ring should be in here
    known = say("everything it knows about", ["bluetoothctl", "devices"])
    live = say("everything connected right now", ["bluetoothctl", "devices", "Connected"])
    if not live.strip() or live.startswith("("):
        # Older BlueZ has no "devices Connected"; fall back to asking each one.
        live = known
    for mac in macs_in(live)[:6]:
        say(f"what {mac} is", ["bluetoothctl", "info", mac])

    # 3. Where does sound go. This is the half that decides whether the app has to do
    #    anything at all once a speaker is connected.
    say("the sound server", ["pactl", "info"])
    say("the outputs it offers", ["pactl", "list", "short", "sinks"])
    say("the same, if this is a wireplumber mat", ["wpctl", "status"])
    say("ALSA's own cards", ["aplay", "-l"])
    print("\n--- which players are installed " + "-" * 31)
    for player in ("mpg123", "ffplay", "mpv", "cvlc", "paplay"):
        where = shutil.which(player)
        print(f"  {player:8s} {where or '(not installed)'}")

    # 4. The input side, so the ring and a speaker can be told apart
    say("bluetooth input devices (the ring)",
        ["sh", "-c", "grep -i -A4 'Bustype=0005' /proc/bus/input/devices || true"])

    if args.scan:
        print("\n--- looking round for ten seconds " + "-" * 29)
        print("$ bluetoothctl --timeout 10 scan on")
        code, out = run(["bluetoothctl", "--timeout", "10", "scan", "on"], seconds=25)
        for line in out.splitlines():
            print(f"  {line}")
        say("and what it found", ["bluetoothctl", "devices"])

    print("\n" + "=" * 70)
    print("Done. Nothing was paired, disconnected or switched over.")
    print("If a speaker is already paired to this Pi, connect it by hand and run this")
    print("again -- what matters is whether 'pactl info' then names it as the default,")
    print("because that is what decides whether the app has to route anything itself.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
