"""
seat_estimator.py
WRO 2026 Future Engineers — camera detection -> seat-index classifier.

This is the missing link between camera/contours.py (which reports raw
pixel boxes: cx, cy, distance_cm, ...) and world_model.obstacle's seat
vector format (a 6-element [TL, TC, TR, BL, BC, BR] list — see the big
docstring at the top of world_model/obstacle.py for the index convention).

WHAT THIS DOES
    Turns one detection dict (from camera/contours.py::detect_objects) into
    a single seat index 0..5, using:
      - LEFT / CENTER / RIGHT  <- horizontal thirds of the ROI (cx)
      - TOP  / BOTTOM          <- near/far split (distance_cm), i.e. which
                                  half of the section the pillar sits in

WHAT THIS DOES NOT DO (left for section_observer.py / the planner)
    - It does not know which straightforward section is currently in view.
    - It does not decide when a section "starts" or "ends".
    - It does not accumulate seats across frames into a full 6-slot vector.

>>> ASSUMPTION FLAG <<< (copied forward from obstacle.py's own flag)
"top" = entrance edge of the section, "bottom" = exit edge, is INFERRED
from Figure 3 and NOT yet confirmed against the physical field or camera
mount. The near/far <-> top/bottom mapping below assumes the robot drives
INTO a section nose-first, so a pillar that is currently FAR is nearer the
entrance (top row) and a pillar that is NEAR is closer to the exit (bottom
row) as the robot approaches it. This has NOT been validated on a real
track. If seat vectors come out mirrored top<->bottom during calibration,
flip TOP_BOTTOM_SPLIT_CM's meaning (swap the two branches below) rather
than touching obstacle.py's CARD_CATALOG.
"""

from __future__ import annotations
from typing import Optional

from world_model.obstacle import EMPTY, RED, GREEN, TL, TC, TR, BL, BC, BR

# Column boundaries as fractions of ROI width — pillar cx below LEFT_FRAC
# of the width is LEFT column, above RIGHT_FRAC is RIGHT column, else CENTER.
LEFT_FRAC = 1.0 / 3.0
RIGHT_FRAC = 2.0 / 3.0

# Near/far split, in the same cm units camera/distance.py returns.
# TODO: calibrate against the real 1000mm / 600mm section lengths once the
# camera + track are physically available (see the assumption flag above).
# Starting point only: half the nominal 1000mm corridor length.
TOP_BOTTOM_SPLIT_CM = 50.0

_SEAT_INDEX_BY_ROW_COL = {
    ("TOP", "LEFT"):    TL,
    ("TOP", "CENTER"):  TC,
    ("TOP", "RIGHT"):   TR,
    ("BOTTOM", "LEFT"):  BL,
    ("BOTTOM", "CENTER"): BC,
    ("BOTTOM", "RIGHT"):  BR,
}


def classify_column(cx: int, roi_width: int) -> str:
    """cx (pixels) -> 'LEFT' | 'CENTER' | 'RIGHT' third of the ROI."""
    if roi_width <= 0:
        raise ValueError(f"roi_width must be positive, got {roi_width}")
    frac = cx / roi_width
    if frac < LEFT_FRAC:
        return "LEFT"
    if frac > RIGHT_FRAC:
        return "RIGHT"
    return "CENTER"


def classify_row(distance_cm: float, split_cm: float = TOP_BOTTOM_SPLIT_CM) -> str:
    """distance_cm (from camera/distance.py) -> 'TOP' (far) | 'BOTTOM' (near)."""
    return "TOP" if distance_cm >= split_cm else "BOTTOM"


def classify_seat(cx: int, distance_cm: float, roi_width: int,
                   split_cm: float = TOP_BOTTOM_SPLIT_CM) -> int:
    """
    Single detection -> seat index 0..5 (TL,TC,TR,BL,BC,BR order — see
    world_model/obstacle.py for what that order means).
    """
    row = classify_row(distance_cm, split_cm)
    col = classify_column(cx, roi_width)
    return _SEAT_INDEX_BY_ROW_COL[(row, col)]


def classify_detections(detections: list[dict], color: int, roi_width: int,
                         split_cm: float = TOP_BOTTOM_SPLIT_CM) -> list[tuple[int, int]]:
    """
    Batch version for a full frame's worth of same-colour detections
    (camera/contours.py::detect_objects output for one mask).

    Returns a list of (seat_index, color) pairs — one per detection. Color
    is passed through unchanged (RED or GREEN from world_model.obstacle)
    so the caller (section_observer.py) doesn't need a second lookup.
    """
    if color not in (RED, GREEN):
        raise ValueError(f"color must be RED or GREEN, got {color}")

    out = []
    for det in detections:
        seat = classify_seat(det["cx"], det["distance"], roi_width, split_cm)
        out.append((seat, color))
    return out

