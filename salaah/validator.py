"""Structural checks on units and school presets. Catches wiring and ordering mistakes (like the
old Pi app's Maghrib bug). Does NOT replace review by someone qualified in each school."""
from __future__ import annotations

from .content import PRAYERS, Content, Unit

FARZ_RAKATS = {"fajr": 2, "dhuhr": 4, "asr": 4, "maghrib": 3, "isha": 4}


def check(content: Content) -> list[str]:
    problems: list[str] = []
    for uid in sorted(content.units):
        _check_unit(content.units[uid], content, problems)
    for sid in sorted(content.schools):
        _check_school(sid, content, problems)
    return problems


def _check_unit(u: Unit, content: Content, problems: list[str]) -> None:
    steps = []
    for ref in u.sequence:
        if ref.step_id not in content.steps:
            problems.append(f"{u.id}: unknown step '{ref}'")
            return
        steps.append(content.steps[ref.step_id])
    postures = [s.posture for s in steps]
    recs = [s.recitation for s in steps]
    n = u.rakats

    ruku = [i for i, p in enumerate(postures) if p == "ruku"]
    if len(ruku) != n:
        problems.append(f"{u.id}: {len(ruku)} ruku for a {n}-rakat unit")
    sujood = postures.count("sujood")
    if sujood != 2 * n:
        problems.append(f"{u.id}: {sujood} sujood, expected {2 * n}")
    tash = recs.count("tashahhud")
    want = 1 if n == 2 else 2
    if tash != want:
        problems.append(f"{u.id}: {tash} tashahhud, expected {want}")
    if str(u.sequence[-1]) != "salam":
        problems.append(f"{u.id}: does not end with the salam")
    if len(ruku) >= 2:
        for i, r in enumerate(recs):
            if r.startswith("qunut") and i < ruku[-2]:
                rakat = sum(1 for k in ruku if k < i) + 1
                problems.append(f"{u.id}: '{u.sequence[i]}' is in rakat {rakat}, expected final rakat {n}")
    for i in range(1, len(steps)):
        if postures[i - 1] == "sujood" and postures[i] != "sujood" and recs[i] != "takbir":
            problems.append(f"{u.id}: no takbir between '{u.sequence[i - 1]}' and '{u.sequence[i]}' (step {i + 1})")


def _check_school(sid: str, content: Content, problems: list[str]) -> None:
    s = content.schools[sid]
    for p in PRAYERS:
        if p not in s.prayers:
            problems.append(f"{sid}: missing prayer '{p}'")
    for prayer, entries in s.prayers.items():
        for e in entries:
            unit = content.units.get(e.unit_id)
            if unit is None:
                problems.append(f"{sid}/{prayer}: unknown unit '{e.unit_id}'")
                continue
            want = FARZ_RAKATS.get(prayer)
            if e.kind == "farz" and want and unit.rakats != want:
                problems.append(f"{sid}/{prayer}: farz uses {unit.rakats}-rakat unit, expected {want}")
    for a, b in s.step_overrides.items():
        if a not in content.steps or b not in content.steps:
            problems.append(f"{sid}: step override '{a}' -> '{b}' names an unknown step")
