#!/usr/bin/env python3
"""Play a game's rules thousands of times and report whether it can be won without learning.

    python3 tools/check_fairness.py salaah/game.py
    python3 tools/check_fairness.py path/to/your_game.py --games 2000

This is the other half of tools/check_game.py. That one reads the file; this one plays it.

HOW IT GETS AT THE RULES WITHOUT QT. It parses the module, keeps the parts that are not the
screen -- the constants, the dataclasses, the plain functions, and every class that does not
use a Qt name -- and runs just those. So it needs no display, no Qt and no mat.

That is not a trick to avoid installing something. It is the contract being checked: if the
rules cannot be lifted out and played on their own, they are tangled up with the screen, and a
game whose rules can only be exercised by waiting 1.35 seconds for a highlight to move is a
game nobody can test. A module that fails to come apart here fails MAKING-A-GAME.md section 9,
and the error says so.

WHAT IT MEASURES
  - that a game of it ends, in a sane number of moves
  - that the score only moves on a right answer
  - that an answer cannot be changed once given
  - that a round nobody answered is not skipped
  - that every choice gets to be the right one
  - and the one that matters: what a child scores by pressing the same box every time, which
    in the first version of the prayer game was four out of five.

WHAT IT CANNOT MEASURE is the rest of section 8. A fixed BOX is only one lazy strategy. The
jigsaw passed this checker with its boxes properly shuffled while its pieces came in reading
order, so the answer was always the next empty hole and the thing could be finished perfectly
without ever looking at a piece. Whether some other cue on the screen gives the answer away is
a question only somebody who can see the screen can ask.
"""
from __future__ import annotations

import argparse
import ast
import random
import sys
import types
from pathlib import Path

# What the rules half of a module may import. Qt is deliberately absent: if the rules need it,
# they are not rules.
SAFE_IMPORTS = {"random", "math", "json", "dataclasses", "enum", "itertools", "collections",
                "functools", "typing", "__future__", "abc", "re", "unicodedata", "copy"}

# Names that mean Qt is being used. Matched as NAMES in the syntax tree, never as text in the
# file: the rules class of the reference game has "No Qt, no clock" in its own docstring, and
# a substring search threw it out as a screen on the strength of that sentence.
QT_NAMES = {"QtWidgets", "QtCore", "QtGui", "QtSvg", "Qt", "Signal", "Slot", "QWidget",
            "QObject", "QTimer", "QPainter", "QColor", "QFont", "QRect", "QRectF", "QPoint",
            "QPixmap", "QImage", "QFrame", "QLabel", "QAbstractButton"}


