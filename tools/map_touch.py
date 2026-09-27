#!/usr/bin/env python3
"""Points the touchscreen at the screen it is actually printed on. Run this on the Pi.

A USB touchscreen reports positions across the whole desktop, so on a Pi with two displays the
compositor sends its taps to whichever screen it happened to pick -- usually the wrong one. The
panel then looks broken while being perfectly healthy. This writes the one line of labwc
configuration that ties the two together.

It is safe to run twice: if a <touch> block is already there it changes nothing.

    python3 tools/map_touch.py            work out which screen and write it
    python3 tools/map_touch.py --show     say what it would do and stop
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

RC = Path.home() / ".config" / "labwc" / "rc.xml"
STUB = '<openbox_config xmlns="http://openbox.org/3.4/rc"/>'
ROOT = "openbox_config"
NAMESPACE = "http://openbox.org/3.4/rc"

# A line that starts a screen in wlr-randr's output: HDMI-A-2 "Some Monitor (HDMI-A-2)"
SCREEN = re.compile(r'^(\S+) "')
# The mode it is running at now:   1024x600 px, 60.043999 Hz (preferred, current)
NOW = re.compile(r"^\s+(\d+)x(\d+) px,.*\bcurrent\b")


def screens(text: str) -> dict[str, int]:
    """Screen name -> how many pixels it is showing, for every screen with a current mode."""
    found: dict[str, int] = {}
    name = ""
    for line in text.splitlines():
        start = SCREEN.match(line)
        if start:
            name = start.group(1)
            continue
        size = NOW.match(line)
        if size and name and name not in found:
            found[name] = int(size.group(1)) * int(size.group(2))
    return found


def smallest(found: dict[str, int]) -> str:
    """The touch panel is the little one. Empty if that cannot be said for certain."""
    if len(found) < 2:
        return ""
    order = sorted(found.items(), key=lambda pair: pair[1])
    if order[0][1] == order[1][1]:          # two screens the same size: no way to tell them apart
        return ""
    return order[0][0]


def touch_block(screen: str) -> str:
    return (f"  <touch>\n"
            f"    <mapToOutput>{screen}</mapToOutput>\n"
            f"    <mouseEmulation>no</mouseEmulation>\n"
            f"  </touch>\n")


def with_touch(current: str, screen: str) -> str:
    """The contents rc.xml should have. Raises ValueError if it is not a shape we understand."""
    body = touch_block(screen)
    if STUB in current or current.strip() == "":
        # What Raspberry Pi OS ships: an empty self-closing root, nothing to insert into.
        return ('<?xml version="1.0"?>\n'
                f'<{ROOT} xmlns="{NAMESPACE}">\n{body}</{ROOT}>\n')
    closing = f"</{ROOT}>"
    if current.count(closing) == 1:
        return current.replace(closing, body + closing)
    raise ValueError(f"rc.xml has no single {closing} and is not the stub; leaving it alone")


def look() -> str:
    try:
        done = subprocess.run(["wlr-randr"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as why:
        print(f"Could not ask about the screens ({why}).", file=sys.stderr)
        return ""
    if done.returncode != 0:
        print("wlr-randr failed -- is this running inside the desktop session?", file=sys.stderr)
        return ""
    return done.stdout


def main() -> int:
    ap = argparse.ArgumentParser(prog="map_touch")
    ap.add_argument("--show", action="store_true", help="say what would happen and stop")
    ap.add_argument("--screen", default="", help="name the screen yourself, e.g. HDMI-A-2")
    args = ap.parse_args()

    if RC.exists() and "<touch" in RC.read_text():
        print("Touch is already mapped in rc.xml; nothing to do.")
        return 0

    screen = args.screen
    if not screen:
        found = screens(look())
        if not found:
            print("Could not read the screens, so touch has not been mapped.")
            print("Run 'wlr-randr' yourself and pass --screen <name> for the small panel.")
            return 0                        # not a reason to fail an install
        screen = smallest(found)
        if not screen:
            names = ", ".join(sorted(found)) or "none"
            print(f"Cannot tell which screen the touch panel is ({names}).")
            print("Pass --screen <name> to say. Touch has not been mapped.")
            return 0
        print(f"Screens: " + ", ".join(f"{n} ({p:,}px)" for n, p in sorted(found.items())))

    print(f"Touch will be sent to {screen}.")
    if args.show:
        return 0

    RC.parent.mkdir(parents=True, exist_ok=True)
    current = RC.read_text() if RC.exists() else ""
    try:
        wanted = with_touch(current, screen)
    except ValueError as why:
        print(f"!! {why}", file=sys.stderr)
        print(f"!! Add this inside {RC} by hand:\n{touch_block(screen)}", file=sys.stderr)
        return 0
    if RC.exists():
        shutil.copy2(RC, RC.with_suffix(".xml.before-touch"))
        print(f"Kept the old one as {RC.with_suffix('.xml.before-touch').name}")
    RC.write_text(wanted)
    print(f"Wrote {RC}")

    # Takes effect on the next reboot anyway, but no reason to wait for one.
    subprocess.run(["pkill", "-HUP", "labwc"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
