# What the two pieces of game artwork measured, 21 October 2026

Harry sent `kaaba-puzzle.svg` and a screenshot of the Qibla Quest prototype's world map and
asked whether they were any good. Both are. This is what had to change, measured rather than
judged by eye, with the tools left beside this file so the measurements can be repeated:

    QT_QPA_PLATFORM=offscreen python3 -I tools/sheet.py   <picture>     # nine pieces
    QT_QPA_PLATFORM=offscreen python3 -I tools/mirrors.py <picture>     # left-right twins
    QT_QPA_PLATFORM=offscreen python3 -I tools/pins.py    <map svg>     # bearings and pins
    QT_QPA_PLATFORM=offscreen python3 -I tools/build_assets.py <outdir> # makes both PNGs

Every one of them runs its controls first and stops if a control misbehaves. One earlier
version of the piece checker called nine printed digits "eight twins out of nine" and was
thrown away for it; see the note at the top of `sheet.py`.

## The Kaaba

**Polarity.** Drawn white-on-black. Inverted for the mat it also becomes *more* correct, not
just more consistent: the faces go black and the band goes white, which is how the kiswah
actually looks.

**Empty corners, as sent.** The building is centred, so two of the nine pieces the game cuts
are white squares with one pale hairline across them:

| piece | visible ink | = coverage | x contrast |
|---|---|---|---|
| top-left | 0.78% | 2.2% | 35% |
| top-right | 0.78% | 2.2% | 35% |
| the other seven | 21.9% - 77.9% | | |

Cropping to the building (the group is `translate(125 218)` spanning 0..650 by 0..635) takes
that to **0 of 9 empty**, every piece between 38% and 89%. That is what
`assets/children/kaaba-jigsaw.png` is: inverted, cropped there, squared off to 633x633 so the
game's integer thirds divide evenly. The crescent and the stars are lost in the crop.

**Still outstanding: two mirror pairs.** `mirrors.py` compares each piece with its horizontal
partner flipped. Both as sent and cropped:

| pair | as-is | flipped |
|---|---|---|
| top-left / top-right | 0.61 | **0.98** |
| left / right | 0.53 | **0.95** |
| bottom-left / bottom-right | 0.50 | 0.62 |

Four of nine pieces have an identical twin, so those rounds are a coin-flip between two of the
three positions offered. The bottom row escapes **only because the door is on one side** --
which is also the fix, and the control proves it is enough: marking a single corner of a
symmetric diamond cleared that pair and left the other two standing. What is needed from the
artist is one distinct mark in the left half with no twin in the right half, in the top row
and in the middle row. Nothing else.

The game does not punish a wrong answer, so it is playable meanwhile.

## The world map

**It is vector, not a bitmap.** `standalone_prototype/static/index.html` holds the map inline:
viewBox `0 0 1200 590`, ten `<path>` continents in a `class="continents"` group. So
`assets/children/qibla-quest.png` is rendered from that geometry at 1600x786 and inverted --
not traced off the screenshot. The route line and the `YOU` and `MAKKAH` labels are left out:
the game draws those, and no words may be baked into the picture.

**All five bearings are right.** Initial great-circle bearing to 21.4225 N, 39.8262 E, binned
to eight points: London 119.0 deg SE, Cape Town 23.4 NE, Tashkent 240.3 SW, Jakarta 295.2 NW,
Istanbul 151.6 SE. Every one matches the shipped answer.

**The five pin coordinates in `qibla_quest.py` are mis-transcribed.** The module carries
fractions that are nowhere near the prototype's own points -- off by up to 130 px, an
ninth of the map's width -- and three of them land in open sea. The right numbers are the
prototype's `map_point` divided by the viewBox:

| city | module ships | prototype point | correct fraction | module was out by |
|---|---|---|---|---|
| london | (0.45, 0.25) | (430, 110) | **(0.358, 0.186)** | 116 px, into the Mediterranean |
| cape_town | (0.53, 0.78) | (538, 420) | **(0.448, 0.712)** | 106 px, into the Indian Ocean |
| tashkent | (0.63, 0.29) | (735, 145) | **(0.613, 0.246)** | 33 px |
| jakarta | (0.78, 0.70) | (1008, 305) | **(0.840, 0.517)** | 130 px, onto Australia |
| istanbul | (0.55, 0.34) | (558, 150) | **(0.465, 0.254)** | 114 px, out to sea |

Apply these when the module goes in, and pin the test to them.

