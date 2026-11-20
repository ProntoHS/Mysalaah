#!/usr/bin/env python3
"""SUPERSEDED AT 2.43 by install_colour.py, which puts the watercolours in. Running this
would put the flat black-and-white set back. Kept because it records how the 2.38 artwork was
measured and which scene fills which slot; do not run it.

Puts Harry's five drawn scenes into the jigsaw, in place of the five it has now.

    python3 tools/jigsaw/install_scenes.py <folder of the five scenes>

THE FILENAMES ON THE MAT DO NOT CHANGE. journey_jigsaw.py names its five pictures, the packs
name them in ten languages, and both the loader and playable() read that one list. Harry:
"everything should be the same, including difficulty levels apart from the pictures
themselves." So this writes over the five files and touches nothing else.

WHICH SCENE REPLACES WHICH IS A JUDGEMENT, so it is written down here rather than worked out
from a filename, and four of the five are plain:

    kaaba_courtyard        -> kaaba-jigsaw.png          "Kaaba"
    hajj_journey_to_kaaba  -> journey-jigsaw.png        "Journey to Mecca"
    mosque_family_meal     -> ramadan-iftar-jigsaw.png  "Ramadan Iftar"   (night, crescent,
                                                         lanterns, a family eating)
    quran_mosque_interior  -> quran-rehal-jigsaw.png    "Qur'an on Rehal" (it is on a rehal)

The fifth is not plain. Harry's file is called congregational_prayer and the slot it fills is
named "Eid Prayer" in ten packs. Eid prayer IS congregational, held after sunrise, outdoors or
in a large gathering, with families and children -- which is what the picture shows -- so the
name is not wrong. But it is more particular than the drawing, and a name that is more
particular than its picture is the fault already on the open list against the maze's pickups.
Flagged for Harry; renaming it costs a string in ten languages.

THE PICTURES ARE STILL NOT INVERTED FOR THE DARK THEME, and that wants saying because the
reason looks as though it has expired. journey_jigsaw._image explains that the old five were
photographic and inverting them made negatives. These are flat line art, which everywhere else
on this mat is exactly the kind that DOES invert. It still must not here, for the same two
reasons as before and in the same two pictures: the Kaaba is drawn as a solid black cube and
inverts to a white one, and the worshippers are drawn as dark silhouettes and invert to glowing
white figures.
"""
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = HERE / "assets" / "children"

#: Harry's name -> the file on the mat. See the note above; this is a judgement, not a rule.
INTO = {
    "kaaba_courtyard_flat_black_white": "kaaba-jigsaw.png",
    "hajj_journey_to_kaaba_flat_black_white": "journey-jigsaw.png",
    "mosque_family_meal_flat_black_white": "ramadan-iftar-jigsaw.png",
    "congregational_prayer_flat_black_white": "eid-prayer-jigsaw.png",
    "quran_mosque_interior_flat_black_white": "quran-rehal-jigsaw.png",
}

WIDE, TALL = 1600, 900      # what the five on the mat have always been
GREYS = 16                  # flat art: sixteen is enough for clean edges and cheap files


def main():
    scenes = pathlib.Path(sys.argv[1]).resolve()
    have = {p.stem: p for p in scenes.glob("*.png")}
    missing = [n for n in INTO if n not in have]
    spare = [n for n in have if n not in INTO]
    if missing:
        sys.exit("the folder has no scene called " + ", ".join(missing) +
                 "\nIt has: " + ", ".join(sorted(have)))
    if spare:
        sys.exit("scenes this tool has no slot for: " + ", ".join(sorted(spare)) +
                 "\nAdd them to INTO by hand -- which picture replaces which is a judgement.")

    was = {name: (OUT / name).stat().st_size for name in INTO.values() if (OUT / name).is_file()}
    for source, name in sorted(INTO.items(), key=lambda kv: kv[1]):
        picture = Image.open(have[source])
        # The shape has to match, or a plain resize would squash the drawing. These arrive at
        # 1672x941, which is 16:9 to within a thousandth, so nothing is cropped.
        ratio = picture.width / picture.height
        if abs(ratio - WIDE / TALL) > 0.01:
            sys.exit(f"{source} is {picture.size}, which is {ratio:.3f} to 1 and not 16:9. "
                     f"Resizing it would squash the drawing.")
        flat = picture.convert("L").resize((WIDE, TALL), Image.LANCZOS)
        small = flat.quantize(colors=GREYS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        small.save(OUT / name, optimize=True)
        now = (OUT / name).stat().st_size
        before = was.get(name)
        print(f"  {name:26s} <- {source}")
        print(f"  {'':26s}    {before:>9,} -> {now:>9,} bytes" if before else
              f"  {'':26s}    {now:>9,} bytes (new)")

    total_before, total_now = sum(was.values()), sum((OUT / n).stat().st_size for n in INTO.values())
    print(f"\n  five pictures: {total_before / 1024:,.0f} KB -> {total_now / 1024:,.0f} KB")


if __name__ == "__main__":
    main()
