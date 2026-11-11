"""Where the mat is, from a postcode, with no internet.

The mat works its prayer times out from the sun, so it needs a latitude and longitude and
nothing else -- no service, no lookup, no network. What it did NOT have until now was any way
to change them: they were set to Bury in the settings file and there was no screen for it. Carry
the mat to Birmingham and it showed Bury's times, confidently, with nothing to say it was wrong.
A mat that is quietly wrong about Fajr is worse than one that admits it does not know.

A postcode district -- the "BL9" before the space -- is the right unit for this. It is small
enough to carry: three thousand districts against 1.8 million full postcodes, which is 88KB
instead of 70MB.

HOW MUCH BEING IN THE WRONG PLACE ACTUALLY MATTERS, corrected in 2.20. This file used to say,
flatly, that 5km of error moves the prayer times by under a minute and that it takes 60km to
move them by five. Those numbers were measured with the mat's own sums, at Bury, and then
written down as though they held everywhere all year. They do not, and 2.20 went back and
measured properly because the whole case for a town list with a 15,000 cut-off rested on them:

    at Bury, worst shift of any prayer, moving north or south
                        5km      15km      60km
    around the equinox  <1 min    1 min     2 min
    midwinter            1 min    1 min     4 min
    midsummer            6 min   11 min    16 min

The old figure was the equinox row. Dhuhr, asr and maghrib stay inside it all year -- dhuhr
is solar noon and does not move with latitude at all. Fajr and isha are the sensitive ones,
and only in summer, because the sun's path is then shallow enough that the moment it reaches
18 degrees below the horizon slides fast with latitude. Over mid-May to July at Bury the isha
shift for 60km reaches half an hour. Nearer the equator the whole table collapses to under a
minute: at Mecca, 60km moves nothing by more than 2 minutes.

AND FOR 78 DAYS A YEAR, 14 MAY TO 30 JULY, BURY HAS NO REAL FAJR AT ALL at 18 degrees -- the
sun never gets that low. prayer_times falls back to the nearest day that does have one, which
is a recognised convention and not a calculation, and it is unstable in latitude: the borrowed
day flips from the 13th to the 12th of May somewhere in the ten kilometres north of Bury, and
fajr jumps about a quarter of an hour when it does. So in summer the fajr two neighbouring
villages are shown can differ by more than the distance between them would suggest, and that
is the convention showing through rather than an error in the sums. Which convention to use is
a question for somebody qualified, not for me.

The table is built by tools/build_postcodes.py from the National Statistics Postcode Lookup
under the Open Government Licence.
"""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime
import re
from dataclasses import dataclass
from pathlib import Path

# The outward half of a UK postcode. AA9A, A9A, AA99, A99, AA9, A9 are all real shapes -- W1A,
# EC1A, M1, BL9, SW1A. Anchored, so "BL99999" is refused rather than quietly trimmed.
OUTWARD = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")

#: The same shape, half typed: what somebody is part-way through when they have got as far as
#: "B" or "BL" or "BL9". Not for looking anything up -- only the place screen uses it, to
#: decide whether the box shows capitals, since the box now takes town names too.
PARTIAL = re.compile(r"^[A-Z]{1,2}([0-9][A-Z0-9]?)?$")


@dataclass(frozen=True)
class Found:
    outward: str
    latitude: float
    longitude: float
    #: Empty for a postcode, which cannot be in a surprising timezone -- every district in
    #: the table is in Europe/London. A city carries its own, and the screen uses it to
    #: notice when the Pi's clock disagrees with the place it has just been told it is in.
    timezone: str = ""
    #: Two-letter country code, empty for a postcode. Only for telling apart the eight
    #: places called Springfield; nothing is calculated from it.
    country: str = ""
    #: A state or province, where the country uses readable ones. Empty elsewhere.
    region: str = ""

    @property
    def is_a_town(self) -> bool:
        return bool(self.timezone)


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


def fold(said: str) -> str:
    """A name flattened for searching: no case, no accents, no surrounding space.

    Somebody looking for Málaga types "malaga", because the mat's own keyboard has no easy
    way to make the accent and because that is how most people type anyway. The table is
    folded the same way when it is searched, so the two meet in the middle.
    """
    bare = unicodedata.normalize("NFKD", said.strip().casefold())
    return "".join(ch for ch in bare if not unicodedata.combining(ch))


