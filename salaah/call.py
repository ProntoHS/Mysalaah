"""The call to prayer, on the screen as well as out of the speaker.

Five times a day the mat says it is time. It used to do that with a box carrying the name of
the prayer and a button to stop it. This shows the call itself: the muezzin, the words being
called, and what they mean -- so a boy who hears the adhan every day can read along with it and
come to know it, which is the whole point of the mat.

Three parts, each honest about what it is:

  * adhan.json -- the lines of the call, in Arabic, with the meaning in every language the app
    speaks. Drafted, and carrying reviewed: false until a reader of Arabic has been over it.
  * times.json -- where each line falls in a particular recording, measured off the recording
    by tools/build_azaan_times.py. A recording with no entry here simply shows the words
    without lighting them, which is the right way round: no red beats red in the wrong place.
  * this file -- the box, which knows how to show either.
"""
from __future__ import annotations

import json
from pathlib import Path

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .render import Fonts, TextBox

# The called words are the point of the box, and they were coming out at eighteen pixels on the
# 7" screen -- readable at arm's length and not from across a room, which is where somebody
# stands when the call goes off. The size is not chosen here: each line is drawn as large as its
# row is tall, so the way to make the words bigger is to give the rows more height. That is what
# the numbers below are for. The cap is only a backstop now, high enough never to be what
# decides.
ARABIC_FLOOR, ARABIC_CAP = 22, 110
BRICK = "#A63D33"


