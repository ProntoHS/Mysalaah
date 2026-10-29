"""Prayer Day Journey: a dual-touch, five-prayer learning game.

The 16-inch display presents the approved prayer-time scenes. The 7-inch
companion carries translated questions, feedback and controls. A second mode
lets children put the scenes in chronological order on the main touchscreen.
All progress is held in memory and artwork is loaded through ``window.assets``.
"""
from __future__ import annotations

import random

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts
from .theme import palette


SCENES = ("fajr", "dhuhr", "asr", "maghrib", "isha")
ASSETS = {
    "fajr": "prayer-day-fajr.png",
    "dhuhr": "prayer-day-zuhr.png",
    "asr": "prayer-day-asr.png",
    "maghrib": "prayer-day-maghrib.png",
    "isha": "prayer-day-isha.png",
}


class Rules:
    """Pure game state: no Qt, files, clocks or input devices."""

    NAME, ORDER = 0, 1
    LEVEL_COUNTS = (3, 4, 5)
    ORDER_LEVELS = (
        ("fajr", "dhuhr", "isha"),
        ("fajr", "dhuhr", "maghrib", "isha"),
        SCENES,
    )

    def __init__(self, shuffle=None):
        self._shuffle = shuffle if shuffle is not None else random.shuffle
        self.mode = self.NAME
        self.difficulty = 0
        self.restart()

    def restart(self) -> None:
        self.done = False
        self.active = 0
        self.selected = None
        self.moves = 0
        self.score = 0
        self.at = 0
        self.locked = False
        self.chosen = None
        if self.mode == self.NAME:
            self.sequence = list(SCENES)
            self._shuffle(self.sequence)
            self._deal()
        else:
            self.target = list(self.ORDER_LEVELS[self.difficulty])
            self.order = list(self.target)
            self._shuffle(self.order)
            if self.order == self.target and len(self.order) > 1:
                self.order = self.order[1:] + self.order[:1]

    @property
    def rounds(self) -> int:
        return len(SCENES)

    @property
    def answer_key(self) -> str:
        return self.sequence[self.at]

    @property
    def right(self):
        if self.chosen is None:
            return None
        return self.choices[self.chosen] == self.answer_key

    @property
    def correct_places(self) -> int:
        if self.mode != self.ORDER:
            return 0
        return sum(left == right for left, right in zip(self.order, self.target))

    def _deal(self) -> None:
        answer = self.answer_key
        distractors = [key for key in SCENES if key != answer]
        self._shuffle(distractors)
        picks = [answer, *distractors[:self.LEVEL_COUNTS[self.difficulty] - 1]]
        self._shuffle(picks)
        self.choices = tuple(picks)
        self.active = 0
        self.locked = False
        self.chosen = None

    def cycle_mode(self) -> None:
        self.mode = self.ORDER if self.mode == self.NAME else self.NAME
        self.restart()

    def cycle_difficulty(self) -> None:
        self.difficulty = (self.difficulty + 1) % len(self.LEVEL_COUNTS)
        self.restart()

    def step(self) -> None:
        if self.done or self.locked:
            return
        count = len(self.choices) if self.mode == self.NAME else len(self.order)
        self.active = (self.active + 1) % count

    def answer(self, which: int) -> str:
        if (self.mode != self.NAME or self.done or self.locked
                or not 0 <= which < len(self.choices)):
            return "nothing"
        self.active = which
        self.chosen = which
        self.locked = True
        if self.right:
            self.score += 1
        return "answered"

    def next_round(self) -> str:
        if self.mode != self.NAME or not self.locked:
            return "nothing"
        if self.at + 1 >= len(self.sequence):
            self.done = True
            return "complete"
        self.at += 1
        self._deal()
        return "next"

    def tap_order(self, which: int) -> str:
        if self.mode != self.ORDER or self.done or not 0 <= which < len(self.order):
            return "nothing"
        self.active = which
        if self.selected is None:
            self.selected = which
            return "selected"
        if self.selected == which:
            self.selected = None
            return "nothing"
        first = self.selected
        self.order[first], self.order[which] = self.order[which], self.order[first]
        self.selected = None
        self.moves += 1
        if self.order == self.target:
            self.done = True
            return "complete"
        return "moved"

    def press(self, which=None) -> str:
        if self.done:
            self.restart()
            return "again"
        if self.mode == self.NAME:
            if self.locked:
                return self.next_round()
            return self.answer(self.active if which is None else which)
        return self.tap_order(self.active if which is None else which)


