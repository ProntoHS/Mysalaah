"""Where the mat is, from a postcode, with no internet.

The mat works its prayer times out from the sun, so it needs a latitude and longitude and
nothing else -- no service, no lookup, no network. What it did NOT have until now was any way
to change them: they were set to Bury in the settings file and there was no screen for it. Carry
the mat to Birmingham and it showed Bury's times, confidently, with nothing to say it was wrong.
A mat that is quietly wrong about Fajr is worse than one that admits it does not know.

A postcode district -- the "BL9" before the space -- is the right unit for this. Measured with
the mat's own sums, 5km of error moves the prayer times by under a minute and it takes 60km to
move them by five, so a district a few kilometres across is comfortably inside a minute. It is
also small enough to carry: three thousand districts against 1.8 million full postcodes, which
is 88KB instead of 70MB.

The table is built by tools/build_postcodes.py from the National Statistics Postcode Lookup
under the Open Government Licence.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# The outward half of a UK postcode. AA9A, A9A, AA99, A99, AA9, A9 are all real shapes -- W1A,
# EC1A, M1, BL9, SW1A. Anchored, so "BL99999" is refused rather than quietly trimmed.
OUTWARD = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")


@dataclass(frozen=True)
class Found:
    outward: str
    latitude: float
    longitude: float


def tidy(typed: str) -> str:
    """What somebody typed, as an outward code: upper case, no spaces, and the inward half
    dropped if they typed the whole postcode.

    People type their postcode the way they write it -- "bl9 0ab", "BL90AB", " BL9 ". All of
    those mean BL9, and refusing them because of a space would be the app being difficult about
    something it can perfectly well understand.
    """
    bare = re.sub(r"[^A-Za-z0-9]", "", typed or "").upper()
    if not bare:
        return ""
    if OUTWARD.match(bare):
        return bare
    # A full postcode: the inward half is always three characters, digit-letter-letter.
    if len(bare) > 3 and re.match(r"^[0-9][A-Z]{2}$", bare[-3:]):
        head = bare[:-3]
        if OUTWARD.match(head):
            return head
    return bare          # handed back as typed, for `look_up` to refuse with


class Places:
    """The postcode table, read once off the disk."""

    def __init__(self, assets: Path):
        self.path = Path(assets) / "content" / "postcodes.json"
        self._districts: dict | None = None
        self._source = ""

    @property
    def districts(self) -> dict:
        if self._districts is None:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._districts = {}
                return self._districts
            self._districts = raw.get("districts", {}) or {}
            self._source = str(raw.get("source", ""))
        return self._districts

    @property
    def there(self) -> bool:
        return bool(self.districts)

    @property
    def source(self) -> str:
        """The attribution the licence requires. Reading the table is what loads it."""
        self.districts
        return self._source

    def look_up(self, typed: str) -> Found | None:
        """A postcode to a place, or None if it is not one."""
        code = tidy(typed)
        if not code or not OUTWARD.match(code):
            return None
        where = self.districts.get(code)
        if not where:
            return None
        return Found(code, float(where[0]), float(where[1]))
