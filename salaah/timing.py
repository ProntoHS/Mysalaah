"""Tap-along word timings, done on the mat with the ring.

The red highlight follows word timings that were worked out from pauses and text length. They
drift inside long lines, and they can't know how long this Pi's audio player takes to start.
Tapping along fixes both at once: each press is timed by the very clock the prayer screen uses to
colour the words, so the start-up delay is inside every tap.

For each recording: press to play it, then press the ring as each red word begins. The first word
starts with the recording, so it needs no tap. The new timings are saved as soon as the recording
ends, then played back once so you can see whether they are right. Press again for the next
recording, or back to tap this one again.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .audio import SCHEMA, Span, Timings
from .qt import QtCore, QtWidgets, Qt

# A press comes a little after the word is heard: the ring's radio and the hand both take time.
# Taking this off each tap puts the red on the word as it begins rather than just after.
REACTION = 0.10

# The order the recordings come in, which is the order they come in the prayer.
ORDER = ["takbir", "istiftah", "taawwudh_basmala", "fatiha", "ameen", "kawthar", "ikhlas", "falaq", "nas",
         "ruku_tasbih", "tasmi_tahmid", "sujood_tasbih", "jalsa_dua", "tashahhud", "salawat",
         "rabbana_atina", "salam", "istighfar", "ayat_kursi", "dhikr_salam", "subhanallah", "alhamdulillah",
         "allahu_akbar", "dhikr_tahlil", "qunut_1", "qunut_2"]

LETTERS = re.compile(r"[ء-ي]")

READY, TAPPING, CHECKING = "ready", "tapping", "checking"


def letters(word: str) -> int:
    return max(1, len(LETTERS.findall(word)))


class TapSession:
    """The taps for one recording, and the timings they make. No screen code, so it can be
    tested on its own."""

    def __init__(self, lines: list[str], old: Timings):
        self.lines = lines
        self.old = old
        self.words = [(li, wi, w) for li, line in enumerate(lines) for wi, w in enumerate(line.split())]
        first = old.words[0][0].start if old.words and old.words[0] else old.segments[0].start
        self.starts: list[float] = [first]        # the first word begins with the recording

    @property
    def next_word(self) -> tuple[int, int] | None:
        """(line, word) of the word waiting for its tap, or None when every word has one."""
        if len(self.starts) >= len(self.words):
            return None
        li, wi, _ = self.words[len(self.starts)]
        return li, wi

    @property
    def complete(self) -> bool:
        return self.next_word is None

    def tap(self, heard_at: float) -> None:
        if self.complete:
            return
        t = heard_at - REACTION
        self.starts.append(max(t, self.starts[-1] + 0.05))    # always after the word before

    def timings(self) -> dict:
        """The timings file these taps make. Words nobody tapped (the recording ended first)
        share out what is left by length, so the file is always whole."""
        speech_end = self.old.segments[-1].end
        starts = list(self.starts)
        missing = self.words[len(starts):]
        if missing:
            begin = starts[-1] + 0.3
            room = max(0.1, speech_end - begin)
            total = sum(letters(w) for _, _, w in missing)
            t = begin
            for _, _, w in missing:
                starts.append(t)
                t += room * letters(w) / total

        # A word runs until the next one starts, except at the end of a line where the
        # recording pauses: there the old timings already know where the voice stopped.
        segments: list[dict] = []
        for n, (li, wi, _) in enumerate(self.words):
            start = starts[n]
            if n + 1 < len(self.words):
                end = starts[n + 1]
                last_in_line = self.words[n + 1][0] != li
                old_end = self.old.segments[li].end if li < len(self.old.segments) else end
                if last_in_line and start < old_end < end:
                    end = old_end
            else:
                end = max(speech_end, start + 0.3)
            if wi == 0:
                segments.append({"start": round(start, 3), "end": 0.0, "words": []})
            segments[-1]["words"].append({"start": round(start, 3), "end": round(end, 3)})
            segments[-1]["end"] = round(end, 3)
        return {
            "schema": SCHEMA,
            "file": self.old.audio.name,
            "reciter": self.old.reciter,
            "estimated": False,
            "note": "Word starts tapped in by ear on the mat (Settings, Tap in the timings).",
            "segments": segments,
        }


class TimingScreen(QtWidgets.QWidget):
    """Full screen: the recording's words, big, with the next word to tap in red."""

    def __init__(self, window, text_box):
        super().__init__()
        self.win = window
        self.setObjectName("timingRoot")
        self.keys = [k for k in ORDER if k in window.timings] + \
                    sorted(k for k in window.timings if k not in ORDER)
        self.index = 0
        self.state = READY
        self.session: TapSession | None = None
        self.message = ""
        px = window.px

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(36), px(20), px(36), px(24))
        lay.setSpacing(px(14))

        bar = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("timingTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(self.title)
        bar.addStretch(1)
        self.count = QtWidgets.QLabel()
        self.count.setObjectName("timingCount")
        bar.addWidget(self.count)
        bar.addSpacing(px(24))
        leave = QtWidgets.QPushButton(window.t("timing.leave"))
        leave.setObjectName("mainScreen")
        leave.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        leave.clicked.connect(self.leave)
        bar.addWidget(leave)
        lay.addLayout(bar)

        self.words = text_box
        lay.addWidget(self.words, 1)

        self.hint = QtWidgets.QLabel()
        self.hint.setObjectName("timingHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(px(20))
        self.previous_button = self._button(window.t("timing.previous"), lambda: self.go(-1))
        self.again_button = self._button(window.t("timing.again"), self.start)
        self.next_button = self._button(window.t("timing.next"), lambda: self.go(1))
        buttons.addStretch(1)
        for b in (self.previous_button, self.again_button, self.next_button):
            buttons.addWidget(b)
        buttons.addStretch(1)
        lay.addLayout(buttons)

        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(40)
        self.follow.timeout.connect(self.tick)

    def _button(self, text: str, action) -> QtWidgets.QPushButton:
        b = QtWidgets.QPushButton(text)
        b.setObjectName("timingButton")
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.clicked.connect(action)
        return b

    # -- which recording ----------------------------------------------------------------------

    @property
    def key(self) -> str:
        return self.keys[self.index]

    def open(self, index: int = 0) -> None:
        self.index = max(0, min(index, len(self.keys) - 1))
        self.show_ready()

    def go(self, step: int) -> None:
        self.win.recitation.stop()
        self.index = (self.index + step) % len(self.keys)
        self.show_ready()

    def leave(self) -> None:
        self.follow.stop()
        self.win.recitation.stop()
        self.win.open_settings()

    # -- the three states ---------------------------------------------------------------------

    def show_ready(self) -> None:
        self.follow.stop()
        self.state = READY
        self.session = None
        self.words.set_lines(self.win.content.arabic.get(self.key, []))
        self.words.set_highlight(None)
        self.title.setText(self.win.t(f"recording.{self.key}"))
        self.count.setText(self.win.t("timing.count", n=self.index + 1, total=len(self.keys)))
        measured = not self.win.timings[self.key].estimated
        self.hint.setText(self.win.t("timing.ready_done" if measured else "timing.ready"))

    def start(self) -> None:
        """Plays the recording once, from the top, and starts taking taps."""
        timings = self.win.timings[self.key]
        self.session = TapSession(self.win.content.arabic.get(self.key, []), timings)
        span = Span(0.0, timings.segments[-1].end + 0.6)
        if not self.win.recitation.play(timings.audio, span):
            self.hint.setText(self.win.t("timing.no_sound"))
            return
        self.state = TAPPING
        self.words.set_highlight(self.session.next_word)
        self.hint.setText(self.win.t("timing.tapping"))
        self.follow.start()

    def finish(self) -> None:
        """Saves what was tapped, then plays it back so it can be checked."""
        self.win.recitation.stop()
        data = self.session.timings()
        timings = self.win.timings[self.key]
        path = timings.audio.with_suffix(".json")
        try:
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError:
            self.hint.setText(self.win.t("timing.not_saved"))
            self.state = READY
            return
        fresh = Timings.load(path)
        if fresh is not None:
            self.win.timings[self.key] = fresh
        missed = len(self.session.words) - len(self.session.starts)
        self.state = CHECKING
        self.message = self.win.t("timing.saved_missed" if missed > 0 else "timing.saved", n=missed)
        self.hint.setText(self.message)
        fresh = self.win.timings[self.key]
        self.win.recitation.play(fresh.audio, Span(0.0, fresh.segments[-1].end + 0.3))
        self.follow.start()

    def tick(self) -> None:
        position = self.win.recitation.position()
        if self.state == TAPPING:
            if position is None and not self.win.recitation.busy:
                self.finish()                     # the recording ran out
            return
        if self.state == CHECKING:
            if position is None and not self.win.recitation.busy:
                self.follow.stop()
                self.words.set_highlight(None)
                return
            timings = self.win.timings[self.key]
            lit = None
            for li in range(len(timings.segments)):
                wi = timings.word_at(li, position) if position is not None else None
                if wi is not None:
                    lit = (li, wi)
                    break
            self.words.set_highlight(lit)

    # -- the ring ------------------------------------------------------------------------------

    def mousePressEvent(self, e):
        """A tap on the screen works like the ring: the left third is back, the rest forward."""
        self.win.timing_press("back" if e.position().x() < self.width() / 3 else "next")

    def press(self, forward: bool) -> None:
        """Forward: start, tap, or (once checked) on to the next recording.
        Back: to the previous recording, or tap this one again."""
        if self.state == READY:
            self.start() if forward else self.go(-1)
        elif self.state == TAPPING:
            if not forward:
                self.win.recitation.stop()
                self.start()
                return
            position = self.win.recitation.position()
            if position is None:
                return
            self.session.tap(position)
            if self.session.complete:
                self.finish()
            else:
                self.words.set_highlight(self.session.next_word)
        elif self.state == CHECKING:
            if forward:
                self.go(1)
            else:
                self.win.recitation.stop()
                self.start()
