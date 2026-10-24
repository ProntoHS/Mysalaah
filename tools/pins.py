#!/usr/bin/env python3
"""Two checks on Qibla Quest's five cities, done separately so neither can cover for the other.

ONE: the answer. The initial great-circle bearing from each city to the Kaaba, worked out from
latitudes and longitudes, binned to eight points, and compared with the answer the game ships.
This is arithmetic and owes nothing to the artwork.

TWO: the pin. The game places each city at a fraction of the map's width and height. Each
continent in the artwork is rasterised ON ITS OWN, so the pin's pixel can be attributed to a
named landmass rather than just "some ink". A pin in the sea, or on the wrong continent, is
wrong however right the bearing is.

The continents are identified once, by their drawn extent, and the naming is printed so it can
be checked rather than believed.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg          # noqa: F401
from PySide6.QtWidgets import QApplication

KAABA = (21.4225, 39.8262)

# The five rounds as the module ships them: city, answer, (x fraction, y fraction).
ROUNDS = [("london", "se", (0.45, 0.25)),
          ("cape_town", "ne", (0.53, 0.78)),
          ("tashkent", "sw", (0.63, 0.29)),
          ("jakarta", "nw", (0.78, 0.70)),
          ("istanbul", "se", (0.55, 0.34))]

WHERE = {"london": (51.5074, -0.1278), "cape_town": (-33.9249, 18.4241),
         "tashkent": (41.2995, 69.2401), "jakarta": (-6.2088, 106.8456),
         "istanbul": (41.0082, 28.9784)}

POINTS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]


def bearing(lat1, lon1, lat2=KAABA[0], lon2=KAABA[1]) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def to_point(deg: float) -> str:
    return POINTS[int((deg + 22.5) % 360 // 45)]


def continents(svg_text: str):
    """Each continent path on its own, as (index, d)."""
    inner = re.search(r'<g class="continents"[^>]*>(.*?)</g>', svg_text, re.S)
    body = inner.group(1) if inner else svg_text
    return list(enumerate(re.findall(r'<path[^>]*\bd="([^"]+)"', body)))


def mask(d: str, box: str, w: int, h: int):
    """Rasterise one path, filled, and return a function saying whether a pixel is inside it."""
    one = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}">'
           f'<path d="{d}" fill="#000"/></svg>')
    r = QtSvg.QSvgRenderer(QtCore.QByteArray(one.encode()))
    img = QtGui.QImage(w, h, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("white"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, False)
    r.render(p)
    p.end()
    return img


def extent(img):
    """(x0, y0, x1, y1) of the drawn pixels, for naming the landmass."""
    xs, ys = [], []
    for y in range(img.height()):
        for x in range(img.width()):
            if QtGui.qGray(img.pixel(x, y)) < 128:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def main() -> int:
    app = QApplication(sys.argv[:1])                                   # noqa: F841
    svg_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    box = re.search(r'viewBox="([^"]*)"', svg_text).group(1)
    vw, vh = (float(v) for v in box.split()[2:4])
    w, h = 600, int(600 * vh / vw)

    print("ONE  the answers, from latitude and longitude\n")
    print(f"  {'city':12s} {'lat':>8s} {'lon':>9s} {'bearing':>9s} {'computed':>9s} "
          f"{'shipped':>8s}   verdict")
    wrong = []
    for city, answer, _ in ROUNDS:
        lat, lon = WHERE[city]
        deg = bearing(lat, lon)
        got = to_point(deg)
        ok = got == answer
        if not ok:
            wrong.append(f"{city}: computed {got} ({deg:.0f} deg), ships {answer}")
        print(f"  {city:12s} {lat:8.2f} {lon:9.2f} {deg:8.1f}d {got:>9s} {answer:>8s}   "
              f"{'' if ok else 'WRONG'}")

    print("\nTWO  the pins, against the drawn artwork\n")
    masks = []
    for i, d in continents(svg_text):
        img = mask(d, box, w, h)
        e = extent(img)
        masks.append((i, img, e))
    print("  landmasses found, by drawn extent (check these names against the picture):")
    for i, _, e in masks:
        print(f"      path {i}: x {e[0]:3d}-{e[2]:3d}  y {e[1]:3d}-{e[3]:3d}")

    print()
    print(f"  {'city':12s} {'pin px':>12s}   on")
    for city, _, (fx, fy) in ROUNDS:
        px, py = int(fx * w), int(fy * h)
        on = [i for i, img, _ in masks
              if 0 <= px < w and 0 <= py < h and QtGui.qGray(img.pixel(px, py)) < 128]
        where = f"path {on[0]}" if on else "SEA -- no landmass under the pin"
        if not on:
            wrong.append(f"{city}: pin at ({fx}, {fy}) falls in open sea")
        print(f"  {city:12s} {str((px, py)):>12s}   {where}")

    print()
    if wrong:
        for b in wrong:
            print(f"  WRONG  {b}")
        return 1
    print("  every bearing matches the shipped answer and every pin sits on land.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
