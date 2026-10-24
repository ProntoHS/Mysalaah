#!/usr/bin/env python3
"""Is the picture left-right symmetric, so that its left and right pieces are the same piece
flipped over?

This is the thing a three-by-three jigsaw cannot have, and it is invisible to the empty-square
measure: a mirror pair can both be 51% ink and still give a child two equally good homes for
one piece. Cropping the Kaaba to the building removed the empty corners and left this.

HOW. Each piece is compared with its horizontal partner FLIPPED, using the same ink-mask
agreement as the piece sheet. A flipped match near 1 means the two holes accept the same
piece turned round.

CONTROLS, because a symmetry detector that fires on everything says nothing:
  a centred diamond           the three mirror pairs must all be found
  nine printed digits         no pair may be found: "1" flipped is not "3"
  a diamond with one corner   the pair containing that corner must drop out while the others
  marked                      stay, which is exactly the edit being recommended
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg          # noqa: F401
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheet import NAMES, confusion, crop, digits, grey, invert, piece_of, raster  # noqa: E402

PAIRS = [(0, 2), (3, 5), (6, 8)]        # top corners, middle sides, bottom corners
FLIPPED = 0.80                          # agreement with the partner flipped, above which the
                                        # two holes take the same piece turned round


def flip(piece):
    return [list(reversed(row)) for row in piece]


def mirrored(rows, quiet=False):
    found = []
    if not quiet:
        print(f"      {'pair':32s} {'as-is':>7s} {'flipped':>9s}   verdict")
    for i, j in PAIRS:
        a, b = piece_of(rows, i), piece_of(rows, j)
        plain, turned = confusion(a, b), confusion(a, flip(b))
        hit = turned > FLIPPED
        if hit:
            found.append((NAMES[i], NAMES[j]))
        if not quiet:
            print(f"      {NAMES[i] + ' / ' + NAMES[j]:32s} {plain:7.2f} {turned:9.2f}   "
                  f"{'MIRROR TWINS' if hit else ''}")
    return found


def diamond(side, mark=False):
    """A centred diamond: symmetric by construction. With mark=True one corner gets a blob,
    which is the asymmetry being recommended for the artwork."""
    img = QtGui.QImage(side, side, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("white"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    p.setBrush(QtGui.QColor("black"))
    p.setPen(QtCore.Qt.NoPen)
    m = side // 2
    p.drawPolygon(QtGui.QPolygon([QtCore.QPoint(m, side // 10), QtCore.QPoint(side * 9 // 10, m),
                                  QtCore.QPoint(m, side * 9 // 10), QtCore.QPoint(side // 10, m)]))
    if mark:
        p.drawEllipse(QtCore.QPoint(side // 9, side // 9), side // 14, side // 14)
    p.end()
    return grey(img)


def main() -> int:
    app = QApplication(sys.argv[:1])                                   # noqa: F841
    svg = Path(sys.argv[1])

    print("CONTROLS")
    print("\n  a centred diamond (all three pairs must be MIRROR TWINS)")
    if len(mirrored(diamond(600))) != 3:
        print("\nREFUSED: the detector misses a picture that is symmetric by construction.")
        return 2
    print("\n  nine printed digits (no pair may be found)")
    if mirrored(digits(600)):
        print("\nREFUSED: the detector calls plainly different marks mirror twins.")
        return 2
    print("\n  the same diamond with ONE corner marked (top pair must drop out, others stay)")
    got = mirrored(diamond(600, mark=True))
    if sorted(p[0] for p in got) != ["bottom-left", "left"]:
        print(f"\nREFUSED: marking one corner did not clear that pair alone; left {got}")
        return 2
    print("\n  all three controls behaved.")

    k = 600 / 900
    whole = invert(grey(raster(svg, 600)))
    tight = crop(whole, int(125 * k), int(218 * k), int(775 * k), int(853 * k))
    print("\nCANDIDATE")
    print("\n  as sent, the whole frame")
    a = mirrored(whole)
    print("\n  cropped to the building")
    b = mirrored(tight)
    print()
    for label, got in (("as sent", a), ("cropped", b)):
        if got:
            print(f"  {label}: {len(got)} mirror pair(s) -- "
                  + "; ".join(f"{x} / {y}" for x, y in got))
        else:
            print(f"  {label}: no mirror pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
