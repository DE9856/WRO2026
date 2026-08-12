"""
tests/test_camera_math.py
WRO 2026 Future Engineers — unit tests for the pure-function/numpy camera
math modules: contours.py, angle.py, distance.py, tracker.py, parking.py,
lines.py.

GAP #6 FIX: none of these had any test coverage before, despite every
one of them being either a pure function or a function that only takes
numpy arrays as input. Every test here builds a synthetic mask/frame in
memory (cv2.rectangle onto a zeros array) — no camera, no real footage,
no hardware needed to catch a regression before it hits real footage.

Run from the repo root:
    python3 -m tests.test_camera_math
"""

import numpy as np
import cv2

from camera.angle import estimate_angle, compute_error, FRAME_WIDTH, CLEARANCE_PX
from camera.distance import estimate_distance, FOCAL_LENGTH, REAL_PILLAR_WIDTH_MM
from camera.contours import detect_objects
from camera.tracker import CentroidTracker
from camera.parking import find_markers, locate_parking_lot
from camera.lines import detect_corner_line, _largest_blob


def _blank_mask(w=480, h=300):
    return np.zeros((h, w), dtype=np.uint8)


def _draw_block(mask, x, y, w, h):
    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    return mask


# ---------------------------------------------------------------------------
# angle.py
# ---------------------------------------------------------------------------
def test_estimate_angle_center_is_zero():
    assert estimate_angle(FRAME_WIDTH / 2) == 0.0
    print("  [PASS] estimate_angle: dead-center cx gives 0 degrees")


def test_estimate_angle_sign_and_symmetry():
    left = estimate_angle(0)
    right = estimate_angle(FRAME_WIDTH)
    assert left < 0 < right, (left, right)
    assert abs(left) == abs(right), "should be symmetric about center"
    print("  [PASS] estimate_angle: symmetric, correct sign left/right of center")


def test_compute_error_red_targets_left_of_pillar():
    # RED: robot should pass on the pillar's right -> target is LEFT of pillar cx.
    pillar_cx = 300
    err = compute_error(pillar_cx, "RED")
    center = FRAME_WIDTH / 2
    expected = (pillar_cx - CLEARANCE_PX) - center
    assert err == expected, (err, expected)
    print("  [PASS] compute_error: RED clearance target sits left of the pillar")


def test_compute_error_green_targets_right_of_pillar():
    pillar_cx = 300
    err = compute_error(pillar_cx, "GREEN")
    center = FRAME_WIDTH / 2
    expected = (pillar_cx + CLEARANCE_PX) - center
    assert err == expected, (err, expected)
    print("  [PASS] compute_error: GREEN clearance target sits right of the pillar")


# ---------------------------------------------------------------------------
# distance.py
# ---------------------------------------------------------------------------
def test_estimate_distance_matches_similar_triangles_formula():
    pixel_width = 100
    expected_cm = (REAL_PILLAR_WIDTH_MM * FOCAL_LENGTH / pixel_width) / 10.0
    assert estimate_distance(pixel_width) == round(expected_cm, 2)
    print("  [PASS] estimate_distance: matches the similar-triangles formula directly")


def test_estimate_distance_closer_pillar_is_wider_in_pixels():
    far = estimate_distance(50)
    near = estimate_distance(150)
    assert near < far, "a wider pixel measurement must mean the pillar is closer"
    print("  [PASS] estimate_distance: wider pixel width -> shorter distance")


def test_estimate_distance_zero_width_is_infinite():
    assert estimate_distance(0) == float("inf")
    print("  [PASS] estimate_distance: zero pixel width -> inf (no div-by-zero crash)")


# ---------------------------------------------------------------------------
# contours.py
# ---------------------------------------------------------------------------
def test_detect_objects_finds_a_tall_blob():
    mask = _blank_mask()
    frame = np.zeros((300, 480, 3), dtype=np.uint8)
    _draw_block(mask, x=100, y=50, w=30, h=90)  # tall, aspect < 2.5 -> real pillar
    dets = detect_objects(mask, frame, "RED", (0, 0, 255))
    assert len(dets) == 1, dets
    d = dets[0]
    assert d["cx"] == 100 + 30 // 2
    assert d["cy"] == 50 + 90 // 2
    assert d["distance"] > 0
    print("  [PASS] detect_objects: finds a single tall blob with correct centroid")


