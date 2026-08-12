"""
tests/test_proximity.py
WRO 2026 Future Engineers — pytest cases for control/proximity.py.

H.28 FIX: converted from proximity.py's in-module _run_tests() into
real pytest test_* functions. No functional change.
"""

from control.proximity import ParkingCollisionGuard

ROI_W = 300
FAR_LOT = {"left": {"w": 20}, "right": {"w": 20}}
HUGE_LOT = {"left": {"w": 20}, "right": {"w": 130}}  # right marker fills >35% of ROI


def test_comfortable_range_and_small_markers_never_trips():
    g = ParkingCollisionGuard()
    touched = False
    for _ in range(10):
        touched = g.update(forward_distance_cm=25.0, parking_lot=FAR_LOT, roi_width=ROI_W)
    assert touched is False
    assert g.touched() is False


def test_sustained_close_range_trips_and_latches():
    g2 = ParkingCollisionGuard(frames_to_trip=2)
    assert g2.update(forward_distance_cm=3.0, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g2.update(forward_distance_cm=2.5, parking_lot=FAR_LOT, roi_width=ROI_W) is True
    assert g2.touched() is True
    # Range "recovering" afterwards must NOT un-latch it.
    assert g2.update(forward_distance_cm=30.0, parking_lot=FAR_LOT, roi_width=ROI_W) is True


def test_single_noisy_reading_is_debounced_away():
    g3 = ParkingCollisionGuard(frames_to_trip=2)
    assert g3.update(forward_distance_cm=1.0, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g3.update(forward_distance_cm=25.0, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g3.touched() is False, "a single-frame blip must not trip the debounce"


def test_marker_filling_roi_trips_even_with_clear_forward_range():
    g4 = ParkingCollisionGuard(frames_to_trip=2)
    assert g4.update(forward_distance_cm=40.0, parking_lot=HUGE_LOT, roi_width=ROI_W) is False
    assert g4.update(forward_distance_cm=40.0, parking_lot=HUGE_LOT, roi_width=ROI_W) is True


def test_missing_forward_distance_degrades_to_camera_only_cue():
    g5 = ParkingCollisionGuard(frames_to_trip=2)
    assert g5.update(forward_distance_cm=None, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g5.update(forward_distance_cm=None, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g5.touched() is False


def test_zero_or_negative_sentinel_readings_are_ignored():
    """A timed-out ping reported as 0 (or a negative sentinel) must not
    be read as "0 cm away = definitely touching."."""
    g6 = ParkingCollisionGuard(frames_to_trip=2)
    assert g6.update(forward_distance_cm=0.0, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g6.update(forward_distance_cm=-1.0, parking_lot=FAR_LOT, roi_width=ROI_W) is False
    assert g6.touched() is False, "a 0/negative sentinel reading must not be treated as contact"


def test_reset_clears_debounce_counter_and_latch():
    g7 = ParkingCollisionGuard(frames_to_trip=2)
    g7.update(forward_distance_cm=2.0, parking_lot=FAR_LOT, roi_width=ROI_W)
    g7.update(forward_distance_cm=2.0, parking_lot=FAR_LOT, roi_width=ROI_W)
    assert g7.touched() is True
    g7.reset()
    assert g7.touched() is False
    assert g7.update(forward_distance_cm=25.0, parking_lot=FAR_LOT, roi_width=ROI_W) is False
