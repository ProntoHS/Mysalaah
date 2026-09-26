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
    translation: str = ""  # "" for Arabic only, or a language in content/translations (en, fr)
    figure: str = "boy"  # whose posture pictures to show: a set in assets/postures
    theme: str = "auto"  # "auto" (dark from Maghrib to sunrise), "light" or "dark"
    cursor: bool = True  # show the mouse pointer (turn off in Settings for a touchscreen alone)
    arabic_font: str = "scheherazade"  # a key from render.FONTS
    inset: int = 0  # pixels kept clear on every edge, if the monitor cuts them off
    main_output: str = ""  # the screen the words went on last time, e.g. HDMI-A-1
    side_output: str = ""  # the 7" posture screen last time; both are worked out if they are wrong
    recitation: bool = True  # play the recorded recitation and follow the words in red
    volume: int = 80  # 0-100: how loud the recitation is, set by the bar on the prayer screen
    azaan: bool = True        # call to prayer when a prayer falls due
    sleep_after: int = 3      # minutes with nothing pressed before the screens go off; 0 never.
                              # Not on the Settings screen: two more rows there would push a
                              # 1920x1080 monitor into scrolling. Edit it here to change it.
    latitude: float = 53.5933     # for prayer times; Bury, Greater Manchester
    longitude: float = -2.2966
    place: str = "Bury"
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
