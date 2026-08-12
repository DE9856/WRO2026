"""
tests/test_corridor.py
WRO 2026 Future Engineers — pytest cases for camera/corridor.py.

H.28 FIX: converted from corridor.py's in-module _run_tests() into real
pytest test_* functions. No functional change to the originally-covered
behaviour. Also covers the new ultrasonic_corridor_error() fallback
(punch-list item: wiring left/right HC-SR04 into corridor centering).
"""

import numpy as np
import cv2

from camera.corridor import (
    estimate_corridor, corridor_error, ultrasonic_corridor_error,
    ULTRASONIC_FALLBACK_CONFIDENCE,
)

W, H = 300, 200


def test_symmetric_corridor_centers_with_full_confidence():
    mask = np.zeros((H, W), dtype=np.uint8)
    cv2.rectangle(mask, (0, 0), (30, H), 255, -1)          # left wall
    cv2.rectangle(mask, (W - 30, 0), (W, H), 255, -1)      # right wall
    result = estimate_corridor(mask, W, H)
    assert abs(result["center_x"] - W / 2) < 2, result
    assert result["confidence"] == 1.0


def test_corridor_shifted_right_gives_positive_error():
    # left wall spans 0-150, right wall spans 250-300 -> midpoint (150+250)/2=200,
    # which is right of frame-center (150).
    mask2 = np.zeros((H, W), dtype=np.uint8)
    cv2.rectangle(mask2, (0, 0), (150, H), 255, -1)
    cv2.rectangle(mask2, (250, 0), (W, H), 255, -1)
    result2 = estimate_corridor(mask2, W, H)
    err = corridor_error(result2, W)
    assert err is not None and err > 0, err


def test_no_walls_visible_gives_none_not_a_crash():
    mask3 = np.zeros((H, W), dtype=np.uint8)
    result3 = estimate_corridor(mask3, W, H)
    assert result3["center_x"] is None
    assert corridor_error(result3, W) is None


def test_single_wall_visible_yields_lower_confidence_fallback():
    mask4 = np.zeros((H, W), dtype=np.uint8)
    cv2.rectangle(mask4, (0, 0), (30, H), 255, -1)  # left wall only
    result4 = estimate_corridor(mask4, W, H)
    assert result4["center_x"] is not None
    assert result4["confidence"] < 1.0


# ---------------------------------------------------------------------------
# ultrasonic_corridor_error() -- placeholder side-ultrasonic fallback.
# ---------------------------------------------------------------------------
def test_ultrasonic_fallback_none_when_neither_reading_usable():
    assert ultrasonic_corridor_error(None, None) is None
    assert ultrasonic_corridor_error(0.0, -1.0) is None, "0/negative sentinel readings are not usable"


def test_ultrasonic_fallback_closer_left_wall_steers_right():
    # Closer to the left wall (smaller left_cm) than the right -> corridor
    # center is to the vehicle's right -> positive error (steer right).
    result = ultrasonic_corridor_error(left_distance_cm=20.0, right_distance_cm=60.0)
    assert result is not None
    err_px, confidence = result
    assert err_px > 0, err_px
    assert confidence == ULTRASONIC_FALLBACK_CONFIDENCE


def test_ultrasonic_fallback_closer_right_wall_steers_left():
    result = ultrasonic_corridor_error(left_distance_cm=60.0, right_distance_cm=20.0)
    assert result is not None
    err_px, _ = result
    assert err_px < 0, err_px


def test_ultrasonic_fallback_balanced_readings_give_near_zero_error():
    result = ultrasonic_corridor_error(left_distance_cm=40.0, right_distance_cm=40.0)
    assert result is not None
    err_px, _ = result
    assert abs(err_px) < 1e-6, err_px


def test_ultrasonic_fallback_single_sensor_still_returns_a_reading():
    left_only = ultrasonic_corridor_error(left_distance_cm=20.0, right_distance_cm=None)
    assert left_only is not None
    right_only = ultrasonic_corridor_error(left_distance_cm=None, right_distance_cm=20.0)
    assert right_only is not None


def test_ultrasonic_fallback_confidence_always_capped_low():
    """Regardless of the reading, this fallback must never report a
    confidence at or above what a real vision reading would -- it is a
    placeholder, not a calibrated sensor fusion."""
    result = ultrasonic_corridor_error(left_distance_cm=1.0, right_distance_cm=99.0)
    assert result is not None
    _, confidence = result
    assert confidence < 0.5
