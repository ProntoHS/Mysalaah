"""Core checks. Run on the Pi or any computer: python3 -m unittest discover -s tests"""
import os
import unittest
from unittest import mock
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from salaah.buttons import BACK, NEXT, PressFilter
from salaah.content import PRAYERS, available_packs, load, UnitEntry
from salaah.pages import build_pages, posture_image
from salaah.qt import QtWidgets
from salaah.session import Debouncer, PrayerSession, assign_rakats
from salaah.validator import check

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CONTENT = load(ASSETS)

# Several of these load fonts or build a widget, which needs an application to exist first --
# loading a font without one segfaults. It used to work by luck: some other test class happened
# to make one earlier, and unittest runs classes in alphabetical order, so adding a class whose
# name sorted earlier moved the luck and the suite started crashing. Made here, once, on purpose.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ContentTest(unittest.TestCase):
    def test_loads_everything(self):
        self.assertEqual(35, len(CONTENT.steps))
        self.assertEqual({"two_rakat", "three_farz", "three_witr", "four_farz", "four_sunnah"}, set(CONTENT.units))
        for step in CONTENT.steps.values():
            self.assertIn(step.posture, ("standing", "ruku", "sujood", "sitting", "salam"))
        en = available_packs(ASSETS)["en"]
        self.assertEqual("Rakat 2 of 4", en.t("player.rakat", n=2, total=4))

    def test_every_prayer_has_an_arabic_name(self):
        for prayer in PRAYERS:
            name = CONTENT.prayer_names.get(prayer, "")
            self.assertTrue(name, prayer)
            self.assertTrue(any("\u0621" <= ch <= "\u064A" for ch in name), f"{prayer}: {name}")

    def test_witr_has_the_qunut_in_the_third_rakat(self):
        """After the surah in the last rakat: the takbir with hands raised, then the dua."""
        from salaah.session import PrayerSession as Session
        pages = Session(CONTENT.units["three_witr"], CONTENT).pages
        third = [p for p in pages if p.rakat == 3]
        recitations = [p.step.recitation for p in third]
        self.assertIn("qunut_1", recitations)
        self.assertIn("qunut_2", recitations)
        surah = recitations.index("ikhlas")
        qunut = recitations.index("qunut_1")
        ruku = next(i for i, p in enumerate(third) if p.step.posture == "ruku")
        self.assertLess(surah, qunut, "the dua comes after the surah")
        self.assertLess(qunut, ruku, "and before bowing")
        self.assertEqual("takbir", recitations[qunut - 1], "with a takbir before it")

    def test_maghrib_farz_is_three_rakats(self):
        self.assertEqual(UnitEntry("farz", "three_farz"), CONTENT.schools["hanafi"].prayers["maghrib"][0])

    def test_the_content_passes_every_check(self):
        """Both findings from the old slides are fixed: the qunut is in the last rakat of the
        witr only, and every unit has the takbir between the last sujood and the tashahhud."""
        self.assertEqual([], check(CONTENT))

    def test_the_qunut_is_only_in_the_last_rakat(self):
        from salaah.session import PrayerSession as Session
        for unit in CONTENT.units.values():
            for page in Session(unit, CONTENT).pages:
                if page.step.recitation.startswith("qunut"):
                    self.assertEqual(unit.rakats, page.rakat, f"{unit.id}/{page.step.id}")

    def test_every_unit_takes_a_takbir_into_the_tashahhud(self):
        from salaah.session import PrayerSession as Session
        for unit in CONTENT.units.values():
            pages = Session(unit, CONTENT).pages
            for i, page in enumerate(pages[1:], start=1):
                if page.step.recitation == "tashahhud":
                    self.assertEqual("takbir", pages[i - 1].step.recitation,
                                     f"{unit.id}: nothing said on the way into the tashahhud")

    def test_catches_the_pi_maghrib_bug(self):
        school = CONTENT.schools["hanafi"]
        broken = replace(school, prayers={**school.prayers, "maghrib": [UnitEntry("farz", "four_farz")]})
        problems = check(replace(CONTENT, schools={"hanafi": broken}))
        self.assertIn("hanafi/maghrib: farz uses 4-rakat unit, expected 3", problems)


class StepListTest(unittest.TestCase):
    """The prayer follows the steps on quranmualim.com/arabic-prayer: takbir, the opening dua,
    seeking refuge, Al-Fatiha (and a surah), ruku, rising, sujood, the dua between the sujood,
    tashahhud, salawat, salam."""

    def recitations(self, unit_id):
        return [p.step.recitation for p in PrayerSession(CONTENT.units[unit_id], CONTENT).pages]

    def test_every_unit_opens_in_that_order(self):
        for unit in CONTENT.units:
            self.assertEqual(["intention", "takbir", "istiftah", "taawwudh_basmala", "fatiha"],
                             self.recitations(unit)[:5], unit)

    def test_it_ends_salawat_rabbana_atina_salam(self):
        for unit in CONTENT.units:
            r = self.recitations(unit)
            self.assertEqual(["tashahhud", "salawat", "rabbana_atina", "salam"], r[-4:], unit)
            for gone in ("wajjahtu", "thana", "rabbij_alni"):
                self.assertNotIn(gone, r, unit)
                self.assertNotIn(gone, CONTENT.arabic)

    def test_the_dua_between_the_sujood_has_a_takbir_either_side(self):
        for unit in CONTENT.units.values():
            pages = PrayerSession(unit, CONTENT).pages
            r = [p.step.recitation for p in pages]
            duas = [i for i, x in enumerate(r) if x == "jalsa_dua"]
            self.assertEqual(unit.rakats, len(duas), f"{unit.id}: once in every rakat")
            for i in duas:
                self.assertEqual(["sujood_tasbih", "takbir", "jalsa_dua", "takbir", "sujood_tasbih"],
                                 r[i - 2:i + 3], unit.id)
                self.assertEqual("sitting", pages[i].step.posture)
                self.assertEqual(1, pages[i - 1].step.repeat, "one takbir each side, not X2")
                self.assertEqual(2, pages[i].step.repeat, "rabbi ghfir li is said twice (X2)")

    def test_the_opening_dua_and_refuge_are_only_in_the_first_rakat(self):
        for unit in CONTENT.units.values():
            for page in PrayerSession(unit, CONTENT).pages:
                if page.step.recitation in ("istiftah", "taawwudh_basmala"):
                    self.assertEqual(1, page.rakat, f"{unit.id}/{page.step.id}")

    def test_every_screen_of_every_prayer_has_a_recording(self):
        from salaah.render import load_timings
        recorded = set(load_timings(ASSETS))
        unrecorded = {p.step.recitation for u in CONTENT.units.values()
                      for p in PrayerSession(u, CONTENT).pages} - recorded
        self.assertEqual({"intention"}, unrecorded, "only the intention, which is read, not recited")


class AameenTest(unittest.TestCase):
    def test_aameen_follows_every_fatiha_standing(self):
        pack = available_packs(ASSETS)["en"]
        for unit in CONTENT.units.values():
            pages = build_pages(PrayerSession(unit, CONTENT).pages, CONTENT, pack)
            fatihas = [i for i, p in enumerate(pages) if p.recitation == "fatiha"]
            self.assertEqual(unit.rakats, len(fatihas), unit.id)
            for i in fatihas:
                after = pages[i + 1]
                self.assertEqual("ameen", after.recitation, f"{unit.id} rakat {pages[i].rakat}")
                self.assertEqual(pages[i].posture_image, after.posture_image, "still standing")
                self.assertEqual(pages[i].rakat, after.rakat)
        self.assertEqual(["آمِين"], CONTENT.arabic["ameen"])

    def test_every_recording_is_in_the_tap_along_list(self):
        from salaah.render import load_timings
        from salaah.timing import ORDER
        self.assertEqual(set(), set(load_timings(ASSETS)) - set(ORDER))


class NewScreensTest(unittest.TestCase):
    """The intention first, the subhanaka opening, rabbi ghfir li X2, rabbana atina after salawat."""

    def pages(self, unit_id, intention=None):
        pack = available_packs(ASSETS)["en"]
        return build_pages(PrayerSession(CONTENT.units[unit_id], CONTENT).pages, CONTENT, pack,
                           intention=intention)

    def test_the_intention_is_the_first_screen_standing_with_arms_down(self):
        for unit in CONTENT.units:
            first = self.pages(unit, "I intend to perform 2 Rakats Sunnah of Fajr")[0]
            self.assertEqual(["I intend to perform 2 Rakats Sunnah of Fajr"], first.arabic)
            self.assertTrue(first.latin, "written left to right, in English")
            self.assertEqual("postures/standing_arms_down.png", first.posture_image)
            self.assertEqual(1, first.rakat)

    def test_the_opening_dua_is_subhanaka_in_three_lines(self):
        lines = CONTENT.arabic["istiftah"]
        self.assertEqual(3, len(lines))
        self.assertTrue(lines[0].startswith("سُبْحَانَكَ"))
        self.assertTrue(lines[-1].endswith("غَيْرُكَ"))

    def test_rabbana_atina_is_sat_like_the_salawat(self):
        for unit in CONTENT.units:
            pages = self.pages(unit)
            i = next(n for n, p in enumerate(pages) if p.recitation == "rabbana_atina")
            self.assertEqual("salawat", pages[i - 1].recitation)
            self.assertEqual(pages[i - 1].posture_image, pages[i].posture_image, "same picture")
            self.assertEqual(2, len(pages[i].arabic))

    def test_rabbi_ghfir_li_is_one_short_line(self):
        self.assertEqual(["رَبِّ اغْفِرْ لِي"], CONTENT.arabic["jalsa_dua"])


class TextPageTest(unittest.TestCase):
    def test_every_step_has_arabic_and_a_posture(self):
        pack = available_packs(ASSETS)["en"]
        for unit in CONTENT.units.values():
            s = PrayerSession(unit, CONTENT)
            for page in build_pages(s.pages, CONTENT, pack):
                self.assertTrue(page.arabic, f"{unit.id}/{page.ref}: no Arabic")
                self.assertTrue((ASSETS / page.posture_image).is_file(), page.posture_image)

    def test_a_recitation_is_one_screen(self):
        pack = available_packs(ASSETS)["en"]
        for unit in CONTENT.units.values():
            pages = build_pages(PrayerSession(unit, CONTENT).pages, CONTENT, pack)
            for page in pages:
                self.assertEqual(1, page.pages_in_step, f"{unit.id}/{page.ref} is split")
                if page.latin:
                    continue                      # the intention: one sentence, not from the file
                self.assertEqual(len(CONTENT.arabic[page.step.recitation]), len(page.arabic))
                self.assertEqual(0, page.first_segment)

    def test_hands_are_down_after_bowing(self):
        """Standing after bowing, and the takbir down into sujood, use the side view with the
        hands at the sides."""
        pack = available_packs(ASSETS)["en"]
        for unit in CONTENT.units.values():
            pages = build_pages(PrayerSession(unit, CONTENT).pages, CONTENT, pack)
            firsts = [p for p in pages if p.is_first_of_step]
            for i, page in enumerate(firsts):
                after_bowing = i > 0 and firsts[i - 1].step.posture == "ruku"
                itidal = page.step.recitation == "tasmi_tahmid"
                if itidal or after_bowing or (i > 0 and firsts[i - 1].step.recitation == "tasmi_tahmid"
                                              and page.step.posture == "standing"):
                    self.assertEqual("postures/standing_itidal.png", page.posture_image,
                                     f"{unit.id}/{page.step.id}")
            # and the hands are folded again for the recitation in a new rakat
            for page in firsts:
                if page.step.recitation in ("fatiha", "istiftah", "taawwudh_basmala"):
                    self.assertEqual("postures/standing_folded.png", page.posture_image,
                                     f"{unit.id}/{page.step.id}")

    def test_the_salam_is_one_step_said_twice(self):
        """One picture shows the turn to each side, so the prayer ends on a single screen."""
        for unit in CONTENT.units.values():
            pages = build_pages(PrayerSession(unit, CONTENT).pages, CONTENT, available_packs(ASSETS)["en"])
            salam = [p for p in pages if p.step.posture == "salam"]
            self.assertEqual(1, len(salam), unit.id)
            self.assertEqual("postures/salam.png", salam[0].posture_image)
            self.assertEqual(2, salam[0].repeat, "said to the right, then the left")
            self.assertIs(salam[0], pages[-1], f"{unit.id} ends with the salam")

    def test_splitting_still_works_if_it_is_ever_wanted(self):
        from salaah.pages import group_segments
        ar = [f"line {i}" for i in range(7)]
        self.assertEqual([range(0, 7)], group_segments(ar, ar, 2))
        self.assertEqual([range(0, 2), range(2, 4), range(4, 6), range(6, 7)],
                         group_segments(ar, ar, 2, one_page=False))


class AudioTest(unittest.TestCase):
    def setUp(self):
        from salaah.render import load_timings
        self.all = load_timings(ASSETS)
        self.t = self.all["fatiha"]

    def test_every_recording_matches_its_text(self):
        self.assertEqual({"takbir", "istiftah", "taawwudh_basmala", "fatiha", "kawthar", "ikhlas",
                          "ruku_tasbih", "tasmi_tahmid", "sujood_tasbih", "jalsa_dua",
                          "tashahhud", "salawat", "salam", "qunut_1", "qunut_2",
                          "falaq", "nas", "rabbana_atina", "istighfar", "dhikr_salam",
                          "subhanallah", "alhamdulillah", "allahu_akbar", "dhikr_tahlil",
                          "ameen", "ayat_kursi"}, set(self.all))
        for key, timings in self.all.items():
            verses = CONTENT.arabic[key]
            self.assertEqual(len(verses), len(timings.segments), key)
            for i, verse in enumerate(verses):
                self.assertEqual(len(verse.split()), len(timings.words[i]), f"{key} verse {i + 1}")

    def test_timings_run_forwards(self):
        for key, timings in self.all.items():
            last = -1.0
            for i, seg in enumerate(timings.segments):
                # A zero-length span means that segment is not in the recording at all.
                self.assertLessEqual(seg.start, seg.end, f"{key} verse {i + 1}")
                self.assertGreaterEqual(seg.start, last, f"{key} verses are in order")
                last = seg.end
                for w in timings.words[i]:
                    self.assertLessEqual(seg.start - 0.01, w.start)
                    self.assertLessEqual(w.end, seg.end + 0.01)

    def test_a_recording_may_cover_only_part_of_the_text(self):
        """A recording need not hold every line on a screen. Lines it does not cover get a
        moment with no length, so nothing is highlighted for them rather than the wrong word
        being lit. Nothing uses that at the moment, but the tool and the player both support it."""
        from salaah.audio import Span, Timings
        timings = Timings(audio=self.all["fatiha"].audio,
                          segments=[Span(0.0, 3.0), Span(3.0, 3.0)],
                          words=[[Span(0.0, 3.0)], [Span(3.0, 3.0)]])
        self.assertIsNotNone(timings.word_at(0, 1.0))
        self.assertIsNone(timings.word_at(1, 3.0), "a line with no audio never lights up")
        self.assertEqual(3.0, timings.span_for(0, 1).end)

    def test_the_taawwudh_screen_is_one_line(self):
        """The basmala was taken off this screen: it is recited at the start of the Fatiha,
        which is the screen straight after, and the recording matches."""
        self.assertEqual(1, len(CONTENT.arabic["taawwudh_basmala"]))
        timings = self.all["taawwudh_basmala"]
        self.assertEqual(1, len(timings.segments))
        self.assertGreater(timings.segments[0].end, 1.0)

    def test_recordings_cover_their_audio(self):
        """The last verse should end near the end of the recording. The slack allows for
        trailing silence, but still catches a file missing its basmala (about five seconds)
        or a recording of something else entirely."""
        import subprocess
        for key, timings in self.all.items():
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(timings.audio)], capture_output=True, text=True)
            if out.returncode != 0:
                self.skipTest("ffprobe not available")
            duration = float(out.stdout.strip())
            self.assertLess(abs(duration - timings.segments[-1].end), 2.5, key)

    def test_a_screenful_plays_as_one_span(self):
        span = self.t.span_for(0, 2)
        self.assertEqual(self.t.segments[0].start, span.start)
        self.assertEqual(self.t.segments[2].end, span.end)
        self.assertIsNone(self.t.span_for(0, 99))

    def test_rising_from_ruku_is_both_phrases_and_all_of_it_is_recorded(self):
        """Praying alone, both are said: sami'a llahu liman hamidah, then rabbana laka l-hamd.
        The recording holds both, so each line has its own stretch of audio."""
        self.assertEqual(["سَمِعَ ٱللَّهُ لِمَنۡ حَمِدَهُۥ", "رَبَّنَا لَكَ ٱلۡحَمۡدُ"],
                         CONTENT.arabic["tasmi_tahmid"])
        t = self.all["tasmi_tahmid"]
        self.assertEqual(2, len(t.segments))
        for seg in t.segments:
            self.assertGreater(seg.end - seg.start, 1.0)

    def test_ayat_al_kursi_is_split_where_the_reciter_pauses(self):
        """2:255 in nine lines, one per pause mark, and the recording's eight pauses fall
        exactly between them."""
        lines = CONTENT.arabic["ayat_kursi"]
        self.assertEqual(9, len(lines))
        import re

        def bare(text):          # letters only, so the test doesn't depend on how marks are typed
            return re.sub(r"[^\u0621-\u064A ]", "", text.replace("\u0671", "\u0627"))
        self.assertTrue(bare(lines[0]).startswith("الله لا إله إلا هو الحي القيوم"), bare(lines[0]))
        self.assertTrue(bare(lines[-1]).endswith("العلي العظيم"), bare(lines[-1]))
        t = self.all["ayat_kursi"]
        for a, b in zip(t.segments, t.segments[1:]):
            self.assertLess(a.end, b.start, "a real pause between every line")

    def test_fatiha_waits_through_the_breath_in_the_last_verse(self):
        """This reciter breathes after 'an'amta 'alayhim'. No word is lit in the silence."""
        t = self.all["fatiha"]
        last = t.words[6]
        self.assertLess(last[3].end, last[4].start - 0.3, "a gap between the 4th and 5th word")
        self.assertGreater(t.segments[3].start, t.segments[2].start + 1.0,
                           "verses 3 and 4 run together but each gets its own time")

    def test_the_qunut_is_one_recording_cut_between_its_two_screens(self):
        """Both halves come from witr_qunut.mp3, cut in the pause before the second Allahumma,
        so neither screen starts or ends part way through a word."""
        first, second = self.all["qunut_1"], self.all["qunut_2"]
        self.assertEqual(3, len(first.segments))
        self.assertEqual(3, len(second.segments))
        self.assertAlmostEqual(11.1, first.segments[-1].end, delta=0.2)
        self.assertGreater(second.segments[0].start, 0.1, "starts in the silence it was cut in")

    def test_a_repeated_phrase_plays_as_many_times_as_the_circle_says(self):
        """X3 plays three times with a breath between; the position starts from the top each
        time, so the red follows every saying. A 'sleep' stands in for the audio player."""
        import time
        from salaah import audio
        from salaah.audio import Recitation, Span
        audio.PLAYERS["test"] = lambda f, s, d, v: ["sleep", f"{d:.2f}"]
        old_rest, audio.REST = audio.REST, 0.1
        try:
            r = Recitation(player="test")
            self.assertTrue(r.play(self.t.audio, Span(0.0, 0.25), times=3))
            starts, was_sounding, deadline = 0, False, time.monotonic() + 3
            while r.busy and time.monotonic() < deadline:
                p = r.position()
                if p is not None and not was_sounding:
                    starts += 1
                    self.assertLess(p, 0.1, "each saying starts from the top")
                was_sounding = p is not None
                time.sleep(0.01)
            self.assertEqual(3, starts, "said three times")
            self.assertFalse(r.busy)
            self.assertIsNone(r.position())

            self.assertTrue(r.play(self.t.audio, Span(0.0, 0.25), times=3))
            r.stop()                                  # moving on stops the repeats too
            self.assertFalse(r.busy)
        finally:
            audio.PLAYERS.pop("test", None)
            audio.REST = old_rest

    def test_the_x3_and_x2_screens_ask_for_repeats(self):
        pack = available_packs(ASSETS)["en"]
        pages = build_pages(PrayerSession(CONTENT.units["two_rakat"], CONTENT).pages, CONTENT, pack)
        repeats = {p.step.recitation: p.repeat for p in pages}
        self.assertEqual(3, repeats["ruku_tasbih"])
        self.assertEqual(3, repeats["sujood_tasbih"])
        self.assertEqual(2, repeats["salam"])
        self.assertEqual(1, repeats["fatiha"])

    def test_word_lookup(self):
        first = self.t.words[0][0]
        self.assertEqual(0, self.t.word_at(0, first.start + 0.01))
        self.assertIsNone(self.t.word_at(0, self.t.segments[-1].end + 5))
        self.assertIsNone(self.t.word_at(99, 1.0))

    def test_every_player_is_told_the_volume(self):
        from salaah.audio import PLAYERS
        for name, build in PLAYERS.items():
            quiet = " ".join(build(self.t.audio, 1.0, 2.0, 20))
            loud = " ".join(build(self.t.audio, 1.0, 2.0, 100))
            self.assertNotEqual(quiet, loud, f"{name} takes notice of the volume")

    def test_volume_is_kept_inside_nought_to_a_hundred(self):
        from salaah.audio import Recitation, clamp_volume
        self.assertEqual(0, clamp_volume(-30))
        self.assertEqual(100, clamp_volume(140))
        player = Recitation(player="ffplay", volume=250)
        self.assertEqual(100, player.volume)
        player.set_volume(-5)
        self.assertEqual(0, player.volume)

    def test_turned_all_the_way_down_plays_nothing(self):
        from salaah.audio import Recitation
        player = Recitation(player="ffplay", volume=0)
        self.assertFalse(player.play(self.t.audio, self.t.segments[0]))
        self.assertFalse(player.playing)


