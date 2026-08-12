"""
tests/test_speed.py
WRO 2026 Future Engineers — pytest cases for control/speed.py.

H.28 FIX: converted from speed.py's in-module _run_tests() into real
pytest test_* functions. No functional change.
"""

from control.speed import SpeedController, CRUISE_PWM, CORNER_PWM, PARK_PWM, MIN_PWM


def test_straight_full_confidence_speed_run_gives_cruise_pwm():
    sc = SpeedController()
    pwm = sc.compute(steering_angle_deg=0, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.0)
    assert abs(pwm - CRUISE_PWM) < 1e-6, pwm


def test_sharp_corner_drops_to_corner_pwm_tier():
    sc = SpeedController()
    pwm = sc.compute(steering_angle_deg=25, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.0)
    assert abs(pwm - CORNER_PWM) < 1e-6, pwm


def test_low_confidence_throttles_speed_but_not_below_floor():
    sc = SpeedController()
    full_conf = sc.compute(steering_angle_deg=0, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.0)
    low_conf = sc.compute(steering_angle_deg=0, confidence=0.0, lap_phase="SPEED_RUN", smoothing=0.0)
    assert low_conf < full_conf, (low_conf, full_conf)
    assert low_conf >= MIN_PWM, "must never drop below the stall floor"


def test_lap_phase_multiplier_scales_speed():
    """MAP_BUILD is more cautious than SPEED_RUN at identical angle/confidence."""
    sc1 = SpeedController()
    map_build = sc1.compute(steering_angle_deg=0, confidence=1.0, lap_phase="MAP_BUILD", smoothing=0.0)
    sc2 = SpeedController()
    speed_run = sc2.compute(steering_angle_deg=0, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.0)
    assert map_build < speed_run, (map_build, speed_run)


def test_parking_overrides_schedule_with_flat_park_pwm():
    sc = SpeedController()
    pwm = sc.compute(steering_angle_deg=25, confidence=1.0, lap_phase="SPEED_RUN",
                      parking=True, smoothing=0.0)
    assert abs(pwm - PARK_PWM) < 1e-6, pwm


def test_smoothing_dampens_sudden_target_change():
    sc = SpeedController()
    for _ in range(20):  # let the smoothed output converge near CRUISE_PWM first
        sc.compute(steering_angle_deg=0, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.5)
    assert abs(sc._last_pwm - CRUISE_PWM) < 0.5, sc._last_pwm

    jump = sc.compute(steering_angle_deg=30, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.5)
    assert CORNER_PWM < jump < CRUISE_PWM, jump


def test_reset_clears_smoothing_memory():
    sc = SpeedController()
    sc.compute(steering_angle_deg=0, confidence=1.0, lap_phase="SPEED_RUN", smoothing=0.9)
    sc.reset()
    assert sc._last_pwm == 0.0
