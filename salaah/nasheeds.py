"""Nasheeds: a list of recordings, and a player that plays one at a time.

WHERE THE RECORDINGS COME FROM, which is the whole design of this.

Nothing ships with the mat. A nasheed is a recording somebody made and owns, and the artists
worth listening to -- Zain Bhikha, Dawud Wharnsby, Maher Zain -- are on labels. The sites that
offer "copyright free" collections of them are aggregators who do not hold the rights, and the
compilations on archive.org are the same material with the uploader's name on it. Putting any
of that on a device would be Phantom Interactive distributing somebody else's record.

So the mat is a PLAYER, not a library. It reads whatever is in the owner's own folder:

    ~/.salaah/nasheeds/

which is where the recitation cache already lives, and which no release ever touches. Drop mp3s
in, they appear; take them out, they go. The family's own copies, their own recordings, or
something properly licensed -- the mat does not care and does not need to.

assets/nasheeds/ is read too, for anything that is one day licensed to ship with the mat. It is
empty, and the test suite checks that it stays empty of audio until a licence file sits beside
it saying what may be there and under what terms. That check exists because "we will sort the
licence out later" is exactly how an mp3 ends up in a release.

A TITLE comes from the file name, tidied. A nasheeds.json beside the files can give a better
one, with the artist and the licence, and that is the file a shipped set would have to fill in.

THE PLAYER is audio.Call -- the one that plays a file beginning to end and stops, which is what
the call to prayer uses. Not Recitation, which plays a span and can repeat it for following
words on a screen. A nasheed is a whole recording listened to, so it wants the simple one, and
having its own instance means the prayer machinery cannot cut it off by accident. The call to
prayer cuts it off ON PURPOSE -- see ui.py, where a prayer falling due stops whatever is
playing before the muezzin starts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .audio import Call
from .qt import QtCore, QtWidgets, Qt, Signal

# What counts as a recording. Kept narrow on purpose: the folder is one a person drops files
# into, and a stray cover.jpg or .DS_Store should not become a row with a play button on it.
SOUNDS = (".mp3", ".m4a", ".ogg", ".wav", ".opus", ".flac")

# The owner's own folder. Beside the recitation cache, because it is the same kind of thing --
# audio that belongs to this mat and this family, and that no update may overwrite or ship.
MINE = Path.home() / ".salaah" / "nasheeds"


def tidy_name(stem: str) -> str:
    """A file name as something to read on a screen.

    "01_zain-bhikha_allah-knows.mp3" is how files arrive off a phone or a download, and a row
    reading that is a row nobody wants. Numbers at the front go, separators become spaces, and
    the words are left alone otherwise -- no title casing, because "Allahu Akbar" and "du'a"
    are not improved by a machine's idea of capitals.
    """
    said = re.sub(r"^\s*\d+\s*[-_.)]*\s*", "", stem)      # a leading track number
    said = re.sub(r"[_\-]+", " ", said).strip()
    said = re.sub(r"\s{2,}", " ", said)
    return said or stem


class Track:
    """One recording: where it is, what to call it, and who it belongs to."""

    def __init__(self, path: Path, title: str = "", artist: str = "", licence: str = ""):
        self.path = Path(path)
        self.title = title or tidy_name(self.path.stem)
        self.artist = artist
        self.licence = licence

    @property
    def said(self) -> str:
        return f"{self.title} · {self.artist}" if self.artist else self.title


class Nasheeds:
    """What is in the folders, read fresh each time the screen is opened.

    Fresh rather than cached, because the point of the owner's folder is that somebody can put
    a file in it and find it on the mat -- and they will do that while the mat is running, with
    a USB stick, not by restarting it.
    """

    def __init__(self, assets: Path, mine: Path | None = None):
        self.folders = [Path(assets) / "nasheeds", Path(mine) if mine is not None else MINE]

    def described(self, folder: Path) -> dict:
        """Titles and credits from nasheeds.json, if the folder has one."""
        try:
            raw = json.loads((folder / "nasheeds.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        out = {}
        for row in raw.get("tracks", []):
            if isinstance(row, dict) and row.get("file"):
                out[str(row["file"])] = row
        return out

    @property
    def tracks(self) -> list[Track]:
        found: list[Track] = []
        seen: set[str] = set()
        for folder in self.folders:
            if not folder.is_dir():
                continue
            said = self.described(folder)
            for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
                if not path.is_file() or path.suffix.lower() not in SOUNDS:
                    continue
                # A file of the same name in both folders is the owner's, not the shipped one:
                # their folder is read second and a name already taken is left alone... which
                # would be the wrong way round, so the shipped one is what gets skipped.
                if path.name.lower() in seen:
                    continue
                seen.add(path.name.lower())
                row = said.get(path.name, {})
                found.append(Track(path, str(row.get("title", "")),
                                   str(row.get("artist", "")), str(row.get("licence", ""))))
        return found


class NasheedScreen(QtWidgets.QWidget):
    """The list, with one playing at a time.

    No shuffle, no repeat, no queue. This is a shelf of recordings on a prayer mat, and a child
    picks one; the machinery of a music player would be more screen than the thing deserves.
    Pressing the one that is playing stops it, which is the whole of the control.
    """

    back = Signal()

    def __init__(self, window, nasheeds: Nasheeds):
        super().__init__()
        self.win = window
        self.nasheeds = nasheeds
        self.player = Call(volume=window.settings.volume)
        self.playing: Track | None = None
        self.rows_for: list[Track] = []
        self.setObjectName("nasheedScreen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(window.px(20), window.px(10), window.px(20), 0)
        self.title = QtWidgets.QLabel(window.t("corner.nasheeds"))
        self.title.setObjectName("namePlate")
        bar.addWidget(self.title)
        bar.addStretch(1)
        self.back_button = QtWidgets.QPushButton(window.t("corner.back"))
        self.back_button.setObjectName("backButton")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.leaving)
        bar.addWidget(self.back_button)
        outer.addLayout(bar)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")      # the wide, touchable slider
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        self.rows = QtWidgets.QVBoxLayout(inner)
        self.rows.setContentsMargins(window.px(20), window.px(10), window.px(20), window.px(20))
        self.rows.setSpacing(window.px(10))
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, 1)

        # An empty folder is the ordinary state of this screen on a new mat, so it says what to
        # do about it rather than showing nothing and looking broken.
        self.empty = QtWidgets.QLabel(window.t("nasheeds.empty", folder=str(MINE)))
        self.empty.setObjectName("soonText")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.empty, 1)

        # Watches for the end of a track, so the row stops saying it is playing when it is not.
        self.watch = QtCore.QTimer(self)
        self.watch.setInterval(400)
        self.watch.timeout.connect(self.look)

    # What is on the shelf

    def fill(self) -> None:
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()
        self.rows_for = self.nasheeds.tracks
        for track in self.rows_for:
            row = QtWidgets.QPushButton(track.said)
            row.setObjectName("nasheedRow")
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.setCheckable(True)
            row.clicked.connect(lambda _=False, t=track: self.touched(t))
            self.rows.addWidget(row)
        self.rows.addStretch(1)
        there = bool(self.rows_for)
        self.scroll.setVisible(there)
        self.empty.setVisible(not there)
        self.mark()

    def mark(self) -> None:
        """Show which row is playing, if any."""
        for i, track in enumerate(self.rows_for):
            row = self.rows.itemAt(i).widget()
            if row is not None:
                row.setChecked(track is self.playing)

    # Playing one

    def touched(self, track: Track) -> None:
        if track is self.playing:
            return self.stop()
        self.play(track)

    def play(self, track: Track) -> None:
        self.win.stir()
        self.player.volume = self.win.settings.volume
        self.playing = track if self.player.play(track.path) else None
        self.mark()
        if self.playing is not None:
            self.watch.start()

    def stop(self) -> None:
        self.player.stop()
        self.playing = None
        self.watch.stop()
        self.mark()

    def look(self) -> None:
        """The track ran out on its own. Let the row go back to normal."""
        if self.playing is not None and not self.player.playing:
            self.stop()

    @property
    def saying(self) -> bool:
        """Something is being listened to. The sleep timer asks this: going dark in the middle
        of a nasheed is the same rudeness as going dark in the middle of a du'a."""
        return self.player.playing

    def leaving(self) -> None:
        self.stop()
        self.back.emit()

    def retitle(self) -> None:
        self.title.setText(self.win.t("corner.nasheeds"))
        self.back_button.setText(self.win.t("corner.back"))
        self.empty.setText(self.win.t("nasheeds.empty", folder=str(MINE)))

    def showEvent(self, ev):
        self.fill()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Leaving the screen stops the sound. A nasheed playing on from behind the Qur'an is
        # not a feature anybody asked for, and there would be no way to stop it.
        self.stop()
        super().hideEvent(ev)
