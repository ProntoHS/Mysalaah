# Recordings

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