def test_detect_objects_rejects_wide_blobs():
    mask = _blank_mask()
    frame = np.zeros((300, 480, 3), dtype=np.uint8)
    _draw_block(mask, x=100, y=50, w=120, h=20)  # aspect >> 2.5 -> floor reflection, rejected
    dets = detect_objects(mask, frame, "RED", (0, 0, 255))
    assert dets == [], dets
    print("  [PASS] detect_objects: rejects wide/flat blobs via the aspect-ratio filter")


def test_detect_objects_rejects_tiny_noise():
    mask = _blank_mask()
    frame = np.zeros((300, 480, 3), dtype=np.uint8)
    _draw_block(mask, x=100, y=50, w=5, h=8)  # area well under the 500px threshold
    dets = detect_objects(mask, frame, "RED", (0, 0, 255))
    assert dets == [], dets
    print("  [PASS] detect_objects: rejects tiny-area noise")


def test_detect_objects_finds_multiple_blobs():
    mask = _blank_mask()
    frame = np.zeros((300, 480, 3), dtype=np.uint8)
    _draw_block(mask, x=50, y=50, w=30, h=90)
    _draw_block(mask, x=350, y=50, w=30, h=90)
    dets = detect_objects(mask, frame, "GREEN", (0, 255, 0))
    assert len(dets) == 2, dets
    print("  [PASS] detect_objects: finds multiple separate blobs in one frame")


# ---------------------------------------------------------------------------
# tracker.py
# ---------------------------------------------------------------------------
def test_tracker_picks_largest_on_first_frame():
    t = CentroidTracker()
    small = {"cx": 10, "cy": 10, "area": 500}
    big = {"cx": 200, "cy": 200, "area": 5000}
    result = t.track([small, big])
    assert result is big
    print("  [PASS] CentroidTracker: first frame picks the largest-area detection")


def test_tracker_follows_nearest_centroid_across_frames():
    t = CentroidTracker()
    t.track([{"cx": 100, "cy": 100, "area": 1000}])  # establishes previous_center
    near = {"cx": 105, "cy": 102, "area": 300}   # small but close to previous
    far = {"cx": 400, "cy": 400, "area": 9000}   # huge but far away
    result = t.track([near, far])
    assert result is near, "should follow the nearest centroid, not the largest area"
    print("  [PASS] CentroidTracker: follows nearest centroid across frames, not largest area")


def test_tracker_returns_none_on_empty_detections():
    t = CentroidTracker()
    assert t.track([]) is None
    t.track([{"cx": 1, "cy": 1, "area": 100}])
    assert t.track([]) is None, "an empty frame should return None without crashing"
    print("  [PASS] CentroidTracker: returns None on empty detections, doesn't crash")


# ---------------------------------------------------------------------------
# parking.py
# ---------------------------------------------------------------------------
def test_find_markers_sorted_by_area_descending():
    mask = _blank_mask()
    _draw_block(mask, x=10, y=10, w=10, h=10)    # area 100 -> below MIN_MARKER_AREA(200), excluded
    _draw_block(mask, x=100, y=10, w=20, h=20)   # area 400
    _draw_block(mask, x=300, y=10, w=30, h=30)   # area 900
    markers = find_markers(mask)
    assert len(markers) == 2, markers
    assert markers[0]["area"] >= markers[1]["area"]
    print("  [PASS] find_markers: filters sub-threshold blobs, sorts largest first")


def test_locate_parking_lot_needs_two_markers():
    mask = _blank_mask()
    _draw_block(mask, x=100, y=10, w=20, h=20)
    assert locate_parking_lot(mask) is None, "a single marker must not produce a lot"
    print("  [PASS] locate_parking_lot: returns None with fewer than 2 markers")


