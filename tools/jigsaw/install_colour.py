#!/usr/bin/env python3
"""Puts Harry's 2.43 watercolours in: five for the jigsaw, five skies for the prayer-day game.

    python3 tools/jigsaw/install_colour.py <the five jigsaw scenes> <the five skies>

SUPERSEDES install_scenes.py, which put the flat black-and-white set in at 2.38. Harry, at
2.43: "i don't like the jigsaw's i had you swap before, they are too b&w which actually makes
it difficult for a jigsaw, we need colour." He is right about the game as well as the look --
a piece of flat white is a piece of flat white wherever in the picture it came from, and
colour is most of what lets a child place one.

THE FILENAMES ON THE MAT DO NOT CHANGE. journey_jigsaw.py and prayer_day_journey.py name their
pictures, the packs name them in ten languages, and the loaders read those lists. So this
writes over the ten files and touches nothing else.

WHICH SCENE REPLACES WHICH IS A JUDGEMENT, carried over from install_scenes.py unchanged, and
the same caveat stands: Harry's congregational_prayer fills a slot the packs call "Eid Prayer"
in ten languages. Eid prayer IS congregational, so the name is not wrong, but it is more
particular than the picture. Still flagged, still costs ten strings to change.

TWO HUNDRED AND FIFTY-SIX COLOURS, NOT SIXTEEN MILLION. Written whole these ten come to 29 MB,
which is half the release again for ten pictures. A 256-colour palette with dithering brings
them to 9 MB, and the difference is not visible: measured on the Fajr sky, which is the one
with the longest gradient and so the one most likely to band, the mean error is 3.4 levels out
of 255 and the two crops side by side cannot be told apart. The old black-and-white set was
quantised to sixteen greys for the same reason.

THE TWO HAND-DRAWN DARK PICTURES GO. Harry drew kaaba-jigsaw-dark.png and
journey-jigsaw-dark.png at 2.40 so the dark theme would not invert a black Kaaba into a white
one. The pictures they shadowed are gone, and a painting is never turned over at all -- see
journey_jigsaw.Screen._image -- so they are 580 KB shadowing nothing.
"""
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = HERE / "assets" / "children"

#: Enough of Harry's filename to know it by -> the file on the mat. A fragment rather than the
#: whole stem, because the whole stem carries what he happened to call that version of it
#: ("_v3_light_blue_sky_1920x1080").
INTO = {
    "kaaba": "kaaba-jigsaw.png",
    "hajj_journey": "journey-jigsaw.png",
    "mosque_family_meal": "ramadan-iftar-jigsaw.png",
    "congregational_prayer": "eid-prayer-jigsaw.png",
    "quran_mosque_interior": "quran-rehal-jigsaw.png",
}

#: The skies, which are named for their prayers already. Note zuhr: the file is Harry's
#: spelling and the mat's filename, and the app's own key for it is "dhuhr".
SKIES = {name: f"prayer-day-{name}.png" for name in
         ("fajr", "zuhr", "asr", "maghrib", "isha")}

JIGSAW = (1600, 900)        # what the five on the mat have always been
SKY = (1920, 1080)          # and the five skies likewise
COLOURS = 256
SQUARE = 0.004              # how far off 16:9 a drawing may be before it is refused

GONE = ("kaaba-jigsaw-dark.png", "journey-jigsaw-dark.png")


def colourfulness(im: Image.Image) -> float:
    """How far from grey, on average. Reported so that a drawing's colour can be seen here
    rather than discovered on the mat.

    THIS IS NO LONGER THE MAT'S OWN TEST. salaah/render.has_colour was this measure until 2.46
    and is now the SHARE of pixels that are clearly coloured, because an average is diluted by
    whatever surrounds the subject -- a gold Kaaba on a black field read as a line drawing and
    was turned inside out on the screen. These jigsaws are full-bleed paintings, so the two
    measures agree on every one of them; this is kept because it is a useful number to print,
    not because it is the deciding one."""
    small = im.convert("RGB").resize((160, 90), Image.LANCZOS)
    pixels = list(small.convert("RGB").tobytes())
    rgb = [pixels[i:i + 3] for i in range(0, len(pixels), 3)]
    return sum(max(p) - min(p) for p in rgb) / len(rgb)


def shaped(path: pathlib.Path, size) -> Image.Image:
    im = Image.open(path).convert("RGB")
    want = size[0] / size[1]
    got = im.width / im.height
    if abs(got - want) > SQUARE:
        raise SystemExit(f"{path.name}: {im.width}x{im.height} is {got:.4f}, wanted {want:.4f}")
    return im.resize(size, Image.LANCZOS)


def put(im: Image.Image, where: pathlib.Path) -> int:
    flat = im.quantize(colors=COLOURS, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG)
    flat.save(where, optimize=True)
    return where.stat().st_size


def install(folder: pathlib.Path, wanted: dict, size, what: str) -> None:
    print(f"{what}")
    have = {p.stem: p for p in folder.glob("*.png")}
    for key, name in wanted.items():
        matches = [p for stem, p in have.items() if key in stem]
        if len(matches) != 1:
            raise SystemExit(f"{folder}: {len(matches)} files match {key!r}, wanted exactly one")
        im = shaped(matches[0], size)
        was = (OUT / name).stat().st_size if (OUT / name).is_file() else 0
        now = put(im, OUT / name)
        print(f"   {matches[0].name[:44]:46s} -> {name:26s} "
              f"{was/1024:6.0f}K -> {now/1024:6.0f}K   colour {colourfulness(im):5.1f}")


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__.splitlines()[2].strip())
    install(pathlib.Path(sys.argv[1]).resolve(), INTO, JIGSAW, "The five jigsaw pictures")
    install(pathlib.Path(sys.argv[2]).resolve(), SKIES, SKY, "The five prayer-day skies")
    for name in GONE:
        here = OUT / name
        if here.is_file():
            here.unlink()
            print(f"   dropped {name}, which shadowed a picture that is no longer there")


if __name__ == "__main__":
    main()
