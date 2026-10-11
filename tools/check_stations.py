#!/usr/bin/env python3
"""Asks every station on the radio list whether it is still there.

    python3 tools/check_stations.py                     # the shipped list
    python3 tools/check_stations.py --play              # and sound two seconds of each
    python3 tools/check_stations.py --url https://...   # just this one

RUN IT ON THE MAT, or on anything with a connection. It cannot be run where the list is
written: the machine this project is built on reaches package registries and GitHub and
nothing else, so every address in stations.json arrived from a directory rather than from
listening to it. This is the thing that turns that into knowledge.

It is also the thing to run when somebody says the radio has stopped working. Stations move
host, run out of money and go off the air, and an address that worked in March is not a
promise about June -- so this prints, for each one: whether it answers, what it answers with,
and what the stream calls itself. A station that does not answer comes out of the list.

WHAT COUNTS AS ANSWERING. Not "the web page loads" -- a station's home page is not its
stream, and the usual mistake is to put the page's address in the list. What is asked for
here is the stream itself, and what proves it is audio arriving: a content type of audio/...
and bytes actually flowing. A playlist (.m3u, .pls) is followed one step to the stream it
names, which is what a player would do.

Nothing is saved and nothing is played unless --play is given. It reads a few kilobytes of
each station and drops the connection.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "assets" / "content" / "radio" / "stations.json"

# Long enough for a station on the other side of the world, short enough that a dead one does
# not hold the whole list up.
WAIT = 8
BYTES = 8192

# Said when asking. A station's log should be able to see who this was, and some hosts refuse
# a request with no name on it at all.
WHO = "salaah-pi station check (https://github.com/ProntoHS/Mysalaah)"

PLAYLIST = ("audio/x-mpegurl", "audio/mpegurl", "application/vnd.apple.mpegurl",
            "audio/x-scpls", "application/pls+xml", "application/x-mpegurl")


def first_in_playlist(body: bytes) -> str:
    """The first stream address a .m3u or .pls names, or ""."""
    text = body.decode("utf-8", "replace")
    found = re.search(r"^\s*File\d+\s*=\s*(\S+)\s*$", text, re.MULTILINE | re.IGNORECASE)
    if found:
        return found.group(1)
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def ask(url: str, depth: int = 0) -> dict:
    """What this address actually is."""
    out = {"url": url, "ok": False, "why": "", "type": "", "name": "", "bitrate": "",
           "bytes": 0, "took": 0.0}
    started = time.monotonic()
    request = urllib.request.Request(url, headers={
        "User-Agent": WHO,
        # Asked for by name: a Shoutcast or Icecast server sends back the station's name and
        # bitrate in its headers when the listener says it can take them.
        "Icy-MetaData": "1",
    })
    try:
        with urllib.request.urlopen(request, timeout=WAIT) as answer:
            out["type"] = (answer.headers.get("Content-Type") or "").split(";")[0].strip()
            out["name"] = (answer.headers.get("icy-name") or "").strip()
            out["bitrate"] = (answer.headers.get("icy-br") or "").strip()
            body = answer.read(BYTES)
            out["bytes"] = len(body)
    except (urllib.error.URLError, OSError, ValueError) as why:
        out["why"] = str(getattr(why, "reason", why))[:80]
        out["took"] = round(time.monotonic() - started, 1)
        return out
    out["took"] = round(time.monotonic() - started, 1)

    if out["type"] in PLAYLIST or url.lower().endswith((".m3u", ".m3u8", ".pls")):
        nested = first_in_playlist(body)
        if not nested or depth >= 2:
            out["why"] = "a playlist with nothing playable in it"
            return out
        deeper = ask(nested, depth + 1)
        deeper["url"] = f"{url} -> {nested}"
        return deeper

    if out["type"].startswith("audio/") or out["type"] in ("application/ogg",):
        out["ok"] = out["bytes"] > 0
        if not out["ok"]:
            out["why"] = "answered, but sent no audio"
    elif out["type"].startswith("text/html"):
        out["why"] = "this is a web page, not a stream"
    else:
        # Some Shoutcast servers answer with nothing useful in the type but do send audio.
        out["ok"] = out["bytes"] > 0
        out["why"] = "" if out["ok"] else f"not audio ({out['type'] or 'no type given'})"
    return out


def sound_it(url: str, seconds: float = 2.0) -> str:
    """Two seconds of it out loud, so a person can hear what the station is."""
    sys.path.insert(0, str(ROOT))
    from salaah.audio import Stream
    player = Stream(volume=60)
    if not player.available:
        return "no player installed"
    if not player.play(url):
        return "the player would not start"
    time.sleep(seconds)
    heard = player.playing
    player.stop()
    return "heard" if heard else "the player gave up"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", type=Path, default=LIST, help="the stations file to check")
    ap.add_argument("--url", action="append", default=[], help="check this address instead")
    ap.add_argument("--play", action="store_true", help="sound two seconds of each one")
    args = ap.parse_args()

    if args.url:
        rows = [{"name": u, "url": u} for u in args.url]
    else:
        try:
            rows = json.loads(args.list.read_text(encoding="utf-8")).get("stations", [])
        except (OSError, ValueError) as why:
            print(f"cannot read {args.list}: {why}")
            return 2

    good, bad = [], []
    for row in rows:
        found = ask(row["url"])
        mark = "ok  " if found["ok"] else "DEAD"
        said = [f"{found['took']}s"]
        if found["type"]:
            said.append(found["type"])
        if found["bitrate"]:
            said.append(f"{found['bitrate']}k")
        if found["name"]:
            said.append(f"calls itself {found['name']!r}")
        if found["why"]:
            said.append(found["why"])
        print(f"{mark} {row.get('name', '')[:28]:<28} {', '.join(said)}")
        if found["ok"] and args.play:
            print(f"     {sound_it(row['url'])}")
        (good if found["ok"] else bad).append(row.get("name") or row["url"])

    print(f"\n{len(good)} answered, {len(bad)} did not.")
    if bad:
        print("take these out of the list, or find where they moved to:")
        for name in bad:
            print(f"  {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
