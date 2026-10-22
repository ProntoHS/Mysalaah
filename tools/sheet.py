#!/usr/bin/env python3
"""Cut a candidate jigsaw picture the way the game cuts it, and say whether a child could
place each of the nine pieces by looking at it.

WHY THE FIRST VERSION OF THIS WAS WRONG. It compared two pieces by mean absolute difference
over every pixel. Nine squares each holding one printed digit came back as eight twins out of
nine, because a square holding "3" and a square holding "8" are both 95% white: only 5% of the
pixels can differ at all, so the average over all of them is near zero however different the
marks are. The control was right and the measure was wrong.

So two things are measured instead, and they answer two different questions.

  visible ink   coverage multiplied by contrast. A piece that is 2% covered by a hairline at
                28% grey carries 0.6% visible ink and reads as an empty square at any size a
                7-inch panel can show it. This is what rules out a corner of a centred
                composition, where the artwork simply is not.
  confusion     of the pixels where EITHER piece has ink, the fraction both agree about. Two
                pieces whose marks sit in the same places with the same weight score near 1
                and are the same piece as far as the eye is concerned. Mirror images score
                low, correctly: a stroke leaning left is not a stroke leaning right.

Controls run first, and the run stops if any of them misbehaves:
  a blank white square       all nine must be called empty
  nine printed digits        none may be called empty or confusable
  a picture with two cells   exactly those two must be called confusable
  deliberately identical
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg          # noqa: F401
from PySide6.QtWidgets import QApplication

NAMES = ["top-left", "top-middle", "top-right", "left", "centre", "right",
         "bottom-left", "bottom-middle", "bottom-right"]
PALE = 247          # at or above this is background
EMPTY = 0.010       # visible ink below 1% is an empty square
SAME = 0.55         # agreement above this is the same piece to look at


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


def grey(img: QtGui.QImage):
    g = img.convertToFormat(QtGui.QImage.Format_Grayscale8)
    raw, stride, w = bytes(g.constBits()), g.bytesPerLine(), g.width()
    return [[raw[y * stride + x] for x in range(w)] for y in range(g.height())]


def invert(rows):
    return [[255 - v for v in row] for row in rows]


def piece_of(rows, number: int):
    """Exactly the game's crop: divmod(number, 3) and integer thirds."""
    h, w = len(rows), len(rows[0])
    row, col = divmod(number, 3)
    x0, x1 = int(col * w / 3), int((col + 1) * w / 3)
    y0, y1 = int(row * h / 3), int((row + 1) * h / 3)
    return [r[x0:x1] for r in rows[y0:y1]]


def visible(piece) -> tuple[float, float, float]:
    """(visible ink, coverage, mean contrast of the covered pixels)."""
    n = len(piece) * len(piece[0])
    marks = [255 - v for row in piece for v in row if v < PALE]
    if not marks:
        return 0.0, 0.0, 0.0
    cover = len(marks) / n
    strength = (sum(marks) / len(marks)) / 255
    return cover * strength, cover, strength


def confusion(a, b) -> float:
    """Of the pixels where either has ink, the fraction the two agree about.

    Agreement is per pixel: 1 minus the difference in ink weight, so a black mark against a
    pale one counts as partial disagreement rather than a match.
    """
    both = agree = 0
    for ra, rb in zip(a, b):
        for va, vb in zip(ra, rb):
            ia, ib = max(0, PALE - va), max(0, PALE - vb)
            if ia or ib:
                both += 1
                agree += 1 - abs(ia - ib) / max(ia, ib)
    return agree / both if both else 1.0


def verdict(rows):
    pieces = [piece_of(rows, n) for n in range(9)]
    out = []
    for i, piece in enumerate(pieces):
        vis, cover, strength = visible(piece)
        worst, who = 0.0, ""
        for j, other in enumerate(pieces):
            if j != i:
                c = confusion(piece, other)
                if c > worst:
                    worst, who = c, NAMES[j]
        # EMPTY is the only VERDICT, because it is the only one of the two measures whose
        # controls hold. Agreement is reported and ranked, and left to a person: nine printed
        # digits put "3" and "8" at 0.74 because they really do share most of their strokes,
        # and no threshold tells that apart from two pieces that are actually the same. A
        # measure that cannot pass its own control does not get to fail anybody's artwork.
        flag = "EMPTY" if vis < EMPTY else ""
        out.append((NAMES[i], vis, cover, strength, worst, who, flag))
    return out


