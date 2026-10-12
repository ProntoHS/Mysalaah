# The station logos

One per station, named for its key in `../stations.json`. A station with no file here is drawn
with its name written across the square instead, which is what every station had until 1.74.

These are **not pictures**. Each is a stencil: the colour has been thrown away and only the
alpha channel is kept, so the mat paints its own ink through the shape at the moment it draws
it — black on white by day, white on black at night, and white over the red of the station
that is playing. Opened in anything else they look like white artwork on nothing, which is why
they are listed here rather than left to be worked out from a thumbnail.

Made with `tools/make_station_logo.py`, which is also where the how and why of that is written
down. To add one:

    python3 tools/make_station_logo.py <their-logo.png> assets/content/radio/logos/<key>.png

and look at what comes out. The tool guesses which side of the artwork is the drawing from the
colour of its border and says so as it runs; `--no-invert` or `--invert` settles it when the
guess is wrong, which it was for one of these six.

| File | Station | Supplied as | Made with |
|---|---|---|---|
| `radio-sunna.png` | Radio Sunna | `7765f0bb-image.png`, 239×239 | guessed: framed in white, dark pixels are the drawing |
| `mishary.png` | Mishary Alafasy | `14b4a1a9-image.png`, 1254×1504 | guessed: framed in black |
| `nasheeds.png` | Nasheeds | `a5fef2fe-image.png`, 1200×1200 | guessed: framed in black |
| `imc-uk.png` | Islam Media Central | `27e77a61-image.png`, 600×600 | guessed: framed in black |
| `buzz-islam.png` | Buzz Islam | `70adb9c9-image.png`, 330×330 | `--no-invert`: the white corners outside its rounded square fooled the guess |
| `radio-ikhlas.png` | Radio Ikhlas | `920c9dba-image.png`, 476×476 | guessed: framed in black |

## Where they came from, and on what footing

All six were sent by Harry on 12 October 2026, with the two new addresses, to replace the names
that were written on the squares: "the icons should be self explanatory so no text needed
underneath".

They are each station's own mark, used here to say which station a square will tune to and for
nothing else — the mat does not sell anything, does not claim any connection to any of them,
and the square is a tuning button in a list of six. That is the ordinary footing for naming
somebody by their own name. It is also not a licence, and none has been asked for: if a station
would rather its mark were not used this way, delete its file and the square goes back to
carrying its name in words, which is all it did until now.

Nothing here has been checked by anybody qualified, and the same goes for the stations
themselves — see the note at the top of `../stations.json`.