**A caution about the automatic land test, and why there is no longer one.** It passed Jakarta
at the module's own fraction, because that point *is* on land -- the wrong land, Australia.
Being on ink is not being in the right place, and only looking at the overlay showed it.

Measured against the shipping picture, distance-to-land does not separate right from wrong at
all:

| city | the shipped pin | the mis-transcribed pin |
|---|---|---|
| london | 0 px from land | **7 px** |
| cape_town | 0 px | 81 px |
| tashkent | 0 px | 0 px |
| jakarta | **45 px** | **0 px** |
| istanbul | 9 px | 16 px |

Any tolerance loose enough to pass the correct Jakarta also passes the wrong London, and the
wrong Jakarta scores better than the right one. So the test in `tests/test_ui.py` pins the five
points against the prototype's authored coordinates instead -- which is the fault that actually
happened -- and the artwork's gaps are recorded here rather than tested around.
`tools/pins.py` still prints which numbered path each pin lands on; the judgement is a person's.

## One thing the strings turned up

**In Chinese the compass screen and Qibla Quest have the same heading.** `qibla.title` and
`qiblaquest.title` both read 朝向天房. The key collision is fixed -- that was the point of the
rename, and eight packs would otherwise have had "Face the Qibla" overwritten -- but in zh the
two translations coincide, so a Chinese mat shows two different screens under one name. Nothing
in the code can fix that and inventing Chinese would be worse than reporting it. English, the
language this copy was written in, reads differently.

`tests/test_ui.py` records the list of languages where they coincide and fails if it changes,
so a new one appearing shows up rather than passing unnoticed. For whoever reviews the Chinese:
this is one to look at.

**The artwork has no Arabia and no Indonesia.** Even the prototype's own points put Jakarta,
Istanbul and Makkah itself in water, because the map is stylised down to ten blobs. Makkah is
the one that matters, being the fixed point every route line is drawn to. It reads acceptably
as "where Arabia should be", but if the map is ever redrawn, a peninsula there and some islands
at Indonesia would earn their place.

## The coloured wu'du artwork, 17 November 2026

Harry redrew the seven wu'du steps and the eight animations in colour, and recoloured the
world map, and asked for one thing of all of them: "as the background is white, the white can
be inverted if on dark theme and the pictures can stay the same", and then, on seeing the
first attempt, "i dont want you to invert the the actual child and wash basin etc, just the
background only if possible."

    python3 -I tools/wudu/install_colour.py <animations> <sheets> <map>
    python3 -I tools/wudu/install_colour.py --measure   . . <map>    # the map alone

### Why the background cannot be found by colour

The obvious rule -- invert every pixel close to grey -- was rendered and looked at, and it is
wrong twice over. Near-white paper and the near-white of the boy's thobe are the same colour,
so the thobe goes with the paper; his hair is near-black and comes back speckled, because the
dither leaves half its pixels just over the line and half just under.

Measured on the first frame of `01_wash_hands`: only **46%** of the pixels darker than 110 are
within 20 levels of grey, and the median saturation of the dark pixels is **36**. The outlines
are warm dark brown, not black. There is no threshold that separates the paper from the boy.

So the paper is a REGION: near-white, reachable from the edge of the picture without crossing
an outline. It does not depend on where the threshold is put, because the paper meets the
drawing at a hard outline:

| how far from white still counts as paper | 20 | 28 | 40 | 60 |
|---|---|---|---|---|
| paper found | 58.24% | 58.24% | 58.24% | 58.24% |

and specks of dither stranded inside it are absorbed, which is flat over six doublings:

| specks up to | 1px | 16px | 64px | 256px | 1024px |
|---|---|---|---|---|---|
| paper found | 58.24% | 62.24% | 62.24% | 62.24% | 62.24% |

### Two different dilations, because there are two kinds of artwork

The paper is then taken a little way back into the drawing, to eat the edge. How far is not
the same for the animations and the sheets, and the difference is not small.

Every ink-and-paper boundary in the **animations** carries a lime-green fringe one to two
pixels wide. It is in the files as sent, it is invisible on white paper, and on a black page
it is a bright rim round the boy. Two pixels takes it off; one leaves a trace along the top of
his hair.

The **sheets and the map** have no such fringe, and two pixels does real damage:

| pixels taken back | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| the frame round a step, thickness | 5px | 3px | **1px** | — |
| the map's drawn land still there | 99.4% | 95.1% | **91.1%** | 87.0% |
| pale halo round every coastline | yes | no | no | no |

