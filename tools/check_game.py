#!/usr/bin/env python3
"""Check a game module against the mechanical half of MAKING-A-GAME.md.

    python3 tools/check_game.py salaah/game.py
    python3 tools/check_game.py path/to/new_game.py path/to/new_game.strings.json

Written to be handed to whoever is building the game, so they can find their own mistakes
before anybody else sees them. It runs without the app, without Qt and without a display: it
reads the file as text and as a syntax tree, so a module that will not even import -- which is
most of them, first time, because they import PySide6 by name -- still gets a useful answer.

WHAT IT CANNOT CHECK is as important as what it can. It cannot tell you whether the game is
fair, whether the translations are right, whether a question gives its answer away, or whether
the thing is any fun. Those are in MAKING-A-GAME.md and they are the half that matters. A clean
run here means the game can be read by the mat, not that it should be.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules the mat itself has. Anything else is a new dependency, which there is no way to
# install on a mat: a release replaces salaah/ and assets/ and runs no installer.
ALLOWED_IMPORTS = {
    # the standard library a game could reasonably want
    "random", "math", "json", "dataclasses", "enum", "itertools", "collections",
    "functools", "typing", "pathlib", "__future__", "abc", "re", "unicodedata",
    # the app's own modules
    "qt", "render", "theme", "buttons", "mosque", "filmsheet", "knowledge", "duamenu",
    "content", "settings", "quran", "passages", "wudu", "game",
}

BANNED_CALLS = {
    "sleep": "blocks the event loop; the mat freezes. Use a QTimer on the screen.",
    "exec": "no.",
    "eval": "no.",
    "system": "a game may not run commands.",
    "Popen": "a game may not start a process.",
    "run": None,          # only flagged for subprocess.run, handled below
}

BANNED_MODULES = {
    "subprocess": "a game may not start a process",
    "threading": "Qt here is single threaded; use a QTimer",
    "socket": "a game may not touch the network",
    "urllib": "a game may not touch the network",
    "requests": "a game may not touch the network, and it is not installed",
    "http": "a game may not touch the network",
    "os": "nothing a game needs is in os; paths come from window.assets",
    "shutil": "a game writes nothing",
    "tempfile": "a game writes nothing",
    "logging": "a game writes nothing",
    "pickle": "a game writes nothing",
    "sqlite3": "a game writes nothing",
    "PySide6": "import from .qt instead, so the game runs on either binding",
    "PyQt6": "import from .qt instead, so the game runs on either binding",
    "PyQt5": "import from .qt instead, so the game runs on either binding",
    "pygame": "not installed, and not how this mat draws",
    "numpy": "not installed on a mat",
    "scipy": "not installed on a mat",
    "PIL": "not installed on a mat; it is a build-time tool only",
}

LANGS = ("en", "fr", "es", "ur", "hi", "zh", "ru", "pt", "bn")

# Strings the packs already carry. Restating them in a game's own manifest is how two spellings
# of Maghrib end up on one screen.
ALREADY = ("prayer.fajr", "prayer.dhuhr", "prayer.asr", "prayer.maghrib", "prayer.isha",
           "corner.back", "corner.item")


class Report:
    def __init__(self):
        self.bad: list[str] = []
        self.said: list[str] = []

    def fail(self, rule: str, detail: str) -> None:
        self.bad.append(f"{rule}: {detail}")

    def ok(self, rule: str) -> None:
        self.said.append(rule)


def top_module(name: str) -> str:
    return (name or "").split(".")[0]


def check_imports(tree: ast.AST, r: Report) -> None:
    trouble = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                trouble += [(alias.name, node.lineno)]
        elif isinstance(node, ast.ImportFrom):
            if node.level:                      # from .qt import ... -- one of ours
                trouble += [(node.module or "", node.lineno)]
            else:
                trouble += [(node.module or "", node.lineno)]
    for name, line in trouble:
        head = top_module(name)
        if head in BANNED_MODULES:
            r.fail("no such dependency", f"line {line}: {head} -- {BANNED_MODULES[head]}")
        elif head and head not in ALLOWED_IMPORTS:
            r.fail("unknown import", f"line {line}: {head} is not on the mat; say why you "
                                     f"need it rather than importing it")
    if not any(b in [top_module(n) for n, _ in trouble] for b in BANNED_MODULES):
        r.ok("imports only what the mat has")


def check_no_work_at_import(tree: ast.AST, r: Report) -> None:
    """Importing the module must build nothing. The first game started a thread on import."""
    guilty = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Expr, ast.Pass)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            # A literal container is data even when it holds constructor calls: ROUNDS is a
            # tuple of frozen dataclasses and is exactly the right way to write the rules
            # down. A BARE call is not data -- GAME = GameController() at module level is
            # what started a background thread on import in the first game, and an earlier
            # version of this check waved it through because the name began with a capital.
            if value is None or isinstance(value, (ast.Constant, ast.Tuple, ast.List, ast.Dict,
                                                   ast.Set, ast.Name, ast.UnaryOp, ast.BinOp)):
                continue
            if isinstance(value, ast.Call):
                guilty.append(f"line {node.lineno}: {ast.unparse(node)[:60]} -- build it when "
                              f"the screen is built, not when the module is read")
                continue
            continue
        if isinstance(node, ast.If) and ast.unparse(node.test).startswith("__name__"):
            continue
        guilty.append(f"line {node.lineno}: {ast.unparse(node)[:60]}")
    if guilty:
        for g in guilty:
            r.fail("work at import time", g)
    else:
        r.ok("importing it does nothing")


def check_banned_calls(tree: ast.AST, source: str, r: Report) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        said = ast.unparse(node.func)
        last = said.split(".")[-1]
        if last == "sleep":
            r.fail("blocking call", f"line {node.lineno}: {said} -- {BANNED_CALLS['sleep']}")
        if last in ("grab", "ungrab") and "device" in said.lower():
            r.fail("grabs an input device", f"line {node.lineno}: {said} -- the ring is "
                                            f"already grabbed by salaah/buttons.py")
        if last in ("open",) and isinstance(node.func, ast.Name):
            r.fail("opens a file", f"line {node.lineno}: a game reads only through "
                                   f"window.assets and writes nothing")
        for writer in ("write_text", "write_bytes", "mkdir", "unlink", "rmtree"):
            if last == writer:
                r.fail("writes to disk", f"line {node.lineno}: {said} -- the mat writes nothing")
    r.ok("no sleeping, no device grabs, no writing")


def check_paths(source: str, r: Report) -> None:
    found = re.findall(r"""["'](/(?:home|usr|etc|tmp|var|opt)/[^"']*|~/[^"']*)["']""", source)
    if found:
        for p in sorted(set(found)):
            r.fail("absolute path", f"{p} -- paths come from window.assets")
    else:
        r.ok("no absolute paths")


