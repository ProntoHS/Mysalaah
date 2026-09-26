"""Drives the real screens without a display and saves screenshots to /tmp/salaah-shots."""
import json
import os
import time
import unittest
from unittest import mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from salaah.content import available_packs, load  # noqa: E402
from salaah.qt import API, QtCore, QtGui, QtWidgets, Qt  # noqa: E402
from salaah.render import MIN_ARABIC_PX  # noqa: E402
from salaah.settings import Settings  # noqa: E402
from salaah.ui import MainWindow  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SHOTS = Path("/tmp/salaah-shots") / API
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
CONTENT = load(ASSETS)
CONTENT_ARABIC = CONTENT.arabic


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
            self.assertTrue(w.slide.done.isVisible(), f"{prayer} {kind}")

    def test_the_counters_start_again_with_each_fardh_prayer(self):
        w = self.finish("asr", "farz")
        for _ in range(5):
            w.slide.tasbih.press()
        self.assertEqual(28, w.slide.tasbih.beads.left[0])
        w = self.finish("isha", "farz")
        self.assertEqual([33, 33, 33], w.slide.tasbih.beads.left)

    def test_completion_screen_shows_the_day_s_passage_and_saying(self):
        from datetime import datetime
        w = self.win
        w.start("fajr", w.school.prayers["fajr"][0])
        APP.processEvents()
        w.session.position = len(w.text_pages) - 1
        w.session.finished = True
        w.refresh()
        APP.processEvents()
        self.assertTrue(w.slide.done.isVisible())
        passage, saying = w.content.daily.for_day(datetime.now().date())
        self.assertEqual([saying["arabic"]], w.hadith_arabic.lines, "the saying in Arabic too")
        self.assertIn("Sahih", saying["reference"], "with a reference that can be checked")
        self.assertEqual(saying["reference"], w.hadith_source.text())
        self.assertEqual(saying["english"], w.hadith_text.text())
        buttons = [b.text() for b in w.slide.done.findChildren(QtWidgets.QPushButton)]
        self.assertEqual([], buttons, "no Done button; the Menu button leaves")
        self.assertEqual(passage["english"], w.quran_english.text())
        self.assertEqual([passage["arabic"]], w.quran_arabic.lines)
        self.assertIn(passage["reference"], w.quran_source.text())
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
        w = self.win
        for prayer in ("fajr", "maghrib"):
            w.open_prayer(prayer)
            APP.processEvents()
            labels = {x.objectName(): x for x in w.pick.findChildren(QtWidgets.QLabel)}
            self.assertEqual(w.t(f"prayer.{prayer}"), labels["h1"].text())
            self.assertEqual(CONTENT.prayer_names[prayer], labels["prayerNameBig"].text())
            # English one side, Arabic the other
            middle = w.pick.width() / 2
            self.assertLess(labels["h1"].mapTo(w.pick, labels["h1"].rect().center()).x(), middle)
            self.assertGreater(
                labels["prayerNameBig"].mapTo(w.pick, labels["prayerNameBig"].rect().center()).x(),
                middle)
            texts = [x.text() for x in w.pick.findChildren(QtWidgets.QLabel)]
            self.assertNotIn(w.t("prayer.pick"), texts, "no 'choose what to pray' line")
            back = next(b for b in w.pick.findChildren(QtWidgets.QPushButton)
                        if b.objectName() == "backButton")
            self.assertIn("QPushButton#backButton", w.styleSheet())
            back.click()
            APP.processEvents()
            self.assertIs(w.home, w.stack.currentWidget())

    def test_choosing_an_arch_starts_that_unit(self):
        from salaah.mosque import ArchButton
        w = self.win
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

    def test_the_time_is_larger_than_a_plain_fit_in_the_dome(self):
        from salaah.mosque import CLOCK_BOOST
        w = self.win
        w.tick()
        APP.processEvents()
        box = w.mosque.clock_box
        self.assertGreater(box.width(), 10, "the dome was found in the picture")
        font = w.mosque.clock_type(box, "21:45")
        plain = QtGui.QFont(font)
        plain.setPixelSize(max(8, int(font.pixelSize() / CLOCK_BOOST)))
        self.assertAlmostEqual(CLOCK_BOOST, font.pixelSize() / plain.pixelSize(), delta=0.03)
        # the plain size is the one that fits the dome's flat middle
        self.assertLessEqual(QtGui.QFontMetrics(plain).horizontalAdvance("21:45"),
                             box.width() * 0.95)

    def test_settings_is_two_columns_of_circles(self):
        from salaah.mosque import GearButton
        w = self.win
        w.open_settings()
        APP.processEvents()
        screen = w.settings_screen
        self.assertIs(screen, w.stack.currentWidget())

        choices = [b for b in screen.findChildren(QtWidgets.QRadioButton)
                   if b.objectName() == "choice"]
        self.assertGreater(len(choices), 8, "every option is a circle")
        self.assertTrue(any(b.isChecked() for b in choices), "the ones in use are filled in")
        self.assertEqual(1, len(screen.findChildren(GearButton)), "a cog, not the word Settings")

        # two columns: the options are split either side of the middle
        middle = screen.width() / 2
        lefts = [b for b in choices if b.mapTo(screen, b.rect().center()).x() < middle]
        rights = [b for b in choices if b.mapTo(screen, b.rect().center()).x() >= middle]
        self.assertTrue(lefts and rights, "options sit in both columns")

        home = next(b for b in screen.findChildren(QtWidgets.QPushButton)
                    if b.objectName() == "mainScreen")
        self.assertGreater(home.mapTo(screen, home.rect().center()).x(), middle, "top right")
        home.click()
        APP.processEvents()
        self.assertIs(w.home, w.stack.currentWidget(), "it goes back to the mosque")
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
        w = self.win
        app = QtWidgets.QApplication.instance()
        w.set_cursor("1")
        self.assertTrue(w.settings.cursor)
        self.assertIsNone(app.overrideCursor())      # pointer visible
        w.set_cursor("0")
        self.assertIsNotNone(app.overrideCursor())   # pointer hidden again
        w.set_cursor("1")                            # leave it visible for the next test
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.assertIs(w.home, w.stack.currentWidget())
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
        for lang in sorted(available_packs(ASSETS)):
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
        self.assertIs(w.home, w.stack.currentWidget())

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
        self.assertIs(w.home, w.stack.currentWidget())

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
        self.assertIs(w.home, w.stack.currentWidget())

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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
        return w

    def fardh(self, w, prayer="dhuhr"):
        entry = [e for e in w.school.prayers[prayer] if e.kind == "farz"][0]
        w.open_prayer(prayer)
        w.start(prayer, entry)
        APP.processEvents()

    def test_start_up_puts_the_compass_on_the_side_and_the_mosque_on_the_main(self):
        w = self.window()
        w.begin()
        self.assertIs(w.home, w.stack.currentWidget(), "the main screen is not held up")
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
        self.assertIs(w.home, w.stack.currentWidget())

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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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

    def test_arabic_only_is_the_default(self):
        w = self.window()
        self.fardh(w)
        self.go(w, "fatiha")
        self.assertTrue(w.slide.arabic.isVisible())
        self.assertFalse(w.slide.parallel.isVisible())
        self.assertIn("I intend", w.text_pages[0].arabic[0])

    def test_french_sits_beside_the_arabic(self):
        w = self.window(translation="fr")
        self.fardh(w)
        self.assertTrue(w.text_pages[0].arabic[0].startswith("J'ai l'intention d'accomplir 4 rak'ats fardh"))
        self.assertTrue(w.slide.arabic.isVisible(), "the intention is one sentence, full width")
        self.go(w, "fatiha")
        box = w.slide.parallel
        self.assertTrue(box.isVisible())
        self.assertFalse(w.slide.arabic.isVisible())
        self.assertEqual(7, len(box.arabic))
        self.assertIn("Louange à Dieu", box.meaning[1])
        px, rows, total = box.layout()
        self.assertLessEqual(total, box.height())
        self.assertGreaterEqual(box.latin_px(px), 30, "readable from standing")
        SHOTS.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(SHOTS / "40-french-fatiha.png"))

    def test_the_translation_lights_up_with_the_arabic(self):
        w = self.window(translation="en")
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
        w = self.window(translation="fr")
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

    def test_settings_offers_the_translations_in_a_dropdown(self):
        w = self.window()
        boxes = w.settings_screen.findChildren(QtWidgets.QComboBox)
        self.assertEqual(3, len(boxes),
                         "pickers, not rows of circles: the language, this one and the colours")
        picker = w.translation_picker
        labels = [picker.itemText(i) for i in range(picker.count())]
        for want in ("Arabic only", "English", "Français", "اردو"):
            self.assertIn(want, labels)
        self.assertEqual("Arabic only", picker.currentText(), "the setting it is on")
        self.assertEqual("none", picker.itemData(picker.currentIndex()))
        w.set_translation("fr")
        self.assertEqual("fr", w.settings.translation)
        w.set_translation("none")
        self.assertEqual("", w.settings.translation)


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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
        return w

    def test_the_compass_goes_on_the_small_screen_and_the_menu_on_the_big_one(self):
        w = self.window(side=True)
        w.begin()
        self.assertTrue(w.side.showing_compass, "the 7\" should show the Qibla at start-up")
        self.assertIs(w.home, w.stack.currentWidget(), "the big screen goes straight to the menu")
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
        self.assertIs(w.home, w.stack.currentWidget())

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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
        return w

    def words(self, w):
        texts = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel)]
        return texts + [x.text() for x in w.settings_screen.findChildren(QtWidgets.QAbstractButton)]

    def test_it_says_which_version_this_is(self):
        from salaah import __version__
        self.assertIn(f"Salaah version {__version__}", self.words(self.window()))

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
        for lang, pack in packs.items():
            self.assertIn("{number}", pack.ui.get("settings.version", ""), lang)
            self.assertNotIn("settings.exit", pack.ui, f"{lang} still offers the desktop")

    def test_no_choice_is_ever_squeezed(self):
        """A squeezed row of choices loses the bottom edge of its lettering, which is what the
        scroller is there to prevent. Checked in every language, from the mat's own screen down
        to a small window."""
        for lang in sorted(available_packs(ASSETS)):
            for size in ((1920, 1200), (1920, 1080), (1280, 720)):
                w = self.window(lang=lang, translation="en")
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
        w = self.window(translation="en")
        w.resize(1920, 1200)
        w.stack.setCurrentWidget(w.settings_screen)
        APP.processEvents()
        self.assertEqual(0, w.settings_scroll.verticalScrollBar().maximum(),
                         "everything should fit on the 16 inch screen without a scrollbar")

    def test_a_common_monitor_needs_no_scrolling_either(self):
        """1920x1080 used to be 80px short and scrolled; the rows taken out of Settings since
        have bought that back."""
        w = self.window(translation="en")
        w.resize(1920, 1080)
        w.stack.setCurrentWidget(w.settings_screen)
        APP.processEvents()
        self.assertEqual(0, w.settings_scroll.verticalScrollBar().maximum())

    def test_a_screen_too_short_for_it_scrolls_instead_of_squeezing(self):
        w = self.window(translation="en")
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
        return w

    def test_it_is_laid_out_right_to_left_in_the_arabic_face(self):
        from salaah.render import Fonts
        w = self.window(translation="ur")
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
        w = self.window(translation="en")
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.assertEqual(1, text.count("<span"), "only the prayer due")
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        for colour in painted:      # scaling shifts a channel by a point or two
            for got, want in ((colour.red(), mosque.GREEN.red()),
                              (colour.green(), mosque.GREEN.green()),
                              (colour.blue(), mosque.GREEN.blue())):
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
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        # the lettering really does need that room: it is boosted past the box's width
        font = screen.clock_type(box, "23:59")
        self.assertGreater(QtGui.QFontMetrics(font).horizontalAdvance("23:59"), box.width())
        self.assertLessEqual(QtGui.QFontMetrics(font).horizontalAdvance("23:59"), where.width())

    def test_the_line_between_the_columns_is_the_colour_of_the_words(self):
        """Black by day and white after dark, like everything else that is drawn."""
        from salaah import theme
        for mode in ("light", "dark"):
            w = self.window(translation="en", theme=mode)
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
        w.go_home()
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        them or they read as one lump."""
        from salaah.mosque import ArchButton
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        APP.processEvents()
        w.refresh()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.assertIs(w.home, w.stack.currentWidget())

    def test_nothing_to_photograph_is_not_a_crash(self):
        w = self.window()
        w.veil.start(QtGui.QPixmap(), QtCore.QRect(0, 0, 1920, 1200), QtCore.QPoint(10, 10))
        self.assertFalse(w.veil.running)
        w.veil.start(w.stack.grab(), QtCore.QRect(0, 0, 2, 2), QtCore.QPoint(1, 1))
        self.assertFalse(w.veil.running)


class ArchColoursTest(unittest.TestCase):
    """The unit arches are an outline on the page they sit on: white inside by day, black
    inside after dark. They used to be a cream panel, which showed as a grey slab."""

    def arch(self, **settings):
        from salaah.mosque import ArchButton
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(**{"theme": "light", "recitation": False, **settings}),
                       scale=1.0, save_settings=False, aspect=None)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        """The screen it fills is the seven-line one, where the leading cost the most."""
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
            for translation in ("", "en"):
                w = MainWindow(load(ASSETS), available_packs(ASSETS),
                               Settings(theme="light", recitation=False, arabic_font=key,
                                        translation=translation),
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
                        box = w.slide.parallel if translation else w.slide.arabic
                        if box.isVisible() and (box.arabic if translation else box.lines):
                            self.check(box, translation, f"{key}/{translation or 'arabic'} {step}")
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
                                   "translation": "en", **settings}),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
    """Tapping one of a prayer's unit arches walks into it the same way the mosque does."""

    def window(self):
        w = MainWindow(load(ASSETS), available_packs(ASSETS),
                       Settings(theme="light", recitation=False), scale=1.0,
                       save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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

    def test_the_headings_are_white_on_a_box_and_bigger_than_the_words_under_them(self):
        for mode, chip in (("light", "#000000"), ("dark", "#262626")):
            w = self.window(theme=mode)
            self.at_the_end(w)
            heads = [x for x in w.slide.done.findChildren(QtWidgets.QLabel)
                     if x.objectName() == "dailyHead"]
            self.assertEqual(2, len(heads), "one heading over each passage")
            for head in heads:
                background, tally = self.painted(head)
                self.assertEqual(chip, background, f"{mode}: {head.text()!r} sits on {background}")
                self.assertIn("#ffffff", tally, f"{mode}: {head.text()!r} is not in white")
            english = [x for x in w.slide.done.findChildren(QtWidgets.QLabel)
                       if x.objectName() == "dailyEnglish"][0]
            # The heading used to be the bigger of the two, back when the meaning was a small
            # caption. Now the meaning is lettered to match the Arabic, so the heading is the
            # smaller: it is a label on the passage, not a title competing with it.
            self.assertLess(heads[0].font().pixelSize(), english.font().pixelSize(),
                            "the passage should be lettered larger than the label over it")

    def test_there_is_no_prayer_complete_heading(self):
        w = self.window()
        self.at_the_end(w)
        words = [x.text() for x in w.slide.done.findChildren(QtWidgets.QLabel) if x.text()]
        self.assertFalse([x for x in words if "complete" in x.lower()],
                         "the 'Prayer complete' heading is meant to be gone")
        self.assertFalse([x for x in w.slide.done.findChildren(QtWidgets.QLabel)
                          if x.objectName() == "doneTitle"])
        for lang, pack in available_packs(ASSETS).items():
            self.assertNotIn("player.done_title", pack.ui, f"{lang} still carries the wording")

    def test_the_two_passages_are_still_there(self):
        w = self.window()
        self.at_the_end(w)
        self.assertTrue(w.slide.done.isVisible())
        self.assertTrue(w.hadith_arabic.lines, "no hadith")
        self.assertTrue(w.quran_arabic.lines, "no Qur'an passage")
        self.assertTrue(w.hadith_source.text())
        self.assertTrue(w.quran_source.text())

    def pairs(self, w):
        """Every passage against the longest saying, and every saying against the longest
        passage. Each kind against the worst of the other is the case that binds; all of them
        against all of them would be two and a half thousand combinations for no more cover."""
        passages, sayings = list(w.content.daily.passages), list(w.content.daily.sayings)
        longest = lambda items: max(items, key=lambda x: len(x["english"]) + len(x["arabic"]))
        return ([(p, longest(sayings)) for p in passages]
                + [(longest(passages), s) for s in sayings])

    def show(self, w, passage, saying):
        w.quran_arabic.set_lines([passage["arabic"]])
        w.quran_english.setText(passage["english"])
        w.hadith_arabic.set_lines([saying["arabic"]])
        w.hadith_text.setText(saying["english"])
        w.match_daily_sizes()
        APP.processEvents()

    def test_the_arabic_and_its_meaning_are_set_at_one_size(self):
        """They are quotations read one under the other, so the meaning is not a caption: it is
        lettered the same size as the Arabic above it, and both columns agree, whichever pair the
        day brings up."""
        w = self.window()
        self.at_the_end(w)
        for passage, saying in self.pairs(w):
            self.show(w, passage, saying)
            size = w.quran_arabic.fitted_size()
            what = f"{passage['reference']} with {saying['reference']}"
            self.assertEqual(size, w.hadith_arabic.fitted_size(),
                             f"{what}: the two columns' Arabic is lettered differently")
            for label in (w.quran_english, w.hadith_text):
                self.assertEqual(size, label.font().pixelSize(),
                                 f"{what}: the meaning is {label.font().pixelSize()}px against "
                                 f"{size}px of Arabic")

    def test_no_pair_is_lettered_too_small_to_read_from_the_mat(self):
        w = self.window()
        self.at_the_end(w)
        floor = int(MIN_ARABIC_PX * w.quran_arabic.scale)
        for passage, saying in self.pairs(w):
            self.show(w, passage, saying)
            self.assertGreaterEqual(
                w.quran_arabic.fitted_size(), floor,
                f"{passage['reference']} with {saying['reference']}: down to "
                f"{w.quran_arabic.fitted_size()}px, under the {floor}px we hold to")

    def test_no_meaning_is_cut_off_at_the_foot_of_its_box(self):
        """Checked by looking at the pixels rather than by asking the same measurement that chose
        the size, which would only agree with itself."""
        w = self.window()
        self.at_the_end(w)

        def reaches_the_edge(widget):
            picture = widget.grab().toImage().convertToFormat(
                QtGui.QImage.Format.Format_ARGB32)
            for y in (picture.height() - 1, picture.height() - 2):
                for x in range(0, picture.width(), 2):
                    dot = picture.pixelColor(x, y)
                    if dot.alpha() > 128 and dot.lightness() < 128:
                        return True        # lettering on the last row: something is cut
            return False

        for passage, saying in self.pairs(w):
            self.show(w, passage, saying)
            for label in (w.quran_english, w.hadith_text):
                self.assertFalse(reaches_the_edge(label),
                                 f"{passage['reference']} with {saying['reference']}: the meaning "
                                 f"runs off the bottom at {w.quran_arabic.fitted_size()}px")


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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
        return w

    def buttons(self, w):
        return [b.text() for b in w.settings_screen.findChildren(QtWidgets.QAbstractButton)
                if b.text()]

    def test_no_show_the_qibla_button(self):
        """With a 7 inch screen the compass is on it the whole time Settings is up."""
        w = self.window()
        self.assertFalse([x for x in self.buttons(w) if "Qibla" in x and "how" in x.lower()],
                         "the 'Show the Qibla' button is meant to be gone")
        self.assertTrue(w.side.showing_compass or not w.settings.qibla_start,
                        "and the compass really is on the small screen")
        for lang, pack in available_packs(ASSETS).items():
            self.assertNotIn("settings.qibla_show", pack.ui, f"{lang} still carries the wording")

    def test_the_qibla_rows_that_matter_are_still_there(self):
        w = self.window()
        words = [x.text() for x in w.settings_screen.findChildren(QtWidgets.QLabel) if x.text()]
        words += self.buttons(w)
        self.assertTrue([x for x in words if "Qibla" in x], "the Qibla section went with it")
        self.assertTrue([x for x in words if "118" in x], "the bearing should still be shown")

    def test_the_recitation_hint_no_longer_points_at_a_button_that_is_gone(self):
        for lang, pack in available_packs(ASSETS).items():
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
                       Settings(theme="light", recitation=False, lang=lang,
                                translation=lang if lang in content.translations else ""),
                       scale=1.0, save_settings=False, aspect=None, side=True)
        w.resize(1920, 1200)
        w.show()
        APP.processEvents()
        w.refresh()
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
        return w

    def test_all_six_are_offered(self):
        packs = available_packs(ASSETS)
        self.assertEqual({"en", "fr", "ur", "es", "zh", "hi"}, set(packs))
        # Counted against English rather than against a number written in here: a hard-coded
        # count only ever says "someone added a string", which is not a fault.
        english = packs["en"].ui
        for lang, pack in packs.items():
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
            for key, english in packs["en"].ui.items():
                wanted = set(re.findall(r"\{(\w+)\}", english))
                got = set(re.findall(r"\{(\w+)\}", pack.ui[key]))
                self.assertEqual(wanted, got, f"{lang} {key}: wanted {wanted}, got {got}")

    def test_the_menus_are_drawn_in_a_face_that_has_the_letters(self):
        for lang in sorted(available_packs(ASSETS)):
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
        self.assertEqual(6, picker.count())
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
        from salaah.mosque import ArchButton
        from salaah.render import Fonts
        w = self.window("hi")
        w.open_prayer("dhuhr")
        APP.processEvents()
        arches = w.pick.findChildren(ArchButton)
        self.assertTrue(arches)
        for arch in arches:
            self.assertEqual(Fonts.scripts["devanagari"], arch.family,
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
        self.addCleanup(lambda: (w.close(), w.deleteLater(), APP.processEvents()))
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
        APP.processEvents()
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.assertTrue(w.clock.isActive())
        self.assertTrue(w.mosque.flutter.isActive())
        self.press(w)
        self.assertFalse(w.clock.isActive(), "the ten-second clock is still running")
        self.assertFalse(w.mosque.flutter.isActive(), "the sky is still animating")
        self.press(w)
        self.assertTrue(w.clock.isActive())
        self.assertTrue(w.mosque.flutter.isActive())

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
        self.assertIs(w.home, w.stack.currentWidget())
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

    def test_it_wakes_at_the_main_menu_rather_than_where_it_was_left(self):
        """The mat is picked up by whoever prays next. A screen left open in the middle of
        someone else's Settings is no way to greet them."""
        w = self.window()
        w.open_settings()
        APP.processEvents()
        self.assertIsNot(w.home, w.stack.currentWidget())
        self.press(w)
        self.press(w)
        self.assertIs(w.home, w.stack.currentWidget(), "it woke up back in Settings")

    def test_waking_from_the_end_of_a_prayer_forgets_the_prayer(self):
        w = self.window()
        self.to_the_end(w)
        self.press(w)
        self.press(w)
        self.assertIs(w.home, w.stack.currentWidget())
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
        self.assertTrue(w.side.showing_compass,
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.addCleanup(lambda: (w.shutdown(), w.close(), w.deleteLater(), APP.processEvents()))
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
        self.assertIn("TIME TO PRAY", self.words(w))
        self.assertEqual(["azaan.mp3"], w.call.played)

    def test_fajr_is_announced_but_not_called(self):
        """The Fajr azaan has a line the others do not. Calling it with the wrong words would
        be worse than not calling it, so for now the mat says it is time and stays quiet."""
        w = self.window()
        self.at(w, "fajr")
        self.assertIsNotNone(w.call_box, "Fajr should still be announced")
        self.assertEqual([], w.call.played, "and should not play the ordinary azaan")

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
        self.assertIs(w.home, w.stack.currentWidget(), "and come back at the mosque")
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