class DailyTest(unittest.TestCase):
    def test_every_saying_has_arabic_english_and_a_reference(self):
        for saying in CONTENT.daily.sayings:
            self.assertTrue(saying["arabic"].strip(), saying["reference"])
            self.assertTrue(saying["english"].strip(), saying["reference"])
            self.assertRegex(saying["reference"], r"^Sahih (al-Bukhari|Muslim) \d+$")
            self.assertLess(len(saying["arabic"]), 200, "short enough for the screen")

    def test_every_passage_has_arabic_english_and_a_reference(self):
        for passage in CONTENT.daily.passages:
            self.assertTrue(passage["arabic"].strip(), passage["reference"])
            self.assertTrue(passage["english"].strip(), passage["reference"])
            self.assertRegex(passage["reference"], r"^\d+:\d+$")

    def test_the_pair_changes_by_day_and_holds_all_day(self):
        from datetime import date, timedelta
        first = CONTENT.daily.for_day(date(2026, 9, 16))
        again = CONTENT.daily.for_day(date(2026, 9, 16))
        tomorrow = CONTENT.daily.for_day(date(2026, 9, 16) + timedelta(days=1))
        self.assertEqual(first, again)
        self.assertNotEqual(first, tomorrow)

    @staticmethod
    def words(arabic: str) -> list[str]:
        """The Arabic words, with the vowel marks and the recitation marks taken off."""
        import re
        import unicodedata
        marks = {chr(c) for c in range(0x600, 0x900)
                 if unicodedata.category(chr(c)) == "Mn"} | {chr(0x640)}
        plain = "".join(c for c in unicodedata.normalize("NFC", arabic) if c not in marks)
        return re.sub(r"[^ء-ي\s]", " ", plain).split()

    def test_the_english_renders_all_of_the_arabic_beside_it(self):
        """The two columns are read side by side, so each must say the same thing.

        English takes more words than Arabic to say the same thing -- never fewer. A count well
        under the Arabic's means the English has rendered an opening clause and left the rest of
        the line unaccounted for, which is the one fault a reader cannot see for themselves.
        """
        both = ([("Qur'an", p) for p in CONTENT.daily.passages]
                + [("hadith", s) for s in CONTENT.daily.sayings])
        for kind, item in both:
            arabic = len(self.words(item["arabic"]))
            english = len(item["english"].split())
            self.assertGreaterEqual(
                english / arabic, 0.95,
                f"{kind} {item['reference']}: {english} English words for {arabic} Arabic ones, so "
                f"the English is rendering only part of it: {item['english']!r}")

    def test_the_passages_name_allah_the_way_the_rest_of_the_app_does(self):
        for item in list(CONTENT.daily.passages) + list(CONTENT.daily.sayings):
            self.assertNotIn("God", item["english"].split(),
                             f"{item['reference']} says God where the app says Allah")


class DhikrTest(unittest.TestCase):
    """The dhikr counted after a fardh prayer."""

    def test_every_part_has_its_words_and_a_recording(self):
        from salaah.render import load_timings
        timings = load_timings(ASSETS)
        d = CONTENT.dhikr
        for key in [d.salam_key, d.tahlil_key] + [b.key for b in d.beads] + ["istighfar"]:
            self.assertIn(key, CONTENT.arabic, key)
            self.assertIn(key, timings, key)
            self.assertEqual(len(CONTENT.arabic[key]), len(timings[key].segments), key)
        self.assertEqual(d.salam, " ".join(CONTENT.arabic[d.salam_key]), "shown as one line")
        self.assertEqual(3, len(CONTENT.arabic[d.tahlil_key]), "split at the recording's two pauses")

    def test_three_beads_of_thirty_three(self):
        d = CONTENT.dhikr
        self.assertTrue(d.usable)
        self.assertEqual(3, len(d.beads))
        self.assertEqual([33, 33, 33], [b.count for b in d.beads])

    def test_the_words_are_the_three_tasbih_in_order(self):
        subhan, hamd, akbar = CONTENT.dhikr.beads
        self.assertIn("سُبْحَانَ", subhan.text)
        self.assertIn("حَمْدُ", hamd.text)
        self.assertIn("أَكْبَرُ", akbar.text)

    def test_both_duas_are_there_and_whole(self):
        d = CONTENT.dhikr
        self.assertTrue(d.salam.startswith("اللَّهُمَّ"), "the salam dua")
        self.assertIn("الْجَلاَلِ", d.salam)
        # The tahlil must start with the whole of "laa ilaaha" — its lam is easy to drop.
        self.assertTrue(d.tahlil.startswith("لاَ إِلَهَ إِلاَّ اللَّهُ"), d.tahlil[:20])
        self.assertTrue(d.tahlil.rstrip().endswith("قَدِيرٌ"))
        for text in (d.salam, d.tahlil):
            self.assertLess(len(text), 160, "short enough to fit across the screen on one line")

    def test_every_word_is_vowelled_for_a_beginner(self):
        """A beginner reads the marks, so every bead and dua carries them."""
        marks = set("ًٌٍَُِّْٰ")
        d = CONTENT.dhikr
        for text in [d.salam, d.tahlil] + [b.text for b in d.beads]:
            self.assertTrue(marks & set(text), text)
        self.assertNotIn("ـ", d.salam + d.tahlil + "".join(b.text for b in d.beads),
                         "no tatweel: it stretches letters and confuses a learner")


class QiblaTest(unittest.TestCase):
    def test_the_bearing_from_places_whose_qibla_is_well_known(self):
        from salaah.qibla import bearing_to_kaaba
        self.assertAlmostEqual(118.5, bearing_to_kaaba(53.5933, -2.2966), delta=0.2)   # Bury
        self.assertAlmostEqual(119.0, bearing_to_kaaba(51.5074, -0.1278), delta=0.5)   # London
        self.assertAlmostEqual(58.5, bearing_to_kaaba(40.7128, -74.0060), delta=0.5)   # New York
        self.assertAlmostEqual(295.1, bearing_to_kaaba(-6.2088, 106.8456), delta=0.5)  # Jakarta

    def test_which_way_to_turn(self):
        from salaah.qibla import turn_needed
        self.assertAlmostEqual(18.5, turn_needed(100, 118.5))
        self.assertAlmostEqual(-41.5, turn_needed(160, 118.5))
        self.assertAlmostEqual(20, turn_needed(350, 10), msg="across north, the short way")
        self.assertAlmostEqual(-20, turn_needed(10, 350))

    def test_the_smoother_averages_across_north(self):
        from salaah.qibla import Smoother
        s = Smoother(weight=0.5)
        s.add(350)
        value = s.add(10)
        self.assertTrue(value > 355 or value < 5, value)

    def test_no_chip_means_no_compass(self):
        from salaah.qibla import find_compass
        compass = find_compass()
        self.assertFalse(compass.fitted)          # nothing on I2C here
        self.assertIsNone(compass.heading())


class PrayerTimesTest(unittest.TestCase):
    """Muslim World League method, worked out on the device."""

    def test_the_default_location_is_bury(self):
        from salaah.settings import Settings
        s = Settings()
        self.assertEqual("Bury", s.place)
        self.assertAlmostEqual(53.5933, s.latitude, places=3)
        self.assertAlmostEqual(-2.2966, s.longitude, places=3)

    def setUp(self):
        from salaah.prayer_times import Place
        self.bury = Place(53.5933, -2.2966, "Bury")
        self.makkah = Place(21.4225, 39.8262, "Makkah")

    def times(self, place, day, offset):
        from datetime import date
        from salaah.prayer_times import times_for
        return times_for(date(*day), place, "hanafi", offset)

    def test_times_are_in_order_and_about_right(self):
        t = self.times(self.makkah, (2026, 9, 13), 3.0)
        minutes = {k: v.hour * 60 + v.minute for k, v in t.items()}
        self.assertLess(minutes["fajr"], minutes["dhuhr"])
        self.assertLess(minutes["dhuhr"], minutes["asr"])
        self.assertLess(minutes["asr"], minutes["maghrib"])
        self.assertLess(minutes["maghrib"], minutes["isha"])
        # Makkah in mid-September: noon is around quarter past twelve, sunset around half six
        self.assertAlmostEqual(12 * 60 + 17, minutes["dhuhr"], delta=8)
        self.assertAlmostEqual(18 * 60 + 26, minutes["maghrib"], delta=10)

    def test_hanafi_asr_is_later_than_the_others(self):
        from datetime import date
        from salaah.prayer_times import times_for
        day = date(2026, 9, 13)
        hanafi = times_for(day, self.bury, "hanafi", 1.0)["asr"]
        standard = times_for(day, self.bury, "standard", 1.0)["asr"]
        self.assertGreater(hanafi, standard)

    def test_far_north_summer_has_no_fajr_or_isha_of_its_own(self):
        """At this latitude the sun never dips 18 degrees under in June, so those moments do not
        exist. That is the astronomy, and it is why the mat needs a convention for those weeks --
        this checks the sums still say so plainly, with no rule applied. What the mat then SHOWS
        is Aqrab al-Ayyam, which HighLatitudeTest covers."""
        from salaah.prayer_times import times_for
        from datetime import date
        t = times_for(date(2026, 6, 21), self.bury, "hanafi", 1.0, high_latitude="none")
        self.assertIsNone(t["fajr"])
        self.assertIsNone(t["isha"])
        self.assertIsNotNone(t["dhuhr"])

    def test_no_prayer_is_due_between_sunrise_and_dhuhr(self):
        from datetime import date, datetime, time as clock
        from salaah.prayer_times import current_prayer
        t = self.times(self.bury, (2026, 9, 14), 1.0)

        def at(hh, mm):
            return datetime.combine(date(2026, 9, 14), clock(hh, mm))

        self.assertEqual("fajr", current_prayer(at(5, 30), t), "Fajr runs until sunrise")
        self.assertIsNone(current_prayer(at(7, 30), t), "after sunrise, nothing is due")
        self.assertIsNone(current_prayer(at(12, 0), t), "still nothing, just before Dhuhr")
        self.assertEqual("dhuhr", current_prayer(at(13, 30), t))

    def test_sun_and_moon_move_across_the_sky(self):
        from datetime import date, datetime, time as clock
        from salaah.prayer_times import day_fraction
        t = self.times(self.bury, (2026, 9, 14), 1.0)

        def at(hh, mm):
            return day_fraction(datetime.combine(date(2026, 9, 14), clock(hh, mm)), t)

        morning_up, morning = at(8, 0)
        noon_up, midday = at(13, 0)
        evening_up, evening = at(18, 30)
        self.assertTrue(morning_up and noon_up and evening_up, "the sun is up through the day")
        self.assertLess(morning, midday)
        self.assertLess(midday, evening)
        night_up, _ = at(23, 0)
        self.assertFalse(night_up, "the moon is out at night")

    def test_which_prayer_it_is_now(self):
        from datetime import date, datetime, time as clock
        from salaah.prayer_times import current_prayer, next_prayer
        t = self.times(self.bury, (2026, 9, 13), 1.0)

        def at(hh, mm):
            return datetime.combine(date(2026, 9, 13), clock(hh, mm))

        self.assertEqual("fajr", current_prayer(at(5, 0), t))
        self.assertEqual("dhuhr", current_prayer(at(13, 30), t))
        self.assertEqual("asr", current_prayer(at(17, 40), t))
        self.assertEqual("maghrib", current_prayer(at(20, 0), t))
        self.assertEqual("isha", current_prayer(at(23, 0), t))
        self.assertEqual("isha", current_prayer(at(2, 0), t), "still Isha before Fajr")
        self.assertEqual("fajr", next_prayer(at(2, 0), t))


class AudioToolTest(unittest.TestCase):
    def test_extract_refuses_to_read_and_write_the_same_file(self):
        """Cutting a section out of a file in place would destroy it, as it once did."""
        import sys
        sys.path.insert(0, str(ASSETS.parent / "tools"))
        from build_audio_timings import extract
        with self.assertRaises(SystemExit):
            extract(ASSETS / "audio" / "fatiha.mp3", "fatiha", 1.0, 2.0)
        self.assertGreater((ASSETS / "audio" / "fatiha.mp3").stat().st_size, 300_000,
                           "the recording is untouched")


class SessionTest(unittest.TestCase):
    def test_rakats_for_every_unit(self):
        for unit in CONTENT.units.values():
            s = PrayerSession(unit, CONTENT)
            rakats = [p.rakat for p in s.pages]
            self.assertEqual(list(range(1, unit.rakats + 1)), sorted(set(rakats)), unit.id)
            self.assertEqual(unit.rakats, rakats[-1], unit.id)
            ruku = [p.rakat for p in s.pages if p.step.posture == "ruku"]
            self.assertEqual(list(range(1, unit.rakats + 1)), ruku, unit.id)

    def test_navigation_and_finish(self):
        s = PrayerSession(CONTENT.units["two_rakat"], CONTENT)
        self.assertFalse(s.back())
        while not s.finished:
            s.next()
        self.assertEqual("salam", str(s.current.ref))
        self.assertFalse(s.next())
        self.assertTrue(s.back())  # back from "complete" returns to the last step
        self.assertFalse(s.finished)

    def test_school_overrides(self):
        s = PrayerSession(CONTENT.units["two_rakat"], CONTENT, {"ruku_a": "ruku_b"})
        self.assertFalse(any(p.step.id == "ruku_a" for p in s.pages))

    def test_rakat_rule(self):
        self.assertEqual([1, 1, 1, 1, 2, 2, 2, 2, 2], assign_rakats(
            ["standing", "ruku", "sujood", "sujood", "standing", "sujood", "sujood", "sitting", "salam"]))


