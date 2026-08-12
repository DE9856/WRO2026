"""
warp.py
WRO 2026 Future Engineers — perspective ("bird's-eye") transform.

GAP #4 FIX: the Camera Guide's Bird's-Eye Warp step (§04A) was
documented but never implemented — every distance/steering/corridor
computation reasoned in raw, perspective-distorted ROI pixel space
(near objects spread wide across many pixels, far objects compressed
into few). A bird's-eye warp re-projects the ROI onto a top-down view
where pixel distances are roughly uniform regardless of how far down
the track they are — this is what makes corridor_width_px
(camera/corridor.py, world_model/track.py) directly comparable frame to
frame, and eventually comparable to the rulebook's real-world
1000mm/600mm corridor widths (WRO Game Rules 2026 §8) once calibrated.

CALIBRATION
    WARP_SRC below are four ROI-pixel corners of a real rectangle on
    the track floor (e.g. mark a 400mm x 400mm square with tape and
    click its four corners in the ROI window), in TL, TR, BR, BL order.
    THESE ARE PLACEHOLDERS scaled to the current 480x300 ROI geometry —
    recalibrate for your actual camera mount angle/height before
    trusting corridor_width_cm() in real units. Until then, everything
    downstream still works correctly in *relative* pixel terms — corridor
    centering (camera/corridor.py) doesn't need real-world calibration
    to function; only the cm conversion does.
"""

from __future__ import annotations
from typing import Optional
import numpy as np
import cv2

# Placeholder source quad (ROI pixel space, 480x300 ROI) — a trapezoid
# roughly matching where a straight track corridor appears under a
# forward, tilted-down camera mount. TL, TR, BR, BL order.
WARP_SRC = np.float32([
    [140, 40],    # top-left
    [340, 40],    # top-right
    [460, 299],   # bottom-right
    [20, 299],    # bottom-left
])

# Destination: a rectangle in the warped output, giving a fixed pixel
# scale we can treat as a uniform ground plane.
WARP_OUT_WIDTH = 480
WARP_OUT_HEIGHT = 480

WARP_DST = np.float32([
    [0, 0],
    [WARP_OUT_WIDTH - 1, 0],
    [WARP_OUT_WIDTH - 1, WARP_OUT_HEIGHT - 1],
    [0, WARP_OUT_HEIGHT - 1],
])

# PX_PER_MM: fill in during calibration (see module docstring) by warping
# a known real-world distance and dividing the resulting warped pixel
# span by it. Stays None until calibrated — corridor_width_cm() below
# returns None rather than a silently-wrong number until this is set.
PX_PER_MM: Optional[float] = None


def get_warp_matrix(src: np.ndarray = WARP_SRC, dst: np.ndarray = WARP_DST):
    return cv2.getPerspectiveTransform(src, dst)


_M = get_warp_matrix()


def warp_frame(frame: np.ndarray, M: Optional[np.ndarray] = None,
               out_size=(WARP_OUT_WIDTH, WARP_OUT_HEIGHT)):
    """Apply the bird's-eye perspective warp to a ROI-sized BGR frame or
    single-channel mask (e.g. camera/hsv.py::get_black_mask output)."""
    matrix = M if M is not None else _M
    return cv2.warpPerspective(frame, matrix, out_size)


def warp_point(x: float, y: float, M: Optional[np.ndarray] = None):
    """Warp a single (x, y) ROI-pixel point into bird's-eye space."""
    matrix = M if M is not None else _M
    pt = np.array([[[x, y]]], dtype=np.float32)
    warped = cv2.perspectiveTransform(pt, matrix)
    return float(warped[0, 0, 0]), float(warped[0, 0, 1])


def corridor_width_cm(corridor_width_px: Optional[float]) -> Optional[float]:
    """Convert a warped-space corridor width in px to real cm, IF
    PX_PER_MM has been calibrated (see module docstring). Returns None
    (never a silently-wrong guess) otherwise."""
    if corridor_width_px is None or PX_PER_MM is None:
        return None
    return (corridor_width_px / PX_PER_MM) / 10.0

