"""The call to prayer, on the screen as well as out of the speaker.

Five times a day the mat says it is time. It used to do that with a box carrying the name of
the prayer and a button to stop it. This shows the call itself: the muezzin, the words being
called, and what they mean -- so a boy who hears the adhan every day can read along with it and
come to know it, which is the whole point of the mat.

Three parts, each honest about what it is:

  * adhan.json -- the lines of the call, in Arabic, with the meaning in every language the app
    speaks. Drafted, and carrying reviewed: false until a reader of Arabic has been over it.
  * times.json -- where each line falls in a particular recording, measured off the recording
    by tools/build_azaan_times.py. A recording with no entry here simply shows the words
    without lighting them, which is the right way round: no red beats red in the wrong place.
  * this file -- the box, which knows how to show either.
"""
from __future__ import annotations

import json
from pathlib import Path

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts, TextBox

ARABIC_FLOOR, ARABIC_CAP = 22, 64
BRICK = "#A63D33"


class Adhan:
    """The words of the call, and where they fall in the recordings there are timings for."""

    def __init__(self, assets: Path):
        self.folder = Path(assets) / "content" / "azaan"
        self._words: dict | None = None
        self._times: dict | None = None

    def _read(self, name: str) -> dict:
        try:
            return json.loads((self.folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @property
    def words(self) -> dict:
        if self._words is None:
            self._words = self._read("adhan.json")
        return self._words

    @property
    def times(self) -> dict:
        if self._times is None:
            self._times = self._read("times.json")
        return self._times

    @property
    def there(self) -> bool:
        return bool(self.words.get("lines"))

    @property
    def reviewed(self) -> bool:
        """Whether a reader of Arabic has been over the words. Nothing is hidden when this is
        false -- it is here so the file, and anyone reading the code, can say where it stands."""
        return bool(self.words.get("reviewed", False))

    def picture(self) -> Path:
        return self.folder.parent.parent / "azaan" / "muezzin.png"

    def line(self, key: str) -> dict:
        for row in self.words.get("lines", []):
            if row.get("key") == key:
                return row
        return {}

    def order(self, recording: str) -> list[str]:
        """The keys of the lines called, in order, for this recording.

        From the timings when there are some, and otherwise from which call it is -- Fajr by
        its file name, the ordinary call for everything else. So the words are shown in the
        right order whether or not the recording has been measured.
        """
        known = self.times.get(recording)
        if known:
            return [row["key"] for row in known.get("lines", [])]
        which = "fajr" if "fajr" in recording else "ordinary"
        return list(self.words.get("calls", {}).get(which, []))

    def shown(self, recording: str) -> list[str]:
        """The distinct lines to put on screen, in the order they are first called."""
        seen, out = set(), []
        for key in self.order(recording):
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out

    def at(self, recording: str, seconds: float) -> tuple[str, int] | None:
        """Which line is being called and which of its words, or None between lines.

        None is a real answer, not a failure: the muezzin breathes between the lines, and
        nothing should be lit while he does.
        """
        known = self.times.get(recording)
        if not known:
            return None
        when = seconds * 1000.0
        for row in known.get("lines", []):
            if row["start"] <= when < row["end"]:
                for i, (a, b) in enumerate(row.get("words", [])):
                    if a <= when < b:
                        return row["key"], i
                return row["key"], -1        # in the line, between two of its words
        return None

    def measured(self, recording: str) -> bool:
        return bool(self.times.get(recording))


class Drawing(QtWidgets.QWidget):
    """A line drawing painted in one colour, keeping its shape.

    The picture is black lines on nothing, which is invisible on the black box it sits in. Only
    its shape matters, so it is used as a stencil and filled with whatever colour is wanted --
    and it stays the shape it was drawn, whatever shape the box it is given turns out to be.
    """

    def __init__(self, path: Path, colour: str = "#FFFFFF"):
        super().__init__()
        self.picture = QtGui.QPixmap(str(path)) if Path(path).is_file() else QtGui.QPixmap()
        self.colour = colour
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    @property
    def there(self) -> bool:
        return not self.picture.isNull()

    def paintEvent(self, _):
        if self.picture.isNull():
            return
        fitted = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        stencil = QtGui.QPixmap(fitted.size())
        stencil.fill(Qt.GlobalColor.transparent)
        ink = QtGui.QPainter(stencil)
        ink.drawPixmap(0, 0, fitted)
        ink.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        ink.fillRect(stencil.rect(), QtGui.QColor(self.colour))
        ink.end()
        p = QtGui.QPainter(self)
        p.drawPixmap((self.width() - fitted.width()) // 2,
                     (self.height() - fitted.height()) // 2, stencil)


class CallBox(QtWidgets.QDialog):
    """The box that comes up when the call is made.

    Black with a white border, like the app's other notices and for the same reason: the call
    is not part of the prayer screen, and it should not look as though it is. The muezzin on
    the left, the lines of the call on the right, each with its meaning underneath, and the
    word being called in red.
    """

    LINE_TICK = 50       # ms; how often the red moves, matching the Qur'an screen

    def __init__(self, window, prayer: str, recording: str, adhan: Adhan):
        super().__init__(window)
        self.win = window
        self.adhan = adhan
        self.recording = recording
        px = window.px
        self.setObjectName("callBox")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog#callBox {{ background:#000000; border:{px(3)}px solid #FFFFFF;
                               border-radius:{px(20)}px; }}
            QDialog#callBox QLabel {{ color:#FFFFFF; background:transparent; }}
            QLabel#callTitle {{ font-size:{px(44)}px; font-weight:bold; }}
            QLabel#callMeaning {{ font-size:{px(24)}px; color:#C9C9C9; }}
            QDialog#callBox QPushButton {{ background:{BRICK}; color:#FFFFFF; border:none;
                                           border-radius:{px(8)}px; font-size:{px(28)}px;
                                           font-weight:bold; padding:{px(14)}px {px(34)}px; }}
            QDialog#callBox QPushButton:pressed {{ background:#8E342C; }}
        """)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(px(40), px(32), px(40), px(28))
        outer.setSpacing(px(16))

        head = QtWidgets.QLabel(f"{window.t('call.title')} · {window.t(f'prayer.{prayer}')}")
        head.setObjectName("callTitle")
        outer.addWidget(head)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(px(32))
        self.drawing = Drawing(adhan.picture())
        if self.drawing.there:
            self.drawing.setMinimumWidth(px(220))
            body.addWidget(self.drawing, 2)
        else:
            self.drawing.hide()

        lines = QtWidgets.QVBoxLayout()
        lines.setSpacing(px(10))
        self.boxes: dict[str, TextBox] = {}
        lang = self.meaning_language()
        for key in adhan.shown(recording):
            row = adhan.line(key)
            arabic = TextBox(Fonts.arabic(window.settings.arabic_font),
                             ARABIC_FLOOR, ARABIC_CAP, rtl=True, by_word=True, one_line=True)
            arabic.scale = window.s
            arabic.set_lines([row.get("arabic", "")])
            arabic.setMinimumHeight(px(52))
            lines.addWidget(arabic, 3)
            self.boxes[key] = arabic

            said = QtWidgets.QLabel(row.get("text", {}).get(lang)
                                    or row.get("text", {}).get("en", ""))
            said.setObjectName("callMeaning")
            said.setWordWrap(True)
            said.setAlignment(Qt.AlignmentFlag.AlignCenter)
            said.setLayoutDirection(Qt.LayoutDirection.RightToLeft if lang in ("ur", "ar")
                                    else Qt.LayoutDirection.LeftToRight)
            lines.addWidget(said, 0)
        body.addLayout(lines, 5)
        outer.addLayout(body, 1)

        foot = QtWidgets.QHBoxLayout()
        foot.addStretch(1)
        self.stop_button = QtWidgets.QPushButton(window.t("call.stop"))
        self.stop_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stop_button.clicked.connect(self.accept)
        foot.addWidget(self.stop_button)
        outer.addLayout(foot)

        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(self.LINE_TICK)
        self.follow.timeout.connect(self.tick)
        if adhan.measured(recording):
            self.follow.start()

    def meaning_language(self) -> str:
        """The interface language if the call has been translated into it, else English."""
        wanted = getattr(self.win.pack, "lang", "en")
        rows = self.adhan.words.get("lines", [])
        have = all(row.get("text", {}).get(wanted) for row in rows) if rows else False
        return wanted if have else "en"

    def tick(self) -> None:
        """Move the red onto the word being called."""
        clock = getattr(self.win.call, "position", None)
        position = clock() if callable(clock) else None
        if position is None:
            return self.clear()
        where = self.adhan.at(self.recording, position)
        for key, box in self.boxes.items():
            if where is not None and where[0] == key and where[1] >= 0:
                box.set_highlight((0, where[1]))
            else:
                box.set_highlight(None)

    def clear(self) -> None:
        for box in self.boxes.values():
            box.set_highlight(None)

    def fit(self) -> None:
        """Most of the screen, but not all of it: it is a box on top of the mat, not the mat."""
        parent = self.parentWidget()
        if parent is None:
            return
        wide, tall = int(parent.width() * 0.82), int(parent.height() * 0.84)
        self.resize(wide, tall)
        self.move(parent.x() + (parent.width() - wide) // 2,
                  parent.y() + (parent.height() - tall) // 2)

    def showEvent(self, ev):
        self.fit()
        super().showEvent(ev)

    def done(self, result):
        self.follow.stop()
        super().done(result)
