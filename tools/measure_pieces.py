#!/usr/bin/env python3
"""Cut a candidate jigsaw picture the way the game cuts it and measure the nine pieces.

The question is not whether the artwork is handsome. It is whether a child shown ONE piece can
tell which of three holes it came from. Two measurements answer that:

  ink      what fraction of the piece is not background. A piece that is 1% ink is a blank
           square with a speck on it, and three blank squares are the same square.
  nearest  how different the piece is from the piece it most resembles, as mean absolute
           difference per pixel out of 255. Low means two holes accept the same piece by eye.

Both are computed on the picture AFTER inverting to the mat's black-on-white convention,
because that is what would ship.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg          # noqa: F401  (QtSvg registers the handler)
from PySide6.QtWidgets import QApplication


def raster(svg: Path, side: int) -> QtGui.QImage:
    renderer = QtSvg.QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise SystemExit(f"Qt will not read {svg}")
    img = QtGui.QImage(side, side, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("black"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    renderer.render(p)
    p.end()
    return img


def grey(img: QtGui.QImage) -> list[list[int]]:
    g = img.convertToFormat(QtGui.QImage.Format_Grayscale8)
    w, h = g.width(), g.height()
    ptr = g.constBits()
    stride = g.bytesPerLine()
    raw = bytes(ptr)
    return [[raw[y * stride + x] for x in range(w)] for y in range(h)]


def invert(rows):
    return [[255 - v for v in row] for row in rows]


def piece_of(rows, number: int):
    """Exactly the game's crop: divmod(number, 3), integer thirds."""
    h, w = len(rows), len(rows[0])
    row, col = divmod(number, 3)
    x0, x1 = int(col * w / 3), int((col + 1) * w / 3)
    y0, y1 = int(row * h / 3), int((row + 1) * h / 3)
    return [r[x0:x1] for r in rows[y0:y1]]


def ink(piece) -> float:
    """Fraction of pixels that are not within 8 of pure white (the background, after inverting)."""
    n = sum(1 for row in piece for v in row if v < 247)
    return n / (len(piece) * len(piece[0]))


def difference(a, b) -> float:
    """Mean absolute difference per pixel, 0-255. Pieces are the same size by construction."""
    total = 0
    for ra, rb in zip(a, b):
        for va, vb in zip(ra, rb):
            total += abs(va - vb)
    return total / (len(a) * len(a[0]))


def main() -> int:
    app = QApplication(sys.argv[:1])                                   # noqa: F841
    svg = Path(sys.argv[1])
    side = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    rows = invert(grey(raster(svg, side)))

    pieces = [piece_of(rows, n) for n in range(9)]
    names = ["top-left", "top-middle", "top-right",
             "left", "centre", "right",
             "bottom-left", "bottom-middle", "bottom-right"]

    print(f"{svg.name}, rasterised at {side}x{side}, inverted to black-on-white")
    print(f"whole picture: {ink(rows) * 100:.1f}% ink\n")
    print(f"  {'piece':14s} {'ink':>7s}   nearest other piece")
    worst = []
    for i, piece in enumerate(pieces):
        diffs = sorted(((difference(piece, other), names[j])
                        for j, other in enumerate(pieces) if j != i))
        near, who = diffs[0]
        flag = ""
        if ink(piece) < 0.03:
            flag = "   <-- BLANK"
        elif near < 12:
            flag = "   <-- hard to tell from it"
        print(f"  {names[i]:14s} {ink(piece) * 100:6.1f}%   {who} ({near:.1f} of 255){flag}")
        if flag:
            worst.append(names[i])

    print()
    if worst:
        print(f"{len(worst)} of 9 pieces a child could not place by looking: {', '.join(worst)}")
        return 1
    print("All nine pieces carry enough to tell apart.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
