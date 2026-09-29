#!/usr/bin/env python3
"""Builds the postcode table the mat uses to know where it is.

    git clone --depth 1 https://github.com/odileeds/Postcodes2LatLon.git
    python3 tools/build_postcodes.py Postcodes2LatLon/postcodes

Why a postcode rather than a list of towns. The mat works its prayer times out from the sun, so
all it needs is a latitude and longitude -- and it is far less fussy about them than you would
think. Measured with the mat's own sums at Bury: 5km of error moves the times by under a minute,
15km by one minute, and it takes 60km to move them by five. A postcode DISTRICT -- the "BL9"
before the space -- is a few km across, so it is comfortably inside a minute. "Manchester" is
sixty km of sprawl and would be worse.

That also makes the table small. There are about three thousand districts in the UK against 1.8
million full postcodes, so this is a hundred kilobytes rather than seventy megabytes, and every
bit of it works with no internet at all -- which is the entire point, since the mat needs this
most when it has been carried somewhere new.

Source and licence. The coordinates come from the National Statistics Postcode Lookup, via
github.com/odileeds/Postcodes2LatLon, and are licensed under the Open Government Licence. That
requires the attribution written into the file this produces and shown on the credits screen.
Contains OS data (c) Crown copyright and database right; contains Royal Mail data (c) Royal Mail
copyright and database right; contains National Statistics data (c) Crown copyright and
database right.

The centre of a district is the mean of every full postcode in it. A mean is pulled towards
wherever the houses are, which for this is a feature rather than a fault: it lands where people
live rather than in the middle of a moor the district happens to include.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "content" / "postcodes.json"

# The outward half of a UK postcode: one or two letters, a digit, then optionally another digit
# or a letter. AA9A, A9A, AA99, A99, AA9, A9 -- all of them real shapes.
OUTWARD = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")

ATTRIBUTION = (
    "Postcode coordinates from the National Statistics Postcode Lookup, via "
    "github.com/odileeds/Postcodes2LatLon, under the Open Government Licence. "
    "Contains OS data (c) Crown copyright and database right; contains Royal Mail data "
    "(c) Royal Mail copyright and database right; contains National Statistics data "
    "(c) Crown copyright and database right."
)


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_postcodes")
    ap.add_argument("folder", type=Path, help="the postcodes/ folder of Postcodes2LatLon")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(args.folder.glob("*.csv"))
    if not files:
        print(f"No CSVs in {args.folder}.", file=sys.stderr)
        return 1

    summed: dict[str, list[float]] = {}     # outward -> [lat total, lon total, how many]
    rows = skipped = 0
    for path in files:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                code = (row.get("Postcode") or "").strip().upper()
                try:
                    lat, lon = float(row["lat"]), float(row["long"])
                except (KeyError, TypeError, ValueError):
                    skipped += 1
                    continue
                outward = code.split(" ")[0] if " " in code else code[:-3].strip()
                if not OUTWARD.match(outward):
                    skipped += 1
                    continue
                # The islands and a couple of others sit outside anything sensible; a zero-zero
                # coordinate is a missing one, not a place in the Gulf of Guinea.
                if not (-11 < lon < 3 and 49 < lat < 62):
                    skipped += 1
                    continue
                rows += 1
                got = summed.setdefault(outward, [0.0, 0.0, 0])
                got[0] += lat
                got[1] += lon
                got[2] += 1

    table = {code: [round(lat / n, 4), round(lon / n, 4)]
             for code, (lat, lon, n) in sorted(summed.items())}
    print(f"{rows:,} postcodes -> {len(table):,} districts   ({skipped:,} rows skipped)")
    for check in ("BL9", "M1", "E1", "EH1", "BT1", "SW1A"):
        if check in table:
            print(f"   {check:5s} {table[check][0]:8.4f}, {table[check][1]:8.4f}")

    if args.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema": 1,
        "about": ("The centre of each UK postcode district, as the mean of every full postcode "
                  "in it. Used to set where the mat is without needing the internet."),
        "source": ATTRIBUTION,
        "districts": table,
    }, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n-> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