class SceneCanvas(QtWidgets.QFrame):
    """The artwork-only main display and touch target for ordering mode."""

    chosen = Signal(int)

    def __init__(self, window, game, images):
        super().__init__()
        self.win = window
        self.game = game
        self.images = images
        self._slots = []
        self._ignore_mouse_release = False
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _picture(self, key):
        """The scene, as drawn, whatever the theme.

        IT USED TO BE TURNED OVER AFTER DARK, and here that did not just look wrong -- it
        answered the question.

        This game asks "which prayer is this?" and a child answers from the light in the sky.
        Inverting the scene inverts exactly that: Zuhr's midday sun became a black disc in a
        dark sky, and Isha's night sky with its crescent became bright white daylight. On a
        dark-themed mat the two read as each other, so the picture argued for the wrong
        answer and the child was marked wrong for believing it.

        The mat's invert-for-dark convention is for line art, where the inverse is the same
        drawing at night. A picture whose SUBJECT is the time of day has no inverse. See
        journey_jigsaw.Screen._image, which had the same fault for a different reason.
        """
        return self.images[key]

    @staticmethod
    def _source_crop(pixmap, target):
        source_ratio = pixmap.width() / max(1, pixmap.height())
        target_ratio = target.width() / max(1.0, target.height())
        if source_ratio > target_ratio:
            wanted = pixmap.height() * target_ratio
            left = (pixmap.width() - wanted) / 2
            return QtCore.QRectF(left, 0, wanted, pixmap.height())
        wanted = pixmap.width() / target_ratio
        top = (pixmap.height() - wanted) / 2
        return QtCore.QRectF(0, top, pixmap.width(), wanted)

    def _grid(self):
        count = len(self.game.order)
        columns = 3 if count in (3, 5) else 2
        rows = (count + columns - 1) // columns
        gap = self.win.px(22)
        margin = self.win.px(36)
        usable_w = self.width() - margin * 2 - gap * (columns - 1)
        usable_h = self.height() - margin * 2 - gap * (rows - 1)
        cell_w = usable_w / columns
        cell_h = usable_h / rows
        ratio = 16 / 9
        card_w = min(cell_w, cell_h * ratio)
        card_h = card_w / ratio
        if card_h > cell_h:
            card_h = cell_h
            card_w = card_h * ratio
        slots = []
        for index in range(count):
            row, column = divmod(index, columns)
            cells_here = min(columns, count - row * columns)
            row_width = cells_here * card_w + (cells_here - 1) * gap
            start_x = (self.width() - row_width) / 2
            row_top = margin + row * (usable_h / rows + gap)
            top = row_top + (usable_h / rows - card_h) / 2
            left = start_x + column * (card_w + gap)
            slots.append(QtCore.QRectF(left, top, card_w, card_h))
        return slots

    def paintEvent(self, _):
        c = palette()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QtGui.QColor(c.paper))
        if self.game.mode == self.game.NAME:
            pixmap = self._picture(self.game.answer_key)
            if not pixmap.isNull():
                source = self._source_crop(pixmap, QtCore.QRectF(self.rect()))
                painter.drawPixmap(QtCore.QRectF(self.rect()), pixmap, source)
            return

        self._slots = self._grid()
        for index, (key, slot) in enumerate(zip(self.game.order, self._slots)):
            pixmap = self._picture(key)
            source = self._source_crop(pixmap, slot)
            painter.drawPixmap(slot, pixmap, source)
            edge = c.green if self.game.done else c.line
            thick = self.win.px(8) if self.game.selected == index else self.win.px(4)
            if self.game.selected == index or self.game.active == index:
                edge = c.lapis
            painter.setPen(QtGui.QPen(QtGui.QColor(edge), thick))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(slot, self.win.px(10), self.win.px(10))
            badge = QtCore.QRectF(slot.left() + self.win.px(12),
                                  slot.top() + self.win.px(12),
                                  self.win.px(54), self.win.px(54))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(c.panel))
            painter.drawEllipse(badge)
            words = str(index + 1)
            font = QtGui.QFont(Fonts.for_text(words))
            font.setPixelSize(self.win.px(28))
            font.setWeight(QtGui.QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(c.paper))
            painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), words)

    def _slot_at(self, point):
        for index, rect in enumerate(self._slots):
            if rect.contains(point):
                return index
        return None

    def mouseReleaseEvent(self, event):
        if self._ignore_mouse_release:
            self._ignore_mouse_release = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.game.mode == self.game.ORDER:
            which = self._slot_at(event.position())
            if which is not None:
                self.chosen.emit(which)
            self._ignore_mouse_release = True
            event.accept()

    @staticmethod
    def _touch_position(event):
        points = event.points() if hasattr(event, "points") else event.touchPoints()
        if not points:
            return None
        point = points[0]
        return point.position() if hasattr(point, "position") else point.pos()

    def event(self, event):
        if event.type() == QtCore.QEvent.Type.TouchEnd and self.game.mode == self.game.ORDER:
            point = self._touch_position(event)
            which = self._slot_at(point) if point is not None else None
            if which is not None:
                self.chosen.emit(which)
            event.accept()
            return True
        return super().event(event)


