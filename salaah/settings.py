"""User settings, kept in ~/.config/salaah/settings.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PATH = Path.home() / ".config" / "salaah" / "settings.json"


@dataclass
class Settings:
    school: str = "hanafi"
    lang: str = "en"
    brightness: int = 100  # 10-100: the monitor's own backlight, over the cable (DDC/CI).
                           # On a monitor that will not take instruction this dims the prayer
                           # screen with a veil instead, which looks darker without saving power.
    # "translation" (the meaning shown beside the Arabic) was a setting of its own until 1.58.
    # It asked the same question as `lang` and could disagree with it, so it has gone; `lang`
    # decides the meaning now, and lang == "ar" means no meaning at all. Old settings.json
    # files may still carry the key -- load() ignores what it does not know, so it just goes.
    figure: str = "boy"  # whose posture pictures to show: a set in assets/postures
    theme: str = "auto"  # "auto" (dark from Maghrib to sunrise), "light" or "dark"
    cursor: bool = True  # show the mouse pointer (turn off in Settings for a touchscreen alone)
    arabic_font: str = "scheherazade"  # a key from render.FONTS
    text_step: int = 0        # how large the Qur'an is set: 0, 1 or 2, chosen by the three A
                              # buttons on the reading bar. Each step is half as big again as
                              # the one before -- see reading.TEXT_STEPS. Kept here rather than
                              # on the Settings screen because it is a thing you reach for
                              # while reading, with the page in front of you.
    inset: int = 0  # pixels kept clear on every edge, if the monitor cuts them off
    main_output: str = ""  # the screen the words went on last time, e.g. HDMI-A-1
    side_output: str = ""  # the 7" posture screen last time; both are worked out if they are wrong
    recitation: bool = True  # play the recorded recitation and follow the words in red
    volume: int = 80  # 0-100: how loud the recitation is, set by the bar on the prayer screen
    # "quran_lang" went the same way as "translation" in 1.58. It was the meaning shown beside
    # the Qur'an, set by a row of buttons on the reading bar, and it was the third place the mat
    # asked a question it now asks once. `lang` decides it, and lang == "ar" means the Arabic
    # takes both pages with no meaning beside it.
    azaan: bool = True        # call to prayer when a prayer falls due
    sleep_after: int = 3      # minutes with nothing pressed before the screens go off; 0 never.
                              # Not on the Settings screen: two more rows there would push a
                              # 1920x1080 monitor into scrolling. Edit it here to change it.
    latitude: float = 53.5933     # for prayer times; Bury, Greater Manchester
    longitude: float = -2.2966
    place: str = "Bury"
    # What to show for Fajr and Isha in the weeks when the sun never gets 18 degrees below the
    # horizon -- about 14 May to 30 July at Bury's latitude. "nearest_day" is Aqrab al-Ayyam:
    # the times from the closest date that did have them. "none" leaves them blank, which is
    # what the mat did before. Which convention is right is a question for a teacher.
    high_latitude: str = "nearest_day"
    qibla_start: bool = True        # show the Qibla compass when the app starts
    qibla_heading: float | None = None   # which way the display faced when last lined up
    compass_declination: float = 0.0     # magnetic to true north, east positive (UK: under 1)
    compass_mounting: float = 0.0        # the compass chip's forward edge vs the display's
    update_url: str = ""       # where to look for updates; empty uses the one built in.
                               # A way to point one mat at a laptop while this is tested,
                               # or to move a mat if the address ever has to change.

    @staticmethod
    def load(path: Path = PATH) -> "Settings":
        try:
            data = json.loads(path.read_text())
            # "dim" was how dark to make the screen; "brightness" is how bright to leave it.
            # Carry the old answer across rather than quietly resetting somebody's setting.
            if "dim" in data and "brightness" not in data:
                try:
                    data["brightness"] = max(10, 100 - int(data["dim"]))
                except (TypeError, ValueError):
                    pass
            return Settings(**{k: v for k, v in data.items() if k in Settings.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self, path: Path = PATH) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2))
        except OSError:
            pass
