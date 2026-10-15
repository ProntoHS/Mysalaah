"""The Bluetooth screen: find a speaker or a headset, connect it, and never leave the app.

Reached from a row in Settings, directly under Wi-Fi, and built to the same shape as the Wi-Fi
screen on purpose -- a list you look at, a row you tap, a line that says what is happening.
Somebody who has joined a network on this mat already knows how to use this.

It is NOT a box that jumps in front of whatever is on the mat. This screen sits in a room and
shows prayer times; a dialog that seized it mid-prayer would be worse than no speaker at all.

WHAT TAPPING A ROW DOES. Connect, or disconnect if it is already connected. Connecting pairs
first if it has to, and always trusts, so the speaker comes back by itself the next time the mat
is switched on at the wall -- see the note in bluetooth.py.

WHAT IT WILL NOT DO. It will not type a PIN, and it does not need to: a speaker or a headset
pairs with no number. A device that insists on one comes back as "would not pair" rather than
hanging, and can still be paired from the Pi's own Bluetooth menu.

WHY THE RING IS IN THE LIST BUT CANNOT TURN THE CIRCLE GREEN. The ring is on the same adapter
and the mat remembers it, so hiding it would be a lie about what is connected. But the circle in
Settings answers "is there a speaker", and it asks what each connected device IS rather than
counting them -- the ring reads as an input device and is passed over.
"""
from __future__ import annotations

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .bluetooth import Sound
from .wifiscreen import Bars, Errand


class DeviceRow(QtWidgets.QPushButton):
    """One device to tap."""

    def __init__(self, window, device):
        super().__init__()
        self.win = window
        self.device = device
        self.setObjectName("surahRow")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(window.px(96))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(window.px(20), window.px(8), window.px(20), window.px(8))
        lay.setSpacing(window.px(16))
        lay.addWidget(Bars(window, device.bars))
        name = QtWidgets.QLabel(device.shown)
        name.setObjectName("wifiName")
        lay.addWidget(name)
        lay.addStretch(1)
        # Right to left, so the most important word is nearest the edge the eye lands on: what
        # this device is doing now, then whether the mat remembers it, then what it is.
        if device.connected:
            here = QtWidgets.QLabel(window.t("bt.this_one"))
            here.setObjectName("sub")
            lay.addWidget(here)
        elif device.paired:
            saved = QtWidgets.QLabel(window.t("bt.saved"))
            saved.setObjectName("sub")
            lay.addWidget(saved)
        if device.audio:
            lay.addWidget(Speakerlet(window))


class Speakerlet(QtWidgets.QWidget):
    """A little speaker, drawn rather than lettered, marking the rows that make a noise.

    Drawn because this list is read at arm's length on a touchscreen and because a word here
    would need translating into seven languages to say something a shape says at a glance.
    """

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setFixedSize(window.px(34), window.px(34))

    def paintEvent(self, _):
        from .theme import palette
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        ink = QtGui.QColor(palette().ink)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        w, h = self.width(), self.height()
        # the box, then the cone: a speaker seen side-on
        box = QtCore.QRectF(w * 0.14, h * 0.34, w * 0.20, h * 0.32)
        p.drawRect(box)
        cone = QtGui.QPolygonF([QtCore.QPointF(w * 0.34, h * 0.36),
                                QtCore.QPointF(w * 0.58, h * 0.14),
                                QtCore.QPointF(w * 0.58, h * 0.86),
                                QtCore.QPointF(w * 0.34, h * 0.64)])
        p.drawPolygon(cone)
        # two waves coming off it
        pen = QtGui.QPen(ink, max(1.0, w * 0.06))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, reach in enumerate((0.20, 0.34)):
            box = QtCore.QRectF(w * (0.52 - reach / 2), h * (0.5 - reach),
                                w * reach, h * reach * 2)
            p.drawArc(box, -55 * 16, 110 * 16)


