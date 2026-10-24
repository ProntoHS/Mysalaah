#!/usr/bin/env python3
"""Play a game's rules with the lazy strategies a child could follow without understanding.

    python3 tools/check_lazy.py salaah/game.py

tools/check_fairness.py measures one lazy strategy: pressing the same BOX every time. That is
the one the prayer game failed. It is not the only one, and the two that came after it failed
different ones:

  the jigsaw     offered its nine pieces in reading order, so the answer was always the next
                 empty hole. Boxes properly shuffled; 500 of 500 perfect games by a strategy
                 that never looked at a piece.
  Qibla Quest    asked its five cities in the same order every game, so the sequence of
                 answers -- south-east, north-east, south-west, north-west, south-east -- could
                 be learnt by position and replayed.

So this plays the strategies that do not look at the question at all and reports what each one
scores. Anything near full marks is a game asking a different question from the one it thinks.

It cannot be exhaustive: only somebody looking at the screen knows what it shows. This covers
the cues that live in the RULES, which is where the two above lived.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_fairness import build, load_rules                              # noqa: E402


def play(cls, pick, games: int) -> tuple[float, int, int, list[float]]:
    """Returns (mean score, perfect games, rounds, mean score of each round).

    The per-round scores are what tell a CUE from a WON GAME. A placement game's last piece
    has one hole left by arithmetic, so any strategy gets it; that shows up as a spike in the
    final round or two with chance everywhere else. A game whose answer is given away shows up
    as every round at once. Same mean, nothing alike.
    """
    total = perfect = rounds = 0
    got = [0.0] * 60
    for _ in range(games):
        g = build(cls)
        seen: list = []
        while not getattr(g, "done", False) and len(seen) < 60:
            at = getattr(g, "at", len(seen))
            which = pick(g, seen)
            seen.append(which)
            was = getattr(g, "score", 0)
            g.answer(which)
            g.go_on()
            if at < 60:
                got[at] += getattr(g, "score", 0) - was
        rounds = getattr(g, "rounds", len(seen))
        total += getattr(g, "score", 0)
        perfect += getattr(g, "score", 0) == rounds
    return total / games, perfect, rounds, [n / games for n in got[:rounds]]


def learnt_sequence(cls, games: int):
    """Play once to learn the answers by ROUND NUMBER, then replay from memory.

    This is the Qibla hole. If the rounds always come in the same order, the answers always
    come in the same order, and one playthrough teaches you the whole game by heart without
    teaching you anything about its subject.
    """
    g = build(cls)
    learnt = []
    while not getattr(g, "done", False) and len(learnt) < 60:
        learnt.append(getattr(g, "choices", ())[getattr(g, "correct", 0)])
        g.answer(getattr(g, "correct", 0))
        g.go_on()

    def pick(game, seen):
        want = learnt[len(seen)] if len(seen) < len(learnt) else None
        choices = list(getattr(game, "choices", ()))
        return choices.index(want) if want in choices else 0
    return play(cls, pick, games)


def judge(mean, perfect, rounds, per_round, chance, games):
    """WRONG, LOOK or nothing, and why.

    WRONG is reserved for a strategy that WINS: near full marks, or perfect games often enough
    that a child would notice. Merely beating chance is a CUE -- worth a person's eye, not an
    automatic failure -- and the per-round figures usually say which it is. The jigsaw's
    original hole scored full marks in every round; its fixed endgame scores chance in every
    round but the last. A checker that called both the same would get one of them ignored.
    """
    if perfect > games // 20 or mean >= 0.75 * rounds:
        return "WRONG", (f"scores {mean:.2f} of {rounds} against {chance:.2f} by chance "
                         f"({perfect}/{games} perfect) -- this wins the game")

    # JUDGED ON CERTAINTIES, NOT ON THE TOTAL. A strategy that does not look at the question
    # scores a whole number of rounds, so its total is lumpy: on five rounds one lucky round
    # is +1.00 and clears any sensible margin over chance. The prayer game's shipped rules
    # score 2.00 of 5 to "the lowest-numbered choice", which is 0.3 of a standard deviation
    # from chance -- a coincidence of which option sorts first, not a cue.
    #
    # What is not a coincidence is a round the strategy gets right EVERY time. Over hundreds
    # of games that is a certainty, and a certainty is a cue by definition, whatever it does
    # to the mean.
    sure = [i + 1 for i, n in enumerate(per_round) if n >= 0.95]
    if not sure:
        return "", ""
    why = (f"is right EVERY time in round{'s' if len(sure) > 1 else ''} "
           f"{', '.join(str(i) for i in sure)} of {rounds} (total {mean:.2f}, chance "
           f"{chance:.2f})")
    if sure == list(range(rounds - len(sure) + 1, rounds + 1)):
        why += (". Those are the LAST rounds, and in a game that fills a board the last piece "
                "has one place left by arithmetic. Check that is all this is")
    return "LOOK", why


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("module", type=Path)
    ap.add_argument("--games", type=int, default=400)
    args = ap.parse_args()
    if not args.module.is_file():
        print(f"no such file: {args.module}")
        return 2

    bad, notes = [], []
    for name, cls in load_rules(args.module):
        probe = build(cls)
        if probe is None:
            continue
        rounds = getattr(probe, "rounds", 0) or 1
        choices = len(getattr(probe, "choices", ()) or (1,))
        chance = rounds / max(1, choices)
        print(f"\n  {name}: {rounds} rounds, {choices} choices, chance is {chance:.2f}")

        ways = [
            ("guessing at random",
             lambda g, seen: random.randrange(len(g.choices))),
            ("always the first box",
             lambda g, seen: 0),
            ("the lowest-numbered choice on offer",
             lambda g, seen: min(range(len(g.choices)), key=lambda i: str(g.choices[i]))),
            ("the only choice not already used",
             lambda g, seen: _unused(g)),
            ("whatever was right last time",
             lambda g, seen: _repeat(g, seen)),
        ]
        for label, how in ways:
            mean, perfect, _, per_round = play(cls, how, args.games)
            call, why = judge(mean, perfect, rounds, per_round, chance, args.games)
            flag = {"WRONG": "   <-- LEARNS NOTHING AND WINS",
                    "LOOK": "   <-- above chance, see below"}.get(call, "")
            if call == "WRONG":
                bad.append(f"{name}: {label} {why}")
            elif call == "LOOK":
                notes.append(f"{name}: {label} {why}.\n         by round: "
                             + " ".join(f"{n:.2f}" for n in per_round))
            print(f"      {label:38s} {mean:5.2f} of {rounds}  "
                  f"perfect {perfect:4d}/{args.games}{flag}")

        # A FIXED ROUND ORDER IS A NOTE, NOT A FAILURE, and the difference is the whole of
        # the judgement this tool cannot make.
        #
        # The prayer game asks its five rounds dawn to night, every time, so the answers can
        # be replayed from memory by round number -- and that is right. The rounds are the
        # hours of a day, the order IS the lesson, and each question names its own time of
        # day, so answering from position and answering from knowledge are the same act.
        #
        # The jigsaw was the opposite. Its question was a PICTURE of a piece, and round number
        # predicted the answer, so the piece could be ignored entirely. Same measurement,
        # opposite meaning.
        #
        # So it is printed and left to a person: does each question state its own subject, and
        # is the order of the rounds part of what is being taught?
        mean, perfect, _, _ = learnt_sequence(cls, args.games)
        fixed = mean >= chance + 0.6 or perfect > args.games // 20
        print(f"      {'the answers learnt by round number':38s} {mean:5.2f} of {rounds}  "
              f"perfect {perfect:4d}/{args.games}"
              f"{'   <-- fixed round order, see below' if fixed else ''}")
        if fixed:
            notes.append(
                f"{name}: the rounds come in the same order every game, so one playthrough "
                f"teaches the answers by position ({mean:.2f} of {rounds}). That is correct "
                f"when the order is the lesson and each question names its own subject -- the "
                f"prayer game's dawn-to-night is. It is a hole when the question is something "
                f"the child could then ignore, as the jigsaw's piece was. Decide which this is.")

    print()
    for note in notes:
        print(f"  LOOK   {note}\n")
    if bad:
        for b in bad:
            print(f"  WRONG  {b}")
        print(f"\n{len(bad)} to fix. MAKING-A-GAME.md section 8.")
        return 1
    if notes:
        # NOT "nothing wins". Something printed above may well win -- a fixed round order
        # scores full marks by replaying from memory -- and it is above as a LOOK precisely
        # because only a person can say whether that is the lesson or the hole. Saying
        # "nothing wins" under a 9.00 of 9 is the one output worse than no checker at all.
        print(f"Nothing failed outright, but {len(notes)} "
              f"{'strategies' if len(notes) > 1 else 'strategy'} that beat chance "
              f"{'are' if len(notes) > 1 else 'is'} printed")
        print("above as LOOK and have not been judged. Read each one before calling this clean.")
        return 0
    print("No lazy strategy in the rules wins outright. What the SCREEN shows is still yours")
    print("to check.")
    return 0


def _unused(game):
    used = set()
    for attr in ("placed", "used", "done_cells", "filled"):
        got = getattr(game, attr, None)
        if isinstance(got, (list, tuple, set)):
            used |= set(got)
    free = [i for i, c in enumerate(game.choices) if c not in used]
    return free[0] if free else 0


def _repeat(game, seen):
    return seen[-1] if seen else 0


if __name__ == "__main__":
    raise SystemExit(main())
