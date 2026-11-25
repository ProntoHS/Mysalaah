"""Journey to the Mosque: a native dual-touch MySalaah maze game.

The 16-inch touch display contains only the approved maze artwork and the live
footprint trail. The 7-inch companion shows the hint, translated instructions,
progress, scenery, New Game and Exit. All state stays in memory.
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

    #: Positional against each background's `items` tuple: the nth cell is the nth key, and
    #: the nth drawing in ITEM_ART.
    #:
    #: TEN SINCE 2.53, AND THEY DO TWO DIFFERENT JOBS. Harry, 25 November 2026: "i want to use
    #: all the objects at some point, lets keep the 3 main objects in corner and the other can
    #: be smaller and scattered."
    #:
    #: The first three are the three corners, and they are the three things a child actually
    #: DOES before praying -- washing, dressing, putting the mat down. They are big, they are
    #: in the three corners he left clear, and they are why the corners are worth the walk.
    #:
    #: The other seven are things met on the way, named for what they are and nothing more.
    #: That distinction is deliberate. The nine that were here before were nine steps of
    #: getting ready, in order, and the order was the point: it is what stopped this being a
    #: maze with dots wearing an Islamic name, which is the fault six games were taken out for
    #: in October 2026 -- see the note in ui.build_corner. Harry's ten objects are not a
    #: sequence; a lantern and a bowl of dates are not stages of anything. So rather than
    #: pretend, the three that ARE stages carry that meaning and the rest are honestly just
    #: the things you pass.
    #:
    #: None of these words has been read by anyone qualified.
    ITEM_KEYS = ("wudu", "clothes", "mat",
                 "quran", "tasbih", "lantern", "dates", "crescent", "kaaba", "mosque")

    #: The drawing for each, in assets/children/mosque-items. Harry's set of 25 November 2026.
    ITEM_ART = ("brass_ewer", "kufi_cap", "prayer_rug",
                "quran_on_rehal", "tasbih_beads", "ramadan_lantern", "dates_bowl",
                "crescent_moon_star", "kaaba", "mosque")

    #: How many of the ten are the big corner ones.
    BIG = 3

    WIDTH = 160
    HEIGHT = 90
    MAX_TOUCH_ROUTE = 14
    BACKGROUNDS = (
    {
        'name': 'hedge',
        'asset': 'mosque-maze-hedge.png',
        'mask': '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000f0ff830fffffffffffffffffffffffc1ff0f0000f0ff870fffffffffffffffffffffffe1ff0f0000f0ff870fffffffffffffffffffffffe1ff0f0000f0ff870fffffffffffffffffffffffe1ff0f0000f0ff870fffff01fc070000000000fce1ff0f0000f0ff870fffff01fc070000000000fce1ff0f0000f0ff87ff1ffe01f0070000000000fce1ff0f0000f0ff87ff1ffe01f0070000000000fce1ff0f0000f0ff87ff1ffefff0ffffffff3ff8ffe1ff0f0000f0ff87ff1ffefff0ffffffff7ff8ffe1ff0f0000f0ff87ff1ffefff0ffffffff7ff8ffe1ff0f0000f0ff87ff1ffefff0ffffffff7ff8ffe1ff0f000000f807000000fef007e0ff7f00f8ffe11f00000000f807000000fef007e0ff7f00f8ffe11f00000000e00f000000fef007800f1f00fef0ff1f00000000e01f000000fef007800f1f00fef0ff1f000000f0e1ff0ffffffff0ff830f1ffcfff0ffff0f0000f0e1ff0ffffffff0ff870f1ffefff0ffff0f0000f0e1ff0ffffffff0ff870f1ffefff0ffff0f0000f0e1ff0ffffffff0ff870f1ffefff0ffff0f0000f001e00fffff01000000001ffe01f00700000000f001e00fffff01000000001ffe01f00700000000f007e00f1f7e00000000001f7e00fc0100000000f007e00f1f7e00000000001f7e00fc0100000000f0ffff0f1f7ef8f0ffff0f1f7ef8ffc1ff0f0000f0ffff0f1f7ef8f0ffff0f1f7ef8ffe1ff0f0000f0ffff0f1f7ef8f0ffff0f1f7ef8ffe1ff0f0000f0ffff0f1f7ef8f0ffff0f1f7ef8ffe1ff0f0000f00700001f7ef8f0ffff0f007ef803e0ff0f0000f00700001f7ef8f001800f007ef803e0ff0f0000f00100001f7ef8ff01800f007ff803f0870f0000f00100001f7ef8ff01800f807ff803f8870f0000f0c1ff0f1f7ef8ff01800fff7ff8ffff870f0000f0e1ff0f1f7ef8ff01800fff7ff8ffff870f0000f0e1ff0f1f7ef8ff01800fff7ff8ffff870f0000f0e1ff0f1f7ef8ff01800fff3ff8ffff830f0000f0e1ff0f1f7ef8ff01800f7f0000fc07800f0000f0e1ff0f1f7ef8ff01800f7f0000fc07800f0000f0e187ff1f7ef8f001800f7f0000f007800f0000f0e187ff1f7ef8f0ffff0f7f0000f007800f0000f0e187ff1f7ef8f0ffff0ffffffff0ff870f0000f0e187ff1f7ef8f0ffff0ffffffff0ff870f0000f0e187ff1f7ef8f0ffff0ffffffff0ff870f0000f0e187ff1f7ef8f0ffff0ffffffff0ff830f0000f0e10700007ef80000000080ffff0000800f0000f0e10700007ef80000000080ffff0000800f0000f0e10700807ff800000000807ff80300800f0000f0e10700807ff800000000807ff80300800f0000f0e187ffff7ff8f0ff87ffff7ff8ffff870f0000f0e187ffff7ff8f0ff87ffff7ff8ffff870f0000f0e187ffff7ff8f0ff87ffff7ff8ffff870f0000f0e187ffff3ff8f0ff83ffff3ff8ffff830f0000f0e1873f0000f8f007803f000000000000000000f0e1873f0000f8f007803f000000000000000000f0e1870f0000fef007803f000000000000000000f0e1870f0000fef007803f000000000000000000f0e1870ffffffff0ff87ffffffffffffff0f0000f0e1870ffffffff0ff87ffffffffffffff0f0000f0e1870ffffffff0ff87ffffffffffffff0f0000f0e1870ffffffff0ff87ffffffffffffff0f0000f0e1870f7f000000f8873f0000fe03f8ff0f0000f0e1870f7f000000f8873f0000fe03f0ff0f0000feff87ff7f000000f8873f0000f803e0ff0f0000feff87ff7f000000f8873f0000f803e0ff0f0000feff87ffffffffffff87ffff7ff8ffe1ff0f0000feff87ffffffffffff87ffff7ff8ffe1ff0f0000feff87ffffffffffff87ffff7ff8ffe1ff0f0000feff83ffffffffffff83ffff3ff8ffc1ff0f0000020000000000000000000000000000000000000002000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
        'start': (9, 76),
        'items': ((18, 17), (142, 17), (142, 73), (23, 76), (87, 22), (51, 43), (14, 47), (54, 13), (115, 28), (31, 34)),
        'item_norm': ((0.115625, 0.194444), (0.890625, 0.194444), (0.890625, 0.816667), (0.146875, 0.85), (0.546875, 0.25), (0.321875, 0.483333), (0.090625, 0.527778), (0.340625, 0.15), (0.721875, 0.316667), (0.196875, 0.383333)),
        'approach': (79, 50),
    },
    {
        'name': 'city',
        'asset': 'mosque-maze-city.png',
        'mask': '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000e0ff83ffffffffffffffffff3ff8ffc1ff070000f0ff83ffffffffffffffffff3ff8ffc1ff0f0000f0ff83ffffffffffffffffff3ff8ffc1ff0f0000f0ff83ffffffffffffffffff3ff8ffc1ff0f0000f0ff03c0ffff0000000000003ff8ffc1ff0f0000f0ff03c0ffff0000000000003ff8ffc1ff0f0000f0ff03c01ffc070000000000fcfdf0c1ff0f0000f0ff03c01ffc010000000000fcfff0c1ff0f0000f0ff83ff1ffcffffffffff1ffcfff0c1ff0f0000f0ff83ff1ffcffffffffff1ffcfff0c1ff0f0000f0ff83ff1ffcffffffffff1ffcfff0c1ff0f0000f0ff83ff1ffcffffffffff1ffcfff0c1ff0f000000f0833f00fcff0300e03f00000000c00f00000000f0833f00fcff0300e03f00000000c00f00000000c0df0f003ef80300803f00000000c00300000000c0ff0f003ff80300803f00000000c003000000e0c1ff0ffe3ff8ffff83ffffffffffc183070000f0c1ff0fff3ff8ffff83ffffffffffc1830f0000f0c1ff0fff3ff8ffff83ffffffffffc1830f0000f0c1ff0fff3ff8ffff83ffffffffffc1830f0000f00100007f00f8030000c07f0000fcc1830f0000f00100007f00f8030000c07f0000fcc1830f0000f0070000ff03f8000000001f0000fcc1ff0f0000f00700007f00f8000000001f0000fcc1ff0f0000f0ffff0fff3ff8f0ffff0f1ffcffffc1ff0f0000f0ffff0fff3ff8f0ffff0f1ffcffffc1ff0f0000f0ffff0fff3ff8f0ffff0f1ffcffffc1ff0f0000f0ffff0fff3ff8f0ffff0f1ffcffffc1ff0f0000f007e00f003ff8f0ffff0f1ffc000000e00f0000f007e00f003ff8f401800f1ffc000000e00f0000f001e03f003cf8ff01800f1ffc070000e00f0000f001e03f003cf8ff01800f1ffc010000e00f0000f0c1ffff1f3cf8ff01800f1ffcffffffff0f0000f0c1ffff1f3cf8ff01800f1ffcffffffff0f0000f0c1ffff1f3cf8ff01800f1ffcffffffff0f0000f0c1ffff1f3cf8ff01800f1ffcffffffff0f0000f0010000003c00fc01800f1f00000000e00f0000f0010000003c00fc01800f1f00000000e00f0000f0010000003c00f401800f1f00000000a00f0000f0010000003c00f4ffff0f1f00000000800f0000f0c1ffff1f3cf8f0ffff0f1ffcffffff830f0000f0c1ffff1f3cf8f0ffff0f1ffcffffff830f0000f0c1ffff1f3cf8f0ffff0f1ffcffffff830f0000f0c1ffff1f3cf8f0ffff0f1ffcffffff830f0000f0c10fc01f3cf8000000001f0000fcff830f0000f0c11fc01f3cf8000000001f0000fcff830f0000f0c17f401f3cf8030000001f0000f0c1830f0000f0c11f401f3cf8030000001f0000fcc1830f0000f0c1ff0f1f3cf8ffff830f1ffcffffc1830f0000f0c1ff0f1f3cf8ffff830f1ffcffffc1830f0000f0c1ff0f1f3cf8ffff830f1ffcffffc1830f0000f0c1ff0f1f3cf8ffff830f1ffcffffc183070000f001e00f1f3cf8ff07800f1ffcff030000000000f001e00f1f3cf8ff07800f1ffcff030000000000f001a00fff3ff8f43f800fff3ffa000000000000f001e00fff3ff8f407e00fff3ff8000000000000f0c1ff0fff3ff8f0ffff0fff3ff8f0ffff0f0000f0c1ff0fff3ff8f0ffff0fff3ff8f0ffff0f0000f0c1ff0fff3ff8f0ffff0fff3ff8f0ffff0f0000f0c1ff07fe3ff8e0ffff07fe3ff8f0ffff0f0000f4c10f000000f8000000000000f8f4ffff0f0000f4c11f000000f8000000000000f8f4ffff0f0000feff7f000000f8000000000000f8ffd1ff0f0000feff1f000000fe000000000000feffc1ff0f0000fefffffffffffff0ffffffffffffffc1ff0f0000fefffffffffffff0ffffffffffffffc1ff0f0000fefffffffffffff0ffffffffffffffc1ff0f0000feffffffffff7fe0ffffffffffffffc1ff070000020000000000000000000000000000000000000002000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
        'start': (9, 76),
        'items': ((18, 17), (142, 17), (142, 73), (60, 76), (87, 22), (14, 65), (51, 38), (89, 61), (115, 20), (49, 13)),
        'item_norm': ((0.115625, 0.194444), (0.890625, 0.194444), (0.890625, 0.816667), (0.378125, 0.85), (0.546875, 0.25), (0.090625, 0.727778), (0.321875, 0.427778), (0.559375, 0.683333), (0.721875, 0.227778), (0.309375, 0.15)),
        'approach': (79, 50),
    },
    {
        'name': 'cloud',
        'asset': 'mosque-maze-cloud.png',
        'mask': '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000f0ff87fffffffffffffffffffffff0e1ff0f0000f0ff87fffffffffffffffffffffff0e1ff0f0000f0ff87fffffffffffffffffffffff0e1ff0f0000f0ff87fffffffffffffffffffffff0e1ff0f0000f0ff871f00000000f0cf9f7f0000f0e1ff0f0000f0ff870f00000000e0c70f3f0000f0e1ff0f0000f0ff870f00000000e0870f3f0000f0e1ff0f0000f0ff870f00000000e0870f3f0000f8e1ff0f0000f0ff870ffffffff0ff870fff7ff8ffe1ff0f0000f0ff870ffffffff0ff870fff7ff8ffe1ff0f0000f0ff870ffffffff0ff870fff7ff8ffe1ff0f0000f0ff870ffffffff0ff870fff7ff8ffe1ff0f000000f0870f3f0000f0f30700007ff8f9e10f00000000e0870f3f0000f0e30700007ef8f0e10700000000e0870f3f0000f0e10700007ef8f0e30700000000e0c70f3f0000f8e10700007efcf0e307000000f0e1ff0fffffffffe1ffff1ffefff0ff870f0000f0e1ff0fffffffffe1ffff1ffefff0ff870f0000f0e1ff0fffffffffe1ffff1ffefff0ff870f0000f0e1ff0fffffffffe1ffff1ffefff0ff870f0000f00100003fff00000000801f00fcf0f3870f0000f00100003f7e00000000001f00fcf0e3870f0000f00300001f7e00000000003f00f8f0e1870f0000f00300001ffe00000000003f00f8f0e1cf0f0000f0ffff0f1ffefff0ffff0fff7ff8f0e1ff0f0000f0ffff0f1ffefff0ffff0fff7ff8f0e1ff0f0000f0ffff0f1ffefff0ffff0fff7ff8f0e1ff0f0000f0ffff0f1ffefff0ffff0fff7ff8f0e1ff0f0000f0f3cf0f1ffe00f0ffff0f3f7f00f001c00f0000f0e3c70f1f7e00f001800f3f7e00f001c00f0000f0e1870f1f7e00f001800f1f7e00f003800f0000f0e1870f1ffe00f801800f1ffe00f003800f0000f0e1870f1ffeffff01800f1ffefff0ff870f0000f0e1870f1ffeffff01800f1ffefff0ff870f0000f0e1870f1ffeffff01800f1ffefff0ff870f0000f0e1870f1ffeffff01800f1ffefff0ff870f0000f0e107001ffe00f801800f1f00fc00f0870f0000f0e107001f7e00f001800f1f00fc00e0870f0000f0e107001f7e00f001800f3f00f800e0870f0000f0e10f001ffe00f0ffff0f3f00f801e0870f0000f0e1ff0f1ffefff0ffff0fff7ff8ffe1870f0000f0e1ff0f1ffefff0ffff0fff7ff8ffe1870f0000f0e1ff0f1ffefff0ffff0fff7ff8ffe1870f0000f0e1ff0f1ffefff0ffff0fff7ff8ffe1870f00000000c00f1f00fc00000000007f00f8e1070000000000800f1f00f800000000007e00f0e1070000000000800f3f00f800000000007e00f0e1070000000000c00f3f00f800000000007f00f8e10f000000f0ffff0fff7ff8f0ff870fff7ff8ffe1ff0f0000f0ffff0fff7ff8f0ff870fff7ff8ffe1ff0f0000f0ffff0fff3ff8f0ff870fff7ff8ffe1ff0f0000f0ffff0fff7ff8f0ff870fff7ff8ffe1ff0f0000f0030000007e00f0e3870f0000f8010000000000f0030000007e00f0e3870f0000f8000000000000f0010000007e00f0e1870f0000fc000000000000f0010000007e00f8e1871f0000fc000000000000f0e1ffff1f7ef8ffe187ff1ffefff0ffff0f0000f0e1ffff1f7ef8ffe187ff1ffefff0ffff0f0000f0e1ffff1f7ef8ffe187ff1ffefff0ffff0f0000f0e1ffff1f7ef8ffe187ff1ffefff0ffff0f0000f0e1cf1f007ef801e007801ffe00f0e3ff0f0000f0e1870f007ef800e007001f7e00f0e3ff0f0000f0e3870f007efc00e007003f7e00f0e1ff0f0000f9f3871f00fffc00f00f003fff00f8e1ff0f0000ffff87fffffffff0ffff0fffffffffe1ff0f0080ffff87fffffffff0ffff0fffffffffe1ff0f0080ffff87fffffffff0ffff0fffffffffe1ff0f0000ffff87fffffffff0ffff0fffffffffe1ff0f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
        'start': (7, 76),
        'items': ((18, 17), (142, 17), (142, 73), (61, 76), (80, 13), (14, 65), (51, 34), (108, 28), (24, 42), (80, 61)),
        'item_norm': ((0.115625, 0.194444), (0.890625, 0.194444), (0.890625, 0.816667), (0.384375, 0.85), (0.503125, 0.15), (0.090625, 0.727778), (0.321875, 0.383333), (0.678125, 0.316667), (0.153125, 0.472222), (0.503125, 0.683333)),
        'approach': (79, 50),
    },
    )

    #: Where the mosque stands, as a fraction of the picture, and where its door is. The same
    #: in all three backgrounds -- measured off the pictures rather than taken on trust, and
    #: they agreed to the pixel: Harry drew them from one template.
    MOSQUE_NORM = (0.461, 0.453, 0.539, 0.546)
    DOOR_NORM = (0.488, 0.515, 0.512, 0.551)

    def __init__(self):
        self.scene = 0
        self.restart()

    @property
    def level(self):
        return self.BACKGROUNDS[self.scene]

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
        return self.gate_open and self.player in self.doorstep

    def restart(self) -> None:
        level = self.BACKGROUNDS[self.scene]
        packed = bytes.fromhex(level["mask"])
        self.active = {
            (index % self.WIDTH, index // self.WIDTH)
            for index in range(self.WIDTH * self.HEIGHT)
            if packed[index // 8] & (1 << (index % 8))
        }
        self.start = tuple(level["start"])
        self.items = tuple(tuple(cell) for cell in level["items"])
        self.item_norm = tuple(tuple(point) for point in level["item_norm"])
        self.item_reach = tuple(self._near_enough(cell) for cell in self.items)
        self.gate_cell = tuple(level["approach"])
        self.goal = self.gate_cell
        self.mosque_cells = self._the_building()
        self.doorstep = self._the_doorstep()
        self.gate_norm = self.DOOR_NORM
        self.player = self.start
        self.collected = set()
        self.last_item = None
        self.route = []
        self.trail = [self.start]

    def _the_building(self) -> frozenset:
        """The cells the mosque's drawing covers, so nothing is drawn on top of it."""
        x0, y0, x1, y1 = self.MOSQUE_NORM
        return frozenset((x, y)
                         for x in range(int(x0 * self.WIDTH), int(x1 * self.WIDTH) + 1)
                         for y in range(int(y0 * self.HEIGHT), int(y1 * self.HEIGHT) + 1))

    def _the_doorstep(self) -> frozenset:
        """Where a child counts as having arrived: the gate cell and the floor touching it.

        NOT ONE FLAGSTONE, and this is the second time that lesson has had to be learnt here.
        Harry, 15 November 2026: "when completed and clicked mosque, no well done message or
        sound appeared." Arriving was `player == goal`, one named cell, and tapping the mosque
        put the child wherever the tap was nearest -- so the game ended only if they happened
        to land on the single cell that counted. Measured by tapping every spot inside the
        mosque: it finished 1 time in 117 on the easiest maze. He thought the hardest one was
        unfinishable; it was the easy ones that were nearly impossible to finish.

        That was fixed by letting anywhere INSIDE the mosque count. Harry's mosques of 25
        November have no inside -- they are a building drawn on the floor with a door, not a
        walled yard -- so there is nothing to stand in, and the rule becomes the doorstep.
        Kept deliberately roomy for the same reason it was then.
        """
        near = {self.gate_cell}
        for step in range(2):
            near |= {n for cell in near for n in self._cardinal(cell) if n in self.active}
        return frozenset(near)

    #: How far either side of an item's own cell its drawing is recorded.
    ITEM_REACH = 10

    #: One colour per pickup, in the order they appear in each level's `items`.
    #:
    #: Harry, 15 November 2026: "the mosque should be green and the items to be collected in
    #: red or individual colours." Individual, because it costs nothing more and does more: a
    #: child hunting the blue one has something to hunt, and the catalogue on the 7in shows
    #: each thing in the colour it had on the board, so the two read as the same object.
    #:
    #: Chosen to stay apart from each other on black and from the green of the mosque, and
    #: light enough to read at the size these are drawn. None of them is the mat's own red,
    #: which belongs to the things you press.
    #: NONE OF THEM GREEN, which is the rule that matters. Green means the mosque, and it
    #: means the footprints, so a green thing to collect would be the one colour on the board
    #: that already says something else. The first draft had a mint and a lime in it and the
    #: mint badge read as a small piece of mosque.
    #: TEN SINCE 2.53, and the tenth is not decoration. There were nine of these and ten
    #: pickups, and the lookup takes the colour modulo the length -- so the tenth thing on
    #: the board would have quietly worn the first one's red, and the line pointing a child
    #: at it would have pointed in the same colour as the line to another thing entirely.
    #: Tan, because it has to stay clear of the three floors Harry painted -- slate, pale
    #: grey, deep navy -- as well as of the other nine.
    ITEM_COLOURS = ("#F2545B", "#F0924F", "#F0C24F", "#D9D94F", "#4FB3F0",
                    "#4F7BF0", "#9B7BE8", "#E85FD0", "#F07FB0", "#C98A5B")

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

    def cycle_scene(self) -> None:
        self.scene = (self.scene + 1) % len(self.BACKGROUNDS)
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