class BluetoothScreen(QtWidgets.QWidget):
    """A list of devices, and a line saying where the sound is going."""

    changed = Signal()      # something connected or disconnected; Settings repaints its circle

    def __init__(self, window, sound: Sound | None = None):
        super().__init__()
        self.win = window
        self.sound = sound or Sound()
        self.errand: Errand | None = None
        self.then_refresh = False
        self.setObjectName("btScreen")

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(self.win.px(20), self.win.px(14), self.win.px(20), self.win.px(14))
        lay.setSpacing(self.win.px(10))

        top = QtWidgets.QHBoxLayout()
        self.heading = QtWidgets.QLabel(self.win.t("bt.title"))
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
        self.again = QtWidgets.QPushButton(self.win.t("bt.again"))
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

    # -- looking ------------------------------------------------------------------------------

    def look(self) -> None:
        """Look round, on a worker so the mat does not freeze for the ten seconds it takes."""
        if self.busy():
            return
        self.saying.setText(self.win.t("bt.looking"))
        self.again.setEnabled(False)
        self.start(self.sound.look, self.found)

    def found(self, devices) -> None:
        self.again.setEnabled(True)
        if isinstance(devices, Exception):
            self.saying.setText(self.win.t("bt.why.unknown"))
            devices = []
        # Things with no name but their own address are left out. They are mostly fitness bands
        # and tyre sensors advertising to nobody, and a list of eleven rows of hexadecimal is a
        # list somebody gives up on before reaching the speaker underneath it.
        devices = [d for d in devices if not d.nameless]
        self.clear_rows()
        for device in devices:
            row = DeviceRow(self.win, device)
            row.clicked.connect(lambda _=False, d=device: self.tapped(d))
            self.rows.addWidget(row)
        self.rows.addStretch(1)
        self.saying.setText("" if devices else self.win.t("bt.none"))
        self.show_where()

    def clear_rows(self) -> None:
        while self.rows.count():
            old = self.rows.takeAt(0)
            if old.widget() is not None:
                old.widget().deleteLater()

    def device_rows(self) -> list[DeviceRow]:
        return [self.rows.itemAt(i).widget() for i in range(self.rows.count())
                if isinstance(self.rows.itemAt(i).widget(), DeviceRow)]

    def show_where(self) -> None:
        """The line in the corner: what is connected, and -- if it can be read -- where the
        sound is actually coming out.

        Two separate questions, and worth both. The mat was measured moving its own default
        output to a speaker the moment one connected, so these normally agree; on the day they
        do not, the second line is the one that explains the silence.
        """
        playing = self.sound.speaking()
        if playing is None:
            self.where.setText(self.win.t("bt.off"))
            return
        said = self.win.t("bt.connected", name=playing.shown)
        out = self.sound.sound_goes_to()
        if out and out != playing.shown:
            said += " · " + self.win.t("bt.sound_goes", name=out)
        self.where.setText(said)

    # -- connecting ---------------------------------------------------------------------------

    def tapped(self, device) -> None:
        """Connect it, or disconnect it if it is the one already connected."""
        if self.busy():
            return
        if device.connected:
            self.saying.setText(self.win.t("bt.disconnecting", name=device.shown))
            self.start(lambda: ("off", self.sound.disconnect(device.mac)), self.settled)
            return
        self.saying.setText(self.win.t("bt.connecting", name=device.shown))
        self.start(lambda: ("on",) + tuple(self.sound.connect(device.mac)), self.settled)

    def settled(self, answer) -> None:
        if isinstance(answer, Exception) or not isinstance(answer, tuple):
            self.saying.setText(self.win.t("bt.why.unknown"))
            self.changed.emit()
            return
        if answer[0] == "off":
            self.saying.setText("" if answer[1] else self.win.t("bt.why.unknown"))
        else:
            _, ok, why = answer
            self.saying.setText("" if ok else self.win.t(f"bt.why.{why}"))
        self.changed.emit()
        # Ask again rather than assume: what the mat now has connected is the only thing worth
        # repainting from, and a connect that reported success can still have dropped.
        #
        # NOT started here. This runs from the errand's own `done` signal, and that errand has
        # not finished yet -- starting the next one from inside it left two errands with one
        # reference between them, and the first to finish deleted the other while it was still
        # running. That is an abort, not an exception. So it is asked for, and taken up in
        # errand_finished once the thread it came from has gone.
        self.then_refresh = True

    def refresh(self) -> None:
        """Repaint the rows from what is connected now, without another ten-second look."""
        if self.busy():
            self.then_refresh = True
            return
        self.start(self.sound.known, self.relisted)

    def relisted(self, devices) -> None:
        if isinstance(devices, Exception):
            return
        remembered = {d.mac: d for d in devices}
        for row in self.device_rows():
            fresh = remembered.get(row.device.mac)
            if fresh is None:
                continue
            # Keep the signal strength: only a scan ever has it, and this was not one.
            row.device = type(fresh)(mac=fresh.mac, name=fresh.name or row.device.name,
                                     paired=fresh.paired, trusted=fresh.trusted,
                                     connected=fresh.connected,
                                     audio=(fresh.audio if fresh.audio is not None
                                            else row.device.audio),
                                     strength=row.device.strength)
        self.redraw_rows()
        self.show_where()

    def redraw_rows(self) -> None:
        devices = [row.device for row in self.device_rows()]
        self.clear_rows()
        for device in devices:
            row = DeviceRow(self.win, device)
            row.clicked.connect(lambda _=False, d=device: self.tapped(d))
            self.rows.addWidget(row)
        self.rows.addStretch(1)

    # -- threads ------------------------------------------------------------------------------

    def busy(self) -> bool:
        return self.errand is not None and self.errand.isRunning()

    def start(self, work, then) -> None:
        """Run one bluetoothctl call on a worker.

        The reference is dropped when the thread finishes, BEFORE the object is deleted -- the
        same order the Wi-Fi screen had to learn, where letting the thread deleteLater itself
        while this still pointed at it killed the app on the second scan.
        """
        errand = Errand(work)
        errand.done.connect(then)
        # Which errand finished, rather than whichever one this happens to be holding. Reading
        # it off self.errand is only right while there is never more than one in flight, and
        # a connect that asks for a repaint afterwards breaks that.
        errand.finished.connect(lambda e=errand: self.errand_finished(e))
        self.errand = errand
        errand.start()

    def errand_finished(self, which) -> None:
        if self.errand is which:
            self.errand = None
        which.deleteLater()
        # A repaint asked for from inside that errand's own callback. Taken up here, where the
        # thread it was asked from has gone and the reference has been let go.
        if self.then_refresh and self.errand is None:
            self.then_refresh = False
            self.refresh()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.show_where()
        if not self.device_rows():
            self.look()

    def shutdown(self) -> None:
        # Nothing new is to be started once the app is going: a repaint asked for a moment ago
        # would otherwise begin a thread nobody is left to wait for.
        self.then_refresh = False
        if self.busy():
            self.errand.wait(2000)

    def retitle(self) -> None:
        self.heading.setText(self.win.t("bt.title"))
        self.again.setText(self.win.t("bt.again"))
        self.leave.setText(self.win.t("corner.back"))
        self.show_where()