def test_locate_parking_lot_orders_left_right_and_midpoint():
    mask = _blank_mask()
    _draw_block(mask, x=300, y=10, w=20, h=20)  # cx = 310, drawn RIGHT first
    _draw_block(mask, x=50, y=10, w=20, h=20)   # cx = 60,  drawn LEFT second
    lot = locate_parking_lot(mask)
    assert lot is not None
    assert lot["left"]["cx"] < lot["right"]["cx"]
    assert lot["center_x"] == (lot["left"]["cx"] + lot["right"]["cx"]) // 2
    assert lot["width_px"] == lot["right"]["cx"] - lot["left"]["cx"]
    print("  [PASS] locate_parking_lot: correctly orders left/right regardless of draw order")


# ---------------------------------------------------------------------------
# lines.py
# ---------------------------------------------------------------------------
def test_largest_blob_ignores_small_noise():
    mask = _blank_mask()
    _draw_block(mask, x=10, y=10, w=5, h=5)     # area 25 -> below MIN_LINE_AREA(300)
    assert _largest_blob(mask) is None
    print("  [PASS] _largest_blob: ignores sub-threshold noise")


def test_detect_corner_line_reports_none_when_nothing_visible():
    orange = _blank_mask()
    blue = _blank_mask()
    result = detect_corner_line(orange, blue, roi_width=480)
    assert result == {"color": None, "side": None, "phase": None, "blob": None}
    print("  [PASS] detect_corner_line: reports all-None when neither colour is visible")


def test_detect_corner_line_orange_means_exiting():
    orange = _blank_mask()
    _draw_block(orange, x=350, y=50, w=40, h=200)  # right side of frame
    blue = _blank_mask()
    result = detect_corner_line(orange, blue, roi_width=480)
    assert result["color"] == "ORANGE"
    assert result["phase"] == "EXITING"
    assert result["side"] == "RIGHT"
    print("  [PASS] detect_corner_line: ORANGE -> EXITING phase, correct side-of-frame")


def test_detect_corner_line_blue_means_entering():
    orange = _blank_mask()
    blue = _blank_mask()
    _draw_block(blue, x=20, y=50, w=40, h=200)  # left side of frame
    result = detect_corner_line(orange, blue, roi_width=480)
    assert result["color"] == "BLUE"
    assert result["phase"] == "ENTERING"
    assert result["side"] == "LEFT"
    print("  [PASS] detect_corner_line: BLUE -> ENTERING phase, correct side-of-frame")


def test_detect_corner_line_prefers_larger_blob_when_both_visible():
    orange = _blank_mask()
    _draw_block(orange, x=20, y=50, w=10, h=10)    # small
    blue = _blank_mask()
    _draw_block(blue, x=200, y=50, w=100, h=200)   # much larger
    result = detect_corner_line(orange, blue, roi_width=480)
    assert result["color"] == "BLUE", "should trust the larger (closer/more certain) blob"
    print("  [PASS] detect_corner_line: when both colours visible, trusts the larger blob")


def run_all():
    print("Running tests/test_camera_math.py...")
    test_estimate_angle_center_is_zero()
    test_estimate_angle_sign_and_symmetry()
    test_compute_error_red_targets_left_of_pillar()
    test_compute_error_green_targets_right_of_pillar()
    test_estimate_distance_matches_similar_triangles_formula()
    test_estimate_distance_closer_pillar_is_wider_in_pixels()
    test_estimate_distance_zero_width_is_infinite()
    test_detect_objects_finds_a_tall_blob()
    test_detect_objects_rejects_wide_blobs()
    test_detect_objects_rejects_tiny_noise()
    test_detect_objects_finds_multiple_blobs()
    test_tracker_picks_largest_on_first_frame()
    test_tracker_follows_nearest_centroid_across_frames()
    test_tracker_returns_none_on_empty_detections()
    test_find_markers_sorted_by_area_descending()
    test_locate_parking_lot_needs_two_markers()
    test_locate_parking_lot_orders_left_right_and_midpoint()
    test_largest_blob_ignores_small_noise()
    test_detect_corner_line_reports_none_when_nothing_visible()
    test_detect_corner_line_orange_means_exiting()
    test_detect_corner_line_blue_means_entering()
    test_detect_corner_line_prefers_larger_blob_when_both_visible()
    print("All tests/test_camera_math.py tests passed.")


if __name__ == "__main__":
    run_all()
