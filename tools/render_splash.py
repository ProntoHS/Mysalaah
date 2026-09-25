#!/usr/bin/env python3
"""Renders the opening logo animation to a video, to look at before it goes in the app.

    python3 tools/render_splash.py out.mp4 [--size 1920x1080] [--fps 30] [--no-handoff]

The frames are drawn by the same code the app uses (salaah/splash.py), so what you see is what
the screen will show. Unless --no-handoff is given, the video ends by fading into the mosque main
screen, as the app would.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from salaah.qt import QtCore, QtGui, QtWidgets  # noqa: E402
from salaah.splash import Splash  # noqa: E402

HOLD = 0.5        # the finished logo, held before the handoff
HANDOFF = 0.8     # the fade into the main screen, through white
AFTER = 1.0       # the main screen, held at the end


def main_screen(size: QtCore.QSize) -> QtGui.QImage:
    from salaah import content as C
    from salaah.settings import Settings
    from salaah.ui import MainWindow
    assets = ROOT / "assets"
    w = MainWindow(C.load(assets), C.available_packs(assets), Settings(), save_settings=False,
                   scale=size.height() / 1080)
    w.resize(size)
    w.show()
    QtWidgets.QApplication.processEvents()
    w.tick()
    QtWidgets.QApplication.processEvents()
    image = w.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGB888)
    w.hide()
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--size", default="1920x1080")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-handoff", action="store_true")
    args = parser.parse_args()
    width, height = (int(v) for v in args.size.lower().split("x"))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    splash = Splash(ROOT / "assets")
    size = QtCore.QSize(width, height)
    home = None if args.no_handoff else main_screen(size)

    total = splash.DURATION + HOLD + (0 if home is None else HANDOFF + AFTER)
    count = int(round(total * args.fps))
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{width}x{height}", "-r", str(args.fps), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", args.out],
        stdin=subprocess.PIPE)

    frame = QtGui.QImage(size, QtGui.QImage.Format.Format_RGB888)
    rect = QtCore.QRectF(0, 0, width, height)
    handoff_start = splash.DURATION + HOLD
    for n in range(count):
        t = n / args.fps
        p = QtGui.QPainter(frame)
        splash.paint(p, rect, min(t, splash.DURATION))
        if home is not None and t > handoff_start:
            # through white rather than straight across, so the two pictures never muddle
            k = (t - handoff_start) / HANDOFF
            p.setOpacity(min(1.0, k * 2))
            p.fillRect(rect, QtGui.QColor("white"))
            if k > 0.5:
                p.setOpacity(min(1.0, (k - 0.5) * 2))
                p.drawImage(0, 0, home)
        p.end()
        ffmpeg.stdin.write(bytes(frame.constBits())[: width * height * 3]
                           if frame.bytesPerLine() == width * 3 else _packed(frame))
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(f"wrote {args.out}: {count} frames, {total:.1f}s")
    del app


def _packed(frame: QtGui.QImage) -> bytes:
    """Rows without the padding Qt adds to keep each one aligned."""
    w, h, stride = frame.width(), frame.height(), frame.bytesPerLine()
    raw = bytes(frame.constBits())
    return b"".join(raw[y * stride: y * stride + w * 3] for y in range(h))


if __name__ == "__main__":
    main()
