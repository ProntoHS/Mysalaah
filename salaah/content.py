"""Prayer content: steps, units, school presets and language packs, loaded from JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = 1
PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]
POSTURES = ["standing", "ruku", "sujood", "sitting", "salam"]


@dataclass(frozen=True)
class Step:
    id: str
    posture: str
    recitation: str
    repeat: int


@dataclass(frozen=True)
class StepRef:
    step_id: str
    variant: str | None = None

    @staticmethod
    def parse(s: str) -> "StepRef":
        sid, _, var = s.partition("@")
        return StepRef(sid, var or None)

    def __str__(self) -> str:
        return f"{self.step_id}@{self.variant}" if self.variant else self.step_id


@dataclass(frozen=True)
class Unit:
    id: str
    rakats: int
    sequence: list[StepRef]


@dataclass(frozen=True)
class UnitEntry:
    kind: str
    unit_id: str


@dataclass(frozen=True)
class School:
    id: str
    status: str
    prayers: dict[str, list[UnitEntry]]
    asr_method: str | None
    step_overrides: dict[str, str]

    @property
    def reviewed(self) -> bool:
        return self.status == "reviewed"


@dataclass
class LanguagePack:
    lang: str
    name: str
    native_name: str
    rtl: bool
    ui: dict[str, str]
    transliteration: dict[str, list[str]] = field(default_factory=dict)
    translation: dict[str, list[str]] = field(default_factory=dict)

    def t(self, key: str, fallback: "LanguagePack | None" = None, **args) -> str:
        s = self.ui.get(key) or (fallback.ui.get(key) if fallback else None) or key
        for k, v in args.items():
            s = s.replace("{" + k + "}", str(v))
        return s


@dataclass
class Translation:
    """The meaning of the recitations in another language, shown beside the Arabic. One file
    per language in content/translations; adding a language is adding a file.

    [lines] matches core/arabic.json verse for verse, so each line sits level with its Arabic."""
    lang: str
    name: str
    native_name: str
    rtl: bool
    lines: dict[str, list[str]]
    intention: str = ""
    kinds: dict[str, str] = field(default_factory=dict)
    prayers: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    about: str = ""
    personal: bool = False      # a file named *.personal.json: private use, never in a release

    def for_key(self, key: str, count: int) -> list[str] | None:
        """The lines for a recitation, or None if they are missing or out of step with the
        Arabic (then that screen shows Arabic only, rather than lines that don't match)."""
        lines = self.lines.get(key)
        return lines if lines and len(lines) == count else None

    def intend(self, rakats: int, kind: str, prayer: str) -> str:
        return (self.intention.replace("{n}", str(rakats))
                .replace("{kind}", self.kinds.get(kind, kind))
                .replace("{prayer}", self.prayers.get(prayer, prayer)))


DEFAULT_FIGURE = "boy"


def available_figures(root: Path) -> list[str]:
    """Who can be shown in the posture pictures. The pictures in assets/postures are the
    original set; a folder inside it (assets/postures/girl) is another set, named by its
    folder. A set may be short of a picture or two: the original is used for those."""
    folder = root / "postures"
    extra = sorted(d.name for d in folder.glob("*")
                   if d.is_dir() and any(d.glob("*.png")))
    return [DEFAULT_FIGURE] + [name for name in extra if name != DEFAULT_FIGURE]


def load_translations(root: Path) -> dict[str, Translation]:
    out = {}
    for f in sorted((root / "content" / "translations").glob("*.json")):
        try:
            d = _read(f)
            out[d["lang"]] = Translation(
                d["lang"], d["name"], d["nativeName"], d.get("dir") == "rtl", d.get("lines", {}),
                d.get("intention", ""), d.get("kinds", {}), d.get("prayers", {}),
                d.get("sources", {}), d.get("about", ""),
                personal=".personal." in f.name)
        except (OSError, ValueError, KeyError):
            continue
    return out


@dataclass(frozen=True)
class Daily:
    """What is shown when a prayer finishes: a short passage and a saying, one for each day."""
    passages: list[dict]
    sayings: list[dict]

    def for_day(self, day) -> tuple[dict | None, dict | None]:
        """The same pair all day, a different pair tomorrow."""
        number = day.toordinal()
        passage = self.passages[number % len(self.passages)] if self.passages else None
        saying = self.sayings[number % len(self.sayings)] if self.sayings else None
        return passage, saying


@dataclass(frozen=True)
class Bead:
    """One of the three counted dhikr said after a fardh prayer. [key] names its words in
    core/arabic.json and its recording in assets/audio."""
    text: str
    count: int
    key: str = ""


@dataclass(frozen=True)
class Dhikr:
    """What is said after a fardh prayer: the salam dua, the three counted dhikr, the tahlil.
    The texts are each shown as one line; the keys name their words and recordings."""
    salam: str
    tahlil: str
    beads: list[Bead]
    salam_key: str = ""
    tahlil_key: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.beads)


