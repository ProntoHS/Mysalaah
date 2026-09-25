# Salaah — mat display prototype (Raspberry Pi 4B + 16" touchscreen, optional 7" posture screen)

A full-screen, touch-and-button prayer guide. Choose a prayer by touch; step through it with the
Bluetooth ring or shutter button. It starts by itself when the Pi turns on.

## Set up (once)

1. With Raspberry Pi Imager, put **Raspberry Pi OS (64-bit)** with desktop on a microSD card.
   In the Imager settings, set a username, password and your Wi-Fi.
2. Plug the monitor into the Pi: HDMI for the picture, USB for touch. Boot the Pi.
3. Copy this `salaah-pi` folder to the Pi (a USB stick is easiest), e.g. into your home folder.
4. Open a Terminal in the folder and run: `./install.sh`
5. Pair the ring (and/or AB Shutter3) with the Bluetooth icon at the top of the screen.
   Put the ring in camera/shutter mode if it has modes.
6. Reboot. The app starts full screen.

## Using it

- **Touch:** the main screen is a mosque with an arch for each prayer. The time shows on the
  dome and a sun or moon crosses the sky behind it as the day goes on. Along the top is a black
  banner with the place, the times, and a red cog for Settings. The prayer that may be prayed right
  now has **its time in green** there, and **its name on the arch in green** too. Behind the
  mosque, a few stars twinkle after dark and a few birds flutter across by day; they move five
  times a second and only while the main screen is on show, so they cost the Pi nothing the rest
  of the time. Between sunrise and Dhuhr no prayer is due, so nothing is
  green and the two minaret tops glow instead. Tap an arch and the mosque swells towards that
  arch and dissolves, as though you had walked into it; behind it are the prayer's
  units, as arches too — "4 Sunnah", "4 Fardh" and so on — as many as that prayer has.
  Tap one and it walks into that arch in turn, coming out at the first screen of the prayer.
  The button top left of that screen says **Menu**, the same word as everywhere else in the
  app, so there is only ever one way back out.

  The walk takes a second and is only a picture laid over the top: the screen
  underneath has already changed before it starts, so it can be interrupted, or fail to run at
  all, without ever leaving you on the wrong screen. A touch or a button press during it clears
  the picture at once, so there is no waiting for it. It is paced by the clock rather than by
  frames, so a busy Pi drops frames instead of running it in slow motion. If it does judder,
  raise `COARSE` in `ZoomVeil` (`salaah/mosque.py`) from 2 to 3: the picture is then taken at a
  third of full size, which quarters the work again and is not visible at this speed.
- **Ring or shutter button:** a click moves to the next step. Volume Down (the second button on
  some remotes) goes back. A press held longer than one second is ignored, so a palm resting on
  the ring in sujood doesn't turn the page.
- **Power button:** a click puts the mat to sleep — both screens off — and the next click wakes it
  at the main menu, with the 7" back on the Qibla, however it was left. It works from any screen,
  a prayer included, which also makes it the way out of anything that has stopped behaving. See
  **Sleep** below, which has to be set up once or the Pi will shut down instead.
- **Touch during a prayer:** the right two-thirds of the screen goes forward, the left third back.
- **Leaving mid-prayer without the screen:** click twice quickly and it asks "Leave the prayer?".
  One more quick click leaves; pause, then click, and it carries on exactly where you were. Going
  back from the first page also leaves. A hold is deliberately ignored, because a palm resting on
  a ring in sujood looks exactly like one.
- **Menu** (the red button, top left) leaves the prayer. Where a recitation is said more than
  once, a black circle in the top right corner inside the picture frame says how many times: X3
  in ruku and sujood, X2 for *rabbi ghfir li* and the salam. With the recitation on, the recording plays that many
  times, with a short breath between, and the red follows each one.
- **Volume** is the rectangle in the top row, beside the rakat: ten blocks filled black up to
  the level. Tap or
  drag anywhere along it. All the way down is silence, and switches the recitation off; turning it
  up switches it back on. A change takes effect on the next screen, so a verse being recited is
  never cut off part way through.
- **When a fardh prayer finishes:** after the salam, *astaghfirullah* (X3) and Ayat al-Kursi,
  sitting. Then the
  dhikr, counted on beads. The salam dua runs across the top, the tahlil across the bottom, and
  between them three beads on a cord — سبحان الله, الحمد لله, الله أكبر — each with its count
  underneath. The bead being said has its name in red; every click takes one off it, and at
  nought it fills in **green** and the next name turns red. The counts underneath are in red. With the recitation on, the top dua is
  recited as the screen appears, each click plays that bead's recording (Subhan Allah,
  Alhamdulillah or Allahu akbar), and after the ninety-ninth the bottom dua is recited, each with
  its words turning red. Going back steps into the prayer again; Menu leaves. The counts start
  again at 33 with the next fardh prayer. The words are in `assets/content/core/arabic.json`
  (keys named in `core/dhikr.json`), the counts in `core/dhikr.json`.
- **When a sunnah, nafl or witr prayer finishes:** a saying of the Prophet on the left and a short
  passage of the Qur'an on the right, each under a white-on-black heading, in Arabic with its
  meaning and its reference underneath, separated by a thin line. **The Arabic and its meaning are
  lettered the same size**, and both columns agree on that size: it is the largest at which all
  four blocks of words still fit, worked out for the pair of the day rather than fixed, so it
  comes out between about 55px and 88px. That makes the meaning something you read from the mat
  rather than a caption under the Arabic, and it is why the heading is now the smaller of the
  two — it labels the passage instead of competing with it. Each column hangs from its heading,
  so the two first lines stay level however differently long the passages are. The same pair all
  day, a different pair tomorrow. There is no "prayer complete" heading: the two passages are the
  screen. The Menu button leaves. The top bar names the prayer on the left and puts the rakat
  straight after it in a box of its own — "Dhuhr, 2 Nafl" then "Rakat 2 of 2", read as one
  phrase rather than one at each end of the bar — with the prayer's name in Arabic in the centre
  and a large dot on the right: green when a button is connected, red when not. All three boxes
  are the same height.