def clock_disagrees(zone: str) -> bool:
    """Whether the Pi's own clock is set to a different time from the chosen town's.

    THE FAILURE THIS EXISTS TO CATCH. Prayer times are worked out from the system timezone
    and the coordinates together. While the only places a mat could be told it was in were
    British, those two could not disagree. The moment Sydney is on the list they can be
    eleven hours apart, and nothing about the screen would look wrong -- the times would
    simply all be untrue, every day, until somebody noticed.

    Compared by the OFFSET IN FORCE TODAY rather than by name, because Europe/London and
    Europe/Dublin are different names for the same clock and warning about that would be
    noise. Two zones that agree today and part in March will be caught in March, which is
    the price of not crying wolf.

    An unknown zone answers False: the table is this mat's own and a name it does not
    recognise means the table is wrong, which is not a thing to tell a family off about.
    """
    if not zone:
        return False
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now()
        theirs = now.astimezone(ZoneInfo(zone)).utcoffset()
        ours = now.astimezone().utcoffset()
    except Exception:                      # noqa: BLE001 - an unknown zone is not an error
        return False
    return theirs != ours


class Cities:
    """The towns of the world, read once off the disk.

    Beside the postcode table rather than instead of it. A UK postcode district puts the mat
    within a mile or two; the nearest town of 15,000 people can be twenty miles away. For
    somebody in Britain the postcode is the better answer and it already worked, so it stays.
    """

    #: How many towns the screen offers at once. FIVE, down from eight in the same release
    #: that introduced it, because eight never fitted: five rows of "name, country" leave the
    #: keyboard underneath enough room to draw itself, and eight did not. The rows are in
    #: population order, so the place somebody means is at or near the top and the ones lost
    #: off the end are the ones they did not mean. See salaah/keys.py for the other half.
    SHOW = 5

    def __init__(self, assets: Path):
        self.path = Path(assets) / "content" / "cities.json"
        self._rows: list | None = None
        self._folded: list[tuple[str, tuple[str, ...], int]] = []
        self._countries: dict = {}
        self._source: dict = {}

    @property
    def rows(self) -> list:
        if self._rows is None:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._rows = []
                return self._rows
            self._rows = raw.get("cities", []) or []
            self._countries = raw.get("countries", {}) or {}
            self._source = raw.get("source", {}) or {}
            # Folded once here rather than on every keystroke: 34,000 rows folded on each of
            # six letters typed is 200,000 normalisations a word, on a Raspberry Pi.
            self._folded = [
                (fold(row[0]), tuple(fold(n) for n in (row[5] if len(row) > 5 else ())), n)
                for n, row in enumerate(self._rows)
            ]
        return self._rows

    @property
    def there(self) -> bool:
        return bool(self.rows)

    @property
    def source(self) -> dict:
        """The attribution CC BY 4.0 requires. Reading the table is what loads it."""
        self.rows
        return self._source

    def country_called(self, code: str) -> str:
        self.rows
        return self._countries.get(code, code)

    def search(self, typed: str, limit: int | None = None) -> list[Found]:
        """Towns whose name, or one of its spellings, begins with what has been typed.

        THE BEGINNING AND NOT ANYWHERE IN THE MIDDLE. "or" would otherwise answer with
        Gloucester and six hundred others, and a list that long is no better than no list.
        The table is ordered biggest first, so where a name is shared -- and thirteen places
        are called Springfield -- the one most people mean is offered first without this
        having to rank anything.

        A name typed in full comes first even where it is a smaller place, because somebody
        who types the whole of "Bury" means Bury and not Bury St Edmunds.

        AN EXACT ALTERNATE SPELLING COUNTS AS A NAME TYPED IN FULL, which took a second go.
        Ranking every alternate match below every exact one put Medina, Ohio -- population
        26,000 -- above Madinah, because the table calls it Madinah and "Medina" is only one
        of its spellings. On this mat of all mats that is the wrong way round. Ordering by
        size alone fixes Medina and breaks more than it mends: it puts Bathinda above Bath
        and Warner Robins above York, both on alternate spellings nobody typed.
        """
        want = fold(typed)
        if len(want) < 2 or not self.rows:
            return []
        exact, by_name, by_other = [], [], []
        for name, others, n in self._folded:
            if name == want or want in others:
                exact.append(n)
            elif name.startswith(want):
                by_name.append(n)
            elif any(other.startswith(want) for other in others):
                by_other.append(n)
        wanted = (exact + by_name + by_other)[:limit or self.SHOW]
        return [self._found(self._rows[n]) for n in wanted]

    @staticmethod
    def _found(row: list) -> Found:
        return Found(outward=row[0], latitude=float(row[2]), longitude=float(row[3]),
                     timezone=row[4], country=row[1],
                     region=row[6] if len(row) > 6 else "")
