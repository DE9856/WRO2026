"""
speed.py
WRO 2026 Future Engineers — throttle/speed scheduling.

GAP #2 FIX: world_model/vehicle_state.py::VehicleState.speed existed but
nothing ever wrote to it — main.py's pipeline computed steering only,
never speed. This module is the missing "how fast" half of the control
loop: Cruise / Corner / Parking PWM tiers, tapered by how sharp the
current steering angle is and how much we trust the current steering
source (corridor confidence, or pillar-tracking confidence), and scaled
by the planner's lap-phase strategy (planner.lap_phase(): MAP_BUILD ->
VALIDATE -> SPEED_RUN — Build Guide §06A/§07).

Output is a PWM-style magnitude in [0, 100] for forward driving
(control/serial_link.py packages it for the motor controller — sign/
direction for reverse manoeuvres is handled by whoever calls send(),
e.g. control/parking_maneuver.py). Nothing here talks to hardware
directly, so it's fully unit-testable without a robot.

NOTE ON THE DRIVE MOTOR: the wire protocol and this module's 0-100
output are unchanged by the DC-motor -> stepper (STH-39D219) swap.
firmware/vehicle_controller.ino now maps this same value onto a
step-pulse frequency instead of an H-bridge PWM duty cycle -- see
that file's writeDriveMotor(). Nothing here needs to change.
"""

from __future__ import annotations

# Tier ceilings, in PWM percent (0-100). Retune on-track — these are
# deliberately conservative starting points, not tuned-in values.
CRUISE_PWM = 55   # straight-line, high confidence, flat corridor/pillar read
CORNER_PWM = 35   # sharper steering angle in effect -> slow proportionally
PARK_PWM = 20     # PARK_SEEK / PARK_EXEC — precision over speed
MIN_PWM = 15      # floor so the vehicle doesn't stall out at tight steering

# Steering-angle threshold (degrees, matches camera/angle.py's units)
# beyond which we're clearly "in a corner" rather than "on the straight".
CORNER_ANGLE_DEG = 12.0

# Lap-phase multiplier — Build Guide §06A/§07: lap 1 maps cautiously,
# lap 2 validates, lap 3+ can push harder now the map is trusted.
LAP_PHASE_MULTIPLIER = {
    "MAP_BUILD": 0.75,
    "VALIDATE": 0.9,
    "SPEED_RUN": 1.0,
}


class SpeedController:
    """
    Call compute() once per frame with the current steering angle, a
    0..1 confidence score for whichever steering source is active
    (camera/corridor.py's "confidence" field, or a pillar-tracking
    confidence), the planner's lap_phase() string, and whether the
    planner is in a parking state. Returns the PWM value to hand to
    control/serial_link.py.
    """

    def __init__(self, cruise_pwm: float = CRUISE_PWM, corner_pwm: float = CORNER_PWM,
                 park_pwm: float = PARK_PWM, min_pwm: float = MIN_PWM,
                 corner_angle_deg: float = CORNER_ANGLE_DEG):
        self.cruise_pwm = cruise_pwm
        self.corner_pwm = corner_pwm
        self.park_pwm = park_pwm
        self.min_pwm = min_pwm
        self.corner_angle_deg = corner_angle_deg
        self._last_pwm = 0.0

    def compute(self, *, steering_angle_deg: float, confidence: float = 1.0,
                lap_phase: str = "MAP_BUILD", parking: bool = False,
                smoothing: float = 0.3) -> float:
        """
        steering_angle_deg: magnitude of the current steering command
            (deg); sign is irrelevant here, only how sharp the turn is.
        confidence: 0..1 — trust in the current steering source. Low
            confidence throttles speed down regardless of angle, since a
            fast wrong turn is worse than a slow wrong turn.
        lap_phase: planner.lap_phase() string.
        parking: True while planner.should_seek_parking() or
            planner.should_execute_parking() — overrides the normal
            angle-based schedule with the flat PARK_PWM tier.
        smoothing: exponential smoothing factor against the previous
            output (0 = instant, 0.95 = nearly frozen) so PWM doesn't
            step-jump frame to frame.
        """
        if parking:
            target = self.park_pwm
        else:
            angle_mag = abs(steering_angle_deg)
            if angle_mag >= self.corner_angle_deg:
                base = self.corner_pwm
            else:
                # Linear taper from cruise down to corner as angle rises.
                span = max(self.corner_angle_deg, 1e-6)
                t = min(1.0, angle_mag / span)
                base = self.cruise_pwm - t * (self.cruise_pwm - self.corner_pwm)

            confidence = max(0.0, min(1.0, confidence))
            base *= (0.5 + 0.5 * confidence)   # floors at 50% rather than killing throttle

            phase_mult = LAP_PHASE_MULTIPLIER.get(lap_phase, 1.0)
            target = base * phase_mult

        target = max(self.min_pwm, min(100.0, target))

        smoothing = max(0.0, min(0.95, smoothing))
        pwm = smoothing * self._last_pwm + (1 - smoothing) * target
        self._last_pwm = pwm
        return round(pwm, 1)

    def reset(self) -> None:
        self._last_pwm = 0.0

