"""
serial_link.py
WRO 2026 Future Engineers — packages (steering, speed) into a command
message and ships it to the motor controller (Arduino/SBM) over serial.

GAP #3 FIX: previously the whole pipeline dead-ended at cv2.imshow(...)
— nothing ever left the SBC. This module is that missing output stage,
wired into main.py's per-frame loop.

PROTOCOL (plain text, newline-terminated — parseable on the Arduino
side with Serial.readStringUntil('\\n') + a comma split/sscanf):

    "S<steer_deg>,<speed_pwm>,<flag>\\n"

    steer_deg : signed float, degrees, positive = steer right
    speed_pwm : signed float, 0-100 magnitude (negative sign = reverse,
                used by control/parking_maneuver.py). Name/format is
                unchanged since the drive motor swap to a stepper
                (STH-39D219, A4988/DRV8825 STEP/DIR driver) -- the
                Arduino now maps this magnitude onto a step-pulse
                frequency instead of an H-bridge PWM duty cycle; see
                firmware/vehicle_controller.ino::writeDriveMotor().
    flag      : single ASCII state marker for the Arduino side's own
                onboard LED/buzzer feedback if it wants one —
                'D' = driving, 'P' = parking, 'S' = stopped/waiting

DRY-RUN / MOCK MODE
    If pyserial isn't installed, no Arduino is plugged in, or the given
    port can't be opened, this does NOT crash the vision pipeline. It
    falls back to a MockBackend that logs every command it would have
    sent (stdout, and every command is also visible in the returned
    history for tests) so the exact same main.py runs identically on a
    laptop with no hardware attached and on the real robot — a real
    output stage with a drop-in mock, not a pipeline that silently does
    nothing when hardware isn't present.
"""

from __future__ import annotations
import time
from typing import Optional

try:
    import serial  # pyserial
    _HAS_PYSERIAL = True
except ImportError:  # pragma: no cover — exercised in environments without pyserial
    _HAS_PYSERIAL = False


class _MockBackend:
    """Stand-in for a real serial.Serial when no hardware is attached."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.sent: list[bytes] = []   # history — useful for tests/telemetry review

    def write(self, payload: bytes) -> int:
        self.sent.append(payload)
        if self.verbose:
            print(f"[serial_link:MOCK] {payload.decode().strip()}")
        return len(payload)

    def close(self) -> None:
        pass

    @property
    def in_waiting(self) -> int:
        return 0  # nothing to read back — no real device is attached

    def readline(self) -> bytes:
        return b""

    @property
    def is_open(self) -> bool:
        return True


class SerialLink:
    """
    One instance per round. Call send(steering_deg, speed_pwm, flag)
    once per control-loop tick (main.py's frame loop). Automatically
    falls back to a MockBackend if the real port can't be opened, and
    demotes to MockBackend mid-run if a write ever fails (e.g. USB
    unplugged) rather than crashing the vision loop mid-competition.
    """

    def __init__(self, port: str = "/dev/ttyACM0", baud: int = 115200,
                 timeout: float = 0.05, min_send_interval: float = 0.0,
                 force_mock: bool = False, verbose_mock: bool = True):
        self.port = port
        self.baud = baud
        self.min_send_interval = min_send_interval
        self._last_send_t = 0.0
        self._is_mock = True
        self._backend = None

        if force_mock or not _HAS_PYSERIAL:
            reason = "forced" if force_mock else "pyserial not installed"
            print(f"[serial_link] Using MOCK backend ({reason}).")
            self._backend = _MockBackend(verbose=verbose_mock)
            return

        try:
            self._backend = serial.Serial(port, baud, timeout=timeout)
            time.sleep(2.0)  # let an Arduino finish its auto-reset boot
            self._is_mock = False
            print(f"[serial_link] Connected to {port} @ {baud} baud.")
        except Exception as e:  # noqa: BLE001 — any pyserial failure -> mock
            print(f"[serial_link] Could not open {port} ({e}); falling back to MOCK backend.")
            self._backend = _MockBackend(verbose=verbose_mock)

    def is_mock(self) -> bool:
        return self._is_mock

    def send(self, steering_deg: float, speed_pwm: float, state_flag: str = "D") -> bool:
        """
        Returns True if a command was actually written this call (False
        only if throttled by min_send_interval). Never raises — a write
        failure demotes the link to MOCK for the rest of the run.
        """
        now = time.time()
        if self.min_send_interval and (now - self._last_send_t) < self.min_send_interval:
            return False

        message = f"S{steering_deg:.2f},{speed_pwm:.1f},{state_flag}\n"

        try:
            self._backend.write(message.encode("ascii"))
            self._last_send_t = now
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[serial_link] write failed ({e}); demoting to MOCK backend.")
            self._backend = _MockBackend()
            self._is_mock = True
            self._backend.write(message.encode("ascii"))
            self._last_send_t = now
            return True

    def read_events(self) -> list[str]:
        """
        UPLINK: non-blocking read of any lines the Arduino has sent back
        this tick (see vehicle_controller.ino's serviceStartButton() /
        serviceLineSensor()). Returns a list of stripped strings, e.g.
        ["BTN"] or ["LINE"] or [] most frames. Never blocks and never
        raises — a read failure is treated the same as "nothing arrived"
        so it can't take down the vision loop mid-round.

        Call this once per frame in main.py's loop, same as send().
        """
        events: list[str] = []
        if self._is_mock:
            return events  # MockBackend has no real device pushing events

        try:
            while self._backend.in_waiting > 0:
                line = self._backend.readline().decode("ascii", errors="ignore").strip()
                if line:
                    events.append(line)
        except Exception as e:  # noqa: BLE001
            print(f"[serial_link] read_events failed ({e}); ignoring this tick.")
        return events

    def close(self) -> None:
        try:
            self._backend.close()
        except Exception:  # noqa: BLE001 — best-effort cleanup only
            pass

