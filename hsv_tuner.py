"""
HSV Tuner — run this on the robot to find colour ranges for ALL FIVE
tracked colours (RED, GREEN, MAGENTA, ORANGE, BLUE) under your actual
lighting.

Usage:
    python3 hsv_tuner.py

Controls:
    [ / ]   -> cycle to the previous / next colour
    x       -> (RED only) toggle between its two hue ranges -- RED wraps
               hue 0, so it needs a low-hue range AND a high-hue range,
               tune and save both
    Trackbars -> live H/S/V min & max for whichever colour is active
    s       -> save the current trackbar values for the active colour
    p       -> print every colour's current saved ranges to the terminal
    ESC     -> quit

Saved values are written to config/hsv_ranges.json and are picked up
automatically by config/hsv_config.py the next time it's imported
(e.g. next time you run main.py) -- no code edits needed.
"""

import cv2
import numpy as np

from camera.capture import init_camera, read_frame, release_camera
from config.hsv_config import COLOR_ORDER, get_ranges, save_ranges

state = {
    "color_idx": 0,
    "red_range_idx": 0,   # 0 = low-hue range (0-10ish), 1 = high-hue wrap range (170-180ish)
}


def nothing(x):
    pass


cv2.namedWindow("Tuner")
cv2.createTrackbar("H min", "Tuner", 0, 180, nothing)
cv2.createTrackbar("H max", "Tuner", 180, 180, nothing)
cv2.createTrackbar("S min", "Tuner", 60, 255, nothing)
cv2.createTrackbar("S max", "Tuner", 255, 255, nothing)
cv2.createTrackbar("V min", "Tuner", 60, 255, nothing)
cv2.createTrackbar("V max", "Tuner", 255, 255, nothing)


def active_color():
    return COLOR_ORDER[state["color_idx"]]


def load_trackbars_from_config():
    color = active_color()
    ranges = get_ranges(color)

    idx = state["red_range_idx"] if color == "RED" else 0
    idx = min(idx, len(ranges) - 1)

    r = ranges[idx]
    lo, hi = r["lower"], r["upper"]

    cv2.setTrackbarPos("H min", "Tuner", lo[0])
    cv2.setTrackbarPos("H max", "Tuner", hi[0])
    cv2.setTrackbarPos("S min", "Tuner", lo[1])
    cv2.setTrackbarPos("S max", "Tuner", hi[1])
    cv2.setTrackbarPos("V min", "Tuner", lo[2])
    cv2.setTrackbarPos("V max", "Tuner", hi[2])


load_trackbars_from_config()

cam = init_camera()

print(__doc__)

while True:

    frame = read_frame(cam)
    if frame is None:
        continue

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    h_min = cv2.getTrackbarPos("H min", "Tuner")
    h_max = cv2.getTrackbarPos("H max", "Tuner")
    s_min = cv2.getTrackbarPos("S min", "Tuner")
    s_max = cv2.getTrackbarPos("S max", "Tuner")
    v_min = cv2.getTrackbarPos("V min", "Tuner")
    v_max = cv2.getTrackbarPos("V max", "Tuner")

    lower = np.array([h_min, s_min, v_min])
    upper = np.array([h_max, s_max, v_max])

    mask = cv2.inRange(hsv, lower, upper)
    result = cv2.bitwise_and(frame, frame, mask=mask)

    color = active_color()
    label = color if color != "RED" else f"RED (range {state['red_range_idx'] + 1}/2)"

    cv2.putText(frame, f"Tuning: {label}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(frame, "[ / ] colour   x red-range   s save   p print   ESC quit",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    cv2.imshow("Tuner", frame)
    cv2.imshow("Mask", mask)
    cv2.imshow("Result", result)

    key = cv2.waitKey(1) & 0xFF

    if key == 27:  # ESC
        break

    elif key == ord('['):
        state["color_idx"] = (state["color_idx"] - 1) % len(COLOR_ORDER)
        load_trackbars_from_config()

    elif key == ord(']'):
        state["color_idx"] = (state["color_idx"] + 1) % len(COLOR_ORDER)
        load_trackbars_from_config()

    elif key == ord('x') and color == "RED":
        state["red_range_idx"] = 1 - state["red_range_idx"]
        load_trackbars_from_config()

    elif key == ord('s'):
        new_range = {
            "lower": [h_min, s_min, v_min],
            "upper": [h_max, s_max, v_max],
        }

        if color == "RED":
            ranges = list(get_ranges("RED"))  # copy, keep the other range intact
            ranges[state["red_range_idx"]] = new_range
        else:
            ranges = [new_range]

        save_ranges(color, ranges)

    elif key == ord('p'):
        for c in COLOR_ORDER:
            print(c, get_ranges(c))

release_camera(cam)
cv2.destroyAllWindows()
