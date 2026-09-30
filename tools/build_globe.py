#!/usr/bin/env python3
"""Prepares the turning globe, and works out where things are on it.

    python3 tools/build_globe.py path/to/globe.gif

Needs Pillow, NumPy and SciPy:  pip3 install --break-system-packages pillow numpy scipy

The world screen draws the mat's own place on this globe and a line from there to the Kaaba.
For that to land anywhere near right, the app has to know the globe's geometry exactly: where
its centre is, how big it is, which way it is tilted, and which longitude is facing us on each
frame of the animation. None of that is written down anywhere, so it is measured here, out of
the animation itself, and written beside the film as globe.json.

Two measurements, taken independently of each other.

The circle is found by walking in from outside the picture at one hundred and eighty angles
until the outline is hit, and fitting a circle to where it was. On the drawing this was built
from that lands within four tenths of a pixel.

The rest comes from the Kaaba, which the animator drew onto the globe and which therefore turns
with it. It is tracked across every frame it appears in -- twenty-one of them -- and then the
five unknowns (the tilt, the longitude facing us at the start, how far it turns per frame, and
where the pin sits relative to the point it marks) are fitted to those twenty-one positions.
Mecca is at a known latitude and longitude, so this is an ordinary least-squares problem with
forty-two numbers going in and five coming out. The residual is about a pixel, and the pin comes
out sitting sixteen pixels above the place it marks, which is exactly what a map pin does. That
is the check that the answer means something rather than merely fitting.

It is worth saying what this buys: the arc the app draws ends on the pin the animator drew,
because both are placed by the same numbers. A calibration taken from the coastlines instead
would be a few degrees out and the line would miss.

As a second opinion the tool can compare the frames against real coastlines
(pip3 install global-land-mask; --check). That agreement peaks within two degrees of the fit in
both the tilt and the longitude, which is as close as a stylised drawing of the world gets.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence
from scipy.optimize import least_squares
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "world"

WIDE = 600           # what the globe ships at; it is drawn no larger than this on any screen
INK = 128
PIN_RADIUS = 34      # the disc inside the Kaaba marker, away from its edge

MECCA = (21.4225, 39.8262)


def frames(source: Path) -> list[np.ndarray]:
    film = Image.open(source)
    shots = [np.asarray(f.convert("L")) for f in ImageSequence.Iterator(film)]
    film.close()
    return shots


def fit_circle(shot: np.ndarray) -> tuple[float, float, float]:
    """The globe's outline, found by walking in from outside it."""
    dark = shot < INK
    h, w = dark.shape
    cx, cy = w / 2, h / 2
    found = []
    for deg in range(0, 360, 2):
        th = np.radians(deg)
        for rr in np.arange(max(w, h) * 0.55, w * 0.3, -0.5):
            x, y = int(round(cx + rr * np.cos(th))), int(round(cy + rr * np.sin(th)))
            if 0 <= x < w and 0 <= y < h and dark[y, x]:
                found.append((x, y))
                break
    pts = np.array(found, float)
    if len(pts) < 60:
        raise SystemExit("could not find the globe's outline")

    def residual(p):
        return np.hypot(pts[:, 0] - p[0], pts[:, 1] - p[1]) - p[2]

    answer = least_squares(residual, [cx, cy, w * 0.4])
    rms = float(np.sqrt((residual(answer.x) ** 2).mean()))
    print(f"outline: centre ({answer.x[0]:.2f}, {answer.x[1]:.2f})  radius {answer.x[2]:.2f}"
          f"   (rms {rms:.2f}px)")
    if rms > 2:
        raise SystemExit("the outline is not a circle; this tool assumes an orthographic globe")
    return tuple(answer.x)


def track_pin(shots: list[np.ndarray], seed: tuple[int, int], floor: float = 0.5):
    """Where the Kaaba marker is on each frame, until it turns out of sight.

    Matched as black-and-white agreement over the disc inside the marker: the marker is drawn at
    the same size on every frame, so the pattern is identical and only what shows around its
    edge changes.
    """
    binary = [(s > INK).astype(float) for s in shots]
    sx, sy, r = seed[0], seed[1], PIN_RADIUS
    template = binary[0][sy - r:sy + r + 1, sx - r:sx + r + 1]
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    mask = ((xx * xx + yy * yy) <= r * r).astype(float)
    weights = (2 * template - 1) * mask
    total = mask.sum()

    seen = []
    for f, shot in enumerate(binary):
        score = fftconvolve(2 * shot - 1, weights[::-1, ::-1], mode="same")
        at = np.unravel_index(int(np.argmax(score)), score.shape)
        agreement = float(score[at] / total)
        if agreement < floor:
            break            # it has gone round the far side; everything after is a false match
        seen.append((f, float(at[1]), float(at[0]), agreement))
    return seen