class ButtonTest(unittest.TestCase):
    def test_debouncer(self):
        d = Debouncer(0.3)
        self.assertTrue(d.accept(10.0))
        self.assertFalse(d.accept(10.1))
        self.assertTrue(d.accept(10.4))

    def test_clicks_count_and_holds_are_ignored(self):
        f = PressFilter(hold=1.0)
        self.assertIsNone(f.event(115, 1, 0.0))           # Volume Up down
        self.assertEqual(NEXT, f.event(115, 0, 0.12))     # short click: next
        f.event(114, 1, 1.0)
        self.assertEqual(BACK, f.event(114, 0, 1.1))      # Volume Down: back
        f.event(272, 1, 2.0)                               # ring in mouse mode: left button
        self.assertIsNone(f.event(272, 2, 2.5))           # auto-repeat ignored
        self.assertIsNone(f.event(272, 0, 4.0))           # held 2 s (palm on the floor): ignored
        self.assertIsNone(f.event(28, 0, 5.0))            # release without a press: ignored


if __name__ == "__main__":
    unittest.main()


class TranslationTest(unittest.TestCase):
    """English and French beside the Arabic."""

    def setUp(self):
        from salaah.content import load
        self.content = load(Path(__file__).resolve().parent.parent / "assets")

    def test_every_language_matches_the_arabic_line_for_line(self):
        shipping = [k for k, v in self.content.translations.items() if not v.personal]
        self.assertGreaterEqual(len(shipping), 6, "en, fr, ur, es, zh, hi")
        for lang in shipping:
            tr = self.content.translations[lang]
            for key, arabic in self.content.arabic.items():
                if key in tr.lines:
                    self.assertEqual(len(arabic), len(tr.lines[key]), f"{lang} {key}")
            for step in self.content.steps.values():
                if step.recitation != "intention":
                    self.assertIn(step.recitation, tr.lines, f"{lang} has {step.recitation}")

    def test_every_line_says_where_it_came_from(self):
        for tr in self.content.translations.values():
            self.assertEqual(set(tr.lines), set(tr.sources))
            self.assertTrue(tr.about)

    def test_the_intention_is_in_the_chosen_language(self):
        fr = self.content.translations["fr"]
        self.assertEqual("J'ai l'intention d'accomplir 2 rak'ats sunnah de Fajr",
                         fr.intend(2, "sunnah", "fajr"))
        en = self.content.translations["en"]
        self.assertEqual("I intend to perform 4 Rakats Fardh of Dhuhr", en.intend(4, "farz", "dhuhr"))

    def test_a_translation_out_of_step_is_left_out(self):
        tr = self.content.translations["en"]
        self.assertIsNone(tr.for_key("fatiha", 6))
        self.assertIsNone(tr.for_key("no_such_thing", 1))


class PersonalTranslationTest(unittest.TestCase):
    """A *.personal.json translation is for one private device, never for a device that is sold."""

    def setUp(self):
        from salaah.content import load
        self.root = Path(__file__).resolve().parent.parent / "assets"
        self.content = load(self.root)

    def test_they_are_marked_and_say_so(self):
        personal = [t for t in self.content.translations.values() if t.personal]
        for tr in personal:
            self.assertIn("PERSONAL USE ONLY", tr.about)
            self.assertIn("publisher", tr.about)
        for tr in self.content.translations.values():
            named = tr.lang.replace("-", ".") + ".personal.json"
            self.assertEqual(tr.personal, (self.root / "content" / "translations" / named).is_file()
                             or f"{tr.lang}.personal.json" in
                             [p.name for p in (self.root / "content" / "translations").glob("*.json")])

    def test_the_shipped_ones_are_ours_alone(self):
        for tr in self.content.translations.values():
            if tr.personal:
                continue
            for key, source in tr.sources.items():
                self.assertNotIn("Clear Qur'an", source, f"{tr.lang} {key}")
                self.assertNotIn("Rashid Maash", source, f"{tr.lang} {key}")

    def test_they_match_the_arabic_line_for_line(self):
        for tr in self.content.translations.values():
            if not tr.personal:
                continue
            for key, arabic in self.content.arabic.items():
                if key in tr.lines:
                    self.assertEqual(len(arabic), len(tr.lines[key]), f"{tr.lang} {key}")


class ScreenPickingTest(unittest.TestCase):
    """Which screen the words go on and which gets the posture. Worked out from the shapes of
    the screens, so the two HDMI sockets can be either way round."""

    class Screen:
        def __init__(self, name, width, height):
            self._name, self.box = name, (width, height)

        def name(self):
            return self._name

        def geometry(self):
            from salaah.qt import QtCore
            return QtCore.QRect(0, 0, *self.box)

    class App:
        def __init__(self, *screens):
            self._screens = list(screens)

        def screens(self):
            return self._screens

        def primaryScreen(self):
            return self._screens[0] if self._screens else None

    def setUp(self):
        from salaah import main
        self.main = main
        self.big = self.Screen("HDMI-A-1", 1920, 1200)
        self.small_upright = self.Screen("HDMI-A-2", 600, 1024)
        self.small_flat = self.Screen("HDMI-A-2", 1024, 600)

    def pick(self, *screens, **names):
        return self.main.pick_screens(self.App(*screens), **names)

    def test_the_seven_inch_is_found_by_its_shape_either_way_round(self):
        for small in (self.small_upright, self.small_flat):
            self.assertTrue(self.main.looks_like_the_seven_inch(small))
        self.assertFalse(self.main.looks_like_the_seven_inch(self.big))

    def test_the_sockets_can_be_either_way_round(self):
        for order in ((self.big, self.small_upright), (self.small_upright, self.big)):
            main, side = self.pick(*order)
            self.assertIs(self.big, main, "the words go on the big screen")
            self.assertIs(self.small_upright, side, "the posture goes on the 7 inch")

    def test_the_names_can_swap_over_without_changing_anything(self):
        # the same two panels, reported with each other's names after a reboot
        swapped = (self.Screen("HDMI-A-2", 1920, 1200), self.Screen("HDMI-A-1", 600, 1024))
        main, side = self.pick(*swapped)
        self.assertEqual((1920, 1200), main.box)
        self.assertEqual((600, 1024), side.box)

    def test_one_screen_on_its_own_gets_the_words(self):
        main, side = self.pick(self.big)
        self.assertIs(self.big, main)
        self.assertIsNone(side, "no posture screen to use")

    def test_a_name_overrules_the_shape(self):
        main, side = self.pick(self.big, self.small_upright, main_name="HDMI-A-2")
        self.assertIs(self.small_upright, main, "asked for by name")
        self.assertIs(self.big, side)

    def test_two_ordinary_monitors_still_work_for_trying_it_out(self):
        second = self.Screen("HDMI-A-2", 1280, 720)
        main, side = self.pick(self.big, second)
        self.assertIs(self.big, main)
        self.assertIs(second, side, "the smaller one stands in for the 7 inch")

    def test_no_screens_at_all_does_not_fall_over(self):
        main, side = self.main.pick_screens(self.App())
        self.assertIsNone(main)
        self.assertIsNone(side)


class RememberedScreensTest(unittest.TestCase):
    """The screens that worked are remembered, but a remembered name is dropped once it stops
    making sense: names can come back in a different order after a reboot."""

    def setUp(self):
        from salaah import main
        from salaah.settings import Settings
        self.main = main
        self.Settings = Settings
        self.big = ScreenPickingTest.Screen("HDMI-A-1", 1920, 1200)
        self.small = ScreenPickingTest.Screen("HDMI-A-2", 600, 1024)
        self.app = ScreenPickingTest.App(self.big, self.small)

    def test_a_name_given_this_run_beats_the_remembered_one(self):
        kept = self.Settings(main_output="HDMI-A-1", side_output="HDMI-A-2")
        self.assertEqual(("HDMI-A-2", ""), self.main.remembered(self.app, kept, "HDMI-A-2", ""))

    def test_a_remembered_name_is_used_when_it_still_fits(self):
        kept = self.Settings(main_output="HDMI-A-1", side_output="HDMI-A-2")
        self.assertEqual(("HDMI-A-1", "HDMI-A-2"), self.main.remembered(self.app, kept, "", ""))

    def test_a_remembered_main_screen_that_is_now_the_small_panel_is_dropped(self):
        kept = self.Settings(main_output="HDMI-A-2", side_output="HDMI-A-1")
        self.assertEqual(("", ""), self.main.remembered(self.app, kept, "", ""),
                         "both are stale, so the shapes decide instead")

    def test_a_remembered_screen_that_is_gone_is_dropped(self):
        kept = self.Settings(main_output="DSI-1", side_output="DSI-2")
        self.assertEqual(("", ""), self.main.remembered(self.app, kept, "", ""))

    def kept_settings(self, **fields):
        kept = self.Settings(**fields)
        kept.save = lambda *a, **k: None       # no writing to the real settings file in a test
        return kept

    def test_what_was_used_is_written_down(self):
        kept = self.kept_settings()
        self.main.remember(kept, self.big, self.small)
        self.assertEqual(("HDMI-A-1", "HDMI-A-2"), (kept.main_output, kept.side_output))

    def test_a_stale_pair_is_corrected_by_the_shapes_and_remembered(self):
        kept = self.kept_settings(main_output="HDMI-A-2", side_output="HDMI-A-1")
        names = self.main.remembered(self.app, kept, "", "")
        main, side = self.main.pick_screens(self.app, *names)
        self.main.remember(kept, main, side)
        self.assertEqual(("HDMI-A-1", "HDMI-A-2"), (kept.main_output, kept.side_output))


class NewLanguagesTest(unittest.TestCase):
    """Spanish, Mandarin and Hindi, added for testing. Each is written for this app rather than
    taken from a published translation, because no free one exists in these three languages."""

    WANTED = ("es", "zh", "hi")

    def setUp(self):
        from salaah.content import load
        self.content = load(ASSETS)

    def test_all_three_are_there_and_ship(self):
        for lang in self.WANTED:
            tr = self.content.translations.get(lang)
            self.assertIsNotNone(tr, f"{lang} is missing")
            self.assertFalse(tr.personal, f"{lang} should be a shipping file, not a personal one")
            self.assertTrue(tr.native_name, f"{lang} has no name in its own language")
            self.assertFalse(tr.rtl, f"{lang} runs left to right")

    def test_none_of_them_carries_a_publisher_s_words(self):
        """The standing rule for anything that ships: nothing from a translation in copyright.
        Every line of these three was written for the app, so there is nothing to strip out."""
        for lang in self.WANTED:
            tr = self.content.translations[lang]
            for key, where in tr.sources.items():
                self.assertIn("written for this app", where,
                              f"{lang} {key} came from somewhere else: {where}")
            self.assertIn("DRAFT", tr.about, f"{lang} does not say it still needs checking")

    def test_the_intention_reads_in_each_language(self):
        """Filled in from that language's own words for the prayer and the kind. Spanish keeps
        the Arabic names as they are normally written in Spanish, so what is checked is that the
        names come from the file rather than that they differ from the English."""
        for lang in self.WANTED:
            tr = self.content.translations[lang]
            said = tr.intend(4, "farz", "dhuhr")
            self.assertIn("4", said, lang)
            self.assertNotIn("{", said, f"{lang} left a gap unfilled: {said}")
            self.assertIn(tr.prayers["dhuhr"], said, f"{lang}: {said}")
            self.assertIn(tr.kinds["farz"], said, f"{lang}: {said}")

    def test_they_cover_every_recitation_the_app_shows(self):
        for lang in self.WANTED:
            tr = self.content.translations[lang]
            for step in self.content.steps.values():
                if step.recitation != "intention":
                    self.assertIn(step.recitation, tr.lines, f"{lang} is missing {step.recitation}")


class WrappingTest(unittest.TestCase):
    """Chinese is written without spaces between words, so the pieces a line may be broken
    between have to be worked out rather than assumed."""

    def pieces(self, text):
        from salaah.render import wrappable
        return wrappable(text)

    def test_a_language_with_spaces_breaks_between_words(self):
        got = self.pieces("En el nombre de Dios")
        self.assertEqual(["En", "el", "nombre", "de", "Dios"], [p for p, _ in got])
        self.assertEqual([False, True, True, True, True], [s for _, s in got])

    def test_chinese_breaks_between_characters_with_no_space_between_them(self):
        got = self.pieces("奉安拉之名")
        self.assertEqual(["奉", "安", "拉", "之", "名"], [p for p, _ in got])
        self.assertFalse(any(s for _, s in got), "no spaces belong between Chinese characters")

    def test_a_chinese_line_is_no_longer_one_unbreakable_lump(self):
        verse = "你所喜悦者的路，不是受谴怒者的路，也不是迷误者的路。"
        self.assertEqual(1, len(verse.split()), "it really does arrive as a single word")
        self.assertGreater(len(self.pieces(verse)), 20, "so it must be broken up to wrap at all")

    def test_arabic_keeps_a_space_between_every_word(self):
        """The fix for Chinese is where a bug in the Arabic spacing came from, so this is
        checked from the placed words rather than from the string."""
        from salaah.render import Fonts, lay_out_words
        Fonts.load(ASSETS)
        line = CONTENT.arabic["fatiha"][0]
        placed, _ = lay_out_words([line], 1600, Fonts.arabic("scheherazade"), 60, 700, True, 0.18)
        self.assertEqual(len(line.split()), len(placed))
        right_to_left = sorted(placed, key=lambda w: -w.x)
        gaps = [right_to_left[i].x - (right_to_left[i + 1].x + right_to_left[i + 1].width)
                for i in range(len(right_to_left) - 1)]
        self.assertTrue(gaps, "not enough words to have a gap")
        for gap in gaps:
            self.assertGreater(gap, 0, f"two Arabic words have run together: gaps {gaps}")

    def test_hindi_breaks_between_its_words(self):
        got = self.pieces("अल्लाह के नाम से")
        self.assertEqual(["अल्लाह", "के", "नाम", "से"], [p for p, _ in got])


class PowerButtonTest(unittest.TestCase):
    """Reading the Pi 5's power button, so a press sleeps the mat rather than shutting it down."""

    LISTING = """I: Bus=0003 Vendor=046d Product=c52b Version=0111
N: Name="Logitech K400"
H: Handlers=sysrq kbd event0 leds

I: Bus=0019 Vendor=0001 Product=0001 Version=0100
N: Name="pwr_button"
P: Phys=
S: Sysfs=/devices/platform/pwr_button/input/input5
H: Handlers=kbd event5 
B: PROP=0
"""

    def test_the_button_is_found_by_name_not_by_number(self):
        """The event number moves about with whatever else is plugged in, so a mat that slept
        only when no keyboard was connected would be a puzzling thing to own."""
        from salaah.power import power_device
        self.assertEqual("/dev/input/event5", power_device(self.LISTING))

    def test_a_listing_without_one_gives_nothing_rather_than_a_guess(self):
        from salaah.power import power_device
        without = self.LISTING.split("\n\n")[0]
        self.assertIsNone(power_device(without))

    def test_a_click_counts_and_a_long_hold_does_not(self):
        """Holding the button is someone forcing the board off in hardware. The screens should
        not blink on the way to that."""
        from salaah.power import PressWatch
        watch = PressWatch(hold=1.5)
        self.assertFalse(watch.event(1, 10.0), "nothing happens on the way down")
        self.assertTrue(watch.event(0, 10.2), "a click counts on release")
        self.assertFalse(watch.event(1, 20.0))
        self.assertFalse(watch.event(0, 24.0), "a four second hold is a force-off, not a press")

    def test_auto_repeat_while_held_is_not_a_second_press(self):
        from salaah.power import PressWatch
        watch = PressWatch()
        watch.event(1, 0.0)
        self.assertFalse(watch.event(2, 0.5))
        self.assertFalse(watch.event(2, 1.0))
        self.assertTrue(watch.event(0, 1.2), "still one press when it is let go")

    def test_a_release_on_its_own_is_ignored(self):
        """The app can start with the button already down -- during the press that booted it."""
        from salaah.power import PressWatch
        self.assertFalse(PressWatch().event(0, 1.0))

    def test_the_event_struct_is_the_size_the_kernel_writes(self):
        import struct
        from salaah.power import EVENT, EVENT_SIZE
        self.assertEqual(struct.calcsize(EVENT), EVENT_SIZE)
        self.assertIn(EVENT_SIZE, (16, 24), "16 on a 32-bit Pi, 24 on a 64-bit one")

    def test_it_says_why_rather_than_failing_silently(self):
        from salaah.power import PowerButton
        button = PowerButton(lambda: None, listing="/does/not/exist")
        self.assertFalse(button.start())
        self.assertTrue(button.why)


class OutputsTest(unittest.TestCase):
    """Switching the screens off at the panel, not painting them black."""

    def runner(self, code=0, error=""):
        calls = []

        def run(command, **kw):
            calls.append(command)
            return SimpleNamespace(returncode=code, stdout="", stderr=error)
        return run, calls

    def test_off_and_on_reach_every_output(self):
        from salaah.power import Outputs
        run, calls = self.runner()
        outputs = Outputs(run=run)
        self.assertTrue(outputs.set(False))
        self.assertTrue(outputs.set(True))
        self.assertEqual([["wlopm", "--off", "*"], ["wlopm", "--on", "*"]], calls)

    def test_a_missing_wlopm_is_reported_not_raised(self):
        """The mat should still sleep on a machine without it; it just won't save the power."""
        from salaah.power import Outputs

        def run(command, **kw):
            raise FileNotFoundError(command[0])
        outputs = Outputs(run=run)
        self.assertFalse(outputs.set(False))
        self.assertIn("not installed", outputs.why)

    def test_a_refusal_is_reported(self):
        from salaah.power import Outputs
        run, _ = self.runner(code=1, error="no outputs")
        outputs = Outputs(run=run)
        self.assertFalse(outputs.set(False))
        self.assertIn("no outputs", outputs.why)


