"""An on-screen keyboard, because the mat has a touchscreen and nothing else.

Until now the app asked nobody to type anything -- not one text field in it. A wifi password
cannot be avoided though: it is long, it is case-sensitive, and nobody's router takes a number
from a list. So this is the first typing the mat has ever done, and it is built to be used with
a thumb while standing over a mat, not with a mouse.

What that means in practice:

  * keys as big as the screen will allow, laid out QWERTY so it is not a puzzle
  * a SHIFT that shows what it is doing -- a password typed in the wrong case is the commonest
    way this goes wrong, and on a touchscreen there is no feel to tell you
  * a numbers-and-symbols layer, because wifi passwords are full of them
  * one character per press and no auto-anything: no capitalising the first letter, no
    correcting, no predicting. This is a password. Guessing at it would be worse than useless.

The keyboard knows nothing about what it is typing into. It says which key was pressed and the
screen above decides what that means, so the same keyboard serves the wifi password and, next,
the postcode.
"""
from __future__ import annotations

from .qt import QtCore, QtWidgets, Qt, Signal

LETTERS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
SYMBOLS = ("1234567890", "-/:;()£&@\"", ".,?!'#%*+=")
MORE = ("[]{}\\|~^", "<>$€¥_`", "§±¿¡")

SHIFT = "⇧"        # the arrow, not the word: the word is six letters wide in a key's space
BACK = "⌫"
DONE = "⏎"


class Key(QtWidgets.QPushButton):
    """One key. Wide enough for a thumb and no wider than its share of the row."""

    def __init__(self, label: str, window, wide: float = 1.0):
        super().__init__(label)
        self.setObjectName("key")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(78))
        self.setMinimumWidth(int(window.px(74) * wide))
        # Capped as well as floored. Left to expand, the keys stretched into tall thin slots on
        # a 1080p screen -- still pressable, but nothing like a keyboard, and the eye hunts for
        # letters that are not where it expects them.
        self.setMaximumHeight(window.px(104))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Preferred)


class Keyboard(QtWidgets.QWidget):
    """Letters, symbols and the keys that are not characters."""

    typed = Signal(str)          # one character
    rubbed_out = Signal()        # backspace
    finished = Signal()          # the enter key

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("keyboard")
        self.shifted = False
        self.layer = 0           # 0 letters, 1 symbols, 2 more symbols
        self.rows = QtWidgets.QVBoxLayout(self)
        self.rows.setContentsMargins(window.px(10), window.px(6), window.px(10), window.px(10))
        self.rows.setSpacing(window.px(8))
        self.keys: list[Key] = []
        self.build()

    def plan(self) -> tuple[str, ...]:
        return (LETTERS, SYMBOLS, MORE)[self.layer]

    def build(self) -> None:
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
            elif old.layout() is not None:
                while old.layout().count():
                    inner = old.layout().takeAt(0)
                    if inner.widget() is not None:
                        inner.widget().deleteLater()
        self.keys = []

        for line in self.plan():
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(self.win.px(8))
            row.addStretch(1)
            for letter in line:
                shown = letter.upper() if (self.shifted and self.layer == 0) else letter
                key = Key(shown, self.win)
                key.clicked.connect(lambda _=False, c=shown: self.press(c))
                row.addWidget(key)
                self.keys.append(key)
            row.addStretch(1)
            self.rows.addLayout(row)

        last = QtWidgets.QHBoxLayout()
        last.setSpacing(self.win.px(8))
        if self.layer == 0:
            shift = Key(SHIFT, self.win, wide=1.6)
            shift.setObjectName("keyShift" if self.shifted else "key")
            shift.setCheckable(True)
            shift.setChecked(self.shifted)
            shift.clicked.connect(self.flip_shift)
            last.addWidget(shift)
            self.shift_key = shift
        swap = Key("123" if self.layer == 0 else ("#+=" if self.layer == 1 else "abc"),
                   self.win, wide=1.6)
        swap.clicked.connect(self.next_layer)
        last.addWidget(swap)
        space = Key(" ", self.win, wide=5.0)
        space.setToolTip(self.win.t("keys.space"))
        space.clicked.connect(lambda: self.press(" "))
        last.addWidget(space)
        rub = Key(BACK, self.win, wide=1.6)
        rub.clicked.connect(self.rubbed_out.emit)
        last.addWidget(rub)
        enter = Key(DONE, self.win, wide=1.6)
        enter.setObjectName("keyDone")
        enter.clicked.connect(self.finished.emit)
        last.addWidget(enter)
        self.rows.addLayout(last)

    def press(self, character: str) -> None:
        self.typed.emit(character)
        # Shift is for one letter, the way a phone does it -- a shift that stays on is how a
        # whole password ends up in capitals without anyone noticing.
        if self.shifted and self.layer == 0:
            self.shifted = False
            self.build()

    def flip_shift(self) -> None:
        self.shifted = not self.shifted
        self.build()

    def next_layer(self) -> None:
        self.layer = 1 if self.layer == 0 else (2 if self.layer == 1 else 0)
        self.shifted = False
        self.build()

    def letters_on_show(self) -> list[str]:
        return [k.text() for k in self.keys]
