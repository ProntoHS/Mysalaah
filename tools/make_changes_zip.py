#!/usr/bin/env python3
"""Build a changes zip: every shipping file that differs from a published release.

    python3 tools/make_changes_zip.py ../salaah-1.88-tree salaah-1.89-changes.zip

The list is worked out by comparing against the release the mat is actually running --
unpacked from the zip off the repo, checked against the sha256 in latest.json -- rather than
from a note of what was edited. 1.51 shipped half of a rename because the list came from
memory.

WHY THIS LIVES IN THE REPO NOW. It did not until 1.89, when the machine this session runs on
was reclaimed and took the only copy with it. salaah/ and assets/ survived because they are
what a release carries, and tests/ and tools/ survived because they are in the repository.
This file was in neither. A tool that only exists on one machine is a tool that exists until
that machine is recycled.

What is deliberately NOT in a changes zip:
  *.personal.json   the licensed translations. Private use only, never in a release, never in
                    a public repo. tools/sign_release.py excludes them too; this is the second
                    lock on the same door.
  tools/            never ships to a mat. salaah/update.py REPLACES = ("salaah", "assets").
  run.sh            the guard that puts the old version back when an update will not start. An
                    update able to replace its own guard has nothing left to catch it.
  tests/, README, install.sh, salaah.desktop, .gitignore
                    not part of a release at all.

A changes zip ADDS and REPLACES; it never deletes. A file taken out of the tree stays on the
mat until somebody removes it by hand, which is why RELEASING.md keeps a list of those.

THE WHOLE OF salaah/ GOES EVERY TIME, changed or not. This cost 1.89.

A diff against a published release assumes the mat's folder matches that release. It did not.
1.89 was built as a diff against 1.88, where render.py and wudu.py are byte-identical to the
tree, so neither was sent -- correct arithmetic, wrong assumption. The mat had an older
render.py, the new ui.py reached wudu.py, wudu.py asked that render.py for ArrowButton, and
the mat died on import in under a second:

    ImportError: cannot import name 'ArrowButton' from 'salaah.render'

The guard rolled it back, which is the only reason this was an inconvenience rather than a
brick. But no diff can ever fix a file it has decided is already correct, so a mat that has
quietly drifted stays broken through every release that follows.

The Python is 924KB. Sending all of it costs about a fiftieth of the zip and removes the
assumption completely: whatever state the mat's salaah/ is in, afterwards it is this version's
code, entire and self-consistent. Assets stay a diff, because they are fifty megabytes and
because a missing picture shows a note on screen while a missing name kills the import.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import zipfile

TREE = pathlib.Path(__file__).resolve().parent.parent
NEVER = ("personal.json",)
SKIP_DIRS = {"tools", "tests", "__pycache__", ".git", "reference-translations", "daily"}


def digest(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def walk(root: pathlib.Path) -> dict[str, str]:
    out = {}
    for ship in ("salaah", "assets"):
        for p in (root / ship).rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            if set(rel.parts) & SKIP_DIRS or any(n in p.name for n in NEVER):
                continue
            out[str(rel)] = digest(p)
    return out


def main(base: pathlib.Path, out: pathlib.Path) -> int:
    if not (base / "salaah").is_dir():
        print(f"{base} does not look like an unpacked release (no salaah/)")
        return 2
    was, now = walk(base), walk(TREE)
    # Every Python file, whether it differs or not -- see the note at the top of this file.
    always = sorted(f for f in now if f.startswith("salaah/"))
    differs = sorted(set(now) - set(was)) + sorted(f for f in set(now) & set(was)
                                                  if now[f] != was[f])
    ship = sorted(set(always) | set(differs))
    same = len(always) - len([f for f in always if f in differs])
    print(f"  all {len(always)} files under salaah/ ({same} of them unchanged, sent anyway "
          f"so the code cannot be a mixture)")
    if not ship:
        print("nothing differs from that release; no zip written")
        return 1
    for name in ship:                      # the locks, checked rather than trusted
        assert not any(n in name for n in NEVER), name
        assert name.startswith(("salaah/", "assets/")), name
        assert "run.sh" not in name, name
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ship:
            z.write(TREE / name, name)
    with zipfile.ZipFile(out) as z:
        inside = z.namelist()
        assert sorted(inside) == sorted(ship), "the zip is not what was asked for"
        for name in inside:
            assert digest(TREE / name) == hashlib.sha256(z.read(name)).hexdigest(), name
    print(f"  {out.name}: {len(ship)} files, {out.stat().st_size:,} bytes")
    print("  every file re-read out of the zip and matched against the tree")
    kinds: dict[str, int] = {}
    for name in ship:
        where = name.split("/")[1] if name.startswith("assets/") else "salaah"
        kinds[where] = kinds.get(where, 0) + 1
    print(f"  by folder: {dict(sorted(kinds.items(), key=lambda kv: -kv[1]))}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])))