class Adhan:
    """The words of the call, and where they fall in the recordings there are timings for."""

    def __init__(self, assets: Path):
        self.folder = Path(assets) / "content" / "azaan"
        self._words: dict | None = None
        self._times: dict | None = None

    def _read(self, name: str) -> dict:
        try:
            return json.loads((self.folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @property
    def words(self) -> dict:
        if self._words is None:
            self._words = self._read("adhan.json")
        return self._words

    @property
    def times(self) -> dict:
        if self._times is None:
            self._times = self._read("times.json")
        return self._times

    @property
    def there(self) -> bool:
        return bool(self.words.get("lines"))

    @property
    def reviewed(self) -> bool:
        """Whether a reader of Arabic has been over the words. Nothing is hidden when this is
        false -- it is here so the file, and anyone reading the code, can say where it stands."""
        return bool(self.words.get("reviewed", False))

    def picture(self) -> Path:
        return self.folder.parent.parent / "azaan" / "muezzin.png"

    def film(self) -> Path:
        """The moving muezzin, if there is one. The still is what shows when there is not."""
        return self.folder.parent.parent / "azaan" / "muezzin.gif"

    def line(self, key: str) -> dict:
        for row in self.words.get("lines", []):
            if row.get("key") == key:
                return row
        return {}

    def order(self, recording: str) -> list[str]:
        """The keys of the lines called, in order, for this recording.

        From the timings when there are some, and otherwise from which call it is -- Fajr by
        its file name, the ordinary call for everything else. So the words are shown in the
        right order whether or not the recording has been measured.
        """
        known = self.times.get(recording)
        if known:
            return [row["key"] for row in known.get("lines", [])]
        which = "fajr" if "fajr" in recording else "ordinary"
        return list(self.words.get("calls", {}).get(which, []))

    def shown(self, recording: str) -> list[str]:
        """The distinct lines to put on screen, in the order they are first called."""
        seen, out = set(), []
        for key in self.order(recording):
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out

    def at(self, recording: str, seconds: float) -> tuple[str, int] | None:
        """Which line is being called and which of its words, or None between lines.

        None is a real answer, not a failure: the muezzin breathes between the lines, and
        nothing should be lit while he does.
        """
        known = self.times.get(recording)
        if not known:
            return None
        when = seconds * 1000.0
        for row in known.get("lines", []):
            if row["start"] <= when < row["end"]:
                for i, (a, b) in enumerate(row.get("words", [])):
                    if a <= when < b:
                        return row["key"], i
                return row["key"], -1        # in the line, between two of its words
        return None

    def measured(self, recording: str) -> bool:
        return bool(self.times.get(recording))


class Drawing(QtWidgets.QWidget):
    """A line drawing painted in one colour, keeping its shape.

    The picture is black lines on nothing, which is invisible on the black box it sits in. Only
    its shape matters, so it is used as a stencil and filled with whatever colour is wanted --
    and it stays the shape it was drawn, whatever shape the box it is given turns out to be.
    """

    def __init__(self, path: Path, colour: str = "#FFFFFF", film: Path | None = None):
        super().__init__()
        self.picture = QtGui.QPixmap(str(path)) if Path(path).is_file() else QtGui.QPixmap()
        self.colour = colour
        # A moving muezzin if there is one. It is drawn on its own black ground rather than
        # used as a stencil: it is a film, not a shape, and filling it with one colour would
        # flatten every frame to the same silhouette.
        self.film: QtGui.QMovie | None = None
        if film is not None and Path(film).is_file():
            movie = QtGui.QMovie(str(film))
            if movie.isValid() and movie.frameCount() > 1:
                movie.setParent(self)
                # A bound method, not a lambda. A lambda holding this widget is just a Python
                # object as far as Qt is concerned, so the connection outlives the widget: a
                # frame arriving while the call box is being taken down repainted something
                # whose C++ half had already gone, and one of the two Qt kits died on it. A
                # bound method of a QObject is tied to that object, and Qt drops the
                # connection when it goes.
                movie.frameChanged.connect(self.next_frame)
                self.film = movie
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    @property
    def there(self) -> bool:
        return self.film is not None or not self.picture.isNull()

    @property
    def moving(self) -> bool:
        return self.film is not None and self.film.state() == QtGui.QMovie.MovieState.Running

    def next_frame(self, _frame: int) -> None:
        self.update()

    def start(self) -> None:
        if self.film is not None:
            self.film.start()

    def stop(self) -> None:
        if self.film is not None:
            self.film.stop()

    def showEvent(self, ev):
        self.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        # Whenever it goes off screen, not only when the call box is dismissed. A film left
        # running is a timer asking a hidden widget to repaint five times a second -- on the Pi
        # that is the processor woken for nobody, and when the widget is on its way out it is a
        # crash. Which is what happened: the box in one test was closed by the window going
        # away rather than by its own button, and the next test died with it.
        self.stop()
        super().hideEvent(ev)

    def paintEvent(self, _):
        if self.film is not None:
            frame = self.film.currentPixmap()
            if not frame.isNull():
                fitted = frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                p = QtGui.QPainter(self)
                p.drawPixmap((self.width() - fitted.width()) // 2,
                             (self.height() - fitted.height()) // 2, fitted)
                return
        if self.picture.isNull():
            return
        fitted = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        stencil = QtGui.QPixmap(fitted.size())
        stencil.fill(Qt.GlobalColor.transparent)
        ink = QtGui.QPainter(stencil)
        ink.drawPixmap(0, 0, fitted)
        ink.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        ink.fillRect(stencil.rect(), QtGui.QColor(self.colour))
        ink.end()
        p = QtGui.QPainter(self)
        p.drawPixmap((self.width() - fitted.width()) // 2,
                     (self.height() - fitted.height()) // 2, stencil)


class CallBox(QtWidgets.QDialog):
    """The box that comes up when the call is made.

    Black with a white border, like the app's other notices and for the same reason: the call
    is not part of the prayer screen, and it should not look as though it is. The muezzin on
    the left, the lines of the call on the right, each with its meaning underneath, and the
    word being called in red.
    """

    LINE_TICK = 50       # ms; how often the red moves, matching the Qur'an screen

    def __init__(self, window, prayer: str, recording: str, adhan: Adhan):
        super().__init__(window)
        self.win = window
        self.adhan = adhan
        self.recording = recording
        px = window.px
        self.setObjectName("callBox")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        # THE MUEZZIN GOES ON THE 7in WHERE THERE IS ONE, and the words get this screen to
        # themselves. Harry, 12 November 2026: "could the gif be moved to the 7" posture
        # screen instead. this way the text / translation will have the main screen to
        # itself."
        #
        # It is free to take: the 7in shows postures during a prayer and the Knowledge Corner
        # between them, and the call comes BEFORE the prayer, so at that moment the small
        # screen is doing nothing anybody is watching.
        #
        # Checked rather than assumed, because the thing that would sink it is not obvious:
        # this dialog is MODAL, and a modal dialog blocks input to every other window in the
        # application. Input, not painting -- the event loop keeps running and the 7in's
        # timers keep firing, which was measured on a window with the call box up before any
        # of this was built. Nothing on the companion is pressable anyway.
        #
        # A ONE-SCREEN MAT KEEPS THE MUEZZIN HERE. Moving him to a screen that does not exist
        # would simply lose him, and a mat with one display would have gone from a picture and
        # the words to the words alone without anybody asking for that.
        self.small = getattr(window, "side", None)
        self.companion = self.small_screen_panel(prayer) if self.small is not None else None

        # BIGGER WORDS WHERE THERE IS ROOM FOR THEM, and the room is the title row rather
        # than the muezzin's old column. Harry asked for the text to "take advantage of extra
        # space", and the obvious reading -- the width the picture gave back -- turns out to
        # buy nothing: the Arabic is set one line to a row and sized to the HEIGHT of its row,
        # and it was already at its 110px ceiling with 1,852px of width it could not use.
        #
        # What did free up is vertical: "TIME TO PRAY" and the prayer's name are off this
        # screen, which is about 70px spread over six rows. So the ceiling goes up, which lets
        # the rows actually take it, and the meanings -- 26px drawing 318px of line in a
        # 1,852px space -- come up with them. On a one-screen mat none of that room exists and
        # both stay where they were.
        cap = ARABIC_CAP + (26 if self.companion is not None else 0)
        meaning = 34 if self.companion is not None else 26

        # No rounded corners and no border: it covers the screen, so there is no edge for them
        # to sit on and a white line down the side of a full screen is just a white line.
        self.setStyleSheet(f"""
            QDialog#callBox {{ background:#000000; }}
            QDialog#callBox QLabel {{ color:#FFFFFF; background:transparent; }}
            QLabel#callTitle {{ font-size:{px(52)}px; font-weight:bold; }}
            QLabel#callMeaning {{ font-size:{px(meaning)}px; color:#C9C9C9; }}
            QDialog#callBox QPushButton {{ background:{BRICK}; color:#FFFFFF; border:none;
                                           border-radius:{px(8)}px; font-size:{px(28)}px;
                                           font-weight:bold; }}
            QDialog#callBox QPushButton:pressed {{ background:#8E342C; }}
        """)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(px(34), px(20), px(34), px(18))
        outer.setSpacing(px(10))

        # The title, and Stop in the corner beside it.
        #
        # The call fills the screen now rather than sitting in a box in the middle of it, and
        # a button at the bottom of a full screen is a long way from a thumb. Top right, square
        # and large: it is the only thing on this screen to press, and the one moment somebody
        # wants it is the moment the mat has started calling out loud in a quiet house.
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(px(16))
        # "TIME TO PRAY" HAS GONE, at Harry's asking: the mat has just called the azaan out
        # loud in the house, so a line of screen saying it is time to pray is telling somebody
        # something they have already been told, in the only words on the screen that are not
        # the call itself.
        #
        # The prayer's name goes with the muezzin to the 7in where there is one, so this
        # screen is the words and the Stop button and nothing else. Where there is no 7in the
        # name stays here, because otherwise nothing on the mat would say which prayer it is.
        if self.companion is None:
            head = QtWidgets.QLabel(window.t(f"prayer.{prayer}"))
            head.setObjectName("callTitle")
            head.setWordWrap(True)
            top.addWidget(head, 1)
            top.addWidget(self.make_stop(), 0, Qt.AlignmentFlag.AlignTop)
            outer.addLayout(top)
        else:
            # NO ROW FOR STOP WHEN IT IS THE ONLY THING IN ONE. With the name and the muezzin
            # gone to the 7in, a row holding one button in the corner was 120px of height for
            # 120px of button -- and height is the ONLY thing the words are short of.
            #
            # That is worth saying plainly, because the obvious reading of "the picture has
            # gone, so there is more room" is wrong. The Arabic is set one line to a row and
            # sized to the HEIGHT of its row: measured against the published 2.22, taking the
            # muezzin off this screen moved the rows not one pixel -- 98px before and 98px
            # after -- because the 550px it gave back was width the words already had too much
            # of. The meanings could have grown, but only by taking that height off the
            # Arabic, which is the wrong way round on the one screen where the Arabic IS the
            # point.
            #
            # So the button floats in the corner instead and the words get the whole height.
            # The lines keep a margin either side as wide as the button, so a long line cannot
            # run under it -- symmetric, so the text stays centred, and affordable because
            # width is the one thing there is plenty of.
            self.make_stop().setParent(self)
            self.stop_button.raise_()


        body = QtWidgets.QHBoxLayout()
        body.setSpacing(px(32))
        self.drawing = Drawing(adhan.picture(), film=adhan.film())
        if not self.drawing.there:
            self.drawing.hide()
        elif self.companion is None:
            # ONE SCREEN: the muezzin stays here beside the words, as he always did.
            self.drawing.setMinimumWidth(px(220))
            body.addWidget(self.drawing, 2)

        lines = QtWidgets.QVBoxLayout()
        # Tight. Every pixel not spent between the rows is a pixel the words are drawn at, seven
        # times over, and a meaning belongs against the line it translates rather than floating
        # between two of them.
        lines.setSpacing(px(2))
        self.boxes: dict[str, TextBox] = {}
        lang = self.meaning_language()
        for key in adhan.shown(recording):
            row = adhan.line(key)
            arabic = TextBox(Fonts.arabic(window.settings.arabic_font),
                             ARABIC_FLOOR, cap, rtl=True, by_word=True, one_line=True)
            arabic.scale = window.s
            arabic.set_lines([row.get("arabic", "")])
            arabic.setMinimumHeight(px(52))
            lines.addWidget(arabic, 3)
            self.boxes[key] = arabic

            # No meaning at all when the mat is set to Arabic only -- the call is the one
            # screen where the Arabic is the whole point, and a line of English under each
            # one is exactly what that setting says not to show.
            said = QtWidgets.QLabel(row.get("text", {}).get(lang, "") if lang else "")
            said.setObjectName("callMeaning")
            said.setVisible(bool(lang))
            said.setWordWrap(True)
            said.setAlignment(Qt.AlignmentFlag.AlignCenter)
            said.setLayoutDirection(Qt.LayoutDirection.RightToLeft if lang == "ur"
                                    else Qt.LayoutDirection.LeftToRight)
            said.setContentsMargins(0, 0, 0, px(8))     # the gap goes below the pair, not inside it
            lines.addWidget(said, 0)
        if self.companion is not None:
            # Clear of the floating Stop, and the same margin on the other side so the words
            # stay centred on the screen rather than on what is left of it.
            room = max(self.win.px(92), int(1008 * 0.11)) + self.win.px(40)
            lines.setContentsMargins(room, 0, room, 0)
        body.addLayout(lines, 5)
        outer.addLayout(body, 1)

        # Nothing along the bottom any more: Stop has gone to the top right, where the thumb
        # is, and the room it leaves goes to the lines of the call.

        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(self.LINE_TICK)
        self.follow.timeout.connect(self.tick)
        if adhan.measured(recording):
            self.follow.start()

    def small_screen_panel(self, prayer: str) -> QtWidgets.QWidget:
        """What the 7" shows while the call is being made: the prayer, then the muezzin.

        The name centred along the top and the picture directly under it, which is the order
        Harry asked for and the order they are read in -- which prayer, then the man calling
        it. Nothing else: no Stop (it is on the big screen, under the hand that would reach
        for it) and no words of the call (they are on the big screen too, at a size that
        wants the room).

        Built here rather than in side.py for the same reason a game's companion is: the
        screen is lent, not handed over, and the thing that knows what to put on it is the
        thing that borrowed it.
        """
        px = self.win.px
        panel = QtWidgets.QWidget()
        panel.setObjectName("callCompanion")
        panel.setStyleSheet(f"""
            QWidget#callCompanion {{ background:#000000; }}
            QWidget#callCompanion QLabel {{ color:#FFFFFF; background:transparent; }}
            QLabel#callCompanionTitle {{ font-size:{px(44)}px; font-weight:bold; }}
        """)
        column = QtWidgets.QVBoxLayout(panel)
        column.setContentsMargins(px(16), px(14), px(16), px(16))
        column.setSpacing(px(10))

        said = QtWidgets.QLabel(self.win.t(f"prayer.{prayer}"))
        said.setObjectName("callCompanionTitle")
        said.setAlignment(Qt.AlignmentFlag.AlignCenter)
        said.setWordWrap(True)
        column.addWidget(said, 0)

        self.companion_drawing = Drawing(self.adhan.picture(), film=self.adhan.film())
        if self.companion_drawing.there:
            column.addWidget(self.companion_drawing, 1)
        else:
            self.companion_drawing.hide()
            column.addStretch(1)
        return panel

    def lend_the_small_screen(self) -> None:
        """Put the companion on the 7" and start its film."""
        if self.companion is None:
            return
        # NOTHING STARTS THE FILM HERE, and that is not an oversight. Drawing starts itself
        # on show and stops itself on hide, which is deliberate and documented where it is
        # written: a film must stop when the widget goes off screen however that happens, not
        # only when a particular button is pressed. Mounting the companion shows it, and
        # handing the screen back hides it.
        #
        # It had an explicit start() and stop() around this until a sabotage run put the lie
        # to them: breaking the start changed nothing anybody could observe, because the
        # widget had already done it. A line that cannot be seen to matter is worse than no
        # line, since the next person to read it believes it is holding something up.
        self.small.show_call(self.companion)

    def give_the_small_screen_back(self) -> None:
        """Hand the 7" back to whatever it was showing, and stop the film with it.

        STOPPING IT MATTERS MORE THAN IT LOOKS. A film left running is a timer waking the Pi
        ten times a second to repaint a widget nobody can see, and this mat calls five times
        a day for months at a stretch -- which is the same reason ui.let_go_of_the_box exists
        at all.
        """
        if self.companion is None:
            return
        self.small.show_idle()

    def meaning_language(self) -> str:
        """The interface language if the call has been translated into it, English if not, and
        "" -- no meaning under the lines -- when the mat is set to Arabic only."""
        from .ui import ARABIC_ONLY
        wanted = getattr(self.win.pack, "lang", "en")
        if wanted == ARABIC_ONLY:
            return ""
        rows = self.adhan.words.get("lines", [])
        have = all(row.get("text", {}).get(wanted) for row in rows) if rows else False
        return wanted if have else "en"

    def tick(self) -> None:
        """Move the red onto the word being called."""
        clock = getattr(self.win.call, "position", None)
        position = clock() if callable(clock) else None
        if position is None:
            return self.clear()
        where = self.adhan.at(self.recording, position)
        for key, box in self.boxes.items():
            if where is not None and where[0] == key and where[1] >= 0:
                box.set_highlight((0, where[1]))
            else:
                box.set_highlight(None)

    def clear(self) -> None:
        for box in self.boxes.values():
            box.set_highlight(None)

    def fit(self) -> None:
        """The whole screen but the strip across the top.

        It used to be 88% by 92%, a box sitting on top of the mat with the mat showing round
        the edge. Harry asked for the full screen and he is right: the call is not a message
        about something else happening, it IS what the mat is doing, and a margin of prayer
        times round the outside is the screen arguing with itself. It also buys the Arabic a
        good deal more room, which is the point of showing it at all.

        The strip stays, though -- "full screen BUT retain the top banner only". It is the one
        part of the screen that is true wherever you are, and during the call it is the thing
        worth seeing: where you are, and which prayer the mat has just reached. The call takes
        everything under it.
        """
        parent = self.parentWidget()
        if parent is None:
            return
        strip = getattr(parent, "banner_height", None)
        top = strip() if callable(strip) else 0
        top = max(0, min(int(top), parent.height() // 3))
        self.resize(parent.width(), parent.height() - top)
        self.move(parent.x(), parent.y() + top)

    def make_stop(self) -> QtWidgets.QPushButton:
        """The one thing on this screen to press, built once wherever it ends up living."""
        self.stop_button = QtWidgets.QPushButton(self.win.t("call.stop"))
        self.stop_button.setObjectName("callStop")
        self.stop_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(self.accept)
        return self.stop_button

    def put_the_stop_in_the_corner(self) -> None:
        """Where the button floats rather than sitting in a row of its own.

        Top right, a margin in from both edges: the corner a thumb reaches for, and the one
        moment anybody wants it is the moment the mat has started calling out loud in a quiet
        house. Only used where the words have the screen to themselves; with the muezzin here
        the button sits in the title row as it always did.
        """
        if self.companion is None:
            return
        gap = self.win.px(20)
        self.stop_button.move(self.width() - self.stop_button.width() - gap, gap)
        self.stop_button.raise_()

    def square_off_the_stop(self) -> None:
        """Stop is a square, and a big one.

        Sized against the title beside it rather than set in the stylesheet, for the reason the
        Qur'an screen's play mark is: "Stop" is Arrêter in French and رک جائیں in Urdu, so how
        wide the word is depends on the language and the face, and is only known once it has
        been laid out. A fixed size in the stylesheet either clips the long ones or leaves the
        short ones rattling around.
        """
        side = max(self.win.px(92), int(self.height() * 0.11))
        if self.stop_button.size() != QtCore.QSize(side, side):
            self.stop_button.setFixedSize(side, side)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.square_off_the_stop()
        self.put_the_stop_in_the_corner()

    def showEvent(self, ev):
        self.fit()
        self.square_off_the_stop()
        self.put_the_stop_in_the_corner()
        self.drawing.start()
        # The two screens come up together: the words here, the muezzin on the 7in.
        self.lend_the_small_screen()
        super().showEvent(ev)

    def done(self, result):
        self.follow.stop()
        self.drawing.stop()          # nothing to repaint for once the call is over
        self.give_the_small_screen_back()
        super().done(result)
