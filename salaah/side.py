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
        """Between prayers: the compass, or with it switched off the standing figure."""
        self.set_dim(0)
        if self.compass is None or not self.win.settings.qibla_start:
            self.posture.set_repeat(1)
            self.posture.set_image(self.win.picture(self.IDLE_PICTURE))
            self.stack.setCurrentWidget(self.prayer)
            return
        self.stack.setCurrentWidget(self.compass)
        self.compass.open()

    show_compass = show_idle

    def show_prayer(self) -> None:
        if self.compass is not None:
            self.compass.close_screen()
        self.stack.setCurrentWidget(self.prayer)

    def close_screens(self) -> None:
        if self.compass is not None:
            self.compass.close_screen()

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
        pal = self.palette()
        pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(palette().paper))
        self.setPalette(pal)
        self.setStyleSheet(self.win.stylesheet())
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.update()

    def resizeEvent(self, _):
        self.dim.setGeometry(self.rect())