def report(label, rows, quiet=False):
    rowsout = verdict(rows)
    if not quiet:
        print(f"\n  {label}")
        print(f"      {'piece':14s} {'visible':>8s} {'= cover':>8s} {'x contrast':>11s}"
              f"   {'most like':>13s}  agree   verdict")
        for name, vis, cover, strength, worst, who, flag in rowsout:
            print(f"      {name:14s} {vis * 100:7.2f}% {cover * 100:7.1f}% {strength * 100:10.0f}%"
                  f"   {who:>13s} {worst:5.2f}   {flag}")
    bad = [r[0] for r in rowsout if r[6]]
    pair = max(rowsout, key=lambda r: r[4])
    if not quiet:
        print(f"      -> {len(bad)} of 9 empty"
              f"{': ' + ', '.join(bad) if bad else ''}")
        print(f"      -> most alike: {pair[0]} and {pair[5]}, agreeing {pair[4]:.2f} "
              f"-- LOOK at the sheet and judge")
    return bad, (pair[0], pair[5], pair[4])


def blank(side):
    img = QtGui.QImage(side, side, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("white"))
    return grey(img)


def digits(side, twins=False):
    """Nine printed digits; with twins=True, cells 1 and 3 get the same digit."""
    img = QtGui.QImage(side, side, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("white"))
    p = QtGui.QPainter(img)
    f = p.font()
    f.setPixelSize(side // 5)
    p.setFont(f)
    for n in range(9):
        r, c = divmod(n, 3)
        box = QtCore.QRect(c * side // 3, r * side // 3, side // 3, side // 3)
        shown = "1" if (twins and n in (0, 2)) else str(n + 1)
        p.drawText(box, QtCore.Qt.AlignCenter, shown)
    p.end()
    return grey(img)


def crop(rows, x0, y0, x1, y1):
    return [r[x0:x1] for r in rows[y0:y1]]


def sheet(rows, out: Path, title: str):
    cell, gap, pad, top = 170, 14, 20, 56
    w = pad * 2 + cell * 3 + gap * 2
    h = top + pad + cell * 3 + gap * 2 + 3 * 24
    img = QtGui.QImage(w, h, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor("#d6d6d6"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    f = p.font()
    f.setPixelSize(21)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QtGui.QColor("#111"))
    p.drawText(QtCore.QRect(0, 14, w, 30), QtCore.Qt.AlignCenter, title)
    for n in range(9):
        piece = piece_of(rows, n)
        ph, pw = len(piece), len(piece[0])
        # RGB32 and setPixelColor, NOT setPixel on a Grayscale8 image: on an 8-bit image
        # setPixel takes a colour-TABLE INDEX, and a grayscale image has no table, so the
        # first version of this sheet drew a dark smear that contradicted its own numbers.
        small = QtGui.QImage(pw, ph, QtGui.QImage.Format_RGB32)
        for y, row in enumerate(piece):
            for x, v in enumerate(row):
                small.setPixelColor(x, y, QtGui.QColor(v, v, v))
        r, c = divmod(n, 3)
        x, y = pad + c * (cell + gap), top + r * (cell + gap + 24)
        p.drawImage(QtCore.QRect(x, y, cell, cell), small)
        p.setPen(QtGui.QColor("#666"))
        p.drawRect(QtCore.QRect(x, y, cell, cell))
        f.setPixelSize(15)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QtGui.QColor("#111"))
        vis = visible(piece)[0]
        p.drawText(QtCore.QRect(x, y + cell + 3, cell, 20), QtCore.Qt.AlignCenter,
                   f"{NAMES[n]}  {vis * 100:.1f}% visible")
    p.end()
    img.save(str(out))
    print(f"  wrote {out}")


def main() -> int:
    app = QApplication(sys.argv[:1])                                   # noqa: F841
    svg = Path(sys.argv[1])
    here = Path(__file__).resolve().parent

    print("CONTROLS")
    bad, _ = report("a blank white square (all nine must be EMPTY)", blank(600))
    if len(bad) != 9:
        print("\nREFUSED: the checker does not notice a blank picture.")
        return 2
    bad, _ = report("nine printed digits (none may be EMPTY)", digits(600))
    if bad:
        print(f"\nREFUSED: the checker calls a plainly marked square empty: {bad}")
        return 2
    bad, pair = report("digits, with top-left and top-right made identical", digits(600, twins=True))
    if bad or sorted(pair[:2]) != ["top-left", "top-right"]:
        print(f"\nREFUSED: the ranking did not put the deliberate twins first; it said {pair}")
        return 2
    print("\n  all three controls behaved: empty is detected, a marked square is not called")
    print("  empty, and the one pair that really is identical ranks top for agreement.")

    print("\nCANDIDATE")
    whole = invert(grey(raster(svg, 600)))
    report("as sent, the whole 900x900 frame", whole)
    sheet(whole, here / "pieces-whole-frame.png", "kaaba-puzzle.svg as sent, inverted")

    # The Kaaba group is translate(125 218) spanning 0..650 across and 0..635 down, so on the
    # page it is x 125..775, y 218..853. Cropping there loses the crescent and the stars.
    k = 600 / 900
    tight = crop(whole, int(125 * k), int(218 * k), int(775 * k), int(853 * k))
    report("cropped to the building (crescent and stars lost)", tight)
    sheet(tight, here / "pieces-cropped.png", "cropped to the building")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