At two pixels the frame is a hairline and the smallest islands in Indonesia and the Caribbean
are gone. So: **two for the films, one for the stills**, and both were arrived at by rendering
the alternatives onto a black page and looking at them.

### Paper the edge of the picture cannot reach

Flooding in from the border leaves enclosed paper opaque, and on a black page a patch of opaque
paper is a white box. All three kinds of artwork have some, and none of them have it the same
way.

**A film** has gaps in the drawing -- the piece of wall seen through the arch of the tap is the
biggest, and it came out as a white rectangle under the spout. What tells a gap from a drawn
white line is not its area but its THICKNESS, so an enclosed piece is taken when a disc of
GAP_DEEP pixels fits inside it. Measured on the still plate of all eight:

| film | enclosed pieces taken, by size | deepest |
|---|---|---|
| hands | 4029 | 27.7 |
| mouth | 800, 705 | 10.8 |
| nose | 4801, 1461, 656 | 32.1 |
| face | 628, 450 | 10.0 |
| arms | 3316, 660 | 22.0 |
| head | 949, 908, 790 | 11.0 |
| head-2 | 2221, 2050 | 17.8 |
| feet | 4108, 3880 | 28.0 |

**The same pieces are taken at 8, 9 and 10 in every one of the eight.** The set only changes at
6, which starts taking highlights off the thobe, and at 12, which starts leaving gaps behind.

**A step sheet** has a frame drawn round it, so its paper is the margin outside the frame plus
the column inside it. There is exactly one enclosed piece and it is 212,636 pixels against 283
for the next largest -- a factor of 750, with nothing to tune.

**A map** is land on water. Nothing is white inside the drawing, so every enclosed piece is
sea: the Mediterranean at 6404 pixels, then 1688, 1374 and 1262, and the largest thing that is
not a sea is a 42-pixel speckle inside Greenland. A floor anywhere from 100 to 800 takes
exactly the four. A first attempt that took ALL the white punched those speckles through
Greenland and had to be looked at to be found.

THE GAPS ARE FOUND ON THE STILL PLATE, not frame by frame. Water falling through the arch of
the tap splits that gap into two thinner pieces, neither thick enough to count, so found per
frame the gap would be dropped altogether -- or, worse, taken in the frames where the water is
elsewhere and the stream cut. Checked frame by frame afterwards: the stream and every droplet
survive.

### Thirty-three megabytes down to seven

The eight animations arrived at 4.1-4.3 MB each. That is not detail, it is noise: they were
saved with the picture re-dithered on every frame.

| measured on `01_wash_hands` | |
|---|---|
| pixels swinging more than 40 levels across the 48-frame loop | **80.2%** |
| pixels differing from the frame before, as sent | 26.6% |
| the same after one shared palette and no dithering | 18.9% |
| the same after the plate | **4.1%**, all of it inside the moving part |

The drawing does not move. Frames 0, 1, 16 and 32 of the hem and the tap are the same
linework pixel for pixel; what changes is which stipple pattern the quantiser chose that
frame. So the median of the 48 frames is taken: random dither cancels and what is left is the
painting underneath, grain and all. The plate is **better** than any single frame as sent.

Each frame is then rebuilt as the plate with its own pixels put back only where something
moves, and what moves is found on the SIGNED difference from the plate, smoothed over a 9px
window. On the ABSOLUTE difference it does not work at all -- the mean of an absolute dither
is a large positive number everywhere, and the mask comes back covering a quarter of the
picture at every threshold tried.

| film | as sent | built | page shows through |
|---|---|---|---|
| hands | 4141 KB | 630 KB | 65.0% |
| mouth | 4235 KB | 768 KB | 65.3% |
| nose | 4100 KB | 979 KB | 64.0% |
| face | 4257 KB | 916 KB | 66.0% |
| arms | 4185 KB | 1114 KB | 65.4% |
| head | 4318 KB | 1027 KB | 62.3% |
| head-2 | 3851 KB | 813 KB | 66.2% |
| feet | 4251 KB | 831 KB | 68.0% |
| **eight** | **33342 KB** | **7083 KB** | |

Qt decodes the result -- transparent, one palette, each frame carrying only what changed, left
in place for the next -- **identically to Pillow**: zero colour difference over all 48 frames
of all eight, and transparency agreeing on every pixel.

### The sheets, and the one thing that must turn over

Each step is a drawing with a frame, a numbered badge and a label in black around it. The boy
must not turn over and the lettering must, so a night version is built beside each picture and
what turns over in it is decided per DRAWN SHAPE: a connected piece of ink with colour in it
is left alone, a piece with none is inverted. The boy keeps his black hair because his hair is
part of a shape that also contains his face.

