"""Reads Bluetooth buttons (selfie ring, AB Shutter3) straight from Linux input devices.

Reading devices directly, like the original Pi app did, means presses reach the app even when the
desktop would normally take them (volume keys change the volume). Bluetooth devices are "grabbed"
so their presses only go to the prayer app.

Rules: any press on a Bluetooth input device means NEXT, except back-type keys (Volume Down,
Previous, Page Up, Left). A press held longer than HOLD seconds is ignored, because that is what
a palm pressing on a ring in sujood looks like; deliberate clicks are short.
"""
from __future__ import annotations

import select
import threading
import time
from typing import Callable

NEXT, BACK = "next", "back"

EV_KEY = 0x01
BUS_BLUETOOTH = 0x05
BACK_CODES = {114, 165, 104, 105}  # KEY_VOLUMEDOWN, KEY_PREVIOUSSONG, KEY_PAGEUP, KEY_LEFT


def action_for(code: int) -> str:
    return BACK if code in BACK_CODES else NEXT


class PressFilter:
    """Turns raw key down/up events into actions: act on release, ignore long holds and repeats."""

    def __init__(self, hold: float = 1.0):
        self.hold = hold
        self._down: dict[int, float] = {}

    def event(self, code: int, value: int, t: float) -> str | None:
        if value == 1:  # pressed
            self._down[code] = t
            return None
        if value == 0:  # released
            start = self._down.pop(code, None)
            if start is None or t - start > self.hold:
                return None
            return action_for(code)
        return None  # 2 = auto-repeat while held


class BluetoothButtons:
    """Background thread watching for Bluetooth input devices. Calls [on_action] with NEXT/BACK
    and [on_devices] with the list of connected device names. Callbacks run on the reader thread."""

    RESCAN = 2.0

    def __init__(self, on_action: Callable[[str], None], on_devices: Callable[[list[str]], None],
                 hold: float = 1.0):
        self.on_action = on_action
        self.on_devices = on_devices
        self.filter = PressFilter(hold)
        self._stop = threading.Event()
        self._devices = {}
        self._thread: threading.Thread | None = None
        self.available = True
        try:
            import evdev  # noqa: F401
        except ImportError:
            self.available = False

    def start(self) -> None:
        if not self.available:
            return
        self._thread = threading.Thread(target=self._run, name="bt-buttons", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _scan(self) -> None:
        import evdev
        changed = False
        for path in evdev.list_devices():
            if path in self._devices:
                continue
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            if dev.info.bustype != BUS_BLUETOOTH or EV_KEY not in dev.capabilities():
                dev.close()
                continue
            try:
                dev.grab()
            except OSError:
                pass  # still readable; the desktop may also see its presses
            self._devices[path] = dev
            changed = True
        if changed:
            self._report()

    def _report(self) -> None:
        names = sorted({d.name for d in self._devices.values()})
        self.on_devices(names)

    def _drop(self, path: str) -> None:
        dev = self._devices.pop(path, None)
        if dev:
            try:
                dev.close()
            except OSError:
                pass
        self._report()

    def _run(self) -> None:
        self.on_devices([])
        last_scan = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_scan > self.RESCAN:
                self._scan()
                last_scan = now
            if not self._devices:
                self._stop.wait(0.5)
                continue
            by_fd = {d.fd: (p, d) for p, d in self._devices.items()}
            try:
                ready, _, _ = select.select(list(by_fd), [], [], 0.5)
            except (OSError, ValueError):
                ready = []
            for fd in ready:
                path, dev = by_fd[fd]
                try:
                    for ev in dev.read():
                        if ev.type == EV_KEY:
                            action = self.filter.event(ev.code, ev.value, time.monotonic())
                            if action:
                                self.on_action(action)
                except OSError:  # device went away (switched off or out of range)
                    self._drop(path)