class ItemPictures:
    """The ten pickup drawings, loaded once each.

    A class rather than a dict on the screen, because the 7in catalogue wants the same
    pictures and there is no reason to hold two copies of a lantern.
    """

    CACHE: dict[str, QtGui.QPixmap] = {}

    @classmethod
    def get(cls, window, name: str):
        if name not in cls.CACHE:
            path = window.assets / "children" / "mosque-items" / f"{name}.png"
            cls.CACHE[name] = QtGui.QPixmap(str(path)) if path.is_file() else QtGui.QPixmap()
        return cls.CACHE[name]


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
            for level in self.game.BACKGROUNDS
        )
        self._move_timer = QtCore.QTimer(self)
        self._move_timer.setInterval(24)
        self._move_timer.timeout.connect(self._advance)
        self._ignore_mouse_release = False
        #: Which thing the map's line points at; see what_we_are_after.
        self._after = None
        self._after_key = None
        #: The floor colour of the board on show, and which board that was. See board_floor.
        self._floor = None
        self._floor_for = None
        #: How far every cell is from the thing being headed for; see the_way_to.
        self._field: dict = {}
        self._field_key = None
        #: {key: (tinted pixmap, cell bounds)}; see painted().
        self._tints: dict = {}
        #: {(scene, item index, ink): the item's own drawing, for the 7in catalogue}.
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

        self.scene_button = QtWidgets.QPushButton()
        self.scene_button.setObjectName("gameButton")
        self.scene_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scene_button.setMinimumHeight(self.win.side_px(68))
        self.scene_button.clicked.connect(self.cycle_scene)
        layout.addWidget(self.scene_button)

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
        # THE SCENERY, NOT A DIFFICULTY. Harry, 25 November 2026: "remove different level
        # settings. instead we will have 3 different backgrounds to choose from... the
        # starting location and end destination are the same but backdrop and maze layout is
        # different." The three are the same size of task; what changes is where you are.
        #
        # The name on its own, no "Scenery:" in front: see the note in
        # prayer_day_journey.retell. The button it is written on is what says what it means.
        scenes = tuple(self.win.t(f"mosque_maze.scene.{b['name']}")
                       for b in self.game.BACKGROUNDS)
        scenery = scenes[self.game.scene]
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
        self.scene_button.setText(scenery)
        self.status.setText(status)
        self.new_button.setText(new_game)
        self.exit_button.setText(exit_game)

        self.title.setFont(self._font(title, 36, True))
        self.status.setFont(self._font(status, 22, True))
        for button, words in ((self.progress_button, progress),
                              (self.scene_button, scenery),
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
        return all((base / level["asset"]).is_file() for level in Rules.BACKGROUNDS)

    def start_again(self) -> None:
        self._move_timer.stop()
        self.game.restart()
        self.changed.emit()

    def cycle_scene(self) -> None:
        self._move_timer.stop()
        self.game.cycle_scene()
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

    def painted(self, cells, colour: str):
        """The artwork over those cells, in `colour`, with the floor left transparent.

        FAST ON PURPOSE. The obvious way -- read the brightness of every pixel and write a
        coloured one back -- is what item_icon does for the 7in, where it runs once on a
        thumbnail. Doing it here would mean a quarter of a million pixels for nine things
        every time the level changed, which on a Pi is a pause a child would see.

        So Qt does the work: the crop is thresholded to one bit, inverted so the DRAWING is
        what shows rather than the floor, and used as a mask over a flat fill of the colour.
        Measured at 49ms for the whole 1920x1080 board, against seconds for the pixel loop.

        Cached by the cells and the colour, so it survives repaints and is rebuilt only when
        the level or the theme changes.
        """
        image = self.images[self.game.scene]
        if image.isNull() or not cells:
            return None, None
        key = (self.game.scene, colour, len(cells), min(cells), max(cells))
        found = self._tints.get(key)
        if found is not None:
            return found
        xs = [cell[0] for cell in cells]
        ys = [cell[1] for cell in cells]
        wide = image.width() / self.game.WIDTH
        tall = image.height() / self.game.HEIGHT
        box = QtCore.QRect(int(min(xs) * wide), int(min(ys) * tall),
                           int((max(xs) + 1 - min(xs)) * wide),
                           int((max(ys) + 1 - min(ys)) * tall))
        piece = image.copy(box)
        mono = piece.toImage().convertToFormat(QtGui.QImage.Format.Format_Mono,
                                               Qt.ImageConversionFlag.MonoOnly
                                               | Qt.ImageConversionFlag.ThresholdDither)
        mono.invertPixels()
        tint = QtGui.QPixmap(piece.size())
        tint.fill(QtGui.QColor(colour))
        tint.setMask(QtGui.QBitmap.fromImage(mono))
        self._tints[key] = (tint, (min(xs), min(ys), max(xs) + 1, max(ys) + 1))
        return self._tints[key]

    # colour_layer lived here until 2.53. It rubbed out each pickup and the mosque from the
    # maze artwork and painted them back in colour, because they were drawn INTO that artwork
    # in one flat white-on-black picture. Harry's boards of 25 November are painted, with the
    # mosque already coloured in the picture, and his pickups arrive as ten separate drawings
    # with their own transparency -- so there is nothing to rub out and nothing to recolour.

    def item_icon(self, index: int, size: int):
        """One pickup's drawing, for the catalogue on the 7in.

        Since 2.53 this is simply the drawing, scaled. It used to be a great deal more: the
        pickups were painted into the maze artwork, one flat white-on-black picture, so the
        icon had to be cut out of the board, keyed to transparency by reading its brightness
        pixel by pixel -- createMaskFromColor keys on ONE colour and that floor was not one
        colour -- clipped to the cells the drawing actually stood on, repainted in the colour
        it had on the board, and cached per level, item and ink so that changing the theme did
        not hand back yesterday's colour.

        None of that is needed for ten PNGs with their own transparency. The cache stays,
        keyed on the drawing and the size, because scaling on every repaint of the panel is
        still waste; the ink is no longer in the key because nothing is recoloured.
        """
        if size <= 0:
            return None
        art = ItemPictures.get(self.win, self.game.ITEM_ART[index])
        if art is None or art.isNull():
            return None
        key = (self.game.ITEM_ART[index], size)
        found = self._icons.get(key)
        if found is None:
            found = art.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            self._icons[key] = found
        return found

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
        image = self.images[self.game.scene]
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QtGui.QColor(c.paper))
        if not image.isNull():
            source = QtCore.QRectF(0, 0, image.width(), image.height())
            painter.drawPixmap(QtCore.QRectF(self.rect()), image, source)

        # THE BOARD DOES NOT FOLLOW THE THEME SINCE 2.53, so neither can anything drawn on it.
        # Harry, 25 November 2026: "the new main screen image will be consistent regardless of
        # theme, only the side menu screen retains its own theme."
        #
        # This used to be `c.paper if c.dark else c.ink`, with a comment explaining that the
        # maze was white-on-black in both themes so the floor was whichever of the two was
        # dark. Harry's boards have a slate floor, a pale grey one and a deep navy one, and
        # none of those is the palette's ink or its paper. Read off the picture instead: see
        # board_floor.
        background = self.board_floor()
        if not self.game.gate_open:
            # THE GATE IS DRAWN, NOT ERASED, and that is the other way round from before. The
            # old artwork drew the mosque shut and the game painted the doorway away once
            # everything was collected. Harry's mosques are drawn with the door standing open
            # -- "the mosque entryway is currently open so you will have to place a gate" --
            # so the gate is a thing put IN FRONT of the door and taken away at the end. It is
            # also the better way round to be seen: a child meets a closed gate first and
            # watches it go, rather than never knowing there was one.
            left, top, right, bottom = self.game.gate_norm
            gate = QtCore.QRectF(left * self.width(), top * self.height(),
                                 (right - left) * self.width(),
                                 (bottom - top) * self.height())
            self._draw_gate(painter, gate)

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
        # EACH THING IS ITS OWN PICTURE NOW, so collecting one is simply not drawing it. The
        # paragraphs above describe a machine that no longer has to exist: when the pickups
        # were painted into the maze artwork, removing one meant covering it exactly, cell by
        # cell, because a disc big enough to hide a lantern was bigger than the gap to the
        # wall beside it -- and a disc over a wall is a lie about where a child may walk.
        # Harry's objects of 25 November arrive as ten separate drawings with their own
        # transparency, so none of that is needed. Kept as a note rather than deleted: the
        # reasoning is still why nothing may be rubbed out with a shape of its own choosing.
        self.draw_the_things(painter)

        # THE TRAIL, ONE COLOUR PER SCENERY SINCE 2.54, AND BIGGER.
        #
        # It was green until now, for a good reason that stopped being true. Harry, earlier:
        # "have the footprints in green colour and make slightly bigger" -- on the old
        # white-on-black maze the grey prints were the one thing on screen with no colour of
        # its own, and green is the mat's word for "this is the live one". That argument
        # assumed ONE board. There are three now, painted on slate, on pale grey and on deep
        # navy, and no single colour is legible on all three: see foot_colour.
        #
        # The older prints keep the sense of a trail by fading rather than by greying: the
        # same colour, carrying less of itself the further back it is.
        trail = self.game.trail[-18:]
        base = self.foot_colour()
        for index, cell in enumerate(trail):
            colour = QtGui.QColor(base)
            if index < len(trail) - 1:
                colour.setAlpha(self.FADE_FLOOR + int(
                    (255 - self.FADE_FLOOR) * index / max(1, len(trail) - 1)))
            self._draw_footprint(painter, self._cell_point(cell),
                                 float(self.win.px(self.FOOT)), colour)

        if self.game.finished:
            centre = self._cell_point(self.game.goal)
            painter.setPen(QtGui.QPen(QtGui.QColor(c.faint), self.win.px(5)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(centre, self.win.px(34), self.win.px(34))

    #: How wide a pickup is drawn, as a share of the board's width: the three corner ones and
    #: the seven others. The corners hold a clear 12x12 block of a 160x90 grid, which is where
    #: the big number comes from -- it fills the room Harry left and no more.
    BIG_WIDE, SMALL_WIDE = 0.06875, 0.03125

    #: The footprints, one colour per scenery. Harry, 25 November 2026: "the footprint in the
    #: hedge garden will be white and stay white when walking. in city streets the footprints
    #: will be black & remain black throughout. in night clouds, the footprints should be red
    #: throughout."
    #:
    #: MEASURED AGAINST EACH FLOOR rather than taken on trust, because the three floors are
    #: nothing like each other -- the median of the middle of each picture is slate (84,128,136),
    #: pale grey (216,219,218) and deep navy (16,40,89). Contrast of the print against its own
    #: floor, by the usual sRGB formula:
    #:
    #:     hedge   white    4.36:1          city    black   15.06:1
    #:     cloud   #FF5555   4.55:1         cloud   the mat's own red #B4443A   2.63:1
    #:
    #: THE RED IS NOT THE MAT'S RED, and that is the one choice here that was not Harry's. The
    #: mat's brick is a dark red made to sit on white, and on a near-black floor it comes out
    #: at 2.63:1 -- there, but a smudge. #FF5555 is the same red lifted until it clears 4.5:1,
    #: which is the line below which a thing this small stops being reliably findable.
    #:
    #: NOT A CLASH WITH ITEM_COLOURS[0], which is a near-identical red. That one is drawn on
    #: the 7in side map and these are on the big board, so the two are never on one screen.
    #: Checked rather than assumed -- see the route line in the hint painter.
    FOOT_COLOURS = {"hedge": "#FFFFFF", "city": "#000000", "cloud": "#FF5555"}

    #: How much of itself the OLDEST print in the trail still carries, out of 255. Was 70,
    #: chosen when there was one board and the prints were green.
    #:
    #: What the oldest print actually measures against its own floor, blended:
    #:
    #:             alpha 70     alpha 120
    #:     hedge     1.61:1       2.19:1
    #:     city      1.91:1       3.38:1
    #:     cloud     1.35:1       1.85:1
    #:
    #: 120 rather than 70 because 1.35:1 is not a faint print, it is no print: the navy trail
    #: simply stopped a third of the way back. 1.85 is faint and there, which is what the far
    #: end of a trail is for. It is NOT a legible contrast and is not claimed as one -- the
    #: oldest print is history, and the prints that have to be readable are the recent ones,
    #: which run up to full strength. Not raised further because at 140 the city's oldest
    #: print reaches 4.34:1 and the trail stops looking like a trail at all.
    FADE_FLOOR = 120

    def foot_colour(self) -> QtGui.QColor:
        """What the footprints are painted in on the board that is showing.

        Falls back to the mat's green, which is what every board used before 2.54, so adding
        a fourth scenery and forgetting this table gives dull footprints rather than none.
        """
        return QtGui.QColor(self.FOOT_COLOURS.get(self.game.level["name"], palette().green))

    def board_floor(self) -> QtGui.QColor:
        """The colour of the floor of whichever board is showing, read off the picture.

        Cached per board, because this walks the picture and paintEvent is not the place to do
        that: measured at 132ms for the same job on the pillar board, which is seven frames a
        second while a child drags something.

        The MEDIAN of the middle of the picture, not the mean and not the commonest exact
        pixel. The mean slides towards whatever is drawn; the commonest exact value is fine
        here but would fail on a board with a gradient or noise in its floor, and these three
        are painted.
        """
        if self._floor_for != self.game.scene:
            image = self.images[self.game.scene]
            colour = QtGui.QColor("#202020")
            if not image.isNull():
                shot = image.toImage()
                wide, tall = shot.width(), shot.height()
                reds, greens, blues = [], [], []
                for y in range(tall // 4, tall * 3 // 4, max(1, tall // 60)):
                    for x in range(wide // 4, wide * 3 // 4, max(1, wide // 60)):
                        pixel = shot.pixelColor(x, y)
                        reds.append(pixel.red())
                        greens.append(pixel.green())
                        blues.append(pixel.blue())
                mid = lambda vs: sorted(vs)[len(vs) // 2]
                colour = QtGui.QColor(mid(reds), mid(greens), mid(blues))
            self._floor = colour
            self._floor_for = self.game.scene
        return self._floor

    def _draw_gate(self, painter, box: QtCore.QRectF) -> None:
        """A barred gate across the mosque door, until everything has been collected."""
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#6B4A1F"))
        painter.drawRoundedRect(box, self.win.px(6), self.win.px(6))
        bar = QtGui.QPen(QtGui.QColor("#D9A441"), max(2.0, box.width() / 14))
        painter.setPen(bar)
        for n in range(1, 4):
            x = box.left() + box.width() * n / 4
            painter.drawLine(QtCore.QPointF(x, box.top() + box.height() * 0.12),
                             QtCore.QPointF(x, box.bottom() - box.height() * 0.08))
        painter.drawLine(QtCore.QPointF(box.left(), box.top() + box.height() * 0.38),
                         QtCore.QPointF(box.right(), box.top() + box.height() * 0.38))
        painter.restore()

    def draw_the_things(self, painter) -> None:
        """Every pickup still on the board, as its own drawing.

        The first three are drawn big: they are the three things a child actually does before
        praying, they sit in the corners Harry left clear for them, and their size is what
        makes the walk to a corner worth making.
        """
        for index, cell in enumerate(self.game.items):
            if cell in self.game.collected:
                continue
            art = ItemPictures.get(self.win, self.game.ITEM_ART[index])
            if art is None or art.isNull():
                continue
            # THE LONGEST SIDE GETS THE ALLOWANCE, not the width. The room each drawing was
            # placed in was measured as a radius -- so many cells of clear floor in every
            # direction -- and a jug two-thirds as wide as it is tall, sized by its width,
            # stands a third of itself out into the hedge. Sized by whichever side is longer,
            # the whole picture fits the room that was measured for it.
            share = self.BIG_WIDE if index < self.game.BIG else self.SMALL_WIDE
            scale = self.width() * share / max(1, max(art.width(), art.height()))
            wide, tall = art.width() * scale, art.height() * scale
            centre = self._cell_point(cell)
            painter.drawPixmap(QtCore.QRectF(centre.x() - wide / 2, centre.y() - tall / 2,
                                             wide, tall),
                               art, QtCore.QRectF(art.rect()))

    def what_we_are_after(self):
        """Which thing the line on the map points at, chosen once per thing collected.

        Rules.nearest_objective searches the board once FOR EVERY remaining item to find the
        closest -- nine searches on expert. Called on every redraw that cost more than the
        drawing did: it was most of the 112ms a step this was measured at.

        It only needs asking when the answer can have changed, which is when something has
        been collected or the gate has opened. Keeping the same objective in between is also
        better to follow: a line that re-aims itself every time a child shuffles a step is a
        line that is hard to walk along.
        """
        key = (self.game.scene, len(self.game.collected), self.game.gate_open)
        if self._after_key != key:
            self._after = self.game.nearest_objective()
            self._after_key = key
        return self._after

    def the_way_to(self, objective):
        """The cells from the child to their objective, worked out cheaply enough to redraw.

        SEARCHED FROM THE OBJECTIVE, NOT FROM THE CHILD, and that is the whole trick. The
        obvious route_to(objective) runs a fresh search of the whole board every time anything
        moves: measured at 42ms a step on beginner and 67ms on expert, against a move timer
        that fires every 24ms. On a Pi, several times slower again, the game would have
        crawled -- a help that makes the thing it is helping unusable.

        The objective changes nine times in a game; the child moves hundreds of times. So the
        search runs once per objective and stores how far every cell is FROM it, and each
        redraw just walks downhill from wherever the child is. That is a few hundred
        comparisons instead of ten thousand.

        Keyed on the gate as well as the level, because opening the gate adds a way through
        the mosque wall and so changes every distance behind it.
        """
        key = (self.game.scene, objective, self.game.gate_open)
        if self._field_key != key:
            self._field = self.game.distances(objective)
            self._field_key = key
        cell = self.game.player
        if cell not in self._field:
            return []
        route = [cell]
        while cell != objective and len(route) < len(self._field):
            nearer = [near for near in self.game.neighbours(cell)
                      if near in self._field and self._field[near] < self._field[cell]]
            if not nearer:
                break
            cell = min(nearer, key=lambda near: self._field[near])
            route.append(cell)
        return route

    def draw_the_way(self, painter, wide: float, tall: float) -> None:
        """On the little map only: a line from where the child is to what they are after.

        Harry, 15 November 2026, on the expert maze: "there is no way to collect the items as
        the routes lead to dead ends." They were all reachable -- I had walked every one -- but
        reaching them means tracing about 1,975 cells of corridor on expert, against 424 on
        beginner, and a child cannot see round a corner. The maze was not unfair, it was
        unreadable.

        ON THE 7in AND NOT ON THE BOARD, which is the whole idea. The big screen keeps the
        maze exactly as it was, so finding the way is still the game; the little screen is a
        map, and drawing the route on a map is what a map is for. A child who wants to work it
        out can ignore it, the way you can ignore a signpost.

        IN THE COLOUR OF WHAT IT LEADS TO, so the line explains itself: blue while it is
        taking you to the blue thing, green once everything is collected and the only thing
        left is the mosque. Nothing has to say in words what the line means, which also means
        nothing has to say it in ten languages.
        """
        objective = self.what_we_are_after()
        if objective is None or self.game.finished:
            return
        colour = QtGui.QColor(palette().green)
        for index, cell in enumerate(self.game.items):
            if cell == objective:
                colour = QtGui.QColor(
                    self.game.ITEM_COLOURS[index % len(self.game.ITEM_COLOURS)])
        route = self.the_way_to(objective)

        def middle(cell):
            return QtCore.QPointF((cell[0] + 0.5) * wide, (cell[1] + 0.5) * tall)

        if len(route) > 1:
            faint = QtGui.QColor(colour)
            faint.setAlpha(150)
            pen = QtGui.QPen(faint, max(1.0, wide * 0.8))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(QtGui.QPolygonF([middle(cell) for cell in route]))

        # And where the child is now, or the line starts from nowhere.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawEllipse(middle(self.game.player), wide * 1.6, tall * 1.6)

    def _update_hint(self) -> None:
        if not hasattr(self, "hint"):
            return
        image = self.images[self.game.scene]
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
        wide = shown.width() / self.game.WIDTH
        tall = shown.height() / self.game.HEIGHT
        painter = QtGui.QPainter(shown)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        # The things still to find, as little pictures. The paragraph above is about the ones
        # already found, and it still holds -- it is just that since 2.53 "gone from the map"
        # takes care of itself: the pictures are drawn here rather than painted into the board,
        # so a collected thing is one this loop skips.
        for index, cell in enumerate(self.game.items):
            if cell in self.game.collected:
                continue
            art = ItemPictures.get(self.win, self.game.ITEM_ART[index])
            if art is None or art.isNull():
                continue
            span = wide * (12 if index < self.game.BIG else 7)
            high = span * art.height() / max(1, art.width())
            painter.drawPixmap(
                QtCore.QRectF((cell[0] + 0.5) * wide - span / 2,
                              (cell[1] + 0.5) * tall - high / 2, span, high),
                art, QtCore.QRectF(art.rect()))
        self.draw_the_way(painter, wide, tall)
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
