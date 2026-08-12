"""
tests/test_track.py
WRO 2026 Future Engineers — pytest cases for world_model/track.py.

H.28 FIX: converted from track.py's in-module _run_tests() into real
pytest test_* functions. No functional change.
"""

from world_model.track import Track


def test_set_width_smooths_over_rolling_window():
    t = Track(smoothing_window=3)
    assert t.corridor_width_px is None
    t.set_width(100.0)
    t.set_width(110.0)
    t.set_width(90.0)
    assert abs(t.corridor_width_px - 100.0) < 1e-6, t.corridor_width_px


def test_rolling_window_evicts_oldest_sample():
    t = Track(smoothing_window=3)
    t.set_width(100.0)
    t.set_width(110.0)
    t.set_width(90.0)
    t.set_width(200.0)  # window slides -- oldest (100) drops out
    assert abs(t.corridor_width_px - (110 + 90 + 200) / 3) < 1e-6


def test_is_narrow_section_thresholds():
    t2 = Track()
    assert not t2.is_narrow_section(500)
    t2.set_width(400.0)
    assert t2.is_narrow_section(500)
    assert not t2.is_narrow_section(300)


def test_per_section_history_is_recorded():
    t3 = Track()
    t3.set_width(150.0, section=2)
    assert t3.sections[2] == 150.0


def test_set_width_none_is_safe_noop():
    t3 = Track()
    t3.set_width(150.0, section=2)
    t3.set_width(None)  # must be a safe no-op, not a crash
    assert t3.corridor_width_px == 150.0


def test_reset_clears_rolling_window_and_smoothed_value():
    t4 = Track()
    t4.set_width(120.0)
    t4.reset()
    assert t4.corridor_width_px is None
