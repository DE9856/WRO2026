"""
Corner-line detection — ORANGE / BLUE track boundary lines.

WRO 2026 marks the inside edge of certain corners with a coloured line
(orange or blue). Detecting which colour is currently visible, and on
which side of the frame, gives the robot an early signal for which way
the upcoming corner turns — before pillar geometry alone could tell it.

This reuses the same "find the biggest blob" contour approach as the
rest of camera/contours.py rather than a separate Canny+Hough line
pipeline, so it tunes with the exact same hsv_tuner.py workflow as
every other colour and stays consistent with the rest of the stack.
If you want the Canny+Hough lateral-error style pipeline described in
the Overall Guide (§06) instead/as well, `hough_lines()` below gives
you that as a drop-in alternative — see its docstring.
"""

import math
import cv2

MIN_LINE_AREA = 300


def _largest_blob(mask, min_area=MIN_LINE_AREA):
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    best = None
    best_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        if area > best_area:
            best_area = area
            best = cnt

    if best is None:
        return None

    x, y, w, h = cv2.boundingRect(best)
    cx = x + w // 2
    cy = y + h // 2

    return {"x": x, "y": y, "w": w, "h": h, "cx": cx, "cy": cy, "area": best_area}


def detect_corner_line(orange_mask, blue_mask, roi_width):
    """
    Inspect the ORANGE and BLUE masks and report which colour line
    (if any) is visible, which side of the frame it's on, and what
    phase of a corner it signals:

        BLUE   -> corner STARTING (about to enter a turn)
        ORANGE -> corner ENDING   (about to straighten out)

    Returns:
        {
          "color": "ORANGE" | "BLUE" | None,
          "side":  "LEFT" | "RIGHT" | None,        # where the blob sits in-frame
          "phase": "ENTERING" | "EXITING" | None,   # corner-phase hint
          "blob":  {x,y,w,h,cx,cy,area} | None
        }

    NOTE: this tells you a corner is starting or ending, not which way
    it turns — that still comes from pillar/geometry logic or the mat
    layout itself. Don't steer left/right off `phase` alone.
    """

    orange_blob = _largest_blob(orange_mask)
    blue_blob = _largest_blob(blue_mask)

    if orange_blob and blue_blob:
        # Both visible — trust whichever blob is larger (closer / more certain).
        if orange_blob["area"] >= blue_blob["area"]:
            chosen_color, blob = "ORANGE", orange_blob
        else:
            chosen_color, blob = "BLUE", blue_blob
    elif orange_blob:
        chosen_color, blob = "ORANGE", orange_blob
    elif blue_blob:
        chosen_color, blob = "BLUE", blue_blob
    else:
        return {"color": None, "side": None, "phase": None, "blob": None}

    side = "LEFT" if blob["cx"] < roi_width // 2 else "RIGHT"

    PHASE_BY_COLOR = {
        "BLUE": "ENTERING",
        "ORANGE": "EXITING",
    }

    phase = PHASE_BY_COLOR[chosen_color]

    return {"color": chosen_color, "side": side, "phase": phase, "blob": blob}


def hough_lines(mask, min_line_length=40, max_line_gap=10,
                 canny_low=50, canny_high=150):
    """
    Optional alternative front-end matching the Overall Guide §06
    pipeline: Canny edge detection + probabilistic Hough transform,
    for teams that want lateral-error-from-line-angle steering rather
    than blob-centroid steering. Feed it a single-colour mask (e.g.
    get_orange_mask(hsv) or a combined orange|blue mask).

    Returns a list of (x1, y1, x2, y2) line segments, or [] if none found.
    """
    edges = cv2.Canny(mask, canny_low, canny_high)

    lines = cv2.HoughLinesP(
        edges,
        1,
        math.pi / 180,
        threshold=40,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )

    if lines is None:
        return []

    return [tuple(line[0]) for line in lines]
