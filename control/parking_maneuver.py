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

HEADING CORRECTION (punch-list item C.13 fix): centering center_x alone
zeroes horizontal pixel error but has no way to know whether the
vehicle is actually PARALLEL to the wall — WRO §1.8.2's real
requirement, and §10's scoring table gives 0 of the 15 parking points
for "partly or not parallel" (rubric items 1.8.2/1.8.3). This is now a
second proportional term against heading_error_deg — the MPU-6050 yaw
delta since PARK_EXEC started (vehicle_controller.ino's serviceImu(),
wired through in main.py). Both terms are summed and clamped together,
so the controller simultaneously drives toward "centered" and "still
facing the way it started" rather than treating them as separate
passes. If heading_error_deg is never provided (no MPU-6050 wired /
detected, or --dry-run with no serial hardware), this degrades
gracefully to the original pixel-only behaviour — heading is an
additive refinement, not a hard dependency.
"""

from __future__ import annotations
from typing import Optional

PARK_CENTERED_PX_THRESHOLD = 12   # |error| below this counts as "centered"
PARK_HEADING_THRESHOLD_DEG = 6.0  # |heading error| below this counts as "parallel enough"
PARK_STABLE_FRAMES = 8            # consecutive centered+parallel frames required to finish
PARK_KP = 0.18                    # proportional gain, error(px) -> steering(deg)
PARK_KP_HEADING = 0.6             # proportional gain, heading error(deg) -> steering(deg)
PARK_MAX_STEER_DEG = 25.0
PARK_BASE_PWM = 20.0              # matches control/speed.py's PARK_PWM
PARK_MIN_PWM = 10.0

# H.29: valid values for `start_strategy` -- what to do the moment
# PARK_EXEC begins, before a parking lot has ever been seen this run.
# "creep"  (default, matches the original/only behaviour): ease forward
#          at PARK_MIN_PWM, steering straight, so the camera has a
#          chance to pick up the magenta markers as they scroll into
#          view. Matches how PARK_SEEK already approaches the lot.
# "hold"   : stay stopped (speed 0) and wait for a lot to appear before
#            moving at all. Safer default if PARK_EXEC can be entered
#            with the lot already just out of frame edge-on (e.g. a
#            tight approach angle) where creeping forward blind risks
#            a wall/marker touch before vision ever locks on.
START_STRATEGIES = ("creep", "hold")


class ParkingManeuver:
    def __init__(self, kp: float = PARK_KP, centered_threshold: float = PARK_CENTERED_PX_THRESHOLD,
                 stable_frames: int = PARK_STABLE_FRAMES,
                 kp_heading: float = PARK_KP_HEADING,
                 heading_threshold_deg: float = PARK_HEADING_THRESHOLD_DEG,
                 start_strategy: str = "creep"):
        if start_strategy not in START_STRATEGIES:
            raise ValueError(f"start_strategy must be one of {START_STRATEGIES}, got {start_strategy!r}")
        self.kp = kp
        self.centered_threshold = centered_threshold
        self.stable_frames = stable_frames
        self.kp_heading = kp_heading
        self.heading_threshold_deg = heading_threshold_deg
        self.start_strategy = start_strategy
        self._stable_count = 0
        self._last_error: Optional[float] = None

    def reset(self) -> None:
        self._stable_count = 0
        self._last_error = None

    def update(self, parking_lot: Optional[dict], roi_width: int,
               heading_error_deg: Optional[float] = None):
        """
        Call once per frame while planner.should_execute_parking() is True.

        heading_error_deg: current MPU-6050 yaw minus the yaw captured
            the instant PARK_EXEC began (main.py owns that reference
            capture — see its "PARKING EVENTS + MANEUVER EXECUTION"
            block). Positive = rotated clockwise since the manoeuvre
            started, matching the steer_deg "positive = right" sign
            convention. Pass None if no MPU-6050 reading is available
            (no IMU wired, or --dry-run/mock-serial) — the controller
            then falls back to pixel-only centering, same as before
            this feature existed.

        Returns (steering_deg, speed_pwm, centered: bool). "centered"
        requires BOTH the pixel error and (if heading data is available)
        the heading error to be within their thresholds for
        stable_frames consecutive frames — WRO §1.8.2 requires the
        vehicle to be centered in the lot AND parallel to the wall, not
        just one or the other. If parking_lot is None this frame
        (markers briefly lost), holds the last known pixel error rather
        than snapping steering to zero — a single dropped frame
        shouldn't jerk the wheel straight mid-manoeuvre. If no lot has
        EVER been seen, falls back to `start_strategy`: "creep" (default)
        eases forward straight at PARK_MIN_PWM so the camera gets a
        chance to find the markers; "hold" stays fully stopped instead.
        """
        if parking_lot is not None:
            error = parking_lot["center_x"] - (roi_width / 2.0)
            self._last_error = error
        elif self._last_error is not None:
            error = self._last_error
        else:
            no_lot_pwm = 0.0 if self.start_strategy == "hold" else PARK_MIN_PWM
            return 0.0, no_lot_pwm, False

        steering_deg = self.kp * error

        heading_ok = True
        if heading_error_deg is not None:
            steering_deg += self.kp_heading * heading_error_deg
            heading_ok = abs(heading_error_deg) <= self.heading_threshold_deg

        steering_deg = max(-PARK_MAX_STEER_DEG, min(PARK_MAX_STEER_DEG, steering_deg))

        abs_error = abs(error)
        position_ok = abs_error <= self.centered_threshold

        if position_ok and heading_ok:
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

