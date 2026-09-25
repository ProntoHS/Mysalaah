"""Prayer times, worked out on the device from the sun's position.

Uses the Muslim World League convention: Fajr when the sun is 18 degrees below the horizon and
Isha at 17 degrees. Asr follows the school — the Hanafi school uses twice the object's shadow,
the others once.

The sums are the standard ones (Julian day, the sun's declination and the equation of time), so
no internet and no service are needed: the same answer every time, anywhere, offline.

Accuracy: within about a minute of published tables for the same method and place. Local mosques
often round or add a couple of minutes, so treat these as a guide, and let the user set their own
if it matters.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

# Muslim World League
FAJR_ANGLE = 18.0
ISHA_ANGLE = 17.0
SUNSET_ANGLE = 0.833     # the sun's edge plus refraction at the horizon

ASR_SHADOW = {"hanafi": 2, "standard": 1}


@dataclass(frozen=True)
class Place:
    latitude: float
    longitude: float
    name: str = ""


def julian_day(day: date) -> float:
    year, month = day.year, day.month
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1))
            + day.day + b - 1524.5)


def sun_position(jd: float) -> tuple[float, float]:
    """The sun's declination and the equation of time, both for noon UTC on that day."""
    d = jd - 2451545.0
    mean_anomaly = (357.529 + 0.98560028 * d) % 360
    mean_longitude = (280.459 + 0.98564736 * d) % 360
    apparent_longitude = (mean_longitude
                          + 1.915 * math.sin(math.radians(mean_anomaly))
                          + 0.020 * math.sin(math.radians(2 * mean_anomaly))) % 360
    obliquity = 23.439 - 0.00000036 * d

    declination = math.degrees(math.asin(
        math.sin(math.radians(obliquity)) * math.sin(math.radians(apparent_longitude))))
    right_ascension = math.degrees(math.atan2(
        math.cos(math.radians(obliquity)) * math.sin(math.radians(apparent_longitude)),
        math.cos(math.radians(apparent_longitude)))) % 360
    equation_of_time = (mean_longitude - right_ascension + 180) % 360 - 180
    return declination, equation_of_time / 15   # in hours


def hour_angle(latitude: float, declination: float, altitude: float) -> float | None:
    """Hours either side of noon at which the sun sits at [altitude] degrees. None in the far
    north or south in summer, when the sun never gets that low."""
    lat, dec = math.radians(latitude), math.radians(declination)
    value = ((math.sin(math.radians(altitude)) - math.sin(lat) * math.sin(dec))
             / (math.cos(lat) * math.cos(dec)))
    if not -1 <= value <= 1:
        return None
    return math.degrees(math.acos(value)) / 15


def asr_altitude(latitude: float, declination: float, shadow: int) -> float:
    """How high the sun sits when a stick's shadow has grown by [shadow] times its length."""
    noon_zenith = abs(latitude - declination)
    return math.degrees(math.atan(1 / (shadow + math.tan(math.radians(noon_zenith)))))


def times_for(day: date, place: Place, school: str = "hanafi",
              utc_offset_hours: float | None = None) -> dict[str, time | None]:
    """Each prayer's start, in local clock time. None where the sun never reaches that angle."""
    if utc_offset_hours is None:
        utc_offset_hours = local_utc_offset(day)
    declination, eq_time = sun_position(julian_day(day))
    noon = 12 - place.longitude / 15 - eq_time + utc_offset_hours

    sunrise_gap = hour_angle(place.latitude, declination, -SUNSET_ANGLE)
    fajr_gap = hour_angle(place.latitude, declination, -FAJR_ANGLE)
    isha_gap = hour_angle(place.latitude, declination, -ISHA_ANGLE)
    asr_gap = hour_angle(place.latitude, declination,
                         asr_altitude(place.latitude, declination, ASR_SHADOW.get(school, 2)))

    hours = {
        "fajr": noon - fajr_gap if fajr_gap is not None else None,
        "sunrise": noon - sunrise_gap if sunrise_gap is not None else None,
        "dhuhr": noon,
        "asr": noon + asr_gap if asr_gap is not None else None,
        "maghrib": noon + sunrise_gap if sunrise_gap is not None else None,
        "isha": noon + isha_gap if isha_gap is not None else None,
    }
    return {name: _clock(value) for name, value in hours.items()}


def _clock(hours: float | None) -> time | None:
    if hours is None:
        return None
    minutes = round(hours * 60) % (24 * 60)
    return time(minutes // 60, minutes % 60)


def local_utc_offset(day: date) -> float:
    """The machine's own offset from UTC on that day, so British Summer Time is handled."""
    moment = datetime.combine(day, time(12, 0)).astimezone()
    offset = moment.utcoffset() or timedelta(0)
    return offset.total_seconds() / 3600


# Each prayer may be prayed from its own time until the next thing starts. Fajr ends at sunrise,
# and after sunrise there is no prayer to be praying until Dhuhr.
WINDOW_ENDS = {"fajr": "sunrise", "dhuhr": "asr", "asr": "maghrib", "maghrib": "isha", "isha": "fajr"}


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def current_prayer(now: datetime, times: dict[str, time | None]) -> str | None:
    """Which prayer may be prayed right now, or None between sunrise and Dhuhr, when none may.

    Isha runs through the night until Fajr. A prayer whose time cannot be worked out at this
    latitude (far north in summer) has no window.
    """
    minute = _minutes(now.time())
    for prayer, ends_at in WINDOW_ENDS.items():
        start, end = times.get(prayer), times.get(ends_at)
        if start is None or end is None:
            continue
        begins, finishes = _minutes(start), _minutes(end)
        if begins < finishes:
            if begins <= minute < finishes:
                return prayer
        elif minute >= begins or minute < finishes:   # runs past midnight
            return prayer
    return None


def next_prayer(now: datetime, times: dict[str, time | None]) -> str | None:
    for name in PRAYERS:
        if times.get(name) is not None and times[name] > now.time():
            return name
    return "fajr" if times.get("fajr") is not None else None


def day_fraction(now: datetime, times: dict[str, time | None]) -> tuple[bool, float]:
    """Whether the sun is up, and how far through the day (or the night) we are, 0 to 1.

    Used to place the sun or the moon in the sky behind the mosque.
    """
    sunrise, sunset = times.get("sunrise"), times.get("maghrib")
    minute = _minutes(now.time())
    if sunrise is None or sunset is None:
        return (True, 0.5) if sunrise is not None else (False, 0.5)
    up, down = _minutes(sunrise), _minutes(sunset)
    if up <= minute < down:
        return True, (minute - up) / max(1, down - up)
    night = (24 * 60 - down) + up
    since = (minute - down) if minute >= down else (24 * 60 - down + minute)
    return False, since / max(1, night)