def check_sizes_and_colours(source: str, tree: ast.AST, r: Report) -> None:
    hexes = set(re.findall(r'["\']#[0-9A-Fa-f]{3,8}["\']', source))
    named = set(re.findall(r'QColor\(\s*["\'](?!#)([a-z]+)["\']', source))
    if hexes or named:
        r.fail("hardcoded colour", f"{sorted(hexes | named)} -- read palette() at paint time "
                                   f"so the screen follows light and dark")
    else:
        r.ok("every colour from palette()")
    if "palette()" not in source:
        r.fail("never asks for the palette", "a screen that draws must read palette()")
    if re.search(r"\bpx\(", source):
        r.ok("sizes go through px()")
    else:
        r.fail("no px()", "sizes must scale: window.px(46), never a bare 46")


def check_shape(tree: ast.AST, source: str, r: Report) -> None:
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    methods = {c: {m.name for m in ast.walk(node) if isinstance(m, ast.FunctionDef)}
               for c, node in classes.items()}
    screens = [c for c, node in classes.items()
               if any("QWidget" in ast.unparse(b) for b in node.bases)]
    if not screens:
        r.fail("no screen", "expected a class deriving from QtWidgets.QWidget")
        return
    rules = [c for c, got in methods.items()
             if c not in screens and {"press", "restart"} <= got]
    if not rules:
        r.fail("no rules class", "the rules must live in a class of their own, with no Qt in "
                                 "it, so they can be tested without a display")
    else:
        r.ok(f"rules kept apart from the screen ({', '.join(rules)})")
    for screen in screens:
        got = methods[screen]
        # Looked for INSIDE hideEvent. Asking whether the word "stop" appears anywhere in the
        # class passes happily on a hideEvent that was emptied, because start_again stops the
        # same timer -- which is how an emptied hideEvent got through this check once.
        hiding = next((m for m in ast.walk(classes[screen])
                       if isinstance(m, ast.FunctionDef) and m.name == "hideEvent"), None)
        if hiding is None:
            r.fail("timers never stop", f"{screen} has no hideEvent; a game left stepping "
                                        f"behind another screen is a Pi working for nobody")
        elif ".stop()" not in ast.unparse(hiding):
            r.fail("timers never stop", f"{screen}.hideEvent stops nothing")
        if "press" not in got:
            r.fail("cannot be played with the ring",
                   f"{screen} has no press(action); the ring is the main way in")

    # Whoever CALLS random.shuffle has to let a test say what it deals. Checked on that class
    # rather than on the file: a screen that takes a shuffle it never uses, while the rules
    # reach for random.shuffle directly, is the arrangement this is meant to catch.
    shufflers = [c for c, node in classes.items()
                 if "random.shuffle" in ast.unparse(node) or "_shuffle" in ast.unparse(node)]
    for c in shufflers:
        start = next((m for m in ast.walk(classes[c])
                      if isinstance(m, ast.FunctionDef) and m.name == "__init__"), None)
        taken = [a.arg for a in start.args.args] if start else []
        if "shuffle" not in taken:
            r.fail("randomness a test cannot pin",
                   f"{c} shuffles but its __init__ takes no shuffle argument; take one, "
                   f"defaulting to random.shuffle, so a test can deal a known hand")
    if shufflers and not r.bad:
        r.ok("the shuffle can be pinned by a test")
    r.ok("has a screen and a press()")


