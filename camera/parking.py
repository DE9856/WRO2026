"""
Magenta parking-marker detection (WRO 2026 rule §13.27).

Two magenta markers bound the parking lot entrance. This finds every
magenta blob in the mask, and — when at least two are visible — pairs
up the two largest and reports the midpoint between them so the robot
can centre itself for parallel parking, per Camera Guide §18
(parking mode: "searches for two magenta bounding boxes forming the
parking lot boundary and centers itself between them").
"""

import cv2

MIN_MARKER_AREA = 200


def find_markers(mask, min_area=MIN_MARKER_AREA):
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    markers = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        cx = x + w // 2
        cy = y + h // 2

        markers.append({
            "x": x, "y": y, "w": w, "h": h,
            "cx": cx, "cy": cy, "area": area,
        })

    # Largest first — the two nearest/most confident markers sort to the front.
    markers.sort(key=lambda m: m["area"], reverse=True)

    return markers


def locate_parking_lot(mask):
    """
    Returns None if fewer than two magenta markers are visible, else:
        {
          "left":     marker dict (smaller cx),
          "right":    marker dict (larger cx),
          "center_x": pixel midpoint between the two markers,
          "width_px": pixel distance between them
        }
    """

    markers = find_markers(mask)

    if len(markers) < 2:
        return None

    top_two = markers[:2]
    top_two.sort(key=lambda m: m["cx"])  # left marker first, right marker second

    left, right = top_two

    return {
        "left": left,
        "right": right,
        "center_x": (left["cx"] + right["cx"]) // 2,
        "width_px": right["cx"] - left["cx"],
    }