@dataclass
class Content:
    root: Path
    steps: dict[str, Step]
    units: dict[str, Unit]
    schools: dict[str, School]
    arabic: dict[str, list[str]]
    prayer_names: dict[str, str]  # each prayer's name in Arabic
    daily: Daily
    dhikr: Dhikr
    translations: dict[str, "Translation"] = field(default_factory=dict)
    figures: list[str] = field(default_factory=lambda: [DEFAULT_FIGURE])

    def unit_label(self, entry: UnitEntry, pack: LanguagePack, fallback: LanguagePack | None = None) -> str:
        unit = self.units[entry.unit_id]
        return pack.t("unit.label", fallback, rakats=unit.rakats, kind=pack.t(f"kind.{entry.kind}", fallback))


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: unsupported schema {data.get('schema')}")
    return data


def load_pack(path: Path) -> LanguagePack:
    d = _read(path)
    return LanguagePack(
        lang=d["lang"], name=d["name"], native_name=d["nativeName"], rtl=d.get("dir") == "rtl",
        ui=d.get("ui", {}), transliteration=d.get("transliteration", {}), translation=d.get("translation", {}),
    )


def load(root: Path) -> Content:
    """[root] is the assets folder holding content/ and steps/."""
    c = root / "content"
    steps = {
        sid: Step(sid, s["posture"], s["recitation"], int(s["repeat"]))
        for sid, s in _read(c / "steps.json")["steps"].items()
    }
    units = {}
    for f in sorted((c / "units").glob("*.json")):
        d = _read(f)
        units[d["id"]] = Unit(d["id"], int(d["rakats"]), [StepRef.parse(x) for x in d["sequence"]])
    schools = {}
    for f in sorted((c / "schools").glob("*.json")):
        d = _read(f)
        prayers = {p: [UnitEntry(e["kind"], e["unit"]) for e in entries] for p, entries in d["prayers"].items()}
        schools[d["id"]] = School(d["id"], d["status"], prayers, d.get("prayerTimes", {}).get("asrMethod"),
                                  d.get("stepOverrides", {}))
    core = _read(c / "core" / "arabic.json")

    def daily(name: str, key: str) -> list[dict]:
        path = c / "daily" / f"{name}.json"
        try:
            return _read(path).get(key, [])
        except (OSError, ValueError):
            return []

    try:
        after = _read(c / "core" / "dhikr.json")["after_farz"]
        words = core.get("text", {})

        def said(key: str) -> str:
            return " ".join(words.get(key, []))

        dhikr = Dhikr(said(after.get("salam", "")), said(after.get("tahlil", "")),
                      [Bead(said(b["key"]), int(b["count"]), b["key"]) for b in after.get("beads", [])],
                      after.get("salam", ""), after.get("tahlil", ""))
    except (OSError, ValueError, KeyError):
        dhikr = Dhikr("", "", [])

    return Content(root, steps, units, schools, core.get("text", {}), core.get("prayers", {}),
                   Daily(daily("quran", "passages"), daily("hadith", "sayings")), dhikr,
                   load_translations(root), available_figures(root))


def available_packs(root: Path) -> dict[str, LanguagePack]:
    packs = {}
    for f in sorted((root / "content" / "packs").glob("*/pack.json")):
        p = load_pack(f)
        packs[p.lang] = p
    return packs
