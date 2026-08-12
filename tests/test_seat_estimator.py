"""
tests/test_seat_estimator.py
WRO 2026 Future Engineers — pytest cases for world_model/seat_estimator.py.

H.28 FIX: converted from seat_estimator.py's in-module _run_tests() into
real pytest test_* functions. No functional change.
"""

import pytest

from world_model.obstacle import RED
from world_model.seat_estimator import (
    classify_column, classify_row, classify_seat, classify_detections,
    TOP_BOTTOM_SPLIT_CM, TL, TC, TR, BL, BC, BR,
)


def test_classify_column_thirds():
    assert classify_column(10, 300) == "LEFT"
    assert classify_column(150, 300) == "CENTER"
    assert classify_column(290, 300) == "RIGHT"


def test_classify_row_near_far_split():
    assert classify_row(80.0) == "TOP"
    assert classify_row(20.0) == "BOTTOM"
    assert classify_row(TOP_BOTTOM_SPLIT_CM) == "TOP"  # boundary is inclusive to TOP


def test_classify_seat_all_six_combinations():
    roi_w = 300
    cases = [
        (10, 80.0, TL), (150, 80.0, TC), (290, 80.0, TR),
        (10, 20.0, BL), (150, 20.0, BC), (290, 20.0, BR),
    ]
    for cx, dist, expected in cases:
        got = classify_seat(cx, dist, roi_w)
        assert got == expected, f"cx={cx} dist={dist} -> {got}, expected {expected}"


def test_classify_detections_batches_and_validates_color():
    roi_w = 300
    dets = [{"cx": 10, "distance": 80.0}, {"cx": 290, "distance": 20.0}]
    result = classify_detections(dets, RED, roi_w)
    assert result == [(TL, RED), (BR, RED)]

    with pytest.raises(ValueError):
        classify_detections(dets, 99, roi_w)
