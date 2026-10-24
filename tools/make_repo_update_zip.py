#!/usr/bin/env python3
"""Builds the zip that brings a clone of the repository up to this tree.

    python3 tools/make_repo_update_zip.py ~/clones/Mysalaah ~/mysalaah-repo-update-1.93.zip

Unlike tools/make_changes_zip.py, which builds something to lay over a MAT, this builds
something to lay over a CLONE: it carries tests/ and tools/ as well, because those live in the
repository and never ship to a mat, and it is what turns "the work is done in the container"
into "the work is in the repository".

HOW IT DECIDES WHAT TO SEND. By comparing this tree against a clone of the branch, file by file
and by sha256. Not from a note of what was edited: 1.51 shipped half of a rename because the
list came from memory, and 1.89 reverted the whole app because a folder that looked like a
clone was not the clone.

WHAT IT CANNOT DO, and this is the part that bites. A zip ADDS and REPLACES. It cannot delete.
A file taken out of this tree stays in the clone, gets committed again, and comes back -- which
for salaah/second_row_games.py would mean an import of six screens that no longer exist. So the
deletions are written into the zip as DELETED.txt and printed here, and they have to be acted
on with git rm. There is no way to make a zip do it, so the only defence is saying so loudly.

THE LOCKS, checked rather than trusted:
  *.personal.json   licensed translations, private use only. Never in the public repository.
  .git              the clone's own history is not ours to overwrite.
  __pycache__, *.pyc
                    compiled bytecode, and worse than useless: Python will prefer a stale .pyc
                    whose recorded source size and mtime-to-the-second match, neither of which
                    is a hash, and it has cost this project an afternoon of chasing a fault in
                    a file that was already correct.
  .salaah, signing-key
                    the private signing key lives in the home directory and goes nowhere near
                    a zip, a repository or anybody else.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

SKIP_PARTS = {"__pycache__", ".git", ".salaah", "node_modules", ".pytest_cache"}
NEVER = ("personal.json", "signing-key")


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk(root: pathlib.Path) -> dict[str, str]:
    out = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if set(rel.parts) & SKIP_PARTS or path.suffix == ".pyc":
            continue
        if any(n in path.name for n in NEVER):
            continue
        out[rel.as_posix()] = digest(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="make_repo_update_zip", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clone", type=pathlib.Path, help="a clone of the branch being updated")
    ap.add_argument("out", type=pathlib.Path, help="the zip to write")
    args = ap.parse_args()

    if not (args.clone / "salaah" / "__init__.py").is_file():
        print(f"{args.clone} does not look like a clone of this repository.", file=sys.stderr)
        return 2

    theirs, ours = walk(args.clone), walk(ROOT)
    added = sorted(set(ours) - set(theirs))
    changed = sorted(f for f in set(ours) & set(theirs) if ours[f] != theirs[f])
    removed = sorted(set(theirs) - set(ours))
    send = added + changed

    if not send and not removed:
        print("The clone already matches this tree. Nothing written.")
        return 1

    for name in send:                                  # the locks, checked not trusted
        assert not any(n in name for n in NEVER), name
        assert not set(pathlib.PurePosixPath(name).parts) & SKIP_PARTS, name

    note = ("These files were REMOVED from the tree and a zip cannot remove them.\n"
            "Delete them in the clone, with git, before committing:\n\n"
            + "".join(f"    git rm {name}\n" for name in removed)
            + "\nLeaving any of them behind re-commits a file the app no longer has, and for\n"
              "a deleted module that means importing something that is not there.\n")

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name in send:
            zipped.write(ROOT / name, name)
        if removed:
            zipped.writestr("DELETED.txt", note)

    with zipfile.ZipFile(args.out) as zipped:           # read back, do not assume
        inside = [n for n in zipped.namelist() if n != "DELETED.txt"]
        assert sorted(inside) == sorted(send), "the zip is not what was asked for"
        for name in inside:
            assert hashlib.sha256(zipped.read(name)).hexdigest() == ours[name], name

    print(f"  {args.out.name}: {len(send)} files, {args.out.stat().st_size / 1e6:.1f} MB")
    print(f"      {len(added)} added, {len(changed)} changed")
    print("      every file read back out of the zip and matched against the tree")
    kinds: dict[str, int] = {}
    for name in send:
        top = name.split("/")[0]
        kinds[top] = kinds.get(top, 0) + 1
    print(f"      by folder: {dict(sorted(kinds.items(), key=lambda kv: -kv[1]))}")
    if removed:
        print(f"\n  {len(removed)} FILES MUST BE DELETED BY HAND -- a zip cannot do it:")
        for name in removed:
            print(f"      git rm {name}")
        print("  (the same list is in DELETED.txt inside the zip)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
