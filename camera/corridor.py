"""
corridor.py
WRO 2026 Future Engineers — wall/corridor centering for Open Challenge
(and as a no-pillar-visible fallback during the Obstacle Challenge).

GAP #1 FIX: previously `steering_value` only had a source when a red or
green pillar was in view (main.py's `if closest_red: ... elif
closest_green: ...`). Open Challenge rounds have NO pillars at all (WRO
Game Rules 2026 §5 / §8 — "During Open Challenge rounds, the racetrack
will have no traffic signs"), so the vehicle had literally nothing
steering it and would drive straight into whichever wall it happened to
be pointed at.

This module gives the vehicle a second, independent steering source:
corridor centering off the track's black walls (interior + exterior are
both black — rule §13.4/§13.6). It samples several horizontal rows in a
binary "is this wall" mask (see camera/hsv.py::get_black_mask), finds the
nearest wall pixel left and right of image-center on each row, and
averages the resulting corridor midpoints, weighted toward the row
closest to the vehicle (least perspective distortion, most immediately
actionable for steering).

main.py uses this as the steering source whenever no red/green pillar
is currently tracked — which is ALWAYS in Open Challenge, and only when
no sign is in view during Obstacle Challenge.
"""

from __future__ import annotations
from typing import Optional
import numpy as np

# Rows to sample, as fractions of frame height, closest-to-vehicle first.
# Weight favors the bottom row.
SAMPLE_ROW_FRACS = (0.95, 0.85, 0.70)
ROW_WEIGHTS = (0.5, 0.3, 0.2)

MIN_WALL_RUN_PX = 3  # ignore single-pixel noise when scanning a row

# Fallback half-corridor-width (px) used when only ONE wall is visible on
# a sampled row. Retune on-track once real corridor widths (WRO §8: 1000mm
# or 600mm +/- tolerance) have been measured in your camera's pixel space.
NOMINAL_HALF_WIDTH_PX = 140.0

# ---------------------------------------------------------------------------
# HC-SR04 side-ultrasonic fallback (left/right, see firmware's "NOTE ON
# HC-SR04 USAGE"). This is a LAST-RESORT source only, used when the
# vision estimate above finds NO wall pixels at all on any sampled row
# (e.g. mid-corner, or a badly lit frame) -- it never overrides a real
# vision reading.
#
# PLACEHOLDER -- NOT TRACK-CALIBRATED. The cm->px conversion below
# assumes a corridor half-width of ULTRASONIC_NOMINAL_HALF_WIDTH_CM,
# which is a rough midpoint of the WRO §8 corridor widths (1000mm /
# 600mm +/- tolerance -> roughly 30-50cm half-width) and has NOT been
# measured against this camera's actual px-per-cm on the physical
# field. Retune ULTRASONIC_NOMINAL_HALF_WIDTH_CM (and re-derive
# ULTRASONIC_PX_PER_CM) once real on-track measurements exist -- see
# the punch-list item this fixes. Until then, ULTRASONIC_FALLBACK_CONFIDENCE
# is deliberately capped low so a mistuned placeholder can only ever
# nudge steering gently, never drive it with false confidence.
ULTRASONIC_NOMINAL_HALF_WIDTH_CM = 40.0
ULTRASONIC_PX_PER_CM = NOMINAL_HALF_WIDTH_PX / ULTRASONIC_NOMINAL_HALF_WIDTH_CM
ULTRASONIC_FALLBACK_CONFIDENCE = 0.2  # always below a real vision reading's minimum


def _find_wall_edge(row: np.ndarray, start: int, step: int, min_run: int = MIN_WALL_RUN_PX):
    """
    Scan `row` (1-D uint8 array, 255 = wall) from `start` in direction
    `step` (+1 or -1) and return the index of the first pixel that
    begins a run of at least `min_run` consecutive wall pixels, or None
    if the scan runs off the array without finding one.
    """
    n = len(row)
    i = start
    run = 0
    while 0 <= i < n:
        if row[i] >= 128:
            run += 1
            if run >= min_run:
                return i - step * (min_run - 1)
        else:
            run = 0
        i += step
    return None


