#!/usr/bin/env python3
"""Writes the manifest tools/sign_release.py refuses to sign without.

    python3 tools/write_release_manifest.py

Reads the version out of salaah/__init__.py, lists every file a release of it would carry with
its sha256, and writes tools/release-manifest-<version>.txt.

WHY THIS EXISTS. release-manifest-1.92.txt was written by hand, on a machine that no longer
exists, by a method nobody wrote down -- which is the same fault as the font subsets and the
same fault that lost make_changes_zip.py when a container was reclaimed. A release step that
only one person can perform, once, is not a release step.

WHAT A MANIFEST CAN AND CANNOT DO, because it is easy to believe it does more than it does.

It is a SNAPSHOT, not a derivation. It says "the tree looked like this when somebody looked at
it", and sign_release.py then refuses anything that has drifted since. That catches a file
edited, replaced or reverted between the checking and the signing -- which is exactly what went
wrong before 1.91, where a hadith file stale by one release survived a diff and went out with
86 of 109 in it.

It cannot catch a tree that was already wrong when the manifest was written. Writing the
manifest from a damaged tree simply records the damage, and signing then passes. So a manifest
written at the wrong moment is worse than none: it looks like a check and is a photograph.

WHICH IS WHY THIS REFUSES TO WRITE ONE UNTIL THE REAL CHECKS PASS. tools/check_quran.py proves
the scripture is the shape scripture is; tools/subset_fonts.py --check-only proves every
character the mat can draw has a glyph in the face that will draw it. Both are read from the
files rather than from a list, both are independent of this tool, and neither will pass on a
tree that has lost something. Run the test suites too -- this cannot make you do that, and it
says so rather than pretending the manifest covers it.
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from sign_release import PACKS, why_not   # noqa: E402  -- the same rule about what ships

# Run from the files, not from a written list, and refusing on anything missing. If either of
# these cannot pass, a manifest taken now would be a photograph of a fault.
GATES = (
    ("tools/check_quran.py", []),
    ("tools/subset_fonts.py", ["--check-only"]),
)


def version() -> str:
    for line in (ROOT / "salaah" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("could not find __version__ in salaah/__init__.py")


def shipping() -> dict[str, str]:
    out = {}
    for pack in PACKS:
        for path in sorted((ROOT / pack).rglob("*")):
            if path.is_file() and not why_not(path):
                out[str(path.relative_to(ROOT)).replace("\\", "/")] = \
                    hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def gates_pass() -> bool:
    ok = True
    for script, extra in GATES:
        run = subprocess.run([sys.executable, "-I", str(ROOT / script), *extra],
                             capture_output=True, text=True, cwd=ROOT)
        head = (run.stdout.strip().splitlines() or ["(no output)"])[0]
        print(f"  {'passed' if run.returncode == 0 else 'FAILED'}  {script} {' '.join(extra)}")
        print(f"          {head[:96]}")
        if run.returncode != 0:
            ok = False
            for line in (run.stderr or run.stdout).strip().splitlines()[:6]:
                print(f"          {line[:96]}")
    return ok


def main() -> int:
    number = version()
    where = ROOT / "tools" / f"release-manifest-{number}.txt"
    print(f"  version {number}")
    if not gates_pass():
        print("\nA check failed, so this tree is not one to photograph. Nothing written.",
              file=sys.stderr)
        return 1

    files = shipping()
    lines = [
        f"# Every file release {number} carries, by sha256. tools/sign_release.py refuses to "
        f"sign a",
        "# tree that does not match this, and that refusal is the whole point: 1.91 shipped 86",
        "# hadith instead of 109 because a stale asset survived a diff, and both a file count",
        "# and six hashes had been written down and neither was run.",
        f"# Written by tools/write_release_manifest.py, which refused until check_quran.py and",
        "# subset_fonts.py --check-only both passed on this tree.",
    ]
    lines += [f"{digest}  {name}" for name, digest in sorted(files.items())]
    where.write_text("\n".join(lines) + "\n", encoding="utf-8")

    older = sorted(p for p in (ROOT / "tools").glob("release-manifest-*.txt") if p != where)
    print(f"\n  {where.relative_to(ROOT)}: {len(files)} files")
    if older:
        was = {}
        for line in older[-1].read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                digest, name = line.split(None, 1)
                was[name.strip()] = digest
        added = sorted(set(files) - set(was))
        gone = sorted(set(was) - set(files))
        changed = sorted(f for f in set(files) & set(was) if files[f] != was[f])
        print(f"  against {older[-1].name}: {len(added)} added, {len(gone)} removed, "
              f"{len(changed)} changed")
        for label, group in (("added", added), ("removed", gone), ("changed", changed)):
            for name in group[:6]:
                print(f"      {label:8} {name}")
            if len(group) > 6:
                print(f"      {label:8} ... and {len(group) - 6} more")
    print("\n  The suites are not covered by any of this. Run them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
