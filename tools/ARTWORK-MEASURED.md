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
