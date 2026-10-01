#!/usr/bin/env python3
"""Starts the app from a release plus a set of changes zips, the way a mat would.

    python3 tools/check_changes_zip.py --base ~/Downloads/salaah-1.49.zip \
        --changes ~/Downloads/salaah-1.5*-changes.zip

This exists because of a fortnight that should not have happened. Versions 1.50, 1.51 and 1.52
were each tested until the whole suite passed on two toolkits -- and 1.51 renamed a keyword
argument in salaah/duaboard.py and in salaah/ui.py, shipped duaboard.py in the changes zip and
did not ship ui.py. The tests passed because they ran against a folder where both files had been
changed. The mat got one of the two, and died on startup with

    TypeError: DuaBoard.__init__() got an unexpected keyword argument 'mark_by_meaning'

every time it was offered an update, for three releases running, while the guard quietly put the
old version back and deleted the evidence.

The lesson is narrow and worth writing down: a test suite proves that the WORKING TREE is
consistent. It says nothing whatever about whether the files picked out of that tree to be
shipped are the complete set. Those are different claims and only one of them was ever checked.

So this checks the other one. It lays down the release the mat is actually running, applies the
changes on top in order -- which is exactly what unpacking them over the project does -- and
starts the app. If a file was left out, the app fails here, on a laptop, in thirty seconds,
rather than on a mat in somebody's home with nothing on screen to say why.

Run it before sending a changes zip. Every time.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def version_in(tree: Path) -> str:
    try:
        line = next(x for x in (tree / "salaah" / "__init__.py").read_text().splitlines()
                    if "__version__" in x)
        return line.split('"')[1]
    except (OSError, StopIteration, IndexError):
        return "?"


def lay_it_down(base: Path, changes: list[Path], into: Path) -> None:
    with zipfile.ZipFile(base) as z:
        z.extractall(into)
    print(f"  base {base.name:<34} -> {version_in(into)}")
    for one in changes:
        with zipfile.ZipFile(one) as z:
            z.extractall(into)          # overwrites, the way Expand-Archive -Force does
        print(f"  plus {one.name:<34} -> {version_in(into)}")


def start_it(tree: Path, seconds: float) -> tuple[int, str]:
    """Run the app as run.sh does, and give it a moment to fall over."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("SALAAH_QT", None)
    try:
        done = subprocess.run([sys.executable, "-m", "salaah", "--quit-after", str(seconds)],
                              cwd=tree, env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return 1, "it never came back"
    return done.returncode, done.stderr


def main() -> int:
    ap = argparse.ArgumentParser(prog="check_changes_zip")
    ap.add_argument("--base", type=Path, required=True,
                    help="the release zip the mat is running now")
    ap.add_argument("--changes", type=Path, nargs="+", required=True,
                    help="changes zips, in the order they would be unpacked")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--keep", action="store_true", help="leave the folder behind to poke at")
    args = ap.parse_args()

    tree = Path(tempfile.mkdtemp(prefix="salaah-check-"))
    try:
        lay_it_down(args.base, list(args.changes), tree)
        code, said = start_it(tree, args.seconds)
        want = version_in(tree)
        if code == 0 and f"Salaah {want} " in said:
            print(f"\nIt starts, and says it is {want}. The zips are complete.")
            return 0
        print("\n" + "=" * 70)
        print("IT DOES NOT START. A mat offered this would roll straight back.\n")
        # The last lines are the ones with the traceback in them.
        print("\n".join(said.strip().splitlines()[-25:]))
        print("=" * 70)
        if "unexpected keyword argument" in said or "ImportError" in said \
                or "ModuleNotFoundError" in said or "AttributeError" in said:
            print("\nThat shape of error usually means a file was changed and not shipped.")
        return 1
    finally:
        if args.keep:
            print(f"\nleft in {tree}")
        else:
            shutil.rmtree(tree, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