def touches_qt(node: ast.AST) -> bool:
    """Whether this code actually USES Qt, as opposed to mentioning it in a comment."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name) and inner.id in QT_NAMES:
            return True
        if isinstance(inner, ast.Attribute):
            root = inner
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in QT_NAMES:
                return True
    return False


def rules_only(source: str) -> tuple[str, list[str]]:
    """The module with the screen taken out, and a note of what was taken."""
    tree = ast.parse(source)
    kept, dropped = [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.level:
                dropped.append(f"import of .{node.module}")      # one of the app's own
                continue
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""])
            if (names[0] or "").split(".")[0] not in SAFE_IMPORTS:
                dropped.append(f"import of {(names[0] or '').split('.')[0]}")
                continue
            kept.append(node)
            continue
        if isinstance(node, ast.ClassDef):
            if any(touches_qt(b) for b in node.bases):
                dropped.append(f"class {node.name} (a screen)")
                continue
            if touches_qt(node):
                dropped.append(f"class {node.name} (uses Qt)")
                continue
            kept.append(node)
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.FunctionDef)):
            if touches_qt(node):
                dropped.append(f"line {node.lineno} (uses Qt)")
                continue
            kept.append(node)
            continue
        if isinstance(node, ast.Expr):            # docstrings
            continue
        dropped.append(f"line {node.lineno}")
    return ast.unparse(ast.Module(body=kept, type_ignores=[])), dropped


def load_rules(path: Path, want: str = ""):
    """Every rules class in the module, lifted out and ready to play."""
    source, dropped = rules_only(path.read_text(encoding="utf-8"))
    # A REAL module, registered in sys.modules, rather than a bare dict. With
    # `from __future__ import annotations` in force -- which every module here has --
    # @dataclass resolves its annotations through sys.modules[cls.__module__].__dict__, and
    # for code exec'd into a plain dict that lookup returns None and the dataclass blows up
    # with an AttributeError that has nothing to do with the game.
    where = "rules_under_test"
    module = types.ModuleType(where)
    sys.modules[where] = module
    try:
        exec(compile(source, f"<{path.name}: rules>", "exec"), module.__dict__)   # noqa: S102
    except Exception as e:                                                       # noqa: BLE001
        raise SystemExit(
            f"REFUSED  the rules will not run on their own: {type(e).__name__}: {e}\n"
            f"         The rules must live in a class with no Qt in it (MAKING-A-GAME.md\n"
            f"         section 9) so a test can play the game without a display. What was\n"
            f"         left out as screen: " + ", ".join(dropped[:6]))
    found = []
    for name, thing in module.__dict__.items():
        if not isinstance(thing, type) or name.startswith("_"):
            continue
        if {"press", "restart"} <= set(dir(thing)):
            found.append((name, thing))
    if not found:
        raise SystemExit("REFUSED  no rules class found: expected a class with restart() and "
                         "press() on it (MAKING-A-GAME.md section 9).")
    if want:
        found = [(n, t) for n, t in found if n == want] or found
    return found


def build(cls):
    """Build the rules, letting a test pin the shuffle where the game allows it."""
    try:
        return cls()
    except TypeError:
        return None


def spin(game, box: int, cap: int = 500) -> tuple[int, int]:
    """Play a whole game pressing the same box every round. Returns (score, rounds played)."""
    rounds = 0
    while not getattr(game, "done", False) and rounds < cap:
        game.answer(box)
        game.go_on()
        rounds += 1
    return getattr(game, "score", 0), rounds


def examine(name, cls, games: int) -> list[str]:
    bad: list[str] = []
    probe = build(cls)
    if probe is None:
        return [f"{name}: the rules cannot be built without arguments"]
    rounds = getattr(probe, "rounds", 0) or 0
    choices = len(getattr(probe, "choices", ()) or ())
    print(f"\n  {name}: {rounds} rounds, {choices} choices a round")
    if rounds < 1:
        bad.append(f"{name}: does not say how many rounds it has (expected .rounds)")
        return bad
    if choices < 2:
        bad.append(f"{name}: a round offers fewer than two choices (expected .choices)")
        return bad

    g = build(cls)
    score, played = spin(g, 0)
    if not getattr(g, "done", False):
        bad.append(f"{name}: had not ended after {played} rounds")
    else:
        print(f"      ends after {played} rounds")

    g = build(cls)
    while not getattr(g, "done", False):
        g.answer((getattr(g, "correct", 0) + 1) % choices)
        g.go_on()
    if getattr(g, "score", 0):
        bad.append(f"{name}: answering wrongly every time still scored {g.score}")
    else:
        print("      answering wrongly every time scores nothing")

    g = build(cls)
    right = getattr(g, "correct", 0)
    g.answer(right)
    was = getattr(g, "score", 0)
    g.answer((right + 1) % choices)
    g.press()
    if getattr(g, "score", 0) != was or getattr(g, "chosen", None) != right:
        bad.append(f"{name}: an answer could be changed after it was given")
    else:
        print("      an answer cannot be changed once given")

    g = build(cls)
    before = getattr(g, "at", 0)
    g.go_on()
    if getattr(g, "at", 0) != before:
        bad.append(f"{name}: go_on() skipped a round nobody had answered")
    else:
        print("      an unanswered round is not skipped")

    seen = {getattr(build(cls), "correct", 0) for _ in range(max(200, games))}
    if len(seen) < choices:
        bad.append(f"{name}: only box(es) {sorted(i + 1 for i in seen)} are ever right; a real "
                   f"shuffle would use all {choices}")
    else:
        print(f"      all {choices} boxes get to be the right answer")

    fair = rounds / choices
    print(f"      pressing one box every time, {games} games each:")
    for box in range(choices):
        total = sum(spin(build(cls), box)[0] for _ in range(games))
        mean = total / games
        verdict = "about chance" if mean < fair + 0.6 else "BETTER THAN CHANCE"
        print(f"          box {box + 1}: {mean:5.2f} of {rounds}   "
              f"(chance is {fair:.2f})  {verdict}")
        if mean >= fair + 0.6:
            bad.append(f"{name}: pressing box {box + 1} every time scores {mean:.2f} of "
                       f"{rounds} against {fair:.2f} by chance -- a child can win it without "
                       f"reading the question")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("module", type=Path)
    ap.add_argument("--games", type=int, default=600,
                    help="games per fixed box (default 600; the mean is then good to about "
                         "a twentieth of a point)")
    ap.add_argument("--rules", default="", help="only this rules class, when a module has several")
    args = ap.parse_args()
    if not args.module.is_file():
        print(f"no such file: {args.module}")
        return 2

    found = load_rules(args.module, args.rules)
    print(f"{args.module}  rules: {', '.join(n for n, _ in found)}")
    bad: list[str] = []
    for name, cls in found:
        bad += examine(name, cls, args.games)

    print()
    if bad:
        for b in bad:
            print(f"  WRONG  {b}")
        print(f"\n{len(bad)} to fix. MAKING-A-GAME.md section 8 says why each one is there.")
        return 1
    print("Fair: no fixed box beats chance, the score only follows right answers, and it ends.")
    print("NOT checked here: whether some OTHER cue gives the answer away -- the order things")
    print("are offered in, what is already on the board, which option is the only one left.")
    print("Write down the lazy strategy yourself and play it. See section 8.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
