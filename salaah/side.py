"""The second screen: a 7" touchscreen stood upright (600 x 1024) beside the main display.

It gives the main screen's whole width to the words. It shows:

    between prayers   the Qibla compass, from start-up, so the mat can be lined up at any time
                      (while the compass is switched off: the standing figure and the volume bar)
    during a prayer   the posture figure, as large as the screen allows, with the X2 / X3
                      circle in its top right corner (the volume is in the main screen's bar)

With no second screen, none of this is used and the main screen works as it always has, with the
picture on its left.

The 7" is turned upright by the operating system (see the README), so the app simply sees a tall
screen. Its touch has to be tied to that screen too, or a touch on the 7" lands on the 16".
"""
from __future__ import annotations

from .knowledge import KnowledgeScreen
from .qt import QtGui, QtWidgets, Qt
from .render import Fonts, PostureView
from .theme import palette


class SideWindow(QtWidgets.QWidget):
    """The 7" screen's own window. The main window owns it and says what to show."""

    IDLE_PICTURE = "postures/standing_arms_down.png"

    def __init__(self, window, compass_screen=None):
        super().__init__()
        self.win = window
        self.setWindowTitle("Salaah (posture)")
        self.setObjectName("sideRoot")
        self.setAutoFillBackground(True)
        px = window.px

        self.stack = QtWidgets.QStackedWidget(self)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)

        # The compass. It keeps watching after it is lined up, as the mat can be moved.
        # What the 7" offers between prayers now that the compass has gone: three things to
        # read, chosen here and opened on the big screen.
        self.corner = KnowledgeScreen(window)
        self.corner.chose.connect(window.chose_on_the_small_screen)
        self.stack.addWidget(self.corner)

        self.compass = compass_screen
        if self.compass is not None:
            self.compass.stays = True
            self.stack.addWidget(self.compass)

        # The posture picture, filling the screen.
        self.prayer = QtWidgets.QWidget()
        self.prayer.setObjectName("sidePrayer")
        column = QtWidgets.QVBoxLayout(self.prayer)
        column.setContentsMargins(px(10), px(10), px(10), px(10))
        column.setSpacing(0)
        self.posture = PostureView(window.images, Fonts.english_family)
        self.posture.scale = window.s
        self.posture.modes = window.posture_modes
        self.posture.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                   QtWidgets.QSizePolicy.Policy.Expanding)
        column.addWidget(self.posture, 1)
        self.stack.addWidget(self.prayer)

        self.dim = QtWidgets.QWidget(self)
        self.dim.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.dim.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.dim.hide()
        self.follow_theme()

    # What to show

    def show_idle(self) -> None:
        """Between prayers: the Knowledge Corner, or the compass where one is switched on."""
        self.set_dim(0)
        self.idle = True
        if self.compass is not None and self.win.settings.qibla_start:
            self.stack.setCurrentWidget(self.compass)
            self.compass.open()
            return
        self.stack.setCurrentWidget(self.corner)

    show_compass = show_idle

    def show_prayer(self) -> None:
        self.idle = False
        if self.compass is not None:
            self.compass.close_screen()
        self.stack.setCurrentWidget(self.prayer)

    def show_game(self, companion):
        """Lend the 7" to a game, which brings its own widget for it.

        REPLACES show_jigsaw, which took a PICTURE and built the panel here. That was fine for
        one game and wrong for three: each of the three dual-touch games added in 1.97 puts
        something different on the 7in -- a hint picture and a piece count, a question with
        answer buttons, a maze's item tally and its Difficulty and New Game controls -- and a
        method here that knew how to build each of them would be this file growing a copy of
        every game.

        So the game owns its companion and this only mounts it. The widget is added to the
        stack once and kept: a game is built on first open now (see ui.open_a_game) and a child
        goes in and out of the same game repeatedly, so adding and removing it each time would
        churn the stack for no gain. Games hand the screen back by calling show_idle.
        """
        if self.stack.indexOf(companion) < 0:
            self.stack.addWidget(companion)
            if hasattr(companion, "follow_theme"):
                companion.follow_theme()
        self.idle = False
        self.set_dim(0)
        self.stack.setCurrentWidget(companion)
        return companion

    @property
    def showing_game(self) -> bool:
        """Whether a game's own panel is on the 7in rather than the corner or the posture."""
        now = self.stack.currentWidget()
        return now is not None and now not in (self.corner, self.prayer, self.compass)

    def close_screens(self) -> None:
        if self.compass is not None:
            self.compass.close_screen()

    @property
    def showing_idle(self) -> bool:
        """Whether the 7" is showing what it shows between prayers -- whichever that is.

        Asked rather than worked out from the page on top, because between prayers and during
        one the same page can be in front: with the compass switched off, both are the posture
        view, showing a standing figure in one case and the posture being prayed in the other.
        """
        return getattr(self, "idle", True)

    @property
    def showing_corner(self) -> bool:
        return self.stack.currentWidget() is self.corner

    @property
    def showing_compass(self) -> bool:
        return self.compass is not None and self.stack.currentWidget() is self.compass

    def set_dim(self, percent: int) -> None:
        if percent <= 0:
            self.dim.hide()
            return
        self.dim.setStyleSheet(f"background: rgba(0,0,0,{int(255 * percent / 100)});")
        self.dim.setGeometry(self.rect())
        self.dim.show()
        self.dim.raise_()

    def follow_theme(self) -> None:
        self.corner.follow_theme()
        pal = self.palette()
        pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(palette().paper))
        self.setPalette(pal)
        self.setStyleSheet(self.win.stylesheet())
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.update()

    def resizeEvent(self, _):
        self.dim.setGeometry(self.rect())
        # AND MEASURE THE PANEL AGAIN. fill_screen shows this window at 640x480 and then asks
        # the desktop to make it full screen; on Wayland the compositor grants that when it is
        # ready, and main.py asked how tall the panel was on the next line. Asking once, at
        # that moment, is asking before there is an answer -- which is how 2.00 came to lay the
        # 7in out at half size. Measuring here means the last word always comes from a
        # configure event that really happened, and it costs nothing: the games are built when
        # a child first opens one, long after start-up.
        self.win.measure_the_side_screen()