- **Settings:** the red cog on the banner. Two columns, each choice a circle that fills in solid
  when it is the one in use: school, language, Arabic lettering, the
  recitation, screen dimming, screen colours, screen edge, mouse pointer, the Qibla and
  connected buttons, and the version at the foot. The prayer times and the place they are worked
  out for are not repeated here; they are along the top of the main screen, which is one tap
  away. Where to set the place is in this README, under Prayer times. Language, the translation and the screen
  colours are dropdowns; the rest are circles. The red **Main screen** button, top right,
  goes back to the mosque. There is deliberately no way out to the desktop: the mat is the
  product, and there is nothing behind it to go to. With a keyboard: Esc goes back, Ctrl+Q
  quits, which is how to get out of it while working on it. On a screen too short to show
  everything, Settings scrolls.

## Screen colours (light and dark)

Settings → **Screen colours** has three choices:

- **Automatic** (the default): white on black from Maghrib until sunrise, black on white by
  day. It uses the prayer times the app already works out for your place. If the time comes
  mid-prayer, it waits until the prayer is over, so the screen never flips while you pray.
- **Light: black on white**, always.
- **Dark: white on black**, always.

In the dark, the words and lines are white on black. The posture pictures and the mosque are
turned over too, so it becomes a white mosque on a black sky with the time in black on the
white dome. Colours that mean something stay the same: the lit arch is still gold, the
compass still turns green, the Kaaba is still black (with a white edge). The red of the word
being recited is a little brighter so it shows up on black. Choosing in Settings changes the
screen straight away. A black screen has less glare in a dark room. On an LCD monitor the
backlight stays on either way, so for battery the monitor's own brightness matters more.

## Interface language

Settings → **Language** is a dropdown: **English**, **Español**, **Français**, **中文**,
**हिन्दी**, **اردو**. It changes the menus, Settings and the prayer screen's own words. Urdu is
right to left, so the whole interface mirrors: headings move to the right, and on the prayer
screen the "back" third of the screen is the right-hand third, since that is the edge Urdu
starts from.

Each language is listed under its own name, so that one dropdown holds four scripts at once and
no single face covers it. Every row carries the face its own letters need, and so does the shut
box. Anything else that letters a menu word is handed the same face: the whole stylesheet
(`pack_face`), and the unit arches, which are painted rather than styled. Chinese and Hindi get
a bundled face because Raspberry Pi OS has neither script — see `assets/fonts/README.md`.

**The menus and the translation are still two separate settings.** All six languages are now
available for both, but they are chosen independently: the menus can be in English with the
translation in Chinese, or the other way round. Each interface language is 155 strings in
`assets/content/packs/<lang>/pack.json`; a test checks that every pack has the same keys as the
English one and that no translated string has lost a `{gap}` the app needs to fill in.

Spanish, Chinese and Hindi were written for this app and are drafts, like the French and Urdu
before them. They need a native speaker's eye.

Anything a language pack is missing falls back to English, so nothing can come out blank. The
French and Urdu interfaces were written for this app and are drafts; the prayer names on the
mosque itself are part of the artwork and stay in English for now.

## Who is shown in the pictures

The posture pictures live in `assets/postures`. A folder inside it is another set of the same
pictures, named by its folder: `assets/postures/girl/standing_folded.png` and so on. When there
is more than one set, Settings grows a **Who is shown** row (Boy / Girl).

A set does not have to be complete. Any picture it is missing falls back to the original of the
same name, so a half-finished set still works and can be filled in a few at a time.
`assets/postures/girl/README.md` lists the file names and what each posture is.

The girl's set is complete. Her qunut picture is her standing folded one, because that is the
same pose — the boy's `qunut.png` is likewise a second drawing of the folded stance.

> **Needs checking.** Her pictures were drawn from the boy's, pose for pose. In the Hanafi
> school a woman's positions are not the same as a man's — the ruku, the sujood and the sitting
> all differ — so these need going over with someone qualified before anyone learns from them.


To prepare drawings for a set — clear the "Made with AI" badge, reduce them to plain black on
white, trim the blank space and work out the sizing — run:

    python3 tools/build_postures.py path/to/drawings assets/postures/girl

Name each drawing after its posture (`ruku.png` and so on); anything else in the folder is
ignored.

## The arch on the unit screen

The arches that stand for a prayer's units ("4 Sunnah", "4 Fardh") are **drawn**, not pictured,
so a prayer can have as many as it has units and each can carry its own number and name. They
are drawn from two grayscale masks in `assets/mosque`:

| File | What it is |
|---|---|
| `arch-outer.png` | the whole arch, painted in the outline colour |
| `arch-inner.png` | the panel inside it, painted on top |

The gap between the two is what you see as the outline, and both are painted straight off the
theme: the arch is an outline on the page it sits on, white inside by day and black inside after
dark, rather than a panel in a shade of its own. Both masks come from one clean drawing of the
arch as a solid shape:

    python3 tools/build_arch.py path/to/arch.png

That gives the outline an even width all the way round, instead of following whatever the
drawing's own line happened to do. Use the largest drawing you have: the masks are saved 1400
pixels tall, and the shrinking is what smooths the edges. The first pair were traced off the
mosque picture at 683 x 1000 and had a ragged edge, which is what showed as fuzziness on screen.
`--border` sets the outline's width as a fraction of the arch's width (0.036 by default) and
`--height` what the masks are saved at. The base is deliberately left open, so the arch stands
on the ground rather than being closed along the bottom.

## Translation beside the Arabic

