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
