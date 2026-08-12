"""
Focal length calibration — run this on the Pi after swapping cameras
(or whenever REAL_PILLAR_WIDTH_MM / the lens changes).

WHY:
    camera/distance.py estimates distance with:
        distance_mm = (REAL_WIDTH_MM * FOCAL_LENGTH) / pixel_width
    FOCAL_LENGTH is camera+lens specific ("focal length in pixels"),
    so a value tuned for the old Pi camera is wrong for the C270.

HOW:
    1. Place a WRO pillar (or anything of known width) at a measured,
       known distance from the camera lens. Standing it straight on,
       facing the camera, is important — angled objects give a
       shorter apparent width and throw off the result.
    2. Run this script.
    3. Drag a box tightly around the pillar's width in the window
       that pops up, press ENTER/SPACE to confirm, then ESC.
    4. It prints the pixel width and the FOCAL_LENGTH to put in
       camera/distance.py.

For a more reliable number, repeat at 2-3 different known distances
and average the resulting FOCAL_LENGTH values.

Usage:
    python3 calibrate_focal_length.py --distance_cm 50
"""

import argparse
import cv2

from camera.capture import init_camera, read_frame, release_camera
from camera.distance import REAL_PILLAR_WIDTH_MM


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--distance_cm",
        type=float,
        required=True,
        help="Known, measured distance from camera lens to the pillar, in cm",
    )
    args = parser.parse_args()

    known_distance_mm = args.distance_cm * 10.0

    cam = init_camera()

    print("Position the pillar, then press any key when the preview looks good...")

    frame = None
    while True:
        frame = read_frame(cam)
        if frame is None:
            continue
        cv2.imshow("Calibration - press any key to capture", frame)
        if cv2.waitKey(1) != -1:
            break

    cv2.destroyWindow("Calibration - press any key to capture")

    print("Drag a box tightly around the pillar's WIDTH, then press ENTER/SPACE.")
    box = cv2.selectROI("Select pillar width", frame, showCrosshair=True)
    cv2.destroyAllWindows()

    pixel_width = box[2]  # (x, y, w, h)

    if pixel_width <= 0:
        print("[ERROR] No selection made — nothing to calibrate.")
        release_camera(cam)
        return

    focal_length = (pixel_width * known_distance_mm) / REAL_PILLAR_WIDTH_MM

    print("\n--- CALIBRATION RESULT ---")
    print(f"Measured pixel width : {pixel_width}px")
    print(f"Known distance        : {args.distance_cm} cm")
    print(f"=> FOCAL_LENGTH        = {focal_length:.1f}")
    print("\nPut this value in camera/distance.py:")
    print(f"    FOCAL_LENGTH = {focal_length:.1f}")
    print("\nTip: repeat this at 2-3 distances and average the results.\n")

    release_camera(cam)


if __name__ == "__main__":
    main()
