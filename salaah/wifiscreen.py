"""The Wi-Fi screen: pick a network, type the password, and never leave the app.

Reached from a row in Settings. It is deliberately NOT a box that jumps in front of whatever is
on the mat: this screen sits in a room and shows prayer times, and a dialog that seizes it --
possibly mid-prayer, possibly during the call -- would be worse than no wifi at all. So it is a
screen you go to, and the only thing that ever offers it unprompted is the line where something
actually failed for want of a network.

Three things it is careful about, all of them learned from the real mat:

  * it does not say "connected" until a name resolves. The mat spent an evening associated to
    the wifi and unable to reach anything, and a screen that trusted the radio would have said
    everything was fine.
  * a failed attempt puts back the network that was in use. Getting a password wrong in the
    kitchen must not cost somebody the connection they already had.
  * it says WHICH thing went wrong. Wrong password, out of range and a router that never answers
    need three different things doing about them.

The scan and the join both talk to nmcli, which can take a while, so they run on a worker thread
and the screen says what it is doing. Everything the thread touches is handed back through a
signal rather than poked at from underneath.
"""
from __future__ import annotations

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .keys import Keyboard
from .network import Wifi


class Errand(QtCore.QThread):
    """One slow nmcli call, off the screen's thread."""

    done = Signal(object)

    def __init__(self, work):
        super().__init__()
        self.work = work

    def run(self):
        try:
            self.done.emit(self.work())
        except Exception as why:            # a worker must never take the mat down with it
            self.done.emit(why)


class Bars(QtWidgets.QWidget):
    """Signal strength, nought to four."""

    def __init__(self, window, bars: int):
        super().__init__()
        self.win = window
        self.bars = bars
        self.setFixedSize(window.px(44), window.px(36))

    def paintEvent(self, _):
        from .theme import palette
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        ink = QtGui.QColor(palette().ink)
        faint = QtGui.QColor(palette().ink)
        faint.setAlpha(60)
        wide = self.width() / 5.0
        for i in range(4):
            tall = self.height() * (0.3 + 0.22 * i)
            p.setBrush(ink if i < self.bars else faint)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QtCore.QRectF(i * wide * 1.2 + wide * 0.1,
                                     self.height() - tall, wide * 0.8, tall))


class NetworkRow(QtWidgets.QPushButton):
    """One network to tap."""

    def __init__(self, window, network):
        super().__init__()
        self.win = window
        self.network = network
        self.setObjectName("surahRow")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(96))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(window.px(20), window.px(8), window.px(20), window.px(8))
        lay.setSpacing(window.px(16))
        lay.addWidget(Bars(window, network.bars))
        name = QtWidgets.QLabel(network.name)
        name.setObjectName("wifiName")
        lay.addWidget(name)
        lay.addStretch(1)
        if network.known:
            saved = QtWidgets.QLabel(window.t("wifi.known"))
            saved.setObjectName("sub")
            lay.addWidget(saved)
        if network.secured:
            lock = QtWidgets.QLabel("\U0001f512")
            lock.setObjectName("wifiLock")
            lay.addWidget(lock)


