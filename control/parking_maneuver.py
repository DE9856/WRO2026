"""
parking_maneuver.py
WRO 2026 Future Engineers — closes the loop on PARK_SEEK/PARK_EXEC.

GAP #5 FIX: planner.py already had real PARK_SEEK/PARK_EXEC states, and
main.py already called planner.parking_lot_visible(parking_lot) every
frame — but nothing ever turned "two magenta markers visible" into an
actual steering/speed command. The robot would enter PARK_EXEC and just
keep whatever steering value it last had from pillar/corridor tracking,
never actually parking.

This is a closed-loop centering P-controller against
camera/parking.py::locate_parking_lot()'s center_x, run every frame
while planner.should_execute_parking() is True. It is not a full
multi-point parallel-parking trajectory planner (this vehicle
configuration has no rear sensor to support one — see WRO §11 vehicle
rules) — it IS a real, closed-loop steer-to-center-then-stop
controller: steer proportional to how far off-center the lot currently
is, taper speed down as the error shrinks, and declare the manoeuvre
complete only once the error has stayed under
PARK_CENTERED_PX_THRESHOLD for PARK_STABLE_FRAMES consecutive frames.
That debounce matters because WRO §9.24.7 penalizes touching the
parking lot limitations — overshooting to finish one frame early is a
worse trade than taking an extra half-second to confirm centering.
"""

from __future__ import annotations
from typing import Optional

PARK_CENTERED_PX_THRESHOLD = 12   # |error| below this counts as "centered"
PARK_STABLE_FRAMES = 8            # consecutive centered frames required to finish
PARK_KP = 0.18                    # proportional gain, error(px) -> steering(deg)
PARK_MAX_STEER_DEG = 25.0
PARK_BASE_PWM = 20.0              # matches control/speed.py's PARK_PWM
PARK_MIN_PWM = 10.0


class ParkingManeuver:
    def __init__(self, kp: float = PARK_KP, centered_threshold: float = PARK_CENTERED_PX_THRESHOLD,
                 stable_frames: int = PARK_STABLE_FRAMES):
        self.kp = kp
        self.centered_threshold = centered_threshold
        self.stable_frames = stable_frames
        self._stable_count = 0
        self._last_error: Optional[float] = None

    def reset(self) -> None:
        self._stable_count = 0
        self._last_error = None

    def update(self, parking_lot: Optional[dict], roi_width: int):
        """
        Call once per frame while planner.should_execute_parking() is True.

        Returns (steering_deg, speed_pwm, centered: bool). If parking_lot
        is None this frame (markers briefly lost), holds the last known
        error rather than snapping steering to zero — a single dropped
        frame shouldn't jerk the wheel straight mid-manoeuvre. If no lot
        has EVER been seen, returns a safe "creep forward straight"
        default instead.
        """
        if parking_lot is not None:
            error = parking_lot["center_x"] - (roi_width / 2.0)
            self._last_error = error
        elif self._last_error is not None:
            error = self._last_error
        else:
            return 0.0, PARK_MIN_PWM, False

        steering_deg = max(-PARK_MAX_STEER_DEG, min(PARK_MAX_STEER_DEG, self.kp * error))

        abs_error = abs(error)
        if abs_error <= self.centered_threshold:
            self._stable_count += 1
        else:
            self._stable_count = 0

        centered = self._stable_count >= self.stable_frames

        # Taper speed down as the error shrinks — gentle final approach.
        taper = min(1.0, abs_error / (self.centered_threshold * 4))
        speed_pwm = PARK_MIN_PWM + taper * (PARK_BASE_PWM - PARK_MIN_PWM)

        if centered:
            speed_pwm = 0.0

        return steering_deg, speed_pwm, centered


# ---------------------------------------------------------------------------
# Self-test — synthetic parking_lot dicts, no camera needed.
# ---------------------------------------------------------------------------
def _run_tests():
    print("Running parking_maneuver.py tests...")

    roi_w = 300

    # --- Test 1: lot far off-center -> nonzero steering, not yet centered.
    m = ParkingManeuver(stable_frames=3)
    lot = {"left": {}, "right": {}, "center_x": 100, "width_px": 40}
    steer, speed, centered = m.update(lot, roi_w)
    assert steer < 0, "lot left of center should steer left (negative)"
    assert not centered
    assert speed > 0
    print("  [PASS] off-center lot produces proportional steering, not yet centered")

    # --- Test 2: dead-centered lot for enough consecutive frames -> centered & stopped.
    m2 = ParkingManeuver(stable_frames=3, centered_threshold=12)
    centered_lot = {"left": {}, "right": {}, "center_x": 150, "width_px": 40}  # roi_w/2 == 150
    results = [m2.update(centered_lot, roi_w) for _ in range(3)]
    assert results[-1][2] is True, "3 consecutive centered frames should finish the manoeuvre"
    assert results[-1][1] == 0.0, "speed should be zero once centered"
    print("  [PASS] sustained centering finishes the manoeuvre and stops")

    # --- Test 3: a single dropped frame (None) holds the last error instead of snapping to 0.
    m3 = ParkingManeuver()
    m3.update({"left": {}, "right": {}, "center_x": 100, "width_px": 40}, roi_w)
    error_before = m3._last_error
    steer_dropped, _, _ = m3.update(None, roi_w)
    assert m3._last_error == error_before, "dropped frame must hold last known error"
    assert steer_dropped != 0.0
    print("  [PASS] a dropped frame holds the last known error instead of snapping straight")

    # --- Test 4: interrupted centering resets the stability counter.
    m4 = ParkingManeuver(stable_frames=3, centered_threshold=12)
    m4.update(centered_lot, roi_w)
    m4.update(centered_lot, roi_w)
    off = {"left": {}, "right": {}, "center_x": 250, "width_px": 40}
    m4.update(off, roi_w)  # interrupts the streak
    assert m4._stable_count == 0
    print("  [PASS] an off-center frame resets the stability streak")

    # --- Test 5: no lot ever seen -> safe creep-forward default, never crashes.
    m5 = ParkingManeuver()
    steer5, speed5, centered5 = m5.update(None, roi_w)
    assert steer5 == 0.0 and not centered5 and speed5 > 0
    print("  [PASS] no lot ever seen -> safe straight creep-forward default")

    # --- Test 6: reset() clears stability/error memory.
    m6 = ParkingManeuver(stable_frames=2, centered_threshold=12)
    m6.update(centered_lot, roi_w)
    m6.update(centered_lot, roi_w)
    m6.reset()
    assert m6._stable_count == 0 and m6._last_error is None
    print("  [PASS] reset() clears stability/error memory")

    print("All parking_maneuver.py tests passed.")


if __name__ == "__main__":
    _run_tests()
