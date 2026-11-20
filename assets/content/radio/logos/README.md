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
| `radio-seerah.png` | Radio Seerah | `e5b9cf02-image.png`, 1000×1000 | guessed: framed in black |
| `unity-fm.png` | Unity FM | `8d47350b-image.png`, 1000×1000 | guessed: framed in black |
| `inspire-fm.png` | Inspire FM | `a5a555a8-image.png`, 1000×1000 | guessed: framed in black |
| `ramadan-fm.png` | Ramadan FM | `43c56c63-image.png`, 1000×1000 | guessed: framed in black |

## Where they came from, and on what footing

The first six were sent by Harry on 12 October 2026, with the Buzz Islam and Radio Ikhlas
addresses, to replace the names that were written on the squares: "the icons should be self
explanatory so no text needed underneath". Radio Seerah and Unity FM came the same evening,
with theirs, and Inspire FM and Ramadan FM an hour after that.

They are each station's own mark, used here to say which station a square will tune to and for
nothing else — the mat does not sell anything, does not claim any connection to any of them,
and the square is a tuning button in a list of six. That is the ordinary footing for naming
somebody by their own name. It is also not a licence, and none has been asked for: if a station
would rather its mark were not used this way, delete its file and the square goes back to
carrying its name in words, which is all it did until now.

## The coloured marks

Beside each stencil is a `<key>-colour.png`, and those are the one thing in this folder that
**are** pictures. They are shown only in the colour theme, and only while a station is not
playing; the moment one is playing its square turns red and the stencil comes back, because a
mark in its own brand colours on that red is two colours fighting and the red is what has to
be legible.

They did not come from the stations. Harry painted the whole radio page over a render of the
page the app draws, and `tools/radio/install_colour.py` cut the ten squares back out of it --
the sheet itself is not shipped, because the page is built from `../stations.json` at the
moment it is drawn, and freezing it as a picture would mean a station that stopped answering
stayed pictured and stayed pressable. The tool checks that the squares it found sit where the
app puts them, and that each mark looks more like its own station's stencil than like any
other's, before it writes anything.

**These are cut from his second sheet.** The first, on 19 November 2026, was animated -- a
colour ran across the marks -- and the marks it gave were soft-edged. Taking the middle value
of each pixel across the frames removes the sweep, but it cannot sharpen a stroke whose edge
the sweep moved: an edge that is half-lit in every frame is half-lit in the middle one too. He
noticed on the glass before any measurement did, and sent a still sheet the next morning. Cut
from that, the share of soft-edged pixels across the ten marks fell from 65% to 45%, and
nasheeds and ramadan-fm by better than 45 points each. The still sheet came at 1512x794 where
the render is 1920x1008, so the squares are compared at whatever scale the sheet was exported
at rather than pixel for pixel; all forty edges agreed to within a fifth of a pixel.

Stored as real colour with its own alpha, recovered from the black Harry drew on: a pixel's
brightness becomes its alpha and its colour is divided back out. So the soft edge of every
stroke survives, and the mark composites correctly over black and over red alike.

The footing is the same as for the stencils above, and so is the caveat: these are his
paintings of other people's marks, no licence has been asked for or given, and nothing here
has been checked by anybody qualified. Deleting a `-colour.png` is safe at any time -- the
square falls back to the stencil, in every theme.

Three of them are worth knowing about before anybody decides they look wrong:

- `unity-fm-colour.png` carries the station's name twice, small over large. So does the
  stencil, and so does the artwork both were made from.
- `radio-seerah-colour.png` reads `RAD` then a mosque then `SEERAH`. The mosque is standing in
  for the `IO`, which is how the mark is drawn.
- `mishary-colour.png` is a headdress and a beard in green, with nothing inside the outline of
  the face, where the stencil is a line portrait. That is the one mark whose edges are soft by
  design rather than by accident -- it is drawn as a glow, and it was the only one of the ten
  that the still sheet did not sharpen, because there was nothing wrong with it.


Nothing here has been checked by anybody qualified, and the same goes for the stations
themselves — see the note at the top of `../stations.json`.
