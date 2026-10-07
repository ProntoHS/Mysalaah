"""Drives the real screens without a display and saves screenshots to /tmp/salaah-shots."""
import json
import os
import sys
import tempfile
import time
import urllib.request
import unittest
from unittest import mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace  # noqa: E402
from salaah.content import PRAYERS, Translation, available_packs, load  # noqa: E402
from salaah.filmsheet import FilmSheet  # noqa: E402
from salaah.qt import API, QtCore, QtGui, QtWidgets, Qt  # noqa: E402
from salaah.render import MIN_ARABIC_PX  # noqa: E402
from salaah.settings import Settings  # noqa: E402
from salaah.ui import MainWindow  # noqa: E402

# No test goes on the internet. The verse recitation fetches from everyayah.com, and a test
# that quietly dials out is slow, flaky, rude to somebody else's CDN, and -- when it prefetches
# past the files a test laid down -- waits twenty seconds per verse for a connection that is
# never coming. Anything that tries gets an instant refusal instead.
def _offline(*_a, **_k):
    raise OSError("the tests do not go on the internet")


urllib.request.urlopen = _offline

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SHOTS = Path("/tmp/salaah-shots") / API
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
CONTENT = load(ASSETS)
CONTENT_ARABIC = CONTENT.arabic

# "Arabic only" is a pack so that the mat can reach Harry's Arabic menu drawings and lay itself
# out right to left, but it is a deliberately partial one -- the menu headings and nothing else.
# See the note in test_core.py. "Every language the mat speaks" means the six it is WRITTEN in.
WRITTEN_IN = ("en", "fr", "es", "ur", "hi", "zh")
ARABIC_ONLY = "ar"


def full_packs(packs: dict) -> dict:
    return {lang: pack for lang, pack in packs.items() if lang != ARABIC_ONLY}


def shut(w):
    """Close a window and the 7in screen that belongs to it.

    The 7in is a top-level window in its own right with no Qt parent, so w.deleteLater() does
    not reach it and it outlives the test. One per test is 23MB, and the suite creates sixty-odd
    -- which is what was getting the run killed for running out of memory rather than failing.
    The app itself makes one and keeps it, so this is the tests' problem and not the mat's.
    """
    w.shutdown()
    side = getattr(w, "side", None)
    if side is not None:
        side.close()
        side.deleteLater()
    w.close()
    w.deleteLater()
    settle()



def rows_of(tiles):
    """Group tiles into rows. By a band rather than by an exact y, because the boxes of an
    animated sheet are measured off the drawing and a hand-drawn row is not to the pixel."""
    tall = min(t.geometry().height() for t in tiles)
    rows, row = [], []
    for tile in sorted(tiles, key=lambda t: t.geometry().y()):
        if row and tile.geometry().y() - row[0].geometry().y() > tall * 0.5:
            rows.append(row)
            row = []
        row.append(tile)
    rows.append(row)
    return [sorted(r, key=lambda t: t.geometry().x()) for r in rows]

def settle(rounds=5):
    """Let queued work finish before looking at pixels.

    Several things are scheduled with singleShot(0) -- the restyle above all -- and one
    processEvents() does not reliably run them. Grabbing the screen before the restyle has
    happened catches a frame with the previous theme still on it, which is why the theme tests
    failed about one run in five while being perfectly correct about what they asked.
    """
    for _ in range(rounds):
        APP.processEvents()
        APP.sendPostedEvents()
    # And actually deliver the deletes. deleteLater() only posts a DeferredDelete event, which
    # plain processEvents() does not deliver, so every window a test closed stayed in memory --
    # about 25 MB each. Harmless while the suite was small; it grew until the run was killed for
    # running out of memory, which looks like a hang and is not one.
    APP.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def pace(win):
    """Clears the double-click timer, so the next press counts as a fresh, unhurried click."""
    win.last_click = None


def key(win, k):
    for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtWidgets.QApplication.sendEvent(win, QtGui.QKeyEvent(t, k, Qt.KeyboardModifier.NoModifier))


class UiTest(unittest.TestCase):
    def setUp(self):
        SHOTS.mkdir(parents=True, exist_ok=True)
        self.win = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(theme="light", recitation=False), scale=1.0, save_settings=False)
        self.win.resize(1920, 1080)
        self.win.show()
        APP.processEvents()
        # In through the front door, as a person does. The mat opens on the MySalaah screen
        # now, so without this the mosque behind it is never shown and never laid out -- and a
        # test measuring where the banner sits reads the same number for everything.
        self.win.leave_welcome()
        self.win.veil.stop()           # the walk is a picture over the top; not what is tested
        APP.processEvents()
        self.win.debouncer.window = 0  # tests press faster than a person

    def tearDown(self):
        self.win.shutdown()
        self.win.close()
        self.win.deleteLater()
        APP.processEvents()

    def shot(self, name):
        APP.processEvents()
        self.win.grab().save(str(SHOTS / f"{name}.png"))

    def test_text_pages_and_postures(self):
        w = self.win
        w.start("fajr", w.school.prayers["fajr"][0])
        page = w.current_page
        self.assertTrue(page.arabic, "Arabic text is shown")
        for p in w.text_pages:
            self.assertTrue((w.assets / p.posture_image).is_file(), p.posture_image)
        # a whole surah sits on one screen, so the recitation can play without the page turning
        fatiha = [p for p in w.text_pages if p.step.recitation == "fatiha"]
        self.assertEqual(1, fatiha[0].pages_in_step, "Al-Fatiha is one screen")
        self.assertEqual(len(CONTENT_ARABIC["fatiha"]), len(fatiha[0].arabic))
        self.assertEqual(1, fatiha[0].rakat)
        self.assertEqual(len(w.session.pages), len(w.text_pages))

    def test_leaving_mid_prayer(self):
        w = self.win
        w.start("dhuhr", w.school.prayers["dhuhr"][0])
        for _ in range(4):
            w.last_click = None      # a click at a normal pace
            w.move("next")
        self.assertFalse(w.slide.ask.isVisible())
        self.assertEqual(4, w.session.position)

        w.last_click = None
        w.move("next")
        w.move("next")               # two quick clicks
        self.assertTrue(w.slide.ask.isVisible())
        self.assertEqual(4, w.session.position, "place is kept")

        w.last_click = None          # a pause, then a click
        w.move("next")
        self.assertFalse(w.slide.ask.isVisible())
        self.assertTrue(w.playing)

        w.last_click = None
        w.move("next")
        w.move("next")               # two quick clicks ask again
        self.assertTrue(w.slide.ask.isVisible())
        w.move("next")               # one more quick click confirms
        self.assertFalse(w.playing)

    def test_back_on_first_page_leaves(self):
        w = self.win
        w.start("asr", w.school.prayers["asr"][0])
        w.move("back")
        self.assertFalse(w.playing)

    def test_full_prayer_with_keys_and_taps(self):
        w = self.win
        self.shot("1-home")
        w.open_prayer("maghrib")
        self.shot("2-maghrib")
        entry = w.school.prayers["maghrib"][0]
        w.start("maghrib", entry)
        self.assertTrue(w.playing)
        self.assertEqual("Rakat 1 of 3", w.rakat_label.text())
        self.shot("3-player-start")

        key(w, Qt.Key.Key_VolumeUp)          # the ring / shutter
        self.assertEqual(1, w.session.position)
        key(w, Qt.Key.Key_VolumeDown)
        self.assertEqual(0, w.session.position)

        pace(w)
        w.slide.tapped.emit("next")          # tap on the screen
        self.assertEqual(1, w.session.position)
        pace(w)
        w.on_button("next")                   # Bluetooth reader
        self.assertEqual(2, w.session.position)

        while w.session.current.rakat < 3:
            pace(w)
            key(w, Qt.Key.Key_Return)
        self.assertEqual("Rakat 3 of 3", w.rakat_label.text())
        self.shot("4-player-rakat3")
        w.settings.brightness = 60
        w.slide.set_dim(40)
        self.shot("5-player-dimmed")
        w.slide.set_dim(0)
        while not w.session.finished:
            pace(w)
            key(w, Qt.Key.Key_VolumeUp)
        # Maghrib's first unit is the fardh, so it ends on the counted dhikr
        self.assertEqual("farz", entry.kind)
        self.assertTrue(w.slide.tasbih.isVisible())
        self.assertFalse(w.slide.done.isVisible(), "no daily passage after a fardh prayer")
        self.shot("6-complete")
        key(w, Qt.Key.Key_Escape)
        self.assertFalse(w.playing)

    def test_the_intention_names_the_prayer_chosen(self):
        from salaah.render import Fonts
        w = self.win
        for prayer, kind, words in (("fajr", "sunnah", "I intend to perform 2 Rakats Sunnah of Fajr"),
                                    ("maghrib", "farz", "I intend to perform 3 Rakats Fardh of Maghrib"),
                                    ("isha", "witr", "I intend to perform 3 Rakats Witr of Isha"),
                                    ("dhuhr", "farz", "I intend to perform 4 Rakats Fardh of Dhuhr")):
            entry = next(e for e in w.school.prayers[prayer] if e.kind == kind)
            w.start(prayer, entry)
            APP.processEvents()
            self.assertEqual([words], w.slide.arabic.lines)
            self.assertEqual(Fonts.english_family, w.slide.arabic.family)
            self.assertFalse(w.slide.arabic.rtl)
            self.assertTrue(str(w.slide.posture.path).endswith("standing_arms_down.png"))
            if prayer == "fajr":
                self.shot("16-intention")
            pace(w)
            w.move("next")
            self.assertEqual(["ٱللَّهُ أَكۡبَرُ"], w.slide.arabic.lines, "then the takbir")
            self.assertTrue(w.slide.arabic.rtl)
            w.stop()

    def test_arabic_font_choice(self):
        from salaah.render import FONTS, Fonts
        w = self.win
        self.assertIn("scheherazade", Fonts.families, "the default face is bundled")
        w.start("fajr", w.school.prayers["fajr"][0])
        pace(w)
        w.move("next")                        # past the intention, which is in English
        self.assertEqual(Fonts.arabic("scheherazade"), w.slide.arabic.family)
        self.assertEqual(700, w.slide.arabic.weight, "Arabic is bold")
        for key in FONTS:
            if key in Fonts.families:
                w.set_font(key)
                self.assertEqual(Fonts.arabic(key), w.slide.arabic.family)

    def test_picture_is_on_the_left(self):
        w = self.win
        w.start("fajr", w.school.prayers["fajr"][0])
        APP.processEvents()
        self.assertLess(w.slide.posture.x(), w.slide.arabic.x(), "posture sits left of the words")
        # tapping the picture side still goes back, the words side forward
        self.assertEqual(0, w.session.position)
        pace(w)
        w.slide.tapped.emit("next")
        self.assertEqual(1, w.session.position)

    def test_standing_fills_the_frame_and_seated_figures_are_shorter(self):
        w = self.win
        w.start("maghrib", w.school.prayers["maghrib"][0])
        APP.processEvents()
        view = w.slide.posture
        inner = view.inner()

        def drawn(name):
            view.set_image(w.assets / "postures" / f"{name}.png")
            pix = w.images.get(view.path, view.target())
            return pix.width(), pix.height()

        standing_w, standing_h = drawn("standing_folded")
        # A standing figure fills the frame: whichever way round, it reaches an edge.
        self.assertTrue(standing_w >= inner.width() - 2 or standing_h >= inner.height() - 2,
                        f"standing fills the frame ({standing_w}x{standing_h} in {inner})")
        for name in ("ruku", "sujood", "jalsa", "tashahhud", "salam_right"):
            wide, high = drawn(name)
            self.assertLess(high, standing_h, f"{name} is shorter than standing")
            self.assertLessEqual(wide, inner.width() + 1, f"{name} fits the frame width")

    def test_drawing_area_keeps_its_shape(self):
        from salaah.content import available_packs, load
        from salaah.settings import Settings as S
        for size, inset in (((1920, 1080), 0), ((1280, 1024), 0), ((1920, 1200), 0), ((1920, 1080), 40)):
            win = MainWindow(load(ASSETS), available_packs(ASSETS), S(theme="light", recitation=False), 1.0, False, inset=inset)
            win.resize(*size)
            win.show()
            APP.processEvents()
            box = win.content_box()
            self.assertAlmostEqual(16 / 9, box.width() / box.height(), places=2, msg=str(size))
            self.assertLessEqual(box.bottom(), size[1] - inset, "nothing runs off the bottom")
            self.assertLessEqual(box.right(), size[0] - inset, "nothing runs off the side")
            self.assertEqual(box, win.stack.geometry())
            win.shutdown()
            win.close()

    def test_arabic_fills_its_space(self):
        w = self.win
        w.start("maghrib", w.school.prayers["maghrib"][0])
        APP.processEvents()
        box = w.slide.arabic
        self.assertGreater(box.height(), w.slide.height() * 0.8, "the words take the whole column")

        used = []
        for i, page in enumerate(w.text_pages):
            w.session.position = i
            w.refresh()
            APP.processEvents()
            box.set_lines(page.arabic)
            h = box.measure(page.arabic, box.fitted_size())
            self.assertLessEqual(h, box.height(), f"page {i} overflows")
            used.append(h / box.height())
        self.assertGreater(max(used), 0.8, "at least some pages use nearly the whole box")
        self.assertGreater(sum(used) / len(used), 0.55, "little dead space on average")

    def test_each_surah_plays_its_own_recording(self):
        import unittest.mock as mock
        w = self.win
        w.settings.recitation = True
        played = []
        with mock.patch.object(type(w.recitation), "available", property(lambda s: True)), \
             mock.patch.object(type(w.recitation), "play",
                               lambda s, audio, span, times=1: (played.append((audio.stem, span)), True)[1]):
            w.start("fajr", w.school.prayers["fajr"][0])
            APP.processEvents()
            for i in range(len(w.text_pages)):
                w.session.position = i
                w.refresh()
                APP.processEvents()
        names = [n for n, _ in played]
        self.assertIn("fatiha", names)
        self.assertIn("kawthar", names, "the surah after the Fatiha plays too")
        self.assertIn("ikhlas", names)
        for name, span in played:
            timings = w.timings[name]
            self.assertAlmostEqual(timings.segments[0].start, span.start, places=2, msg=name)
            self.assertAlmostEqual(timings.segments[-1].end, span.end, places=2, msg=name)

    def test_recitation_plays_only_the_verses_on_screen(self):
        import unittest.mock as mock
        w = self.win
        w.settings.recitation = True
        played = []
        with mock.patch.object(type(w.recitation), "available", property(lambda s: True)), \
             mock.patch.object(type(w.recitation), "play",
                               lambda s, audio, span, times=1: (played.append(span), True)[1]):
            w.start("fajr", w.school.prayers["fajr"][0])
            APP.processEvents()
            page = next(p for p in w.text_pages if p.recitation == "fatiha")
            w.session.position = w.text_pages.index(page)
            w.refresh()
            APP.processEvents()
        self.assertTrue(played, "audio started for the Fatiha page")
        timings = w.timings["fatiha"]
        last = page.first_segment + len(page.arabic) - 1
        self.assertAlmostEqual(timings.segments[page.first_segment].start, played[-1].start, places=2)
        self.assertAlmostEqual(timings.segments[last].end, played[-1].end, places=2)

    def test_highlight_follows_the_words(self):
        import unittest.mock as mock
        w = self.win
        w.settings.recitation = True
        w.start("fajr", w.school.prayers["fajr"][0])
        APP.processEvents()
        page = next(p for p in w.text_pages if p.recitation == "fatiha")
        w.session.position = w.text_pages.index(page)
        w.refresh()
        APP.processEvents()
        timings = w.timings["fatiha"]
        seen = []
        for line in range(len(page.arabic)):
            for word_index, span in enumerate(timings.words[page.first_segment + line]):
                middle = (span.start + span.end) / 2
                with mock.patch.object(type(w.recitation), "available", property(lambda s: True)), \
                     mock.patch.object(type(w.recitation), "position", lambda s, t=middle: t):
                    w.follow_audio()
                seen.append(w.slide.arabic.highlight)
                self.assertEqual((line, word_index), w.slide.arabic.highlight)
        self.assertEqual(len(seen), len(set(seen)), "every word lights up once")

    def test_audio_is_off_by_default_and_stops_with_the_prayer(self):
        w = self.win
        self.assertFalse(w.settings.recitation)
        w.start("fajr", w.school.prayers["fajr"][0])
        APP.processEvents()
        self.assertFalse(w.follow.isActive(), "nothing plays unless it is switched on")
        w.settings.recitation = True
        w.stop()
        self.assertFalse(w.follow.isActive())
        self.assertIsNone(w.slide.arabic.highlight)

    def test_mosque_arches_start_their_prayer(self):
        from salaah.qt import QtCore
        w = self.win
        APP.processEvents()
        self.assertTrue(w.mosque.ready, "the mosque picture loaded")
        self.assertEqual({"fajr", "dhuhr", "asr", "maghrib", "isha"},
                         {a.prayer for a in w.mosque.arches})
        self.shot("8-mosque")

        _, origin, scale = w.mosque.placement()
        for arch in w.mosque.arches:
            middle = QtCore.QPoint(origin.x() + int((arch.box.x() + arch.box.width() / 2) * scale),
                                   origin.y() + int((arch.box.y() + arch.box.height() / 2) * scale))
            self.assertEqual(arch.prayer, w.mosque.arch_at(middle))
        # tapping above the arches, on the dome, chooses nothing
        self.assertIsNone(w.mosque.arch_at(QtCore.QPoint(w.mosque.width() // 2, 10)))

        w.open_prayer("asr")
        self.assertIs(w.pick, w.stack.currentWidget(), "it opens that prayer")

    def test_choice_screen_draws_an_arch_per_unit(self):
        from salaah.mosque import ArchButton
        w = self.win
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)
        for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
            w.open_prayer(prayer)
            APP.processEvents()
            arches = w.pick.findChildren(ArchButton)
            entries = w.school.prayers[prayer]
            self.assertEqual(len(entries), len(arches), prayer)
            for arch, entry in zip(arches, entries):
                unit = w.content.units[entry.unit_id]
                self.assertEqual(str(unit.rakats), arch.count, f"{prayer}/{entry.unit_id}")
                self.assertEqual(w.t(f"kind.{entry.kind}"), arch.label)
                box = arch.arch_rect()
                self.assertLessEqual(box.bottom(), arch.height(), "the base is not clipped")
                self.assertGreater(box.height(), 50, f"{prayer}: the arches are a decent size")
        self.shot("9-arches")

    def test_repeat_count_is_a_circle_inside_the_picture_top_right(self):
        w = self.win
        w.start("maghrib", w.school.prayers["maghrib"][0])
        APP.processEvents()
        self.assertFalse(hasattr(w, "repeat_label"), "the count is off the banner")
        badge = w.slide.repeat_badge
        for recitation, expected in (("ruku_tasbih", 3), ("sujood_tasbih", 3),
                                     ("salam", 2), ("fatiha", 1)):
            i = next(n for n, p in enumerate(w.text_pages) if p.step.recitation == recitation)
            w.session.position = i
            w.refresh()
            APP.processEvents()
            self.assertEqual(expected, badge.count, recitation)

        posture = w.slide.posture
        self.assertIs(badge.parent(), posture, "the circle rides in the picture frame")
        self.assertEqual(badge.width(), badge.height(), "always a circle")
        self.assertGreater(badge.width(), 40, "big enough to read from standing")
        frame = posture.rect()
        spot = badge.geometry()
        self.assertTrue(frame.contains(spot), "wholly inside the frame")
        self.assertGreater(spot.center().x(), frame.center().x(), "to the right")
        self.assertLess(spot.center().y(), frame.center().y(), "at the top")
        self.shot("11-repeat-badge")

    def test_volume_bar_sits_in_the_top_bar_and_saves_what_it_is_set_to(self):
        w = self.win
        w.start("maghrib", w.school.prayers["maghrib"][0])
        APP.processEvents()
        bar = w.slide.volume
        self.assertTrue(bar.isVisible(), "the volume is there as soon as the prayer starts")
        self.assertEqual(0, bar.volume, "silent while the recitation is switched off")
        w.set_recitation("1")
        self.assertEqual(w.settings.volume, bar.volume, "and shows the level once it is on")

        # a rectangle lying down, in the top bar, over on the right. The rakat used to sit
        # beside it and has moved to the left, next to the prayer it belongs to.
        self.assertIs(w.bar, bar.parentWidget(), "the volume sits in the top bar")
        self.assertGreater(bar.width(), bar.height() * 2, "a rectangle, lying down")
        in_window = bar.mapTo(w, bar.rect().center())
        self.assertLess(in_window.y(), w.slide.mapTo(w, QtCore.QPoint(0, 0)).y(),
                        "above the prayer screen, not on it")
        self.assertGreater(in_window.x(), w.width() / 2, "on the right of the banner")
        self.assertGreater(bar.mapTo(w, bar.rect().topLeft()).x(),
                           w.rakat_label.mapTo(w, w.rakat_label.rect().topRight()).x(),
                           "and clear of the rakat, which is now on the left")

        # dragging it sets the volume, keeps it, and tells the player
        track = bar.track()
        bar._set_from_x(track.x() + track.width() * 0.5)
        self.assertEqual(50, bar.volume)
        self.assertEqual(50, w.settings.volume)
        self.assertEqual(50, w.recitation.volume)
        self.assertTrue(w.settings.recitation)

        bar.set_volume(0, tell=True)
        self.assertFalse(w.settings.recitation, "all the way down switches it off")
        self.assertEqual(50, w.settings.volume, "and keeps the level to come back to")

        bar._set_from_x(track.right() + 50)
        self.assertEqual(100, bar.volume, "past the end is full volume")
        self.assertTrue(w.settings.recitation, "turning it up switches it back on")
        self.shot("12-volume-bar")

    def finish(self, prayer: str, kind: str):
        """Plays a unit of this kind to the end and returns the window."""
        w = self.win
        entry = next(e for e in w.school.prayers[prayer] if e.kind == kind)
        w.start(prayer, entry)
        APP.processEvents()
        w.session.position = len(w.text_pages) - 1
        w.session.finished = True
        w.refresh()
        APP.processEvents()
        return w

    def test_a_fardh_prayer_ends_on_the_counted_dhikr(self):
        w = self.finish("maghrib", "farz")
        screen = w.slide.tasbih
        self.assertTrue(screen.isVisible())
        self.assertFalse(w.slide.done.isVisible(), "the passage and saying are not shown")

        dhikr = w.content.dhikr
        self.assertEqual([dhikr.salam], screen.salam.lines, "the salam dua across the top")
        self.assertEqual([dhikr.tahlil], screen.tahlil.lines, "the tahlil across the bottom")
        self.assertEqual(3, len(screen.beads.beads), "three beads")
        self.assertEqual([33, 33, 33], [b.count for b in screen.beads.beads])

        # the beads are equal, in a row, and joined by a cord through their middles
        row = screen.beads
        places = [row.geometry_for(n) for n in range(3)]
        circles = [c for _, c, _ in places]
        self.assertEqual(1, len({round(c.width()) for c in circles}), "all the same size")
        self.assertEqual(1, len({round(c.center().y()) for c in circles}), "on one cord")
        self.assertLess(circles[0].right(), circles[1].left(), "left to right, not overlapping")
        self.assertLess(circles[1].right(), circles[2].left())
        for name, circle, number in places:      # name above the bead, count below it
            self.assertLess(name.bottom(), circle.top() + 1)
            self.assertGreater(number.top(), circle.bottom() - 1)
        self.shot("13-dhikr")

    def test_the_beads_count_down_one_at_a_time_then_pass_on(self):
        w = self.finish("asr", "farz")
        row = w.slide.tasbih.beads
        self.assertEqual(0, row.current, "the first bead is the one being said")
        self.assertEqual([33, 33, 33], row.left)

        for _ in range(33):
            w.slide.tasbih.press()
        self.assertEqual([0, 33, 33], row.left, "the first is finished")
        self.assertEqual(1, row.current, "and the second is now the one being said")

        for _ in range(66):
            w.slide.tasbih.press()
        self.assertEqual([0, 0, 0], row.left)
        self.assertTrue(row.done, "all three said")
        self.assertFalse(w.slide.tasbih.press(), "nothing left to count")
        self.assertEqual([0, 0, 0], row.left, "and no counting past nought")
        self.shot("14-dhikr-counted")

    def test_a_click_counts_a_bead_and_never_asks_to_leave(self):
        w = self.finish("fajr", "farz")
        row = w.slide.tasbih.beads
        self.assertTrue(w.counting)
        for _ in range(4):                      # as fast as the ring can be clicked
            time.sleep(0.13)                    # past the guard against a doubled key press
            pace(w)
            key(w, Qt.Key.Key_VolumeUp)
        self.assertEqual(29, row.left[0], "every click counted one")
        self.assertFalse(w.slide.ask.isVisible(), "no 'leave the prayer?' while counting")
        self.assertTrue(w.playing)

        pace(w)
        key(w, Qt.Key.Key_VolumeDown)           # back goes into the prayer again
        self.assertFalse(w.session.finished)
        self.assertFalse(w.slide.tasbih.isVisible())

    def test_a_fardh_prayer_says_astaghfirullah_three_times_before_the_beads(self):
        w = self.win
        for prayer, kind in (("fajr", "farz"), ("maghrib", "farz"), ("dhuhr", "farz")):
            entry = next(e for e in w.school.prayers[prayer] if e.kind == kind)
            w.start(prayer, entry)
            salam, istighfar, kursi = w.text_pages[-3:]
            self.assertEqual("salam", salam.recitation)
            self.assertEqual("istighfar", istighfar.recitation, "straight after the salam")
            self.assertEqual(["أَسْتَغْفِرُ اللَّهَ"], istighfar.arabic)
            self.assertEqual(3, istighfar.repeat, "X3, and the recording plays three times")
            self.assertEqual("postures/tashahhud.png", istighfar.posture_image, "sitting, as after the salam")
            self.assertEqual("ayat_kursi", kursi.recitation, "then Ayat al-Kursi, before the beads")
            self.assertEqual(1, kursi.repeat)
            self.assertEqual("postures/tashahhud.png", kursi.posture_image)
        w.session.position = len(w.text_pages) - 2
        w.refresh()
        APP.processEvents()
        self.assertEqual(3, w.slide.repeat_badge.count)
        self.shot("17-istighfar")
        # sunnah, nafl and witr end on the salam as before, whatever unit they share
        for prayer, kind in (("fajr", "sunnah"), ("isha", "witr"), ("dhuhr", "nafl")):
            entry = next(e for e in w.school.prayers[prayer] if e.kind == kind)
            w.start(prayer, entry)
            self.assertEqual("salam", w.text_pages[-1].recitation, f"{prayer} {kind}")
            self.assertNotIn("ayat_kursi", [p.recitation for p in w.text_pages])

    def test_the_beads_screen_plays_its_recordings(self):
        """The salam dua as it appears; a recording with every count; the tahlil at the end."""
        w = self.win
        w.settings.recitation = True
        played = []
        from unittest import mock
        with mock.patch.object(type(w.recitation), "available", new=property(lambda r: True)), \
             mock.patch.object(type(w.recitation), "play",
                               lambda r, audio, span, times=1: (played.append(audio.stem), True)[1]), \
             mock.patch.object(type(w.recitation), "busy", new=property(lambda r: False)), \
             mock.patch.object(type(w.recitation), "position", lambda r: None):
            w = self.finish("asr", "farz")
            self.assertEqual(["dhikr_salam"], played, "the top dua plays as the screen appears")
            for _ in range(33):
                w.count_dhikr()
            self.assertEqual(["subhanallah"] * 33, played[1:])
            w.count_dhikr()
            self.assertEqual("alhamdulillah", played[-1])
            for _ in range(65):
                w.count_dhikr()
            self.assertEqual("allahu_akbar", played[-1])
            self.assertTrue(w.slide.tasbih.done)
            w.follow_dhikr()                   # the last Allahu akbar has finished...
            self.assertEqual("dhikr_tahlil", played[-1], "...so the bottom dua is recited")
            self.assertEqual(1 + 99 + 1, len(played))

    def test_the_bottom_dua_lights_its_words_in_one_line(self):
        """Its words are split in three where the recording pauses, but shown as one line."""
        w = self.finish("asr", "farz")
        key = w.content.dhikr.tahlil_key
        timings = w.timings[key]
        w.dhikr_now = (key, w.slide.tasbih.tahlil)
        word = timings.words[1][0]                    # first word of the second part
        from unittest import mock
        with mock.patch.object(type(w.recitation), "position", lambda r: word.start + 0.01), \
             mock.patch.object(type(w.recitation), "busy", new=property(lambda r: True)):
            w.follow_dhikr()
        self.assertEqual((0, len(timings.words[0])), w.slide.tasbih.tahlil.highlight)
        w.stop_audio()

    def test_only_fardh_units_count_the_dhikr(self):
        w = self.win
        for prayer, kind in (("fajr", "sunnah"), ("isha", "witr"), ("isha", "nafl")):
            self.finish(prayer, kind)
            self.assertFalse(w.slide.tasbih.isVisible(), f"{prayer} {kind}")
            # And nothing takes its place: the passage of the day that used to be here is gone.
            self.assertFalse(w.slide.done.isVisible(), f"{prayer} {kind}")

    def test_the_counters_start_again_with_each_fardh_prayer(self):
        w = self.finish("asr", "farz")
        for _ in range(5):
            w.slide.tasbih.press()
        self.assertEqual(28, w.slide.tasbih.beads.left[0])
        w = self.finish("isha", "farz")
        self.assertEqual([33, 33, 33], w.slide.tasbih.beads.left)

    def test_the_last_page_of_a_prayer_is_the_last_page(self):
        """This used to be the day's passage and saying, checked line by line. Harry had that
        page taken out, so what is left to check is that the end of a prayer is now simply the
        end of it: the dhikr counter and nothing laid over the top of it."""
        w = self.win
        # The fardh units, by their kind: fajr's first entry is its sunnah, and a sunnah prayer
        # ends without the beads, so asking for [0] proved nothing either way.
        fardh = [e for e in w.school.prayers["fajr"] if e.kind == "farz"][0]
        w.start("fajr", fardh)
        APP.processEvents()
        w.session.position = len(w.text_pages) - 1
        w.session.finished = True
        w.refresh()
        APP.processEvents()
        self.assertFalse(w.slide.done.isVisible(), "something is covering the last page")
        self.assertTrue(w.slide.tasbih.isVisible(), "the dhikr counter should be here")
        self.shot("12-prayer-complete")

    def test_the_stop_button_is_now_the_menu(self):
        w = self.win
        w.start("fajr", w.school.prayers["fajr"][0])
        APP.processEvents()
        button = next(b for b in w.player.findChildren(QtWidgets.QPushButton)
                      if b.objectName() == "stop")
        self.assertEqual(w.t("player.menu"), button.text())
        button.click()
        APP.processEvents()
        self.assertFalse(w.playing, "it leaves the prayer")

    def test_prayer_menu_header(self):
        """The plate, which since 1.62 belongs to the fallback screen: Harry's drawings carry
        the prayer's name across the dome, checked in PrayerPagesAreDrawnTest."""
        w = self.win
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)
        for prayer in ("fajr", "maghrib"):
            w.open_prayer(prayer)
            APP.processEvents()
            labels = {x.objectName(): x for x in w.pick.findChildren(QtWidgets.QLabel)}
            self.assertEqual(w.t(f"prayer.{prayer}"), labels["plateWord"].text())
            self.assertEqual(CONTENT.prayer_names[prayer], labels["plateArabic"].text())
            # Both on the same white plate now, side by side. They used to sit at opposite
            # edges of the screen, which read as two headings rather than one name twice.
            plate = w.prayer_plate
            self.assertEqual("namePlate", plate.objectName())
            self.assertLess(plate.mapTo(w.pick, plate.rect().center()).x(), w.pick.width() / 2,
                            "the plate should be on the left")
            texts = [x.text() for x in w.pick.findChildren(QtWidgets.QLabel)]
            self.assertNotIn(w.t("prayer.pick"), texts, "no 'choose what to pray' line")
            back = next(b for b in w.pick.findChildren(QtWidgets.QPushButton)
                        if b.objectName() == "backButton")
            self.assertIn("QPushButton#backButton", w.styleSheet())
            back.click()
            APP.processEvents()
            self.assertIs(w.welcome, w.stack.currentWidget())

    def test_choosing_an_arch_starts_that_unit(self):
        from salaah.mosque import ArchButton
        w = self.win
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)
        w.open_prayer("maghrib")
        APP.processEvents()
        first = w.pick.findChildren(ArchButton)[0]
        first.chosen.emit(first.payload)
        APP.processEvents()
        self.assertTrue(w.playing)
        self.assertEqual(3, w.session.total_rakats, "Maghrib starts with the 3 Fardh")

    def test_banner_has_a_red_stop_and_a_large_dot(self):
        from salaah.ui import BRICK
        w = self.win
        w.start("fajr", w.school.prayers["fajr"][0])
        APP.processEvents()
        self.assertFalse(hasattr(w, "draft_label"), "the draft notice is gone from the prayer screen")
        stop = next(b for b in w.player.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "stop")
        self.assertIn(BRICK.lower(), w.styleSheet().lower())
        self.assertGreater(stop.width(), w.px(80), "Stop is a proper button, not a word")
        self.assertGreaterEqual(w.dot.width(), w.px(64), "the signal dot is large")

    def test_minarets_light_when_no_prayer_is_due(self):
        from datetime import date, datetime, time as clock
        from salaah.prayer_times import current_prayer, day_fraction
        w = self.win
        APP.processEvents()
        self.assertEqual(2, len(w.mosque.minarets), "both minaret tops were found")
        times = w.prayer_times(datetime(2026, 9, 14, 12, 0))

        def show(hh, mm):
            now = datetime.combine(date(2026, 9, 14), clock(hh, mm))
            w.mosque.set_lit(current_prayer(now, times))
            w.mosque.set_sky(*day_fraction(now, times))
            APP.processEvents()

        show(13, 30)
        self.assertEqual("dhuhr", w.mosque.lit)
        self.assertTrue(w.mosque.sun_up)
        show(10, 0)
        self.assertIsNone(w.mosque.lit, "no arch lit outside a prayer's window")
        show(23, 0)
        self.assertEqual("isha", w.mosque.lit)
        self.assertFalse(w.mosque.sun_up, "the moon is out")

    def test_banner_sits_at_the_top_with_a_cog(self):
        from salaah.mosque import GearButton
        w = self.win
        APP.processEvents()
        banner = next(x for x in w.home.findChildren(QtWidgets.QWidget)
                      if x.objectName() == "banner")
        self.assertIn("QWidget#banner", w.styleSheet())
        self.assertEqual(1, len(banner.findChildren(GearButton)), "settings is a cog, not words")
        self.assertIn("Bury", w.times_label.text())
        self.assertLess(banner.mapTo(w.home, banner.rect().center()).y(),
                        w.mosque.mapTo(w.home, w.mosque.rect().center()).y(),
                        "the banner is above the mosque")

    def test_menu_button_and_prayer_name_are_the_same_height(self):
        w = self.win
        w.start("maghrib", w.school.prayers["maghrib"][0])
        APP.processEvents()
        menu = next(b for b in w.player.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "stop")
        self.assertEqual(menu.height(), w.title_label.height())

    def test_screens_are_white(self):
        w = self.win
        self.assertIn("QWidget { background:white", w.stylesheet())
        w.open_prayer("fajr")
        APP.processEvents()
        colour = w.pick.palette().color(w.pick.backgroundRole()).name().lower()
        self.assertIn(colour, ("#ffffff", "#f5f6f3"), "the sub-menu is not tinted")

    def test_the_clock_and_the_lit_arch(self):
        from datetime import datetime
        w = self.win
        w.tick()
        APP.processEvents()
        self.assertRegex(w.mosque.time_text, r"^\d\d:\d\d$")
        times = w.prayer_times()
        from salaah.prayer_times import current_prayer
        self.assertEqual(current_prayer(datetime.now(), times), w.mosque.lit)
        if w.mosque.lit:
            self.assertIn(w.mosque.lit, {a.prayer for a in w.mosque.arches})

    def test_the_time_is_sized_off_the_dome_and_then_trimmed(self):
        """Two steps, kept apart on purpose: the dome curves out either side of the numbers so
        the time is set larger than a flat fit, and then trimmed because it read too big."""
        from salaah.mosque import CLOCK_BOOST, CLOCK_TRIM
        w = self.win
        w.tick()
        APP.processEvents()
        box = w.mosque.clock_box
        self.assertGreater(box.width(), 10, "the dome was found in the picture")
        font = w.mosque.clock_type(box, "21:45")
        plain = QtGui.QFont(font)
        plain.setPixelSize(max(8, int(font.pixelSize() / (CLOCK_BOOST * CLOCK_TRIM))))
        self.assertAlmostEqual(CLOCK_BOOST * CLOCK_TRIM,
                               font.pixelSize() / plain.pixelSize(), delta=0.03)
        # the plain size is the one that fits the dome's flat middle
        self.assertLessEqual(QtGui.QFontMetrics(plain).horizontalAdvance("21:45"),
                             box.width() * 0.95)

    def test_the_time_on_the_dome_is_fifteen_percent_smaller_than_it_was(self):
        """What was asked for. Measured against the untrimmed size rather than against a
        number written down here, so it stays true if the dome or the font ever change."""
        from salaah import mosque
        w = self.win
        box = w.mosque.clock_box
        trimmed = w.mosque.clock_type(box, "21:45").pixelSize()
        was = mosque.CLOCK_TRIM
        mosque.CLOCK_TRIM = 1.0
        self.addCleanup(lambda: setattr(mosque, "CLOCK_TRIM", was))
        before = w.mosque.clock_type(box, "21:45").pixelSize()
        self.assertAlmostEqual(0.85, trimmed / before, delta=0.02,
                               msg=f"{before}px became {trimmed}px")

    def test_settings_is_two_columns_of_settings(self):
        from salaah.mosque import GearButton
        w = self.win
        w.open_settings()
        APP.processEvents()
        screen = w.settings_screen
        self.assertIs(screen, w.stack.currentWidget())

        # The headings are what tells you there are two columns; the controls under them are a
        # mixture of circles, switches, sliders and pickers, and which is which is a separate
        # question from whether the page has two columns at all.
        heads = [x for x in screen.findChildren(QtWidgets.QLabel)
                 if x.objectName() == "settingHead" and x.isVisible()]
        self.assertGreater(len(heads), 8, "every setting has a heading")
        middle = screen.width() / 2
        lefts = [x for x in heads if x.mapTo(screen, x.rect().center()).x() < middle]
        rights = [x for x in heads if x.mapTo(screen, x.rect().center()).x() >= middle]
        self.assertTrue(lefts and rights, "settings sit in both columns")

        choices = [b for b in screen.findChildren(QtWidgets.QRadioButton)
                   if b.objectName() == "choice"]
        self.assertTrue(any(b.isChecked() for b in choices), "the ones in use are filled in")
        self.assertEqual(1, len(screen.findChildren(GearButton)),
                         "a cog for the heading, and none on the banner: it would lead here")

        home = next(b for b in screen.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "mainScreen")
        self.assertGreater(home.mapTo(screen, home.rect().center()).x(), middle, "top right")
        home.click()
        APP.processEvents()
        self.assertIs(w.welcome, w.stack.currentWidget(), "it goes back to the mosque")
        self.shot("10-settings")

    def test_only_two_settings_keep_their_explanation(self):
        w = self.win
        w.backlight = FakeMonitor(answers=True)      # a monitor that does as it is told
        w.rebuild()
        w.open_settings()
        APP.processEvents()
        hints = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                 if x.objectName() == "settingHint"]
        self.assertEqual(2, len(hints), "only the recitation and the lettering are explained")

    def test_settings_and_button_status(self):
        from salaah.ui import BRICK, MINT
        w = self.win
        w.on_devices(["AB Shutter3", "BLE M3"])
        self.assertEqual(MINT, w.dot.color.name().upper().replace("#", "#"), "green when connected")
        w.open_settings()
        APP.processEvents()
        self.assertIn("BLE M3", w.devices_label.text())
        w.on_devices([])
        self.assertEqual("None connected", w.devices_label.text())
        self.assertEqual(BRICK, w.dot.color.name().upper().replace("#", "#"), "red when not")

    def test_banner_shows_the_prayer_in_arabic(self):
        w = self.win
        for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
            w.start(prayer, w.school.prayers[prayer][0])
            APP.processEvents()
            self.assertEqual(CONTENT.prayer_names[prayer], w.arabic_name.text(), prayer)
            # dead centre of the screen, not just somewhere in the middle
            centre = w.arabic_name.mapTo(w, w.arabic_name.rect().center()).x()
            self.assertLess(abs(centre - w.width() // 2), 4, prayer)

    def test_cursor_setting(self):
        """Shown means a pointing finger, not an arrow: everything on the mat is touched, so a
        mouse standing in for a finger should look like one."""
        w = self.win
        app = QtWidgets.QApplication.instance()
        w.set_cursor("1")
        self.assertTrue(w.settings.cursor)
        self.assertIsNotNone(app.overrideCursor(), "the pointer is set, not left to the desktop")
        self.assertEqual(Qt.CursorShape.PointingHandCursor, app.overrideCursor().shape())
        w.set_cursor("0")
        self.assertEqual(Qt.CursorShape.BlankCursor, app.overrideCursor().shape(),
                         "pointer hidden again")
        w.set_cursor("1")                            # leave it visible for the next test
        self.assertEqual(Qt.CursorShape.PointingHandCursor, app.overrideCursor().shape(),
                         "turning it back on restores the finger, not the arrow")
        while app.overrideCursor() is not None:
            app.restoreOverrideCursor()

    def test_mouse_click_advances_the_prayer(self):
        w = self.win
        w.start("fajr", w.school.prayers["fajr"][0])
        self.assertEqual(0, w.session.position)
        pace(w)
        pos = QtCore.QPointF(w.slide.width() * 0.7, w.slide.height() / 2)   # right side: forward
        press = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, pos, Qt.MouseButton.LeftButton,
                                  Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(w.slide, press)
        self.assertEqual(1, w.session.position)
        pace(w)
        back = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress,
                                 QtCore.QPointF(w.slide.width() * 0.1, w.slide.height() / 2),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                 Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(w.slide, back)
        self.assertEqual(0, w.session.position)

    def test_keys_do_nothing_outside_a_prayer(self):
        key(self.win, Qt.Key.Key_VolumeUp)
        self.assertIsNone(self.win.session)


if __name__ == "__main__":
    unittest.main()


class SplashTest(unittest.TestCase):
    """The opening logo animation, drawn by salaah/splash.py (not yet shown by the app)."""

    def setUp(self):
        from salaah.splash import Splash
        self.splash = Splash(CONTENT.root)

    def frame(self, t, w=960, h=540):
        image = QtGui.QImage(w, h, QtGui.QImage.Format.Format_RGB32)
        p = QtGui.QPainter(image)
        self.splash.paint(p, QtCore.QRectF(0, 0, w, h), t)
        p.end()
        return image

    def test_every_piece_is_there(self):
        self.assertEqual({"boy", "hands_pressed", "hands_open", "my", "saalah", "www", "com"},
                         set(self.splash.layers))
        for name, (image, _) in self.splash.layers.items():
            self.assertFalse(image.isNull(), name)

    def test_it_starts_blank_and_ends_on_the_whole_logo(self):
        start = self.frame(0.0)
        self.assertEqual(QtGui.QColor("white"), start.pixelColor(480, 270), "a white screen first")
        end = self.frame(self.splash.DURATION)
        _, cy, r = self.splash.circle
        scale = 540 / self.splash.design_height
        top_of_disc = end.pixelColor(480, int((cy - r * 0.85) * scale))
        self.assertLess(top_of_disc.lightness(), 40, "the black disc, full by the end")

    def test_the_circle_is_round(self):
        end = self.frame(self.splash.DURATION, 1920, 1080)
        _, cy, r = self.splash.circle
        scale = 1080 / self.splash.design_height
        middle_y = int(cy * scale)
        dark = [x for x in range(1920) if end.pixelColor(x, middle_y).lightness() < 128]
        width = max(dark) - min(dark)
        self.assertAlmostEqual(2 * r * scale, width, delta=6, msg="as wide as it is tall")


class TapAlongTest(unittest.TestCase):
    """Setting the word timings by ear with the ring (Settings, Tap in the word timings)."""

    def setUp(self):
        from salaah.render import load_timings
        self.timings = load_timings(ASSETS)

    def test_taps_become_word_starts_less_the_reaction_time(self):
        from salaah.timing import REACTION, TapSession
        old = self.timings["istiftah"]
        s = TapSession(CONTENT.arabic["istiftah"], old)
        self.assertEqual((0, 1), s.next_word, "the first word starts with the recording; tap from the second")
        taps = [0.5, 1.0, 1.5, 2.1, 2.6, 3.1, 3.7, 4.2, 4.8]   # ten words, the first untapped
        for t in taps:
            s.tap(t)
        self.assertTrue(s.complete)
        data = s.timings()
        self.assertFalse(data["estimated"])
        words = [w for seg in data["segments"] for w in seg["words"]]
        self.assertEqual(10, len(words))
        for w, t in zip(words[1:], taps):
            self.assertAlmostEqual(t - REACTION, w["start"], places=3)
        for a, b in zip(words, words[1:]):
            self.assertLessEqual(a["end"], b["start"] + 1e-6, "words never overlap")
        self.assertEqual([3, 4, 3], [len(seg["words"]) for seg in data["segments"]], "kept to its lines")

    def test_words_nobody_tapped_are_still_given_a_time(self):
        from salaah.timing import TapSession
        s = TapSession(CONTENT.arabic["kawthar"], self.timings["kawthar"])
        s.tap(1.0)
        s.tap(1.5)
        data = s.timings()
        words = [w for seg in data["segments"] for w in seg["words"]]
        self.assertEqual(sum(len(line.split()) for line in CONTENT.arabic["kawthar"]), len(words))
        starts = [w["start"] for w in words]
        self.assertEqual(sorted(starts), starts, "still in order")

    def test_a_pause_at_a_line_end_is_kept(self):
        """Between lines the voice stops; the last word of a line ends there, not at the next tap."""
        from salaah.timing import TapSession
        old = self.timings["kawthar"]
        s = TapSession(CONTENT.arabic["kawthar"], old)
        for li, seg in enumerate(old.words):
            for wi, w in enumerate(seg):
                if (li, wi) != (0, 0):
                    s.tap(w.start + 0.1)
        data = s.timings()
        self.assertAlmostEqual(old.segments[0].end, data["segments"][0]["end"], places=2)
        self.assertLess(data["segments"][0]["end"], data["segments"][1]["start"])

    def test_the_screen_follows_the_ring(self):
        from salaah.timing import CHECKING, READY, TAPPING
        import tempfile, shutil
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(theme="light", recitation=False), scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        APP.processEvents()
        try:
            # work on a copy of the timings file so the test never changes the real one
            key = "takbir"
            folder = Path(tempfile.mkdtemp())
            shutil.copy(ASSETS / "audio" / f"{key}.mp3", folder)
            shutil.copy(ASSETS / "audio" / f"{key}.json", folder)
            from salaah.audio import Timings
            w.timings = {key: Timings.load(folder / f"{key}.json")}
            w.timing_screen.keys = [key]
            clock = {"t": None}
            w.recitation.play = lambda audio, span, times=1: clock.update(t=0.0) or True
            w.recitation.position = lambda: clock["t"]
            w.recitation.stop = lambda: clock.update(t=None)
            from unittest import mock
            busy = mock.patch.object(type(w.recitation), "busy",
                                     new=property(lambda r: clock["t"] is not None))
            busy.start()
            self.addCleanup(busy.stop)      # puts the real property back, whatever happens

            w.open_timing()
            screen = w.timing_screen
            self.assertIs(screen, w.stack.currentWidget())
            self.assertEqual(READY, screen.state)
            self.assertEqual(CONTENT.arabic[key], screen.words.lines)
            SHOTS.mkdir(parents=True, exist_ok=True)
            w.grab().save(str(SHOTS / "15-tap-along.png"))

            w.timing_press("next")                       # start
            self.assertEqual(TAPPING, screen.state)
            self.assertEqual((0, 1), screen.words.highlight, "the second word is red, waiting")
            clock["t"] = 0.55
            time.sleep(0.13)
            w.timing_press("next")                       # the last word of 'Allahu akbar'
            self.assertEqual(CHECKING, screen.state, "saved and playing back")
            saved = json.loads((folder / f"{key}.json").read_text())
            self.assertFalse(saved["estimated"])
            self.assertAlmostEqual(0.45, saved["segments"][0]["words"][1]["start"], places=2)
            self.assertFalse(w.timings[key].estimated, "the app uses the new timings straight away")
            time.sleep(0.13)
            w.timing_press("next")                       # on to the next (only) recording
            self.assertEqual(READY, screen.state)
            key_event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
            QtWidgets.QApplication.sendEvent(w, key_event)
            self.assertIs(w.settings_screen, w.stack.currentWidget(), "Escape goes back to Settings")
        finally:
            w.shutdown()
            w.close()
            w.deleteLater()
            APP.processEvents()

    def test_settings_does_not_offer_it(self):
        """Tapping the timings in is a job for building the mat, not for praying on it, so it is
        out of Settings and reached with --tap-timings instead."""
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(theme="light", recitation=False), scale=1.0, save_settings=False)
        try:
            names = [b.objectName() for b in w.settings_screen.findChildren(QtWidgets.QPushButton)]
            self.assertNotIn("tapTimings", names)
            words = [b.text() for b in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]
            self.assertFalse([x for x in words if "timings" in x.lower()])
        finally:
            w.shutdown()
            w.deleteLater()

    def test_the_command_line_still_reaches_it(self):
        from salaah.main import build_parser
        self.assertTrue(build_parser().parse_args(["--tap-timings"]).tap_timings)
        self.assertFalse(build_parser().parse_args([]).tap_timings)
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(theme="light", recitation=False), scale=1.0, save_settings=False)
        try:
            if not w.timings:
                self.skipTest("no word timings to tap")
            w.open_timing()
            self.assertIs(w.timing_screen, w.stack.currentWidget(),
                          "--tap-timings has nothing left to open")
        finally:
            w.shutdown()
            w.deleteLater()


@unittest.skipUnless(__import__("salaah.ui", fromlist=["QIBLA"]).QIBLA,
                     "the Qibla compass is switched off: the mat has a mechanical one")
class QiblaScreenTest(unittest.TestCase):
    """The compass before the main screen."""

    def window(self, compass=None, **settings):
        from unittest import mock
        switch = mock.patch("salaah.ui.QIBLA", True)      # the compass is off in the app for now
        switch.start()
        self.addCleanup(switch.stop)
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(**{"theme": "light", "recitation": False, **settings}), scale=1.0,
                       save_settings=False, compass=compass)
        w.resize(1920, 1080)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_it_comes_first_and_lines_up_with_the_stand_in(self):
        from salaah import compass as compass_module
        from salaah.qibla import StandIn
        chip = StandIn(start=40.0)
        w = self.window(chip)
        w.begin()
        self.assertIs(w.compass_screen, w.stack.currentWidget(), "the compass comes first")
        screen = w.compass_screen
        screen.tick()
        self.assertIn("Turn right", screen.status.text())
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "18-qibla-turn.png"))

        chip.value = 118.0                         # turned to face the Kaaba
        w.facing.smooth = type(w.facing.smooth)()  # no lag in a test
        old_hold, compass_module.HOLD = compass_module.HOLD, 0.0
        try:
            screen.tick()                          # lined up...
            self.assertTrue(screen.dial.aligned)
            w.grab().save(str(SHOTS / "19-qibla-lined-up.png"))
            screen.tick()                          # ...and held: on to the main screen
        finally:
            compass_module.HOLD = old_hold
        self.assertIs(w.welcome, w.stack.currentWidget())
        self.assertAlmostEqual(118.0, w.settings.qibla_heading, delta=0.5, msg="remembered")

    def test_with_no_compass_the_bearing_is_the_headline(self):
        """No chip fitted is the normal case now: a compass in the mat's frame is read by eye,
        so the number is what the screen is for. It used to be buried mid-sentence at 40px."""
        w = self.window()                       # no chip: heading unknown
        screen = w.compass_screen
        screen.tick()
        self.assertIsNone(screen.heading, "this test is meant to have no compass")
        self.assertFalse(screen.bearing.isHidden(), "the bearing label is hidden")
        self.assertIn("118", screen.bearing.text())
        self.assertIn("\u00b0", screen.bearing.text(), "the degree sign belongs on the number")
        self.assertGreater(screen.bearing.font().pixelSize(),
                           2 * screen.status.font().pixelSize(),
                           "the number should dwarf the note under it")

    def test_with_a_compass_the_turn_is_the_headline_not_the_bearing(self):
        """Where the dial turns, "turn right 20" is the instruction and a fixed bearing would
        only be noise."""
        from salaah.qibla import StandIn
        w = self.window(StandIn(start=40.0))
        screen = w.compass_screen
        screen.tick()
        self.assertTrue(screen.bearing.isHidden(), "a fixed bearing is only noise here")
        self.assertIn("Turn", screen.status.text())

    def test_the_bearing_fits_across_the_seven_inch_screen(self):
        """It is read on the 600px-wide panel, and the widest it can ever be is three digits.
        Measured rather than eyeballed, because a number that runs off the edge of the screen is
        exactly the fault this change was meant to fix."""
        w = self.window()
        screen = w.compass_screen
        screen.tick()
        room = 600 - (screen.layout().contentsMargins().left()
                      + screen.layout().contentsMargins().right())
        widest = QtGui.QFontMetrics(screen.bearing.font()).horizontalAdvance("359\u00b0")
        self.assertLessEqual(widest, room,
                             f"the bearing needs {widest}px of {room}px on the 7in screen")

    def test_the_note_under_it_stays_on_one_line_in_every_language(self):
        """Two bold lines wrapped under the number and fought with it."""
        for lang in sorted(full_packs(available_packs(ASSETS))):
            w = self.window(lang=lang)
            screen = w.compass_screen
            screen.tick()
            metrics = QtGui.QFontMetrics(screen.status.font())
            room = 600 - (screen.layout().contentsMargins().left()
                          + screen.layout().contentsMargins().right())
            wide = metrics.horizontalAdvance(screen.status.text())
            self.assertLessEqual(wide, room,
                                 f"{lang}: {screen.status.text()!r} needs {wide}px of {room}px")

    def test_it_is_skipped_when_the_mat_has_not_moved(self):
        from salaah.qibla import StandIn
        w = self.window(StandIn(start=120.0), qibla_heading=118.0)
        w.begin()
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_it_asks_again_when_the_mat_has_been_turned(self):
        from salaah.qibla import StandIn
        w = self.window(StandIn(start=200.0), qibla_heading=118.0)
        w.begin()
        self.assertIs(w.compass_screen, w.stack.currentWidget())

    def test_a_press_always_goes_straight_on(self):
        w = self.window()
        w.begin()
        self.assertIs(w.compass_screen, w.stack.currentWidget())
        w.on_button("next")
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_without_a_compass_it_shows_the_bearing(self):
        w = self.window()
        w.begin()
        w.compass_screen.tick()
        # The number moved out of this sentence and into a label of its own, big enough to read
        # while kneeling on the floor squaring a mat.
        self.assertIn("118", w.compass_screen.bearing.text())
        self.assertIn("compass", w.compass_screen.status.text())
        self.assertIn("Bury", w.compass_screen.detail.text())
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "20-qibla-no-compass.png"))

    def test_it_can_be_switched_off(self):
        w = self.window(qibla_start=False)
        w.begin()
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_the_arrow_keys_turn_the_stand_in(self):
        from salaah.qibla import StandIn
        chip = StandIn(start=100.0)
        w = self.window(chip)
        w.begin()
        key(w, Qt.Key.Key_Right)
        self.assertEqual(105.0, chip.value)
        key(w, Qt.Key.Key_Left)
        key(w, Qt.Key.Key_Left)
        self.assertEqual(95.0, chip.value)
        self.assertIs(w.compass_screen, w.stack.currentWidget(), "turning is not skipping")


class ThemeTest(unittest.TestCase):
    """Light, dark, and automatic: dark from Maghrib until sunrise."""

    def window(self, **settings):
        from salaah import theme
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(**{"recitation": False, **settings}), scale=1.0,
                       save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents(),
                                 theme.set_dark(False)))
        return w

    def test_automatic_follows_maghrib_and_sunrise(self):
        from datetime import datetime, time as clock
        from salaah.theme import wants_dark
        times = {"sunrise": clock(6, 53), "maghrib": clock(19, 12)}
        day = datetime(2026, 9, 21, 12, 0)
        self.assertFalse(wants_dark("auto", day, times))
        self.assertFalse(wants_dark("auto", day.replace(hour=19, minute=11), times))
        self.assertTrue(wants_dark("auto", day.replace(hour=19, minute=12), times))
        self.assertTrue(wants_dark("auto", day.replace(hour=2), times))
        self.assertFalse(wants_dark("auto", day.replace(hour=6, minute=53), times))
        self.assertTrue(wants_dark("dark", day, times))
        self.assertFalse(wants_dark("light", day.replace(hour=23), times))
        # no sunset that far north: the clock decides
        self.assertTrue(wants_dark("auto", day.replace(hour=22), {"sunrise": None, "maghrib": None}))

    def test_dark_is_white_on_black(self):
        w = self.window(theme="dark")
        pic = w.home.grab().toImage()
        corner = pic.pixelColor(pic.width() - 5, pic.height() - 5)
        self.assertLess(corner.lightness(), 30, "the sky behind the mosque is black")
        w.open_settings()
        APP.processEvents()
        page = w.settings_screen.grab().toImage()
        self.assertLess(page.pixelColor(5, page.height() // 2).lightness(), 30)
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "30-dark-settings.png"))
        w.go_home()
        APP.processEvents()
        w.grab().save(str(SHOTS / "31-dark-home.png"))

    def test_the_posture_is_inverted_after_dark(self):
        w = self.window(theme="dark")
        w.open_prayer("fajr")
        w.start("fajr", w.school.prayers["fajr"][-1])
        settle()                      # the posture frame has to be laid out before it is sized
        view = w.slide.posture
        pix = w.images.get(view.path, view.target()).toImage()
        # This fails about one run in five, and only inside the whole suite -- never alone. The
        # message carries what it would take to explain it, so the next failure is evidence
        # rather than another guess.
        from salaah.render import palette
        story = (f"lightness {pix.pixelColor(2, 2).lightness()} at (2,2); "
                 f"image {pix.width()}x{pix.height()}; asked for {view.target()}; "
                 f"palette dark={palette().dark}; path={view.path}")
        self.assertLess(pix.pixelColor(2, 2).lightness(), 30, f"black round the figure -- {story}")
        shot = w.slide.grab().toImage()
        self.assertLess(shot.pixelColor(shot.width() - 5, shot.height() // 2).lightness(), 30)
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "32-dark-prayer.png"))

    def test_choosing_in_settings_switches_straight_away(self):
        from salaah import theme
        w = self.window(theme="light")
        self.assertFalse(theme.is_dark())
        w.set_theme("dark")
        self.assertTrue(theme.is_dark())
        self.assertEqual("dark", w.settings.theme)
        self.assertIn("background:black", w.styleSheet())
        w.set_theme("light")
        self.assertFalse(theme.is_dark())

    def test_automatic_waits_for_the_prayer_to_finish(self):
        from unittest import mock
        from salaah import theme
        w = self.window(theme="auto")
        w.open_prayer("fajr")
        w.start("fajr", w.school.prayers["fajr"][-1])
        was = theme.is_dark()
        with mock.patch.object(type(w), "wants_dark", return_value=not was):
            self.assertFalse(w.apply_theme(), "not in the middle of a prayer")
            self.assertEqual(was, theme.is_dark())
            w.stop()
            self.assertTrue(w.apply_theme())
            self.assertEqual(not was, theme.is_dark())

    def test_settings_offers_the_three_choices_in_a_dropdown(self):
        w = self.window(theme="light")
        picker = w.theme_picker
        labels = [picker.itemText(i) for i in range(picker.count())]
        self.assertEqual(["Automatic: dark from Maghrib to sunrise", "Light: black on white",
                          "Dark: white on black"], labels)
        self.assertEqual(["auto", "light", "dark"],
                         [picker.itemData(i) for i in range(picker.count())])
        self.assertEqual("Light: black on white", picker.currentText(), "the setting it is on")

    def test_picking_from_the_dropdown_changes_the_screen(self):
        from salaah import theme
        w = self.window(theme="light")
        self.assertFalse(theme.is_dark())
        w.set_theme("dark")
        self.assertTrue(theme.is_dark())
        self.assertEqual("dark", w.settings.theme)
        w.set_theme("light")
        self.assertFalse(theme.is_dark())

    def test_the_choices_are_not_rows_of_circles_any_more(self):
        w = self.window(theme="light")
        labels = [b.text() for b in w.settings_screen.findChildren(QtWidgets.QRadioButton)]
        self.assertFalse([x for x in labels if "black on white" in x])


class SideScreenTest(unittest.TestCase):
    """The 7-inch screen: the Qibla between prayers, the posture picture during one."""

    def window(self, compass=None, **settings):
        from unittest import mock
        switch = mock.patch("salaah.ui.QIBLA", True)      # the compass is off in the app for now
        switch.start()
        self.addCleanup(switch.stop)
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, compass=compass, side=True)
        w.resize(1920, 1200)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def fardh(self, w, prayer="dhuhr"):
        entry = [e for e in w.school.prayers[prayer] if e.kind == "farz"][0]
        w.open_prayer(prayer)
        w.start(prayer, entry)
        APP.processEvents()

    def test_start_up_puts_the_compass_on_the_side_and_the_mosque_on_the_main(self):
        w = self.window()
        w.begin()
        self.assertIs(w.welcome, w.stack.currentWidget(), "the main screen is not held up")
        self.assertTrue(w.side.showing_compass)
        self.assertTrue(w.side.compass.timer.isActive())

    def test_the_posture_moves_to_the_side(self):
        w = self.window()
        w.begin()
        self.fardh(w)
        self.assertFalse(w.side.showing_compass)
        self.assertIs(w.side.posture, w.slide.posture)
        self.assertIs(w.volume, w.slide.volume, "the volume is in the main screen's bar")
        self.assertFalse(hasattr(w.side, "volume"), "and not on the 7-inch screen")
        self.assertIs(w.side, w.slide.posture.window(), "the picture is on the 7-inch screen")
        self.assertIsNotNone(w.slide.posture.path)
        # the words have the main screen's whole width
        self.assertGreater(w.slide.arabic.width(), 1920 * 0.9)
        w.stop()
        self.assertTrue(w.side.showing_compass, "back to the compass after the prayer")

    def test_x3_moves_to_the_side_screen(self):
        w = self.window()
        self.fardh(w)
        while w.current_page.repeat != 3:
            w.session.next()
        w.refresh()
        APP.processEvents()
        self.assertEqual(3, w.slide.repeat_badge.count)
        self.assertIs(w.side, w.slide.repeat_badge.window(), "the circle is on the 7-inch screen")
        self.assertIs(w.side.posture.badge, w.slide.repeat_badge)
        self.assertTrue(w.slide.repeat_badge.isVisible())

    def test_the_volume_bar_in_the_bar_sets_the_volume(self):
        w = self.window(recitation=True, volume=80)
        self.fardh(w)
        w.volume.set_volume(30, tell=True)
        self.assertEqual(30, w.settings.volume)
        w.volume.set_volume(0, tell=True)
        self.assertFalse(w.settings.recitation)

    def test_lining_up_on_the_side_is_remembered_and_the_compass_stays(self):
        from unittest import mock
        from salaah.qibla import StandIn
        chip = StandIn(start=118.5)
        w = self.window(chip)
        w.begin()
        compass = w.side.compass
        compass.lined_up_since = None          # opening it already ticked once on the real clock
        with mock.patch("salaah.compass.time.monotonic", side_effect=[0.0, 5.0, 6.0]):
            compass.tick()
            compass.tick()
            compass.tick()
        self.assertAlmostEqual(118.5, w.settings.qibla_heading, delta=1)
        self.assertTrue(compass.timer.isActive(), "it keeps watching")
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_a_touch_on_the_side_compass_does_not_skip(self):
        w = self.window()
        w.begin()
        told = []
        w.side.compass.done.connect(told.append)
        pos = QtCore.QPointF(300, 500)
        press = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, pos, pos, pos,
                                  Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                  Qt.KeyboardModifier.NoModifier)
        APP.sendEvent(w.side.compass, press)
        self.assertEqual([], told)
        self.assertNotIn("Press", w.side.compass.detail.text())

    def test_dark_reaches_the_side_screen(self):
        from salaah import theme
        w = self.window()
        self.addCleanup(lambda: theme.set_dark(False))
        w.set_theme("dark")
        APP.processEvents()
        pic = w.side.grab().toImage()
        self.assertLess(pic.pixelColor(5, pic.height() - 5).lightness(), 30)

    def test_without_a_side_screen_nothing_changes(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False)
        self.addCleanup(lambda: shut(w))
        self.assertIsNone(w.side)
        self.assertIs(w, w.slide.posture.window())


class TranslationScreenTest(unittest.TestCase):
    """The meaning on the left, the Arabic on the right."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def fardh(self, w):
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        APP.processEvents()

    def go(self, w, key):
        while w.current_page.recitation != key:
            w.session.next()
        w.refresh()
        APP.processEvents()

    def test_arabic_only_is_what_the_arabic_only_setting_gives(self):
        """It used to be the default, because the meaning was off until you went and turned it
        on in a second dropdown. The dropdown has gone and the mat comes up in English, so
        Arabic alone is now something asked for by name rather than what you get by not
        asking."""
        w = self.window(lang="ar")
        self.fardh(w)
        self.go(w, "fatiha")
        self.assertTrue(w.slide.arabic.isVisible())
        self.assertFalse(w.slide.parallel.isVisible())

    def test_the_mat_comes_up_with_the_meaning_beside_the_arabic(self):
        """The other half of that change: a mat nobody has touched shows English under the
        Arabic rather than nothing, because English is a language and the old default was the
        absence of one."""
        w = self.window()
        self.fardh(w)
        self.go(w, "fatiha")
        self.assertTrue(w.slide.parallel.isVisible(), "no meaning on a mat set to English")
        self.assertIn("I intend", w.text_pages[0].arabic[0])

    def test_french_sits_beside_the_arabic(self):
        w = self.window(lang="fr")
        self.fardh(w)
        self.assertTrue(w.text_pages[0].arabic[0].startswith("J'ai l'intention d'accomplir 4 rak'ats fardh"))
        self.assertTrue(w.slide.arabic.isVisible(), "the intention is one sentence, full width")
        self.go(w, "fatiha")
        box = w.slide.parallel
        self.assertTrue(box.isVisible())
        self.assertFalse(w.slide.arabic.isVisible())
        self.assertEqual(7, len(box.arabic))
        # "Louange à", not the whole line. Which French this is depends on whether the licensed
        # Clear Qur'an file is sitting in the folder: the public fr.json has "Louange à Dieu",
        # Harry's private fr-clair has "Louange à Allah", and with the translation dropdown
        # gone the app prefers the personal one when it is installed. Asserting either full
        # line would make this test pass or fail on whether a file that must never be in a
        # release happens to be present -- which is a test reporting on the checkout rather
        # than on the code. The rule itself is tested in PersonalTranslationTest.
        self.assertTrue(box.meaning[1].startswith("Louange à"), box.meaning[1])
        px, rows, total = box.layout()
        self.assertLessEqual(total, box.height())
        self.assertGreaterEqual(box.latin_px(px), 30, "readable from standing")
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "40-french-fatiha.png"))

    def test_the_translation_lights_up_with_the_arabic(self):
        w = self.window(lang="en")
        self.fardh(w)
        self.go(w, "fatiha")
        box = w.slide.parallel
        w.slide.set_highlight((1, 0))         # al-hamdu
        first = box.lit_meaning(1)
        w.slide.set_highlight((1, 3))         # al-'alamin, the last word
        last = box.lit_meaning(1)
        words = box.meaning[1].split()
        self.assertEqual(0, first.start)
        self.assertEqual(len(words), last.stop)
        self.assertLess(first.stop, last.start + 1)
        self.assertEqual(range(0), box.lit_meaning(2), "only the verse being said")
        w.slide.set_highlight(None)
        self.assertEqual(range(0), box.lit_meaning(1))

    def test_every_arabic_word_lights_some_translation(self):
        w = self.window(lang="fr")
        self.fardh(w)
        self.go(w, "tashahhud")
        box = w.slide.parallel
        for row, line in enumerate(box.arabic):
            covered = set()
            for word in range(len(line.split())):
                box.set_highlight((row, word))
                lit = box.lit_meaning(row)
                self.assertTrue(lit, f"row {row} word {word}")
                covered.update(lit)
            self.assertEqual(set(range(len(box.meaning[row].split()))), covered)

    def test_settings_offers_one_language_picker_and_arabic_only_is_in_it(self):
        """There were two dropdowns here: a language, and "Translation beside Arabic" under
        it. They asked the same question and could disagree, so the second has gone and
        "Arabic only" -- which used to be the top row of it -- has moved into the first.

        One picker fewer is the visible half of the change. The invisible half is that there
        is now nowhere to set a meaning language that the menus do not follow.
        """
        w = self.window()
        boxes = w.settings_screen.findChildren(QtWidgets.QComboBox)
        self.assertEqual(4, len(boxes),
                         "pickers, not rows of circles: the language, the screen mode, the "
                         "Arabic lettering and how much edge")
        picker = w.language_picker
        labels = [picker.itemText(i) for i in range(picker.count())]
        for want in ("English", "Français", "اردو", "Arabic only"):
            self.assertIn(want, labels)
        self.assertEqual(len(WRITTEN_IN) + 1, picker.count(),
                         "the six the mat is written in, and Arabic only")
        self.assertEqual("Arabic only", labels[-1], "Arabic belongs on the end, not in the middle")
        self.assertEqual("en", picker.itemData(picker.currentIndex()))


@unittest.skipUnless(__import__("salaah.ui", fromlist=["QIBLA"]).QIBLA,
                     "the Qibla compass is switched off: the mat has a mechanical one")
class QiblaAtStartTest(unittest.TestCase):
    """The compass is back: on the 7" at start-up, with the main menu on the big screen."""

    def window(self, side=False, **settings):
        from salaah import ui
        self.assertTrue(ui.QIBLA, "the compass is meant to be switched on")
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}), scale=1.0,
                       save_settings=False, aspect=None, side=side)
        w.resize(1920, 1200)
        w.show()
        if side:
            w.side.resize(600, 1024)
            w.side.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_compass_goes_on_the_small_screen_and_the_menu_on_the_big_one(self):
        w = self.window(side=True)
        w.begin()
        self.assertTrue(w.side.showing_compass, "the 7\" should show the Qibla at start-up")
        self.assertIs(w.welcome, w.stack.currentWidget(), "the big screen goes straight to the menu")
        self.assertFalse(w.qibla_open, "and not to the compass as well")

    def test_the_small_screen_compass_keeps_watching(self):
        w = self.window(side=True)
        w.begin()
        self.assertTrue(w.side.compass.stays, "the mat can be moved, so it carries on watching")
        self.assertTrue(w.side.compass.timer.isActive())

    def test_with_no_small_screen_the_compass_comes_up_on_the_main_one(self):
        w = self.window()
        w.begin()
        self.assertTrue(w.qibla_open)

    def test_switching_it_off_in_settings_gives_the_small_screen_back_to_the_figure(self):
        w = self.window(side=True, qibla_start=False)
        w.begin()
        self.assertFalse(w.side.showing_compass)
        self.assertTrue(str(w.side.posture.path).endswith("standing_arms_down.png"))
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_the_posture_takes_the_small_screen_during_a_prayer_and_gives_it_back(self):
        w = self.window(side=True)
        w.begin()
        entry = [e for e in w.school.prayers["fajr"] if e.kind == "farz"][0]
        w.open_prayer("fajr")
        w.start("fajr", entry)
        self.assertFalse(w.side.showing_compass, "the posture needs the whole screen")
        w.stop()
        self.assertTrue(w.side.showing_compass, "back to the Qibla afterwards")
        self.assertEqual(1, w.side.posture.badge.count, "no X3 left over")

    def test_settings_has_the_qibla_rows(self):
        w = self.window()
        texts = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        texts += [x.text() for x in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]
        self.assertTrue([t for t in texts if "Qibla" in t])

    def test_with_no_chip_fitted_it_says_which_way_to_line_the_mat_up(self):
        w = self.window()
        w.begin()
        w.compass_screen.tick()
        self.assertIsNone(w.compass_screen.heading, "no compass chip in the test")
        self.assertIn("118", w.compass_screen.bearing.text(), "the bearing from Bury")


class SettingsFootTest(unittest.TestCase):
    """The foot of the Settings screen: the version, and no way out to the desktop."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def words(self, w):
        texts = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        return texts + [x.text() for x in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]

    def test_it_says_which_version_this_is(self):
        from salaah import __version__
        self.assertIn(f"Version {__version__}", self.words(self.window()))

    def test_the_version_can_be_compared_with_another_one(self):
        """It used to be the string "1", which cannot answer "is the one being offered newer".
        Updating rests on that question having an answer."""
        from salaah import __version__
        from salaah.update import newer
        self.assertIn(".", __version__, "a single number cannot be ordered against a later one")
        self.assertTrue(newer(__version__, "1.0"))
        self.assertFalse(newer(__version__, __version__))

    def test_there_is_no_way_out_to_the_desktop(self):
        w = self.window()
        self.assertFalse([t for t in self.words(w) if "desktop" in t.lower()])
        for button in w.settings_screen.findChildren(QtWidgets.QAbstractButton):
            self.assertNotEqual("link", button.objectName(), f"{button.text()!r} leaves the app")

    def test_every_language_has_the_version_line_and_not_the_old_exit_one(self):
        packs = available_packs(ASSETS)
        for lang, pack in full_packs(packs).items():
            self.assertIn("{number}", pack.ui.get("settings.version", ""), lang)
            self.assertNotIn("settings.exit", pack.ui, f"{lang} still offers the desktop")

    def test_no_choice_is_ever_squeezed(self):
        """A squeezed row of choices loses the bottom edge of its lettering, which is what the
        scroller is there to prevent. Checked in every language, from the mat's own screen down
        to a small window."""
        for lang in sorted(full_packs(available_packs(ASSETS))):
            for size in ((1920, 1200), (1920, 1080), (1280, 720)):
                w = self.window(lang=lang)
                w.resize(*size)
                w.stack.setCurrentWidget(w.settings_screen)
                APP.processEvents()
                for button in w.settings_screen.findChildren(QtWidgets.QRadioButton):
                    if not button.isVisible():
                        continue
                    wanted = button.sizeHint().height()
                    self.assertGreaterEqual(
                        button.height(), wanted - 1,
                        f"{lang} at {size}: {button.text()!r} squeezed to {button.height()} "
                        f"of {wanted}")

    def test_the_mats_own_screen_needs_no_scrolling(self):
        w = self.window(lang="en")
        w.resize(1920, 1200)
        w.stack.setCurrentWidget(w.settings_screen)
        APP.processEvents()
        self.assertEqual(0, w.settings_scroll.verticalScrollBar().maximum(),
                         "everything should fit on the 16 inch screen without a scrollbar")

    def test_a_common_monitor_needs_no_scrolling_either(self):
        """1920x1080 used to be 80px short and scrolled; the rows taken out of Settings since
        have bought that back."""
        w = self.window(lang="en")
        w.resize(1920, 1080)
        w.stack.setCurrentWidget(w.settings_screen)
        APP.processEvents()
        self.assertEqual(0, w.settings_scroll.verticalScrollBar().maximum())

    def test_a_screen_too_short_for_it_scrolls_instead_of_squeezing(self):
        w = self.window(lang="en")
        w.resize(1280, 720)
        w.stack.setCurrentWidget(w.settings_screen)
        APP.processEvents()
        bar = w.settings_scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0, "it should scroll rather than squeeze")
        bar.setValue(bar.maximum())
        APP.processEvents()
        bottom = w.settings_scroll.widget().height()
        self.assertLessEqual(bottom - bar.value(), w.settings_scroll.viewport().height() + 1,
                             "the last section can be scrolled to")


class UrduTest(unittest.TestCase):
    """Urdu: the meaning is in the Arabic script, so it runs right to left like the Arabic."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_it_is_laid_out_right_to_left_in_the_arabic_face(self):
        from salaah.render import Fonts
        w = self.window(lang="ur")
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        self.assertIn("رکعت", w.text_pages[0].arabic[0], "the intention is in Urdu")
        self.assertTrue(w.slide.arabic.rtl, "and runs right to left")
        while w.current_page.recitation != "fatiha":
            w.session.next()
        w.refresh()
        APP.processEvents()
        box = w.slide.parallel
        self.assertTrue(box.isVisible())
        self.assertTrue(box.meaning_rtl)
        self.assertEqual(Fonts.arabic(w.settings.arabic_font), box.meaning_family)
        px, rows, total = box.layout()
        self.assertLessEqual(total, box.height())
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "41-urdu-fatiha.png"))

    def test_english_stays_left_to_right(self):
        from salaah.render import Fonts
        w = self.window(lang="en")
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        while w.current_page.recitation != "fatiha":
            w.session.next()
        w.refresh()
        self.assertFalse(w.slide.parallel.meaning_rtl)
        self.assertEqual(Fonts.english_family, w.slide.parallel.meaning_family)


class MainScreenMarkTest(unittest.TestCase):
    """Which prayer it is now: its time in green in the banner, no box on the arch."""

    def test_the_time_of_the_prayer_due_is_green(self):
        from datetime import datetime
        from unittest import mock
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0, save_settings=False)
        self.addCleanup(lambda: shut(w))
        w.resize(1920, 1080)
        w.show()
        times = w.prayer_times()
        noon = datetime.combine(datetime.now().date(), times["dhuhr"])
        with mock.patch("salaah.ui.datetime") as clock:
            clock.now.return_value = noon
            clock.combine = datetime.combine
            w.tick()
        text = w.times_label.text()
        from salaah import theme
        green = theme.palette().green
        self.assertIn(f'<span style="color:{green}">Dhuhr', text, "Dhuhr's time is green")
        # The green ones, not every coloured word on the strip: the place beside them is
        # written in blue now, and counting all the spans counted that too.
        self.assertEqual(1, text.count(f'color:{green}'), "only the prayer due is green")
        self.assertNotIn(f'color:{green}">Fajr', text)

    def test_no_glow_is_drawn_over_an_arch(self):
        import inspect
        from salaah import mosque
        source = inspect.getsource(mosque.MosqueScreen.paintEvent)
        self.assertNotIn("glow_for", source, "no yellow box over the lit arch")
        self.assertIn("name_in_green", source, "the prayer's name on the arch turns green")
        self.assertIn("draw_minaret_glow", source, "the minarets still glow when none is due")

    def test_the_name_on_the_arch_is_stencilled_in_green(self):
        from salaah import mosque
        from salaah.qt import QtGui
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0, save_settings=False)
        self.addCleanup(lambda: shut(w))
        w.resize(1920, 1080)
        w.show()
        APP.processEvents()
        screen = w.mosque
        arch = next(a for a in screen.arches if a.prayer == "dhuhr")
        _, _, scale = screen.placement()
        pix = screen.name_in_green(arch, scale)
        self.assertFalse(pix.isNull())
        image = pix.toImage()
        image = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
        # pixelColor, not QColor(pixel()): QColor of a plain int means a named colour.
        sampled = [image.pixelColor(x, y)
                   for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)]
        painted = [c for c in sampled if c.alpha() > 200]
        self.assertTrue(painted, "some of the lettering is painted")
        # Which green follows the panel the name sits on, not the screen. This artwork is drawn
        # for the dark screen, so on the white one it is turned over and the panel comes out
        # black -- where the lighter green is the one that reads.
        green = mosque.GREEN_DARK if screen.flipped else mosque.GREEN
        for colour in painted:      # scaling shifts a channel by a point or two
            for got, want in ((colour.red(), green.red()),
                              (colour.green(), green.green()),
                              (colour.blue(), green.blue())):
                self.assertAlmostEqual(want, got, delta=4, msg=f"green, got {colour.name()}")
        share = len(painted) / len(sampled)
        self.assertLess(share, 0.5, "the lettering and outline, not the whole arch")
        self.assertGreater(share, 0.02, "and more than a stray pixel")


class SkyAndPolishTest(unittest.TestCase):
    """The dome clock, the line between the two columns, the beads, and the sky."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_clock_has_room_and_sits_higher(self):
        from salaah import mosque
        w = self.window()
        screen = w.mosque
        box = QtCore.QRect(100, 100, 200, 60)
        where = screen.clock_rect(box)
        self.assertGreater(where.width(), box.width(), "room either side, so nothing is clipped")
        self.assertLess(where.y(), box.y(), "lifted towards the middle of the dome")
        self.assertEqual(box.center().x(), where.center().x(), "still centred on the dome")
        # The room is what stops the lettering being clipped at whatever size it ends up.
        # It used to be wider than the box itself; since the time was trimmed it need not be,
        # so what is checked is the thing that still has to hold -- that it fits in the room.
        font = screen.clock_type(box, "23:59")
        self.assertLessEqual(QtGui.QFontMetrics(font).horizontalAdvance("23:59"), where.width())
        self.assertGreater(QtGui.QFontMetrics(font).horizontalAdvance("23:59"), box.width() * 0.6,
                           "the time has shrunk to nothing on the dome")

    def test_the_line_between_the_columns_is_the_colour_of_the_words(self):
        """Black by day and white after dark, like everything else that is drawn."""
        from salaah import theme
        for mode in ("light", "dark"):
            w = self.window(lang="en", theme=mode)
            entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
            w.open_prayer("dhuhr")
            w.start("dhuhr", entry)
            while w.current_page.recitation != "fatiha":
                w.session.next()
            w.refresh()
            APP.processEvents()
            box = w.slide.parallel
            shot = box.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
            ink = QtGui.QColor(theme.palette().ink)
            arabic_width, meaning_width, gap = box.columns()
            middle = box.width() - arabic_width - gap // 2
            found = [x for x in range(middle - 6, middle + 7)
                     for y in (shot.height() // 2,)
                     if shot.pixelColor(x, y) == ink]
            self.assertTrue(found, f"{mode}: no {ink.name()} line down the middle of the gap")
            green = QtGui.QColor(theme.palette().green)
            self.assertFalse([x for x in range(middle - 6, middle + 7)
                              for y in (shot.height() // 2,)
                              if shot.pixelColor(x, y) == green],
                             f"{mode}: the line is still green")


    def test_a_finished_bead_is_green_and_its_count_red(self):
        from salaah import tasbih, theme
        w = self.window()
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        while not w.session.finished:
            w.session.next()
        w.refresh()
        APP.processEvents()
        beads = w.slide.tasbih.beads
        for _ in range(beads.beads[0].count):
            beads.press()
        self.assertEqual(0, beads.left[0], "the first bead is done")
        self.assertEqual(theme.palette().green.lower(), tasbih.finished().name(), "and fills green")
        self.assertEqual(theme.palette().highlight.lower(), tasbih.saying().name(), "counts in red")
        shot = beads.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
        name, circle, number = beads.geometry_for(0)
        middle = circle.center().toPoint()
        self.assertEqual(QtGui.QColor(theme.palette().green).name(),
                         shot.pixelColor(middle.x(), middle.y()).name().lower(),
                         "the bead is filled green")
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "42-beads-green.png"))

    def test_stars_twinkle_at_night_and_birds_flutter_by_day(self):
        from salaah.mosque import Sky
        sky = Sky()
        self.assertTrue(sky.stars and sky.birds)
        bright = {sky.star_alpha(t, p, moment) for _, _, t, p in sky.stars for moment in (0, 1.4)}
        self.assertGreater(len(bright), 4, "they are not all the same brightness")
        for alpha in bright:
            self.assertTrue(0 <= alpha <= 255)
        first = sky.bird_at(sky.birds[0], 0.0)
        later = sky.bird_at(sky.birds[0], 3.0)
        self.assertNotEqual(first[0], later[0], "birds drift across")
        self.assertNotEqual(first[2], later[2], "and flap as they go")

    def test_the_sky_only_moves_while_the_main_screen_is_up(self):
        w = self.window()
        self.assertTrue(w.mosque.flutter.isActive(), "moving while the mosque is on show")
        w.open_prayer("fajr")
        APP.processEvents()
        self.assertFalse(w.mosque.flutter.isActive(), "and stopped once it is not")
        # go_home lands on the front door now, which has a sky of its own and does not run
        # this clock at all -- so the mosque is reached the way a person reaches it, through
        # the door.
        w.leave_welcome()
        APP.processEvents()
        self.assertTrue(w.mosque.flutter.isActive())


class FigureTest(unittest.TestCase):
    """Whose posture pictures are shown: the set in assets/postures, or another beside it."""

    def setUp(self):
        import shutil
        import tempfile
        from salaah.content import load
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        shutil.copytree(ASSETS, self.root / "assets")
        self.assets = self.root / "assets"
        self.load = load
        for folder in (self.assets / "postures").glob("*"):     # start from the original set only
            if folder.is_dir():
                shutil.rmtree(folder)

    def window(self, **settings):
        w = MainWindow(self.load(self.assets), available_packs(self.assets),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def add_girl(self, names=("standing_folded.png", "ruku.png", "standing_arms_down.png")):
        import shutil
        folder = self.assets / "postures" / "girl"
        folder.mkdir(exist_ok=True)
        for name in names:
            shutil.copy(self.assets / "postures" / name, folder / name)
        (folder / "modes.json").write_text('{"ruku": 0.7}')
        return folder

    def test_with_one_set_there_is_nothing_to_choose(self):
        w = self.window()
        self.assertEqual(["boy"], w.content.figures)
        texts = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]
        self.assertNotIn("Girl", texts)

    def test_a_second_set_is_offered_and_used(self):
        self.add_girl()
        w = self.window()
        self.assertEqual(["boy", "girl"], w.content.figures)
        texts = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]
        self.assertIn("Girl", texts)
        self.assertIn("Boy", texts)
        w.set_figure("girl")
        self.assertEqual("girl", w.settings.figure)
        self.assertEqual(self.assets / "postures" / "girl" / "ruku.png",
                         w.picture("postures/ruku.png"))
        self.assertEqual(0.7, w.posture_modes["ruku"], "its own sizing is used")
        self.assertEqual(0.42, w.posture_modes["sujood"], "and the original's for the rest")

    def test_a_missing_picture_falls_back_to_the_original(self):
        self.add_girl()          # this set has three pictures; the rest come from the original
        w = self.window(figure="girl")
        self.assertEqual(self.assets / "postures" / "sujood.png", w.picture("postures/sujood.png"),
                         "no girl sujood yet: the original is shown")
        entry = [e for e in w.school.prayers["fajr"] if e.kind == "farz"][0]
        w.open_prayer("fajr")
        w.start("fajr", entry)
        APP.processEvents()
        self.assertTrue(str(w.slide.posture.path).endswith("standing_arms_down.png"))
        self.assertIn("girl", str(w.slide.posture.path), "the intention picture is hers")
        while w.current_page.recitation != "sujood_tasbih":
            w.session.next()
        w.refresh()
        self.assertNotIn("girl", str(w.slide.posture.path), "and sujood falls back")


class ShippedFigureSetsTest(unittest.TestCase):
    """The sets that ship with the app: every file named after a posture the app asks for."""

    def setUp(self):
        from salaah.content import load
        self.content = load(ASSETS)
        self.wanted = {"standing_arms_down", "standing_folded", "standing_itidal", "takbir_raised",
                       "qunut", "ruku", "sujood", "jalsa", "tashahhud", "salam"}

    def test_the_original_set_is_complete(self):
        have = {p.stem for p in (ASSETS / "postures").glob("*.png")}
        self.assertEqual(self.wanted, have)

    def test_every_other_set_is_named_from_the_same_list(self):
        for figure in self.content.figures[1:]:
            folder = ASSETS / "postures" / figure
            have = {p.stem for p in folder.glob("*.png")}
            self.assertTrue(have <= self.wanted, f"{figure}: unknown names {have - self.wanted}")
            self.assertTrue(have, f"{figure} has no pictures")

    def test_the_girl_set_is_here_and_complete(self):
        self.assertIn("girl", self.content.figures)
        have = {p.stem for p in (ASSETS / "postures" / "girl").glob("*.png")}
        self.assertEqual(set(), self.wanted - have,
                         "the girl falls back to the boy for these postures")


class ArchArtworkTest(unittest.TestCase):
    """The arch the unit screen is drawn from. It was traced off the mosque picture once and
    came out ragged; it is now built from a clean drawing by tools/build_arch.py."""

    def masks(self):
        folder = ASSETS / "mosque"
        outer = QtGui.QImage(str(folder / "arch-outer.png"))
        inner = QtGui.QImage(str(folder / "arch-inner.png"))
        self.assertFalse(outer.isNull(), "arch-outer.png is missing")
        self.assertFalse(inner.isNull(), "arch-inner.png is missing")
        return outer, inner

    @staticmethod
    def span(image, y):
        """Where the shape starts and stops across one row, or None on an empty row."""
        marks = [x for x in range(image.width()) if image.pixelColor(x, y).value() > 128]
        return (marks[0], marks[-1]) if marks else None

    def test_both_masks_are_the_same_size_and_big_enough_to_stay_sharp(self):
        outer, inner = self.masks()
        self.assertEqual(outer.size(), inner.size())
        self.assertGreaterEqual(outer.height(), 1200,
                                "too small: it is blown up to most of the screen's height")

    def test_the_sides_do_not_wobble(self):
        """Down the straight part of the arch the edge should not move at all. The old artwork
        wandered a couple of pixels a row, which is what read as fuzziness."""
        outer, _ = self.masks()
        height = outer.height()
        lefts = [self.span(outer, y)[0]
                 for y in range(int(height * 0.80), int(height * 0.98), 2)]
        self.assertGreater(len(lefts), 20)
        self.assertLessEqual(max(lefts) - min(lefts), 1,
                             "the arch's straight side wanders; rebuild it from the drawing")

    def test_the_outline_is_an_even_width_all_the_way_down(self):
        outer, inner = self.masks()
        height, width = outer.height(), outer.width()
        widths = []
        for y in range(int(height * 0.35), int(height * 0.99), 20):
            out, inn = self.span(outer, y), self.span(inner, y)
            if out is None or inn is None:
                continue
            widths += [inn[0] - out[0], out[1] - inn[1]]
        self.assertGreater(len(widths), 10)
        self.assertGreater(min(widths), 0, "somewhere the outline disappears altogether")
        self.assertLess(max(widths) - min(widths), width * 0.02,
                        f"the outline's width wanders between {min(widths)} and {max(widths)}")

    def test_the_arch_stands_open_on_its_base(self):
        outer, inner = self.masks()
        bottom = outer.height() - 1
        self.assertIsNotNone(self.span(inner, bottom),
                             "the base is closed off; the arch should stand on the ground")

    def test_neighbouring_arches_do_not_touch(self):
        """Four units side by side is the tightest case, so the arches need clear air between
        them or they read as one lump.

        About the arches the app draws for itself, which since 1.62 is the screen a prayer gets
        when it has no drawing of its own. Harry's drawings have the gaps drawn into them.
        """
        from salaah.mosque import ArchButton
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        w.open_prayer("dhuhr")
        APP.processEvents()
        arches = w.pick.findChildren(ArchButton)
        self.assertEqual(4, len(arches), "Dhuhr has four units")
        for one, next_one in zip(arches, arches[1:]):
            right = one.mapTo(w.pick, one.arch_rect().topRight()).x()
            left = next_one.mapTo(w.pick, next_one.arch_rect().topLeft()).x()
            self.assertGreater(left - right, 8, "these two arches are touching")


class ZoomIntoArchTest(unittest.TestCase):
    """Tapping an arch on the mosque walks into it before the units appear. It is a picture laid
    over the top, so the screen itself changes at once and is never left mid-animation."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        APP.processEvents()
        w.refresh()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_screen_changes_at_once_not_when_the_walk_ends(self):
        w = self.window()
        w.enter_prayer("asr")
        self.assertIs(w.pick, w.stack.currentWidget(), "the units are up straight away")
        self.assertEqual("asr", w.prayer)

    def test_a_tap_starts_the_walk_and_it_stops_by_itself(self):
        w = self.window()
        w.enter_prayer("asr")
        self.assertTrue(w.veil.running, "nothing is walking anywhere")
        self.assertTrue(w.veil.isVisible())
        w.veil.began -= w.veil.MS / 1000          # as if its time were up
        w.veil.tick()
        self.assertFalse(w.veil.running)
        self.assertFalse(w.veil.isVisible(), "it should get out of the way when it is done")

    def test_opening_a_prayer_any_other_way_is_left_alone(self):
        w = self.window()
        w.open_prayer("asr")
        self.assertFalse(w.veil.running, "only a tap on the mosque walks in")

    def test_it_walks_towards_the_arch_that_was_tapped(self):
        w = self.window()
        for prayer, side in (("fajr", "left"), ("isha", "right")):
            middle = w.mosque.arch_centre(prayer)
            self.assertIsNotNone(middle, prayer)
            if side == "left":
                self.assertLess(middle.x(), w.mosque.width() / 2, prayer)
            else:
                self.assertGreater(middle.x(), w.mosque.width() / 2, prayer)

    def test_the_arch_ends_up_in_the_middle_of_the_screen(self):
        w = self.window()
        w.enter_prayer("fajr")              # the left-most arch: the furthest to travel
        veil = w.veil
        start, _ = veil.frame(0.0)
        end, _ = veil.frame(1.0)
        centre = QtCore.QPointF(veil.width() / 2, veil.height() / 2)

        def where_the_arch_is(box):
            """The focus point, as it lands on screen for that frame."""
            grown = box.width() / (veil.picture.width() * veil.COARSE)
            return QtCore.QPointF(box.x() + veil.focus.x() * veil.COARSE * grown,
                                  box.y() + veil.focus.y() * veil.COARSE * grown)

        began = where_the_arch_is(start)
        ended = where_the_arch_is(end)
        self.assertGreater(abs(began.x() - centre.x()), 100, "Fajr does not start in the middle")
        self.assertLess(abs(ended.x() - centre.x()), 2, "and should finish in the middle")
        self.assertLess(abs(ended.y() - centre.y()), 2)

    def test_it_grows_and_thins_away(self):
        w = self.window()
        w.enter_prayer("dhuhr")
        veil = w.veil
        sizes, solids = [], []
        for along in (0.0, 0.25, 0.5, 0.75, 1.0):
            box, solid = veil.frame(along)
            sizes.append(box.width())
            solids.append(solid)
        self.assertEqual(sizes, sorted(sizes), "it should only ever get nearer")
        self.assertEqual(solids, sorted(solids, reverse=True), "and only ever thinner")
        self.assertAlmostEqual(sizes[-1] / sizes[0], veil.ZOOM, places=1)
        self.assertEqual(1.0, solids[0], "it starts as a straight copy of the mosque")
        self.assertEqual(0.0, solids[-1], "and ends invisible, or the units stay veiled")

    def test_the_walk_is_paced_by_the_clock_not_by_frames(self):
        """A slow Pi drops frames rather than running the walk in slow motion."""
        w = self.window()
        w.enter_prayer("asr")
        veil = w.veil
        veil.began -= veil.MS / 2000            # halfway through, in real time
        halfway = veil.how_far()
        self.assertGreater(halfway, 0.1)
        self.assertLess(halfway, 0.95)
        veil.began -= veil.MS                   # well past the end
        self.assertEqual(1.0, veil.how_far())

    def test_going_home_calls_the_walk_off(self):
        w = self.window()
        w.enter_prayer("asr")
        self.assertTrue(w.veil.running)
        w.go_home()
        self.assertFalse(w.veil.running)
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_nothing_to_photograph_is_not_a_crash(self):
        w = self.window()
        w.veil.start(QtGui.QPixmap(), QtCore.QRect(0, 0, 1920, 1200), QtCore.QPoint(10, 10))
        self.assertFalse(w.veil.running)
        w.veil.start(w.stack.grab(), QtCore.QRect(0, 0, 2, 2), QtCore.QPoint(1, 1))
        self.assertFalse(w.veil.running)


class ArchColoursTest(unittest.TestCase):
    """The unit arches are an outline on the page they sit on: white inside by day, black
    inside after dark. They used to be a cream panel, which showed as a grey slab."""

    def no_drawing(self):
        """Force the screen the app draws for itself, which since 1.62 is the fallback.

        Harry's five drawings replaced it, and the fallback is still there on purpose: it is
        what a prayer gets when its drawing is missing, and -- the case that matters -- when a
        drawing's arches do not match the units the school says the prayer has. These tests are
        about THAT screen, so they ask for it rather than being deleted along with the default.
        """
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)

    def arch(self, **settings):
        from salaah.mosque import ArchButton
        self.no_drawing()
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        w.open_prayer("fajr")
        APP.processEvents()
        return w, w.pick.findChildren(ArchButton)[0]

    def test_the_inside_is_the_colour_of_the_page(self):
        from salaah import theme
        for mode in ("light", "dark"):
            w, arch = self.arch(theme=mode)
            panel, border, text = arch.colours()
            self.assertEqual(QtGui.QColor(theme.palette().paper), panel,
                             f"{mode}: the arch is not the colour of the page behind it")
            self.assertEqual(QtGui.QColor(theme.palette().ink), border)
            self.assertEqual(QtGui.QColor(theme.palette().ink), text)

    def test_it_is_really_drawn_that_way(self):
        """Not just the colours it reports: the pixels in the belly of the arch."""
        from salaah import theme
        for mode, inside in (("light", "#ffffff"), ("dark", "#000000")):
            w, arch = self.arch(theme=mode)
            shot = arch.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
            box = arch.arch_rect()
            # just under the apex, inside the outline, clear of the number
            spot = shot.pixelColor(box.center().x(), box.y() + int(box.height() * 0.13))
            self.assertEqual(inside, spot.name().lower(),
                             f"{mode}: the inside of the arch is {spot.name()}")

    def test_the_two_themes_really_are_each_other_inverted(self):
        day = self.arch(theme="light")[1].colours()
        night = self.arch(theme="dark")[1].colours()
        for one, other in zip(day, night):
            self.assertEqual(255, one.red() + other.red(), "not an inversion")
            self.assertEqual(255, one.green() + other.green())
            self.assertEqual(255, one.blue() + other.blue())


class WalkLengthTest(unittest.TestCase):
    """How long the walk into an arch lasts."""

    def test_it_takes_a_second(self):
        from salaah.mosque import ZoomVeil
        self.assertEqual(1000, ZoomVeil.MS)

    def test_a_tap_part_way_through_cuts_it_short(self):
        """At a second there is time to reach for the arch you wanted before the walk ends, so
        a press clears the picture rather than leaving you looking at the old screen."""
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        w.enter_prayer("asr")
        self.assertTrue(w.veil.running)
        press = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress,
                                 QtCore.QPointF(400, 600), Qt.MouseButton.LeftButton,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        w.eventFilter(w, press)
        self.assertFalse(w.veil.running, "a tap should clear the walk")
        self.assertFalse(w.veil.isVisible())
        self.assertIs(w.pick, w.stack.currentWidget(), "and leave the units on screen")


class LineSpacingTest(unittest.TestCase):
    """The words are fitted to the box, so the space between the lines decides how large they
    come out. A font's own line height leaves room for every mark it could draw, not the ones
    this text has, so the room is measured from the text in hand."""

    def test_the_lines_are_closed_up_only_as_far_as_the_letters_allow(self):
        from salaah.render import Fonts, INK_ROOM, LEADING, ink_share, line_box
        Fonts.load(ASSETS)
        verses = load(ASSETS).arabic["fatiha"]
        for key in ("scheherazade", "noto", "amiri"):
            family = Fonts.arabic(key)
            if not family:
                continue
            share = ink_share(verses, family, 700)
            font = QtGui.QFont(family)
            font.setPixelSize(120)
            font.setWeight(QtGui.QFont.Weight(700))
            metrics = QtGui.QFontMetrics(font)
            box = line_box(verses, family, 700, metrics)
            self.assertLessEqual(box, metrics.height() + 1,
                                 f"{key}: lines further apart than the font itself asks")
            self.assertGreaterEqual(box / metrics.height(), LEADING - 0.01,
                                    f"{key}: closed up past what is allowed")
            self.assertGreaterEqual(box / metrics.height(), min(1.0, share + INK_ROOM) - 0.01,
                                    f"{key}: no room left for the vowel marks")

    def test_a_font_that_needs_its_room_keeps_it(self):
        """Amiri's letters fill nearly all of its line box, and must be left alone; the others
        have room to spare and should be closed up."""
        from salaah.render import Fonts, ink_share
        Fonts.load(ASSETS)
        verses = load(ASSETS).arabic["fatiha"]
        shares = {key: ink_share(verses, Fonts.arabic(key), 700)
                  for key in ("scheherazade", "noto", "amiri") if Fonts.arabic(key)}
        self.assertGreater(shares["amiri"], 0.85, "Amiri is meant to be the tight one")
        self.assertLess(shares["scheherazade"], 0.85, "Scheherazade has room to spare")

    def test_al_fatiha_is_larger_than_it_was(self):
        """The screen it fills is the seven-line one, where the leading cost the most.

        Measured with the Arabic across the whole screen, which is what this was about: with a
        meaning beside it the Arabic has half the width and is drawn at about 39px, and that
        is the layout working rather than the leading being wrong. Arabic only is how you ask
        for the full-width page now -- it used to be what a mat gave you by default.
        """
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False, lang="ar"), scale=1.0,
                       save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        while w.current_page.recitation != "fatiha":
            w.session.next()
        w.refresh()
        APP.processEvents()
        self.assertGreaterEqual(w.slide.arabic.fitted_size(), 76,
                                "Al-Fatiha was 64px before the leading was tightened")

    def test_no_line_is_clipped_or_run_into_the_next(self):
        """The whole point of measuring: the marks must survive. Every recitation of a fardh
        prayer, in every Arabic lettering, with and without the meaning beside it."""
        from salaah.render import lay_out_words
        for key in ("scheherazade", "noto", "amiri"):
            for reading in ("ar", "en"):      # Arabic alone, then with the meaning beside it
                w = MainWindow(load(ASSETS), available_packs(ASSETS),
                               Settings(theme="light", recitation=False, arabic_font=key,
                                        lang=reading),
                               scale=1.0, save_settings=False, aspect=None, side=True)
                w.resize(1920, 1200)
                w.show()
                APP.processEvents()
                entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
                w.open_prayer("dhuhr")
                w.start("dhuhr", entry)
                seen = set()
                for _ in range(45):
                    step = w.current_page.recitation
                    if step and step not in seen:
                        seen.add(step)
                        w.refresh()
                        APP.processEvents()
                        beside = reading != "ar"      # is there a meaning next to the Arabic
                        box = w.slide.parallel if beside else w.slide.arabic
                        if box.isVisible() and (box.arabic if beside else box.lines):
                            self.check(box, beside, f"{key}/{reading} {step}")
                    try:
                        w.session.next()
                    except Exception:
                        break
                w.shutdown()
                w.close()
                w.deleteLater()
                APP.processEvents()

    def check(self, box, translation, where):
        """Counts the bands of ink down the Arabic column. Fewer bands than there are rows means
        two lines have run into each other; ink on the very first or last row means it is being
        cut off. Diacritics make their own bands, so more than expected is fine."""
        from salaah.render import lay_out_words
        picture = box.grab().toImage()
        if translation:
            arabic_width, _, _ = box.columns()
            _, rows, _ = box.layout()
            left, right = box.width() - arabic_width, box.width()
            wanted = sum(len({word.y for word in arabic}) for arabic, _, _ in rows)
        else:
            placed, _ = lay_out_words(box.lines, box.width(), box.family, box.fitted_size(),
                                      box.weight, box.rtl, box.gap)
            left, right, wanted = 0, box.width(), len({word.y for word in placed})
        inked = [y for y in range(picture.height())
                 if any(picture.pixelColor(x, y).value() < 140 for x in range(left, right, 2))]
        if not inked:
            return
        bands = 1 + sum(1 for a, b in zip(inked, inked[1:]) if b > a + 1)
        self.assertGreaterEqual(bands, wanted, f"{where}: lines have run into each other")
        self.assertGreater(inked[0], 0, f"{where}: cut off at the top")
        self.assertLess(inked[-1], picture.height() - 1, f"{where}: cut off at the bottom")


class FullHeightRuleTest(unittest.TestCase):
    """The line between the two columns runs the whole height of every screen. It used to be
    drawn only as tall as that screen's words, so it grew and shrank recitation to recitation."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False,
                                   "lang": "en", **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def rule_run(self, box):
        """From which row to which does the line down the middle carry ink?"""
        picture = box.grab().toImage()
        arabic_width, _, gap = box.columns()
        middle = box.width() - arabic_width - gap // 2
        rows = [y for y in range(picture.height())
                if min(picture.pixelColor(x, y).value()
                       for x in range(middle - 3, middle + 4)) < 140]
        return (min(rows), max(rows), picture.height()) if rows else None

    def test_it_is_the_same_length_whatever_is_on_the_screen(self):
        w = self.window()
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        checked = 0
        seen = set()
        for _ in range(45):
            step = w.current_page.recitation
            if step and step not in seen:
                seen.add(step)
                w.refresh()
                APP.processEvents()
                box = w.slide.parallel
                if box.isVisible() and box.arabic:
                    run = self.rule_run(box)
                    self.assertIsNotNone(run, f"{step}: no line at all")
                    top, bottom, height = run
                    self.assertLessEqual(top, 1, f"{step}: the line starts {top}px down")
                    self.assertGreaterEqual(bottom, height - 2,
                                            f"{step}: the line stops {height - bottom}px short")
                    checked += 1
            try:
                w.session.next()
            except Exception:
                break
        self.assertGreater(checked, 6, "hardly any screens were checked")


class WalkIntoAUnitTest(unittest.TestCase):
    """Tapping one of a prayer's unit arches walks into it the same way the mosque does.

    Pointed at the drawn-for-itself screen since 1.62, which is the fallback: Harry's drawings
    have their own arches and their own walk, checked in PrayerPagesAreDrawnTest. The walk is
    the same ZoomVeil either way, and this is the place it is measured frame by frame, so it is
    kept here rather than rewritten against a picture.
    """

    def window(self):
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def arches(self, w, prayer="dhuhr"):
        from salaah.mosque import ArchButton
        w.open_prayer(prayer)
        APP.processEvents()
        return w.pick.findChildren(ArchButton)

    def test_a_tap_on_a_unit_walks_in_and_the_prayer_starts_at_once(self):
        w = self.window()
        arch = self.arches(w)[1]                     # Dhuhr's 4 Fardh
        arch.chosen.emit(arch.payload)
        APP.processEvents()
        self.assertIs(w.player, w.stack.currentWidget(), "the prayer should be up straight away")
        self.assertEqual("dhuhr", w.prayer)
        self.assertTrue(w.veil.running, "and the walk should be playing over it")

    def started_from(self, w):
        """Where on screen the walk's focus point sits at the very start: the arch tapped."""
        box, _ = w.veil.frame(0.0)
        grown = box.width() / (w.veil.picture.width() * w.veil.COARSE)
        return box.x() + w.veil.focus.x() * w.veil.COARSE * grown

    def test_it_walks_into_the_arch_that_was_tapped_not_the_first_one(self):
        w = self.window()
        self.assertEqual(4, len(self.arches(w)), "Dhuhr has four units")
        from_left = {}
        for which in (0, -1):
            w.go_home()
            arch = self.arches(w)[which]
            arch.chosen.emit(arch.payload)
            APP.processEvents()
            from_left[which] = self.started_from(w)
            w.veil.stop()
        self.assertLess(from_left[0], from_left[-1],
                        "both walks began at the same place, so the arch is being ignored")

    def test_it_takes_the_same_second_as_the_mosque(self):
        from salaah.mosque import ZoomVeil
        w = self.window()
        arch = self.arches(w)[0]
        arch.chosen.emit(arch.payload)
        self.assertEqual(1000, ZoomVeil.MS)
        self.assertTrue(w.veil.running)
        w.veil.began -= ZoomVeil.MS / 1000
        w.veil.tick()
        self.assertFalse(w.veil.running, "it should have finished by now")

    def test_starting_a_prayer_any_other_way_is_left_alone(self):
        w = self.window()
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        self.assertFalse(w.veil.running, "only a tap on an arch walks in")


class BannerAndDoneScreenTest(unittest.TestCase):
    """The rakat reads as one of the banner's boxes, and the prayer-complete screen is the two
    passages alone, each under a heading you can read across the room."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def at_the_end(self, w):
        """A sunnah prayer, run to its last screen: the one with the two passages."""
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "sunnah"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        while not w.session.finished:
            w.session.next()
        w.refresh()
        APP.processEvents()
        return w

    @staticmethod
    def painted(widget):
        """The colours a widget is actually drawn in: its most common pixel, and whether any of
        it is the colour of its lettering."""
        picture = widget.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
        tally = {}
        for y in range(0, picture.height(), 2):
            for x in range(0, picture.width(), 2):
                name = picture.pixelColor(x, y).name().lower()
                tally[name] = tally.get(name, 0) + 1
        return max(tally, key=tally.get), tally

    def test_the_rakat_is_a_box_like_the_others_in_the_banner(self):
        from salaah import theme
        for mode, chip in (("light", "#000000"), ("dark", "#262626")):
            w = self.window(theme=mode)
            self.at_the_end(w)
            self.assertEqual(w.title_label.height(), w.rakat_label.height(),
                             f"{mode}: the rakat box is a different height to the prayer's name")
            background, tally = self.painted(w.rakat_label)
            self.assertEqual(chip, background, f"{mode}: the rakat box is {background}")
            self.assertIn("#ffffff", tally, f"{mode}: the rakat is not written in white")

    def test_nothing_is_shown_when_a_prayer_finishes(self):
        """There was a hadith and a passage of the Qur'an for the day here, and Harry had it
        taken out: the mat has a Qur'an section and a hadith section of its own now, so a
        quotation nobody asked for at the end of a prayer was a page to get past rather than a
        page to read. Eight tests went with it; this is what is left of them."""
        w = self.window()
        self.at_the_end(w)
        self.assertFalse(w.slide.done.isVisible(), "something is still covering the last page")
        for gone in ("hadith_arabic", "quran_arabic", "hadith_source", "quran_source",
                     "show_daily", "match_daily_sizes"):
            self.assertFalse(hasattr(w, gone), f"{gone} is still here")
        words = [x.text() for x in w.slide.findChildren(QtWidgets.QLabel) if x.text()]
        for lang, pack in full_packs(available_packs(ASSETS)).items():
            for key in ("daily.hadith", "daily.quran"):
                said = pack.ui.get(key, "")
                if said:
                    self.assertNotIn(said, words, f"{lang} still shows {key}")

    def test_what_fed_that_page_was_taken_out_with_it(self):
        """The page went in 1.49; what it read stayed on the disk until 1.57.

        Two files of scripture nothing opened, three strings in each of six packs, a dataclass,
        and the loader that filled it -- about forty kilobytes on a card that is 95% full, and
        more to the point, content carrying its own copies of Qur'an verses and hadith that no
        reviewer would ever think to check because nothing shows it.
        """
        self.assertFalse((ASSETS / "content" / "daily").exists(),
                         "assets/content/daily is still on the disk")
        from salaah import content as content_module
        self.assertFalse(hasattr(content_module, "Daily"), "the Daily class is still here")
        self.assertFalse(hasattr(CONTENT, "daily"), "Content still carries a daily field")
        for lang, pack in full_packs(available_packs(ASSETS)).items():
            left = sorted(k for k in pack.ui if k.startswith("daily."))
            self.assertEqual([], left, f"{lang} still has {left}")



class MenusAreDrawnInEveryLanguageTest(unittest.TestCase):
    """Harry drew the du'a, hadith and 7in menus again in each language the mat speaks.

    The words on these tiles are part of the picture, not text laid over it, so following the
    language means showing a different film -- not relabelling anything. Seven films per menu,
    twenty-one in all, and one set of touch boxes serving the lot.
    """

    MENUS = (("hadith-menu", "hadith_menu"), ("duas-menu", "dua_menu"))

    def window(self, lang):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def described(self, folder):
        return json.loads((ASSETS / folder / "menu.json").read_text(encoding="utf-8"))

    def test_every_language_has_its_own_film_of_every_menu(self):
        for folder in ("hadith-menu", "duas-menu", "knowledge"):
            films = self.described(folder).get("films", {})
            with self.subTest(folder):
                self.assertEqual(set(WRITTEN_IN) | {ARABIC_ONLY}, set(films))
                for lang, name in films.items():
                    path = ASSETS / folder / name
                    self.assertTrue(path.is_file(), f"{folder}/{name} is missing")
                    self.assertGreater(path.stat().st_size, 20_000, f"{name} is suspiciously small")

    def test_the_mat_shows_the_film_of_the_language_it_is_set_to(self):
        for lang in ("fr", "ur", "zh", ARABIC_ONLY, "en"):
            with self.subTest(lang):
                for folder, _ in self.MENUS:
                    chose = FilmSheet.sheet_for(self.described(folder), lang)
                    want = self.described(folder)["films"][lang]
                    self.assertEqual(want, chose)

    def test_a_language_with_no_film_drawn_falls_back_to_english(self):
        """Rather than to nothing. A menu in the wrong language still works; a menu that is
        not there is a black screen with eighteen invisible buttons on it."""
        described = self.described("hadith-menu")
        self.assertEqual(described["films"]["en"], FilmSheet.sheet_for(described, "sw"))
        self.assertEqual(described["films"]["en"], FilmSheet.sheet_for(described, ""))

    def test_one_set_of_boxes_serves_them_all(self):
        """The claim that lets there be one menu.json for seven films.

        Every sheet was drawn to the same grid. This measures how far the tiles actually move
        between the English drawing and each of the others -- it was seven pixels at worst on
        a 304px tile, a fiftieth of a tile and a fraction of a fingertip. If a redrawn sheet
        ever shifts its grid, the touch targets would quietly stop matching the pictures and
        nothing else would notice.
        """
        from PIL import Image
        for folder, attr in self.MENUS:
            described = self.described(folder)
            wide, tall = described["size"]
            for lang, name in described["films"].items():
                with self.subTest(f"{folder} {lang}"):
                    with Image.open(ASSETS / folder / name) as film:
                        self.assertEqual((wide, tall), film.size,
                                         f"{name} is not the size the boxes were cut at")

    def test_the_tiles_still_open_their_own_sections_in_another_language(self):
        """A film per language must not mean a menu per language: the same eighteen names,
        in the same places, whatever is written on them."""
        from salaah.duamenu import SAYINGS
        # Opened, not just built: the targets are placed on showEvent, so reading geometry off
        # a menu that was never shown compares against a widget still sat at the origin. The
        # first run of this test did exactly that and reported every tile as having moved.
        base = self.window("en")
        base.open_corner("hadith")
        settle()
        english = {t.name: t.geometry() for t in base.hadith_menu.tiles}
        for lang in ("ur", ARABIC_ONLY):
            with self.subTest(lang):
                w = self.window(lang)
                w.open_corner("hadith")
                settle()
                tiles = {t.name: t.geometry() for t in w.hadith_menu.tiles}
                self.assertEqual(set(SAYINGS), set(tiles))
                for name, box in tiles.items():
                    moved = max(abs(box.x() - english[name].x()),
                                abs(box.y() - english[name].y()))
                    self.assertLess(moved, 12, f"{name} has moved {moved}px in {lang}")


class NasheedPlayerTest(unittest.TestCase):
    """The nasheeds tile: a shelf of whatever is in the owner's own folder.

    Nothing ships. See the note at the top of nasheeds.py -- the artists are on labels, the
    sites offering their work "copyright free" are aggregators who do not hold the rights, and
    a device carrying that is Phantom Interactive distributing somebody else's record. So the
    mat reads ~/.salaah/nasheeds, the folder beside the recitation cache that no release ever
    touches, and plays what it finds.
    """

    class FakeCall:
        """Stands in for audio.Call. The real one shells out to ffplay, which is neither
        present nor wanted in a test; FakePlayer further down is the wrong shape -- it stands
        in for Recitation, whose play() takes a span and a repeat count."""

        def __init__(self):
            self.on, self.played, self.stops = False, [], 0

        @property
        def playing(self):
            return self.on

        def play(self, audio):
            self.played.append(Path(audio).name)
            self.on = True
            return True

        def stop(self):
            self.stops += 1
            self.on = False

    def shelf(self, *names):
        import shutil
        room = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(room, ignore_errors=True))
        for name in names:
            (room / name).write_bytes(b"ID3" + b"\0" * 2000)
        return room

    def window(self, room=None, lang="en"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        if room is not None:
            w.nasheeds.folders = [ASSETS / "nasheeds", room]
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def open(self, w):
        w.open_corner("nasheeds")
        settle()
        return w.nasheed_screen

    # What is on the shelf

    def test_the_tile_opens_the_shelf_rather_than_nothing_here_yet(self):
        w = self.window(self.shelf("one.mp3"))
        self.assertIs(self.open(w), w.corner_screen.currentWidget())
        self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget())

    def test_it_lists_what_is_in_the_owners_folder(self):
        w = self.window(self.shelf("allah-knows.mp3", "tala-al-badru.m4a"))
        screen = self.open(w)
        self.assertEqual(["allah knows", "tala al badru"],
                         sorted(t.title for t in screen.rows_for))

    def test_things_that_are_not_recordings_are_left_out(self):
        """The folder is one a person drops files into, so it collects cover art and whatever
        the operating system leaves lying about. A row with a play button on a .DS_Store is
        the mat looking broken."""
        w = self.window(self.shelf("real.mp3", "cover.jpg", ".DS_Store", "notes.txt"))
        screen = self.open(w)
        self.assertEqual(["real"], [t.title for t in screen.rows_for])

    def test_an_empty_folder_says_where_to_put_them(self):
        """The ordinary state of this screen on a new mat. It has to be more use than a blank
        page -- somebody has to be able to find out that the folder exists at all."""
        from salaah.nasheeds import MINE
        w = self.window(self.shelf())
        screen = self.open(w)
        self.assertEqual([], screen.rows_for)
        self.assertTrue(screen.empty.isVisible())
        self.assertFalse(screen.scroll.isVisible())
        self.assertIn(str(MINE), screen.empty.text(), "it does not say which folder")

    def test_a_file_dropped_in_while_the_mat_is_running_turns_up(self):
        """Which is how it will actually be used -- a USB stick, not a restart."""
        room = self.shelf("first.mp3")
        w = self.window(room)
        screen = self.open(w)
        self.assertEqual(1, len(screen.rows_for))
        (room / "second.mp3").write_bytes(b"ID3" + b"\0" * 2000)
        w.go_home()
        settle()
        self.open(w)
        self.assertEqual(2, len(screen.rows_for), "the new file was not noticed")

    # Playing one

    def test_pressing_a_row_plays_it_and_pressing_it_again_stops(self):
        w = self.window(self.shelf("one.mp3", "two.mp3"))
        screen = self.open(w)
        screen.player = self.FakeCall()
        first = screen.rows_for[0]
        screen.touched(first)
        self.assertIs(first, screen.playing)
        screen.touched(first)
        self.assertIsNone(screen.playing, "pressing the playing one did not stop it")

    def test_only_one_plays_at_a_time(self):
        w = self.window(self.shelf("one.mp3", "two.mp3"))
        screen = self.open(w)
        screen.player = self.FakeCall()
        one, two = screen.rows_for
        screen.touched(one)
        screen.touched(two)
        self.assertIs(two, screen.playing)
        self.assertEqual(1, sum(1 for i, _ in enumerate(screen.rows_for)
                                if screen.rows.itemAt(i).widget().isChecked()))

    def test_leaving_the_screen_stops_the_sound(self):
        """A nasheed playing on from behind the Qur'an would have no way to be stopped."""
        w = self.window(self.shelf("one.mp3"))
        screen = self.open(w)
        screen.player = self.FakeCall()
        screen.touched(screen.rows_for[0])
        self.assertIsNotNone(screen.playing)
        w.go_home()
        settle()
        self.assertIsNone(screen.playing, "it is still playing behind another screen")

    # The two interactions that matter on a prayer mat

    def test_the_screen_does_not_go_dark_in_the_middle_of_one(self):
        """The same rule the du'as and the Qur'an already have. Going dark over a nasheed is
        the same rudeness as going dark over a surah."""
        w = self.window(self.shelf("one.mp3"))
        screen = self.open(w)
        screen.player = self.FakeCall()
        self.assertFalse(w.saying_a_passage())
        screen.touched(screen.rows_for[0])
        self.assertTrue(w.saying_a_passage(), "the sleep timer would cut it off")

    def test_a_prayer_falling_due_stops_the_nasheed(self):
        """Two things singing at once is the worst version of this, and of the two it is not
        the call to prayer that should give way.

        TWO things stop it and this tests the one that is meant to. call_to_prayer goes home
        on its way to the call, which hides this screen, and hideEvent stops the sound -- so
        the first version of this test passed with the explicit stop commented out, and would
        have gone on passing if it were deleted. Going home is incidental: it stops a nasheed
        because of where the screen went, not because a prayer is due. So the way home is
        stubbed out here, which leaves only the deliberate guard to do the job.
        """
        w = self.window(self.shelf("one.mp3"))
        screen = self.open(w)
        screen.player = self.FakeCall()
        screen.touched(screen.rows_for[0])
        self.assertIsNotNone(screen.playing)
        w.go_home = lambda *a, **k: None          # the incidental one, held still
        w.call_to_prayer("maghrib")
        settle()
        self.assertIsNone(screen.playing, "the nasheed sang over the muezzin")

    def test_and_walking_away_from_the_screen_stops_it_as_well(self):
        """The incidental one, which is worth having on purpose: whatever takes the screen
        away -- the call, the front door, a prayer starting -- leaves no sound behind it."""
        w = self.window(self.shelf("one.mp3"))
        screen = self.open(w)
        screen.player = self.FakeCall()
        screen.touched(screen.rows_for[0])
        w.call_to_prayer("maghrib")
        settle()
        self.assertIsNone(screen.playing)
        self.assertFalse(screen.player.playing)

    # The rule about what ships

    def test_nothing_ships_with_the_mat(self):
        """The guard on the whole arrangement.

        assets/nasheeds is read, so that something properly licensed could one day sit there.
        Until a LICENCE.txt beside it says what the tracks are and on what terms, there must be
        no audio in it -- because "we will sort the licence out later" is exactly how an mp3
        ends up in a release, and a release is the thing that is hard to take back.
        """
        from salaah.nasheeds import SOUNDS
        folder = ASSETS / "nasheeds"
        audio = [p.name for p in folder.iterdir()
                 if p.is_file() and p.suffix.lower() in SOUNDS] if folder.is_dir() else []
        if audio:
            licence = folder / "LICENCE.txt"
            self.assertTrue(licence.is_file(),
                            f"{audio} ship with the mat and there is no LICENCE.txt saying "
                            f"what they are or who said they could")
            said = licence.read_text(encoding="utf-8")
            for name in audio:
                self.assertIn(Path(name).stem, said,
                              f"{name} ships and the licence file does not mention it")

    def test_the_owners_folder_is_outside_everything_a_release_touches(self):
        """It must not be under assets/ or salaah/, the two folders an update replaces whole."""
        from salaah.nasheeds import MINE
        for name in ("assets", "salaah"):
            self.assertNotIn(name, MINE.parts,
                             f"the owner's nasheeds are inside {name}, which updates replace")
        self.assertIn(".salaah", MINE.parts, "it should sit beside the recitation cache")

    def test_every_language_can_say_the_folder_is_empty(self):
        for lang, pack in available_packs(ASSETS).items():
            with self.subTest(lang):
                said = pack.ui.get("nasheeds.empty", "")
                self.assertTrue(said.strip(), f"{lang} cannot say the shelf is empty")
                self.assertIn("{folder}", said, f"{lang} does not say which folder")


class ArrowsPointTheWayTheReadingGoesTest(unittest.TestCase):
    """Back and forward arrows, on a mat that is sometimes laid out right to left.

    Qt mirrors a row of buttons when the app reads right to left, which is correct -- in Urdu
    and Arabic the first thing you come to is the one on the RIGHT. What it cannot do is turn
    the arrowhead round, so the pair moved to the other corner with "‹" still pointing left
    while sitting in the position that means "onward". The glyph said one thing and its place
    said the other.

    Three screens had it: the wu'du step, the Qur'an and the du'a reader. The rule is the same
    for all three -- back points the way you came from, which is left in English and right in
    Urdu -- so it lives in one function and this tests all three against it.
    """

    SCREENS = ("wudu", "quran", "duas")

    def window(self, lang):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def pair(self, w, screen):
        """(back button, onward button) on that screen, once it is up."""
        if screen == "wudu":
            w.open_wudu_step("face")
            settle()
            return w.wudu_step.back_button, w.wudu_step.on_button
        if screen == "quran":
            w.open_surah(2)
            settle()
            return w.reader.earlier, w.reader.later
        w.open_passage("duas", 0)
        settle()
        reader = w.section_readers["duas"]
        return reader.earlier, reader.later

    def test_the_head_turns_with_the_layout(self):
        from salaah.qt import BACK_ARROW, ON_ARROW
        for lang, back_glyph, on_glyph in (("en", BACK_ARROW, ON_ARROW),
                                           ("fr", BACK_ARROW, ON_ARROW),
                                           ("ur", ON_ARROW, BACK_ARROW),
                                           ("ar", ON_ARROW, BACK_ARROW)):
            w = self.window(lang)
            for screen in self.SCREENS:
                with self.subTest(f"{lang}.{screen}"):
                    back, on = self.pair(w, screen)
                    self.assertEqual(back_glyph, back.text(), "back points the wrong way")
                    self.assertEqual(on_glyph, on.text(), "onward points the wrong way")

    def test_the_arrow_points_where_the_button_sits(self):
        """The whole point, stated as the thing a person actually sees: whichever button is on
        the left has the left-pointing arrow on it, in every language."""
        from salaah.qt import BACK_ARROW
        for lang in ("en", "fr", "ur", "ar", "zh"):
            w = self.window(lang)
            for screen in self.SCREENS:
                with self.subTest(f"{lang}.{screen}"):
                    back, on = self.pair(w, screen)
                    parent = back.parentWidget()
                    here = back.mapTo(parent, back.rect().center()).x()
                    there = on.mapTo(parent, on.rect().center()).x()
                    leftmost = back if here < there else on
                    self.assertEqual(BACK_ARROW, leftmost.text(),
                                     f"the button on the left is {leftmost.text()!r}, which "
                                     f"points away from it")

    def test_back_is_the_first_one_reached_in_the_reading_direction(self):
        """In English you read left to right and meet Back first; in Urdu you read right to
        left and should still meet Back first. That is the layout mirroring doing its job, and
        it is what makes the swapped glyphs right rather than a cosmetic fiddle."""
        for lang, rtl in (("en", False), ("ur", True), ("ar", True)):
            w = self.window(lang)
            for screen in self.SCREENS:
                with self.subTest(f"{lang}.{screen}"):
                    back, on = self.pair(w, screen)
                    parent = back.parentWidget()
                    here = back.mapTo(parent, back.rect().center()).x()
                    there = on.mapTo(parent, on.rect().center()).x()
                    if rtl:
                        self.assertGreater(here, there, "back is not the first one reached")
                    else:
                        self.assertLess(here, there, "back is not the first one reached")

    def test_the_two_glyphs_are_not_the_same_character(self):
        """A swap that returned the same glyph twice would pass every test above by accident."""
        from salaah.qt import BACK_ARROW, ON_ARROW, arrows
        self.assertNotEqual(BACK_ARROW, ON_ARROW)
        self.assertEqual((BACK_ARROW, ON_ARROW), arrows(False))
        self.assertEqual((ON_ARROW, BACK_ARROW), arrows(True))


class ListSliderIsThickEnoughForAThumbTest(unittest.TestCase):
    """The slider down the side of the surah list, and the other lists that share it.

    A desktop draws this 14px wide, which is a target for a mouse pointer. It went to 42 when
    the lists were built and Harry asked for it thicker again after dragging it on glass, so
    it is 56 -- about a centimetre on the mat's screen, which is the width of the thumb doing
    the dragging rather than the width of a line somebody thought looked right.
    """

    def window(self, lang="en"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_surah_list_slider_is_drawn_at_the_width_asked_for(self):
        from salaah.reading import LIST_BAR
        w = self.window()
        w.open_corner("quran")
        settle(8)
        bar = w.surah_list.scroll.verticalScrollBar()
        self.assertTrue(bar.isVisible(), "there is no slider on a list of 114")
        self.assertGreaterEqual(bar.width(), int(LIST_BAR * w.s) - 2,
                                f"the slider came out {bar.width()}px")

    def test_it_is_thicker_than_it_was_and_far_thicker_than_a_desktops(self):
        """Measured against the two numbers that mean something: 14px is what Qt gives a
        mouse, and 42 is where this was before Harry used it."""
        from salaah.reading import LIST_BAR
        self.assertGreater(LIST_BAR, 42, "no thicker than it already was")
        self.assertGreater(LIST_BAR, 14 * 3)
        self.assertLess(LIST_BAR, 90, "a slider, not a column")

    def test_the_list_gives_up_the_width_rather_than_being_sat_on(self):
        """A fatter slider must take its room out of the rows, not cover them. The rows are
        what somebody is aiming at, and a surah with its last word under the slider is worse
        than a thin slider."""
        w = self.window()
        w.open_corner("quran")
        settle(8)
        bar = w.surah_list.scroll.verticalScrollBar()
        inner = w.surah_list.scroll.widget()
        self.assertLessEqual(inner.width(), w.surah_list.scroll.width() - bar.width() + 2,
                             "the rows run underneath the slider")


class WuduFollowsTheLanguageTest(unittest.TestCase):
    """The wu'du section in the language the mat is set to -- the drawings and the words.

    Two halves, which failed for two different reasons. The seven tall tiles have their
    numbers and headings DRAWN INTO them, so following the language means loading a different
    file; Harry redrew the sheet in each language and they are cut beside the English ones as
    step-hands.fr.png and so on. The paragraph under a step is text, and it was English
    whatever the mat was set to, because there was only English in the file.
    """

    KEYS = ("hands", "mouth", "nose", "face", "arms", "head", "feet")

    def window(self, lang="en"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_every_language_has_its_own_drawing_of_every_step(self):
        for lang in WRITTEN_IN + (ARABIC_ONLY,):
            for key in self.KEYS:
                with self.subTest(f"{lang}.{key}"):
                    name = f"step-{key}.png" if lang == "en" else f"step-{key}.{lang}.png"
                    path = ASSETS / "wudu" / name
                    self.assertTrue(path.is_file(), f"{name} is missing")

    def test_no_two_steps_in_a_language_are_the_same_picture(self):
        """The failure a mis-cut sheet actually produces: the same slice written under two
        names, or a step left holding its neighbour's drawing.

        WHAT THIS DOES NOT CHECK, and why there is no test that does: that each picture shows
        the step it is named after. The sheets are cut by arithmetic from a fixed grid, and
        getting that arithmetic backwards is a real risk -- the Arabic and Urdu sheets read
        right to left, so their slices are handed to the steps in reverse. Four ways of
        checking it by pixels were tried and all four were too weak to rely on: the tiles are
        nine tenths white paper, steps 1 and 4 are both a boy at a sink, and the numeral in
        the circle comes out of a crop that also catches Devanagari and Han headings. A test
        tuned until it passed would have proved nothing. The mapping was checked by eye
        instead, on a contact sheet of all fourteen captions in key order -- 1 غسل اليدين
        through 7 غسل القدمين and the Urdu beside it -- which is the right instrument for
        "does this picture say one and show hands".
        """
        for lang in WRITTEN_IN + (ARABIC_ONLY,):
            seen = {}
            for key in self.KEYS:
                name = f"step-{key}.png" if lang == "en" else f"step-{key}.{lang}.png"
                raw = (ASSETS / "wudu" / name).read_bytes()
                with self.subTest(f"{lang}.{key}"):
                    self.assertNotIn(raw, seen,
                                     f"{name} is the same picture as {seen.get(raw)}")
                seen[raw] = name

    def test_the_tiles_loaded_are_the_ones_for_that_language(self):
        for lang in ("fr", "ur", "zh", ARABIC_ONLY):
            with self.subTest(lang):
                w = self.window(lang)
                self.assertIsNotNone(w.wudu_menu, "the wu'du page did not build")
                for tile in w.wudu_menu.tiles:
                    self.assertTrue(tile.path.name.endswith(f".{lang}.png"),
                                    f"{lang} is showing {tile.path.name}")
                    self.assertTrue(tile.path.is_file())

    def test_english_keeps_the_plain_name(self):
        """It is what everything else falls back to, so it must not need a suffix of its own."""
        w = self.window("en")
        for tile in w.wudu_menu.tiles:
            self.assertRegex(tile.path.name, r"^step-\w+\.png$", tile.path.name)

    def test_a_language_with_no_drawing_falls_back_to_english(self):
        from salaah.duamenu import drawn_in
        folder = ASSETS / "wudu"
        self.assertEqual("step-hands.png", drawn_in(folder, "step-hands", "sw").name)
        self.assertEqual("step-hands.png", drawn_in(folder, "step-hands", "").name)
        self.assertEqual("step-hands.fr.png", drawn_in(folder, "step-hands", "fr").name)

    def test_the_explanation_under_a_step_is_in_that_language(self):
        """The half that was still English. Checked by script, because a paragraph that is
        there but in the wrong language is exactly what this looked like before."""
        def script(said):
            arabic = sum(1 for c in said if "؀" <= c <= "ۿ")
            deva = sum(1 for c in said if "ऀ" <= c <= "ॿ")
            han = sum(1 for c in said if "一" <= c <= "鿿")
            latin = sum(1 for c in said if c.isascii() and c.isalpha())
            return max((arabic, "arabic"), (deva, "devanagari"), (han, "han"),
                       (latin, "latin"))[1]

        for lang, want in (("en", "latin"), ("fr", "latin"), ("ur", "arabic"),
                           ("hi", "devanagari"), ("zh", "han"), (ARABIC_ONLY, "arabic")):
            with self.subTest(lang):
                w = self.window(lang)
                w.open_wudu_step("hands")
                settle()
                said = w.wudu_step.words.text()
                self.assertTrue(said.strip(), "the step has nothing written under it")
                self.assertEqual(want, script(said), f"{lang} shows {said[:50]!r}")

    def test_the_heading_and_the_words_under_it_are_the_same_language(self):
        """They came from different places and only one of them followed the setting, which is
        how the mat ended up with an Urdu heading over an English paragraph."""
        w = self.window("ur")
        w.open_wudu_step("face")
        settle()
        for said in (w.wudu_step.heading.text(), w.wudu_step.words.text()):
            arabic = sum(1 for c in said if "؀" <= c <= "ۿ")
            latin = sum(1 for c in said if c.isascii() and c.isalpha())
            self.assertGreater(arabic, latin, f"not Urdu: {said[:60]!r}")


class ArabicOnlyOnTheScreenTest(unittest.TestCase):
    """What "Arabic only" actually does once it is more than a row in a dropdown.

    Harry: "in language option add 'arabic only' this will just show arabic only and when
    playing qur'an it will display 2 pages instead of 1."
    """

    def window(self, lang="ar"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_quran_takes_both_pages_instead_of_one(self):
        w = self.window()
        w.open_surah(112)
        settle()
        spread = w.reader.spread
        self.assertFalse(spread.translated, "there is still a meaning on the left page")
        self.assertTrue(spread.right.lines, "the right page is empty")
        self.assertTrue(spread.left.lines, "the left page is empty -- this is the one-page look")
        self.assertFalse(spread.parallel.isVisible())

    def test_a_language_puts_the_meaning_back_on_the_left_page(self):
        """The other half of it, so the test above cannot pass by the Qur'an being broken."""
        w = self.window("en")
        w.open_surah(112)
        settle()
        self.assertTrue(w.reader.spread.translated)
        self.assertTrue(w.reader.spread.parallel.isVisible())

    def test_the_sayings_show_their_arabic_rather_than_nothing(self):
        """The hadith board shows a translation and no Arabic, by Harry's own instruction in
        1.51. With the translation gone it would have been a blank card with a play button on
        it, so the Arabic -- which has been in the file all along -- takes its place."""
        w = self.window()
        w.open_saying_category("faith")
        settle()
        self.assertEqual("", w.hadith_board.language())
        for card in w.hadith_board.cards:
            self.assertTrue(card.arabic.isVisible(), "the card is empty")
            self.assertFalse(card.english.isVisible(), "the translation is still there")
            shown = " ".join(card.arabic.lines)
            arabic = sum(1 for c in shown if "؀" <= c <= "ۿ")
            self.assertGreater(arabic, 20, f"not Arabic: {shown[:40]!r}")

    def test_a_duas_card_drops_the_line_underneath(self):
        w = self.window()
        w.open_dua_category("morning")
        settle()
        for card in w.dua_board.cards:
            self.assertTrue(card.arabic.isVisible())
            self.assertFalse(card.meaning.isVisible(), "the meaning is still under the Arabic")

    def test_the_prayer_screen_shows_the_arabic_alone(self):
        w = self.window()
        self.assertIsNone(w.translation)

    def test_the_call_to_prayer_has_nothing_written_under_it(self):
        """The call is the one screen where the Arabic is the whole point, so a line of
        English under each one is exactly what this setting says not to show."""
        from salaah.call import CallBox
        for lang, want in (("ar", ""), ("en", "en"), ("fr", "fr")):
            with self.subTest(lang):
                w = self.window(lang)
                box = CallBox(w, "dhuhr", "azaan.mp3", w.adhan)
                self.addCleanup(box.deleteLater)
                self.assertEqual(want, box.meaning_language())
                said = [x for x in box.findChildren(QtWidgets.QLabel)
                        if x.objectName() == "callMeaning"]
                self.assertTrue(said, "the call has no meaning labels at all")
                if lang == "ar":
                    self.assertTrue(all(not x.text().strip() for x in said),
                                    "there is still a meaning under the call")
                else:
                    self.assertTrue(any(x.text().strip() for x in said))

    def test_the_menus_are_harrys_arabic_drawings(self):
        w = self.window()
        described = json.loads((ASSETS / "hadith-menu" / "menu.json").read_text(encoding="utf-8"))
        self.assertEqual(described["films"]["ar"],
                         FilmSheet.sheet_for(described, ARABIC_ONLY))

    def test_the_headings_over_the_boards_are_in_arabic(self):
        """So the board agrees with the tile that opened it."""
        w = self.window()
        w.open_saying_category("faith")
        settle()
        said = w.hadith_board.title.text()
        self.assertEqual("الإيمان", said)

    def test_the_words_the_mat_has_no_arabic_for_still_say_something(self):
        """The pack is partial on purpose, so the fallback is what stops Settings going blank."""
        w = self.window()
        self.assertTrue(w.t("settings.school").strip())
        self.assertNotEqual("settings.school", w.t("settings.school"))


class PersonalTranslationTest(unittest.TestCase):
    """A licensed translation sitting in the folder is the one that gets used.

    The "Translation beside Arabic" dropdown was the only way to reach these. Harry has the
    Clear Qur'an text under licence for his own mat; it is keyed en-clear rather than en,
    precisely so it can never be mistaken for the public one and can be kept out of a release
    by name. Take the dropdown away and that file becomes a thing on the disk that nothing
    reads -- so installing it now IS choosing it.

    Tested on a made-up set rather than on the folder, because the real folder's answer depends
    on whether a file that must never ship happens to be there. These assertions hold either
    way, which is the point.
    """

    def window(self, translations, lang):
        content = load(ASSETS)
        content = replace(content, translations=translations)
        w = MainWindow(content, available_packs(ASSETS),
                       Settings(theme="light", recitation=False, lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=False)
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def stub(lang, personal=False):
        return Translation(lang, lang, lang, False, {}, personal=personal)

    def test_the_public_one_is_used_when_that_is_all_there_is(self):
        w = self.window({"fr": self.stub("fr")}, "fr")
        self.assertEqual("fr", w.translation.lang)

    def test_a_personal_one_of_that_language_wins(self):
        got = {"fr": self.stub("fr"), "fr-clair": self.stub("fr-clair", personal=True)}
        w = self.window(got, "fr")
        self.assertEqual("fr-clair", w.translation.lang,
                         "the licensed file is installed and is not being used")

    def test_a_personal_one_of_another_language_is_left_alone(self):
        """en-clear must not be served to somebody reading French."""
        got = {"fr": self.stub("fr"), "en-clear": self.stub("en-clear", personal=True)}
        w = self.window(got, "fr")
        self.assertEqual("fr", w.translation.lang)

    def test_arabic_only_takes_no_translation_at_all(self):
        got = {"fr": self.stub("fr"), "ar": self.stub("ar")}
        w = self.window(got, "ar")
        self.assertIsNone(w.translation,
                          "Arabic only is showing a meaning beside the Arabic")

    def test_a_language_with_no_translation_shows_none(self):
        w = self.window({"fr": self.stub("fr")}, "zh")
        self.assertIsNone(w.translation)


class ChangingALanguageStartsTheAppAgainTest(unittest.TestCase):
    """Changing the language used to rebuild every screen in place, and the mat ended up on
    the desktop.

    What was happening: rebuild() throws every screen away and builds new ones, and the memory
    does not come back. Measured on this machine with the hadith menu open -- 147 MB after the
    first build, 243 MB after six language changes, 347 MB after twelve, about twenty
    megabytes a time that is never returned. On a Pi running the rest of the mat that ends
    with the kernel killing the app, which from the prayer mat looks like the screen going out.

    So the setting is written to the disk and the process starts over. These are the tests for
    the parts of that which can be checked without actually replacing the test runner: that it
    execs rather than exits, that the command it execs is the right one, and that the setting
    is on the disk BEFORE it goes. That the command works is checked separately, by running it.
    """

    def window(self, **over):
        kw = dict(theme="dark", recitation=False, place="Bury")
        kw.update(over)
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(**kw),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def caught(self):
        """Hold the exec, and record what it was asked to run."""
        ran = []
        patch = mock.patch.object(os, "execv", lambda p, a: ran.append((p, a)))
        patch.start()
        self.addCleanup(patch.stop)
        return ran

    @staticmethod
    def wait(ms=1400):
        """Really wait. settle() only drains the queue -- it does not let the clock move, so a
        singleShot(700) never comes round and the restart looks as though it never happened."""
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            APP.processEvents()
            APP.sendPostedEvents()
            time.sleep(0.01)

    def test_choosing_a_language_starts_the_app_over(self):
        w = self.window(lang="en")
        ran = self.caught()
        w.set_lang("ur")
        self.wait()                      # the message is up for 700ms before it goes
        self.assertEqual(1, len(ran), "the app did not start itself again")
        path, args = ran[0]
        self.assertEqual(sys.executable, path)
        self.assertEqual([sys.executable, "-m", "salaah"], args[:3],
                         f"it would have run {args}")

    def test_the_choice_is_on_the_disk_before_the_process_goes(self):
        """execv does not come back. A setting still sitting in memory when it is called is a
        setting that never happened, and the mat would come up in the old language."""
        w = self.window(lang="en")
        written = []
        w.persist = lambda: written.append(w.settings.lang)
        ran = self.caught()
        w.set_lang("fr")
        self.wait()
        self.assertEqual(["fr"], written, "the language was not persisted")
        self.assertEqual(1, len(ran), "it did not start again")

    def test_choosing_the_language_already_in_use_does_nothing(self):
        """The dropdown fires on every pick, including picking the row already showing. A
        restart for that is the mat blinking at somebody who changed nothing."""
        w = self.window(lang="en")
        ran = self.caught()
        w.set_lang("en")
        self.wait()
        self.assertEqual([], ran, "it restarted for a language that was already set")

    def test_changing_the_school_starts_over_the_same_way(self):
        """set_school called rebuild() too, so it leaked the same memory the same way."""
        w = self.window(school="hanafi")
        ran = self.caught()
        other = next((s for s in sorted(w.content.schools) if s != "hanafi"), None)
        if other is None:
            self.skipTest("only one school is shipped, so there is nothing to change to")
        w.set_school(other)
        self.wait()
        self.assertEqual(1, len(ran))

    def test_it_does_not_stand_down_with_the_update_code(self):
        """The one thing this must not do.

        Exit code 42 means "an update has been installed". run.sh counts those: a version
        still on trial that exits before settling is taken for a version that died and the
        PREVIOUS one is put back, and a sixth restart in a run is treated as a failure on
        purpose. Changing the language six times is a child with a dropdown, and it would
        have reverted the mat to the last version.
        """
        w = self.window(lang="en")
        self.caught()
        stood_down = []
        app = QtWidgets.QApplication.instance()
        self.addCleanup(mock.patch.object(type(app), "exit",
                                          lambda self, code=0: stood_down.append(code)).stop)
        mock.patch.object(type(app), "exit",
                          lambda self, code=0: stood_down.append(code)).start()
        w.set_lang("es")
        self.wait()
        self.assertEqual([], stood_down,
                         f"it exited with {stood_down}; run.sh counts those as updates")

    def test_it_says_what_is_happening_rather_than_going_dark(self):
        w = self.window(lang="en")
        self.caught()
        w.set_lang("fr")
        settle(4)                       # before the 700ms timer fires
        self.assertIsNotNone(w.notice, "nothing was said; the screen just goes black")
        said = w.notice.text.text()
        self.assertEqual(w.t("settings.restarting"), said)
        self.assertTrue(said.strip())
        self.wait()

    def test_every_language_can_say_it(self):
        for lang, pack in full_packs(available_packs(ASSETS)).items():
            with self.subTest(lang):
                self.assertTrue(pack.ui.get("settings.restarting", "").strip(),
                                f"{lang} cannot say the app is starting again")


class TheMeaningFollowsTheLanguageTest(unittest.TestCase):
    """Setting the mat to Urdu puts the du'as and the sayings into Urdu.

    It did not. The boards and the reader asked for settings.lang -- the Qur'an's own
    meaning setting, which is "" until somebody presses a language button on a reading page --
    and fell back to English when it was empty. So the whole mat could be in Urdu with every
    du'a still in English, and the only way to change that was a control that says Qur'an on it.

    They fall back to the app's language now. quran_lang still wins when it has been set,
    because that is somebody asking for a meaning language by hand, which is a more specific
    answer than the language the menus happen to be in.
    """

    def window(self, **over):
        kw = dict(theme="dark", recitation=False, place="Bury")
        kw.update(over)
        w = MainWindow(load(ASSETS), available_packs(ASSETS), Settings(**kw),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def script(text: str) -> str:
        arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        return "arabic" if arabic > latin else "latin"

    def shown(self, w):
        """What the hadith board is actually showing, off the cards rather than the file."""
        return [p.meaning(w.hadith_board.language()) for _, p in w.hadith_board.showing]

    def test_a_mat_set_to_urdu_shows_its_sayings_in_urdu(self):
        w = self.window(lang="ur")
        w.open_saying_category("faith")
        settle()
        self.assertEqual("ur", w.hadith_board.language())
        for said in self.shown(w):
            self.assertEqual("arabic", self.script(said), f"not Urdu: {said[:60]!r}")

    def test_a_mat_set_to_french_shows_its_sayings_in_french(self):
        w = self.window(lang="fr")
        w.open_saying_category("prayer")
        settle()
        self.assertEqual("fr", w.hadith_board.language())
        said = " ".join(self.shown(w))
        self.assertEqual("latin", self.script(said))
        self.assertNotIn("Narrated", said, "that is the English")

    def test_a_language_the_sayings_have_not_got_falls_back_to_english(self):
        """Spanish, Hindi and Chinese have no edition of these collections anywhere I can
        reach. English beats a blank half of the screen, and is what the du'as have always
        done -- but it has to be ENGLISH, not an empty string or a crash."""
        for lang in ("es", "hi", "zh"):
            with self.subTest(lang):
                w = self.window(lang=lang)
                w.open_saying_category("charity")
                settle()
                self.assertEqual("en", w.hadith_board.language())
                for said in self.shown(w):
                    self.assertTrue(said.strip(), "the card is empty")
                    self.assertEqual("latin", self.script(said))

    def test_the_duas_follow_the_language_too(self):
        """The du'as have had translations all along -- it was the choosing that was wrong."""
        w = self.window(lang="ur")
        w.open_dua_category("forgiveness")
        settle()
        self.assertEqual("ur", w.dua_board.language())

    def test_there_is_only_one_place_left_that_decides_this(self):
        """This test used to assert the opposite, and it was right to at the time.

        There were three controls: the language in Settings, a "translation beside Arabic"
        dropdown under it, and a row of language buttons on the reading bar. The buttons and
        the dropdown wrote to settings the menus did not read, so a mat could be in Urdu with
        English du'as and nothing was broken -- each control was doing what it said.

        Harry had the lot reduced to one. So the thing worth checking now is that there IS no
        second place: no setting the boards read other than the language, and no leftover
        control writing one.
        """
        w = self.window(lang="ur")
        self.assertFalse(hasattr(w.settings, "quran_lang"), "the Qur'an's own language is back")
        self.assertFalse(hasattr(w.settings, "translation"), "the translation setting is back")
        self.assertFalse(hasattr(w, "set_translation"))
        self.assertFalse(hasattr(w, "translation_picker"))
        reader = w.section_readers["hadith"]
        self.assertEqual({}, reader.buttons, "the reading bar still has language buttons")
        self.assertFalse(hasattr(reader, "set_language"))
        # And the one that is left reaches everything.
        w.open_saying_category("faith")
        settle()
        self.assertEqual("ur", w.hadith_board.language())

    def test_the_board_and_the_page_it_opens_agree(self):
        """Two separate pieces of code choose this, and a du'a that reads one way on the board
        and another way when you open it is the kind of thing nobody reports and everybody
        notices."""
        w = self.window(lang="ur")
        w.open_saying_category("family")
        settle()
        reader = w.section_readers["hadith"]
        index = w.hadith_board.showing[0][0]
        w.open_passage("hadith", index)
        settle()
        self.assertEqual(w.hadith_board.language(), reader.language())

    def test_the_wudu_steps_follow_it_as_well(self):
        """Same fallback, same reason -- they were reading quran_lang too."""
        w = self.window(lang="ur")
        w.open_wudu_step("hands")
        settle()
        self.assertTrue(w.wudu_step.words.text().strip(),
                        "the step has nothing written under it")


class SettingsTidiedTest(unittest.TestCase):
    """Two buttons taken out of Settings: they duplicated what was already on screen, or they
    belonged to building the mat rather than praying on it."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def buttons(self, w):
        return [b.text() for b in w.settings_screen.findChildren(QtWidgets.QAbstractButton)
                if b.text()]

    @unittest.skipUnless(__import__("salaah.ui", fromlist=["QIBLA"]).QIBLA,
                         "the Qibla compass is switched off")
    def test_no_show_the_qibla_button(self):
        """With a 7 inch screen the compass is on it the whole time Settings is up."""
        w = self.window()
        self.assertFalse([x for x in self.buttons(w) if "Qibla" in x and "how" in x.lower()],
                         "the 'Show the Qibla' button is meant to be gone")
        self.assertTrue(w.side.showing_compass or not w.settings.qibla_start,
                        "and the compass really is on the small screen")
        for lang, pack in full_packs(available_packs(ASSETS)).items():
            self.assertNotIn("settings.qibla_show", pack.ui, f"{lang} still carries the wording")

    @unittest.skipUnless(__import__("salaah.ui", fromlist=["QIBLA"]).QIBLA,
                         "the Qibla compass is switched off")
    def test_the_qibla_rows_that_matter_are_still_there(self):
        w = self.window()
        words = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel) if x.text()]
        words += self.buttons(w)
        self.assertTrue([x for x in words if "Qibla" in x], "the Qibla section went with it")
        self.assertTrue([x for x in words if "118" in x], "the bearing should still be shown")

    def test_the_recitation_hint_no_longer_points_at_a_button_that_is_gone(self):
        for lang, pack in full_packs(available_packs(ASSETS)).items():
            hint = pack.ui.get("settings.recitation_hint", "")
            self.assertNotIn("ring", hint.lower().replace("during", ""),
                             f"{lang}: the hint still sends you to the tap-timings button")


class ScriptFontsTest(unittest.TestCase):
    """Raspberry Pi OS ships neither Chinese nor Devanagari, so both are bundled, cut down to
    the characters the translations use. Without them the meaning column would be empty boxes,
    which is the kind of fault that only shows up on the device."""

    def setUp(self):
        from salaah.render import Fonts
        Fonts.load(ASSETS)
        self.Fonts = Fonts

    def test_the_two_faces_are_bundled_and_loaded(self):
        from salaah.render import SCRIPT_FONTS
        for key, name in SCRIPT_FONTS.items():
            self.assertTrue((ASSETS / "fonts" / name).is_file(), f"{name} is not bundled")
            self.assertIn(key, self.Fonts.scripts, f"{name} did not load")

    def test_they_are_small_enough_to_ship(self):
        """A whole CJK face is about ten megabytes; the SD card has not got it to spare."""
        from salaah.render import SCRIPT_FONTS
        for name in SCRIPT_FONTS.values():
            size = (ASSETS / "fonts" / name).stat().st_size
            self.assertLess(size, 600_000, f"{name} is {size // 1024} KB; subset it again")

    def test_the_face_is_chosen_from_the_letters(self):
        self.assertEqual(self.Fonts.scripts["han"], self.Fonts.for_text("奉安拉之名"))
        self.assertEqual(self.Fonts.scripts["devanagari"], self.Fonts.for_text("अल्लाह के नाम"))
        self.assertEqual(self.Fonts.english_family, self.Fonts.for_text("En el nombre de Dios"))

    def test_no_translation_can_come_out_as_empty_boxes(self):
        """Every character of every shipping translation, against the face the app will pick."""
        content = load(ASSETS)
        for lang, tr in sorted(content.translations.items()):
            if tr.personal:
                continue
            texts = [line for part in tr.lines.values() for line in part]
            texts += [tr.intention] + list(tr.kinds.values()) + list(tr.prayers.values())
            whole = "".join(texts)
            family = (self.Fonts.arabic("scheherazade") if tr.rtl
                      else self.Fonts.for_text(whole))
            font = QtGui.QFont(family)
            font.setPixelSize(48)
            metrics = QtGui.QFontMetrics(font)
            missing = sorted({c for c in whole if not c.isspace() and not metrics.inFont(c)})
            self.assertFalse(missing,
                             f"{lang}: {family} has no glyph for {''.join(missing)}")

    def test_the_licence_travels_with_them(self):
        self.assertTrue((ASSETS / "fonts" / "OFL-Noto.txt").is_file(),
                        "the Noto licence must ship beside the fonts")
        words = (ASSETS / "fonts" / "OFL-Noto.txt").read_text(errors="ignore")
        self.assertIn("Open Font License", words)


class EveryInterfaceLanguageTest(unittest.TestCase):
    """Six languages for the menus now, in four scripts. The Pi has fonts for neither Chinese
    nor Devanagari, so everything that draws a menu word has to be given the right face."""

    def window(self, lang):
        packs = available_packs(ASSETS)
        content = load(ASSETS)
        w = MainWindow(content, packs,
                       Settings(theme="light", recitation=False, lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        w.refresh()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_all_six_are_offered(self):
        packs = available_packs(ASSETS)
        self.assertEqual(set(WRITTEN_IN) | {ARABIC_ONLY}, set(packs))
        # Counted against English rather than against a number written in here: a hard-coded
        # count only ever says "someone added a string", which is not a fault.
        #
        # Arabic is held out of the key-for-key comparison on purpose -- it is the Arabic-only
        # setting's pack and carries the menu headings alone, with everything else falling back
        # to English. What it must carry is checked exactly in ArabicOnlyPackTest, so holding
        # it out here does not leave it untested.
        english = packs["en"].ui
        for lang, pack in full_packs(packs).items():
            self.assertEqual(len(english), len(pack.ui),
                             f"{lang} has {len(pack.ui)} strings against English's {len(english)}")
            self.assertEqual(set(english), set(pack.ui), f"{lang} does not match English key for key")
            for key, said in pack.ui.items():
                self.assertTrue(said.strip(), f"{lang} {key} is blank")

    def test_every_gap_in_a_string_survives_translation(self):
        """A translator dropping {n} or {total} would leave the app unable to fill it in."""
        import re
        packs = available_packs(ASSETS)
        for lang, pack in packs.items():
            # Arabic carries only the menu headings, so it is checked on the keys it HAS
            # rather than on English's whole list. The headings are names and hold no gaps,
            # but a heading that grew one and lost it would still be caught here.
            for key, said in pack.ui.items():
                wanted = set(re.findall(r"\{(\w+)\}", packs["en"].ui.get(key, "")))
                got = set(re.findall(r"\{(\w+)\}", said))
                self.assertEqual(wanted, got, f"{lang} {key}: wanted {wanted}, got {got}")

    def test_the_menus_are_drawn_in_a_face_that_has_the_letters(self):
        for lang in sorted(full_packs(available_packs(ASSETS))):
            w = self.window(lang)
            face = w.pack_face()
            font = QtGui.QFont(face)
            font.setPixelSize(24)
            metrics = QtGui.QFontMetrics(font)
            whole = "".join(w.pack.ui.values())
            missing = sorted({c for c in whole if not c.isspace() and not metrics.inFont(c)})
            self.assertFalse(missing, f"{lang}: {face} has no glyph for {''.join(missing)}")

    def test_chinese_and_hindi_get_a_bundled_face_not_the_system_one(self):
        from salaah.render import Fonts
        for lang, script in (("zh", "han"), ("hi", "devanagari")):
            w = self.window(lang)
            self.assertEqual(Fonts.scripts[script], w.pack_face(),
                             f"{lang} is falling back to the system font, which the Pi lacks")
        for lang in ("en", "es", "fr"):
            w = self.window(lang)
            self.assertEqual(Fonts.english_family, w.pack_face(), lang)

    def test_the_arabic_prayer_name_keeps_its_own_face(self):
        """Setting a Chinese face on every widget must not take the Arabic with it."""
        w = self.window("zh")
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "farz"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        APP.processEvents()
        self.assertIn("Scheherazade", w.arabic_name.font().family())
        self.assertTrue(w.arabic_name.text())

    def test_the_language_list_draws_each_name_in_its_own_script(self):
        """The one list that holds four scripts at once. Each row carries its own face, and so
        does the shut box, or the names the Pi has no font for come out as boxes."""
        from salaah.render import Fonts
        w = self.window("en")
        picker = w.language_picker
        self.assertEqual(len(WRITTEN_IN) + 1, picker.count(), "six languages, and Arabic only")
        wanted = {"中文": Fonts.scripts["han"], "हिन्दी": Fonts.scripts["devanagari"],
                  "English": Fonts.english_family, "Español": Fonts.english_family}
        seen = {}
        for i in range(picker.count()):
            label = picker.itemText(i)
            face = picker.itemData(i, Qt.ItemDataRole.FontRole)
            self.assertIsNotNone(face, f"{label} has no face of its own")
            seen[label] = face.family()
        for label, face in wanted.items():
            self.assertIn(label, seen, f"{label} is not in the list")
            self.assertEqual(face, seen[label], f"{label} is set in {seen[label]}")

    def test_the_shut_box_shows_the_chosen_name_in_its_own_script(self):
        from salaah.render import Fonts
        w = self.window("zh")
        self.assertEqual("中文", w.language_picker.currentText())
        self.assertEqual(Fonts.scripts["han"], w.language_picker.font().family())

    def test_the_unit_arches_are_lettered_in_the_interface_face(self):
        """Hindi words need a Devanagari face or they come out as empty boxes on the Pi.

        Since 1.62 the words in a prayer's arches are painted by the drawing's own screen
        rather than by an ArchButton, so that is where the face has to arrive. Both are
        checked: the drawn page as the mat actually shows it, and the fallback behind it.
        """
        from salaah.mosque import ArchButton
        from salaah.render import Fonts
        want = Fonts.scripts["devanagari"]

        w = self.window("hi")
        w.open_prayer("dhuhr")
        APP.processEvents()
        drawn = w.prayer_mosque
        self.assertIsNotNone(drawn, "dhuhr did not open on its drawing")
        self.assertTrue(drawn.labels, "nothing is written in the arches")
        self.assertEqual(want, drawn.label_face,
                         "the words in the arches would be empty boxes on the Pi")

        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)
        w.open_prayer("dhuhr")
        APP.processEvents()
        arches = w.pick.findChildren(ArchButton)
        self.assertTrue(arches, "the fallback drew no arches")
        for arch in arches:
            self.assertEqual(want, arch.family,
                             "the arch labels would be empty boxes on the Pi")

    def test_a_language_change_takes_the_face_with_it(self):
        from salaah.render import Fonts
        w = self.window("en")
        self.assertEqual(Fonts.english_family, w.pack_face())
        w.set_lang("zh")
        APP.processEvents()
        self.assertEqual(Fonts.scripts["han"], w.pack_face())
        self.assertIn(Fonts.scripts["han"], w.stylesheet())


class ShutdownTest(unittest.TestCase):
    """A window that has been shut down must stop reaching into the app. Its ten-second clock
    calls apply_theme, which sets the palette for everything, so leaving it running let a dead
    window change the colours under a live one."""

    def make(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        return w

    def test_the_clock_stops(self):
        w = self.make()
        self.assertTrue(w.clock.isActive(), "the clock should run while the window is up")
        w.shutdown()
        self.assertFalse(w.clock.isActive(), "a shut-down window is still keeping time")
        w.close()
        w.deleteLater()
        APP.processEvents()

    def test_what_the_clock_would_have_done(self):
        """Why stopping it matters: every tick sets the light-or-dark palette for the whole app
        from that window's own settings. One window is kept here rather than two, so the test
        does not depend on what any other window is doing."""
        from salaah import theme
        was = theme.is_dark()
        self.addCleanup(lambda: theme.set_dark(was))
        w = self.make(theme="dark")
        self.addCleanup(lambda: (w.close(), w.deleteLater(), settle()))
        self.assertTrue(theme.is_dark(), "its own settings say dark")
        w.settings.theme = "light"          # as if another window's settings were in charge
        w.tick()
        self.assertFalse(theme.is_dark(), "a tick reaches the palette for the whole app")
        w.shutdown()
        self.assertFalse(w.clock.isActive(), "so after shutdown it must not tick again")


class SleepTest(unittest.TestCase):
    """The power button puts the mat to sleep instead of shutting it down.

    The screens go off at the panel, and the work that was only drawing them stops with them.
    """

    class Screens:
        """Stands in for wlopm, and remembers what it was asked to do."""
        why = ""

        def __init__(self):
            self.calls = []

        def set(self, on):
            self.calls.append(on)
            return True

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.outputs = self.Screens()
        w.resize(1920, 1200)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def press(self, w):
        w.bridge.power.emit()
        APP.processEvents()

    def test_a_press_sleeps_and_the_next_one_wakes(self):
        w = self.window()
        self.assertFalse(w.asleep)
        self.press(w)
        self.assertTrue(w.asleep)
        self.press(w)
        self.assertFalse(w.asleep)
        self.assertEqual([False, True], w.outputs.calls, "the screens went off, then back on")

    def test_asleep_nothing_is_still_drawing_the_screens(self):
        """The panels are the bulk of it, but the sky animating several times a second and the
        clock redrawing the times cost something too, and nobody can see either of them."""
        w = self.window()
        skies = [w.mosque] + ([w.welcome_mosque] if w.welcome is not None else [])
        self.assertTrue(w.clock.isActive())
        self.assertTrue(any(s.flutter.isActive() for s in skies))
        self.press(w)
        self.assertFalse(w.clock.isActive(), "the ten-second clock is still running")
        self.assertFalse(any(s.flutter.isActive() for s in skies), "the sky is still animating")
        self.press(w)
        # It wakes at the front door, whose drawing brings its own sky and runs no clock for
        # one. So what has to come back is the ten-second clock -- the thing that keeps the
        # times right -- and no sky anywhere may still be running.
        self.assertTrue(w.clock.isActive())
        self.assertFalse(any(s.flutter.isActive() for s in skies if not s.isVisible()),
                         "a sky is animating on a screen nobody is looking at")

    def test_it_sleeps_from_any_screen_including_partway_through_a_prayer(self):
        """One rule and no exceptions. This used to be refused mid-prayer; a button that does
        nothing turned out to be worse than one that does something, and it is the only way out
        of a screen that has stopped behaving."""
        w = self.window()
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "sunnah"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        APP.processEvents()
        self.assertTrue(w.playing)
        self.press(w)
        self.assertTrue(w.asleep, "the button did nothing partway through a prayer")

    def test_sleeping_partway_through_a_prayer_puts_the_prayer_away_properly(self):
        """Waking goes to the mosque, so the prayer is left rather than paused. It has to be let
        go of cleanly: no session still running, and nothing still being recited."""
        w = self.window()
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == "sunnah"][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        APP.processEvents()
        self.press(w)
        self.press(w)
        self.assertIs(w.welcome, w.stack.currentWidget())
        self.assertIsNone(w.session, "the abandoned prayer is still hanging about")
        self.assertFalse(w.recitation.busy, "it is still reciting into an empty room")

    def to_the_end(self, w, kind="sunnah"):
        entry = [e for e in w.school.prayers["dhuhr"] if e.kind == kind][0]
        w.open_prayer("dhuhr")
        w.start("dhuhr", entry)
        while not w.session.finished:
            w.session.next()
        w.refresh()
        APP.processEvents()
        return w

    def test_it_sleeps_from_the_screens_that_follow_a_prayer(self):
        """The passages and the counted dhikr sit on the prayer screen and so look like praying
        to most of the app. They are the likeliest moment of all to reach for the button:
        finished, and putting the mat away."""
        for kind, screen in (("sunnah", "the passages"), ("farz", "the beads")):
            w = self.window()
            self.to_the_end(w, kind)
            self.press(w)
            self.assertTrue(w.asleep, f"{screen}: the button did nothing")

    def test_it_wakes_at_the_front_door_rather_than_where_it_was_left(self):
        """The mat is picked up by whoever prays next. A screen left open in the middle of
        someone else's Settings is no way to greet them. The screen it greets them with is the
        front door now; the reason for not leaving Settings up is the one it always was."""
        w = self.window()
        w.open_settings()
        APP.processEvents()
        self.assertIsNot(w.welcome, w.stack.currentWidget())
        self.press(w)
        self.press(w)
        self.assertIs(w.welcome, w.stack.currentWidget(), "it woke up back in Settings")

    def test_waking_from_the_end_of_a_prayer_forgets_the_prayer(self):
        w = self.window()
        self.to_the_end(w)
        self.press(w)
        self.press(w)
        self.assertIs(w.welcome, w.stack.currentWidget())
        self.assertIsNone(w.session, "the finished prayer is still hanging about")
        self.assertFalse(w.playing)

    def test_the_seven_inch_goes_back_to_what_it_shows_at_the_start(self):
        """Named rather than just "something changed": the 7in shows the Qibla between prayers,
        and that is what someone waking the mat should be met by, not the last posture of
        whatever was prayed before."""
        w = self.window()
        self.to_the_end(w)
        self.assertFalse(w.side.showing_compass, "the posture should be up during a prayer")
        self.press(w)
        self.press(w)
        self.assertTrue(w.side.showing_idle,
                        "the 7in is still showing the posture from the prayer")

    def test_the_screens_are_handed_back_on_the_way_out(self):
        """Quitting while asleep must not leave the panels dark for whatever runs next."""
        w = self.window()
        self.press(w)
        self.assertTrue(w.asleep)
        w.shutdown()
        self.assertFalse(w.asleep)
        self.assertEqual([False, True], w.outputs.calls)

    def test_waking_catches_up_with_the_time(self):
        """It may have slept through a prayer, so the mosque cannot come back showing the hour
        it went to sleep at."""
        from unittest import mock
        w = self.window()
        self.press(w)
        with mock.patch.object(type(w), "tick", autospec=True) as ticked:
            self.press(w)
        self.assertTrue(ticked.called, "nothing brought the clock and the lit prayer up to date")

    def test_sleeping_twice_over_does_nothing_the_second_time(self):
        w = self.window()
        w.sleep()
        w.sleep()
        w.wake()
        w.wake()
        self.assertEqual([False, True], w.outputs.calls)


class UpdateNoticeTest(unittest.TestCase):
    """What the person actually sees when they press Check for updates.

    Everything here was previously a line of small grey text in the corner of the Settings
    screen, which on a mat across a room amounts to nothing happening at all.
    """

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def manifest(version):
        """Stands in for the network: hands back a signed release without one."""
        from salaah.update import Release

        def check(url="", opener=None, key=""):
            return Release(version=version, url="http://example/x.zip", sha256="0" * 64)
        return check

    @staticmethod
    def notice_words(w):
        return [x.text() for x in w.notice.findChildren(QtWidgets.QLabel)]

    @staticmethod
    def notice_buttons(w):
        return [x.text() for x in w.notice.findChildren(QtWidgets.QAbstractButton)]

    def test_the_update_button_is_white_on_red(self):
        """It is the one control on the Settings screen that does something irreversible, and
        it used to look like a piece of text."""
        w = self.window()
        from salaah.ui import BRICK
        sheet = w.styleSheet()
        rule = sheet[sheet.index("QPushButton#updateButton"):]
        rule = rule[:rule.index("}")]
        self.assertIn(BRICK.lower(), rule.lower(), "the update button should be brick red")
        self.assertIn("color:white", rule.replace(" ", ""))
        self.assertEqual("updateButton", w.update_button.objectName())

    def test_being_up_to_date_is_said_in_a_box_that_has_to_be_dismissed(self):
        from salaah import __version__
        import salaah.update as updater
        w = self.window()
        with mock.patch.object(updater, "check", self.manifest("0.1")):
            w.check_for_update()
        self.assertIsNotNone(w.notice, "a box should be on screen")
        self.assertTrue(w.notice.isVisible())
        self.assertTrue(any(__version__ in t for t in self.notice_words(w)),
                        f"the box should name the version: {self.notice_words(w)}")
        self.assertEqual(["Close"], self.notice_buttons(w))

    def test_an_available_update_is_offered_with_a_way_to_decline(self):
        import salaah.update as updater
        w = self.window()
        with mock.patch.object(updater, "check", self.manifest("99.0")):
            w.check_for_update()
        self.assertTrue(any("99.0" in t for t in self.notice_words(w)))
        self.assertEqual(["Not now", "Update now"], self.notice_buttons(w))

    def test_a_failure_says_why_rather_than_closing_silently(self):
        import salaah.update as updater

        def refuse(url="", opener=None, key=""):
            raise updater.Refused("the roof fell in")

        w = self.window()
        with mock.patch.object(updater, "check", refuse):
            w.check_for_update()
        self.assertTrue(any("the roof fell in" in t for t in self.notice_words(w)),
                        self.notice_words(w))
        self.assertEqual(["Close"], self.notice_buttons(w))

    def test_the_box_is_black_with_white_writing_whichever_theme_is_on(self):
        """A message about the app is not part of the prayer, and should not be dressed as it."""
        import salaah.update as updater
        for theme in ("light", "dark"):
            w = self.window(theme=theme)
            with mock.patch.object(updater, "check", self.manifest("0.1")):
                w.check_for_update()
            sheet = w.notice.styleSheet().replace(" ", "").lower()
            self.assertIn("background:#000000", sheet, f"{theme}: the box should be black")
            self.assertIn("color:#ffffff", sheet, f"{theme}: the writing should be white")

    def test_closing_the_box_lets_it_be_opened_again(self):
        """It is a dialog now, not a label. One that cannot be reopened is worse than a label."""
        import salaah.update as updater
        w = self.window()
        with mock.patch.object(updater, "check", self.manifest("0.1")):
            w.check_for_update()
        w.notice.accept()
        APP.processEvents()
        self.assertIsNone(w.notice, "the box should be forgotten once closed")
        self.assertTrue(w.update_button.isEnabled(), "and the button usable again")
        with mock.patch.object(updater, "check", self.manifest("0.1")):
            w.check_for_update()
        self.assertIsNotNone(w.notice, "pressing again should bring it back")

    def test_it_will_not_check_in_the_middle_of_a_prayer(self):
        w = self.window()
        with mock.patch.object(MainWindow, "playing", True):
            w.check_for_update()
        self.assertTrue(any("prayer" in t.lower() for t in self.notice_words(w)),
                        self.notice_words(w))

    def test_a_message_that_wraps_is_not_cut_in_half(self):
        """Found by looking at the box, not at the numbers that sized it. A wrapped label has
        no height until it knows its width, so a single sizing pass leaves the last line sliced
        through the middle -- which is exactly how it shipped the first time."""
        import salaah.update as updater

        long_one = ("the update could not be reached: the name of the server could not be "
                    "looked up, which usually means this mat is not on the internet just now")

        def refuse(url="", opener=None, key=""):
            raise updater.Refused(long_one)

        w = self.window()
        with mock.patch.object(updater, "check", refuse):
            w.check_for_update()
        APP.processEvents()

        note = w.notice
        self.assertGreater(note.text.height(), note.text.fontMetrics().height() * 1.5,
                           "this message must wrap, or the test proves nothing")

        picture = note.grab().toImage()
        top_left = note.text.mapTo(note, QtCore.QPoint(0, 0))
        rows_with_ink = []
        for y in range(note.text.height()):
            line = top_left.y() + y
            if any(QtGui.qGray(picture.pixel(top_left.x() + x, line)) > 120
                   for x in range(0, note.text.width(), 2)):
                rows_with_ink.append(y)
        self.assertTrue(rows_with_ink, "no writing found in the message area at all")
        self.assertLess(rows_with_ink[-1], note.text.height() - 2,
                        "the writing runs to the very bottom of its area, so it is being cut off")


class FakeMonitor:
    """A monitor that either takes brightness commands or does not, without one being present."""

    def __init__(self, answers=True):
        self.available = answers
        self.applied = []

    def set(self, percent):
        self.applied.append(percent)

    def settle(self, seconds=0):
        pass


class BrightnessTest(unittest.TestCase):
    """The screen brightness setting, which drives the monitor's own backlight where it can."""

    def window(self, answers=True, **settings):
        from salaah.ui import MainWindow as MW
        with mock.patch.object(MW, "apply_brightness", lambda self: None):
            w = MW(load(ASSETS), available_packs(ASSETS),
                   Settings(**{"theme": "light", "recitation": False, **settings}),
                   scale=1.0, save_settings=False, aspect=None)
        w.backlight = FakeMonitor(answers=answers)
        w.rebuild()
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_it_is_a_slider_not_five_buttons(self):
        w = self.window(brightness=70)
        bars = w.settings_screen.findChildren(QtWidgets.QSlider)
        bars = [b for b in bars if b.objectName() == "brightness"]
        self.assertEqual(1, len(bars), "there should be one brightness slider")
        self.assertEqual(70, bars[0].value(), "it should start where the setting is")

    def test_it_cannot_be_taken_down_to_nothing(self):
        """A mat with the backlight off cannot be turned back up: you cannot see the slider."""
        from salaah.backlight import LEAST
        w = self.window()
        bar = [b for b in w.settings_screen.findChildren(QtWidgets.QSlider)
               if b.objectName() == "brightness"][0]
        self.assertGreaterEqual(bar.minimum(), LEAST)
        self.assertGreater(bar.minimum(), 0, "a slider that reaches zero is a trap")
        bar.setValue(0)
        self.assertGreaterEqual(bar.value(), LEAST)

    def test_moving_it_tells_the_monitor_and_remembers(self):
        w = self.window()
        bar = [b for b in w.settings_screen.findChildren(QtWidgets.QSlider)
               if b.objectName() == "brightness"][0]
        bar.setValue(35)
        APP.processEvents()
        self.assertEqual(35, w.settings.brightness, "the setting should follow the slider")
        self.assertIn(35, w.backlight.applied, "and the monitor should be told")

    def test_the_veil_is_not_used_when_the_monitor_does_it_for_real(self):
        """Turning the backlight down AND drawing a veil over it would darken it twice."""
        w = self.window(answers=True, brightness=40)
        self.assertEqual(0, w.veil_percent())

    def two_screens(self, answers=True, **settings):
        """A mat as it actually is: the monitor and the 7" posture screen beside it."""
        from salaah.ui import MainWindow as MW
        with mock.patch.object(MW, "apply_brightness", lambda self: None):
            w = MW(load(ASSETS), available_packs(ASSETS),
                   Settings(**{"theme": "light", "recitation": False, **settings}),
                   scale=1.0, save_settings=False, aspect=None, side=True)
        w.backlight = FakeMonitor(answers=answers)
        w.resize(1920, 1200)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_little_screen_is_actually_veiled_and_the_big_one_is_not(self):
        """The calculation being right is not the same as it reaching the screen. This checks
        what each window was told, which is what the person sees."""
        w = self.two_screens(answers=True, brightness=40)
        w.apply_brightness()
        APP.processEvents()
        self.assertTrue(w.side.dim.isVisible(),
                        "the posture screen must be veiled: it cannot dim itself")
        self.assertFalse(w.slide.dim.isVisible(),
                         "the monitor dims for real, so it must not be veiled as well")

    def test_neither_screen_is_veiled_at_full_brightness(self):
        w = self.two_screens(answers=True, brightness=100)
        w.apply_brightness()
        APP.processEvents()
        self.assertFalse(w.side.dim.isVisible())
        self.assertFalse(w.slide.dim.isVisible())

    def test_the_posture_screen_is_always_dimmed_in_software(self):
        """It has no brightness of its own: it gives its EDID on the bus and refuses every
        brightness command, even slowed right down. Judging this once for the whole mat left
        the little screen glaring at full power beside a monitor that had properly dimmed."""
        w = self.window(answers=True, brightness=40)
        self.assertEqual(0, w.veil_percent(), "the monitor dims for real")
        self.assertEqual(36, w.side_veil_percent(), "eased off so it matches the monitor")

    def test_both_screens_are_veiled_when_neither_can_dim_itself(self):
        w = self.window(answers=False, brightness=40)
        self.assertEqual(36, w.veil_percent())
        self.assertEqual(36, w.side_veil_percent())

    def test_the_posture_screen_never_goes_fully_black(self):
        w = self.window(answers=True, brightness=10)
        self.assertLessEqual(w.side_veil_percent(), 80)
        self.assertGreater(w.side_veil_percent(), 0)

    def test_a_monitor_that_will_not_listen_falls_back_to_the_veil(self):
        w = self.window(answers=False, brightness=40)
        self.assertEqual(36, w.veil_percent(), "eased off from the bare 60%")
        self.assertEqual([], w.backlight.applied, "nothing should be sent to a deaf monitor")

    def test_the_veil_never_goes_fully_black(self):
        w = self.window(answers=False, brightness=10)
        self.assertLessEqual(w.veil_percent(), 80)

    def test_the_fallback_says_so_and_a_working_monitor_does_not(self):
        """The words exist for the case where the slider cannot do what it appears to."""
        for answers, wanted in ((False, True), (True, False)):
            w = self.window(answers=answers)
            hints = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                     if x.objectName() == "settingHint"]
            said = any("monitor" in h.lower() for h in hints)
            self.assertEqual(wanted, said, f"backlight available={answers}: hints were {hints}")


class CallToPrayerTest(unittest.TestCase):
    """The azaan when a prayer falls due, and the mat putting itself to sleep."""

    class Speaker:
        """Stands in for the audio player: records what it was asked to play."""

        def __init__(self):
            self.played, self.stopped, self.playing, self.volume = [], 0, False, 80

        def play(self, audio):
            self.played.append(Path(audio).name)
            self.playing = True
            return True

        def stop(self):
            self.stopped += 1
            self.playing = False

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.call = self.Speaker()
        w.outputs = type(w.outputs)()
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def at(w, prayer, seconds_late=5):
        """Pretend it is [seconds_late] past the time for [prayer], and let the mat notice."""
        from datetime import datetime, timedelta
        due = w.prayer_times()[prayer]
        when = datetime.combine(datetime.now().date(), due) + timedelta(seconds=seconds_late)
        with mock.patch("salaah.ui.datetime") as clock:
            clock.now.return_value = when
            clock.combine = datetime.combine
            w.check_the_hour()
        APP.processEvents()

    def words(self, w):
        return [x.text() for x in w.call_box.findChildren(QtWidgets.QLabel)]

    def test_a_prayer_falling_due_says_so_and_calls(self):
        w = self.window()
        self.at(w, "dhuhr")
        self.assertIsNotNone(w.call_box, "a box should be on screen")
        self.assertTrue([t for t in self.words(w) if t.startswith("TIME TO PRAY")],
                        f"nothing on the box says it is time: {self.words(w)}")
        self.assertTrue([t for t in self.words(w) if "Dhuhr" in t], "and which prayer")
        self.assertEqual(["azaan.mp3"], w.call.played)

    def test_fajr_is_called_with_its_own_azaan(self):
        """The call at dawn has a line the other four do not. The mat used to announce Fajr and
        stay quiet, because saying the wrong words would have been worse than silence. There is
        a Fajr recording now, so it speaks -- and the guarantee the old behaviour existed to
        keep still holds: whatever happens, Fajr is never given the ordinary call."""
        w = self.window()
        self.at(w, "fajr")
        self.assertIsNotNone(w.call_box, "Fajr should still be announced")
        self.assertEqual(["azaan-fajr.mp3"], w.call.played)
        self.assertNotIn("azaan.mp3", w.call.played, "never the ordinary call for Fajr")

    def test_stopping_it_silences_the_call(self):
        w = self.window()
        self.at(w, "asr")
        self.assertTrue(w.call.playing)
        w.call_box.accept()                      # the Stop button
        APP.processEvents()
        self.assertFalse(w.call.playing, "the azaan should stop")
        self.assertIsNone(w.call_box, "and the box should go")

    def test_a_sleeping_mat_wakes_itself_to_call(self):
        w = self.window()
        w.sleep()
        self.assertTrue(w.asleep)
        self.at(w, "maghrib")
        self.assertFalse(w.asleep, "it should wake to call")
        self.assertIs(w.welcome, w.stack.currentWidget(), "and come back at the mosque")
        self.assertEqual(["azaan.mp3"], w.call.played)

    def test_it_does_not_call_over_somebody_already_praying(self):
        w = self.window()
        w.open_prayer("isha")
        w.start("isha", w.school.prayers["isha"][0])
        APP.processEvents()
        self.at(w, "isha")
        self.assertIsNone(w.call_box, "a call during the prayer it calls for would be absurd")
        self.assertEqual([], w.call.played)

    def test_each_prayer_is_called_once_a_day(self):
        w = self.window()
        for _ in range(4):
            self.at(w, "dhuhr")
        self.assertEqual(1, len(w.call.played), "it should not call again every fifteen seconds")

    def test_a_prayer_long_past_is_not_called(self):
        """A call well after the time is worse than none -- it sends somebody to pray late."""
        w = self.window()
        self.at(w, "dhuhr", seconds_late=int(w.GRACE) + 60)
        self.assertIsNone(w.call_box)
        self.assertEqual([], w.call.played)

    def test_turning_it_off_means_no_call(self):
        w = self.window(azaan=False)
        self.at(w, "dhuhr")
        self.assertIsNone(w.call_box)
        self.assertEqual([], w.call.played)

    # Going to sleep on its own

    def test_nothing_pressed_for_a_while_and_it_sleeps(self):
        w = self.window()
        w.maybe_sleep()
        self.assertTrue(w.asleep)

    def test_it_does_not_sleep_in_the_middle_of_a_prayer(self):
        """The screen is being read, not pressed. Idleness and stillness are not the same."""
        w = self.window()
        w.open_prayer("dhuhr")
        w.start("dhuhr", w.school.prayers["dhuhr"][0])
        APP.processEvents()
        w.maybe_sleep()
        self.assertFalse(w.asleep)

    def test_it_does_not_sleep_while_the_azaan_is_sounding(self):
        w = self.window()
        self.at(w, "dhuhr")
        w.maybe_sleep()
        self.assertFalse(w.asleep, "it should not go dark part way through calling")

    def test_it_does_not_sleep_with_a_message_waiting_to_be_answered(self):
        import salaah.update as updater
        from salaah.update import Release
        w = self.window()
        with mock.patch.object(updater, "check",
                               lambda url="", opener=None, key="": Release(
                                   version="0.1", url="http://x/x.zip", sha256="0" * 64)):
            w.check_for_update()
        w.maybe_sleep()
        self.assertFalse(w.asleep)

    def test_a_press_puts_sleep_off(self):
        w = self.window()
        w.stir()
        self.assertTrue(w.idle.isActive(), "the clock should be running")
        self.assertGreater(w.idle.remainingTime(), 60_000, "3 minutes, not seconds")

    def test_sleep_can_be_turned_off_altogether(self):
        w = self.window(sleep_after=0)
        w.stir()
        self.assertFalse(w.idle.isActive(), "0 means never")


class NoQiblaTest(unittest.TestCase):
    """The compass is switched off: the mat has a mechanical one set into its frame.

    The tests that guard the compass itself skip while it is off. These assert the other side
    of it -- that with it off, nothing of it reaches the screens.
    """

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        APP.processEvents()
        self.addCleanup(lambda: shut(w))
        return w

    def test_it_is_switched_off(self):
        from salaah import ui
        self.assertFalse(ui.QIBLA, "the mat has a compass in its frame; the screen one is off")

    def test_settings_says_nothing_about_the_qibla(self):
        w = self.window()
        said = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        said += [x.text() for x in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]
        self.assertFalse([s for s in said if "qibla" in s.lower()],
                         f"Settings still mentions the Qibla: {[s for s in said if 'qibla' in s.lower()]}")

    def test_the_small_screen_has_no_compass_on_it(self):
        w = self.window()
        self.assertIsNone(w.side.compass, "no compass should be built for the 7 inch screen")
        self.assertFalse(w.side.showing_compass)

    def test_the_app_does_not_open_on_a_compass(self):
        w = self.window()
        w.begin()
        APP.processEvents()
        self.assertIs(w.welcome, w.stack.currentWidget(), "it should start at the mosque")

    def test_the_compass_code_is_still_there_to_switch_back_on(self):
        """Switched off, not torn out. A mat with a sensor fitted should need one line."""
        from salaah.compass import CompassScreen        # noqa: F401
        from salaah import qibla                        # noqa: F401


class KnowledgeCornerTest(unittest.TestCase):
    """The 7" menu and what it opens on the big screen."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_small_screen_offers_eight_things_between_prayers(self):
        w = self.window()
        self.assertTrue(w.side.showing_corner, "the 7in should show the corner between prayers")
        self.assertEqual(["quran", "salaah", "hadith", "duas",
                          "wudu", "nasheeds", "settings", "world"],
                         [t.name for t in w.side.corner.tiles])

    def test_the_posture_takes_the_small_screen_back_during_a_prayer(self):
        w = self.window()
        w.open_prayer("dhuhr")
        w.start("dhuhr", w.school.prayers["dhuhr"][0])
        APP.processEvents()
        self.assertFalse(w.side.showing_corner, "the posture is what matters during a prayer")

    def test_touching_the_quran_opens_the_list_on_the_big_screen(self):
        w = self.window()
        w.side.corner.tiles[0].click()
        APP.processEvents()
        self.assertTrue(w.reading, "the big screen should have opened the corner")
        self.assertIs(w.surah_list, w.corner_screen.currentWidget())

    def test_a_touch_during_a_prayer_is_ignored(self):
        """Mid-prayer the big screen is busy and a touch on the 7in is most likely a knee."""
        w = self.window()
        w.open_prayer("asr")
        w.start("asr", w.school.prayers["asr"][0])
        APP.processEvents()
        w.open_corner("quran")
        self.assertFalse(w.reading, "the prayer should not be shoved aside")

    def test_the_two_reading_tiles_open_something(self):
        """Both of these used to say "not filled in yet". They are filled in.

        There were three. The third was the six kalima, which are reached from the du'a menu
        now; its square on this menu is Salaah, and that is a way out rather than something to
        read, so it is tested with the rest of the way out."""
        w = self.window()
        by_name = {t.name: t for t in w.side.corner.tiles}
        for which in ("quran", "duas"):
            by_name[which].click()
            APP.processEvents()
            self.assertTrue(w.reading, which)
            self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget(),
                             f"{which} should no longer land on the empty page")

    def test_the_salaah_tile_is_the_way_to_the_prayers(self):
        """It landed on the front door when the tile was new. Harry moved it on: a square with
        a prayer mat and the word Salaah should open the prayers, not the screen you came in
        by, which is one touch further out."""
        w = self.window()
        by_name = {t.name: t for t in w.side.corner.tiles}
        self.assertIn("salaah", by_name, "the Salaah tile is not on the menu")
        self.assertNotIn("kalima", by_name, "the kalima square is still there")
        by_name["salaah"].click()
        APP.processEvents()
        self.assertIs(w.home, w.stack.currentWidget())
        self.assertFalse(w.reading, "it should leave the Knowledge Corner, not read in it")

    def test_a_section_whose_file_is_missing_still_says_so(self):
        """The fallback has not been thrown away: a mat whose assets were half copied lands on
        the plain word rather than an empty screen that looks broken."""
        w = self.window()
        w.section_lists["duas"].passages._items = []
        w.open_corner("duas")
        APP.processEvents()
        self.assertIs(w.corner_soon, w.corner_screen.currentWidget())


class QuranTest(unittest.TestCase):
    """The Qur'an on the big screen: the list of 114, and reading one as an open book."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_all_one_hundred_and_fourteen_are_listed(self):
        w = self.window()
        w.open_corner_list()            # the list is built when it is opened, not at start-up
        settle()
        rows = w.surah_list.findChildren(QtWidgets.QPushButton)
        rows = [b for b in rows if b.objectName() == "surahRow"]
        self.assertEqual(114, len(rows))

    def test_each_is_named_in_arabic_and_in_english(self):
        w = self.window()
        w.open_corner_list()
        settle()
        said = [x.text() for x in w.surah_list.findChildren(QtWidgets.QLabel)]
        for wanted in ("Al-Fatihah", "الفاتحة", "An-Nas", "الناس", "Al-Mu'minun"):
            self.assertIn(wanted, said, f"{wanted} is missing from the list")

    def test_opening_one_shows_that_surah(self):
        w = self.window()
        w.open_surah(23)
        settle()
        self.assertIn("Al-Mu'minun", w.reader.title.text())
        self.assertIn("المؤمنون", w.reader.title.text())

    def every_verse_once(self, w, number, lang):
        """The invariant that matters: the pages between them hold every verse of the surah,
        each exactly once, in order. A reader that quietly drops a verse would be far worse
        than one that looked wrong."""
        w.settings.lang = lang
        w.open_surah(number)
        settle()
        spread = w.reader.spread
        seen = []
        for start, end in spread.pages:
            seen.extend(v.number for v in spread.verses[start:end])
        wanted = list(range(1, w.quran.surah(number).verses + 1))
        self.assertEqual(wanted, seen,
                         f"surah {number} in {lang or 'arabic'}: the pages do not add up")
        self.assertTrue(all(end > start for start, end in spread.pages), "an empty page")

    def test_the_pages_hold_every_verse_exactly_once(self):
        w = self.window()
        for number, lang in ((1, "en"), (23, "en"), (2, "en"), (36, ""), (112, "ur"),
                             (18, "fr"), (55, "zh"), (114, "es"), (9, "")):
            self.every_verse_once(w, number, lang)

    def test_a_long_surah_takes_more_than_one_page(self):
        w = self.window()
        w.settings.lang = "en"
        w.open_surah(2)
        settle()
        self.assertGreater(w.reader.spread.pages_count, 10, "Al-Baqarah is 286 verses")

    def test_a_short_one_fits_on_a_single_page(self):
        w = self.window()
        w.settings.lang = "en"
        w.open_surah(112)
        settle()
        self.assertEqual(1, w.reader.spread.pages_count, "Al-Ikhlas is four verses")

    def test_the_arrows_say_where_you_are_now_that_the_words_do_not(self):
        """"Page 1 of 39" has gone from the bar -- it was the widest thing in a crowded row --
        so the arrows carry it: greyed out at the ends, live in between.

        This replaces a test that read the page count off that label. The bug it guarded is
        still worth guarding: the count used to be worked out before the widget had a size, so
        it said 50 when it was 8. Turning to what the reader thinks is the last page and
        finding the forward arrow dead proves the same thing without the label."""
        w = self.window()
        w.settings.lang = "en"
        w.open_surah(23)
        settle()
        r = w.reader
        pages = r.spread.pages_count
        self.assertGreater(pages, 1, "surah 23 with a translation should be several pages")
        self.assertFalse(r.earlier.isEnabled(), "nothing before the first page")
        self.assertTrue(r.later.isEnabled())
        for _ in range(pages - 1):
            r.turn(True)
        settle()
        self.assertTrue(r.earlier.isEnabled())
        self.assertFalse(r.later.isEnabled(),
                         "the count is wrong: there was still a page after the last one")

    def test_the_bar_no_longer_spells_out_the_page(self):
        w = self.window()
        w.open_surah(2)
        settle()
        said = " ".join(x.text() for x in w.reader.findChildren(QtWidgets.QLabel))
        self.assertNotIn("Page", said)
        self.assertNotIn(" of ", said)

    def test_turning_past_either_end_does_nothing(self):
        w = self.window()
        w.open_surah(112)
        settle()
        self.assertFalse(w.reader.turn(False), "there is nothing before the first page")
        self.assertFalse(w.reader.turn(True), "nor after the last")

    def test_turning_forward_and_back_comes_home(self):
        w = self.window()
        w.settings.lang = "en"
        w.open_surah(2)
        settle()
        first = w.reader.spread.pages[0]
        self.assertTrue(w.reader.turn(True))
        self.assertNotEqual(first, w.reader.spread.pages[w.reader.spread.at])
        self.assertTrue(w.reader.turn(False))
        self.assertEqual(0, w.reader.spread.at)

    def test_with_no_translation_the_arabic_takes_both_pages(self):
        w = self.window(lang="")
        w.open_surah(36)
        settle()
        spread = w.reader.spread
        self.assertFalse(spread.translated)
        self.assertTrue(spread.left.isVisible() and spread.right.isVisible())
        self.assertFalse(spread.parallel.isVisible())
        self.assertTrue(spread.right.lines, "the right page is read first and must be filled")
        self.assertTrue(spread.left.lines, "and the left page carries the rest")

    def test_with_a_translation_it_is_the_left_page(self):
        w = self.window(lang="en")
        w.open_surah(36)
        settle()
        spread = w.reader.spread
        self.assertTrue(spread.translated)
        self.assertTrue(spread.parallel.isVisible())
        self.assertFalse(spread.left.isVisible() or spread.right.isVisible())
        self.assertTrue(all(spread.parallel.meaning), "every verse should have its meaning")

    def test_every_language_we_have_is_offered_and_hindi_is_not_pretended(self):
        """The source has no Hindi. Offering it and showing English would be worse than five."""
        # The Qur'an carries five of the mat's six languages; there is no Hindi text for it.
        # Checked on what the reader will actually set beside the Arabic, since the row of
        # buttons that used to advertise this has gone.
        self.assertEqual({"en", "fr", "ur", "es", "zh"}, set(self.window().quran.languages()))
        for lang, want in (("fr", "fr"), ("zh", "zh"), ("hi", ""), ("ar", "")):
            with self.subTest(lang):
                w = self.window(lang=lang)
                w.open_surah(1)
                settle()
                self.assertEqual(want, w.reader.meaning_language())

    def test_the_surah_is_read_in_the_mats_language(self):
        """The row of language buttons on this bar has gone -- see the note in reading.py.
        Harry asked for them out: the left-hand page should already be in the language the mat
        is set to, without being told again here."""
        w = self.window(lang="fr")
        w.open_surah(1)
        settle()
        self.assertEqual("fr", w.reader.meaning_language())
        self.assertEqual({}, w.reader.buttons, "the buttons are back")
        self.assertTrue(any("Allah" in m or "Dieu" in m for m in w.reader.spread.parallel.meaning),
                        w.reader.spread.parallel.meaning[:2])

    def test_urdu_is_laid_out_right_to_left(self):
        w = self.window(lang="ur")
        w.open_surah(1)
        settle()
        self.assertTrue(w.reader.spread.parallel.meaning_rtl, "Urdu reads the other way")

    def test_a_swipe_turns_the_page(self):
        from salaah.qt import QtCore, QtGui
        w = self.window(lang="en")
        w.open_surah(2)
        settle()
        spread = w.reader.spread
        was = spread.at
        middle = spread.rect().center()
        for kind, where in ((QtCore.QEvent.Type.MouseButtonPress, middle),
                            (QtCore.QEvent.Type.MouseButtonRelease,
                             QtCore.QPoint(middle.x() - 400, middle.y()))):
            APP.sendEvent(spread, QtGui.QMouseEvent(
                kind, QtCore.QPointF(where), Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(was + 1, spread.at, "a swipe leftwards should go forward")

    def test_a_small_wobble_is_not_a_swipe(self):
        """A finger resting on the page, or a tap that drifts, must not turn it."""
        from salaah.qt import QtCore, QtGui
        w = self.window(lang="en")
        w.open_surah(2)
        settle()
        spread = w.reader.spread
        was = spread.at
        middle = spread.rect().center()
        for kind, where in ((QtCore.QEvent.Type.MouseButtonPress, middle),
                            (QtCore.QEvent.Type.MouseButtonRelease,
                             QtCore.QPoint(middle.x() - 8, middle.y()))):
            APP.sendEvent(spread, QtGui.QMouseEvent(
                kind, QtCore.QPointF(where), Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(was, spread.at)

    def test_the_list_is_not_built_until_somebody_asks_for_it(self):
        """114 rows is the better part of six hundred widgets. Most times the mat is switched
        on nobody opens this screen at all, and a Pi should not pay for it."""
        w = self.window()
        self.assertFalse(w.surah_list.filled, "the list should be empty until it is opened")
        w.open_corner_list()
        settle()
        self.assertTrue(w.surah_list.filled)

    def test_there_is_a_way_back_to_the_mosque_from_the_list(self):
        """It lived on the list itself; it lives in the banner above the list now. Either way
        the only escape from 114 surahs must not be the power button."""
        w = self.window()
        w.open_corner_list()
        settle()
        back = next((b for b in w.corner_page.findChildren(QtWidgets.QPushButton)
                     if b.objectName() == "mainScreen" and b.isVisible()), None)
        self.assertIsNotNone(back, "no way back to the mosque from the surah list")
        back.click()
        settle()
        self.assertFalse(w.reading)

    def test_the_reader_goes_back_to_the_list(self):
        w = self.window()
        w.open_surah(23)
        settle()
        w.reader.back_button.click()
        settle()
        self.assertIs(w.surah_list, w.corner_screen.currentWidget())


class PassageScreenTest(unittest.TestCase):
    """The du'a and kalima screens: the list, one open, and the note about the kalima."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_all_ten_are_still_reachable_through_the_kinds(self):
        """Ten du'as went in and ten must come out. Filing them under kinds is no good if one
        of them ends up behind a tile nobody can reach."""
        from salaah.duamenu import CATEGORIES, NOT_A_KIND
        w = self.window()
        w.open_corner("duas")
        settle()
        self.assertIs(w.dua_menu, w.corner_screen.currentWidget())
        seen, drawn = set(), 0
        for cat in (c for c in CATEGORIES if c not in NOT_A_KIND):
            w.open_dua_category(cat)
            settle()
            if w.corner_screen.currentWidget() is not w.dua_board:
                continue
            board = w.dua_board
            drawn += len(board.cards)
            seen.update(item.key for _, item in board.wanted())
        self.assertEqual({d.key for d in w.duas.items}, seen, "a du'a is behind no tile at all")
        self.assertGreaterEqual(len(seen), 48, "du'as have gone missing from the menu")
        self.assertEqual(2 * len([c for c in CATEGORIES if c not in NOT_A_KIND]), drawn, "every kind should draw exactly two")

    def test_the_shuffle_can_reach_every_dua_and_not_just_the_first_two(self):
        """Only two of a kind are shown at a time now, so 'reachable' means the shuffle will
        get to it. A pick that always returned the same two would pass the test above -- every
        du'a would still be FILED behind a tile -- while half of them were never once seen.

        Drawn from pick() two hundred times a kind rather than by opening screens: it is the
        same call the screen makes, it is fast, and two hundred draws makes a false alarm about
        one in 10^25 rather than one run in a hundred.
        """
        from salaah.duamenu import CATEGORIES, NOT_A_KIND
        w = self.window()
        board = w.dua_board
        for cat in (c for c in CATEGORIES if c not in NOT_A_KIND):
            board.only = cat
            whole = {item.key for _, item in board.wanted()}
            self.assertGreaterEqual(len(whole), 3, f"{cat} has too few to shuffle")
            reached = set()
            for _ in range(200):
                got = board.pick()
                self.assertEqual(2, len(got), f"{cat} picked {len(got)}")
                reached.update(item.key for _, item in got)
            self.assertEqual(whole, reached,
                             f"{cat}: the shuffle never reaches {sorted(whole - reached)}")

    def test_choosing_one_opens_it_and_back_returns_to_the_list(self):
        w = self.window()
        w.open_corner("duas")
        settle()
        w.open_dua_category("guidance")
        settle()
        board = w.dua_board
        # Whichever card is on screen, not a du'a named here: only two of the kind are shown
        # and which two is shuffled, so hunting for one by reference passed or failed on the
        # luck of the draw.
        card = board.cards[0]
        card.opened.emit(card.index)
        settle()
        reader = w.corner_screen.currentWidget()
        self.assertIs(w.section_readers["duas"], reader)
        self.assertIn(card.item.ref, reader.title.text(),
                      f"opened {reader.title.text()!r}, expected {card.item.ref}")
        reader.back_button.click()
        settle()
        self.assertIs(board, w.corner_screen.currentWidget())
        self.assertEqual("guidance", board.only,
                         "Back dropped the kind and went somewhere else")

    def test_nothing_on_either_screen_says_it_is_waiting_to_be_checked(self):
        """The kalima screens used to carry a line saying the Arabic was pending review. Harry
        has read it, so the line is gone -- and gone rather than merely hidden, which is what
        this checks by looking at every word on both screens."""
        w = self.window()
        for which in ("duas", "kalima"):
            for screen in (w.section_lists[which], w.section_readers[which]):
                w.open_passage(which, 0)
                settle()
                said = " ".join(x.text() for x in screen.findChildren(QtWidgets.QLabel)).lower()
                for word in ("waiting", "checked", "pending", "unchecked"):
                    self.assertNotIn(word, said, f"{which} still mentions being {word}")

    def test_what_each_section_has_been_translated_into(self):
        """The du'as carry five languages and the kalima only English.

        This used to be read off the row of buttons on the reading bar, which listed what the
        section had. The bar has no buttons now, so it is read off the section itself -- which
        is where the answer always came from, and is the thing that decides whether a mat set
        to Chinese gets Chinese du'as or falls back to English.
        """
        w = self.window()
        self.assertEqual(["en", "fr", "ur", "es", "zh"],
                         list(w.section_lists["duas"].passages.languages()))
        self.assertEqual(["en"], list(w.section_lists["kalima"].passages.languages()))
        for section in ("duas", "kalima"):
            w.open_passage(section, 0)
            settle()
            self.assertEqual({}, w.section_readers[section].buttons,
                             f"the {section} bar still carries language buttons")

    def test_the_meaning_shown_is_the_mats_language(self):
        """This used to press a language button on the reader's own bar. The bar has none now
        -- the mat is asked once, in Settings -- so the same claim is made by opening the same
        du'a on two mats set to two languages."""
        english = self.window()
        english.open_passage("duas", 0)
        settle()
        said = english.section_readers["duas"].meaning.text()

        chinese = self.window(lang="zh")
        chinese.open_passage("duas", 0)
        settle()
        other = chinese.section_readers["duas"].meaning.text()

        self.assertTrue(said.strip() and other.strip())
        self.assertNotEqual(said, other, "the du'a reads the same in English and Chinese")
        self.assertEqual({}, chinese.section_readers["duas"].buttons,
                         "the reader still has language buttons on it")

    def test_a_kalima_keeps_english_when_the_reading_language_is_chinese(self):
        """Choosing Chinese for the Qur'an must not leave the kalima screen blank."""
        w = self.window(lang="zh")
        w.open_passage("kalima", 0)
        settle()
        reader = w.section_readers["kalima"]
        self.assertTrue(reader.meaning.text().strip())
        self.assertEqual("en", reader.language())

    def test_the_arrows_move_between_passages(self):
        w = self.window()
        w.open_passage("duas", 0)
        settle()
        reader = w.section_readers["duas"]
        self.assertFalse(reader.earlier.isEnabled(), "nothing before the first")
        first = reader.arabic.lines[0]
        reader.later.click()
        settle()
        self.assertNotEqual(first, reader.arabic.lines[0])
        self.assertTrue(reader.earlier.isEnabled())
        # The last one, whatever number that is -- hard-coding 9 made this test go stale the
        # moment more du'as were added, and it failed by saying the arrow worked when the
        # index simply was not the end any more.
        w.open_passage("duas", len(w.duas.items) - 1)
        settle()
        self.assertFalse(reader.later.isEnabled(), "nothing after the last")

    def test_nothing_is_clipped_on_any_passage_in_either_section(self):
        """Measured off the drawn text, not off the layout's opinion of it. A wrapped label
        reporting a size hint twice its height is exactly what a clipped one looks like, and
        the only way to know is to ask the font how tall the words really are."""
        w = self.window()
        bad = []
        for which, count in (("duas", 10), ("kalima", 6)):
            for i in range(count):
                w.open_passage(which, i)
                settle()
                reader = w.section_readers[which]
                for name, label in (("said", reader.said), ("meaning", reader.meaning)):
                    metrics = QtGui.QFontMetrics(label.font())
                    tall = metrics.boundingRect(QtCore.QRect(0, 0, label.width(), 0),
                                                Qt.TextFlag.TextWordWrap, label.text()).height()
                    if tall > label.height():
                        bad.append(f"{which}[{i}] {name}: needs {tall}px, has {label.height()}px")
        self.assertEqual([], bad)

    def test_the_arabic_is_never_drawn_too_small_to_read(self):
        from salaah.passages import ARABIC_FLOOR
        w = self.window()
        for which, count in (("duas", 10), ("kalima", 6)):
            for i in range(count):
                w.open_passage(which, i)
                settle()
                box = w.section_readers[which].arabic
                self.assertTrue(box.lines and box.lines[0].strip(), f"{which}[{i}] has no Arabic")
                self.assertGreaterEqual(box.height(), ARABIC_FLOOR,
                                        f"{which}[{i}] has no room for the script")

    def test_both_sections_survive_the_dark_screen(self):
        w = self.window(theme="dark")
        for which in ("duas", "kalima"):
            w.open_passage(which, 0)
            settle()
            w.grab().save(str(SHOTS / f"{which}-dark.png"))
            self.assertTrue(w.section_readers[which].arabic.lines)


class FakePlayer:
    """Stands in for the real player so a test can say exactly where in the audio it is."""

    available = True

    def __init__(self):
        self.at = 0.0
        self.on = False
        self.played = []
        self.stops = 0

    @property
    def busy(self):
        return self.on

    def play(self, path, span, times=1):
        self.played.append(Path(path).name)
        self.on = True
        self.at = 0.0
        return True

    def stop(self):
        self.on = False
        self.stops += 1

    def position(self):
        return self.at if self.on else None

    def set_volume(self, volume):
        pass

    def finish(self):
        """The recording has run out."""
        self.on = False


class ReciteTest(unittest.TestCase):
    """Reciting a surah on the big screen, with the word going red as it is said."""

    def window(self, surah=1, verses=8, **settings):
        """Set to Arabic only unless a test says otherwise.

        These tests read the spread's right and left pages, which is the layout you get when
        there is no meaning to put on the left. That used to be what a mat with nothing chosen
        looked like; the mat now comes up in English and puts the meaning there, so the layout
        under test has to be asked for by name. The one test that wants a meaning passes its
        own language.
        """
        import tempfile
        from salaah.recite import Store
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False,
                                   "lang": "ar", **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        room = Path(tempfile.mkdtemp())
        w.verses = Store(room=room, opener=_offline)
        for v in range(1, verses + 1):          # pretend they are already downloaded
            path = w.verses.path_for(surah, v)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ID3" + b"\0" * 4000)
        w.recitation = FakePlayer()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents(),
                                 __import__("shutil").rmtree(room, ignore_errors=True)))
        return w

    def test_pressing_recite_starts_the_first_verse_of_the_page(self):
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        self.assertFalse(r.reciting)
        r.recite_button.click()
        settle()
        self.assertTrue(r.reciting)
        self.assertEqual(["001001.mp3"], w.recitation.played)
        self.assertEqual("1:1", r.saying.text())

    def test_the_word_being_said_is_the_word_that_is_lit(self):
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        for start_word, _end, start_ms, end_ms in w.word_times.words(1, 1):
            w.recitation.at = (start_ms + end_ms) / 2000.0
            r.tick()
            settle()
            self.assertEqual((0, start_word), r.spread.right.highlight,
                             f"at {w.recitation.at:.2f}s the wrong word was lit")

    def test_the_lit_word_is_really_drawn_red(self):
        """Setting a highlight and drawing one are different claims. This one counts pixels."""
        from salaah import theme
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        want = QtGui.QColor(theme.palette().highlight)

        def redness():
            image = r.spread.right.grab().toImage()
            count = 0
            for y in range(image.height()):
                for x in range(image.width()):
                    c = QtGui.QColor(image.pixel(x, y))
                    if (abs(c.red() - want.red()) < 50 and abs(c.green() - want.green()) < 50
                            and abs(c.blue() - want.blue()) < 50):
                        count += 1
            return count
        r.spread.clear_highlight()
        settle()
        dark = redness()
        w.recitation.at = 1.0
        r.tick()
        settle()
        self.assertIsNotNone(r.spread.right.highlight)
        self.assertGreater(redness(), dark + 30, "the highlight was set but nothing went red")

    def test_it_moves_on_to_the_next_verse_when_one_finishes(self):
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        w.recitation.finish()
        r.tick()
        settle()
        self.assertEqual(["001001.mp3", "001002.mp3"], w.recitation.played)
        self.assertEqual("1:2", r.saying.text())

    def test_it_stops_itself_at_the_end_of_the_surah(self):
        w = self.window(surah=1, verses=7)
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        for _ in range(8):
            w.recitation.finish()
            r.tick()
            settle()
        self.assertFalse(r.reciting, "it should have stopped at the end rather than run on")
        self.assertEqual("", r.saying.text())

    def test_the_page_turns_to_follow_the_recitation(self):
        w = self.window(surah=2, verses=60)
        w.open_surah(2)
        settle()
        r = w.reader
        self.assertGreater(r.spread.pages_count, 1, "Al-Baqarah should be many pages")
        r.recite_button.click()
        settle()
        first_page = r.spread.at
        seen = {first_page}
        for _ in range(60):
            w.recitation.finish()
            r.tick()
            settle()
            seen.add(r.spread.at)
            if len(seen) > 1:
                break
        self.assertGreater(len(seen), 1, "the page never turned to keep up with the reciting")

    def test_no_word_is_lit_on_the_twelve_verses_we_cannot_be_sure_of(self):
        """2:72 is one of the twelve where our text and the timings disagree about where a word
        ends. Lighting a word there would light the wrong one."""
        w = self.window(surah=2, verses=80)
        w.open_surah(2)
        settle()
        r = w.reader
        self.assertTrue(w.word_times.whole_only(2, 72))
        verses = r.spread.verses
        r.at_verse = next(i for i, v in enumerate(verses) if v.number == 72)
        r.reciting = True
        r.waiting = False
        w.recitation.play(w.verses.path_for(2, 72), None)
        w.recitation.at = 1.0
        r.tick()
        settle()
        self.assertIsNone(r.spread.right.highlight)
        self.assertIsNone(r.spread.left.highlight)
        self.assertIsNone(r.spread.parallel.highlight)

    def test_a_verse_on_the_left_page_lights_on_the_left_page(self):
        """Without a translation the page is split down the middle, right page read first, so
        a verse in the second half sits in a different box at a different row. Dropping that
        offset lights a word on the wrong half of the spread, and every test that only ever
        recited the first verse of a page would sail straight past it."""
        w = self.window(surah=1, verses=8)
        w.open_surah(1)
        settle()
        r = w.reader
        start, end = r.spread.pages[r.spread.at]
        half = (end - start + 1) // 2
        self.assertLess(half, end - start, "this surah needs verses on both pages")
        index = start + half                      # the first verse of the left page
        r.at_verse = index
        r.reciting = True
        r.waiting = False
        number = r.spread.verses[index].number
        w.recitation.play(w.verses.path_for(1, number), None)
        words = w.word_times.words(1, number)
        w.recitation.at = (words[0][2] + words[0][3]) / 2000.0
        r.tick()
        settle()
        self.assertEqual((0, words[0][0]), r.spread.left.highlight,
                         "the left page should light its own first row")
        self.assertIsNone(r.spread.right.highlight, "and the right page should go dark")

    def test_the_twelve_are_refused_even_if_timings_turned_up_for_them(self):
        """The built data carries no word timings for those twelve, so nothing lights whatever
        the code does. That is belt and braces, not a reason to leave the braces untested: if
        a future build ever did emit timings for one of them, the code must still refuse."""
        w = self.window(surah=2, verses=80)
        w.open_surah(2)
        settle()
        r = w.reader
        real = w.word_times.words

        def pretend(surah, verse):
            if (surah, verse) == (2, 72):
                return [[0, 1, 0, 5000]]          # timings that should not be trusted
            return real(surah, verse)
        w.word_times.words = pretend
        self.addCleanup(lambda: setattr(w.word_times, "words", real))
        self.assertIsNotNone(w.word_times.word_at(2, 72, 1.0), "the pretence must be in place")

        verses = r.spread.verses
        r.at_verse = next(i for i, v in enumerate(verses) if v.number == 72)
        r.spread.go_to(r.spread.page_of(r.at_verse))
        r.reciting = True
        r.waiting = False
        w.recitation.play(w.verses.path_for(2, 72), None)
        w.recitation.at = 1.0
        r.tick()
        settle()
        self.assertIsNone(r.spread.right.highlight)
        self.assertIsNone(r.spread.left.highlight)
        self.assertIsNone(r.spread.parallel.highlight)

    def test_a_word_is_lit_on_the_verse_right_after_one_of_the_twelve(self):
        """So the fallback is confined to the verse it belongs to, and does not leak onward."""
        w = self.window(surah=2, verses=80)
        w.open_surah(2)
        settle()
        r = w.reader
        verses = r.spread.verses
        r.at_verse = next(i for i, v in enumerate(verses) if v.number == 73)
        r.reciting = True
        r.waiting = False
        page = r.spread.page_of(r.at_verse)
        r.spread.go_to(page)
        w.recitation.play(w.verses.path_for(2, 73), None)
        words = w.word_times.words(2, 73)
        w.recitation.at = (words[0][2] + words[0][3]) / 2000.0
        r.tick()
        settle()
        lit = (r.spread.right.highlight, r.spread.left.highlight)
        self.assertTrue(any(x is not None for x in lit), "2:73 should still light its words")

    def test_leaving_the_book_stops_the_recitation(self):
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        self.assertTrue(r.reciting)
        w.go_home()
        settle()
        self.assertFalse(r.reciting)
        self.assertGreater(w.recitation.stops, 0, "the player should have been told to stop")

    def test_the_call_to_prayer_silences_it(self):
        """The azaan comes home first, and coming home stops the reciting -- so the two are
        never heard over each other."""
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        w.call_to_prayer("dhuhr")
        settle()
        self.assertFalse(r.reciting)
        if w.call_box is not None:
            w.end_the_call()
            settle()

    def test_it_does_not_fall_asleep_over_the_recitation(self):
        w = self.window()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        w.maybe_sleep()
        settle()
        self.assertFalse(w.asleep, "going to sleep mid-recitation would be the rudest moment")
        self.assertTrue(r.reciting)

    def test_opening_another_surah_stops_it(self):
        w = self.window(surah=1, verses=8)
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        w.open_surah(36)
        settle()
        self.assertFalse(r.reciting)
        self.assertEqual("", r.saying.text())

    def test_with_no_recording_to_be_had_it_says_so_rather_than_hanging(self):
        import urllib.error
        from salaah.recite import Store
        w = self.window()

        def gone(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 404, "nope", {}, None)
        w.verses = Store(room=Path(w.verses.room), opener=gone)
        for leftover in Path(w.verses.room).rglob("*.mp3"):
            leftover.unlink()
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        r.tick()
        settle()
        for _ in range(3):
            r.tick()
            settle()
        self.assertFalse(r.reciting, "it should give up rather than wait for ever")
        self.assertTrue(r.saying.text(), "and say something rather than nothing")

    def test_with_no_player_on_the_machine_the_button_says_so(self):
        w = self.window()
        w.recitation.available = False
        w.open_surah(1)
        settle()
        r = w.reader
        r.recite_button.click()
        settle()
        self.assertFalse(r.reciting)
        self.assertTrue(r.saying.text())

    def test_reciting_works_with_a_translation_on_the_page_too(self):
        w = self.window(lang="en")
        w.open_surah(1)
        settle()
        r = w.reader
        self.assertTrue(r.spread.translated)
        r.recite_button.click()
        settle()
        w.recitation.at = 1.0
        r.tick()
        settle()
        self.assertIsNotNone(r.spread.parallel.highlight,
                             "with a translation the highlight belongs to the parallel view")
        self.assertIsNone(r.spread.right.highlight)


class ArchMenuTest(unittest.TestCase):
    """The kalima sub menu: the same mosque as the front door, with six arches for a menu."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_kalima_open_a_mosque_of_six_arches_not_a_list(self):
        w = self.window()
        w.open_corner("kalima")
        settle()
        self.assertIn("kalima", w.arch_menus)
        self.assertIs(w.arch_menus["kalima"], w.corner_screen.currentWidget())
        self.assertEqual(["1", "2", "3", "4", "5", "6"],
                         [a.prayer for a in w.arch_menus["kalima"].mosque.arches])

    def test_the_duas_open_their_own_kinds_and_not_the_kalima_arches(self):
        """The du'as have a menu of their own now. What matters here is that it is theirs --
        the arch screen belongs to the kalima and must not turn up under Du'as."""
        w = self.window()
        w.open_corner("duas")
        settle()
        self.assertIs(w.dua_menu, w.corner_screen.currentWidget())
        self.assertIsNot(w.arch_menus["kalima"], w.corner_screen.currentWidget())
        w.open_dua_category("worry")
        settle()
        self.assertIs(w.dua_board, w.corner_screen.currentWidget())

    def test_touching_an_arch_opens_that_kalima(self):
        w = self.window()
        w.open_corner("kalima")
        settle()
        for number, expect in ((1, "First"), (3, "Third"), (6, "Sixth")):
            w.open_corner("kalima")
            settle()
            w.arch_menus["kalima"].mosque.chosen.emit(str(number))
            settle()
            reader = w.corner_screen.currentWidget()
            self.assertIs(w.section_readers["kalima"], reader)
            self.assertIn(expect, reader.title.text(), f"arch {number}")

    def test_an_arch_is_touched_where_it_is_drawn(self):
        """Hit-testing, not just the signal: a press in the middle of arch four must choose
        four, so the boxes worked out from the drawing line up with what is on screen."""
        w = self.window()
        w.open_corner("kalima")
        settle()
        mosque = w.arch_menus["kalima"].mosque
        for number in ("1", "4", "6"):
            middle = mosque.arch_centre(number)
            self.assertIsNotNone(middle, number)
            self.assertEqual(number, mosque.arch_at(middle),
                             f"the middle of arch {number} did not land on it")

    def test_the_gaps_between_arches_choose_nothing(self):
        w = self.window()
        w.open_corner("kalima")
        settle()
        mosque = w.arch_menus["kalima"].mosque
        one, two = mosque.arch_centre("1"), mosque.arch_centre("2")
        between = QtCore.QPoint((one.x() + two.x()) // 2, one.y())
        self.assertIsNone(mosque.arch_at(between), "the pillar between two arches is not a choice")

    def test_the_clock_is_on_the_dome_and_follows_the_window(self):
        w = self.window()
        w.open_corner("kalima")
        settle()
        w.tick()
        settle()
        mosque = w.arch_menus["kalima"].mosque
        self.assertRegex(mosque.time_text, r"^\d\d:\d\d$")
        self.assertEqual(w.mosque.time_text, mosque.time_text,
                         "both domes should say the same time")
        self.assertTrue(mosque.clock_box.width() > 0 and mosque.clock_box.height() > 0)

    def test_the_sky_follows_the_time_of_day(self):
        w = self.window()
        w.open_corner("kalima")
        settle()
        menu = w.arch_menus["kalima"]
        menu.follow_clock("06:00", True, 0.3)
        settle()
        self.assertTrue(menu.mosque.sun_up)
        menu.follow_clock("23:00", False, 0.8)
        settle()
        self.assertFalse(menu.mosque.sun_up, "after dark it should be the moon and stars")
        self.assertAlmostEqual(0.8, menu.mosque.through, places=3)

    def test_the_artwork_does_not_paint_over_the_sky(self):
        """The drawing arrived with an opaque background. The sun, moon, stars and birds are
        drawn BEHIND the mosque, so it covered them and the sky sat empty -- the code was
        perfect and showed nothing. The fix knocks the background out to see-through while
        leaving the building and the insides of the arches solid, which is what this checks,
        on the asset, where the property actually lives."""
        image = QtGui.QImage(str(ASSETS / "kalima" / "mosque.png"))
        self.assertFalse(image.isNull())
        self.assertTrue(image.hasAlphaChannel(), "no transparency at all: the sky is boxed in")
        self.assertEqual(0, QtGui.QColor(image.pixelColor(20, 20)).alpha(),
                         "the sky should be see-through")
        import json
        described = json.loads((ASSETS / "kalima" / "mosque.json").read_text(encoding="utf-8"))
        x0, y0, x1, y1 = described["arches"]["3"]["box"]
        inside = image.pixelColor((x0 + x1) // 2, y0 + (y1 - y0) // 3)
        self.assertEqual(255, QtGui.QColor(inside).alpha(),
                         "the inside of an arch should stay solid, as the front door's does")

    def test_the_stars_reach_the_screen(self):
        """Measured as a difference rather than against a fixed count. Counting marks in a band
        and hoping a star had drifted into it passed while the sky was not drawn at all -- the
        mosque's own minarets filled the band -- and then failed at random once the band was
        narrowed, because the birds move and the sun climbs. Emptying the sky and rendering
        again isolates its contribution exactly, and the stars sit at seeded positions, so this
        answers the same way every run."""
        w = self.window()
        w.open_corner("kalima")
        settle()
        menu = w.arch_menus["kalima"]
        menu.follow_clock("23:00", False, 0.5)
        settle()

        def marks():
            image = w.grab().toImage()
            count = 0
            for y0, y1, x0, x1 in ((140, 330, 430, 860), (150, 380, 1080, 1480)):
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        colour = QtGui.QColor(image.pixel(x, y))
                        if colour.red() + colour.green() + colour.blue() < 3 * 235:
                            count += 1
            return count
        with_sky = marks()
        menu.mosque.sky.stars = []
        menu.mosque.sky.birds = []
        menu.mosque.update()
        settle()
        without = marks()
        self.assertGreater(with_sky, without + 20,
                           f"the stars put nothing on the screen ({with_sky} vs {without})")

    def test_the_minarets_do_not_glow_on_a_menu(self):
        """On the front door a glow means no prayer is due. Here it would mean nothing."""
        w = self.window()
        self.assertFalse(w.arch_menus["kalima"].mosque.idle_glow)
        self.assertTrue(w.mosque.idle_glow, "the front door still glows")

    def test_the_birds_only_flutter_while_it_is_on_show(self):
        w = self.window()
        menu = w.arch_menus["kalima"]
        w.open_corner("kalima")
        settle()
        self.assertTrue(menu.mosque.flutter.isActive())
        w.go_home()
        settle()
        self.assertFalse(menu.mosque.flutter.isActive(), "still animating a screen nobody sees")

    def test_there_is_a_way_back_to_the_main_screen(self):
        """The arches used to carry their own way out. Once the banner went in above them there
        was nowhere for it to sit, so it moved up there -- but it must still be there, and it
        must still work, which is what this asks."""
        w = self.window()
        w.open_corner("kalima")
        settle()
        back = self.home_button(w)
        self.assertIsNotNone(back, "no way back to the mosque from the kalima menu")
        back.click()
        settle()
        self.assertFalse(w.reading)

    @staticmethod
    def home_button(w):
        for button in w.corner_page.findChildren(QtWidgets.QPushButton):
            if button.objectName() == "mainScreen" and button.isVisible():
                return button
        return None

    def test_back_from_a_kalima_returns_to_the_arches(self):
        w = self.window()
        w.open_passage("kalima", 2)
        settle()
        w.section_readers["kalima"].back_button.click()
        settle()
        self.assertIs(w.arch_menus["kalima"], w.corner_screen.currentWidget())


class KalimaVoiceTest(unittest.TestCase):
    """Saying a kalima aloud, with the word going red as it is said."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        w.recitation = FakePlayer()
        self.addCleanup(lambda: shut(w))
        return w

    def test_there_is_a_recording_for_each_and_it_can_be_played(self):
        w = self.window()
        for i in range(6):
            w.open_passage("kalima", i)
            settle()
            self.assertTrue(w.section_readers["kalima"].can_say(), f"kalima {i + 1}")

    def test_pressing_play_starts_it_and_pressing_stop_ends_it(self):
        w = self.window()
        w.open_passage("kalima", 0)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        self.assertTrue(r.saying)
        self.assertEqual(["1.mp3"], w.recitation.played)
        r.say_button.click()
        settle()
        self.assertFalse(r.saying)
        self.assertIsNone(r.arabic.highlight)

    def test_the_word_being_said_is_the_word_that_is_lit(self):
        w = self.window()
        w.open_passage("kalima", 0)
        settle()
        r = w.section_readers["kalima"]
        item = r.passages.at(0)
        r.say_button.click()
        settle()
        for i, (start, end) in enumerate(item.times):
            w.recitation.at = (start + end) / 2000.0
            r.tick()
            settle()
            self.assertEqual((0, i), r.arabic.highlight,
                             f"at {w.recitation.at:.2f}s the wrong word was lit")

    def test_the_lit_word_is_really_drawn_red(self):
        from salaah import theme
        w = self.window()
        w.open_passage("kalima", 0)
        settle()
        r = w.section_readers["kalima"]
        want = QtGui.QColor(theme.palette().highlight)

        def redness():
            image = r.arabic.grab().toImage()
            count = 0
            for y in range(image.height()):
                for x in range(image.width()):
                    c = QtGui.QColor(image.pixel(x, y))
                    if (abs(c.red() - want.red()) < 50 and abs(c.green() - want.green()) < 50
                            and abs(c.blue() - want.blue()) < 50):
                        count += 1
            return count
        r.say_button.click()
        settle()
        r.arabic.set_highlight(None)
        settle()
        dark = redness()
        w.recitation.at = (item := r.passages.at(0)).times[1][0] / 1000.0 + 0.01
        r.tick()
        settle()
        self.assertIsNotNone(r.arabic.highlight)
        self.assertGreater(redness(), dark + 30, "the highlight was set but nothing went red")

    def test_it_stops_when_the_recording_runs_out(self):
        w = self.window()
        w.open_passage("kalima", 0)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        w.recitation.finish()
        r.tick()
        settle()
        self.assertFalse(r.saying)
        self.assertIsNone(r.arabic.highlight)

    def test_opening_another_kalima_stops_the_one_playing(self):
        w = self.window()
        w.open_passage("kalima", 0)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        w.open_passage("kalima", 4)
        settle()
        self.assertFalse(r.saying)
        self.assertGreater(w.recitation.stops, 0)

    def test_leaving_the_screen_stops_it(self):
        w = self.window()
        w.open_passage("kalima", 1)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        w.go_home()
        settle()
        self.assertFalse(r.saying)

    def test_the_call_to_prayer_silences_it(self):
        w = self.window()
        w.open_passage("kalima", 1)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        w.call_to_prayer("asr")
        settle()
        self.assertFalse(r.saying)
        if w.call_box is not None:
            w.end_the_call()
            settle()

    def test_it_does_not_fall_asleep_over_a_kalima(self):
        w = self.window()
        w.open_passage("kalima", 5)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        w.maybe_sleep()
        settle()
        self.assertFalse(w.asleep)
        self.assertTrue(r.saying)

    def test_a_duaa_has_a_play_button_now_and_it_stays_awake_too(self):
        """This said the opposite until Harry recorded the du'as: there was nothing to play, so
        the button was not offered. There is now, so a du'a behaves like a kalima -- including
        the part that matters at two in the morning, which is that the mat does not go to sleep
        in the middle of reading one aloud."""
        w = self.window()
        w.open_passage("duas", 0)
        settle()
        r = w.section_readers["duas"]
        self.assertTrue(r.can_say())
        r.say_button.click()
        settle()
        w.maybe_sleep()
        settle()
        self.assertFalse(w.asleep, "it went to sleep while reading a du'a")
        self.assertTrue(r.saying)
        r.stop_saying()
        settle()

    def test_with_no_player_on_the_machine_nothing_happens(self):
        w = self.window()
        w.recitation.available = False
        w.open_passage("kalima", 0)
        settle()
        r = w.section_readers["kalima"]
        r.say_button.click()
        settle()
        self.assertFalse(r.saying)


class SwitchTest(unittest.TestCase):
    """The three yes-or-no settings are switches now, not pairs of circles."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def switches(self, w):
        from salaah.render import Switch
        return {s.objectName(): s for s in w.settings_screen.findChildren(Switch)}

    def test_the_three_that_are_yes_or_no_have_a_switch(self):
        w = self.window()
        self.assertEqual({"azaanSwitch", "cursorSwitch", "recitationSwitch"},
                         set(self.switches(w)))

    def test_each_switch_shows_where_the_setting_actually_is(self):
        w = self.window(azaan=True, cursor=False, recitation=True)
        knobs = self.switches(w)
        self.assertTrue(knobs["azaanSwitch"].isChecked())
        self.assertFalse(knobs["cursorSwitch"].isChecked())
        self.assertTrue(knobs["recitationSwitch"].isChecked())

    def test_flipping_one_changes_the_setting_and_saves_it(self):
        w = self.window(azaan=True, cursor=False)
        knobs = self.switches(w)
        knobs["azaanSwitch"].click()
        settle()
        self.assertFalse(w.settings.azaan)
        knobs["cursorSwitch"].click()
        settle()
        self.assertTrue(w.settings.cursor)

    def test_the_word_beside_it_follows_the_switch(self):
        w = self.window(azaan=True)
        said = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        self.assertIn(w.t("settings.on"), said)
        self.switches(w)["azaanSwitch"].click()
        settle()
        said = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        self.assertIn(w.t("settings.off"), said)

    def test_the_choices_with_more_than_two_answers_are_not_switches(self):
        """A switch is for yes or no. Who is shown, the school, which lettering and how much
        edge all have more than two answers, so none of them may become a switch -- a switch
        cannot say "40 px". Circles for the short lists, a picker for the wordy ones."""
        w = self.window()
        circles = [b for b in w.settings_screen.findChildren(QtWidgets.QRadioButton)
                   if b.objectName() == "choice"]
        self.assertIn("Girl", [b.text() for b in circles], "who is shown stayed as circles")
        pickers = [b for b in w.settings_screen.findChildren(QtWidgets.QComboBox)
                   if b.objectName() == "picker"]
        said = {b.itemText(i) for b in pickers for i in range(b.count())}
        for px in ("0 px", "20 px", "40 px", "60 px"):
            self.assertIn(px, said, "how much edge is not a yes-or-no question")
        for face in ("Traditional", "Clear naskh", "Noto naskh"):
            self.assertIn(face, said, "the lettering is not a yes-or-no question")

    def test_a_switch_is_one_target_rather_than_two_small_ones(self):
        """The point of the change: a finger has one thing to hit, and it is big enough to hit."""
        w = self.window()
        for name, knob in self.switches(w).items():
            self.assertGreaterEqual(knob.width(), w.px(80), name)
            self.assertGreaterEqual(knob.height(), w.px(40), name)


class BannerTest(unittest.TestCase):
    """The black strip across the top: the same one on the front door and in the Qur'an."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": True, "volume": 70,
                                   "place": "Bury", **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        settle()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_knowledge_corner_has_a_banner_too(self):
        w = self.window()
        self.assertEqual(4, len(w.banner_labels),
                         "the mosque, the front door, the corner and Settings")

    def test_both_banners_say_the_same_thing(self):
        w = self.window()
        said = {label.text() for label in w.banner_labels}
        self.assertEqual(1, len(said), "the two banners disagree about the time or the place")

    def test_the_banner_says_where_you_are_and_when_the_prayers_are(self):
        w = self.window()
        for label in w.banner_labels:
            self.assertIn("Bury", label.text())
            for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
                self.assertIn(w.t(f"prayer.{prayer}"), label.text(), prayer)
            self.assertNotIn("next", label.text().lower(),
                             "what is next was dropped: the five times already say it")

    def test_the_corner_banner_is_on_screen_while_reading(self):
        w = self.window()
        w.open_surah(2)
        settle()
        showing = [label for label in w.banner_labels if label.isVisible()]
        self.assertTrue(showing, "the corner's banner should be up while a surah is open")
        self.assertIn("Bury", showing[0].text())

    def test_the_banner_slider_is_drawn_as_a_slider_and_not_a_white_box(self):
        """It was a white rectangle with a bar across it: the blanket QWidget rule painted the
        slider's own background paper-white, which is invisible in the layout and plain the
        moment it is rendered. A slider on a black banner is mostly black."""
        w = self.window(volume=40)
        bar = w.volume_bars[0][0]
        where = bar.mapTo(w, bar.rect().topLeft())
        image = w.grab().toImage()
        pale = total = 0
        for y in range(where.y(), where.y() + bar.height()):
            for x in range(where.x(), where.x() + bar.width()):
                colour = QtGui.QColor(image.pixel(x, y))
                total += 1
                if colour.red() > 240 and colour.green() > 240 and colour.blue() > 240:
                    pale += 1
        self.assertLess(pale / total, 0.5,
                        f"{pale}/{total} of the slider is paper-white; it is a box, not a slider")


class VolumeEverywhereTest(unittest.TestCase):
    """One notion of volume, however many controls are showing it."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": True, "volume": 60,
                                   **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_there_is_one_slider_in_each_banner_and_none_below(self):
        """There were briefly two within a centimetre of each other in the Qur'an: one in the
        banner and one in the row under it. The banner's is the one that stayed."""
        w = self.window()
        self.assertEqual(4, len(w.volume_bars),
                         "the mosque, the front door, the corner and Settings")
        w.open_surah(2)
        settle()
        from salaah.qt import QtWidgets as Q
        inside = w.reader.findChildren(Q.QSlider)
        self.assertEqual([], inside, "the reader should have no slider of its own")

    def test_they_all_start_where_the_setting_is(self):
        w = self.window(volume=45)
        for bar, read in w.volume_bars:
            self.assertEqual(45, bar.value())
            self.assertEqual("45%", read.text())

    def test_moving_one_moves_the_others(self):
        """Otherwise the banner sits claiming it is loud while the Qur'an has been turned down."""
        w = self.window(volume=60)
        w.volume_bars[0][0].setValue(25)
        settle()
        self.assertEqual(25, w.settings.volume)
        for bar, read in w.volume_bars:
            self.assertEqual(25, bar.value())
            self.assertEqual("25%", read.text())

    def test_all_the_way_down_is_silence(self):
        """The same thing the prayer screen's bar has always meant, so the two agree."""
        w = self.window(volume=60)
        w.volume_bars[0][0].setValue(0)
        settle()
        self.assertFalse(w.settings.recitation, "silence should switch the recitation off")
        self.assertEqual(60, w.settings.volume, "and remember the level to come back to")

    def test_turning_it_off_in_settings_shows_as_silence_on_every_slider(self):
        w = self.window(volume=60)
        w.set_recitation("0")
        w.show_volume()
        settle()
        for bar, read in w.volume_bars:
            self.assertEqual(0, bar.value())
            self.assertEqual("0%", read.text())


class ReaderBarTest(unittest.TestCase):
    """What is left in the Qur'an reader's top row, and what has gone from it."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": True, **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_way_out_is_called_back(self):
        w = self.window()
        w.open_surah(2)
        settle()
        self.assertEqual("Back", w.reader.back_button.text())

    def test_it_still_goes_back_to_the_list(self):
        w = self.window()
        w.open_surah(2)
        settle()
        w.reader.back_button.click()
        settle()
        self.assertIs(w.surah_list, w.corner_screen.currentWidget())

    def test_the_page_is_not_spelled_out_any_more(self):
        w = self.window()
        w.open_surah(2)
        settle()
        said = " ".join(x.text() for x in w.reader.findChildren(QtWidgets.QLabel))
        self.assertNotIn("Page", said)

    def test_nothing_in_the_row_is_squashed(self):
        """The row had run out of room, which is why the page readout went. Every language is
        checked, because the words are longer in some of them."""
        for lang in ("", "en", "fr", "ur"):
            w = self.window(lang=lang)
            w.open_surah(2)
            settle()
            r = w.reader
            tight = [name for name, widget in
                     [("back", r.back_button), ("recite", r.recite_button),
                      ("earlier", r.earlier), ("later", r.later)]
                     + [(f"tongue {k or 'ar'}", b) for k, b in r.buttons.items()]
                     if widget.width() < widget.sizeHint().width()]
            self.assertEqual([], tight, f"squashed with lang={lang!r}")
            w.close()
            settle()

    def test_the_arrows_still_turn_the_pages(self):
        w = self.window()
        w.open_surah(2)
        settle()
        r = w.reader
        self.assertEqual(0, r.spread.at)
        r.later.click()
        settle()
        self.assertEqual(1, r.spread.at)
        r.earlier.click()
        settle()
        self.assertEqual(0, r.spread.at)


class FajrCallTest(unittest.TestCase):
    """Fajr has its own call, because the words at dawn are not the same."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, "azaan": True,
                                   **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_fajr_has_a_recording_of_its_own(self):
        w = self.window()
        self.assertEqual("azaan-fajr.mp3", w.azaan_for("fajr").name)

    def test_the_other_four_share_the_ordinary_one(self):
        w = self.window()
        for prayer in ("dhuhr", "asr", "maghrib", "isha"):
            self.assertEqual("azaan.mp3", w.azaan_for(prayer).name, prayer)

    def test_calling_fajr_plays_the_fajr_recording(self):
        w = self.window()
        played = []

        class Player:
            volume = 80
            playing = True

            def play(self, path):
                played.append(Path(path).name)
                return True

            def stop(self):
                pass
        w.call = Player()
        w.call_to_prayer("fajr")
        settle()
        self.assertEqual(["azaan-fajr.mp3"], played)
        self.assertIsNotNone(w.call_box, "and the notice still says it is time")
        w.end_the_call()
        settle()

    def test_with_no_fajr_recording_it_stays_silent_rather_than_saying_the_wrong_words(self):
        """The fallback that was the whole behaviour before the recording arrived, and is still
        right: the notice appears, nothing is said, because the ordinary call says words that do
        not belong to Fajr.

        This used to replace azaan_for with a stub that returned None, which tested the stub and
        not the app -- deleting the real fallback broke nothing. So it gives the window a folder
        holding only the ordinary recording and asks the real method.
        """
        import shutil
        import tempfile
        w = self.window()
        room = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(room, ignore_errors=True))
        (room / "audio").mkdir()
        shutil.copy(ASSETS / "audio" / "azaan.mp3", room / "audio" / "azaan.mp3")
        w.assets = room
        self.assertIsNone(w.azaan_for("fajr"), "Fajr must not be given the ordinary call")
        self.assertEqual("azaan.mp3", w.azaan_for("isha").name, "the others still have theirs")

        played = []

        class Player:
            volume = 80
            playing = False

            def play(self, path):
                played.append(Path(path).name)
                return True

            def stop(self):
                pass
        w.call = Player()
        w.call_to_prayer("fajr")
        settle()
        self.assertEqual([], played)
        self.assertIsNotNone(w.call_box, "but the mat still says it is time")
        w.end_the_call()
        settle()

    def test_a_prayer_with_no_recording_at_all_is_still_announced(self):
        """A half-copied mat has no audio. It should still put the notice up."""
        import tempfile
        w = self.window()
        w.assets = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(w.assets, ignore_errors=True))
        for prayer in ("fajr", "dhuhr"):
            self.assertIsNone(w.azaan_for(prayer), prayer)
        w.call_to_prayer("dhuhr")
        settle()
        self.assertIsNotNone(w.call_box)
        w.end_the_call()
        settle()


class MatchedButtonsTest(unittest.TestCase):
    """The play button is sized off Back beside it, in every language.

    It used to match Back exactly. It is now square and twice Back's height, because the mark on
    it was asked for twice as big -- but it is still MEASURED from Back rather than written down
    as a number, which is the part that cannot be done in the stylesheet."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": True, **settings}),
                       scale=1.0, save_settings=False)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_they_are_the_same_size_whatever_the_word_for_back_is(self):
        """It cannot be done in the stylesheet: Back is Retour in French and Volver in Spanish,
        so its width is only known once it has been styled and laid out, while the glyph is
        always one character. Setting it while building the screen did nothing at all, because
        the stylesheet had not been applied yet."""
        for lang in ("en", "fr", "es", "ur"):
            w = self.window(lang=lang)
            w.open_surah(2)
            settle()
            r = w.reader
            self.assertEqual(r.back_button.height() * 2, r.recite_button.height(),
                             f"in {lang}: Back is {r.back_button.size()}, "
                             f"play is {r.recite_button.size()}")
            self.assertEqual(r.recite_button.height(), r.recite_button.width(),
                             f"in {lang}: the play button is not square")
            self.assertGreater(r.recite_button.width(), 0)
            w.close()
            settle()

    def test_they_stay_matched_when_the_window_is_resized(self):
        w = self.window()
        w.open_surah(2)
        settle()
        w.resize(1280, 800)
        settle()
        r = w.reader
        self.assertEqual(r.back_button.height() * 2, r.recite_button.height())
        self.assertEqual(r.recite_button.height(), r.recite_button.width())


class TwoMosquesTest(unittest.TestCase):
    """The kalima menu and the front door show the same building in the same place.

    Measured off the drawn screens, not off the asset files: what matters is where the minarets
    and the dome land once each screen has laid itself out, banner and all."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        settle()
        # The birds drift and the stars twinkle, and both are drawn in the same white as the
        # building. Left in, the topmost ink in a band is whichever bird happens to be passing.
        for screen in (w.mosque, *(menu.mosque for menu in w.arch_menus.values())):
            screen.sky.birds = []
            screen.sky.stars = []
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def landmarks(w):
        """Where the minaret tips and the top of the dome are on screen, in window pixels.

        The ink is whatever stands out from the page: dark lines on the white screen, bright
        ones on the black. This used to look for dark pixels only. On the night screen that is
        every pixel, so it found row 110 -- the first row it looked at -- and averaged 480
        pixels of empty sky. Both screens gave the same meaningless number and the test passed
        without ever having measured a minaret.

        The sun is skipped by colour: it is the one thing up there that is not a shade of grey.
        The birds and stars are cleared by the window above, because they move.
        """
        image = w.grab().toImage()
        wide, tall = image.width(), image.height()
        from salaah import theme
        night = theme.palette().dark
        ink = [[False] * wide for _ in range(tall)]
        for y in range(110, tall):              # below the banner, which is black all through
            row = ink[y]
            for x in range(wide):
                colour = QtGui.QColor(image.pixel(x, y))
                total = colour.red() + colour.green() + colour.blue()
                spread = (max(colour.red(), colour.green(), colour.blue())
                          - min(colour.red(), colour.green(), colour.blue()))
                row[x] = (total > 450 if night else total < 330) and spread < 40
        found = {}
        for name, low, high in (("left", 0, wide // 4), ("dome", wide // 4, 3 * wide // 4),
                                ("right", 3 * wide // 4, wide)):
            top = next((y for y in range(110, tall)
                        if any(ink[y][low:high])), None)
            if top is None:
                return None
            xs = [x for x in range(low, high) if ink[top][x]]
            found[name] = (sum(xs) // len(xs), top)
        return found

    def test_the_minarets_and_dome_land_in_the_same_place_on_both(self):
        w = self.window()
        # In to the mosque, not the screen the mat opens on. go_home lands on the new front
        # door now, which is a different drawing altogether -- no minarets on it to line up
        # against, and a dome in another place. This test is about the kalima building being
        # the five-arch mosque with six arches, and that is what it has always been about.
        #
        # Shown rather than walked into: leave_welcome plays a zoom over the top, and offscreen
        # that animation never finishes, so the grab catches a screen mid-walk. The first go
        # measured a dome 450px from where it is and a left minaret that moved every run.
        w.stack.setCurrentWidget(w.home)
        settle()
        mosque = self.landmarks(w)
        w.open_corner("kalima")
        settle()
        arches = self.landmarks(w)
        self.assertIsNotNone(mosque)
        self.assertIsNotNone(arches)
        for part in ("left", "right", "dome"):
            across = abs(arches[part][0] - mosque[part][0])
            down = abs(arches[part][1] - mosque[part][1])
            self.assertLess(across, 25, f"{part} is {across}px across from the mosque's")
            self.assertLess(down, 25, f"{part} is {down}px below the mosque's")

    def test_the_kalima_drawing_is_the_same_shape_as_the_front_door(self):
        """The artwork arrived at a different size and aspect, so it sat smaller and higher
        than the mosque it was meant to echo."""
        front = QtGui.QImage(str(ASSETS / "mosque" / "mosque.png"))
        arches = QtGui.QImage(str(ASSETS / "kalima" / "mosque.png"))
        self.assertEqual(front.size(), arches.size())

    def test_the_arch_menu_has_no_bar_of_its_own_stealing_height(self):
        """It used to carry a Main screen button in a row above the mosque, which pushed the
        drawing down and made it shorter than the front door's."""
        w = self.window()
        menu = w.arch_menus["kalima"]
        self.assertEqual(menu.mosque.height(), menu.height(),
                         "something above the mosque is taking height from it")


class SettingsScreenTest(unittest.TestCase):
    """The Settings screen after the tidy: the same strip over it as the rest of the mat, the
    wordy choices as pickers, the ring's circle, and the foot pushed apart."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, "place": "Bury",
                                   **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        w.open_settings()
        w.tick()                 # the clock is what writes the strip's words
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def banner(self, w):
        strips = [x for x in w.settings_screen.findChildren(QtWidgets.QWidget)
                  if x.objectName() == "banner"]
        self.assertEqual(1, len(strips), "one strip over Settings, no more and no fewer")
        return strips[0]

    def test_settings_wears_the_same_strip_as_the_rest_of_the_mat(self):
        """It was the one screen with a bare white top. It now says where you are, when the
        prayers are and how loud it is, exactly as the Knowledge Corner does."""
        w = self.window()
        strip = self.banner(w)
        self.assertEqual(0, strip.mapTo(w.settings_screen, QtCore.QPoint(0, 0)).y(),
                         "the strip is the top of the screen, not a row part way down")
        said = [x for x in strip.findChildren(QtWidgets.QLabel)
                if x.objectName() == "bannerText"]
        self.assertEqual(1, len(said))
        self.assertIn("Bury", said[0].text())
        for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
            self.assertIn(w.t(f"prayer.{prayer}"), said[0].text(), prayer)
        self.assertEqual(1, len(strip.findChildren(QtWidgets.QSlider)), "and how loud it is")

    def test_the_strip_carries_the_way_home_and_no_cog(self):
        """A cog on the Settings banner would be a button back to the screen you are on."""
        from salaah.mosque import GearButton
        w = self.window()
        strip = self.banner(w)
        self.assertEqual([], strip.findChildren(GearButton), "no cog on Settings' own strip")
        home = [b for b in strip.findChildren(QtWidgets.QPushButton)
                if b.objectName() == "mainScreen"]
        self.assertEqual(1, len(home), "the way home is on the strip now")
        home[0].click()
        settle()
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_it_is_painted_black_over_white_and_not_white_over_white(self):
        """Rendered rather than read off the layout: a strip that lays out correctly and paints
        the same colour as the page underneath it is not a strip."""
        w = self.window()
        strip = self.banner(w)
        where = strip.mapTo(w, QtCore.QPoint(0, 0))
        image = w.grab().toImage()
        dark = total = 0
        for y in range(where.y() + 2, where.y() + strip.height() - 2):
            for x in range(where.x() + 2, where.x() + strip.width() - 2):
                colour = QtGui.QColor(image.pixel(x, y))
                total += 1
                if colour.red() < 90 and colour.green() < 90 and colour.blue() < 90:
                    dark += 1
        self.assertGreater(dark / total, 0.7, f"only {dark}/{total} of the strip is dark")

    def test_the_lettering_is_a_picker_and_picking_changes_it(self):
        w = self.window()
        box = w.font_picker
        self.assertIsInstance(box, QtWidgets.QComboBox)
        faces = [box.itemData(i) for i in range(box.count())]
        self.assertGreater(len(faces), 1)
        other = next(f for f in faces if f != w.settings.arabic_font)
        box.setCurrentIndex(faces.index(other))
        box.activated.emit(faces.index(other))       # what a finger on the list does
        settle()
        self.assertEqual(other, w.settings.arabic_font, "picking a face did not change it")

    def test_the_edge_is_a_picker_and_picking_changes_it(self):
        w = self.window(inset=0)
        box = w.inset_picker
        self.assertIsInstance(box, QtWidgets.QComboBox)
        values = [box.itemData(i) for i in range(box.count())]
        self.assertEqual(["0", "20", "40", "60"], values)
        self.assertEqual("0", box.itemData(box.currentIndex()), "it starts on the setting")
        box.activated.emit(values.index("40"))
        settle()
        self.assertEqual(40, w.settings.inset, "picking an edge did not change it")

    def test_the_ring_has_a_filled_circle_that_follows_the_connection(self):
        from salaah.ui import BRICK, MINT
        w = self.window()
        heads = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                 if x.objectName() == "settingHead"]
        self.assertIn("MySalaah Ring", heads)
        self.assertNotIn("Bluetooth buttons", heads)

        self.assertEqual(BRICK, w.ring_dot.color.name().upper(), "red with nothing paired")
        w.on_devices(["MySalaah Ring"])
        settle()
        self.assertEqual(MINT, w.ring_dot.color.name().upper(), "green once it is connected")
        self.assertIn("MySalaah Ring", w.devices_label.text())
        w.on_devices([])
        settle()
        self.assertEqual(BRICK, w.ring_dot.color.name().upper(), "red again when it goes")

    def test_the_circle_is_beside_the_words_and_actually_filled_in(self):
        """Drawn, not just built: the circle is painted by hand rather than styled, so the test
        looks at the pixels in the middle of it."""
        from salaah.ui import MINT
        w = self.window()
        w.on_devices(["MySalaah Ring"])
        settle()
        dot, words = w.ring_dot, w.devices_label
        self.assertTrue(dot.isVisible() and words.isVisible())
        gap = words.mapTo(w, words.rect().center()).x() - dot.mapTo(w, dot.rect().center()).x()
        self.assertGreater(gap, 0, "the circle goes before the words")
        self.assertLess(gap, w.px(400), "and beside them, not across the page")
        middle = dot.grab().toImage().pixel(dot.width() // 2, dot.height() // 2)
        self.assertEqual(MINT, QtGui.QColor(middle).name().upper(),
                         "the circle is solid, not an outline")

    def test_the_update_button_sits_in_the_bottom_right_corner(self):
        w = self.window()
        button = w.update_button
        version = next(x for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                       if x.text().startswith("Version "))
        screen = w.settings_screen
        self.assertGreater(button.mapTo(screen, button.rect().center()).x(), screen.width() * 0.75,
                           "hard against the right-hand edge")
        self.assertLess(version.mapTo(screen, version.rect().center()).x(), screen.width() * 0.25,
                        "and the version left where it was")
        self.assertGreater(button.mapTo(screen, button.rect().center()).y(),
                           screen.height() * 0.85, "in the foot, not part way up")

    def test_the_version_no_longer_says_the_app_name_twice(self):
        from salaah import __version__
        w = self.window()
        said = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        self.assertIn(f"Version {__version__}", said)
        self.assertNotIn(f"Salaah version {__version__}", said)

    def test_the_screen_mode_setting_is_called_the_mode_not_the_colours(self):
        w = self.window()
        heads = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                 if x.objectName() == "settingHead"]
        self.assertIn("Screen mode", heads)
        self.assertNotIn("Screen colours", heads)

    def test_every_pack_renamed_the_same_three_things(self):
        """Six packs, one screen: if one of them still says the old words the screen changes
        meaning when the language does."""
        import json
        for lang in sorted(full_packs(available_packs(ASSETS))):
            ui = json.loads((ASSETS / "content" / "packs" / lang / "pack.json")
                            .read_text(encoding="utf-8"))["ui"]
            self.assertEqual("MySalaah Ring", ui["settings.buttons"], lang)
            self.assertNotIn("Bluetooth", ui["settings.buttons"], lang)
            self.assertIn("{number}", ui["settings.version"], lang)
            self.assertNotIn("Salaah", ui["settings.version"], lang)


class AzaanScreenTest(unittest.TestCase):
    """The call to prayer on the screen: the muezzin, the words, and the red following them."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "dark", "recitation": False, "place": "Bury",
                                   "azaan": True, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def box(self, w, prayer="fajr", recording="azaan-fajr.mp3"):
        from salaah.call import CallBox
        b = CallBox(w, prayer, recording, w.adhan)
        b.show()
        settle()
        self.addCleanup(lambda: (b.close(), b.deleteLater(), settle()))
        return b

    # The words

    def test_the_call_has_its_words_and_every_language_the_app_speaks(self):
        import json
        raw = json.loads((ASSETS / "content" / "azaan" / "adhan.json").read_text(encoding="utf-8"))
        # The six the mat is written in. Arabic only shows the call with nothing under it --
        # see AdhanScreen.meaning_language -- so there is no Arabic meaning to be missing.
        langs = set(full_packs(available_packs(ASSETS)))
        for line in raw["lines"]:
            self.assertTrue(line["arabic"].strip(), line["key"])
            missing = [lang for lang in langs if not line.get("text", {}).get(lang, "").strip()]
            self.assertEqual([], missing, f"{line['key']} has no meaning in {missing}")

    def test_the_call_covers_the_whole_screen(self):
        """It was 88% by 92% -- a box on top of the mat with prayer times showing round the
        edge. The call is not a message about something else happening; it is what the mat is
        doing, so it takes the screen."""
        w = self.window()
        b = self.box(w)
        self.assertEqual(w.size(), b.size(),
                         "the call is still a box in the middle of the screen")
        self.assertEqual(w.pos(), b.pos())

    def test_stop_is_a_big_square_in_the_top_corner(self):
        """Harry asked for it moved off the bottom. On a full screen the bottom edge is a long
        way from a thumb, and this is the one thing on the screen to press -- at the one moment
        somebody wants it, which is when the mat has started calling out in a quiet house."""
        w = self.window()
        b = self.box(w)
        stop = b.stop_button
        self.assertTrue(stop.isVisible())
        self.assertEqual(stop.width(), stop.height(), f"not square: {stop.size()}")
        self.assertGreaterEqual(stop.width(), 90, "too small to aim at in a hurry")
        # Top right of the box, not the bottom.
        middle = stop.mapTo(b, stop.rect().center())
        self.assertLess(middle.y(), b.height() * 0.25, "it is not at the top")
        self.assertGreater(middle.x(), b.width() * 0.75, "it is not on the right")

    def test_stop_is_square_in_every_language_it_is_labelled_in(self):
        """The word is Arrêter in French and رک جائیں in Urdu, so a size written into the
        stylesheet would clip the long ones. It is measured against the screen instead."""
        for lang in ("en", "fr", "ur", "zh"):
            with self.subTest(lang):
                w = self.window(lang=lang)
                stop = self.box(w).stop_button
                self.assertEqual(stop.width(), stop.height(), f"{lang}: {stop.size()}")
                self.assertGreaterEqual(stop.width(), stop.sizeHint().width() * 0.5,
                                        "the label will not fit in it")

    def test_fajr_carries_the_line_the_other_four_do_not(self):
        w = self.window()
        ordinary = w.adhan.shown("azaan.mp3")
        fajr = w.adhan.shown("azaan-fajr.mp3")
        self.assertNotIn("nawm", ordinary, "the dawn line must not be called at Dhuhr")
        self.assertIn("nawm", fajr, "the dawn line is what makes the Fajr call different")
        self.assertEqual([k for k in fajr if k != "nawm"], ordinary,
                         "the two calls are otherwise the same lines in the same order")

    def test_the_lines_shown_are_the_distinct_ones_not_the_repeats(self):
        """The call says most lines twice. Printing it twice would be a wall of the same words;
        the line is shown once and lights again when it is called again."""
        w = self.window()
        self.assertEqual(14, len(w.adhan.order("azaan-fajr.mp3")), "fourteen stretches are called")
        self.assertEqual(7, len(w.adhan.shown("azaan-fajr.mp3")), "seven distinct lines")

    # The timings, measured off the recording

    def test_the_fajr_timings_run_in_order_and_stay_inside_the_recording(self):
        import json
        raw = json.loads((ASSETS / "content" / "azaan" / "times.json").read_text(encoding="utf-8"))
        known = raw["azaan-fajr.mp3"]
        lines = known["lines"]
        self.assertEqual(14, len(lines))
        last = 0
        for row in lines:
            self.assertGreaterEqual(row["start"], last, f"{row['key']} starts before the one before")
            self.assertGreater(row["end"], row["start"], row["key"])
            last = row["end"]
        self.assertLess(lines[-1]["end"], 211_000, "past the end of a 210-second recording")

    def test_every_word_of_a_line_has_a_time_inside_that_line(self):
        w = self.window()
        import json
        known = json.loads((ASSETS / "content" / "azaan" / "times.json")
                           .read_text(encoding="utf-8"))["azaan-fajr.mp3"]
        for row in known["lines"]:
            words = w.adhan.line(row["key"])["arabic"].split()
            self.assertEqual(len(words), len(row["words"]),
                             f"{row['key']}: {len(row['words'])} times for {len(words)} words")
            for a, b in row["words"]:
                self.assertGreaterEqual(a, row["start"], row["key"])
                self.assertLessEqual(b, row["end"] + 1, row["key"])

    def test_the_word_being_called_is_found_from_the_clock(self):
        w = self.window()
        import json
        known = json.loads((ASSETS / "content" / "azaan" / "times.json")
                           .read_text(encoding="utf-8"))["azaan-fajr.mp3"]
        for row in known["lines"]:
            for i, (a, b) in enumerate(row["words"]):
                middle = (a + b) / 2000.0
                self.assertEqual((row["key"], i), w.adhan.at("azaan-fajr.mp3", middle),
                                 f"{row['key']} word {i} at {middle:.2f}s")

    def test_between_the_lines_nothing_is_lit(self):
        """The muezzin breathes. Lighting a word through the silence would be a lie about
        where he is."""
        w = self.window()
        import json
        lines = json.loads((ASSETS / "content" / "azaan" / "times.json")
                           .read_text(encoding="utf-8"))["azaan-fajr.mp3"]["lines"]
        for before, after in zip(lines, lines[1:]):
            middle = (before["end"] + after["start"]) / 2000.0
            self.assertIsNone(w.adhan.at("azaan-fajr.mp3", middle),
                              f"something is lit in the gap before {after['key']}")

    def test_both_recordings_are_measured_now(self):
        """The first ordinary recording would not come apart into its twelve lines and shipped
        without timings. The one that replaced it does, so the red follows the voice at all
        five prayers rather than only at Fajr."""
        w = self.window()
        for recording, lines in (("azaan.mp3", 12), ("azaan-fajr.mp3", 14)):
            self.assertTrue(w.adhan.measured(recording), recording)
            self.assertEqual(lines, len(w.adhan.times[recording]["lines"]), recording)

    def test_a_recording_with_no_measured_timings_lights_nothing(self):
        """Still the rule, and still worth holding: a recording nobody has measured shows its
        words with no red at all. Red in the wrong place is worse than none."""
        w = self.window()
        self.assertFalse(w.adhan.measured("somebody-elses-azaan.mp3"))
        for t in (0.0, 30.0, 90.0, 170.0):
            self.assertIsNone(w.adhan.at("somebody-elses-azaan.mp3", t))
        box = self.box(w, "dhuhr", "somebody-elses-azaan.mp3")
        self.assertFalse(box.follow.isActive(), "nothing to follow, so the clock stays off")
        self.assertTrue(box.boxes, "the words are still shown")

    # The box

    def test_the_box_shows_the_muezzin_the_words_and_the_meanings(self):
        w = self.window()
        box = self.box(w)
        self.assertTrue(box.drawing.there, "the drawing is missing")
        self.assertTrue(box.drawing.isVisible())
        self.assertEqual(7, len(box.boxes), "one for each distinct line of the Fajr call")
        said = [x.text() for x in box.findChildren(QtWidgets.QLabel)
                if x.objectName() == "callMeaning"]
        self.assertEqual(7, len(said), "a meaning under every line")
        self.assertIn("Come to prayer", said)
        self.assertIn("Prayer is better than sleep", said)

    def test_the_meaning_follows_the_language_setting(self):
        w = self.window(lang="ur")
        box = self.box(w)
        said = " ".join(x.text() for x in box.findChildren(QtWidgets.QLabel)
                        if x.objectName() == "callMeaning")
        self.assertIn("نماز", said, "the meanings should be in Urdu")
        self.assertNotIn("Come to prayer", said)

    def test_the_word_being_called_turns_red_and_only_that_one(self):
        w = self.window()
        box = self.box(w)
        box.boxes["salah"].set_highlight((0, 1))
        self.assertEqual((0, 1), box.boxes["salah"].highlight)
        box.clear()
        self.assertTrue(all(b.highlight is None for b in box.boxes.values()))

    def test_the_red_is_actually_painted_red(self):
        """Rendered, not read off the widget: the highlight is drawn by hand, and a box that
        holds the right number and paints the word white is no use to anybody."""
        w = self.window()
        box = self.box(w)
        # The driver is stopped first. It runs every 50ms and clears the red whenever nothing
        # is sounding, which in here is always -- so a highlight set by hand and then left to
        # settle is wiped before it can be looked at, and the test grades a blank line.
        box.follow.stop()
        line = box.boxes["shahada"]
        plain = line.grab().toImage()
        line.set_highlight((0, 2))
        settle()
        lit = line.grab().toImage()
        # Counted against the theme's own highlight colour rather than "looks reddish". White
        # letters on black carry orange fringes from the antialiasing -- (231, 158, 74) and the
        # like -- and a loose test counts those, so it reports red on a line with none.
        from salaah import theme
        want = QtGui.QColor(theme.palette().highlight)
        def lit_pixels(image):
            found = 0
            for y in range(image.height()):
                for x in range(image.width()):
                    c = QtGui.QColor(image.pixel(x, y))
                    if (abs(c.red() - want.red()) < 30 and abs(c.green() - want.green()) < 30
                            and abs(c.blue() - want.blue()) < 30):
                        found += 1
            return found
        self.assertEqual(0, lit_pixels(plain), "nothing is red before a word is lit")
        self.assertGreater(lit_pixels(lit), 20, "the lit word is not painted in the red")

    def test_the_drawing_is_painted_in_the_colour_it_is_given(self):
        """The picture is black lines on nothing, which is invisible on a black box. It is used
        as a stencil, so it has to come out whatever colour it is filled with."""
        from salaah.call import Drawing
        w = self.window()
        for colour, want in (("#FFFFFF", (255, 255, 255)), ("#A63D33", (166, 61, 51))):
            d = Drawing(w.adhan.picture(), colour)
            d.resize(300, 380)
            image = d.grab().toImage()
            hits = set()
            for y in range(0, image.height(), 3):
                for x in range(0, image.width(), 3):
                    c = QtGui.QColor(image.pixel(x, y))
                    if c.alpha() > 200:
                        hits.add((c.red(), c.green(), c.blue()))
            self.assertTrue(any(abs(r-want[0]) < 12 and abs(g-want[1]) < 12 and abs(b-want[2]) < 12
                                for r, g, b in hits),
                            f"nothing drawn in {colour}; got {sorted(hits)[:6]}")
            d.deleteLater()

    # How it is put up and taken down

    def test_the_call_puts_the_box_up_and_stopping_it_stops_the_sound(self):
        from salaah.call import CallBox
        w = self.window()
        w.call_to_prayer("fajr")
        settle()
        self.assertIsInstance(w.call_box, CallBox, "the plain notice should have been replaced")
        self.assertTrue(w.call_box.isVisible())
        w.call_box.accept()
        settle()
        self.assertIsNone(w.call_box, "the box should be let go of when it closes")
        self.assertFalse(w.call.playing)

    def test_it_has_no_border_or_rounded_corners_now_it_fills_the_screen(self):
        """This test used to say the opposite, and said it for a reason: the box was 88% of
        the screen, so the mosque showing round the edge was what made it read as a notice on
        top of the mat rather than a new screen.

        Harry has asked for the full screen, which settles it the other way -- and takes the
        border and the rounded corners with it. They were the edge of a box; on a screen that
        reaches the bezel there is no edge for them to sit on, and a white line down the side
        of a full screen is a white line.
        """
        w = self.window()
        box = self.box(w)
        style = box.styleSheet()
        self.assertNotIn("border-radius", style.split("QDialog#callBox QPushButton")[0],
                         "the box still has rounded corners")
        self.assertNotIn("solid #FFFFFF", style, "the box still has a white border round it")

    def test_the_words_are_marked_as_not_yet_read_over_by_a_reader_of_arabic(self):
        """Drafted, not checked. The flag is what says so; when Harry has read the lines on the
        mat he sets it true, and this test is what will notice if it was set without thought."""
        w = self.window()
        self.assertFalse(w.adhan.reviewed,
                         "if the words have now been checked, say so here as well")

    def test_the_red_goes_out_when_the_call_is_not_sounding(self):
        """Found by accident while writing the test above: the driver clears the red whenever
        the player has no position. That is right and worth holding onto -- when the call is
        stopped part way, the last word must not be left lit."""
        w = self.window()
        box = self.box(w)
        box.follow.stop()
        box.boxes["falah"].set_highlight((0, 1))
        self.assertIsNotNone(box.boxes["falah"].highlight)
        self.assertIsNone(w.call.position(), "nothing is playing in the test")
        box.tick()
        self.assertTrue(all(b.highlight is None for b in box.boxes.values()),
                        "the red stayed on after the voice stopped")


class SurahNumberTest(unittest.TestCase):
    """The number beside each surah: white in a thick white square, every one the same."""

    def window(self, theme="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=theme, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.open_corner_list()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def badges(self, w):
        return [x for x in w.surah_list.findChildren(QtWidgets.QLabel)
                if x.objectName() == "surahNumber"]

    def test_every_one_of_the_114_is_the_same_square(self):
        """It used to be a fixed width and whatever height the row came out at, so 1 and 114
        sat in boxes of different shapes."""
        w = self.window()
        sizes = {(x.width(), x.height()) for x in self.badges(w)}
        self.assertEqual(114, len(self.badges(w)))
        self.assertEqual(1, len(sizes), f"the squares come in {len(sizes)} sizes: {sizes}")
        wide, tall = sizes.pop()
        self.assertEqual(wide, tall, "a square, not a rectangle")

    def test_the_number_and_its_outline_are_drawn_in_the_ink_colour(self):
        """Rendered: white on the dark screen, which is what was asked for, and black on the
        light one, where white would be invisible. Read off the pixels, not off the stylesheet."""
        for mode, want in (("dark", 255), ("light", 0)):
            w = self.window(mode)
            badge = self.badges(w)[0]
            image = badge.grab().toImage()
            edge = [QtGui.QColor(image.pixel(x, 1)).red() for x in range(4, badge.width() - 4)]
            self.assertTrue(edge, mode)
            near = sum(1 for v in edge if abs(v - want) < 60)
            self.assertGreater(near / len(edge), 0.9,
                               f"{mode}: the top of the outline is not the ink colour")

    def test_the_outline_is_thick_enough_to_read_across_a_room(self):
        from salaah.reading import NUMBER_LINE
        self.assertGreaterEqual(NUMBER_LINE, 3, "a hairline box is not what was asked for")
        w = self.window()
        badge = self.badges(w)[0]
        image = badge.grab().toImage()
        middle = badge.width() // 2
        run = 0
        for y in range(badge.height() // 2):
            if QtGui.QColor(image.pixel(middle, y)).red() > 195:
                run += 1
            elif run:
                break
        self.assertGreaterEqual(run, 3, f"the drawn outline is only {run}px thick")

    def test_the_numbers_are_no_longer_blue(self):
        from salaah.ui import LAPIS
        w = self.window("light")
        badge = self.badges(w)[0]
        image = badge.grab().toImage()
        blue = QtGui.QColor(LAPIS)
        for y in range(image.height()):
            for x in range(image.width()):
                c = QtGui.QColor(image.pixel(x, y))
                self.assertFalse(abs(c.red() - blue.red()) < 20 and abs(c.green() - blue.green()) < 20
                                 and abs(c.blue() - blue.blue()) < 20,
                                 f"still painting in the old blue at {x},{y}")


class SoundSettingsTogetherTest(unittest.TestCase):
    """The two settings that decide whether the mat makes a sound, in one column."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=True, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.open_settings()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def head(self, w, key):
        wanted = w.t(key)
        found = [x for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                 if x.objectName() == "settingHead" and x.text() == wanted]
        self.assertEqual(1, len(found), f"{key} is not on the screen once")
        return found[0]

    def test_the_call_to_prayer_moved_to_the_right_hand_column(self):
        w = self.window()
        screen = w.settings_screen
        middle = screen.width() / 2
        call = self.head(w, "settings.azaan")
        self.assertGreater(call.mapTo(screen, call.rect().center()).x(), middle,
                           "the call to prayer is still on the left")

    def test_it_sits_directly_below_the_recitation(self):
        w = self.window()
        screen = w.settings_screen
        call = self.head(w, "settings.azaan")
        recitation = self.head(w, "settings.recitation")
        self.assertGreater(call.mapTo(screen, call.rect().topLeft()).y(),
                           recitation.mapTo(screen, recitation.rect().topLeft()).y(),
                           "the call should come after the recitation, not before it")
        # Only the right-hand column: the left one runs down the page alongside, and its
        # headings sit between these two in height without being between them on the screen.
        middle = screen.width() / 2
        between = [x for x in w.settings_screen.findChildren(QtWidgets.QLabel)
                   if x.objectName() == "settingHead"
                   and x.mapTo(screen, x.rect().center()).x() > middle
                   and recitation.mapTo(screen, recitation.rect().center()).y()
                   < x.mapTo(screen, x.rect().center()).y()
                   < call.mapTo(screen, call.rect().center()).y()]
        self.assertEqual([], [x.text() for x in between],
                         "something got in between the two sound settings")

    def test_the_switch_still_works_where_it_now_lives(self):
        w = self.window()
        knob = next(b for b in w.settings_screen.findChildren(QtWidgets.QAbstractButton)
                    if b.objectName() == "azaanSwitch")
        was = w.settings.azaan
        knob.click()
        settle()
        self.assertNotEqual(was, w.settings.azaan, "moving it broke it")


class TouchableSliderTest(unittest.TestCase):
    """The slider down the side of the lists is slid with a finger, not pointed at with a mouse."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def surahs(self, w):
        w.open_corner_list()
        settle()
        return w.surah_list

    def duas(self, w):
        w.open_section("duas")
        settle()
        return w.section_lists["duas"]

    def test_the_list_slider_is_far_wider_than_the_one_in_settings(self):
        """Settings is read sitting still and its slider is the ordinary 14px. The lists are
        scrolled through with a thumb while standing over the mat.

        Measured against LIST_BAR rather than a multiple written in here. It was exactly three
        times the settings one until Harry used it and asked for more, at which point a test
        saying "three times" failed on a change that was the point of the exercise.
        """
        from salaah.reading import LIST_BAR
        w = self.window()
        w.open_settings()
        settle()
        thin = w.settings_scroll.verticalScrollBar().width()
        self.assertEqual(14, thin, "the settings slider was the one measured against")
        for name, listing in (("surahs", self.surahs(w)), ("du'as", self.duas(w))):
            wide = listing.scroll.verticalScrollBar().width()
            self.assertEqual(w.px(LIST_BAR), wide, f"the {name} slider is {wide}px")
            self.assertGreaterEqual(wide, thin * 3, "no wider than a mouse's slider")

    def test_settings_keeps_its_thin_one(self):
        """Only the lists changed. Widening every slider in the app would have eaten the
        settings columns for a screen nobody scrolls with a finger."""
        w = self.window()
        w.open_settings()
        settle()
        self.assertEqual(14, w.settings_scroll.verticalScrollBar().width())

    def test_the_rows_gave_up_the_width_and_kept_their_height(self):
        """What was asked for: narrower rectangles, same height. The lists resize to whatever
        the slider leaves, so this is what should have happened by itself."""
        w = self.window()
        for listing in (self.surahs(w), self.duas(w)):
            rows = [b for b in listing.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "surahRow"]
            self.assertTrue(rows)
            self.assertEqual({w.px(96)}, {b.height() for b in rows}, "the height should not move")
            edge = max(b.mapTo(listing, b.rect().topRight()).x() for b in rows)
            bar = listing.scroll.verticalScrollBar()
            self.assertLessEqual(edge, bar.mapTo(listing, bar.rect().topLeft()).x(),
                                 "a row runs under the slider instead of stopping short of it")

    def test_the_handle_is_a_finger_sized_target_and_is_actually_drawn(self):
        """Rendered: a slider styled to a width it then paints nothing into is not a target.
        The surah list is 114 rows, so its handle is as small as the handle ever gets."""
        w = self.window()
        listing = self.surahs(w)
        bar = listing.scroll.verticalScrollBar()
        self.assertTrue(bar.isVisible(), "114 surahs should need scrolling")
        self.assertGreaterEqual(bar.height(), w.px(300))
        image = bar.grab().toImage()
        rows_painted = 0
        for y in range(image.height()):
            across = sum(1 for x in range(image.width())
                         if QtGui.QColor(image.pixel(x, y)).lightness() > 90)
            if across > image.width() * 0.6:
                rows_painted += 1
        self.assertGreaterEqual(rows_painted, w.px(100),
                                f"only {rows_painted}px of handle is painted; it is a groove, "
                                f"not a handle")

    def test_the_slider_actually_scrolls_the_list(self):
        w = self.window()
        listing = self.surahs(w)
        bar = listing.scroll.verticalScrollBar()
        self.assertEqual(0, bar.value())
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        settle()
        self.assertEqual(bar.maximum(), bar.value(), "the slider did not take")

    def test_the_kalima_list_behind_the_arches_got_it_too(self):
        """The kalima are chosen off the mosque, but the list is still there when the drawing
        is missing, and it is the same widget -- so it should not be the one left behind."""
        w = self.window()
        # Shown directly: open_section puts the arches up instead, so going that way leaves the
        # list never laid out and its slider at an unrealised default width.
        listing = w.section_lists["kalima"]
        w.stack.setCurrentWidget(w.corner_page)
        w.corner_screen.setCurrentWidget(listing)
        settle()
        self.assertTrue(listing.isVisible(), "the list was never actually shown")
        self.assertEqual("listScroll", listing.scroll.objectName(), "the rule would not reach it")
        # Six kalima fit without scrolling, so the slider is hidden and its width means nothing
        # until it is asked for. Turned on, it should be the same wide one as the others.
        listing.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        settle()
        from salaah.reading import LIST_BAR
        bar = listing.scroll.verticalScrollBar()
        self.assertTrue(bar.isVisible())
        self.assertEqual(w.px(LIST_BAR), bar.width())


class MuezzinPictureTest(unittest.TestCase):
    """The drawing is used as a stencil, so what matters is its shape and that it can be
    filled. A picture saved the ordinary way -- black lines on white -- would be a black
    rectangle on a black box, which the eye would notice and no other test would."""

    def test_the_picture_is_a_stencil_and_not_a_flat_drawing(self):
        picture = ASSETS / "azaan" / "muezzin.png"
        self.assertTrue(picture.is_file())
        image = QtGui.QImage(str(picture))
        self.assertFalse(image.isNull())
        self.assertTrue(image.hasAlphaChannel(), "no alpha: there is no shape to fill")
        clear = ink = 0
        colours = set()
        for y in range(0, image.height(), 5):
            for x in range(0, image.width(), 5):
                c = QtGui.QColor(image.pixelColor(x, y))
                if c.alpha() < 20:
                    clear += 1
                elif c.alpha() > 230:
                    ink += 1
                    colours.add((c.red(), c.green(), c.blue()))
        self.assertGreater(clear, ink, "most of the picture should be see-through")
        self.assertGreater(ink, 0, "nothing is drawn")
        self.assertEqual({(255, 255, 255)}, colours,
                         "the ink must be white so the screen can tint it to any colour")

    def test_it_is_the_tall_shape_the_box_gives_it(self):
        """Tall, and big enough for the largest the box ever draws it -- which is about four
        hundred pixels across on a 1920 monitor, so this has headroom. It used to ask for eight
        hundred pixels of height, back when the drawing shipped at whatever size it arrived in;
        the one it wants now is cut down on purpose, because seven megabytes of muezzin is a
        download every mat pays for and nobody can see."""
        image = QtGui.QImage(str(ASSETS / "azaan" / "muezzin.png"))
        self.assertGreater(image.height(), image.width(), "an upright arch, not a wide one")
        self.assertGreaterEqual(image.width(), 430, "too small to draw at the size of the box")


class DrawnForTheDarkTest(unittest.TestCase):
    """The artwork says which screen it was drawn for, and the screen does the rest.

    The first mosque was dark ink on a light ground and is turned inside out after dark. The
    ones drawn since are white lines on black. Without the drawing saying so, the night screen
    turned the new artwork inside out and showed the negative of what was drawn."""

    def window(self, mode="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_both_drawings_say_they_were_made_for_the_dark_screen(self):
        import json
        for folder in ("mosque", "kalima"):
            described = json.loads((ASSETS / folder / "mosque.json").read_text(encoding="utf-8"))
            self.assertEqual("dark", described.get("drawn"), folder)

    def test_it_is_shown_as_drawn_after_dark_and_turned_over_by_day(self):
        self.assertFalse(self.window("dark").mosque.flipped, "the night screen is the one it suits")
        self.assertTrue(self.window("light").mosque.flipped, "and the white one is not")

    def test_the_dome_stays_dark_after_dark_so_the_clock_reads_white_on_it(self):
        """The clock used to be painted black whenever the screen was dark, because the old
        artwork came out light when it was turned over. This one is not turned over, so its
        dome is still dark and black numerals would vanish into it."""
        w = self.window("dark")
        m = w.mosque
        m.sky.birds = []
        m.sky.stars = []
        scaled, origin, scale = m.placement()
        box = m.clock_box
        m.set_time("")
        settle()
        bare = w.grab().toImage()
        middle = QtGui.QColor(bare.pixel(origin.x() + int((box.x() + box.width() * 0.05) * scale),
                                         origin.y() + int((box.y() + box.height() * 0.5) * scale)))
        self.assertLess(middle.lightness(), 110, "the dome is not dark; the clock will not read")

        # The numerals are found by turning them on and off, not by counting bright pixels in
        # the box: the dome's own outline runs through that box, so counting alone reported
        # plenty of light even with the time painted black and invisible.
        m.set_time("14:28")
        settle()
        shown = w.grab().toImage()
        lighter = darker = 0
        for y in range(origin.y() + int(box.y() * scale),
                       origin.y() + int((box.y() + box.height()) * scale), 2):
            for x in range(origin.x() + int(box.x() * scale),
                           origin.x() + int((box.x() + box.width()) * scale), 2):
                was = QtGui.QColor(bare.pixel(x, y)).lightness()
                now = QtGui.QColor(shown.pixel(x, y)).lightness()
                if now - was > 60:
                    lighter += 1
                elif was - now > 60:
                    darker += 1
        self.assertGreater(lighter, 200, "the time is not painted in light ink on the dark dome")
        self.assertGreater(lighter, darker * 4, "the time is being painted dark on a dark dome")

    def test_an_old_style_drawing_would_still_be_turned_over_after_dark(self):
        """The flag defaults to the way the first mosque was made, so artwork without it keeps
        the behaviour it has always had."""
        from salaah.mosque import MosqueScreen
        screen = MosqueScreen(ASSETS)
        self.assertTrue(screen.drawn_dark, "this one is dark-drawn")
        screen.drawn_dark = False                     # as an old drawing would load
        from salaah import theme
        self.assertEqual(theme.palette().dark, screen.flipped,
                         "without the flag, dark mode is what turns it over")
        screen.deleteLater()


class NewMosqueArtTest(unittest.TestCase):
    """The two new drawings: five named arches and six numbered ones, with the sky knocked out."""

    def window(self, mode="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.leave_welcome()      # past the front door: these look at the mosque behind it
        w.veil.stop()          # and at the screen, not at the walk laid over it
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_front_door_still_has_its_five_prayers_in_order(self):
        w = self.window()
        self.assertEqual(["fajr", "dhuhr", "asr", "maghrib", "isha"],
                         [a.prayer for a in w.mosque.arches])
        lefts = [a.box.x() for a in w.mosque.arches]
        self.assertEqual(lefts, sorted(lefts), "the arches are not left to right")

    def test_the_kalima_menu_has_its_six(self):
        w = self.window()
        w.open_section("kalima")
        settle()
        self.assertEqual(["1", "2", "3", "4", "5", "6"],
                         [a.prayer for a in w.arch_menus["kalima"].mosque.arches])

    def test_the_sky_is_see_through_so_what_is_behind_it_shows(self):
        """What Harry asked about: the sun, moon, stars and birds are drawn behind the mosque,
        so an opaque drawing hides them. Checked by painting the sky full of stars and counting
        how many survive."""
        w = self.window()
        m = w.mosque
        m.sky.birds = []
        m.set_sky(False, 0.5)
        self.assertGreater(len(m.sky.stars), 20, "there should be stars to see")

        # Counted by taking the stars away, not by counting bright pixels: the building's own
        # white outlines run through the same rows, and with the sky painted solid they alone
        # were enough to pass. What matters is whether anything BEHIND the drawing gets through.
        stars = list(m.sky.stars)
        m.sky.stars = []
        m.update()
        settle()
        bare = w.grab().toImage()
        m.sky.stars = stars
        m.update()
        settle()
        starry = w.grab().toImage()
        showing = 0
        for y in range(120, m.height()):
            for x in range(0, w.width()):
                if (QtGui.QColor(starry.pixel(x, y)).lightness()
                        - QtGui.QColor(bare.pixel(x, y)).lightness()) > 30:
                    showing += 1
        self.assertGreater(showing, 150,
                           f"only {showing} pixels of sky get through; the drawing covers it")

    def test_the_minaret_boxes_were_written_and_land_on_the_minarets(self):
        """They used to be left empty by the builder, which is not an error anywhere -- the
        glow would simply never appear and nothing would say why."""
        w = self.window()
        m = w.mosque
        self.assertEqual({"left", "right"}, set(m.minarets))
        for side, box in m.minarets.items():
            self.assertGreater(box.width(), 0, side)
            self.assertGreater(box.height(), 0, side)
            self.assertLess(box.y(), m.picture.height() * 0.45, f"{side} is not near the top")
        left, right = m.minarets["left"], m.minarets["right"]
        self.assertLess(left.center().x(), m.picture.width() * 0.3)
        self.assertGreater(right.center().x(), m.picture.width() * 0.7)

    def test_the_prayer_whose_time_it_is_is_picked_out_in_green(self):
        """The names are part of the drawing, so they are lifted off it with the arch's mask.
        New artwork, same trick -- and if the mask and the drawing disagree, nothing is lit."""
        w = self.window()
        m = w.mosque
        m.set_lit("dhuhr")
        settle()
        from salaah.mosque import GREEN, GREEN_DARK
        arch = next(a for a in m.arches if a.prayer == "dhuhr")
        stencil = m.name_in_green(arch, 1.0).toImage()
        painted, shades = 0, set()
        for y in range(0, stencil.height(), 2):
            for x in range(0, stencil.width(), 2):
                c = QtGui.QColor(stencil.pixelColor(x, y))
                if c.alpha() > 40:
                    painted += 1
                    shades.add((c.red(), c.green(), c.blue()))
        self.assertGreater(painted, 200, "the name did not come off the drawing")
        # Which green matters, not just that something was painted. The panel under it is
        # white on this artwork whatever the screen is, so it wants the darker green; the
        # lighter one is for a name sitting on a dark panel and is washed out on a white one.
        want = GREEN_DARK if m.flipped else GREEN
        # A few shades wide: the stencil is scaled smoothly, so the edges of the letters blend
        # a point or two either side of the colour they were filled with.
        off = [c for c in shades if max(abs(c[0] - want.red()), abs(c[1] - want.green()),
                                        abs(c[2] - want.blue())) > 6]
        self.assertEqual([], off,
                         f"the name is not painted in {want.name()}; found {sorted(shades)[:4]}")
        panel = QtGui.QColor("white") if not m.flipped else QtGui.QColor("black")
        gap = abs(want.lightness() - panel.lightness())
        self.assertGreater(gap, 60, "the green does not stand out from the panel it sits on")


class MovingMuezzinTest(unittest.TestCase):
    """The call screen plays a little film of the muezzin instead of a still."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury", azaan=True),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def box(self, w):
        from salaah.call import CallBox
        b = CallBox(w, "fajr", "azaan-fajr.mp3", w.adhan)
        b.show()
        settle()
        self.addCleanup(lambda: (b.close(), b.deleteLater(), settle()))
        return b

    def test_there_is_a_film_and_it_is_running_while_the_call_is_up(self):
        w = self.window()
        self.assertTrue(w.adhan.film().is_file())
        box = self.box(w)
        self.assertIsNotNone(box.drawing.film, "the still is being shown instead of the film")
        self.assertGreater(box.drawing.film.frameCount(), 1)
        self.assertTrue(box.drawing.moving, "the film is loaded but not playing")

    def test_the_frames_are_different_pictures_and_each_one_gets_painted(self):
        """A film that loads, reports six frames and paints the same one six times is a still
        with extra steps. Compared over the whole widget: the frames sit in the middle of a
        tall box, so the first few thousand bytes are the black margin above them and match
        whatever is playing."""
        w = self.window()
        box = self.box(w)
        drawn = []
        for i in range(box.drawing.film.frameCount()):
            box.drawing.film.jumpToFrame(i)
            settle()
            image = box.drawing.grab().toImage()
            # Sampled pixel by pixel rather than hashing the raw buffer: the two Qt kits hand
            # back different things from bits(), and PyQt6's has no tobytes().
            drawn.append(tuple(image.pixel(x, y)
                               for y in range(0, image.height(), 7)
                               for x in range(0, image.width(), 7)))
        self.assertEqual(len(drawn), len(set(drawn)),
                         f"only {len(set(drawn))} of {len(drawn)} frames are different pictures")

    def test_it_stops_when_the_call_is_over(self):
        """Nothing is on screen to repaint, and a film left running on a Pi is a timer waking
        the processor five times a second for nobody."""
        w = self.window()
        box = self.box(w)
        self.assertTrue(box.drawing.moving)
        box.accept()
        settle()
        self.assertFalse(box.drawing.moving, "the film is still running with the box closed")

    def test_with_no_film_it_falls_back_to_the_still_and_tints_it(self):
        from salaah.call import Drawing
        w = self.window()
        plain = Drawing(w.adhan.picture(), "#FFFFFF", film=ASSETS / "azaan" / "no-such-film.gif")
        self.assertIsNone(plain.film)
        self.assertTrue(plain.there, "with no film it should still show the still")
        plain.resize(300, 380)
        image = plain.grab().toImage()
        white = sum(1 for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
                    if QtGui.QColor(image.pixel(x, y)).lightness() > 230)
        self.assertGreater(white, 50, "the still was not drawn")
        plain.deleteLater()

    def test_the_film_is_not_flattened_by_the_tinting_the_still_needs(self):
        """The still is a stencil filled with one colour. Doing that to a film would make every
        frame the same silhouette, which is the opposite of the point."""
        w = self.window()
        box = self.box(w)
        image = box.drawing.grab().toImage()
        shades = set()
        for y in range(0, image.height(), 4):
            for x in range(0, image.width(), 4):
                c = QtGui.QColor(image.pixel(x, y))
                if c.lightness() > 40:
                    shades.add(c.lightness() // 32)
        self.assertGreater(len(shades), 2,
                           "the film came out in one flat shade; it is being used as a stencil")

    def test_hiding_it_any_other_way_also_stops_the_film(self):
        """Pressing Stop is not the only way the box leaves the screen -- the window can go, or
        another screen can come up over it. The film has to notice all of them, which is why it
        stops on being hidden rather than only on the box being dismissed."""
        w = self.window()
        box = self.box(w)
        self.assertTrue(box.drawing.moving)
        box.hide()                       # not accept(): no dismissing, just off the screen
        settle()
        self.assertFalse(box.drawing.moving, "the film ran on with nothing to paint on")

    def test_a_second_call_lets_go_of_the_first_box(self):
        """Five calls a day for months. The boxes used to be forgotten rather than dropped,
        which was harmless when a box was a few labels and is not now one carries a film."""
        from salaah.call import CallBox
        w = self.window()
        for prayer in ("dhuhr", "asr", "maghrib"):
            w.call_to_prayer(prayer)
            settle()
            w.end_the_call()
            settle()
        alive = [b for b in w.findChildren(CallBox)]
        self.assertEqual([], alive, f"{len(alive)} call boxes are still about")
        self.assertIsNone(w.call_box)

    def test_the_box_up_now_is_the_only_one(self):
        from salaah.call import CallBox
        w = self.window()
        w.call_to_prayer("dhuhr")
        settle()
        w.call_to_prayer("asr")          # a second call while the first box is still up
        settle()
        self.assertEqual(1, len(w.findChildren(CallBox)), "the first box was left behind")


class WelcomeScreenTest(unittest.TestCase):
    """The front door: the mosque with MySalaah across it, which the mat opens on."""

    def window(self, mode="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_mat_opens_on_it(self):
        w = self.window()
        self.assertIsNotNone(w.welcome, "the welcome drawing was not found")
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_it_has_one_opening_with_the_name_across_it(self):
        w = self.window()
        self.assertEqual(["enter"], [a.prayer for a in w.welcome_mosque.arches])
        box = w.welcome_mosque.arches[0].box
        self.assertGreater(box.width(), box.height() * 2,
                           "the opening is a wide panel, not one of the upright arches")
        # Against the building rather than the canvas. The drawing is widened to the screen's
        # shape with bars of its own sky either side, and those are not part of the front.
        self.assertGreater(box.width(), w.welcome_mosque.picture.width() * 0.4,
                           "and it spans most of the front")

    def test_touching_it_goes_through_to_the_mosque(self):
        w = self.window()
        middle = w.welcome_mosque.arch_centre("enter")
        self.assertIsNotNone(middle)
        self.assertEqual("enter", w.welcome_mosque.arch_at(middle), "the middle is not the panel")
        w.welcome_mosque.chosen.emit("enter")
        settle()
        self.assertIs(w.home, w.stack.currentWidget(), "it did not go in")

    def test_the_rest_of_the_mat_still_comes_back_to_the_mosque(self):
        """Main screen means the five arches, not back out to the front door: that is the
        screen the mat is for, and a call to prayer lands there too."""
        w = self.window()
        w.welcome_mosque.chosen.emit("enter")
        settle()
        w.open_settings()
        settle()
        w.go_home()
        settle()
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_it_keeps_the_clock_but_lights_no_prayer(self):
        w = self.window()
        front = w.welcome_mosque
        self.assertTrue(front.time_text, "no time on the dome")
        self.assertEqual(w.mosque.time_text, front.time_text, "the two clocks disagree")
        self.assertIsNone(front.lit, "the front door should not be picking a prayer")
        self.assertFalse(front.idle_glow, "and should not be glowing its minarets either")

    def test_with_no_welcome_drawing_the_mat_opens_on_the_mosque_as_it_did(self):
        """The screen is an extra, not a thing the mat depends on."""
        import shutil, tempfile
        spare = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(spare, ignore_errors=True))
        shutil.copytree(ASSETS, spare / "assets", symlinks=True)
        shutil.rmtree(spare / "assets" / "welcome")
        w = MainWindow(load(spare / "assets"), available_packs(spare / "assets"),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        self.assertIsNone(w.welcome)
        self.assertIs(w.home, w.stack.currentWidget())


class CleanArtworkTest(unittest.TestCase):
    """The drawings are two-tone. The first pair had a glow painted round every line, and where
    the sky was knocked out from under it a grey fringe was left standing on the black."""

    def solid_shades(self, folder):
        image = QtGui.QImage(str(ASSETS / folder / "mosque.png"))
        self.assertFalse(image.isNull(), folder)
        mid = solid = 0
        for y in range(0, image.height(), 3):
            for x in range(0, image.width(), 3):
                c = QtGui.QColor(image.pixelColor(x, y))
                if c.alpha() < 200:
                    continue
                solid += 1
                if 40 < c.lightness() < 215:
                    mid += 1
        return mid, solid

    def test_the_drawings_are_black_and_white_and_not_much_in_between(self):
        for folder in ("mosque", "kalima", "welcome"):
            mid, solid = self.solid_shades(folder)
            self.assertGreater(solid, 1000, folder)
            share = mid / solid
            self.assertLess(share, 0.12,
                            f"{folder}: {share*100:.1f}% of what is drawn is a half shade -- "
                            f"that is the glow that made the first pair look muddy")

    def test_the_two_that_are_compared_share_a_canvas(self):
        """The mosque and the kalima menu are meant to read as the same building seen twice, so
        they are lined up against each other and must be the same size. The front door is not
        compared with either -- it was cropped to fill the screen, which is a different shape."""
        sizes = {QtGui.QImage(str(ASSETS / f / "mosque.png")).size() for f in ("mosque", "kalima")}
        self.assertEqual(1, len(sizes), "the two mosques are drawn at different sizes")
        front = QtGui.QImage(str(ASSETS / "welcome" / "mosque.png")).size()
        self.assertGreater(front.width() / front.height(), 1.85,
                           "the front door should be cut to the shape of the screen")


class ArchFinderTest(unittest.TestCase):
    """Two rules the builder needed for the new drawings, tested on shapes made here rather
    than on the artwork, so what is being checked is the rule and not one picture."""

    @staticmethod
    def grey(shapes, size=(400, 300)):
        """A black field with white rectangles punched in it, as an image the finder can read.

        A shape given as (x0, y0, x1, y1, "ring") is drawn as an outline with a gap inside it,
        which is how a double-outlined panel actually looks. Filling one rectangle inside
        another just makes one bigger white blob -- which is what the first version of this
        did, so the nesting rule it was meant to test was never exercised.
        """
        from PIL import Image, ImageDraw
        image = Image.new("L", size, 0)
        draw = ImageDraw.Draw(image)
        for shape in shapes:
            x0, y0, x1, y1 = shape[:4]
            if len(shape) > 4 and shape[4] == "ring":
                draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=255, width=6)
            else:
                draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
        return image

    def finder(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "arch_menu", Path(__file__).resolve().parent.parent / "tools" / "build_arch_menu.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_a_wide_panel_is_found_only_when_the_rule_is_relaxed(self):
        """The default throws away anything wider than it is tall -- the slots in a minaret,
        the line under the plinth. The welcome screen's opening is exactly that shape."""
        tools = self.finder()
        panel = self.grey([(40, 180, 360, 260)])         # 320 wide, 80 tall
        self.assertEqual([], tools.arches_in(panel, tools.SMALLEST),
                         "a flat panel should not pass for an arch by default")
        self.assertEqual(1, len(tools.arches_in(panel, tools.SMALLEST, 0.2)),
                         "and should be found once the rule is relaxed")

    def test_a_shape_inside_another_is_one_opening_not_two(self):
        """A panel drawn with a double outline appears twice: the border and the fill within
        it. The welcome drawing has one, and the builder refused it as two openings."""
        tools = self.finder()
        # An outline with a filled panel inside it and a black gap between: two separate white
        # shapes, one wholly within the other.
        nested = self.grey([(40, 100, 360, 260, "ring"), (60, 120, 340, 240)])
        found = tools.arches_in(nested, tools.SMALLEST, 0.2)
        self.assertEqual(1, len(found), f"got {found}")
        self.assertEqual((40, 100, 360, 260), found[0], "the outer shape is the opening")

    def test_arches_standing_side_by_side_are_left_alone(self):
        """The rule above must not swallow a row of arches, which is what the other two
        drawings are."""
        tools = self.finder()
        row = self.grey([(30 + i * 90, 80, 100 + i * 90, 260) for i in range(4)])
        found = tools.arches_in(row, tools.SMALLEST)
        self.assertEqual(4, len(found), f"got {found}")
        self.assertEqual([b[0] for b in found], sorted(b[0] for b in found), "left to right")



class ArtworkCacheTest(unittest.TestCase):
    """The drawings are read once and shared. Three mosques, rebuilt on every settings change,
    were re-reading about twenty megabytes of picture each time."""

    def test_the_same_drawing_is_not_read_twice(self):
        """The two screens should be handed the very same object. Comparing the pictures'
        contents, or their cacheKey, proves nothing: Qt keeps a cache of its own for images
        read from a file, so two pixmaps loaded separately can come back identical anyway.
        Identity is the thing that can only be true if this cache handed out what it had."""
        from salaah import mosque
        a = mosque.MosqueScreen(ASSETS)
        b = mosque.MosqueScreen(ASSETS)
        self.addCleanup(lambda: (a.deleteLater(), b.deleteLater(), APP.processEvents()))
        self.assertTrue(a.ready and b.ready)
        self.assertIs(a.picture, b.picture, "the drawing was read again for the second screen")
        for one, two in zip(a.arches, b.arches):
            self.assertIs(one.mask, two.mask, f"the {one.prayer} mask was read again")

    def test_rebuilding_the_artwork_is_picked_up_and_not_served_stale(self):
        """Harry rebuilds these drawings often. A cache keyed on the file name alone would go
        on handing out the old picture until the app was restarted."""
        import shutil, tempfile
        from salaah import mosque
        spare = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(spare, ignore_errors=True))
        shutil.copytree(ASSETS / "mosque", spare / "mosque")
        first = mosque.MosqueScreen(spare)
        self.addCleanup(lambda: (first.deleteLater(), APP.processEvents()))
        self.assertTrue(first.ready)
        was = first.picture.size()

        shutil.copy(ASSETS / "kalima" / "mosque.png", spare / "mosque" / "mosque.png")
        import os, time
        later = time.time() + 5
        os.utime(spare / "mosque" / "mosque.png", (later, later))
        again = mosque.MosqueScreen(spare)
        self.addCleanup(lambda: (again.deleteLater(), APP.processEvents()))
        self.assertNotEqual(first.picture.cacheKey(), again.picture.cacheKey(),
                            "the old picture was handed out again after the file changed")
        self.assertEqual(was, again.picture.size(), "same canvas, different drawing")


class MovingFrontDoorTest(unittest.TestCase):
    """The front door is a little film, not a still. Everything measured on this screen -- the
    panel you touch, the box the clock sits in -- came off the still, so the two have to stay
    the same canvas and the film has to sit exactly on top of it."""

    def window(self, mode="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_front_door_has_a_film_and_the_other_two_mosques_do_not(self):
        w = self.window()
        self.assertTrue((ASSETS / "welcome" / "mosque.gif").is_file())
        self.assertIsNotNone(w.welcome_mosque.film, "the front door is showing the still")
        self.assertGreater(w.welcome_mosque.film.frameCount(), 1)
        self.assertIsNone(w.mosque.film, "the five prayers should not be animated")
        w.open_section("kalima")
        settle()
        self.assertIsNone(w.arch_menus["kalima"].mosque.film, "nor should the kalima")

    def test_it_runs_while_the_screen_is_up_and_stops_when_it_is_not(self):
        w = self.window()
        front = w.welcome_mosque
        running = QtGui.QMovie.MovieState.Running
        self.assertEqual(running, front.film.state(), "not playing on the screen it is on")
        w.leave_welcome()
        settle()
        self.assertNotEqual(running, front.film.state(),
                            "still playing with the mosque up in front of it")

    def test_the_film_is_the_same_canvas_as_the_still(self):
        """Every box on this screen was measured against the still."""
        w = self.window()
        front = w.welcome_mosque
        front.film.jumpToFrame(0)
        self.assertEqual(front.picture.size(), front.film.currentPixmap().size())

    def test_a_film_on_a_different_canvas_is_refused(self):
        """Rather than shown stretched, which would slide the drawing out of step with the
        places you can touch."""
        import shutil, tempfile
        from PIL import Image
        from salaah import mosque
        spare = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(spare, ignore_errors=True))
        shutil.copytree(ASSETS / "welcome", spare / "welcome")
        # Every frame resized, not just the first: resize() hands back one frame, and a
        # one-frame film is refused for being a still rather than for being the wrong size --
        # so the test passed without the size check ever running.
        from PIL import ImageSequence
        with Image.open(ASSETS / "welcome" / "mosque.gif") as source:
            frames = [f.convert("P").resize((400, 300))
                      for f in ImageSequence.Iterator(source)]
        frames[0].save(spare / "welcome" / "mosque.gif", save_all=True,
                       append_images=frames[1:], loop=0, duration=100)
        with Image.open(spare / "welcome" / "mosque.gif") as check:
            self.assertGreater(getattr(check, "n_frames", 1), 1, "the stand-in is not a film")
        screen = mosque.MosqueScreen(spare, folder="welcome")
        self.addCleanup(lambda: (screen.deleteLater(), APP.processEvents()))
        self.assertIsNone(screen.film, "a film of the wrong size was accepted")
        self.assertTrue(screen.ready, "and the still should still be shown")

    def test_the_frames_are_different_pictures_on_the_screen(self):
        w = self.window()
        front = w.welcome_mosque
        front.sky.birds = []
        front.sky.stars = []            # they twinkle, and would make every grab differ
        seen = []
        for i in range(front.film.frameCount()):
            front.film.jumpToFrame(i)
            settle()
            image = front.grab().toImage()
            seen.append(tuple(image.pixel(x, y)
                              for y in range(0, image.height(), 11)
                              for x in range(0, image.width(), 11)))
        self.assertGreater(len(set(seen)), 2,
                           f"the film has {front.film.frameCount()} frames but only "
                           f"{len(set(seen))} of them reach the screen")

    def test_the_dome_still_hides_the_sky_behind_it(self):
        """The film has no transparency of its own. Drawn instead of the still it would either
        paint over the stars everywhere or let them through the dome the clock sits on; laid
        over it, the still goes on doing the masking."""
        w = self.window()
        front = w.welcome_mosque
        front.sky.birds = []
        front.set_sky(False, 0.5)
        scaled, origin, scale = front.placement()
        box = front.clock_box
        front.set_time("")
        # A thick field of stars laid right across the dome rather than the handful the sky
        # happens to put there. With the real ones, so few land on the dome that the difference
        # was inside the tolerance and the test passed with the masking removed.
        stars = [(x / 60.0, y / 60.0, 1.0, 0.0) for x in range(20, 45) for y in range(20, 40)]
        self.assertGreater(len(stars), 300)

        def dome_pixels():
            settle()
            image = front.grab().toImage()
            return sum(1 for y in range(origin.y() + int((box.y() + 20) * scale),
                                        origin.y() + int((box.y() + box.height() - 20) * scale), 2)
                       for x in range(origin.x() + int((box.x() + 20) * scale),
                                      origin.x() + int((box.x() + box.width() - 20) * scale), 2)
                       if QtGui.QColor(image.pixel(x, y)).lightness() > 120)
        front.sky.stars = []
        bare = dome_pixels()
        front.sky.stars = stars
        starry = dome_pixels()
        self.assertLessEqual(starry, bare + 12,
                             f"{starry - bare} star pixels are showing through the dome")
        self.assertGreater(len(stars), 0, "the stars were put there to be masked")


    def test_the_film_moves_without_burying_the_sky_behind_it(self):
        """REVERSED IN 1.62. This said the drawing brought its own sky and the app painted none,
        which was true of the drawing it was written for. Harry's new animation has no sun, moon
        or stars in it and he asked for the app's, so the sky is cut out of every frame.

        The thing worth testing is therefore the opposite one, and it is the thing that would
        actually go wrong: a film is a rectangle, and a frame with the sky painted into it would
        bury the moon behind a black box while the still underneath looked perfectly right.
        """
        w = self.window()
        front = w.welcome_mosque
        self.assertTrue(front.own_sky, "the front door is not asking for a sky")
        self.assertIsNotNone(front.film, "there is no film to check")
        for frame in range(0, front.film.frameCount(), 7):
            with self.subTest(frame):
                front.film.jumpToFrame(frame)
                picture = front.film.currentPixmap()
                self.assertTrue(picture.hasAlphaChannel(),
                                f"frame {frame} has no see-through sky at all")
                corner = picture.toImage().pixelColor(2, 2)
                self.assertEqual(0, corner.alpha(),
                                 f"frame {frame} paints over the corner of the sky")

    def test_the_time_is_still_on_the_dome(self):
        """The one thing Harry asked for from the new drawing. It is written dark on it, where
        the old one was written light: that dome is a solid shape and the old one was a hole."""
        w = self.window()
        w.tick()                         # what puts the time on the dome
        settle()
        front = w.welcome_mosque
        self.assertTrue(front.clock_dark, "the numbers would be white on a white dome")
        self.assertRegex(front.time_text, r"^\d{1,2}:\d{2}$", "there is no time on the dome")
        self.assertTrue(front.clock_box.isValid() and front.clock_box.width() > 100)

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "dark", "recitation": False, "place": "Bury",
                                   "sleep_after": 1, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_it_wakes_at_the_front_door_not_where_it_was_left(self):
        w = self.window()
        w.leave_welcome()
        w.open_settings()
        settle()
        self.assertIs(w.settings_screen, w.stack.currentWidget())
        w.maybe_sleep()
        settle()
        self.assertTrue(w.asleep, "it should have gone to sleep")
        w.wake()
        settle()
        self.assertFalse(w.asleep)
        self.assertIs(w.welcome, w.stack.currentWidget(),
                      "it came back on yesterday's screen")

    def test_waking_mid_prayer_stays_where_it_was(self):
        """A prayer on screen is the one thing that must not be walked away from: the call
        wakes the mat and then takes it home itself."""
        w = self.window()
        w.leave_welcome()
        entry = w.school.prayers["fajr"][0]
        w.start("fajr", entry)
        settle()
        self.assertTrue(w.playing)
        was = w.stack.currentWidget()
        w.maybe_sleep()
        w.asleep = True                      # a prayer keeps it awake, so put it under by hand
        w.wake()
        settle()
        self.assertIs(was, w.stack.currentWidget(), "it walked out of a prayer")


class FrontDoorBannerTest(unittest.TestCase):
    """The front door wears the same strip as the mosque, and the strip now leads with a pin."""

    def window(self, **settings):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "dark", "recitation": False, "place": "Bury",
                                   **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def strip(self, w, page):
        strips = [x for x in page.findChildren(QtWidgets.QWidget)
                  if x.objectName() == "banner"]
        self.assertEqual(1, len(strips), "one strip, no more and no fewer")
        return strips[0]

    def test_the_front_door_has_the_same_strip_as_the_mosque(self):
        w = self.window()
        front = self.strip(w, w.welcome)
        said = [x for x in front.findChildren(QtWidgets.QLabel)
                if x.objectName() == "bannerText"]
        self.assertEqual(1, len(said))
        self.assertIn("Bury", said[0].text())
        for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
            self.assertIn(w.t(f"prayer.{prayer}"), said[0].text(), prayer)
        self.assertEqual(1, len(front.findChildren(QtWidgets.QSlider)), "and how loud it is")
        self.assertEqual(0, front.mapTo(w.welcome, QtCore.QPoint(0, 0)).y(),
                         "the strip is the top of the screen")

    def test_the_pin_comes_before_the_place(self):
        w = self.window()
        front = self.strip(w, w.welcome)
        pins = [x for x in front.findChildren(QtWidgets.QLabel) if x.objectName() == "bannerPin"]
        self.assertEqual(1, len(pins), "no pin on the strip")
        pin, words = pins[0], next(x for x in front.findChildren(QtWidgets.QLabel)
                                   if x.objectName() == "bannerText")
        self.assertFalse(pin.pixmap().isNull(), "the pin is empty")
        self.assertLess(pin.mapTo(front, pin.rect().center()).x(),
                        words.mapTo(front, QtCore.QPoint(0, 0)).x(),
                        "the pin should come before the words, not after them")

    def test_every_strip_has_one(self):
        w = self.window()
        pins = [x for x in w.findChildren(QtWidgets.QLabel) if x.objectName() == "bannerPin"]
        self.assertEqual(len(w.banner_labels), len(pins),
                         "a strip somewhere is missing its pin")

    def test_the_place_is_written_in_blue_and_the_times_are_not(self):
        from salaah.ui import BANNER_BLUE
        w = self.window()
        said = next(x for x in w.welcome.findChildren(QtWidgets.QLabel)
                    if x.objectName() == "bannerText").text()
        self.assertIn(f'<span style="color:{BANNER_BLUE}">Bury</span>', said)
        after = said.split("</span>", 1)[1]
        self.assertNotIn(BANNER_BLUE, after, "the prayer times went blue as well")

    def test_the_blue_is_a_blue_and_reads_on_the_black_strip(self):
        """The test below compares against the constant, so it follows wherever the constant
        goes -- set it to off-white and that test still passes. This is what pins it down."""
        from salaah.ui import BANNER_BLUE
        blue = QtGui.QColor(BANNER_BLUE)
        self.assertGreater(blue.blue(), blue.red() + 60, "that is not a blue")
        self.assertGreater(blue.blue(), blue.green() + 40, "that is not a blue")
        self.assertGreater(blue.lightness(), 110, "too dark to read on a black strip")

    def test_the_place_is_painted_blue_on_the_screen(self):
        """Rendered: rich text that names a colour and then does not use it is a real enough
        mistake, and only the pixels say."""
        from salaah.ui import BANNER_BLUE
        w = self.window()
        front = self.strip(w, w.welcome)
        words = next(x for x in front.findChildren(QtWidgets.QLabel)
                     if x.objectName() == "bannerText")
        image = words.grab().toImage()
        want = QtGui.QColor(BANNER_BLUE)
        # Near enough the exact colour, not merely blue-ish. White lettering carries coloured
        # fringes from the antialiasing, and some of them are bluer than the blue -- a loose
        # test counted those and passed on a strip with no blue on it at all.
        blue = sum(1 for y in range(image.height()) for x in range(image.width())
                   if (abs(QtGui.QColor(image.pixel(x, y)).red() - want.red()) < 10
                       and abs(QtGui.QColor(image.pixel(x, y)).green() - want.green()) < 10
                       and abs(QtGui.QColor(image.pixel(x, y)).blue() - want.blue()) < 10))
        self.assertGreater(blue, 150, "nothing on the strip is painted in the blue")


class MapPinTest(unittest.TestCase):
    """The pin is drawn in code. The picture that was sent over is a stock-library preview with
    a watermark down its left edge, which has no business on a mat somebody owns."""

    def test_it_is_a_round_head_with_a_hole_and_a_point(self):
        from salaah.ui import map_pin
        image = map_pin(240, "#8FB1F0").toImage()
        self.assertEqual(0, QtGui.QColor(image.pixelColor(120, 90)).alpha(),
                         "the middle of the head should be a hole")
        self.assertEqual(255, QtGui.QColor(image.pixelColor(120, 30)).alpha(), "the head")
        self.assertEqual(255, QtGui.QColor(image.pixelColor(120, 225)).alpha(), "the point")
        self.assertEqual(0, QtGui.QColor(image.pixelColor(12, 225)).alpha(),
                         "it should taper: the bottom corners are empty")

    def test_it_takes_the_colour_it_is_given(self):
        from salaah.ui import map_pin
        for colour in ("#8FB1F0", "#B4443A"):
            image = map_pin(120, colour).toImage()
            got = QtGui.QColor(image.pixelColor(60, 15))
            self.assertEqual(QtGui.QColor(colour).name(), got.name(), colour)

    def test_it_is_drawn_rather_than_carried_as_a_picture(self):
        self.assertFalse((ASSETS / "pin.png").exists())
        self.assertFalse(list(ASSETS.glob("**/*pin*")), "a pin picture crept into the assets")


class WalkIntoTheNameTest(unittest.TestCase):
    """Touching MySalaah walks into the name, the way touching an arch walks into the arch."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_touching_the_name_starts_a_walk(self):
        w = self.window()
        self.assertFalse(w.veil.running)
        w.welcome_mosque.chosen.emit("enter")
        settle()
        self.assertTrue(w.veil.running, "nothing is walking anywhere")
        self.assertIs(w.home, w.stack.currentWidget(),
                      "the screen changes first; the walk is only laid over it")

    def test_the_walk_heads_for_the_name_and_not_the_middle_of_the_screen(self):
        w = self.window()
        panel = w.welcome_mosque.arch_centre("enter")
        w.welcome_mosque.chosen.emit("enter")
        settle()
        aimed = w.veil.focus * w.veil.COARSE
        self.assertLess(abs(aimed.x() - panel.x()), 30, "not aimed at the name across the front")
        self.assertLess(abs(aimed.y() - (panel.y() + w.welcome.height() - w.welcome_mosque.height())),
                        60, "not aimed at the right height")

    def test_it_ends_on_the_mosque_even_if_the_walk_is_cut_short(self):
        """The animation is never what decides which screen you are on."""
        w = self.window()
        w.welcome_mosque.chosen.emit("enter")
        settle()
        w.veil.stop()
        settle()
        self.assertFalse(w.veil.running)
        self.assertIs(w.home, w.stack.currentWidget())

    def test_going_in_from_anywhere_else_does_not_start_a_walk(self):
        """Only the front door walks into the name. Coming back from Settings, or a prayer
        falling due, should not blow the mosque up in somebody's face."""
        w = self.window()
        w.leave_welcome()
        w.veil.stop()
        settle()
        w.open_settings()
        settle()
        w.leave_welcome()
        settle()
        self.assertFalse(w.veil.running, "it walked in from a screen that is not the front door")


class SixTileMenuTest(unittest.TestCase):
    """The 7in menu: six tiles, two across and three down, filling the screen with no heading."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_tiles_sit_two_across_and_four_down(self):
        """Three down until Harry redrew the sheet with Wu'du and Nasheeds on the end."""
        w = self.window()
        tiles = w.side.corner.tiles
        self.assertEqual(8, len(tiles))
        columns = sorted({t.x() for t in tiles})
        rows = sorted({t.y() for t in tiles})
        self.assertEqual(2, len(columns), f"expected two columns, got {columns}")
        self.assertEqual(4, len(rows), f"expected four rows, got {rows}")
        # reading order: across, then down
        order = sorted(tiles, key=lambda t: (t.y(), t.x()))
        self.assertEqual(["quran", "salaah", "hadith", "duas",
                          "wudu", "nasheeds", "settings", "world"],
                         [t.name for t in order])

    def test_the_heading_is_gone_and_the_tiles_take_the_height(self):
        """The words are drawn into the tiles, so a title above them said a third thing on a
        screen with room for two -- and took the height the tiles wanted."""
        w = self.window()
        corner = w.side.corner
        said = [x.text() for x in corner.findChildren(QtWidgets.QLabel) if x.text()]
        self.assertEqual([], said, f"there is still lettering above the tiles: {said}")
        self.assertNotIn("Knowledge", " ".join(
            x.text() for x in w.side.findChildren(QtWidgets.QLabel)))
        top = min(t.y() for t in corner.tiles)
        bottom = max(t.y() + t.height() for t in corner.tiles)
        self.assertLess(top, w.side.height() * 0.05, "space wasted above the tiles")
        self.assertGreater(bottom, w.side.height() * 0.95, "space wasted below them")

    def test_every_tile_has_its_own_picture_and_they_are_all_different(self):
        """The picture each tile is actually pointed at, not the files on disk. Eight correct
        files prove nothing if every tile is wired to the same one -- which is exactly what
        the first version of this missed."""
        w = self.window()
        pointed = {t.name: t.path for t in w.side.corner.tiles}
        self.assertEqual(8, len(set(pointed.values())), f"tiles share pictures: {pointed}")
        seen = {}
        for name, path in pointed.items():
            self.assertEqual(f"{name}.png", path.name, f"{name} is pointed at {path.name}")
            self.assertTrue(path.is_file(), name)
            image = QtGui.QImage(str(path))  # noqa: the path the tile itself carries
            self.assertFalse(image.isNull(), name)
            self.assertGreater(image.width(), 200, name)
            self.assertLess(abs(image.width() - image.height()), image.width() * 0.2,
                            f"{name} is not the square the tiles were drawn as")
            ink = tuple(image.pixel(x, y) for y in range(0, image.height(), 9)
                        for x in range(0, image.width(), 9))
            self.assertNotIn(ink, seen, f"{name} is the same picture as {seen.get(ink)}")
            seen[ink] = name

    def test_the_four_that_are_filled_in_still_open_what_they_did(self):
        w = self.window()
        by_name = {t.name: t for t in w.side.corner.tiles}
        by_name["quran"].click()
        settle()
        self.assertIs(w.surah_list, w.corner_screen.currentWidget())
        w.go_home()
        by_name["duas"].click()
        settle()
        self.assertIs(w.dua_menu, w.corner_screen.currentWidget(),
                      "the Du'as tile should open the kinds")
        w.go_home()
        by_name["hadith"].click()
        settle()
        self.assertIs(w.hadith_menu, w.corner_screen.currentWidget(),
                      "the Hadith tile should open the twelve headings")
        w.go_home()
        # The fifth used to be the kalima. They are behind the du'a menu now, and this square
        # is Salaah: straight to the five prayers rather than into the Knowledge Corner.
        by_name["salaah"].click()
        settle()
        self.assertIs(w.home, w.stack.currentWidget())

    def test_a_tile_whose_section_is_missing_lands_on_a_named_empty_screen(self):
        """Every one of the six leads somewhere now -- hadith was the last that did not, and it
        has its twelve headings since. What is left to check is the fallback: a mat whose assets
        were half copied still lands on a screen that SAYS which section is missing, rather than
        on an empty menu or a blank page."""
        w = self.window()
        by_name = {t.name: t for t in w.side.corner.tiles}
        for name, heading in (("hadith", "Hadith"),):
            w.go_home()
            settle()
            w.section_lists[name].passages._items = []
            by_name[name].click()
            settle()
            self.assertIs(w.corner_soon, w.corner_screen.currentWidget(), name)
            self.assertIs(w.corner_page, w.stack.currentWidget(), name)
            self.assertEqual(heading, w.soon_title.text(), name)
            said = [x.text() for x in w.corner_soon.findChildren(QtWidgets.QLabel)]
            self.assertIn(w.t("corner.not_yet"), said, name)

    def test_the_empty_screen_carries_the_strip_like_every_other(self):
        w = self.window()
        w.section_lists["hadith"].passages._items = []
        {t.name: t for t in w.side.corner.tiles}["hadith"].click()
        settle()
        strips = [x for x in w.corner_page.findChildren(QtWidgets.QWidget)
                  if x.objectName() == "banner"]
        self.assertEqual(1, len(strips))
        said = next(x for x in strips[0].findChildren(QtWidgets.QLabel)
                    if x.objectName() == "bannerText")
        self.assertIn("Bury", said.text())
        for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
            self.assertIn(w.t(f"prayer.{prayer}"), said.text(), prayer)

    def test_every_reading_tile_is_named_in_every_language(self):
        """Every tile that lands on a Knowledge screen needs a name for its heading. Settings
        is not one of those -- it goes to the Settings screen, which has its own title."""
        import json
        from salaah.knowledge import TILES
        readings = [n for n in TILES if n != "settings"]
        self.assertEqual(7, len(readings))
        for lang in sorted(full_packs(available_packs(ASSETS))):
            ui = json.loads((ASSETS / "content" / "packs" / lang / "pack.json")
                            .read_text(encoding="utf-8"))["ui"]
            for name in readings:
                self.assertTrue(ui.get(f"corner.{name}", "").strip(),
                                f"{lang} has no name for {name}")

    def test_a_tile_is_a_big_enough_target_for_a_finger(self):
        w = self.window()
        for tile in w.side.corner.tiles:
            self.assertGreater(tile.width(), 200, tile.name)
            self.assertGreater(tile.height(), 200, tile.name)


class SettingsFromTheTileTest(unittest.TestCase):
    """Settings is reached from the 7in tile, so the red cog has left the strip."""

    def window(self, side=True):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=side)
        w.resize(1920, 1080)
        w.show()
        if side:
            w.side.resize(600, 1024)
            w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_settings_tile_opens_settings(self):
        w = self.window()
        {t.name: t for t in w.side.corner.tiles}["settings"].click()
        settle()
        self.assertIs(w.settings_screen, w.stack.currentWidget())

    def test_it_does_not_land_on_the_not_filled_in_screen(self):
        """Settings is not a reading. Sent through the same door as the others it would have
        come out on the screen that says there is nothing here yet."""
        w = self.window()
        {t.name: t for t in w.side.corner.tiles}["settings"].click()
        settle()
        self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget())
        self.assertIsNot(w.corner_page, w.stack.currentWidget())

    def test_no_cog_on_any_strip_when_the_small_screen_is_there(self):
        from salaah.mosque import GearButton
        w = self.window()
        for page in (w.welcome, w.home, w.corner_page):
            strips = [x for x in page.findChildren(QtWidgets.QWidget)
                      if x.objectName() == "banner"]
            for strip in strips:
                self.assertEqual([], strip.findChildren(GearButton),
                                 "a cog is still on a strip")

    def test_the_cog_stays_when_there_is_no_small_screen_to_replace_it(self):
        """Without the 7in there is no Settings tile, and taking the cog away as well would
        wall Settings off with no way in at all."""
        from salaah.mosque import GearButton
        w = self.window(side=False)
        self.assertTrue(w.needs_a_gear)
        cogs = [x for x in w.home.findChildren(GearButton)]
        self.assertTrue(cogs, "no way into Settings on a mat with one screen")
        cogs[0].pressed_signal.emit()
        settle()
        self.assertIs(w.settings_screen, w.stack.currentWidget())

    def test_the_settings_tile_is_not_shown_as_a_reading(self):
        w = self.window()
        w.chose_on_the_small_screen("settings")
        settle()
        self.assertIs(w.settings_screen, w.stack.currentWidget())
        w.go_home()
        settle()
        w.chose_on_the_small_screen("hadith")
        settle()
        self.assertIs(w.hadith_menu, w.corner_screen.currentWidget(),
                      "the readings should still go the way they did")


class VolumeSliderLookTest(unittest.TestCase):
    """The slider on the strip: bigger, and with no figure printed beside it."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=True, place="Bury", volume=60),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def showing(self, w):
        bars = [b for b, _ in w.volume_bars if b.isVisible()]
        self.assertTrue(bars, "no slider is on screen")
        return bars[0]

    def test_no_percentage_is_printed_beside_it(self):
        w = self.window()
        for bar, read in w.volume_bars:
            self.assertFalse(read.isVisible(), "the figure is still on the strip")
        # Anything else on the strip that prints one -- a hidden label still answers text(),
        # so only what is actually on screen counts.
        said = " ".join(x.text() for x in w.welcome.findChildren(QtWidgets.QLabel)
                        if x.text() and x.isVisible())
        self.assertNotIn("%", said, "a percentage is still printed on the strip")

    def test_it_is_bigger_than_it_was(self):
        w = self.window()
        bar = self.showing(w)
        self.assertGreaterEqual(bar.width(), w.px(300), "no wider than before")
        self.assertGreaterEqual(bar.height(), w.px(50), "no taller than before")

    def test_it_still_fits_inside_the_strip(self):
        w = self.window()
        bar = self.showing(w)
        strip = next(x for x in w.welcome.findChildren(QtWidgets.QWidget)
                     if x.objectName() == "banner")
        self.assertLessEqual(bar.height(), strip.height(),
                             "the slider is taller than the strip it sits in")

    def test_it_still_sets_the_volume(self):
        w = self.window()
        self.showing(w).setValue(25)
        settle()
        self.assertEqual(25, w.settings.volume)
        for bar, _ in w.volume_bars:
            self.assertEqual(25, bar.value(), "the sliders came out of step")


class FrontDoorFillsTheScreenTest(unittest.TestCase):
    """The drawing carried about a fifth of its height in empty sky. Cut to the shape of the
    screen, it fills it: palms on both edges, the base on the floor, the moon under the strip."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_there_are_no_black_bars_round_the_picture(self):
        w = self.window()
        front = w.welcome_mosque
        scaled, origin, _ = front.placement()
        self.assertLessEqual(origin.x(), 8, f"{origin.x()}px of black either side")
        self.assertLessEqual(origin.y(), 8, f"{origin.y()}px of black above and below")
        self.assertGreaterEqual(scaled.width(), front.width() - 8, "it does not reach the sides")
        self.assertGreaterEqual(scaled.height(), front.height() - 8, "it does not fill the height")

    def test_the_sky_above_the_drawing_is_where_the_moon_goes(self):
        """CHANGED IN 1.62. This used to insist the drawing began within a twelfth of the top,
        because empty canvas above it was black nobody could do anything with.

        Harry's new one starts a fifth of the way down, and that space is not empty: it is the
        sky he asked to have populated, and the moon, the sun and the stars are painted into it.
        So what has to be true is not that there is no sky above the building but that the app's
        sky REACHES it -- the gap has to be see-through all the way across, and the moon has to
        land inside it rather than behind the dome.
        """
        image = QtGui.QImage(str(ASSETS / "welcome" / "mosque.png"))
        top = bottom = None
        for y in range(image.height()):
            if any(QtGui.QColor(image.pixelColor(x, y)).alpha() > 40
                   for x in range(0, image.width(), 5)):
                top = y if top is None else top
                bottom = y
        self.assertIsNotNone(top)
        self.assertGreater(bottom, image.height() * 0.92,
                           f"{image.height()-bottom}px of empty space below it")
        for y in range(0, top, 7):
            clear = sum(1 for x in range(0, image.width(), 5)
                        if QtGui.QColor(image.pixelColor(x, y)).alpha() == 0)
            self.assertEqual(len(range(0, image.width(), 5)), clear,
                             f"row {y} above the building is not see-through")
        w = self.window()
        front = w.welcome_mosque
        scaled, origin, _ = front.placement()
        # At the top of its arc -- the middle of the day or the middle of the night -- the body
        # has to be clear of the building. Not at the ends of it: there the sun is rising or
        # setting and goes down behind the mosque, which is what rising and setting look like
        # and is how it has always behaved on the two mosques behind this one.
        front.set_sky(False, 0.5)
        centre, radius = front.sky_body(scaled, origin)
        roof = origin.y() + scaled.height() * (top / image.height())
        self.assertLess(centre.y() + radius, roof,
                        f"at its highest the moon is at y {centre.y():.0f}, and the building "
                        f"starts at {roof:.0f}")

    def test_the_picture_is_cut_to_the_shape_of_the_screen(self):
        w = self.window()
        front = w.welcome_mosque
        self.assertLess(abs(front.picture.width() / front.picture.height()
                            - front.width() / front.height()), 0.05,
                        "the drawing is not the shape of the screen it has to fill")

    def test_the_film_was_cut_the_same_way(self):
        w = self.window()
        front = w.welcome_mosque
        self.assertIsNotNone(front.film, "the film was lost in the recut")
        front.film.jumpToFrame(0)
        self.assertEqual(front.picture.size(), front.film.currentPixmap().size())

    def test_the_name_is_still_where_it_can_be_touched(self):
        """The boxes were measured on the old canvas. Cut the picture and forget to rebuild
        them and the panel you touch is somewhere else entirely."""
        w = self.window()
        front = w.welcome_mosque
        middle = front.arch_centre("enter")
        self.assertIsNotNone(middle)
        self.assertEqual("enter", front.arch_at(middle))
        box = front.arches[0].box
        self.assertGreater(box.y(), front.picture.height() * 0.45, "the panel is too high up")
        self.assertLess(box.bottom(), front.picture.height(), "the panel runs off the bottom")


class DuaMenuTest(unittest.TestCase):
    """Touching Du'as lands on the eighteen kinds, and a kind shows only its own."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_duas_tile_opens_the_kinds_and_not_the_long_list(self):
        w = self.window()
        w.chose_on_the_small_screen("duas")
        settle()
        self.assertIsNotNone(w.dua_menu, "the menu was not built")
        self.assertIs(w.dua_menu, w.corner_screen.currentWidget())

    def test_every_kind_is_touchable_and_carries_its_own_picture(self):
        from salaah.duamenu import CATEGORIES, NOT_A_KIND
        w = self.window()
        tiles = {t.name: t for t in w.dua_menu.tiles}
        self.assertEqual(set(CATEGORIES), set(tiles))
        for name, tile in tiles.items():
            self.assertEqual(f"{name}.png", tile.path.name,
                             f"the {name} tile is drawn from {tile.path.name}")
            self.assertTrue(tile.path.is_file())
            self.assertTrue(tile.isEnabled())

    def test_a_kind_shows_only_the_duas_filed_under_it(self):
        w = self.window()
        w.open_dua_category("worry")
        settle()
        board = w.dua_board
        self.assertIs(board, w.corner_screen.currentWidget())
        shown = [item for _, item in board.showing]
        self.assertTrue(shown, "nothing came up under worry")
        for item in shown:
            self.assertIn("worry", item.cats, "a du'a of another kind is on screen")
        # by key: a Passage carries a dict of meanings, so it cannot go in a set
        self.assertTrue({d.key for d in shown}
                        <= {d.key for d in board.passages.items if "worry" in d.cats})

    def test_the_rows_on_screen_are_the_ones_the_filter_kept(self):
        """wanted() saying the right thing is not the same as the screen showing it."""
        w = self.window()
        w.open_dua_category("forgiveness")
        settle()
        board = w.dua_board
        titles = {item.title for _, item in board.showing}
        on_screen = {x.text() for x in board.findChildren(QtWidgets.QLabel)
                     if x.text() and x.isVisible()}
        self.assertTrue(titles <= on_screen, f"{titles - on_screen} was picked but not drawn")
        others = {d.title for d in board.passages.items
                  if "forgiveness" not in d.cats}
        self.assertEqual(set(), others & on_screen, "a du'a from another kind is on screen")

    def test_changing_kind_replaces_the_rows_rather_than_adding_to_them(self):
        w = self.window()
        board = w.dua_board
        w.open_dua_category("worry")
        settle()
        first = len(board.cards)
        self.assertGreater(first, 0, "nothing was shown to begin with")
        w.open_dua_category("mosque")
        settle()
        self.assertEqual(len(board.showing), len(board.cards),
                         f"{len(board.cards)} cards for {len(board.showing)} picked -- "
                         f"the cards from the kind before are still standing")
        for card in board.cards:
            self.assertIn("mosque", card.item.cats, "a card from the kind before survived")

    def test_opening_one_from_a_narrowed_list_opens_that_very_dua(self):
        """The row keeps its place in the whole section. Number the rows 0,1,2 inside the
        filter instead and the third du'a under a kind opens the third du'a overall."""
        w = self.window()
        w.open_dua_category("worry")
        settle()
        listing = w.section_lists["duas"]
        board = w.dua_board
        card = board.cards[-1]
        index, wanted = card.index, card.item
        # Press the card itself. Emitting chose(index) here instead would prove nothing: the
        # test would be supplying the very number the card is supposed to carry.
        card.opened.emit(card.index)
        settle()
        reader = w.section_readers["duas"]
        self.assertIs(reader, w.corner_screen.currentWidget())
        self.assertEqual(index, reader.at, "a different du'a opened")
        opened = reader.passages.items[reader.at]
        self.assertEqual(wanted.title, opened.title)
        self.assertIn("worry", opened.cats)

    def test_a_kind_with_nothing_in_it_says_which_kind_it_is(self):
        """Every kind has du'as now, so this empties one to get at the behaviour -- which is
        what a mat with a half-copied content folder would see."""
        w = self.window()
        listing = w.section_lists["duas"]
        kept = list(listing.passages.items)     # reading it is what loads the file
        listing.passages._items = [d for d in kept if "travel" not in d.cats]
        self.addCleanup(lambda: setattr(listing.passages, "_items", kept))
        w.open_dua_category("travel")
        settle()
        self.assertIs(w.corner_soon, w.corner_screen.currentWidget())
        self.assertEqual(w.t("dua.travel"), w.soon_title.text())
        self.assertNotEqual("", w.soon_title.text().strip())

    def test_the_whole_list_comes_back_when_it_is_asked_for(self):
        w = self.window()
        board = w.dua_board
        w.open_dua_category("worry")
        settle()
        narrowed = len(board.wanted())
        board.show_only(None)
        settle()
        self.assertEqual(len(board.passages.items), len(board.wanted()))
        self.assertLess(narrowed, len(board.wanted()))

    def test_the_kinds_are_left_alone_while_a_prayer_is_going_on(self):
        w = self.window()
        w.open_dua_category("worry")
        settle()
        board = w.dua_board
        # Both kinds land on the same widget, so what is SHOWN is what has to be looked at.
        was = [i for i, _ in board.wanted()]
        with mock.patch.object(type(w), "playing", property(lambda _self: True)):
            w.open_dua_category("forgiveness")
            settle()
            self.assertEqual(was, [i for i, _ in board.wanted()],
                             "a stray knee changed the screen mid-prayer")
        w.open_dua_category("forgiveness")
        settle()
        self.assertNotEqual(was, [i for i, _ in board.wanted()],
                            "and it still works once the prayer is over")


class DuaBoardTest(unittest.TestCase):
    """Two columns with a rule between them, a play mark on every du'a, and the meaning under
    the Arabic -- all of it measured off what is drawn, not off the layout's opinion."""

    def window(self, theme="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=theme, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def board(self, w, cat="travel"):
        w.open_corner("duas")
        settle()
        w.open_dua_category(cat)
        settle()
        self.assertIs(w.dua_board, w.corner_screen.currentWidget())
        return w.dua_board

    def test_two_duas_are_shown_one_each_side(self):
        """Two, no more: the whole point of the size they are drawn at."""
        from salaah.duamenu import CATEGORIES, NOT_A_KIND
        w = self.window()
        for cat in (c for c in CATEGORIES if c not in NOT_A_KIND):
            board = self.board(w, cat)
            left = [board.left.itemAt(i).widget() for i in range(board.left.count())]
            right = [board.right.itemAt(i).widget() for i in range(board.right.count())]
            left = [x for x in left if x is not None]
            right = [x for x in right if x is not None]
            self.assertEqual(1, len(left), f"{cat} has {len(left)} on the left")
            self.assertEqual(1, len(right), f"{cat} has {len(right)} on the right")
            self.assertEqual(2, len(board.cards), f"{cat} drew {len(board.cards)} cards")

    def test_the_two_columns_really_are_side_by_side_on_screen(self):
        """Counting widgets in two boxes says nothing about where they were drawn."""
        w = self.window()
        board = self.board(w, "worry")
        left = [c for c in board.cards if board.left.indexOf(c) >= 0]
        right = [c for c in board.cards if board.right.indexOf(c) >= 0]
        edge = max(c.mapTo(board, c.rect().topRight()).x() for c in left)
        start = min(c.mapTo(board, c.rect().topLeft()).x() for c in right)
        self.assertLess(edge, start, "the columns overlap instead of sitting side by side")

    def test_a_thick_rule_is_drawn_between_them(self):
        w = self.window()
        board = self.board(w, "travel")
        self.assertIsNotNone(board.rule, "no rule between the columns")
        self.assertGreaterEqual(board.rule.width(), w.px(5), "the rule is a hairline")
        # Drawn, not merely sized: a widget styled to a width it paints nothing into is not a
        # line. Its own pixels are what settle it.
        image = board.rule.grab().toImage()
        self.assertGreater(image.width(), 0)
        middle = image.pixelColor(image.width() // 2, image.height() // 2)
        page = w.palette().color(w.backgroundRole())
        self.assertNotEqual((page.red(), page.green(), page.blue()),
                            (middle.red(), middle.green(), middle.blue()),
                            "the rule is the same colour as the page behind it")

    def test_the_rule_sits_between_the_columns_and_not_beside_them(self):
        w = self.window()
        board = self.board(w, "worry")
        rule = board.rule.mapTo(board, board.rule.rect().center()).x()
        left = [c for c in board.cards if board.left.indexOf(c) >= 0]
        right = [c for c in board.cards if board.right.indexOf(c) >= 0]
        self.assertLess(max(c.mapTo(board, c.rect().topRight()).x() for c in left), rule)
        self.assertGreater(min(c.mapTo(board, c.rect().topLeft()).x() for c in right), rule)

    def test_every_dua_carries_a_play_mark_that_is_actually_drawn(self):
        w = self.window()
        board = self.board(w, "worry")
        for card in board.cards:
            self.assertFalse(card.button.icon().isNull(), f"{card.item.key} has no play mark")
            shot = card.button.grab().toImage()
            page = w.palette().color(w.backgroundRole())
            ink = sum(1 for y in range(0, shot.height(), 2) for x in range(0, shot.width(), 2)
                      if abs(shot.pixelColor(x, y).red() - page.red()) > 40)
            self.assertGreater(ink, 20, f"{card.item.key}'s mark is a blank square")

    def test_the_arabic_and_the_meaning_are_both_on_the_card(self):
        w = self.window()
        board = self.board(w, "travel")
        for card in board.cards:
            self.assertEqual([card.item.arabic], list(card.arabic.lines))
            self.assertTrue(card.meaning.text().strip(), f"{card.item.key} has no meaning")
            self.assertTrue(card.meaning.isVisible())
            self.assertNotEqual(card.item.arabic, card.meaning.text())

    def test_a_dua_with_no_transliteration_shows_no_empty_line_for_it(self):
        """The ones from hadith have no transliteration yet. An empty italic line would read
        as a missing word rather than as nothing to say.

        Which is now moot: there is no transliteration line on a card at all. It appeared on ten
        du'as and not on the other thirty-eight, and Harry had it taken out once every du'a could
        be heard read aloud. So what this asks is the stronger version of what it used to ask --
        not that the line is hidden when empty, but that it is not there to be empty."""
        w = self.window()
        board = self.board(w, "travel")
        for card in board.cards:
            self.assertFalse(hasattr(card, "said"),
                             f"{card.item.key} still carries a transliteration line")

    def test_pressing_a_card_opens_that_very_dua(self):
        w = self.window()
        board = self.board(w, "worry")
        # Taken before pressing anything: reopening the kind reshuffles, so a card held across
        # the loop would be a card that is no longer on screen.
        want = [(c.index, c.item.title) for c in board.cards]
        for index, title in want:
            card = next(c for c in board.cards if c.index == index)
            card.opened.emit(card.index)
            settle()
            reader = w.section_readers["duas"]
            self.assertIs(reader, w.corner_screen.currentWidget())
            self.assertEqual(index, reader.at)
            self.assertEqual(title, reader.passages.items[reader.at].title)
            w.corner_screen.setCurrentWidget(board)      # back without reshuffling
            settle()

    def test_the_play_mark_reads_the_dua_its_card_stands_for(self):
        """It used to open that du'a's own page. It reads it here now, and the card it reads is
        the card that was pressed -- which is the same claim, about the right du'a, made against
        what actually happens."""
        w = self.window()
        board = self.board(w, "health")
        card = board.cards[-1]
        card.button.click()
        settle()
        self.assertIs(board, w.corner_screen.currentWidget(), "it left the board")
        self.assertIs(card, board.said_by, "the wrong card is being read")
        board.stop_saying()
        settle()

    def test_there_is_no_button_strip_along_the_bottom(self):
        """It was taken away to give the Arabic the height. Checked by looking for any button
        on the board rather than for the one that used to be there, so a different one put
        back in the same place is caught too."""
        w = self.window()
        board = self.board(w, "travel")
        self.assertFalse(hasattr(board, "back_button"))
        buttons = [b for b in board.findChildren(QtWidgets.QAbstractButton) if b.isVisible()]
        for b in buttons:
            self.assertEqual("duaPlay", b.objectName(),
                             f"{b.objectName() or b.text()!r} is on the board")
        floor = max(c.mapTo(board, c.rect().bottomLeft()).y() for c in board.cards)
        self.assertGreater(floor, board.height() * 0.93,
                           "the cards stop short of the bottom -- something is taking that strip")

    def test_no_kind_scrolls_at_all(self):
        """Now that the Arabic sizes itself to its box, nothing should ever need scrolling."""
        from salaah.duamenu import CATEGORIES, NOT_A_KIND
        w = self.window()
        scrolls = []
        for cat in (c for c in CATEGORIES if c not in NOT_A_KIND):
            board = self.board(w, cat)
            if board.scroll.verticalScrollBar().maximum() > 0:
                scrolls.append(cat)
        self.assertEqual([], scrolls, f"these kinds do not fit: {scrolls}")

    def test_the_two_longest_duas_together_still_fit(self):
        """The worst pair the shuffle can deal, forced rather than waited for."""
        w = self.window()
        board = self.board(w, "forgiveness")
        board.showing = sorted(board.wanted(), key=lambda p: -len(p[1].arabic))[:2]
        board.filled = None
        board.fill()
        settle()
        self.assertEqual(0, board.scroll.verticalScrollBar().maximum(),
                         "the longest two run off the screen")

    def test_a_short_dua_is_drawn_far_larger_than_a_long_one(self):
        """The box earns its keep only if it really does change size. Measured off the font
        the box settled on, not off the stylesheet."""
        w = self.window()
        board = self.board(w, "mosque")             # two very short du'as
        short = max(c.arabic.fitted_size() for c in board.cards)
        board = self.board(w, "forgiveness")
        board.showing = sorted(board.wanted(), key=lambda p: -len(p[1].arabic))[:2]
        board.filled = None
        board.fill()
        settle()
        long = max(c.arabic.fitted_size() for c in board.cards)
        self.assertGreater(short, long * 1.5, f"short {short}px vs long {long}px")

    def test_which_two_are_shown_changes_between_visits(self):
        """Opening the same kind ten times should not give the same pair every time. Every kind
        holds at least three, so there is always another pair to give."""
        w = self.window()
        seen = set()
        for _ in range(12):
            board = self.board(w, "gratitude")
            seen.add(tuple(sorted(i for i, _ in board.showing)))
        self.assertGreater(len(seen), 1, "the same two came up twelve times running")

    def test_nothing_along_the_bottom_takes_height_from_the_arabic(self):
        """Back was removed to give that strip's height to the words. If anything creeps back
        along the bottom, the reason for two-at-a-time is gone."""
        w = self.window()
        board = self.board(w, "worry")
        self.assertFalse(hasattr(board, "back_button"), "a Back button is on the board again")
        floor = max(c.mapTo(board, c.rect().bottomLeft()).y() for c in board.cards)
        self.assertGreater(floor, board.height() * 0.9,
                           f"the cards stop {board.height() - floor}px short of the bottom")

    def test_the_board_is_not_a_dead_end(self):
        """Taking Back off is only safe because the strip above carries the way out. If that
        ever goes too, somebody is stuck on a du'a screen with no way off it."""
        w = self.window()
        board = self.board(w, "travel")
        outs = [b for b in w.corner_page.findChildren(QtWidgets.QPushButton)
                if b.isVisible() and b.objectName() in ("mainScreen", "backButton")]
        self.assertTrue(outs, "no way off the du'a board at all")
        outs[0].click()
        settle()
        self.assertIs(w.welcome, w.stack.currentWidget(), "the way out did not lead anywhere")

    def test_the_pair_does_not_change_under_you_while_the_screen_is_shown(self):
        """Stepping into a du'a and coming back must bring back the same two. The pick belongs
        to opening the kind, not to the screen being shown.

        Driven through the screens rather than by hiding and showing the widget. hide() then
        show() on a page inside a stack delivers no showEvent at all, so the first version of
        this test passed a sabotage that re-picked the pair on every show -- it was watching a
        door nobody uses. Opening a du'a and pressing Back is the path that really happens.
        """
        w = self.window()
        board = self.board(w, "gratitude")
        was = [i for i, _ in board.showing]
        card = board.cards[0]
        card.opened.emit(card.index)
        settle()
        reader = w.section_readers["duas"]
        self.assertIs(reader, w.corner_screen.currentWidget(), "the du'a did not open")
        reader.back_button.click()
        settle()
        self.assertIs(board, w.corner_screen.currentWidget(), "Back did not return to the board")
        self.assertEqual(was, [i for i, _ in board.showing], "the du'as changed on their own")
        self.assertEqual(was, [c.index for c in board.cards], "the cards and the pick disagree")


class PlayMarkTest(unittest.TestCase):
    """One mark means play, wherever it is."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=True, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_it_is_a_ring_with_a_mark_inside_and_not_a_filled_blob(self):
        from salaah.ui import play_icon
        shot = play_icon(120, "#ffffff").toImage()
        def lit(x, y):
            c = shot.pixelColor(x, y)
            return c.alpha() > 40 and c.red() > 120
        self.assertTrue(lit(60, 4) or lit(60, 6), "no ring at the top")
        self.assertFalse(lit(20, 20), "the corner is filled in -- this is a blob, not a ring")
        self.assertTrue(lit(56, 60), "nothing inside the ring")
        # the gap between ring and triangle: a filled circle would have no dark band here
        self.assertFalse(lit(26, 60), "the ring and the mark have run together")

    def test_the_stop_mark_is_a_different_shape_from_the_play_mark(self):
        from salaah.ui import play_icon
        go = play_icon(120, "#ffffff").toImage()
        stop = play_icon(120, "#ffffff", stop=True).toImage()
        def ink(image):
            return sum(1 for y in range(0, 120, 2) for x in range(0, 120, 2)
                       if image.pixelColor(x, y).alpha() > 40)
        self.assertNotEqual(ink(go), ink(stop), "play and stop draw the same thing")
        # the play triangle has a sloped edge, so its bottom-left corner is empty and the
        # square's is not
        self.assertNotEqual(go.pixelColor(46, 78).alpha() > 40,
                            stop.pixelColor(46, 78).alpha() > 40)

    def test_the_quran_recite_button_is_the_drawn_mark_not_a_blue_rectangle(self):
        w = self.window()
        w.open_surah(1)
        settle()
        button = w.reader.recite_button
        self.assertFalse(button.icon().isNull(), "the recite button has no mark on it")
        self.assertEqual("", button.text(), "the recite button still spells something out")
        shot = button.grab().toImage()
        # It used to be a solid lapis slab with a glyph on it. Two things settle that it is not:
        # the button's background is the page's, not a colour of its own, and there is a mark
        # drawn on it. Counting distinct colours does not settle either -- a white ring on a
        # black page is two colours, and so is a blue slab.
        page = w.palette().color(w.backgroundRole())
        lapis = QtGui.QColor(w.colours().lapis)
        blue = ink = total = 0
        for y in range(0, shot.height(), 2):
            for x in range(0, shot.width(), 2):
                c = shot.pixelColor(x, y)
                total += 1
                if abs(c.red() - lapis.red()) < 40 and abs(c.blue() - lapis.blue()) < 40 \
                        and c.blue() > c.red() + 30:
                    blue += 1
                if abs(c.red() - page.red()) > 60:
                    ink += 1
        self.assertLess(blue / total, 0.05, "the button is still a blue slab")
        self.assertGreater(ink / total, 0.02, "nothing is drawn on the button")
        self.assertLess(ink / total, 0.6, "the button is filled in rather than marked")

    def test_the_recite_mark_is_twice_the_size_it_was(self):
        """It was 0.62 of a button the height of Back. The button is now square and twice
        Back's height, so the mark inside it doubles -- measured against Back, which has not
        changed, rather than against a number written in here."""
        w = self.window()
        w.open_surah(1)
        settle()
        button, back = w.reader.recite_button, w.reader.back_button
        self.assertEqual(back.height() * 2, button.height(), "the button did not double")
        self.assertEqual(button.height(), button.width(), "the button is not square")
        was = int(back.height() * 0.62)          # what the mark used to be
        self.assertGreaterEqual(button.iconSize().height(), was * 2 - 2,
                                f"the mark is {button.iconSize().height()}px, was {was}px")
        self.assertLessEqual(button.iconSize().height(), button.height(),
                             "the mark is bigger than the button and would be cropped")

    def test_the_mark_turns_to_stop_and_back(self):
        """Driven through the flag rather than by starting the audio. Playing a recitation for
        real needs a player, which is not always there in a test run -- this failed once in a
        full run and passed on its own, and a test that only sometimes looks is no test."""
        w = self.window()
        w.open_surah(1)
        settle()
        reader = w.reader
        before = reader.recite_button.icon().pixmap(40, 40).toImage()
        reader.reciting_now = True
        reader.draw_recite_mark()
        during = reader.recite_button.icon().pixmap(40, 40).toImage()
        self.assertNotEqual(before, during, "the mark did not change")
        reader.reciting_now = False
        reader.draw_recite_mark()
        self.assertEqual(before, reader.recite_button.icon().pixmap(40, 40).toImage())

    def test_starting_and_stopping_are_what_set_that_flag(self):
        """The half the test above does not cover: that reciting actually flips the flag the
        mark is drawn from. Checked without a player, which start_reciting copes with."""
        w = self.window()
        w.open_surah(1)
        settle()
        reader = w.reader
        self.assertFalse(reader.reciting_now)
        reader.start_reciting()
        settle()
        # `reciting` is the flag that says it really began -- `saying` is the label in the bar
        # and is always truthy, which is how the first version of this test managed to pass
        # and fail on the same code.
        if reader.reciting:                    # no recitation audio here: nothing to check
            self.assertTrue(reader.reciting_now, "reciting did not change the mark")
        reader.stop_reciting()
        settle()
        self.assertFalse(reader.reciting_now, "the mark was left on stop")


class EmptyKindScreenTest(unittest.TestCase):
    """The screen a kind with nothing behind it lands on."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def empty(self, w, cat="travel"):
        listing = w.section_lists["duas"]
        kept = list(listing.passages.items)
        listing.passages._items = [d for d in kept if cat not in d.cats]
        w.dua_board.filled = None
        self.addCleanup(lambda: setattr(listing.passages, "_items", kept))
        w.open_corner("duas")
        settle()
        w.open_dua_category(cat)
        settle()
        return w

    def test_the_name_is_on_a_white_plate_with_black_letters(self):
        w = self.empty(w=self.window())
        plate = w.soon_title
        self.assertTrue(plate.isVisible())
        shot = plate.grab().toImage()
        white = black = 0
        for y in range(0, shot.height(), 2):
            for x in range(0, shot.width(), 2):
                c = shot.pixelColor(x, y)
                if c.red() > 230 and c.green() > 230 and c.blue() > 230:
                    white += 1
                elif c.red() < 60 and c.green() < 60 and c.blue() < 60:
                    black += 1
        self.assertGreater(white, black, "the plate is not mostly white")
        self.assertGreater(black, 20, "there are no black letters on it")

    def test_the_plate_sits_top_left(self):
        """It was centred across the top until Harry asked for it on the left, like the world
        screen's. A heading centred over an empty page has nothing to be centred on."""
        w = self.empty(w=self.window())
        plate, page = w.soon_title, w.corner_soon
        middle = plate.mapTo(page, plate.rect().center())
        left = plate.mapTo(page, QtCore.QPoint(0, 0)).x()
        self.assertLess(left, page.width() * 0.1, "the name is not against the left")
        self.assertLess(middle.x(), page.width() * 0.45, "the name is still in the middle")
        self.assertLess(middle.y(), page.height() * 0.25, "the name is not near the top")

    def test_the_button_says_back_and_returns_to_the_kinds(self):
        w = self.empty(w=self.window())
        button = w.soon_back_button
        self.assertEqual(w.t("corner.back"), button.text())
        self.assertNotIn(w.t("settings.main_screen"), button.text())
        button.click()
        settle()
        self.assertIs(w.dua_menu, w.corner_screen.currentWidget())

    def test_the_button_is_in_the_bottom_right(self):
        w = self.empty(w=self.window())
        button, page = w.soon_back_button, w.corner_soon
        at = button.mapTo(page, button.rect().center())
        self.assertGreater(at.x(), page.width() * 0.7, "not on the right")
        self.assertGreater(at.y(), page.height() * 0.7, "not at the bottom")


class WifiScreenTest(unittest.TestCase):
    """The Wi-Fi screen, driven against a fake nmcli. No radio is involved."""

    SCAN = ("NOVA_26DU_A2:95:WPA2\nNOVA_26DU_A2:77:WPA2\nBT-HUB-9K2:64:WPA2\n"
            "Free Library Wifi:38:\n")
    SAVED = "NOVA_26DU_A2:802-11-wireless\nlo:loopback\n"

    def window(self, online=True, join=(0, "ok", "")):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        self.asked = []

        def runner(args, timeout=None):
            self.asked.append(list(args))
            if "list" in args:
                return 0, self.SCAN, ""
            if "--active" in args:
                return 0, "NOVA_26DU_A2:802-11-wireless:wlan0\n", ""
            if any("NAME,TYPE" in a for a in args):
                return 0, self.SAVED, ""
            if "connect" in args:
                return join
            return 0, "", ""

        from salaah.network import Wifi
        w.open_wifi()
        settle()
        w.wifi_screen.wifi = Wifi(runner=runner, resolver=lambda n=None: online)
        return w

    def scanned(self, w):
        screen = w.wifi_screen
        screen.look()
        settle()
        if screen.errand is not None:
            screen.errand.wait(5000)
        settle()
        return screen

    def test_the_wifi_row_in_settings_opens_it_without_leaving_the_app(self):
        w = self.window()
        w.open_settings()
        settle()
        self.assertTrue(w.wifi_button.isVisible(), "no way to Wi-Fi from Settings")
        w.wifi_button.click()
        settle()
        self.assertIs(w.wifi_page, w.stack.currentWidget())

    def test_it_wears_the_same_strip_as_every_other_screen(self):
        """A screen without it reads as having left the app, which is the one thing it must
        never do."""
        w = self.window()
        strips = [x for x in w.wifi_page.findChildren(QtWidgets.QWidget)
                  if x.objectName() == "banner"]
        self.assertTrue(strips, "the Wi-Fi screen has no strip")
        home = [b for b in w.wifi_page.findChildren(QtWidgets.QPushButton)
                if b.objectName() == "mainScreen"]
        self.assertTrue(home, "no way back to the mat from the Wi-Fi screen")

    def test_one_row_per_network_however_many_times_it_is_seen(self):
        w = self.window()
        screen = self.scanned(w)
        names = [r.network.name for r in screen.network_rows()]
        self.assertEqual(["NOVA_26DU_A2", "BT-HUB-9K2", "Free Library Wifi"], names)

    def test_a_saved_secured_network_joins_without_asking_for_a_password(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[0].click()          # NOVA: secured but already saved
        settle()
        self.assertEqual(0, screen.pages.currentIndex(),
                         "it asked for a password it already has")

    def test_an_open_network_joins_without_asking_either(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[2].click()          # Free Library Wifi: no password
        settle()
        self.assertEqual(0, screen.pages.currentIndex())

    def test_a_new_secured_network_asks_for_one(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[1].click()          # BT-HUB: secured, never seen
        settle()
        self.assertEqual(1, screen.pages.currentIndex())
        self.assertIn("BT-HUB-9K2", screen.asking.text())

    def test_the_password_is_hidden_until_show_is_pressed(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        for ch in "Pa55":
            screen.add(ch)
        settle()
        self.assertNotIn("Pa55", screen.field.text(), "the password is on screen in the clear")
        self.assertEqual(4, len(screen.field.text()))
        screen.reveal.setChecked(True)
        settle()
        self.assertEqual("Pa55", screen.field.text(),
                         "Show password must really show it -- on a touchscreen there is no "
                         "other way to tell a key missed")

    def test_backspace_takes_one_character_off(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        for ch in "abc":
            screen.add(ch)
        screen.rub()
        screen.reveal.setChecked(True)
        settle()
        self.assertEqual("ab", screen.field.text())

    def test_shift_gives_one_capital_and_then_lets_go(self):
        """A shift that stays on is how a whole password ends up in capitals unnoticed."""
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        keys = screen.keys
        keys.flip_shift()
        self.assertIn("Q", keys.letters_on_show())
        keys.press("Q")
        settle()
        self.assertIn("q", keys.letters_on_show(), "shift stayed on")
        keys.press("b")
        screen.reveal.setChecked(True)
        settle()
        self.assertEqual("Qb", screen.field.text())

    def test_the_numbers_layer_has_digits_and_comes_back_to_letters(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        keys = screen.keys
        keys.next_layer()
        self.assertIn("1", keys.letters_on_show())
        keys.next_layer()
        keys.next_layer()
        self.assertIn("q", keys.letters_on_show(), "it never got back to the letters")

    def test_joining_with_no_internet_is_not_called_a_success(self):
        """The evening that prompted all this: associated to the wifi, unable to reach a thing."""
        w = self.window(online=False)
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        screen.go()
        settle()
        if screen.errand is not None:
            screen.errand.wait(5000)
        settle()
        self.assertIn(w.t("why.no_internet"), screen.trouble.text() + screen.saying.text())

    def test_a_wrong_password_says_so_rather_than_could_not_connect(self):
        w = self.window(join=(4, "", "Error: Secrets were required, but not provided"))
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        screen.go()
        settle()
        if screen.errand is not None:
            screen.errand.wait(5000)
        settle()
        said = screen.trouble.text() + screen.saying.text()
        self.assertIn(w.t("why.password"), said)
        self.assertNotIn(w.t("why.unknown"), said)

    def test_the_password_is_dropped_the_moment_it_has_been_used(self):
        w = self.window()
        screen = self.scanned(w)
        screen.network_rows()[1].click()
        settle()
        for ch in "hunter2":
            screen.add(ch)
        screen.go()
        settle()
        if screen.errand is not None:
            screen.errand.wait(5000)
        settle()
        self.assertEqual("", screen.typed, "the password is still held after joining")
        screen.reveal.setChecked(True)
        settle()
        self.assertNotIn("hunter2", screen.field.text())

    def test_searching_again_does_not_bring_the_mat_down(self):
        """The worker used to delete itself while the screen still pointed at it, and the
        second press died on a deleted C++ object -- which on the mat is the app going."""
        w = self.window()
        for _ in range(3):
            screen = self.scanned(w)
        self.assertEqual(3, len(screen.network_rows()))

    def test_it_is_left_alone_while_a_prayer_is_going_on(self):
        w = self.window()
        w.go_home()
        settle()
        was = w.stack.currentWidget()
        with mock.patch.object(type(w), "playing", property(lambda _s: True)):
            w.open_wifi()
            settle()
            self.assertIs(was, w.stack.currentWidget(), "a stray knee opened Wi-Fi mid-prayer")


class PlaceScreenTest(unittest.TestCase):
    """Telling the mat where it is. The failure this stops is a mat confidently showing the
    wrong town's times with nothing on screen to suggest it."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury",
                                latitude=53.5933, longitude=-2.2966),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def typed(self, screen, text):
        for ch in text:
            screen.add(ch)
        settle()

    def test_the_location_row_in_settings_opens_it(self):
        w = self.window()
        w.open_settings()
        settle()
        self.assertTrue(w.place_button.isVisible(), "no way to set the location from Settings")
        w.place_button.click()
        settle()
        self.assertIs(w.place_page, w.stack.currentWidget())

    def test_it_wears_the_same_strip_as_every_other_screen(self):
        w = self.window()
        w.open_place()
        settle()
        strips = [x for x in w.place_page.findChildren(QtWidgets.QWidget)
                  if x.objectName() == "banner"]
        self.assertTrue(strips, "the place screen has no strip")

    def test_typing_a_postcode_shows_what_it_would_mean_before_saving(self):
        """Showing the times first is the point: a typo is caught by the times looking wrong,
        not a fortnight later."""
        w = self.window()
        w.open_place()
        settle()
        screen = w.place_screen
        self.typed(screen, "cf10")
        self.assertEqual("CF10", screen.field.text(), "postcodes are written in capitals")
        self.assertIsNotNone(screen.found)
        for prayer in ("fajr", "dhuhr", "maghrib"):
            self.assertIn(w.t(f"prayer.{prayer}"), screen.preview.text())
        self.assertEqual("Bury", w.settings.place, "it saved before being asked to")

    def test_saving_really_moves_the_prayer_times_and_the_strip(self):
        w = self.window()
        before = dict(w.prayer_times())
        w.open_place()
        settle()
        self.typed(w.place_screen, "cf10")
        w.place_screen.keep()
        settle()
        w.tick()
        settle()
        self.assertEqual("CF10", w.settings.place)
        self.assertAlmostEqual(51.47, w.settings.latitude, places=1)
        after = dict(w.prayer_times())
        moved = max(abs((before[p].hour * 60 + before[p].minute)
                        - (after[p].hour * 60 + after[p].minute))
                    for p in before if before[p] and after[p])
        self.assertGreater(moved, 4, "the times did not follow the mat to Cardiff")
        said = " ".join(x.text() for x in w.home.findChildren(QtWidgets.QLabel) if x.text())
        self.assertIn("CF10", said, "the strip still names the old place")

    def test_the_times_cache_does_not_serve_the_old_towns_times(self):
        """The cache is keyed on the coordinates, so it should invalidate itself -- but a cache
        that decides for itself when it is stale is exactly what would show Bury's times in
        Cardiff for the rest of the day."""
        w = self.window()
        w.prayer_times()
        w.open_place()
        settle()
        self.typed(w.place_screen, "cf10")
        w.place_screen.keep()
        settle()
        fresh = w.prayer_times()
        straight = __import__("salaah.prayer_times", fromlist=["times_for"])
        from salaah.prayer_times import Place, times_for
        from datetime import datetime
        want = times_for(datetime.now().date(),
                         Place(w.settings.latitude, w.settings.longitude, "CF10"),
                         w.school.id, high_latitude=w.settings.high_latitude)
        self.assertEqual(want["fajr"], fresh["fajr"], "a stale time was served")

    def test_a_postcode_it_does_not_know_is_refused_and_cannot_be_saved(self):
        w = self.window()
        w.open_place()
        settle()
        screen = w.place_screen
        self.typed(screen, "zz99")
        self.assertIsNone(screen.found)
        self.assertFalse(screen.save.isEnabled(), "it would have saved a place it cannot find")
        self.assertEqual("", screen.preview.text())
        screen.keep()
        settle()
        self.assertEqual("Bury", w.settings.place, "it moved the mat somewhere unknown")

    def test_nothing_typed_yet_offers_nothing_to_save(self):
        w = self.window()
        w.open_place()
        settle()
        self.assertFalse(w.place_screen.save.isEnabled())

    def test_a_full_postcode_is_understood_not_refused(self):
        """People type their postcode the way they write it."""
        w = self.window()
        w.open_place()
        settle()
        screen = w.place_screen
        self.typed(screen, "bl9 0ab")
        self.assertIsNotNone(screen.found, "a whole postcode was refused")
        self.assertEqual("BL9", screen.found.outward)

    def test_backspace_works_and_takes_the_answer_with_it(self):
        w = self.window()
        w.open_place()
        settle()
        screen = w.place_screen
        # BL9 backspaces to "BL", which is not a postcode. CF10 would backspace to CF1, which
        # IS one -- a real Cardiff district that is in the table -- so using that here tested
        # nothing and failed for being right.
        self.typed(screen, "bl9")
        self.assertIsNotNone(screen.found)
        screen.rub()
        settle()
        self.assertEqual("BL", screen.field.text())
        self.assertIsNone(screen.found, "it still offers the answer for a postcode now changed")
        self.assertFalse(screen.save.isEnabled())

    def test_it_is_left_alone_while_a_prayer_is_going_on(self):
        w = self.window()
        w.go_home()
        settle()
        was = w.stack.currentWidget()
        with mock.patch.object(type(w), "playing", property(lambda _s: True)):
            w.open_place()
            settle()
            self.assertIs(was, w.stack.currentWidget())

    def test_the_keyboard_fills_the_screen_it_is_given(self):
        """A touchscreen keyboard huddled in the middle of a 1920 screen is a keyboard you miss.
        Measured off the drawn keys, not off the layout's intentions."""
        w = self.window()
        w.open_place()
        settle()
        keys = w.place_screen.keys
        drawn = [k for k in keys.keys if k.isVisible()]
        self.assertTrue(drawn)
        widest = max(k.width() for k in drawn)
        self.assertGreater(widest, w.px(140), f"the keys are only {widest}px wide")
        self.assertGreater(max(k.height() for k in drawn), w.px(120))
        left = min(k.mapTo(keys, k.rect().topLeft()).x() for k in drawn)
        right = max(k.mapTo(keys, k.rect().topRight()).x() for k in drawn)
        self.assertGreater(right - left, keys.width() * 0.92,
                           "the keyboard is not using the width it has")

    def test_every_row_of_keys_is_the_same_size(self):
        """They are laid out in units so a key is a key wherever it is. Rows that size
        themselves independently give a keyboard that looks broken and reads worse."""
        w = self.window()
        w.open_place()
        settle()
        drawn = [k for k in w.place_screen.keys.keys if k.isVisible()]
        widths = {k.width() for k in drawn}
        self.assertLessEqual(max(widths) - min(widths), 4,
                             f"key widths range over {sorted(widths)}")


class WifiCircleTest(unittest.TestCase):
    """The circle beside the Wi-Fi row in Settings.

    It was drawn and then never told anything, so it sat red on a mat that was online. Harry
    spotted it on his: "the wifi circle is red even though it is connected". A circle that is
    always red is worse than no circle, because it is an answer rather than a blank.
    """

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def radio(self, w, card=True, joined="NOVA_26DU_A2", reaches=True):
        """A mat whose wifi says what we tell it to, with no radio in sight."""
        from salaah.network import Wifi

        def runner(args, timeout=None):
            if "status" in args:
                return (0, "wifi\nethernet\n" if card else "ethernet\n", "")
            if "--active" in args:
                return 0, (f"{joined}:802-11-wireless:wlan0\n" if joined else ""), ""
            return 0, "", ""

        w.wifi = Wifi(runner=runner, resolver=lambda n=None: reaches)
        return w

    def settled(self, w):
        w.open_settings()
        settle()
        if getattr(w, "wifi_errand", None) is not None:
            w.wifi_errand.wait(5000)
        settle()
        return w.wifi_dot.color.name().upper()

    def test_green_when_it_is_on_a_network_and_can_reach_the_world(self):
        from salaah.ui import MINT
        w = self.radio(self.window())
        self.assertEqual(MINT, self.settled(w), "green when connected")
        self.assertIn("NOVA_26DU_A2", w.wifi_dot.toolTip())

    def test_red_when_it_is_on_no_network(self):
        from salaah.ui import BRICK
        w = self.radio(self.window(), joined="")
        self.assertEqual(BRICK, self.settled(w), "red when not connected")

    def test_red_when_the_mat_has_no_wifi_at_all(self):
        from salaah.ui import BRICK
        w = self.radio(self.window(), card=False)
        self.assertEqual(BRICK, self.settled(w))

    def test_amber_when_it_has_joined_a_network_that_reaches_nothing(self):
        """The evening the mat spent associated to the router and unable to fetch a thing.
        Green would have said everything was fine."""
        from salaah.ui import AMBER
        w = self.radio(self.window(), reaches=False)
        self.assertEqual(AMBER, self.settled(w))

    def test_a_mat_with_no_wifi_is_never_asked_what_it_is_joined_to(self):
        """nmcli is slow enough that the order matters: each question is only asked when the
        one before it makes it worth asking."""
        from salaah.network import Wifi
        asked = []

        def runner(args, timeout=None):
            asked.append(list(args))
            return 0, "ethernet\n", ""

        w = self.window()
        w.wifi = Wifi(runner=runner, resolver=lambda n=None: self.fail("looked a name up"))
        self.settled(w)
        self.assertEqual(1, len(asked), f"asked more than it needed: {asked}")

    def test_opening_settings_twice_quickly_starts_one_errand(self):
        w = self.radio(self.window())
        w.open_settings()
        first = w.wifi_errand
        w.open_settings()
        self.assertIs(first, w.wifi_errand, "a second errand was started over the first")
        if first is not None:
            first.wait(5000)
        settle()

    def test_the_circle_is_asked_again_on_the_way_back_from_the_wifi_screen(self):
        """Joining a network and coming back should not leave the old answer on screen."""
        from salaah.ui import BRICK, MINT
        w = self.radio(self.window(), joined="")
        self.assertEqual(BRICK, self.settled(w))
        w.open_wifi()
        settle()
        self.radio(w, joined="NOVA_26DU_A2")          # as if it had just been joined
        w.wifi_screen.leave.click()
        settle()
        if getattr(w, "wifi_errand", None) is not None:
            w.wifi_errand.wait(5000)
        settle()
        self.assertEqual(MINT, w.wifi_dot.color.name().upper(), "the circle kept a stale answer")


class CalledWordsTest(unittest.TestCase):
    """How large the call is written.

    It was coming out at eighteen pixels on a 1024x600 screen -- fine at arm's length, and the
    call is heard from wherever you happen to be standing. The size is not set anywhere: each
    line is drawn as large as its row is tall, so the words got bigger by the rows getting
    taller. Which is exactly why this is measured rather than read off a constant.
    """

    def box(self, wide, tall, prayer="fajr", recording="azaan-fajr.mp3"):
        from salaah.call import CallBox
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(wide, tall)
        w.show()
        settle()
        self.addCleanup(lambda: shut(w))
        b = CallBox(w, prayer, recording, w.adhan)
        b.show()
        settle()
        self.addCleanup(lambda: (b.close(), b.deleteLater(), settle()))
        return b

    def test_the_words_are_worth_reading_from_across_a_room(self):
        for wide, tall, floor in ((1024, 600, 24), (1280, 720, 28), (1920, 1080, 40)):
            with self.subTest(f"{wide}x{tall}"):
                b = self.box(wide, tall)
                sizes = [x.fitted_size() for x in b.boxes.values()]
                self.assertGreaterEqual(min(sizes), floor,
                                        f"the call is drawn at {min(sizes)}px on {wide}x{tall}")

    def test_fajr_has_the_most_lines_and_they_all_get_the_same_room(self):
        """Fajr carries "prayer is better than sleep" and so runs to seven lines against six.
        Nothing ever hangs out of the box -- Qt shrinks the rows instead, which is the failure
        worth looking for: one line squeezed while the rest are comfortable."""
        for wide, tall in ((1024, 600), (1280, 720), (1920, 1080)):
            with self.subTest(f"{wide}x{tall}"):
                b = self.box(wide, tall)
                self.assertEqual(7, len(b.boxes), "Fajr should have seven lines")
                heights = [x.height() for x in b.boxes.values()]
                self.assertGreater(min(heights) / max(heights), 0.9,
                                   f"the rows are uneven: {heights}")

    def test_each_meaning_sits_under_its_own_line(self):
        """The English is nearer the Arabic it translates than the Arabic below it. It used to
        sit midway between the two, which on seven lines reads as a list of fourteen things."""
        b = self.box(1920, 1080)
        keys = list(b.boxes)
        meanings = [x for x in b.findChildren(QtWidgets.QLabel)
                    if x.objectName() == "callMeaning"]
        self.assertEqual(len(keys), len(meanings))
        for i in range(len(keys) - 1):
            # The label's own margin is where the gap lives, so it is the text's box that is
            # measured from, not the widget's.
            text = meanings[i].contentsRect().translated(meanings[i].pos())
            above = text.top() - b.boxes[keys[i]].geometry().bottom()
            below = b.boxes[keys[i + 1]].y() - text.bottom()
            self.assertLess(above, below,
                            f"{keys[i]}: {above}px under its line, {below}px above the next")

    def test_it_fills_a_small_screen_too(self):
        """The second place that said the call must leave the mat showing round the edge, and
        it meant it: bigger words were not thought worth the box becoming the whole screen.
        Harry has decided the other way, so the only thing left to check here is that a small
        screen gets the same treatment as the mat's own -- the sizing is a fraction of the
        parent, and a fraction is the kind of thing that works at one size and not another."""
        b = self.box(1024, 600)
        self.assertEqual(1024, b.width())
        self.assertEqual(600, b.height())


class WorldScreenTest(unittest.TestCase):
    """The world tile: the earth turning, with the mat's own place on it and a line to the
    Kaaba. The maths is tested in test_core; this is about what actually gets drawn."""

    def window(self, theme="dark", place="Bury", where=(53.593, -2.298), size=(1024, 600)):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=theme, place=place, latitude=where[0], longitude=where[1]),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(*size)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def blue(self, widget):
        """Where the line and the marker are: the globe is black and white, so anything blue
        was drawn by us."""
        shot = widget.grab().toImage()
        found = []
        for y in range(0, shot.height(), 2):
            for x in range(0, shot.width(), 2):
                c = shot.pixelColor(x, y)
                if c.blue() > c.red() + 40 and c.blue() > 80:
                    found.append((x, y))
        return found

    def test_the_world_tile_opens_the_globe(self):
        w = self.window()
        w.open_corner("world")
        settle()
        self.assertIs(w.world_page, w.corner_screen.currentWidget(),
                      "the world tile still lands on the empty screen")
        self.assertIs(w.corner_page, w.stack.currentWidget())

    def test_there_are_no_words_under_the_globe(self):
        """There was a line saying "Bury to Makkah, about 5,030 km" and Harry asked for it to
        go. It was a fact rather than something to look at, sat across the bottom of a screen
        whose whole job is the picture above it."""
        w = self.window()
        w.open_corner("world")
        settle()
        said = " ".join(x.text() for x in w.world_page.findChildren(QtWidgets.QLabel)
                        if x.isVisible() and x.text())
        for gone in ("Makkah", "km", "5,030"):
            self.assertNotIn(gone, said, f"{gone!r} is still under the globe: {said!r}")

    def test_the_mat_still_knows_how_far_it_is(self):
        """The words went; the arithmetic did not, and the line on the globe is drawn from it.
        Measured here so that losing the caption cannot quietly lose the thing behind it."""
        from salaah.globe import KAABA, apart
        bury = apart((53.593, -2.298), KAABA)
        cape = apart((-33.9249, 18.4241), KAABA)
        self.assertEqual(5030, round(bury, -1))
        self.assertEqual(6560, round(cape, -1))

    def test_the_line_is_drawn_and_it_reaches_the_kaaba(self):
        """Blue on the screen, running from the mat's place to where Mecca is projected. The
        Kaaba end is the marker the animator drew, so the line landing on it is the whole
        calibration showing its work."""
        from salaah.globe import KAABA
        w = self.window()
        w.open_corner("world")
        settle()
        world = w.world_screen.world
        left, top, side = world.circle()
        drawn = world.film.currentPixmap().scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio)
        at = world.film.currentFrameNumber()
        spots = self.blue(world)
        self.assertGreater(len(spots), 40, "nothing blue was drawn on the globe")
        mecca = w.world_screen.globe.at(at, *KAABA)
        target = (left + mecca.x * drawn.width(), top + mecca.y * drawn.width())
        near = min((abs(x - target[0]) + abs(y - target[1])) for x, y in spots)
        self.assertLess(near, side * 0.06,
                        f"the line stops {near:.0f}px short of the Kaaba on a {side}px globe")

    def test_the_marker_moves_when_the_mat_does(self):
        here = self.window(place="Bury", where=(53.593, -2.298))
        here.open_corner("world")
        settle()
        one = self.blue(here.world_screen.world)
        there = self.window(place="Cairo", where=(30.0444, 31.2357))
        there.open_corner("world")
        settle()
        two = self.blue(there.world_screen.world)
        self.assertTrue(one and two)
        # The topmost blue is the home end of the line in both cases, and Bury is a long way
        # north of Cairo.
        self.assertLess(min(y for _, y in one), min(y for _, y in two) - 20,
                        "the mat is drawn in the same place wherever it is")

    def test_the_film_is_stopped_when_the_screen_is_left(self):
        """Ten repaints a second for a screen nobody is looking at is the Pi woken for nothing,
        and on the call box it was worse than that -- it was a crash."""
        w = self.window()
        w.open_corner("world")
        settle()
        self.assertEqual(QtGui.QMovie.MovieState.Running, w.world_screen.world.film.state())
        w.go_home()
        settle()
        self.assertNotEqual(QtGui.QMovie.MovieState.Running, w.world_screen.world.film.state(),
                            "the globe is still turning off screen")

    def test_the_globe_leaves_nothing_behind_when_the_window_goes(self):
        """A window that has shown the globe must take all of it with it. The suite was killed
        for running out of memory once already, by a screen that was a top-level window without
        meaning to be, and this one holds a seventy-two frame film."""
        # Counted in two passes rather than measured against a baseline. A plain count would be
        # satisfied by whatever earlier tests have left lying about, and comparing the objects
        # themselves does not work either: PySide6 hands out a fresh Python wrapper for a widget
        # whose old one has been collected, so the same window looks like a new one. What a leak
        # does is grow, so growth is what this looks for -- the same work twice, and the second
        # time must add nothing the first did not.
        def pass_of(n):
            for _ in range(n):
                w = MainWindow(load(ASSETS), available_packs(ASSETS),
                               Settings(theme="dark", place="Bury"),
                               scale=1.0, save_settings=False, aspect=None, side=True)
                w.resize(1024, 600)
                w.show()
                w.side.resize(600, 1024)
                w.side.show()
                w.tick()
                w.open_corner("world")
                settle()
                shut(w)
            settle()
            return len(QtWidgets.QApplication.topLevelWidgets())

        first = pass_of(3)
        second = pass_of(3)
        self.assertLessEqual(second, first,
                             f"windows pile up as the globe is opened: {first} then {second}")

        # And the plain statement of what must be true, which the counting is only evidence for:
        # everything the world screen makes belongs to the page it was put on, so that closing
        # the window closes all of it.
        w = self.window()
        w.open_corner("world")
        settle()
        floating = []
        for name in dir(w.world_screen):
            if name.startswith("__"):
                continue
            thing = getattr(w.world_screen, name, None)
            if isinstance(thing, QtWidgets.QWidget) and thing.window() is not w:
                floating.append(f"{name} ({type(thing).__name__})")
        if isinstance(w.world_screen, QtWidgets.QWidget) and w.world_screen.window() is not w:
            floating.append(f"the screen itself ({type(w.world_screen).__name__})")
        self.assertEqual([], floating, f"not part of the window: {floating}")

    def test_it_is_drawn_the_right_way_round_for_the_screen_it_is_on(self):
        """The globe is drawn black on white like every other picture here, and turned inside
        out for the dark screen. A white disc on a black screen at Fajr would be no good."""
        inside = {}
        for theme in ("dark", "light"):
            w = self.window(theme=theme)
            w.open_corner("world")
            settle()
            world = w.world_screen.world
            shot = world.grab().toImage()
            left, top, side = world.circle()
            middle, spread = side / 2, side * 0.32
            inside[theme] = [shot.pixelColor(int(left + middle + dx),
                                             int(top + middle + dy)).red()
                             for dx in range(-int(spread), int(spread), 7)
                             for dy in range(-int(spread), int(spread), 7)]
        dark, light = inside["dark"], inside["light"]
        self.assertEqual(len(dark), len(light))
        # Point for point, one is the other turned inside out. Allowing a few to disagree: the
        # line drawn over the top is a different blue on the two screens.
        odd = sum(1 for a, b in zip(dark, light) if abs(a + b - 255) > 30)
        self.assertLess(odd, len(dark) * 0.08,
                        f"{odd} of {len(dark)} points are not inverses of each other")
        # And it is a picture of the world on both, not a grey wash on either.
        for theme, seen in inside.items():
            black = sum(1 for v in seen if v < 60) / len(seen)
            white = sum(1 for v in seen if v > 195) / len(seen)
            self.assertGreater(black, 0.2, f"{theme}: hardly anything is dark")
            self.assertGreater(white, 0.2, f"{theme}: hardly anything is light")


class CommunityColumnTest(unittest.TestCase):
    """The column beside the globe: how many mats are on, and which of them can be seen.

    The service that would tell a mat about any other does not exist yet, on purpose -- it is a
    decision about children's home locations before it is a piece of code. So the count is one.
    What is tested here is the shape it will arrive into, because a seam that has never had
    anything put through it is not a seam.
    """

    def window(self, theme="dark", place="Bury", where=(53.593, -2.298), size=(1024, 600)):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=theme, place=place, latitude=where[0], longitude=where[1]),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(*size)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    FOUR = ((53.593, -2.298, "Bury", True), (-33.8688, 151.2093, "Sydney", False),
            (30.0444, 31.2357, "Cairo", False), (31.5204, 74.3587, "Lahore", False))

    def pretend(self, w, rows=FOUR):
        """Put a community in the list the screen draws from, as the service would."""
        from salaah.worldscreen import Mat
        mats = [Mat(lat, lon, name, mine=mine) for lat, lon, name, mine in rows]
        w.world_screen.mats = lambda: mats
        return mats

    def opened(self, w):
        w.open_corner("world")
        settle()
        return w.world_screen

    def wind_to(self, screen, frame):
        """QMovie will only seek forward a frame at a time, so the film is walked there."""
        screen.world.film.stop()
        while screen.world.film.currentFrameNumber() % 72 != frame:
            screen.world.film.jumpToNextFrame()
        settle()
        screen.relight()
        screen.world.repaint()
        settle()

    def blue(self, widget):
        shot = widget.grab().toImage()
        found = []
        for y in range(0, shot.height(), 2):
            for x in range(0, shot.width(), 2):
                c = shot.pixelColor(x, y)
                if c.blue() > c.red() + 40 and c.blue() > 80:
                    found.append((x, y))
        return found

    # -- the header ---------------------------------------------------------------------------

    def test_the_header_is_the_name_of_the_thing(self):
        w = self.window()
        self.opened(w)
        self.assertEqual("MySalaah Community", w.world_title.text())

    def test_it_is_the_name_in_every_language(self):
        """A brand is not translated. Every pack carries it as it is written."""
        for lang in full_packs(available_packs(ASSETS)):
            with self.subTest(lang):
                w = MainWindow(load(ASSETS), available_packs(ASSETS),
                               Settings(theme="dark", place="Bury", lang=lang),
                               scale=1.0, save_settings=False, aspect=None, side=True)
                w.resize(1024, 600)
                w.show()
                w.tick()
                settle()
                self.addCleanup(lambda x=w: shut(x))
                w.open_corner("world")
                settle()
                self.assertEqual("MySalaah Community", w.world_title.text())

    # -- the count ---------------------------------------------------------------------------

    def test_one_mat_on_its_own_counts_one(self):
        w = self.window()
        screen = self.opened(w)
        self.assertEqual("Active", screen.heading.text())
        self.assertEqual("1", screen.count.text())

    def test_the_count_follows_the_list(self):
        w = self.window()
        self.pretend(w)
        screen = self.opened(w)
        self.assertEqual("4", screen.count.text())

    def test_a_thousand_mats_are_written_as_a_thousand(self):
        """Not 1000. The number is the thing a child reads off the screen."""
        w = self.window()
        self.pretend(w, tuple((10 + i % 60, (i * 7) % 300 - 150, "", i == 0)
                              for i in range(1000)))
        screen = self.opened(w)
        self.assertEqual("1,000", screen.count.text())

    # -- what is drawn ------------------------------------------------------------------------

    def test_a_line_is_drawn_for_every_mat_that_can_be_seen(self):
        """Four mats at a frame where all four are on the near side: four routes to the Kaaba,
        four markers. Counted as separate runs of blue rather than by area, so that a single
        fatter line cannot pass for four."""
        from salaah.globe import KAABA
        w = self.window()
        mats = self.pretend(w)
        screen = self.opened(w)
        self.wind_to(screen, 19)
        seen = [m for m in mats if screen.globe.at(19, m.latitude, m.longitude).seen]
        self.assertEqual(4, len(seen), "the frame chosen does not show all four")
        spots = self.blue(screen.world)
        left, top, side = screen.world.circle()
        # Each mat's marker is its own island of blue. Finding blue within a marker's width of
        # every one of the four is the claim that all four were drawn.
        for mat in seen:
            here = screen.globe.at(19, mat.latitude, mat.longitude)
            target = (left + here.x * side, top + here.y * side)
            near = min(abs(x - target[0]) + abs(y - target[1]) for x, y in spots)
            self.assertLess(near, side * 0.05,
                            f"nothing drawn at {mat.name or 'a remote mat'}")
        # And the Kaaba end, which every line has to reach.
        mecca = screen.globe.at(19, *KAABA)
        target = (left + mecca.x * side, top + mecca.y * side)
        near = min(abs(x - target[0]) + abs(y - target[1]) for x, y in spots)
        self.assertLess(near, side * 0.06, "no line reaches the Kaaba")

    def test_more_mats_means_more_blue_on_the_globe(self):
        """The plain version of the same thing, measured a different way: four lines put more
        blue on the picture than one does."""
        one = self.window()
        alone = self.opened(one)
        self.wind_to(alone, 19)
        few = len(self.blue(alone.world))
        many_window = self.window()
        self.pretend(many_window)
        crowd = self.opened(many_window)
        self.wind_to(crowd, 19)
        lots = len(self.blue(crowd.world))
        self.assertGreater(lots, few * 1.8, f"one mat drew {few}, four drew {lots}")

    # -- the dots ----------------------------------------------------------------------------

    def test_a_mat_round_the_back_has_its_dot_dimmed(self):
        """Bury and Sydney are 153 degrees apart, so they share the visible face for six frames
        in seventy-two. A count of four beside one line would read as a fault; the dots are what
        makes the number and the picture agree."""
        w = self.window()
        self.pretend(w)
        screen = self.opened(w)
        self.wind_to(screen, 39)      # the Pacific facing us: Sydney only
        lit = {mat.name or "remote": pip.lit for pip, mat in screen.pips}
        self.assertEqual({"Bury": False, "Sydney": True, "Cairo": False, "Lahore": False}, lit)

    def test_the_dots_come_back_as_the_earth_turns(self):
        w = self.window()
        self.pretend(w)
        screen = self.opened(w)
        self.wind_to(screen, 39)
        self.assertFalse(dict((m.name, p) for p, m in screen.pips)["Bury"].lit)
        self.wind_to(screen, 66)
        self.assertTrue(dict((m.name, p) for p, m in screen.pips)["Bury"].lit,
                        "Bury never came back round")

    # -- what is not shown --------------------------------------------------------------------

    def test_only_this_mat_is_named(self):
        """A town beside a dot is a household. This screen is looked at by children, and the
        only one it is allowed to name is the one it is standing on."""
        w = self.window()
        self.pretend(w)
        screen = self.opened(w)
        said = [x.text() for x in screen.column.findChildren(QtWidgets.QLabel)
                if x.objectName() == "worldWho"]
        self.assertIn("Bury", said, "the mat's own place should be named")
        for elsewhere in ("Sydney", "Cairo", "Lahore"):
            self.assertNotIn(elsewhere, said, f"{elsewhere} is named on screen")
        whole = " ".join(x.text() for x in w.world_page.findChildren(QtWidgets.QLabel))
        for elsewhere in ("Sydney", "Cairo", "Lahore"):
            self.assertNotIn(elsewhere, whole, f"{elsewhere} appears somewhere on the page")

    def test_the_list_stops_before_it_runs_out_of_page(self):
        """Thirty-one mats must not push the Back button off the bottom."""
        w = self.window()
        self.pretend(w, tuple((10 + i, 20 + i * 3, "", i == 0) for i in range(31)))
        screen = self.opened(w)
        self.assertEqual("31", screen.count.text(), "the count should still be the truth")
        self.assertLessEqual(len(screen.pips), screen.ROWS)
        self.assertTrue(w.world_back_button.isVisible())
        self.assertLessEqual(screen.column.height(), w.world_page.height(),
                             "the column is taller than the page it is on")

    # -- the room it takes --------------------------------------------------------------------

    def test_the_column_costs_the_globe_nothing(self):
        """The globe is square and every screen the mat has is wider than it is tall, so its
        size is settled by the height left over and never by the width. The column goes in room
        that was already empty beside it.

        This was written against the three sizes the globe came out at, and a version later that
        caught something real and named it wrongly: the globe had shrunk, but by the Back button
        doubling in height underneath it, not by the column. So what it asks now is the thing it
        always meant -- that the globe is still hemmed in by the height and not by the width. If
        the column ever starts squeezing it, the globe turns width-limited and this fails.
        """
        for size in ((1024, 600), (1280, 720), (1920, 1080)):
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size=size)
                screen = self.opened(w)
                world = screen.world
                side = world.circle()[2]
                self.assertEqual(world.height(), side,
                                 "the globe is no longer as tall as the room it has -- the "
                                 "column is squeezing it")
                self.assertGreater(world.width(), side,
                                   "there is no width to spare beside the globe any more")
                # And a floor, so it cannot quietly dwindle: still over half the page.
                self.assertGreater(side, w.world_page.height() * 0.6,
                                   f"the globe is down to {side}px on a "
                                   f"{w.world_page.height()}px page")


class ThumbButtonsTest(unittest.TestCase):
    """The buttons that are pressed hardest, given room to be pressed.

    Back on the world and hadith screens came out 29 pixels tall on the 7" panel, and the
    update button 23. That is a fingernail, on a screen somebody prods with a thumb while
    standing over a mat on the floor. These are twice that and no narrower than they are tall.

    Measured against a plain Back button in the same window rather than against a pixel count,
    because the point is the ratio: the sizes follow the screen, so a number written here would
    only be true on one of them.
    """

    def window(self, size=(1024, 600), lang="en"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury", lang=lang),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(*size)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def plain_back(self, w):
        """An ordinary Back button in this same window, for the comparison."""
        w.open_place()
        settle()
        return w.place_screen.leave

    SIZES = ((1024, 600), (1280, 720), (1920, 1080))

    def test_the_world_back_button_is_twice_the_height_of_a_plain_one(self):
        for size in self.SIZES:
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size)
                plain = self.plain_back(w).height()
                w.open_world()
                settle()
                big = w.world_back_button
                self.assertGreater(big.height(), plain * 1.8,
                                   f"{big.height()}px against a plain {plain}px")
                self.assertGreaterEqual(big.width(), big.height(),
                                        "taller than it is wide is not a square")

    def test_the_hadith_back_button_is_the_same(self):
        for size in self.SIZES:
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size)
                plain = self.plain_back(w).height()
                w.open_corner("hadith")
                settle()
                big = w.soon_back_button
                self.assertGreater(big.height(), plain * 1.8,
                                   f"{big.height()}px against a plain {plain}px")
                self.assertGreaterEqual(big.width(), big.height())

    def test_the_update_button_says_update_and_is_twice_as_tall(self):
        for size in self.SIZES:
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size)
                plain = self.plain_back(w).height()
                w.open_settings()
                settle()
                button = w.update_button
                self.assertEqual("UPDATE", button.text())
                self.assertGreater(button.height(), plain * 1.5,
                                   f"{button.height()}px against a plain back button's {plain}px")

    def test_the_update_button_is_a_block_in_every_language(self):
        """The height is only half of it: "Check for updates" was three times wider than it was
        tall, which is a strip rather than something to aim a thumb at. Measured as the ratio in
        all six languages at all three sizes -- Spanish is the widest at 2.21 and Chinese the
        narrowest at 0.98, against 3.0 for the words it used to carry."""
        for lang in sorted(full_packs(available_packs(ASSETS))):
            for size in self.SIZES:
                with self.subTest(f"{lang} {size[0]}x{size[1]}"):
                    w = self.window(size, lang=lang)
                    w.open_settings()
                    settle()
                    button = w.update_button
                    self.assertTrue(button.text(), f"{lang} has no word for it")
                    shape = button.width() / button.height()
                    self.assertLess(shape, 2.6,
                                    f"{lang}: {button.text()!r} makes it {shape:.2f} times "
                                    f"wider than it is tall")
                    # Never narrower than it is tall. Chinese is the word that tests it: 更新
                    # comes out 47px wide against 48 tall on its own, and the floor in the
                    # stylesheet takes it to 62 -- a third more to aim at.
                    self.assertGreaterEqual(shape, 1.0,
                                            f"{lang}: {button.text()!r} makes it "
                                            f"{button.width()}x{button.height()}, narrower "
                                            f"than it is tall")

    def test_the_ordinary_back_buttons_are_left_as_they_were(self):
        """The bigger size is its own object name rather than a change to every Back button in
        the app. The reader's bar and the keyboard screens are laid out around the small one."""
        w = self.window()
        plain = self.plain_back(w)
        self.assertEqual("backButton", plain.objectName())
        w.open_wifi()
        settle()
        self.assertEqual("backButton", w.wifi_screen.leave.objectName())
        w.open_world()
        settle()
        self.assertEqual("bigBack", w.world_back_button.objectName())
        # And the plain one is still the small size beside the big one.
        self.assertLess(plain.height(), w.world_back_button.height() * 0.7)


class WorldHeadingTest(unittest.TestCase):
    """Where the name plate sits on the world screen. It was centred over the whole page, which
    once the Active column took the right-hand side left it floating above nothing in
    particular. Harry asked for it on the left, over the globe."""

    def window(self, size=(1024, 600)):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(*size)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        w.open_corner("world")
        settle()
        return w

    def test_the_plate_is_against_the_left_of_the_page(self):
        for size in ((1024, 600), (1920, 1080)):
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size)
                plate = w.world_title
                page = w.world_page
                left = plate.mapTo(page, QtCore.QPoint(0, 0)).x()
                middle = plate.mapTo(page, plate.rect().center()).x()
                self.assertLess(left, page.width() * 0.1,
                                f"the plate starts {left}px in on a {page.width()}px page")
                self.assertLess(middle, page.width() * 0.45,
                                "the plate is still sitting in the middle of the page")

    def test_it_is_over_the_globe_rather_than_the_column(self):
        w = self.window()
        plate = w.world_title
        page = w.world_page
        globe = w.world_screen.world
        plate_middle = plate.mapTo(page, plate.rect().center()).x()
        column_left = w.world_screen.column.mapTo(page, QtCore.QPoint(0, 0)).x()
        globe_left, _, side = globe.circle()
        globe_middle = globe.mapTo(page, QtCore.QPoint(globe_left + side // 2, 0)).x()
        self.assertLess(plate_middle, column_left, "the heading has drifted over the column")
        self.assertLess(abs(plate_middle - globe_middle), page.width() * 0.5,
                        "the heading is nowhere near the globe it heads")


class DuaPlayTest(unittest.TestCase):
    """The play mark on a du'a card. It opened the du'a and stopped there for as long as there
    were no recordings; there are recordings now, so it should read it aloud."""

    def window(self, size=(1024, 600)):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(*size)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def board(self, w, kind="morning"):
        w.open_the_kinds_of_dua()
        settle()
        w.open_dua_category(kind)
        settle()
        return w.dua_board

    def test_the_mark_is_twice_the_size_it_was(self):
        """46 pixels on a 440 pixel card is a stamp to aim a thumb at, and it is now the only
        way to hear a du'a read."""
        from salaah.duaboard import DuaCard
        for size in ((1024, 600), (1920, 1080)):
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size)
                card = self.board(w).cards[0]
                self.assertEqual(w.px(DuaCard.MARK) + w.px(10), card.button.width())
                self.assertGreaterEqual(card.button.height(), w.px(92),
                                        "the mark has gone back to its old size")
                self.assertEqual(card.button.width(), card.button.height(), "it is square")
                self.assertLess(card.button.width(), card.width() * 0.25,
                                "the mark has taken over the card")

    def test_every_du_a_can_be_read_aloud_now(self):
        w = self.window()
        reader = w.section_readers["duas"]
        cannot = []
        for i in range(len(w.duas.items)):
            reader.open(i)
            settle()
            if not reader.can_say():
                cannot.append(w.duas.items[i].key)
        self.assertEqual([], cannot, f"no recording or no timings for: {cannot}")

    def test_the_mark_reads_the_du_a_where_it_stands(self):
        """It used to open the du'a's own page and read it there, which meant the two-column
        screen vanished the moment you pressed play -- and with it the du'a beside the one you
        wanted. It reads it here now, and here is where it stays."""
        w = self.window()
        board = self.board(w)
        board.cards[0].button.click()
        settle()
        self.assertIs(board, w.corner_screen.currentWidget(), "it left the two-column screen")
        self.assertTrue(board.saying, "nothing is being read")
        self.assertIs(board.cards[0], board.said_by)
        board.stop_saying()
        settle()

    def test_pressing_it_again_stops_and_the_other_card_takes_over(self):
        w = self.window()
        board = self.board(w)
        board.cards[0].button.click()
        settle()
        board.cards[1].button.click()
        settle()
        self.assertIs(board.cards[1], board.said_by, "the voice did not move across")
        board.cards[1].button.click()
        settle()
        self.assertFalse(board.saying, "pressing it again should stop it")

    def test_a_du_a_with_no_recording_opens_instead(self):
        """A mat part way through an update, or a set of du'as that grew past its recordings.
        The mark must not become a dead button."""
        w = self.window()
        board = self.board(w)
        opened = []
        board.chose.connect(opened.append)
        with mock.patch.object(type(board), "can_say", lambda self, card: False):
            board.cards[0].button.click()
            settle()
            self.assertFalse(board.saying)
            self.assertEqual([board.cards[0].index], opened,
                             "with no recording it should open the du'a instead")

    def test_leaving_the_screen_stops_the_voice(self):
        """A recording left playing to an empty room."""
        w = self.window()
        board = self.board(w)
        board.cards[0].button.click()
        settle()
        self.assertTrue(board.saying)
        w.go_home()
        settle()
        self.assertFalse(board.saying, "it is still reading to nobody")

    def test_it_does_not_fall_asleep_over_a_du_a_on_the_board(self):
        w = self.window()
        board = self.board(w)
        board.cards[0].button.click()
        settle()
        w.maybe_sleep()
        settle()
        self.assertFalse(w.asleep, "it went to sleep while reading a du'a aloud")
        board.stop_saying()
        settle()

    def test_the_word_being_said_goes_red_on_the_card(self):
        """The whole point of reading it here rather than on its own page."""
        w = self.window()
        board = self.board(w)
        board.cards[0].button.click()
        settle()
        card = board.said_by
        self.assertTrue(card.arabic.by_word, "the card cannot light a single word")
        for k in (0, 1):
            start, end = card.item.times[k]
            with mock.patch.object(type(w.recitation), "position",
                                   lambda self, k=k: (card.item.times[k][0]
                                                      + card.item.times[k][1]) / 2000.0):
                board.tick()
                settle()
                self.assertEqual((0, k), card.arabic.highlight,
                                 f"word {k + 1} was not the one lit")
        board.stop_saying()
        settle()
        self.assertIsNone(card.arabic.highlight, "a word is still red after it stopped")

    def test_the_word_being_said_is_the_one_in_red(self):
        """Walked against the timings rather than against the clock: at a moment inside word
        five's span, word five is the one lit."""
        w = self.window()
        reader = w.section_readers["duas"]
        reader.open(1)                       # the 37-word one, which has the most to get wrong
        settle()
        item = w.duas.items[1]
        for k in (0, 5, 17, 36):
            start, end = item.times[k]
            middle = (start + end) / 2000.0
            reader.arabic.set_highlight((0, item.word_at(middle)))
            settle()
            self.assertEqual(k, item.word_at(middle),
                             f"half way through word {k + 1} the app thinks it is somewhere else")
            self.assertEqual((0, k), reader.arabic.highlight)


class PlainerDuasTest(unittest.TestCase):
    """No transliteration on the du'as. Ten of the forty-eight had one and thirty-eight did
    not, so it was a line that turned up on some and not others; and now that every du'a can be
    heard read aloud, pressing play is a better answer to "how does it sound" than English
    letters are. The kalima keep theirs -- same reader, but only six of them and all six have it.
    """

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1024, 600)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def said_on(self, page):
        return [x for x in page.findChildren(QtWidgets.QLabel)
                if x.objectName() in ("duaCardSaid", "passageSaid") and x.isVisible()
                and x.text().strip()]

    def test_no_transliteration_on_a_du_a_card(self):
        w = self.window()
        w.open_the_kinds_of_dua()
        settle()
        for kind in ("general", "morning", "forgiveness"):
            with self.subTest(kind):
                w.open_dua_category(kind)
                settle()
                for card in w.dua_board.cards:
                    self.assertEqual([], self.said_on(card),
                                     "a card is still showing a transliteration")

    def test_no_transliteration_on_a_du_a_s_own_page(self):
        w = self.window()
        for i in (0, 3, 9):          # three of the ten that have one in the file
            with self.subTest(i):
                w.open_passage("duas", i)
                settle()
                self.assertEqual([], self.said_on(w.section_readers["duas"]))

    def test_the_kalima_keep_theirs(self):
        """The same reader serves both, so this is the line that stops the du'a change from
        quietly taking the kalima's transliteration with it."""
        w = self.window()
        w.open_passage("kalima", 0)
        settle()
        said = self.said_on(w.section_readers["kalima"])
        self.assertTrue(said, "the first kalima has lost its transliteration")
        self.assertIn("ilaha", said[0].text().lower())

    def test_the_arabic_got_the_room(self):
        """The point of removing it. Measured against a card built with the line put back."""
        w = self.window()
        w.open_the_kinds_of_dua()
        settle()
        w.open_dua_category("gratitude")
        settle()
        card = w.dua_board.cards[0]
        self.assertGreater(card.arabic.height(), card.height() * 0.45,
                           "the Arabic is not using the room the transliteration left")


class HadithHeadingTest(unittest.TestCase):
    """The Hadith plate sits against the left of the page, as the world screen's does.

    Hadith opens its twelve headings now, so the page this is about is reached the way a mat
    whose assets were half copied reaches it: with the section emptied. That is still a screen
    the mat can land on, and the plate on it is still the one Harry asked to have moved left.
    """

    def window(self, size=(1024, 600)):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(*size)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        w.section_lists["hadith"].passages._items = []
        w.open_corner("hadith")
        settle()
        return w

    def test_the_plate_is_against_the_left(self):
        for size in ((1024, 600), (1920, 1080)):
            with self.subTest(f"{size[0]}x{size[1]}"):
                w = self.window(size)
                plate = w.soon_title
                page = w.corner_soon
                left = plate.mapTo(page, QtCore.QPoint(0, 0)).x()
                middle = plate.mapTo(page, plate.rect().center()).x()
                self.assertEqual("Hadith", plate.text())
                self.assertLess(left, page.width() * 0.1,
                                f"the plate starts {left}px in on a {page.width()}px page")
                self.assertLess(middle, page.width() * 0.45,
                                "the plate is still in the middle of the page")


class PrayerPlateTest(unittest.TestCase):
    """Each prayer's name on the same white plate the Hadith and world screens wear, with the
    Arabic beside the English rather than at the far edge of the screen.

    SINCE 1.62 this is the fallback screen. Harry's drawings carry the prayer's name across the
    dome instead, which is a better place for it and leaves no room for a plate; the plate is
    what a prayer still gets when it has no drawing. These tests are kept, pointed at that
    screen, because the fallback is a guard rather than dead weight -- see no_drawing below.
    """

    def no_drawing(self):
        """Force the screen the app draws for itself, which since 1.62 is the fallback.

        Harry's five drawings replaced it, and the fallback is still there on purpose: it is
        what a prayer gets when its drawing is missing, and -- the case that matters -- when a
        drawing's arches do not match the units the school says the prayer has. These tests are
        about THAT screen, so they ask for it rather than being deleted along with the default.
        """
        patch = mock.patch.object(MainWindow, "prayer_page", lambda self, pid: None)
        patch.start()
        self.addCleanup(patch.stop)

    def window(self):
        self.no_drawing()
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1024, 600)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")

    def test_every_prayer_wears_the_plate(self):
        w = self.window()
        for pid in self.PRAYERS:
            with self.subTest(pid):
                w.open_prayer(pid)
                settle()
                plate = w.prayer_plate
                self.assertEqual("namePlate", plate.objectName())
                words = [x.text() for x in plate.findChildren(QtWidgets.QLabel)]
                self.assertIn(w.t(f"prayer.{pid}"), words, "the name is not on the plate")
                self.assertIn(w.content.prayer_names.get(pid, ""), words,
                              "the Arabic name is not on the plate")

    def test_the_plate_is_white_with_the_name_on_it_in_black(self):
        """The thing Harry asked for is the look, so the look is what is measured: a white
        rectangle with dark lettering, grabbed off the screen rather than read off a stylesheet.
        """
        w = self.window()
        w.open_prayer("fajr")
        settle()
        shot = w.prayer_plate.grab().toImage()
        white = dark = 0
        for y in range(0, shot.height(), 2):
            for x in range(0, shot.width(), 2):
                c = shot.pixelColor(x, y)
                level = (c.red() + c.green() + c.blue()) / 3
                if level > 230:
                    white += 1
                elif level < 80:
                    dark += 1
        self.assertGreater(white, dark * 2, "the plate is not mostly white")
        self.assertGreater(dark, 40, "there is no dark lettering on it")

    def test_the_arabic_sits_beside_the_english_not_across_the_screen(self):
        """They are the same name. At opposite edges they read as two separate headings."""
        w = self.window()
        w.open_prayer("maghrib")
        settle()
        labels = w.prayer_plate.findChildren(QtWidgets.QLabel)
        self.assertEqual(2, len(labels))
        gap = abs(labels[0].geometry().center().x() - labels[1].geometry().center().x())
        self.assertLess(gap, w.width() * 0.3,
                        f"{gap}px apart on a {w.width()}px screen is not beside each other")


class NewFrontDoorTest(unittest.TestCase):
    """Harry's new drawing, which the mat now opens on, and the one job it has: the time.

    Three things about it differ from the two mosques behind it, and all three are measured off
    the rendered screen rather than read back out of mosque.json. The file is only what the
    drawing says about itself, so a test that reads it proves the file agrees with itself and
    nothing else.
    """

    def window(self, mode="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def front(self, w):
        front = w.welcome_mosque
        self.assertIs(w.welcome, w.stack.currentWidget(), "the mat did not open on the front door")
        # The film is sixty frames of walking figures and breathing lettering, and -- since
        # 1.62 -- the app's own stars twinkle behind it on their own clock. Both held still, so
        # that what differs between two grabs is the time and only the time. Before 1.62 only
        # the film needed holding: the drawing brought its own sky and the app painted none.
        if front.film is not None:
            front.film.stop()
            front.film.jumpToFrame(0)
        front.flutter.stop()
        held = front.sky.now()
        frozen = mock.patch.object(type(front.sky), "now", staticmethod(lambda: held))
        frozen.start()
        self.addCleanup(frozen.stop)
        settle()
        return front

    @staticmethod
    def moved(front, before, after, step=2):
        """Which pixels differ between two clock readings: (x0, y0, x1, y1), or None."""
        front.set_time(before)
        settle()
        one = front.grab().toImage()
        front.set_time(after)
        settle()
        two = front.grab().toImage()
        xs, ys = [], []
        for y in range(0, one.height(), step):
            for x in range(0, one.width(), step):
                if one.pixel(x, y) != two.pixel(x, y):
                    xs.append(x)
                    ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None

    def test_the_time_is_written_on_the_dome_and_nowhere_else(self):
        """Where the numbers land is worked out from the drawing, and this is the check that it
        landed on the dome: the only part of the picture that changes when the clock does sits
        above the doorway and across the middle of it, which is where a dome is."""
        w = self.window()
        front = self.front(w)
        box = self.moved(front, "00:00", "18:48")
        self.assertIsNotNone(box, "the clock is not being drawn at all")
        x0, y0, x1, y1 = box
        door = front.arch_centre("enter")
        self.assertIsNotNone(door, "the name panel is missing, so there is nothing to go in by")
        self.assertLess(y1, door.y(), f"the time is drawn at y {y1}, below the doorway at {door.y()}")
        middle = (x0 + x1) // 2
        self.assertLess(abs(middle - front.width() // 2), front.width() * 0.1,
                        f"the time is off to one side, centred at x {middle}")
        self.assertGreater(x1 - x0, front.width() * 0.04, "the numbers are too small to read")
        self.assertLess(x1 - x0, front.width() * 0.5, "the numbers are spread across the building")

    def test_the_numbers_stand_out_from_the_dome_on_either_screen(self):
        """The dome is a solid shape in this drawing rather than an outline, so the numbers on
        it have to be the opposite of whatever it is -- and the whole drawing inverts with the
        theme, so both ways round need checking."""
        for mode, dome_is_light in (("dark", True), ("light", False)):
            with self.subTest(mode):
                w = self.window(mode)
                front = self.front(w)
                box = self.moved(front, "00:00", "18:48")
                self.assertIsNotNone(box, f"{mode}: no clock on the dome")
                x0, y0, x1, y1 = box
                front.set_time("18:48")
                settle()
                shot = front.grab().toImage()
                ink, dome = [], []
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        c = shot.pixelColor(x, y)
                        ink.append((c.red() + c.green() + c.blue()) / 3)
                # The dome either side of the numbers, in the band they sit in.
                for y in range(y0, y1 + 1):
                    for x in (max(0, x0 - 40), min(shot.width() - 1, x1 + 40)):
                        c = shot.pixelColor(x, y)
                        dome.append((c.red() + c.green() + c.blue()) / 3)
                darkest = min(ink)
                lightest = max(ink)
                around = sum(dome) / len(dome)
                if dome_is_light:
                    self.assertGreater(around, 170, f"{mode}: the dome is not light")
                    self.assertLess(darkest, 80, f"{mode}: the numbers are not dark on it")
                else:
                    self.assertLess(around, 90, f"{mode}: the dome is not dark")
                    self.assertGreater(lightest, 170, f"{mode}: the numbers are not light on it")

    def test_the_app_paints_the_sky_behind_the_front_door(self):
        """REVERSED IN 1.62, and worth saying why rather than quietly rewriting it.

        The drawing this replaced had a sun, a moon and stars drawn into it, all moving, so the
        app painted none: a second moon beside the one already there would have been worse than
        none. Harry's new drawing has none of them -- "there is no star, birds or sun on this
        one, i want you to populate the sky like the others according to time of day" -- so the
        sky is cut out of it and the app paints behind it again, exactly as it does on the
        mosque. The old test is not wrong about the old drawing; it is about a drawing that is
        no longer there.
        """
        w = self.window()
        front = self.front(w)
        self.assertTrue(front.own_sky, "the front door is not asking for a sky")
        self.assertTrue(front.isVisible(), "and this is with the screen up, not hidden")
        # The proof it is really coming through: take the stars away and the picture changes.
        front.set_sky(False, 0.5)
        stars = list(front.sky.stars)
        self.assertGreater(len(stars), 20, "there are stars to have shown")
        front.sky.stars = []
        front.update()
        settle()
        bare = front.grab().toImage()
        front.sky.stars = stars
        front.update()
        settle()
        starry = front.grab().toImage()
        showing = sum(1 for y in range(0, front.height(), 2)
                      for x in range(0, front.width(), 2)
                      if (QtGui.QColor(starry.pixel(x, y)).lightness()
                          - QtGui.QColor(bare.pixel(x, y)).lightness()) > 30)
        self.assertGreater(showing, 10, "none of the app's stars reach the screen")

    def test_the_drawing_fills_the_screen_side_to_side(self):
        """It arrived narrower than the screen and sat in the middle with a black bar either
        side. The bars are now part of the drawing, cut from its own sky, so they invert with
        it and are not there to see."""
        w = self.window()
        front = self.front(w)
        shown = front.picture.size()
        self.assertGreater(shown.width() / shown.height(), 1.8,
                           f"the drawing is {shown.width()}x{shown.height()}, which will letterbox")
        shot = front.grab().toImage()
        band = front.height() // 3
        edge = [shot.pixelColor(x, band) for x in range(0, 12)]
        levels = {(c.red() + c.green() + c.blue()) // 3 for c in edge}
        self.assertEqual(1, len(levels),
                         "the far edge of the screen is not one flat colour, so a bar shows")


class DuaMenuSwapTest(unittest.TestCase):
    """Harry redrew the du'a menu: the General du'as square has gone and a 6 Kalima square is
    in its place. The kalima are not a kind of du'a, so the tile has to leave the du'as
    altogether and land on the six arches."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_there_is_no_general_duas_square_and_nothing_is_filed_under_it(self):
        w = self.window()
        w.chose_on_the_small_screen("duas")
        settle()
        self.assertNotIn("general", [t.name for t in w.dua_menu.tiles],
                         "the General du'as square is still on the menu")
        listing = w.section_lists["duas"]
        stranded = [item.said or item.english for item in listing.passages.items
                    if item.cats == ["general"]]
        self.assertEqual([], stranded,
                         f"{len(stranded)} du'a(s) are filed under General only, so the square "
                         f"went and took them with it")

    def test_the_six_kalima_square_is_there_in_its_place(self):
        w = self.window()
        w.chose_on_the_small_screen("duas")
        settle()
        tiles = {t.name: t for t in w.dua_menu.tiles}
        self.assertIn("kalima", tiles, "there is no 6 Kalima square on the du'a menu")
        self.assertTrue(tiles["kalima"].path.is_file(),
                        f"its picture is missing: {tiles['kalima'].path}")
        self.assertTrue(tiles["kalima"].isEnabled())

    def test_touching_it_lands_on_the_six_arches_and_not_on_a_list_of_duas(self):
        w = self.window()
        w.chose_on_the_small_screen("duas")
        settle()
        next(t for t in w.dua_menu.tiles if t.name == "kalima").click()
        settle()
        self.assertIn("kalima", w.arch_menus, "the kalima mosque was never built")
        self.assertIs(w.arch_menus["kalima"], w.corner_screen.currentWidget(),
                      "the kalima square did not land on the six arches")
        self.assertIsNot(w.dua_board, w.corner_screen.currentWidget(),
                         "it landed on a board of du'as instead")
        self.assertEqual(["1", "2", "3", "4", "5", "6"],
                         [a.prayer for a in w.arch_menus["kalima"].mosque.arches],
                         "six arches is the whole point of the screen")

    def test_a_kind_that_is_not_a_kind_is_never_looked_for_among_the_duas(self):
        """open_dua_category filters the long list by the tile's name. Left to do that with
        kalima it would find nothing filed under it and land on the empty page, under the
        heading '6 Kalima' -- which looks like a section of the mat that was never finished."""
        w = self.window()
        w.open_dua_category("kalima")
        settle()
        self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget(),
                         "the kalima went looking for du'as and found the empty page")


class EveryWayBackTest(unittest.TestCase):
    """Harry: any button labelled Menu now points at the new default page. There are four of
    them on four different screens, and before this they landed on the mosque."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def a_menu_button(self, w, page):
        """The button on [page] that says Menu, by what is written on it rather than by name."""
        said = w.t("player.menu")
        found = [b for b in page.findChildren(QtWidgets.QPushButton) if b.text() == said]
        self.assertTrue(found, f"nothing on this screen says {said!r}")
        return found[0]

    def test_the_front_door_is_what_the_mat_opens_on(self):
        w = self.window()
        self.assertIsNotNone(w.welcome, "there is no front door")
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_the_way_back_from_a_prayers_units_lands_on_the_front_door(self):
        """CHANGED IN 1.62: the word on the button, not the claim.

        The units screen used to carry its own Menu button above the arches. It is a drawing
        now, with the same banner as every other screen, and the way home is the Main screen
        button up there -- so there is nowhere for a second one to sit and no reason for it.
        What still has to be true is that the screen has a way back and that it lands on the
        front door, which is what this checks, by what is written on the button.
        """
        w = self.window()
        w.leave_welcome()
        settle()
        w.open_prayer("asr")
        settle()
        self.assertIsNot(w.welcome, w.stack.currentWidget(), "we never left the front door")
        page = w.stack.currentWidget()
        home = [b for b in page.findChildren(QtWidgets.QPushButton)
                if b.text() in (w.t("player.menu"), w.t("settings.main_screen"))]
        self.assertTrue(home, "there is no way back off a prayer's units")
        home[0].click()
        settle()
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_main_screen_out_of_the_knowledge_corner_lands_on_it(self):
        w = self.window()
        w.open_corner("hadith")
        settle()
        self.assertIsNot(w.welcome, w.stack.currentWidget())
        w.go_home()
        settle()
        self.assertIs(w.welcome, w.stack.currentWidget())

    def test_it_lands_there_from_every_screen_that_can_leave(self):
        """go_home is the one road out, so every screen that offers a way back uses it. Each of
        these was somewhere the mat could get stuck if it landed wrong."""
        w = self.window()
        for name, go in (("a prayer's units", lambda: w.open_prayer("fajr")),
                         ("the Qur'an", lambda: w.open_corner("quran")),
                         ("the du'as", lambda: w.open_corner("duas")),
                         ("the six kalima", lambda: w.open_corner("kalima")),
                         ("the world", lambda: w.open_corner("world")),
                         ("Settings", lambda: w.open_settings())):
            with self.subTest(name):
                w.leave_welcome()
                settle()
                go()
                settle()
                self.assertIsNot(w.welcome, w.stack.currentWidget(), f"{name} never opened")
                w.go_home()
                settle()
                self.assertIs(w.welcome, w.stack.currentWidget(),
                              f"leaving {name} did not land on the front door")

    def test_the_salaah_tile_carries_a_prayer_mat_and_not_the_kalima_drawing(self):
        """The square the kalima used to have is a prayer mat now. The picture is checked as a
        picture: mostly white paper with a drawing on it, and not the file it replaced."""
        w = self.window()
        tile = next(t for t in w.side.corner.tiles if t.name == "salaah")
        self.assertEqual("salaah.png", tile.path.name)
        self.assertTrue(tile.path.is_file(), f"{tile.path} is missing")
        shot = QtGui.QImage(str(tile.path))
        self.assertFalse(shot.isNull(), "the Salaah tile will not open as a picture")
        ink = 0
        for y in range(0, shot.height(), 2):
            for x in range(0, shot.width(), 2):
                c = shot.pixelColor(x, y)
                if (c.red() + c.green() + c.blue()) / 3 < 128 and c.alpha() > 128:
                    ink += 1
        looked = (shot.height() // 2 + 1) * (shot.width() // 2 + 1)
        self.assertGreater(ink, looked * 0.02, "the tile is very nearly blank paper")
        self.assertLess(ink, looked * 0.5, "the tile is very nearly solid ink")
        beside = QtGui.QImage(str(tile.path.with_name("quran.png")))
        self.assertEqual(beside.size(), shot.size(),
                         "it is a different size to the five tiles beside it")


class WholeFrontDoorTest(unittest.TestCase):
    """Harry: the whole of the main page opens the prayers, not just the name across its front.

    The name panel still works and is still what the walk zooms towards; what changed is that
    the sky, the palm trees and the people walking past count too.
    """

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def touch(screen, point):
        ev = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, QtCore.QPointF(point),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier)
        screen.mousePressEvent(ev)
        settle()

    def corners(self, front):
        """Four places on the drawing that are not the name panel, by construction: a box round
        the panel is worked out and the points are taken outside it."""
        door = front.arch_centre("enter")
        self.assertIsNotNone(door)
        wide, tall = front.width(), front.height()
        return {
            "the top left sky": QtCore.QPoint(20, 20),
            "the top right sky": QtCore.QPoint(wide - 20, 20),
            "the far left, level with the door": QtCore.QPoint(8, door.y()),
            "the bottom right": QtCore.QPoint(wide - 8, tall - 8),
        }

    def test_a_touch_anywhere_on_it_opens_the_prayers(self):
        w = self.window()
        front = w.welcome_mosque
        for where, point in self.corners(front).items():
            with self.subTest(where):
                w.stack.setCurrentWidget(w.welcome)
                settle()
                self.touch(front, point)
                self.assertIs(w.home, w.stack.currentWidget(),
                              f"touching {where} did not open the prayers")

    def test_the_name_across_it_still_works_and_is_still_what_the_walk_aims_at(self):
        w = self.window()
        front = w.welcome_mosque
        door = front.arch_centre("enter")
        w.stack.setCurrentWidget(w.welcome)
        settle()
        self.touch(front, door)
        self.assertIs(w.home, w.stack.currentWidget())
        self.assertEqual("enter", front.arch_at(door),
                         "the name panel is no longer a panel, only a screen")

    def test_the_menus_did_not_become_touchable_all_over(self):
        """On the five arches and the six, the arch IS the choice. A touch on the sky there
        would pick a prayer nobody aimed at -- which is the whole reason this is a flag and
        not a change to every mosque on the mat."""
        w = self.window()
        self.assertTrue(w.welcome_mosque.anywhere)
        for name, screen in [("the prayers", w.mosque)] + \
                [(f"the {k} menu", m.mosque) for k, m in w.arch_menus.items()]:
            with self.subTest(name):
                self.assertFalse(screen.anywhere, f"{name} would open on a touch anywhere")
        sky = QtCore.QPoint(20, 20)
        self.assertIsNone(w.mosque.arch_at(sky), "the test aimed at an arch, not at the sky")
        w.stack.setCurrentWidget(w.home)
        settle()
        self.touch(w.mosque, sky)
        self.assertIs(w.home, w.stack.currentWidget(), "the sky started a prayer")

    def test_the_salaah_tile_lands_on_the_prayers_and_not_on_the_main_page(self):
        w = self.window()
        tile = next(t for t in w.side.corner.tiles if t.name == "salaah")
        tile.click()
        settle()
        self.assertIs(w.home, w.stack.currentWidget())
        self.assertIsNot(w.welcome, w.stack.currentWidget())

    def test_menu_still_means_the_main_page(self):
        """The Salaah tile moved; the buttons labelled Menu did not."""
        w = self.window()
        w.open_corner("quran")
        settle()
        w.go_home()
        settle()
        self.assertIs(w.welcome, w.stack.currentWidget())


class SayingsMenuTest(unittest.TestCase):
    """The Hadith tile opens Harry's twelve headings, and a heading shows its own sayings."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_the_hadith_tile_no_longer_lands_on_nothing_here_yet(self):
        w = self.window()
        w.open_corner("hadith")
        settle()
        self.assertIsNotNone(w.hadith_menu, "the menu was not built")
        self.assertIs(w.hadith_menu, w.corner_screen.currentWidget())
        self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget())

    def test_every_heading_has_its_own_picture(self):
        from salaah.duamenu import SAYINGS
        w = self.window()
        tiles = {t.name: t for t in w.hadith_menu.tiles}
        self.assertEqual(set(SAYINGS), set(tiles))
        self.assertEqual(18, len(tiles))
        for name, tile in tiles.items():
            with self.subTest(name):
                self.assertEqual(f"{name}.png", tile.path.name)
                self.assertTrue(tile.path.is_file())
                self.assertTrue(tile.isEnabled())

    def test_they_are_laid_out_six_across_the_way_the_sheet_was_drawn(self):
        """Eighteen now, in three rows of six -- Harry redrew it from twelve.

        Read off the sheet rather than off a constant, because the boxes come out of
        menu.json and a menu.json cut from the wrong drawing is the failure this catches.
        No check that the tiles are all one size: the six new ones on the bottom row were
        drawn 360x344 against 366x350 above them, and a test demanding they match would be
        testing my tidiness rather than Harry's drawing.
        """
        w = self.window()
        w.open_corner("hadith")      # shown, or every tile is still sat at the top left
        settle()
        rows = rows_of(w.hadith_menu.tiles)
        self.assertEqual(3, len(rows), f"the eighteen came out in {len(rows)} rows")
        for n, row in enumerate(rows):
            self.assertEqual(6, len(row), f"row {n + 1} has {len(row)}")

    def test_the_duas_menu_is_untouched_and_still_six_across(self):
        """One widget serves both menus now. If the sharing went wrong it would show here
        before it showed anywhere else."""
        w = self.window()
        w.open_corner("duas")
        settle()
        rows = rows_of(w.dua_menu.tiles)
        self.assertEqual(3, len(rows), f"the eighteen came out in {len(rows)} rows")
        for n, row in enumerate(rows):
            self.assertEqual(6, len(row), f"row {n + 1} has {len(row)}")
        self.assertEqual(18, len(w.dua_menu.tiles))

    def test_every_heading_opens_sayings_filed_under_that_heading(self):
        from salaah.duamenu import SAYINGS
        w = self.window()
        for kind in SAYINGS:
            with self.subTest(kind):
                w.open_saying_category(kind)
                settle()
                self.assertIs(w.hadith_board, w.corner_screen.currentWidget(),
                              f"{kind} did not open its board")
                shown = [item for _, item in w.hadith_board.showing]
                self.assertEqual(2, len(shown), "the board shows two")
                for item in shown:
                    self.assertIn(kind, item.cats, f"a saying of another kind is under {kind}")

    def test_a_saying_under_two_headings_can_be_reached_from_both(self):
        """Harry: "some hadiths will fall under multiple categories, which is fine."

        Checked on the board rather than in the file, because what matters is that the same
        narration comes up under either tile. The bag is shuffled, so it is dealt until the
        one being looked for appears rather than opened once and hoped for -- and the loop is
        bounded by the size of the heading, since the bag deals everything before repeating.
        """
        w = self.window()
        shared = [i for i in w.hadith_board.passages.items if len(i.cats) > 1]
        self.assertTrue(shared, "nothing is filed under two headings")
        for item in shared[:4]:
            for heading in item.cats:
                with self.subTest(f"{item.ref} under {heading}"):
                    held = sum(1 for p in w.hadith_board.passages.items
                               if heading in p.cats)
                    found = False
                    for _ in range(held + 2):
                        w.open_saying_category(heading)
                        settle(2)
                        if any(p.ref == item.ref for _, p in w.hadith_board.showing):
                            found = True
                            break
                    self.assertTrue(found, f"{item.ref} never came up under {heading} "
                                           f"in {held + 2} visits to a heading of {held}")

    def test_the_heading_is_written_across_the_top_in_the_reading_language(self):
        w = self.window()
        w.open_saying_category("hereafter")
        settle()
        self.assertEqual(w.t("saying.hereafter"), w.hadith_board.title.text())
        self.assertEqual("namePlate", w.hadith_board.title.objectName())

    def test_backing_out_of_a_saying_returns_to_the_heading_it_came_from(self):
        w = self.window()
        w.open_saying_category("charity")
        settle()
        index = w.hadith_board.showing[0][0]
        w.open_passage("hadith", index)
        settle()
        self.assertIs(w.section_readers["hadith"], w.corner_screen.currentWidget())
        w.open_section("hadith")
        settle()
        self.assertIs(w.hadith_board, w.corner_screen.currentWidget())
        self.assertEqual("charity", w.hadith_board.only)


class SayingsBoardTest(unittest.TestCase):
    """The two columns Harry asked for, with the play mark carried over to the translation."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        w.open_saying_category("knowledge")
        settle()
        return w

    def test_two_cards_side_by_side_with_the_rule_between_them(self):
        w = self.window()
        board = w.hadith_board
        self.assertEqual(2, len(board.cards))
        left, right = board.cards
        self.assertLess(left.geometry().right(), right.geometry().left(),
                        "the two cards are not side by side")
        self.assertIsNotNone(board.rule, "there is no rule between the columns")

    def test_the_play_mark_sits_beside_the_translation(self):
        w = self.window()
        for card in w.hadith_board.cards:
            with self.subTest(card.item.ref):
                self.assertTrue(card.sayings)
                mark = card.button.mapTo(card, QtCore.QPoint(0, 0)).y()
                words = card.english.mapTo(card, QtCore.QPoint(0, 0)).y()
                self.assertLess(abs(mark - words), card.height() * 0.2,
                                "the mark is not alongside the translation")
                self.assertLess(card.button.geometry().right(), card.english.geometry().left(),
                                "the mark is not to the left of the words it belongs to")
                self.assertLess(card.name.geometry().bottom(), card.button.geometry().top(),
                                "the heading is not above the two of them")

    def test_it_is_the_same_size_mark_as_the_duas(self):
        w = self.window()
        saying = w.hadith_board.cards[0]
        w.open_dua_category("travel")
        settle()
        dua = w.dua_board.cards[0]
        self.assertEqual(dua.MARK, saying.MARK)
        self.assertEqual(dua.button.size(), saying.button.size())

    def test_a_duas_mark_stayed_where_it_was_at_the_top(self):
        w = self.window()
        w.open_dua_category("travel")
        settle()
        for card in w.dua_board.cards:
            self.assertFalse(card.sayings)
            self.assertLess(card.button.mapTo(card, QtCore.QPoint(0, 0)).y(),
                            card.arabic.mapTo(card, QtCore.QPoint(0, 0)).y())

    def test_the_card_says_which_hadith_it_is(self):
        """The heading on a saying is its collection and number. Anybody who wants to check
        one needs that, and it is the only heading for a hadith that is not a summary of it
        written by somebody."""
        w = self.window()
        for card in w.hadith_board.cards:
            with self.subTest(card.item.ref):
                self.assertEqual(card.item.ref, card.name.text())
                self.assertTrue(card.name.text().startswith(("Sahih al-Bukhari", "Sahih Muslim")))

    def test_there_is_no_arabic_anywhere_in_the_section(self):
        """Harry asked for the translation and the play button and nothing else. The Arabic is
        still in hadith.json -- it is what the wording was checked against -- and this is the
        check that none of it reaches the glass, on the board or on the reader behind it."""
        from salaah.duamenu import SAYINGS
        w = self.window()
        for kind in SAYINGS:
            with self.subTest(kind):
                w.open_saying_category(kind)
                settle()
                for card in w.hadith_board.cards:
                    # Walked rather than asked. The first version of this checked
                    # card.arabic.isVisible(), which is False for a box that was never put on
                    # the card at all -- so it would have passed just as happily with the
                    # Arabic drawn by some other route, and removing the line that hides it
                    # changed nothing. What is checked now is every widget actually on the
                    # card and what it is holding.
                    self.assertIsNone(card.arabic.parentWidget(),
                                      "the Arabic box is on the card")
                    for bit in card.findChildren(QtWidgets.QWidget):
                        if not bit.isVisible():
                            continue
                        words = "".join(getattr(bit, "lines", []) or []) \
                            + (bit.text() if hasattr(bit, "text") else "")
                        self.assertFalse(any("\u0600" <= c <= "\u06ff" for c in words),
                                         f"{card.item.ref}: Arabic on a {type(bit).__name__}")
                    self.assertTrue(card.english.isVisible())
                    self.assertTrue(card.item.arabic, "the Arabic was dropped from the file too")
        # And the reader behind the board
        w.open_saying_category("faith")
        settle()
        w.open_passage("hadith", w.hadith_board.showing[0][0])
        settle()
        reader = w.section_readers["hadith"]
        self.assertFalse(reader.arabic.isVisible(), "the reader still opens on the Arabic")
        self.assertEqual([], reader.arabic.lines)

    def test_the_translation_is_drawn_as_large_as_its_card_allows(self):
        """With the Arabic gone the translation is the card. A label at a size fixed by the
        stylesheet would leave a short saying swimming and run a long one off the bottom, so it
        is drawn in the same fitting box the Arabic used to have."""
        from salaah.duamenu import SAYINGS
        from salaah.duaboard import SAYING_FLOOR, SAYING_CAP
        w = self.window()
        smallest, biggest, worst = 999, 0, ""
        for kind in SAYINGS:
            for _ in range(3):
                w.open_saying_category(kind)
                settle()
                for card in w.hadith_board.cards:
                    size = card.english.fitted_size()
                    if size < smallest:
                        smallest, worst = size, card.item.ref
                    biggest = max(biggest, size)
        self.assertGreaterEqual(smallest, int(SAYING_FLOOR * w.s),
                                f"{worst} is drawn at {smallest}px")
        self.assertLessEqual(biggest, int(SAYING_CAP * w.s))
        self.assertGreater(biggest, smallest,
                           "every saying came out the same size, so nothing is being fitted")

    def test_the_duas_still_show_their_arabic(self):
        """The Arabic came off the sayings, not off the du'as -- which are Arabic you say, and
        a du'a card with only the English on it would be the wrong screen entirely."""
        w = self.window()
        w.open_dua_category("travel")
        settle()
        for card in w.dua_board.cards:
            self.assertTrue(card.arabic.isVisible())
            self.assertEqual([card.item.arabic], card.arabic.lines)
            self.assertIsNone(card.english, "a du'a card built itself a translation box")
            self.assertIs(card.words, card.arabic, "the voice would light the wrong box")


class TwoNewTilesTest(unittest.TestCase):
    """Harry redrew the 7in sheet with Wu'du and Nasheeds on it. Both have something behind
    them now -- the seven steps, and the shelf of whatever is in the owner's folder -- so
    neither lands on the page that says "nothing here yet" any more."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_both_of_them_are_drawn_and_touchable(self):
        w = self.window()
        tiles = {t.name: t for t in w.side.corner.tiles}
        for name in ("wudu", "nasheeds"):
            with self.subTest(name):
                self.assertIn(name, tiles)
                self.assertEqual(f"{name}.png", tiles[name].path.name)
                self.assertTrue(tiles[name].path.is_file())
                self.assertTrue(tiles[name].isEnabled())

    def test_neither_lands_on_nothing_here_yet_any_more(self):
        """This used to assert the opposite for Nasheeds, and was right to: the tile was drawn
        before there was anything behind it. There is now, and an empty folder is not the same
        thing as an unbuilt section -- the shelf says where to put the files."""
        w = self.window()
        tiles = {t.name: t for t in w.side.corner.tiles}
        for name, screen in (("nasheeds", "nasheed_screen"), ("wudu", "wudu_menu")):
            with self.subTest(name):
                w.go_home()
                settle()
                tiles[name].click()
                settle()
                self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget(),
                                 f"{name} still lands on 'nothing here yet'")
                self.assertIs(w.corner_page, w.stack.currentWidget())
                self.assertIs(getattr(w, screen), w.corner_screen.currentWidget())

    def test_the_two_of_them_are_named_in_every_language_the_mat_speaks(self):
        for lang, pack in full_packs(available_packs(ASSETS)).items():
            for name in ("wudu", "nasheeds"):
                with self.subTest(f"{lang}.{name}"):
                    self.assertTrue(pack.ui.get(f"corner.{name}", "").strip(),
                                    f"{lang} cannot name {name}")

    def test_the_six_that_were_there_before_still_go_where_they_went(self):
        """Two tiles were added to the end of the sheet. If the cut or the naming slipped, the
        six already working would be the first thing to break, and quietly."""
        w = self.window()
        tiles = {t.name: t for t in w.side.corner.tiles}
        for name, check in (("quran", lambda: w.surah_list is w.corner_screen.currentWidget()),
                            ("duas", lambda: w.dua_menu is w.corner_screen.currentWidget()),
                            ("hadith", lambda: w.hadith_menu is w.corner_screen.currentWidget()),
                            ("world", lambda: w.world_page is w.corner_screen.currentWidget()),
                            ("settings", lambda: w.settings_screen is w.stack.currentWidget()),
                            ("salaah", lambda: w.home is w.stack.currentWidget())):
            with self.subTest(name):
                w.go_home()
                settle()
                tiles[name].click()
                settle()
                self.assertTrue(check(), f"the {name} tile landed somewhere new")


class FreshPairTest(unittest.TestCase):
    """Two at a time, and a different two every time the kind is opened -- on both boards.

    It used to be random.sample, which is not the same thing: two drawn out of four at random
    come up the same about one visit in six, and nothing promises the other two are ever seen.
    Each kind keeps a shuffled bag now and two are dealt off the top.
    """

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def visits(self, w, opener, board, kind, times=16):
        out = []
        for _ in range(times):
            opener(kind)
            settle(2)
            out.append(frozenset(i for i, _ in board.showing))
        return out

    BOTH = (("sayings", "hadith_board", "open_saying_category", "character"),
            ("du'as", "dua_board", "open_dua_category", "worry"))

    def test_never_the_same_two_twice_running(self):
        w = self.window()
        for name, board, opener, kind in self.BOTH:
            with self.subTest(name):
                seen = self.visits(w, getattr(w, opener), getattr(w, board), kind)
                for before, after in zip(seen, seen[1:]):
                    self.assertNotEqual(before, after,
                                        f"{name}: the same pair came up twice running")

    def test_two_at_a_time_and_only_two(self):
        w = self.window()
        for name, board, opener, kind in self.BOTH:
            with self.subTest(name):
                for pair in self.visits(w, getattr(w, opener), getattr(w, board), kind, 6):
                    self.assertEqual(2, len(pair), name)
                self.assertEqual(2, len(getattr(w, board).cards), name)

    def test_the_whole_kind_comes_round_rather_than_the_same_favourites(self):
        """The thing random sampling could not promise. With a bag, everything in the kind is
        dealt before anything comes round again."""
        w = self.window()
        for name, board, opener, kind in self.BOTH:
            with self.subTest(name):
                held = {i for i, item in enumerate(getattr(w, board).passages.items)
                        if kind in item.cats}
                seen = set()
                for pair in self.visits(w, getattr(w, opener), getattr(w, board), kind,
                                        len(held)):
                    seen |= pair
                self.assertEqual(held, seen,
                                 f"{name}: {len(held) - len(seen)} of {len(held)} never showed "
                                 f"in {len(held)} visits")

    def test_a_kind_holding_only_two_shows_both_and_does_not_fall_over(self):
        w = self.window()
        board = w.hadith_board
        board.show_only("hereafter", "The Hereafter")
        settle()
        board.passages._items = [x for x in board.passages.items
                                 if "hereafter" not in x.cats][:0] or board.passages.items
        # A kind with two in it: faked by asking the board for a pair out of exactly two.
        held = [(i, x) for i, x in enumerate(board.passages.items) if "hereafter" in x.cats][:2]
        board.wanted = lambda: held
        board.bags.clear()
        for _ in range(4):
            board.show_only("hereafter", "The Hereafter")
            settle()
            self.assertEqual(2, len(board.showing))
            self.assertEqual({i for i, _ in held}, {i for i, _ in board.showing})


class TheTrialEndsTest(unittest.TestCase):
    """The app has to clear its own trial, or every update is reverted on the next restart.

    This is the thing that broke 1.51 on the mat: the guard saw a version still on trial that
    had already been started once, concluded it was never going to settle, and put 1.49 back.
    It is checked here against a real state file and a real window rather than by reading the
    code, because what matters is whether the timer actually fires in a running app.
    """

    def window(self, root):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def test_a_version_on_trial_clears_it_by_running(self):
        import json
        import time
        from salaah.update import Installer
        state = ASSETS.parent / "update-state.json"
        kept = state.read_text(encoding="utf-8") if state.is_file() else None

        def put_it_back():
            if kept is None:
                state.unlink(missing_ok=True)
            else:
                state.write_text(kept, encoding="utf-8")
        self.addCleanup(put_it_back)

        state.write_text(json.dumps({"trial": "9.99", "was": "9.98",
                                     "at": time.time(), "attempts": 1}), encoding="utf-8")
        w = self.window(ASSETS.parent)
        self.assertEqual(ASSETS.parent, w.root, "the app is looking for the state file elsewhere")
        giving_up = time.time() + Installer.SETTLES + 10
        while time.time() < giving_up:
            settle(2)
            time.sleep(0.05)
            if not json.loads(state.read_text(encoding="utf-8")).get("trial"):
                break
        now = json.loads(state.read_text(encoding="utf-8"))
        self.assertFalse(now.get("trial"),
                         "still on trial: the guard would put the previous version back")
        self.assertEqual("9.99", now.get("installed"),
                         "the trial cleared without recording what was installed")


class WuduScreensTest(unittest.TestCase):
    """The Wu'du tile opens the seven steps; a step opens its drawing beside its words."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    KEYS = ("hands", "mouth", "nose", "face", "arms", "head", "feet")

    def test_the_wudu_tile_opens_the_seven_steps(self):
        w = self.window()
        w.open_corner("wudu")
        settle()
        self.assertIsNotNone(w.wudu_menu, "the seven were never built")
        self.assertIs(w.wudu_menu, w.corner_screen.currentWidget())
        self.assertIsNot(w.corner_soon, w.corner_screen.currentWidget(),
                         "Wu'du still lands on the page that says it is coming")
        self.assertEqual([f"step-{k}" for k in self.KEYS],
                         [t.name for t in w.wudu_menu.tiles])

    def test_the_seven_sit_in_one_row_across_the_screen(self):
        w = self.window()
        w.open_corner("wudu")
        settle()
        tops = {t.geometry().y() for t in w.wudu_menu.tiles}
        self.assertEqual(1, len(tops), f"the steps came out in {len(tops)} rows")
        order = sorted(w.wudu_menu.tiles, key=lambda t: t.geometry().x())
        self.assertEqual([f"step-{k}" for k in self.KEYS], [t.name for t in order],
                         "the steps are not left to right in order")

    def test_each_step_opens_its_own_drawing_heading_and_words(self):
        w = self.window()
        for n, key in enumerate(self.KEYS, start=1):
            with self.subTest(key):
                w.open_wudu_step(key)
                settle(4)
                step = w.wudu_step
                self.assertIs(step, w.corner_screen.currentWidget())
                self.assertEqual(f"{n} - {w.t(f'wudu.{key}')}", step.heading.text())
                self.assertGreater(len(step.words.text()), 60)
                self.assertTrue(step.films, "no drawing on this step")
                for film in step.films:
                    self.assertTrue(film.film.isValid(), "the drawing will not open")
                    self.assertGreater(film.film.frameCount(), 1, "it does not move")

    def test_the_drawing_takes_the_full_height_of_the_screen(self):
        """Harry asked for the left-hand side to use the full vertical space, and it is the
        whole reason the page is laid out this way round."""
        w = self.window()
        w.open_wudu_step("hands")
        settle(4)
        step = w.wudu_step
        drawn = step.films[0].drawn_size()
        self.assertGreater(drawn.height(), step.height() * 0.9,
                           f"the drawing is {drawn.height()}px tall on a {step.height()}px page")
        self.assertGreater(drawn.width(), 400, "and it should be wide with it")
        # Its shape is kept: a stretched boy is worse than a smaller one.
        shape = step.films[0].shape
        self.assertAlmostEqual(drawn.width() / drawn.height(),
                               shape.width() / shape.height(), places=1)

    def test_the_head_shows_both_its_drawings_at_the_same_size(self):
        """Wiping the head and wiping the ears are one step and two drawings. Side by side,
        because stacked they each get half the height -- and on tall portraits the height is
        what decides how big they come out."""
        w = self.window()
        # A one-film step first, and then the head with no layout pass in between. The order
        # matters and it took two goes to find out how: opened on its own, both drawings start
        # the same size and the row splits evenly whatever the labels ask for, so the test
        # passed with the fix taken out. Opened straight after another step, the one that had
        # already been scaled up asks the layout for more and gets it -- 647px beside 381px.
        w.open_wudu_step("hands")
        settle(4)
        w.open_wudu_step("head")
        settle(4)
        films = w.wudu_step.films
        self.assertEqual(2, len(films))
        left, right = sorted(films, key=lambda f: f.geometry().x())
        self.assertLess(left.geometry().right(), right.geometry().left() + 2,
                        "the two drawings are stacked, not side by side")
        self.assertEqual(left.drawn_size(), right.drawn_size(),
                         "one drawing is bigger than the other")
        self.assertGreater(left.drawn_size().height(), w.wudu_step.height() * 0.7)

    def test_back_is_square_at_the_bottom_right_and_returns_to_the_seven(self):
        w = self.window()
        w.open_wudu_step("hands")      # the first step: < is the way out of the section
        settle(4)
        step = w.wudu_step
        button = step.back_button
        self.assertEqual("bigBack", button.objectName())
        # The glyph, not the ASCII "<" this used to say. It is "‹" now and it turns round
        # in Urdu and Arabic -- see ArrowsPointTheWayTheReadingGoesTest. This window is
        # English, so back points left.
        from salaah.qt import BACK_ARROW
        self.assertEqual(BACK_ARROW, button.text())
        side = button.size()
        self.assertGreater(side.width(), w.px(80), "not a square: too narrow")
        self.assertGreater(side.height(), w.px(80), "not a square: too short")
        here = button.mapTo(step, QtCore.QPoint(0, 0))
        self.assertGreater(here.x(), step.width() * 0.75, "it is not over on the right")
        self.assertGreater(here.y(), step.height() * 0.6, "it is not down at the bottom")
        button.click()
        settle()
        self.assertIs(w.wudu_menu, w.corner_screen.currentWidget())

    def test_the_drawings_stop_when_the_screen_is_left(self):
        """Thirty frames a second of something nobody is looking at, on a mat that is left on
        all day."""
        from salaah.qt import QtGui as G
        w = self.window()
        w.open_wudu_step("hands")
        settle(4)
        step = w.wudu_step
        self.assertTrue(all(f.film.state() == G.QMovie.MovieState.Running for f in step.films))
        step.back_button.click()       # off the first step: out to the seven
        settle()
        self.assertTrue(all(f.film.state() == G.QMovie.MovieState.NotRunning
                            for f in step.films), "a drawing is still running off screen")

    def test_the_seven_in_sheet_is_in_the_order_harry_drew_it(self):
        w = self.window()
        order = sorted(w.side.corner.tiles, key=lambda t: (t.y(), t.x()))
        self.assertEqual(["quran", "salaah", "hadith", "duas",
                          "wudu", "nasheeds", "settings", "world"],
                         [t.name for t in order])


class StepArrowsTest(unittest.TestCase):
    """Two square buttons, < and >, walking the seven steps in order.

    < off the first step is the way out to the seven; > stops at the seventh rather than
    wrapping round, because the end of wu'du is not the beginning of it.
    """

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        w.open_wudu_step("hands")
        settle(4)
        return w

    def test_they_are_arrows_the_same_size_as_each_other(self):
        w = self.window()
        step = w.wudu_step
        from salaah.qt import BACK_ARROW, ON_ARROW
        self.assertEqual(BACK_ARROW, step.back_button.text())
        self.assertEqual(ON_ARROW, step.on_button.text())
        self.assertEqual(step.back_button.size(), step.on_button.size())
        for button in (step.back_button, step.on_button):
            self.assertEqual("bigBack", button.objectName(), "not the mat's square button")
            self.assertGreater(button.width(), w.px(80))
            self.assertGreater(button.height(), w.px(80))

    def test_both_sit_at_the_bottom_right_with_back_on_the_left_of_the_pair(self):
        w = self.window()
        step = w.wudu_step
        for button in (step.back_button, step.on_button):
            here = button.mapTo(step, QtCore.QPoint(0, 0))
            self.assertGreater(here.x(), step.width() * 0.7, "not over on the right")
            self.assertGreater(here.y(), step.height() * 0.6, "not down at the bottom")
        self.assertLess(step.back_button.geometry().right(), step.on_button.geometry().left() + 2,
                        "< should be to the left of >")

    def test_forward_walks_the_seven_in_order_and_stops_at_the_last(self):
        w = self.window()
        step = w.wudu_step
        seen = [step.heading.text()]
        for _ in range(9):          # more presses than there are steps, on purpose
            step.on_button.click()
            settle(3)
            seen.append(step.heading.text())
        wanted = [f"{n} - {w.t(f'wudu.{k}')}" for n, k in
                  enumerate(("hands", "mouth", "nose", "face", "arms", "head", "feet"), start=1)]
        self.assertEqual(wanted, seen[:7], "forward does not walk them in order")
        self.assertEqual([wanted[-1]] * 4, seen[6:],
                         "forward went past the last step, or wrapped round to the first")
        self.assertIs(step, w.corner_screen.currentWidget(), "it left the section")

    def test_forward_is_dead_on_the_last_step_and_alive_everywhere_else(self):
        w = self.window()
        step = w.wudu_step
        for _ in range(6):
            self.assertTrue(step.on_button.isEnabled(), step.heading.text())
            step.on_button.click()
            settle(3)
        self.assertEqual("7 - Wash Feet", step.heading.text())
        self.assertFalse(step.on_button.isEnabled(), "forward is still live on the last step")
        self.assertTrue(step.on_button.isVisible(),
                        "it should be there and dead, not gone: a button that vanishes moves "
                        "the other one, and a thumb learns where things are")

    def test_back_walks_them_the_other_way(self):
        w = self.window()
        step = w.wudu_step
        w.open_wudu_step("feet")
        settle(3)
        for wanted in ("6 - Wipe Head & Ears", "5 - Wash Arms", "4 - Wash Face"):
            step.back_button.click()
            settle(3)
            self.assertEqual(wanted, step.heading.text())
        self.assertIs(step, w.corner_screen.currentWidget())

    def test_back_off_the_first_step_leaves_the_section(self):
        w = self.window()
        step = w.wudu_step
        self.assertEqual("1 - Wash Hands", step.heading.text())
        step.back_button.click()
        settle()
        self.assertIs(w.wudu_menu, w.corner_screen.currentWidget(),
                      "< on the first step should go out to the seven")
        self.assertTrue(all(f.film.state() != f.film.MovieState.Running for f in step.films),
                        "and stop the drawing on the way")


class FilmsFollowTheThemeTest(unittest.TestCase):
    """Harry's drawings are black lines on white paper. On the night screen that was a slab of
    white light beside words in the opposite colours; everything else on the mat inverts, and
    these do now too -- in code, off the one set of files, rather than a second set shipped
    alongside them."""

    def window(self, mode):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    @staticmethod
    def levels(widget):
        """How light the drawn picture is, measured off the screen rather than off the file."""
        shot = widget.grab().toImage()
        light = dark = 0
        for y in range(0, shot.height(), 3):
            for x in range(0, shot.width(), 3):
                c = shot.pixelColor(x, y)
                level = (c.red() + c.green() + c.blue()) / 3
                if level > 200:
                    light += 1
                elif level < 60:
                    dark += 1
        return light, dark

    def test_a_wudu_drawing_is_dark_on_the_night_screen_and_light_by_day(self):
        for mode, mostly_dark in (("dark", True), ("light", False)):
            with self.subTest(mode):
                w = self.window(mode)
                w.open_wudu_step("hands")
                settle(6)
                light, dark = self.levels(w.wudu_step.films[0])
                if mostly_dark:
                    self.assertGreater(dark, light * 2,
                                       "the night screen is showing a slab of white paper")
                else:
                    self.assertGreater(light, dark * 2, "the day screen has gone black")

    def test_an_animated_menu_turns_inside_out_the_same_way(self):
        for mode, mostly_dark in (("dark", True), ("light", False)):
            with self.subTest(mode):
                w = self.window(mode)
                w.open_corner("hadith")
                settle(6)
                light, dark = self.levels(w.hadith_menu.sheet)
                if mostly_dark:
                    self.assertGreater(dark, light * 2, "the menu is white paper at night")
                else:
                    self.assertGreater(light, dark * 2, "the menu is black by day")

    def test_the_drawings_are_shipped_once_not_once_per_theme(self):
        """There is no inverted copy of anything on disk. If one ever appears it means somebody
        solved this with files again, and the two sets will drift."""
        for folder in ("wudu", "duas-menu", "hadith-menu", "knowledge"):
            for path in (ASSETS / folder).glob("*"):
                with self.subTest(path.name):
                    self.assertNotIn("invert", path.name.lower())
                    self.assertNotIn("-dark", path.name.lower())
                    self.assertNotIn("_dark", path.name.lower())


class AnimatedMenusTest(unittest.TestCase):
    """The du'a, hadith and 7in menus are one moving picture with the tiles touchable over it,
    rather than eighteen, eighteen and eight separate ones."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="dark", recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1080)
        w.show()
        w.side.resize(600, 1024)
        w.side.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def menus(self, w):
        """Each menu, and how many tiles it ought to have.

        The count comes from the tuple of names the app builds the menu from, not from a
        number written here. It used to be written here -- and in a SHEETS constant above as
        well, which this method built a list out of and then threw away in favour of the
        hard-coded one. Harry redrew the hadith sheet from twelve headings to eighteen and
        this was the one test that failed on it, saying 12 != 18 about a menu that was
        perfectly correct. A number copied into a test is a number that has to be found and
        changed every time the drawing changes, which is how a suite starts getting edited to
        agree with whatever it was given.

        What is still being checked: that the names the app asks for and the tiles it ends up
        with are the same set. A sheet cut with a tile missing makes FilmSheet refuse its
        boxes and fall back to the stills, which the assertions above this catch.
        """
        from salaah.duamenu import CATEGORIES, SAYINGS
        from salaah.knowledge import TILES
        return [("duas", w.dua_menu, CATEGORIES),
                ("hadith", w.hadith_menu, SAYINGS),
                ("the 7in", w.side.corner, TILES)]

    def test_all_three_are_drawn_as_one_film_rather_than_separate_pictures(self):
        w = self.window()
        for name, menu, names in self.menus(w):
            with self.subTest(name):
                self.assertIsNotNone(menu.sheet, f"{name} fell back to the stills")
                self.assertTrue(menu.sheet.ready)
                self.assertTrue(menu.sheet.film.isValid())
                self.assertGreater(menu.sheet.film.frameCount(), 1, "it does not move")
                self.assertEqual(len(names), len(menu.tiles))
                self.assertEqual(set(names), {t.name for t in menu.tiles},
                                 f"{name} shows tiles the app did not ask for")

    def test_the_touch_targets_sit_on_the_tiles_they_are_named_after(self):
        """The boxes are found at build time and written into menu.json in the sheet's own
        pixels; this is the check that they are scaled onto the right part of the screen."""
        w = self.window()
        w.open_corner("hadith")
        settle(6)
        sheet = w.hadith_menu.sheet
        drawn, scale = sheet.placement()
        self.assertGreater(scale, 0.1)
        seen = []
        for tile in sheet.tiles:
            with self.subTest(tile.name):
                here = tile.geometry()
                self.assertTrue(drawn.contains(here),
                                f"{tile.name} at {here} is off the drawing at {drawn}")
                self.assertGreater(here.width(), 40)
                self.assertGreater(here.height(), 40)
                for other in seen:
                    self.assertFalse(here.intersects(other),
                                     f"{tile.name} overlaps another tile")
                seen.append(here)

    def test_pressing_a_target_opens_what_is_drawn_under_it(self):
        w = self.window()
        w.open_corner("duas")
        settle(6)
        by_name = {t.name: t for t in w.dua_menu.tiles}
        by_name["travel"].click()
        settle()
        self.assertIs(w.dua_board, w.corner_screen.currentWidget())
        self.assertEqual("travel", w.dua_board.only)

    def test_the_targets_draw_nothing_so_the_film_shows_through(self):
        w = self.window()
        for name, menu, _ in self.menus(w):
            with self.subTest(name):
                for tile in menu.tiles:
                    self.assertTrue(tile.quiet, f"{tile.name} is painting over the film")

    def test_a_menu_nobody_is_looking_at_stops_turning(self):
        w = self.window()
        w.open_corner("hadith")
        settle(6)
        sheet = w.hadith_menu.sheet
        self.assertEqual(sheet.film.MovieState.Running, sheet.film.state())
        w.open_corner("duas")
        settle(6)
        self.assertEqual(sheet.film.MovieState.NotRunning, sheet.film.state(),
                         "the hadith menu is still turning behind the du'a menu")
        self.assertEqual(w.dua_menu.sheet.film.MovieState.Running,
                         w.dua_menu.sheet.film.state())

    def test_the_films_are_small_enough_to_put_on_a_mat(self):
        """They arrived at forty-one megabytes between them."""
        total = 0
        for folder in ("duas-menu", "hadith-menu", "knowledge"):
            film = ASSETS / folder / "menu.gif"
            with self.subTest(folder):
                self.assertTrue(film.is_file(), f"{folder} has no film")
                total += film.stat().st_size
        self.assertLess(total, 6_000_000, f"the three menus are {total / 1e6:.0f} MB")

    def test_every_tile_the_menu_wants_has_a_box_in_the_file(self):
        """A sheet redrawn with one tile missing would otherwise show the film with a square
        that does nothing, which reads as the mat being broken rather than the drawing."""
        import json
        from salaah.duamenu import CATEGORIES, SAYINGS
        from salaah.knowledge import TILES
        for folder, names in (("duas-menu", CATEGORIES), ("hadith-menu", SAYINGS),
                              ("knowledge", TILES)):
            with self.subTest(folder):
                boxes = json.loads((ASSETS / folder / "menu.json")
                                   .read_text(encoding="utf-8"))["tiles"]
                self.assertEqual(set(names), set(boxes),
                                 f"{folder}: the film and the menu disagree about the tiles")

    def test_a_menu_with_no_film_still_falls_back_to_its_pictures(self):
        """The wu'du steps have no animated sheet, so they are the live proof that the old way
        still works -- and if Harry draws one tomorrow, it will pick it up with no code change."""
        w = self.window()
        self.assertIsNone(w.wudu_menu.sheet, "the wu'du menu found a film it should not have")
        self.assertEqual(7, len(w.wudu_menu.tiles))
        for tile in w.wudu_menu.tiles:
            self.assertFalse(tile.quiet, "a still tile is not drawing itself")
            self.assertTrue(tile.path.is_file())


class PrayerPagesAreDrawnTest(unittest.TestCase):
    """Harry's five new prayer pages, in place of the arches the app used to draw for itself.

    The drawings carry the mosque and the arches; they do NOT carry the words any more. The
    number of units and what kind they are come from the pack and are written in, which is the
    whole reason for taking them out -- the drawings say SUNNAH and FARDH in English, and the
    mat is read in seven languages.

    Everything here is measured off the rendered screen or off the window's own state, not read
    back out of mosque.json, which would only prove the file agrees with itself.
    """

    def window(self, lang="en", mode="dark"):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme=mode, lang=lang, recitation=False, place="Bury"),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1080)
        w.show()
        w.tick()
        settle()
        self.addCleanup(lambda: shut(w))
        return w

    def page(self, w, prayer="isha"):
        w.open_prayer(prayer)
        settle()
        screen = getattr(w, "prayer_mosque", None)
        self.assertIsNotNone(screen, f"{prayer} did not open on a drawing")
        return screen

    @staticmethod
    def touch(screen, point):
        ev = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, QtCore.QPointF(point),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier)
        screen.mousePressEvent(ev)
        settle()

    def freeze(self, screen):
        """Stop the sky where it is, so two grabs can be compared."""
        held = screen.sky.now()
        patch = mock.patch.object(type(screen.sky), "now", staticmethod(lambda: held))
        patch.start()
        self.addCleanup(patch.stop)

    def test_each_prayer_opens_on_its_own_drawing_with_an_arch_for_each_unit(self):
        w = self.window()
        for prayer in PRAYERS:
            with self.subTest(prayer):
                screen = self.page(w, prayer)
                self.assertEqual(len(w.school.prayers[prayer]), len(screen.arches),
                                 f"{prayer} has an arch for every unit")

    def test_the_words_in_the_arches_come_from_the_pack(self):
        """Not from the drawing. Checked against what the rest of the app would say for the same
        unit, so a label that drifted away from the word used elsewhere shows up here."""
        w = self.window()
        screen = self.page(w, "isha")
        entries = w.school.prayers["isha"]
        for i, entry in enumerate(entries, start=1):
            with self.subTest(i):
                count, kind = screen.labels[str(i)]
                unit = w.content.units.get(entry.unit_id)
                self.assertEqual(str(unit.rakats), count)
                self.assertEqual(w.t(f"kind.{entry.kind}"), kind)

    def test_the_words_are_really_painted_into_the_arches(self):
        """The labels being set is not the same as their being on the screen. Taken away and the
        arch repainted, the inside of it has to change -- and change INSIDE the arch, not
        somewhere else on the page."""
        w = self.window()
        screen = self.page(w, "isha")
        said = dict(screen.labels)
        # The stars twinkle on their own clock, so two grabs a moment apart differ all over the
        # sky whatever the arches are doing. Held still, what is left between them is the words.
        screen.flutter.stop()
        self.freeze(screen)
        before = screen.grab().toImage()
        screen.set_labels({})
        settle()
        after = screen.grab().toImage()
        _, origin, scale = screen.placement()
        first = screen.arches[0].box
        inside = QtCore.QRect(origin.x() + int(first.x() * scale),
                              origin.y() + int(first.y() * scale),
                              int(first.width() * scale), int(first.height() * scale))
        changed, strayed = 0, 0
        for y in range(0, before.height(), 2):
            for x in range(0, before.width(), 2):
                if before.pixel(x, y) == after.pixel(x, y):
                    continue
                if inside.contains(x, y):
                    changed += 1
                elif not any(QtCore.QRect(origin.x() + int(a.box.x() * scale),
                                          origin.y() + int(a.box.y() * scale),
                                          int(a.box.width() * scale),
                                          int(a.box.height() * scale)).contains(x, y)
                             for a in screen.arches):
                    strayed += 1
        screen.set_labels(said, w.pack_face())
        self.assertGreater(changed, 40, "nothing was written inside the first arch")
        self.assertEqual(0, strayed, "the words were painted outside the arches")

    def test_the_prayers_name_is_written_on_the_dome_in_the_right_language(self):
        for lang, expected in (("en", "Isha"), ("ur", None)):
            with self.subTest(lang):
                w = self.window(lang=lang)
                screen = self.page(w, "isha")
                self.assertEqual(w.t("prayer.isha"), screen.time_text)
                if expected:
                    self.assertEqual(expected, screen.time_text)

    def test_the_words_change_with_the_language(self):
        """The reason the drawings gave up their lettering. English and Urdu have to differ, and
        the Urdu has to be the pack's own word rather than the English left in place."""
        english = self.window(lang="en")
        urdu = self.window(lang="ur")
        one, two = self.page(english, "isha"), self.page(urdu, "isha")
        self.assertNotEqual(one.labels, two.labels, "the arches say the same in both languages")
        self.assertNotEqual(one.time_text, two.time_text, "the dome says the same in both")
        for i in one.labels:
            with self.subTest(i):
                self.assertNotEqual(one.labels[i][1], two.labels[i][1],
                                    f"arch {i} is still in English on an Urdu mat")

    def test_touching_an_arch_starts_that_unit(self):
        """The arches are read off by position, so this is the test that the positions line up:
        the third arch has to start the third thing the prayer is made of, not the first."""
        for which in (1, 3, 5):
            with self.subTest(which):
                w = self.window()
                screen = self.page(w, "isha")
                middle = screen.arch_centre(str(which))
                self.assertIsNotNone(middle)
                self.touch(screen, middle)
                self.assertIsNotNone(w.session, "nothing started")
                self.assertEqual(w.school.prayers["isha"][which - 1].unit_id,
                                 w.session.unit.id)

    def test_it_walks_into_the_arch_on_the_way(self):
        w = self.window()
        screen = self.page(w, "isha")
        self.touch(screen, screen.arch_centre("2"))
        self.assertTrue(w.veil.running, "no walk into the arch")

    def test_a_drawing_that_disagrees_with_the_school_is_refused(self):
        """The words come from the pack and are written into whatever arches are there, so a
        drawing with one arch too many would quietly put Fardh where Nafl belongs. Better the
        old screen, which draws an arch per unit and cannot be out by one."""
        w = self.window()
        short = [e for e in w.school.prayers["isha"]][:-1]
        with mock.patch.dict(w.school.prayers, {"isha": short}):
            self.assertIsNone(w.prayer_page("isha"),
                              "a drawing with more arches than units was accepted")
            w.open_prayer("isha")
            settle()
        self.assertIsNone(w.prayer_mosque, "it should have fallen back to the drawn arches")
        self.assertIs(w.pick, w.stack.currentWidget(), "and still be on a usable screen")

    def test_the_main_prayer_page_behind_them_is_untouched(self):
        """Harry: "the only page that stays the same is the main prayer page". The five arches
        still say their own names, out of the drawing, and have no labels written over them."""
        w = self.window()
        self.assertEqual({}, w.mosque.labels, "something is being written over the main mosque")
        self.assertEqual([a.prayer for a in w.mosque.arches], list(PRAYERS))
