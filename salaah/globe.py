"""Where a place is on the turning globe.

The world screen shows an animation of the earth going round, and draws on top of it the mat's
own place, the Kaaba, and the line between them. For any of that to land in the right spot the
app has to know how the animation is drawn: where the circle is, how big, which way it is
tilted, and which longitude is facing us on each frame.

None of that is written down in a GIF, so it was measured out of the animation itself by
tools/build_globe.py and left beside it in globe.json. The measurement is worth a sentence,
because it is the reason the line ends on the Kaaba rather than near it: the animator drew a
marker on Mecca, and that marker turns with the globe, so tracking it across the twenty frames
it is visible for and fitting a sphere to where it went gives the geometry directly. It came out
to a pixel.

The projection is orthographic -- the globe as seen from far away, which is what a drawing of a
ball is. Everything here works in fractions of the picture rather than pixels, so the screen can
draw the globe at whatever size it has room for and these numbers still hold.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

# 21°25'N 39°49'E: the Kaaba. The same figure the qibla compass uses.
KAABA = (21.4225, 39.8262)

EARTH_KM = 6371.0


@dataclass(frozen=True)
class Spot:
    """Where a place lands on the picture, as fractions of its width and height."""
    x: float
    y: float
    facing: float        # 1 dead centre, 0 on the edge, below 0 round the back

    @property
    def seen(self) -> bool:
        return self.facing >= 0


def _vector(lat: float, lon: float) -> tuple[float, float, float]:
    """A place on the earth as a direction from its centre."""
    a, b = math.radians(lat), math.radians(lon)
    return math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a)


def between(one: tuple[float, float], two: tuple[float, float], steps: int = 96):
    """The great circle from one place to the other: the way you would actually go.

    Walked as a turn from the first direction to the second rather than as a line drawn on a
    map, so it comes out as the curve it is -- which from England to Mecca bends noticeably
    east of the straight line anyone would draw on a wall map.
    """
    a, b = _vector(*one), _vector(*two)
    dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(a, b))))
    angle = math.acos(dot)
    if angle < 1e-9:
        return [one]
    out = []
    for i in range(steps + 1):
        t = i / steps
        # Turning evenly from one to the other, keeping to the surface the whole way.
        k1 = math.sin((1 - t) * angle) / math.sin(angle)
        k2 = math.sin(t * angle) / math.sin(angle)
        x, y, z = (k1 * a[0] + k2 * b[0], k1 * a[1] + k2 * b[1], k1 * a[2] + k2 * b[2])
        out.append((math.degrees(math.asin(max(-1.0, min(1.0, z)))), math.degrees(math.atan2(y, x))))
    return out


def apart(one: tuple[float, float], two: tuple[float, float]) -> float:
    """How far apart two places are, in kilometres, over the surface."""
    a, b = _vector(*one), _vector(*two)
    dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(a, b))))
    return EARTH_KM * math.acos(dot)


class Globe:
    """The animation's own geometry, read off the file the build tool wrote."""

    # What the measurement came to for the globe that ships with the app. Kept here as a
    # fallback so a mat missing the file still draws something sensible rather than nothing.
    FALLBACK = {"centre": [0.5, 0.5], "radius": 0.413623, "tilt": 9.978,
                "start": -0.66, "per_frame": 5.10918, "frames": 72}

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.film = self.folder / "globe.gif"
        try:
            said = json.loads((self.folder / "globe.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            said = {}
        for key, value in self.FALLBACK.items():
            setattr(self, key, said.get(key, value))
        self.measured = bool(said)

    @property
    def there(self) -> bool:
        return self.film.is_file()

    def facing(self, frame: int) -> tuple[float, float]:
        """The point of the earth looking straight at us on this frame."""
        return self.tilt, self.start + self.per_frame * (frame % max(1, self.frames))

    def at(self, frame: int, lat: float, lon: float) -> Spot:
        """Where a place lands on the picture on this frame."""
        view_lat, view_lon = self.facing(frame)
        p0, l0 = math.radians(view_lat), math.radians(view_lon)
        p, gap = math.radians(lat), math.radians(lon) - l0
        # How far round the ball it is from the point facing us: positive is this side.
        facing = math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(gap)
        cx, cy = self.centre
        x = cx + self.radius * math.cos(p) * math.sin(gap)
        y = cy - self.radius * (math.cos(p0) * math.sin(p)
                                - math.sin(p0) * math.cos(p) * math.cos(gap))
        return Spot(x, y, facing)

    def route(self, frame: int, one: tuple[float, float], two: tuple[float, float],
              steps: int = 96) -> list[Spot]:
        """The part of the great circle between two places that is on this side of the earth.

        One run, never several. The half of the earth facing us is a hemisphere, and the shorter
        way round between two points in a hemisphere never leaves it -- so a route is either
        wholly in sight, or in sight from one end until it goes over the edge, and it cannot
        come back. Forty thousand random pairs of places bear that out and so does the geometry.
        Worth knowing, because a line that could break in the middle would have to be drawn in
        pieces, and drawing it as one would lay a chord straight across the face of the globe.
        """
        return [spot for spot in (self.at(frame, lat, lon)
                                  for lat, lon in between(one, two, steps)) if spot.seen]
