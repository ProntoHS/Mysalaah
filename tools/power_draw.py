#!/usr/bin/env python3
"""Measures what the mat actually costs to run, so a battery can be sized from numbers.

The Pi 5's power management chip can be asked what every internal rail is drawing. Summing those
gives a good picture of the board, and this converts that to what the whole thing takes at the
wall -- but only roughly, and it is worth knowing why. The PMIC sees the rails it feeds. It does
not see what a USB socket is handing to a screen, a speaker or a touch panel, so the sum always
reads low. The correction below is the one the RPi5-power project arrived at by measuring boards
against a meter (github.com/jfikar/RPi5-power). It is a decent estimate and not a substitute for
an inline USB meter, so treat what comes out as a guide.

Run it while the mat is doing the thing you want to know about:

    python3 tools/power_draw.py --for 120                  two minutes, then a summary
    python3 tools/power_draw.py --for 120 --pack 72        and how long a 72Wh pack would last
    python3 tools/power_draw.py --csv awake.csv            keep every reading

The number worth having is the difference between awake and asleep. Take one reading with the
screens on, press the power button, and take another. That difference is what the sleep is worth,
and it decides whether the mat also needs to shut down overnight.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time

# 'name volt(7)=1.79746093V' and 'name current(6)=0.24218750A'
READING = re.compile(r"^\s*(\S+?)_(A|V)\s+(?:current|volt)\(\d+\)=([\d.]+)[AV]\s*$")

# What the PMIC cannot see -- USB devices, the displays' own draw -- against a meter.
SCALE, OFFSET = 1.1451, 0.5879


def parse(text: str) -> tuple[float, float]:
    """The board's power in watts, and the input voltage, from one pmic_read_adc.

    Each rail reports a current and a voltage under the same name; multiplied and added up they
    are the board. EXT5V_V is the voltage coming in, which has no current beside it: on a battery
    it is the thing to watch, because a pack that is nearly flat sags before it cuts out.
    """
    amps: dict[str, float] = {}
    volts: dict[str, float] = {}
    supply = 0.0
    for line in text.splitlines():
        found = READING.match(line)
        if not found:
            continue
        name, kind, value = found.group(1), found.group(2), float(found.group(3))
        if name == "EXT5V":
            supply = value
        elif kind == "A":
            amps[name] = value
        else:
            volts[name] = value
    rails = sum(amps[name] * volts[name] for name in amps if name in volts)
    return (rails * SCALE + OFFSET if rails else 0.0), supply


def read(command: str = "vcgencmd") -> tuple[float, float]:
    try:
        done = subprocess.run([command, "pmic_read_adc"], capture_output=True, text=True,
                              timeout=5)
    except FileNotFoundError:
        sys.exit(f"{command} not found: this has to run on the Pi itself")
    if done.returncode != 0:
        sys.exit(f"{command} pmic_read_adc failed: {(done.stderr or '').strip()}")
    return parse(done.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(prog="power_draw")
    ap.add_argument("--for", dest="seconds", type=float, default=0,
                    help="how long to measure for; leave it out to run until Ctrl-C")
    ap.add_argument("--every", type=float, default=2.0, help="seconds between readings")
    ap.add_argument("--pack", type=float, default=0,
                    help="watt-hours of a battery, to turn the answer into hours")
    ap.add_argument("--csv", help="write every reading to this file as well")
    ap.add_argument("--quiet", action="store_true", help="only the summary")
    args = ap.parse_args()

    readings: list[float] = []
    supplies: list[float] = []
    out = open(args.csv, "w", encoding="utf-8") if args.csv else None
    if out:
        out.write("seconds,watts,supply_volts\n")
    began = time.monotonic()
    try:
        while True:
            watts, supply = read()
            since = time.monotonic() - began
            readings.append(watts)
            supplies.append(supply)
            if out:
                out.write(f"{since:.1f},{watts:.2f},{supply:.3f}\n")
                out.flush()
            if not args.quiet:
                print(f"{since:7.1f}s  {watts:5.2f} W   in {supply:.2f} V", flush=True)
            if args.seconds and since >= args.seconds:
                break
            time.sleep(args.every)
    except KeyboardInterrupt:
        print()
    finally:
        if out:
            out.close()

    if not readings:
        return 1
    average = sum(readings) / len(readings)
    print(f"\n{len(readings)} readings over {time.monotonic() - began:.0f}s")
    print(f"  average {average:.2f} W   lowest {min(readings):.2f}   highest {max(readings):.2f}")
    if supplies and max(supplies):
        print(f"  supply  {min(supplies):.2f} V to {max(supplies):.2f} V")
    if args.pack and average:
        # Most of a pack's rating reaches the board; the rest goes into the step up to 5V.
        for efficiency, label in ((0.85, "at 85% efficiency"), (0.90, "at 90%")):
            print(f"  a {args.pack:.0f}Wh pack: {args.pack * efficiency / average:.1f} hours "
                  f"{label}")
    print("\nEstimated from the PMIC, which cannot see what the USB sockets give out; an inline\n"
          "USB meter is the way to check it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
