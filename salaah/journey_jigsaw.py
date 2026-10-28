"""Islamic Jigsaw: a native multi-picture, multi-level game for both MySalaah screens.

The 16-inch screen is deliberately only the shuffled picture. The companion widget is
intended for the 7-inch touch screen and contains the complete hint, translated title,
Picture, Difficulty, New Game and Exit controls. No web server, browser, worker or file write is used.
"""
from __future__ import annotations

import random

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


class Rules:
    """Pure, deterministic-testable rules for all three difficulty grids."""

    GRIDS = ((3, 2), (4, 3), (6, 3))
    PICTURE_COUNT = 5

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.difficulty = 0
        self.picture = 0
        self.restart()

    @property
    def columns(self) -> int:
        return self.GRIDS[self.difficulty][0]

    @property
    def rows(self) -> int:
        return self.GRIDS[self.difficulty][1]

    @property
    def piece_count(self) -> int:
        return self.columns * self.rows

    def restart(self) -> None:
        self.order = list(range(self.piece_count))
        self._shuffle(self.order)
        if self.order == list(range(self.piece_count)):
            self.order = self.order[1:] + self.order[:1]
        self.selected: int | None = None
        self.moves = 0

    @property
    def complete(self) -> bool:
        return self.order == list(range(self.piece_count))

    def cycle_difficulty(self) -> None:
        self.difficulty = (self.difficulty + 1) % len(self.GRIDS)
        self.restart()

    def cycle_picture(self) -> None:
        self.picture = (self.picture + 1) % self.PICTURE_COUNT
        self.restart()

    def press(self, slot: int) -> str:
        """Tap once to select a tile and tap another tile to swap it."""
        if not 0 <= slot < len(self.order):
            return "nothing"
        if self.selected is None:
            self.selected = slot
            return "selected"
        if self.selected == slot:
            self.selected = None
            return "nothing"
        source, self.selected = self.selected, None
        return self.swap(source, slot)

    def swap(self, source: int, target: int) -> str:
        if (not 0 <= source < len(self.order)
                or not 0 <= target < len(self.order)
                or source == target):
            return "nothing"
        self.order[source], self.order[target] = self.order[target], self.order[source]
        self.selected = None
        self.moves += 1
        return "moved"