class WifiScreen(QtWidgets.QWidget):
    """The whole thing: a list of networks, and a password screen behind it."""

    def __init__(self, window, wifi: Wifi | None = None):
        super().__init__()
        self.win = window
        self.wifi = wifi or Wifi()
        self.errand: Errand | None = None
        self.picked = None
        self.typed = ""
        self.setObjectName("wifiScreen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.pages = QtWidgets.QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.pages.addWidget(self.build_list())
        self.pages.addWidget(self.build_password())

    # -- the list ---------------------------------------------------------------------------

    def build_list(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(self.win.px(20), self.win.px(14), self.win.px(20), self.win.px(14))
        lay.setSpacing(self.win.px(10))

        top = QtWidgets.QHBoxLayout()
        self.heading = QtWidgets.QLabel(self.win.t("wifi.title"))
        self.heading.setObjectName("h1")
        top.addWidget(self.heading)
        top.addStretch(1)
        self.where = QtWidgets.QLabel("")
        self.where.setObjectName("sub")
        top.addWidget(self.where)
        lay.addLayout(top)

        self.saying = QtWidgets.QLabel("")
        self.saying.setObjectName("settingHead")
        self.saying.setWordWrap(True)
        lay.addWidget(self.saying)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("listScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        self.rows = QtWidgets.QVBoxLayout(inner)
        self.rows.setSpacing(self.win.px(10))
        self.scroll.setWidget(inner)
        lay.addWidget(self.scroll, 1)

        feet = QtWidgets.QHBoxLayout()
        self.again = QtWidgets.QPushButton(self.win.t("wifi.again"))
        self.again.setObjectName("pill")
        self.again.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.again.clicked.connect(self.look)
        feet.addWidget(self.again)
        feet.addStretch(1)
        self.leave = QtWidgets.QPushButton(self.win.t("corner.back"))
        self.leave.setObjectName("backButton")
        self.leave.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        feet.addWidget(self.leave)
        lay.addLayout(feet)
        return page

    def look(self) -> None:
        """Scan, on a worker so the mat does not freeze while nmcli thinks."""
        if self.busy():
            return
        self.saying.setText(self.win.t("wifi.scanning"))
        self.again.setEnabled(False)
        self.start(self.wifi.scan, self.found)

    def found(self, networks) -> None:
        self.again.setEnabled(True)
        if isinstance(networks, Exception):
            self.saying.setText(self.win.t("why.unknown"))
            networks = []
        self.clear_rows()
        for network in networks:
            row = NetworkRow(self.win, network)
            row.clicked.connect(lambda _=False, n=network: self.chose(n))
            self.rows.addWidget(row)
        self.rows.addStretch(1)
        self.saying.setText("" if networks else self.win.t("wifi.none"))
        self.show_where()

    def clear_rows(self) -> None:
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()

    def show_where(self) -> None:
        on = self.wifi.active()
        self.where.setText(self.win.t("wifi.joined", name=on) if on
                           else self.win.t("wifi.offline"))

    def network_rows(self) -> list[NetworkRow]:
        return [self.rows.itemAt(i).widget() for i in range(self.rows.count())
                if isinstance(self.rows.itemAt(i).widget(), NetworkRow)]

    # -- the password -----------------------------------------------------------------------

    def build_password(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(self.win.px(20), self.win.px(14), self.win.px(20), self.win.px(10))
        lay.setSpacing(self.win.px(8))

        self.asking = QtWidgets.QLabel("")
        self.asking.setObjectName("h2")
        lay.addWidget(self.asking)

        self.field = QtWidgets.QLabel("")
        self.field.setObjectName("wifiField")
        self.field.setMinimumHeight(self.win.px(70))
        lay.addWidget(self.field)

        row = QtWidgets.QHBoxLayout()
        # Show the password. On a touchscreen there is no feel to tell you a key missed, and a
        # wifi password is long and case-sensitive -- without this people retype blind.
        self.reveal = QtWidgets.QCheckBox(self.win.t("wifi.show"))
        self.reveal.setObjectName("choice")
        self.reveal.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reveal.toggled.connect(self.redraw_field)
        row.addWidget(self.reveal)
        row.addStretch(1)
        self.trouble = QtWidgets.QLabel("")
        self.trouble.setObjectName("wifiTrouble")
        self.trouble.setWordWrap(True)
        row.addWidget(self.trouble, 1)
        lay.addLayout(row)

        self.keys = Keyboard(self.win)
        self.keys.typed.connect(self.add)
        self.keys.rubbed_out.connect(self.rub)
        self.keys.finished.connect(self.go)
        lay.addWidget(self.keys, 1)

        feet = QtWidgets.QHBoxLayout()
        self.give_up = QtWidgets.QPushButton(self.win.t("wifi.cancel"))
        self.give_up.setObjectName("pill")
        self.give_up.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.give_up.clicked.connect(self.back_to_list)
        feet.addWidget(self.give_up)
        feet.addStretch(1)
        self.join = QtWidgets.QPushButton(self.win.t("wifi.join"))
        self.join.setObjectName("primary")
        self.join.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.join.clicked.connect(self.go)
        feet.addWidget(self.join)
        lay.addLayout(feet)
        return page

    def chose(self, network) -> None:
        self.picked = network
        self.typed = ""
        self.trouble.setText("")
        self.reveal.setChecked(False)
        if not network.secured or network.known:
            self.go()                       # nothing to type
            return
        self.asking.setText(self.win.t("wifi.password", name=network.name))
        self.redraw_field()
        self.pages.setCurrentIndex(1)

    def add(self, character: str) -> None:
        self.typed += character
        self.redraw_field()

    def rub(self) -> None:
        self.typed = self.typed[:-1]
        self.redraw_field()

    def redraw_field(self) -> None:
        self.field.setText(self.typed if self.reveal.isChecked() else "•" * len(self.typed))

    def go(self) -> None:
        if self.picked is None or self.busy():
            return
        name, password = self.picked.name, self.typed
        self.saying.setText(self.win.t("wifi.joining", name=name))
        self.trouble.setText(self.win.t("wifi.joining", name=name))
        self.join.setEnabled(False)
        self.start(lambda: self.wifi.join(name, password), self.joined)

    def joined(self, answer) -> None:
        self.join.setEnabled(True)
        if isinstance(answer, Exception):
            ok, why = False, "unknown"
        else:
            ok, why = answer
        if ok:
            self.typed = ""               # the password is not kept a moment longer than needed
            self.redraw_field()
            self.trouble.setText("")
            self.back_to_list()
            self.saying.setText(self.win.t("wifi.joined", name=self.picked.name))
            self.show_where()
            return
        self.trouble.setText(self.win.t(f"why.{why}"))
        self.saying.setText(self.win.t(f"why.{why}"))
        if self.pages.currentIndex() == 0 and self.picked.secured and not self.picked.known:
            self.asking.setText(self.win.t("wifi.password", name=self.picked.name))
            self.pages.setCurrentIndex(1)

    def back_to_list(self) -> None:
        self.typed = ""
        self.redraw_field()
        self.pages.setCurrentIndex(0)

    # -- threads ----------------------------------------------------------------------------

    def busy(self) -> bool:
        return self.errand is not None and self.errand.isRunning()

    def start(self, work, then) -> None:
        """Run one nmcli call on a worker.

        The reference is dropped when the thread finishes, BEFORE the object is deleted. Letting
        the thread deleteLater itself while self.errand still pointed at it left a dangling
        handle, and the next press of Search again died on "Internal C++ object already deleted"
        -- which on the mat is the whole app going down.
        """
        errand = Errand(work)
        errand.done.connect(then)
        errand.finished.connect(self.errand_finished)
        self.errand = errand
        errand.start()

    def errand_finished(self) -> None:
        done, self.errand = self.errand, None
        if done is not None:
            done.deleteLater()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.show_where()
        if not self.network_rows():
            self.look()

    def shutdown(self) -> None:
        if self.busy():
            self.errand.wait(2000)

    def retitle(self) -> None:
        self.heading.setText(self.win.t("wifi.title"))
        self.again.setText(self.win.t("wifi.again"))
        self.leave.setText(self.win.t("corner.back"))
        self.give_up.setText(self.win.t("wifi.cancel"))
        self.join.setText(self.win.t("wifi.join"))
        self.reveal.setText(self.win.t("wifi.show"))
        self.show_where()
