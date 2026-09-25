#!/usr/bin/env python3
"""Packages a version of the app and signs it, ready to upload. Run this on your own computer.

    python3 tools/sign_release.py --out ~/releases

It writes two files:

    salaah-<version>.zip    the app itself: the salaah and assets folders, nothing else
    latest.json             what version that is, where to fetch it, its hash, and a signature

Upload the zip wherever it is going to live, put its address in latest.json (or pass --url so
this writes it for you), and upload latest.json too. The mats fetch latest.json, check the
signature against the public key built into them, and refuse anything that does not verify.

The signature is made with the private key that make_key.py wrote. It never leaves this machine.

Note what is NOT in the zip: run.sh. It is the guard that puts the old version back when a new
one will not start, so it deliberately cannot be replaced by an update. If you ever change it,
that is a change people have to make by hand.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ("salaah", "assets")
DEFAULT_KEY = Path.home() / ".salaah" / "signing-key"

# Private use only: licensed translations that must not go out in a release.
NEVER = ("*.personal.json",)


def version() -> str:
    text = (ROOT / "salaah" / "__init__.py").read_text()
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("could not find __version__ in salaah/__init__.py")


def why_not(path: Path) -> str:
    """Empty if the file belongs in a release, otherwise the reason it does not."""
    if "__pycache__" in path.parts or path.suffix == ".pyc":
        return "junk"
    if any(path.match(pattern) for pattern in NEVER):
        return "licensed"
    return ""


def build(out: Path, number: str) -> tuple[Path, int, str]:
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"salaah-{number}.zip"
    licensed, junk = [], 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipped:
        for folder in PACKS:
            for item in sorted((ROOT / folder).rglob("*")):
                if not item.is_file():
                    continue
                skip = why_not(item)
                if skip == "licensed":
                    licensed.append(item.relative_to(ROOT))
                    continue
                if skip:
                    junk += 1
                    continue
                zipped.write(item, item.relative_to(ROOT).as_posix())
    # The licensed translations are private use only, so whether they were left out is the one
    # thing worth seeing every time. Kept apart from the build noise so it cannot be missed.
    if licensed:
        print("\n  KEPT OUT of this release -- private use only:")
        for name in licensed:
            print(f"      {name}")
    if junk:
        print(f"\n  ({junk} compiled and cache files skipped)")
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return zip_path, zip_path.stat().st_size, sha


def sign(body: dict, key_path: Path) -> str:
    from cryptography.hazmat.primitives import serialization
    private = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    # Signed over the body exactly as the mat will re-encode it, so the two agree byte for byte.
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(private.sign(payload)).decode()


def main() -> int:
    ap = argparse.ArgumentParser(prog="sign_release")
    ap.add_argument("--out", type=Path, default=ROOT.parent / "releases",
                    help="where to write the zip and latest.json")
    ap.add_argument("--url", default="",
                    help="where the zip will live once uploaded; goes into latest.json")
    ap.add_argument("--notes", default="", help="one line shown on the mat before it updates")
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY, help="your private signing key")
    args = ap.parse_args()

    if not args.key.exists():
        print(f"No signing key at {args.key}.", file=sys.stderr)
        print("Run tools/make_key.py first.", file=sys.stderr)
        return 1

    number = version()
    zip_path, size, sha = build(args.out, number)
    body = {
        "version": number,
        "url": args.url or f"PUT THE ADDRESS OF {zip_path.name} HERE",
        "sha256": sha,
        "bytes": size,
        "notes": args.notes,
    }
    manifest = {"release": body, "signature": sign(body, args.key)}
    where = args.out / "latest.json"
    where.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"\n  {zip_path}  ({size / 1e6:.1f} MB)")
    print(f"  {where}")
    print(f"\nversion {number}, sha256 {sha[:16]}...")
    if not args.url:
        print("\nNo --url given, so latest.json has a placeholder in it. Edit that line to the")
        print("address the zip will be fetched from, then run this again with --url to have it")
        print("signed properly -- a hand-edited manifest will not verify.")
    return 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception:                      # noqa: BLE001 -- so a double-click shows the reason
        traceback.print_exc()
    finally:
        try:
            input("Press Enter to close. ")
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(code)
