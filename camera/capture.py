import sys
import cv2

# =====================================
# CAMERA SETUP — Logitech C270 (USB UVC webcam)
# =====================================
# Switched from the Raspberry Pi Camera Module (picamera2 / OV5647)
# to a Logitech C270. The C270 is a standard USB webcam that shows
# up as a V4L2 device (e.g. /dev/video0 on the Pi), so we talk to it
# through OpenCV's VideoCapture + V4L2 backend instead of picamera2.
#
# Notes on the C270 vs the old Pi camera:
#   - Fixed-focus lens (no autofocus hunting) — good for stable
#     pixel widths used in distance estimation.
#   - Native resolutions include 640x480 @ 30fps (MJPG), which is
#     what the rest of the pipeline (ROI crop, FOV math) expects.
#   - Field of view / colour response are different from the OV5647,
#     so CAMERA_FOV (camera/angle.py) and the HSV ranges
#     (config/hsv_config.py) need to be re-tuned for this camera.
#     Re-run hsv_tuner.py to get new colour ranges.
# =====================================

CAMERA_INDEX  = 0        # /dev/video0 — change if the C270 enumerates elsewhere
CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480
CAMERA_FPS    = 30

# =====================================
# MANUAL EXPOSURE / WHITE BALANCE
# Auto exposure/WB will drift as lighting or the scene changes,
# which throws off HSV colour thresholds mid-run. Lock them like
# we did on the Pi camera. Set MANUAL_CONTROLS = False to fall back
# to the C270's auto exposure/WB if manual locking misbehaves on
# your OS/driver (support for these UVC controls varies).
# =====================================

MANUAL_CONTROLS = True

# 0.0-1.0 range as used by OpenCV's V4L2 backend for these props.
# Start here, then tune on-track under your actual lighting.
EXPOSURE      = -6      # roughly "fast/dim" on the V4L2 log2 exposure scale
WB_TEMPERATURE = 4600   # Kelvin — tune ColourGain-style via this instead


def init_camera():

    cam = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

    if not cam.isOpened():
        print(f"[ERROR] Could not open camera at index {CAMERA_INDEX}")
        sys.exit(1)

    # MJPG gives the C270 its full frame rate at 640x480.
    # Without this some UVC drivers fall back to a much slower YUYV mode.
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cam.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)

    if MANUAL_CONTROLS:

        # Lock auto exposure (0.25 == manual mode on most V4L2 UVC drivers)
        cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cam.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE)

        # Lock auto white balance
        cam.set(cv2.CAP_PROP_AUTO_WB, 0)
        cam.set(cv2.CAP_PROP_WB_TEMPERATURE, WB_TEMPERATURE)

    else:
        cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # auto
        cam.set(cv2.CAP_PROP_AUTO_WB, 1)

    # Warm up — first few frames from a UVC cam are often stale/dark
    # while auto controls (and our manual overrides) settle.
    for _ in range(5):
        cam.read()

    return cam


def read_frame(cam):

    ok, frame = cam.read()

    if not ok or frame is None:
        return None

    return frame


def release_camera(cam):

    cam.release()
