"""Starts the prayer app full screen. Run: python3 -m salaah [--windowed] [--cursor]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .buttons import BluetoothButtons
from .power import PowerButton
from .content import available_packs, load
from .qibla import NoCompass, find_compass
from .qt import API, QtCore, QtWidgets
from .settings import Settings
from .ui import QIBLA, MainWindow

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def build_parser() -> argparse.ArgumentParser:
    """Every switch the app takes. Its own function so the switches can be checked without
    starting the app."""
    ap = argparse.ArgumentParser(prog="salaah")
    ap.add_argument("--windowed", action="store_true", help="run in a 1280x720 window instead of full screen")
    ap.add_argument("--cursor", action="store_true", help="show the mouse pointer for this run (Settings remembers it)")
    ap.add_argument("--no-buttons", action="store_true", help="don't read Bluetooth buttons directly")
    ap.add_argument("--no-sleep", action="store_true",
                    help="leave the power button to the desktop, which will shut the Pi down")
    ap.add_argument("--aspect", default="fill",
                    help="shape of the drawing area, e.g. 16:9 or 4:3; 'fill' (the default) uses "
                         "the whole screen")
    ap.add_argument("--side-screen", choices=("auto", "off", "window"), default="auto",
                    help="the 7-inch posture screen: 'auto' uses a second screen if one is "
                         "plugged in, 'off' ignores it, 'window' shows it in a 600x1024 window "
                         "to try it on one monitor")
    ap.add_argument("--inset", type=int, default=None,
                    help="pixels to keep clear on every edge, if the monitor cuts them off "
                         "(remembered; also in Settings)")
    ap.add_argument("--compass-stand-in", action="store_true",
                    help="try the Qibla screen without a compass chip: the arrow keys turn it")
    ap.add_argument("--tap-timings", action="store_true",
                    help="open the screen for tapping the word timings in with the ring, for "
                         "when the red runs ahead of or behind the voice. Not in Settings: it "
                         "is a job for building the mat, not for praying on it")
    ap.add_argument("--cover-screens", action="store_true",
                    help="don't ask the desktop to go full screen: cover each screen with a "
                         "borderless window instead. Use if a window lands on the wrong screen")
    ap.add_argument("--list-screens", action="store_true",
                    help="print the screens the Pi is reporting, and stop")
    ap.add_argument("--main-output", default="",
                    help="name of the screen the words go on, e.g. HDMI-A-1 (see --list-screens)")
    ap.add_argument("--side-output", default="",
                    help="name of the 7-inch posture screen, e.g. HDMI-A-2")
    ap.add_argument("--quit-after", type=float, default=0, help=argparse.SUPPRESS)  # smoke tests
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("Salaah")
    content = load(ASSETS)
    packs = available_packs(ASSETS)
    settings = Settings.load()
    if args.cursor and not settings.cursor:
        settings.cursor = True
        settings.save()  # so it stays on next time, including when it starts by itself

    aspect = None
    if args.aspect.lower() not in ("fill", "none", ""):
        try:
            w, h = (float(x) for x in args.aspect.replace("/", ":").split(":"))
            aspect = w / h
        except (ValueError, ZeroDivisionError):
            print(f"--aspect {args.aspect!r} not understood; using the whole screen", file=sys.stderr)

    if args.list_screens:
        return list_screens(app)
    main_name, side_name = remembered(app, settings, args.main_output, args.side_output)
    main_screen, side_screen = pick_screens(app, main_name, side_name)
    remember(settings, main_screen, side_screen)
    use_side = args.side_screen == "window" or (args.side_screen == "auto" and side_screen is not None)
    screen = main_screen.geometry()
    height = 720 if args.windowed else screen.height()
    if args.inset is not None:
        settings.inset = max(0, args.inset)
        settings.save()
    # The compass is switched off for now (ui.QIBLA), so the chip is not looked for.
    compass = find_compass(stand_in=args.compass_stand_in) if QIBLA else NoCompass()
    print(f"compass: {compass.name}", file=sys.stderr)
    win = MainWindow(content, packs, settings, scale=max(0.5, height / 1080),
                     aspect=aspect, inset=settings.inset, compass=compass, side=use_side)

    buttons = None
    if not args.no_buttons:
        buttons = BluetoothButtons(win.bridge.action.emit, win.bridge.devices.emit)
        buttons.start()
        if not buttons.available:
            print("python3-evdev not installed: Bluetooth buttons work only as normal key presses", file=sys.stderr)

    # The power button on J2. Its presses arrive here rather than at logind, so the mat sleeps
    # instead of shutting down. See the README about logind, which otherwise shuts it down first.
    power = None
    if not args.no_sleep:
        power = PowerButton(win.bridge.power.emit)
        if power.start():
            held = "grabbed" if power.grabbed else "shared with the desktop"
            print(f"power button: {power.path} ({held})", file=sys.stderr)
        else:
            print(f"power button: {power.why}", file=sys.stderr)
            power = None

    win.apply_cursor()
    if args.windowed:
        win.resize(1280, 720)
        win.show()
    else:
        fill_screen(app, win, main_screen, args.cover_screens)
    if win.side is not None:
        if args.side_screen == "window" or side_screen is None:
            win.side.resize(600, 1024)
            win.side.show()
        else:
            fill_screen(app, win.side, side_screen, args.cover_screens)
    # Some desktops (Wayland ones especially) put a window where they like and ignore the app.
    # Check a moment later that each window really is on its own screen, and say so if not.
    QtCore.QTimer.singleShot(1200, lambda: report_windows(win, main_screen, side_screen))
    win.begin()                     # the Qibla compass first, then the main screen
    if args.tap_timings:
        win.open_timing()
    if args.quit_after:
        QtCore.QTimer.singleShot(int(args.quit_after * 1000), app.quit)
    for tr in content.translations.values():
        if tr.personal:
            print(f"personal translation loaded: {tr.name} ({tr.lang}.personal.json). "
                  "Private use only; delete it before packaging a release.", file=sys.stderr)
    print(f"Salaah running with {API}", file=sys.stderr)
    code = app.exec()
    if buttons:
        buttons.stop()
    if power:
        power.stop()
    win.shutdown()
    win.deleteLater()
    app.processEvents()
    return code


SEVEN_INCH = (1024, 600)        # the posture panel's own pixels, whichever way round it is stood
SLACK = 1.15                    # room for a panel that reports itself a little differently


def describe(screen) -> str:
    g = screen.geometry()
    return f"{screen.name()} {g.width()}x{g.height()} at {g.x()},{g.y()}"


def area(screen) -> int:
    g = screen.geometry()
    return g.width() * g.height()


def looks_like_the_seven_inch(screen) -> bool:
    """Is this the 7" posture panel? Judged by its shape rather than its name or its socket, so
    it comes out right whichever cable went into which port, and whether the desktop has it
    upright (600x1024) or flat (1024x600)."""
    g = screen.geometry()
    long_edge, short_edge = max(g.width(), g.height()), min(g.width(), g.height())
    return long_edge <= SEVEN_INCH[0] * SLACK and short_edge <= SEVEN_INCH[1] * SLACK


def list_screens(app) -> int:
    """What the Pi is reporting. Run this first when a window lands on the wrong screen."""
    import os
    print(f"session: {os.environ.get('XDG_SESSION_TYPE', 'unknown')}, "
          f"Qt platform: {app.platformName()}")
    main_screen, side_screen = pick_screens(app)
    for screen in app.screens():
        if screen is main_screen:
            role = "  <- the words"
        elif screen is side_screen:
            role = "  <- the posture (7\")"
        else:
            role = "  <- not used"
        print(f"  {describe(screen)}{role}")
    print("The 7-inch panel is recognised by its shape, so the sockets can be either way round.")
    print("Pass a name to --main-output or --side-output to overrule it, e.g. --main-output HDMI-A-1")
    return 0


def by_name(app, name: str):
    """A screen by name, matched loosely: HDMI-A-1, hdmi-a-1 or just 1 all find the same one."""
    if not name:
        return None
    wanted = name.strip().lower()
    for screen in app.screens():
        if screen.name().lower() in (wanted, f"hdmi-a-{wanted}"):
            return screen
    print(f"no screen named {name!r}; run --list-screens to see the names", file=sys.stderr)
    return None


def pick_screens(app, main_name: str = "", side_name: str = ""):
    """The main screen and the 7" one.

    A name given for either wins. Otherwise the 7" is found by its shape, and the largest screen
    that is left over holds the words. Nothing depends on which HDMI socket a screen is in, or on
    the order the Pi happens to report them in, so the same two screens come out the same way
    round on every boot.
    """
    screens = sorted(app.screens(), key=area, reverse=True)
    if not screens:
        return app.primaryScreen(), None
    main = by_name(app, main_name)
    side = by_name(app, side_name)
    why = "named"
    if side is None:
        others = [s for s in screens if s is not main]
        if main is None:
            others = others[1:]                      # the largest is the words screen
        matches = [s for s in others if looks_like_the_seven_inch(s)]
        if matches:
            side, why = matches[-1], "by its shape"
        elif others:
            side, why = others[-1], "the smallest screen left over"
    if main is None:
        main = next((s for s in screens if s is not side), screens[0])
    if side is main:
        side = None
    print(f"main screen: {describe(main)}", file=sys.stderr)
    print(f"posture screen: {describe(side) + ' (' + why + ')' if side else 'none'}",
          file=sys.stderr)
    return main, side


def remembered(app, settings, main_name: str, side_name: str) -> tuple[str, str]:
    """Which screen names to use: one given on the command line this run, else the one last
    given, which is remembered in Settings.

    A remembered name is only used while it still makes sense. Screen names can come back in a
    different order after a reboot, and a stale name would then point at the wrong panel, so a
    remembered main screen that now looks like the 7" is dropped, as is a remembered 7" that is
    now the largest screen. Detection by shape takes over, and the new choice is remembered.
    """
    screens = sorted(app.screens(), key=area, reverse=True)
    main, side = main_name, side_name
    if not main and settings.main_output:
        kept = by_name(app, settings.main_output)
        if kept is not None and not looks_like_the_seven_inch(kept):
            main = settings.main_output
        else:
            print(f"forgetting the remembered main screen {settings.main_output!r}: it is not "
                  "there any more, or it is the small panel now", file=sys.stderr)
    if not side and settings.side_output:
        kept = by_name(app, settings.side_output)
        taken = by_name(app, main) if main else None
        if kept is not None and kept is not taken and (len(screens) < 2 or kept is not screens[0]):
            side = settings.side_output
        else:
            print(f"forgetting the remembered posture screen {settings.side_output!r}: it is not "
                  "there any more, or it is the words screen now", file=sys.stderr)
    return main, side


def remember(settings, main_screen, side_screen) -> None:
    """Writes the screens that were actually used into Settings, so the next run starts from the
    same place even if the Pi reports them in a different order."""
    main = main_screen.name() if main_screen is not None else ""
    side = side_screen.name() if side_screen is not None else ""
    if (main, side) != (settings.main_output, settings.side_output):
        settings.main_output, settings.side_output = main, side
        settings.save()


def report_windows(win, main_screen, side_screen) -> None:
    """Says which screen each window actually ended up on."""
    def where(widget):
        handle = widget.windowHandle()
        screen = handle.screen() if handle is not None else None
        return screen.name() if screen is not None else "?"

    wanted_main = main_screen.name() if main_screen else "?"
    print(f"words window on: {where(win)} (wanted {wanted_main}), "
          f"{win.width()}x{win.height()}", file=sys.stderr)
    if win.side is not None:
        wanted_side = side_screen.name() if side_screen else "a window"
        print(f"posture window on: {where(win.side)} (wanted {wanted_side}), "
              f"{win.side.width()}x{win.side.height()}", file=sys.stderr)
    if win.side is not None and side_screen is not None and where(win) == where(win.side):
        print("Both windows landed on the same screen. The desktop is ignoring where the app "
              "asks its windows to go; see 'Two screens' in the README.", file=sys.stderr)
    # A last resort, a moment after the desktop has settled: cover each screen by hand.
    for widget, screen in ((win, main_screen), (win.side, side_screen)):
        if widget is None or screen is None:
            continue
        handle = widget.windowHandle()
        if handle is not None and handle.screen() is not screen:
            cover(widget, screen)


def fill_screen(app, widget, screen, by_hand: bool = False) -> None:
    """Fills one particular screen with a window.

    Asking to go full screen leaves the choice of screen to the desktop, and some desktops
    choose the wrong one. So the window is first shown, small, at the corner of the screen it
    belongs to; the desktop then has only one screen to choose from when it is told to go full
    screen. If it still gets it wrong, [cover] takes the screen over without asking.
    """
    if screen is None:
        widget.show()
        return
    if by_hand:
        widget.show()
        cover(widget, screen)
        app.processEvents()
        return
    box = screen.geometry()
    widget.winId()                          # makes the native window, so it can be placed
    handle = widget.windowHandle()
    if handle is not None:
        handle.setScreen(screen)
    widget.setGeometry(box.x(), box.y(), min(640, box.width()), min(480, box.height()))
    widget.show()
    app.processEvents()
    # QWidget.move by name, since the main window has a move() of its own (the prayer steps).
    QtWidgets.QWidget.move(widget, box.x(), box.y())   # the desktop may have moved it on mapping
    app.processEvents()
    widget.showFullScreen()
    app.processEvents()
    if widget.windowHandle() is not None and widget.windowHandle().screen() is not screen:
        cover(widget, screen)
        app.processEvents()


def cover(widget, screen) -> None:
    """Takes a screen over the blunt way: a borderless window the size of the screen, put where
    the screen is. No full-screen request, so the desktop has no say in which screen it is."""
    from .qt import Qt
    box = screen.geometry()
    widget.setWindowState(Qt.WindowState.WindowNoState)
    widget.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    widget.showNormal()
    widget.setGeometry(box)
    QtWidgets.QWidget.move(widget, box.x(), box.y())
    widget.raise_()
    print(f"{widget.windowTitle()!r}: the desktop would not put it on {screen.name()}, "
          f"so it was covered by hand", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
