"""
HSV Tuner — run this on the Pi to find the right colour ranges
for your lighting conditions.

Usage:
    python3 hsv_tuner.py

Controls:
    Trackbars → adjust H/S/V min and max
    Press 'r'  → print RED ranges to terminal
    Press 'g'  → print GREEN ranges to terminal
    Press ESC  → quit
"""

import cv2
import numpy as np
from camera.capture import init_camera, read_frame, release_camera

# =====================================
# TRACKBAR SETUP
# =====================================

def nothing(x):
    pass

cv2.namedWindow("Tuner")
cv2.createTrackbar("H min", "Tuner",   0, 180, nothing)
cv2.createTrackbar("H max", "Tuner", 180, 180, nothing)
cv2.createTrackbar("S min", "Tuner",  60, 255, nothing)
cv2.createTrackbar("S max", "Tuner", 255, 255, nothing)
cv2.createTrackbar("V min", "Tuner",  60, 255, nothing)
cv2.createTrackbar("V max", "Tuner", 255, 255, nothing)

cam = init_camera()

print("Controls: 'r' print red ranges | 'g' print green ranges | ESC quit")

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

    mask   = cv2.inRange(hsv, lower, upper)
    result = cv2.bitwise_and(frame, frame, mask=mask)

    cv2.imshow("Tuner",  frame)
    cv2.imshow("Mask",   mask)
    cv2.imshow("Result", result)

    key = cv2.waitKey(1) & 0xFF

    if key == 27:   # ESC
        break

    elif key == ord('r'):
        print("\n--- RED CONFIG ---")
        print(f"RED_LOWER1 = np.array([{h_min}, {s_min}, {v_min}])")
        print(f"RED_UPPER1 = np.array([{h_max}, {s_max}, {v_max}])")
        print("(Set a second range for the other red hue band if needed)\n")

    elif key == ord('g'):
        print("\n--- GREEN CONFIG ---")
        print(f"GREEN_LOWER = np.array([{h_min}, {s_min}, {v_min}])")
        print(f"GREEN_UPPER = np.array([{h_max}, {s_max}, {v_max}])\n")

release_camera(cam)
cv2.destroyAllWindows()