def estimate_corridor(wall_mask: np.ndarray, frame_width: int, frame_height: int):
    """
    wall_mask: binary mask (0/255), where 255 marks a wall pixel.

    Returns:
        {
          "center_x":          float px of the corridor midpoint, or None,
          "corridor_width_px": float (right_wall_x - left_wall_x), or None,
          "left_wall_x":       float or None,
          "right_wall_x":      float or None,
          "confidence":        0..1 — fraction of sampled rows that saw BOTH walls,
          "rows_used":         list[int] — the actual pixel rows sampled (debug/draw)
        }
    """
    center_col = frame_width // 2

    midpoints = []
    widths = []
    weights_used = []
    left_last = right_last = None
    rows_used = []

    for frac, weight in zip(SAMPLE_ROW_FRACS, ROW_WEIGHTS):
        row_y = min(frame_height - 1, max(0, int(frac * (frame_height - 1))))
        rows_used.append(row_y)
        row = wall_mask[row_y, :]

        left_x = _find_wall_edge(row, center_col, -1)
        right_x = _find_wall_edge(row, center_col, +1)

        if left_x is None and right_x is None:
            continue

        if left_x is not None and right_x is not None:
            midpoints.append((left_x + right_x) / 2.0)
            widths.append(right_x - left_x)
            weights_used.append(weight)
            left_last, right_last = left_x, right_x
        elif left_x is not None:
            # Only the left wall visible — assume a nominal corridor width
            # so a single missing wall doesn't kill steering entirely;
            # down-weighted so it influences less than a confirmed row.
            midpoints.append(left_x + NOMINAL_HALF_WIDTH_PX)
            weights_used.append(weight * 0.5)
            left_last = left_x
        else:
            midpoints.append(right_x - NOMINAL_HALF_WIDTH_PX)
            weights_used.append(weight * 0.5)
            right_last = right_x

    rows_sampled = len(SAMPLE_ROW_FRACS)
    rows_with_both_walls = len(widths)

    if not midpoints:
        return {
            "center_x": None, "corridor_width_px": None,
            "left_wall_x": None, "right_wall_x": None,
            "confidence": 0.0, "rows_used": rows_used,
        }

    total_weight = sum(weights_used)
    center_x = sum(m * w for m, w in zip(midpoints, weights_used)) / total_weight
    corridor_width_px = (sum(widths) / len(widths)) if widths else None
    confidence = rows_with_both_walls / rows_sampled

    return {
        "center_x": center_x,
        "corridor_width_px": corridor_width_px,
        "left_wall_x": left_last,
        "right_wall_x": right_last,
        "confidence": confidence,
        "rows_used": rows_used,
    }


def corridor_error(corridor: dict, frame_width: int):
    """
    Turn estimate_corridor()'s result into a signed pixel error suitable
    for control/pid.py::PIDController.compute() — positive means the
    corridor center is to the RIGHT of image-center (steer right).
    Returns None if no corridor could be estimated this frame (caller
    should hold the last steering value rather than snapping to 0 — see
    main.py's `last_steering_value` fallback).
    """
    if corridor["center_x"] is None:
        return None
    return corridor["center_x"] - (frame_width / 2.0)


def _valid_reading(distance_cm: Optional[float]) -> bool:
    """A distance reading counts as usable only if it's a real positive
    number -- mirrors control/proximity.py's treatment of a 0/negative
    sentinel (timed-out ping) as "no reading," not "zero distance."""
    return distance_cm is not None and distance_cm > 0


def ultrasonic_corridor_error(left_distance_cm: Optional[float],
                               right_distance_cm: Optional[float]):
    """
    PLACEHOLDER side-ultrasonic fallback for corridor centering (see the
    module-level PLACEHOLDER comment above ULTRASONIC_NOMINAL_HALF_WIDTH_CM).

    Meant to be called ONLY when estimate_corridor() + corridor_error()
    above return None this frame -- i.e. vision found no wall pixels at
    all on any sampled row. It is never meant to outrank a real vision
    reading; main.py should only reach for this as the last fallback
    before holding the last steering value.

    Sign convention matches corridor_error(): positive means the
    corridor center is to the RIGHT of the vehicle (steer right). If the
    left sensor reads a shorter distance than the right, the vehicle is
    closer to the left wall than the right, so the corridor center is to
    the vehicle's right -> positive error.

    Returns (error_px, confidence), or None if neither reading is
    currently usable.
    """
    have_left = _valid_reading(left_distance_cm)
    have_right = _valid_reading(right_distance_cm)

    if not have_left and not have_right:
        return None

    if have_left and have_right:
        error_cm = right_distance_cm - left_distance_cm
    elif have_left:
        # Only the left sensor -- assume the nominal half-width on the
        # (unseen) right side, same down-weighted-fallback spirit as
        # estimate_corridor()'s single-wall branch above.
        error_cm = ULTRASONIC_NOMINAL_HALF_WIDTH_CM - left_distance_cm
    else:
        error_cm = right_distance_cm - ULTRASONIC_NOMINAL_HALF_WIDTH_CM

    error_px = error_cm * ULTRASONIC_PX_PER_CM
    return error_px, ULTRASONIC_FALLBACK_CONFIDENCE
