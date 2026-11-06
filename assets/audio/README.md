# Recordings

**Three kinds of recording live here, and the guard now checks all three by name.**

Until 2.09 `test_no_audio_ships_without_a_licence_beside_it` skipped the whole of
`assets/audio`, on the grounds that this README documented it file by file. That was true of
the 26 prayer recitations in the table below and of nothing else, so the exemption quietly
carried 11.9MB it was never meant to cover. It now names the two azaans and nothing else, so
every other file in here has to be accounted for below or the suite fails — including anything
added later.

## Generated voice — the 48 in `duas/` and the 6 in `kalima/`

Harry: *"all 48 du'as and 6 kalima are ai voice generated"*, with **ElevenLabs
(elevenlabs.io) on a paid tier**.

ElevenLabs' own documentation says a paid subscription carries a commercial licence with no
time limit, where the free plan "does not include a commercial license and cannot be used for
any commercial purpose". **Two conditions on that are not yet confirmed for these files:**
content generated with **Beta Services** cannot be used commercially or in production at all,
and on paid plans the attribution requirement "depends on your agreement with ElevenLabs"
rather than being waived. Neither has been checked against the account these were made on.

Two things about these 54 files are not licensing questions and should not be filed as though
they were. A **synthesised voice reciting du'as and the kalima** is a question for a scholar,
separately from whether the words are right. And the **pronunciation** is whatever the model
produced: tajwid is exactly what a synthetic voice gets subtly wrong in ways a non-speaker
cannot hear, and this is a teaching tool for a child. Nothing here has been reviewed by anyone
qualified.

These are named by path below because the guard matches on the path. Their file names are
bare numbers, so a rule that looked for the NAME alone would be satisfied by any text
containing a digit — which is no check at all.

**`duas/` (48):** `audio/duas/1.mp3`, `audio/duas/10.mp3`, `audio/duas/11.mp3`, `audio/duas/12.mp3`, `audio/duas/13.mp3`, `audio/duas/14.mp3`, `audio/duas/15.mp3`, `audio/duas/16.mp3`, `audio/duas/17.mp3`, `audio/duas/18.mp3`, `audio/duas/19.mp3`, `audio/duas/2.mp3`, `audio/duas/20.mp3`, `audio/duas/21.mp3`, `audio/duas/22.mp3`, `audio/duas/23.mp3`, `audio/duas/24.mp3`, `audio/duas/25.mp3`, `audio/duas/26.mp3`, `audio/duas/27.mp3`, `audio/duas/28.mp3`, `audio/duas/29.mp3`, `audio/duas/3.mp3`, `audio/duas/30.mp3`, `audio/duas/31.mp3`, `audio/duas/32.mp3`, `audio/duas/33.mp3`, `audio/duas/34.mp3`, `audio/duas/35.mp3`, `audio/duas/36.mp3`, `audio/duas/37.mp3`, `audio/duas/38.mp3`, `audio/duas/39.mp3`, `audio/duas/4.mp3`, `audio/duas/40.mp3`, `audio/duas/41.mp3`, `audio/duas/42.mp3`, `audio/duas/43.mp3`, `audio/duas/44.mp3`, `audio/duas/45.mp3`, `audio/duas/46.mp3`, `audio/duas/47.mp3`, `audio/duas/48.mp3`, `audio/duas/5.mp3`, `audio/duas/6.mp3`, `audio/duas/7.mp3`, `audio/duas/8.mp3`, `audio/duas/9.mp3`

**`kalima/` (6):** `audio/kalima/1.mp3`, `audio/kalima/2.mp3`, `audio/kalima/3.mp3`, `audio/kalima/4.mp3`, `audio/kalima/5.mp3`, `audio/kalima/6.mp3`

## Downloaded — `azaan.mp3` and `azaan-fajr.mp3`

**These two are the open problem, and they are the two the guard still skips by name.**

Harry: *"the 2 azaans were available via download off the internet"*. Availability is not a
licence. Nearly every recorded adhan is a performance someone owns, and `salaah-*.zip` is a
public release asset on a public repository — so these are redistributed to anyone who clicks,
whether or not a mat is ever sold. Harry is finding replacements with terms that can be written
down; until then the exemption in the guard is two file names, visible in the test, rather than
a folder-wide skip nobody could see.

`azaan.mp3` was re-encoded in 2.08 — 192kbps stereo to 96kbps mono, 3.50MB to 1.75MB. It is the
same recording: the loudness envelopes of the old file and the new correlate at 0.9999 against
0.049 for a different recitation, the length matches to the millisecond and the first sound
falls on the same sample, so the word timings in `assets/content/azaan/` are untouched. A
re-encode inherits whatever standing the original had, which here is the gap above.

## Harry's own — the 26 prayer recitations

