"""
tests/test_warp.py
WRO 2026 Future Engineers — pytest cases for camera/warp.py.

H.28 FIX: converted from warp.py's in-module _run_tests() into real
pytest test_* functions. No functional change.
"""

import numpy as np

import camera.warp as warp
from camera.warp import (
    warp_frame, warp_point, corridor_width_cm,
    WARP_SRC, WARP_DST, WARP_OUT_WIDTH, WARP_OUT_HEIGHT,
)


def test_warp_frame_outputs_configured_canvas_size():
    frame = np.zeros((300, 480, 3), dtype=np.uint8)
    warped = warp_frame(frame)
    assert warped.shape[:2] == (WARP_OUT_HEIGHT, WARP_OUT_WIDTH), warped.shape


def test_warp_point_maps_calibration_corners_to_destination():
    for src_pt, dst_pt in zip(WARP_SRC, WARP_DST):
        wx, wy = warp_point(float(src_pt[0]), float(src_pt[1]))
        assert abs(wx - dst_pt[0]) < 1.0, (wx, dst_pt[0])
        assert abs(wy - dst_pt[1]) < 1.0, (wy, dst_pt[1])


def test_corridor_width_cm_refuses_to_guess_before_calibration(monkeypatch):
    monkeypatch.setattr(warp, "PX_PER_MM", None)
    assert corridor_width_cm(200.0) is None, "must not fabricate a cm value before calibration"


def test_corridor_width_cm_converts_correctly_once_calibrated(monkeypatch):
    monkeypatch.setattr(warp, "PX_PER_MM", 2.0)  # e.g. 2 px per mm
    cm = warp.corridor_width_cm(400.0)  # 400px / 2 px-per-mm = 200mm = 20cm
    assert cm == 20.0, cm


def test_corridor_width_cm_none_is_safe_noop():
    assert corridor_width_cm(None) is None
