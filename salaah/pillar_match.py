"""Pillar Match: drag each object to the matching pillar of Islam.

The 16-inch touchscreen is artwork-only. The companion widget is for the
7-inch screen. A Bluetooth ring remains usable as an alternative input.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette

PILLARS = ("faith", "prayer", "charity", "fasting", "hajj")


@dataclass(frozen=True)
class Item:
    key: str
    pillar: str
    art: str


ITEMS = (
    Item("testimony", "faith", "scroll"),
    Item("one_finger", "faith", "finger"),
    Item("prayer_rug", "prayer", "rug"),
    Item("mosque", "prayer", "mosque"),
    Item("charity_box", "charity", "charity_box"),
    Item("coins", "charity", "coins"),
    Item("dates", "fasting", "dates"),
    Item("iftar", "fasting", "plate"),
    Item("kaaba", "hajj", "kaaba"),
    Item("pilgrimage_bag", "hajj", "bag"),
)


class Rules:
    """Pure state: no Qt, files, clocks or device knowledge."""

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.restart()

    def restart(self) -> None:
        self.sequence = list(ITEMS)
        self._shuffle(self.sequence)
        self.at = 0
        self.active = 0
        self.locked = False
        self.done = False
        self.attempted = False
        self.last = "ready"
        self.first_try = 0

    @property
    def rounds(self) -> int:
        return len(self.sequence)

    @property
    def item(self) -> Item:
        return self.sequence[self.at]

    @property
    def correct(self) -> int:
        return PILLARS.index(self.item.pillar)

    def step(self) -> None:
        if not self.done and not self.locked:
            self.active = (self.active + 1) % len(PILLARS)

    def answer(self, which: int) -> str:
        if self.done or self.locked or not 0 <= which < len(PILLARS):
            return "nothing"
        self.active = which
        if which != self.correct:
            self.attempted = True
            self.last = "wrong"
            return "wrong"
        if not self.attempted:
            self.first_try += 1
        self.locked = True
        self.last = "correct"
        return "correct"

    def next_round(self) -> str:
        if not self.locked:
            return "nothing"
        if self.at + 1 >= self.rounds:
            self.done = True
            self.locked = False
            self.last = "complete"
            return "complete"
        self.at += 1
        self.active = 0
        self.locked = False
        self.attempted = False
        self.last = "ready"
        return "next"

    def press(self) -> str:
        if self.done:
            self.restart()
            return "again"
        if self.locked:
            return self.next_round()
        return self.answer(self.active)


class ItemArt:
    """Simple face-free monochrome pictograms drawn in the live palette."""

    @staticmethod
    def draw(p, kind, rect, window, ink, paper) -> None:
        p.save()
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        line = max(2, window.px(4))
        pen = QtGui.QPen(QtGui.QColor(ink), line, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(QtGui.QColor(ink))
        cx, cy, w, h = rect.center().x(), rect.center().y(), rect.width(), rect.height()

        if kind == "scroll":
            card = QtCore.QRectF(cx - w * .31, cy - h * .30, w * .62, h * .55)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(card, w * .04, w * .04)
            for y in (-.14, -.02, .10):
                p.drawLine(QtCore.QPointF(cx - w * .19, cy + h * y),
                           QtCore.QPointF(cx + w * .19, cy + h * y))
            p.drawArc(QtCore.QRectF(cx - w * .39, cy - h * .34, w * .18, h * .18),
                      90 * 16, 180 * 16)
            p.drawArc(QtCore.QRectF(cx + w * .21, cy + h * .15, w * .18, h * .18),
                      -90 * 16, 180 * 16)
        elif kind == "finger":
            hand = QtGui.QPainterPath()
            hand.moveTo(cx - w * .20, cy + h * .30)
            hand.lineTo(cx - w * .20, cy - h * .02)
            hand.quadTo(cx - w * .20, cy - h * .13, cx - w * .10, cy - h * .13)
            hand.lineTo(cx - w * .10, cy + h * .02)
            hand.lineTo(cx - w * .04, cy - h * .34)
            hand.quadTo(cx, cy - h * .46, cx + w * .07, cy - h * .34)
            hand.lineTo(cx + w * .08, cy + h * .02)
            hand.lineTo(cx + w * .15, cy - h * .10)
            hand.quadTo(cx + w * .24, cy - h * .12, cx + w * .24, cy)
            hand.lineTo(cx + w * .20, cy + h * .25)
            hand.closeSubpath()
            p.drawPath(hand)
        elif kind == "rug":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QtCore.QRectF(cx - w * .28, cy - h * .36,
                                            w * .56, h * .68), w * .03, w * .03)
            arch = QtGui.QPainterPath()
            arch.moveTo(cx - w * .16, cy + h * .18)
            arch.lineTo(cx - w * .16, cy - h * .08)
            arch.quadTo(cx, cy - h * .31, cx + w * .16, cy - h * .08)
            arch.lineTo(cx + w * .16, cy + h * .18)
            p.drawPath(arch)
            for dx in (-.22, -.11, 0, .11, .22):
                p.drawLine(QtCore.QPointF(cx + w * dx, cy + h * .32),
                           QtCore.QPointF(cx + w * dx, cy + h * .41))
        elif kind == "mosque":
            p.drawRect(QtCore.QRectF(cx - w * .32, cy, w * .64, h * .26))
            p.drawEllipse(QtCore.QRectF(cx - w * .25, cy - h * .24, w * .50, h * .40))
            for x in (-.34, .26):
                p.drawRect(QtCore.QRectF(cx + w * x, cy - h * .22, w * .08, h * .48))
                p.drawPolygon(QtGui.QPolygonF([
                    QtCore.QPointF(cx + w * (x - .02), cy - h * .22),
                    QtCore.QPointF(cx + w * (x + .04), cy - h * .38),
                    QtCore.QPointF(cx + w * (x + .10), cy - h * .22)]))
            p.setBrush(QtGui.QColor(paper))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QtCore.QRectF(cx - w * .06, cy + h * .08,
                                            w * .12, h * .18), w * .05, w * .05)
        elif kind == "charity_box":
            p.drawRoundedRect(QtCore.QRectF(cx - w * .31, cy - h * .10,
                                            w * .62, h * .39), w * .04, w * .04)
            p.drawRect(QtCore.QRectF(cx - w * .25, cy - h * .22, w * .50, h * .13))
            p.setPen(QtGui.QPen(QtGui.QColor(paper), line))
            p.drawLine(QtCore.QPointF(cx - w * .10, cy - h * .15),
                       QtCore.QPointF(cx + w * .10, cy - h * .15))
            heart = QtGui.QPainterPath()
            heart.moveTo(cx, cy + h * .19)
            heart.cubicTo(cx - w * .17, cy + h * .07,
                          cx - w * .12, cy - h * .03, cx, cy + h * .04)
            heart.cubicTo(cx + w * .12, cy - h * .03,
                          cx + w * .17, cy + h * .07, cx, cy + h * .19)
            p.drawPath(heart)
        elif kind == "coins":
            for x, y in ((-.22, .06), (0, .14), (.22, .02), (-.08, -.13), (.14, -.22)):
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QtCore.QRectF(cx + w * x - w * .10,
                                             cy + h * y - w * .10, w * .20, w * .20))
                p.drawLine(QtCore.QPointF(cx + w * x, cy + h * y - w * .055),
                           QtCore.QPointF(cx + w * x, cy + h * y + w * .055))
        elif kind == "dates":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QtCore.QPointF(cx, cy - h * .34), QtCore.QPointF(cx, cy - h * .14))
            p.drawLine(QtCore.QPointF(cx, cy - h * .22), QtCore.QPointF(cx - w * .22, cy - h * .10))
            p.drawLine(QtCore.QPointF(cx, cy - h * .18), QtCore.QPointF(cx + w * .22, cy - h * .06))
            p.setBrush(QtGui.QColor(ink))
            for x, y in ((-.24, .02), (-.08, .13), (.10, .03), (.25, .15), (0, .29)):
                p.drawEllipse(QtCore.QRectF(cx + w * x - w * .075,
                                             cy + h * y - h * .10, w * .15, h * .20))
        elif kind == "plate":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QtCore.QRectF(cx - w * .27, cy - h * .10, w * .54, h * .36))
            p.drawEllipse(QtCore.QRectF(cx - w * .17, cy - h * .04, w * .34, h * .22))
            p.drawLine(QtCore.QPointF(cx - w * .35, cy - h * .27),
                       QtCore.QPointF(cx - w * .35, cy + h * .27))
            p.drawLine(QtCore.QPointF(cx + w * .35, cy - h * .27),
                       QtCore.QPointF(cx + w * .35, cy + h * .27))
            for dx in (-.08, .08):
                p.drawArc(QtCore.QRectF(cx + w * dx - w * .06, cy - h * .36,
                                        w * .12, h * .21), 20 * 16, 140 * 16)
        elif kind == "kaaba":
            top = QtGui.QPolygonF([QtCore.QPointF(cx - w * .29, cy - h * .22),
                                   QtCore.QPointF(cx, cy - h * .36),
                                   QtCore.QPointF(cx + w * .29, cy - h * .22),
                                   QtCore.QPointF(cx, cy - h * .08)])
            left = QtGui.QPolygonF([top[0], top[3], QtCore.QPointF(cx, cy + h * .34),
                                    QtCore.QPointF(cx - w * .29, cy + h * .17)])
            right = QtGui.QPolygonF([top[3], top[2], QtCore.QPointF(cx + w * .29, cy + h * .17),
                                     QtCore.QPointF(cx, cy + h * .34)])
            p.drawPolygon(top); p.drawPolygon(left); p.drawPolygon(right)
            p.setPen(QtGui.QPen(QtGui.QColor(paper), line))
            p.drawLine(QtCore.QPointF(cx - w * .28, cy - h * .08),
                       QtCore.QPointF(cx, cy + h * .07))
            p.drawLine(QtCore.QPointF(cx, cy + h * .07),
                       QtCore.QPointF(cx + w * .28, cy - h * .08))
        else:
            p.drawRoundedRect(QtCore.QRectF(cx - w * .29, cy - h * .16,
                                            w * .58, h * .45), w * .04, w * .04)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QtCore.QRectF(cx - w * .16, cy - h * .36,
                                    w * .32, h * .36), 0, 180 * 16)
            p.drawLine(QtCore.QPointF(cx - w * .29, cy + h * .02),
                       QtCore.QPointF(cx + w * .29, cy + h * .02))
            p.drawLine(QtCore.QPointF(cx, cy - h * .16), QtCore.QPointF(cx, cy + h * .29))
        p.restore()


class ItemPreview(QtWidgets.QFrame):
    def __init__(self, window):
        super().__init__()
        self.win = window
        self.kind = "scroll"
        self.setMinimumHeight(window.px(200))

    def show_kind(self, kind) -> None:
        self.kind = kind
        self.update()

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        margin = self.win.px(8)
        box = QtCore.QRectF(self.rect()).adjusted(margin, margin, -margin, -margin)
        p.setPen(QtGui.QPen(QtGui.QColor(c.paper), self.win.px(3)))
        p.setBrush(QtGui.QColor(c.paper))
        p.drawRoundedRect(box, self.win.px(14), self.win.px(14))
        art = box.adjusted(box.width() * .18, box.height() * .12,
                           -box.width() * .18, -box.height() * .12)
        ItemArt.draw(p, self.kind, art, self.win, c.ink, c.paper)


class PillarBoard(QtWidgets.QFrame):
    """Artwork-only board with a draggable current item."""

    dropped = Signal(int)

    def __init__(self, window, game, board):
        super().__init__()
        self.win = window
        self.game = game
        self.board = board
        self.dragging = False
        self.drag_position = None
        self.wrong_zone = None
        self._ignore_mouse_release = False
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _zones(self):
        centers = (.125, .3125, .5, .6875, .875)
        return [QtCore.QRectF(self.width() * (center - .075), self.height() * .48,
                              self.width() * .15, self.height() * .37)
                for center in centers]

    def _home(self):
        return QtCore.QPointF(self.width() * .5, self.height() * .22)

    def _item_rect(self, center=None, small=False):
        center = center or self._home()
        side = min(self.width() * (.082 if small else .11),
                   self.height() * (.20 if small else .27))
        return QtCore.QRectF(center.x() - side / 2, center.y() - side / 2, side, side)

    def reset_item(self) -> None:
        self.dragging = False
        self.drag_position = None
        self.wrong_zone = None
        self.update()

    def reject(self, which) -> None:
        self.dragging = False
        self.drag_position = None
        self.wrong_zone = which
        self.update()

    def _zone_at(self, point):
        for index, zone in enumerate(self._zones()):
            if zone.contains(point):
                return index
        return None

    def paintEvent(self, _):
        c = palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QtGui.QColor(c.ink))
        if not self.board.isNull():
            p.drawPixmap(QtCore.QRectF(self.rect()), self.board,
                         QtCore.QRectF(self.board.rect()))
        zones = self._zones()
        if not self.game.done:
            if not self.dragging and not self.game.locked:
                p.setPen(QtGui.QPen(QtGui.QColor(c.lapis), self.win.px(6)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(zones[self.game.active], self.win.px(12), self.win.px(12))
            if self.wrong_zone is not None:
                p.setPen(QtGui.QPen(QtGui.QColor(c.highlight), self.win.px(7)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(zones[self.wrong_zone], self.win.px(12), self.win.px(12))
            center = self.drag_position or self._home()
            small = False
            if self.game.locked:
                center = zones[self.game.correct].center()
                small = True
            ItemArt.draw(p, self.game.item.art, self._item_rect(center, small),
                         self.win, c.paper, c.ink)

    def _start_drag(self, point):
        if self.game.done or self.game.locked:
            return False
        target = self._item_rect(self.drag_position or self._home()).adjusted(
            -self.win.px(24), -self.win.px(24), self.win.px(24), self.win.px(24))
        if not target.contains(point):
            return False
        self.wrong_zone = None
        self.dragging = True
        self.drag_position = point
        self.update()
        return True

    def _move_drag(self, point):
        if self.dragging:
            self.drag_position = point
            self.update()

    def _finish_drag(self, point):
        if not self.dragging:
            return
        self.dragging = False
        self.drag_position = point
        which = self._zone_at(point)
        if which is None:
            self.drag_position = None
            self.update()
        else:
            self.dropped.emit(which)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_drag(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._move_drag(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._ignore_mouse_release:
            self._ignore_mouse_release = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._finish_drag(event.position())
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
        if kind == QtCore.QEvent.Type.TouchBegin:
            point = self._touch_position(event)
            if point is not None:
                self._start_drag(point)
            event.accept()
            return True
        if kind == QtCore.QEvent.Type.TouchUpdate:
            point = self._touch_position(event)
            if point is not None:
                self._move_drag(point)
            event.accept()
            return True
        if kind == QtCore.QEvent.Type.TouchEnd:
            point = self._touch_position(event)
            if point is not None:
                self._finish_drag(point)
            self._ignore_mouse_release = True
            event.accept()
            return True
        return super().event(event)


class Screen(QtWidgets.QWidget):
    """Main 16-inch game screen with its 7-inch companion attached."""

    CYCLE = 1350
    SHOWN = 1050
    leave = Signal()
    changed = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = Rules(shuffle)
        self.setObjectName("pillarMatchMain")
        self.board_image = QtGui.QPixmap(str(window.assets / "children" / self.BOARD))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.board = PillarBoard(window, self.game, self.board_image)
        self.board.dropped.connect(self._drop)
        layout.addWidget(self.board)
        self._scan = QtCore.QTimer(self)
        self._scan.setInterval(self.CYCLE)
        self._scan.timeout.connect(self._scan_step)
        self._advance = QtCore.QTimer(self)
        self._advance.setSingleShot(True)
        self._advance.timeout.connect(self._next)
        self.companion = self._build_companion()
        self.changed.connect(self.board.update)
        self.changed.connect(self.retell)
        self.follow_theme()
        self.start_again()

    #: The one picture this game needs, named once so the loader and playable() cannot drift.
    BOARD = "pillar-match-board.png"

    @property
    def ready(self) -> bool:
        """Whether the board is on the mat. See journey_jigsaw.Screen.ready."""
        return not self.board_image.isNull()

    @staticmethod
    def playable(assets) -> bool:
        """Can this game be built at all? Asked of the DISK, before anything is constructed.

        Added here; the pack did not offer it. Since 1.97 the children's menu builds a game only
        when a child first opens it, and decides whether to offer the tile at all by asking the
        filesystem for the artwork -- see ui.build_corner. A module with no playable() is taken
        to be always playable, so without this a mat that never received the board would show a
        tile that opens a screen with a blank rectangle on it.
        """
        return (assets / "children" / Screen.BOARD).is_file()

    def _build_companion(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("pillarMatchCompanion")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.px(20), self.win.px(18),
                                  self.win.px(20), self.win.px(18))
        layout.setSpacing(self.win.px(10))
        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.progress = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress)
        self.preview = ItemPreview(self.win)
        layout.addWidget(self.preview, 1)
        self.item_name = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.item_name.setWordWrap(True)
        layout.addWidget(self.item_name)
        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setWordWrap(True)
        layout.addWidget(self.question)
        self.feedback = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(self.win.px(10))
        self.new_button = QtWidgets.QPushButton()
        self.new_button.setObjectName("controlButton")
        self.new_button.setMinimumHeight(self.win.px(64))
        self.new_button.clicked.connect(self.start_again)
        controls.addWidget(self.new_button, 1)
        self.exit_button = QtWidgets.QPushButton()
        self.exit_button.setObjectName("controlButton")
        self.exit_button.setMinimumHeight(self.win.px(64))
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

    def _pillar_name(self, key):
        return self.win.t("pillar_match.pillar." + key)

    def retell(self) -> None:
        t, game = self.win.t, self.game
        self.title.setText(t("pillar_match.title"))
        self.new_button.setText(t("pillar_match.new_game"))
        self.exit_button.setText(t("pillar_match.exit"))
        if game.done:
            self.progress.setText(t("pillar_match.progress", at=str(game.rounds),
                                    of=str(game.rounds)))
            self.item_name.clear()
            self.question.setText(t("pillar_match.complete"))
            self.feedback.setText(t("pillar_match.complete_score",
                                    score=str(game.first_try), of=str(game.rounds)))
            self.preview.hide()
        else:
            self.preview.show()
            self.preview.show_kind(game.item.art)
            self.progress.setText(t("pillar_match.progress", at=str(game.at + 1),
                                    of=str(game.rounds)))
            self.item_name.setText(t("pillar_match.item." + game.item.key))
            self.question.setText(t("pillar_match.question"))
            if game.last == "correct":
                self.feedback.setText(t("pillar_match.correct",
                                        pillar=self._pillar_name(game.item.pillar)))
            elif game.last == "wrong":
                self.feedback.setText(t("pillar_match.wrong"))
            else:
                self.feedback.setText(t("pillar_match.instruction"))
        self.title.setFont(self._font(self.title.text(), 31, True))
        self.progress.setFont(self._font(self.progress.text(), 20, True))
        self.item_name.setFont(self._font(self.item_name.text(), 25, True))
        self.question.setFont(self._font(self.question.text(), 23, True))
        self.feedback.setFont(self._font(self.feedback.text(), 19, True))
        self.new_button.setFont(self._font(self.new_button.text(), 20, True))
        self.exit_button.setFont(self._font(self.exit_button.text(), 20, True))

    def follow_theme(self) -> None:
        c = palette()
        radius = self.win.px(11)
        edge = self.win.px(3)
        self.companion.setStyleSheet(
            # PAPER, not ink. This arrived inverted against the rest of the mat -- a white panel
            # at night and a black one by day -- which is how Prayer Day Journey arrived too.
            # The 7in beside this game would have been the opposite colour to the other five
            # and to every other screen.
            f"QWidget#pillarMatchCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            # AND THE EDGE IS INK, not paper. It was the same colour as the button's own fill,
            # so New Game and Exit had no visible outline at all -- the same fault, again, as
            # Prayer Day's answer buttons. paper and ink are the one pair this palette
            # guarantees to be opposites in both themes.
            f"QPushButton#controlButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; border-radius: {radius}px; }}"
            f"QPushButton:pressed {{ background: {c.pressed}; color: {c.ink}; }}")
        self.retell()
        self.board.update()
        self.preview.update()

    def start_again(self) -> None:
        self._advance.stop()
        self._scan.stop()
        self.game.restart()
        self.board.reset_item()
        self._scan.start()
        self.changed.emit()

    def _drop(self, which) -> None:
        result = self.game.answer(which)
        if result == "correct":
            self._scan.stop()
            self.board.drag_position = None
            self.changed.emit()
            self._advance.start(self.SHOWN)
        elif result == "wrong":
            self.board.reject(which)
            self.changed.emit()

    def _next(self) -> None:
        result = self.game.next_round()
        self.board.reset_item()
        if result == "next":
            self._scan.start()
        else:
            self._scan.stop()
        self.changed.emit()

    def _scan_step(self) -> None:
        self.game.step()
        self.changed.emit()

    def press(self, action="") -> None:
        from .buttons import BACK
        if action == BACK or str(action).lower() in ("back", "exit", "escape"):
            self._scan.stop()
            self._advance.stop()
            self.leave.emit()
            return
        result = self.game.press()
        if result == "correct":
            self._scan.stop()
            self._advance.start(self.SHOWN)
        elif result == "wrong":
            self.board.reject(self.game.active)
        elif result in ("next", "complete"):
            self._advance.stop()
            self.board.reset_item()
            if result == "next":
                self._scan.start()
            else:
                self._scan.stop()
        elif result == "again":
            self.board.reset_item()
            self._scan.start()
        self.changed.emit()

    def showEvent(self, event):
        self.follow_theme()
        if not self.game.done and not self.game.locked:
            self._scan.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._scan.stop()
        self._advance.stop()
        super().hideEvent(event)