**By path (26):** `audio/alhamdulillah.mp3`, `audio/allahu_akbar.mp3`, `audio/ameen.mp3`, `audio/ayat_kursi.mp3`, `audio/dhikr_salam.mp3`, `audio/dhikr_tahlil.mp3`, `audio/falaq.mp3`, `audio/fatiha.mp3`, `audio/ikhlas.mp3`, `audio/istiftah.mp3`, `audio/istighfar.mp3`, `audio/jalsa_dua.mp3`, `audio/kawthar.mp3`, `audio/nas.mp3`, `audio/qunut_1.mp3`, `audio/qunut_2.mp3`, `audio/rabbana_atina.mp3`, `audio/ruku_tasbih.mp3`, `audio/salam.mp3`, `audio/salawat.mp3`, `audio/subhanallah.mp3`, `audio/sujood_tasbih.mp3`, `audio/taawwudh_basmala.mp3`, `audio/takbir.mp3`, `audio/tashahhud.mp3`, `audio/tasmi_tahmid.mp3`

One recording per recitation, supplied by Harry in September 2026. Each `<key>.mp3` has a
`<key>.json` beside it holding the start and end of every line and word, which drives the red
highlight. The timings are estimates (`"estimated": true`): pauses in the audio are real, the
rest is shared out by text length. Tap real ones in by ear on the Pi: Settings, Play the
recitation, Tap in the word timings.

| Key | Supplied as | Plays on | Notes |
|---|---|---|---|
| `takbir` | Takbir_al-Ihram.mp3 | every Allahu akbar screen | |
| `istiftah` | Dua_al-Istiftah - updated.mp3 | the opening dua | *subhanaka llahumma…* |
| `taawwudh_basmala` | Seeking_Refuge.mp3 | a'udhu billah | no basmala; that is on the Fatiha screen |
| `fatiha` | al-fatiha.mp3 | Al-Fatiha | begins with the basmala; see below |
| `ameen` | ameen.mp3 | after every Al-Fatiha | |
| `kawthar` | al-kawthar.mp3 | Al-Kawthar | begins with the basmala |
| `ikhlas` | al-ikhlas.mp3 | Al-Ikhlas | begins with the basmala |
| `ruku_tasbih` | Ruku_Bowing.mp3 | ruku | said once in the file; played three times (X3) |
| `tasmi_tahmid` | rising_from_ruku.mp3 (the second one) | standing up from ruku | *sami'a llahu liman hamidah, rabbana laka l-hamd*; no pause between them, so the join is an estimate |
| `sujood_tasbih` | Sujud_Prostration.mp3 | sujood | said once in the file; played three times (X3) |
| `jalsa_dua` | Rabbighfir_li.mp3 | sitting between the two sujood | said once in the file; played twice (X2) |
| `tashahhud` | Tashahhud.mp3 | tashahhud | |
| `salawat` | Salawat.mp3 | salawat | |
| `rabbana_atina` | For_Good_in_Both_Worlds.mp3 | after the salawat | |
| `salam` | Ending_Salah.mp3 | salam | said once in the file; played twice (X2) |
| `istighfar` | Astaghfirullāh.mp3 | after the salam of a fardh prayer | said once in the file; played three times (X3) |
| `ayat_kursi` | Ayat_al-Kursi.mp3 | after astaghfirullah, fardh prayers | nine lines, split at the verse's pause marks; the reciter pauses at all eight |
| `dhikr_salam` | Supplication.mp3 | the top dua on the beads screen | plays as the screen appears |
| `subhanallah` | Subhanallah.mp3 | each count of the first bead | |
| `alhamdulillah` | Alhamdulillah.mp3 | each count of the second bead | |
| `allahu_akbar` | Allahu_Akbar.mp3 | each count of the third bead | |
| `dhikr_tahlil` | Supplication - end.mp3 | the bottom dua on the beads screen | plays after the 99th count |
| `qunut_1`, `qunut_2` | witr_qunut.mp3 | the two qunut screens in witr | cut in two at the pause before the second *Allahumma* (11.1–11.9s) |
| `falaq` | Al-Falaq.mp3 | Al-Falaq | begins with the basmala |
| `nas` | An-Nas.mp3 | An-Nas | begins with the basmala; see below |

Every screen in every prayer has a recording, except the intention, which is read rather than recited.

Rebuild the timings for one recording with

    python3 tools/build_audio_timings.py assets/audio/<key>.mp3 <key> --min-gap 0.18

The qunut halves were cut from the one recording:

    python3 tools/build_audio_timings.py witr_qunut.mp3 qunut_1 --to 11.45 --min-gap 0.18
    python3 tools/build_audio_timings.py witr_qunut.mp3 qunut_2 --from 11.55 --min-gap 0.18

An-Nas runs verses 4 and 5 together, with a short break at 11.02s:

    python3 tools/build_audio_timings.py assets/audio/nas.mp3 nas --min-gap 0.18 \
        --ends 2.15,4.55,6.0,7.4,11.02,13.85

Al-Fatiha needs its verse ends given too, because this reciter runs verses 3 and 4 together and breathes after the fourth word of verse 7:

    python3 tools/build_audio_timings.py assets/audio/fatiha.mp3 fatiha --min-gap 0.18 \
        --ends 1.6,3.7,5.24,6.7,9.55,11.74 --pause-after 7:4
