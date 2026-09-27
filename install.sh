#!/bin/bash
# Sets up the prayer app on Raspberry Pi OS (64-bit, with desktop). Needs internet the first time.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "== Installing packages"
sudo apt-get update
sudo apt-get install -y python3-evdev python3-venv libxcb-cursor0 mpg123

# ddcutil turns the brightness slider into the monitor's real backlight rather than a grey veil.
# wlr-randr is how we find out which screen is which. Both are optional; the app copes without.
sudo apt-get install -y ddcutil wlr-randr || echo "!! No ddcutil/wlr-randr: brightness and touch mapping will be skipped"

# For the Qibla compass chip (BNO055) on the I2C pins. Harmless if no chip is fitted.
sudo apt-get install -y python3-smbus i2c-tools || echo "!! Could not install the I2C tools; the compass will be skipped"
sudo raspi-config nonint do_i2c 0 || echo "!! Turn on I2C in raspi-config (Interface Options) for the compass"
if ! id -nG "$USER" | grep -qw i2c; then sudo usermod -aG i2c "$USER" || true; fi

if sudo apt-get install -y python3-pyqt6 && python3 -c "import PyQt6.QtWidgets" 2>/dev/null; then
    echo "== Using PyQt6 from Raspberry Pi OS"
else
    echo "== Installing PySide6 into .venv (a few minutes)"
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install PySide6
fi

# The app reads Bluetooth buttons directly, which needs the 'input' group.
if ! id -nG "$USER" | grep -qw input; then
    sudo usermod -aG input "$USER"
    echo "== Added $USER to the input group (takes effect after a reboot)"
fi

# The screen must not blank in the middle of a prayer.
sudo raspi-config nonint do_blanking 1 || echo "!! Turn off Screen Blanking in the Control Centre (Display)"

# A USB touchscreen reports positions across the whole desktop, so with two displays the taps
# land on the wrong screen and the panel looks broken while being perfectly healthy.
echo "== Pointing the touchscreen at the small display"
python3 tools/map_touch.py || echo "!! Touch mapping skipped; run tools/map_touch.py by hand"

# Start automatically when the Pi logs in, and add a menu entry.
chmod +x run.sh
mkdir -p ~/.config/autostart ~/.local/share/applications
sed "s#@DIR@#$DIR#g" salaah.desktop > ~/.config/autostart/salaah.desktop
sed "s#@DIR@#$DIR#g" salaah.desktop > ~/.local/share/applications/salaah.desktop

echo "== Done. Start it now with ./run.sh, or reboot and it starts by itself."
