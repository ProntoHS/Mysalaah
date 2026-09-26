#!/usr/bin/env python3
"""Checks a release the way a mat would, before any mat has to.

Run this on your own computer AFTER the zip is uploaded to its release and BEFORE latest.json
is published. That is the only moment when a mistake is still free.

    python tools/check_release.py                      the latest.json just built
    python tools/check_release.py --live               the one mats actually read
    python tools/check_release.py --manifest <path|url>

It does what the mat does, in the same order, with the same code: verifies the signature
against the built-in key, downloads the zip from the address written in the manifest, checks
its hash and its size, and looks inside it for anything that has no business being there.

Every failure this catches is one that would otherwise be found by a mat, in somebody's home,
with nothing on screen but a short apology.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from salaah.update import (                                            # noqa: E402
    DEFAULT_URL, PUBLIC_KEY, Refused, digest, fetch, read_manifest, safe_members,
)

# Must not be in a release, ever: licensed translations are private use only.
NEVER = ("*.personal.json",)

# What a 404 on the zip actually means, in the order worth checking. Every one of these has
# happened, and from the mat's end they look identical.
WHY_404 = """
  The manifest is fine; the file it names is not there. Usually one of:

    - the zip was put in the release's description box instead of the attachment area
      (the release page then shows Assets 2, not 3)
    - the tag is a different case from the one in the manifest -- v1.15 and V1.15 are
      two different tags as far as git and GitHub are concerned
    - the release was saved as a draft, which looks normal to you but is invisible to
      everyone else, your mat included
    - the upload had not finished when the release was published
"""


def look_inside(path: Path) -> list:
    """The checks the mat makes before it writes a single file, plus one it cannot make: that
    nothing licensed has escaped into a public release."""
    licensed = []
    with zipfile.ZipFile(path) as zipped:
        safe_members(zipped)                       # raises Refused on anything it dislikes
        for name in zipped.namelist():
            if any(Path(name).match(pattern) for pattern in NEVER):
                licensed.append(name)
        for wanted in ("salaah/", "assets/"):
            if not any(n.startswith(wanted) for n in zipped.namelist()):
                raise Refused(f"the zip has no {wanted} in it")
    return licensed


def check(manifest_at: str, key: str) -> int:
    if manifest_at.startswith(("http://", "https://")):
        print(f"manifest   {manifest_at}")
        raw = fetch(manifest_at)
    else:
        where = Path(manifest_at)
        if not where.is_file():
            print(f"No manifest at {where}.", file=sys.stderr)
            print("Run tools/sign_release.py first, or pass --manifest.", file=sys.stderr)
            return 1
        print(f"manifest   {where}")
        raw = where.read_bytes()

    release = read_manifest(raw, key)              # raises Refused if it is not properly signed
    print(f"signature  good -- signed by the holder of the key mats carry")
    print(f"version    {release.version}")
    print(f"url        {release.url}")

    hold = Path(tempfile.mkdtemp(prefix="salaah-check-"))
    try:
        zip_path = Path(fetch(release.url, into=hold / "release.zip"))
        got = zip_path.stat().st_size
        print(f"downloaded {got:,} bytes")

        if release.bytes and got != release.bytes:
            raise Refused(f"the file is {got:,} bytes; the manifest promises {release.bytes:,}")
        theirs = digest(zip_path)
        if theirs != release.sha256:
            raise Refused("the file does not match the manifest's hash.\n"
                          f"    manifest says  {release.sha256}\n"
                          f"    the file is    {theirs}\n"
                          "  A different build was uploaded, or the manifest was rebuilt after.")
        print(f"sha256     {theirs[:16]}... matches")

        licensed = look_inside(zip_path)
        print("contents   nothing the mat would refuse")
        if licensed:
            print("\n  LICENSED FILES ARE IN THIS RELEASE -- do not publish it:", file=sys.stderr)
            for name in licensed:
                print(f"      {name}", file=sys.stderr)
            return 1
        print("licensed   none in the zip")
    finally:
        import shutil
        shutil.rmtree(hold, ignore_errors=True)

    print(f"\nA mat offered this would install version {release.version}. Publish latest.json.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="check_release")
    ap.add_argument("--manifest", default="",
                    help="path or address of the manifest to check "
                         "(default: ../salaah-release/latest.json)")
    ap.add_argument("--live", action="store_true",
                    help="check the published manifest -- what mats actually read")
    ap.add_argument("--key", default=PUBLIC_KEY,
                    help="the public key to check the signature against (default: the one "
                         "built into the app)")
    args = ap.parse_args()

    where = args.manifest or (DEFAULT_URL if args.live
                              else str(ROOT.parent / "salaah-release" / "latest.json"))
    try:
        return check(where, args.key)
    except Refused as why:
        print(f"\nREFUSED: {why}", file=sys.stderr)
        if "nothing has been published" in str(why):
            print(WHY_404, file=sys.stderr)
        print("\nDo not publish latest.json until this passes.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception:                      # noqa: BLE001 -- so a double-click shows the reason
        traceback.print_exc()
    finally:
        try:
            input("\nPress Enter to close. ")
        except EOFError:
            pass
    raise SystemExit(code)
