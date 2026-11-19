#!/usr/bin/env python3
"""Puts a coloured film in beside the black-and-white one it twins.

    python3 tools/install_colour_film.py assets/welcome/front.gif  kaaba.gif
    python3 tools/install_colour_film.py assets/azaan/muezzin.gif  azaan.gif
    python3 tools/install_colour_film.py assets/world/globe.gif    globe.gif

For the three coloured films that are one picture rather than a sheet of tiles, so there is
nothing to cut and nothing to line up -- the front door, the muezzin and the turning globe. The
two menus have their own tool, tools/menu/install_colour.py, because they carry ten languages
and a set of touchable boxes.

The name is the convention the rest of the mat already uses for a second version of a picture:
render.PixmapCache.after_dark writes `<stem>-dark<suffix>`, so a coloured twin is
`<stem>-colour<suffix>`. One rule, so one helper in the app can find any of them.

WHAT IS CHECKED. The twin has to be the same shape as the film it stands in for -- not the same
size, because these are scaled to whatever screen they land on, but the same shape, since a
drawing at a different aspect would be letterboxed or cropped where the original was not. And it
has to be a film: a single frame would stand still where the mat expects movement.

AND IT SQUEEZES, OR LEAVES WELL ALONE. One palette for the whole film, laid on without dither,
is what makes these files small: an exporter writes every frame in a palette built for
photographs and re-dithers each one, so a background that never moves is different on every
frame and the compressor can do nothing with it. That is worth three quarters of the front door
and two thirds of the side menu. It is worth NOTHING on the globe, which is seventy-two frames
of a photographic earth where almost every pixel honestly changes -- there the squeeze comes out
6% LARGER, so the file is taken as it was drawn. Measured each time rather than assumed, and the
smaller of the two is kept.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent

#: How far the twin's shape may differ from the film it twins, as a fraction. A 1600x900 front
#: door and a 1920x1080 one are the same shape to seven decimal places; this is for rounding,
#: not for a different crop.
SHAPE = 0.01


def frames_of(path: Path):
    with Image.open(path) as film:
        loop = film.info.get("loop", 0)
        frames, held = [], []
        for frame in ImageSequence.Iterator(film):
            frames.append(frame.convert("RGB"))
            held.append(frame.info.get("duration", 100))
    return frames, held, loop


def squeeze(frames, colours: int):
    step = max(1, len(frames) // 8)
    sample = frames[::step]
    tall = Image.new("RGB", (frames[0].width, frames[0].height * len(sample)))
    for i, frame in enumerate(sample):
        tall.paste(frame, (0, i * frame.height))
    palette = tall.quantize(colors=colours, method=Image.Quantize.MEDIANCUT)
    out = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    for frame in out:
        frame.info.pop("transparency", None)
    return out


def install(twins: Path, source: Path, colours: int) -> int:
    if not twins.is_file():
        raise SystemExit(f"{twins} is not there; a coloured film stands beside one that ships")
    out = twins.with_name(f"{twins.stem}-colour{twins.suffix}")

    frames, held, loop = frames_of(source)
    if len(frames) < 2:
        raise SystemExit(f"{source.name} has {len(frames)} frame(s); the mat expects a film here")
    with Image.open(twins) as old:
        was_size, was_frames = old.size, getattr(old, "n_frames", 1)
    shape = frames[0].width / frames[0].height
    want = was_size[0] / was_size[1]
    if abs(shape - want) / want > SHAPE:
        raise SystemExit(f"{source.name} is {frames[0].size} ({shape:.4f}) and {twins.name} is "
                         f"{was_size} ({want:.4f}); a different shape would be cropped or "
                         f"letterboxed where the original is not. Nothing written.")

    beside = out.with_suffix(out.suffix + ".new")
    try:
        kept = squeeze(frames, colours)
        kept[0].save(beside, format="GIF", save_all=True, append_images=kept[1:], loop=loop,
                     duration=held, optimize=True, disposal=1)
        smaller = beside.stat().st_size < source.stat().st_size
        if not smaller:
            # The squeeze made it bigger. Take the film as it was drawn -- but read it back the
            # same way, so a file the mat cannot play is caught here rather than on the mat.
            shutil.copyfile(source, beside)
        with Image.open(beside) as check:
            if check.size != frames[0].size or getattr(check, "n_frames", 1) != len(frames):
                raise SystemExit(f"{beside.name} came back as {check.size} with "
                                 f"{getattr(check, 'n_frames', 1)} frames; not written")
        beside.replace(out)
    finally:
        beside.unlink(missing_ok=True)

    print(f"{out.relative_to(ROOT)}: {frames[0].size}, {len(frames)} frames, "
          f"{out.stat().st_size / 1e6:.2f}MB "
          f"({'squeezed from' if smaller else 'as drawn,'} {source.stat().st_size / 1e6:.2f}MB)")
    print(f"  stands beside {twins.name}: {was_size}, {was_frames} frames, "
          f"{twins.stat().st_size / 1e6:.2f}MB")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("twins", type=Path, help="the film that ships, e.g. assets/welcome/front.gif")
    ap.add_argument("source", type=Path, help="the coloured film as it was drawn")
    ap.add_argument("--colours", type=int, default=128, help="palette size to try (default 128)")
    args = ap.parse_args()
    return install(args.twins if args.twins.is_absolute() else ROOT / args.twins,
                   args.source if args.source.is_absolute() else ROOT / args.source,
                   args.colours)


if __name__ == "__main__":
    raise SystemExit(main())
