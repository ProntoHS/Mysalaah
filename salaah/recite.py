"""Reciting the Qur'an on the mat: fetching the verses and knowing which word is being said.

The recordings are one file per verse, fetched from everyayah.com the first time a verse is
read and kept for good. Per verse rather than per surah for three reasons: Al-Baqarah as one
file is 120 MB and nobody waits for that, a verse is 143 KB so reciting starts at once, and the
word timings were measured against these very files -- timings made for one recording do not
fit another.

Nothing here draws or plays anything. It hands back a file on disk and, for a given moment in
that file, which word is sounding. reading.py decides what turns red.

The cache lives outside the app folder, in ~/.salaah, because an update replaces the app folder
wholesale and nobody wants to fetch a gigabyte of recitation again because the app went from
1.21 to 1.22.

Everything is forgiving about the network. A mat with no wifi shows the surah and says it cannot
recite; it does not refuse to open the text, and it never plays half a file.
"""
from __future__ import annotations

import json
import queue
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

RECITER = "Alafasy_128kbps"
BASE = "https://everyayah.com/data"

# One verse. The longest in this recitation is about two and a half minutes, which at 128 kbps
# is under 3 MB; the ceiling is well clear of that and still far from filling a card.
LEAST = 1024
MOST = 12 * 1024 * 1024
TIMEOUT = 20
TRIES = 2               # a verse is small: try twice, then give up and let the reader carry on
AHEAD = 3               # verses fetched in the background ahead of the one being recited


def headers() -> dict:
    """Say who we are. A mat quietly hammering somebody's CDN should at least be identifiable."""
    return {"User-Agent": f"Salaah/{__version__} (+https://github.com/ProntoHS/Mysalaah)",
            "Accept": "audio/mpeg, */*"}


def url_for(surah: int, verse: int, reciter: str = RECITER) -> str:
    return f"{BASE}/{reciter}/{surah:03d}{verse:03d}.mp3"


class Store:
    """Verse recordings on disk, and a background thread that goes and gets the missing ones."""

    def __init__(self, room: Path | None = None, reciter: str = RECITER,
                 opener=None, base: str = BASE):
        self.reciter = reciter
        self.base = base
        self.room = Path(room) if room else Path.home() / ".salaah" / "recitation"
        self.opener = opener or urllib.request.urlopen
        self._asked: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._failed: set[tuple[int, int]] = set()
        self.tried = 0                 # how many downloads have been attempted, for the tests

    # Where things are

    def path_for(self, surah: int, verse: int) -> Path:
        return self.room / self.reciter / f"{surah:03d}{verse:03d}.mp3"

    def url_for(self, surah: int, verse: int) -> str:
        return f"{self.base}/{self.reciter}/{surah:03d}{verse:03d}.mp3"

    def have(self, surah: int, verse: int) -> bool:
        path = self.path_for(surah, verse)
        try:
            return path.is_file() and path.stat().st_size >= LEAST
        except OSError:
            return False

    def gave_up_on(self, surah: int, verse: int) -> bool:
        """Asked for and could not be had. Stops the reader retrying the same verse forever."""
        with self._lock:
            return (surah, verse) in self._failed

    # Getting them

    def fetch(self, surah: int, verse: int) -> Path | None:
        """The file, fetching it if need be. Returns None rather than raising: a mat with no
        network shows the words and stays quiet."""
        if self.have(surah, verse):
            return self.path_for(surah, verse)
        path = self.path_for(surah, verse)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        # Written beside the real name and moved into place only once it is whole, so a
        # download cut off half way can never be played or mistaken for a good file.
        part = path.with_suffix(".part")
        for attempt in range(TRIES):
            self.tried += 1
            try:
                request = urllib.request.Request(self.url_for(surah, verse), headers=headers())
                with self.opener(request, timeout=TIMEOUT) as answer:
                    size = answer.headers.get("Content-Length")
                    if size and int(size) > MOST:
                        break                       # not a verse; do not start the download
                    with part.open("wb") as out:
                        got = shutil.copyfileobj(answer, out, 64 * 1024)  # noqa: F841
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
                part.unlink(missing_ok=True)
                if attempt + 1 >= TRIES:
                    break
                continue
            try:
                if not (LEAST <= part.stat().st_size <= MOST):
                    part.unlink(missing_ok=True)
                    break
                part.replace(path)
            except OSError:
                part.unlink(missing_ok=True)
                break
            return path
        with self._lock:
            self._failed.add((surah, verse))
        return None

    def want(self, wanted: list[tuple[int, int]]) -> None:
        """Ask for these in the background, nearest first. Ones already here are skipped."""
        for surah, verse in wanted[:AHEAD + 1]:
            if not self.have(surah, verse) and not self.gave_up_on(surah, verse):
                self._asked.put((surah, verse))
        self._wake()

    def _wake(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._work, daemon=True)
        self._worker.start()

    def _work(self) -> None:
        while True:
            try:
                surah, verse = self._asked.get_nowait()
            except queue.Empty:
                return
            try:
                self.fetch(surah, verse)
            except Exception:              # noqa: BLE001 -- a background thread must not die
                pass

    def settle(self, seconds: float = 20.0) -> None:
        """Wait for the background fetching to finish. For the tests, not for the mat."""
        worker = self._worker
        if worker is not None:
            worker.join(timeout=seconds)


class WordTimes:
    """When each word of a surah is recited, and which verses must glow whole instead.

    Twelve verses in the whole Qur'an are marked whole: quran-align counts words by splitting
    Tanzil's Uthmani text, our Arabic comes from quranenc, and where the two split a word
    differently the timings would light the wrong one. Those verses glow a verse at a time.
    tools/build_timings.py is what decides which, by counting.
    """

    def __init__(self, assets: Path):
        self.root = Path(assets) / "content" / "quran" / "timings"
        self._held: dict[int, dict] = {}

    @property
    def there(self) -> bool:
        return self.root.is_dir()

    def _surah(self, surah: int) -> dict:
        if surah not in self._held:
            try:
                raw = json.loads((self.root / f"{surah}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {"words": {}, "whole": []}
            if len(self._held) > 4:                 # a surah of timings is tens of kilobytes
                self._held.clear()
            self._held[surah] = raw
        return self._held[surah]

    def known(self, surah: int) -> bool:
        spot = self._surah(surah)
        return bool(spot.get("words")) or bool(spot.get("whole"))

    def whole_only(self, surah: int, verse: int) -> bool:
        """True when this verse must be highlighted a whole verse at a time."""
        return verse in self._surah(surah).get("whole", [])

    def words(self, surah: int, verse: int) -> list:
        return self._surah(surah).get("words", {}).get(str(verse), [])

    def word_at(self, surah: int, verse: int, seconds: float) -> int | None:
        """Which word is sounding at that moment, or None between words and after the last.

        A segment carries the range of words it covers, because in twenty-three places across
        the Qur'an two words could not be told apart. The first word of the range is lit; it is
        better to light the first of two than to light neither.
        """
        when = seconds * 1000.0
        for start_word, _end_word, start_ms, end_ms in self.words(surah, verse):
            if start_ms <= when < end_ms:
                return start_word
        return None

    def length(self, surah: int, verse: int) -> float:
        """How long the verse takes, in seconds, by its last word. 0 when not known."""
        words = self.words(surah, verse)
        return (words[-1][3] / 1000.0) if words else 0.0
