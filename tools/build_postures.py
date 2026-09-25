"""Prepares posture artwork for the app.

Takes the drawings as supplied, clears the "Made with AI" badge in the top corner, reduces them
to plain black on white, trims the blank space and writes them to assets/postures.

Run: python3 tools/build_postures.py path/to/folder-of-drawings [where/to/put/them]
Each drawing is named after the posture it shows, e.g. ruku.png. Any name not in HEIGHT_SHARE
below is skipped, so the folder can hold other files.

Without a second argument the drawings go to assets/postures, the set the app shows by default.
Give one to build another set, e.g. assets/postures/girl; a set may be short of a posture or two,
and the app falls back to the default set for those.
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "postures"

EXPORT_BOX = 1200     # longest side, so nothing is blown up much on a 1080p screen
BADGE = (0.70, 0.0, 1.0, 0.10)   # the watermark sits in this corner: left, top, right, bottom
INK = 170             # darker than this counts as a line

# How tall each posture is compared with standing. The frame gives a standing figure its full
# height; the others are drawn to these shares of it, and capped to the frame's width so the
# whole figure is always visible.
HEIGHT_SHARE = {
    "standing_folded": 1.00,
    "standing_arms_down": 1.00,
    "standing_itidal": 1.00,      # standing straight again after bowing, seen from the side
    "takbir_raised": 1.00,
    "qunut": 1.00,
    "ruku": 0.68,
    "sujood": 0.42,
    "jalsa": 0.60,
    "tashahhud": 0.62,
    "salam": 0.60,
}

SUFFIXES = (".png", ".jpg", ".jpeg", ".jfif", ".webp")


def clear_badge(image: Image.Image) -> Image.Image:
    """Paints out the watermark, which would otherwise be trimmed to and shown as artwork."""
    w, h = image.size
    image.paste(255, (int(w * BADGE[0]), int(h * BADGE[1]), int(w * BADGE[2]), int(h * BADGE[3])))
    return image


def trim(image: Image.Image, pad: int = 4) -> Image.Image:
    """Cuts away the blank space round the drawing.

    A single stray speck in a corner would otherwise hold the whole margin in place, so a row
    or column only counts as part of the drawing when it carries more than a few marks."""
    mask = image.point(lambda v: 255 if v < 200 else 0).convert("L")
    width, height = mask.size
    marks = list(mask.tobytes())
    rows = [sum(1 for v in marks[y * width:(y + 1) * width] if v) for y in range(height)]
    cols = [sum(1 for y in range(height) if marks[y * width + x]) for x in range(width)]
    row_floor = max(2, int(width * 0.004))
    col_floor = max(2, int(height * 0.004))
    used_rows = [y for y, n in enumerate(rows) if n >= row_floor]
    used_cols = [x for x, n in enumerate(cols) if n >= col_floor]
    if not used_rows or not used_cols:
        return image
    return image.crop((max(0, used_cols[0] - pad), max(0, used_rows[0] - pad),
                       min(width, used_cols[-1] + 1 + pad), min(height, used_rows[-1] + 1 + pad)))


def build(source: Path, out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    modes: dict[str, float] = {}
    for path in sorted(source.iterdir()):
        name = path.stem.lower()
        if name not in HEIGHT_SHARE or path.suffix.lower() not in SUFFIXES:
            continue
        figure = clear_badge(Image.open(path).convert("L"))
        figure = figure.point(lambda v: 0 if v < INK else 255).convert("L")   # plain black on white
        figure = trim(figure)
        scale = EXPORT_BOX / max(figure.width, figure.height)
        if scale < 1:
            figure = figure.resize((round(figure.width * scale), round(figure.height * scale)),
                                   Image.LANCZOS).point(lambda v: 0 if v < INK else 255).convert("L")
        figure.save(out / f"{name}.png", optimize=True)
        modes[name] = HEIGHT_SHARE[name]
        print(f"{name:20} {figure.width:4}x{figure.height:4}  height share {modes[name]:.2f}")

    if not modes:
        raise SystemExit("no drawings found: name each one after its posture, e.g. ruku.png")
    missing = sorted(set(HEIGHT_SHARE) - set(modes))
    if missing:
        where = "THE APP NEEDS THESE" if out == OUT else "the default set is shown for those"
        print(f"missing: {', '.join(missing)} ({where})")
    (out / "modes.json").write_text(json.dumps(modes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else OUT)
