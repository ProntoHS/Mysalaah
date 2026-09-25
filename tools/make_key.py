#!/usr/bin/env python3
"""Makes the pair of keys that updates are signed with. Run this once, on your own computer.

    pip install cryptography
    python3 tools/make_key.py

It writes two things:

    a PRIVATE key, to a file outside this folder. It never leaves your computer. It is what
      proves an update came from you. Anyone holding it can put software on every mat you have
      ever built, so it is not emailed, not pasted into a chat, and not committed to the project.
      Back it up somewhere safe: lose it and you cannot issue updates any more, and every mat has
      to be opened up and given a new key by hand.

    a PUBLIC key, printed to the screen as one short line. It can check a signature but cannot
      make one, so it is safe to hand out. It goes into the app, and so onto every mat.

Why bother, when the files will be fetched over HTTPS: HTTPS says "this really is your website".
It does not say "this file is the one you meant". If your hosting account is ever broken into,
or somebody swaps the file at the host, HTTPS is perfectly happy and the mats install it. A
signature is the part that says you made this exact file. It is the difference between an update
button and a way into a child's bedroom.

The default location keeps the private key out of the project folder on purpose, so it cannot be
committed by accident.

Run it again whenever you need the public key back: the public half can always be worked out
from the private half, so it prints it rather than making a new pair. It never overwrites a key
you already have.

It waits for Enter before closing, because on Windows this gets double-clicked and the window
would otherwise vanish with the answer still in it.
"""
from __future__ import annotations

import argparse
import base64
import os
import stat
import sys
import traceback
from pathlib import Path

DEFAULT = Path.home() / ".salaah" / "signing-key"


def load_bits():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return serialization, Ed25519PrivateKey


def show(private, where: Path, fresh: bool) -> None:
    from cryptography.hazmat.primitives import serialization
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    print(f"\nPrivate key {'written to' if fresh else 'already at'} {where}")
    print("  Keep it. Back it up. Do not send it to anyone, including me.\n")
    print("Public key -- this is the one to hand over, and to put in the app:\n")
    print(f"    {base64.b64encode(public).decode()}\n")


def main() -> int:
    ap = argparse.ArgumentParser(prog="make_key")
    ap.add_argument("--to", type=Path, default=DEFAULT,
                    help=f"where the private key lives (default {DEFAULT})")
    args = ap.parse_args()

    try:
        serialization, Ed25519PrivateKey = load_bits()
    except ImportError:
        print("This needs the cryptography package. Install it with:\n", file=sys.stderr)
        print("    pip install cryptography\n", file=sys.stderr)
        print("If that is not recognised, try:  py -m pip install cryptography\n", file=sys.stderr)
        return 1

    if args.to.exists():
        # Not an error. The public key is not a secret and can always be worked out again, so
        # the useful thing to do is print it rather than refuse and leave you stuck.
        try:
            private = serialization.load_pem_private_key(args.to.read_bytes(), password=None)
        except Exception:
            print(f"{args.to} exists but could not be read as a key.", file=sys.stderr)
            print("Move it aside if you want to make a new one.", file=sys.stderr)
            return 1
        show(private, args.to, fresh=False)
        return 0

    private = Ed25519PrivateKey.generate()
    args.to.parent.mkdir(parents=True, exist_ok=True)
    args.to.write_bytes(private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    try:
        os.chmod(args.to, stat.S_IRUSR | stat.S_IWUSR)    # only you can read it
    except OSError:
        pass            # Windows has no such thing; the file sits in your own user folder
    show(private, args.to, fresh=True)
    return 0


def wait() -> None:
    """Hold the window open. Double-clicking this on Windows would otherwise close it at once,
    taking the answer -- or the error saying what went wrong -- with it."""
    try:
        input("Press Enter to close. ")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception:                      # noqa: BLE001 -- show it rather than flash and vanish
        traceback.print_exc()
    finally:
        wait()
    sys.exit(code)