Across all seventy, measured on the shipped files:

| | |
|---|---|
| worst change to a strongly coloured pixel (saturation >= 40) | **0 levels** |
| black in the frame band that came out light | **100%** |
| black in the top fifth -- badge and label -- that came out light | **100%** |
| seventy day pictures and seventy night ones | 2387 KB, against 6078 KB for the old seventy |

**The sheets do not all read the same way.** Harry draws the Urdu and Arabic ones with step 1
on the right. The first run of the installer read all ten left to right and put the feet on
the hands and the hands on the feet in both. The order now follows the language's own pack,
and is then checked against the drawing: the head is the one step drawn as two pictures, so
whichever column holds two must be the sixth, or nothing is written. Counted as bands of
drawing down the column, every sheet gives `[1, 1, 1, 1, 1, 2, 1]` in step order.

### The world map is the same projection

`qibla_quest.py` warns that a redrawn map silently invalidates every city pin, and it has
happened twice. This one is the October map recoloured:

| | old | new |
|---|---|---|
| land | 27.3% | 26.8% |
| centre of the land | (0.5061, 0.3984) | (0.5066, 0.3989) |
| extent | x 13..1886, y 74..988 | x 14..1887, y 74..986 |
| land the two share | **96.0%** | |

and every city still lands on the land. Measured under the pin the game actually draws -- a
filled disc of `px(16)` -- on both maps at the same size, so the two are comparable:

| | London | Cape Town | Tashkent | Jakarta | Istanbul |
|---|---|---|---|---|---|
| on the October map | 83% | 42% | 100% | 26% | 78% |
| on this one | 68% | 36% | 100% | 16% | 74% |

Every one of them is a few points lower, which is the one pixel of paper taken back round
every coastline, and Jakarta is the tightest because Java is thin. A pin in open sea reads 0%.
**No point in `qibla_quest.py` has been touched.** `--measure` prints this table against
whatever map is passed in, and refuses the install if the two share less than 90% of their
land or any pin falls in the sea.

### The lettering is the 2.43 lettering, and the badge decides which tile it comes from

Harry's 2.44 labels lost between a third and three quarters of their ink in all ten languages,
and in Urdu, Arabic and Hindi the letters came apart as well -- the joins are not made, so the
words do not read. Asked, he chose to keep the lettering already on the mat and take only the
drawings from the new sheets.

| label ink, step 1 | en | ar | bn | es | fr | hi | pt | ru | ur | zh |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.43 | 3084 | 3081 | 3422 | 3071 | 3067 | 3122 | 3186 | 3752 | 3026 | 2617 |
| 2.44 sheets | 1954 | 1079 | 1397 | 2015 | 1939 | 1220 | 1960 | 960 | 1066 | 1243 |
| change | -37% | -65% | -59% | -34% | -37% | -61% | -38% | -74% | -65% | -53% |

The transplant needs no guessed rows. The two sets are on the same grid -- 284x1026 against
285x1027 -- so the older tile is scaled the one pixel it is out. The FRAME is the one connected
piece of ink whose bounding box spans the whole tile: exactly one in each of the seventy,
12,376 pixels every time. The BADGE AND LABEL are the ink above the drawing, cut in the middle
of the blank run between the two, which is **63 rows at its tightest** (Arabic and Urdu's
"rinse mouth") and 308 at its widest.

**WHICH older tile is asked of the badge, not of the filename**, because the filename lies. The
2.43 release has its Urdu and Arabic step pictures in reverse -- `step-hands.ur.png` is wholly
the seventh tile, badge, words and drawing together, and `step-feet.ur.png` is the first. The
digit in the badge is the same drawing in every language, so the tile whose badge is closest to
English step N's badge is step N. Across the seventy 2.43 pictures:

| | matched English steps, 0-based, in filename order |
|---|---|
| Urdu | 6, 5, 4, 3, 2, 1, 0 |
| Arabic | 6, 5, 4, 3, 2, 1, 0 |
| Bengali and the rest | 0, 1, 2, 3, 4, 5, 6 |

which finds the fault, in exactly the two languages that have it, with nothing told to it.

**The sweep.** Only two sets of pictures on the mat are drawn one per language: the seventy
wu'du steps, which had this, and the ten mosques, which are a single picture each and so have
no order within them to get wrong. Every other menu has one set of pictures for all ten
languages.