class Screen(QtWidgets.QWidget):
    """Main touch puzzle; ``companion`` is mounted on the 7-inch screen."""

    leave = Signal()
    changed = Signal()

    #: The five pictures, in the order cycle_picture walks them, as they are named in
    #: assets/children. Written once: the loader and playable() both read this list, and
    #: before they did they each held their own copy of the same five names.
    PICTURES = ("kaaba-jigsaw.png", "journey-jigsaw.png", "ramadan-iftar-jigsaw.png",
                "eid-prayer-jigsaw.png", "quran-rehal-jigsaw.png")

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = Rules(shuffle)
        self.setObjectName("journeyJigsawMain")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        # ONE FILE PER PICTURE, and only one picture per file. The pack this came from shipped
        # a matched dark PNG beside every light one -- 7.6 MB of SD card and 29 MB of RAM --
        # and the two were pixel-exact inversions of each other, so the second was dropped and
        # the inversion done in a blit instead, the way the mat has done it since 1.76.
        #
        # Then the inversion itself was dropped. These pictures must not be turned over at all;
        # _image says why. What is left is the plain thing: five files, loaded once, drawn as
        # they are.
        base = window.assets / "children"
        self.images = tuple(QtGui.QPixmap(str(base / name)) for name in self.PICTURES)

        self._down_slot: int | None = None
        self._down_at = QtCore.QPointF()
        self._pointer = QtCore.QPointF()
        self._dragging = False
        self._ignore_mouse_release = False
        self._lifecycle_timer = QtCore.QTimer(self)

        self.companion = self._build_companion()
        self.follow_theme()
        self.changed.connect(self.update)
        self.changed.connect(self._update_hint)
        self.start_again()

    def _image(self):
        """The picture, as drawn, in both themes.

        IT USED TO BE TURNED OVER AFTER DARK and that was wrong, which is worth setting out
        because the convention it was following is right everywhere else on this mat.

        "Ship the light half and invert it for the dark screen" works for LINE ART -- black ink
        on white paper, where the inverse genuinely is the night version of the same drawing,
        and where one file does the work of two. The menus, the wu'du sheets, the postures and
        the front door are all that, and all still invert.

        These five are not. They are pictures of real places, with grey tones and silhouettes,
        and inverting them produces a photographic negative rather than a dark rendering. The
        Kaaba's kiswah came out WHITE, which is the one thing about it a child is most certain
        of; in three of the other four the people are drawn as dark silhouettes and came out as
        glowing white figures.

        So the artwork is shown as it was drawn and the chrome around it -- the banner, the
        panel, the lettering, the piece outlines -- still follows the theme, which is what
        makes the screen read as dark without lying about the picture.
        """
        return self.images[self.game.picture]

    @property
    def ready(self) -> bool:
        """Whether the pictures are on the mat.

        THE PICTURE IS THE QUESTION in a jigsaw, so a mat without the artwork shows no tile
        rather than a screen of blank rectangles. Asked of the files by Screen.playable before
        this is ever built -- see ui.build_corner -- so that a missing picture costs no widget
        at all; this stays for anything holding a built screen.
        """
        return all(not p.isNull() for p in self.images)

    @staticmethod
    def playable(assets) -> bool:
        """Can this game be built at all? Asked of the DISK, before anything is constructed.

        Readiness used to be decided by building a screen and asking it, which is why every
        game was built at start-up whether or not a child opened the menu. Pictures are files;
        a file is a question the filesystem can answer.
        """
        base = assets / "children"
        return all((base / name).is_file() for name in Screen.PICTURES)

    def _build_companion(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("journeyJigsawCompanion")

        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.px(22), self.win.px(22),
                                  self.win.px(22), self.win.px(22))
        layout.setSpacing(self.win.px(14))

        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.hint = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.hint.setObjectName("gameHint")
        self.hint.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                QtWidgets.QSizePolicy.Policy.Expanding)
        self.hint.setMinimumHeight(self.win.px(230))
        self.hint.installEventFilter(self)
        layout.addWidget(self.hint, 1)

        self.picture_button = QtWidgets.QPushButton()
        self.picture_button.setObjectName("gameButton")
        self.picture_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.picture_button.setMinimumHeight(self.win.px(64))
        self.picture_button.clicked.connect(self.cycle_picture)
        layout.addWidget(self.picture_button)

        self.difficulty_button = QtWidgets.QPushButton()
        self.difficulty_button.setObjectName("gameButton")
        self.difficulty_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.difficulty_button.setMinimumHeight(self.win.px(68))
        self.difficulty_button.clicked.connect(self.cycle_difficulty)
        layout.addWidget(self.difficulty_button)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(self.win.px(14))
        self.new_button = QtWidgets.QPushButton()
        self.new_button.setObjectName("gameButton")
        self.new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_button.setMinimumHeight(self.win.px(72))
        self.new_button.clicked.connect(self.start_again)
        controls.addWidget(self.new_button, 1)

        self.exit_button = QtWidgets.QPushButton()
        self.exit_button.setObjectName("gameButton")
        self.exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_button.setMinimumHeight(self.win.px(72))
        self.exit_button.clicked.connect(self.leave.emit)
        controls.addWidget(self.exit_button, 1)
        layout.addLayout(controls)

        self.retitle()
        return panel

    def retitle(self) -> None:
        title = self.win.t("journey_jigsaw.title")
        new_game = self.win.t("journey_jigsaw.new_game")
        exit_game = self.win.t("journey_jigsaw.exit")
        levels = (self.win.t("journey_jigsaw.beginner"),
                  self.win.t("journey_jigsaw.medium"),
                  self.win.t("journey_jigsaw.expert"))
        pictures = (self.win.t("journey_jigsaw.kaaba"),
                    self.win.t("journey_jigsaw.journey"),
                    self.win.t("journey_jigsaw.ramadan_iftar"),
                    self.win.t("journey_jigsaw.eid_prayer"),
                    self.win.t("journey_jigsaw.quran_rehal"))
        level = levels[self.game.difficulty]
        picture_name = pictures[self.game.picture]
        picture = self.win.t("journey_jigsaw.picture").format(picture=picture_name)
        difficulty = self.win.t("journey_jigsaw.difficulty").format(level=level)
        self.title.setText(title)
        self.picture_button.setText(picture)
        self.difficulty_button.setText(difficulty)
        self.new_button.setText(new_game)
        self.exit_button.setText(exit_game)

        title_font = QtGui.QFont(Fonts.for_text(title))
        title_font.setPixelSize(self.win.px(38))
        title_font.setWeight(QtGui.QFont.Weight.Bold)
        self.title.setFont(title_font)
        for button, words in ((self.picture_button, picture),
                              (self.difficulty_button, difficulty),
                              (self.new_button, new_game),
                              (self.exit_button, exit_game)):
            button_font = QtGui.QFont(Fonts.for_text(words))
            button_font.setPixelSize(self.win.px(27))
            button_font.setWeight(QtGui.QFont.Weight.Bold)
            button.setFont(button_font)

    def follow_theme(self) -> None:
        c = palette()
        radius = self.win.px(12)
        edge = self.win.px(3)
        self.companion.setStyleSheet(
            f"QWidget#journeyJigsawCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            f"QPushButton#gameButton {{ background: {c.panel}; color: {c.paper}; "
            f"border: {edge}px solid {c.ink}; border-radius: {radius}px; }}"
            f"QPushButton#gameButton:pressed {{ background: {c.pressed}; color: {c.ink}; }}"
        )
        self._update_hint()
        self.update()

    def cycle_picture(self) -> None:
        self._down_slot = None
        self._dragging = False
        self.game.cycle_picture()
        self.retitle()
        self.changed.emit()

    def cycle_difficulty(self) -> None:
        self._down_slot = None
        self._dragging = False
        self.game.cycle_difficulty()
        self.retitle()
        self.changed.emit()

    def start_again(self) -> None:
        self._down_slot = None
        self._dragging = False
        self.game.restart()
        self.changed.emit()

    def press(self, action) -> None:
        """Optional host-key compatibility; touch remains the normal control."""
        if str(action).lower() in ("back", "exit", "escape"):
            self.leave.emit()

    def _cell_at(self, point: QtCore.QPointF) -> int | None:
        if not self.rect().contains(point.toPoint()) or self.width() <= 0 or self.height() <= 0:
            return None
        columns, rows = self.game.columns, self.game.rows
        col = min(columns - 1, max(0, int(point.x() * columns / self.width())))
        row = min(rows - 1, max(0, int(point.y() * rows / self.height())))
        return row * columns + col

    def _begin_pointer(self, point: QtCore.QPointF) -> None:
        self._down_slot = self._cell_at(point)
        self._down_at = point
        self._pointer = point
        self._dragging = False
        self.update()

    def _move_pointer(self, point: QtCore.QPointF) -> None:
        if self._down_slot is None:
            return
        self._pointer = point
        distance = point - self._down_at
        if distance.x() * distance.x() + distance.y() * distance.y() > self.win.px(18) ** 2:
            self._dragging = True
        self.update()

    def _end_pointer(self, point: QtCore.QPointF) -> None:
        source, target = self._down_slot, self._cell_at(point)
        dragged = self._dragging
        self._down_slot = None
        self._dragging = False
        if source is None or target is None:
            self.update()
            return
        if dragged:
            self.game.swap(source, target)
        else:
            self.game.press(target)
        self.changed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._ignore_mouse_release = False
            self._begin_pointer(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._move_pointer(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._ignore_mouse_release:
            self._ignore_mouse_release = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._end_pointer(event.position())
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
            if point is None:
                return True
            if kind == QtCore.QEvent.Type.TouchBegin:
                self._begin_pointer(point)
            elif kind == QtCore.QEvent.Type.TouchUpdate:
                self._move_pointer(point)
            else:
                self._end_pointer(point)
                self._ignore_mouse_release = True
            event.accept()
            return True
        return super().event(event)

    def eventFilter(self, watched, event):
        if watched is self.hint and event.type() == QtCore.QEvent.Type.Resize:
            self._update_hint()
        return super().eventFilter(watched, event)

    def _source_rect(self, piece: int, image) -> QtCore.QRectF:
        columns, rows = self.game.columns, self.game.rows
        row, col = divmod(piece, columns)
        x0 = col * image.width() / columns
        x1 = (col + 1) * image.width() / columns
        y0 = row * image.height() / rows
        y1 = (row + 1) * image.height() / rows
        return QtCore.QRectF(x0, y0, x1 - x0, y1 - y0)

    def _target_rect(self, slot: int) -> QtCore.QRectF:
        columns, rows = self.game.columns, self.game.rows
        row, col = divmod(slot, columns)
        x0 = col * self.width() / columns
        x1 = (col + 1) * self.width() / columns
        y0 = row * self.height() / rows
        y1 = (row + 1) * self.height() / rows
        return QtCore.QRectF(x0, y0, x1 - x0, y1 - y0)

    def paintEvent(self, _):
        c = palette()
        image = self._image()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QtGui.QColor(c.paper))
        if image.isNull():
            return

        for slot, piece in enumerate(self.game.order):
            if self._dragging and slot == self._down_slot:
                continue
            painter.drawPixmap(self._target_rect(slot), image, self._source_rect(piece, image))

        line = QtGui.QPen(QtGui.QColor(c.line), self.win.px(2))
        painter.setPen(line)
        columns, rows = self.game.columns, self.game.rows
        for step in range(1, columns):
            x = self.width() * step / columns
            painter.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, self.height()))
        for step in range(1, rows):
            y = self.height() * step / rows
            painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(self.width(), y))

        if self.game.selected is not None and not self._dragging:
            painter.setPen(QtGui.QPen(QtGui.QColor(c.lapis), self.win.px(7)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._target_rect(self.game.selected).adjusted(
                self.win.px(4), self.win.px(4), -self.win.px(4), -self.win.px(4)))

        if self._dragging and self._down_slot is not None:
            piece = self.game.order[self._down_slot]
            cell = self._target_rect(self._down_slot)
            floating = QtCore.QRectF(self._pointer.x() - cell.width() / 2,
                                     self._pointer.y() - cell.height() / 2,
                                     cell.width(), cell.height())
            painter.setOpacity(0.92)
            painter.drawPixmap(floating, image, self._source_rect(piece, image))
            painter.setOpacity(1.0)
            painter.setPen(QtGui.QPen(QtGui.QColor(c.lapis), self.win.px(7)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(floating)

    def _update_hint(self) -> None:
        if not hasattr(self, "hint"):
            return
        image = self._image()
        if image.isNull() or self.hint.width() <= 0 or self.hint.height() <= 0:
            self.hint.clear()
            return
        shown = image.scaled(self.hint.size(), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        self.hint.setPixmap(shown)

    def showEvent(self, event):
        self.retitle()
        self.follow_theme()
        super().showEvent(event)

    def hideEvent(self, event):
        self._lifecycle_timer.stop()
        super().hideEvent(event)