def fit_turning(seen, cx: float, cy: float, radius: float) -> dict:
    """Tilt, starting longitude, degrees per frame, and where the pin sits on its point."""
    obs = np.array([[f, x, y] for f, x, y, _ in seen], float)
    phi = np.radians(MECCA[0])
    lam = np.radians(MECCA[1])

    def where(p):
        tilt, start, dx, dy, per = p
        gap = lam - (start + per * obs[:, 0])
        x = cx + radius * np.cos(phi) * np.sin(gap) + dx
        y = cy - radius * (np.cos(tilt) * np.sin(phi)
                           - np.sin(tilt) * np.cos(phi) * np.cos(gap)) + dy
        return x, y

    def residual(p):
        x, y = where(p)
        return np.concatenate([x - obs[:, 1], y - obs[:, 2]])

    answer = least_squares(residual, [0.0, 0.0, 0.0, -radius * 0.04, np.radians(5.0)])
    tilt, start, dx, dy, per = answer.x
    res = residual(answer.x)
    rms, worst = float(np.sqrt((res ** 2).mean())), float(np.abs(res).max())
    print(f"turning: tilt {np.degrees(tilt):+.3f}deg   longitude facing us at frame 0 "
          f"{np.degrees(start):+.3f}deg   {np.degrees(per):.4f}deg per frame "
          f"({np.degrees(per) * len(obs) and np.degrees(per) * 72:.1f}deg over 72)")
    print(f"         the pin is drawn ({dx:+.1f}, {dy:+.1f})px from the place it marks")
    print(f"         fitted to {len(obs)} frames; rms {rms:.2f}px, worst {worst:.2f}px")
    if rms > 3:
        raise SystemExit("the marker does not move like a point on a turning sphere")
    if abs(dx) > radius * 0.03:
        raise SystemExit("the marker is not above the place it marks; check --pin")
    return {"tilt": float(np.degrees(tilt)), "start": float(np.degrees(start)),
            "per_frame": float(np.degrees(per)), "rms": rms, "frames_fitted": len(obs)}


def compare_with_the_world(shots, cx, cy, radius, turning, at=(0, 18, 36, 54)) -> None:
    """A second opinion, from real coastlines rather than from the pin."""
    try:
        from global_land_mask import globe
    except ImportError:
        print("(--check needs global-land-mask; skipped)")
        return
    n = shots[0].shape[0]
    yy, xx = np.mgrid[0:n, 0:n]
    X, Y = (xx - cx) / radius, -(yy - cy) / radius
    rho = np.hypot(X, Y)
    inside = rho <= 1
    c = np.arcsin(np.clip(rho, 0, 1))
    safe = np.where(rho == 0, 1, rho)

    def agreement(frame, tilt_offset=0.0, lon_offset=0.0):
        tilt = np.radians(turning["tilt"] + tilt_offset)
        lon0 = np.radians(turning["start"] + lon_offset + turning["per_frame"] * frame)
        with np.errstate(invalid="ignore", divide="ignore"):
            lat = np.arcsin(np.cos(c) * np.sin(tilt) + Y * np.sin(c) * np.cos(tilt) / safe)
            lon = lon0 + np.arctan2(X * np.sin(c),
                                    rho * np.cos(c) * np.cos(tilt) - Y * np.sin(c) * np.sin(tilt))
        lon = (np.degrees(lon) + 180) % 360 - 180
        mine = np.zeros((n, n), bool)
        mine[inside] = globe.is_land(np.degrees(lat)[inside], lon[inside])
        theirs = (shots[frame] < INK) & inside
        return 1 - ((mine != theirs) & inside).sum() / inside.sum()

    for name, offsets in (("longitude", range(-8, 9, 2)), ("tilt", range(-8, 9, 2))):
        scores = [(o, np.mean([agreement(f, **{f"{name[:3]}_offset" if False else
                                               ("lon_offset" if name == "longitude"
                                                else "tilt_offset"): o})
                               for f in at])) for o in offsets]
        best = max(scores, key=lambda s: s[1])
        print(f"coastlines: best {name} is {best[0]:+d}deg from the fit "
              f"({best[1] * 100:.1f}% of the disc agrees)")
        if abs(best[0]) > 4:
            print(f"   WARNING: that is a long way off; the fit may be wrong")


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_globe")
    ap.add_argument("source", type=Path, help="the turning globe, as supplied")
    ap.add_argument("--pin", default="768,396",
                    help="where the Kaaba marker is on the first frame, in the source's pixels")
    ap.add_argument("--check", action="store_true", help="second opinion from real coastlines")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    shots = frames(args.source)
    if len(shots) < 8:
        raise SystemExit(f"{args.source} has {len(shots)} frames; that is not an animation")
    print(f"{args.source.name}: {len(shots)} frames, {shots[0].shape[1]}x{shots[0].shape[0]}")

    cx, cy, radius = fit_circle(shots[0])
    seed = tuple(int(v) for v in args.pin.split(","))
    seen = track_pin(shots, seed)
    print(f"the Kaaba is in view on frames {seen[0][0]}..{seen[-1][0]}")
    turning = fit_turning(seen, cx, cy, radius)
    if args.check:
        compare_with_the_world(shots, cx, cy, radius, turning)

    args.out.mkdir(parents=True, exist_ok=True)
    small = [Image.fromarray(s).resize((WIDE, WIDE), Image.LANCZOS)
              .point(lambda v: 0 if v < INK else 255)
              .convert("P", palette=Image.Palette.ADAPTIVE, colors=2) for s in shots]
    film = args.out / "globe.gif"
    small[0].save(film, save_all=True, append_images=small[1:],
                  duration=Image.open(args.source).info.get("duration", 100), loop=0,
                  optimize=True)

    # Written as fractions of the picture, so the app can scale the globe to whatever room it
    # has and the numbers still hold.
    n = shots[0].shape[1]
    (args.out / "globe.json").write_text(json.dumps({
        "about": ("Where things are on the turning globe. Measured by tools/build_globe.py from "
                  "the animation itself: the outline gives the circle, and the Kaaba marker "
                  "drawn onto it gives the tilt and the turning. Fractions of the picture."),
        "centre": [round(cx / n, 6), round(cy / n, 6)],
        "radius": round(radius / n, 6),
        "tilt": round(turning["tilt"], 4),
        "start": round(turning["start"], 4),
        "per_frame": round(turning["per_frame"], 5),
        "frames": len(shots),
        "fit_rms_px": round(turning["rms"], 3),
        "fitted_over_frames": turning["frames_fitted"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\n-> {film.relative_to(ROOT)}  ({film.stat().st_size / 1024:.0f} KB, {WIDE}x{WIDE})")
    print(f"-> {(args.out / 'globe.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
