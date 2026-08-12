"""
tests/test_parking_maneuver.py
WRO 2026 Future Engineers — pytest cases for control/parking_maneuver.py.

H.28 FIX: converted from parking_maneuver.py's in-module _run_tests()
into real pytest test_* functions. No functional change to the
originally-covered behaviour. Also covers H.29's `start_strategy` flag.
"""

import pytest

from control.parking_maneuver import ParkingManeuver

ROI_W = 300
CENTERED_LOT = {"left": {}, "right": {}, "center_x": 150, "width_px": 40}  # roi_w/2 == 150


def test_off_center_lot_gives_proportional_steering_not_centered():
    m = ParkingManeuver(stable_frames=3)
    lot = {"left": {}, "right": {}, "center_x": 100, "width_px": 40}
    steer, speed, centered = m.update(lot, ROI_W)
    assert steer < 0, "lot left of center should steer left (negative)"
    assert not centered
    assert speed > 0


def test_sustained_centering_finishes_and_stops():
    m2 = ParkingManeuver(stable_frames=3, centered_threshold=12)
    results = [m2.update(CENTERED_LOT, ROI_W) for _ in range(3)]
    assert results[-1][2] is True, "3 consecutive centered frames should finish the manoeuvre"
    assert results[-1][1] == 0.0, "speed should be zero once centered"


def test_dropped_frame_holds_last_error():
    m3 = ParkingManeuver()
    m3.update({"left": {}, "right": {}, "center_x": 100, "width_px": 40}, ROI_W)
    error_before = m3._last_error
    steer_dropped, _, _ = m3.update(None, ROI_W)
    assert m3._last_error == error_before, "dropped frame must hold last known error"
    assert steer_dropped != 0.0


def test_interrupted_centering_resets_stability_counter():
    m4 = ParkingManeuver(stable_frames=3, centered_threshold=12)
    m4.update(CENTERED_LOT, ROI_W)
    m4.update(CENTERED_LOT, ROI_W)
    off = {"left": {}, "right": {}, "center_x": 250, "width_px": 40}
    m4.update(off, ROI_W)  # interrupts the streak
    assert m4._stable_count == 0


def test_no_lot_ever_seen_defaults_to_safe_creep():
    m5 = ParkingManeuver()  # default start_strategy="creep"
    steer5, speed5, centered5 = m5.update(None, ROI_W)
    assert steer5 == 0.0 and not centered5 and speed5 > 0


def test_reset_clears_stability_and_error_memory():
    m6 = ParkingManeuver(stable_frames=2, centered_threshold=12)
    m6.update(CENTERED_LOT, ROI_W)
    m6.update(CENTERED_LOT, ROI_W)
    m6.reset()
    assert m6._stable_count == 0 and m6._last_error is None


def test_heading_error_none_matches_original_pixel_only_behaviour():
    m7 = ParkingManeuver(stable_frames=3, centered_threshold=12)
    lot_left = {"left": {}, "right": {}, "center_x": 100, "width_px": 40}
    steer_no_heading, _, _ = m7.update(lot_left, ROI_W, heading_error_deg=None)
    m7b = ParkingManeuver(stable_frames=3, centered_threshold=12)
    steer_baseline, _, _ = m7b.update(lot_left, ROI_W)
    assert steer_no_heading == steer_baseline


def test_pixel_centered_but_not_parallel_withholds_centered():
    """WRO Section1.8.2 needs both pixel-centered AND parallel."""
    m8 = ParkingManeuver(stable_frames=2, centered_threshold=12, heading_threshold_deg=6.0)
    steer8, _, centered8 = m8.update(CENTERED_LOT, ROI_W, heading_error_deg=20.0)
    assert steer8 > 0, "positive heading error (rotated clockwise) should steer right to correct"
    assert centered8 is False, "pixel-centered but far from parallel must not count as centered"


def test_centered_and_parallel_finishes():
    m9 = ParkingManeuver(stable_frames=2, centered_threshold=12, heading_threshold_deg=6.0)
    m9.update(CENTERED_LOT, ROI_W, heading_error_deg=2.0)
    _, speed9, centered9 = m9.update(CENTERED_LOT, ROI_W, heading_error_deg=1.0)
    assert centered9 is True
    assert speed9 == 0.0


def test_heading_only_excursion_resets_stability_streak():
    m10 = ParkingManeuver(stable_frames=3, centered_threshold=12, heading_threshold_deg=6.0)
    m10.update(CENTERED_LOT, ROI_W, heading_error_deg=1.0)
    m10.update(CENTERED_LOT, ROI_W, heading_error_deg=1.0)
    m10.update(CENTERED_LOT, ROI_W, heading_error_deg=15.0)  # heading drifts -- interrupts streak
    assert m10._stable_count == 0


# ---------------------------------------------------------------------------
# H.29: `start_strategy` CLI-facing flag.
# ---------------------------------------------------------------------------
def test_start_strategy_hold_stays_stopped_until_lot_seen():
    m = ParkingManeuver(start_strategy="hold")
    steer, speed, centered = m.update(None, ROI_W)
    assert steer == 0.0 and speed == 0.0 and not centered


def test_start_strategy_creep_is_the_default():
    m = ParkingManeuver()
    assert m.start_strategy == "creep"


def test_start_strategy_rejects_unknown_value():
    with pytest.raises(ValueError):
        ParkingManeuver(start_strategy="reverse")
