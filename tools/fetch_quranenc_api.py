#!/usr/bin/env python3
"""Captures a translation from quranenc.com's own API, for import_quranenc.py to install.

    python tools\\fetch_quranenc_api.py russian_aboadel french_hameedullah urdu_junagarhi

Writes one file per edition into --out (the repo root by default), named
quranenc-<edition>.json, in exactly the shape import_quranenc.py's read_api() expects.

WHY THIS RUNS ON HARRY'S MACHINE AND NOT WHERE THE REST OF THE TOOLS RUN. The container the
rest of this is built in cannot reach quranenc.com -- its network allows package registries
and GitHub and nothing else, and a request to anything else is refused before it leaves. The
browser pane can read their pages but cannot run a script in them. So the one step that needs
the open internet is this one, and it is deliberately the smallest, dullest part of the job:
fetch, check, write. Everything that decides anything happens afterwards, where it can be
tested.

WHY THE API AND NOT THE EXPORT, for these three. The Encyclopedia publishes an XML export for
75 of its 163 translations and these are in the other 88 -- the same bucket the Bengali was
found in, where /home/d/xml/<edition> answers with an empty page. Their API serves them, so
this is the only official road to a text the mat is permitted to carry. import_quranenc.py's
docstring explains why the export is preferred where there is one, and nothing here disagrees
with it.

ABOUT VERSIONS, AND A CORRECTION I MADE TWICE. read_api() was written believing the API
states no revision at all. That is true of the per-surah endpoint and not of
    https://quranenc.com/api/v1/translations/list
which carries a version and a last_update:

    {"key":"english_rwwad","direction":"ltr","language_iso_code":"en",
     "version":"1.0.20","last_update":1792...}

So this reads that endpoint and records the version where there is one. But the list answers
with 76 editions where the site carries around 163, and the ones it omits appear to be exactly
the ones with no downloadable export -- which is to say the editions this tool exists for. The
first run of it refused russian_aboadel on those grounds, which was the tool being wrong rather
than the edition being absent.

The upshot, said plainly: for an edition with an export, the version is here and the export is
the better road anyway. For an edition without one -- Russian, Bengali -- there is no version
to be had from anywhere we can see, and a mat carrying it cannot be told it has gone stale.
That is the cost of coming this way, it has not gone away, and asking quranenc.com to publish
exports for those editions is the fix.

WHAT IT REFUSES. Anything short. It will not write a file that is not 114 surahs numbered
1..114, nor one where a verse came back blank. A partial capture that looked fine is how 1.91
went out with 86 hadith instead of 109, and the whole point of writing the file only at the end
is that a half-finished download cannot be mistaken for a finished one.

WHAT IT CANNOT CHECK. Whether the words are right. Nobody who reads these languages has been
over any of it; the SOURCE.json that import_quranenc.py writes will say reviewed: false, and
that is the only honest thing to say until somebody has.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

LIST = "https://quranenc.com/api/v1/translations/list"
SURA = "https://quranenc.com/api/v1/translation/sura/{edition}/{number}"

#: Long enough that a hiccup does not end the run, short enough that a site that is down does
#: not keep somebody waiting twenty minutes to find out.
TRIES = 4
PAUSE = 1.5
#: A courtesy to their server rather than a technical need: 114 requests in a burst from one
#: address looks like something it should not have to think about.
BETWEEN = 0.2


def fetch(url: str, what: str, missing_is_answer: bool = False):
    """The JSON at a URL, retried a few times. None for a 404 when the caller expects one.

    A 404 is an answer and not a hiccup, so it is never retried: asking four times whether an
    edition exists gets four noes a second and a half apart.
    """
    last = None
    for attempt in range(1, TRIES + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "salaah-pi content build (one-off capture)"})
            with urllib.request.urlopen(request, timeout=30) as answer:
                if answer.status != 200:
                    raise urllib.error.HTTPError(url, answer.status, "not 200", {}, None)
                return json.loads(answer.read().decode("utf-8"))
        except urllib.error.HTTPError as bad:
            if bad.code == 404:
                if missing_is_answer:
                    return None
                raise SystemExit(f"  {what}: not there (404)")
            last = bad
        except Exception as bad:                      # noqa: BLE001 - reported, then retried
            last = bad
        if attempt < TRIES:
            print(f"    {what}: {type(last).__name__}, trying again "
                  f"({attempt} of {TRIES})", file=sys.stderr)
            time.sleep(PAUSE * attempt)
    raise SystemExit(f"  giving up on {what}: {last}")


def versions() -> dict[str, dict]:
    """Every edition the API knows, by key, with the version it reports for each."""
    doc = fetch(LIST, "the list of translations")
    rows = doc.get("translations") or doc.get("result") or []
    return {row["key"]: row for row in rows if isinstance(row, dict) and row.get("key")}


def capture(edition: str, known: dict) -> dict:
    """One edition, all 114 surahs.

    BEING ABSENT FROM THEIR LIST IS NOT BEING ABSENT. The first version of this refused
    anything the list endpoint did not name, and that was wrong: the list returns 76 editions
    where the site carries around 163, and the ones it leaves out are -- as far as can be told
    -- exactly the ones with no downloadable export. Which is to say, the editions this tool
    exists for. Russian, and the Bengali before it, are missing from the list for the same
    reason they are missing from the Downloads page.

    So the list is consulted for a version and nothing else. Whether an edition is really
    there is settled by asking it for surah 1, which is the only test that means anything.
    """
    row = known.get(edition)
    if row is None:
        probe = fetch(SURA.format(edition=edition, number=1),
                      f"{edition} surah 1", missing_is_answer=True)
        if probe is None or not (probe.get("result") or []):
            raise SystemExit(f"  {edition}: their API does not serve it. Check the key "
                             f"against the address bar on quranenc.com/en/browse/<key>.")
        row = {}
        print(f"  {edition}: NOT IN THEIR LIST, so no version is available for it -- "
              f"the same gap the Bengali has. Fetching 114 surahs anyway.")
    else:
        print(f"  {edition}: version {row.get('version') or 'not stated'}, "
              f"{row.get('language_iso_code', '?')}, fetching 114 surahs")
    surahs: dict[str, list] = {}
    for number in range(1, 115):
        doc = fetch(SURA.format(edition=edition, number=number), f"{edition} surah {number}")
        rows = doc.get("result") or []
        verses = []
        for item in rows:
            verses.append({"n": int(item["aya"]), "text": str(item.get("translation", ""))})
        if not verses:
            raise SystemExit(f"  {edition}: surah {number} came back empty")
        surahs[str(number)] = verses
        if number % 20 == 0 or number == 114:
            print(f"    {number} of 114")
        time.sleep(BETWEEN)
    total = sum(len(v) for v in surahs.values())
    if len(surahs) != 114 or total != 6236:
        raise SystemExit(f"  {edition}: got {len(surahs)} surahs and {total} verses, "
                         f"expected 114 and 6236 -- nothing written")
    blank = [f"{s}:{v['n']}" for s, rows in surahs.items() for v in rows if not v["text"].strip()]
    if blank:
        raise SystemExit(f"  {edition}: {len(blank)} verses came back blank "
                         f"({', '.join(blank[:5])}...) -- nothing written")
    return {
        "edition": edition,
        "source": "quranenc.com",
        "endpoint": SURA.format(edition=edition, number="{sura}"),
        "fetched_at": datetime.datetime.now(datetime.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": row.get("version", ""),
        "last_update": row.get("last_update", ""),
        "language_iso_code": row.get("language_iso_code", ""),
        "direction": row.get("direction", ""),
        "title": row.get("title", ""),
        "surahs": surahs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("editions", nargs="+", help="edition keys, e.g. russian_aboadel")
    parser.add_argument("--out", default=".", help="where to write the captures")
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print("  asking quranenc.com which editions it has, and at what version")
    known = versions()
    print(f"  it lists {len(known)} editions")

    written = []
    for edition in args.editions:
        doc = capture(edition, known)
        path = out / f"quranenc-{edition}.json"
        # WRITTEN LAST, in one go, so a run that stopped halfway leaves no file at all rather
        # than a plausible-looking short one.
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        size = path.stat().st_size
        print(f"  wrote {path} ({size // 1024} KB, version "
              f"{doc['version'] or 'not stated'})")
        written.append(path)

    print(f"\n  {len(written)} capture(s) written. Nothing has been installed: hand these to "
          f"tools/import_quranenc.py, which checks them again before writing anything.")
    bare = [p.name for p in written
            if not json.loads(p.read_text(encoding="utf-8")).get("version")]
    if bare:
        print(f"  {len(bare)} of them carry no version, because their list endpoint does not "
              f"name the edition:\n    " + "\n    ".join(bare)
              + "\n  A mat carrying one of these cannot be told it has gone stale. That is "
                "the\n  thing to ask quranenc.com to fix by publishing an export.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
