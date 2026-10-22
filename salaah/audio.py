"""Recitation audio, and the word timings that drive the red highlight.

Timings live in a JSON file next to the audio:

    {"schema": 1, "file": "fatiha.mp3", "reciter": "...", "estimated": true,
     "segments": [{"start": 1.59, "end": 4.99,
                   "words": [{"start": 1.59, "end": 2.2}, ...]}, ...]}

One segment per verse, in the same order as the Arabic in content/core/arabic.json, and one
word per space-separated word of that verse. `estimated` marks timings that were worked out
by arithmetic rather than by ear; tools/tap_timings.py replaces them with real ones.

Playback shells out to a player (ffplay, mpg123, cvlc or mpv), so no extra Python packages are
needed and nothing is required at all on machines with no sound. Position is tracked with the
clock rather than asked of the player, which is accurate enough for highlighting words and
keeps every player interchangeable.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 1

MIN_VOLUME = 0
MAX_VOLUME = 100


def clamp_volume(value: int) -> int:
    return max(MIN_VOLUME, min(MAX_VOLUME, int(value)))


# player -> how to say "play FILE from START for LENGTH seconds at volume V, without a window"
PLAYERS = {
    "ffplay": lambda f, s, d, v: ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                                  "-volume", str(v),
                                  "-ss", f"{s:.3f}", "-t", f"{d:.3f}", str(f)],
    "mpv": lambda f, s, d, v: ["mpv", "--no-video", "--really-quiet", f"--volume={v}",
                               f"--start={s:.3f}", f"--length={d:.3f}", str(f)],
    "mpg123": lambda f, s, d, v: ["mpg123", "-q", "-f", str(int(32768 * (v / 100) ** 2)),
                                  "-k", str(int(s * 38.28)),
                                  "-n", str(int(d * 38.28)), str(f)],
    "cvlc": lambda f, s, d, v: ["cvlc", "--intf", "dummy", "--quiet", "--play-and-exit",
                                f"--gain={v / 100:.2f}",
                                f"--start-time={s:.3f}", f"--stop-time={s + d:.3f}", str(f)],
}


def find_player() -> str | None:
    for name in PLAYERS:
        if shutil.which(name):
            return name
    return None


@dataclass(frozen=True)
class Span:
    start: float
    end: float

    def holds(self, t: float) -> bool:
        return self.start <= t < self.end


@dataclass
class Timings:
    audio: Path
    segments: list[Span]
    words: list[list[Span]]
    estimated: bool = True
    reciter: str = ""

    @staticmethod
    def load(path: Path) -> "Timings | None":
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if d.get("schema") != SCHEMA:
            return None
        segments, words = [], []
        for seg in d.get("segments", []):
            segments.append(Span(float(seg["start"]), float(seg["end"])))
            words.append([Span(float(w["start"]), float(w["end"])) for w in seg.get("words", [])])
        if not segments:
            return None
        return Timings(path.parent / d["file"], segments, words,
                       bool(d.get("estimated", True)), d.get("reciter", ""))

    def span_for(self, first: int, last: int) -> Span | None:
        """One span covering segments [first..last], which is what a screenful holds."""
        if first < 0 or last >= len(self.segments) or first > last:
            return None
        return Span(self.segments[first].start, self.segments[last].end)

    def word_at(self, segment: int, t: float) -> int | None:
        """Which word of this verse is being recited at time [t], if any."""
        if not (0 <= segment < len(self.words)):
            return None
        for i, span in enumerate(self.words[segment]):
            if span.holds(t):
                return i
        return None


REST = 0.5   # seconds of quiet between one saying and the next, when a phrase is repeated


class Recitation:
    """Plays part of a file and reports how far through it is.

    A phrase said more than once (X3 in ruku and sujood, X2 for the salam) is played that many
    times, with a short breath between, and the position starts again from the top each time so
    the red highlight follows every saying."""

    def __init__(self, player: str | None = None, volume: int = 80):
        self.player = player or find_player()
        self.volume = clamp_volume(volume)
        self._process: subprocess.Popen | None = None
        self._started = 0.0
        self._span: Span | None = None
        self._audio: Path | None = None
        self._times_left = 0              # repeats still to come after this one
        self._resting_since: float | None = None

    @property
    def available(self) -> bool:
        return self.player is not None

    @property
    def playing(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def busy(self) -> bool:
        """Playing, or between two sayings of a repeated phrase."""
        return self.playing or (self._span is not None and self._times_left > 0)

    def set_volume(self, volume: int) -> None:
        """The volume is handed to the player as it starts, so a change part way through a
        recitation takes effect on the next screen rather than straight away."""
        self.volume = clamp_volume(volume)

    def play(self, audio: Path, span: Span, times: int = 1) -> bool:
        self.stop()
        if not self.available or not audio.is_file() or span.end <= span.start:
            return False
        if self.volume <= MIN_VOLUME:       # turned all the way down is silence, not quiet
            return False
        self._audio = audio
        self._times_left = max(1, int(times)) - 1
        return self._start(span)

    def _start(self, span: Span) -> bool:
        command = PLAYERS[self.player](self._audio, span.start, span.end - span.start, self.volume)
        try:
            self._process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except OSError:
            self._process = None
            self._span = None
            self._times_left = 0
            return False
        self._started = time.monotonic()
        self._span = span
        self._resting_since = None
        return True

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._span = None
        self._times_left = 0
        self._resting_since = None

    def position(self) -> float | None:
        """Where we are in the audio file, in seconds, or None when nothing is sounding: the
        recitation has finished, or it is the breath between two sayings. Call it often; it is
        also what starts the next saying of a repeated phrase once the breath is over."""
        if self._span is None:
            return None
        if self.playing:
            return self._span.start + (time.monotonic() - self._started)
        if self._times_left <= 0:
            return None
        now = time.monotonic()
        if self._resting_since is None:
            self._resting_since = now
        if now - self._resting_since < REST:
            return None
        self._times_left -= 1
        if not self._start(self._span):
            return None
        return self._span.start


# Longer than any call to prayer. Every player stops at the end of the file regardless, so this
# only has to be an upper bound -- it saves asking the file how long it is, which would mean
# depending on a tool that may not be installed.
WHOLE = 3600.0


# player -> how to say "play this URL, from wherever it is now, at volume V, no window".
#
# A live stream is the same players and a shorter command: there is no seeking to a position
# in something that has no beginning, and no length to stop after. Every one of these takes a
# URL exactly where it takes a path, which is why the radio needed no new dependency -- the
# mat already shells out to whichever of them the Pi has.
#
# mpg123 is last and only half here: it plays an mp3 stream and cannot play AAC or HLS, which
# a good many stations use. The other three can, so a mat with any of them installed should
# use those; find_streamer prefers them for that reason and nothing else.
STREAMERS = {
    "ffplay": lambda u, v: ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                            "-volume", str(v), str(u)],
    "mpv": lambda u, v: ["mpv", "--no-video", "--really-quiet", f"--volume={v}", str(u)],
    "cvlc": lambda u, v: ["cvlc", "--intf", "dummy", "--quiet", "--play-and-exit",
                          f"--gain={v / 100:.2f}", str(u)],
    "mpg123": lambda u, v: ["mpg123", "-q", "-f", str(int(32768 * (v / 100) ** 2)), str(u)],
}


def find_streamer() -> str | None:
    for name in STREAMERS:
        if shutil.which(name):
            return name
    return None


class Call:
    """Plays a file from beginning to end, once. The call to prayer.

    Separate from Recitation on purpose. That one plays a span of a file and can repeat it,
    which is what following words on a screen needs; this plays the lot and stops. Keeping them
    apart means the call cannot be cut short by the prayer machinery, or cut it short.
    """

    def __init__(self, player: str | None = None, volume: int = 80):
        self.player = player or find_player()
        self.volume = clamp_volume(volume)
        self._process: subprocess.Popen | None = None
        self._started: float | None = None

    @property
    def available(self) -> bool:
        return self.player is not None

    @property
    def playing(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def play(self, audio: Path) -> bool:
        """True if sound is on its way. False for every reason it might not be -- no player, no
        file, turned right down -- because none of those is worth an error on a prayer mat."""
        self.stop()
        if not self.available or not Path(audio).is_file():
            return False
        if self.volume <= MIN_VOLUME:
            return False
        command = PLAYERS[self.player](Path(audio), 0.0, WHOLE, self.volume)
        try:
            self._process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except OSError:
            self._process = None
            return False
        self._started = time.monotonic()
        return True

    def position(self) -> float | None:
        """How far into the call we are, in seconds, or None when nothing is sounding.

        A clock started when the player was launched, not a question put to the player -- the
        players this runs on (mpg123 and its like) are told to play a file and say nothing back.
        It is right to within however long the player takes to open the file, which is the same
        way the recitation follows the words on the Qur'an screen.
        """
        if self._started is None or not self.playing:
            return None
        return time.monotonic() - self._started

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._started = None


class Stream:
    """Plays a live stream, and keeps playing until it is stopped.

    The radio. Its own class rather than a flag on Call, because the two differ in the one
    way that matters to everything around them: a call ends, and a station does not. Call is
    watched for the moment it finishes so the notice can close itself; a station finishing is
    not the end of anything, it is a fault -- the network dropped, or the station went off --
    and the screen says so rather than quietly going back to how it looked before.

    SETTLE is how that is told apart. A player handed a URL it cannot use dies at once; one
    that is playing stays up. So a station still sounding a couple of seconds later is a
    station that answered, and one that is not never did. It is a crude test and it is the
    right one here: the alternative is parsing four players' error output, which differs
    between them and between versions, to learn something the exit tells us for nothing.
    """

    SETTLE = 2.5        # seconds; a stream still going after this answered

    def __init__(self, player: str | None = None, volume: int = 80):
        self.player = player or find_streamer()
        self.volume = clamp_volume(volume)
        self._process: subprocess.Popen | None = None
        self._started: float | None = None
        self.url = ""

    @property
    def available(self) -> bool:
        return self.player is not None

    @property
    def playing(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def play(self, url: str) -> bool:
        """True if the player started. Whether the STATION answered is answered() below --
        it cannot be known yet, and a prayer mat should not freeze for two seconds to find
        out."""
        self.stop()
        if not self.available or not str(url).strip():
            return False
        if self.volume <= MIN_VOLUME:
            return False
        try:
            self._process = subprocess.Popen(
                STREAMERS[self.player](str(url).strip(), self.volume),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL)
        except OSError:
            self._process = None
            return False
        self._started = time.monotonic()
        self.url = str(url).strip()
        return True

    def settling(self) -> bool:
        """Still within the moment where "not playing" might just mean "not started yet"."""
        return (self._started is not None
                and time.monotonic() - self._started < self.SETTLE)

    def answered(self) -> bool | None:
        """True once a station has been sounding long enough to count, False once the player
        has given up, and None while it is too early to say."""
        if self._started is None:
            return None
        if self.playing:
            return True if not self.settling() else None
        return False

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._started = None
        self.url = ""
