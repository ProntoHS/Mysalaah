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


if __name__ == "__main__":
    try:
        from .main import main
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as why:          # BaseException: a KeyboardInterrupt is worth knowing
        write_it_down(why)
        traceback.print_exc()
        sys.exit(1)