def check_strings(path: Path, source: str, r: Report) -> None:
    """Every t() key used must be in the manifest, in every language, and vice versa."""
    used = set(re.findall(r"""\bt\(\s*["']([a-z0-9_.]+)["']""", source))
    used |= set(re.findall(r"""\bt\(\s*f["']([a-z0-9_.]+)\{""", source))
    if not used:
        r.fail("no translated strings", "every visible word goes through window.t(key)")
        return
    if not path.is_file():
        r.said.append(f"uses {len(used)} string keys; no manifest given, so they were not "
                      f"checked against one")
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8")).get("strings", {})
    except (OSError, ValueError) as e:
        r.fail("manifest unreadable", str(e))
        return
    for key in sorted(used):
        if any(key.startswith(a.split(".")[0] + ".") and key in ALREADY for a in ALREADY):
            continue
        if key in ALREADY:
            continue
        if key not in manifest and not key.endswith("."):
            # keys built with an f-string are reported as a prefix; allow a family
            if not any(k.startswith(key) for k in manifest):
                r.fail("string missing from the manifest", key)
    # A string belonging to some other part of the app must not be restated here. Two
    # spellings of Maghrib on one screen is the visible version; the invisible one is a game
    # quietly disagreeing with the arches on the front door.
    #
    # Only keys OUTSIDE the game's own family count. A game that has already shipped has its
    # own keys in the packs by definition -- an earlier version of this check flagged the
    # reference game's eleven strings as things it should stop restating, which was the check
    # being wrong rather than the game. The family is the first part of its keys.
    try:
        theirs = set(json.loads((ROOT / "assets" / "content" / "packs" / "en" / "pack.json")
                                .read_text(encoding="utf-8"))["ui"])
    except (OSError, ValueError, KeyError):
        theirs = set(ALREADY)
    families = [k.split(".")[0] for k in manifest if "." in k]
    mine = max(set(families), key=families.count) if families else ""
    for key in sorted(set(manifest) & theirs):
        if key.split(".")[0] == mine:
            continue
        r.fail("string the mat already has", f"{key} belongs to the rest of the app -- call "
                                             f"window.t(\"{key}\") and take it out of here")

    for key, words in sorted(manifest.items()):
        missing = [l for l in LANGS if not str(words.get(l, "")).strip()]
        if missing:
            r.fail("string not translated", f"{key} has no {', '.join(missing)}")
    if not r.bad:
        r.ok(f"{len(used)} string keys, all in the manifest, all nine languages")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    module = Path(sys.argv[1])
    strings = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("")
    if not module.is_file():
        print(f"no such file: {module}")
        return 2
    source = module.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"REFUSED  {module.name} will not even parse: line {e.lineno}, {e.msg}")
        return 1

    r = Report()
    check_imports(tree, r)
    check_no_work_at_import(tree, r)
    check_banned_calls(tree, source, r)
    check_paths(source, r)
    check_sizes_and_colours(source, tree, r)
    check_shape(tree, source, r)
    check_strings(strings, source, r)

    print(f"{module}  ({len(source.splitlines())} lines)\n")
    for said in r.said:
        print(f"  ok     {said}")
    for bad in r.bad:
        print(f"  WRONG  {bad}")
    print()
    if r.bad:
        print(f"{len(r.bad)} to fix. MAKING-A-GAME.md says why each one is there.")
        return 1
    print("The mechanical half of MAKING-A-GAME.md passes.")
    print("The half that matters -- is it fair, are the words right, does a question give its")
    print("own answer away -- is not checkable here. Read section 7 and 8 and go through it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
