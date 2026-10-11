"""Uses PySide6 or PyQt6, whichever is installed. Set SALAAH_QT=PyQt6 or PySide6 to force one."""
import os

_want = os.environ.get("SALAAH_QT", "")
if _want == "PyQt6":
    _order = ("PyQt6", "PySide6")
else:
    _order = ("PySide6", "PyQt6")

for _name in _order:
    try:
        if _name == "PySide6":
            from PySide6 import QtCore, QtGui, QtWidgets  # noqa: F401
            Signal = QtCore.Signal
        else:
            from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: F401
            Signal = QtCore.pyqtSignal
        API = _name
        break
    except ImportError:
        continue
else:
    raise ImportError("Install PySide6 or PyQt6 (see install.sh)")

Qt = QtCore.Qt


# Arrows that point the way the reading goes.
#
# A row of buttons mirrors when the app is laid out right to left -- Qt moves them, which is
# correct: in Urdu and Arabic the first thing you come to is on the RIGHT. What Qt cannot do is
# turn the arrow round, so "<" ended up on the left of the pair, still pointing left, while
# meaning "the one after this". The glyph said one thing and its position said the other.
#
# So the glyphs swap with the direction and the positions are left to Qt. Back always points
# the way you came from -- left in English, right in Urdu -- and on always points onward.
# BACK_ARROW, ON_ARROW and arrows() went in 1.69. Every way-back and next on the mat was
# the character "‹" or "›" set in whatever face the pack is written in, and that is
# exactly what was wrong with them: a guillemet is punctuation, drawn small and light
# because it belongs beside words, so in a button the size of a thumb it was a speck in a
# slab. They are painted now -- see ArrowButton in render.py -- and which way they point is
# the button's own business rather than a pair of characters chosen for it here.
