"""Starts the app, and makes sure that if it will not start, it says why somewhere findable.

The second part is the whole point of this file. A version that crashes on the mat is put back
by the guard in run.sh, which then deletes the broken copy -- so by the time anybody looks, the
code that failed and the traceback it printed are both gone, and all that is left is a mat
sitting on the old version with no explanation. That happened with 1.51 and cost a day.

So anything that escapes is written to startup-error.log next to run.sh BEFORE it is allowed to
take the process down. That file sits outside salaah/ and assets/, which are the only two
folders an update or a rollback touches, so it survives both. The traceback still goes to stderr
as well, and the exit code is still non-zero, so the guard behaves exactly as it did.

The import of main() is INSIDE the net rather than at the top of the file, which is not a style
choice. The likeliest way a release fails to start is a module that will not import -- a typo, a
name that moved, a package missing from the Pi -- and that happens while this file's own imports
are still running. The first version of this had the import at the top and the net below it, and
the test for it caught the hole straight away: a deliberately broken module gave exit code 1 and
an empty log, which is precisely the failure this is supposed to end.
"""
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = "startup-error.log"
KEEP = 64_000           # trim the log rather than let it grow for ever on a mat that loops


def which_version() -> str:
    """The version, if the package is well enough to say. It may not be: this runs when
    something has already gone wrong, and salaah/__init__.py is as able to be broken as
    anything else in the folder."""
    try:
        from . import __version__
        return __version__
    except Exception:
        return "unknown"


def write_it_down(why: BaseException) -> None:
    """Put the traceback where a rollback cannot delete it. Never raises."""
    try:
        from datetime import datetime
        said = (f"\n{'=' * 70}\n{datetime.now():%Y-%m-%d %H:%M:%S}  version {which_version()}  "
                f"{sys.executable}\n"
                + "".join(traceback.format_exception(type(why), why, why.__traceback__)))
        path = ROOT / LOG
        old = ""
        try:
            old = path.read_text(encoding="utf-8")[-KEEP:]
        except OSError:
            pass
        path.write_text(old + said, encoding="utf-8")
        print(f"salaah: this is written down in {path}", file=sys.stderr)
    except Exception:
        pass        # a mat that cannot write its own log still has to show the real error


def fall_over(kind, why, tb) -> None:
    """An exception that escaped while the app was RUNNING, from inside a Qt slot.

    The net at the bottom of this file only catches what escapes main(), and nothing escapes
    main() once the event loop is going: an exception raised in a slot is handed to
    sys.excepthook and the loop carries on. What happens then depends on the toolkit, and the
    two do not agree -- PyQt6 prints it and aborts the process, PySide6 prints it and keeps
    going with whatever half-finished state the slot left behind. Measured, not assumed: the
    same deliberate error gives exit 134 under one and exit 0 under the other.

    Since 1.64 run.sh starts the app again after a crash, so dying is the better of the two:
    the mat comes back in a known state within a couple of seconds. This makes both toolkits
    do that, and writes the traceback to the log that survives a rollback on the way out --
    which is the only record there will be, since the screen is about to be replaced by a
    fresh copy of the app.

    os._exit, not sys.exit: raising SystemExit inside an exception hook does not leave, it is
    reported as another unhandled exception. The screens are handed back first, because _exit
    runs no cleanup and a mat that crashed while asleep would otherwise stay dark -- belt and
    braces with the switch-on at startup in ui.py, since either alone would do it.
    """
    write_it_down(why)
    traceback.print_exception(kind, why, tb)
    try:
        from .power import Outputs
        Outputs().set(True)
    except Exception:
        pass
    import os
    sys.stderr.flush()
    os._exit(1)


#: Held open for as long as the app runs. A module global because the lock belongs to the open
#: file, and letting this be collected would hand the lock to the next copy that asked.
THE_ONLY_ONE = None


def take_the_mat() -> bool:
    """True if this is the only copy running. False if another one already has the mat.

    TWO COPIES OF THIS APP RUN PERFECTLY HAPPILY SIDE BY SIDE and nothing in either of them
    knows. They do not share a window, so you see one. They do not share a clock, so each calls
    the azaan on its own. They do not share a stop button, so stopping one leaves the other
    sounding. Harry: "when azaan plays, it plays twice ... i press stop and there is another
    azaan playing i press stop again". The gap between the two is only however far apart their
    fifteen-second clocks happen to sit -- two seconds one day, a minute the next, which is why
    it never looked like a pattern.

    There are several doors in. ~/.config/autostart starts it at login, the menu entry in
    ~/.local/share/applications starts it again, and on Harry's mat those two files do not even
    agree with each other -- the autostart one carries --main-output/--side-output and the menu
    one does not, so a copy started from the menu would not know which screen is which.

    THIS LIVES IN THE APP AND NOT IN run.sh, which is where it was written first. Asked what it
    was running, Harry's mat said `/usr/bin/python3 -m salaah` with no run.sh anywhere in it:
    he starts it by hand, which is the ordinary thing to do while working on it, and a guard in
    run.sh is a guard that way of starting walks straight past. Here it holds however the app
    was started, and it travels inside a release, which run.sh does not.

    Never raises. A mat that cannot take a lock -- no /tmp to write in, no flock on the
    platform -- runs anyway. The worst that costs is the fault this is here to prevent; the
    worst raising would cost is a mat that will not start at all.
    """
    global THE_ONLY_ONE
    import os
    if os.environ.get("SALAAH_ALLOW_TWO"):
        return True
    try:
        import fcntl
        import tempfile
        where = Path(tempfile.gettempdir()) / f"salaah-{os.getuid()}.lock"
        handle = open(where, "r+" if where.exists() else "w+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # HELD -- but possibly by US. flock belongs to the open file, not to the process,
            # so a process that opens the same file a second time is refused by its own lock.
            # Measured, not assumed: a second flock on a second descriptor in one process gives
            # EAGAIN. That matters because the app's entry point can be run more than once in
            # one process -- the suite does exactly that, with run_module, which builds a fresh
            # copy of this module each time and so cannot be told by a module-level flag.
            #
            # So the holder writes down which process it is, and its own pid is let through.
            # The question being asked is "is another MAT running", and a mat is a process.
            handle.close()
            try:
                held_by = int(where.read_text(encoding="utf-8").strip() or 0)
            except (OSError, ValueError):
                held_by = 0
            THE_ONLY_ONE = None
            return held_by == os.getpid()
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        THE_ONLY_ONE = handle        # held open: the lock goes when this does
        return True
    except Exception:
        THE_ONLY_ONE = None
        return True         # could not ask; let the mat run


if __name__ == "__main__":
    try:
        sys.excepthook = fall_over
        if not take_the_mat():
            # EXIT 0, because a second copy is not a fault -- somebody started the app on a mat
            # that was already running. A non-zero exit would put a line in crash-log.txt and
            # set run.sh's restart guard going after something that never went wrong.
            print("salaah: already running; leaving the one that is up alone.", file=sys.stderr)
            sys.exit(0)
        from .main import main
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as why:          # BaseException: a KeyboardInterrupt is worth knowing
        write_it_down(why)
        traceback.print_exc()
        sys.exit(1)
