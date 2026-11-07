"""When a game is won, said once.

Harry: "during all games, when a game is completed successfully, no pop up box appears on
main screen, there should be a box 'Well Done' and 2 boxes underneath 'Play again' & 'Exit'".

ONE FUNCTION RATHER THAN SIX COPIES, because the six games disagree about everything except
the question. They call the finished state `done` (Pillar Match, Prayer Day, Qibla Quest,
Build the Salaah), `complete` (the jigsaw) and `finished` (the maze); four of them push state
changes through a `changed` signal and two call `retell` directly. What they have in common is
that something runs after every change, and at that moment the game either is finished or is
not. So each screen answers that one question here and nothing else is shared.

WHY IT HAS TO BE "ONCE" AND NOT "WHENEVER FINISHED". The thing that runs after a change runs
on redraws, theme changes and language changes too, and a finished game stays finished until
somebody starts another. Announcing on each of those would put the box up again every time the
mat repainted behind it, and play a praise phrase each time with it.

The flag lives on the screen rather than in here, so two games cannot share one, and it clears
itself the moment a game is no longer finished -- which is what starting again does. No screen
has to remember to reset anything, which is the kind of thing a sixth game added later would
forget.
"""
from __future__ import annotations

#: Where the flag is kept on the screen. Named here so that a test can clear it without
#: guessing, and so the six games cannot drift into spelling it differently.
ALREADY = "_said_well_done"


def announce_if_won(screen, finished: bool) -> bool:
    """Emit the screen's `won` signal the first time it reports itself finished.

    Returns whether it emitted, which is what the tests assert on: a function that silently
    did nothing and a function that worked both leave the game finished.
    """
    if not finished:
        setattr(screen, ALREADY, False)
        return False
    if getattr(screen, ALREADY, False):
        return False
    setattr(screen, ALREADY, True)
    screen.won.emit()
    return True