class PowerDrawTest(unittest.TestCase):
    """The tool that measures what the mat costs to run."""

    SAMPLE = """        3V7_WL_SW_A current(0)=0.01123625A
        3V7_WL_SW_V volt(1)=3.69531250V
        VDD_CORE_A current(16)=2.50000000A
        VDD_CORE_V volt(17)=0.72070312V
        EXT5V_V volt(24)=5.10937500V
        BATT_V volt(25)=0.00000000V
"""

    def tool(self):
        import importlib.util
        path = Path(__file__).resolve().parent.parent / "tools" / "power_draw.py"
        spec = importlib.util.spec_from_file_location("power_draw", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_every_rail_is_counted_and_the_input_voltage_is_kept_apart(self):
        tool = self.tool()
        watts, supply = tool.parse(self.SAMPLE)
        rails = 0.01123625 * 3.69531250 + 2.5 * 0.72070312
        self.assertAlmostEqual(rails * tool.SCALE + tool.OFFSET, watts, places=6)
        self.assertAlmostEqual(5.109375, supply, places=6,
                               msg="the supply is what sags on a battery; it is not a rail")

    def test_nothing_to_read_gives_zero_rather_than_a_wrong_number(self):
        tool = self.tool()
        self.assertEqual((0.0, 0.0), tool.parse("vcgencmd: command not found"))


class UpdateTest(unittest.TestCase):
    """Updating over the internet: the only part of the app that fetches code and runs it, and
    so the only part that can brick the mat or be turned against it."""

    @staticmethod
    def keypair():
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        import base64
        private = Ed25519PrivateKey.generate()
        public = base64.b64encode(private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)).decode()
        return private, public

    def manifest(self, private, **changes):
        import base64
        import json
        body = {"version": "9.9", "url": "http://example/x.zip", "sha256": "0" * 64,
                "bytes": 10, "notes": ""}
        body.update(changes)
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return json.dumps({"release": body,
                           "signature": base64.b64encode(private.sign(payload)).decode()}).encode()

    def test_versions_are_compared_as_numbers_not_as_text(self):
        """The whole reason the version stopped being the string "1"."""
        from salaah.update import newer
        self.assertTrue(newer("1.12", "1.9"), "1.12 must count as newer than 1.9")
        self.assertFalse(newer("1.9", "1.12"))
        self.assertFalse(newer("1.12", "1.12"), "the same version is not an update")
        self.assertTrue(newer("2.0", "1.99"))

    def test_a_properly_signed_manifest_is_accepted(self):
        from salaah.update import read_manifest
        private, public = self.keypair()
        release = read_manifest(self.manifest(private), public)
        self.assertEqual("9.9", release.version)

    def test_a_release_signed_by_anyone_else_is_refused(self):
        """The point of the whole exercise. HTTPS says the file came from the right website; it
        says nothing about whether it is the file its author meant to publish."""
        from salaah.update import read_manifest, Refused
        private, _ = self.keypair()
        _, someone_else = self.keypair()
        with self.assertRaises(Refused):
            read_manifest(self.manifest(private), someone_else)

    def test_changing_the_manifest_after_signing_is_refused(self):
        """Where the download comes from, and which version it claims to be, are both covered
        by the signature -- so neither can be swapped at the host."""
        import json
        from salaah.update import read_manifest, Refused
        private, public = self.keypair()
        for field, value in (("url", "http://evil.example/payload.zip"), ("version", "99.0"),
                             ("sha256", "f" * 64)):
            raw = json.loads(self.manifest(private))
            raw["release"][field] = value
            with self.assertRaises(Refused, msg=f"{field} could be changed after signing"):
                read_manifest(json.dumps(raw).encode(), public)

    def test_rubbish_in_place_of_a_manifest_is_refused(self):
        from salaah.update import read_manifest, Refused
        _, public = self.keypair()
        for rubbish in (b"<html>404 not found</html>", b"", b"{}", b'{"release": {}}'):
            with self.assertRaises(Refused):
                read_manifest(rubbish, public)

    def test_no_release_published_yet_is_said_in_words(self):
        """Before the first release exists the address is simply empty, and that is not a
        malfunction. "HTTP Error 404: Not Found" on a prayer mat tells nobody anything."""
        import urllib.error
        from salaah.update import fetch, Refused

        def missing(url, timeout=None):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with self.assertRaises(Refused) as caught:
            fetch("http://example/latest.json", opener=missing)
        self.assertIn("nothing has been published", str(caught.exception))
        self.assertNotIn("404", str(caught.exception))

    def test_a_dropped_connection_is_tried_again_rather_than_shown_to_anyone(self):
        """Home wifi resets connections. That is not a fault worth putting on a prayer mat."""
        import io
        from salaah.update import fetch

        tried = []

        def flaky(url, timeout=None):
            tried.append(url)
            if len(tried) < 3:
                raise ConnectionResetError(104, "Connection reset by peer")
            return io.BytesIO(b"the release")

        with mock.patch("salaah.update.PAUSE", 0):
            self.assertEqual(b"the release", fetch("http://example/x.zip", opener=flaky))
        self.assertEqual(3, len(tried), "a dropped connection should be retried")

    def test_giving_up_reports_the_last_thing_that_went_wrong(self):
        from salaah.update import fetch, Refused

        def dead(url, timeout=None):
            raise ConnectionResetError(104, "Connection reset by peer")

        with mock.patch("salaah.update.PAUSE", 0):
            with self.assertRaises(Refused) as caught:
                fetch("http://example/x.zip", opener=dead)
        self.assertIn("Connection reset", str(caught.exception))

    def test_the_two_kinds_of_missing_are_told_apart(self):
        """A manifest that is not there means nothing has been published. A zip that is not
        there means a release exists and its file is not where it says. Those have different
        fixes, and calling them the same thing sent us looking in the wrong place."""
        import urllib.error
        from salaah.update import Refused, check, install, Release

        def missing(url, timeout=None):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with self.assertRaises(Refused) as no_manifest:
            check("http://example/latest.json", opener=missing)
        self.assertIn("nothing has been published", str(no_manifest.exception))

        import tempfile
        from pathlib import Path as P
        with mock.patch("salaah.update.PAUSE", 0):
            with self.assertRaises(Refused) as no_zip:
                install(Release(version="9.9", url="http://example/x.zip", sha256="0" * 64),
                        P(tempfile.mkdtemp()), opener=missing)
        self.assertIn("its file is not there", str(no_zip.exception))
        self.assertNotEqual(str(no_manifest.exception), str(no_zip.exception),
                            "the two must not read the same")

    def test_a_missing_file_is_not_retried(self):
        """Asking three times for something that is not there wastes a minute of someone's
        evening to arrive at the same answer."""
        import urllib.error
        from salaah.update import fetch, Refused

        tried = []

        def missing(url, timeout=None):
            tried.append(url)
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with mock.patch("salaah.update.PAUSE", 0):
            with self.assertRaises(Refused):
                fetch("http://example/x.zip", opener=missing)
        self.assertEqual(1, len(tried), "a 404 will say the same thing every time")

    def test_we_do_not_knock_on_the_door_as_python_urllib(self):
        """Python's default User-Agent is what a good many content networks hang up on, and a
        hung-up connection is exactly the reset we were seeing."""
        from salaah.update import headers
        from salaah import __version__
        said = headers()["User-Agent"]
        self.assertNotIn("Python-urllib", said)
        self.assertIn("Salaah", said)
        self.assertIn(__version__, said)

    def test_other_network_failures_still_say_what_went_wrong(self):
        """A 404 is the ordinary case. Everything else keeps its detail, because a mat that
        says nothing useful is a mat nobody can fix."""
        import urllib.error
        from salaah.update import fetch, Refused

        def broken(url, timeout=None):
            raise urllib.error.HTTPError(url, 500, "Server Error", {}, None)

        with mock.patch("salaah.update.PAUSE", 0):
            with self.assertRaises(Refused) as caught:
                fetch("http://example/latest.json", opener=broken)
        self.assertIn("500", str(caught.exception))

    def fake_pi(self, behaviour: str) -> Path:
        """A throwaway folder holding the real run.sh and a stand-in for python.

        The guard is plain shell precisely so that it still works when the installed version
        does not, which means no amount of Python testing covers it. The only way to know what
        it does is to run it.
        """
        import os
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp(prefix="salaah-guard-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shutil.copy(Path(__file__).resolve().parent.parent / "run.sh", root / "run.sh")
        stand_in = root / ".venv" / "bin"
        stand_in.mkdir(parents=True)
        # run.sh uses python for two quite different things: reading the state file with -c,
        # which must really work, and starting the app, which is what we are pretending about.
        (stand_in / "python").write_text(
            '#!/bin/bash\n'
            'if [ "$1" = "-c" ]; then exec python3 "$@"; fi\n'
            'echo started >> starts\n'
            + behaviour)
        os.chmod(stand_in / "python", 0o755)
        return root

    @staticmethod
    def guard(root: Path):
        import subprocess
        return subprocess.run(["bash", str(root / "run.sh")], capture_output=True, timeout=60)

    @staticmethod
    def starts(root: Path) -> int:
        note = root / "starts"
        return len(note.read_text().split()) if note.exists() else 0

    def test_the_guard_starts_the_new_version_after_an_update(self):
        """The defect that left the mat sitting on the desktop: the app installed 1.14, stood
        down so the new version could start, and nothing started it."""
        from salaah.update import RESTART
        root = self.fake_pi(f'if [ "$(wc -l < starts)" -le 1 ]; then exit {RESTART}; fi\nexit 0\n')
        done = self.guard(root)
        self.assertEqual(0, done.returncode, done.stderr.decode())
        self.assertEqual(2, self.starts(root),
                         "the guard must start the app again after an update installs")

    def test_an_older_version_that_quits_cleanly_after_updating_is_still_restarted(self):
        """The trap that caught the 1.14 -> 1.15 update. The app that stands down is the OLD
        one, so it stands down the old way -- a plain clean exit. The state file still shows
        what happened: something is on trial that has never been started."""
        # The trial appears DURING the run, because that is when the install happens -- which is
        # exactly why the exit code alone was not enough to tell an update from a shutdown.
        root = self.fake_pi(
            'if [ "$(wc -l < starts)" -le 1 ]; then\n'
            '  echo \'{"trial": "1.15", "attempts": 0}\' > update-state.json\n'
            'fi\n'
            'exit 0\n')

        done = self.guard(root)

        self.assertEqual(0, done.returncode, done.stderr.decode())
        self.assertEqual(2, self.starts(root),
                         "a freshly installed version must be started even by an old app's exit")

    def test_closing_an_app_on_trial_still_closes_it(self):
        """The line the rule above must not cross: once the trialled version has actually been
        started, a clean exit is a person closing the app, and it must close."""
        import json
        root = self.fake_pi("exit 0\n")
        (root / "update-state.json").write_text(json.dumps({"trial": "1.15", "attempts": 0}))

        done = self.guard(root)

        self.assertEqual(1, self.starts(root), "closing the app must close it")

    def test_closing_the_app_really_closes_it(self):
        """The other half of the same coin. If every exit restarted, the mat could never be
        shut down, which is worse than the bug it would be fixing."""
        root = self.fake_pi("exit 0\n")
        done = self.guard(root)
        self.assertEqual(0, done.returncode)
        self.assertEqual(1, self.starts(root), "a clean exit must not start the app again")

    def test_a_version_that_will_not_start_is_put_back_and_the_old_one_run(self):
        """A bad update must not leave a dark mat, and the guard must do it without asking the
        broken version for help."""
        import json
        root = self.fake_pi('if [ "$(wc -l < starts)" -le 1 ]; then exit 1; fi\nexit 0\n')
        for name in ("salaah", "assets"):
            (root / name).mkdir()
            (root / name / "which").write_text("new")
            (root / f"{name}.prev").mkdir()
            (root / f"{name}.prev" / "which").write_text("old")
        (root / "update-state.json").write_text(json.dumps({"trial": "9.9", "attempts": 0}))

        done = self.guard(root)

        self.assertEqual(0, done.returncode, done.stderr.decode())
        self.assertEqual(2, self.starts(root), "the restored version must be started")
        self.assertEqual("old", (root / "salaah" / "which").read_text())
        self.assertEqual("old", (root / "assets" / "which").read_text())
        self.assertNotIn("trial", json.loads((root / "update-state.json").read_text()))

    def zip_of(self, entries, symlink=None):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for name, data in entries:
                z.writestr(name, data)
            if symlink:
                info = zipfile.ZipInfo(symlink)
                info.external_attr = 0o120777 << 16
                z.writestr(info, "/etc/passwd")
        buf.seek(0)
        return zipfile.ZipFile(buf)

    def test_a_zip_cannot_write_outside_the_folders_it_replaces(self):
        """A zip can name an entry "../../.bashrc" and be unpacked straight over it."""
        from salaah.update import safe_members, Refused
        for entry in ("salaah/../../../.bashrc", "/etc/cron.d/evil", "../outside.py"):
            with self.assertRaises(Refused, msg=f"{entry} was allowed"):
                safe_members(self.zip_of([(entry, "x")]))

    def test_a_zip_cannot_replace_anything_it_was_not_meant_to(self):
        """run.sh above all: it is the guard that undoes a bad update, so a bad update must not
        be able to replace it."""
        from salaah.update import safe_members, Refused
        for entry in ("run.sh", "tools/sign_release.py", "install.sh"):
            with self.assertRaises(Refused, msg=f"{entry} was allowed"):
                safe_members(self.zip_of([(entry, "x")]))

    def test_a_zip_cannot_smuggle_in_a_link(self):
        from salaah.update import safe_members, Refused
        with self.assertRaises(Refused):
            safe_members(self.zip_of([("salaah/ok.py", "x")], symlink="salaah/sneaky"))

    def test_an_honest_zip_goes_through(self):
        from salaah.update import safe_members
        good = self.zip_of([("salaah/ui.py", "x"), ("assets/content/steps.json", "{}")])
        self.assertEqual(2, len(safe_members(good)))

    def test_a_download_that_does_not_match_its_hash_is_refused(self):
        """Catches a damaged download, and a file swapped for one the manifest did not describe."""
        import hashlib
        import tempfile
        import zipfile
        from pathlib import Path
        from salaah.update import Installer, Release, Refused
        with tempfile.TemporaryDirectory() as room:
            room = Path(room)
            zip_path = room / "r.zip"
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("salaah/x.py", "x")
                z.writestr("assets/y.json", "{}")
            right = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            installer = Installer(room)
            with self.assertRaises(Refused):
                installer.unpack(zip_path, Release("9.9", "u", "0" * 64))
            self.assertTrue(installer.unpack(zip_path, Release("9.9", "u", right)).is_dir(),
                            "the honest one should unpack")

    def test_installing_keeps_the_old_version_and_can_put_it_back(self):
        """The mat has no keyboard. A version that will not start has to undo itself."""
        import hashlib
        import tempfile
        import zipfile
        from pathlib import Path
        from salaah.update import Installer, Release
        with tempfile.TemporaryDirectory() as room:
            room = Path(room)
            (room / "salaah").mkdir()
            (room / "assets").mkdir()
            (room / "salaah" / "mark").write_text("old")
            (room / "assets" / "mark").write_text("old")
            zip_path = room / "r.zip"
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("salaah/mark", "new")
                z.writestr("assets/mark", "new")
            release = Release("9.9", "u", hashlib.sha256(zip_path.read_bytes()).hexdigest())
            installer = Installer(room)
            installer.swap(installer.unpack(zip_path, release), release, "1.12")

            self.assertEqual("new", (room / "salaah" / "mark").read_text())
            self.assertEqual("old", (room / "salaah.prev" / "mark").read_text(),
                             "the version it replaced has to be kept")
            self.assertEqual("9.9", installer.state()["trial"], "it should be on trial")

            self.assertTrue(installer.roll_back())
            self.assertEqual("old", (room / "salaah" / "mark").read_text(), "not put back")
            self.assertEqual("old", (room / "assets" / "mark").read_text(),
                             "both folders have to go back, or the two disagree")
            self.assertFalse(installer.state().get("trial"), "the trial should be over")

    def test_a_version_that_settles_is_not_rolled_back(self):
        import tempfile
        from pathlib import Path
        from salaah.update import Installer
        with tempfile.TemporaryDirectory() as room:
            installer = Installer(Path(room))
            installer.write_state(trial="9.9", was="1.12", attempts=0)
            installer.settled()
            self.assertFalse(installer.state().get("trial"))
            self.assertEqual("9.9", installer.state()["installed"])
            self.assertFalse(installer.roll_back(), "nothing on trial, so nothing to undo")

    def test_the_guard_is_not_part_of_what_an_update_replaces(self):
        """run.sh puts the old version back when a new one will not start. If an update could
        replace it, a bad release could take the safety net with it."""
        from salaah.update import REPLACES
        self.assertNotIn("run.sh", REPLACES)
        self.assertNotIn("tools", REPLACES)
        self.assertEqual(("salaah", "assets"), REPLACES)

    def test_the_built_in_key_is_a_real_one(self):
        import base64
        from salaah.update import PUBLIC_KEY
        self.assertEqual(32, len(base64.b64decode(PUBLIC_KEY, validate=True)),
                         "an Ed25519 public key is 32 bytes")


class BacklightTest(unittest.TestCase):
    """Turning the monitor's real backlight down, over the cable that carries the picture."""

    @staticmethod
    def monitor(detect_ok=True, present=True, fails=False, slow=0.0):
        """A stand-in for ddcutil: records what it was asked to do."""
        import subprocess
        import time
        asked = []

        def run(args, **kw):
            asked.append(args)
            if fails:
                raise subprocess.SubprocessError("the monitor said nothing")
            if slow:
                time.sleep(slow)
            out = "Display 1\n" if detect_ok else ""
            return SimpleNamespace(returncode=0 if detect_ok else 1, stdout=out, stderr="")

        return run, (lambda name: "/usr/bin/ddcutil" if present else None), asked

    # Exactly what a mat reports: the monitor answers, the small posture screen does not.
    TWO_SCREENS = """Display 1
   I2C bus:  /dev/i2c-13
   DRM connector:              card1-HDMI-A-1
   EDID synopsis:
      Model:                   RTK FHD HDR
   VCP version:         2.2

Invalid display
   I2C bus:  /dev/i2c-14
   DRM connector:              card1-HDMI-A-2
   EDID synopsis:
      Model:                   MPI7002
   DDC communication failed
"""

    def test_it_says_which_screen_it_means(self):
        """A mat has two screens on one bus. The little posture screen has no brightness and
        reports DDC communication failed; a command that does not say which display it means
        may go nowhere at all."""
        import subprocess
        from salaah.backlight import Backlight
        asked = []

        def run(args, **kw):
            asked.append(args)
            out = self.TWO_SCREENS if "detect" in args else ""
            return SimpleNamespace(returncode=0, stdout=out, stderr="")

        light = Backlight(run=run, finder=lambda name: "/usr/bin/ddcutil")
        self.assertTrue(light.available)
        self.assertEqual("1", light.which, "it should pick the display that answered")
        light.set(45)
        light.settle()
        sent = [a for a in asked if "setvcp" in a][-1]
        self.assertIn("--display", sent, "the command must name a display")
        self.assertEqual("1", sent[sent.index("--display") + 1])

    def test_a_screen_that_cannot_talk_is_not_mistaken_for_one_that_can(self):
        """If the only screen present is the posture screen, there is nothing to turn down."""
        from salaah.backlight import Backlight
        only_the_little_one = "Invalid display\n   DDC communication failed\n"

        def run(args, **kw):
            return SimpleNamespace(returncode=1, stdout=only_the_little_one, stderr="")

        light = Backlight(run=run, finder=lambda name: "/usr/bin/ddcutil")
        self.assertFalse(light.available)

    def test_a_monitor_that_answers_is_used(self):
        from salaah.backlight import Backlight
        run, finder, asked = self.monitor()
        light = Backlight(run=run, finder=finder)
        self.assertTrue(light.available)
        light.set(40)
        light.settle()
        sent = [a for a in asked if "setvcp" in a][-1]
        self.assertEqual(["10", "40"], sent[-2:], f"asked: {sent}")

    def test_without_ddcutil_nothing_is_attempted(self):
        from salaah.backlight import Backlight
        run, finder, asked = self.monitor(present=False)
        light = Backlight(run=run, finder=finder)
        self.assertFalse(light.available)
        light.set(40)
        light.settle()
        self.assertEqual([], asked, "a mat without ddcutil should not be running commands")

    def test_a_monitor_that_does_not_answer_is_left_alone(self):
        from salaah.backlight import Backlight
        run, finder, asked = self.monitor(detect_ok=False)
        light = Backlight(run=run, finder=finder)
        self.assertFalse(light.available)

    def test_the_answer_is_only_worked_out_once(self):
        """Asking is slow, and the answer cannot change without the cable changing."""
        from salaah.backlight import Backlight
        run, finder, asked = self.monitor()
        light = Backlight(run=run, finder=finder)
        for _ in range(5):
            light.available
        self.assertEqual(1, sum(1 for a in asked if "detect" in a))

    def test_dragging_the_slider_does_not_queue_up_a_minute_of_work(self):
        """DDC is slow. Every value a dragged slider produces would still be arriving long
        after the person let go, so the ones overtaken on the way are dropped."""
        from salaah.backlight import Backlight
        run, finder, asked = self.monitor(slow=0.02)
        light = Backlight(run=run, finder=finder)
        self.assertTrue(light.available)
        for value in range(100, 30, -1):        # a finger sweeping down the bar
            light.set(value)
        light.settle()
        sent = [a[-1] for a in asked if a[1] == "setvcp"]
        self.assertLess(len(sent), 20, f"far too many commands sent: {len(sent)}")
        self.assertEqual("31", sent[-1], "the last thing sent must be where the finger stopped")

    def test_it_never_turns_the_backlight_off(self):
        from salaah.backlight import Backlight, LEAST
        run, finder, asked = self.monitor()
        light = Backlight(run=run, finder=finder)
        light.set(0)
        light.settle()
        self.assertEqual(str(LEAST), [a[-1] for a in asked if a[1] == "setvcp"][-1])

    def test_a_monitor_that_stops_answering_is_not_a_crash(self):
        """It is a prayer mat. A monitor having a bad day must not take the app down with it."""
        from salaah.backlight import Backlight
        run, finder, asked = self.monitor()
        light = Backlight(run=run, finder=finder)
        self.assertTrue(light.available)
        broken, _, _ = self.monitor(fails=True)
        light.run = broken
        light.set(50)
        light.settle()                          # no exception reaches here


class ReleaseAddressTest(unittest.TestCase):
    """The signing tool refuses to sign a manifest that points at a file which will not be there.

    This class exists because of one real failure: a release was signed with the address
    .../releases/download/vN/salaah-1.20.zip -- the runbook's placeholder pasted literally into
    the tag, with the file name correct. The old guard compared only the file name, so it passed.
    The manifest verified, the mat trusted it, and then the download 404'd."""

    def tool(self):
        import importlib.util
        from pathlib import Path
        here = Path(__file__).resolve().parent.parent / "tools" / "release_names.py"
        spec = importlib.util.spec_from_file_location("release_names_under_test", here)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_both_tools_use_the_same_judgement(self):
        """Two copies of this rule would drift, and the drift would be silent."""
        from pathlib import Path
        tools = Path(__file__).resolve().parent.parent / "tools"
        for name in ("sign_release.py", "check_release.py"):
            self.assertIn("release_names", (tools / name).read_text(),
                          f"{name} should not have its own copy of the rule")

    def test_the_real_address_that_got_through(self):
        tool = self.tool()
        bad = "https://github.com/ProntoHS/Mysalaah/releases/download/vN/salaah-1.20.zip"
        self.assertTrue(tool.url_complaint(bad, "1.20"),
                        "this is the exact address that shipped a broken release")

    def test_a_wrong_tag_is_caught_even_when_the_file_name_is_right(self):
        tool = self.tool()
        for tag in ("vN", "v1.19", "1.20", "V1.20", "latest"):
            bad = f"https://github.com/a/b/releases/download/{tag}/salaah-1.20.zip"
            self.assertTrue(tool.url_complaint(bad, "1.20"), f"tag {tag} was allowed")

    def test_a_wrong_file_name_is_still_caught(self):
        tool = self.tool()
        for name in ("salaah-N.zip", "salaah-1.19.zip", "salaah.zip"):
            bad = f"https://github.com/a/b/releases/download/v1.20/{name}"
            self.assertTrue(tool.url_complaint(bad, "1.20"), f"file {name} was allowed")

    def test_the_right_address_goes_through(self):
        tool = self.tool()
        good = "https://github.com/ProntoHS/Mysalaah/releases/download/v1.20/salaah-1.20.zip"
        self.assertEqual("", tool.url_complaint(good, "1.20"))
        self.assertEqual("", tool.url_complaint(good + "/", "1.20"), "a trailing slash is fine")

    def test_somewhere_that_is_not_github_is_judged_on_the_file_name_alone(self):
        """The tool should stay usable if the zip is ever hosted elsewhere."""
        tool = self.tool()
        self.assertEqual("", tool.url_complaint("https://example.com/files/salaah-1.20.zip", "1.20"))
        self.assertTrue(tool.url_complaint("https://example.com/files/salaah-1.19.zip", "1.20"))

    def test_the_placeholder_is_named_as_a_placeholder(self):
        """Saying "N is the placeholder from the runbook" is the sentence that ends the confusion."""
        tool = self.tool()
        said = tool.url_complaint("https://example.com/x/vN/salaah-1.20.zip", "1.20")
        self.assertIn("placeholder", said.lower())


class MapTouchTest(unittest.TestCase):
    """Pointing the touchscreen at the panel it is printed on.

    The fixture below is the real wlr-randr output from the mat, trimmed: a 1024x600 panel
    rotated 270 next to a 1920x1080 monitor. Touching the small screen acted on the big one
    until this mapping existed."""

    REAL = '''HDMI-A-2 "Mediatrix Peripherals Inc MPI7002 MPI7002 (HDMI-A-2)"
  Make: Mediatrix Peripherals Inc
  Model: MPI7002
  Physical size: 410x260 mm
  Enabled: yes
  Modes:
    1024x600 px, 60.043999 Hz (preferred, current)
    1920x1080 px, 60.000000 Hz
    1280x720 px, 50.000000 Hz
  Position: 1920,0
  Transform: 270
  Scale: 1.000000
HDMI-A-1 "Invalid Vendor Codename - RTK RTK FHD HDR demoset-1 (HDMI-A-1)"
  Make: Invalid Vendor Codename - RTK
  Model: RTK FHD HDR
  Enabled: yes
  Modes:
    1920x1080 px, 60.000000 Hz (preferred, current)
    1280x720 px, 60.000000 Hz
    800x600 px, 60.317001 Hz
  Position: 0,0
  Transform: normal
  Scale: 1.000000
'''

    STUB = '<?xml version="1.0"?>\n<openbox_config xmlns="http://openbox.org/3.4/rc"/>\n'

    def tool(self):
        import importlib.util
        from pathlib import Path
        here = Path(__file__).resolve().parent.parent / "tools" / "map_touch.py"
        spec = importlib.util.spec_from_file_location("map_touch_under_test", here)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_it_picks_the_small_panel_out_of_the_real_output(self):
        tool = self.tool()
        found = tool.screens(self.REAL)
        self.assertEqual({"HDMI-A-2": 1024 * 600, "HDMI-A-1": 1920 * 1080}, found)
        self.assertEqual("HDMI-A-2", tool.smallest(found))

    def test_it_reads_the_mode_in_use_not_the_first_one_listed(self):
        """In the real output above, the current mode happens to be the first one listed, so it
        cannot tell these two apart. Here the small panel is running at 1024x600 while listing
        1920x1080 FIRST -- which is what a monitor set to a non-preferred mode looks like.
        Reading the wrong line makes the 7in panel look like the big screen and sends touch to
        the monitor: the original bug, restored."""
        tool = self.tool()
        awkward = """HDMI-A-2 "little panel (HDMI-A-2)"
  Modes:
    1920x1080 px, 60.000000 Hz (preferred)
    1280x720 px, 60.000000 Hz
    1024x600 px, 60.043999 Hz (current)
HDMI-A-1 "big monitor (HDMI-A-1)"
  Modes:
    3840x2160 px, 30.000000 Hz (preferred)
    1920x1080 px, 60.000000 Hz (current)
"""
        found = tool.screens(awkward)
        self.assertEqual({"HDMI-A-2": 1024 * 600, "HDMI-A-1": 1920 * 1080}, found)
        self.assertEqual("HDMI-A-2", tool.smallest(found))

    def test_it_refuses_to_guess_with_one_screen_or_two_the_same(self):
        tool = self.tool()
        self.assertEqual("", tool.smallest({"HDMI-A-1": 1920 * 1080}))
        self.assertEqual("", tool.smallest({}))
        self.assertEqual("", tool.smallest({"HDMI-A-1": 2073600, "HDMI-A-2": 2073600}))

    def test_the_stub_pi_os_ships_is_replaced_with_a_real_file(self):
        """Raspberry Pi OS ships a self-closing empty root: there is nothing to insert into."""
        tool = self.tool()
        out = tool.with_touch(self.STUB, "HDMI-A-2")
        self.assertIn("<mapToOutput>HDMI-A-2</mapToOutput>", out)
        self.assertIn("</openbox_config>", out)
        self.assertNotIn("/>", out.split("<touch>")[0].split("openbox_config")[-1],
                         "the self-closing root must be gone")
        import xml.etree.ElementTree as ET
        ET.fromstring(out)                                  # must be well-formed XML

    def test_an_existing_config_keeps_everything_it_had(self):
        tool = self.tool()
        mine = ('<?xml version="1.0"?>\n<openbox_config xmlns="http://openbox.org/3.4/rc">\n'
                '  <theme><name>Clearlooks</name></theme>\n</openbox_config>\n')
        out = tool.with_touch(mine, "HDMI-A-2")
        self.assertIn("Clearlooks", out, "the rest of the config must survive")
        self.assertIn("<mapToOutput>HDMI-A-2</mapToOutput>", out)
        import xml.etree.ElementTree as ET
        ET.fromstring(out)

    def test_a_config_it_does_not_understand_is_left_alone(self):
        """Better to print the block and let him paste it than to mangle a file."""
        tool = self.tool()
        for odd in ("<something_else>\n</something_else>\n",
                    "</openbox_config></openbox_config>"):
            with self.assertRaises(ValueError, msg=f"{odd!r} should not be edited"):
                tool.with_touch(odd, "HDMI-A-2")

    def test_the_block_says_which_screen(self):
        tool = self.tool()
        self.assertIn("HDMI-A-9", tool.touch_block("HDMI-A-9"))


class DuaContentTest(unittest.TestCase):
    """That every word of every du'a really is the Qur'an's.

    The du'as are slices of verses. This re-derives each one from assets/content/quran without
    going anywhere near the builder that wrote them, so a mistake in the builder cannot hide
    behind the builder's own arithmetic. It is the same discipline as check_quran.py: the thing
    that verifies must not be the thing that produced the value."""

    @staticmethod
    def assets():
        from pathlib import Path
        return Path(__file__).resolve().parent.parent / "assets"

    def duas(self):
        """Only the ones taken from the Qur'an. The du'as that come from hadith are not slices
        of verses and there is nothing here to re-derive them from -- they are checked against
        two corpora when they are built, and their own test says the file records that."""
        import json
        whole = json.loads((self.assets() / "content" / "duas" / "duas.json")
                           .read_text(encoding="utf-8"))
        return [d for d in whole["items"] if d.get("verses")]

    def verse(self, lang, surah, number):
        import json
        rows = json.loads((self.assets() / "content" / "quran" / lang / f"{surah}.json")
                          .read_text(encoding="utf-8"))
        for row in rows:
            if int(row["n"]) == number:
                return row
        self.fail(f"{lang} has no {surah}:{number}")

    def test_there_are_ten_of_them_each_with_everything_it_needs(self):
        duas = self.duas()
        self.assertEqual(10, len(duas))
        for d in duas:
            for field in ("key", "title", "ref", "verses", "arabic", "said", "text"):
                self.assertTrue(d.get(field), f"{d.get('ref')} has no {field}")
            self.assertEqual(len(set(x["key"] for x in duas)), len(duas), "keys must be unique")

    def test_every_arabic_word_comes_from_the_verses_it_names(self):
        """Word for word, in order, against the corpus. Catches a slice from the wrong verse,
        a slice that drifted, and any word that was typed rather than copied."""
        for d in self.duas():
            want = d["arabic"].split()
            got = []
            for surah, number in d["verses"]:
                got.extend(self.verse("ar", surah, number)["text"].split())
            # The du'a is the tail of the first verse plus the whole of any that follow, so its
            # words must appear in the corpus words as a contiguous run ending at the end.
            self.assertTrue(len(want) <= len(got), f"{d['ref']} is longer than its verses")
            self.assertEqual(got[len(got) - len(want):], want,
                             f"{d['ref']} does not match the Qur'an on disk")

    def test_the_transliteration_matches_the_same_words(self):
        for d in self.duas():
            want = d["said"].split()
            got = []
            for surah, number in d["verses"]:
                got.extend(self.verse("ar", surah, number)["said"].split())
            self.assertEqual(got[len(got) - len(want):], want, f"{d['ref']} transliteration")

    def test_arabic_and_transliteration_are_the_same_length(self):
        """One word of Arabic, one of transliteration. A mismatch means one was sliced in a
        different place from the other, which is how a du'a ends up saying two different things
        to the two people reading it."""
        for d in self.duas():
            self.assertEqual(len(d["arabic"].split()), len(d["said"].split()), d["ref"])

    def test_no_slice_cuts_into_a_word(self):
        for d in self.duas():
            whole = " ".join(self.verse("ar", s, n)["text"] for s, n in d["verses"])
            self.assertIn(d["arabic"], whole, f"{d['ref']} is not a clean slice")

    def test_every_translation_is_there_and_is_not_empty(self):
        for d in self.duas():
            for lang in ("en", "fr", "ur", "es", "zh"):
                self.assertTrue(d["text"].get(lang, "").strip(),
                                f"{d['ref']} has no {lang}")

    def test_the_untrimmed_translations_are_the_whole_verse(self):
        """Only English is trimmed. The other four keep the verse exactly as the corpus has it,
        because judging where a sentence turns in Urdu or Chinese is not something to guess at."""
        for d in self.duas():
            self.assertEqual(["en"], list(d["trimmed"]), d["ref"])
            for lang in ("fr", "ur", "es", "zh"):
                whole = " ".join(self.verse(lang, s, n).get("text", "") for s, n in d["verses"])
                self.assertEqual(" ".join(whole.split()), d["text"][lang], f"{d['ref']} {lang}")

    def test_the_english_is_a_slice_of_the_english_verse(self):
        """Trimmed, and quote marks dropped -- but every word still the translation's own."""
        for d in self.duas():
            whole = " ".join(self.verse("en", s, n).get("text", "") for s, n in d["verses"])
            for mark in '"“”«»':
                whole = whole.replace(mark, "")
            whole = " ".join(whole.split())
            self.assertIn(d["text"]["en"], whole, f"{d['ref']} English is not a slice")


class KalimaContentTest(unittest.TestCase):
    """The kalima were written from knowledge, not copied from a checked source. These tests
    cannot say the words are right -- only a reader of Arabic can. What they can do is make sure
    the file keeps saying so until somebody has looked."""

    def kalima(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "assets"
        return json.loads((root / "content" / "duas" / "kalima.json").read_text(encoding="utf-8"))

    def test_all_six_are_there_with_arabic_transliteration_and_meaning(self):
        items = self.kalima()["items"]
        self.assertEqual(6, len(items))
        for it in items:
            self.assertTrue(it["arabic"].strip(), it["key"])
            self.assertTrue(it["said"].strip(), it["key"])
            self.assertTrue(it["text"]["en"].strip(), it["key"])
            self.assertTrue(it["title"].strip(), it["key"])

    def test_the_file_records_that_the_arabic_has_been_read_over(self):
        """It used to say the opposite, and the test used to insist on that. Harry has since
        read the Arabic and asked for the pending note to come off the screen, so the file says
        reviewed and this says the same. The flag is the record of who checked it, which is why
        it is set rather than the screen just being quiet about it."""
        self.assertTrue(self.kalima()["reviewed"])

    def test_every_kalima_has_a_recording_and_times_for_all_of_its_words(self):
        """A recording timed against a different wording would light the wrong words, so the
        count has to match the Arabic exactly -- not be at least as long."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "assets"
        for number, item in enumerate(self.kalima()["items"], 1):
            self.assertEqual(f"kalima/{number}.mp3", item["audio"], item["key"])
            self.assertTrue((root / "audio" / item["audio"]).is_file(), item["audio"])
            self.assertEqual(len(item["arabic"].split()), len(item["times"]), item["key"])

    def test_the_times_run_forwards_and_stay_inside_the_recording(self):
        for item in self.kalima()["items"]:
            last = 0
            for start, end in item["times"]:
                self.assertLess(start, end, f"{item['key']} has a word of no length")
                self.assertGreaterEqual(start, last, f"{item['key']} goes backwards")
                last = start
            finish = item["times"][-1][1] / 1000.0
            self.assertLessEqual(finish, item["seconds"] + 0.01,
                                 f"{item['key']} runs past the end of its recording")

    def test_the_times_are_marked_as_estimated_because_they_are(self):
        """There is no aligner for these recordings and no published timings for them. The
        first and last moments are measured; the joins between words are worked out from how
        many letters each word has. Anything that reads these must be able to tell."""
        for item in self.kalima()["items"]:
            self.assertTrue(item["estimated"], item["key"])

    def test_the_arabic_is_arabic(self):
        """Catches a Latin letter or stray punctuation that wandered into the script -- the
        kind of thing that is invisible in a proportional font and wrong on the mat."""
        import unicodedata
        for it in self.kalima()["items"]:
            for ch in it["arabic"]:
                if ch == " ":
                    continue
                name = unicodedata.name(ch, "")
                self.assertIn("ARABIC", name, f"{it['key']} contains {ch!r} ({name})")


class PassagesTest(unittest.TestCase):
    """Reading either section off the disk, including off a disk that is missing things."""

    def loader(self, section, root=None):
        from pathlib import Path
        from salaah.passages import Passages
        return Passages(root or (Path(__file__).resolve().parent.parent / "assets"), section)

    def test_it_reads_both_sections(self):
        duas = self.loader("duas").items
        self.assertEqual(10, len([d for d in duas if d.ref and ":" in d.ref]),
                         "the ten Qur'anic du'as")
        self.assertGreaterEqual(len(duas), 33, "the du'as from hadith as well")
        self.assertEqual(6, len(self.loader("kalima").items))

    def test_the_kalima_are_checked_and_the_duas_are_not_yet(self):
        """The kalima have been read through. The du'as now carry lines lifted from the hadith
        collections whose English and filing nobody has been over, so the file says so -- and
        saying so is the thing that must not quietly stop being true."""
        self.assertTrue(self.loader("kalima").reviewed)
        self.assertFalse(self.loader("duas").reviewed)

    def test_a_kalima_knows_which_word_is_sounding(self):
        item = self.loader("kalima").at(0)
        self.assertTrue(item.times, "the first kalima should carry word times")
        for i, (start, end) in enumerate(item.times):
            middle = (start + end) / 2000.0
            self.assertEqual(i, item.word_at(middle), f"word {i} was not lit in its own middle")
        self.assertIsNone(item.word_at(item.times[-1][1] / 1000.0 + 5))

    def test_a_duaa_has_no_recording_of_its_own(self):
        """The du'as are Qur'an, so they are recited by the surah reader, not from here."""
        self.assertEqual("", self.loader("duas").at(0).audio)

    def test_times_are_never_read_past_the_words_they_belong_to(self):
        """A recording timed against a longer wording would otherwise light a word that is not
        on the screen, and the highlight would point at nothing."""
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as room:
            folder = Path(room) / "content" / "duas"
            folder.mkdir(parents=True)
            (folder / "kalima.json").write_text(json.dumps({"items": [
                {"key": "short", "arabic": "\u0627 \u0628", "said": "a b",
                 "text": {"en": "x"},
                 "times": [[0, 100], [100, 200], [200, 300], [300, 400]]},
            ]}), encoding="utf-8")
            item = self.loader("kalima", Path(room)).at(0)
            self.assertEqual(2, len(item.arabic.split()))
            self.assertEqual(2, len(item.times), "four times for two words should be cut down")

    def test_a_section_only_offers_languages_it_actually_has(self):
        """The kalima are English only. Offering French and then showing English would be
        worse than not offering it."""
        self.assertEqual(("en", "fr", "ur", "es", "zh"), self.loader("duas").languages())
        self.assertEqual(("en",), self.loader("kalima").languages())

    def test_a_missing_meaning_falls_back_to_english_rather_than_to_nothing(self):
        item = self.loader("kalima").at(0)
        self.assertEqual(item.text["en"], item.meaning("fr"))
        self.assertEqual(item.text["en"], item.meaning("zh"))

    def test_a_chosen_language_that_exists_is_used(self):
        item = self.loader("duas").at(0)
        self.assertNotEqual(item.meaning("en"), item.meaning("zh"))
        self.assertTrue(item.meaning("zh"))

    def test_a_missing_file_is_empty_rather_than_a_crash(self):
        """A half-copied mat shows what it has. It does not refuse to start."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as room:
            nothing = self.loader("duas", Path(room))
            self.assertFalse(nothing.there)
            self.assertEqual([], nothing.items)
            self.assertEqual((), nothing.languages())
            self.assertIsNone(nothing.at(0))

    def test_rubbish_in_the_file_is_skipped_not_shown(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as room:
            folder = Path(room) / "content" / "duas"
            folder.mkdir(parents=True)
            (folder / "duas.json").write_text(json.dumps([
                {"key": "fine", "arabic": "الحمد", "said": "alhamd",
                 "text": {"en": "praise"}},
                {"key": "no arabic at all"},
                "not even a row",
            ]), encoding="utf-8")
            got = self.loader("duas", Path(room)).items
            self.assertEqual(1, len(got))
            self.assertEqual("fine", got[0].key)

    def test_a_broken_file_is_empty_rather_than_a_crash(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as room:
            folder = Path(room) / "content" / "duas"
            folder.mkdir(parents=True)
            (folder / "duas.json").write_text("{ this is not json", encoding="utf-8")
            self.assertEqual([], self.loader("duas", Path(room)).items)

    def test_the_list_row_shows_the_opening_words(self):
        item = self.loader("duas").at(0)
        self.assertEqual(item.arabic.split()[:4], item.opening().split())


class VerseStoreTest(unittest.TestCase):
    """Fetching verse recordings, and every way that can go wrong.

    None of these touch the network. The opener is handed in, so a test can be a CDN that is
    slow, truncating, lying about the size, or simply not there."""

    def answer(self, data, length=True, size=None):
        import io

        class Answer(io.BytesIO):
            def __init__(self, blob):
                super().__init__(blob)
                self.headers = {} if not length else {
                    "Content-Length": str(size if size is not None else len(blob))}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False
        return Answer(data)

    def store(self, opener=None, **kw):
        import tempfile
        from pathlib import Path
        from salaah.recite import Store
        room = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(room, ignore_errors=True))
        return Store(room=room, opener=opener, **kw)

    def good(self, size=5000):
        def opener(request, timeout=None):
            return self.answer(b"ID3" + b"\0" * size)
        return opener

    def test_the_address_is_the_one_everyayah_uses(self):
        from salaah.recite import url_for
        self.assertEqual("https://everyayah.com/data/Alafasy_128kbps/001001.mp3", url_for(1, 1))
        self.assertEqual("https://everyayah.com/data/Alafasy_128kbps/002286.mp3", url_for(2, 286))
        self.assertEqual("https://everyayah.com/data/Alafasy_128kbps/114006.mp3", url_for(114, 6))

    def test_a_verse_is_fetched_once_and_then_read_off_the_disk(self):
        s = self.store(self.good())
        first = s.fetch(1, 1)
        self.assertIsNotNone(first)
        self.assertTrue(s.have(1, 1))
        self.assertEqual(1, s.tried)
        self.assertEqual(first, s.fetch(1, 1))
        self.assertEqual(1, s.tried, "the second ask must not go back to the network")

    def test_a_half_finished_download_is_never_left_where_it_could_be_played(self):
        """The file is written beside its real name and moved into place only when whole. A
        recitation cut off in the middle would be worse than none."""
        from pathlib import Path

        def breaks(request, timeout=None):
            raise OSError("the wifi went")
        s = self.store(breaks)
        self.assertIsNone(s.fetch(1, 1))
        self.assertFalse(s.have(1, 1))
        self.assertEqual([], list(Path(s.room).rglob("*.part")), "a .part file was left behind")
        self.assertEqual([], list(Path(s.room).rglob("*.mp3")))

    def test_a_download_that_is_far_too_small_is_thrown_away(self):
        """An error page served with a 200 is a few hundred bytes of HTML, not a recitation."""
        s = self.store(lambda request, timeout=None: self.answer(b"<html>nope</html>"))
        self.assertIsNone(s.fetch(1, 1))
        self.assertFalse(s.have(1, 1))

    def test_something_far_too_big_is_refused_before_it_is_downloaded(self):
        from salaah.recite import MOST
        pulled = []

        def huge(request, timeout=None):
            pulled.append(request.full_url)
            return self.answer(b"x" * 10, size=MOST * 4)
        s = self.store(huge)
        self.assertIsNone(s.fetch(1, 1))
        self.assertEqual(1, len(pulled), "it should look, once, and decline")

    def test_a_verse_that_cannot_be_had_is_not_asked_for_forever(self):
        """Otherwise the reader sits there hammering a CDN that has already said no."""
        import urllib.error

        def gone(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 404, "nope", {}, None)
        s = self.store(gone)
        self.assertIsNone(s.fetch(1, 1))
        self.assertTrue(s.gave_up_on(1, 1))
        self.assertFalse(s.gave_up_on(1, 2))

    def test_it_says_who_it_is(self):
        """A mat fetching from somebody else's CDN should be identifiable."""
        seen = {}

        def opener(request, timeout=None):
            seen.update(request.headers)
            return self.answer(b"ID3" + b"\0" * 5000)
        self.store(opener).fetch(1, 1)
        agent = next(v for k, v in seen.items() if k.lower() == "user-agent")
        self.assertIn("Salaah/", agent)
        self.assertIn("github.com/ProntoHS", agent)

    def test_the_cache_is_not_inside_the_app_folder(self):
        """An update replaces the app folder wholesale. Keeping a gigabyte of recitation in
        there would throw it away every time the version changed."""
        from pathlib import Path
        from salaah.recite import Store
        from salaah.update import REPLACES
        where = Store().path_for(1, 1)
        self.assertNotIn("assets", where.parts)
        for folder in REPLACES:
            self.assertNotIn(folder, where.parts, f"the cache sits inside {folder}")
        self.assertIn(".salaah", where.parts)
        self.assertTrue(str(where).endswith("001001.mp3"))

    def test_asking_in_the_background_fetches_what_is_missing_and_skips_what_is_not(self):
        got = []

        def opener(request, timeout=None):
            got.append(request.full_url)
            return self.answer(b"ID3" + b"\0" * 5000)
        s = self.store(opener)
        s.fetch(1, 1)
        s.want([(1, 1), (1, 2), (1, 3)])
        s.settle()
        names = sorted(u.rsplit("/", 1)[-1] for u in got)
        self.assertEqual(["001001.mp3", "001002.mp3", "001003.mp3"], names)
        self.assertEqual(1, names.count("001001.mp3"), "the one already here was fetched twice")

    def test_a_broken_cdn_does_not_take_the_background_thread_down(self):
        def explode(request, timeout=None):
            raise ValueError("something nobody expected")
        s = self.store(explode)
        s.want([(1, 1), (1, 2)])
        s.settle()                       # no exception reaches here, and it finished


class WordTimesTest(unittest.TestCase):
    """Which word is sounding, and the twelve verses where we must not guess."""

    # Worked out in this conversation by comparing quran-align's word counts with our own
    # Arabic, verse by verse. If this list changes, the text or the timings changed under us.
    WHOLE = [(2, 72), (2, 181), (8, 6), (10, 1), (13, 1), (13, 37),
             (15, 7), (27, 20), (36, 22), (37, 164), (41, 47), (50, 34)]

    def times(self):
        from pathlib import Path
        from salaah.recite import WordTimes
        return WordTimes(Path(__file__).resolve().parent.parent / "assets")

    def test_the_timings_are_on_the_mat(self):
        self.assertTrue(self.times().there)

    def test_every_surah_has_timings(self):
        t = self.times()
        for surah in range(1, 115):
            self.assertTrue(t.known(surah), f"surah {surah} has no timings")

    def test_the_right_word_is_lit_at_the_right_moment(self):
        t = self.times()
        words = t.words(1, 1)
        self.assertTrue(words, "al-Fatihah's first verse should have word timings")
        for start_word, _end, start_ms, end_ms in words:
            middle = (start_ms + end_ms) / 2000.0
            self.assertEqual(start_word, t.word_at(1, 1, middle),
                             f"the word starting at {start_ms}ms was not lit in its own middle")

    def test_nothing_is_lit_before_the_first_word_or_after_the_last(self):
        t = self.times()
        words = t.words(1, 1)
        self.assertIsNone(t.word_at(1, 1, (words[0][2] - 20) / 1000.0))
        self.assertIsNone(t.word_at(1, 1, words[-1][3] / 1000.0 + 5))

    def test_the_twelve_verses_we_cannot_be_sure_of_are_marked(self):
        """quran-align counts words by splitting Tanzil's text; our Arabic is quranenc's. In
        twelve verses the two split a word differently, and lighting a word there would light
        the wrong one -- so no word is lit in those twelve."""
        t = self.times()
        for surah, verse in self.WHOLE:
            self.assertTrue(t.whole_only(surah, verse), f"{surah}:{verse} should be marked")
            self.assertEqual([], t.words(surah, verse),
                             f"{surah}:{verse} must carry no word timings at all")

    def test_nothing_else_is_marked(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "assets" / "content" / "quran" / "timings"
        marked = []
        for surah in range(1, 115):
            spot = json.loads((root / f"{surah}.json").read_text(encoding="utf-8"))
            marked.extend((surah, v) for v in spot.get("whole", []))
        self.assertEqual(sorted(self.WHOLE), sorted(marked))

    def test_every_verse_with_timings_has_one_per_word_of_our_own_arabic(self):
        """The check that makes the highlight safe, run against what actually ships: for every
        verse we will light word by word, the timings must account for exactly as many words as
        we are going to draw. This is the same comparison the builder makes, done again on the
        built files, so a builder bug cannot hide behind itself."""
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "assets" / "content" / "quran"
        wrong, checked = [], 0
        for surah in range(1, 115):
            arabic = {int(v["n"]): len(v["text"].split())
                      for v in json.loads((root / "ar" / f"{surah}.json")
                                          .read_text(encoding="utf-8"))}
            spot = json.loads((root / "timings" / f"{surah}.json").read_text(encoding="utf-8"))
            for verse, words in spot.get("words", {}).items():
                checked += 1
                if max(w[1] for w in words) != arabic[int(verse)]:
                    wrong.append(f"{surah}:{verse}")
        self.assertEqual([], wrong)
        self.assertEqual(6224, checked, "6224 verses should be safe for word-by-word")

    def test_timings_never_run_backwards(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "assets" / "content" / "quran" / "timings"
        for surah in range(1, 115):
            spot = json.loads((root / f"{surah}.json").read_text(encoding="utf-8"))
            for verse, words in spot.get("words", {}).items():
                last = -1
                for _ws, _we, start, end in words:
                    self.assertLess(start, end, f"{surah}:{verse} has a word of no length")
                    self.assertGreaterEqual(start, last, f"{surah}:{verse} goes backwards")
                    last = start

    def test_a_mat_with_no_timings_asks_for_nothing_and_crashes_nowhere(self):
        import tempfile
        from pathlib import Path
        from salaah.recite import WordTimes
        with tempfile.TemporaryDirectory() as room:
            t = WordTimes(Path(room))
            self.assertFalse(t.there)
            self.assertFalse(t.known(1))
            self.assertEqual([], t.words(1, 1))
            self.assertIsNone(t.word_at(1, 1, 0.5))
            self.assertFalse(t.whole_only(1, 1))


class DuaCategoriesTest(unittest.TestCase):
    """The eighteen kinds of du'a: the drawing, the filing and the words for them."""

    def setUp(self):
        from salaah.duamenu import CATEGORIES
        self.cats = CATEGORIES
        self.assets = Path(__file__).resolve().parent.parent / "assets"

    def duas(self):
        import json
        return json.loads((self.assets / "content" / "duas" / "duas.json")
                          .read_text(encoding="utf-8"))["items"]

    def test_every_category_has_a_tile_drawn_for_it(self):
        for cat in self.cats:
            picture = self.assets / "duas-menu" / f"{cat}.png"
            self.assertTrue(picture.is_file(), f"nothing drawn for {cat}")

    def test_no_tile_is_drawn_that_the_menu_has_no_place_for(self):
        """A picture left over from an older cut would never be shown and would quietly rot."""
        drawn = {p.stem for p in (self.assets / "duas-menu").glob("*.png")}
        self.assertEqual(set(self.cats), drawn)

    def test_every_dua_is_filed_under_a_category_that_exists(self):
        for d in self.duas():
            self.assertTrue(d.get("cats"), f"{d['key']} is filed nowhere")
            for cat in d["cats"]:
                self.assertIn(cat, self.cats, f"{d['key']} is filed under {cat!r}")

    def test_every_kind_has_at_least_three_duas_behind_it(self):
        """Three, not two. Two are shown at a time, so a kind holding exactly two shows the
        same pair on every visit and the shuffling has nothing to work with."""
        import collections
        how_many = collections.Counter(c for d in self.duas() for c in d["cats"])
        thin = {c: how_many[c] for c in self.cats if how_many[c] < 3}
        self.assertEqual({}, thin, f"these kinds have fewer than three: {thin}")

    def test_the_hadith_duas_carry_their_source_and_are_marked_unchecked(self):
        """The Arabic was lifted from two corpora and nothing was typed from memory, but no
        reviewer has been through the English or the filing. The file must say so."""
        import json
        whole = json.loads((self.assets / "content" / "duas" / "duas.json")
                           .read_text(encoding="utf-8"))
        self.assertFalse(whole["reviewed"], "the du'as are marked as checked, and they are not")
        from_hadith = [d for d in self.duas() if d.get("from") == "hadith"]
        self.assertGreaterEqual(len(from_hadith), 20)
        for d in from_hadith:
            self.assertTrue(d.get("ref", "").strip(), f"{d['key']} does not say where it is from")
            self.assertTrue(d.get("arabic", "").strip(), f"{d['key']} has no Arabic")

    def test_every_pack_can_name_every_category(self):
        """A category with no word for it would head its screen with a blank."""
        packs = available_packs(self.assets)
        self.assertGreaterEqual(len(packs), 6, "the packs did not load")
        for lang, pack in packs.items():
            for cat in self.cats:
                said = pack.ui.get(f"dua.{cat}", "")
                self.assertTrue(said.strip(), f"{lang} cannot name {cat}")

    def test_the_names_are_that_language_and_not_a_copy_of_the_english(self):
        """A pack filled in by copying the English would pass the test above and tell a Urdu
        reader nothing. The five other packs must differ from English somewhere."""
        packs = available_packs(self.assets)
        english = packs["en"]
        for lang, pack in packs.items():
            if lang == "en":
                continue
            same = [c for c in self.cats
                    if pack.ui.get(f"dua.{c}") == english.ui.get(f"dua.{c}")]
            self.assertLess(len(same), len(self.cats) // 2,
                            f"{lang} is mostly the English words: {same}")


class RecutArtworkTest(unittest.TestCase):
    """The main mosque and the six-kalima mosque, cut to the shape of the screen they fill."""

    def setUp(self):
        self.assets = Path(__file__).resolve().parent.parent / "assets"

    SHAPE = 1920 / 1008          # the screen under the strip, at 1080p

    def described(self, folder):
        import json
        return json.loads((self.assets / folder / "mosque.json").read_text(encoding="utf-8"))

    def test_each_drawing_is_the_shape_of_the_screen(self):
        for folder in ("mosque", "kalima", "welcome"):
            wide, tall = self.described(folder)["size"]
            self.assertLess(abs(wide / tall - self.SHAPE), 0.02,
                            f"{folder} is {wide/tall:.3f}, the screen is {self.SHAPE:.3f}")

    def test_what_the_file_says_is_the_size_of_the_picture(self):
        from salaah.qt import QtGui
        for folder in ("mosque", "kalima", "welcome"):
            said = self.described(folder)["size"]
            image = QtGui.QImage(str(self.assets / folder / "mosque.png"))
            self.assertEqual(said, [image.width(), image.height()],
                             f"{folder}: the file and the picture disagree")

    def test_no_dead_sky_is_left_above_the_drawing(self):
        from salaah.qt import QtGui
        for folder in ("mosque", "kalima"):
            image = QtGui.QImage(str(self.assets / folder / "mosque.png"))
            top = next((y for y in range(image.height())
                        if any(image.pixelColor(x, y).alpha() > 40
                               for x in range(0, image.width(), 5))), None)
            self.assertIsNotNone(top, f"{folder} is empty")
            self.assertLess(top, image.height() * 0.08,
                            f"{folder}: {top}px of empty sky above the drawing")

    def test_every_box_still_sits_inside_the_picture(self):
        """The boxes were measured on the taller canvas. Crop and forget to move them and an
        arch lights up somewhere the drawing no longer is."""
        for folder in ("mosque", "kalima"):
            said = self.described(folder)
            wide, tall = said["size"]
            boxes = [a["box"] for a in said["arches"].values()]
            boxes.append(said["clock"]["box"])
            boxes.extend(said["minarets"].values())
            for box in boxes:
                x0, y0, x1, y1 = box
                self.assertTrue(0 <= y0 < y1 <= tall and 0 <= x0 < x1 <= wide,
                                f"{folder}: {box} is off a {wide}x{tall} picture")

    def test_each_arch_box_is_over_a_light_panel(self):
        """The real check: not that the numbers are inside the picture, but that what is under
        them is still the panel they are meant to light."""
        from salaah.qt import QtGui
        for folder in ("mosque", "kalima"):
            image = QtGui.QImage(str(self.assets / folder / "mosque.png"))
            for name, arch in self.described(folder)["arches"].items():
                x0, y0, x1, y1 = arch["box"]
                lit = total = 0
                for y in range(y0, y1, 4):
                    for x in range(x0, x1, 4):
                        c = image.pixelColor(x, y)
                        total += 1
                        lit += (c.alpha() > 40
                                and (c.red() + c.green() + c.blue()) / 3 > 200)
                self.assertGreater(lit / total, 0.55,
                                   f"{folder}/{name}: the box is not over a panel any more")


class HighLatitudeTest(unittest.TestCase):
    """Fajr and Isha in the weeks when it never gets dark enough for them to have a moment.

    At Bury the sun only reaches about 13 degrees below the horizon at midsummer, and Fajr is
    defined at 18. The sums are right to return nothing; a mat blank for eleven weeks a year is
    still no use. Aqrab al-Ayyam holds the times from the nearest date that did have them.
    """

    BURY = None

    def setUp(self):
        from salaah.prayer_times import Place
        self.BURY = Place(53.5933, -2.2966, "Bury")
        self.MAKKAH = Place(21.42, 39.83, "Makkah")

    def days(self, year=2026):
        from datetime import date, timedelta
        d, out = date(year, 1, 1), []
        while d <= date(year, 12, 31):
            out.append(d)
            d += timedelta(days=1)
        return out

    def test_without_the_rule_bury_really_does_go_blank(self):
        """The problem this exists for. If this ever stops being true the rule is moot and the
        rest of these tests would be passing over nothing."""
        from salaah.prayer_times import times_for
        blank = [d for d in self.days()
                 if times_for(d, self.BURY, high_latitude="none")["fajr"] is None]
        self.assertGreater(len(blank), 30, "Bury should lose Fajr for weeks in summer")
        self.assertTrue(all(d.month in (5, 6, 7) for d in blank),
                        "the blank days should all be in the summer")

    def test_with_the_rule_no_day_of_the_year_is_blank(self):
        from salaah.prayer_times import times_for
        for d in self.days():
            got = times_for(d, self.BURY)
            for which in ("fajr", "isha"):
                self.assertIsNotNone(got[which], f"{d} has no {which}")

    def test_the_borrowed_time_is_the_nearest_days_and_not_invented(self):
        """Not just 'a time appeared'. The time shown on a blank day must be exactly the time
        the nearest dated day really has -- checked by working that day out separately."""
        from datetime import date
        from salaah.prayer_times import times_for, nearest_day_with, local_utc_offset
        for d in (date(2026, 6, 1), date(2026, 6, 21), date(2026, 7, 20)):
            offset = local_utc_offset(d)
            shown = times_for(d, self.BURY)
            for which in ("fajr", "isha"):
                found = nearest_day_with(d, self.BURY, "hanafi", offset, which)
                self.assertIsNotNone(found, f"nothing found for {which} on {d}")
                _value, borrowed = found
                real = times_for(borrowed, self.BURY, utc_offset_hours=offset,
                                 high_latitude="none")[which]
                self.assertIsNotNone(real, f"{borrowed} was borrowed from but has no {which}")
                self.assertEqual(real, shown[which],
                                 f"{d} shows {shown[which]} for {which}, but {borrowed} "
                                 f"really has {real}")

    def test_it_borrows_from_the_nearest_side_not_always_backwards(self):
        """Late July is closer to the far edge of the gap than the near one. Always searching
        backwards would hold May's times into August, which is a different method."""
        from datetime import date
        from salaah.prayer_times import nearest_day_with, local_utc_offset
        early, late = date(2026, 5, 20), date(2026, 7, 24)
        got_early = nearest_day_with(early, self.BURY, "hanafi", local_utc_offset(early), "fajr")
        got_late = nearest_day_with(late, self.BURY, "hanafi", local_utc_offset(late), "fajr")
        self.assertLess(got_early[1], early, "the May day should borrow from before it")
        self.assertGreater(got_late[1], late, "the July day should borrow from after it")

    def test_the_rule_changes_nothing_where_it_is_not_needed(self):
        """Makkah never loses a prayer, and Bury outside the summer does not either. The rule
        must not touch a day that has its own time -- a rule that quietly rewrote every day
        would pass every test above."""
        from salaah.prayer_times import times_for
        for place in (self.MAKKAH, self.BURY):
            same = 0
            for d in self.days():
                plain = times_for(d, place, high_latitude="none")
                ruled = times_for(d, place)
                for which, value in plain.items():
                    if value is not None:
                        self.assertEqual(value, ruled[which],
                                         f"{place.name} {d}: the rule moved {which}")
                        same += 1
            self.assertGreater(same, 2000, "hardly anything was compared")

    def test_none_leaves_it_exactly_as_it_was(self):
        from salaah.prayer_times import times_for
        blank = [d for d in self.days()
                 if times_for(d, self.BURY, high_latitude="none")["isha"] is None]
        self.assertTrue(blank, "the setting is not doing anything to test")

    def test_the_setting_is_what_decides_it(self):
        """The mat must read the setting rather than the rule being welded on."""
        from datetime import date
        from salaah.prayer_times import times_for, HIGH_LATITUDE
        midsummer = date(2026, 6, 21)
        self.assertEqual(("none", "nearest_day"), HIGH_LATITUDE)
        self.assertIsNone(times_for(midsummer, self.BURY, high_latitude="none")["fajr"])
        self.assertIsNotNone(times_for(midsummer, self.BURY, high_latitude="nearest_day")["fajr"])

    def test_it_gives_up_rather_than_searching_for_ever(self):
        """Inside the Arctic circle there may be no such night at all. It must stop and say
        nothing rather than spin, and nothing is the honest answer there."""
        from datetime import date
        from salaah.prayer_times import times_for, Place
        pole = Place(89.0, 0.0, "the pole")
        got = times_for(date(2026, 6, 21), pole)
        self.assertIsNone(got["fajr"], "it invented a Fajr at the north pole")


class WifiTest(unittest.TestCase):
    """Joining a network, tested against recorded nmcli output on a machine with no wifi.

    Everything goes through a runner that can be swapped, so the real nmcli is never needed.
    The recordings below are what Harry's mat actually printed, including its own network
    appearing five times.
    """

    # straight from the mat: one network, five access points, one of them weak
    REAL_SCAN = ("NOVA_26DU_A2:95:WPA2\n"
                 "NOVA_26DU_A2:95:WPA2\n"
                 "NOVA_26DU_A2:89:WPA2\n"
                 "NOVA_26DU_A2:77:WPA2\n"
                 "NOVA_26DU_A2:64:WPA2\n")
    REAL_CONNECTIONS = ("NOVA_26DU_A2:802-11-wireless\n"
                        "lo:loopback\n"
                        "Wired connection 1:802-3-ethernet\n")

    def wifi(self, replies, online=True):
        """A Wifi whose nmcli is a lookup table, and a note of what was asked."""
        from salaah.network import Wifi
        asked = []

        def runner(args, timeout=None):
            asked.append(list(args))
            for match, answer in replies:
                if all(m in args for m in match):
                    return answer
            return 1, "", "unexpected"

        w = Wifi(runner=runner, resolver=lambda name=None: online)
        w.asked = asked
        return w

    def test_the_same_network_seen_five_times_is_listed_once(self):
        w = self.wifi([(["wifi", "list"], (0, self.REAL_SCAN, "")),
                       (["connection", "show"], (0, self.REAL_CONNECTIONS, ""))])
        found = w.scan()
        self.assertEqual(1, len(found), f"listed {[n.name for n in found]}")
        self.assertEqual("NOVA_26DU_A2", found[0].name)
        self.assertEqual(95, found[0].strength, "the strongest of the five should be kept")

    def test_a_saved_network_is_marked_as_known(self):
        w = self.wifi([(["wifi", "list"], (0, self.REAL_SCAN, "")),
                       (["connection", "show"], (0, self.REAL_CONNECTIONS, ""))])
        self.assertTrue(w.scan()[0].known, "the mat has joined this one before")

    def test_a_network_it_has_never_seen_is_not_marked_known(self):
        w = self.wifi([(["wifi", "list"], (0, "SomeCafe:70:WPA2\n", "")),
                       (["connection", "show"], (0, self.REAL_CONNECTIONS, ""))])
        self.assertFalse(w.scan()[0].known)

    def test_networks_come_back_strongest_first(self):
        scan = "Weak:20:WPA2\nStrong:90:WPA2\nMiddling:55:WPA2\n"
        w = self.wifi([(["wifi", "list"], (0, scan, "")),
                       (["connection", "show"], (0, "", ""))])
        self.assertEqual(["Strong", "Middling", "Weak"], [n.name for n in w.scan()])

    def test_an_open_network_is_not_marked_secured(self):
        scan = "Free Wifi:60:\nLocked:60:WPA2\n"
        w = self.wifi([(["wifi", "list"], (0, scan, "")),
                       (["connection", "show"], (0, "", ""))])
        got = {n.name: n.secured for n in w.scan()}
        self.assertFalse(got["Free Wifi"])
        self.assertTrue(got["Locked"])

    def test_a_nameless_hidden_network_is_left_out(self):
        """It has nothing to show on a row and nothing to tap."""
        scan = ":80:WPA2\nReal:60:WPA2\n"
        w = self.wifi([(["wifi", "list"], (0, scan, "")),
                       (["connection", "show"], (0, "", ""))])
        self.assertEqual(["Real"], [n.name for n in w.scan()])

    def test_a_name_with_a_colon_in_it_survives(self):
        r"""nmcli -t escapes them as \:. Splitting on every colon turns one network into two
        pieces of nonsense."""
        w = self.wifi([(["wifi", "list"], (0, "Joe\\: Wifi:70:WPA2\n", "")),
                       (["connection", "show"], (0, "", ""))])
        found = w.scan()
        self.assertEqual(1, len(found))
        self.assertEqual("Joe: Wifi", found[0].name)
        self.assertEqual(70, found[0].strength)

    def test_bars_run_from_nought_to_four(self):
        from salaah.network import Network
        got = [Network("x", s, True).bars for s in (0, 10, 40, 60, 95)]
        self.assertEqual([0, 1, 2, 3, 4], got)

    def test_joining_says_yes_only_when_a_name_really_resolves(self):
        """The evening this was written for: nmcli happy, mat still unable to reach anything."""
        w = self.wifi([(["connect"], (0, "successfully activated", "")),
                       (["--active"], (0, "", ""))], online=False)
        joined, why = w.join("NOVA_26DU_A2", "hunter2")
        self.assertFalse(joined, "it called a network with no internet a success")
        self.assertEqual("no_internet", why)

    def test_joining_says_yes_when_it_does_resolve(self):
        w = self.wifi([(["connect"], (0, "successfully activated", "")),
                       (["--active"], (0, "", ""))], online=True)
        joined, why = w.join("NOVA_26DU_A2", "hunter2")
        self.assertTrue(joined, why)
        self.assertEqual("", why)

    def test_a_wrong_password_is_told_apart_from_being_out_of_range(self):
        bad = self.wifi([(["connect"], (4, "", "Error: Secrets were required, but not provided")),
                         (["--active"], (0, "", ""))])
        self.assertEqual("password", bad.join("Net", "wrong")[1])
        far = self.wifi([(["connect"], (10, "", "Error: No network with SSID 'Net' found.")),
                         (["--active"], (0, "", ""))])
        self.assertEqual("range", far.join("Net", "x")[1])

    def test_a_failed_attempt_puts_the_old_network_back(self):
        """A typo in the kitchen must not cost somebody the network they were already on."""
        w = self.wifi([(["--active"], (0, "NOVA_26DU_A2:802-11-wireless:wlan0\n", "")),
                       (["connect"], (4, "", "Error: Secrets were required, but not provided")),
                       (["connection", "up"], (0, "", ""))])
        joined, why = w.join("SomeCafe", "wrong")
        self.assertFalse(joined)
        self.assertEqual("password", why)
        put_back = [a for a in w.asked if a[:2] == ["connection", "up"]]
        self.assertEqual([["connection", "up", "NOVA_26DU_A2"]], put_back,
                         "the network that was in use was not restored")

    def test_it_does_not_bother_restoring_the_one_it_was_already_on(self):
        w = self.wifi([(["--active"], (0, "NOVA_26DU_A2:802-11-wireless:wlan0\n", "")),
                       (["connect"], (4, "", "Error: Secrets were required")),
                       (["connection", "up"], (0, "", ""))])
        w.join("NOVA_26DU_A2", "wrong")
        self.assertEqual([], [a for a in w.asked if a[:2] == ["connection", "up"]])

    def test_the_password_is_never_put_in_the_failure_message(self):
        w = self.wifi([(["connect"], (4, "", "Error: Secrets were required for 'hunter2'")),
                       (["--active"], (0, "", ""))])
        _joined, why = w.join("Net", "hunter2")
        self.assertNotIn("hunter2", why, "the password leaked into what gets shown")

    def test_a_mat_with_no_wifi_card_is_not_offered_the_screen(self):
        none = self.wifi([(["device", "status"], (0, "ethernet\nloopback\n", ""))])
        self.assertFalse(none.there())
        some = self.wifi([(["device", "status"], (0, "wifi\nethernet\nloopback\n", ""))])
        self.assertTrue(some.there())

    def test_nmcli_missing_altogether_is_a_refusal_not_a_crash(self):
        w = self.wifi([([], (127, "", "nmcli is not installed"))])
        self.assertEqual([], w.scan())
        self.assertFalse(w.there())
        self.assertEqual("missing", w.join("Net", "x")[1])


class EscapeHatchTest(unittest.TestCase):
    """The way onto a network when the wifi screen itself is what is broken.

    This is the one thing on the mat that cannot be fixed by shipping a new version, so it is
    tested harder than the screen it exists to rescue.
    """

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.folder = Path(tempfile.mkdtemp())
        self.card = self.folder / "salaah-wifi.txt"
        self.addCleanup(lambda: __import__("shutil").rmtree(self.folder, ignore_errors=True))

    def wifi(self, joined=True, why="", online=False):
        from salaah.network import Wifi
        calls = []

        class Fake(Wifi):
            def __init__(self):
                super().__init__(runner=lambda *a, **k: (0, "", ""), resolver=lambda n=None: online)

            def join(self, name, password=""):
                calls.append((name, password))
                return joined, why

            def online(self):
                return online

        w = Fake()
        w.calls = calls
        return w

    def test_it_reads_the_network_and_password(self):
        from salaah.network import read_hatch
        self.card.write_text("network: TheirWifi\npassword: hunter2\n", encoding="utf-8")
        self.assertEqual(("TheirWifi", "hunter2"), read_hatch(self.card))

    def test_a_password_with_a_colon_in_it_survives(self):
        """Wifi passwords are allowed colons, and the file is 'key: value'. Splitting on every
        colon would hand the router half a password and blame the user."""
        from salaah.network import read_hatch
        self.card.write_text("network: Cafe\npassword: a:b:c\n", encoding="utf-8")
        self.assertEqual(("Cafe", "a:b:c"), read_hatch(self.card))

    def test_spacing_and_case_and_comments_are_forgiven(self):
        """Somebody types this on a laptop, probably in Notepad, probably in a hurry."""
        from salaah.network import read_hatch
        self.card.write_text("# my wifi\n\n  NETWORK :  Their Wifi  \n  Password:hunter2\n",
                             encoding="utf-8")
        self.assertEqual(("Their Wifi", "hunter2"), read_hatch(self.card))

    def test_no_file_at_all_is_simply_nothing(self):
        from salaah.network import read_hatch, join_from_the_card
        self.assertEqual(("", ""), read_hatch(self.card))
        self.assertEqual("", join_from_the_card(self.wifi(), self.card))

    def test_it_joins_what_the_card_says(self):
        from salaah.network import join_from_the_card
        self.card.write_text("network: TheirWifi\npassword: hunter2\n", encoding="utf-8")
        w = self.wifi(joined=True)
        said = join_from_the_card(w, self.card, when="a Tuesday")
        self.assertEqual([("TheirWifi", "hunter2")], w.calls)
        self.assertIn("joined", said)

    def test_the_password_is_wiped_once_it_has_been_used(self):
        from salaah.network import join_from_the_card, read_hatch
        self.card.write_text("network: TheirWifi\npassword: hunter2\n", encoding="utf-8")
        join_from_the_card(self.wifi(joined=True), self.card, when="a Tuesday")
        left = self.card.read_text(encoding="utf-8")
        self.assertNotIn("hunter2", left, "the password is still on the card")
        self.assertIn("TheirWifi", left, "it should still say what it joined")
        self.assertEqual(("TheirWifi", ""), read_hatch(self.card))

    def test_the_password_is_kept_if_joining_failed(self):
        """Wiping a password that never worked would take away the only thing they could fix."""
        from salaah.network import join_from_the_card
        self.card.write_text("network: TheirWifi\npassword: hunter2\n", encoding="utf-8")
        said = join_from_the_card(self.wifi(joined=False, why="password"), self.card)
        self.assertIn("hunter2", self.card.read_text(encoding="utf-8"))
        self.assertIn("password", said)

    def test_it_does_nothing_when_the_mat_is_already_online(self):
        """The card is a way in, not something that re-joins a network on every start."""
        from salaah.network import join_from_the_card
        self.card.write_text("network: TheirWifi\npassword: hunter2\n", encoding="utf-8")
        w = self.wifi(online=True)
        said = join_from_the_card(w, self.card)
        self.assertEqual([], w.calls, "it joined a network despite already being online")
        self.assertIn("already online", said)
        self.assertNotIn("hunter2", self.card.read_text(encoding="utf-8"),
                         "the password should still be cleared off the card")

    def test_a_card_it_cannot_write_to_still_gets_the_mat_online(self):
        """Being unable to tidy up must not be treated as being unable to connect.

        The failure is injected rather than made with chmod, because these tests run as root
        and root ignores file permissions -- a chmod 444 here wrote happily and the test passed
        while proving nothing. On the mat the app runs as `pi` and a read-only card really is
        read-only. What is under test is the handling, and that runs for real.
        """
        from unittest.mock import patch
        from salaah.network import join_from_the_card
        self.card.write_text("network: TheirWifi\npassword: hunter2\n", encoding="utf-8")
        with patch("pathlib.Path.write_text", side_effect=OSError("read-only file system")):
            said = join_from_the_card(self.wifi(joined=True), self.card)
        self.assertIn("joined", said, "it should still report being on the network")
        self.assertIn("could not clear", said, "it should say the password is still on the card")
        self.assertIn("hunter2", self.card.read_text(encoding="utf-8"),
                      "the fixture did not actually stop the write")

    def test_rubbish_in_the_file_is_ignored_rather_than_thrown(self):
        from salaah.network import read_hatch, join_from_the_card
        for junk in ("", "\n\n", "hello", "network:\n", "\x00\xff binary", "password: lonely\n"):
            self.card.write_text(junk, encoding="utf-8", errors="replace")
            name, _ = read_hatch(self.card)
            self.assertEqual("", name, f"{junk!r} should name no network")
            self.assertEqual("", join_from_the_card(self.wifi(), self.card))

    def test_an_open_network_needs_no_password_line(self):
        from salaah.network import join_from_the_card
        self.card.write_text("network: Free Library Wifi\n", encoding="utf-8")
        w = self.wifi(joined=True)
        join_from_the_card(w, self.card)
        self.assertEqual([("Free Library Wifi", "")], w.calls)

    def test_the_hatch_lives_on_the_boot_partition(self):
        """It has to be somewhere a Windows or Mac laptop can write to with the card in a
        reader. That is the FAT partition, and on Bookworm it is /boot/firmware."""
        from salaah.network import HATCH
        self.assertEqual("/boot/firmware/salaah-wifi.txt", str(HATCH))


class PostcodeTest(unittest.TestCase):
    """Setting where the mat is, from a postcode, with nothing to ask."""

    def places(self):
        from pathlib import Path
        from salaah.places import Places
        return Places(Path(__file__).resolve().parent.parent / "assets")

    def test_the_table_is_there_and_covers_the_country(self):
        p = self.places()
        self.assertTrue(p.there, "no postcode table shipped")
        self.assertGreater(len(p.districts), 2500, "too few districts to be the whole UK")
        for corner in ("BL9", "M1", "EH1", "BT1", "CF10", "TR19", "KW1", "SW1A"):
            self.assertIn(corner, p.districts, f"{corner} is missing")

    def test_it_carries_the_attribution_the_licence_requires(self):
        """Open Government Licence data has to say where it came from. If that ever falls out
        of the file the mat is shipping data it is not entitled to ship."""
        said = self.places().source
        for must in ("Open Government Licence", "Royal Mail", "Crown copyright"):
            self.assertIn(must, said, f"the attribution does not mention {must}")

    def test_a_postcode_lands_where_it_should(self):
        """Checked against coordinates that did not come from this table."""
        import math
        known = {"BL9": (53.593, -2.297, 3), "EH1": (55.95, -3.19, 3), "BT1": (54.60, -5.93, 3),
                 "B1": (52.48, -1.90, 3), "CF10": (51.48, -3.18, 3)}
        p = self.places()
        for code, (lat, lon, tolerance) in known.items():
            got = p.look_up(code)
            self.assertIsNotNone(got, code)
            dy = (got.latitude - lat) * 111.0
            dx = (got.longitude - lon) * 111.0 * math.cos(math.radians(lat))
            self.assertLess(math.hypot(dx, dy), tolerance, f"{code} is {math.hypot(dx,dy):.1f}km out")

    def test_people_type_their_postcode_all_sorts_of_ways(self):
        p = self.places()
        for typed in ("BL9", "bl9", " BL9 ", "BL9 0AB", "bl90ab", "BL9-0AB", "  bl9  0ab  "):
            got = p.look_up(typed)
            self.assertIsNotNone(got, f"{typed!r} was refused")
            self.assertEqual("BL9", got.outward, f"{typed!r} came out as {got.outward}")

    def test_rubbish_is_refused_rather_than_guessed_at(self):
        p = self.places()
        for junk in ("", "   ", "hello", "9BL", "1234", "ZZ99", "BL", "!!!", "BL999999", None):
            self.assertIsNone(p.look_up(junk), f"{junk!r} was accepted")

    def test_every_district_in_the_table_is_a_real_shape_and_in_the_sea_nowhere(self):
        from salaah.places import OUTWARD
        p = self.places()
        for code, (lat, lon) in p.districts.items():
            self.assertTrue(OUTWARD.match(code), f"{code} is not an outward code")
            self.assertTrue(49 < lat < 62, f"{code} is at latitude {lat}")
            self.assertTrue(-11 < lon < 3, f"{code} is at longitude {lon}")

    def test_a_missing_table_is_a_quiet_no_rather_than_a_crash(self):
        from pathlib import Path
        from salaah.places import Places
        p = Places(Path("/nowhere/at/all"))
        self.assertFalse(p.there)
        self.assertIsNone(p.look_up("BL9"))

    def test_moving_the_mat_really_moves_the_prayer_times(self):
        """The whole point. If setting a postcode did not change the times, the screen would be
        decoration."""
        from datetime import date
        from salaah.prayer_times import times_for, Place
        p = self.places()
        bury, cardiff = p.look_up("BL9"), p.look_up("CF10")
        day = date(2026, 6, 21)
        a = times_for(day, Place(bury.latitude, bury.longitude, "BL9"))
        b = times_for(day, Place(cardiff.latitude, cardiff.longitude, "CF10"))
        gap = max(abs((a[x].hour * 60 + a[x].minute) - (b[x].hour * 60 + b[x].minute))
                  for x in a if a[x] and b[x])
        self.assertGreater(gap, 5, "Bury and Cardiff should not share a timetable")

    def test_two_postcodes_in_the_same_town_barely_differ(self):
        """The other half of it: a district is small enough that the exact one hardly matters,
        which is why a district is the unit rather than a full postcode."""
        from datetime import date
        from salaah.prayer_times import times_for, Place
        p = self.places()
        one, two = p.look_up("BL9"), p.look_up("BL8")
        day = date(2026, 6, 21)
        a = times_for(day, Place(one.latitude, one.longitude, "a"))
        b = times_for(day, Place(two.latitude, two.longitude, "b"))
        gap = max(abs((a[x].hour * 60 + a[x].minute) - (b[x].hour * 60 + b[x].minute))
                  for x in a if a[x] and b[x])
        self.assertLessEqual(gap, 1, "two Bury districts should agree to the minute")


class PostureBadgeTest(unittest.TestCase):
    """The drawings come with a "Made with AI" badge in the top right that has to go before the
    picture is trimmed, or the trim keeps the whole margin to hold on to it.

    Rubbing it out used to mean painting the corner white. That is fine on eight of the ten
    drawings and quietly wrong on the other two: in both salam pictures the right-hand figure's
    cap reaches up into that corner, so the white rectangle took the top off his head.
    """

    def tool(self):
        import sys
        sys.path.insert(0, str(ASSETS.parent / "tools"))
        import build_postures
        return build_postures

    def draw(self, size=(1000, 600)):
        """A blank picture with a helper to lay black on it."""
        from PIL import Image, ImageDraw
        img = Image.new("L", size, 255)
        return img, ImageDraw.Draw(img)

    def test_a_mark_floating_in_the_corner_is_rubbed_out(self):
        img, pen = self.draw()
        pen.rectangle((900, 20, 960, 40), fill=0)          # the badge: alone up in the corner
        black = sum(self.tool().clear_badge(img).histogram()[:170])
        self.assertEqual(0, black, "the badge should be gone")

    def test_a_cap_reaching_into_the_corner_is_left_alone(self):
        """The salam case. The figure starts well below the corner and rises into it; every
        pixel of him has to survive, cap included."""
        img, pen = self.draw()
        pen.rectangle((880, 40, 920, 400), fill=0)         # a body, from low down up into the corner
        before = sum(img.histogram()[:170])
        after = sum(self.tool().clear_badge(img).histogram()[:170])
        self.assertEqual(before, after, "the figure should be untouched")

    def test_the_badge_goes_and_the_figure_stays_in_the_same_picture(self):
        """Both at once, which is the real drawing."""
        img, pen = self.draw()
        pen.rectangle((880, 40, 920, 400), fill=0)         # the figure
        pen.rectangle((940, 10, 990, 30), fill=0)          # the badge beside it
        out = self.tool().clear_badge(img)
        px = out.load()
        self.assertLess(px[900, 45], 170, "the top of the figure is still there")
        self.assertLess(px[900, 380], 170, "and so is the rest of him")
        self.assertEqual(255, px[960, 20], "the badge is gone")

    def test_the_two_salam_drawings_keep_their_caps(self):
        """Against the pictures themselves rather than a drawing of my own: the built salam is
        as tall at the right-hand edge as the drawing it came from.

        A cap is a closed outline with white inside it. Cut the corner out and the cap is left
        open at the side, so what was the inside of his head runs out into the air around him --
        which is both how it looks and how this measures it: flood the outside white, and the
        white left inside the right-hand figure's head is what the outline still holds in. A
        whole cap holds a fifth of that part of the picture; a cut one about half as much.
        """
        from PIL import Image, ImageDraw
        for name in ("salam.png", "girl/salam.png"):
            with self.subTest(name):
                img = Image.open(ASSETS / "postures" / name).convert("L")
                img = img.point(lambda v: 0 if v < 170 else 255).convert("L")
                w, h = img.size
                ImageDraw.floodfill(img, (0, 0), 128)          # the air, from both top corners
                ImageDraw.floodfill(img, (w - 1, 0), 128)
                head = img.crop((int(w * 0.5), 0, w, int(h * 0.35)))
                held = sum(head.histogram()[255:]) / (head.width * head.height)
                self.assertGreater(held, 0.18,
                                   f"{name}: the right-hand figure's cap is cut open")


class PostureTrimTest(unittest.TestCase):
    """The pictures are trimmed to the drawing, and "a few marks" has to mean a few relative to
    the picture. The girl's sujood arrived with eight specks of dirt along its top edge; at the
    old floor of 0.4% of 1760 that counted as drawing, and the trim kept nine hundred rows of
    blank paper above her to hold on to them. On screen she was a quarter of everyone else."""

    def tool(self):
        import sys
        sys.path.insert(0, str(ASSETS.parent / "tools"))
        import build_postures
        return build_postures

    def test_dirt_along_an_edge_does_not_hold_the_margin(self):
        from PIL import Image, ImageDraw
        img = Image.new("L", (1760, 2336), 255)
        pen = ImageDraw.Draw(img)
        pen.rectangle((0, 0, 7, 0), fill=0)                  # the dirt, on the very top row
        pen.rectangle((400, 1800, 1300, 2200), fill=0)       # the figure, right down at the bottom
        cut = self.tool().trim(img)
        self.assertLess(cut.height, 500, "the blank paper above her should be gone")

    def test_a_real_stroke_still_holds_the_margin(self):
        """The other side of it: the floor must not be so high that a thin part of the drawing
        is trimmed off. A stroke is eight pixels thick before it is anything else."""
        from PIL import Image, ImageDraw
        img = Image.new("L", (1760, 2336), 255)
        pen = ImageDraw.Draw(img)
        pen.rectangle((880, 100, 900, 2200), fill=0)         # a thin upright, 21px wide
        cut = self.tool().trim(img)
        self.assertGreater(cut.height, 2000, "the whole upright should be kept")

    def test_no_posture_picture_carries_a_band_of_blank_paper(self):
        """Against the built pictures rather than a drawing of my own. Looking at where the ink
        starts is no good -- it was the dirt that came first, and it is ink. What gives the fault
        away is the gap behind it: the widest run of rows with nothing on them at all. Every
        picture here sits between nothing and six thousandths of its height. The badly trimmed
        sujood was 0.557, which is to say more than half of her picture was paper."""
        from PIL import Image
        for folder in ("", "girl"):
            for path in sorted((ASSETS / "postures" / folder).glob("*.png")):
                with self.subTest(f"{folder}/{path.name}"):
                    img = Image.open(path).convert("L")
                    w, h = img.size
                    px = img.load()
                    widest = run = 0
                    for y in range(h):
                        run = 0 if any(px[x, y] < 170 for x in range(w)) else run + 1
                        widest = max(widest, run)
                    self.assertLess(widest / h, 0.05,
                                    f"{folder}/{path.name}: a band of blank paper in the picture")
