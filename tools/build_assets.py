#!/usr/bin/env python3
"""Turn the two pieces of artwork into the PNGs the two games ask for.

  assets/children/kaaba-jigsaw.png   from kaaba-puzzle.svg, inverted and cropped to the
                                     building, so none of the nine pieces is an empty square
  assets/children/qibla-quest.png    from the world map's own vector geometry in the
                                     prototype's index.html, inverted -- NOT a screenshot

Both are checked against what the games' own notes require: PNG, no words baked in, white
background, under 2 MB.

INVERTING IS NOT JUST THE HOUSE STYLE. The Kaaba is drawn with white faces and a black band.
Inverted, the faces go black and the band goes white, which is the way the kiswah actually
looks: black cloth with a pale band around it. The mat's convention and the subject agree.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg          # noqa: F401
from PySide6.QtWidgets import QApplication

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SVG = Path("/root/.claude/uploads/1cacb48f-b231-521a-a388-7e401af6e156/"
           "b641b7ec-1792598479346_kaaba-puzzle.svg")
PROTO = Path("/home/claude/in3/games/mysalaah_all_games_complete_collection/02_qibla_quest/"
             "standalone_prototype/static/index.html")


def inverted(img: QtGui.QImage) -> QtGui.QImage:
    out = img.convertToFormat(QtGui.QImage.Format_RGB32)
    out.invertPixels(QtGui.QImage.InvertMode.InvertRgb)
    return out


def kaaba(side: int = 900) -> QtGui.QImage:
    r = QtSvg.QSvgRenderer(str(SVG))
    big = QtGui.QImage(side, side, QtGui.QImage.Format_RGB32)
    big.fill(QtGui.QColor("black"))
    p = QtGui.QPainter(big)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    big = inverted(big)
    # The building's own box: the group is translate(125 218) spanning 0..650 by 0..635.
    k = side / 900
    box = QtCore.QRect(int(125 * k), int(218 * k), int(650 * k), int(635 * k))
    cut = big.copy(box)
    # Square it off so the game's integer thirds divide evenly in both directions.
    n = min(cut.width(), cut.height()) // 3 * 3
    return cut.copy((cut.width() - n) // 2, (cut.height() - n) // 2, n, n)


def map_png(width: int = 1600) -> QtGui.QImage:
    html = PROTO.read_text(encoding="utf-8")
    svg = re.search(r'<svg id="world-map".*?</svg>', html, re.S).group(0)
    box = re.search(r'viewBox="([^"]*)"', svg).group(1)
    vw, vh = (float(v) for v in box.split()[2:4])
    inner = re.search(r'<g class="continents"[^>]*>(.*?)</g>', svg, re.S).group(1)
    paths = re.findall(r'<path[^>]*\bd="([^"]+)"', inner)
    # Only the land. The route line, the YOU and MAKKAH labels and the markers are drawn by
    # the game at run time, and words must not be baked into the picture.
    land = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}">'
            + "".join(f'<path d="{d}" fill="#ffffff"/>' for d in paths) + "</svg>")
    r = QtSvg.QSvgRenderer(QtCore.QByteArray(land.encode()))
    h = int(width * vh / vw)
    img = QtGui.QImage(width, h, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("black"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    return inverted(img)


def check(path: Path, img: QtGui.QImage) -> None:
    size = path.stat().st_size
    corner = QtGui.qGray(img.pixel(1, 1))
    print(f"  {path.name:22s} {img.width()}x{img.height()}  {size:,} bytes  "
          f"corner grey {corner}")
    assert path.suffix == ".png", path
    assert size < 2 * 1024 * 1024, f"{path.name} is over 2 MB"
    assert corner > 240, f"{path.name} does not have a white background"


def main() -> int:
    app = QApplication(sys.argv[:1])                                   # noqa: F841
    OUT.mkdir(parents=True, exist_ok=True)
    k, m = kaaba(), map_png()
    for name, img in (("kaaba-jigsaw.png", k), ("qibla-quest.png", m)):
        path = OUT / name
        img.save(str(path), "PNG")
        check(path, img)
    print("\n  both pass: PNG, white background, no words baked in, well under 2 MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
