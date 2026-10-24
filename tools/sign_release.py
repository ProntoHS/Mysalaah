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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_names import tag_name, url_complaint, zip_name   # noqa: E402

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
    zip_path = out / zip_name(number)
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


MANIFEST = "release-manifest-{}.txt"


def shipping() -> dict:
    """Every file this version would put in a release, by sha256."""
    out = {}
    for pack in PACKS:
        for p in sorted((ROOT / pack).rglob("*")):
            if p.is_file() and not why_not(p):
                out[str(p.relative_to(ROOT)).replace("\\", "/")] = \
                    hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def manifest_complaint(number: str) -> str:
    """Empty when the tree matches the manifest for this version, or there is no manifest.

    The manifest is version-stamped on purpose. A manifest for an older version is not a
    weaker check, it is a check of the wrong thing, so it is simply absent and this says so.
    """
    where = ROOT / "tools" / MANIFEST.format(number)
    if not where.is_file():
        return (f"There is no {where.relative_to(ROOT)}, so this tree has not been checked\n"
                f"against anything. Ask for the manifest for {number} before signing it.\n"
                f"(If you are deliberately releasing a tree nobody has verified, delete this\n"
                f"check rather than working around it -- and write down why.)")
    want = {}
    for line in where.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split(None, 1)
        want[name.strip()] = digest
    have = shipping()
    wrong = sorted(f for f in set(want) & set(have) if want[f] != have[f])
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    if not (wrong or missing or extra):
        return ""
    lines = [f"This tree does not match tools/{MANIFEST.format(number)}."]
    for f in wrong[:10]:
        lines.append(f"    different : {f}")
    for f in missing[:10]:
        lines.append(f"    missing   : {f}")
    for f in extra[:10]:
        lines.append(f"    unexpected: {f}")
    more = len(wrong) + len(missing) + len(extra) - min(10, len(wrong)) \
        - min(10, len(missing)) - min(10, len(extra))
    if more > 0:
        lines.append(f"    ... and {more} more")
    lines.append("")
    lines.append("A file that is DIFFERENT is the dangerous one: it means the copy in this")
    lines.append("folder is not the copy the release was meant to carry. That is how 1.91 went")
    lines.append("out with 86 hadith instead of 109.")
    return "\n".join(lines)


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

    # Refuse to sign a tree that does not match the manifest written for this version.
    #
    # 1.91 went out carrying 86 hadith instead of 109, because the copy of hadith.json in the
    # folder it was built from had been cut down by an earlier bad commit. Every Python file was
    # correct -- the changes zip ships all of salaah/ for exactly that reason -- but assets are
    # fifty megabytes and are sent as a diff, so a file that matches the PREVIOUS release is not
    # in the zip, and a stale copy of it survives into the next one. The same fault as the
    # ImportError, one folder over and quieter: nothing failed, there was just less content.
    #
    # A file count would have caught it. So would six hashes. Both were written down and neither
    # was run, which is the point: a check that depends on somebody remembering it at eight in
    # the evening after three days of this is not a check. This one cannot be skipped, because
    # nothing gets signed until it passes.
    if (problem := manifest_complaint(number)):
        print(f"\n{problem}", file=sys.stderr)
        print("\nNothing has been built and nothing signed.", file=sys.stderr)
        return 1

    # Refuse to sign a manifest that points somewhere other than the file being built. Getting
    # this wrong produces a release that verifies perfectly and then cannot be downloaded, which
    # is a horrible thing to debug from the other end -- the mat says the download failed and
    # gives no hint that the address was never right in the first place.
    if args.url:
        complaint = url_complaint(args.url, number)
        if complaint:
            print(f"\n{complaint}", file=sys.stderr)
            print(f"\nsalaah/__init__.py says the version is {number}, so the address wants to be",
                  file=sys.stderr)
            print(f"    .../releases/download/{tag_name(number)}/{zip_name(number)}",
                  file=sys.stderr)
            print("\nNothing has been built and nothing signed.", file=sys.stderr)
            return 1

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
