"""Journey to the Mosque: a native dual-touch MySalaah maze game.

The 16-inch touch display contains only the approved maze artwork and the live
footprint trail. The 7-inch companion shows the hint, translated instructions,
progress, difficulty, New Game and Exit. All state stays in memory.
"""
from __future__ import annotations

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette
from .winning import announce_if_won


class Rules:
    """Pure routing, collection and gate rules over the three artwork masks.

    WHAT A CHILD COLLECTS, and why it is named. The game arrived with five, seven and nine
    pickups per level and nothing identifying any of them: they were bare cell coordinates and
    the only words were "Collect every item to open the gate". A child who finished it had
    solved a maze and touched some dots, and the mat had called it a journey to the mosque.

    That is the fault six games were taken out for in October 2026 -- see the note in
    ui.build_corner about putting an Islamic name on a secular drill -- so rather than leave it
    or cut the game, each pickup is one of the things you do before you pray, in the order a
    child meets them. The first five are the beginner level, seven is medium, nine is expert,
    so the harder maze also teaches more. Each one says what it is when it is picked up.

    None of these words has been read by anyone qualified. They are drafted here like the rest
    of the mat's text and marked for review.
    """

    #: Positional against each level's `items` tuple: the nth cell collected is the nth key.
    ITEM_KEYS = ("wudu", "clothes", "adhan", "mat", "calm",
                 "miswak", "scent", "right_foot", "salaam")

    WIDTH = 160
    HEIGHT = 90
    MAX_TOUCH_ROUTE = 14
    LEVEL_DATA = (
        {
            'name': 'beginner',
            'asset': 'mosque-maze-beginner.png',
            'mask': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff1f000000000000000000000000000000000000f81f000000000000000000000000000000000000f89fffffff3ffeffffff7ffeffffff7ffcfffffff99fffffff3ffeffffff7ffeffffff7ffcfffffff99fffffff3ffeffffff7ffeffffff7ffcfffffff99fffffff3ffeffffff7ffeffffff7ffcfffffff99fffffff3ffeffffff7ffeffffff7ffcf7fffff99fffffff3ffeffffff7ffeffffff7ffcc3fffff99f1f00f03efe0300e07ffe0700c07ffca303f8f99f1f00f03efe0300e07ffe0700c07ffcf203f8f99f1f00707cfeffffff7ffeffffff7f7ef003f8f99f1f0070fcffffffffffffffffffff3ff003f8f99f1f0070f8ffffffffffffffffffff3ff803f8f99f1f0070fcfffffffffffffffffffffffe03f8f99ffffffffffffffffffffffffffffffffefffff99ffffffffffffffffffffffffffffffffffffff99fffffff7f0080ff00000080ff0100fefffffff99fffffff3f0080ff00000000ff0000fcfffffff99fffffff3f0080ff01000080ff0100fcfffffff99fffffff3ffeffffff7ffeffffff7ffcfffffff91f00fcf33ffeffffff7ffeffffff7ffccf3f00f81f00fcf33ffeffffff7ffeffffff7ffccf3f00f8fffffcf33ffeffffff7ffeffffff7ffccf3ffffffffffcf33ffeffffff7ffeffffff7ffccf3ffffffffffcf33ffeffffff7ffeffffff7ffccf3ffffffffffcf33ffeff0300000000c0ff7ffccf3ffffffffffcf33ffeff0300000000c0ff7ffccf3ffffffffffcf33ffefff3ffffffffcfff7ffccf3ffffffffffcf3fffffff3ffffffffcfffffffcf3ffffffffffcf3fffffff3ff7ffeffcfffffffcf3fffff1f00fcf3fffffff3ffffffffcfffffffcf3f00f81f00fcf3fffffff3cf7ffefbcfffffffcf3f00f8ffffff030000fcf3cf1ff8ffcf3f0000c0ffffffffffff030000fcf3ef0ff0ffcf3f0000c0fffffffffffffffffffff3cf0ff0f9cfffffffff73ffffff7ffefffffffff3cf07f0f9cfffffffff01ffffff1ffefffffffff3cf0180f9cfffffffff01fffffffffffffffffff3cf0000f9cfffffffff01ffffff7ffefffffffff34fc003f9cfffffffff8dffffff1ffffffffffff34fc803f9cfffffffff09feffffffff030000fcf34fea5ff9cf3f0000c0ffffffffffff030000fcf34fca5bf1cf3f0000c0ffffff1f00fcf3fffffff307e002f0cfffffffcf3f00f81f00fcf3fffffff3ffffffffcfffffffcf3f00f8fffffcf3fffffff3ff1ffcffcfffffffcf3ffffffffffcf3fffffff3ffffffffcfffffffcf3ffffffffffcf37ffeff0300000000c0ff7ffecf3ffffffffffcf33ffeff0300000000c0ff7ffccf3ffffffffffcf33ffeffffffffffffffff7ffccf3ffffffffffcf33ffeffffffffffffffff7ffccf3ffffffffffcf33ffeffffffffffffffff7ffccf3ffffffffffcf33ffeffffffffffffffff7ffccf3ffffffffffcf33ffeffffffffffffffff7ffccf3fffff1f00fcf33ffeffffffffffffffff7ffccf3f00f81f00fcf33f0080ff00000000ff0000fccf3f00f89fffffff7f0080ff00000080ff0000fefffffff99fffffffffffffffff7ffefffffffffffffffff99fffffffffffffffff7ffefffffffffffffffff99fffff7ffeffffffff7ffeffffffff3ffcfffff99fffff3ffcffffffff7ffeffffffff5ffafffff99fffff3ffcffffffff7ffeffffffffbff9fffff99f1f00bcfdffffffff7ffeffffffff3f3900f8f99f1f00bc3dfe0700e07ffe0700e07f1c3900f8f99f1f00bc3ffe0700e07ffe0700e07fbc3d00f8f99f1f003c3cfe0700e07ffe0700e07ffc3f00f8f99f1f003c3cfeffffff7ffeffffff7ffc3f00f8f99fffffff3ffeffffff7ffeffffff7ffcfffffff99fffffff3ffeffffff7ffeffffff7ffcfffffff99fffffff3ffeffffffffffffffff7ffcfffffff99fffffff3ffeffffffffffffffff7ffcfffffff99fffffff3ffeffffffffffffffff7ffcfffffff99fffffff3ffeffffffffffffffff7ffcfffffff91f000000000000000000000000000000000000f81f000000000000000000000000000000000000f8ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            'start': (14, 45),
            'items': ((34, 18), (129, 16), (139, 45), (32, 69), (128, 68)),
            'item_norm': ((0.203125, 0.199074), (0.809896, 0.194444), (0.880208, 0.490741), (0.203125, 0.768519), (0.802083, 0.763889)),
            'approach': (80, 55),
            'goal': (80, 49),
            'item_cells': ('000000000000000000000000000000000000000800800300f000001f00e003007c0000070000000000000000000000000000000000000000',
                           '00000000000000000000000000000000000000c00100fc00c01f00fc01c01f00fc03803f00e0030018000000000000000000000000000000',
                           '00000000000000000000000000000000c03f00f80f00ff01e03f00fc0780ff00000100000000000000000000000000000000000000000000',
                           '00000000000000000000006000000c00c003007800801f00e003007c00800f00f801003e00c0070000000000000000000000000000000000',
                           '00000000000000000000000000000000000000fc00801f00f80700ff00e01f00f801001e0000000000000000000000000000000000000000'),
            'gate_norm': (0.471354, 0.5, 0.528646, 0.615741),
        },
        {
            'name': 'medium',
            'asset': 'mosque-maze-medium.png',
            'mask': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff0f000000000000000000000000000000000000f00f000000000000000000000000000000000000f0cffffffffffff9fffffffffdff9fffffffe7fff3cffffffffffff9fffffffffdff9fffffffe7fff3cffffffffffff9fffffffffdff9fffffffe7fff3cffffffffffff9fffffffffdff9fffffffe7fff3cf0700801f00f8010000fcfd7d02e80f0000f8f3cf0700801f00f8010000f8fd7c00c8070000e0f3cfe7ff9fdfffffffdffffffdfcffcfe7ffffeff3cfe7ff9fdfffffffdffffffdfcffcfe7ffffeff3cfe7ff9fdfffffffdffffffdf1ffcfe7fffdeff3cfe7ff9bdfffffffdffffffdffffcfe7fff9eff3cfe7e799dfffffffdffffffdffffcfe77ff0eff3cfe7e791df0f00c0df0f000000c0cfe71f18e0f3cfffe791df0f00c0df0f000000c0cfffaf1fe0f3cfffe799ffffffdfdfffffffffcfcfff379efff3cfffe79fffffffdfffffffffffcfcfff6f9ffff3cfffe79fffffffdfffffffffffcfcfffbf9ffff3cfffe79fffffffdfffffffffffcf0f00f89ffff30fc0e79fffffffdfffffffffffcf0f00f89ffff30fc0070000003e1f00800f00c0cffffff98107f0ffcfffcfffff3f1f00800f00c0cffffff98107f0ffcfffcfffff3fffff9fffffcfcffffff9ffe7ffffcfffcfffff3fffff9fffffcfcffffff9ffe7ffffcfffcfffff3fffff9fffffcfcffffff9ffe7ffffcfffcfffff3fffff9fffffcf0f00f0f9ffe7ffffcf9fcfffff2fffff9fffffcffffff7f9ffe7ffffcf9fcf0300003f00000000fefffff701c0e7ff0fc09fcff3cfffbfffffff7ffefffff701c007f0cfff9fcff3cfffbfffffff7ffefffff7f9cf0ff0cfff9fcff3cfffbfffffff7ffefffff7f9cffff3cfff9fcff3cfffbfffbfff7ffefffff7f9cffff3cfff9ffff3cfffbfff7fff7f0000e0f7f9cffff30f0080fff3cff7bfff7fff7f0000e0f7f9cffff30f0080fff3cff7bf9f3ffe7cfe7ffef7f9cffff3ffff9ffff3cff7bf9f0ffc7dfe7ffefff90c00f0ffff9ffff3cf07809f0ff87cfe7ffefff91c00f0fff11f00f0cf07809f07f87cfe7ffefff9fcffffffff1f00f0cfffbf9f01e07cfe7ffefff9fc03ffffff9fffffcfffbf9f00c07cfe7f3e00f8fc03fffff89fffffcfffbf9f40807c007e3e00f8fc03ffffff9fffffcfffbf9f0aa37c7e7efefffffc33ffffff9fffffcfffbf9f0aac7c7e7efefffffcffff0fc09f03000f00bf0f0003787e7efeffff0000f00fc09f03000f00bf0f0002787e7efeffff0000f0cfdfffff3cff3fbfff1fff7f7e7e0000fffffff3cfdfffff3cff3fbfff1fff7f7e7e0000fffffff3cfdfffff3cff3f3f000000007efeff3ffffffff3cfdfffff3cff3f3f000000007ffeff3ffffffff3cfdfffff3cff3fffff3fffff7ffeff3ffffffff3cf0f00f83c003effff3fffff7ffeff3f1f00e0f3cffffff97c003effff3fffff7ffeff3f1f00e0f3cffffff9fc7f3effff3fffff7f00003fffffe7f3cffffff9fc7f3e00003c1f007e00003fffffe7f3cffffff9fc7f3e00003c1f00feff3f3fffffe7f30fe0fff9fc7ffeffff3cff7ffeff3f3fffffe7f30fe0fff9fc7ffefffffcff7ffeff3f3f00c0e7f3cfffedf9007cfefffffcff7ffeff3fffffdfe7f3cfffeff9007cfefffffcff7ffeff3fffffcfe7f3cfffedf9ff7dfefffffcff7f00003effffcfe7f3cfffe1f9ff7d0000ff3c007c00003effffcfe7f3cfffeff9ff7d0000e77c007cfeff3f00c0cfe7f3cfe7cff9fffdff3fe7fcff7cfeff3f00c0cfe7f3cfe7fff9fffdff3fe7ffff7cfeffffffcfcffff3cfe7fff9f9fdff3fe7ffff7cfeffffffcfcffff3cfe7fff9f9fddf3fe7ffff7cfeffff3fcccffff3cf0700f8f9018e3fe7ffff7c3e00001ccecffff3cf0700f8f901863f0700fc7c3effff1cc80fe0f3cffffffff9ffef3f0f00fc7c3effff1cc81fe0f3cffffffff9ffaf3ffffffcfc3fffff3cccffe7f3cffffffff9ffaf3ffffffcfc3fffff7cceffe7f3cffffffff9ff8f3ffffffcfc3ffffffccfffe7f3cf070000f8ff8f3ffffffc00007ffefccfffe7f3cf070000f8f9030000f8fc00007ffe0000c0e7f3cffffffffff9030000f8fcffff7ffeffffcfeff3cffffffffff9fffffffffcffff7ffeffffcffff3cffffffffff9fffffffffcffff7ffeffffcffff3cffffffffff9fffffffffcffff7ffeffffcffff30f000000000000000000000000000000000000f00f000000000000000000000000000000000000f0ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            'start': (11, 45),
            'items': ((27, 20), (99, 14), (136, 19), (149, 46), (19, 64), (53, 74), (129, 71)),
            'item_norm': ((0.161458, 0.208333), (0.619792, 0.162037), (0.854167, 0.203704), (0.929688, 0.49537), (0.117188, 0.712963), (0.333333, 0.819444), (0.799479, 0.805556)),
            'approach': (80, 55),
            'goal': (80, 49),
            'item_cells': ('00000000000000000000000000000400c000003c00800700f000001e00000000000000000000000000000000000000000000000000000000',
                           '000000000000000000000000000000000000001c008001003000003e00c00700000000000000000000000000000000000000000000000000',
                           '00000000000000000000000000001000000700f001007f00f007007f00f007007e0080070060000000000000000000000000000000000000',
                           '00000000000000000000000000000000e00700fe01c03f00f80700ff00e01f00000000000000000000000000000000000000000000000000',
                           '000000000000000000000000000000000000003000800f003003006600c00f00e00100300000060000000000000000000000000000000000',
                           '00000000000000000000000000000800800300f800001f00e003006c00800d00f001003e0000000000000000000000000000000000000000',
                           '000000000000000000000000000000000000000000000300f801003f00e00700fc00801f00e0010000000000000000000000000000000000'),
            'gate_norm': (0.466146, 0.49537, 0.523438, 0.611111),
        },
        {
            'name': 'expert',
            'asset': 'mosque-maze-expert.png',
            'mask': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff0f000000000000000000000000000000000000f0efff0ffeffffdffffffdffcfffff7ffffffffff7effffffeffffdffffffdffcfffff7ffffffffff7effffffeffffdffffffdffcfffff7ffffffffff76ff8fffe3f00c0ffff3d00ccffff7f0f3c0000f76f30f0003c00c003c03d00ce7d00700fbeff3ff7ef33ffff3dffdffbffbdffcffcff77efbfff3ff7ef33ffff3dffdffbffbdffcffcff77efbfbf3ff7ef33ffff3dffdffbffbdffcff1ff77efbf5f3ff7ef33ffef3dffff3b00bcfbcfff9ff7ef80cf3ef70f3080c73d07fc3b00bc7bc0ff9ff7effcbf3ff70ff0bfc73de7ff3bffbffb0f009cf7effcc33ff7efffbfcf3de7ff3bffbffb0f009cf7effce101f7efffbfdf01e7ff3bffbffbffff9c07e0fcf901f7efffbfffcde701380f80fbffff9cfffffcf3f9f7ef01bcffffe7fd3f0f800300f09cffff00fff9f7eff93c00fce7fd3ffffbfffff39cffff01fff9f7eff93c00fce7fd3ffffbfffff380ffff3fff79f0eff9fcfffde03d38ff03e0fff30000fe3fff39f0eff9fcff3de03d308003c0fff31f00fe3f0f38ffeff9fcfffdfffd7380ffcf81f3ffff1e30ff3fffeff900e0fdfffdf39fffcf9ff3ffff0e30ff3fffeff901e0fdfffdf39fffcf9ff3ffffce3fff7fffeff9ffef01fffcf39f7fc09f0300f8ce3fff7fffeff9ffef010f80f39f7fc09ff3fff9ce3f0000f0fff9ffef7fff9f03807fff9ff3fff9c0f3f7fff70fc001ee7fff9ff3ff7fff9ff3fff9c0f3f7fff70fc0f9ef7fff9ff3ff7fff9ff3fff9fff3f7fff7ffdff90f70ff9ff30100008003f0f9fff3f701f7ffdff9ff73ff9ff30100008003f0f9fff3f700f7ffdff9ff7300fcf3fdffff9fff33001e70f07cf7ffdf01bff3fffdf3fdffff9fff33001e70f07cf70fc0010ff3fffdf3fdbfff9fff33ff9fffff7cf7efff3fe7f3fffdf3bd7fff9ee833ff9fffff7cf7efff3fc3f3fffdf3b97fff1ec033ff9fefcc7cf7efff3fff03e001f0b93ffe9eff33ff9fefc07cf70f003eff03e0fffff90ff89fff330780efc07cf7ffff3ffff3e7ffffb90ff89eff3fe7ffeff17cf07fff3f00f0e7ffffb90ff89eff3fe7ffefc0fcf71ffefff7ffe78103b801c09eff3fe7ffeffffcf7fffffff7ffe78103bc01801ec03fe7ffeffffcf70fffe1f7ffe79df3bd00809edf3f07780f0080f7bfffe7f7ffe79df3bd0aa89edf010f70ffff9ff7ffffe7f700e79df3390aa89edfffff73ffff9ff70ff0e7f700e79df31920009cdfffff7bffff9ff7efffe7f77ee09dfff91f389edfffff73ffff9ff7efffe7f77ee09dfff91ffc9f1f00e073007880f7efff07f07eff9dfff97fff9f1f00e0fbff7980f7ef0107f07eff9dff01000080dfffefffff79fff7ef00feff7eff1dc0ff7fffffdfffefffff79fff7ef7cfeff7eff1dc0ff7fffffdfbf0f00e079fff7ef7cfeff7e0ffccfff7fffffdfbf0f00e079fff7ef7cfeff0eefffcfff7fffffc11fefffef7900f0ef7cc001eeefffcf017c00e0c05defffeff9fff7effccffdefefffcff9fcffe7fffdefffeff9fff7effccffdefefffcff9fcffe7fffdef01fff9fff70fbccffdef0f00cffdfcffe7ff01e001ff01c0f7efefcffdefff7f0ff8fcffe7ff01e03dfff9dff7efefce01eeff7f0ffc00c007c0fdff3dfff9dff7efefce01eeff7fffff00c007c0fdff3d03f8dff7efbfcfffeeff7fffffffdfffdffdff3df3ffdff7efffceff0e0078ffffffdfffdf3d003cf37fdcf7eff9cefffeff79e00180dfffdf3dff3ff3ffdcf7eff90ff0feff79c0fd9fdfffdf3dff3ff3ffdcf7eff90ff0fefff9cffd9f1f80df3dff3f73001cf0ef01e0f7fefff9cffd9fdf9fc33dff3f3300fcf7effffff700f0b9cffd9fdf9fc33d070073fffff7effffff7fff319cf7d1fc09ffb3ff7ff3ffffff7effffff7fff319cf7d1fc09ffb3ff7ff7fdbfff70ffcfff7ff3378cf7dffff9ffb3ff7ff7f8f03f7ef3c80f7ff3358cf7fffff9ffb00f701008973f7effcbf07e0335fcf7fffff9ffb80f701008773f7effcbfc7ef331fcf7f07009cfbfff7fdffdb73f7effcbfffff33ff0f7007009cfbfff7fdffff73f7ef00bcffff33000060e7ff1c00c0f7fdffff73f7ef00bcff3f3000c07fe7ff1c00c0f73d000070f7efff3f00ffffffff7ff7fffcffcfff3d0000f0f7efffff3fffffffff7ffff0fcffcffffdfffffff7efffff3fffffffff3ffff0fcffcffffdfffffff70f000000000000000000000000000000000000f0ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            'start': (10, 44),
            'items': ((29, 14), (98, 12), (140, 15), (30, 39), (138, 39), (14, 62), (54, 74), (110, 58), (139, 75)),
            'item_norm': ((0.177083, 0.166667), (0.614583, 0.138889), (0.875, 0.175926), (0.182292, 0.435185), (0.864583, 0.453704), (0.088542, 0.694444), (0.338542, 0.805556), (0.690104, 0.634259), (0.875, 0.833333)),
            'approach': (80, 55),
            'goal': (82, 50),
            'item_cells': ('0000000000000000000000000000000000000000000000004000001c00800300f800001f0080030000000000000000000000000000000000',
                           '0000000000000000000000000000000000000030000007006000001c00800f00e00000000000000000000000000000000000000000000000',
                           '00000000000000000000000000000000000000c001007c00c01f00fc01c01f00fc01801f00e0010018000000000000000000000000000000',
                           '000000000000000000000000000000000000007000000f00f801000f00e00100000000000000000000000000000000000000000000000000',
                           '000000000000000000000000000000000000000000000000000000fe01c03f00f80700ff00e01f0060000000000000000000000000000000',
                           '000000000000000000000000000000000000000000000000e003006c00800c00f001003c00000e00c301600000fc3f80ff07f0ff00000000',
                           '000000000000000000000000000000000003007000001e00e003007800000d00f001003e00c0070000000000000000000000000000000000',
                           '000000000000000000000000000000000000002000001f00e003003800000500000000000000000000000000000000000000000000000000',
                           '00000000000000000000000000000000000000f000003f00e00f00fc01803f00f003003c0000000000000000000000000000000000000000'),
            'gate_norm': (0.46875, 0.49537, 0.526042, 0.611111),
        },
    )

    def __init__(self):
        self.difficulty = 0
        self.restart()

    @property
    def level(self):
        return self.LEVEL_DATA[self.difficulty]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def gate_open(self) -> bool:
        return len(self.collected) == len(self.items)

    @property
    def finished(self) -> bool:
        """Inside the mosque with the gate open -- ANYWHERE inside it, not on one flagstone.

        Harry, 15 November 2026: "when completed and clicked mosque, no well done message or
        sound appeared." He was doing exactly the right thing and the game was not listening.

        This used to be `player == goal`: one named cell. Once the gate opens the mosque is a
        room a child can walk about in, and tapping it lands them wherever the tap was nearest
        -- so the game ended only if they happened to touch the one cell that counted.
        Measured by tapping every spot inside the mosque from the door: it finished 1 time in
        117 on beginner, 6 in 117 on medium, 30 in 117 on expert. He thought the expert maze
        was unfinishable. It was the other two that were nearly impossible to finish.

        The journey is called Journey to the Mosque. Arriving at the mosque is arriving.
        """
        return self.gate_open and (self.player == self.goal or self.player in self.inside)

    def restart(self) -> None:
        level = self.LEVEL_DATA[self.difficulty]
        packed = bytes.fromhex(level["mask"])
        self.active = {
            (index % self.WIDTH, index // self.WIDTH)
            for index in range(self.WIDTH * self.HEIGHT)
            if packed[index // 8] & (1 << (index % 8))
        }
        self.start = tuple(level["start"])
        self.items = tuple(tuple(cell) for cell in level["items"])
        self.item_norm = tuple(tuple(point) for point in level["item_norm"])
        self.item_cells = tuple(self._unpack_item(level["item_cells"][index], cell)
                                for index, cell in enumerate(self.items))
        self.item_reach = tuple(self._near_enough(cell) for cell in self.items)
        self.gate_cell = tuple(level["approach"])
        self.goal = tuple(level["goal"])
        self.inside = self._the_mosque()      # needs goal, so it comes after it
        self.gate_norm = tuple(level["gate_norm"])
        self.player = self.start
        self.collected = set()
        self.last_item = None
        self.route = []
        self.trail = [self.start]

    #: How far either side of an item's own cell its drawing is recorded.
    ITEM_REACH = 10

    #: How close a child has to come to pick something up, in steps along the floor.
    #:
    #: Harry, 15 November 2026: "when collecting items, you have to be very precise and go
    #: over with your footprints, make the area on & around the object easier, so it becomes
    #: collected rather than finding its sweet spot ;)". It was one cell -- the single floor
    #: cell under a drawing that is five or six cells wide -- so a child could walk over the
    #: lantern and not pick it up, which is a rule nobody can see and nobody would guess.
    #:
    #: Counted in STEPS ALONG THE FLOOR rather than as a distance, so it cannot be collected
    #: through a wall: three steps round a corner is three, three steps through a wall is not
    #: a route at all. Generous is the point, magic is not.
    PICKUP = 3

    def _the_mosque(self) -> frozenset:
        """The floor sealed inside the mosque wall: what counts as having arrived.

        Worked out rather than written down, by walking out from the goal over the floor
        WITHOUT the gate -- so it is the pocket the wall encloses, whatever shape that is. If
        a future map's mosque is a different shape this still knows where inside is, and if
        somebody leaves a hole in a wall this grows to the whole maze, which the sealing test
        is watching for.
        """
        start = [cell for cell in self._cardinal(self.goal) if cell in self.active]
        found = set(start)
        queue = list(start)
        cursor = 0
        while cursor < len(queue):
            for near in self._cardinal(queue[cursor]):
                if near in self.active and near not in found:
                    found.add(near)
                    queue.append(near)
            cursor += 1
        return frozenset(found)

    def _near_enough(self, item) -> frozenset:
        """The floor a child can be standing on and still have picked this up. See PICKUP."""
        steps = {item: 0}
        queue = [item]
        cursor = 0
        while cursor < len(queue):
            current = queue[cursor]
            cursor += 1
            if steps[current] >= self.PICKUP:
                continue
            for near in self._cardinal(current):
                if near in self.active and near not in steps:
                    steps[near] = steps[current] + 1
                    queue.append(near)
        return frozenset(steps)

    @classmethod
    def _unpack_item(cls, hexed: str, centre) -> frozenset:
        """The cells one pickup's DRAWING covers, which is not what `active` can tell you.

        WHY THIS IS STORED RATHER THAN WORKED OUT. The maze mask was derived from the artwork,
        so it calls an item's own drawing a wall exactly as it calls a wall a wall -- the only
        floor cell an item has is the single one a child stands on. Asking the mask which
        pixels belong to the water drop gets the answer "none of them", and an erase clipped
        to floor cells rubbed out the gap around a drawing and left the drawing.

        What separates a drawing from a wall is SHAPE: a wall is a long run that leaves any
        window you put around an item, and an item is a small thing that does not. That is a
        connected-component question over the artwork -- far too slow to ask while a child is
        playing, and pointless to ask twice -- so it was asked once and the answer written
        down here, the same way the maze's own walls are.

        Recorded in CELLS rather than pixels because it is 1.5KB that way and 52KB the other.
        The two only share a cell where a wall passes within a pixel or two of a drawing, and
        there the wall loses that corner; see the erasing note in Screen.paintEvent.
        """
        packed = bytes.fromhex(hexed)
        span = cls.ITEM_REACH * 2 + 1
        cx, cy = centre
        return frozenset(
            (cx - cls.ITEM_REACH + n % span, cy - cls.ITEM_REACH + n // span)
            for n in range(span * span)
            if packed[n // 8] & (1 << (n % 8))
        )

    def cycle_difficulty(self) -> None:
        self.difficulty = (self.difficulty + 1) % len(self.LEVEL_DATA)
        self.restart()

    def _cardinal(self, cell):
        x, y = cell
        return ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1))

    def neighbours(self, cell):
        linked = {other for other in self._cardinal(cell) if other in self.active}
        if self.gate_open:
            if cell == self.gate_cell:
                linked.add(self.goal)
            elif cell == self.goal:
                linked.add(self.gate_cell)
        return linked

    def distances(self, origin=None):
        origin = self.player if origin is None else origin
        distance = {origin: 0}
        queue = [origin]
        cursor = 0
        while cursor < len(queue):
            current = queue[cursor]
            cursor += 1
            for neighbour in self.neighbours(current):
                if neighbour not in distance:
                    distance[neighbour] = distance[current] + 1
                    queue.append(neighbour)
        return distance

    def route_to(self, target):
        target = tuple(target)
        if target == self.goal and not self.gate_open:
            return []
        if target not in self.active and target != self.goal:
            return []
        previous = {self.player: None}
        queue = [self.player]
        cursor = 0
        while cursor < len(queue):
            current = queue[cursor]
            cursor += 1
            if current == target:
                break
            for neighbour in self.neighbours(current):
                if neighbour not in previous:
                    previous[neighbour] = current
                    queue.append(neighbour)
        if target not in previous:
            return []
        route = []
        step = target
        while previous[step] is not None:
            route.append(step)
            step = previous[step]
        route.reverse()
        return route

    def within_reach(self) -> dict:
        """Every cell a finger could move to in one touch, with how many steps away it is.

        The ordinary distances() walks the whole board; this stops at MAX_TOUCH_ROUTE, which
        is all touch_to will accept anyway. On expert that is a few hundred cells instead of
        ten thousand, and it runs on every drag event.
        """
        reach = {self.player: 0}
        queue = [self.player]
        cursor = 0
        while cursor < len(queue):
            current = queue[cursor]
            cursor += 1
            if reach[current] >= self.MAX_TOUCH_ROUTE:
                continue
            for neighbour in self.neighbours(current):
                if neighbour not in reach:
                    reach[neighbour] = reach[current] + 1
                    queue.append(neighbour)
        return reach

    def nearest_active(self, target, radius=5):
        """The cell a touch means, which is the nearest one the finger can ACTUALLY GET TO.

        THIS USED TO PICK THE NEAREST CELL AS THE CROW FLIES, and that one word is why Harry
        could not finish the expert maze. A cell one step away through a wall beat a cell two
        steps away along the corridor, so a finger dragged round a corner kept landing on the
        far side of something and the mat did nothing. Measured over the whole board before
        this change: 7.3% of touches did nothing on beginner, 13.8% on medium and 20.6% on
        expert -- one touch in five -- and of the ones refused for distance the median real
        route was 96 cells against a cap of 14.

        Nothing about that is a blocked maze. Every level could be finished by a program all
        along, which is exactly why the test I had did not notice: it walked with walk_to,
        which knows the whole board, and a child has a fingertip.

        So reachability comes first and nearness second: of the cells near the touch that can
        be reached in one touch, take the one closest to where the finger actually is. The cap
        itself is untouched -- it is what stops a tap solving the maze.
        """
        target = tuple(target)
        reach = self.within_reach()
        if target in reach:
            return target
        tx, ty = target
        candidates = [cell for cell in reach
                      if abs(cell[0] - tx) <= radius and abs(cell[1] - ty) <= radius]
        if not candidates:
            # Nothing within a touch of here. Fall back to the old answer so that callers
            # which only want "name a cell" -- and the tests that check this names one --
            # still get one; touch_to will refuse it on the route length, as it always did.
            near = [cell for cell in self.active
                    if abs(cell[0] - tx) <= radius and abs(cell[1] - ty) <= radius]
            if self.gate_open:
                near.append(self.goal)
            if not near:
                return None
            return min(near, key=lambda cell: (cell[0] - tx) ** 2 + (cell[1] - ty) ** 2)
        return min(candidates,
                   key=lambda cell: ((cell[0] - tx) ** 2 + (cell[1] - ty) ** 2, reach[cell]))

    def _arrive(self, cell) -> str:
        self.player = cell
        self.trail.append(cell)
        self.trail = self.trail[-34:]
        event = "moved"
        # NEAR ENOUGH, not exactly on it. See PICKUP: standing anywhere within a few steps of
        # a thing counts as having picked it up, because the thing is drawn several cells wide
        # and a child walking over it and not collecting it is a rule they cannot see.
        for index, item in enumerate(self.items):
            if item in self.collected or cell not in self.item_reach[index]:
                continue
            self.collected.add(item)
            self.last_item = self.ITEM_KEYS[index]
            event = "gate" if self.gate_open else "collected"
        if self.finished:
            self.route = []
            return "finished"
        return event

    def touch_to(self, target) -> str:
        """Move only a short local route, so touch traces the maze instead of solving it."""
        target = self.nearest_active(target)
        if target is None:
            return "nothing"
        route = self.route_to(target)
        if not route or len(route) > self.MAX_TOUCH_ROUTE:
            return "nothing"
        event = "moved"
        for cell in route:
            arrived = self._arrive(cell)
            if arrived != "moved":
                event = arrived
        return event

    def walk_to(self, target) -> bool:
        route = self.route_to(target)
        if not route:
            return False
        self.route = route
        return True

    def step(self) -> str:
        if not self.route:
            return "nothing"
        return self._arrive(self.route.pop(0))

    def nearest_objective(self):
        remaining = [cell for cell in self.items if cell not in self.collected]
        if not remaining:
            return self.goal
        routes = [(len(self.route_to(cell)), cell) for cell in remaining]
        routes = [entry for entry in routes if entry[0]]
        return min(routes)[1] if routes else None

    def press(self) -> str:
        """Optional one-button accessibility route; touch remains the normal control."""
        objective = self.nearest_objective()
        if objective is None or not self.walk_to(objective):
            return "nothing"
        return "walking"


class Catalogue(QtWidgets.QWidget):
    """What has been collected so far, drawn on the 7in as the things themselves.

    Harry, 15 November 2026: "the small screen catalogues the items collected." Once the
    items vanish from the maze there is nothing on the big screen saying what a child has
    picked up, and "Items: 3 of 5" says how many but not which.

    THE DRAWINGS RATHER THAN THEIR NAMES, for two reasons. A child of six recognises the
    lantern and the prayer mat long before reading either word. And the words for these
    things exist on the mat only as whole sentences -- "Wash for prayer. This washing is
    called wudu." -- so a list of names would mean inventing nine short labels in ten
    languages, every one of them unreviewed, to say what the pictures already say. There is
    enough unreviewed wording in this game.

    The pictures are cut out of the maze artwork itself, so the thing on the 7in is exactly
    the thing that was on the board a moment ago, and nothing new has to be drawn or shipped.
    """

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.setObjectName("mosqueMazeCatalogue")

    def sizeHint(self):
        return QtCore.QSize(self.screen.win.side_px(560), self.screen.win.side_px(190))

    def paintEvent(self, _):
        game = self.screen.game
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        got = [i for i, cell in enumerate(game.items) if cell in game.collected]
        if not got:
            return
        # One row while they fit, two when nine of them will not. Worked out from how many
        # there are rather than from the level, so the expert board does not decide the
        # layout for a beginner who has collected five.
        across = len(got) if len(got) <= 5 else (len(got) + 1) // 2
        down = 1 if len(got) <= 5 else 2
        box = min(self.width() / max(1, across), self.height() / down)
        left = (self.width() - box * across) / 2
        top = (self.height() - box * down) / 2
        for place, index in enumerate(got):
            icon = self.screen.item_icon(index, int(box * 0.86))
            if icon is None or icon.isNull():
                continue
            x = left + (place % across) * box + (box - icon.width()) / 2
            y = top + (place // across) * box + (box - icon.height()) / 2
            painter.drawPixmap(int(x), int(y), icon)


class Screen(QtWidgets.QWidget):
    """Artwork-only main maze; ``companion`` is mounted on the 7-inch screen."""

    leave = Signal()
    changed = Signal()
    won = Signal()

    #: How far around an item's centre is repainted when it is collected. The widest drawing
    #: measured on this artwork reaches 66px of 1920, so this covers every one of them with a
    #: little to spare. It can be generous because the paint is clipped to floor cells and
    #: cannot reach a wall however large it is; see paintEvent.
    ERASE = 80

    #: The footprint size. Was 7 until 2.28, when Harry asked for "slightly bigger".
    FOOT = 10


    #: Anything darker than this in the artwork is floor, not a drawing. Not zero, because the
    #: floor in these files is not a flat black: it carries values all the way up from 0, and
    #: a cut-out that trusted pure black came out as a speckled white tile.
    FLOOR_IS_BELOW = 110

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.game = Rules()
        self.setObjectName("mosqueMazeMain")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        base = window.assets / "children"
        self.images = tuple(
            QtGui.QPixmap(str(base / level["asset"]))
            for level in self.game.LEVEL_DATA
        )
        self._move_timer = QtCore.QTimer(self)
        self._move_timer.setInterval(24)
        self._move_timer.timeout.connect(self._advance)
        self._ignore_mouse_release = False
        #: {(difficulty, item index, ink): the item's own drawing, for the 7in catalogue}.
        self._icons: dict[tuple[int, int, str], QtGui.QPixmap] = {}

        self.companion = self._build_companion()
        self.changed.connect(self.update)
        self.changed.connect(self._look_for_a_win)
        self.changed.connect(self._update_hint)
        self.changed.connect(self.retell)
        self.follow_theme()
        self.start_again()

    def _build_companion(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("mosqueMazeCompanion")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.side_px(22), self.win.side_px(22),
                                  self.win.side_px(22), self.win.side_px(22))
        layout.setSpacing(self.win.side_px(14))

        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.hint = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.hint.setObjectName("gameHint")
        self.hint.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                QtWidgets.QSizePolicy.Policy.Expanding)
        self.hint.setMinimumHeight(self.win.side_px(250))
        self.hint.installEventFilter(self)
        layout.addWidget(self.hint, 1)

        # Under the little maze and above the words: what has been picked up so far. It sits
        # in the gap the panel already had -- there were about 180 blank pixels here.
        self.catalogue = Catalogue(self)
        self.catalogue.setMinimumHeight(self.win.side_px(150))
        layout.addWidget(self.catalogue)

        self.status = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.status.setObjectName("gameStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress_button = QtWidgets.QPushButton()
        self.progress_button.setObjectName("gameButton")
        self.progress_button.setMinimumHeight(self.win.side_px(64))
        self.progress_button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.progress_button)

        self.difficulty_button = QtWidgets.QPushButton()
        self.difficulty_button.setObjectName("gameButton")
        self.difficulty_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.difficulty_button.setMinimumHeight(self.win.side_px(68))
        self.difficulty_button.clicked.connect(self.cycle_difficulty)
        layout.addWidget(self.difficulty_button)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(self.win.side_px(14))
        self.new_button = QtWidgets.QPushButton()
        self.new_button.setObjectName("gameButton")
        self.new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_button.setMinimumHeight(self.win.side_px(72))
        self.new_button.clicked.connect(self.start_again)
        controls.addWidget(self.new_button, 1)

        self.exit_button = QtWidgets.QPushButton()
        self.exit_button.setObjectName("gameButton")
        self.exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_button.setMinimumHeight(self.win.side_px(72))
        self.exit_button.clicked.connect(self.leave.emit)
        controls.addWidget(self.exit_button, 1)
        layout.addLayout(controls)
        return panel

    def _font(self, words, size, bold=False):
        font = QtGui.QFont(Fonts.for_text(words))
        font.setPixelSize(self.win.px(size))
        if bold:
            font.setWeight(QtGui.QFont.Weight.Bold)
        return font

    def retell(self) -> None:
        title = self.win.t("mosque_maze.title")
        progress = self.win.t("mosque_maze.progress",
                              at=str(len(self.game.collected)),
                              of=str(len(self.game.items)))
        levels = (self.win.t("mosque_maze.beginner"),
                  self.win.t("mosque_maze.medium"),
                  self.win.t("mosque_maze.expert"))
        # The level on its own, no "Difficulty:" in front: see the note in
        # prayer_day_journey.retell. The button it is written on is what says what it means.
        difficulty = levels[self.game.difficulty]
        if self.game.finished:
            status = self.win.t("mosque_maze.complete")
        elif self.game.gate_open:
            status = self.win.t("mosque_maze.gate_open")
        elif self.game.last_item:
            # What was just picked up, which is the only part of this game that teaches
            # anything. Falls back to the instruction before the first one is reached.
            status = self.win.t(f"mosque_maze.item.{self.game.last_item}")
        else:
            status = self.win.t("mosque_maze.collect")
        new_game = self.win.t("mosque_maze.new_game")
        exit_game = self.win.t("mosque_maze.exit")

        self.catalogue.update()
        self.title.setText(title)
        self.progress_button.setText(progress)
        self.difficulty_button.setText(difficulty)
        self.status.setText(status)
        self.new_button.setText(new_game)
        self.exit_button.setText(exit_game)

        self.title.setFont(self._font(title, 36, True))
        self.status.setFont(self._font(status, 22, True))
        for button, words in ((self.progress_button, progress),
                              (self.difficulty_button, difficulty),
                              (self.new_button, new_game),
                              (self.exit_button, exit_game)):
            button.setFont(self._font(words, 27, True))

    def follow_theme(self) -> None:
        c = palette()
        radius = self.win.side_px(12)
        edge = self.win.side_px(3)
        # TYPE SIZES IN THE PANEL'S OWN PIXELS. Without these the panel inherits the app
        # stylesheet's QWidget rule -- font-size px(24) -- which is scaled by the MAIN screen.
        # On a 1080x1920 panel beside a 1920x1200 display that lettering is about half the
        # size it was drawn at, which is the other half of why Harry's photographs showed a
        # thin strip of unreadable controls. Sized against the 1024-tall panel these were
        # designed on, so they come out the same on any panel.
        title = self.win.side_px(40)
        body = self.win.side_px(28)
        label = self.win.side_px(30)
        self.companion.setStyleSheet(
            f"QWidget#mosqueMazeCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            f"QWidget#mosqueMazeCatalogue {{ background: {c.paper}; }}"
            # See journey_jigsaw.follow_theme: background:panel with color:paper was black on
            # #1C1C1C after dark. paper and ink are opposites in both themes; panel is not.
            f"QPushButton#gameButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; border-radius: {radius}px; }}"
            f"QPushButton#gameButton:pressed {{ background: {c.pressed}; color: {c.ink}; }}"
            f"QLabel#gameTitle {{ font-size: {title}px; font-weight: bold; }}"
            f"QLabel#gameStatus {{ font-size: {body}px; }}"
            f"QPushButton#gameButton {{ font-size: {label}px; font-weight: bold; }}"
        )
        self.retell()
        self._update_hint()
        self.catalogue.update()
        self.update()

    @property
    def ready(self) -> bool:
        return all(not p.isNull() for p in self.mazes)

    @staticmethod
    def playable(assets) -> bool:
        """Asked of the disk before anything is built. See journey_jigsaw.Screen.playable."""
        base = assets / "children"
        return all((base / level["asset"]).is_file() for level in Rules.LEVEL_DATA)

    def start_again(self) -> None:
        self._move_timer.stop()
        self.game.restart()
        self.changed.emit()

    def cycle_difficulty(self) -> None:
        self._move_timer.stop()
        self.game.cycle_difficulty()
        self.changed.emit()

    def press(self, action="") -> None:
        from .buttons import BACK
        if action == BACK or str(action).lower() in ("back", "exit", "escape"):
            self._move_timer.stop()
            self.leave.emit()
            return
        if self.game.finished or self._move_timer.isActive():
            return
        if self.game.press() == "walking":
            self._move_timer.start()

    def _cell_at(self, point):
        if self.width() <= 0 or self.height() <= 0:
            return None
        x = min(self.game.WIDTH - 1,
                max(0, int(point.x() * self.game.WIDTH / self.width())))
        y = min(self.game.HEIGHT - 1,
                max(0, int(point.y() * self.game.HEIGHT / self.height())))
        return self.game.nearest_active((x, y))

    def _trace_to(self, point) -> None:
        if self.game.finished or self._move_timer.isActive():
            return
        target = self._cell_at(point)
        if target is None:
            return
        result = self.game.touch_to(target)
        if result != "nothing":
            self.changed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._ignore_mouse_release = False
            self._trace_to(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._trace_to(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._ignore_mouse_release:
            self._ignore_mouse_release = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._trace_to(event.position())
            event.accept()

    @staticmethod
    def _touch_position(event):
        points = event.points() if hasattr(event, "points") else event.touchPoints()
        if not points:
            return None
        point = points[0]
        return point.position() if hasattr(point, "position") else point.pos()

    def event(self, event):
        kind = event.type()
        if kind in (QtCore.QEvent.Type.TouchBegin,
                    QtCore.QEvent.Type.TouchUpdate,
                    QtCore.QEvent.Type.TouchEnd):
            point = self._touch_position(event)
            if point is not None:
                self._trace_to(point)
            if kind == QtCore.QEvent.Type.TouchEnd:
                self._ignore_mouse_release = True
            event.accept()
            return True
        return super().event(event)

    def eventFilter(self, watched, event):
        if watched is self.hint and event.type() == QtCore.QEvent.Type.Resize:
            self._update_hint()
        return super().eventFilter(watched, event)

    def _advance(self) -> None:
        result = self.game.step()
        self.changed.emit()
        if result in ("nothing", "finished") or not self.game.route:
            self._move_timer.stop()

    def item_icon(self, index: int, size: int):
        """One item's drawing, cut from the maze artwork and recoloured to suit the theme.

        The artwork is white on black and the 7in panel follows the mat's theme, so a plain
        crop would be a black tile on a white panel in daylight mode. The black is turned into
        a mask instead, and what is left is painted in the panel's own ink.

        Cached per level, item and ink -- the ink is in the key so that changing the theme
        does not hand back yesterday's colour, which is the bug that a cache keyed on the
        cheap half of the question always has.
        """
        if size <= 0:
            return None
        image = self.images[self.game.difficulty]
        if image.isNull():
            return None
        key = (self.game.difficulty, index, palette().ink, size)
        found = self._icons.get(key)
        if found is not None:
            return found
        x, y = self.game.item_norm[index]
        reach = int(image.width() * self.ERASE / 1920)
        piece = image.copy(QtCore.QRect(int(x * image.width()) - reach,
                                        int(y * image.height()) - reach,
                                        reach * 2, reach * 2))
        # SCALED FIRST, THEN READ PIXEL BY PIXEL. The brightness has to become the alpha, and
        # Qt has no one call that does it -- createMaskFromColor was tried and is the wrong
        # tool: it keys on ONE colour, and this artwork's floor is not one colour. It carries
        # values all the way up from 0, so keying out pure black left the floor behind and the
        # catalogue came out as dark shapes on speckled white tiles.
        #
        # Reading the pixels is therefore the honest way, and doing it AFTER the scale is what
        # makes it cheap: a few thousand pixels at the size it is shown instead of 25,600 at
        # the size it was drawn. It happens once per item per theme, not per repaint.
        small = (piece.toImage()
                 .convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
                 .scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation))
        out = QtGui.QImage(small.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(QtGui.QColor(0, 0, 0, 0))
        ink = QtGui.QColor(palette().ink)
        # ONLY WHAT STANDS ON FLOOR, by the same mask the eraser is clipped to. A square cut
        # around an item catches whatever else is near it, and near is near: the walls in this
        # artwork come within 2px of some of these drawings. Without this the catalogue showed
        # the lantern with two lengths of somebody else's wall standing beside it.
        #
        # It also makes the two halves agree by construction. What the board loses and what
        # the 7in gains are decided by one bitmap, so the catalogue cannot show a thing that is
        # still on the board, or miss one that is gone.
        left_px = int(x * image.width()) - reach
        top_px = int(y * image.height()) - reach
        span = reach * 2
        for row in range(small.height()):
            ay = top_px + (row + 0.5) * span / small.height()
            cell_y = int(ay * self.game.HEIGHT / image.height())
            for column in range(small.width()):
                value = small.pixelColor(column, row).red()      # grey: r == g == b
                if value < self.FLOOR_IS_BELOW:
                    continue
                ax = left_px + (column + 0.5) * span / small.width()
                if (int(ax * self.game.WIDTH / image.width()),
                        cell_y) not in self.game.item_cells[index]:
                    continue
                out.setPixelColor(column, row, QtGui.QColor(
                    ink.red(), ink.green(), ink.blue(),
                    min(255, (value - self.FLOOR_IS_BELOW) * 255
                        // (255 - self.FLOOR_IS_BELOW))))
        shown = QtGui.QPixmap.fromImage(out)
        self._icons[key] = shown
        return shown

    def _cell_point(self, cell):
        return QtCore.QPointF((cell[0] + 0.5) * self.width() / self.game.WIDTH,
                              (cell[1] + 0.5) * self.height() / self.game.HEIGHT)

    def _draw_footprint(self, painter, point, scale, colour):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawEllipse(QtCore.QRectF(point.x() - scale * 0.72,
                                          point.y() - scale * 0.42,
                                          scale * 0.58, scale * 0.92))
        painter.drawEllipse(QtCore.QRectF(point.x() + scale * 0.14,
                                          point.y() - scale * 0.42,
                                          scale * 0.58, scale * 0.92))
        for side in (-1, 1):
            base_x = point.x() + side * scale * 0.43
            for toe in range(3):
                painter.drawEllipse(QtCore.QPointF(
                    base_x + side * scale * (0.12 + toe * 0.12),
                    point.y() - scale * (0.55 + toe * 0.05)),
                    scale * 0.11, scale * 0.11)

    def paintEvent(self, _):
        c = palette()
        image = self.images[self.game.difficulty]
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QtGui.QColor(c.paper))
        if not image.isNull():
            source = QtCore.QRectF(0, 0, image.width(), image.height())
            painter.drawPixmap(QtCore.QRectF(self.rect()), image, source)

        # The maze artwork is white on black in either theme, so "the colour of the floor" is
        # the dark one whichever way round the mat is set. The gate opening and a collected
        # item being erased both paint with it. (A `foreground` partner to this went with the
        # ticks in 2.28: nothing else was ever drawn in it.)
        background = QtGui.QColor(c.paper if c.dark else c.ink)
        if self.game.gate_open:
            left, top, right, bottom = self.game.gate_norm
            gate = QtCore.QRectF(left * self.width(), top * self.height(),
                                 (right - left) * self.width(),
                                 (bottom - top) * self.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(gate, self.win.px(8), self.win.px(8))

        # WHAT IS COLLECTED IS GONE, not ticked. Harry, 15 November 2026: "instead of the
        # items collected showing a tick they disappear and the small screen catalogues the
        # items collected." A tick left the thing on the board and wrote on it; a child
        # looking for what is left still had to read every marker to see which were spent.
        #
        # ERASED CELL BY CELL, over exactly the cells the drawing occupies. The items are
        # painted into the maze artwork, so removing one means covering it -- and a disc big
        # enough to cover an item is bigger than the gap to the wall beside it. Measured on
        # this artwork: the drawings reach up to 66px from their centres while a wall can be
        # 2px away. A disc would have eaten holes in the maze, and a hole in the wall of a
        # maze is not a blemish, it is a lie about where a child may walk.
        #
        # Clipping to the cells the MASK calls floor was tried and is wrong for a reason worth
        # keeping: the mask was made from this artwork, so it calls the drawing a wall too.
        # That erase rubbed out the floor around each item and left the item sitting in it.
        # Rules.item_cells is the list of what each drawing actually covers.
        wide = self.width() / self.game.WIDTH
        tall = self.height() / self.game.HEIGHT
        for index, cell in enumerate(self.game.items):
            if cell not in self.game.collected:
                continue
            for x, y in self.game.item_cells[index]:
                # Rounded outward so neighbouring cells overlap by a pixel rather than leaving
                # a hairline of the drawing along the seam between them.
                left, top = int(x * wide), int(y * tall)
                painter.fillRect(left, top,
                                 int((x + 1) * wide) - left + 1,
                                 int((y + 1) * tall) - top + 1, background)

        # THE TRAIL IN GREEN, AND BIGGER. Harry: "have the footprints in green colour and make
        # slightly bigger." On a white-on-black maze the old grey prints were the one thing on
        # the screen with no colour of its own and they were easy to lose. Green is the mat's
        # own colour for "this is the live one" -- it is what the current prayer is drawn in --
        # so it carries the same meaning here without a new colour being invented for it.
        #
        # The older prints keep the sense of a trail by fading rather than by greying: the same
        # green, carrying less of itself the further back it is.
        trail = self.game.trail[-18:]
        green = QtGui.QColor(c.green)
        for index, cell in enumerate(trail):
            colour = QtGui.QColor(green)
            if index < len(trail) - 1:
                colour.setAlpha(70 + int(120 * index / max(1, len(trail) - 1)))
            self._draw_footprint(painter, self._cell_point(cell),
                                 float(self.win.px(self.FOOT)), colour)

        if self.game.finished:
            centre = self._cell_point(self.game.goal)
            painter.setPen(QtGui.QPen(QtGui.QColor(c.faint), self.win.px(5)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(centre, self.win.px(34), self.win.px(34))

    def _update_hint(self) -> None:
        if not hasattr(self, "hint"):
            return
        image = self.images[self.game.difficulty]
        if image.isNull() or self.hint.width() <= 0 or self.hint.height() <= 0:
            self.hint.clear()
            return
        shown = image.scaled(self.hint.size(), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        # AND WHAT HAS BEEN COLLECTED IS GONE FROM THE LITTLE MAP TOO. This is a picture of
        # the board, and from 2.28 the board no longer has those things on it. Left alone it
        # would show a child a map with the water drop still sitting where they picked it up,
        # a hand's width from the catalogue saying they have it -- which is the sort of
        # disagreement a six-year-old notices long before an adult does.
        got = [i for i, cell in enumerate(self.game.items) if cell in self.game.collected]
        if got:
            wide = shown.width() / self.game.WIDTH
            tall = shown.height() / self.game.HEIGHT
            painter = QtGui.QPainter(shown)
            c = palette()
            for index in got:
                for x, y in self.game.item_cells[index]:
                    left, top = int(x * wide), int(y * tall)
                    painter.fillRect(left, top,
                                     int((x + 1) * wide) - left + 1,
                                     int((y + 1) * tall) - top + 1,
                                     QtGui.QColor(c.paper if c.dark else c.ink))
            painter.end()
        self.hint.setPixmap(shown)

    def showEvent(self, event):
        self.retell()
        self.follow_theme()
        super().showEvent(event)

    def hideEvent(self, event):
        self._move_timer.stop()
        super().hideEvent(event)

    def _look_for_a_win(self) -> None:
        """Runs after every change. See salaah/winning.py for why it is once and not always."""
        announce_if_won(self, self.game.finished)
