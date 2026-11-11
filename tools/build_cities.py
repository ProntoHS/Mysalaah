#!/usr/bin/env python3
"""Builds assets/content/cities.json: the towns the mat can be told it is in.

    python3 tools/build_cities.py

WHY THIS EXISTS. Until 2.20 the mat could only be placed by UK postcode district, which is a
fine unit and a useless one if you live in Sydney. Harry: "a person in sydney, australia wont
be able to use it. postcode good for uk but not any where else." The postcode table stays --
it is offline, already tested, and gives better precision than any city list can -- and this
sits beside it for everybody else.

WHERE THE DATA COMES FROM. The geonamescache package, which carries a snapshot of GeoNames'
cities15000 table. GeoNames is CC BY 4.0, so the mat must credit it: import_credit() below
writes the SOURCE record that the "Where the words come from" page reads, and a test fails if
the credit goes missing.

The package is a BUILD dependency and is not installed on any mat: this writes a plain JSON
file and nothing at run time imports geonamescache.

THE CUT-OFF IS 15,000, which Harry chose, and it is also the floor of the data: the snapshot
is nominally cities15000 and the 45 rows it holds below that are junk, some with a population
of nought. A finer cut-off would need a different GeoNames file, not a different number here.

WHAT THE CUT-OFF COSTS, measured rather than assumed. The listed towns sit a median 11km from
their nearest listed neighbour (75th percentile 23km, 90th 42km), so somebody in a village is
usually within ten or fifteen kilometres of a town on this list. What that distance does to
prayer times depends on where you are and when, by much more than I first wrote: see the
measurements in salaah/places.py. Near the equator it is under a minute all year. At British
latitudes dhuhr, asr and maghrib stay inside a minute or two, while fajr and isha in summer
move several minutes over the same distance. The threshold is a reasonable one; the claim it
was first justified with was too tidy.

WHAT EACH ROW CARRIES, and why the timezone is in it. Name, country, latitude, longitude,
timezone, and a few alternate names. The timezone is the one that stops a quiet disaster: the
mat works its times out from the Pi's own system timezone plus the coordinates, which cannot
disagree while the only choices are British, and can be eleven hours apart the moment Sydney
is on the list. salaah/places.py compares the two and the screen says so.

THE ALTERNATE NAMES ARE NOT A FLOURISH. The canonical entry for the holiest city on this mat
is "Makkah"; somebody typing "Mecca" would find nothing. Jeddah is also "Djeddah". So a few
spellings per town are carried, and a search matches any of them.

LATIN SPELLINGS ONLY, WHICH IS A CORRECTION. The first build also kept one name per script
the mat's own languages use -- Arabic, Bengali, Devanagari, Cyrillic, Han -- on the reasoning
that a mat whose interface is in Urdu should be searchable by somebody typing in Urdu. That
reasoning never checked the keyboard. salaah/keys.py offers a-z, digits and punctuation and
nothing else: there is no way to type an Urdu or Chinese letter on this mat, so those 42,124
names could not be reached by anybody and were carried for nothing.

The guard that caught it was the one that asks whether any shipping text could come out as
empty boxes -- those names had no glyph in the fonts that ship either, so the mat could not
have drawn them had it tried. Dropping them costs no reachable search and takes a third off
the file. If the keyboard ever learns another script, this is the decision to revisit, and
the fonts have to be checked at the same time.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unicodedata

#: Harry's choice. See the note above: this decides list length, not accuracy.
SMALLEST = 15000

#: How many alternate spellings to keep per city.
#:
#: FIVE AND NOT THREE because three was not enough for the one city this mat cares most
#: about. Makkah's Latin alternates sorted shortest-first are Meca, Meka, Meke, Makka,
#: Mecca -- so at three, the spelling an English speaker would actually type was cut for
#: being a character longer than three variants nobody uses. The rule prefers short names
#: because short names are usually the common ones; Makkah is where that breaks, and the
#: cheapest honest fix is to carry enough that being wrong about the order does not matter.
SOME_LATIN = 5


def pick_names(called: str, alternates: list[str]) -> list[str]:
    """The few alternate names worth carrying, chosen rather than truncated.

    THE FIRST VERSION OF THIS TOOK THE SIX SHORTEST and produced nonsense: Sydney's
    alternates came out as "SYD", Dhaka's as "DAC", and Makkah's as "mkh", "mkt", "Meca",
    "Meka". Airport codes and lowercase transliteration fragments, while "Mecca" -- the one
    name an English speaker would actually type for the holiest city on this mat -- was cut
    for being a character too long. The point of carrying alternates at all is that somebody
    typing "Mecca" finds Makkah, so the rule has to prefer names a person would type.

    So: proper-case words of four letters or more, single words before phrases and shorter
    before longer, which puts "Mecca" and "Makka" ahead of "Makkah al Mukarramah" and keeps
    three-letter codes out entirely.

    ASCII ONLY, and that is the whole rule now -- see the note at the top of this file about
    the 42,124 names in other scripts that the mat's keyboard cannot type.
    """
    flat = fold(called)
    seen, latin = {flat}, []
    for name in alternates:
        if not name or not name.isascii() or len(name) < 4 or not name[:1].isupper():
            continue
        key = fold(name)
        if key in seen:
            continue
        seen.add(key)
        latin.append(name)
    latin.sort(key=lambda n: (" " in n, len(n), n))
    return latin[:SOME_LATIN]


def fold(said: str) -> str:
    """A name flattened for searching: no case, no accents.

    Somebody typing "malaga" should find "Málaga", and somebody typing on the mat's own
    keyboard has no easy way to produce the accent. Done here as well as at search time so
    that the file can be searched without every row being folded on every keystroke.
    """
    bare = unicodedata.normalize("NFKD", said.casefold())
    return "".join(ch for ch in bare if not unicodedata.combining(ch))


def main() -> int:
    try:
        import geonamescache
    except ImportError:
        print("  geonamescache is not installed. It is a build dependency and never ships:\n"
              "    pip install --break-system-packages geonamescache", file=sys.stderr)
        return 1

    gc = geonamescache.GeonamesCache()
    countries = {c["iso"]: c["name"] for c in gc.get_countries().values()}

    rows = []
    for city in gc.get_cities().values():
        if city["population"] < SMALLEST:
            continue
        called = city["name"]
        rows.append([
            called,
            city["countrycode"],
            round(city["latitude"], 3),
            round(city["longitude"], 3),
            city["timezone"],
            pick_names(called, [n for n in city["alternatenames"] if n]),
            # The region, kept for now and thrown away below unless it is needed.
            city["admin1code"] if (city["admin1code"].isalpha()
                                   and len(city["admin1code"]) <= 3) else "",
            city["population"],        # sorted on, then dropped before writing
        ])

    # Biggest first, so that a search for a name many places share offers the one most people
    # mean before the rest. "Springfield" has thirteen answers and only one of them is likely.
    #
    # SORTED ON EACH ROW'S OWN POPULATION, which took a second go. The first version looked
    # the population up by NAME, in a dict built from the same source -- so every city
    # sharing a name collapsed to whichever one happened to be written last, and the order
    # among exactly the rows that needed ordering was arbitrary. Searching "malaga" offered
    # Málaga in Colombia, population 18,000, ahead of Málaga in Spain, population 570,000.
    rows.sort(key=lambda row: (-row[-1], row[0]))
    rows = [row[:-1] for row in rows]

    # THE REGION IS KEPT ONLY WHERE IT TELLS TWO PLACES APART. GeoNames has a region code for
    # everywhere, and most of them are numbers -- Andorra la Vella is admin1 "07" -- which on
    # a screen is worse than nothing. The alphabetic ones are mostly US, Canadian and
    # Australian states, which IS where the same town name repeats: eight Springfields, all
    # of them saying "United States" and nothing else.
    #
    # But showing it everywhere it exists reads badly the other way. The United Kingdom's
    # code is "ENG", so the first build offered "Bury, ENG (United Kingdom)" -- an
    # abbreviation that disambiguates nothing, on the one town this mat's owner lives in.
    # So a region survives only where the same name occurs more than once in the same
    # country, which is exactly and only where a reader needs it.
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        seen[(row[0], row[1])] = seen.get((row[0], row[1]), 0) + 1
    shared = 0
    for row in rows:
        if seen[(row[0], row[1])] > 1 and row[6]:
            shared += 1
        else:
            row[6] = ""

    out = {
        "schema": 1,
        "about": ("Towns and cities of more than 15,000 people, for telling the mat where it "
                  "is without the internet. Each carries its timezone so the mat can notice "
                  "when the Pi's own clock disagrees with the place it has been told it is."),
        "source": {
            "who": "GeoNames",
            "where": "https://www.geonames.org/",
            "licence": "CC BY 4.0",
            "licence_at": "https://creativecommons.org/licenses/by/4.0/",
            "via": "the geonamescache package's snapshot of cities15000",
            "smallest": SMALLEST,
            "reviewed": False,
        },
        "countries": countries,
        "cities": rows,
    }

    here = pathlib.Path(__file__).resolve().parent.parent
    path = here / "assets" / "content" / "cities.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")

    read_back = json.loads(path.read_text(encoding="utf-8"))
    assert len(read_back["cities"]) == len(rows), "the file does not read back whole"
    size = path.stat().st_size
    with_names = sum(1 for r in rows if r[5])
    print(f"  wrote {path.relative_to(here)}")
    print(f"    {len(rows):,} towns of {SMALLEST:,} people or more, in "
          f"{len({r[1] for r in rows})} countries")
    print(f"    {with_names:,} of them carry alternate names")
    print(f"    {len({r[4] for r in rows})} distinct timezones")
    print(f"    {shared:,} keep a region, because their name repeats in their country")
    print(f"    {size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