Settings → **Translation beside the Arabic** is a dropdown, so the page stays the same size
however many languages are added: *Arabic only* (the default), *English*, *Français*, *اردو*,
*Español*, *中文*, *हिन्दी*, and any personal file (below). It takes effect from the next prayer
started.

- The Arabic is on the right and its meaning on the left, verse level with verse, so the eye
  can go straight across. Each verse starts on the same line on both sides, and a thin line runs
  down the middle between the two, the same colour as the words. It runs the full height of
  every screen, so it stays put rather than growing and shrinking with the amount of text.
- The intention screen is written in the chosen language ("J'ai l'intention d'accomplir 4
  rak'ats fardh de Dhuhr").
- With the recitation on, the translation follows the Arabic voice. As each Arabic word turns
  red, the stretch of the translation at the same point in the verse turns red with it. The
  two languages order their words differently, so this is a good guess, not a word-for-word
  match.
- The beads screen stays Arabic only for now.

Where the words come from (also recorded line by line in `assets/content/translations/*.json`):

| | Qur'an passages | Duas and dhikr |
|---|---|---|
| English | plain modern English written for this app, draft | written for this app, draft |
| Français | Albert Kazimirski, 1840 (out of copyright) | rédigé pour l'application, brouillon |
| اردو | Fateh Muhammad Jalandhry, 1929 (out of copyright) | written for this app, draft |
| Español | written for this app, draft | written for this app, draft |
| 中文 | written for this app, draft | written for this app, draft |
| हिन्दी | written for this app, draft | written for this app, draft |

Urdu is written in the Arabic script, so its column runs right to left like the Arabic and is
set in the same face. Its duas need checking by an Urdu speaker.

Every modern published English translation (Saheeh International, Abdel Haleem, The Clear
Qur'an) is in copyright and would need the publisher's permission for a product. The
out-of-copyright ones are archaic ("Thee (alone) we worship"). So the English here is written
plainly for this app, which is free of both problems. Pickthall's 1930 wording was used up to
v0.47 and dropped as too old-fashioned.

**Spanish, Chinese and Hindi are written for this app from end to end**, because unlike French
and Urdu there is no usable free translation in any of the three. Every Spanish translation in
circulation is in copyright; the only public-domain one (Joaquin Garcia Bravo, 1907) is an
indirect rendering of Savary's French that survives only as uncorrected OCR with its verses
numbered one behind. Ma Jian's Chinese is in copyright until 2029 at the earliest and 2048 in
the UK, and Wang Jingzhai's (out of copyright since 1999) has never been digitised. Every Hindi
translation in circulation is in copyright, and the one pre-1930 Hindi Qur'an (Ahmad Shah, 1915)
has never been digitised either. So all three are plain modern prose written here: legally clean
to ship, and drafts that need a native speaker's eye before anyone learns from them. Spanish
uses "Dios" as the French uses "Dieu"; Chinese uses 安拉 and simplified characters; Hindi is in
Devanagari.

If you would rather see a published rendering in one of these languages, put it in a
`*.personal.json` file (below) rather than in a shipping one. QuranEnc publishes an explicit
permission to redistribute its translations subject to attribution and version conditions
(quranenc.com, keys `spanish_garcia`, `chinese_makin`, `hindi_omari`); that is a real written
grant, but it is a publisher's text, so it stays out of anything sold or given away.

Chinese is written without spaces between words. A verse would therefore arrive as one
unbreakable "word" that neither wrapped nor followed the voice, so a run of Han characters is
broken into its characters instead (`wrappable` in `salaah/render.py`) — which is where Chinese
breaks its lines anyway, and gives the red something to move along.

The French Fatiha and Ayat al-Kursi were taken from Wikisource. Surahs 108, 112, 113 and 114
were entered from the Kazimirski text and should be checked against a printed copy. Everything
in both languages needs checking by a qualified reviewer before anyone relies on it. English
says "Allah" throughout; the French says "Dieu", as Kazimirski does.

### Personal translations (not for a device you sell)

A file named `*.personal.json` in the same folder is treated as private: it appears in Settings
like any other, and the app prints a warning at start-up naming it. Two are included, both for
one household's own use:

| File | Qur'an passages |
|---|---|
| `en-clear.personal.json` | The Clear Qur'an, Dr Mustafa Khattab |
| `fr-clair.personal.json` | Le Noble Coran, Rashid Maash |

Both are modern, in copyright, and downloaded from `github.com/fawazahmed0/quran-api`. Private
use on your own device is what the publishers allow; a device **sold or given away** with these
files on it would need the publisher's written permission. So:

    rm assets/content/translations/*.personal.json

before packaging anything for anyone else. The duas and dhikr in those files are the app's own
draft wording, not the publisher's.

To add a language: copy `en.json` to a new file named for the language (e.g. `ur.json`),
translate the lines keeping the same number of lines per recitation, and set `"dir": "rtl"`
for a right-to-left language. It then appears in Settings.

## Two screens: the 7" posture screen

A second screen, a 7" 1024 x 600 touchscreen stood upright beside the main one, takes the posture
posture picture, as large as the screen allows, with the X2 / X3 circle in its top right
corner. The main screen then gives its whole width to the words, and the volume bar sits in its
top row beside the rakat.

- **Between prayers** the 7" shows the Qibla compass, from the moment the app starts. The main
  screen comes straight up with the mosque, so nothing has to be pressed first. Once the mat is
  lined up the compass turns green and stays up, still watching, because the mat can be moved; a
  touch on it does nothing, so it cannot be knocked off by accident.
- **During a prayer** it shows the posture picture, filling the screen.
- **After the prayer**, back to the compass.
- Turning the compass off in Settings (**Qibla, Don't show**) gives the 7" back to the standing
  figure between prayers.
- Dark and light apply to both screens, and so does **Dim the prayer screen**.

With no second screen plugged in, the app works as before, with the picture on the left of the
main screen.

**Setting it up (once):**

1. Plug the **16" into HDMI 0**, the micro-HDMI socket next to the power socket, and the **7"
   into HDMI 1**. Each needs a micro-HDMI to HDMI cable. Plug the 7"'s touch USB into the Pi.
   **The sockets can be either way round.** The app recognises the 7" by its shape (about
   1024 x 600, upright or flat) and gives the words to the largest screen left over, so it comes
   out the same way round on every boot however the cables went in.
2. Turn the 7" upright: **Raspberry Pi menu, Preferences, Screen Configuration**, right-click the
   7" screen (HDMI-A-2), **Orientation**, then **right** or **left** to suit how it stands.
   Apply. The app then sees a 600 x 1024 screen.
3. Tie each touchscreen to its own screen, or a touch on the 7" lands on the 16". Newer
   versions of Screen Configuration have a **Touchscreen** menu for this. If yours doesn't:
   run `libinput list-devices` to find the 7"'s touch name, then add this line inside
   `<labwc_config>` in `~/.config/labwc/rc.xml`, and log out and back in:

   ```
   <touch deviceName="NAME FROM LIBINPUT" mapToOutput="HDMI-A-2" />
   ```

   Do the same for the 16"'s touch with `HDMI-A-1`.
4. Plug both screens in before the Pi starts. A screen plugged in later is picked up next time.

**If a window lands on the wrong screen**, or both windows pile onto one screen, the desktop is
placing them itself and ignoring the app. That happens on Wayland, which newer Raspberry Pi OS
uses by default. In order:

1. See what the Pi reports, and what the app makes of it:
   ```
   ./run.sh --list-screens
   ```
   It prints each screen's name (such as `HDMI-A-1`), its size, the session type, and which
   screen it would use for what. Screens chosen by name are remembered in Settings, and forgotten
   again if they stop making sense (names can come back in a different order after a reboot).
2. Say which screen is which, using those names:
   ```
   ./run.sh --main-output HDMI-A-1 --side-output HDMI-A-2
   ```
   A few seconds after it starts, the app prints which screen each window really landed on, so
   you can see whether the desktop took any notice.
3. If a window still lands on the wrong screen, stop asking the desktop at all. This covers
   each screen with a borderless window of its own, which no desktop can move:
   ```
   ./run.sh --main-output HDMI-A-1 --side-output HDMI-A-2 --cover-screens
   ```
4. Another thing worth trying is the X11 layer, which lets an app place its own windows:
   ```
   QT_QPA_PLATFORM=xcb ./run.sh --main-output HDMI-A-1 --side-output HDMI-A-2
   ```

Options: `./run.sh --side-screen off` ignores a second screen. `--side-screen window --windowed`
tries the two-screen layout on one monitor, with the 7" as a 600 x 1024 window.

## Qibla compass

**On.** With a 7" screen the compass lives there: it comes up as the app starts, the mosque
comes up on the main screen at the same time, and it keeps watching between prayers. With one
screen only, it shows before the main screen and a press goes on to the mosque. To take it out
altogether, set `QIBLA = False` near the top of `salaah/ui.py`; to turn it off without that,
use **Qibla, Don't show** in Settings.

The pointer at the top is the way the display (and so the mat) faces; the Kaaba sits on the rim in its true direction, worked
out from the location in Settings (118.5° from north from Bury). Turn the display until the
Kaaba is under the pointer: the band turns green, and after two seconds the main screen comes up
by itself. **A press of the ring, or a touch, always goes straight on.** Anything within 10°
counts as facing the Qibla.

It remembers which way the display faced when it was lined up, and next time only asks again
if the display has been turned more than 15° since. Settings has **Qibla**: the bearing, whether
a compass is fitted, *Show when the app starts* or *Don't show*, and a **Show the Qibla** button.

**No compass fitted** — which is the intended arrangement, not a gap waiting to be filled. A
compass inset into the mat's frame, at the far end from the electronics, reads a clean field;
a chip soldered inside the housing sits beside the speaker magnet and the battery wiring and
cannot be moved away from either. That is a geometry problem, not a calibration one.

So with no chip the dial is drawn with north at the top and the Kaaba at its bearing, and **the
bearing itself is the headline**: the number, large, under the dial, with the compass point and
the place in small print beneath. It is read while kneeling on the floor squaring a mat against
a compass held in the other hand, so it is set at the size of the thing you actually use rather
than buried in a sentence, which is where it used to be. Tests hold the number to the width of
the 7" screen at its widest possible value, and hold the note under it to one line in all six
languages.

**To try the moving compass without the chip**, start it with `./run.sh --compass-stand-in`; the
left and right arrow keys turn it. With a chip fitted the number is hidden, because there the
turning dial and *Turn right 20°* are the instruction and a fixed bearing would only be noise.

**Fitting the chip:** a BNO055 board (Adafruit 4646, or any BNO055 at address 0x28). It gives a
heading that stays right when the display is tilted back on its stand. Four wires to the Pi:
3.3V (pin 1), SDA (pin 3), SCL (pin 5), ground (pin 6). `install.sh` switches I2C on; check the
chip with `i2cdetect -y 1` (it shows 28). The app finds it by itself at start-up. Mount it away
from the speaker magnet and the battery, then calibrate once by moving the whole unit slowly in a
figure of eight. If the chip is mounted turned in the housing, set `compass_mounting` (degrees)
in `~/.config/salaah/settings.json`; `compass_declination` corrects magnetic to true north
(under 1° in the UK, so it is left at 0). The chip driver is written to the datasheet and has
not yet been tried on a real chip.

## Mouse or touch

Everything works with either. The pointer is **shown by default**. On a finished mat, where a
stray pointer sitting on the screen looks untidy, hide it in **Settings, Mouse pointer, Hidden**
(it stays hidden, including when the app starts by itself). `./run.sh --cursor` brings it back
for one run if you ever hide it and then need it. During a prayer,
click the right two-thirds of the screen to go forward and the left third to go back, exactly as a
tap would. A keyboard works too: Space or Enter for the next step, Backspace or Left for the previous.

## Sleep

A click of the Pi's power button turns both screens off; the next click brings them back at the
main menu, with the 7" showing the Qibla, exactly as when the mat is switched on. Nothing is shut
down and nothing reboots, so waking is instant.

Waking at the menu rather than where it was left is deliberate: the mat is picked up by whoever
prays next, and a screen left open halfway through someone else's Settings is no way to greet
them. The reset happens while the screens are already dark, so the panels come up showing the
right thing rather than changing in front of you.

It works from every screen, with no exceptions: press to put the mat away, press to pick it up,
and it always comes back at the mosque. That includes partway through a prayer, which leaves the
prayer rather than pausing it — the session is let go of and anything being recited stops.

Earlier versions refused mid-prayer, on the grounds that a press then was more likely a knee than
a decision. That reasoning was borrowed from the wrong button: the ring that gets knelt on lies
on the mat, while this one is on the box, where a knee will not find it. A button that does
nothing also turned out to be worse than one that does something — a child has no way of telling
"ignored on purpose" from "broken". And having one screen the button cannot rescue you from is a
poor trade on a mat with no keyboard: a press now gets you out of anything that has stopped
behaving, which is worth more than the case the rule was guarding.

Holding the button is still a hardware force-off, and a press while the board is halted still
starts it. Neither goes through this.

**Why it needs setting up.** The Pi 5's power button is not a hardware switch. A short press
arrives as an ordinary input event — `KEY_POWER`, from a device the kernel calls `pwr_button` —
and whoever reads that event decides what it means. Out of the box systemd-logind reads it and
shuts the machine down. The app reads it first and blanks the screens instead. Two of the
button's jobs are done in hardware and are untouched: **holding** it still forces the board off,
and **pressing it while the board is halted** still starts it. That last one is why the button is
worth wiring even with sleep working — nothing in software can start a board that is off.

An external button goes on **J2**, the two through-holes beside the USB-C socket, on the
board-edge side of the RTC battery connector. Any normally-open momentary switch bridging the two
will do; it behaves exactly as the onboard button does.

Three things to set up once:

1. **Let this user read input devices.** `sudo usermod -aG input $USER`, then log out and back in.
   Without it the app prints `cannot read /dev/input/eventN` at start-up and the button does
   nothing.
2. **Stop logind shutting the Pi down.** Put `HandlePowerKey=ignore` in
   `/etc/systemd/logind.conf` and reboot. The app also *grabs* the device, which usually keeps
   the presses to itself without this, but grabbing is best-effort and the setting is the certain
   way. On Raspberry Pi OS Desktop this also stops the shutdown/reboot/logout dialog appearing
   over the app, which otherwise looks like a fault.
3. **Install `wlopm`** (`sudo apt install wlopm`) so the screens are powered down rather than
   painted black. A black screen still lights its backlight, which is most of what a panel costs
   to run, so without this the mat sleeps but saves almost nothing. It prints
   `sleep: wlopm is not installed…` and carries on.

At start-up the app says which device it found and whether it grabbed it. `--no-sleep` leaves the
button to the desktop.

If the app stops for any reason the grab goes with it and the button shuts the Pi down again,
which is the right way round for something that has stopped responding.

**What it saves, and what it doesn't.** Sleep turns the panels off; the Pi itself keeps running,
so this is a few watts rather than none. Good for the gaps between prayers. It does not make the
mat last a week on a battery — for that it would have to shut down properly and be woken by the
Pi's RTC alarm before the next prayer, which is not built yet. Measure both states before sizing
a battery:

    python3 tools/power_draw.py --for 120 --pack 72

That reads the Pi 5's power management chip, sums every rail and corrects for what the chip cannot
see (the USB sockets, and so the displays), then says what a pack of that many watt-hours would
give you. Take one reading awake and one asleep; the difference is what the sleep is worth. The
correction comes from the RPi5-power project's measurements against a meter, so treat the answer
as a good estimate rather than a reading — an inline USB meter is how to check it.

## Updating over the internet

Settings has **Check for updates**. It says either "up to date" or offers the newer version by
number, with a line about what changed, and nothing is installed without being agreed to. A check
during a prayer is refused.

This is the only part of the app that fetches code and runs it, which makes it the only part that
can brick the mat or be turned against it. Everything below exists to make one of those two
things harder.

**Releases are signed, and a signature is not the same as HTTPS.** HTTPS says "this really is the
website you asked for". It says nothing about whether the file sitting there is the one its
author meant to publish. If the hosting account is ever broken into, or a file swapped at the
host, HTTPS is perfectly happy and every mat installs whatever is there. So the manifest is
signed with a key only its author holds; the public half is in `salaah/update.py`, and anything
that does not verify is refused before a byte of it is unpacked. Replacing that line is how a mat
is taught to trust somebody else, which is why it sits in the source rather than in a settings
file.

**Nothing is trusted until it is checked.** The signature is checked before the manifest is
believed. The download's hash is checked against the manifest before the zip is opened. Every
entry in the zip is checked before anything is written — a zip can name a file `../../.bashrc`,
or carry a symlink pointing anywhere, and be unpacked straight over them.

**Nothing is replaced in place.** The new version is unpacked beside the old one and moved into
place with renames, so a download cut off halfway leaves a working mat rather than half of two
versions. The version it replaces is kept alongside as `salaah.prev` and `assets.prev`.

**A new version is on trial until it proves itself.** It has to run for a minute before the app
marks it good. If it crashes first, or is started twice without ever settling, `run.sh` puts the
previous version back without anyone being asked, and starts that instead. **That guard is in
`run.sh`, in plain shell, and deliberately does not call into the app** — the whole point is that
it still works when the installed version is broken, and code from a broken version cannot be
trusted to undo its own installation. For the same reason `run.sh` is not one of the things an
update replaces: only `salaah/` and `assets/` are. A change to `run.sh` is a change people have
to make by hand.

One consequence worth knowing: if the mat is switched off within a minute of updating, the new
version never settles, and the next start puts the old one back. It is the right way round —
better a needless rollback than a mat stuck on a version that cannot run — but it explains an
update that appears not to have taken.

### Making a release

    python3 tools/make_key.py                   once, ever: makes your signing key
    python3 tools/sign_release.py --url https://.../salaah-1.13.zip --notes "what changed"

`make_key.py` writes the private key to `~/.salaah/signing-key` and prints the public half. The
private key never leaves your machine; **back it up**, because losing it means no existing mat
will ever accept an update again, and every one would have to be opened up and given a new key by
hand.

`sign_release.py` builds `salaah-<version>.zip` from `salaah/` and `assets/`, and a signed
`latest.json` beside it. It prints, separately from the rest of its output, any licensed
`*.personal.json` translation it kept out — those are private use only and must never go into a
release. Bump `__version__` in `salaah/__init__.py` first; it is compared as numbers, so 1.12 is
newer than 1.9.

Upload both files. The mat fetches `latest.json` from the address in `update.py`, and takes the
download link from inside it — so only that one address is permanent, and where the zips live can
change whenever you like.

### Trying it without publishing anything

Point one mat at your own computer. In the folder holding `latest.json` and the zip:

    python3 -m http.server 8000

then put that address in `~/.config/salaah/settings.json`:

    "update_url": "http://192.168.1.50:8000/latest.json"

That is also the only practical way to test what matters — not the case where everything works,
but the refusals. Serve a zip you have edited after signing, a manifest signed with a different
key, a release that crashes on startup. Each one should be refused or rolled back without the mat
needing anything from you.

## Recitation audio (learning aid)

Settings has **Play the recitation**, **on by default** at volume 80. Any screen showing a
recitation that has a recording plays it, and each Arabic word turns red as it is recited.
Only the verses on that screen are played, and the audio stops the moment you move on. The
volume bar in the top row sets how loud, and doubles as the switch: dragged all the way down
it is silent and the recitation is off, and turning it up switches it on again at that volume.

Recordings live in `assets/audio`: an mp3 plus a timings file naming the start and end of every
line and word. There is one for every step of the prayer: the takbir (used on every Allahu akbar
screen), the opening dua, a'udhu billah, Al-Fatiha, Al-Kawthar, Al-Ikhlas, the tasbih of ruku
and sujood, rising from ruku, *rabbi ghfir li*, the tashahhud, the salawat, *rabbana atina* and the
salam. `assets/audio/README.md` lists which file is which and how each was timed.

Every screen in every prayer has a recording, including the witr qunut and Al-Falaq and An-Nas
in the four sunnah, except the intention, which is read rather than recited.

A recording need not cover a whole screen: if one holds only the first line, say so when
adding it and nothing is highlighted for the lines it leaves out, rather than the wrong word:

    python3 tools/build_audio_timings.py ~/recording.mp3 <key> --covers 1

Where a reciter runs verses together or breathes part way through one, give the verse ends
yourself and say which word the breath follows, as Al-Fatiha needs:

    python3 tools/build_audio_timings.py assets/audio/fatiha.mp3 fatiha --min-gap 0.18 \
        --ends 1.6,3.7,5.24,6.7,9.55,11.74 --pause-after 7:4

**Getting the red to follow the voice.** The timings that ship are estimates: they come from
the pauses in the audio, with the rest shared out by how long each word is, so the red can run
ahead of or behind the voice inside a long line. The audio player also takes a moment to start,
which varies from machine to machine. Both are fixed by tapping along once, on the Pi itself:

1. Start the app with `./run.sh --tap-timings`. It is not in Settings: it is a job for building
   the mat rather than for praying on it, and it only needs doing once.
2. Each recording comes up in turn, starting with Allahu akbar. Press the ring to play it, then
   press as each **red** word begins (the first word starts with the recording, so it needs no
   press). A tap on the right of the screen, Space or Enter work too.
3. When it ends, the new timings are saved and played straight back so you can watch them.
   Press for the next recording, or back to tap that one again.

It takes about six minutes for all twenty-six. Each tap is timed by the same clock the prayer
screen uses, so the player's start-up delay is built into the timings, and 0.1s is taken off each
tap for the time between hearing a word and pressing. Tapped files are marked as measured
(`"estimated": false`); **Previous** and **Next** move between recordings without tapping.

The same can be done at a keyboard with `python3 tools/tap_timings.py assets/audio/fatiha.json`.

If a recording is a lesson, or holds several recitations, cut the one you want out of it by
seconds as you add it:

    python3 tools/build_audio_timings.py ~/lesson.mp3 tashahhud --from 79.9 --to 108.4

To add another recitation, drop `<key>.mp3` into `assets/audio` (the key is the recitation name
from `content/core/arabic.json`, e.g. `ikhlas`), then:

    python3 tools/build_audio_timings.py assets/audio/ikhlas.mp3 ikhlas --reciter "Name"
    python3 tools/tap_timings.py assets/audio/ikhlas.json

Audio needs a player: `mpg123` (installed by `install.sh`), or ffplay, mpv or cvlc.

## Prayer times

Each prayer may be prayed within its own window: Fajr until sunrise, Dhuhr until Asr, Asr until
Maghrib, Maghrib until Isha, and Isha through the night until Fajr. The arch is lit only inside
that window, which is why nothing is lit between sunrise and Dhuhr.

Times are worked out on the device from the sun's position, using the **Muslim World League** method
(Fajr 18 degrees, Isha 17) and the Asr rule of the school chosen in Settings — the Hanafi school
uses the longer shadow, so its Asr is later. No internet and no service is involved, so the times
are the same offline and never stop working.

Set your location in `~/.config/salaah/settings.json`. It comes set to Bury:

    "latitude": 53.5933, "longitude": -2.2966, "place": "Bury"

The times, and the place they are worked out for, run along the top of the main screen so they
can be checked against a local timetable. They used to be repeated in Settings as well; that was
dropped, as the main screen is one tap away. Mosques often round or shift a couple of minutes, so
treat these as a guide.

Far north in summer the sun never drops 18 degrees below the horizon, so Fajr and Isha have no
time at all. The app shows a dash for those rather than inventing one.

## If the screen looks wrong

The app uses the **whole screen**. It is laid out for 1920 x 1080. On a taller screen, such as
the 16" at 1920 x 1200, the sizes stay the same and the extra height is used as room.

If the monitor is chopping off an edge (a common one on older HDMI screens is overscan), either:

- set **Settings, Edge of the screen** to 20, 40 or 60 px until nothing is cut off, or
- run `./run.sh --inset 40` once, which sets the same thing and remembers it.

To keep a fixed shape instead, with an even margin round it: `./run.sh --aspect 16:9` (or
`4:3`, and so on).

Worth trying the Pi's own fix too: **Raspberry Pi Configuration, Display**, or `raspi-config`,
has an overscan setting that cures the cause rather than working around it.

## For testing

- `./run.sh --windowed --cursor` runs it in a window with the pointer showing.
- `python3 -m unittest discover -s tests` runs the checks (content, rakat counting, buttons, screens).

## The steps of the prayer

Every prayer runs:

1. **The intention**, in English, naming what was chosen: "I intend to perform 2 Rakats Sunnah of
   Fajr". Standing, arms at the sides. It is read, not recited, so it has no recording.
2. Takbir al-Ihram, then the opening dua *subhanaka llahumma…* and a'udhu billah — in the first
   rakat only
3. Al-Fatiha, then *aameen*, then a short surah (Al-Kawthar, Al-Ikhlas, then Al-Falaq and An-Nas in the third
   and fourth rakats of the four sunnah)
4. Ruku (X3), rising from ruku (*sami'a llahu liman hamidah*, *rabbana laka l-hamd*)
5. Sujood (X3), sitting with *rabbi ghfir li* (X2), sujood again (X3), with an Allahu akbar
   screen for every movement in between
6. After the second and last rakats: tashahhud; at the end, the salawat, *rabbana atina* and
   then the salam (X2)
7. After a fardh prayer only: *astaghfirullah* (X3), Ayat al-Kursi, then the dhikr on the beads

The witr has its qunut before ruku in the third rakat. The steps are data
(`assets/content/steps.json` and `units/`); the intention's wording is `intention` in
`assets/content/packs/en/pack.json`.

## How large the words come out

The words on the prayer screen are not a fixed size: each screen is fitted with the largest
lettering at which everything on it still fits the space, so a single phrase fills the screen and
Al-Fatiha's seven verses come out smaller.

What decides that is mostly how far apart the lines sit. A font's own line height leaves room for
every mark it could ever draw, not the marks the text in hand actually has: Scheherazade reserves
about a third more than these verses need, and on a seven-line screen that is a third of the
height given over to nothing, with the lettering shrunk to fit what is left. So the room is
measured from the text and the font in use - the tallest letters and marks that really occur -
and the lines are closed up to that and no further (`ink_share` and `line_box` in
`salaah/render.py`). Al-Fatiha came out about a quarter larger for it.

That measuring is what keeps it safe, and it is worth understanding before changing it. Amiri's
letters fill nearly all of its line box and it is left almost exactly as it was; Scheherazade and
Noto have room to spare and are closed up. `LEADING` is a floor on how close the lines may ever
come, and `INK_ROOM` is the clear space always kept above the tallest marks. A test renders every
recitation in all three lettering choices, with and without the meaning beside it, and counts the
bands of ink to prove no line has run into the next and nothing is cut off at an edge.

## The prayer screen

The left third of the screen is a fixed picture frame with a black border. A standing figure
fills its full height; bowing, sitting and prostrating figures are drawn at the share of that
height the posture really takes and capped to the frame's width, so the whole figure is always
visible. They all stand on the frame's bottom line. Those shares live in
`tools/build_postures.py` (HEIGHT_SHARE) if any figure wants adjusting.

The rest of the screen is Arabic only, in bold Scheherazade New, a clear modern naskh with the
vowel marks in full. Settings offers two other faces; they fit slightly differently, so on a long
surah one may come out larger than another. Each recitation is one screen: a whole surah is never split, so the recording can play straight
through without the page turning underneath it. The text is drawn as large as that screen allows,
which means a short line like "Allahu Akbar" is enormous and Al-Fatiha, the longest, is the
smallest at around 55px on a 1080p screen.

The English translation is not shown. It is still in the language packs, so it can come back
later (in a separate learning view, for instance) without redoing the content. Transliteration is not shown.

The fonts are in `assets/fonts`, all under the SIL Open Font License, so they can ship in a
product. See that folder's README about the Madinah Mushaf script.

The daily passage and saying come from `assets/content/daily/`. There are **58 Qur'an passages
and 42 sayings**, paired by the date, so a pair comes round about once every six weeks rather
than every fortnight as it did at first.

- **Qur'an:** Arabic verbatim from a verified text. The first twenty passages are the Uthmani
  text from quranenc.com; the rest are the Ḥafṣ mushaf published as the `quran-text` package
  (CC BY 4.0), with its pause marks re-attached and its three "open" tanwīn codepoints mapped to
  the set the first twenty use. That conversion was proved by rebuilding all twenty of the
  originals from it: eighteen came back character for character, and the two that differed did so
  only by a presentational tatweel that the original text itself uses twice in twenty-eight
  places.
- **Hadith:** the saying itself, verbatim from a public-domain dataset
  (github.com/fawazahmed0/hadith-api, Unlicense), cut to the part in quotation marks so the chain
  of narrators is left out, and kept with its canonical reference (e.g. Sahih al-Bukhari 13) so it
  can be checked on sunnah.com. A saying of the Prophet is not something to take on one source,
  so **all forty-two are also looked for, letter for letter, in a corpus that had no part in
  producing the file** — the MIT-licensed `hadith` package, 62,178 narrations across the nine
  collections. All forty-two are there. One candidate that was not was thrown away rather than
  patched. Re-run it with `python3 tools/check_hadith.py` (needs `pip install hadith`).
  What that cannot check is whether the reference *number* is right, or whether the saying is
  sound; the numbers want checking one at a time on sunnah.com, and the content by a reviewer.
- **The English in both is ours**, a plain rendering written for this app. sunnah.com's own
  English translations are modern copyrighted works and are deliberately not used; their terms
  also bar mass reproduction. If you want their wording, or their grading fields, apply for an API
  key at github.com/sunnah-com/api and we can add it properly.
- **Each English rendering covers the whole of the Arabic beside it.** The two are read side by
  side, a column each, so the one fault a reader cannot spot for themselves is English that
  renders the opening clause of a long verse and silently leaves off the rest. Ten of the
  passages are verses too long to read across a room; for those the Arabic is **a clause of the
  verse**, cut at a sentence boundary out of the verbatim text, and the reference is still the
  verse it came from. The cuts were taken by word position rather than by retyping, and then
  checked against the Tanzil text in the `pyquran` package — a corpus with no part in producing
  any of this — so each one provably lands on word boundaries with nothing altered in between.

  Two checks keep it that way. `python3 tools/check_daily.py` (needs `pip install quran-text`)
  asks the reference text whether every passage is still an unbroken run of the words of the
  verse it claims to be, and names any that is not.
  `DailyTest.test_the_english_renders_all_of_the_arabic_beside_it` counts the words on both sides
  and fails if an English rendering is shorter than its Arabic, which is what slipping back to an
  opening clause would look like. Both checks, and the hadith one above, were tried against
  deliberately damaged copies of the files first, to be sure they fail when they should.
  Because the Arabic and its meaning are now lettered to one size worked out from how much there
  is to say, a longer passage makes the whole pair smaller. Three tests hold the floor: every
  passage against the longest saying and every saying against the longest passage, checking that
  the pair is still at or above the size we hold to, that the Arabic and the meaning agree, and
  that no meaning is cut off at the foot of its box — that last one by looking at the pixels,
  rather than by asking the same measurement that chose the size, which would only agree with
  itself. It caught a case sitting one pixel clear of the bottom.
- **Neither file is built by a script any more.** `tools/build_daily.py` and
  `tools/build_hadith.py` each wrote their file from a table inside themselves, and both tables
  stopped at the first version; running either now would throw away most of the pool and put the
  older English back. They are kept because those tables are the record of what was picked and
  what English was written for it, but both refuse to run and say why. The two `check_` tools
  above are what to reach for instead.
- **Both files are still draft** and need a reviewer to check every line — the English above all,
  and the choice of where the ten clauses end.

Text comes from `assets/content`: Arabic in `core/arabic.json`, the after-prayer dhikr in
`core/dhikr.json`, English in `packs/en/pack.json`.
Rebuild them with `python3 tools/build_text.py <quran.json>`. Posture figures are in `assets/postures`; rebuild them from a folder of drawings with
`python3 tools/build_postures.py path/to/drawings` (it clears the watermark, reduces them to
black on white and trims them). The mosque screen is built from the main drawing with
`python3 tools/build_mosque.py path/to/Main_Screen.png`, which finds the arches and the dome. The
arch used on the choice screen is taken from the arch artwork with
`python3 tools/build_arch.py path/to/prayer_arches.png`: the app keeps the shape, not the
picture, and draws its own numbers and labels, so a prayer can have any number of units. Which figure a step gets is decided in
`salaah/pages.py`, including where the hands are: folded for the recitation, at the sides from
standing up after bowing until prostration.

## Known limits (prototype)

- The dhikr words in `core/dhikr.json` are vowelled for a beginner and need the same review as
  the rest of the non-Qur'anic Arabic. The counts are 33 each, which is the common practice, but
  they are data, so a reviewer can change them.
- Content is still draft, though the screen no longer says so. The school is marked
  "Draft, needs review" in Settings until a teacher has been through it. The structural checks
  all pass now, but that is not the same as being reviewed. Two findings from the old slides await a teacher's review:
  the witr qunut is in rakat 2 instead of 3, and the 2-rakat unit lacks a takbir before tashahhud.
- The power button sleeps the screens but the Pi stays running, so the mat still draws a few watts
  doing nothing. Running a day on a battery wants a proper shutdown between prayers, woken by the
  Pi's RTC alarm from the prayer times the app already works out. Not built yet. A UPS HAT that
  cuts its output after shutdown would stop the wake working, so that is worth checking before
  buying one.
- Whether to play a recitation aloud while actually praying is a question for your reviewer;
  in prayer a person recites themselves. It is off by default and is meant for learning and
  practice rather than for use inside the prayer.
- The English is a plain-English meaning written for this app, not a published translation, and
  the non-Qur'anic wordings were typed from memory of the standard Hanafi texts. Both need
  checking by a qualified reviewer before anyone relies on them.
- A Bluetooth keyboard paired with the Pi would also be treated as the prayer button.
