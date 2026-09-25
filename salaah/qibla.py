"""The direction of the Kaaba, and which way the mat is facing.

The direction comes from the location alone: the great-circle bearing from here to the Kaaba,
in degrees clockwise from true north (118.5 from Bury). Which way the mat faces needs a sensor:
a compass chip in the display housing. Three sources of heading:

    NoCompass     nothing fitted; the screen shows the bearing to line up with a phone compass
    BNO055        the recommended chip on the Pi's I2C pins; gives a tilt-compensated heading
    StandIn       for trying the screen without the chip: the arrow keys turn it

A compass reads magnetic north, a few degrees off true north in places; `declination` (east is
positive) corrects it. In the UK it is under a degree, so it defaults to nought.
"""
from __future__ import annotations

import math

KAABA = (21.4225, 39.8262)
IN_LINE = 10.0          # degrees either side that count as facing the Qibla
MOVED = 15.0            # turned further than this since last lined up: ask again


def bearing_to_kaaba(latitude: float, longitude: float) -> float:
    """Great-circle bearing from here to the Kaaba, degrees clockwise from true north."""
    lat1, lon1 = math.radians(latitude), math.radians(longitude)
    lat2, lon2 = math.radians(KAABA[0]), math.radians(KAABA[1])
    d = lon2 - lon1
    y = math.sin(d) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d)
    return math.degrees(math.atan2(y, x)) % 360


def turn_needed(heading: float, qibla: float) -> float:
    """How far to turn, in degrees: positive to the right, negative to the left, within ±180."""
    return (qibla - heading + 180) % 360 - 180


def compass_point(degrees: float) -> str:
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((degrees % 360) / 22.5 + 0.5) % 16]


class Smoother:
    """Evens out a jittery compass. Headings wrap at 360, so it averages them as directions,
    not as numbers (the average of 359 and 1 is 0, not 180)."""

    def __init__(self, weight: float = 0.25):
        self.weight = weight
        self.x = self.y = None

    def add(self, degrees: float) -> float:
        r = math.radians(degrees)
        if self.x is None:
            self.x, self.y = math.cos(r), math.sin(r)
        else:
            self.x += self.weight * (math.cos(r) - self.x)
            self.y += self.weight * (math.sin(r) - self.y)
        return math.degrees(math.atan2(self.y, self.x)) % 360


class NoCompass:
    """Nothing fitted: the heading is unknown."""
    name = "none"
    fitted = False

    def heading(self) -> float | None:
        return None


class StandIn:
    """Pretends to be a compass so the screen can be tried without one. The arrow keys turn
    it, five degrees a press."""
    name = "stand-in"
    fitted = True

    def __init__(self, start: float = 0.0):
        self.value = start % 360

    def turn(self, degrees: float) -> None:
        self.value = (self.value + degrees) % 360

    def heading(self) -> float | None:
        return self.value


class BNO055:
    """Bosch BNO055 on I2C bus 1 (the Pi's pins 3 and 5), address 0x28. In its NDOF mode the
    chip combines its compass, accelerometer and gyro itself and reports a heading that stays
    right when the display is tilted back on its stand.

    Needs smbus2 (or Raspberry Pi OS's python3-smbus) and I2C switched on
    (sudo raspi-config nonint do_i2c 0). Written to the datasheet, not yet tried on a real chip."""
    name = "BNO055"
    ADDRESS = 0x28
    CHIP_ID, CHIP_ID_VALUE = 0x00, 0xA0
    OPR_MODE, CONFIG_MODE, NDOF_MODE = 0x3D, 0x00, 0x0C
    HEADING = 0x1A           # two bytes, little end first, sixteenths of a degree
    CALIB_STAT = 0x35        # two bits for the compass in the lowest pair: 3 is fully calibrated

    def __init__(self, bus: int = 1):
        import time
        try:                                 # only needed when the chip is fitted
            from smbus2 import SMBus         # noqa: PLC0415
        except ImportError:
            from smbus import SMBus          # noqa: PLC0415 - Raspberry Pi OS's python3-smbus
        self.bus = SMBus(bus)
        if self.bus.read_byte_data(self.ADDRESS, self.CHIP_ID) != self.CHIP_ID_VALUE:
            raise OSError("no BNO055 answering at 0x28")
        self.bus.write_byte_data(self.ADDRESS, self.OPR_MODE, self.CONFIG_MODE)
        time.sleep(0.03)
        self.bus.write_byte_data(self.ADDRESS, self.OPR_MODE, self.NDOF_MODE)
        time.sleep(0.03)
        self.fitted = True

    def heading(self) -> float | None:
        try:
            low, high = self.bus.read_i2c_block_data(self.ADDRESS, self.HEADING, 2)
        except OSError:
            return None
        return ((high << 8 | low) / 16.0) % 360

    def calibrated(self) -> int:
        """0 (not yet) to 3 (fully): the chip learns as it is moved in a figure of eight."""
        try:
            return self.bus.read_byte_data(self.ADDRESS, self.CALIB_STAT) & 0x03
        except OSError:
            return 0


def find_compass(stand_in: bool = False):
    """The compass to use: the stand-in if asked for, a BNO055 if one answers, else none."""
    if stand_in:
        return StandIn()
    try:
        return BNO055()
    except Exception:  # noqa: BLE001 - no smbus2, no I2C, no chip: all mean "not fitted"
        return NoCompass()


class Facing:
    """Which way the display faces, in degrees from true north, from a compass: smoothed,
    corrected for declination and for how the chip is mounted in the housing."""

    def __init__(self, compass, declination: float = 0.0, mounting: float = 0.0):
        self.compass = compass
        self.declination = declination
        self.mounting = mounting
        self.smooth = Smoother()

    @property
    def fitted(self) -> bool:
        return getattr(self.compass, "fitted", False)

    def read(self) -> float | None:
        raw = self.compass.heading()
        if raw is None:
            return None
        return self.smooth.add((raw + self.declination + self.mounting) % 360)