class Screen(QtWidgets.QWidget):
    """Host screen with an attached widget for the 7-inch companion display."""

    CYCLE = 1350
    leave = Signal()
    changed = Signal()

    def __init__(self, window, shuffle=None):
        super().__init__()
        self.win = window
        self.game = Rules(shuffle)
        self.setObjectName("prayerDayJourneyMain")
        base = window.assets / "children"
        # FIVE PIXMAPS, not ten. This arrived turning every scene over at construction for a
        # dark set it kept beside the light one -- 37 MB of pixmaps rather than 18 -- which
        # was first made lazy and then taken out altogether, because these scenes must not be
        # inverted at all. SceneCanvas._picture says why.
        self.images = {key: QtGui.QPixmap(str(base / ASSETS[key])) for key in SCENES}

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = SceneCanvas(window, self.game, self.images)
        self.canvas.chosen.connect(self._order_choice)
        main_layout.addWidget(self.canvas)

        self._scan = QtCore.QTimer(self)
        self._scan.setInterval(self.CYCLE)
        self._scan.timeout.connect(self._scan_step)
        self.companion = self._build_companion()
        self.changed.connect(self.canvas.update)
        self.changed.connect(self.retell)
        self.follow_theme()
        self.start_again()

    def _build_companion(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("prayerDayCompanion")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(self.win.side_px(20), self.win.side_px(18),
                                  self.win.side_px(20), self.win.side_px(18))
        layout.setSpacing(self.win.side_px(10))

        self.title = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.progress = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress)
        self.question = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question.setWordWrap(True)
        layout.addWidget(self.question)

        self.answers = []
        self.answer_box = QtWidgets.QWidget()
        answer_layout = QtWidgets.QVBoxLayout(self.answer_box)
        answer_layout.setContentsMargins(0, 0, 0, 0)
        answer_layout.setSpacing(self.win.side_px(8))
        for index in range(len(SCENES)):
            button = QtWidgets.QPushButton()
            button.setObjectName("answerButton")
            button.setMinimumHeight(self.win.side_px(54))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, which=index: self._choose(which))
            answer_layout.addWidget(button)
            self.answers.append(button)
        layout.addWidget(self.answer_box, 1)

        self.feedback = QtWidgets.QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)

        self.next_button = QtWidgets.QPushButton()
        self.next_button.setObjectName("controlButton")
        self.next_button.setMinimumHeight(self.win.side_px(58))
        self.next_button.clicked.connect(self._next)
        layout.addWidget(self.next_button)

        selectors = QtWidgets.QHBoxLayout()
        selectors.setSpacing(self.win.side_px(10))
        self.mode_button = QtWidgets.QPushButton()
        self.mode_button.setObjectName("controlButton")
        self.mode_button.setMinimumHeight(self.win.side_px(58))
        self.mode_button.clicked.connect(self.cycle_mode)
        selectors.addWidget(self.mode_button, 1)
        self.difficulty_button = QtWidgets.QPushButton()
        self.difficulty_button.setObjectName("controlButton")
        self.difficulty_button.setMinimumHeight(self.win.side_px(58))
        self.difficulty_button.clicked.connect(self.cycle_difficulty)
        selectors.addWidget(self.difficulty_button, 1)
        layout.addLayout(selectors)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(self.win.side_px(10))
        self.new_button = QtWidgets.QPushButton()
        self.new_button.setObjectName("controlButton")
        self.new_button.setMinimumHeight(self.win.side_px(62))
        self.new_button.clicked.connect(self.start_again)
        controls.addWidget(self.new_button, 1)
        self.exit_button = QtWidgets.QPushButton()
        self.exit_button.setObjectName("controlButton")
        self.exit_button.setMinimumHeight(self.win.side_px(62))
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

    def _prayer(self, key):
        return self.win.t("prayer." + key)

    def _level(self):
        keys = ("prayer_day.beginner", "prayer_day.medium", "prayer_day.expert")
        return self.win.t(keys[self.game.difficulty])

    def retell(self) -> None:
        title = self.win.t("prayer_day.title")
        mode = (self.win.t("prayer_day.mode_name") if self.game.mode == self.game.NAME
                else self.win.t("prayer_day.mode_order"))
        mode_text = self.win.t("prayer_day.mode", mode=mode)
        difficulty = self.win.t("prayer_day.difficulty", level=self._level())
        new_game = self.win.t("prayer_day.new_game")
        exit_game = self.win.t("prayer_day.exit")
        next_text = self.win.t("prayer_day.next")

        self.title.setText(title)
        self.mode_button.setText(mode_text)
        self.difficulty_button.setText(difficulty)
        self.new_button.setText(new_game)
        self.exit_button.setText(exit_game)
        self.next_button.setText(next_text)

        if self.game.mode == self.game.NAME:
            progress = self.win.t("prayer_day.round", at=str(self.game.at + 1),
                                  of=str(self.game.rounds))
            self.progress.setText(progress)
            self.answer_box.show()
            if self.game.done:
                self.question.setText(self.win.t("prayer_day.complete_name"))
                self.feedback.setText(self.win.t("prayer_day.final_score",
                                                 score=str(self.game.score),
                                                 of=str(self.game.rounds)))
                self.answer_box.hide()
                self.next_button.hide()
            else:
                self.question.setText(self.win.t("prayer_day.question"))
                self.next_button.setVisible(self.game.locked)
                for index, button in enumerate(self.answers):
                    visible = index < len(self.game.choices)
                    button.setVisible(visible)
                    if not visible:
                        continue
                    key = self.game.choices[index]
                    button.setText(self._prayer(key))
                    state = "idle"
                    if self.game.locked:
                        if key == self.game.answer_key:
                            state = "right"
                        elif index == self.game.chosen:
                            state = "chosen"
                    elif index == self.game.active:
                        state = "active"
                    button.setProperty("answerState", state)
                    button.style().unpolish(button)
                    button.style().polish(button)
                if self.game.locked:
                    clue = self.win.t("prayer_day.clue." + self.game.answer_key)
                    if self.game.right:
                        feedback = self.win.t("prayer_day.correct", clue=clue)
                    else:
                        feedback = self.win.t("prayer_day.answer",
                                              prayer=self._prayer(self.game.answer_key),
                                              clue=clue)
                    self.feedback.setText(feedback)
                elif self.game.difficulty == 0:
                    self.feedback.setText(self.win.t("prayer_day.beginner_hint"))
                else:
                    self.feedback.clear()
        else:
            progress = self.win.t("prayer_day.places",
                                  at=str(self.game.correct_places),
                                  of=str(len(self.game.target)))
            self.progress.setText(progress)
            self.answer_box.hide()
            self.next_button.hide()
            self.question.setText(self.win.t("prayer_day.order_question"))
            if self.game.done:
                self.feedback.setText(self.win.t("prayer_day.complete_order"))
            elif self.game.selected is None:
                self.feedback.setText(self.win.t("prayer_day.order_first"))
            else:
                self.feedback.setText(self.win.t("prayer_day.order_second"))

        self.title.setFont(self._font(title, 32, True))
        self.progress.setFont(self._font(self.progress.text(), 21, True))
        self.question.setFont(self._font(self.question.text(), 25, True))
        self.feedback.setFont(self._font(self.feedback.text(), 19, True))
        for button in [*self.answers, self.next_button, self.mode_button,
                       self.difficulty_button, self.new_button, self.exit_button]:
            button.setFont(self._font(button.text(), 20, True))

    def follow_theme(self) -> None:
        c = palette()
        radius = self.win.side_px(11)
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
        active = self.win.side_px(6)
        self.companion.setStyleSheet(
            # THE PANEL IS PAPER, not ink. This arrived inverted against the rest of the mat --
            # a white panel at night and a black one by day -- so the 7in beside the Islamic
            # Jigsaw and the maze was the opposite colour to both of them and to every other
            # screen. Nothing needed it; it was simply the odd one out.
            f"QWidget#prayerDayCompanion {{ background: {c.paper}; color: {c.ink}; }}"
            f"QLabel {{ color: {c.ink}; background: {c.paper}; }}"
            f"QPushButton {{ border-radius: {radius}px; }}"
            # THE EDGE IS INK. It was paper -- the same colour as the button's own fill and as
            # the box the five of them sit in -- so an answer had no visible edge at all and
            # the five choices read as bare words floating on the panel. Only the one the ring
            # was resting on could be seen, because its lapis border came from the rule below.
            # The three state borders still override this one, which is the whole point of
            # having an ordinary edge to begin with: before, "active" was the only state that
            # looked like anything.
            f"QPushButton#answerButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; }}"
            f"QPushButton#answerButton[answerState='active'] {{ border: {active}px solid {c.lapis}; }}"
            f"QPushButton#answerButton[answerState='right'] {{ border: {active}px solid {c.green}; "
            f"color: {c.green}; }}"
            f"QPushButton#answerButton[answerState='chosen'] {{ border: {active}px solid {c.highlight}; "
            f"color: {c.highlight}; }}"
            f"QPushButton#controlButton {{ background: {c.paper}; color: {c.ink}; "
            f"border: {edge}px solid {c.ink}; }}"
            f"QPushButton:pressed {{ background: {c.pressed}; }}"
            f"QLabel#gameTitle {{ font-size: {title}px; font-weight: bold; }}"
            f"QLabel#gameStatus {{ font-size: {body}px; }}"
            f"QPushButton {{ font-size: {label}px; font-weight: bold; }}"
        )
        self.retell()
        self.canvas.update()

    @property
    def ready(self) -> bool:
        return all(not p.isNull() for p in self.images.values())

    @staticmethod
    def playable(assets) -> bool:
        """Asked of the disk before anything is built. See journey_jigsaw.Screen.playable."""
        base = assets / "children"
        return all((base / ASSETS[key]).is_file() for key in SCENES)

    def start_again(self) -> None:
        self._scan.stop()
        self.game.restart()
        self._scan.start()
        self.changed.emit()

    def cycle_mode(self) -> None:
        self._scan.stop()
        self.game.cycle_mode()
        self._scan.start()
        self.changed.emit()

    def cycle_difficulty(self) -> None:
        self._scan.stop()
        self.game.cycle_difficulty()
        self._scan.start()
        self.changed.emit()

    def _choose(self, which) -> None:
        if self.game.answer(which) == "answered":
            self._scan.stop()
            self.changed.emit()

    def _next(self) -> None:
        result = self.game.next_round()
        if result != "nothing":
            if not self.game.done:
                self._scan.start()
            self.changed.emit()

    def _order_choice(self, which) -> None:
        result = self.game.tap_order(which)
        if result != "nothing":
            if self.game.done:
                self._scan.stop()
            self.changed.emit()

    def _scan_step(self) -> None:
        self.game.step()
        self.changed.emit()

    def press(self, action="") -> None:
        from .buttons import BACK
        if action == BACK or str(action).lower() in ("back", "exit", "escape"):
            self._scan.stop()
            self.leave.emit()
            return
        result = self.game.press()
        if self.game.done or self.game.locked:
            self._scan.stop()
        else:
            self._scan.start()
        if result != "nothing":
            self.changed.emit()

    def showEvent(self, event):
        self.follow_theme()
        if not self.game.done and not self.game.locked:
            self._scan.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._scan.stop()
        super().hideEvent(event)
