#!/usr/bin/env python3
"""Read a maze layout off its picture and print the LEVEL_DATA entry for it.

WHY THIS EXISTS AT ALL. mosque_maze.Rules carries, per layout, a 160x90 bitmap of where a
child may walk, packed as hex. Until now those three bitmaps had no tool behind them -- they
were made once, somehow, and nothing in the repository could make another. Harry's three new
layouts of 25 November 2026 need three more, and a fourth background later will need a fourth.

WHAT THE BITMAP MEANS, since the sense is easy to get backwards and silent when wrong: a set
bit is FLOOR, somewhere a child may stand. Everything drawn on the picture -- walls, the
mosque, and the pickup drawings themselves -- is clear. The drawings being clear is not an
oversight: PICKUP in Rules lets a child collect a thing from three steps away, so nobody ever
needs to stand on one.

HOW THE FLOOR IS FOUND. Not "darker than" or "brighter than": the old artwork was white line
on black, and these are painted, with a slate floor under green hedges, a pale floor under
brick, and a navy floor under cloud. The floor is simply THE COLOUR MOST OF THE BOARD IS, read
off the middle of the picture, and anything far enough from it is something drawn. That is the
same reasoning board_ground uses in pillar_match, and for the same reason: a rule about
brightness is a rule about one set of pictures.

ISLANDS. Downsampling 1920x1080 to 160x90 leaves specks -- a decorative dot on the floor, a
corner where two walls nearly meet -- and a speck of floor cut off from the rest is a place a
child can be routed to and then be stuck in. Any pocket of floor not joined to the main body
is filled in as wall, and the tool says how much it filled so that a number creeping upwards
is visible rather than quiet.

Run:  python3 tools/maze/build_levels.py <picture.png> [--name hedge]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

WIDTH, HEIGHT = 160, 90

#: How far a pixel may sit from the floor colour and still count as floor, per channel.
#: 40 holds across all three of Harry's layouts: the nearest thing drawn to any of the three
#: floors is the hedge wall at 81, so there is room either side of this number.
TOLERANCE = 40

#: A pocket of floor smaller than this, and cut off from the main body, is filled in. Sized
#: from measurement rather than taste: on Harry's city layout the cut-off pockets are all
#: under 20 cells and the main body is 5,800, so anything in between would do.
ISLAND = 60


def floor_colour(small: np.ndarray) -> np.ndarray:
    """The colour most of the board is, read off the middle of it.

    The middle, because the border is a frame in all three pictures and the frame is not the
    floor. The median rather than the mean: a mean slides towards whatever is drawn.
    """
    inner = small[10:HEIGHT - 10, 10:WIDTH - 10].reshape(-1, 3)
    return np.median(inner, axis=0)


def read_floor(path: pathlib.Path) -> tuple[np.ndarray, dict]:
    picture = Image.open(path).convert("RGB")
    small = np.asarray(picture.resize((WIDTH, HEIGHT), Image.BOX)).astype(int)
    floor = floor_colour(small)
    walkable = np.abs(small - floor).max(2) < TOLERANCE

    # THE MOSQUE IS A BUILDING, whatever colour it happens to be painted. On Harry's city
    # board it is pink on a pale grey floor, and parts of it sit inside TOLERANCE of that
    # floor -- so read off colour alone, the middle of the mosque came out walkable and a
    # child could stroll straight through it. Stamped out by position instead, which is the
    # one thing about the mosque that is identical on all three boards. The rectangle is a
    # little larger than the drawing, which costs a ring of floor nobody needs: the pickups
    # are kept off it anyway and the door is below it.
    x0, y0, x1, y1 = MOSQUE
    walkable[int(y0 * HEIGHT):int(y1 * HEIGHT) + 1, int(x0 * WIDTH):int(x1 * WIDTH) + 1] = False

    label, count = ndimage.label(walkable)
    if count == 0:
        raise SystemExit(f"{path.name}: no floor found at all.")
    sizes = ndimage.sum(walkable, label, range(1, count + 1))
    main = int(np.argmax(sizes)) + 1
    islands = walkable & (label != main)
    others = [int(s) for n, s in enumerate(sizes, start=1) if n != main]
    walkable = label == main

    return walkable, {
        "floor_colour": tuple(int(v) for v in floor),
        "pockets_filled": int(islands.sum()),
        "pockets": int(count - 1),
        # THE SIZE OF THE BIGGEST ONE IS THE ANSWER, not how many there are. Two hundred
        # one-cell specks between wall blocks are nothing; one forty-cell pocket is a corridor
        # the downsample pinched shut, and filling that in walls off part of the maze.
        "biggest_pocket": max(others) if others else 0,
        "walkable": int(walkable.sum()),
    }


#: Where the mosque sits, as a fraction of the picture. The same in all three of Harry's
#: layouts -- measured, not assumed: taking the one island of drawn stuff in the middle that
#: is not joined to the wall network gives x 886-1034, y 489-589 on every one of them, centre
#: (0.500, 0.500) exactly. He drew them from the same template.
MOSQUE = (0.461, 0.453, 0.539, 0.546)

#: Where the footprint mark is, as a fraction. Bottom-left on all three. The start cell is the
#: nearest floor to this, because the mark itself sits on the frame rather than on the floor.
FOOT = (0.045, 0.85)

#: The three corners Harry left clear, as fractions, and how much room a drawing needs at the
#: centre of one. Measured: each of these holds a clear 12x12 block of cells in every layout,
#: while the fourth corner holds 6x7 because the start is in it.
BOXES = (("top-left", 0.05, 0.09, 0.17, 0.29),
         ("top-right", 0.83, 0.09, 0.95, 0.29),
         ("bottom-right", 0.83, 0.71, 0.95, 0.91))

#: How wide a drawing is as a share of the picture's width -- the same two numbers as
#: Screen.BIG_WIDE and Screen.SMALL_WIDE in salaah/mosque_maze.py, where they are used to
#: scale the artwork. They are repeated here rather than imported because this tool must run
#: without Qt; test_no_drawing_lies_across_a_wall is what holds the two copies together, and
#: it does it from the finished data rather than by comparing the numbers.
BIG_WIDE, SMALL_WIDE = 0.06875, 0.03125

#: Cells of clear floor a drawing needs around its centre: half its longest side, plus the
#: half cell between a wall cell's centre and its near edge. Guessing these instead of working
#: them out was a real fault and it shipped as far as the test suite: 5.0 was called "a little
#: over half" of a drawing 12 cells across, which is under half, and the hedge Qur'an ended up
#: lying on a hedge.
#:
#: Both shares come from what the pictures measure, not from what looks nice in isolation:
#:
#: - 0.06875 (11 cells across) and not 0.075 (12), because the three corners Harry cleared
#:   hold 6.0 cells of room at best, so 12 cannot sit in any of them without its outer half
#:   cell on a wall. 11 fits with nothing spare.
#: - 0.03125 (5 cells across) and not 0.042 (6.7), because the corridors of all three mazes
#:   are 4 cells wide -- median room 2.0 in every one of them -- so a drawing 6.7 across only
#:   ever fitted in the rare open pockets. The hedge and the city have enough of those spread
#:   about to hide the problem; the Night Clouds pockets are all in one corner, which is why
#:   six of its pickups came out in a heap there.
ROOM_BIG = WIDTH * BIG_WIDE / 2 + 0.5
ROOM_SMALL = WIDTH * SMALL_WIDE / 2 + 0.5

#: How far a route to an item may wander beyond the straight-line distance, as a SHARE of that
#: distance rather than a flat number of steps. Flat was the first attempt and it was quietly
#: wrong: a cell far from the start piles up detour simply by being far, so a fixed allowance
#: pushed every item into the quarter of the maze nearest the child's feet.
WANDER = 0.35


def pack(walkable: np.ndarray) -> str:
    """The 160x90 bitmap as hex, bit n of byte n//8, exactly as Rules.restart unpacks it."""
    out = bytearray((WIDTH * HEIGHT + 7) // 8)
    for index in range(WIDTH * HEIGHT):
        if walkable[index // WIDTH, index % WIDTH]:
            out[index // 8] |= 1 << (index % 8)
    return out.hex()


def walk_from(walkable: np.ndarray, origin: tuple[int, int]) -> dict:
    """Every cell reachable from `origin`, and how many steps away it is."""
    from collections import deque
    steps = {origin: 0}
    queue = deque([origin])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and walkable[ny, nx] and (nx, ny) not in steps:
                steps[(nx, ny)] = steps[(x, y)] + 1
                queue.append((nx, ny))
    return steps


def place(walkable: np.ndarray, count: int = 10) -> dict:
    """Where the start, the ten pickups and the mosque go, read off the floor.

    The three corner pickups first, because their places are nearly fixed; then the rest by
    taking, each time, the cell furthest from everything already placed. Furthest-first rather
    than at random: random wants rejecting and re-rolling to stop two landing in one corridor,
    and this cannot produce that in the first place.
    """
    room = ndimage.distance_transform_edt(walkable)
    floor = [(x, y) for y in range(HEIGHT) for x in range(WIDTH) if walkable[y, x]]
    want = (FOOT[0] * WIDTH, FOOT[1] * HEIGHT)
    start = min(floor, key=lambda c: (c[0] - want[0]) ** 2 + (c[1] - want[1]) ** 2)
    steps = walk_from(walkable, start)

    mosque = (int(MOSQUE[0] * WIDTH), int(MOSQUE[1] * HEIGHT),
              int(MOSQUE[2] * WIDTH), int(MOSQUE[3] * HEIGHT))
    chosen = []
    for name, x0, y0, x1, y1 in BOXES:
        here = [c for c in steps
                if x0 * WIDTH <= c[0] <= x1 * WIDTH and y0 * HEIGHT <= c[1] <= y1 * HEIGHT
                and room[c[1], c[0]] >= ROOM_BIG]
        if not here:
            raise SystemExit(f"no room for a big drawing in the {name} corner.")
        mid = ((x0 + x1) / 2 * WIDTH, (y0 + y1) / 2 * HEIGHT)
        chosen.append(min(here, key=lambda c: (c[0] - mid[0]) ** 2 + (c[1] - mid[1]) ** 2))

    def wander(cell):
        direct = abs(cell[0] - start[0]) + abs(cell[1] - start[1])
        return (steps[cell] - direct) / max(direct, 1)

    def half(index):
        """Half the longest side of drawing `index`, in cells. The big three come first."""
        return (ROOM_BIG if index < len(BOXES) else ROOM_SMALL) - 0.5

    #: Two drawings must be at least the sum of their halves apart or they overlap on screen.
    #: Leaving this out is what put six of the Night Clouds pickups in one heap in the
    #: top-right corner: that maze is tight enough that the wander filter left a pool of a
    #: few cells in one corner, and "furthest from the others" inside a pool that small still
    #: means next to them. The tool had no way to say it was stuck, so it produced a pile.
    def spaced(cell, placed):
        return all((cell[0] - d[0]) ** 2 + (cell[1] - d[1]) ** 2 >= (half(len(placed)) + half(i)) ** 2
                   for i, d in enumerate(placed))

    allowance, relaxed = WANDER, []
    while True:
        pool = [c for c in steps
                if not (mosque[0] - 5 <= c[0] <= mosque[2] + 5 and mosque[1] - 5 <= c[1] <= mosque[3] + 5)
                and (c[0] - start[0]) ** 2 + (c[1] - start[1]) ** 2 > 12 ** 2
                and wander(c) <= allowance and room[c[1], c[0]] >= ROOM_SMALL]
        picks, stuck = list(chosen), False
        for _ in range(count - len(BOXES)):
            room_for = [c for c in pool if spaced(c, picks)]
            if not room_for:
                stuck = True
                break
            far = max(room_for, key=lambda c: min((c[0] - d[0]) ** 2 + (c[1] - d[1]) ** 2
                                                  for d in picks))
            picks.append(far)
            pool.remove(far)
        if not stuck:
            chosen = picks
            break
        if allowance > 3.0:
            raise SystemExit("no way to place ten drawings in this maze without two overlapping.")
        allowance = round(allowance + 0.35, 2)
        relaxed.append(allowance)

    # The door is the middle of the mosque's foot; the approach is the first floor below it.
    door = ((mosque[0] + mosque[2]) // 2, mosque[3])
    below = [c for c in steps if abs(c[0] - door[0]) <= 3 and c[1] > door[1]]
    approach = min(below, key=lambda c: (c[1], abs(c[0] - door[0]))) if below else door
    return {"start": start, "items": chosen, "approach": approach, "mosque": mosque,
            "steps": steps, "room": room, "allowance": allowance, "relaxed": relaxed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("picture", type=pathlib.Path)
    ap.add_argument("--name", default=None, help="the name for the LEVEL_DATA entry")
    ap.add_argument("--preview", type=pathlib.Path, default=None,
                    help="write the bitmap out as a picture, to be looked at")
    ap.add_argument("--entry", action="store_true",
                    help="print the whole BACKGROUNDS entry, not just the mask")
    args = ap.parse_args()

    walkable, found = read_floor(args.picture)
    name = args.name or args.picture.stem

    print(f"  {name}")
    print(f"     floor colour      {found['floor_colour']}")
    print(f"     walkable          {found['walkable']} cells "
          f"({100 * found['walkable'] / (WIDTH * HEIGHT):.1f}% of the board)")
    print(f"     pockets filled in {found['pockets_filled']} cells "
          f"in {found['pockets']} patches cut off from the rest, "
          f"biggest {found['biggest_pocket']} cells")
    if found["biggest_pocket"] > ISLAND:
        print(f"     ^^ LOOK AT THE PREVIEW. A pocket of {found['biggest_pocket']} cells is too")
        print("        big to be a speck between two wall blocks. That is the shape of a")
        print("        corridor pinched shut by the downsample, and filling it in walls off")
        print("        part of the maze a child is meant to be able to reach.")

    if args.preview:
        Image.fromarray((walkable * 255).astype(np.uint8)).resize(
            (WIDTH * 6, HEIGHT * 6), Image.NEAREST).save(args.preview)
        print(f"     preview written   {args.preview}")

    if not args.entry:
        print(f"\n'mask': '{pack(walkable)}',")
        return 0

    put = place(walkable)
    start, items, approach = put["start"], put["items"], put["approach"]
    steps, room = put["steps"], put["room"]
    print(f"     start             {start}")
    print(f"     approach          {approach}  ({steps.get(approach, '??')} steps away)")
    apart = min(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                for i, a in enumerate(items) for b in items[i + 1:])
    print(f"     ten pickups, furthest {max(steps[c] for c in items)} steps away, "
          f"clearance {min(room[c[1], c[0]] for c in items):.1f} at the tightest, "
          f"{apart:.1f} cells apart at the closest")
    if put["relaxed"]:
        print(f"     ^^ the wander allowance had to go {WANDER} -> {put['allowance']} to fit ten")
        print("        drawings in without two of them overlapping. That is this maze being")
        print("        tight rather than anything wrong; it means more of the pickups sit off")
        print("        the straight line to the mosque than in the other two.")
    for n, c in enumerate(items):
        print(f"        {n + 1:2d}  {str(c):10s} {steps[c]:4d} steps  "
              f"{room[c[1], c[0]]:.1f} cells of room  {'BIG' if n < 3 else ''}")
    if not all(c in steps for c in items):
        raise SystemExit("a pickup is not reachable from the start.")

    norm = tuple((round((c[0] + 0.5) / WIDTH, 6), round((c[1] + 0.5) / HEIGHT, 6)) for c in items)
    print("\n    {")
    print(f"        'name': {name!r},")
    print(f"        'asset': 'mosque-maze-{name}.png',")
    print(f"        'mask': '{pack(walkable)}',")
    print(f"        'start': {tuple(start)},")
    print(f"        'items': {tuple(tuple(c) for c in items)},")
    print(f"        'item_norm': {norm},")
    print(f"        'approach': {tuple(approach)},")
    print("    },")
    return 0


if __name__ == "__main__":
    sys.exit(main())
